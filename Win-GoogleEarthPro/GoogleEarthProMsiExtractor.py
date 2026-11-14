#!/usr/local/autopkg/python
"""Cut the Windows Installer database out of the Google Earth Pro EXE.

The file that Google serves at the fixed address is a PE32 wrapper with no
version resource (the first run under AutoPkg 2.9.0, on 2026-11-13, stopped at
WindowsExeVersion for that reason). 7-Zip's listing of the same file, the same
day, showed one resource of the type BINARY with the name ID_MSI (language
1033, 63475712 bytes): a Windows Installer database for Google Earth Pro. The
recipe publishes that MSI, not the wrapper, so that the importers read the
version from the MSI itself.

This processor reads the PE file's resource directory in pure Python. It runs
no program, uses no network, and never executes the file. It finds the one
entry of the root whose NAME is BINARY (a named entry, not a number), in it the
one entry named ID_MSI, and in that exactly one language entry, which must be a
data entry. The data must lie inside the raw data of its section and inside the
file, be at most MAX_MSI_BYTES long, and begin with the compound file signature
D0 CF 11 E0 A1 B1 1A E1 that every MSI begins with.

The bytes are copied as they are into <the EXE's name without .exe>.msi beside
the EXE: through a temporary file in the same folder and a rename, so that no
partial file is left. A link at the target is refused. The same EXE gives the
same MSI, byte for byte, so the importers' "Nothing new" (by hash) holds.

What this proves: nothing about where the file came from. The MSI is a part
cut out of a download that is NOT verified. It outputs:

    pathname                         the MSI (the EXE's path before)
    googleearthpro_wrapper_pathname  the EXE

No output is set, and no MSI is left, unless every check passed.
"""
import os
import struct
import tempfile

from autopkglib import Processor, ProcessorError

__all__ = ["GoogleEarthProMsiExtractor", "find_msi_resource", "extract_msi", "msi_path_for"]

DOS_HEADER_BYTES = 64
DOS_MAGIC = b"MZ"
LFANEW_OFFSET = 0x3C
PE_SIGNATURE = b"PE\0\0"
COFF_HEADER_BYTES = 20
SECTION_HEADER_BYTES = 40
# The Windows loader accepts at most 96 sections.
MAX_SECTIONS = 96

MAGIC_PE32 = 0x10B
MAGIC_PE32_PLUS = 0x20B
# Bytes of the optional header before its data directories.
FIXED_OPTIONAL_BYTES = {MAGIC_PE32: 96, MAGIC_PE32_PLUS: 112}
DATA_DIRECTORY_BYTES = 8
RESOURCE_DIRECTORY_INDEX = 2

RESOURCE_DIRECTORY_BYTES = 16
RESOURCE_ENTRY_BYTES = 8
RESOURCE_DATA_ENTRY_BYTES = 16
# A directory of a real file has a few entries; more than this is refused.
MAX_DIRECTORY_ENTRIES = 4096
# A resource name is a short word; more characters than this is refused.
MAX_NAME_CHARACTERS = 256
HIGH_BIT = 0x80000000
LOW_31_BITS = 0x7FFFFFFF

TYPE_NAME = "BINARY"
RESOURCE_NAME = "ID_MSI"
# The MSI was 63475712 bytes on 2026-11-13, in a download of 100802200 bytes.
# More than this is not the file that the recipe was written for.
MAX_MSI_BYTES = 512 * 1024 * 1024
# Every Windows Installer database is an OLE compound file.
COMPOUND_FILE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
COPY_CHUNK_BYTES = 1024 * 1024
MSI_SUFFIX = ".msi"
READ_WRITE_BITS = 0o666


def read_exact(handle, file_size, offset, length, what):
    """Read exactly `length` bytes at `offset`, or raise ValueError. Nothing
    is read that the file does not hold."""
    if offset < 0 or length < 0 or offset + length > file_size:
        raise ValueError("the file is truncated: %s lies outside the file" % what)
    handle.seek(offset)
    data = handle.read(length)
    if len(data) != length:
        raise ValueError("the file is truncated: %s could not be read" % what)
    return data


