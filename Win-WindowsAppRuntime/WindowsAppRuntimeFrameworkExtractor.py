#!/usr/local/autopkg/python
"""Take the Windows App Runtime framework package (.msix) out of Microsoft's redistributable zip.

Microsoft's redistributable for a release of the Windows App SDK is one zip. On
2026-11-16 the zip of release 1.4 (about 252 MB) held, under MSIX/win10-<arch>/ for
the architectures x64, x86 and arm64, four packages each: the framework package
(Microsoft.WindowsAppRuntime.<release>.msix) and the Main, Singleton and DDLM
packages, and three installer programs outside MSIX/. The recipe publishes only the
framework package of one architecture, as an item of its own.

The zip is only read, with the standard zipfile module. Nothing in it is run and
nothing is extracted except the one package. Every member name of the zip is
checked first: an absolute name, a drive letter, a backslash, a NUL, or a part
named ".." refuses the whole file. Exactly one member must be named
MSIX/win10-<architecture>/Microsoft.WindowsAppRuntime.<release>.msix (the letter
case of the name is not significant, but two members that differ only in case are
a double). The Main, Singleton and DDLM packages have other names and are never
taken. The package is then read as a zip of its own: its AppxManifest.xml (at most
MAX_MANIFEST_BYTES, UTF-8 only, no document type or entity declaration) must have an Identity
whose Publisher is Microsoft's (the one read on 2026-11-16), whose Name is Microsoft.WindowsAppRuntime.<release> and whose ProcessorArchitecture
is the wanted one, and Properties/Framework must be true. A damaged member or package (a bad CRC, an unsupported or encrypted entry) is a refusal with the same message. A missing member, a
double, a name that does not fit, a size above the bound, or a manifest that does
not fit stops the run with nothing written.

The package is copied through a temporary file in the folder of the zip and a rename,
under the name <identity name>_<version>_<architecture>.msix, so that a package of
another version or architecture never replaces this one. A link at the target is
refused.

Verification. The shared ChecksumVerifier, run before this step on the ZIP, sets
checksum_verified and checksum_sha256 (the hash of the zip). The importers accept a
download as verified only when checksum_sha256 is the hash of the file they import,
and the file they import is the package, not the zip. So this processor hashes the
zip itself, and ONLY when checksum_verified is true and checksum_sha256 is the zip's
hash does it replace checksum_sha256 with the hash of the package (it leaves
checksum_verified true). The package is then verified in the one sense that it is
bytes out of a zip that has the pinned hash. When the zip was not verified, or
checksum_sha256 is the hash of another file, nothing is changed (the importers then
refuse a real run) or, for another file's hash, the run stops.

Outputs:

    pathname                           the package (the zip's path before)
    windowsappruntime_zip_pathname     the zip
    windowsappruntime_zip_sha256       the hash of the zip
    windowsappruntime_identity_name    Identity Name of the package
    windowsappruntime_version          Identity Version of the package
    windowsappruntime_package_architecture  Identity ProcessorArchitecture of the package
    windowsappruntime_publisher        Identity Publisher of the package
    checksum_sha256                    the package's hash, only when the zip was verified

No output is set, and no package is left, unless every check passed.
"""
import hashlib
import os
import re
import tempfile
import zlib
import xml.etree.ElementTree as ElementTree
import zipfile

from autopkglib import Processor, ProcessorError

__all__ = ["WindowsAppRuntimeFrameworkExtractor", "find_framework_member", "extract_framework",
           "read_identity", "check_member_names", "target_name"]

