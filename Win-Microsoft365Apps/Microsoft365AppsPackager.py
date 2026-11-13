#!/usr/local/autopkg/python
"""Download the source of Microsoft 365 Apps for Windows (Office Click-to-Run)
from Microsoft's CDN and pack it, with Microsoft's setup.exe, into ONE
self-extracting EXE that installs Office from the files it carries.

Why one EXE: a Cimian item has one installer file, and the Office source is a
folder of files (one of them 2.9 GB). The PC needs nothing but this file: no
Chocolatey, no download from the internet.

What the processor does, in order:

 1. Reads the version that Microsoft offers for the channel: the file
    Office/Data/v64.cab of the channel's CDN folder holds VersionDescriptor.xml,
    whose Available element names it (I640Version). That is the file Microsoft's
    own Office Deployment Tool reads. The input office_version pins a version.
 2. Stops early when the EXE of that version, built with the same settings,
    is in the cache already (a sidecar file beside the EXE records them).
 3. Downloads the source files of that version with curl (a download that
    was cut off is resumed) and compares each file's size with the size the
    server gives. Downloads Microsoft's setup.exe (the Office Deployment Tool).
 4. Downloads the LZMA SDK (public domain) from the address in the input
    sfx_sdk_url, compares it with the SHA-256 in sfx_sdk_sha256, and takes the
    small console installer stub 7zS2con.sfx out of it.
 5. Stages the files: every file larger than PART_BYTES is cut into parts,
    because the stub unpacks one file at a time in memory. Writes
    configuration.xml and setup.bat (below).
 6. Packs the stage with 7z, stored (no compression: the files are compressed
    already), one file per block, and writes stub + archive as the EXE. Stops
    when the EXE would be 4 GiB or more: Windows does not run such a file.

On the PC the EXE unpacks into a new folder under the temp folder, runs
setup.bat with that folder as the current folder, waits, removes the folder
and ends with setup.bat's exit code. setup.bat joins the parts, checks the
sizes (join.ps1: one pass, each part appended once and deleted), writes the folder's path into configuration.xml as SourcePath and runs
`setup.exe /configure configuration.xml`; its exit code is setup.exe's. Exit
codes 30 to 39 are setup.bat's own (see SETUP_BAT_CODES).

NOT verified: Microsoft publishes no hash for these files, and no signature is
checked here. The files come from Microsoft's CDN over https, each with the
size the server announced, and nothing more is proven. On the PC, setup.exe
and the Click-to-Run client check the source files against Microsoft's
catalogs (.cat); nothing checks setup.exe itself. So this processor sets no
checksum_verified, and the importers refuse a real run until the override
allows an unverified download.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ElementTree

from autopkglib import Processor, ProcessorError

__all__ = [
    "Microsoft365AppsPackager",
    "CHANNELS",
    "LANGUAGES",
    "parse_version_descriptor",
    "source_files",
    "configuration_xml",
    "part_names",
    "setup_bat",
    "settings_digest",
]

CDN_HOST = "https://officecdn.microsoft.com"
CDN_PREFIX = CDN_HOST + "/pr/"
SETUP_URL = CDN_PREFIX + "wsus/setup.exe"
# The channel names of the Office Deployment Tool and the CDN folder of each.
# Read on 2026-11-13: each folder's v64.cab named the version that Microsoft's
# release list gave for the channel on that day.
CHANNELS = {
    "Current": "492350f6-3a01-4f97-b9c0-c7c6ddf67d60",
    "MonthlyEnterprise": "55336b82-a18d-4dd6-b5f6-9e5095c314a6",
    "SemiAnnual": "7ffbc6bf-bc32-4f92-8982-f9dd17fd3114",
}
# The culture names this processor knows, and the number Microsoft uses for
# each in the file names (the Windows language identifier, decimal).
LANGUAGES = {"en-us": 1033, "es-es": 3082, "fr-fr": 1036}
ARCHITECTURE = "x64"

VERSION_PATTERN = re.compile(r"16\.0\.[0-9]{4,6}\.[0-9]{4,6}", re.ASCII)
PRODUCT_PATTERN = re.compile(r"[A-Za-z0-9]{3,64}", re.ASCII)
APP_PATTERN = re.compile(r"[A-Za-z]{2,32}", re.ASCII)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}", re.ASCII)

FETCH_TIMEOUT_SECONDS = 120
MAX_DESCRIPTOR_CAB_BYTES = 1024 * 1024
MAX_SDK_BYTES = 16 * 1024 * 1024
# A file larger than this is cut into parts of this size. The stub (32-bit)
# holds one whole file in memory while it unpacks it.
PART_BYTES = 64 * 1024 * 1024
# Windows does not start an EXE of 4 GiB or more.
MAX_EXE_BYTES = 4 * 1024 * 1024 * 1024 - 1
STUB_MEMBER = "bin/7zS2con.sfx"
SOURCE_PLACEHOLDER = "@SOURCEPATH@"
USER_AGENT = "autopkg-Microsoft365AppsPackager"
SEVENZIP_NAMES = ("7zz", "7z", "7za")
SEVENZIP_FOLDERS = ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin")

SETUP_BAT_CODES = {
    30: "the folder of setup.bat could not be made the current folder",
    31: "a part could not be joined to its file",
    32: "a joined file does not have the size of the original",
    33: "the folder's path could not be written into configuration.xml",
}


def parse_version_descriptor(xml_text):
    """The version that the descriptor offers for 64-bit Office, or raise ValueError."""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as err:
        raise ValueError("VersionDescriptor.xml is not XML: %s" % err)
    available = root.find("Available")
    if available is None:
        raise ValueError("VersionDescriptor.xml has no Available element")
    version = available.get("I640Version", "")
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError("the Available element's I640Version is not an Office version: %r" % version[:40])
    return version


def source_files(version, language, include_arm64x=False):
    """The files of the source of one version, as paths below the channel's
    CDN folder (and below the source folder on the PC), in a fixed order.

    The list is what Microsoft's `setup.exe /download` (16.0.20430.20146)
    fetched on 2026-11-13 for O365BusinessRetail, 64-bit, en-us, with the
    version 16.0.20527.20194 named: these 14 files and no other.

    Two of them, stream.x64.x-none.arm64x.dat (489 MB) and its catalog, are
    left out unless include_arm64x is true: on the same day a 64-bit Intel
    PC installed from a source without them, with the CDN fallback off."""
    if not VERSION_PATTERN.fullmatch(str(version)):
        raise ValueError("%r is not an Office version" % str(version)[:40])
    if language not in LANGUAGES:
        raise ValueError("the language must be one of %s, not %r" % (", ".join(sorted(LANGUAGES)), str(language)[:20]))
    lcid = LANGUAGES[language]
    data = "Office/Data"
    names = [
        "a640_exp.cab", "i640.cab", "i640.cab.cat", "i64%d.cab" % lcid,
        "s640.cab", "s64%d.cab" % lcid, "sa640.cab",
        "stream.x64.%s.dat" % language, "stream.x64.%s.dat.cat" % language,
    ] + (["stream.x64.x-none.arm64x.dat", "stream.x64.x-none.arm64x.dat.cat"] if include_arm64x else []) + [
        "stream.x64.x-none.dat", "stream.x64.x-none.dat.cat",
    ]
    return ["%s/v64_%s.cab" % (data, version)] + ["%s/%s/%s" % (data, version, name) for name in names]


def as_bool(value, name):
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "yes", "1"):
        return True
    if text in ("false", "no", "0", ""):
        return False
    raise ValueError("%s must be true or false, not %r" % (name, str(value)[:20]))


def configuration_xml(version, channel, language, product_id, exclude_apps, updates_enabled,
                      migrate_architecture, remove_msi, force_app_shutdown):
    """The configuration that setup.exe gets. SourcePath is a placeholder that
    setup.bat replaces with the folder the EXE unpacked into, so that setup.exe
    takes the files from there and from nowhere else."""
    if channel not in CHANNELS:
        raise ValueError("the channel must be one of %s, not %r" % (", ".join(sorted(CHANNELS)), str(channel)[:30]))
    if not PRODUCT_PATTERN.fullmatch(str(product_id)):
        raise ValueError("the product ID %r is not letters and digits" % str(product_id)[:40])
    for app in exclude_apps:
        if not APP_PATTERN.fullmatch(str(app)):
            raise ValueError("the excluded app %r is not a name of letters" % str(app)[:40])
    source_files(version, language)  # checks the version and the language
    root = ElementTree.Element("Configuration")
    add = ElementTree.SubElement(root, "Add", {
        "OfficeClientEdition": "64",
        "Channel": channel,
        "Version": version,
        "SourcePath": SOURCE_PLACEHOLDER,
        "AllowCdnFallback": "FALSE",
        "MigrateArch": "TRUE" if migrate_architecture else "FALSE",
    })
    product = ElementTree.SubElement(add, "Product", {"ID": product_id})
    ElementTree.SubElement(product, "Language", {"ID": language})
    for app in exclude_apps:
        ElementTree.SubElement(product, "ExcludeApp", {"ID": app})
    ElementTree.SubElement(root, "Updates", {"Enabled": "TRUE" if updates_enabled else "FALSE"})
    if remove_msi:
        ElementTree.SubElement(root, "RemoveMSI")
    ElementTree.SubElement(root, "Property", {
        "Name": "FORCEAPPSHUTDOWN", "Value": "TRUE" if force_app_shutdown else "FALSE"})
    ElementTree.SubElement(root, "Display", {"Level": "None", "AcceptEULA": "TRUE"})
    ElementTree.indent(root, space="  ")
    return ElementTree.tostring(root, encoding="unicode") + "\n"


def part_names(path, size):
    """The names of the parts that a file of this size is cut into, in order;
    an empty list for a file that is not cut."""
    if size <= PART_BYTES:
        return []
    count = (size + PART_BYTES - 1) // PART_BYTES
    return ["%s.part%03d" % (path, number) for number in range(1, count + 1)]


def setup_bat(split_files):
    """The text of setup.bat (CRLF lines). `split_files` is a list of
    (path below the folder, size, [part paths]) for every file that was cut."""
    lines = [
        "@echo off",
        "setlocal",
        'cd /d "%~dp0" || exit 30',
    ]
    for path, size, _parts in split_files:
        target = path.replace("/", "\\")
        lines.append(
            'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File join.ps1 "%s" || exit 31' % target)
        lines.append('for %%%%F in ("%s") do if not "%%%%~zF"=="%d" exit 32' % (target, size))
    lines += [
        'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command '
        '"$t = [IO.File]::ReadAllText(\'configuration.xml\'); '
        "[IO.File]::WriteAllText((Join-Path (Get-Location).Path 'configuration.xml'), "
        "$t.Replace('%s', (Get-Location).Path))\" || exit 33" % SOURCE_PLACEHOLDER,
        'start "" /wait setup.exe /configure configuration.xml',
        "exit %ERRORLEVEL%",
    ]
    return "\r\n".join(lines) + "\r\n"


JOIN_PS1 = """\
# Joins <file>.part001, .part002, ... into <file>, in one pass: each part is
# appended once and deleted at once, so the folder never holds the file twice.
param([Parameter(Mandatory = $true)][string]$Target)
$ErrorActionPreference = 'Stop'
$full = Join-Path (Get-Location).Path $Target
$parts = @(Get-ChildItem -LiteralPath (Split-Path $full) -Filter ((Split-Path $full -Leaf) + '.part*') | Sort-Object Name)
if ($parts.Count -eq 0) { Write-Output "No parts of $Target"; exit 1 }
$out = [IO.File]::Open($full, [IO.FileMode]::Create)
try {
    foreach ($part in $parts) {
        $source = [IO.File]::OpenRead($part.FullName)
        try { $source.CopyTo($out, 4MB) } finally { $source.Close() }
        Remove-Item -LiteralPath $part.FullName
    }
} finally { $out.Close() }
exit 0
"""


def settings_digest(settings):
    """A short name for a set of settings: the EXE in the cache is reused only
    when it was built with the same ones."""
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode("utf-8")).hexdigest()


def is_windows_program(path):
    """Whether the file begins like a Windows program (the letters MZ)."""
    with open(path, "rb") as handle:
        return handle.read(2) == b"MZ"


def sha256_of_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_bytes(url, max_bytes, what, follow_redirects=False):
    """GET a small file. The descriptor comes from Microsoft's CDN without a
    redirect; the SDK comes from a release address that redirects, and is
    checked against a SHA-256 afterwards."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener() if follow_redirects else urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            body = response.read(max_bytes + 1)
    except urllib.error.HTTPError as err:
        message = "The server answered %s %s for %s." % (err.code, err.reason, what)
        err.close()
        raise ProcessorError(message)
    except (urllib.error.URLError, OSError, ValueError) as err:
        raise ProcessorError("%s could not be fetched: %s" % (what, err))
    if len(body) > max_bytes:
        raise ProcessorError("%s is larger than %d bytes." % (what, max_bytes))
    return body


