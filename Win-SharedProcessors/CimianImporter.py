#!/usr/local/autopkg/python
"""Publish a downloaded Windows installer as a new version into a Cimian repository.

This is the last step of a Windows recipe. It does for a Cimian repository what
AutoPkg's MunkiImporter does for a Munki repository, and it needs no other tool.

The repository is the template. The pkginfo with the item's name and the highest
version under pkgsinfo/ is copied for the new version, and only what belongs to the
installer file is replaced: the version, the installer's location, SHA-256, size and
type, and for an MSI the product code, the upgrade code and the versions that the
install checks hold. Everything else is kept, and the input pkginfo does not change
what the template has: it only adds keys the template lacks, and a NOTE names every
key it would have changed (cimian_pkginfo_wins lets it win). Without a template, the
pkginfo is built from the inputs. When the repository has pkginfo files of the item
for several architectures, cimian_architecture says which ones are the template.

Nothing new (the same version, or the same installer file, is in the repository
already) writes nothing and is not an error. A dry run is the default: it writes
nothing and says what it would write. A real run needs cimian_dry_run set to false
in the recipe's override. It copies the installer to pkgs/ and writes the pkginfo to
pkgsinfo/ beside the target first and moves it into place; it never overwrites an
existing file and refuses a folder that leaves the repository.

A download that no step verified is not published silently. A download counts as
verified when checksum_verified is true (ChecksumVerifier sets it) AND
checksum_sha256 (ChecksumVerifier outputs it: the hash of the file it checked) is a
SHA-256 that equals the hash of the file about to be imported; or, in the same way,
when signature_verified is true (AuthenticodeVerifier sets it) AND signature_sha256
(the hash of the file whose signature it checked) equals that hash. This processor
hashes that file itself, once. A real run of a download that does not count is
refused, unless cimian_allow_unverified is true in the override. Then it goes on,
prints a WARNING at every verbosity, and the summary says "published, NOT verified".
A checksum_sha256 or signature_sha256 that is a SHA-256 of another file stops the
run, in a dry run too, and cimian_allow_unverified does not override it.

For an MSI the product version, product code and upgrade code are read with msiinfo
(msitools) when it is on cimian_path; an MSI whose upgrade code is not the template's
is refused unless cimian_allow_product_change is true. Without it the recipe or the override gives the
codes (msi_product_code, msi_upgrade_code) and the version, and the run says what
is missing. This processor does not build catalogs: run Cimian's makecatalogs after a
publish.

An app package (.msix, .appx, .msixbundle, .appxbundle) is installed by the client
itself with Add-AppxProvisionedPackage, and its pkginfo has installer.type msix and one
installs entry of type msix with the package's identity name and version, which is the
install check. The identity name and the version (for a bundle the bundle's own) are
read from the package's manifest: the package is opened as a zip file, one manifest is
read into memory (at most MAX_MANIFEST_BYTES), nothing is extracted, and a manifest
with a document type or entity declaration is refused. The package is not run, and its
signature is not checked. A single package's ProcessorArchitecture (not neutral) is the
installer's architecture; a bundle names none.

The pkginfo files are read and written with PyYAML, which AutoPkg's own Python has.
"""
import copy
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
import zlib
from xml.parsers import expat

from autopkglib import Processor, ProcessorError

__all__ = [
    "CimianImporter",
    "compare_versions",
    "normalize_sha256",
    "parse_property_export",
    "read_package_identity",
    "sha256_of_file",
    "version_parts",
]

MSI_EXTENSION = ".msi"
EXE_EXTENSION = ".exe"
# The app packages that the client installs itself, with Add-AppxProvisionedPackage
# (InstallerService.cs, BuildMsixInstallScript). Their pkginfo has the installer type
# msix; the file keeps its own extension in pkgs/.
APP_PACKAGE_EXTENSIONS = (".msix", ".appx", ".msixbundle", ".appxbundle")
INSTALLER_EXTENSIONS = (MSI_EXTENSION, EXE_EXTENSION) + APP_PACKAGE_EXTENSIONS
APP_PACKAGE_KIND = "msix"
# The installer types that the client dispatches to the app package install (msix or appx).
APP_PACKAGE_TYPES = ("msix", "appx")
# The manifest of a bundle and of a single package; a bundle is recognised by its own.
BUNDLE_MANIFEST = "AppxMetadata/AppxBundleManifest.xml"
SINGLE_MANIFEST = "AppxManifest.xml"
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
# Identity/@Name of a package: letters, digits, dots, underscores, hyphens.
IDENTITY_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
# Identity/@Version as the client compares it, with PowerShell's [System.Version]
# (InstallerService.cs, BuildMsixInstallScript): two to four numbers.
PACKAGE_VERSION_PATTERN = re.compile(r"[0-9]{1,9}(?:\.[0-9]{1,9}){1,3}")
# The ProcessorArchitecture of a single package that names one; neutral (or none)
# is for all.
PACKAGE_ARCHITECTURES = ("x64", "x86", "arm", "arm64")
NEUTRAL_ARCHITECTURE = "neutral"
# The repository's folders. The client builds the installer's address from
# pkgs/ and the item's `installer.location` (DownloadService.cs, BuildFullUrl).
PKGS_DIR = "pkgs"
PKGSINFO_DIR = "pkgsinfo"
# makecatalogs reads only the files that end in .yaml below pkgsinfo/
# (CatalogBuilder.cs, ScanRepo).
PKGINFO_SUFFIX = ".yaml"
# AutoPkg puts its preferences into the run's variables; this one is the
# repository's root when the input cimian_repo is not given.
REPO_PREFERENCE = "CIMIAN_REPO"
# Cimian's own tools default to this catalog (makepkginfo's Program.cs).
DEFAULT_CATALOGS = ("Development",)

# The PATH where msiinfo is looked for. A job that launchd starts may have no
# Homebrew on its PATH, and msiinfo is usually installed there.
DEFAULT_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
MSIINFO = "msiinfo"
MSIINFO_TIMEOUT_SECONDS = 60

# Always shown, also at the default verbosity of AutoPkg.
ALWAYS_SHOWN = 0
MAX_LINES_SHOWN = 12
MAX_LINE_CHARS = 1500

# The result text in the summary.
DRY_RUN_SUMMARY_RESULT = "dry run, nothing written"
DRY_RUN_UNVERIFIED_SUMMARY_RESULT = "dry run, nothing written, NOT verified"
PUBLISHED_SUMMARY_RESULT = "published"
PUBLISHED_UNVERIFIED_SUMMARY_RESULT = "published, NOT verified"

# The values of cimian_result.
RESULT_PUBLISHED = "published"
RESULT_DRY_RUN = "dry-run"
RESULT_NOTHING_NEW = "nothing-new"

# What counts as a verified download: the first is true, and the second is the
# SHA-256 of the file that is imported. ChecksumVerifier sets both.
VERIFIED_FLAG_VARIABLE = "checksum_verified"
VERIFIED_HASH_VARIABLE = "checksum_sha256"
# The same pair from AuthenticodeVerifier, which checks a signature.
SIGNATURE_FLAG_VARIABLE = "signature_verified"
SIGNATURE_HASH_VARIABLE = "signature_sha256"
# Each pair, with the word that a message uses for it.
VERIFICATIONS = (
    (VERIFIED_FLAG_VARIABLE, VERIFIED_HASH_VARIABLE, "checksum"),
    (SIGNATURE_FLAG_VARIABLE, SIGNATURE_HASH_VARIABLE, "signature"),
)
UNVERIFIED_REASON = (
    "no step of the recipe set checksum_verified together with the "
    "checksum_sha256 of this file, or signature_verified together with the "
    "signature_sha256 of this file"
)

# The same rules as ChecksumVerifier. A processor does not depend on a sibling
# file being importable when AutoPkg loads it, so this is a second copy: a test
# keeps the two equal.
HASH_PREFIX = "sha256:"
HEX_DIGITS = 64
HASH_PATTERN = re.compile(r"[0-9a-f]{%d}" % HEX_DIGITS)
READ_BLOCK_BYTES = 1024 * 1024
SHOWN_HEAD_CHARS = 8
SHOWN_TAIL_CHARS = 8

TRUE_WORDS = ("true", "yes", "1")
FALSE_WORDS = ("false", "no", "0")

# An item name: letters, numbers, dots, underscores and hyphens, not beginning
# with a hyphen or a dot. It becomes part of two file names.
NAME_PATTERN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")
MAX_NAME_CHARS = 100
# A version label begins with a digit (the client reads anything else as no
# version, CatalogService.cs, NormalizeVersionString) and is safe in a file name.
VERSION_PATTERN = re.compile(r"[0-9][0-9A-Za-z._-]*")
MAX_VERSION_CHARS = 100
# One folder name of cimian_subdirectory.
SUBDIRECTORY_PART = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._ -]*")
GUID_PATTERN = re.compile(
    r"\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}"
)

# The keys of `installer` that give the arguments of an installer: the client joins
# them all (UpdateModels.cs, GetAllArgs), so two of them in one item run twice.
ARGUMENT_KEYS = ("args", "switches", "flags", "subcommand")
# The keys of `installer` that an app package's item does not take: the client's
# install of it passes no arguments and reads no success codes, and an app package
# has no Windows Installer codes (InstallerService.cs, BuildMsixInstallScript).
APP_PACKAGE_REFUSED_INSTALLER_KEYS = ARGUMENT_KEYS + ("success_codes", "product_code", "upgrade_code")
# AutoPkg's own pattern for a variable (autopkglib/__init__.py:122).
VARIABLE_PATTERN = re.compile(r"%([A-Za-z_][A-Za-z_0-9]*(?:\([A-Za-z0-9]+\))?)%")
# Windows environment variables: a `%name%` of these in the input pkginfo is meant as it stands.
WINDOWS_VARIABLES = frozenset(name.lower() for name in (
    "ALLUSERSPROFILE", "APPDATA", "CommonProgramFiles", "CommonProgramFiles(x86)", "CommonProgramW6432",
    "COMPUTERNAME", "ComSpec", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "LOGONSERVER", "OS", "Path", "PATHEXT",
    "ProgramData", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "PUBLIC", "SystemDrive", "SystemRoot",
    "TEMP", "TMP", "USERDOMAIN", "USERNAME", "USERPROFILE", "windir",
))
ARCHITECTURE_PATTERN = re.compile(r"[a-z0-9_]+")
# A file that has version data of its own: a hash-less file check can still tell
# an old file from a new one by its version.
FILES_WITH_VERSION_DATA = (".exe", ".dll")
# Keys of `pkginfo` that belong to the installer file: a person cannot set them.
FILE_KEYS = ("name", "version")
FILE_INSTALLER_KEYS = ("location", "hash", "size", "type")
# The order of a pkginfo that is built without a template: the order of the
# keys in the model of Cimian's own makepkginfo (PkgsInfo.cs, Order). Other keys
# follow in the order they were given.
KEY_ORDER = (
    "name", "display_name", "identifier", "version", "catalogs", "category",
    "description", "developer", "icon_name", "installer_type", "supported_architectures",
    "unattended_install", "minimum_os_version", "maximum_os_version",
    "minimum_cimian_version", "installs", "installcheck_script", "uninstallcheck_script",
    "preinstall_script", "postinstall_script", "preuninstall_script",
    "postuninstall_script", "uninstaller", "OnDemand", "recurring", "managed_profiles",
    "managed_apps", "check", "installer", "unattended_uninstall",
    "unused_software_removal_info",
)
INSTALLER_KEY_ORDER = ("type", "size", "location", "hash")
# What a force date does once it has passed is the client's decision for one
# release, not a property of the product (UpdateEngine.cs:610-619 and :1241-1290).
NOT_CARRIED_KEYS = ("force_install_after_date",)

