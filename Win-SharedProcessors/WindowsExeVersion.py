#!/usr/local/autopkg/python
"""Read the version of a downloaded Windows .exe from the file itself.

Several installers are EXE files at a fixed address, with no version in the
address and no vendor hash. An importer needs a version label for an EXE,
and the label must be the one that a person reads in the file's properties:
the ProductVersion. This processor reads it from the PE file's version
resource (RT_VERSION, a VS_VERSIONINFO block), in pure Python. It runs no
program, writes nothing and uses no network.

Only the parts of the file that are needed are read: the headers, the section
table, the resource directory and the one version block (at most 1 MiB). The
whole file is never read.

The recipe stops (ProcessorError) when the file does not exist, is not a PE
file, has no resource directory or no version resource, when the version block
is not what its structure says, when a read would leave the file or the block,
or when the string table has neither a ProductVersion nor a FileVersion, or
when the label that would be chosen has no digit other than zero (a file whose
version resource says zeros has no version). A value is never guessed.

The version proves nothing about where the file came from: it is data in the
file. It only gives the label that the importer and the client compare.
"""
import os
import re
import struct

from autopkglib import Processor, ProcessorError

__all__ = ["WindowsExeVersion", "read_exe_version", "choose_version"]

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
RT_VERSION = 16
HIGH_BIT = 0x80000000
LOW_31_BITS = 0x7FFFFFFF

# A version block is a few kilobytes; more than this is an error.
MAX_VERSION_BYTES = 1024 * 1024
BLOCK_HEADER_BYTES = 6
FIXED_FILE_INFO_BYTES = 52
FIXED_FILE_INFO_SIGNATURE = 0xFEEF04BD
ROOT_KEY = "VS_VERSION_INFO"
STRING_FILE_INFO_KEY = "StringFileInfo"
TABLE_KEY_PATTERN = re.compile(r"[0-9A-Fa-f]{8}")
PRODUCT_VERSION_KEY = "ProductVersion"
FILE_VERSION_KEY = "FileVersion"
PRODUCT_NAME_KEY = "ProductName"

# A label that is made of numbers and dots only.
NUMERIC_VERSION_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+)*")
# A label made of numbers and dots has a version in it only when one digit is
# not zero. (Searched in the text: no number is converted, so a very long run
# of digits costs nothing.)
NONZERO_DIGIT_PATTERN = re.compile(r"[1-9]")
SOURCE_STRING = "the ProductVersion string"
SOURCE_NUMBERS = "the numbers of the fixed file information"
# A value of the file is cut to this many characters in a message.
MAX_SHOWN_CHARACTERS = 60

TRUE_WORDS = ("true", "yes", "1")
FALSE_WORDS = ("false", "no", "0")


def parse_bool(value, name):
    """A bool from a recipe value: a plist boolean, or the text that a command
    line or a preference gives. Anything else is an error, never a guess."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        word = value.strip().lower()
        if word in TRUE_WORDS:
            return True
        if word in FALSE_WORDS:
            return False
    raise ProcessorError("%s must be true or false, not %r." % (name, value))


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
    """The sections and the resource directory entry of a PE file.

    Returns (sections, resource_rva, resource_size). A section is a tuple
    (virtual_size, virtual_address, raw_size, raw_offset)."""
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
    table_offset = optional_offset + optional_size
    table = read_exact(
        handle, file_size, table_offset, SECTION_HEADER_BYTES * section_count, "the section table"
    )
    sections = []
    for index in range(section_count):
        # name (8 bytes), virtual size, virtual address, raw size, raw offset
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", table, SECTION_HEADER_BYTES * index + 8
        )
        sections.append((virtual_size, virtual_address, raw_size, raw_offset))
    return sections, resource_rva, resource_size


def read_at_rva(handle, file_size, sections, rva, length, what):
    """Read `length` bytes at a virtual address. The section is the one whose
    range holds the address; the bytes must lie in the section's raw data."""
    for virtual_size, virtual_address, raw_size, raw_offset in sections:
        if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
            inside = rva - virtual_address
            if inside + length > raw_size:
                raise ValueError("%s lies outside the raw data of its section" % what)
            return read_exact(handle, file_size, raw_offset + inside, length, what)
    raise ValueError("%s is at an address that no section holds" % what)


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


