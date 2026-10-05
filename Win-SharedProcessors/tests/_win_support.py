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
import hashlib
import importlib
import json
import os
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

import ChecksumVerifier as checksum  # noqa: E402
import CimianImporter as cimian  # noqa: E402
import GitHubAssetDigest as digest  # noqa: E402
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
