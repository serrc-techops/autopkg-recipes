#!/usr/local/autopkg/python
"""Repack the 64-bit folder of Kyocera's KX print driver zip as a zip of its own, with the version of the driver.

Kyocera publishes one zip for all its KX printers at one fixed address. On 2026-11-17
that zip (about 252 MB, 2743 files in 30 folders, named KX Driver 8.7.0917.zip by the server) held, at its top
level, the folders 32bit/, 64bit/, arm64/ and Utility/ and a few files. The folder
64bit/ held 718 files (3 more entries were folders) of about 81 MB: the driver's OEMSETUP.INF, its catalog
(kyomita.cat) and the driver files.

This processor reads that zip and writes a new zip beside it, KyoceraKXDriver-<version>.zip,
which holds ONE folder, KyoceraKXDriver-<version>/ (for another architecture folder than
the default 64bit, the folder's name is in both: KyoceraKXDriver-<folder>-<version>, so
that two architectures never give one name; each needs a template of its own), with the files of the chosen folder
(input kx_architecture_folder, default 64bit) and the folders under it. That is the
layout that the package tool takes for a print driver item: one folder named like the
zip, with the driver's .inf and its files. The version is read from the INF's
DriverVer line (DriverVer=<date>,<a.b.c.d>); a missing or malformed line stops the run.

What is checked, all before anything is written:

- Every member name of the vendor zip: an absolute name, a drive letter, a backslash, a
  NUL, a part named ".." or a name that appears twice (the whole archive, exact match)
  refuses the file. A member of the chosen folder that is a symbolic link is refused,
  and so are two members of the chosen folder whose names differ only in letter case
  (Windows would merge them).
- The size: more than MAX_MEMBERS members in the zip, or more than MAX_EXPANDED_BYTES of
  expanded files in the chosen folder (the sizes that the zip declares), refuses the file.
- OEMSETUP.INF must be a member of the chosen folder, exactly one. It is decoded
  by its byte order mark (UTF-16 either way, UTF-8), else as BOM-less UTF-16, UTF-8 or
  8-bit text. The INF of 8.7 that was read began with ';' and was 8-bit text without a mark.
- Input kx_required_driver_names, a list: every name must be a model line of the INF (a
  name left of the equals sign in a model section that [Manufacturer] lists). The missing
  names are listed as written. The comparison ignores letter case, as the package tool's
  does; the tool checks the names later too, and saying it here shows it in a dry run.

The new zip is deterministic: members sorted by name, one fixed time stamp, no
compression (so that the bytes do not depend on the zlib of the machine), no extra
fields, no comment, and one fixed attribute value (a regular file, mode 0644). The same vendor zip always gives the same bytes and
the same SHA-256. Only files are written, no folder entries (an empty folder is lost).

Verification. Kyocera publishes no checksum for the file and this recipe does not pin
one, so nothing here proves that the download is what Kyocera published. The processor
sets checksum_sha256 to the SHA-256 of the NEW zip (the file that the importer imports)
and sets checksum_verified to false, whatever it was before. The shared importer then
refuses a real run unless the override sets pcman_allow_unverified to true.

Outputs:

    pathname                    the new zip (the vendor zip's path before)
    version                     the INF's four-number version
    checksum_sha256             the SHA-256 of the new zip
    checksum_verified           false
    kx_vendor_zip_pathname      the vendor zip
    kx_vendor_zip_sha256        the SHA-256 of the vendor zip
    kx_inf_driver_date          the date of the DriverVer line, as written
    kx_driver_folder            the name of the folder inside the new zip
    kx_driver_name_count        the number of distinct model names in the INF
    kx_file_count               the number of files in the new zip

No output is set, and no file is left, unless every check passed.
"""
import hashlib
import os
import re
import stat
import tempfile
import zipfile
import zlib

from autopkglib import Processor, ProcessorError

__all__ = ["KyoceraKXDriverRepacker", "decode_inf", "read_inf_version", "model_names", "select_members",
           "check_member_names", "repack", "output_name"]

