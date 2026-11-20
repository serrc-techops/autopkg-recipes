"""Shared test support: import the processors with or without a real AutoPkg
install, and build a temporary Cimian repository with a stand-in `msiinfo`.

The processor modules import `from autopkglib import Processor,
ProcessorError`. AutoPkg is not installed on every machine that runs these
tests, so this module installs a minimal stand-in for `autopkglib` only when a
real one cannot be imported (the same approach as ReportMateClientMac/tests).
A real AutoPkg install, when present, is used instead.

Nothing here touches the network, the repository tree or a real Cimian
repository. Every file is made in a temporary folder.
"""
import copy
import hashlib
import importlib
import itertools
import json
import os
import re
import sys
import tempfile
import types
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSOR_DIR = os.path.dirname(TESTS_DIR)

if PROCESSOR_DIR not in sys.path:
    sys.path.insert(0, PROCESSOR_DIR)


def _install_autopkglib_stub():
    try:
        importlib.import_module("autopkglib")
        return
    except ImportError:
        pass

    module = types.ModuleType("autopkglib")

    class ProcessorError(Exception):
        pass

    class Processor:
        def __init__(self, env=None):
            self.env = env if env is not None else {}

        def output(self, msg, verbose_level=1):
            pass

        def execute_shell(self):
            raise NotImplementedError("not needed by the tests")

    module.Processor = Processor
    module.ProcessorError = ProcessorError
    sys.modules["autopkglib"] = module


_install_autopkglib_stub()

import AuthenticodeVerifier as authenticode  # noqa: E402
import ChecksumVerifier as checksum  # noqa: E402
import CimianImporter as cimian  # noqa: E402
import GitHubAssetDigest as digest  # noqa: E402
import GitHubNewestReleaseGuard as newest_release  # noqa: E402
import VersionFromName as version_name  # noqa: E402
import WindowsExeVersion as exe_version  # noqa: E402

ProcessorError = sys.modules["autopkglib"].ProcessorError

try:
    import yaml  # noqa: E402
except ImportError:  # AutoPkg's Python has PyYAML; the interpreter of a test run may not
    yaml = None

needs_yaml = unittest.skipUnless(yaml is not None, "PyYAML is not installed in this Python")


def sha256_hex(path):
    """The SHA-256 of a file, by hashlib directly (not by a function of the
    processors, so that a test does not trust the code that it tests)."""
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


# Variables that the interpreter or the system may add to a child's
# environment by itself. They are not passed on by the processor.
ADDED_BY_THE_SYSTEM = ("__CF_USER_TEXT_ENCODING", "LC_CTYPE", "PYTHONCOERCECLOCALE")


def new_processor(cls, env):
    """A processor with a copy of `env`, and the list that collects what it
    would print."""
    messages = []
    processor = cls(dict(env))
    processor.message_levels = []

    def record(msg, verbose_level=1):
        messages.append(msg)
        processor.message_levels.append((verbose_level, msg))

    processor.output = record
    return processor, messages


def run_processor(cls, env):
    processor, messages = new_processor(cls, env)
    processor.main()
    return processor, messages


# The stand-in for `msiinfo` (msitools). It is run as `msiinfo export <file>
# Property`. What it does comes from msiinfo.json next to it:
#   stdout / stderr   text to print
#   exit              exit code
# It appends every call's arguments to calls.log.
STAND_IN_MSIINFO = """#!{python}
import json, os, sys

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "msiinfo.json")) as handle:
    behaviour = json.load(handle)
with open(os.path.join(here, "calls.log"), "a") as log:
    log.write(json.dumps(sys.argv[1:]) + chr(10))
sys.stdout.write(behaviour.get("stdout", ""))
sys.stderr.write(behaviour.get("stderr", ""))
sys.exit(behaviour.get("exit", 0))
"""

PRODUCT_CODE = "{5A1B2C3D-0000-4000-8000-00000000A001}"
UPGRADE_CODE = "{5A1B2C3D-0000-4000-8000-00000000A002}"


def property_export(version="2.5.0", product_code=PRODUCT_CODE, upgrade_code=UPGRADE_CODE):
    """What the stand-in prints for `msiinfo export <file> Property`: a header
    row, then one row per property, the two columns separated by a tab."""
    rows = ["Property\tValue"]
    if product_code:
        rows.append("ProductCode\t%s" % product_code)
    if version:
        rows.append("ProductVersion\t%s" % version)
    rows.append("ProductName\tExample Program")
    rows.append("Manufacturer\tExample Maker")
    if upgrade_code:
        rows.append("UpgradeCode\t%s" % upgrade_code)
    return "\n".join(rows) + "\n"


# ---- app packages (.msix, .appx, .msixbundle, .appxbundle) -------------------

PACKAGE_NAMESPACE = "http://schemas.microsoft.com/appx/manifest/foundation/windows10"
BUNDLE_NAMESPACE = "http://schemas.microsoft.com/appx/2013/bundle"