def parse_headers(handle, file_size):
    """The sections and the resource directory's address of a PE file.

    Returns (sections, resource_rva). A section is a tuple (virtual_size,
    virtual_address, raw_size, raw_offset)."""
    dos = read_exact(handle, file_size, 0, DOS_HEADER_BYTES, "the DOS header")
    if dos[:2] != DOS_MAGIC:
        raise ValueError("not a PE file: no MZ header")
    (pe_offset,) = struct.unpack_from("<I", dos, LFANEW_OFFSET)
    if pe_offset < DOS_HEADER_BYTES:
        raise ValueError("not a PE file: the PE header starts inside the DOS header")
    head = read_exact(handle, file_size, pe_offset, 4 + COFF_HEADER_BYTES, "the PE header")
    if head[:4] != PE_SIGNATURE:
        raise ValueError("not a PE file: no PE signature")
    # machine, number of sections, time stamp, symbol table, symbols,
    # size of the optional header, characteristics
    (_machine, section_count, _stamp, _symbols, _symbol_count,
     optional_size, _flags) = struct.unpack_from("<HHIIIHH", head, 4)
    optional_offset = pe_offset + 4 + COFF_HEADER_BYTES

    if optional_size < 2:
        raise ValueError("not a usable PE file: it has no optional header")
    (magic,) = struct.unpack("<H", read_exact(handle, file_size, optional_offset, 2, "the optional header"))
    if magic not in FIXED_OPTIONAL_BYTES:
        raise ValueError("not a PE32 or PE32+ file: optional header magic 0x%X" % magic)
    fixed = FIXED_OPTIONAL_BYTES[magic]
    wanted = fixed + DATA_DIRECTORY_BYTES * (RESOURCE_DIRECTORY_INDEX + 1)
    if optional_size < fixed:
        raise ValueError("the optional header is too short")
    optional = read_exact(
        handle, file_size, optional_offset, min(optional_size, wanted), "the optional header"
    )
    (directory_count,) = struct.unpack_from("<I", optional, fixed - 4)
    if directory_count <= RESOURCE_DIRECTORY_INDEX or len(optional) < wanted:
        raise ValueError("the file has no resource directory")
    resource_rva, resource_size = struct.unpack_from(
        "<II", optional, fixed + DATA_DIRECTORY_BYTES * RESOURCE_DIRECTORY_INDEX
    )
    if resource_rva == 0 or resource_size == 0:
        raise ValueError("the file has no resource directory")

    if section_count == 0:
        raise ValueError("the file has no sections")
    if section_count > MAX_SECTIONS:
        raise ValueError("the file has %d sections (at most %d are accepted)" % (section_count, MAX_SECTIONS))
    table = read_exact(
        handle, file_size, optional_offset + optional_size, SECTION_HEADER_BYTES * section_count,
        "the section table",
    )
    sections = []
    for index in range(section_count):
        # name (8 bytes), virtual size, virtual address, raw size, raw offset
        sections.append(struct.unpack_from("<IIII", table, SECTION_HEADER_BYTES * index + 8))
    return sections, resource_rva


def file_offset_of(file_size, sections, rva, length, what):
    """The file offset of `length` bytes at a virtual address. The section is
    the one whose range holds the address; the bytes must lie in the section's
    raw data and in the file."""
    for virtual_size, virtual_address, raw_size, raw_offset in sections:
        if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
            inside = rva - virtual_address
            if inside + length > raw_size:
                raise ValueError("%s lies outside the raw data of its section" % what)
            offset = raw_offset + inside
            if offset + length > file_size:
                raise ValueError("the file is truncated: %s lies outside the file" % what)
            return offset
    raise ValueError("%s is at an address that no section holds" % what)


def read_at_rva(handle, file_size, sections, rva, length, what):
    offset = file_offset_of(file_size, sections, rva, length, what)
    return read_exact(handle, file_size, offset, length, what)