# Cimian's version order (CatalogService.cs, CompareVersions): parts that are
# numbers, and these tags that sort before them.
TAG_ORDER = (("alpha", -3), ("beta", -2), ("rc", -1), ("release", 0))
INT32_MAX = 2 ** 31 - 1

INT_TAG = "tag:yaml.org,2002:int"
FLOAT_TAG = "tag:yaml.org,2002:float"
STR_TAG = "tag:yaml.org,2002:str"
BOOL_TAG = "tag:yaml.org,2002:bool"
NULL_TAG = "tag:yaml.org,2002:null"
# How many literal copies of the old version are named in one run.
MAX_OLD_VERSION_WARNINGS = 5


# ---- small helpers ----------------------------------------------------------


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


def text_or_empty(value):
    """An input as stripped text; None and an empty string are 'not given'."""
    if value is None:
        return ""
    return str(value).strip()


def shorten(text):
    """Head and tail of a long value, so that a message stays short."""
    if len(text) <= SHOWN_HEAD_CHARS + SHOWN_TAIL_CHARS + 3:
        return text
    return "%s...%s" % (text[:SHOWN_HEAD_CHARS], text[-SHOWN_TAIL_CHARS:])


def clip(line):
    line = line.strip()
    if len(line) > MAX_LINE_CHARS:
        line = line[:MAX_LINE_CHARS] + "..."
    return line


def normalize_sha256(value):
    """The 64 lower-case hex digits in `value`, or None when it is not a
    SHA-256 (not text, empty, wrong length, not hex). Upper case, white space
    around it and the prefix "sha256:" are accepted, as ChecksumVerifier does."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text[: len(HASH_PREFIX)].lower() == HASH_PREFIX:
        text = text[len(HASH_PREFIX):].strip()
    text = text.lower()
    if not HASH_PATTERN.fullmatch(text):
        return None
    return text


def sha256_of_file(path):
    """SHA-256 of a file, as lower-case hex, read in blocks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(READ_BLOCK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


# ---- versions, as Cimian's catalog code reads them --------------------------


def _is_int(part):
    return part.isascii() and part.isdigit() and int(part) <= INT32_MAX


def _expand_build_timestamp(parts):
    """The client expands a three-part version that can only be a build
    timestamp (yy.M.ddHH) to the full form (CatalogService.cs,
    ExpandBuildTimestamp)."""
    if (
        len(parts) == 3
        and _is_int(parts[0]) and 20 <= int(parts[0]) <= 99
        and _is_int(parts[1]) and 1 <= int(parts[1]) <= 12
        and 3 <= len(parts[2]) <= 4 and _is_int(parts[2])
    ):
        day, hour = divmod(int(parts[2]), 100)
        if 1 <= day <= 31 and hour <= 23:
            return [
                "%d" % (2000 + int(parts[0])),
                "%02d" % int(parts[1]),
                "%02d" % day,
                "%02d00" % hour,
            ]
    return parts


def version_parts(version):
    """The parts of a version as the client reads it (CatalogService.cs,
    NormalizeVersionString), or None when it is not a recognisable version."""
    if not isinstance(version, str) or not version.strip():
        return None
    text = version.strip()
    paren = text.find("(")
    if paren > 0:
        text = text[:paren].strip()
    text = re.sub(r",\s*", ".", text)
    parts = []
    for raw in re.split(r"[.\-_]", text):
        part = raw.strip()
        if not part:
            continue
        if _is_int(part):
            parts.append(part)
            continue
        if part.lower().startswith(tuple(tag for tag, _ in TAG_ORDER)):
            parts.append(part)
            continue
        break
    if not parts:
        return None
    return _expand_build_timestamp(parts)


def _part_value(part):
    if _is_int(part):
        return int(part)
    lower = part.lower()
    for tag, value in TAG_ORDER:
        if lower.startswith(tag):
            return value
    return 0


def compare_versions(first, second):
    """-1, 0 or 1, as the client's CompareVersions (CatalogService.cs). Two
    versions that are the same text are equal; a version that is not
    recognisable is equal to everything there, so callers check version_parts
    first when that matters."""
    if first == second:
        return 0
    one, two = version_parts(first), version_parts(second)
    if one is None or two is None:
        return 0
    for index in range(max(len(one), len(two))):
        value_one = _part_value(one[index]) if index < len(one) else 0
        value_two = _part_value(two[index]) if index < len(two) else 0
        if value_one != value_two:
            return -1 if value_one < value_two else 1
    return 0


def same_version(first, second):
    """True when both are recognisable versions that the client reads as one
    (2.0 and 2.0.0), or are the same text."""
    if first == second:
        return True
    if version_parts(first) is None or version_parts(second) is None:
        return False
    return compare_versions(first, second) == 0


# ---- msiinfo ----------------------------------------------------------------

MSI_PROPERTIES = ("ProductVersion", "ProductCode", "UpgradeCode")


def parse_property_export(text):
    """The properties that matter from the output of `msiinfo export <file>
    Property`: lines of two tab-separated fields whose first field is
    ProductVersion, ProductCode or UpgradeCode. Any other line (a header, a
    property that does not matter) is ignored. A property named twice with two
    values is an error."""
    found = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        name, value = parts[0].strip(), parts[1].strip()
        if name not in MSI_PROPERTIES:
            continue
        if name in found and found[name] != value:
            raise ProcessorError("msiinfo reports two different values for %s." % name)
        found[name] = value
    return found


# ---- app packages -----------------------------------------------------------


class PackageIdentity(object):
    """What is read from an app package: Identity/@Name, Identity/@Version, a single
    package's ProcessorArchitecture as written (lower case, or "" when it names none),
    and whether it is a bundle."""

    def __init__(self, name, version, architecture, bundle):
        self.name = name
        self.version = version
        self.architecture = architecture
        self.bundle = bundle


def _refuse_declaration(*_args):
    raise ProcessorError(
        "The package's manifest has a document type or an entity declaration, which is not read."
    )


def _first_identity(data, shown):
    """The attributes of the first `Identity` element that is a child of the root
    element, whatever its namespace, or None. Read with expat, which builds no tree;
    a document type or an entity declaration stops the reading."""
    found = []
    depth = [0]

    def start(name, attributes):
        if depth[0] == 1 and not found and name.rsplit(" ", 1)[-1] == "Identity":
            found.append(dict(attributes))
        depth[0] += 1

    def end(_name):
        depth[0] -= 1

    parser = expat.ParserCreate(namespace_separator=" ")
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.StartDoctypeDeclHandler = _refuse_declaration
    parser.EntityDeclHandler = _refuse_declaration
    try:
        parser.Parse(data, True)
    except expat.ExpatError as err:
        raise ProcessorError("The manifest of %s is not well-formed XML: %s" % (shown, err))
    return found[0] if found else None


def _manifest_member(archive, wanted):
    """The member whose name is `wanted`, with forward slashes and without regard to
    letter case, or None."""
    for info in archive.infolist():
        if info.filename.replace("\\", "/").lower() == wanted.lower():
            return info
    return None


def read_package_identity(path):
    """The identity of the app package at `path` (a PackageIdentity). A bundle's
    manifest wins over a single package's. Nothing is extracted: one manifest is read
    into memory, at most MAX_MANIFEST_BYTES. Raises ProcessorError with one line."""
    shown = os.path.basename(path)
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError, ValueError) as err:
        raise ProcessorError(
            "%s is not an app package that can be read (a zip file with a manifest): %s" % (shown, err)
        )
    with archive:
        bundle = _manifest_member(archive, BUNDLE_MANIFEST)
        info = bundle or _manifest_member(archive, SINGLE_MANIFEST)
        if info is None:
            raise ProcessorError(
                "%s holds neither %s nor %s: it is not an app package." % (shown, SINGLE_MANIFEST, BUNDLE_MANIFEST)
            )
        if info.file_size > MAX_MANIFEST_BYTES:
            raise ProcessorError("The manifest of %s is larger than %d bytes." % (shown, MAX_MANIFEST_BYTES))
        try:
            with archive.open(info) as handle:
                data = handle.read(MAX_MANIFEST_BYTES + 1)
        except (zipfile.BadZipFile, NotImplementedError, RuntimeError, OSError, zlib.error, EOFError) as err:
            raise ProcessorError("The manifest of %s cannot be read: %s" % (shown, err))
    if len(data) > MAX_MANIFEST_BYTES:
        raise ProcessorError("The manifest of %s is larger than %d bytes." % (shown, MAX_MANIFEST_BYTES))
    identity = _first_identity(data, shown)
    if identity is None:
        raise ProcessorError("The manifest of %s has no Identity element." % shown)
    name = (identity.get("Name") or "").strip()
    version = (identity.get("Version") or "").strip()
    if not name or not version:
        raise ProcessorError("The Identity element in the manifest of %s has no Name or no Version." % shown)
    if not IDENTITY_NAME_PATTERN.fullmatch(name):
        raise ProcessorError(
            "The identity name in the manifest of %s is not one (letters, numbers, dots, underscores, "
            "hyphens): %r" % (shown, name[:40])
        )
    if not PACKAGE_VERSION_PATTERN.fullmatch(version):
        raise ProcessorError(
            "The version in the manifest of %s is not two to four numbers separated by dots, as the "
            "client compares it: %r" % (shown, version[:40])
        )
    architecture = "" if bundle else (identity.get("ProcessorArchitecture") or "").strip().lower()
    return PackageIdentity(name, version, architecture, bundle is not None)


def installer_kind(extension):
    """The installer type of the pkginfo for a file's extension (with its dot)."""
    if extension in APP_PACKAGE_EXTENSIONS:
        return APP_PACKAGE_KIND
    return extension[1:]


# ---- the pkginfo ------------------------------------------------------------