ARCHITECTURES = ("x64", "x86", "arm64")
DEFAULT_ARCHITECTURE = "x64"
DEFAULT_RELEASE = "1.4"
RELEASE_PATTERN = re.compile(r"[0-9]{1,3}\.[0-9]{1,3}")
VERSION_PATTERN = re.compile(r"[0-9]{1,6}(\.[0-9]{1,6}){1,3}")
IDENTITY_NAME_PREFIX = "Microsoft.WindowsAppRuntime."
MEMBER_FOLDER = "MSIX"
# The framework package of 1.4 was 22310719 bytes (x64) on 2026-11-16. More than this is not the
# file that the recipe was written for.
MAX_MSIX_BYTES = 256 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_MEMBERS = 4096
COPY_CHUNK_BYTES = 1024 * 1024
MANIFEST_NAME = "AppxManifest.xml"
UTF8_BOM = b"\xef\xbb\xbf"
# The publisher of every package of the redistributable that was read on 2026-11-16.
EXPECTED_PUBLISHER = "CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US"
# What a damaged or unusual zip member raises while it is read.
READ_ERRORS = (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError)
MSIX_SUFFIX = ".msix"
READ_WRITE_BITS = 0o666
HASH_PATTERN = re.compile(r"[0-9a-f]{64}")