def read_resource_directory(handle, file_size, sections, rva, what):
    """The entries of one resource directory: a list of (name_or_id, offset,
    is_directory). A named entry has a name_or_id with the high bit set."""
    head = read_at_rva(handle, file_size, sections, rva, RESOURCE_DIRECTORY_BYTES, what)
    named, ids = struct.unpack_from("<HH", head, 12)
    total = named + ids
    if total == 0:
        raise ValueError("%s has no entries" % what)
    if total > MAX_DIRECTORY_ENTRIES:
        raise ValueError("%s has %d entries (at most %d are accepted)" % (what, total, MAX_DIRECTORY_ENTRIES))
    raw = read_at_rva(
        handle, file_size, sections, rva + RESOURCE_DIRECTORY_BYTES, RESOURCE_ENTRY_BYTES * total,
        "the entries of " + what,
    )
    entries = []
    for index in range(total):
        name, offset = struct.unpack_from("<II", raw, RESOURCE_ENTRY_BYTES * index)
        entries.append((name, offset & LOW_31_BITS, bool(offset & HIGH_BIT)))
    return entries


def read_entry_name(handle, file_size, sections, resource_rva, name_field):
    """The name of a named entry (a length in characters, then UTF-16), or
    None for an entry with a number."""
    if not name_field & HIGH_BIT:
        return None
    rva = resource_rva + (name_field & LOW_31_BITS)
    (length,) = struct.unpack("<H", read_at_rva(handle, file_size, sections, rva, 2, "the length of a resource name"))
    if length > MAX_NAME_CHARACTERS:
        raise ValueError("a resource name has %d characters (at most %d are accepted)" % (length, MAX_NAME_CHARACTERS))
    raw = read_at_rva(handle, file_size, sections, rva + 2, 2 * length, "a resource name")
    try:
        return raw.decode("utf-16-le")
    except UnicodeDecodeError:
        raise ValueError("a resource name is not valid UTF-16")


def only_named(handle, file_size, sections, resource_rva, entries, wanted, what):
    """The one entry named `wanted`, which must be a directory. None, two, or a
    data entry is an error."""
    found = [entry for entry in entries
             if read_entry_name(handle, file_size, sections, resource_rva, entry[0]) == wanted]
    if not found:
        raise ValueError("%s has no entry named %s" % (what, wanted))
    if len(found) > 1:
        raise ValueError("%s has %d entries named %s (exactly one is accepted)" % (what, len(found), wanted))
    _name, offset, is_directory = found[0]
    if not is_directory:
        raise ValueError("the entry named %s in %s is not a directory" % (wanted, what))
    return offset


def find_msi_resource(handle, file_size):
    """The file offset and the size of the BINARY/ID_MSI resource, after every
    check of the tree, the bounds, the size and the signature. Raises
    ValueError with a reason that is safe to show."""
    sections, resource_rva = parse_headers(handle, file_size)
    root = read_resource_directory(handle, file_size, sections, resource_rva, "the resource directory")
    type_offset = only_named(handle, file_size, sections, resource_rva, root, TYPE_NAME, "the resource directory")
    names = read_resource_directory(
        handle, file_size, sections, resource_rva + type_offset, "the %s resource directory" % TYPE_NAME
    )
    name_offset = only_named(
        handle, file_size, sections, resource_rva, names, RESOURCE_NAME, "the %s resource directory" % TYPE_NAME
    )
    languages = read_resource_directory(
        handle, file_size, sections, resource_rva + name_offset, "the language directory of %s" % RESOURCE_NAME
    )
    if len(languages) != 1:
        raise ValueError(
            "the language directory of %s has %d entries (exactly one is accepted)" % (RESOURCE_NAME, len(languages))
        )
    _language, entry_offset, is_directory = languages[0]
    if is_directory:
        raise ValueError("the language entry of %s is not a data entry" % RESOURCE_NAME)
    entry = read_at_rva(
        handle, file_size, sections, resource_rva + entry_offset, RESOURCE_DATA_ENTRY_BYTES,
        "the data entry of %s" % RESOURCE_NAME,
    )
    data_rva, data_size = struct.unpack_from("<II", entry, 0)
    if data_size == 0:
        raise ValueError("the %s resource is empty" % RESOURCE_NAME)
    if data_size > MAX_MSI_BYTES:
        raise ValueError(
            "the %s resource is %d bytes (at most %d are accepted)" % (RESOURCE_NAME, data_size, MAX_MSI_BYTES)
        )
    offset = file_offset_of(file_size, sections, data_rva, data_size, "the %s resource" % RESOURCE_NAME)
    head = read_exact(handle, file_size, offset, min(data_size, len(COMPOUND_FILE_SIGNATURE)),
                      "the start of the %s resource" % RESOURCE_NAME)
    if head != COMPOUND_FILE_SIGNATURE:
        raise ValueError(
            "the %s resource does not begin with the signature of a Windows Installer database" % RESOURCE_NAME
        )
    return offset, data_size