DEFAULT_ARCHITECTURE_FOLDER = "64bit"
FOLDER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}")
INF_NAME = "OEMSETUP.INF"
OUTPUT_PREFIX = "KyoceraKXDriver-"
# The version of the INF: exactly four numbers (8.7.0917.0 was read on 2026-11-17).
VERSION_PATTERN = re.compile(r"[0-9]{1,5}(\.[0-9]{1,5}){3}")
DRIVER_VER_PATTERN = re.compile(r"^\s*DriverVer\s*=\s*([^,;]*?)\s*,\s*([^;\s]*)", re.I)
# The 64bit folder of 8.7.0917 held 721 files and 81 MB. The whole zip held 2743 files in 30 folders, 343 MB.
MAX_MEMBERS = 20000
MAX_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_INF_BYTES = 16 * 1024 * 1024
MAX_NAME_COUNT = 20000
COPY_CHUNK_BYTES = 1024 * 1024
# The fixed time stamp of every member of the new zip: the earliest that a zip can hold.
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
# Unix as the creating system and a regular file with mode 0644: one fixed value, which Python would
# otherwise choose itself (0600) for an entry with none.
FIXED_CREATE_SYSTEM = 3
FIXED_EXTERNAL_ATTR = (stat.S_IFREG | 0o644) << 16
READ_WRITE_BITS = 0o666
FILE_TYPE_MASK = 0o170000
SYMLINK_TYPE = 0o120000
# What a damaged or unusual zip member raises while it is read.
READ_ERRORS = (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError)
HASH_PATTERN = re.compile(r"[0-9a-f]{64}")