def sha256_of_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(COPY_CHUNK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def check_inputs(release, architecture):
    if not isinstance(release, str) or not RELEASE_PATTERN.fullmatch(release):
        raise ValueError("windowsappruntime_release must look like 1.4: %r" % (str(release)[:20],))
    if architecture not in ARCHITECTURES:
        raise ValueError("windowsappruntime_architecture must be one of %s: %r" % (", ".join(ARCHITECTURES), str(architecture)[:20]))


def check_member_names(archive):
    """Refuse a zip with a member name that could leave a folder, or with too many members."""
    infos = archive.infolist()
    if len(infos) > MAX_MEMBERS:
        raise ValueError("the zip has %d members (at most %d are accepted)" % (len(infos), MAX_MEMBERS))
    for info in infos:
        name = info.filename
        if "\x00" in name or "\\" in name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
            raise ValueError("the zip has a member name that is not a relative path: %r" % name[:80])
        if ".." in name.split("/"):
            raise ValueError("the zip has a member name with a '..' part: %r" % name[:80])


def find_framework_member(archive, release, architecture):
    """The ZipInfo of the one framework package for the architecture. None or two is an error."""
    wanted = "%s/win10-%s/%s%s%s" % (MEMBER_FOLDER, architecture, IDENTITY_NAME_PREFIX, release, MSIX_SUFFIX)
    found = [info for info in archive.infolist() if info.filename.casefold() == wanted.casefold()]
    if not found:
        raise ValueError("the zip has no member %s" % wanted)
    if len(found) > 1:
        raise ValueError("the zip has %d members named %s (exactly one is accepted)" % (len(found), wanted))
    info = found[0]
    if info.is_dir():
        raise ValueError("%s is a folder" % wanted)
    if info.file_size == 0:
        raise ValueError("%s is empty" % wanted)
    if info.file_size > MAX_MSIX_BYTES:
        raise ValueError("%s is %d bytes (at most %d are accepted)" % (wanted, info.file_size, MAX_MSIX_BYTES))
    return info


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def read_identity(msix_path, release, architecture):
    try:
        return _read_identity(msix_path, release, architecture)
    except READ_ERRORS as err:
        raise ValueError("the package could not be read (%s: %s)" % (type(err).__name__, str(err)[:80]))


def _read_identity(msix_path, release, architecture):
    """(name, version, architecture, publisher) from the manifest of the package at
    `msix_path`, after the checks of the identity and of the framework mark. Raises ValueError."""
    try:
        package = zipfile.ZipFile(msix_path)
    except zipfile.BadZipFile:
        raise ValueError("the package is not a zip file")
    with package:
        manifests = [info for info in package.infolist() if info.filename == MANIFEST_NAME]
        if len(manifests) != 1:
            raise ValueError("the package has %d members named %s (exactly one is accepted)" % (len(manifests), MANIFEST_NAME))
        if manifests[0].file_size > MAX_MANIFEST_BYTES:
            raise ValueError("%s is %d bytes (at most %d are accepted)" % (MANIFEST_NAME, manifests[0].file_size, MAX_MANIFEST_BYTES))
        with package.open(manifests[0]) as handle:
            data = handle.read(MAX_MANIFEST_BYTES + 1)
    if len(data) > MAX_MANIFEST_BYTES:
        raise ValueError("%s is longer than %d bytes" % (MANIFEST_NAME, MAX_MANIFEST_BYTES))
    body = data[len(UTF8_BOM):] if data.startswith(UTF8_BOM) else data
    if b"\x00" in body or not body.lstrip().startswith(b"<"):
        raise ValueError("%s is not UTF-8 text (a UTF-16 or UTF-32 manifest is refused)" % MANIFEST_NAME)
    try:
        body.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("%s is not valid UTF-8" % MANIFEST_NAME)
    lowered = data.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ValueError("%s has a document type or entity declaration, which is refused" % MANIFEST_NAME)
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        raise ValueError("%s is not well-formed XML" % MANIFEST_NAME)
    if local_name(root.tag) != "Package":
        raise ValueError("%s has no Package element at its root" % MANIFEST_NAME)
    identities = [child for child in root if local_name(child.tag) == "Identity"]
    if len(identities) != 1:
        raise ValueError("%s has %d Identity elements (exactly one is accepted)" % (MANIFEST_NAME, len(identities)))
    attributes = identities[0].attrib
    name = (attributes.get("Name") or "").strip()
    version = (attributes.get("Version") or "").strip()
    found_architecture = (attributes.get("ProcessorArchitecture") or "").strip().lower()
    publisher = (attributes.get("Publisher") or "").strip()
    expected_name = IDENTITY_NAME_PREFIX + release
    if name != expected_name:
        raise ValueError("the identity name of the package is %r, not %s: it is not the framework package of this release"
                         % (name[:80], expected_name))
    if found_architecture != architecture:
        raise ValueError("the package is for %r, not %s" % (found_architecture[:20], architecture))
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError("the version of the package is not usable: %r" % version[:40])
    if publisher != EXPECTED_PUBLISHER:
        raise ValueError("the publisher of the package is %r, not Microsoft's (%s)" % (publisher[:120], EXPECTED_PUBLISHER))
    properties = [child for child in root if local_name(child.tag) == "Properties"]
    framework = [item for props in properties for item in props if local_name(item.tag) == "Framework"]
    if len(framework) != 1 or (framework[0].text or "").strip().lower() != "true":
        raise ValueError("the manifest does not mark the package as a framework (Properties/Framework true)")
    return name, version, found_architecture, publisher


def target_name(name, version, architecture):
    return "%s_%s_%s%s" % (name, version, architecture, MSIX_SUFFIX)


def extract_framework(zip_path, release, architecture):
    """Write the framework package beside the zip. Returns a dict with the facts, or raises
    ValueError (the file) or OSError (the disk). Nothing is left that was not there, and
    no temporary file is left."""
    check_inputs(release, architecture)
    folder = os.path.dirname(os.path.abspath(zip_path))
    try:
        return _extract_framework(zip_path, release, architecture, folder)
    except READ_ERRORS as err:
        raise ValueError("the zip could not be read (%s: %s)" % (type(err).__name__, str(err)[:80]))


def _extract_framework(zip_path, release, architecture, folder):
    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise ValueError("the file is not a zip file")
    with archive:
        check_member_names(archive)
        info = find_framework_member(archive, release, architecture)
        descriptor, temporary = tempfile.mkstemp(prefix=".windowsappruntime.", suffix=".tmp", dir=folder)
        try:
            digest = hashlib.sha256()
            written = 0
            with os.fdopen(descriptor, "wb") as out, archive.open(info) as source:
                while True:
                    chunk = source.read(COPY_CHUNK_BYTES)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_MSIX_BYTES or written > info.file_size:
                        raise ValueError("the package is longer than its entry says")
                    digest.update(chunk)
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            if written != info.file_size:
                raise ValueError("the package written has not the size of its entry")
            name, version, found_architecture, publisher = read_identity(temporary, release, architecture)
            target = os.path.join(folder, target_name(name, version, found_architecture))
            if os.path.realpath(target) == os.path.realpath(zip_path):
                raise ValueError("the package would replace the zip itself")
            if os.path.islink(target):
                raise ValueError("%s is a link, which is refused" % os.path.basename(target))
            if os.path.lexists(target) and not os.path.isfile(target):
                raise ValueError("%s exists and is not a file" % os.path.basename(target))
            os.chmod(temporary, os.stat(zip_path).st_mode & READ_WRITE_BITS)
            os.replace(temporary, target)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
    return {
        "pathname": target, "name": name, "version": version, "architecture": found_architecture,
        "publisher": publisher, "size": written, "sha256": digest.hexdigest(), "member": info.filename,
    }


class WindowsAppRuntimeFrameworkExtractor(Processor):
    description = __doc__
    input_variables = {
        "pathname": {
            "required": True,
            "description": "Path to the downloaded redistributable zip.",
        },
        "windowsappruntime_release": {
            "required": False,
            "description": "The release of the Windows App SDK, as in the name of the framework package (default 1.4).",
        },
        "windowsappruntime_architecture": {
            "required": False,
            "description": "x64, x86 or arm64 (default x64).",
        },
        "checksum_verified": {
            "required": False,
            "description": "Set by ChecksumVerifier on the zip. Only when it is true, and checksum_sha256 is the zip's hash, "
                           "the package is marked as verified.",
        },
        "checksum_sha256": {
            "required": False,
            "description": "Set by ChecksumVerifier: the hash of the zip. Replaced by the hash of the package when the zip was verified.",
        },
    }
    output_variables = {
        "pathname": {"description": "The framework package that was taken out of the zip, beside it."},
        "windowsappruntime_zip_pathname": {"description": "The zip that the package was taken out of."},
        "windowsappruntime_zip_sha256": {"description": "The SHA-256 of the zip."},
        "windowsappruntime_identity_name": {"description": "Identity Name of the package."},
        "windowsappruntime_version": {"description": "Identity Version of the package."},
        "windowsappruntime_package_architecture": {"description": "Identity ProcessorArchitecture of the package."},
        "windowsappruntime_publisher": {"description": "Identity Publisher of the package."},
        "checksum_sha256": {"description": "The SHA-256 of the package, only when the zip was verified."},
    }

    def main(self):
        path = self.env.get("pathname")
        if not isinstance(path, str) or not path or not os.path.isfile(path):
            raise ProcessorError("pathname is not a file (it does not exist, or it is a folder): %r" % (path,))
        release = self.env.get("windowsappruntime_release") or DEFAULT_RELEASE
        architecture = self.env.get("windowsappruntime_architecture") or DEFAULT_ARCHITECTURE
        name = os.path.basename(path)
        try:
            zip_hash = sha256_of_file(path)
            verified = self.env.get("checksum_verified") is True
            if verified:
                claimed = self.env.get("checksum_sha256")
                claimed = claimed.strip().lower() if isinstance(claimed, str) else ""
                if HASH_PATTERN.fullmatch(claimed) and claimed != zip_hash:
                    raise ValueError("checksum_sha256 is the hash of another file than the zip (the zip has %s...)" % zip_hash[:8])
                verified = claimed == zip_hash
            facts = extract_framework(path, release, architecture)
        except ValueError as err:
            raise ProcessorError("%s: %s. No package was written." % (name, err))
        except OSError as err:
            raise ProcessorError("Could not take the package out of %s: %s" % (path, err))

        self.env["windowsappruntime_zip_pathname"] = path
        self.env["windowsappruntime_zip_sha256"] = zip_hash
        self.env["windowsappruntime_identity_name"] = facts["name"]
        self.env["windowsappruntime_version"] = facts["version"]
        self.env["windowsappruntime_package_architecture"] = facts["architecture"]
        self.env["windowsappruntime_publisher"] = facts["publisher"]
        self.env["pathname"] = facts["pathname"]
        if verified:
            self.env["checksum_sha256"] = facts["sha256"]
        self.output(
            "%s: wrote %s (%d bytes) as %s: identity %s, version %s, architecture %s%s"
            % (name, facts["member"], facts["size"], os.path.basename(facts["pathname"]), facts["name"], facts["version"],
               facts["architecture"], "" if verified else ". The zip was NOT verified, so the package is not either")
        )


if __name__ == "__main__":
    processor = WindowsAppRuntimeFrameworkExtractor()
    processor.execute_shell()