def read_version_block(handle, file_size, sections, resource_rva):
    """The bytes of the first RT_VERSION resource: root -> type 16 -> the first
    entry -> the first language -> the data entry."""
    root = read_resource_directory(handle, file_size, sections, resource_rva, "the resource directory")
    version_entry = None
    for name, offset, is_directory in root:
        if not name & HIGH_BIT and name == RT_VERSION:
            version_entry = (offset, is_directory)
            break
    if version_entry is None:
        raise ValueError("the file has no version resource (RT_VERSION)")
    if not version_entry[1]:
        raise ValueError("the version resource entry is not a directory")

    names = read_resource_directory(
        handle, file_size, sections, resource_rva + version_entry[0], "the version resource directory"
    )
    if not names[0][2]:
        raise ValueError("the first entry of the version resource is not a directory")
    languages = read_resource_directory(
        handle, file_size, sections, resource_rva + names[0][1], "the language directory"
    )
    if languages[0][2]:
        raise ValueError("the first language entry of the version resource is not a data entry")

    entry = read_at_rva(
        handle, file_size, sections, resource_rva + languages[0][1], RESOURCE_DATA_ENTRY_BYTES,
        "the data entry of the version resource",
    )
    data_rva, data_size = struct.unpack_from("<II", entry, 0)
    if data_size == 0:
        raise ValueError("the version resource is empty")
    if data_size > MAX_VERSION_BYTES:
        raise ValueError(
            "the version resource is %d bytes (at most %d are accepted)" % (data_size, MAX_VERSION_BYTES)
        )
    return read_at_rva(handle, file_size, sections, data_rva, data_size, "the version resource")


def align4(offset):
    return (offset + 3) & ~3


def decode_text(raw, what):
    try:
        return raw.decode("utf-16-le")
    except UnicodeDecodeError:
        raise ValueError("%s is not valid UTF-16" % what)


def parse_block(data, start, limit):
    """One block of the version structure at `start`, inside the parent that
    ends at `limit`. Returns (key, value_offset, value_length, end). The
    padding to 4 bytes is counted from the start of the data."""
    if start + BLOCK_HEADER_BYTES > limit:
        raise ValueError("the version block walk runs out of bounds (a block header)")
    length, value_length, _type = struct.unpack_from("<HHH", data, start)
    if length < BLOCK_HEADER_BYTES or start + length > limit:
        raise ValueError("the version block walk runs out of bounds (a block of %d bytes)" % length)
    end = start + length
    position = start + BLOCK_HEADER_BYTES
    while position + 2 <= end and data[position:position + 2] != b"\0\0":
        position += 2
    if position + 2 > end:
        raise ValueError("a key of the version resource has no end")
    key = decode_text(data[start + BLOCK_HEADER_BYTES:position], "a key of the version resource")
    value_offset = align4(position + 2)
    if value_offset > end:
        if value_length:
            raise ValueError("the version block walk runs out of bounds (the value of %r)" % key)
        value_offset = end
    return key, value_offset, value_length, end


def children_of(data, offset, end):
    """The (key, value_offset, value_length, end) of each child block between
    `offset` and `end`. Only zero bytes may remain after the last child."""
    position = offset
    while position < end:
        if end - position < BLOCK_HEADER_BYTES:
            if any(data[position:end]):
                raise ValueError("the version block walk runs out of bounds (bytes after the last block)")
            return
        child = parse_block(data, position, end)
        yield child
        position = align4(child[3])


def string_value(data, value_offset, value_length, end):
    """The text of a String block: UTF-16, null terminated. The length is in
    characters; one that goes past the block is cut at the block's end. The
    text ends at the first null character."""
    stop = min(end, value_offset + 2 * value_length)
    position = value_offset
    while position + 2 <= stop and data[position:position + 2] != b"\0\0":
        position += 2
    return decode_text(data[value_offset:position], "a value of the version resource").strip()


def dotted(most, least):
    return "%d.%d.%d.%d" % (most >> 16, most & 0xFFFF, least >> 16, least & 0xFFFF)


def parse_version_info(data):
    """The content of a VS_VERSIONINFO block. Returns a dict: fixed numbers
    and the strings of the first string table."""
    key, value_offset, value_length, end = parse_block(data, 0, len(data))
    if key != ROOT_KEY:
        raise ValueError("the version resource does not start with %s" % ROOT_KEY)
    if value_length < FIXED_FILE_INFO_BYTES:
        raise ValueError("the version resource has no fixed file information (VS_FIXEDFILEINFO)")
    if value_offset + value_length > end:
        raise ValueError("the version block walk runs out of bounds (the fixed file information)")
    (signature, _structure, file_ms, file_ls, product_ms, product_ls) = struct.unpack_from(
        "<6I", data, value_offset
    )
    if signature != FIXED_FILE_INFO_SIGNATURE:
        raise ValueError("the signature of the fixed file information is wrong")

    strings = None
    children_offset = align4(value_offset + value_length)
    for child_key, child_value_offset, child_length, child_end in children_of(data, children_offset, end):
        if child_key != STRING_FILE_INFO_KEY:
            continue
        # The value of StringFileInfo is empty: its children start at once.
        tables = list(children_of(data, align4(child_value_offset + child_length), child_end))
        if not tables:
            continue
        table_key, table_value_offset, table_length, table_end = tables[0]
        if not TABLE_KEY_PATTERN.fullmatch(table_key):
            raise ValueError("a string table has a key that is not 8 hex digits: %r" % table_key[:16])
        strings = {}
        for name, string_offset, string_length, string_end in children_of(data, align4(table_value_offset + table_length), table_end):
            if name not in strings:
                strings[name] = string_value(data, string_offset, string_length, string_end)
        break
    if strings is None:
        raise ValueError("the version resource has no StringFileInfo with a string table")
    product = strings.get(PRODUCT_VERSION_KEY, "")
    file = strings.get(FILE_VERSION_KEY, "")
    if not product and not file:
        raise ValueError("the string table has no ProductVersion and no FileVersion")
    return {
        "exe_product_version": product,
        "exe_file_version": file,
        "exe_product_version_numbers": dotted(product_ms, product_ls),
        "exe_file_version_numbers": dotted(file_ms, file_ls),
        "exe_product_name": strings.get(PRODUCT_NAME_KEY, ""),
    }


