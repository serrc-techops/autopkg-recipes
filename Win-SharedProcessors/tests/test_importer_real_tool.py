"""Tests of PcmanImporter against the REAL package tool.

These tests are skipped unless two environment variables are set:

  PCMAN_TOOL_SOURCE  the folder of a checkout of the package tool
  PCMAN_TOOL_PYTHON  a Python that has the tool's requirements (PyYAML)

The test copies only the tool's code (`pcman/` and `bin/`) into a temporary
folder, so it never reads the checkout's own settings, items or state. The
repository, the state folder and the installers are made in a temporary folder
too. For an MSI, a stand-in `msiinfo` is used (the real one is not needed to
test the processor).

Run by hand:

  PCMAN_TOOL_SOURCE=<tool folder> PCMAN_TOOL_PYTHON=<python> \\
      python3 -m unittest discover -s tests -t tests -p 'test_importer_real_tool.py'
"""
import os
import shutil
import subprocess
import tempfile
import unittest

from _win_support import ProcessorError, importer, run_processor, sha256_hex

TOOL_SOURCE = os.environ.get("PCMAN_TOOL_SOURCE", "")
TOOL_PYTHON = os.environ.get("PCMAN_TOOL_PYTHON", "")
COPIED_FOLDERS = ("pcman", "bin")
SETUP_TIMEOUT_SECONDS = 120

MSIINFO_TABLE = (
    "Property\tValue\n"
    "ProductCode\t{12345678-1234-1234-1234-1234567890AB}\n"
    "ProductVersion\t%s\n"
    "ProductName\tExample Application\n"
    "Manufacturer\tExample Vendor Inc.\n"
    "UpgradeCode\t{ABCDEF12-3456-7890-ABCD-EF1234567890}\n"
)
STAND_IN_MSIINFO = """#!{python}
import sys
args = sys.argv[1:]
if len(args) == 3 and args[0] == "export" and args[2] == "Property":
    sys.stdout.write({table!r})
    sys.exit(0)
sys.exit(2)
"""

PCMAN = importer.PcmanImporter