def sha256_of_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(COPY_CHUNK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def check_folder_input(folder):
    if not isinstance(folder, str) or not FOLDER_PATTERN.fullmatch(folder):
        raise ValueError("kx_architecture_folder must be one folder name such as 64bit: %r" % (str(folder)[:40],))


def check_required_names(names):
    """The required driver names as a list of text, or ValueError. None is an empty list."""
    if names is None:
        return []
    if not isinstance(names, (list, tuple)):
        raise ValueError("kx_required_driver_names must be a list of driver names, not %s" % type(names).__name__)
    if len(names) > MAX_NAME_COUNT:
        raise ValueError("kx_required_driver_names has more than %d names" % MAX_NAME_COUNT)
    checked = []
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("kx_required_driver_names must hold only non-empty text: %r" % (str(name)[:40],))
        if "\x00" in name or "\n" in name or "\r" in name:
            raise ValueError("kx_required_driver_names has a name with a control character")
        checked.append(name.strip())
    return checked


def check_member_names(archive):
    """Refuse a zip with a member name that could leave a folder, a name twice, or too many members."""
    infos = archive.infolist()
    if len(infos) > MAX_MEMBERS:
        raise ValueError("the zip has %d members (at most %d are accepted)" % (len(infos), MAX_MEMBERS))
    seen = set()
    for info in infos:
        name = info.filename
        if not name:
            raise ValueError("the zip has a member with an empty name")
        if "\x00" in name or "\\" in name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
            raise ValueError("the zip has a member name that is not a relative path: %r" % name[:80])
        if ".." in name.split("/"):
            raise ValueError("the zip has a member name with a '..' part: %r" % name[:80])
        if name in seen:
            raise ValueError("the zip has two members named %r" % name[:80])
        seen.add(name)


def is_symlink(info):
    mode = info.external_attr >> 16
    return stat.S_IFMT(mode) == SYMLINK_TYPE if mode else False


def select_members(archive, folder):
    """The (relative name, ZipInfo) pairs of the files in `folder/`, sorted by relative name,
    and the ZipInfo of its OEMSETUP.INF. Raises ValueError."""
    check_folder_input(folder)
    prefix = folder + "/"
    chosen = []
    seen_folded = {}
    total = 0
    for info in archive.infolist():
        if not info.filename.startswith(prefix):
            continue
        relative = info.filename[len(prefix):]
        if info.is_dir() or not relative:
            continue
        if is_symlink(info):
            raise ValueError("%s is a symbolic link, which is refused" % info.filename[:80])
        if relative.endswith("/"):
            continue
        folded = relative.casefold()
        if folded in seen_folded:
            raise ValueError("%r and %r differ only in letter case, which Windows would merge"
                             % (seen_folded[folded][:60], relative[:60]))
        seen_folded[folded] = relative
        total += info.file_size
        if total > MAX_EXPANDED_BYTES:
            raise ValueError("the files of %s/ expand to more than %d bytes (the limit)" % (folder, MAX_EXPANDED_BYTES))
        chosen.append((relative, info))
    if not chosen:
        raise ValueError("the zip has no files in the folder %s/" % folder)
    infs = [info for relative, info in chosen if relative.casefold() == INF_NAME.casefold()]
    if not infs:
        raise ValueError("the folder %s/ has no member named %s" % (folder, INF_NAME))
    chosen.sort(key=lambda pair: pair[0].encode("utf-8"))
    return chosen, infs[0]


def decode_inf(data):
    """The text of an INF file. A byte order mark decides (UTF-16 either way, UTF-8); without
    one, UTF-16 is taken when the bytes alternate with NUL, else UTF-8, else 8-bit text."""
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16")
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8")
    head = data[:400]
    if len(head) >= 4 and head.count(b"\x00") >= len(head) // 4:
        even_zero = head[0::2].count(b"\x00")
        odd_zero = head[1::2].count(b"\x00")
        try:
            return data.decode("utf-16-le" if odd_zero > even_zero else "utf-16-be")
        except UnicodeDecodeError:
            pass
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def strip_comment(line):
    """The line without its ';' comment, which starts outside double quotes."""
    quoted = False
    for index, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char == ";" and not quoted:
            return line[:index]
    return line


def inf_lines(text):
    """(section, line) pairs of an INF, comments removed, blank lines dropped, a section name lower case."""
    section = ""
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = strip_comment(raw).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        yield section, line


def read_inf_version(text):
    """(date text, version) from the DriverVer line of the [Version] section. Raises ValueError."""
    found = []
    for section, line in inf_lines(text):
        if section != "version":
            continue
        match = DRIVER_VER_PATTERN.match(line)
        if match:
            found.append((match.group(1), match.group(2)))
    if not found:
        raise ValueError("the INF has no DriverVer=<date>,<version> line in its [Version] section")
    if len(found) > 1:
        raise ValueError("the INF has %d DriverVer lines (exactly one is accepted)" % len(found))
    date, version = found[0]
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError("the DriverVer version is not four numbers a.b.c.d: %r" % version[:40])
    return date, version


def unquote(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def model_names(text):
    """The set of driver names that are model lines of the INF: the text left of the '=' of
    every line in a model section, a section that [Manufacturer] names (the base name and the
    base name with each decoration, as in `Kyocera=Kyocera,NTx86.6.0,NTamd64.6.0`). A %key%
    is looked up in [Strings]."""
    lines = list(inf_lines(text))
    strings = {}
    for section, line in lines:
        if section == "strings" and "=" in line:
            key, value = line.split("=", 1)
            strings[key.strip().lower()] = unquote(value)
    model_sections = set()
    for section, line in lines:
        if section != "manufacturer" or "=" not in line:
            continue
        parts = [part.strip() for part in line.split("=", 1)[1].split(",")]
        if not parts or not parts[0]:
            continue
        model_sections.add(parts[0].lower())
        for decoration in parts[1:]:
            if decoration:
                model_sections.add((parts[0] + "." + decoration).lower())
    names = set()
    for section, line in lines:
        if section not in model_sections or "=" not in line:
            continue
        name = unquote(line.split("=", 1)[0])
        match = re.fullmatch(r"%([^%]+)%", name)
        if match:
            name = strings.get(match.group(1).strip().lower(), name)
        if name:
            names.add(name)
    return names


def output_base(version, folder=DEFAULT_ARCHITECTURE_FOLDER):
    """KyoceraKXDriver-<version>, or KyoceraKXDriver-<folder>-<version> for a folder other than the default."""
    if folder == DEFAULT_ARCHITECTURE_FOLDER:
        return "%s%s" % (OUTPUT_PREFIX, version)
    return "%s%s-%s" % (OUTPUT_PREFIX, folder, version)


def output_name(version, folder=DEFAULT_ARCHITECTURE_FOLDER):
    return output_base(version, folder) + ".zip"


def read_member_bounded(archive, info, limit):
    """The bytes of a member, never more than `limit`, and exactly the size that the entry declares."""
    with archive.open(info) as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError("%s is longer than %d bytes" % (info.filename[:80], limit))
    return data


def repack(zip_path, folder=DEFAULT_ARCHITECTURE_FOLDER, required_names=None):
    """Write the new zip beside `zip_path`. Returns a dict of facts, or raises ValueError (the
    file or the inputs) or OSError (the disk). Nothing is left that was not there, and no temporary
    file is left."""
    check_folder_input(folder)
    required = check_required_names(required_names)
    target_folder = os.path.dirname(os.path.abspath(zip_path))
    try:
        return _repack(zip_path, folder, required, target_folder)
    except READ_ERRORS as err:
        raise ValueError("the zip could not be read (%s: %s)" % (type(err).__name__, str(err)[:80]))


def _repack(zip_path, folder, required, target_folder):
    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise ValueError("the file is not a zip file")
    with archive:
        check_member_names(archive)
        chosen, inf_info = select_members(archive, folder)
        inf_text = decode_inf(read_member_bounded(archive, inf_info, MAX_INF_BYTES))
        date, version = read_inf_version(inf_text)
        names = model_names(inf_text)
        if not names:
            raise ValueError("the INF has no model lines (no driver name in a section that [Manufacturer] lists)")
        folded = {name.casefold() for name in names}
        missing = [name for name in required if name.casefold() not in folded]
        if missing:
            raise ValueError("the INF does not list %d of the required driver names as model lines: %s"
                             % (len(missing), "; ".join(repr(name[:80]) for name in missing)))
        top = output_base(version, folder)
        target = os.path.join(target_folder, output_name(version, folder))
        if os.path.realpath(target) == os.path.realpath(zip_path):
            raise ValueError("the new zip would replace the vendor zip itself")
        if os.path.islink(target):
            raise ValueError("%s is a link, which is refused" % os.path.basename(target))
        if os.path.lexists(target) and not os.path.isfile(target):
            raise ValueError("%s exists and is not a file" % os.path.basename(target))
        descriptor, temporary = tempfile.mkstemp(prefix=".kyocerakx.", suffix=".tmp", dir=target_folder)
        try:
            total = sum(info.file_size for _, info in chosen)
            with os.fdopen(descriptor, "wb") as raw:
                with zipfile.ZipFile(raw, "w", zipfile.ZIP_STORED) as out:
                    for relative, info in chosen:
                        entry = zipfile.ZipInfo(top + "/" + relative, FIXED_TIME)
                        entry.compress_type = zipfile.ZIP_STORED
                        entry.create_system = FIXED_CREATE_SYSTEM
                        entry.external_attr = FIXED_EXTERNAL_ATTR
                        entry.file_size = info.file_size
                        with archive.open(info) as source, out.open(entry, "w") as sink:
                            # zipfile never returns more than the declared size and raises on a short or damaged member.
                            while True:
                                chunk = source.read(COPY_CHUNK_BYTES)
                                if not chunk:
                                    break
                                sink.write(chunk)
                raw.flush()
                os.fsync(raw.fileno())
            os.chmod(temporary, os.stat(zip_path).st_mode & READ_WRITE_BITS)
            os.replace(temporary, target)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
    return {
        "pathname": target, "version": version, "date": date, "folder": top, "name_count": len(names),
        "file_count": len(chosen), "size": total, "sha256": sha256_of_file(target),
    }


class KyoceraKXDriverRepacker(Processor):
    description = __doc__
    input_variables = {
        "pathname": {
            "required": True,
            "description": "Path to the downloaded Kyocera KX print driver zip.",
        },
        "kx_architecture_folder": {
            "required": False,
            "description": "The folder of the vendor zip that is repacked (default 64bit).",
        },
        "kx_required_driver_names": {
            "required": False,
            "description": "A list of driver names that must be model lines of the INF. The run stops, listing the "
                           "missing ones, when one is not.",
        },
    }
    output_variables = {
        "pathname": {"description": "The new zip, KyoceraKXDriver-<version>.zip, beside the vendor zip."},
        "version": {"description": "The four-number version of the INF's DriverVer line."},
        "checksum_sha256": {"description": "The SHA-256 of the new zip."},
        "checksum_verified": {"description": "False: Kyocera publishes no checksum."},
        "kx_vendor_zip_pathname": {"description": "The vendor zip."},
        "kx_vendor_zip_sha256": {"description": "The SHA-256 of the vendor zip."},
        "kx_inf_driver_date": {"description": "The date of the DriverVer line, as written."},
        "kx_driver_folder": {"description": "The folder inside the new zip."},
        "kx_driver_name_count": {"description": "The number of distinct model names in the INF."},
        "kx_file_count": {"description": "The number of files in the new zip."},
    }

    def main(self):
        path = self.env.get("pathname")
        if not isinstance(path, str) or not path or not os.path.isfile(path):
            raise ProcessorError("pathname is not a file (it does not exist, or it is a folder): %r" % (path,))
        folder = self.env.get("kx_architecture_folder") or DEFAULT_ARCHITECTURE_FOLDER
        required = self.env.get("kx_required_driver_names")
        name = os.path.basename(path)
        try:
            vendor_hash = sha256_of_file(path)
            facts = repack(path, folder, required)
        except ValueError as err:
            raise ProcessorError("%s: %s. No zip was written." % (name, err))
        except OSError as err:
            raise ProcessorError("Could not repack %s: %s" % (path, err))

        self.env["kx_vendor_zip_pathname"] = path
        self.env["kx_vendor_zip_sha256"] = vendor_hash
        self.env["kx_inf_driver_date"] = facts["date"]
        self.env["kx_driver_folder"] = facts["folder"]
        self.env["kx_driver_name_count"] = facts["name_count"]
        self.env["kx_file_count"] = facts["file_count"]
        self.env["version"] = facts["version"]
        self.env["pathname"] = facts["pathname"]
        self.env["checksum_sha256"] = facts["sha256"]
        self.env["checksum_verified"] = False
        self.output(
            "%s: wrote %s (%d files, %d bytes) holding %s/ from %s/; driver version %s (INF date %s), %d driver names; "
            "the download is NOT verified: Kyocera publishes no checksum"
            % (name, os.path.basename(facts["pathname"]), facts["file_count"], facts["size"], facts["folder"], folder,
               facts["version"], facts["date"], facts["name_count"])
        )


if __name__ == "__main__":
    processor = KyoceraKXDriverRepacker()
    processor.execute_shell()