def walk_strings(value, path):
    """Every text in `value` with its path (`installcheck_script`,
    `installs[1].path`)."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from walk_strings(child, "%s.%s" % (path, key) if path else str(key))
    elif isinstance(value, list):
        for number, child in enumerate(value, start=1):
            yield from walk_strings(child, "%s[%d]" % (path, number))


def merge_into(base, extra):
    """`extra` merged over `base`: a dictionary in both is merged key by key,
    anything else in `extra` replaces the value of `base`."""
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge_into(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def install_check_type(entry):
    """The type of an `installs` entry as the client reads it (UpdateModels.cs,
    EffectiveType): the written type, else msi when it has a code, else file
    when it has a path."""
    written = entry.get("type")
    if isinstance(written, str) and written.strip():
        return written.strip().lower()
    if entry.get("product_code") or entry.get("upgrade_code"):
        return "msi"
    if entry.get("path"):
        return "file"
    return ""


def put_installer_fields(installer, location, digest, size, kind):
    """The four values that belong to the file, set in place; a key the
    installer lacks is added at the end."""
    values = {"type": kind, "size": size, "location": location, "hash": digest}
    for key in INSTALLER_KEY_ORDER:
        installer[key] = values[key]


def order_pkginfo(data):
    """The keys of a pkginfo that was built without a template, in the order
    of Cimian's own model; unknown keys follow in the order they came."""
    ordered = {}
    for key in KEY_ORDER:
        if key in data:
            ordered[key] = data[key]
    for key, value in data.items():
        if key not in ordered:
            ordered[key] = value
    installer = ordered.get("installer")
    if isinstance(installer, dict):
        inner = {key: installer[key] for key in INSTALLER_KEY_ORDER if key in installer}
        for key, value in installer.items():
            if key not in inner:
                inner[key] = value
        ordered["installer"] = inner
    return ordered


def normalize_architecture(text):
    """An architecture as the client compares them (CatalogService.cs,
    SupportsArchitecture): lower case, amd64 and x86_64 are x64."""
    word = str(text).strip().lower()
    return "x64" if word in ("amd64", "x86_64") else word


def resolve_variables(value, variables, path, unresolved):
    """`value` with every `%name%` that `variables` has replaced by its text, in nested dictionaries
    and lists too. A `%name%` that remains and is not a Windows environment variable is added to
    `unresolved` as (path, name). AutoPkg replaces the variables of an Input once, before the first step runs
    (autopkglib/__init__.py:783-797), and leaves the ones that nothing has set yet as they stand
    (:432-437): `version`, which a download step sets, is one of them."""
    if isinstance(value, str):
        def replace(match):
            name = match.group(1)
            return variables[name] if name in variables else match.group(0)

        text = VARIABLE_PATTERN.sub(replace, value)
        for match in VARIABLE_PATTERN.finditer(text):
            if match.group(1).lower() not in WINDOWS_VARIABLES:
                unresolved.append((path, match.group(1)))
        return text
    if isinstance(value, dict):
        return {key: resolve_variables(child, variables, "%s.%s" % (path, key) if path else str(key), unresolved)
                for key, child in value.items()}
    if isinstance(value, list):
        return [resolve_variables(child, variables, "%s[%d]" % (path, number), unresolved)
                for number, child in enumerate(value, start=1)]
    return value


def check_the_client_uses(data):
    """Which check the client consults for this item, in its own order (StatusService.cs:117-186):
    an OnDemand item has none, then installcheck_script, version_script, a non-empty `installs`,
    `check.registry`, `check.file`. Returns "", "installs", "check.registry" or "check.file"."""
    if data.get("OnDemand") is True:
        return ""
    for key in ("installcheck_script", "version_script"):
        if isinstance(data.get(key), str) and data[key]:
            return ""
    installs = data.get("installs")
    if isinstance(installs, list) and installs:
        return "installs"
    check = data.get("check")
    if isinstance(check, dict):
        registry = check.get("registry")
        if isinstance(registry, dict) and registry.get("name"):
            return "check.registry"
        entry = check.get("file")
        if isinstance(entry, dict) and entry.get("path"):
            return "check.file"
    return ""


def merge_pkginfo_into_template(data, extra, replace, notes, path=""):
    """Put the input `pkginfo` into the copy of a template. A key the template
    lacks is added. A key the template has with another value keeps the template's
    value, unless `replace` is true; either way a NOTE names the key. A dictionary in
    both is merged key by key. The arguments of an installer are one group
    (`ARGUMENT_KEYS`): the template's own group is not given a second one."""
    if path == "installer" and replace and any(key in extra for key in ARGUMENT_KEYS):
        for key in ARGUMENT_KEYS:
            if key in data and key not in extra:
                del data[key]
                notes.append(
                    "NOTE: pkginfo gives the installer's arguments as %s, so the template's installer.%s "
                    "is not carried." % (", ".join(k for k in ARGUMENT_KEYS if k in extra), key)
                )
    for key, value in extra.items():
        where = "%s.%s" % (path, key) if path else key
        if key not in data:
            others = [k for k in ARGUMENT_KEYS if k in data and k != key]
            if path == "installer" and key in ARGUMENT_KEYS and others:
                notes.append(
                    "NOTE: pkginfo's %s is not used: the template gives the installer's arguments as %s, "
                    "and the client would run both." % (where, ", ".join("installer." + k for k in others))
                )
                continue
            data[key] = copy.deepcopy(value)
            notes.append("NOTE: pkginfo gives %s and the template has none: it is added." % where)
        elif isinstance(value, dict) and isinstance(data[key], dict):
            merge_pkginfo_into_template(data[key], value, replace, notes, where)
        elif data[key] == value:
            continue
        elif replace:
            data[key] = copy.deepcopy(value)
            notes.append("NOTE: pkginfo replaces %s of the template." % where)
        else:
            notes.append(
                "NOTE: pkginfo's %s differs from the template's and is not used: the template's is kept. "
                "Set cimian_pkginfo_wins to true in the override to make pkginfo win." % where
            )


class PkgInfo(object):
    """A pkginfo file of the repository that has the item's name."""

    def __init__(self, relpath, data):
        self.relpath = relpath
        self.data = data
        self.version = str(data.get("version"))

    @property
    def architectures(self):
        """The architectures the item is for, as a set; empty means all (the client,
        CatalogService.cs, SupportsArchitecture)."""
        listed = self.data.get("supported_architectures")
        if isinstance(listed, str):
            listed = [listed]
        if not isinstance(listed, list):
            return frozenset()
        return frozenset(normalize_architecture(item) for item in listed if isinstance(item, str) and item.strip())

    @property
    def installer_hash(self):
        installer = self.data.get("installer")
        if isinstance(installer, dict):
            return normalize_sha256(installer.get("hash"))
        return None