@unittest.skipUnless(
    TOOL_SOURCE and TOOL_PYTHON,
    "set PCMAN_TOOL_SOURCE and PCMAN_TOOL_PYTHON to run the tests against the real package tool",
)
class RealToolTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="win-shared-real-")
        self.addCleanup(self._tmp.cleanup)
        tmp = os.path.realpath(self._tmp.name)
        self.tool = os.path.join(tmp, "tool")
        os.makedirs(self.tool)
        for folder in COPIED_FOLDERS:
            shutil.copytree(
                os.path.join(TOOL_SOURCE, folder),
                os.path.join(self.tool, folder),
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        os.makedirs(os.path.join(self.tool, "items"))
        self.repo = os.path.join(tmp, "repository")
        os.makedirs(os.path.join(self.repo, "pkgs"))
        os.makedirs(os.path.join(self.repo, "pkgsinfo"))
        self.state = os.path.join(tmp, "state")
        os.makedirs(self.state)
        self.downloads = os.path.join(tmp, "my downloads")
        os.makedirs(self.downloads)
        self.msi_bin = os.path.join(tmp, "msi-bin")
        os.makedirs(self.msi_bin)
        self.set_msi_version("4.7.0")
        self.tool_env = {
            "PCMAN_CIMIAN_REPO": self.repo,
            "PCMAN_STATE_DIR": self.state,
            "PCMAN_CONFIG": os.path.join(tmp, "no-such-config.yaml"),
            "PCMAN_CIMIAN_CATALOGS": "Production",
            "PATH": self.msi_bin + os.pathsep + "/usr/bin:/bin",
            "HOME": tmp,
        }

    def set_msi_version(self, version):
        path = os.path.join(self.msi_bin, "msiinfo")
        with open(path, "w") as handle:
            handle.write(STAND_IN_MSIINFO.format(python=TOOL_PYTHON, table=MSIINFO_TABLE % version))
        os.chmod(path, 0o755)

    def installer(self, name, content):
        path = os.path.join(self.downloads, name)
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def pcman_by_hand(self, *args):
        """The first import of a program: a person runs the tool."""
        proc = subprocess.run(
            [TOOL_PYTHON, os.path.join(self.tool, "bin", "pcman"), *args],
            env=self.tool_env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=SETUP_TIMEOUT_SECONDS,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def make_exe_template(self, name="Example-App"):
        first = self.installer("Example App-1.0.exe", b"MZ first version")
        self.pcman_by_hand(
            "import", first, "--name", name, "--version", "1.0", "--directory", "apps",
            "--install-path", r"C:\Program Files\Example App\example.exe", "--build", "--no-prompt",
        )

    def env(self, installer, **overrides):
        env = {
            "checksum_verified": True,  # as after a ChecksumVerifier step ...
            "checksum_sha256": sha256_hex(installer),  # ... which also gives the hash
            "pathname": installer,
            "pcman_template": "Example-App",
            "pcman_version": "2.0",
            "pcman_root": self.tool,
            "pcman_python": TOOL_PYTHON,
            "pcman_dry_run": False,
            "pcman_path": self.msi_bin + os.pathsep + "/usr/bin:/bin",
            "pcman_cimian_repo": self.repo,
            "pcman_state_dir": self.state,
            "pcman_config": os.path.join(os.path.dirname(self.tool), "no-such-config.yaml"),
        }
        env.update(overrides)
        return {k: v for k, v in env.items() if v is not None}

    def repository_files(self):
        found = set()
        for folder, _, files in os.walk(self.repo):
            for name in files:
                found.add(os.path.relpath(os.path.join(folder, name), self.repo))
        return found

    def test_a_dry_run_writes_nothing(self):
        self.make_exe_template()
        before = self.repository_files()
        second = self.installer("Example App-2.0.exe", b"MZ second version")
        processor, messages = run_processor(PCMAN, self.env(second, pcman_dry_run=None))
        self.assertEqual(processor.env["pcman_result"], "dry-run")
        self.assertIs(processor.env["pcman_repo_changed"], False)
        self.assertEqual(
            processor.env["pcman_importer_summary_result"]["data"]["result"], "dry run, nothing written"
        )
        self.assertEqual(self.repository_files(), before)
        self.assertTrue(any(m.startswith("WARNING:") for m in messages))

    def test_a_publish_from_a_template_writes_the_installer_and_the_pkginfo(self):
        self.make_exe_template()
        second = self.installer("Example App-2.0.exe", b"MZ second version")
        processor, _ = run_processor(PCMAN, self.env(second))
        env = processor.env
        self.assertEqual(env["pcman_result"], "published")
        self.assertIs(env["pcman_repo_changed"], True)
        self.assertEqual(env["pcman_name"], "Example-App")
        self.assertEqual(env["pcman_version_published"], "2.0")
        self.assertTrue(os.path.isfile(env["pcman_pkginfo_path"]))
        self.assertTrue(os.path.isfile(env["pcman_installer_path"]))
        with open(env["pcman_pkginfo_path"], "r", encoding="utf-8") as handle:
            pkginfo = handle.read()
        self.assertIn("pcman_published: true", pkginfo)
        self.assertIn("2.0", pkginfo)
        summary = env["pcman_importer_summary_result"]
        self.assertEqual(summary["data"]["version"], "2.0")

    def test_an_unverified_download_is_refused_in_a_real_run_and_writes_nothing(self):
        self.make_exe_template()
        before = self.repository_files()
        second = self.installer("Example App-2.0.exe", b"MZ second version")
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env(second, checksum_verified=None))
        self.assertIn("not verified", str(caught.exception))
        self.assertEqual(self.repository_files(), before)

    def test_a_file_other_than_the_verified_one_is_refused_and_writes_nothing(self):
        self.make_exe_template()
        before = self.repository_files()
        verified = self.installer("Example App-2.0.exe", b"MZ second version")
        other = self.installer("Example App-2.1.exe", b"MZ a file that nobody checked")
        for dry_run in (False, None):
            with self.subTest(dry_run=dry_run):
                env = self.env(verified, pcman_dry_run=dry_run, pcman_allow_unverified=True)
                env["pathname"] = other
                with self.assertRaises(ProcessorError) as caught:
                    run_processor(PCMAN, env)
                self.assertIn("not the file whose checksum was verified", str(caught.exception))
                self.assertEqual(self.repository_files(), before)

    def test_an_unverified_download_with_the_allowance_is_published_and_marked(self):
        self.make_exe_template()
        second = self.installer("Example App-2.0.exe", b"MZ second version")
        processor, messages = run_processor(
            PCMAN, self.env(second, checksum_verified=None, pcman_allow_unverified=True)
        )
        self.assertEqual(processor.env["pcman_result"], "published")
        self.assertTrue(os.path.isfile(processor.env["pcman_pkginfo_path"]))
        self.assertEqual(
            processor.env["pcman_importer_summary_result"]["data"]["result"], "published, NOT verified"
        )
        self.assertTrue(any("published WITHOUT a verified download" in m for m in messages))

    def test_the_second_run_says_nothing_new(self):
        self.make_exe_template()
        second = self.installer("Example App-2.0.exe", b"MZ second version")
        run_processor(PCMAN, self.env(second))
        before = self.repository_files()
        processor, messages = run_processor(PCMAN, self.env(second))
        self.assertEqual(processor.env["pcman_result"], "nothing-new")
        self.assertIs(processor.env["pcman_repo_changed"], False)
        self.assertNotIn("pcman_importer_summary_result", processor.env)
        self.assertEqual(self.repository_files(), before)
        self.assertTrue(any(m.startswith("Nothing new") for m in messages))

    def test_a_label_the_client_cannot_order_is_an_error_and_writes_nothing(self):
        self.make_exe_template()
        before = self.repository_files()
        second = self.installer("Example App-9.exe", b"MZ other version")
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env(second, pcman_version="v9.0"))
        self.assertIn("v9.0", str(caught.exception))
        self.assertEqual(self.repository_files(), before)

    def test_the_same_version_with_another_installer_is_an_error(self):
        self.make_exe_template()
        second = self.installer("Example App-2.0.exe", b"MZ second version")
        run_processor(PCMAN, self.env(second))
        replaced = self.installer("Example App-2.0-again.exe", b"MZ a vendor replaced the file")
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env(replaced))
        self.assertIn("ERROR", str(caught.exception))

    def test_a_repository_that_is_not_there_is_an_error_and_nothing_is_made(self):
        self.make_exe_template()
        second = self.installer("Example App-2.0.exe", b"MZ second version")
        shutil.rmtree(os.path.join(self.repo, "pkgsinfo"))
        with self.assertRaises(ProcessorError):
            run_processor(PCMAN, self.env(second))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "pkgsinfo")))

    def test_an_unknown_template_is_an_error(self):
        self.make_exe_template()
        second = self.installer("Example App-2.0.exe", b"MZ second version")
        with self.assertRaises(ProcessorError):
            run_processor(PCMAN, self.env(second, pcman_template="No Such Program"))

    def test_an_msi_takes_its_label_from_the_msi(self):
        first = self.installer("Example App-1.0.msi", b"first msi")
        self.set_msi_version("1.0.0")
        self.pcman_by_hand(
            "import", first, "--name", "Example-App", "--directory", "apps", "--build", "--no-prompt",
        )
        self.set_msi_version("4.7.0")
        second = self.installer("Example App-4.7.0.msi", b"second msi")
        processor, messages = run_processor(PCMAN, self.env(second, pcman_version=None))
        self.assertEqual(processor.env["pcman_result"], "published")
        self.assertEqual(processor.env["pcman_version_published"], "4.7.0")
        # The note for a minor upgrade is shown whole, with its advice at the end.
        notes = [m for m in messages if "minor upgrade" in m]
        self.assertEqual(len(notes), 1)
        self.assertTrue(notes[0].startswith("NOTE:"))
        self.assertTrue(notes[0].endswith("No install argument is added by this tool."))
        self.assertEqual(
            [level for level, text in processor.message_levels if text == notes[0]], [importer.ALWAYS_SHOWN]
        )
        self.assertFalse([v for v in processor.env["pcman_importer_summary_result"]["data"].values() if "/" in v])

    def test_an_msi_with_another_label_than_its_own_is_an_error(self):
        first = self.installer("Example App-1.0.msi", b"first msi")
        self.set_msi_version("1.0.0")
        self.pcman_by_hand(
            "import", first, "--name", "Example-App", "--directory", "apps", "--build", "--no-prompt",
        )
        self.set_msi_version("4.7.0")
        second = self.installer("Example App-4.7.0.msi", b"second msi")
        before = self.repository_files()
        with self.assertRaises(ProcessorError):
            run_processor(PCMAN, self.env(second, pcman_version="5.0.0"))
        self.assertEqual(self.repository_files(), before)


if __name__ == "__main__":
    unittest.main()
