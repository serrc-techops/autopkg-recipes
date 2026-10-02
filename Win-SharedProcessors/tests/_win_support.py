"""Shared test support: import the three processors with or without a real
AutoPkg install, and build stand-ins for the package tool.

The processor modules import `from autopkglib import Processor,
ProcessorError`. AutoPkg is not installed on every machine that runs these
tests, so this module installs a minimal stand-in for `autopkglib` only when a
real one cannot be imported (the same approach as ReportMateClientMac/tests).
A real AutoPkg install, when present, is used instead.

Nothing here touches the network, the repository tree or a real package
repository. Every file is made in a temporary folder.
"""
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
import GitHubAssetDigest as digest  # noqa: E402
import PcmanImporter as importer  # noqa: E402

ProcessorError = sys.modules["autopkglib"].ProcessorError

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


# The stand-in for `pcman`. It is run by `<python> <root>/bin/pcman ...`.
# Its behaviour comes from behaviour.json next to the `bin` folder:
#   exit      exit code
#   result    the content of the result file (dict), or null for no file
#   raw_result  text to write instead of JSON (for a broken file)
#   stdout / stderr   text to print
#   sleep     seconds to wait before it ends
#   grandchild  true: start a child that sleeps 30 seconds, quiet
# It writes record.json: argv, the whole environment, what standard input
# looked like, the working folder and its process ids.
STAND_IN_PCMAN = """#!{python}
import json, os, select, subprocess, sys, time

here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(here, "behaviour.json")) as handle:
    behaviour = json.load(handle)

try:
    ready, _, _ = select.select([0], [], [], 0.5)
    if ready:
        stdin_state = "eof" if os.read(0, 1) == b"" else "data"
    else:
        stdin_state = "open"
except OSError:
    stdin_state = "closed"

record = {{
    "argv": sys.argv[1:],
    "env": dict(os.environ),
    "stdin": stdin_state,
    "cwd": os.getcwd(),
    "pid": os.getpid(),
    "grandchild_pid": None,
}}
if behaviour.get("grandchild"):
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    record["grandchild_pid"] = child.pid
with open(os.path.join(here, "record.json"), "w") as handle:
    json.dump(record, handle)

if behaviour.get("sleep"):
    time.sleep(behaviour["sleep"])

args = sys.argv[1:]
if "--result-file" in args:
    path = args[args.index("--result-file") + 1]
    if behaviour.get("raw_result") is not None:
        with open(path, "w") as handle:
            handle.write(behaviour["raw_result"])
    elif behaviour.get("result") is not None:
        with open(path, "w") as handle:
            json.dump(behaviour["result"], handle)

sys.stdout.buffer.write(behaviour.get("stdout", "").encode("utf-8"))
sys.stdout.buffer.write(bytes.fromhex(behaviour.get("stdout_hex", "")))
sys.stderr.buffer.write(behaviour.get("stderr", "").encode("utf-8"))
sys.stderr.buffer.write(bytes.fromhex(behaviour.get("stderr_hex", "")))
sys.stdout.flush()
sys.stderr.flush()
sys.exit(behaviour.get("exit", 0))
"""

STAND_IN_MSIINFO = """#!{python}
import sys
sys.exit(0)
"""


def result_file_content(result="published", name="Example App", version="2.5.0",
                        catalogs=("Production",), **extra):
    """What the tool's result file holds (the keys of its README)."""
    content = {
        "result": result,
        "name": name,
        "version": version,
        "item_path": "/example/items/Example.yaml",
        "installer_path": "/example/pkgs/apps/Example-%s.exe" % version,
        "pkginfo_path": "/example/pkgsinfo/apps/Example-%s.yaml" % version,
        "catalogs": list(catalogs),
        "unreadable_pkginfo": 0,
        "message": "Published %s %s." % (name, version),
    }
    content.update(extra)
    return content


class ToolTestCase(unittest.TestCase):
    """A temporary folder with a stand-in tool, a stand-in msiinfo in its own
    folder, and an installer."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="win-shared-tests-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = os.path.realpath(self._tmp.name)

        self.root = os.path.join(self.tmp, "tool root")  # a space on purpose
        os.makedirs(os.path.join(self.root, "bin"))
        self.script = os.path.join(self.root, "bin", "pcman")
        self.write_executable(self.script, STAND_IN_PCMAN.format(python=sys.executable))
        venv_bin = os.path.join(self.root, ".venv", "bin")
        os.makedirs(venv_bin)
        self.python = os.path.join(venv_bin, "python3")
        os.symlink(sys.executable, self.python)

        self.msi_bin = os.path.join(self.tmp, "msi-bin")
        os.makedirs(self.msi_bin)
        self.write_executable(
            os.path.join(self.msi_bin, "msiinfo"), STAND_IN_MSIINFO.format(python=sys.executable)
        )
        self.empty_bin = os.path.join(self.tmp, "empty-bin")
        os.makedirs(self.empty_bin)

        self.downloads = os.path.join(self.tmp, "my downloads")  # a space on purpose
        os.makedirs(self.downloads)
        self.exe = self.make_installer("Example App-2.5.0.exe")
        self.msi = self.make_installer("Example App-2.5.0.msi")

        self.behave()

    @staticmethod
    def write_executable(path, text):
        with open(path, "w") as handle:
            handle.write(text)
        os.chmod(path, 0o755)

    def make_installer(self, name):
        path = os.path.join(self.downloads, name)
        with open(path, "wb") as handle:
            handle.write(b"not a real installer")
        return path

    def behave(self, **behaviour):
        """Set what the stand-in does. Default: exit 0 with a `published` result."""
        if "result" not in behaviour and "raw_result" not in behaviour:
            behaviour["result"] = result_file_content()
        behaviour.setdefault("exit", 0)
        with open(os.path.join(self.root, "behaviour.json"), "w") as handle:
            json.dump(behaviour, handle)

    def record(self):
        with open(os.path.join(self.root, "record.json")) as handle:
            return json.load(handle)

    def was_run(self):
        return os.path.exists(os.path.join(self.root, "record.json"))

    def env(self, installer=None, **overrides):
        """A complete input set for a real run of an .exe."""
        env = {
            "pathname": installer or self.exe,
            "pcman_template": "Example-App",
            "pcman_version": "2.5.0",
            "pcman_root": self.root,
            "pcman_dry_run": False,
            "pcman_path": self.msi_bin,
        }
        env.update(overrides)
        return {key: value for key, value in env.items() if value is not None}