def read_exe_version(path):
    """The version facts of an .exe, as a dict of the five outputs. Raises
    ValueError with a reason that is safe to show, OSError for a file that
    cannot be opened."""
    with open(path, "rb") as handle:
        file_size = os.fstat(handle.fileno()).st_size
        sections, resource_rva, _resource_size = parse_headers(handle, file_size)
        data = read_version_block(handle, file_size, sections, resource_rva)
    return parse_version_info(data)


def shown(text):
    """A value of the file, cut for a message."""
    if len(text) <= MAX_SHOWN_CHARACTERS:
        return text
    return text[:MAX_SHOWN_CHARACTERS] + "..."


def choose_version(facts):
    """The label for `version`: the ProductVersion string when it is numbers
    and dots only, else the numbers of the fixed file information. Returns
    (label, source). Raises ValueError, with a reason that is safe to show,
    when the label has no digit other than zero: an installer built with no
    version set can say zeros in both places, and zeros are not a version."""
    text = facts["exe_product_version"]
    if NUMERIC_VERSION_PATTERN.fullmatch(text):
        label, source = text, SOURCE_STRING
    else:
        label, source = facts["exe_product_version_numbers"], SOURCE_NUMBERS
    if not NONZERO_DIGIT_PATTERN.search(label):
        raise ValueError(
            "the version label would be %s, taken from %s, and a label of zeros is not a version "
            "(ProductVersion %r, FileVersion %r, file version numbers %s)"
            % (shown(label), source, shown(text), shown(facts.get("exe_file_version", "")),
               facts.get("exe_file_version_numbers", ""))
        )
    return label, source


class WindowsExeVersion(Processor):
    description = __doc__
    input_variables = {
        "pathname": {
            "required": True,
            "description": "Path to the downloaded .exe.",
        },
        "set_version": {
            "required": False,
            "default": True,
            "description": (
                "True (the default): set 'version' to the ProductVersion when it "
                "is numbers and dots only, else to the numbers of the fixed file "
                "information; a label of zeros stops the run. False: leave "
                "'version' alone."
            ),
        },
    }
    output_variables = {
        "exe_product_version": {
            "description": "The ProductVersion string of the first string table, as written.",
        },
        "exe_file_version": {
            "description": "The FileVersion string of the same table.",
        },
        "exe_product_version_numbers": {
            "description": "The product version from the fixed file information, four numbers joined by dots.",
        },
        "exe_file_version_numbers": {
            "description": "The file version from the fixed file information, four numbers joined by dots.",
        },
        "exe_product_name": {
            "description": "The ProductName string, or an empty string.",
        },
        "version": {
            "description": "Set only when set_version is true: the label for the importer.",
        },
    }

    def main(self):
        set_version = parse_bool(self.env.get("set_version", True), "set_version")
        path = self.env.get("pathname")
        if not isinstance(path, str) or not path or not os.path.isfile(path):
            raise ProcessorError("pathname is not a file (it does not exist, or it is a folder): %r" % (path,))
        name = os.path.basename(path)
        try:
            facts = read_exe_version(path)
            # The label is chosen before anything is set, so that a refused
            # label leaves the run as it was.
            label, source = choose_version(facts) if set_version else (None, None)
        except ValueError as err:
            raise ProcessorError("%s: %s." % (name, err))
        except OSError as err:
            raise ProcessorError("Could not read %s: %s" % (path, err))

        for key, value in facts.items():
            self.env[key] = value
        self.output(
            "%s: ProductVersion %r, product version numbers %s, file version %r, file version numbers %s"
            % (name, facts["exe_product_version"], facts["exe_product_version_numbers"],
               facts["exe_file_version"], facts["exe_file_version_numbers"])
        )
        if set_version:
            self.env["version"] = label
            self.output("version is %s, taken from %s" % (label, source))


if __name__ == "__main__":
    processor = WindowsExeVersion()
    processor.execute_shell()
