"""Tests of the two Kyocera KX recipes and the README. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names a processor is compared with what
that processor declares (the shared ones in ../../Win-SharedProcessors, the package tool's importer
in ../../Win-PcmanProcessors, the repacker in this folder). One test runs the chain as a whole:
the repacker on a made-up vendor zip, then the importer with the arguments of the pcman recipe and a
stand-in for the package tool.
"""
import os
import plistlib
import re
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.dirname(TESTS_DIR)
REPO_DIR = os.path.dirname(RECIPE_DIR)
SHARED_DIR = os.path.join(REPO_DIR, "Win-SharedProcessors")
PCMAN_DIR = os.path.join(REPO_DIR, "Win-PcmanProcessors")
for folder in (os.path.join(SHARED_DIR, "tests"), os.path.join(PCMAN_DIR, "tests"), TESTS_DIR, RECIPE_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import _win_support  # noqa: E402,F401  (installs the autopkglib stand-in, imports the processors)
import _pcman_support  # noqa: E402
import test_public_repository as shared_hygiene  # noqa: E402
import test_repacker as repacker_tests  # noqa: E402
import KyoceraKXDriverRepacker as repacker  # noqa: E402
import PcmanImporter as importer  # noqa: E402

PREFIX = "com.github.serrc-techops"
PCMAN_PREFIX = PREFIX + ".PcmanProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "KyoceraKXDriver-Win.download.recipe")
PCMAN = os.path.join(RECIPE_DIR, "KyoceraKXDriver.pcman.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
URL = ("https://www.kyoceradocumentsolutions.us/content/dam/download-center-americas-cf/us/drivers/drivers/"
       "KX_Print_Driver_zip.download.zip")
HEX_64 = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo", "pcman_config",
                     "pcman_cimian_catalogs", "pcman_state_dir", "pcman_allow_unverified", "cimian_allow_unverified",
                     "cimian_dry_run", "cimian_repo", "checksum_verified", "checksum_sha256", "expected_sha256")


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def text_of(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def squeeze(text):
    return re.sub(r"\s+", " ", text)


class RecipeFileTests(unittest.TestCase):
    def test_the_files_have_the_keys_that_autopkg_reads(self):
        for path in (DOWNLOAD, PCMAN):
            recipe = load(path)
            for key in ("Description", "Identifier", "Input", "MinimumVersion", "Process"):
                self.assertIn(key, recipe, path)

    def test_identifiers_and_parents(self):
        download, pcman = load(DOWNLOAD), load(PCMAN)
        self.assertEqual(download["Identifier"], PREFIX + ".download.KyoceraKXDriver-Win")
        self.assertEqual(pcman["Identifier"], PREFIX + ".pcman.KyoceraKXDriver")
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_there_is_no_cimian_recipe_and_the_readme_says_why(self):
        self.assertEqual(sorted(n for n in os.listdir(RECIPE_DIR) if n.endswith(".recipe")),
                         ["KyoceraKXDriver-Win.download.recipe", "KyoceraKXDriver.pcman.recipe"])
        self.assertIn("no `.cimian.recipe`", squeeze(text_of(README)))

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, ["URLDownloader", "EndOfCheckPhase", "KyoceraKXDriverRepacker"])

    def test_the_downloader_address_is_the_fixed_one_and_the_file_name_is_set(self):
        args = load(DOWNLOAD)["Process"][0]["Arguments"]
        self.assertEqual(args["url"], URL)
        self.assertEqual(args["filename"], "KX_Print_Driver.zip")
        self.assertNotIn("request_headers", args)

    def test_the_repacker_step_and_the_inputs(self):
        recipe = load(DOWNLOAD)
        step = recipe["Process"][2]
        self.assertEqual(step["Arguments"], {"pathname": "%pathname%", "kx_architecture_folder": "%KX_ARCHITECTURE_FOLDER%"})
        for key in step["Arguments"]:
            self.assertIn(key, repacker.KyoceraKXDriverRepacker.input_variables)
        inputs = recipe["Input"]
        self.assertEqual(sorted(inputs), ["KX_ARCHITECTURE_FOLDER", "NAME", "kx_required_driver_names"])
        self.assertEqual(inputs["KX_ARCHITECTURE_FOLDER"], "64bit")
        self.assertIsInstance(inputs["kx_required_driver_names"], list)
        self.assertEqual(inputs["kx_required_driver_names"], ["KX DRIVER for Universal Printing"])
        self.assertIn("kx_required_driver_names", repacker.KyoceraKXDriverRepacker.input_variables)

    def test_the_list_input_is_not_passed_through_a_variable(self):
        # A %variable% is replaced through a text substitution, which does not carry a list (AutoPkg's update_data would fail).
        self.assertNotIn("%kx_required_driver_names%", text_of(DOWNLOAD).lower())
        self.assertNotIn("KX_REQUIRED_DRIVER_NAMES", text_of(DOWNLOAD))

    def test_no_hash_anywhere_and_no_check_that_is_not_there(self):
        for path in (DOWNLOAD, PCMAN):
            self.assertIsNone(HEX_64.search(text_of(path)), path)
        # The README holds one hash: the result of the run of 2026-11-17, stated as a result and not as a pin.
        self.assertEqual(HEX_64.findall(text_of(README)), ["938a3b8a4ee6089b9ffde2d5f9aa38a4f4e32ec5c310622935e70be3e34f4c33"])
        for step in load(DOWNLOAD)["Process"]:
            self.assertNotIn("ChecksumVerifier", step["Processor"])
        for path in (DOWNLOAD, PCMAN):
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text_of(path))

    def test_the_pcman_recipe_hands_over_the_zip_and_the_version(self):
        pcman = load(PCMAN)
        self.assertEqual([s["Processor"] for s in pcman["Process"]], [PCMAN_PREFIX + "PcmanImporter"])
        self.assertEqual(pcman["Input"], {"NAME": "KyoceraKXDriver", "PCMAN_TEMPLATE": "KyoceraKXDriver"})
        arguments = pcman["Process"][0]["Arguments"]
        self.assertEqual(arguments, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%", "pcman_version": "%version%"})
        for key in arguments:
            self.assertIn(key, importer.PcmanImporter.input_variables)

    def test_every_required_input_of_the_importer_is_given_but_the_machines(self):
        arguments = load(PCMAN)["Process"][0]["Arguments"]
        for key, flags in importer.PcmanImporter.input_variables.items():
            if flags.get("required") and "default" not in flags and key != "pcman_root":
                self.assertIn(key, arguments)

    def test_the_download_recipe_does_not_stop_on_an_unchanged_download(self):
        for path in (DOWNLOAD, PCMAN):
            for word in ("StopProcessingIf", "latest_only", "blocking_applications"):
                self.assertNotIn(word, text_of(path))

    def test_the_descriptions_say_what_is_not_established(self):
        download = squeeze(load(DOWNLOAD)["Description"])
        for needle in ("is NOT verified", "Kyocera publishes no checksum", "pcman_allow_unverified", "2026-11-17",
                       "ran under AutoPkg 2.9.0 in a scratch folder", "no ETag", "downloads it at every run", "downloaded the whole file again", "checksum_verified stays false"):
            self.assertIn(needle, download)
        pcman = squeeze(load(PCMAN)["Description"])
        for needle in ("is NOT verified", "pcman_allow_unverified", "ran under AutoPkg 2.9.0 into a scratch Cimian repository", "published KyoceraKXDriver 8.7.0917.0", "trusted publisher", "adds no trust", "does not check who signed the catalog", "printer_driver",
                       "dry run", "no cimian recipe"):
            self.assertIn(needle, pcman)

    def test_the_repacker_is_a_file_of_this_folder_and_the_importer_one_of_the_pcman_folder(self):
        self.assertTrue(os.path.isfile(os.path.join(RECIPE_DIR, "KyoceraKXDriverRepacker.py")))
        self.assertTrue(os.path.isfile(os.path.join(PCMAN_DIR, "PcmanImporter.py")))


class ChainTests(_pcman_support.ToolTestCase):
    """The repacker's zip goes to the importer with the pcman recipe's arguments."""

    def test_the_repacked_zip_is_handed_to_the_tool_with_its_version(self):
        zip_path = os.path.join(self.downloads, "KX_Print_Driver.zip")
        repacker_tests.write_zip(zip_path, repacker_tests.vendor_members())
        env = {"pathname": zip_path}
        processor, _ = _win_support.run_processor(repacker.KyoceraKXDriverRepacker, env)
        facts = processor.env
        # The recipe's arguments, resolved from what the repacker left in the run.
        arguments = {"pathname": facts["pathname"], "pcman_template": load(PCMAN)["Input"]["PCMAN_TEMPLATE"],
                     "pcman_version": facts["version"]}
        self.behave(result=_pcman_support.result_file_content(result="dry-run", name="KyoceraKXDriver", version=facts["version"]))
        tool_env = self.env(installer=facts["pathname"], pcman_template=arguments["pcman_template"],
                            pcman_version=arguments["pcman_version"], checksum_verified=None,
                            checksum_sha256=facts["checksum_sha256"], pcman_dry_run=True)
        _win_support.run_processor(importer.PcmanImporter, tool_env)
        argv = self.record()["argv"]
        self.assertEqual(argv[1], facts["pathname"])
        self.assertTrue(argv[1].endswith("KyoceraKXDriver-8.7.0917.0.zip"))
        self.assertEqual(argv[argv.index("--template") + 1], "KyoceraKXDriver")
        self.assertEqual(argv[argv.index("--version") + 1], "8.7.0917.0")
        self.assertIn("--dry-run", argv)

    def test_a_real_run_is_refused_until_the_override_allows_the_unverified_download(self):
        zip_path = os.path.join(self.downloads, "KX_Print_Driver.zip")
        repacker_tests.write_zip(zip_path, repacker_tests.vendor_members())
        processor, _ = _win_support.run_processor(repacker.KyoceraKXDriverRepacker, {"pathname": zip_path})
        facts = processor.env
        tool_env = self.env(installer=facts["pathname"], pcman_version=facts["version"], checksum_verified=facts["checksum_verified"],
                            checksum_sha256=facts["checksum_sha256"])
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(importer.PcmanImporter, tool_env)
        self.assertIn("not verified", str(caught.exception))
        self.assertFalse(self.was_run())
        tool_env["pcman_allow_unverified"] = True
        _win_support.run_processor(importer.PcmanImporter, tool_env)
        self.assertTrue(self.was_run())


class HygieneTests(unittest.TestCase):
    def files(self):
        for folder, dirs, files in os.walk(RECIPE_DIR):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if not name.endswith(".pyc"):
                    yield os.path.join(folder, name)

    def test_no_file_holds_a_value_that_belongs_to_one_site(self):
        for path in self.files():
            text = text_of(path)
            for kind, pattern in shared_hygiene.FORBIDDEN_PATTERNS.items():
                with self.subTest(file=os.path.relpath(path, RECIPE_DIR), kind=kind):
                    self.assertIsNone(pattern.search(text))

    def test_nothing_deeper_than_the_tests_folder(self):
        for path in self.files():
            self.assertLessEqual(len(os.path.relpath(path, RECIPE_DIR).split(os.sep)), 2, path)

    def test_the_folder_holds_what_is_expected(self):
        self.assertEqual(sorted(n for n in os.listdir(RECIPE_DIR) if n != "__pycache__"),
                         ["KyoceraKXDriver-Win.download.recipe", "KyoceraKXDriver.pcman.recipe", "KyoceraKXDriverRepacker.py",
                          "README.md", "tests"])

    def test_the_repacker_has_the_class_of_its_name(self):
        self.assertTrue(hasattr(repacker, "KyoceraKXDriverRepacker"))


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.raw = text_of(README)
        self.text = squeeze(self.raw)

    def commands(self):
        return [m.group(1) for m in re.finditer(r"^ {4,}(autopkg [^\n]*)$", self.raw, re.M)]

    def test_the_status_is_the_third_paragraph_in_bold(self):
        lines = [line for line in self.raw.splitlines() if line.strip()]
        self.assertTrue(lines[0].startswith("# "))
        status = lines[2]
        self.assertTrue(status.startswith("**Status."))
        self.assertTrue(status.endswith("**"))
        self.assertEqual(status.count("**"), 2)
        for needle in ("RUN on 2026-11-17 under AutoPkg 2.9.0", "scratch Cimian repository", "scratch copy of the package tool",
                       "DriverVer=09/17/2026,8.7.0917.0", "549", "718 files", "refused (exit 70)",
                       "published `KyoceraKXDriver` 8.7.0917.0", "Nothing new", "no ETag", "Kyocera publishes no checksum",
                       "pcman_allow_unverified", "THE PUBLISHER'S CERTIFICATE", "trusted publisher", "TrustedPublisher",
                       "Authenticode(tm) signed catalog has not yet been established as trusted", "valid until 2026-12-08",
                       "Windows Hardware Compatibility Publisher", "8.4.1716.0 to 8.7.917.0", "does not add trust",
                       "does not check who signed the catalog", "later version is signed by Microsoft again is NOT established",
                       "a run through the Cimian client", "an install of 8.7.0917.0 on a PC without an older version",
                       "`32bit/` and `arm64/`"):
            self.assertIn(needle, status)
        self.assertLess(self.raw.index("**Status."), self.raw.index("## What protects"))

    def test_every_autopkg_command_carries_the_override_dir_and_names_no_identifier(self):
        commands = self.commands()
        self.assertTrue(commands)
        for command in commands:
            with self.subTest(command=command):
                self.assertIn("--override-dir=<the Windows overrides folder>", command)
                self.assertNotIn("com.github.", command)
        self.assertEqual(len(re.findall(r"^[ \t]*autopkg ", self.raw, re.M)), len(commands))

    def test_the_table_has_the_two_recipes(self):
        for name, identifier in (("KyoceraKXDriver-Win.download.recipe", "com.github.serrc-techops.download.KyoceraKXDriver-Win"),
                                 ("KyoceraKXDriver.pcman.recipe", "com.github.serrc-techops.pcman.KyoceraKXDriver")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)

    def test_the_unverified_download_is_explained(self):
        section = self.text[self.text.index("## What protects"):]
        for needle in ("pcman_allow_unverified", "checksum_verified", "false", "SHA-256 of the NEW zip",
                       "no hash is pinned", "downloads the 252 MB file at every run"):
            self.assertIn(needle, section)

    def test_the_publishers_certificate_section(self):
        self.assertIn("## The publisher's certificate", self.raw)
        section = self.text[self.text.index("## The publisher's certificate"):self.text.index("## Run every override")]
        for needle in ("silently only when the vendor's own signing certificate is a trusted publisher", "TrustedPublisher",
                       "does not add trust and must not", "defeat the check", "changes when it expires",
                       "does not check who signed the catalog"):
            self.assertIn(needle, section)
        self.assertLess(self.raw.index("## The publisher's certificate"), self.raw.index("## With the package tool"))

    def test_nothing_that_is_no_longer_true_is_left(self):
        for old in ("NOT run under AutoPkg", "NOT downloaded", "was not tried", "has not run under AutoPkg"):
            self.assertNotIn(old, self.raw)
        for path in (DOWNLOAD, PCMAN):
            self.assertNotIn("NOT run under AutoPkg", text_of(path))
            self.assertNotIn("has not run under AutoPkg", text_of(path))

    def test_the_tests_section_gives_the_command(self):
        self.assertIn("python3 -m unittest discover -s Win-KyoceraKXDriver/tests -t Win-KyoceraKXDriver/tests", self.raw)

    def test_the_importer_change_is_documented_in_its_readme(self):
        text = squeeze(text_of(os.path.join(PCMAN_DIR, "README.md")))
        self.assertIn("A print driver zip", text)
        self.assertIn("`.zip`", text)


if __name__ == "__main__":
    unittest.main()