def msi_path_for(exe_path):
    """<the EXE's path without its extension>.msi"""
    stem, _extension = os.path.splitext(exe_path)
    return stem + MSI_SUFFIX


def extract_msi(exe_path, msi_path):
    """Write the MSI of `exe_path` to `msi_path` through a temporary file and a
    rename. Returns (exe size, msi size). Raises ValueError (the file) or
    OSError (the disk); nothing is left at `msi_path` that was not there,
    and no temporary file is left."""
    if os.path.realpath(msi_path) == os.path.realpath(exe_path):
        raise ValueError("the MSI would replace the EXE itself")
    if os.path.islink(msi_path):
        raise ValueError("%s is a link, which is refused" % os.path.basename(msi_path))
    if os.path.lexists(msi_path) and not os.path.isfile(msi_path):
        raise ValueError("%s exists and is not a file" % os.path.basename(msi_path))
    with open(exe_path, "rb") as handle:
        exe_size = os.fstat(handle.fileno()).st_size
        offset, size = find_msi_resource(handle, exe_size)
        folder = os.path.dirname(os.path.abspath(msi_path))
        descriptor, temporary = tempfile.mkstemp(
            prefix=".%s." % os.path.basename(msi_path), suffix=".tmp", dir=folder
        )
        try:
            with os.fdopen(descriptor, "wb") as out:
                handle.seek(offset)
                left = size
                while left:
                    chunk = handle.read(min(COPY_CHUNK_BYTES, left))
                    if not chunk:
                        raise ValueError("the file is truncated: the %s resource could not be read" % RESOURCE_NAME)
                    out.write(chunk)
                    left -= len(chunk)
                out.flush()
                os.fsync(out.fileno())
            if os.path.getsize(temporary) != size:
                raise ValueError("the MSI written has not the size of the resource")
            # A temporary file is readable by its owner only; the MSI gets the
            # read and write bits of the download, never an execute bit.
            os.chmod(temporary, os.fstat(handle.fileno()).st_mode & READ_WRITE_BITS)
            # Checked again just before the rename: a link made meanwhile is refused too.
            if os.path.islink(msi_path):
                raise ValueError("%s is a link, which is refused" % os.path.basename(msi_path))
            os.replace(temporary, msi_path)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
    return exe_size, size


class GoogleEarthProMsiExtractor(Processor):
    description = __doc__
    input_variables = {
        "pathname": {
            "required": True,
            "description": "Path to the downloaded Google Earth Pro EXE.",
        },
    }
    output_variables = {
        "pathname": {
            "description": "The MSI that was cut out of the EXE, beside it.",
        },
        "googleearthpro_wrapper_pathname": {
            "description": "The EXE that the MSI was cut out of.",
        },
    }

    def main(self):
        path = self.env.get("pathname")
        if not isinstance(path, str) or not path or not os.path.isfile(path):
            raise ProcessorError("pathname is not a file (it does not exist, or it is a folder): %r" % (path,))
        name = os.path.basename(path)
        target = msi_path_for(path)
        try:
            exe_size, msi_size = extract_msi(path, target)
        except ValueError as err:
            raise ProcessorError("%s: %s. No MSI was written." % (name, err))
        except OSError as err:
            raise ProcessorError("Could not cut the MSI out of %s: %s" % (path, err))

        self.env["googleearthpro_wrapper_pathname"] = path
        self.env["pathname"] = target
        self.output(
            "%s (%d bytes): wrote its %s/%s resource as %s (%d bytes)"
            % (name, exe_size, TYPE_NAME, RESOURCE_NAME, os.path.basename(target), msi_size)
        )


if __name__ == "__main__":
    processor = GoogleEarthProMsiExtractor()
    processor.execute_shell()