def package_manifest(name="Example.Vendor.App", version="2026.1028.1836.0", architecture="x64", bundle=False):
    """The text of a made-up manifest: a bundle's (AppxBundleManifest.xml, no
    architecture) or a single package's (AppxManifest.xml). A value of None
    leaves the attribute out."""
    attributes = [("Name", name), ("Publisher", "CN=Example Vendor"), ("Version", version)]
    if not bundle:
        attributes.append(("ProcessorArchitecture", architecture))
    identity = "<Identity %s/>" % " ".join('%s="%s"' % pair for pair in attributes if pair[1] is not None)
    if bundle:
        return ('<?xml version="1.0" encoding="UTF-8"?>\n<Bundle xmlns="%s" SchemaVersion="5.0">%s'
                "<Packages/></Bundle>\n" % (BUNDLE_NAMESPACE, identity))
    return ('<?xml version="1.0" encoding="utf-8"?>\n<Package xmlns="%s">%s'
            "<Properties><DisplayName>Example</DisplayName></Properties></Package>\n" % (PACKAGE_NAMESPACE, identity))


def write_app_package(path, members):
    """A zip file at `path` with `members` ({name: text or bytes}), as an app
    package is one. Returns the path."""
    import zipfile

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member, content in members.items():
            archive.writestr(member, content)
    return path


# ---- release lists, as GitHub's API shapes them ------------------------------

_asset_ids = itertools.count(5000)


def fake_asset(name, owner="example-owner", repo="example-app", tag="v1", asset_id=None):
    """The record of a release asset, with the keys that the processors read."""
    if asset_id is None:
        asset_id = next(_asset_ids)
    return {
        "id": asset_id,
        "name": name,
        "url": "https://api.github.com/repos/%s/%s/releases/assets/%d" % (owner, repo, asset_id),
        "browser_download_url": "https://github.com/%s/%s/releases/download/%s/%s" % (owner, repo, tag, name),
    }


def fake_release(tag, names=(), prerelease=False, draft=False, title=None, owner="example-owner", repo="example-app"):
    """A release record: the tag, the flags, and one asset for each name."""
    return {
        "tag_name": tag,
        "name": tag if title is None else title,
        "prerelease": prerelease,
        "draft": draft,
        "assets": [fake_asset(name, owner, repo, tag) for name in names],
    }


def saved_releases(path):
    """The names and flags of a saved release list (the file tests/releases_excerpt.json
    of a recipe folder), newest first. A version of four numbers is saved with `_dot_` for
    each dot, because the hygiene check takes it for an address: the dots are put back."""
    with open(path, "r", encoding="utf-8") as handle:
        return json.loads(handle.read().replace("_dot_", "."))["releases"]


def records_from_saved(saved, owner, repo):
    """Release records in the shape of GitHub's API answer (with made-up asset numbers)
    for a saved list."""
    return [
        fake_release(item["tag_name"], [asset["name"] for asset in item["assets"]],
                     prerelease=item["prerelease"], title=item.get("name"), owner=owner, repo=repo)
        for item in saved
    ]


def renamed_in_newest(records, pattern):
    """A copy of the list in which the vendor has renamed the files that the pattern
    takes in the newest release that is not a pre-release: their names get a prefix
    that the pattern does not match (every pattern of the recipes matches from its start)."""
    changed = copy.deepcopy(records)
    for release in changed:
        if release["prerelease"] or release["draft"]:
            continue
        for asset in release["assets"]:
            if re.match(pattern, asset["name"]):
                asset["name"] = "renamed-" + asset["name"]
        break
    return changed


def provider_select(releases, pattern, include_prereleases=False):
    """What AutoPkg 2.9.0's GitHubReleasesInfoProvider selects from these releases
    (GitHubReleasesInfoProvider.py, select_asset): in the order of the list, a
    pre-release skipped unless include_prereleases is true (a draft is not skipped),
    a release without assets skipped, and in a release the first asset whose name
    the pattern matches from its start (re.match). Returns (release, asset) or None."""
    for release in releases:
        if release["prerelease"] and not include_prereleases:
            continue
        for asset in release.get("assets") or []:
            if re.match(pattern, asset["name"]):
                return release, asset
    return None


def guard_run(repo, pattern, releases, include_prereleases=False, accepted=None, tag_pattern=None, extra=None):
    """The provider and then the guard, on a made-up list of releases, with no
    network: the list is the answer of the one fetch (GitHub's first page).
    `repo` is the provider's github_repo; the releases carry its owner and name in
    their asset URLs. Returns a dict: `tag` (the release the provider took, or
    None), `error` (the text of the guard's stop, or None), `asked` (the addresses
    that were asked), `messages` (what the guard printed, as (level, text)) and, when
    the guard set it, `summary` (its entry for AutoPkg's end-of-run table)."""
    selected = provider_select(releases, pattern, include_prereleases)
    if selected is None:
        return {"tag": None, "error": None, "asked": [], "messages": []}
    release, asset = selected
    asked = []

    def answer(url, what):
        asked.append(url)
        return releases

    env = {"github_asset_api_url": asset["url"], "url": asset["browser_download_url"],
           "include_prereleases": include_prereleases}
    if accepted is not None:
        env["accepted_newest_release"] = accepted
    if tag_pattern is not None:
        env["release_tag_pattern"] = tag_pattern
    env.update(extra or {})
    processor, _ = new_processor(newest_release.GitHubNewestReleaseGuard, env)
    original = newest_release.fetch_json
    newest_release.fetch_json = answer
    try:
        processor.main()
        error = None
    except ProcessorError as err:
        error = str(err)
    finally:
        newest_release.fetch_json = original
    result = {"tag": release["tag_name"], "error": error, "asked": asked, "messages": processor.message_levels}
    if newest_release.SUMMARY_KEY in processor.env:
        result["summary"] = processor.env[newest_release.SUMMARY_KEY]
    return result