def make_yaml_classes(yaml):
    """The loader and the dumper.

    The loader resolves only what Cimian's own files need to be typed: the booleans and
    null of YAML 1.2's core schema (`true`, `True`, `TRUE`, `false`, ..., `null`, `Null`,
    `NULL`, `~` and an empty value), and decimal integers in their plain form (`1320`, not `22:00`,
    `007`, `0x1F`, `1_000` or `+5`). Every other plain scalar stays text, so a time
    such as 22:00, a word such as yes, a number such as 2025.10 or a date is neither
    turned into another type nor changed on its way through (PyYAML's own rules are
    YAML 1.1: 22:00 is the integer 1320 there, 2025.10 the float 2025.1, yes a
    boolean). A `version` is text in any case. The dumper writes a multi-line text as
    a literal block, never writes an anchor, and quotes a text that PyYAML would read
    as another type, so the text comes back the same."""

    class Loader(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            if isinstance(node, yaml.MappingNode):
                for key_node, value_node in node.value:
                    if (
                        isinstance(key_node, yaml.ScalarNode)
                        and key_node.value == "version"
                        and isinstance(value_node, yaml.ScalarNode)
                        and value_node.tag in (INT_TAG, FLOAT_TAG)
                    ):
                        value_node.tag = STR_TAG
            return super().construct_mapping(node, deep=deep)

    Loader.yaml_implicit_resolvers = {}
    Loader.add_implicit_resolver(BOOL_TAG, re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF"))
    Loader.add_implicit_resolver(NULL_TAG, re.compile(r"^(?:~|null|Null|NULL|)$"), ["~", "n", "N", ""])
    Loader.add_implicit_resolver(INT_TAG, re.compile(r"^(?:0|-?[1-9][0-9]*)$"), list("-0123456789"))

    class Dumper(yaml.SafeDumper):
        def ignore_aliases(self, data):
            return True

    def represent_text(dumper, data):
        style = "|" if "\n" in data else None
        return dumper.represent_scalar(STR_TAG, data, style=style)

    Dumper.add_representer(str, represent_text)
    return Loader, Dumper


class CimianImporter(Processor):
    description = __doc__
    input_variables = {
        "pathname": {
            "required": True,
            "description": (
                "Path to the downloaded installer (.msi, .exe, or an app package: "
                ".msix, .appx, .msixbundle, .appxbundle)."
            ),
        },
        "cimian_repo": {
            "required": False,
            "description": (
                "The root of the Cimian repository (the folder with pkgs/ and "
                "pkgsinfo/). Default: the AutoPkg preference CIMIAN_REPO. Set it "
                "as a preference or in an override, never in a recipe."
            ),
        },
        "cimian_name": {
            "required": True,
            "description": "The item's name (the pkginfo's `name`).",
        },
        "version": {
            "required": False,
            "description": (
                "The version label. Required for an .exe. For an .msi the "
                "default is the MSI's own ProductVersion, and another label is "
                "refused when msiinfo can read the MSI. For an app package it is "
                "the package's own Identity Version, and another label is refused."
            ),
        },
        "cimian_subdirectory": {
            "required": False,
            "description": (
                "The folder under pkgs/ and pkgsinfo/. Default: the folder of "
                "the template's installer, else none."
            ),
        },
        "pkginfo": {
            "required": False,
            "description": (
                "A dictionary of pkginfo keys. Without a template it is merged over the "
                "pkginfo that is built (nested dictionaries key by key, anything else "
                "replaced). With a template it only adds what the template lacks; a key "
                "with another value keeps the template's and a NOTE says so, unless "
                "cimian_pkginfo_wins is true. It cannot set name, version or "
                "installer.location, hash, size and type."
            ),
        },
        "cimian_pkginfo_wins": {
            "required": False,
            "default": False,
            "description": (
                "False (the default): the input pkginfo never changes a value that the "
                "template has. True: it replaces it, and a NOTE names each key. Set in an "
                "override, never in a recipe."
            ),
        },
        "cimian_architecture": {
            "required": False,
            "description": (
                "The architecture of the installer (x64, x86, arm64). Needed when the "
                "repository has pkginfo files of the item for several architectures: only the "
                "ones for this architecture (or for all) are the template and decide "
                "'nothing new'. A pkginfo without a template is then for this architecture. "
                "For a single app package that names its ProcessorArchitecture, that is the "
                "default, and another value is refused."
            ),
        },
        "cimian_allow_product_change": {
            "required": False,
            "default": False,
            "description": (
                "False (the default): an MSI whose upgrade code is not the template's is "
                "refused. True: it goes on, with a WARNING. Set in an override, never in a recipe."
            ),
        },
        "cimian_catalogs": {
            "required": False,
            "default": list(DEFAULT_CATALOGS),
            "description": (
                "The catalogs of a pkginfo that has no template (a list). With a "
                "template, the template's catalogs are kept."
            ),
        },
        "cimian_dry_run": {
            "required": False,
            "default": True,
            "description": (
                "True (the default): say what would be written and write "
                "nothing. A real run needs the explicit value false."
            ),
        },
        "cimian_allow_unverified": {
            "required": False,
            "default": False,
            "description": (
                "False (the default): a real run of a download that no step "
                "verified is refused. True: it goes on, with a WARNING, and the "
                "summary says 'published, NOT verified'. It does not override a "
                "checksum_sha256 or signature_sha256 that is not the hash of the "
                "file. Set in an override, never in a recipe."
            ),
        },
        "cimian_path": {
            "required": False,
            "default": DEFAULT_PATH,
            "description": "The PATH where msiinfo is looked for (an MSI only).",
        },
        "msi_product_code": {
            "required": False,
            "description": (
                "The MSI's ProductCode ({GUID}). Needed when msiinfo is not "
                "available; when it is, it must equal what msiinfo reads."
            ),
        },
        "msi_upgrade_code": {
            "required": False,
            "description": (
                "The MSI's UpgradeCode ({GUID}). Needed when msiinfo is not "
                "available; when it is, it must equal what msiinfo reads."
            ),
        },
    }
    output_variables = {
        "cimian_result": {
            "description": "published, dry-run or nothing-new.",
        },
        "cimian_version_imported": {
            "description": "The version label of the result (the planned one after a dry run).",
        },
        "cimian_pkginfo_path": {
            "description": "The pkginfo in the repository (planned after a dry run).",
        },
        "cimian_installer_path": {
            "description": "The installer in the repository (planned after a dry run).",
        },
        "cimian_repo_changed": {
            "description": "True only when this run wrote to the repository.",
        },
        "cimian_importer_summary_result": {
            "description": (
                "Summary for AutoPkg's report: a published version, or a dry "
                "run (result 'dry run, nothing written'). No paths."
            ),
        },
    }

    # ---- checks before anything is read from the repository ----

    def read_inputs(self):
        """Check every input and return what the run needs. Hashes the
        installer once."""
        installer = text_or_empty(self.env.get("pathname"))
        if not installer:
            raise ProcessorError("pathname is empty.")
        installer = os.path.abspath(installer)
        extension = os.path.splitext(installer)[1].lower()
        if extension not in INSTALLER_EXTENSIONS:
            raise ProcessorError(
                "The installer must end in %s: %s"
                % (", ".join(INSTALLER_EXTENSIONS[:-1]) + " or " + INSTALLER_EXTENSIONS[-1], os.path.basename(installer))
            )
        if not os.path.isfile(installer):
            raise ProcessorError("The installer does not exist: %s" % installer)

        name = text_or_empty(self.env.get("cimian_name"))
        if (
            not name
            or len(name) > MAX_NAME_CHARS
            or not NAME_PATTERN.fullmatch(name)
        ):
            raise ProcessorError(
                "cimian_name must be an item name (letters, numbers, dots, "
                "underscores, hyphens; not beginning with '-' or '.'; at most %d "
                "characters): %r" % (MAX_NAME_CHARS, name[:40])
            )

        version = text_or_empty(self.env.get("version"))
        if version and (len(version) > MAX_VERSION_CHARS or not VERSION_PATTERN.fullmatch(version)):
            raise ProcessorError(
                "version must be a version label that begins with a digit and has "
                "only letters, numbers, dots, underscores and hyphens: %r" % version[:40]
            )
        if not version and extension == EXE_EXTENSION:
            raise ProcessorError(
                "An .exe needs a version: this processor never reads a version "
                "from the file. Read it with WindowsExeVersion, or give it."
            )

        subdirectory = None
        given_subdirectory = text_or_empty(self.env.get("cimian_subdirectory"))
        if given_subdirectory:
            subdirectory = check_subdirectory(given_subdirectory, "cimian_subdirectory")

        repo_text = text_or_empty(self.env.get("cimian_repo")) or text_or_empty(
            self.env.get(REPO_PREFERENCE)
        )
        if not repo_text:
            raise ProcessorError(
                "The repository is not set. Give cimian_repo, or set the AutoPkg "
                "preference %s. It is never in a recipe." % REPO_PREFERENCE
            )
        repo = os.path.abspath(os.path.expanduser(repo_text))
        if not os.path.isdir(repo):
            raise ProcessorError(
                "The Cimian repository is not a folder: %s. Is the share mounted?" % repo
            )
        for part in (PKGS_DIR, PKGSINFO_DIR):
            if not os.path.isdir(os.path.join(repo, part)):
                raise ProcessorError(
                    "The Cimian repository is not complete: it has no %s/ folder. Is the "
                    "share mounted, and is this the repository's root?" % part
                )

        extra = self.env.get("pkginfo")
        if extra is None or extra == "":
            extra = {}
        if not isinstance(extra, dict) or not all(isinstance(key, str) for key in extra):
            raise ProcessorError("pkginfo must be a dictionary with text keys.")
        check_extra_keys(extra)

        catalogs = self.catalogs_input()
        dry_run = parse_bool(self.env.get("cimian_dry_run", True), "cimian_dry_run")
        allow_unverified = parse_bool(
            self.env.get("cimian_allow_unverified", False), "cimian_allow_unverified"
        )
        replace_template = parse_bool(
            self.env.get("cimian_pkginfo_wins", False), "cimian_pkginfo_wins"
        )
        allow_product_change = parse_bool(
            self.env.get("cimian_allow_product_change", False), "cimian_allow_product_change"
        )
        architecture = normalize_architecture(text_or_empty(self.env.get("cimian_architecture")))
        if architecture and not ARCHITECTURE_PATTERN.fullmatch(architecture):
            raise ProcessorError(
                "cimian_architecture must be a word such as x64, x86 or arm64: %r" % architecture[:40]
            )
        path_value = text_or_empty(self.env.get("cimian_path")) or DEFAULT_PATH

        product_code = text_or_empty(self.env.get("msi_product_code"))
        upgrade_code = text_or_empty(self.env.get("msi_upgrade_code"))
        for key, value in (("msi_product_code", product_code), ("msi_upgrade_code", upgrade_code)):
            if value and not GUID_PATTERN.fullmatch(value):
                raise ProcessorError("%s must be a GUID in braces: %r" % (key, value[:50]))

        package = None
        package_notes = []
        if extension in APP_PACKAGE_EXTENSIONS:
            package = read_package_identity(installer)
            version, architecture = self.package_facts(package, version, architecture, package_notes)

        # The last check: it reads the whole installer, once. The hash is used again
        # for the pkginfo and for the copy.
        try:
            digest = sha256_of_file(installer)
            size = os.path.getsize(installer)
        except OSError as err:
            raise ProcessorError("Could not read %s: %s" % (installer, err))
        verified = self.check_verification(installer, digest)
        if not dry_run and not verified and not allow_unverified:
            raise ProcessorError(
                "The download was not verified: %s. Nothing was published. "
                "Publish by hand after checking the file, or set "
                "cimian_allow_unverified to true in the override." % UNVERIFIED_REASON
            )

        return {
            "installer": installer,
            "extension": extension,
            "name": name,
            "version": version,
            "subdirectory": subdirectory,
            "repo": repo,
            "extra": extra,
            "catalogs": catalogs,
            "dry_run": dry_run,
            "verified": verified,
            "replace_template": replace_template,
            "allow_product_change": allow_product_change,
            "architecture": architecture,
            "path": path_value,
            "msi_product_code": product_code,
            "msi_upgrade_code": upgrade_code,
            "package": package,
            "package_notes": package_notes,
            "sha256": digest,
            "size": size,
        }

    @staticmethod
    def package_facts(package, label, architecture, notes):
        """(version, architecture) of an app package. The version is the package's own
        Identity Version: a `version` input that is not that text is refused, as a label
        that is not an MSI's ProductVersion is. A single package's ProcessorArchitecture
        that names one is the installer's architecture: a `cimian_architecture` that
        names another is refused; neutral and a bundle name none."""
        if label and label != package.version:
            raise ProcessorError(
                "version is %s, but the package's own version (Identity Version of its manifest) is %s. "
                "For an app package the label must be that version: the client compares it with the "
                "version that Windows reports for the provisioned package." % (label, package.version)
            )
        if len(package.version) > MAX_VERSION_CHARS or not VERSION_PATTERN.fullmatch(package.version):
            raise ProcessorError("The package's version is not usable as a label: %r" % package.version[:40])
        notes.append(
            "NOTE: read from the %s: identity name %s, version %s%s."
            % ("bundle" if package.bundle else "package", package.name, package.version,
               " (the bundle's own version, not the application's)" if package.bundle
               else ", architecture %s" % (package.architecture or "not named"))
        )
        named = package.architecture
        if named in PACKAGE_ARCHITECTURES:
            named = normalize_architecture(named)
            if architecture and architecture != named:
                raise ProcessorError(
                    "cimian_architecture is %s, but the package is for %s (ProcessorArchitecture of its "
                    "manifest). The input is wrong, or the file is another package." % (architecture, named)
                )
            architecture = named
        elif named and named != NEUTRAL_ARCHITECTURE:
            notes.append(
                "NOTE: the package's ProcessorArchitecture %s is not one of %s or %s: it is not used."
                % (named[:20], ", ".join(PACKAGE_ARCHITECTURES), NEUTRAL_ARCHITECTURE)
            )
        return package.version, architecture

    def catalogs_input(self):
        value = self.env.get("cimian_catalogs", list(DEFAULT_CATALOGS))
        if isinstance(value, str):
            value = [part.strip() for part in value.split(",")]
        if (
            not isinstance(value, (list, tuple))
            or not value
            or not all(isinstance(item, str) and item.strip() for item in value)
        ):
            raise ProcessorError("cimian_catalogs must be a list of catalog names.")
        return [item.strip() for item in value]

    def check_verification(self, installer, actual):
        """True when the download counts as verified by one of VERIFICATIONS: its
        flag is exactly true (a boolean; text does not count) and its hash is the
        SHA-256 of the installer, which `actual` is. A pair whose flag is not true,
        or whose hash is missing or is not a SHA-256, does not count. A pair whose
        flag is true and whose hash is a SHA-256 of another file is an error: the
        file that was verified is not the file that is imported. Each pair is
        checked, so that one of them cannot hide the other's error."""
        verified = False
        for flag, hash_variable, kind in VERIFICATIONS:
            if self.env.get(flag) is not True:
                continue
            claimed = normalize_sha256(self.env.get(hash_variable))
            if claimed is None:
                continue
            if claimed != actual:
                raise ProcessorError(
                    "The file to import is not the file whose %s was verified: "
                    "%s is %s, but %s has the SHA-256 %s. Nothing was published."
                    % (kind, hash_variable, shorten(claimed), os.path.basename(installer), shorten(actual))
                )
            verified = True
        return verified

    # ---- the repository ----

    @staticmethod
    def load_yaml():
        try:
            import yaml
        except ImportError:
            raise ProcessorError(
                "PyYAML is not available in the Python that runs this processor. "
                "AutoPkg's own Python has it (AutoPkg reads YAML recipes). "
                "CimianImporter reads and writes the pkginfo files with it."
            )
        return yaml

    @staticmethod
    def scan_repository(yaml_loader, yaml, repo, name):
        """The pkginfo files of the repository that have this item's name (a
        list of PkgInfo) and the paths, relative to the repository, of the files
        that could be an item of this name but cannot be read. A file that does
        not hold the name as text cannot be it, and is not read."""
        wanted = name.lower()
        found = []
        unreadable = []
        base = os.path.join(repo, PKGSINFO_DIR)
        for folder, dirs, files in os.walk(base):
            dirs.sort()
            for file_name in sorted(files):
                if file_name.startswith(".") or not file_name.lower().endswith(PKGINFO_SUFFIX):
                    continue
                path = os.path.join(folder, file_name)
                relpath = os.path.relpath(path, repo).replace(os.sep, "/")
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        text = handle.read()
                except (OSError, UnicodeDecodeError):
                    unreadable.append(relpath)
                    continue
                if wanted not in text.lower():
                    continue
                try:
                    data = yaml.load(text, Loader=yaml_loader)
                except (yaml.YAMLError, ValueError, RecursionError):
                    unreadable.append(relpath)
                    continue
                if not isinstance(data, dict) or not isinstance(data.get("name"), str):
                    continue
                if data["name"].strip().lower() != wanted:
                    continue
                if data.get("version") is None or not str(data["version"]).strip():
                    unreadable.append(relpath)
                    continue
                found.append(PkgInfo(relpath, data))
        return found, unreadable

    @staticmethod
    def choose_template(entries):
        """The pkginfo with the highest version, in the client's order. Ties go
        to the later path. A version that the client cannot read is not ranked."""
        best = None
        for entry in entries:
            if version_parts(entry.version) is None:
                continue
            if best is None:
                best = entry
                continue
            order = compare_versions(entry.version, best.version)
            if order > 0 or (order == 0 and entry.relpath > best.relpath):
                best = entry
        return best

    # ---- MSI facts ----

    def read_msi_facts(self, settings):
        """The facts of the MSI that the pkginfo needs, from msiinfo, or None
        when msiinfo is not on the PATH."""
        executable = shutil.which(MSIINFO, path=settings["path"])
        if executable is None:
            return None
        environment = {
            "PATH": settings["path"],
            "HOME": os.environ.get("HOME") or os.path.expanduser("~"),
        }
        try:
            done = subprocess.run(
                [executable, "export", settings["installer"], "Property"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                timeout=MSIINFO_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            raise ProcessorError("msiinfo did not finish in %d seconds." % MSIINFO_TIMEOUT_SECONDS)
        except OSError as err:
            raise ProcessorError("msiinfo could not be started: %s" % err)
        if done.returncode != 0:
            detail = done.stderr.decode("utf-8", errors="replace").strip().splitlines()
            raise ProcessorError(
                "msiinfo could not read %s (exit code %d)%s"
                % (os.path.basename(settings["installer"]), done.returncode,
                   ": " + clip(detail[-1]) if detail else ".")
            )
        facts = parse_property_export(done.stdout.decode("utf-8", errors="replace"))
        for key, pattern in (("ProductCode", GUID_PATTERN), ("UpgradeCode", GUID_PATTERN),
                             ("ProductVersion", VERSION_PATTERN)):
            if key in facts and not pattern.fullmatch(facts[key]):
                raise ProcessorError("msiinfo reports a %s that is not valid: %r" % (key, facts[key][:50]))
        return facts

    def msi_facts(self, settings, facts):
        """(version, product code, upgrade code, notes) of an MSI, from msiinfo
        and the inputs. An input that msiinfo contradicts is an error; facts that
        nothing gives are an error that names them, in a dry run too."""
        label = settings["version"]
        given_product = settings["msi_product_code"]
        given_upgrade = settings["msi_upgrade_code"]
        notes = []
        if facts is None:
            missing = []
            if not label:
                missing.append("version (the MSI's ProductVersion)")
            if not given_product:
                missing.append("msi_product_code")
            if not given_upgrade:
                missing.append("msi_upgrade_code")
            if missing:
                raise ProcessorError(
                    "msiinfo is not on the PATH (%s), so these facts of the MSI must be "
                    "given: %s. Install msitools, or give them in the recipe or the override "
                    "(an argument of the recipe's step wins over an override's Input: a recipe "
                    "whose step passes its own version cannot be given one)."
                    % (settings["path"], ", ".join(missing))
                )
            notes.append(
                "NOTE: msiinfo was not found; the version and the codes are those that "
                "the recipe or the override gave, and nothing checked them against the MSI."
            )
            return label, given_product, given_upgrade, notes
        for key, given, read in (
            ("msi_product_code", given_product, facts.get("ProductCode")),
            ("msi_upgrade_code", given_upgrade, facts.get("UpgradeCode")),
        ):
            if given and read and given.lower() != read.lower():
                raise ProcessorError(
                    "%s is %s, but the MSI says %s. The input is wrong, or the file is "
                    "another product." % (key, given, read)
                )
        product_version = facts.get("ProductVersion")
        if not product_version:
            raise ProcessorError("msiinfo did not report a ProductVersion for this MSI.")
        if label and label != product_version:
            raise ProcessorError(
                "version is %s, but the MSI's own ProductVersion is %s. For an MSI the "
                "label must be the ProductVersion: the client compares it with the "
                "version that Windows Installer records." % (label, product_version)
            )
        product_code = facts.get("ProductCode") or given_product
        if not product_code:
            raise ProcessorError("msiinfo did not report a ProductCode for this MSI.")
        upgrade_code = facts.get("UpgradeCode") or given_upgrade
        if not upgrade_code:
            notes.append(
                "WARNING: the MSI has no UpgradeCode: the install check has a product code "
                "only, and the client cannot tell this version from an update of it."
            )
        return product_version, product_code, upgrade_code, notes

    # ---- building the pkginfo ----

    def build_pkginfo(self, settings, template, facts):
        """The pkginfo of the new version, and the lines to say (notes). `facts`
        is (version, product code, upgrade code) for an MSI, else None."""
        notes = []
        label = settings["version"]
        kind = installer_kind(settings["extension"])
        location = settings["location"]
        if template is None:
            data = {
                "name": settings["name"],
                "version": label,
                "catalogs": list(settings["catalogs"]),
            }
            if settings["architecture"]:
                data["supported_architectures"] = [settings["architecture"]]
            data["installer"] = {}
            put_installer_fields(data["installer"], location, settings["sha256"], settings["size"], kind)
            if kind == "msi":
                entry = {"type": "msi", "product_code": facts[1]}
                if facts[2]:
                    entry["upgrade_code"] = facts[2]
                entry["version"] = label
                data["installs"] = [entry]
            merge_into(data, settings["extra"])
        else:
            data = copy.deepcopy(template.data)
            dropped = []
            self.carry_template(data, template, settings, notes, dropped)
            merge_pkginfo_into_template(data, settings["extra"], settings["replace_template"], notes)
            self.check_dropped_hashes(data, dropped, notes)
            if settings["restrict_architecture"] and not data.get("supported_architectures"):
                # The template is for all architectures, another file of the item names one. The client keeps
                # the highest version among the files for a PC's architecture or for all
                # (CatalogService.cs:43-56): a copy for all would take the other architecture's PCs to this installer.
                data["supported_architectures"] = [settings["architecture"]]
                notes.append(
                    "NOTE: the template is for all architectures and another pkginfo of the item names one: this "
                    "version is written for %s only (supported_architectures)." % settings["architecture"]
                )
        if kind == "msi":
            self.apply_msi_facts(data, facts, notes, template is not None, settings["allow_product_change"])
        if kind == APP_PACKAGE_KIND:
            self.apply_package_facts(data, settings["package"], label, notes, template is not None)
        self.check_versions_readable(data)
        if template is None:
            data = order_pkginfo(data)
            if kind == "exe" and not any(data.get(key) for key in ("installs", "check", "installcheck_script")):
                notes.append(
                    "WARNING: this pkginfo has no install check (no installs, check or "
                    "installcheck_script): the client treats an item with no check as not "
                    "installed unless the ManagedInstalls registry has a trace of it. Add a "
                    "check by hand, or give one in pkginfo."
                )
        else:
            notes.append(
                "NOTE: this pkginfo is a copy of the template %s %s. Apart from the keys that belong to "
                "the file and the keys that the notes above name, it is as the template has it."
                % (data.get("name"), template.version)
            )
        return data, notes

    def carry_template(self, data, template, settings, notes, dropped):
        """Make a copy of the template's pkginfo into the pkginfo of the new
        version: replace what belongs to the file and say what was dropped or
        left."""
        label = settings["version"]
        old = template.version
        kind = installer_kind(settings["extension"])
        data["version"] = label

        installer = data.get("installer")
        if not isinstance(installer, dict):
            installer = {}
            data["installer"] = installer
        written_type = installer.get("type")
        written = written_type.strip().lower() if isinstance(written_type, str) else ""
        if kind == APP_PACKAGE_KIND and written in APP_PACKAGE_TYPES:
            # The client installs both types as an app package (InstallerService.cs, the msix or appx case).
            if written != kind:
                notes.append(
                    "NOTE: the template's installer.type is %s: the new version is written with %s, which the "
                    "client installs the same way." % (written, kind)
                )
        elif written and written != kind:
            raise ProcessorError(
                "The template %s %s is of the kind %s, and the file is an %s. Its install "
                "arguments and checks are those of another kind of installer. Make a new "
                "item by hand." % (data.get("name"), old, written, settings["extension"])
            )
        put_installer_fields(installer, settings["location"], settings["sha256"], settings["size"], kind)

        for key in NOT_CARRIED_KEYS:
            if key in data:
                del data[key]
                notes.append(
                    "NOTE: %s of the template is not carried over: once its date has passed, "
                    "the client installs the new version wherever the item is listed as optional "
                    "and ignores the install window. Whoever publishes a version decides that "
                    "for it." % key
                )

        check = data.get("check")
        if isinstance(check, dict):
            for part in ("registry", "file"):
                entry = check.get(part)
                if isinstance(entry, dict):
                    self.carry_entry("check.%s" % part, entry, old, label, notes, dropped, "check.file" if part == "file" else "")
        installs = data.get("installs")
        if isinstance(installs, list):
            for number, entry in enumerate(installs, start=1):
                if isinstance(entry, dict) and kind == APP_PACKAGE_KIND and install_check_type(entry) == APP_PACKAGE_KIND:
                    continue  # the package's own entry: apply_package_facts
                if isinstance(entry, dict) and install_check_type(entry) != "msi":
                    self.carry_entry(
                        "installs[%d]" % number, entry, old, label, notes, dropped,
                        "installs.file" if install_check_type(entry) == "file" else "",
                    )
                elif isinstance(entry, dict) and kind != "msi":
                    notes.append(
                        "WARNING: installs[%d] is an msi entry with the codes of the template's "
                        "installer, and the new file is not an .msi: carried unchanged. Read it."
                        % number
                    )

        if "." in old:
            literal = re.compile(
                r"(?<![0-9A-Za-z.])%s(?![0-9A-Za-z]|\.[0-9])" % re.escape(old)
            )
            shown = 0
            for path, text in walk_strings(data, ""):
                if path.endswith(".version") or path == "version":
                    continue
                if literal.search(text):
                    if shown < MAX_OLD_VERSION_WARNINGS:
                        notes.append(
                            "WARNING: %s contains the template's version %s. It is kept, but a script "
                            "or a path that names the old version can be wrong for the new one: "
                            "check it." % (path, old)
                        )
                    shown += 1
            if shown > MAX_OLD_VERSION_WARNINGS:
                notes.append(
                    "WARNING: %d more texts contain the template's version %s."
                    % (shown - MAX_OLD_VERSION_WARNINGS, old)
                )

    @staticmethod
    def carry_entry(where, entry, old, label, notes, dropped, role):
        """A version that is the template's version becomes the new version; any
        other is kept and said. A hash belongs to a file of the old version and
        is dropped."""
        if "version" in entry:
            was = str(entry["version"])
            if same_version(was, old):
                entry["version"] = label
            else:
                notes.append(
                    "WARNING: %s.version is %s, not the template's version %s: it is kept as it is. "
                    "A file can carry another version than its installer, so it may be right, or it "
                    "may be stale. Check it." % (where, was, old)
                )
        for key in ("hash", "md5checksum"):
            if key in entry:
                del entry[key]
                notes.append(
                    "NOTE: %s.%s belongs to a file of the old version: it is not carried, so the "
                    "client no longer checks that file's hash." % (where, key)
                )
                if role:
                    dropped.append((where, entry, role))

    @staticmethod
    def check_versions_readable(data):
        """A `version` inside `check` or `installs` that the client cannot read as a version is read as equal to
        every other (CatalogService.cs:260-275, an unreadable version compares equal), so the item would count
        as installed whatever is on the PC and never be updated. Such a value stops the run, naming the entry.
        An empty value is no version (the client tests for emptiness)."""
        places = []
        check = data.get("check")
        if isinstance(check, dict):
            for part in ("registry", "file"):
                if isinstance(check.get(part), dict):
                    places.append(("check.%s" % part, check[part]))
        installs = data.get("installs")
        if isinstance(installs, list):
            places.extend(("installs[%d]" % number, entry) for number, entry in enumerate(installs, start=1) if isinstance(entry, dict))
        for where, entry in places:
            value = entry.get("version")
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            if version_parts(str(value)) is None:
                raise ProcessorError(
                    "%s.version is %r, which the client cannot read as a version: it would read it as equal to "
                    "every version, so the item would count as installed whatever is on the PC and would never be "
                    "updated. Give a real version, or leave the key out. Nothing was written." % (where, str(value)[:40])
                )

    @staticmethod
    def check_dropped_hashes(data, dropped, notes):
        """A check that had a hash and has no version once the hash is gone cannot tell an
        old file from a new one. A file check with no version only tests that the file exists
        (StatusService.cs:1578-1610), so every old version would count as installed and the
        item would never be updated. An `installs` entry for a file with no version of its own
        is compared with the item's version, and a file without version data can then never be
        confirmed as installed (StatusService.cs:632 and :670-680), so the item would install
        again at every run. Both stop the run, naming the entry, but only when the client
        will use that check (`check_the_client_uses`); the entry may be given a version in the
        template (in the repository) or in `pkginfo`, and an entry that `pkginfo` replaced is the
        person's own."""
        advice = (
            "Give it a version in the repository (add `version:` with the template's own version to that check "
            "in the template's pkginfo: this importer then replaces it with the version of every new release), "
            "or a literal version in the override's pkginfo (it then stays that version until it is changed), "
            "or use another install check, and run again. Nothing was written."
        )
        used = check_the_client_uses(data)
        for where, entry, role in dropped:
            if "version" in entry:
                continue
            if role == "check.file":
                check = data.get("check")
                if not isinstance(check, dict) or check.get("file") is not entry or used != "check.file":
                    continue
                raise ProcessorError(
                    "The template's %s had a hash and no version. Without the hash it only tests that the "
                    "file exists, so any old version would count as installed and the item would never be "
                    "updated. %s" % (where, advice)
                )
            installs = data.get("installs")
            if used != "installs" or not isinstance(installs, list) or not any(item is entry for item in installs):
                continue
            path = str(entry.get("path") or "").strip().lower()
            if path.endswith(FILES_WITH_VERSION_DATA):
                notes.append(
                    "WARNING: the template's %s had a hash and no version. The client now compares the file's "
                    "own version with the item's version, and the item installs again at every run if the "
                    "file's version is lower than the label." % where
                )
            else:
                raise ProcessorError(
                    "The template's %s is a file with a hash and no version, and the file has no version data of "
                    "its own to read. Without the hash the client can never confirm it as installed, so the item "
                    "would install again at every run. %s" % (where, advice)
                )

    @staticmethod
    def apply_msi_facts(data, facts, notes, template_mode, allow_change):
        """The codes and the version of the MSI into the pkginfo.

        With a template, the entry of `installs` that is this product's gets the new codes and
        version: the only msi entry, or the one that has the new MSI's upgrade code. Another msi
        entry (a prerequisite, say) is kept and said. The older form (`installer.product_code`)
        follows, and so does `uninstaller[].product_code` when it is the old product code: the client
        runs that uninstaller first and takes an unknown product for removed (InstallerService.cs,
        727-737 and 1507-1548). An upgrade code that is not the template's is refused unless
        `allow_change`: Windows Installer does not upgrade across upgrade codes.

        Without a template, an msi entry that `pkginfo` gave gets the codes it lacks; one with other
        codes than the MSI's is refused; an entry is added when there is none."""
        version, product_code, upgrade_code = facts[0], facts[1], facts[2]
        installs = data.get("installs")
        entries = (
            [item for item in installs if isinstance(item, dict) and install_check_type(item) == "msi"]
            if isinstance(installs, list) else []
        )
        installer = data.get("installer") if isinstance(data.get("installer"), dict) else {}

        def other_upgrade(was):
            """True when the template (or pkginfo) names an upgrade code and the MSI has another, or none."""
            return isinstance(was, str) and bool(was.strip()) and (not upgrade_code or was.lower() != upgrade_code.lower())

        def set_codes(entry):
            entry["product_code"] = product_code
            if upgrade_code:
                entry["upgrade_code"] = upgrade_code
            elif "upgrade_code" in entry:
                del entry["upgrade_code"]
            if "version" in entry:
                entry["version"] = version

        old_codes = set()
        if template_mode:
            own = None
            if len(entries) == 1:
                own = entries[0]
            elif len(entries) > 1:
                matching = [
                    item for item in entries
                    if upgrade_code and str(item.get("upgrade_code", "")).lower() == upgrade_code.lower()
                ]
                if len(matching) != 1:
                    raise ProcessorError(
                        "The template has %d msi entries in installs, and %s of them has the new MSI's upgrade "
                        "code: it cannot be told which one is this product. Nothing was written."
                        % (len(entries), "none" if not matching else str(len(matching)))
                    )
                own = matching[0]
            changed_upgrade = False
            for entry in entries:
                if entry is not own:
                    number = [i for i, item in enumerate(installs, start=1) if item is entry][0]
                    notes.append(
                        "WARNING: installs[%d] is another msi entry, not this product's: it is kept as it is." % number
                    )
            if own is not None:
                if isinstance(own.get("product_code"), str):
                    old_codes.add(own["product_code"].lower())
                changed_upgrade = changed_upgrade or other_upgrade(own.get("upgrade_code"))
                set_codes(own)
            if installer:
                if isinstance(installer.get("product_code"), str):
                    old_codes.add(installer["product_code"].lower())
                changed_upgrade = changed_upgrade or other_upgrade(installer.get("upgrade_code"))
            if changed_upgrade:
                if not allow_change:
                    raise ProcessorError(
                        "The upgrade code of this MSI (%s) is not the template's. It may be another product, or "
                        "the vendor changed the code (or left it out); Windows Installer does not upgrade across "
                        "upgrade codes, so PCs could end up with both products. Nothing was written. Set "
                        "cimian_allow_product_change to true in the override if the change is meant."
                        % (upgrade_code or "none")
                    )
                notes.append(
                    "WARNING: the upgrade code of the MSI is not the template's, and cimian_allow_product_change is "
                    "true: the new version gets the MSI's codes; the client will not see the old product as this item's."
                )
            uninstaller = data.get("uninstaller")
            if isinstance(uninstaller, list):
                for number, entry in enumerate(uninstaller, start=1):
                    if not isinstance(entry, dict):
                        continue
                    written = entry.get("type")
                    if isinstance(written, str) and written.strip() and written.strip().lower() != "msi":
                        continue
                    code = entry.get("product_code")
                    if not isinstance(code, str) or not code:
                        continue
                    if code.lower() in old_codes:
                        entry["product_code"] = product_code
                        notes.append("NOTE: uninstaller[%d].product_code was the old product code: it is now the new MSI's." % number)
                    else:
                        notes.append(
                            "WARNING: uninstaller[%d].product_code is not the template's product code: it is kept "
                            "as it is. Check that removal still finds the product." % number
                        )
        else:
            for entry in entries:
                code = entry.get("product_code")
                if isinstance(code, str) and code and code.lower() != product_code.lower():
                    raise ProcessorError(
                        "pkginfo has an msi entry in installs with the product code %s, but the MSI's is %s. "
                        "The codes are read from the MSI: leave them out of pkginfo." % (code, product_code)
                    )
                if other_upgrade(entry.get("upgrade_code")):
                    raise ProcessorError(
                        "pkginfo has an msi entry in installs with the upgrade code %s, but the MSI's is %s. "
                        "The codes are read from the MSI: leave them out of pkginfo."
                        % (entry.get("upgrade_code"), upgrade_code or "none")
                    )
                set_codes(entry)
            if not entries:
                entry = {"type": "msi", "product_code": product_code}
                if upgrade_code:
                    entry["upgrade_code"] = upgrade_code
                entry["version"] = version
                if isinstance(installs, list):
                    installs.append(entry)
                else:
                    data["installs"] = [entry]
        for key, value in (("product_code", product_code), ("upgrade_code", upgrade_code)):
            if key in installer:
                if value:
                    installer[key] = value
                else:
                    del installer[key]

    @staticmethod
    def apply_package_facts(data, package, label, notes, template_mode):
        """The identity of an app package into the pkginfo.

        The `installs` entry `{type: msix, identity_name, version}` is the install check, and the
        client's install and removal find the package by its identity name (InstallerService.cs,
        BuildMsixInstallScript; StatusService.cs, the msix check). With a template, the entry of
        `installs` that is this package's gets the new version: the only msix entry, whose identity
        name must be the package's (another one is another product), or, when there are several, the
        one with the package's identity name. Without a template, every msix entry that `pkginfo` gave
        must name this package. An entry is added, with a NOTE for a template, when there is none.
        An app package takes no installer arguments, no success codes and no Windows Installer codes:
        such a key from the template or from `pkginfo` stops the run."""
        installer = data.get("installer") if isinstance(data.get("installer"), dict) else {}
        refused = [key for key in APP_PACKAGE_REFUSED_INSTALLER_KEYS if key in installer]
        if refused:
            raise ProcessorError(
                "The pkginfo has %s (from the template or the input pkginfo), and an app package takes none: "
                "the client provisions it with Add-AppxProvisionedPackage, passes no arguments and reads no "
                "success codes or product codes. Remove it. Nothing was written."
                % ", ".join("installer." + key for key in refused)
            )
        wanted = package.name.lower()
        installs = data.get("installs")
        entries = (
            [item for item in installs if isinstance(item, dict) and install_check_type(item) == APP_PACKAGE_KIND]
            if isinstance(installs, list) else []
        )

        def identity_of(entry):
            value = entry.get("identity_name")
            return value.strip() if isinstance(value, str) else ""

        def set_identity(entry):
            if identity_of(entry) and identity_of(entry) != package.name:
                notes.append(
                    "NOTE: the msix entry of installs writes the identity name as %s: it is now the package's own "
                    "spelling, %s." % (identity_of(entry), package.name)
                )
            entry["identity_name"] = package.name
            entry["version"] = label

        def number_of(entry):
            return [i for i, item in enumerate(installs, start=1) if item is entry][0]

        if template_mode:
            own = None
            if len(entries) == 1:
                own = entries[0]
                if identity_of(own).lower() != wanted:
                    raise ProcessorError(
                        "The template's msix entry in installs has the identity name %s, and the package's is %s: "
                        "it is another product. Make a new item for it. Nothing was written."
                        % (identity_of(own) or "none", package.name)
                    )
            elif len(entries) > 1:
                matching = [item for item in entries if identity_of(item).lower() == wanted]
                if len(matching) != 1:
                    raise ProcessorError(
                        "The template has %d msix entries in installs, and %s of them has the package's identity "
                        "name %s: it cannot be told which one is this package. Nothing was written."
                        % (len(entries), "none" if not matching else str(len(matching)), package.name)
                    )
                own = matching[0]
                for entry in entries:
                    if entry is not own:
                        notes.append(
                            "WARNING: installs[%d] is another msix entry, not this package's: it is kept as it is."
                            % number_of(entry)
                        )
            if own is not None:
                set_identity(own)
                return
        else:
            for entry in entries:
                if identity_of(entry) and identity_of(entry).lower() != wanted:
                    raise ProcessorError(
                        "pkginfo has an msix entry in installs with the identity name %s, but the package's is %s. "
                        "The identity is read from the package: leave it out of pkginfo."
                        % (identity_of(entry), package.name)
                    )
                set_identity(entry)
            if entries:
                return
        entry = {"type": APP_PACKAGE_KIND, "identity_name": package.name, "version": label}
        if isinstance(installs, list):
            installs.append(entry)
        else:
            data["installs"] = [entry]
        if template_mode:
            notes.append(
                "NOTE: the template has no msix entry in installs: one is added for %s %s. It is the install "
                "check, and the client finds the package by it." % (package.name, label)
            )

    # ---- writing ----

    @staticmethod
    def check_inside(base, folder, what):
        """Refuse a folder that would lead out of `base`: its deepest part that
        exists must resolve to a place inside `base` (a link of `pkgs/` itself
        may point elsewhere; a link below it may not)."""
        probe = folder
        while not os.path.lexists(probe):
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent
        real_base = os.path.realpath(base)
        real_probe = os.path.realpath(probe)
        try:
            inside = os.path.commonpath([real_base, real_probe]) == real_base
        except ValueError:
            inside = False
        if not inside:
            raise ProcessorError(
                "%s leaves the repository: %s resolves to a place outside %s." % (what, folder, base)
            )

    @staticmethod
    def move_into_place(temp_path, target):
        """Move a finished file to its place without ever replacing a file that
        is there: a hard link fails when the target exists; where links are not
        possible, the target is checked and the file is renamed."""
        try:
            os.link(temp_path, target)
        except FileExistsError:
            raise ProcessorError(
                "%s exists and is never overwritten." % os.path.basename(target)
            )
        except OSError:
            if os.path.lexists(target):
                raise ProcessorError(
                    "%s exists and is never overwritten." % os.path.basename(target)
                )
            os.rename(temp_path, target)
            return
        os.unlink(temp_path)

    def copy_installer(self, source, target, expected_sha256):
        """Copy beside the target, check that what was written has the hash of
        the file that was verified, and move it into place."""
        folder = os.path.dirname(target)
        os.makedirs(folder, exist_ok=True)
        handle, temp_path = tempfile.mkstemp(
            prefix=".%s." % os.path.basename(target), suffix=".cimian-new.tmp", dir=folder
        )
        try:
            digest = hashlib.sha256()
            with os.fdopen(handle, "wb") as out, open(source, "rb") as src:
                for block in iter(lambda: src.read(READ_BLOCK_BYTES), b""):
                    digest.update(block)
                    out.write(block)
                out.flush()
                os.fsync(out.fileno())
            if digest.hexdigest() != expected_sha256:
                raise ProcessorError(
                    "The installer changed while it was copied (the copy has the SHA-256 %s, "
                    "not %s). Nothing was published." % (shorten(digest.hexdigest()), shorten(expected_sha256))
                )
            os.chmod(temp_path, 0o644)
            self.move_into_place(temp_path, target)
        finally:
            if os.path.lexists(temp_path):
                os.unlink(temp_path)

    @staticmethod
    def render_pkginfo(yaml, loader, dumper, data):
        """The text of the pkginfo, and a check that it reads back as what was
        meant. Made before anything is written, in a dry run too."""
        try:
            text = yaml.dump(
                data, Dumper=dumper, sort_keys=False, default_flow_style=False,
                allow_unicode=True, width=80,
            )
        except yaml.YAMLError as err:
            raise ProcessorError("The pkginfo cannot be written as YAML: %s" % err)
        if not text.endswith("\n"):
            text += "\n"
        if yaml.load(text, Loader=loader) != data:
            raise ProcessorError(
                "The pkginfo that was made does not read back as what was meant. "
                "Nothing was written."
            )
        return text

    def write_pkginfo(self, text, target):
        """Write the text beside the target and move it into place."""
        folder = os.path.dirname(target)
        os.makedirs(folder, exist_ok=True)
        handle, temp_path = tempfile.mkstemp(
            prefix=".%s." % os.path.basename(target), suffix=".tmp", dir=folder
        )
        try:
            with os.fdopen(handle, "wb") as out:
                out.write(text.encode("utf-8"))
                out.flush()
                os.fsync(out.fileno())
            os.chmod(temp_path, 0o644)
            self.move_into_place(temp_path, target)
        finally:
            if os.path.lexists(temp_path):
                os.unlink(temp_path)

    # ---- the run ----

    def say(self, head, notes):
        """The lines that say what the run did, and then its notes. The head is always
        shown whole (it holds the result and the warning for an unverified download); only
        the notes are cut."""
        for line in head:
            self.output(clip(line), verbose_level=ALWAYS_SHOWN)
        for line in notes[:MAX_LINES_SHOWN]:
            self.output(clip(line), verbose_level=ALWAYS_SHOWN)
        if len(notes) > MAX_LINES_SHOWN:
            self.output(
                "... and %d more lines." % (len(notes) - MAX_LINES_SHOWN), verbose_level=ALWAYS_SHOWN
            )

    def nothing_new(self, repo, entry, why):
        """The repository has what this run would publish: say so, write nothing."""
        self.env["cimian_result"] = RESULT_NOTHING_NEW
        self.env["cimian_repo_changed"] = False
        self.env["cimian_version_imported"] = entry.version
        self.env["cimian_pkginfo_path"] = os.path.join(repo, *entry.relpath.split("/"))
        self.output(
            "Nothing new: %s %s is in the repository already (%s). Nothing was written."
            % (entry.data["name"], entry.version, why),
            verbose_level=ALWAYS_SHOWN,
        )

    def main(self):
        settings = self.read_inputs()
        yaml = self.load_yaml()
        loader, dumper = make_yaml_classes(yaml)
        repo = settings["repo"]
        name = settings["name"]

        entries, unreadable = self.scan_repository(loader, yaml, repo, name)
        notes = list(settings["package_notes"])
        if unreadable:
            notes.append(
                "NOTE: %d pkginfo file(s) could not be read and were left out: %s"
                % (len(unreadable), ", ".join(unreadable[:3]) + (", ..." if len(unreadable) > 3 else ""))
            )

        # An item can have pkginfo files for several architectures. The client keeps the highest
        # version among those for the PC's architecture (CatalogService.cs:43-56), so the template
        # and "nothing new" are decided among the files for the architecture of this installer.
        architecture = settings["architecture"]
        if architecture:
            candidates = [item for item in entries if not item.architectures or architecture in item.architectures]
            if entries and not candidates and not unreadable:
                notes.append(
                    "NOTE: the repository has pkginfo files of %s for other architectures only: there is no "
                    "template for %s." % (name, architecture)
                )
        else:
            candidates = entries
        for entry in candidates:
            if entry.installer_hash == settings["sha256"]:
                self.nothing_new(repo, entry, "it has this very installer file")
                self.say([], notes)
                return
        if not architecture:
            named = sorted({",".join(sorted(item.architectures)) for item in entries if item.architectures})
            for_all = any(not item.architectures for item in entries)
            if len(named) > 1:
                raise ProcessorError(
                    "The repository has pkginfo files of %s for several architectures (%s). Give "
                    "cimian_architecture, the architecture of this installer, so that the template and "
                    "'nothing new' are decided among the files for it. Nothing was written."
                    % (name, "; ".join(named + (["all"] if for_all else [])))
                )
            if named and for_all:
                notes.append(
                    "NOTE: the repository has pkginfo files of %s for all architectures and files for %s: this "
                    "installer is taken to be for %s. Give cimian_architecture if it is not." % (name, named[0], named[0])
                )

        template = self.choose_template(candidates)
        if template is None and (candidates or unreadable):
            if unreadable:
                raise ProcessorError(
                    "No template was found, and %d pkginfo file(s) of the repository could not "
                    "be read (%s): the template may be among them. Nothing was written."
                    % (len(unreadable), ", ".join(unreadable[:3]))
                )
            raise ProcessorError(
                "The repository has pkginfo files for %s, but none with a version that Cimian "
                "can read, so no template can be chosen. Nothing was written." % name
            )
        if template is not None and template.data["name"] != name:
            notes.append(
                "NOTE: the repository writes the name as %s, and that is kept (the client "
                "reads names without regard to case)." % template.data["name"]
            )
            settings["name"] = name = template.data["name"]
            if not NAME_PATTERN.fullmatch(name) or len(name) > MAX_NAME_CHARS:
                raise ProcessorError(
                    "The template's name is not one that this processor writes into a file name: %r"
                    % name[:40]
                )

        settings["restrict_architecture"] = bool(
            architecture and template is not None and not template.architectures
            and any(item.architectures for item in entries)
        )
        facts = None
        if settings["extension"] == MSI_EXTENSION:
            read = self.read_msi_facts(settings)
            version, product_code, upgrade_code, msi_notes = self.msi_facts(settings, read)
            notes.extend(msi_notes)
            settings["version"] = version
            facts = (version, product_code, upgrade_code)
            if not VERSION_PATTERN.fullmatch(version) or len(version) > MAX_VERSION_CHARS:
                raise ProcessorError("The MSI's version is not usable as a label: %r" % version[:40])
        label = settings["version"]

        # The input pkginfo: variables that a download step has set since AutoPkg replaced the Input
        # (`version`, say) are replaced here, `version` by the label; one that stays is refused.
        variables = {key: value for key, value in self.env.items()
                     if isinstance(key, str) and isinstance(value, (str, int)) and not isinstance(value, bool)}
        variables["version"] = label
        unresolved = []
        settings["extra"] = resolve_variables(settings["extra"], variables, "", unresolved)
        if unresolved:
            raise ProcessorError(
                "pkginfo holds %s, but no variable of that name has a value when the importer runs (AutoPkg replaces the "
                "variables of an Input before the steps run, and leaves the ones that nothing has set yet as they are). "
                "Check the name, or write the text without percent signs. Nothing was written."
                % ", ".join("%%%s%% in %s" % (name, where) for where, name in unresolved[:3])
            )

        for entry in candidates:
            if same_version(entry.version, label):
                self.nothing_new(repo, entry, "it has this version")
                if entry.installer_hash and entry.installer_hash != settings["sha256"]:
                    self.output(
                        "NOTE: the repository's %s %s has another installer file; nothing was "
                        "written. To publish this file, give it a version of its own." % (name, label),
                        verbose_level=ALWAYS_SHOWN,
                    )
                self.say([], notes)
                return

        subdirectory = settings["subdirectory"]
        if subdirectory is None:
            subdirectory = ""
            if template is not None:
                installer = template.data.get("installer")
                written = installer.get("location") if isinstance(installer, dict) else None
                if isinstance(written, str) and written.strip():
                    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", written.strip()):
                        raise ProcessorError(
                            "The template's installer.location is an address, not a place under pkgs/. "
                            "Give cimian_subdirectory."
                        )
                    # A location may begin with a slash or a backslash: Cimian's own importer writes it
                    # so, and the client and makecatalogs read it as relative to pkgs/
                    # (DownloadService.cs:442-452, CatalogBuilder.cs:96).
                    subdirectory = check_subdirectory(
                        os.path.dirname(written.strip().replace("\\", "/").lstrip("/")),
                        "the folder of the template's installer.location",
                        allow_empty=True,
                    )
        base_name = "%s-%s" % (name, label)
        file_name = base_name + settings["extension"]
        installer_folder = os.path.join(repo, PKGS_DIR, *subdirectory.split("/")) if subdirectory else os.path.join(repo, PKGS_DIR)
        pkginfo_folder = os.path.join(repo, PKGSINFO_DIR, *subdirectory.split("/")) if subdirectory else os.path.join(repo, PKGSINFO_DIR)
        self.check_inside(os.path.join(repo, PKGS_DIR), installer_folder, "The installer's folder")
        self.check_inside(os.path.join(repo, PKGSINFO_DIR), pkginfo_folder, "The pkginfo's folder")
        installer_target = os.path.join(installer_folder, file_name)
        pkginfo_target = os.path.join(pkginfo_folder, base_name + PKGINFO_SUFFIX)
        settings["location"] = "%s/%s" % (subdirectory, file_name) if subdirectory else file_name

        if os.path.lexists(pkginfo_target):
            relative = os.path.relpath(pkginfo_target, repo).replace(os.sep, "/")
            holder = [item for item in entries if item.relpath == relative]
            if holder:
                raise ProcessorError(
                    "%s is the pkginfo of %s %s for other architectures (%s); files are named after the item "
                    "and the version only, and it is never overwritten. Give this one a folder of its own "
                    "(cimian_subdirectory). Nothing was written."
                    % (relative, name, label, ",".join(sorted(holder[0].architectures)) or "all")
                )
            raise ProcessorError(
                "%s exists but is not a pkginfo of %s %s that could be read; it is never "
                "overwritten. Nothing was written." % (relative, name, label)
            )
        keep_installer = False
        if os.path.lexists(installer_target):
            try:
                same_file = os.path.isfile(installer_target) and not os.path.islink(installer_target) \
                    and sha256_of_file(installer_target) == settings["sha256"]
            except OSError as err:
                raise ProcessorError("Could not read %s: %s" % (installer_target, err))
            if not same_file:
                raise ProcessorError(
                    "%s exists with other content and is never overwritten. Nothing was written."
                    % os.path.relpath(installer_target, repo).replace(os.sep, "/")
                )
            keep_installer = True
            notes.append(
                "NOTE: the installer file was in the repository already with the same SHA-256 "
                "(an earlier run stopped before it wrote the pkginfo): it is kept."
            )

        data, build_notes = self.build_pkginfo(settings, template, facts)
        notes.extend(build_notes)
        pkginfo_text = self.render_pkginfo(yaml, loader, dumper, data)

        installer_relative = "%s/%s" % (PKGS_DIR, settings["location"])
        pkginfo_relative = os.path.relpath(pkginfo_target, repo).replace(os.sep, "/")
        catalogs = data.get("catalogs")
        catalog_text = ", ".join(str(item) for item in catalogs) if isinstance(catalogs, list) else ""
        result_data = {"name": name, "version": label, "catalogs": catalog_text}

        self.env["cimian_version_imported"] = label
        self.env["cimian_pkginfo_path"] = pkginfo_target
        self.env["cimian_installer_path"] = installer_target

        if settings["dry_run"]:
            self.env["cimian_result"] = RESULT_DRY_RUN
            self.env["cimian_repo_changed"] = False
            head = [
                "WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. "
                "Set cimian_dry_run to false in the override for a real run.",
                "Would write %s %s: %s and %s (%d bytes)%s."
                % (name, label, pkginfo_relative, installer_relative, settings["size"],
                   ", the installer is there already" if keep_installer else ""),
                ("Template: %s %s (%s)." % (name, template.version, template.relpath))
                if template is not None
                else "No template: the pkginfo is built from the inputs.",
            ]
            result_data["result"] = DRY_RUN_SUMMARY_RESULT
            summary_text = "Dry run: nothing was written to the Cimian repository (cimian_dry_run is on):"
            if not settings["verified"]:
                head.append(
                    "WARNING: the download was NOT verified: %s. A real run is refused "
                    "unless cimian_allow_unverified is true in the override." % UNVERIFIED_REASON
                )
                result_data["result"] = DRY_RUN_UNVERIFIED_SUMMARY_RESULT
        else:
            if not keep_installer:
                self.copy_installer(settings["installer"], installer_target, settings["sha256"])
            self.write_pkginfo(pkginfo_text, pkginfo_target)
            self.env["cimian_result"] = RESULT_PUBLISHED
            self.env["cimian_repo_changed"] = True
            head = ["Published %s %s (%s). Build the catalogs with makecatalogs." % (name, label, pkginfo_relative)]
            result_data["result"] = PUBLISHED_SUMMARY_RESULT
            summary_text = "The following versions were published into the Cimian repository:"
            if not settings["verified"]:
                head.append(
                    "WARNING: published WITHOUT a verified download: %s, and "
                    "cimian_allow_unverified is true." % UNVERIFIED_REASON
                )
                result_data["result"] = PUBLISHED_UNVERIFIED_SUMMARY_RESULT
        self.say(head, notes)
        # No path of the repository in the summary: reports are mailed. The paths are
        # the outputs cimian_pkginfo_path and cimian_installer_path.
        self.env["cimian_importer_summary_result"] = {
            "summary_text": summary_text,
            "report_fields": ["name", "version", "catalogs", "result"],
            "data": result_data,
        }


def check_subdirectory(value, what, allow_empty=False):
    """A folder below pkgs/ and pkgsinfo/ as written in a recipe: relative, with
    forward or back slashes, every part a plain folder name. A part that is `..`
    leaves the repository; that and an absolute path are refused."""
    text = value.strip().replace("\\", "/")
    if not text:
        if allow_empty:
            return ""
        raise ProcessorError("%s is empty." % what)
    if text.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", text):
        raise ProcessorError("%s must be a folder below pkgs/, not an absolute path: %r" % (what, text[:40]))
    parts = text.split("/")
    for part in parts:
        if part in ("", ".", ".."):
            raise ProcessorError(
                "%s must not leave the repository or hold an empty part: %r" % (what, text[:40])
            )
        if not SUBDIRECTORY_PART.fullmatch(part) or part.endswith((".", " ")):
            raise ProcessorError(
                "%s has a part that is not a plain folder name (letters, numbers, dots, "
                "underscores, hyphens, spaces): %r" % (what, part[:40])
            )
    return "/".join(parts)


def check_extra_keys(extra):
    """`pkginfo` cannot set what belongs to the file."""
    for key in FILE_KEYS:
        if key in extra:
            raise ProcessorError(
                "pkginfo cannot set %s: it belongs to the installer file and the inputs." % key
            )
    installer = extra.get("installer")
    if installer is not None and not isinstance(installer, dict):
        raise ProcessorError("pkginfo.installer must be a dictionary.")
    if isinstance(installer, dict):
        for key in FILE_INSTALLER_KEYS:
            if key in installer:
                raise ProcessorError(
                    "pkginfo cannot set installer.%s: it belongs to the installer file." % key
                )


if __name__ == "__main__":
    processor = CimianImporter()
    processor.execute_shell()