def remote_size(url, what, curl="/usr/bin/curl"):
    """The size the server announces for a file (a HEAD request)."""
    result = subprocess.run(
        [curl, "--silent", "--show-error", "--fail", "--head", "--max-time", str(FETCH_TIMEOUT_SECONDS),
         "--user-agent", USER_AGENT, url],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise ProcessorError("The server did not answer for %s: %s" % (what, result.stderr.strip()[:200]))
    sizes = re.findall(r"(?im)^content-length:\s*([0-9]+)\s*$", result.stdout)
    if not sizes:
        raise ProcessorError("The server gave no size for %s." % what)
    return int(sizes[-1])


def download_file(url, path, what, curl="/usr/bin/curl"):
    """Download with curl; a file that was cut off is resumed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    result = subprocess.run(
        [curl, "--silent", "--show-error", "--fail", "--continue-at", "-", "--retry", "3",
         "--user-agent", USER_AGENT, "--output", path, url],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise ProcessorError("%s could not be downloaded: %s" % (what, result.stderr.strip()[:200]))


def split_file(source, stage_root, relative, size):
    """Write the parts of one file into the stage. Returns the part paths."""
    parts = part_names(relative, size)
    with open(source, "rb") as handle:
        for part in parts:
            with open(os.path.join(stage_root, part), "wb") as out:
                remaining = PART_BYTES
                while remaining:
                    block = handle.read(min(1024 * 1024, remaining))
                    if not block:
                        break
                    out.write(block)
                    remaining -= len(block)
    return parts


class Microsoft365AppsPackager(Processor):
    description = __doc__
    input_variables = {
        "office_channel": {
            "required": False,
            "default": "MonthlyEnterprise",
            "description": "The update channel whose newest version is packed: %s." % ", ".join(sorted(CHANNELS)),
        },
        "office_version": {
            "required": False,
            "default": "",
            "description": "A version to pack instead of the channel's newest (16.0.x.y). Empty: the newest.",
        },
        "office_language": {
            "required": False,
            "default": "en-us",
            "description": "The language: %s." % ", ".join(sorted(LANGUAGES)),
        },
        "office_product_id": {
            "required": False,
            "default": "O365BusinessRetail",
            "description": "The product ID of the Office Deployment Tool (O365BusinessRetail, O365ProPlusRetail, ...).",
        },
        "office_exclude_apps": {
            "required": False,
            "default": "",
            "description": "The apps that are not installed: ExcludeApp IDs separated by spaces or commas.",
        },
        "office_updates_enabled": {
            "required": False,
            "default": False,
            "description": "Whether Office updates itself from Microsoft. False: the version on a PC is the item's.",
        },
        "office_migrate_architecture": {
            "required": False,
            "default": True,
            "description": "Whether a 32-bit Click-to-Run Office is changed to 64-bit (MigrateArch).",
        },
        "office_remove_msi": {
            "required": False,
            "default": True,
            "description": "Whether an Office installed by Windows Installer (MSI) is removed first (RemoveMSI).",
        },
        "office_force_app_shutdown": {
            "required": False,
            "default": False,
            "description": "Whether open Office programs are closed for the install (unsaved work is lost). "
                           "False: the install fails while one is open, and the next run tries again.",
        },
        "sfx_sdk_url": {
            "required": True,
            "description": "The address of the LZMA SDK archive (.7z) that holds %s." % STUB_MEMBER,
        },
        "sfx_sdk_sha256": {
            "required": True,
            "description": "The SHA-256 of that archive (64 hex digits). A different file stops the run.",
        },
        "office_include_arm64x": {
            "required": False,
            "default": False,
            "description": "Whether the stream for ARM PCs (489 MB) is packed too. A 64-bit Intel or AMD PC "
                           "installs without it.",
        },
        "sevenzip_path": {
            "required": False,
            "default": "",
            "description": "The 7z program. Empty: 7zz, 7z or 7za in /opt/homebrew/bin, /usr/local/bin or /usr/bin.",
        },
    }
    output_variables = {
        "pathname": {"description": "The self-extracting EXE."},
        "version": {"description": "The Office version it installs (16.0.x.y)."},
        "office_setup_sha256": {"description": "The SHA-256 of Microsoft's setup.exe inside the EXE."},
        "microsoft365apps_packager_summary_result": {"description": "What was built."},
    }

    # -- helpers ---------------------------------------------------------
    def sevenzip(self):
        given = str(self.env.get("sevenzip_path") or "").strip()
        candidates = [given] if given else [os.path.join(folder, name) for folder in SEVENZIP_FOLDERS for name in SEVENZIP_NAMES]
        for candidate in candidates:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        raise ProcessorError(
            "No 7z program was found (%s). Install one (brew install sevenzip) or set sevenzip_path."
            % ", ".join(candidates))

    def run_sevenzip(self, arguments, what):
        result = subprocess.run([self.sevenzip()] + arguments, capture_output=True, text=True)
        if result.returncode != 0:
            raise ProcessorError("7z failed (%s): %s" % (what, (result.stderr or result.stdout).strip()[-400:]))

    def offered_version(self, base):
        cab = fetch_bytes(base + "/Office/Data/v64.cab", MAX_DESCRIPTOR_CAB_BYTES, "the version descriptor (v64.cab)")
        with tempfile.TemporaryDirectory() as folder:
            cab_path = os.path.join(folder, "v64.cab")
            with open(cab_path, "wb") as handle:
                handle.write(cab)
            self.run_sevenzip(["e", "-y", "-o" + folder, cab_path, "VersionDescriptor.xml"], "unpacking v64.cab")
            try:
                with open(os.path.join(folder, "VersionDescriptor.xml"), "r", encoding="utf-8-sig") as handle:
                    return parse_version_descriptor(handle.read())
            except (OSError, UnicodeDecodeError, ValueError) as err:
                raise ProcessorError("The version descriptor could not be read: %s" % err)

    def stub(self, work):
        sha256 = str(self.env["sfx_sdk_sha256"]).strip().lower()
        if not SHA256_PATTERN.fullmatch(sha256):
            raise ProcessorError("sfx_sdk_sha256 is not 64 hex digits.")
        body = fetch_bytes(str(self.env["sfx_sdk_url"]), MAX_SDK_BYTES, "the LZMA SDK", follow_redirects=True)
        actual = hashlib.sha256(body).hexdigest()
        if actual != sha256:
            raise ProcessorError(
                "The LZMA SDK does not have the SHA-256 of sfx_sdk_sha256 (got %s...). Nothing was built." % actual[:12])
        archive = os.path.join(work, "lzma-sdk.7z")
        with open(archive, "wb") as handle:
            handle.write(body)
        self.run_sevenzip(["e", "-y", "-o" + work, archive, STUB_MEMBER], "unpacking the stub")
        path = os.path.join(work, os.path.basename(STUB_MEMBER))
        if not os.path.isfile(path) or not is_windows_program(path):
            raise ProcessorError("The LZMA SDK holds no %s that is a Windows program." % STUB_MEMBER)
        return path

    # -- main ------------------------------------------------------------
    def main(self):
        env = self.env
        channel = str(env.get("office_channel") or "MonthlyEnterprise")
        language = str(env.get("office_language") or "en-us").lower()
        if channel not in CHANNELS:
            raise ProcessorError("office_channel must be one of %s." % ", ".join(sorted(CHANNELS)))
        base = CDN_PREFIX + CHANNELS[channel]
        exclude = [app for app in re.split(r"[\s,]+", str(env.get("office_exclude_apps") or "")) if app]
        try:
            flags = {name: as_bool(env.get(name, self.input_variables[name]["default"]), name) for name in (
                "office_updates_enabled", "office_migrate_architecture", "office_remove_msi", "office_force_app_shutdown",
                "office_include_arm64x")}
            version = str(env.get("office_version") or "").strip() or self.offered_version(base)
            files = source_files(version, language, flags["office_include_arm64x"])
            configuration = configuration_xml(
                version, channel, language, str(env.get("office_product_id") or "O365BusinessRetail"), exclude,
                flags["office_updates_enabled"], flags["office_migrate_architecture"], flags["office_remove_msi"],
                flags["office_force_app_shutdown"])
        except ValueError as err:
            raise ProcessorError(str(err))

        cache = env.get("RECIPE_CACHE_DIR")
        if not cache:
            raise ProcessorError("RECIPE_CACHE_DIR is not set.")
        os.makedirs(cache, exist_ok=True)
        exe_path = os.path.join(cache, "Microsoft365Apps-%s-%s.exe" % (version, ARCHITECTURE))
        record_path = exe_path + ".json"
        settings = settings_digest({"configuration": configuration, "sdk": str(env["sfx_sdk_sha256"]).lower(),
                                    "part_bytes": PART_BYTES, "files": files,
                                    "join": JOIN_PS1})
        env["version"] = version
        try:
            with open(record_path, "r", encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, ValueError):
            record = {}
        if (os.path.isfile(exe_path) and record.get("settings") == settings
                and record.get("size") == os.path.getsize(exe_path)):
            env["pathname"] = exe_path
            env["office_setup_sha256"] = record.get("setup_sha256", "")
            self.output("Nothing to build: %s is in the cache with the same settings." % os.path.basename(exe_path))
            return

        # 3. the source
        downloads = os.path.join(cache, "downloads", channel)
        source = os.path.join(downloads, version)
        if os.path.isdir(downloads):
            for other in os.listdir(downloads):  # the source of another version is 3 GB of no use
                if other != version:
                    shutil.rmtree(os.path.join(downloads, other), ignore_errors=True)
        sizes = {}
        for relative in files:
            url = "%s/%s" % (base, relative)
            target = os.path.join(source, relative)
            expected = remote_size(url, relative)
            if not (os.path.isfile(target) and os.path.getsize(target) == expected):
                if os.path.isfile(target) and os.path.getsize(target) > expected:
                    os.remove(target)
                self.output("Downloading %s (%d bytes)" % (relative, expected))
                download_file(url, target, relative)
            if os.path.getsize(target) != expected:
                raise ProcessorError("%s has %d bytes, and the server announced %d." % (
                    relative, os.path.getsize(target), expected))
            sizes[relative] = expected
        setup_path = os.path.join(source, "setup.exe")
        if os.path.exists(setup_path):
            os.remove(setup_path)  # the address has no version in it: always the current one
        download_file(SETUP_URL, setup_path, "setup.exe")
        if not is_windows_program(setup_path):
            raise ProcessorError("What the server gave for setup.exe is not a Windows program.")
        setup_sha256 = sha256_of_file(setup_path)

        # 4. to 6. stub, stage, pack
        work = tempfile.mkdtemp(prefix="m365-build-", dir=cache)
        try:
            stub_path = self.stub(work)
            stage = os.path.join(work, "stage")
            split = []
            for relative in files:
                os.makedirs(os.path.dirname(os.path.join(stage, relative)), exist_ok=True)
                parts = split_file(os.path.join(source, relative), stage, relative, sizes[relative]) \
                    if sizes[relative] > PART_BYTES else []
                if parts:
                    split.append((relative, sizes[relative], parts))
                else:
                    shutil.copyfile(os.path.join(source, relative), os.path.join(stage, relative))
            shutil.copyfile(setup_path, os.path.join(stage, "setup.exe"))
            with open(os.path.join(stage, "configuration.xml"), "w", encoding="utf-8", newline="\r\n") as handle:
                handle.write(configuration)
            with open(os.path.join(stage, "setup.bat"), "w", encoding="ascii", newline="") as handle:
                handle.write(setup_bat(split))
            with open(os.path.join(stage, "join.ps1"), "w", encoding="ascii", newline="\r\n") as handle:
                handle.write(JOIN_PS1)
            archive = os.path.join(work, "source.7z")
            # stored, one file per block: the stub unpacks a block in memory
            result = subprocess.run(
                [self.sevenzip(), "a", "-t7z", "-mx=0", "-ms=off", "-bd", "-y", archive, "."],
                cwd=stage, capture_output=True, text=True)
            if result.returncode != 0:
                raise ProcessorError("7z failed (packing): %s" % (result.stderr or result.stdout).strip()[-400:])
            shutil.rmtree(stage)
            total = os.path.getsize(stub_path) + os.path.getsize(archive)
            if total > MAX_EXE_BYTES:
                raise ProcessorError(
                    "The EXE would have %d bytes, and Windows does not run an EXE of 4 GiB or more. "
                    "Nothing was built: the source has outgrown this way of packing it." % total)
            partial = exe_path + ".partial"
            with open(partial, "wb") as out:
                for piece in (stub_path, archive):
                    with open(piece, "rb") as handle:
                        shutil.copyfileobj(handle, out, 4 * 1024 * 1024)
            os.replace(partial, exe_path)
        finally:
            shutil.rmtree(work, ignore_errors=True)

        with open(record_path, "w", encoding="utf-8") as handle:
            json.dump({"settings": settings, "size": os.path.getsize(exe_path), "version": version,
                       "channel": channel, "setup_sha256": setup_sha256}, handle, indent=2)
        for name in os.listdir(cache):  # an EXE of another version is 3 GB of no use
            if re.fullmatch(r"Microsoft365Apps-.*\.exe(\.json)?", name) and not name.startswith(os.path.basename(exe_path)):
                os.remove(os.path.join(cache, name))
        env["pathname"] = exe_path
        env["office_setup_sha256"] = setup_sha256
        env["microsoft365apps_packager_summary_result"] = {
            "summary_text": "The following Microsoft 365 Apps installer was built (NOT verified: see the processor):",
            "report_fields": ["version", "channel", "size", "path"],
            "data": {"version": version, "channel": channel, "size": str(os.path.getsize(exe_path)), "path": exe_path},
        }
        self.output("Built %s (%d bytes), Office %s, channel %s" % (
            os.path.basename(exe_path), os.path.getsize(exe_path), version, channel))


if __name__ == "__main__":
    PROCESSOR = Microsoft365AppsPackager()
    PROCESSOR.execute_shell()