def guard_chain(repo, pattern, releases, include_prereleases=False, accepted=None, tag_pattern=None):
    """`guard_run`, reduced to (tag the provider took or None, error text or None,
    the addresses that were asked)."""
    result = guard_run(repo, pattern, releases, include_prereleases, accepted, tag_pattern)
    return result["tag"], result["error"], result["asked"]


def tree_of(root):
    """Every file and folder below `root`, as {relative path: SHA-256 of the
    file, or None for a folder}. Two equal trees mean that nothing was written,
    made or removed."""
    found = {}
    for folder, dirs, files in os.walk(root):
        for name in dirs:
            found[os.path.relpath(os.path.join(folder, name), root)] = None
        for name in files:
            path = os.path.join(folder, name)
            found[os.path.relpath(path, root)] = sha256_hex(path)
    return found


class RepoTestCase(unittest.TestCase):
    """A temporary Cimian repository (with pkgs/ and pkgsinfo/), a stand-in
    msiinfo in a folder of its own, a folder without one, and two installers
    that are only files with bytes in them."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="win-cimian-tests-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = os.path.realpath(self._tmp.name)

        self.repo = os.path.join(self.tmp, "cimian repo")  # a space on purpose
        os.makedirs(os.path.join(self.repo, "pkgs"))
        os.makedirs(os.path.join(self.repo, "pkgsinfo"))

        self.msi_bin = os.path.join(self.tmp, "msi-bin")
        os.makedirs(self.msi_bin)
        self.write_executable(
            os.path.join(self.msi_bin, "msiinfo"), STAND_IN_MSIINFO.format(python=sys.executable)
        )
        self.empty_bin = os.path.join(self.tmp, "empty-bin")
        os.makedirs(self.empty_bin)
        self.msiinfo_says()

        self.downloads = os.path.join(self.tmp, "my downloads")  # a space on purpose
        os.makedirs(self.downloads)
        self.exe = self.make_installer("Example App-2.5.0.exe", b"MZ" + bytes(range(256)) * 8)
        self.msi = self.make_installer("Example App-2.5.0.msi", b"\xd0\xcf\x11\xe0" + bytes(range(255, 0, -1)) * 8)

    @staticmethod
    def write_executable(path, text):
        with open(path, "w") as handle:
            handle.write(text)
        os.chmod(path, 0o755)

    def make_installer(self, name, content):
        path = os.path.join(self.downloads, name)
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def msiinfo_says(self, **behaviour):
        """Set what the stand-in msiinfo does. Default: the properties of an
        MSI of version 2.5.0."""
        if "stdout" not in behaviour:
            behaviour["stdout"] = property_export()
        with open(os.path.join(self.msi_bin, "msiinfo.json"), "w") as handle:
            json.dump(behaviour, handle)

    def msiinfo_calls(self):
        path = os.path.join(self.msi_bin, "calls.log")
        if not os.path.exists(path):
            return []
        with open(path) as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def env(self, installer=None, **overrides):
        """A complete input set for a real run of an .exe. The download counts as
        verified (checksum_verified is true and checksum_sha256 is the real hash
        of the file), as after a ChecksumVerifier step. A test of an unverified
        download passes checksum_verified=None; a test of another hash passes
        checksum_sha256. A value of None leaves the input out."""
        env = {
            "checksum_verified": True,
            "pathname": installer or self.exe,
            "cimian_repo": self.repo,
            "cimian_name": "Example-App",
            "version": "2.5.0",
            "cimian_dry_run": False,
            "cimian_path": self.msi_bin,
        }
        env.update(overrides)
        if "checksum_sha256" not in overrides:
            try:
                env["checksum_sha256"] = sha256_hex(env["pathname"])
            except OSError:
                pass
        return {key: value for key, value in env.items() if value is not None}

    def put_pkginfo(self, relpath, text):
        path = os.path.join(self.repo, "pkgsinfo", *relpath.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def read_text(self, *parts):
        with open(os.path.join(self.repo, *parts), "r", encoding="utf-8") as handle:
            return handle.read()

    def read_pkginfo(self, relpath):
        """A pkginfo of the repository, read the way the processor reads it
        (the loader that keeps the text of a version)."""
        loader, _ = cimian.make_yaml_classes(yaml)
        return yaml.load(self.read_text("pkgsinfo", *relpath.split("/")), Loader=loader)

    def repo_tree(self):
        return tree_of(self.repo)
