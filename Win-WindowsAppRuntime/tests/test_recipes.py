"""Tests of the three Windows App Runtime recipes and the README. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names a processor is compared with
what that processor declares (the shared ones in ../../Win-SharedProcessors, the
extractor in this folder).
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
for folder in (os.path.join(SHARED_DIR, "tests"), os.path.join(PCMAN_DIR, "tests"), RECIPE_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import _win_support  # noqa: E402,F401  (installs the autopkglib stand-in, imports the processors)
import _pcman_support  # noqa: E402,F401
import test_public_repository as shared_hygiene  # noqa: E402
import WindowsAppRuntimeFrameworkExtractor as extractor  # noqa: E402

PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = PREFIX + ".PcmanProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "WindowsAppRuntime-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "WindowsAppRuntime.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "WindowsAppRuntime.pcman.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
HEX_64 = re.compile(r"(?i)\b[0-9a-f]{64}\b")
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo", "pcman_config",
                     "pcman_cimian_catalogs", "pcman_state_dir", "pcman_allow_unverified", "cimian_allow_unverified",
                     "cimian_dry_run", "cimian_repo", "checksum_verified", "checksum_sha256")


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def text_of(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def squeeze(text):
    return re.sub(r"\s+", " ", text)


class RecipeFileTests(unittest.TestCase):
    def test_the_three_files_have_the_keys_that_autopkg_reads(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            recipe = load(path)
            for key in ("Description", "Identifier", "Input", "MinimumVersion", "Process"):
                self.assertIn(key, recipe, path)

    def test_identifiers_and_parents(self):
        download, cimian, pcman = load(DOWNLOAD), load(CIMIAN), load(PCMAN)
        self.assertEqual(download["Identifier"], PREFIX + ".download.WindowsAppRuntime-Win")
        self.assertEqual(cimian["Identifier"], PREFIX + ".cimian.WindowsAppRuntime")
        self.assertEqual(pcman["Identifier"], PREFIX + ".pcman.WindowsAppRuntime")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, ["URLDownloader", "EndOfCheckPhase", SHARED_PREFIX + "ChecksumVerifier",
                                 "WindowsAppRuntimeFrameworkExtractor"])

    def test_the_downloader_address_is_built_from_the_release(self):
        args = load(DOWNLOAD)["Process"][0]["Arguments"]
        self.assertEqual(args["url"], "https://aka.ms/windowsappsdk/%WINDOWSAPPRUNTIME_RELEASE%/latest/"
                                      "Microsoft.WindowsAppRuntime.Redist.%WINDOWSAPPRUNTIME_RELEASE%.zip")
        self.assertEqual(args["filename"], "Microsoft.WindowsAppRuntime.Redist.%WINDOWSAPPRUNTIME_RELEASE%.zip")

    def test_the_download_inputs(self):
        inputs = load(DOWNLOAD)["Input"]
        self.assertEqual(sorted(inputs), ["NAME", "REDIST_SHA256", "WINDOWSAPPRUNTIME_ARCHITECTURE", "WINDOWSAPPRUNTIME_RELEASE"])
        self.assertEqual(inputs["WINDOWSAPPRUNTIME_RELEASE"], "1.4")
        self.assertEqual(inputs["WINDOWSAPPRUNTIME_ARCHITECTURE"], "x64")
        self.assertRegex(inputs["REDIST_SHA256"], r"^[0-9a-f]{64}$")

    def test_the_checksum_step_checks_the_zip_against_the_input(self):
        step = load(DOWNLOAD)["Process"][2]
        self.assertEqual(step["Arguments"], {"pathname": "%pathname%", "expected_sha256": "%REDIST_SHA256%"})

    def test_the_extractor_step_passes_the_release_and_the_architecture(self):
        step = load(DOWNLOAD)["Process"][3]
        self.assertEqual(step["Arguments"], {
            "pathname": "%pathname%", "windowsappruntime_release": "%WINDOWSAPPRUNTIME_RELEASE%",
            "windowsappruntime_architecture": "%WINDOWSAPPRUNTIME_ARCHITECTURE%"})
        for key in step["Arguments"]:
            self.assertIn(key, extractor.WindowsAppRuntimeFrameworkExtractor.input_variables)

    def test_the_only_hash_is_the_pinned_one_in_the_download_recipe(self):
        self.assertEqual(len(HEX_64.findall(text_of(DOWNLOAD))), 1)
        for path in (CIMIAN, PCMAN, README):
            self.assertIsNone(HEX_64.search(text_of(path)), path)

    def test_the_pin_is_described_as_our_record_and_not_the_vendors(self):
        text = squeeze(load(DOWNLOAD)["Description"])
        for needle in ("is NOT a checksum that Microsoft publishes", "our own record", "2026-11-16",
                       "the run stops at the checksum step with nothing written", "sets the new value in the override's Input",
                       "the file's ETag is not its SHA-256",
                       "this recipe ran under AutoPkg 2.9.0 into a scratch Cimian repository",
                       "it has not run against a real repository"):
            self.assertIn(needle, text)

    def test_the_importer_recipes(self):
        cimian, pcman = load(CIMIAN), load(PCMAN)
        self.assertEqual([s["Processor"] for s in cimian["Process"]], [SHARED_PREFIX + "CimianImporter"])
        self.assertEqual([s["Processor"] for s in pcman["Process"]], [PCMAN_PREFIX + "PcmanImporter"])
        self.assertEqual(cimian["Input"]["CIMIAN_NAME"], "WindowsAppRuntime.1.4")
        self.assertEqual(pcman["Input"]["PCMAN_TEMPLATE"], "WindowsAppRuntime.1.4")
        self.assertEqual(cimian["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%", "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": ""})
        self.assertEqual(pcman["Process"][0]["Arguments"], {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%"})
        self.assertEqual(cimian["Input"]["pkginfo"], {"developer": "Microsoft Corporation", "display_name": "Windows App Runtime 1.4"})

    def test_every_argument_is_a_declared_input_and_every_required_input_is_given(self):
        declared = {"CimianImporter": _win_support.cimian.CimianImporter.input_variables,
                    "ChecksumVerifier": _win_support.checksum.ChecksumVerifier.input_variables,
                    "PcmanImporter": __import__("PcmanImporter").PcmanImporter.input_variables}
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            for step in load(path)["Process"]:
                name = step["Processor"].rsplit("/", 1)[-1]
                if name not in declared:
                    continue
                for key in step["Arguments"]:
                    self.assertIn(key, declared[name], (path, key))
                for key, flags in declared[name].items():
                    if flags.get("required") and "default" not in flags and key != "pcman_root":
                        self.assertIn(key, step["Arguments"], (path, name, key))

    def test_no_recipe_gives_a_version_label_or_stops_on_an_unchanged_download(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = text_of(path)
            for word in ("pcman_version", "%version%", "StopProcessingIf", "latest_only", "blocking_applications"):
                self.assertNotIn(word, text)

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text_of(path))

    def test_the_importer_descriptions_say_what_is_not_established(self):
        for path in (CIMIAN, PCMAN):
            text = squeeze(load(path)["Description"])
            self.assertIn("is NOT established", text)
            self.assertIn("dry run", text)
            self.assertIn("2026-11-16", text)
            self.assertNotIn("ehearsed", text)
        self.assertIn("names one architecture", squeeze(load(CIMIAN)["Description"]))
        self.assertIn("--architectures x64", squeeze(load(PCMAN)["Description"]))

    def test_the_extractor_is_a_file_of_this_folder_and_a_shared_processor_is_a_file_of_the_shared_folder(self):
        self.assertTrue(os.path.isfile(os.path.join(RECIPE_DIR, "WindowsAppRuntimeFrameworkExtractor.py")))
        self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, "ChecksumVerifier.py")))
        self.assertTrue(os.path.isfile(os.path.join(PCMAN_DIR, "PcmanImporter.py")))


class HygieneTests(unittest.TestCase):
    def files(self):
        for folder, dirs, files in os.walk(RECIPE_DIR):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if not name.endswith(".pyc"):
                    yield os.path.join(folder, name)

    def test_no_file_holds_a_value_that_belongs_to_one_site(self):
        for path in self.files():
            if os.path.basename(path) in ("test_recipes.py", "test_extractor.py"):
                continue
            text = text_of(path)
            for kind, pattern in shared_hygiene.FORBIDDEN_PATTERNS.items():
                with self.subTest(file=os.path.relpath(path, RECIPE_DIR), kind=kind):
                    self.assertIsNone(pattern.search(text))

    def test_the_test_files_hold_no_address_either(self):
        for name in ("test_recipes.py", "test_extractor.py"):
            text = text_of(os.path.join(TESTS_DIR, name))
            self.assertIsNone(shared_hygiene.FORBIDDEN_PATTERNS["an IPv4 address"].search(text), name)

    def test_nothing_deeper_than_the_tests_folder(self):
        for path in self.files():
            self.assertLessEqual(len(os.path.relpath(path, RECIPE_DIR).split(os.sep)), 2, path)


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.raw = text_of(README)
        self.text = squeeze(self.raw)

    def commands(self):
        return [m.group(1) for m in re.finditer(r"^ {4,}(autopkg [^\n]*)$", self.raw, re.M)]

    def test_the_status_line_is_the_third_paragraph_and_says_what_was_read_and_what_was_not(self):
        lines = [line for line in self.raw.splitlines() if line.strip()]
        self.assertTrue(lines[0].startswith("# "))
        status = lines[2]
        self.assertTrue(status.startswith("**Status. Run once under AutoPkg 2.9.0 into a scratch Cimian repository on 2026-11-16"))
        self.assertTrue(status.endswith("**"))
        self.assertEqual(status.count("**"), 2)
        for needle in ("NOT run through a Cimian client", "no real repository was touched", "READ on 2026-11-16",
                       "answers 301", "251851408", "`Microsoft.WindowsAppRuntime.Redist.1.4.240802001.zip`",
                       "That ETag is NOT the SHA-256 of the file", "it is not a hash to compare with", "begins `0x8E966ABF`",
                       "22 entries", "22310719 bytes", "Version `4000.1309.2056.0`", "`Properties/Framework` true",
                       "OUR record of the file read on 2026-11-16, NOT a checksum that Microsoft publishes",
                       "the run stops at the checksum step",
                       "RUN on 2026-11-16 under AutoPkg 2.9.0", "that had no item of that name", "`verify-trust-info` OK",
                       "a dry run, a real run and a second real run", "`ChecksumVerifier` verified the zip's SHA-256",
                       "as `Microsoft.WindowsAppRuntime.1.4_4000.1309.2056.0_x64.msix`",
                       "published `WindowsAppRuntime.1.4` 4000.1309.2056(.0) in the catalog `Development`",
                       "the second run said that nothing is new",
                       "TESTED on 2026-11-16 on one Windows 11 test PC", "as SYSTEM from a scheduled task",
                       "succeeded for the framework ALONE", "WITHOUT any `-DependencyPackagePath`", "within 20 seconds",
                       "in state Installed", "on that PC the x64 framework alone was enough for Acellus",
                       "a framework can be provisioned by itself", "Acellus was not started",
                       "NOT established: the same through the Cimian client", "Windows 10",
                       "an x86 or ARM PC", "a user who signs in for the first time after the provisioning",
                       "removal", "a later Acellus version that names a higher minimum",
                       "a template without an architecture lets a package for one architecture go to every PC",
                       "must name the architecture", "Every command of this README carries `--override-dir`"):
            self.assertIn(needle, status)
        self.assertLess(self.raw.index("**Status."), self.raw.index("## What protects"))

    def test_the_status_claims_no_run_of_the_chain(self):
        self.assertNotIn("Rehearsed on", self.raw)
        self.assertNotIn("Nothing of this folder has run", self.raw)
        self.assertNotIn("Windows App SDK 1.4 is out of servicing", self.raw)
        self.assertNotIn("Run on 20", self.raw)

    def test_every_autopkg_command_carries_the_override_dir(self):
        commands = self.commands()
        self.assertEqual(len([c for c in commands if c.startswith("autopkg run")]), 2)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg verify-trust-info")]), 2)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg make-override")]), 2)
        for command in commands:
            with self.subTest(command=command):
                self.assertIn("--override-dir=<the Windows overrides folder>", command)
        for match in re.finditer(r"`(autopkg (?:run|verify-trust-info|update-trust-info|make-override)[^`]*<[^`]*)`", self.raw):
            self.assertIn("--override-dir=", match.group(1))

    def test_no_line_is_missed_by_the_indent_rule(self):
        self.assertEqual(len(re.findall(r"^[ \t]*autopkg ", self.raw, re.M)), len(self.commands()))

    def test_no_run_names_a_recipe_by_its_identifier(self):
        for command in self.commands():
            self.assertNotIn("com.github.", command)

    def test_the_sections_come_in_this_order(self):
        positions = [self.raw.index(mark) for mark in (
            "**Status.", "## What protects, and what does not", "## Run every override with `--override-dir`",
            "## With any Cimian repository", "## With the package tool (pcman)", "## Other facts", "## Tests")]
        self.assertEqual(positions, sorted(positions))

    def test_what_protects_says_what_the_pin_is_and_is_not(self):
        start = self.text.index("## What protects")
        section = self.text[start:self.text.index("## Run every override")]
        for needle in ("pinned, not vendor-verified", "our record of one file", "It does not prove that Microsoft published that file",
                       "never in the recipe", "From the zip's hash to the package's", "replaces `checksum_sha256` with the hash of the package",
                       "a real run is refused by the importers", "never the Main, Singleton or DDLM packages",
                       "`supported_architectures: [x64]`", "`--architectures x64`", "Only the x64 framework is published by default",
                       "On one test PC the x64 framework alone was enough for Acellus", "Not checked"):
            self.assertIn(needle, section)

    def test_the_table_has_the_three_recipes(self):
        for name, identifier in (("WindowsAppRuntime-Win.download.recipe", "com.github.serrc-techops.download.WindowsAppRuntime-Win"),
                                 ("WindowsAppRuntime.cimian.recipe", "com.github.serrc-techops.cimian.WindowsAppRuntime"),
                                 ("WindowsAppRuntime.pcman.recipe", "com.github.serrc-techops.pcman.WindowsAppRuntime")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)

    def test_the_first_import_with_the_package_tool_names_the_architecture_and_no_version(self):
        start = self.raw.index("pcman import ")
        command = self.raw[start:self.raw.index("\n\n", start)]
        self.assertIn("--architectures x64", command)
        self.assertNotIn("--version", command)

    def test_acellus_readme_points_here_and_keeps_the_by_hand_way(self):
        acellus = text_of(os.path.join(REPO_DIR, "Win-Acellus", "README.md"))
        self.assertGreaterEqual(acellus.count("../Win-WindowsAppRuntime/"), 3)
        self.assertIn("**Make the framework item once**", acellus)
        self.assertIn("By hand, or as the fallback", acellus)


if __name__ == "__main__":
    unittest.main()
