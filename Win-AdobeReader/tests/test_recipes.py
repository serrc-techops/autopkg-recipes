"""Tests of the two Adobe Acrobat Reader recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names one of our
processors is compared with what that processor declares: the shared ones
(see ../../Win-SharedProcessors) and this folder's own AdobeReaderInfoProvider
(tested in test_info_provider.py). The shared folder's tests are run separately.

The download of this program has NO hard check (no vendor hash, no signature
check). The tests make sure that nobody can overlook that: the Description of
both recipes and the top of the README say it, and no recipe invents a check.
The version label of the EXE is read from the file by WindowsExeVersion; the
chain test builds a small PE file to show that the label that reaches the
package tool is the file's, not the products file's.
"""
import os
import plistlib
import re
import subprocess
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.dirname(TESTS_DIR)
SHARED_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-SharedProcessors")
SHARED_TESTS_DIR = os.path.join(SHARED_DIR, "tests")
PCMAN_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-PcmanProcessors")
PCMAN_TESTS_DIR = os.path.join(PCMAN_DIR, "tests")
for folder in (SHARED_TESTS_DIR, RECIPE_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

if PCMAN_TESTS_DIR not in sys.path:
    sys.path.insert(0, PCMAN_TESTS_DIR)

import _win_support  # noqa: E402,F401  (installs the autopkglib stand-in, imports the processors)
import _pcman_support  # noqa: E402,F401  (the stand-in for the package tool, and its processor)
import test_public_repository as shared_hygiene  # noqa: E402
from test_exe_version import build_pe, version_info  # noqa: E402  (builds a small PE file)
import AdobeReaderInfoProvider as own  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
OWN_PROCESSOR = "AdobeReaderInfoProvider"
DOWNLOAD = os.path.join(RECIPE_DIR, "AdobeReader-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "AdobeReader.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "AdobeReader.pcman.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
EXCERPT = os.path.join(TESTS_DIR, "adobe_products_excerpt.json")
# Processors that are part of AutoPkg itself.
CORE_PROCESSORS = ("URLDownloader", "EndOfCheckPhase")
# Required inputs that a recipe must NOT pass: they come from AutoPkg's
# preferences or the override on the machine that runs it.
SUPPLIED_BY_THE_MACHINE = {"PcmanImporter": {"pcman_root"}}
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir", "pcman_timeout")
# What the earlier steps leave in the run (a step reads these without an argument).
SET_BY_CORE_STEPS = {"pathname", "url", "version"}
HEX_64 = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
# File names of recipes in repositories that the build machine has. AutoPkg takes the
# first match by name and says nothing about the others, so none of our file names may
# be one of these.
NAMES_OF_OTHER_REPOSITORIES = (
    "AdobeReader-Win.download", "AdobeReaderDC-Win.download", "AdobeAcrobatReaderDC-Win.download",
    "AdobeReader.download", "AdobeReader.munki", "AdobeReaderDC.download", "AdobeReaderDC.munki",
    "AdobeAcrobatReaderDC.download", "AdobeAcrobatReaderDC.munki", "AdobeReaderDC-Win64.download",
)
# The label that the file carries in the chain test: it is not the products file's.
FILE_LABEL = "26.2.21931.0"
FILE_LABEL_NUMBERS = (26, 2, 21931, 0)
# The product name of the real installer is the wrapper's, not the program's (read on 2026-10-02).
FILE_PRODUCT_NAME = "Adobe Self Extractor"


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def processor_classes():
    import importlib
    classes = {OWN_PROCESSOR: own.AdobeReaderInfoProvider}
    for name in ("PcmanImporter", "CimianImporter", "ChecksumVerifier", "GitHubAssetDigest", "WindowsExeVersion"):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def named_steps(recipe):
    """(processor name without the shared prefix, arguments) of every step
    that is ours: a shared processor or this folder's own."""
    for step in recipe["Process"]:
        name = step["Processor"]
        if name.startswith(SHARED_PREFIX):
            yield name[len(SHARED_PREFIX):], step.get("Arguments", {})
        elif name.startswith(PCMAN_PREFIX):
            yield name[len(PCMAN_PREFIX):], step.get("Arguments", {})
        elif name == OWN_PROCESSOR:
            yield name, step.get("Arguments", {})


def first_sentence(text):
    return re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]


class RecipeFileTests(unittest.TestCase):
    def test_both_files_are_valid_property_lists(self):
        for path in (DOWNLOAD, PCMAN):
            with self.subTest(path=os.path.basename(path)):
                result = subprocess.run(["plutil", "-lint", path], capture_output=True, text=True) \
                    if os.path.exists("/usr/bin/plutil") else None
                if result is not None:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                recipe = load(path)
                for key in ("Description", "Identifier", "Input", "MinimumVersion", "Process"):
                    self.assertIn(key, recipe)
                self.assertEqual(recipe["MinimumVersion"], "1.0.0")

    def test_identifiers_and_parent(self):
        download, cimian = load(DOWNLOAD), load(PCMAN)
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.AdobeReader-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".pcman.AdobeReader")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [
            OWN_PROCESSOR, "URLDownloader", "EndOfCheckPhase", SHARED_PREFIX + "WindowsExeVersion",
        ])

    def test_the_pcman_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(PCMAN)["Process"]]
        self.assertEqual(steps, [PCMAN_PREFIX + "PcmanImporter"])

    def test_the_exe_version_step_comes_after_the_end_of_the_check_phase(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertLess(steps.index("EndOfCheckPhase"), steps.index(SHARED_PREFIX + "WindowsExeVersion"))
        self.assertLess(steps.index("URLDownloader"), steps.index("EndOfCheckPhase"))
        self.assertEqual(steps[-1], SHARED_PREFIX + "WindowsExeVersion")

    def test_the_exe_version_step_reads_the_downloaded_file_and_sets_the_label(self):
        steps = dict(named_steps(load(DOWNLOAD)))
        self.assertEqual(steps["WindowsExeVersion"], {"pathname": "%pathname%"})
        flags = processor_classes()["WindowsExeVersion"].input_variables
        self.assertEqual(set(steps["WindowsExeVersion"]), {"pathname"})
        self.assertTrue(flags["set_version"]["default"])  # so `version` is the file's
        self.assertIn("version", processor_classes()["WindowsExeVersion"].output_variables)
        self.assertNotIn("set_version", read(DOWNLOAD))

    def test_the_provider_arguments_are_the_recipes_inputs(self):
        recipe = load(DOWNLOAD)
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"adobe_language": "%ADOBE_LANGUAGE%"})
        for value in args.values():
            match = re.fullmatch(r"%([A-Z_]+)%", value)
            self.assertTrue(match)
            self.assertIn(match.group(1), recipe["Input"])

    def test_the_defaults_of_the_recipe_are_the_defaults_of_the_processor(self):
        inputs = load(DOWNLOAD)["Input"]
        flags = own.AdobeReaderInfoProvider.input_variables
        self.assertEqual(inputs["ADOBE_LANGUAGE"], "en_US")
        self.assertEqual(inputs["ADOBE_LANGUAGE"], flags["adobe_language"]["default"])
        self.assertIn(inputs["ADOBE_LANGUAGE"], own.LANGUAGES)
        self.assertEqual(inputs["NAME"], "AdobeReader")
        self.assertEqual(sorted(inputs), ["ADOBE_LANGUAGE", "NAME"])

    def test_the_downloader_gets_its_address_from_the_provider_and_needs_no_file_name(self):
        """URLDownloader needs `url`. The provider sets it and the recipe passes no argument.
        The address ends in .exe, so the cached file has a name that PcmanImporter accepts."""
        step = load(DOWNLOAD)["Process"][1]
        self.assertEqual(step["Processor"], "URLDownloader")
        self.assertNotIn("Arguments", step)
        self.assertIn("url", own.AdobeReaderInfoProvider.output_variables)
        for language in own.LANGUAGES:
            url = own.installer_url("2600221931", language)
            self.assertTrue(url.endswith(".exe"))
            self.assertNotIn("?", url)
            self.assertNotIn(" ", url)
        self.assertNotIn("<key>filename</key>", read(DOWNLOAD))

    def test_every_variable_a_recipe_uses_is_an_input_or_set_by_an_earlier_step(self):
        for path in (DOWNLOAD, PCMAN):
            recipe = load(path)
            known = set(recipe["Input"]) | SET_BY_CORE_STEPS
            if path == PCMAN:
                known |= set(load(DOWNLOAD)["Input"])
            for step in recipe["Process"]:
                for value in step.get("Arguments", {}).values():
                    for name in re.findall(r"%([A-Za-z_]+)%", str(value)):
                        with self.subTest(recipe=os.path.basename(path), variable=name):
                            self.assertIn(name, known)
                # AutoPkg keeps the arguments of a step in the run: a later step reads them.
                known |= set(step.get("Arguments", {}))

    def test_the_inputs_of_the_pcman_recipe(self):
        recipe = load(PCMAN)
        self.assertEqual(recipe["Input"]["NAME"], "AdobeReader")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "adobereader")
        self.assertEqual(sorted(recipe["Input"]), ["NAME", "PCMAN_TEMPLATE"])
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%",
                                "pcman_version": "%version%"})

    def test_the_template_keeps_the_name_of_the_item_it_replaces(self):
        self.assertEqual(load(PCMAN)["Input"]["PCMAN_TEMPLATE"], "adobereader")

    def test_an_exe_recipe_passes_the_label_and_the_label_is_the_files(self):
        """For an EXE the package tool has no version of its own to read: the cimian recipe
        passes `version`. The download recipe's last step is the one that sets it from the file."""
        self.assertEqual(load(PCMAN)["Process"][0]["Arguments"]["pcman_version"], "%version%")
        self.assertNotIn("pcman_version", read(DOWNLOAD))
        last = load(DOWNLOAD)["Process"][-1]["Processor"]
        self.assertEqual(last, SHARED_PREFIX + "WindowsExeVersion")

    def test_no_stop_on_an_unchanged_download_and_no_latest_only(self):
        for path in (DOWNLOAD, PCMAN):
            text = read(path)
            self.assertNotIn("StopProcessingIf", text)
            self.assertNotIn("latest_only", text)

    def test_no_blocking_applications(self):
        for path in (DOWNLOAD, PCMAN):
            self.assertNotIn("blocking_applications", read(path))

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in (DOWNLOAD, PCMAN):
            text = read(path)
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text)
            for name in ("catalogs", "catalog", "pcman_catalogs", "path", "repo", "directory"):
                self.assertNotIn("<key>%s</key>" % name, text)

    def test_no_value_of_a_recipe_is_a_path_or_a_catalog(self):
        for path in (DOWNLOAD, PCMAN):
            recipe = load(path)
            values = list(recipe["Input"].values())
            for step in recipe["Process"]:
                values.extend(step.get("Arguments", {}).values())
            for value in values:
                if not isinstance(value, str) or value.startswith("https://"):
                    continue
                with self.subTest(path=os.path.basename(path), value=value):
                    self.assertFalse(value.startswith(("/", "~", ".")), value)
                    self.assertNotIn("\\", value)
                    self.assertNotIn("Production", value)
                    self.assertNotIn("Testing", value)

    def test_no_file_name_of_ours_is_the_name_of_a_recipe_in_another_repository(self):
        ours = [name[: -len(".recipe")].casefold() for name in (os.path.basename(DOWNLOAD), os.path.basename(PCMAN))]
        # The download recipe's own name is on the list as a guard against a future clash:
        # it is the one name that is ours.
        others = [other.casefold() for other in NAMES_OF_OTHER_REPOSITORIES
                  if other != "AdobeReader-Win.download"]
        for name in ours:
            self.assertNotIn(name, others)


class NotVerifiedTests(unittest.TestCase):
    """The download has no hard check. The recipes must say so in their first sentence."""

    def test_the_description_of_both_recipes_begins_by_saying_that_nothing_is_verified(self):
        for path in (DOWNLOAD, PCMAN):
            with self.subTest(path=os.path.basename(path)):
                sentence = first_sentence(load(path)["Description"])
                self.assertIn("NOT verified yet", sentence)

    def test_the_download_description_names_the_two_missing_checks(self):
        sentence = first_sentence(load(DOWNLOAD)["Description"])
        self.assertIn("no hash", sentence)
        self.assertIn("signature", sentence)

    def test_the_download_description_says_what_the_recipe_does_and_that_it_was_not_run(self):
        text = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        for needle in ("AdobeReaderInfoProvider", "WindowsExeVersion", "the 32-bit installer",
                       "replaces the version of the products file", "read on 2026-10-02",
                       "NOT run with AutoPkg"):
            self.assertIn(needle, text)
        self.assertNotRegex(text, r"(?i)\brehearsed\b")

    def test_the_pcman_description_names_what_is_not_established_and_the_dry_run(self):
        text = re.sub(r"\s+", " ", load(PCMAN)["Description"])
        self.assertIn("EXE", text)
        self.assertIn("the version that the installer file itself carries", text)
        self.assertIn("not the version of Adobe's products file", text)
        self.assertIn("must agree as a person reads them", text)
        self.assertIn("same product for an EXE was NOT established", text)
        self.assertIn("pcman_dry_run", text)
        self.assertIn("dry run", text)
        self.assertNotRegex(text, r"(?i)\brehearsed\b")
        self.assertNotIn("upgrade code", text)  # that check is for an MSI

    def test_the_descriptions_say_that_a_real_run_is_refused_unless_the_override_allows_it(self):
        for path in (DOWNLOAD, PCMAN):
            text = re.sub(r"\s+", " ", load(path)["Description"])
            with self.subTest(path=os.path.basename(path)):
                self.assertIn("refuses a real run" if path == DOWNLOAD else "A real run is refused", text)
                self.assertIn("pcman_allow_unverified", text)
                self.assertIn("true", text)

    def test_no_recipe_sets_the_allowance_or_a_verified_flag_itself(self):
        for path in (DOWNLOAD, PCMAN):
            text = read(path)
            self.assertNotIn("<key>pcman_allow_unverified</key>", text)
            self.assertNotIn("checksum_verified", text)
            self.assertNotIn("signature_verified", text)

    def test_the_importer_would_refuse_a_real_run_of_this_chain(self):
        """The download recipe has no step that sets a verified flag, so the
        shared importer refuses a real run: read here from the steps."""
        setters = {"ChecksumVerifier": "checksum_verified"}
        names = [step["Processor"].rsplit("/", 1)[-1] for step in load(DOWNLOAD)["Process"] + load(PCMAN)["Process"]]
        self.assertFalse(set(names) & set(setters))
        # Nor does the provider or the version step declare such an output.
        classes = processor_classes()
        for name in (OWN_PROCESSOR, "WindowsExeVersion"):
            self.assertFalse({"checksum_verified", "checksum_sha256"} & set(classes[name].output_variables))

    def test_no_recipe_invents_a_checksum_step(self):
        for path in (DOWNLOAD, PCMAN):
            text = read(path)
            self.assertNotIn("ChecksumVerifier", text)
            self.assertNotIn("GitHubAssetDigest", text)
            self.assertNotIn("expected_sha256", text)
            self.assertNotIn("sha256", text.lower())
            self.assertIsNone(HEX_64.search(text))
            self.assertNotIn("CodeSignatureVerifier", text)
        self.assertNotIn("expected_sha256", own.AdobeReaderInfoProvider.output_variables)

    def test_the_readme_opens_with_a_bold_status_line(self):
        lines = [line for line in read(README).splitlines() if line.strip()]
        self.assertTrue(lines[0].startswith("# "))
        self.assertTrue(lines[1].startswith("A Windows recipe pair"))
        status = lines[2]
        self.assertTrue(status.startswith("**Status. Run on 2026-10-04 under AutoPkg 2.9.0, as follows."), status[:60])
        self.assertTrue(status.endswith("**"))
        for needle in ("The download is NOT verified", "the shared signature check (`AuthenticodeVerifier`) is not part of this recipe", "REFUSES a real run",
                       "pcman_allow_unverified", "Do not set it before a signature check is part of this recipe",
                       "pcman import <file> --template adobereader --version <the label>",
                       "No run of this recipe has published anything, and none can while the download is unverified",
                       "nothing has been installed on a PC"):
            self.assertIn(needle, status)
        self.assertNotIn("has NOT been run by anyone", status)

    def test_the_readme_says_what_still_protects_and_that_it_is_not_enough(self):
        text = re.sub(r"\s+", " ", read(README))
        self.assertIn("**The label.**", text)
        self.assertIn("**The same product.**", text)
        self.assertIn("Whether it has an equivalent check for an EXE was NOT established by the writer", text)
        self.assertIn("What remains does not replace a verification", text)
        self.assertIn("a real run is refused before the package tool starts", text)

    def test_the_real_run_step_says_not_yet(self):
        text = read(README)
        self.assertIn("## d. Switch a real run on (NOT YET: see the status line)", text)
        self.assertLess(text.index("**Status."), text.index("## a."))

    def test_the_hand_command_uses_the_template_and_the_label(self):
        """After the template exists, `pcman import` without --template would make a second item.
        An EXE needs the label."""
        text = read(README)
        match = re.search(r"\n    (pcman import <the file> --template adobereader[^\n]*)\n", text)
        self.assertTrue(match)
        self.assertIn("--version <the label>", match.group(1))
        self.assertNotIn("--name", match.group(1))
        self.assertNotIn("--build", match.group(1))
        self.assertIn("it makes no second item", re.sub(r"\s+", " ", text))
        # the only `pcman import` with --name is the first import of step a.3
        first_imports = [m for m in re.finditer(r"pcman import [^`]*?--name", text)]
        self.assertEqual(len(first_imports), 1)
        self.assertLess(first_imports[0].start(), text.index("## b."))

    def test_the_override_lines_that_allow_an_unverified_run_are_two_and_marked(self):
        text = read(README)
        self.assertIn("Add :Input:pcman_dry_run bool false", text)
        self.assertIn("Add :Input:pcman_allow_unverified bool true", text)
        self.assertIn("Both lines are needed", text)
        import PcmanImporter
        refusal = "The download was not verified: %s. Nothing was published." % PcmanImporter.UNVERIFIED_REASON
        self.assertIn(refusal, re.sub(r"\s+", " ", text))
        self.assertIn("published, NOT verified", text)
        self.assertIn("published WITHOUT a verified download", text)


class ProcessorTests(unittest.TestCase):
    def test_every_named_processor_exists(self):
        for path in (DOWNLOAD, PCMAN):
            for step in load(path)["Process"]:
                name = step["Processor"]
                if name.startswith(SHARED_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, name[len(SHARED_PREFIX):] + ".py")), name)
                elif name.startswith(PCMAN_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(PCMAN_DIR, name[len(PCMAN_PREFIX):] + ".py")), name)
                elif name not in CORE_PROCESSORS:
                    self.assertTrue(os.path.isfile(os.path.join(RECIPE_DIR, name + ".py")), name)

    def test_the_own_processor_has_no_prefix_and_a_class_of_the_same_name(self):
        text = read(os.path.join(RECIPE_DIR, OWN_PROCESSOR + ".py"))
        self.assertIn("class %s(Processor):" % OWN_PROCESSOR, text)

    def test_the_stub_identifier_is_the_prefix_of_the_processor_names(self):
        stub = load(os.path.join(SHARED_DIR, "SharedProcessors.recipe"))
        self.assertEqual(stub["Identifier"] + "/", SHARED_PREFIX)
        self.assertIn("/WindowsExeVersion", stub["Description"])

    def test_every_argument_is_a_declared_input(self):
        classes = processor_classes()
        for path in (DOWNLOAD, PCMAN):
            for name, args in named_steps(load(path)):
                for key in args:
                    with self.subTest(recipe=os.path.basename(path), processor=name, argument=key):
                        self.assertIn(key, classes[name].input_variables)

    def test_every_required_input_is_passed_or_comes_from_the_machine(self):
        classes = processor_classes()
        for path in (DOWNLOAD, PCMAN):
            for name, args in named_steps(load(path)):
                for key, flags in classes[name].input_variables.items():
                    if not flags.get("required") or "default" in flags:
                        continue
                    with self.subTest(recipe=os.path.basename(path), processor=name, input=key):
                        if key in SUPPLIED_BY_THE_MACHINE.get(name, ()):
                            self.assertNotIn(key, args)
                        else:
                            self.assertIn(key, args)

    def test_every_input_of_the_own_processor_has_the_flags_that_autopkg_reads(self):
        for name, flags in own.AdobeReaderInfoProvider.input_variables.items():
            self.assertIn("required", flags, name)
            self.assertIn("description", flags, name)


class HygieneTests(unittest.TestCase):
    def files(self):
        for folder, dirs, files in os.walk(RECIPE_DIR):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if not name.endswith(".pyc"):
                    yield os.path.join(folder, name)

    def test_no_file_holds_a_value_that_belongs_to_one_site(self):
        for path in self.files():
            if os.path.basename(path) == "test_recipes.py":
                continue  # this file names the inputs that must not appear
            text = read(path)
            for kind, pattern in shared_hygiene.FORBIDDEN_PATTERNS.items():
                with self.subTest(file=os.path.relpath(path, RECIPE_DIR), kind=kind):
                    self.assertIsNone(pattern.search(text))

    def test_nothing_deeper_than_the_tests_folder(self):
        for path in self.files():
            self.assertLessEqual(len(os.path.relpath(path, RECIPE_DIR).split(os.sep)), 2, path)

    def test_the_folder_holds_only_what_is_expected(self):
        names = sorted(os.path.relpath(path, RECIPE_DIR) for path in self.files())
        self.assertEqual(names, sorted([
            "AdobeReader-Win.download.recipe", "AdobeReader.cimian.recipe", "AdobeReader.pcman.recipe", "AdobeReaderInfoProvider.py",
            "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
            os.path.join("tests", "test_info_provider.py"),
            os.path.join("tests", "adobe_products_excerpt.json"),
        ]))

    def test_the_hand_written_excerpt_is_small(self):
        self.assertLess(os.path.getsize(EXCERPT), 2000)

    def test_no_recipe_no_readme_and_no_provider_holds_a_hash(self):
        for path in (DOWNLOAD, PCMAN, README, os.path.join(RECIPE_DIR, OWN_PROCESSOR + ".py")):
            with self.subTest(path=os.path.basename(path)):
                self.assertIsNone(HEX_64.search(read(path)))


class ReadmeTests(unittest.TestCase):
    """The README must not teach what the rehearsal of 7-Zip showed to be wrong."""

    def setUp(self):
        self.raw = read(README)
        self.text = re.sub(r"\s+", " ", self.raw)

    def test_every_make_override_command_names_an_override_folder(self):
        commands = list(re.finditer(r"autopkg make-override([^`\n]*(?:\n[ \t]+--[^\n`]*)?)", self.raw))
        self.assertTrue(commands)
        for match in commands:
            self.assertIn("--override-dir=", match.group(1))
            self.assertRegex(match.group(1), r"AdobeReader\.(?:cimian|pcman)")

    def test_no_run_of_a_recipe_identifier(self):
        runs = list(re.finditer(r"autopkg run([^`\n]*)", self.raw))
        self.assertTrue(runs)
        for match in runs:
            self.assertNotIn("com.github.", match.group(1))

    def operator_commands(self):
        """The lines of an operator step that run autopkg: indented four spaces or more."""
        pattern = re.compile(r"^ {4,}(autopkg (?:run|verify-trust-info|update-trust-info)\b.*)$", re.M)
        return [match.group(1) for match in pattern.finditer(self.raw)]

    def test_every_run_and_every_trust_command_carries_the_override_dir_and_the_path(self):
        """An override outside AutoPkg's configured override folders loses its trust check
        unless the folder is named on the command line (AutoPkg 2.9.0)."""
        commands = self.operator_commands()
        self.assertEqual(len([c for c in commands if c.startswith("autopkg run")]), 6)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg verify-trust-info")]), 4)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg update-trust-info")]), 2)
        for command in commands:
            with self.subTest(command=command):
                self.assertRegex(
                    command,
                    r"^autopkg (run|verify-trust-info|update-trust-info)( -vv?)? "
                    r"--override-dir=<the Windows overrides folder> "
                    r"<the Windows overrides folder>/AdobeReader\.(?:cimian|pcman)\.recipe$",
                )

    def test_no_autopkg_command_line_is_missed_by_the_indent_rule(self):
        """Every line that begins with an autopkg command is one of the lines checked
        above, and `autopkg run ` occurs three times in the whole file."""
        pattern = r"^[ \t]*autopkg (?:run|verify-trust-info|update-trust-info)\b"
        at_line_start = re.findall(pattern, self.raw, re.M)
        self.assertEqual(len(at_line_start), len(self.operator_commands()))
        self.assertEqual(len(re.findall(r"autopkg run ", self.raw)), 6)

    def test_no_prose_line_shows_a_full_command_without_the_option(self):
        for match in re.finditer(r"`(autopkg (?:run|verify-trust-info|update-trust-info)[^`]*<[^`]*)`", self.raw):
            self.assertIn("--override-dir=", match.group(1))

    def test_a_bold_paragraph_says_why_and_what_to_do_when_the_warning_appears(self):
        self.assertIn("## Run every override with `--override-dir`", self.raw)
        i = self.raw.index("## Run every override with `--override-dir`")
        paragraph = re.sub(r"\s+", " ", self.raw[i:i + 2500])
        for needle in ("**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`",
                       "skips the trust check with one warning line", "is missing trust info",
                       "a changed processor is not caught",
                       "If that line ever appears in a run of an override, stop: the run was not checked.**",
                       "`FAIL_RECIPES_WITHOUT_TRUST_INFO`", "not set on the build machine today",
                       "change how the Mac recipes run", "owner's decision"):
            self.assertIn(needle, paragraph)
        self.assertLess(i, self.raw.index("## a."))

    def test_the_sections_a_to_g_are_there_in_order(self):
        positions = [self.raw.index(heading) for heading in (
            "## a. What must exist first", "## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER",
            "## c. First try: a dry run", "## d. Switch a real run on", "## e. The real run, the catalogs, the second run",
            "## f. When a recipe or a processor changes upstream", "## g. A share that is not mounted")]
        self.assertEqual(positions, sorted(positions))

    def test_the_steps_of_the_model_folders_are_there(self):
        for needle in ("pcman catalogs", "pcman versions adobereader", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string", "make-override"):
            self.assertIn(needle, self.text)

    def test_the_readme_says_that_the_label_is_the_wrappers_version_and_nothing_compares_it(self):
        heading = "## The label is the wrapper's version, and nothing compares it with the product's"
        self.assertIn(heading, self.raw)
        start = self.text.index(heading)
        section = self.text[start:self.text.index("## Run every override")]
        for needle in ("Adobe's self-extracting wrapper", "`Adobe Self Extractor`",
                       "No step of this recipe compares the two",
                       "the version that the installed Reader shows has not been read by anyone",
                       "would still publish under the wrapper's number",
                       "that number orders the versions in the repository",
                       "does not check this at any run", "A person checks it, at the first dry run",
                       "with `-v`", "`26.002.21931` and `26.2.21931.0`", "the same three numbers (26, 2 and 21931)",
                       "If the three numbers differ, stop and tell the owner before anything is published",
                       "After the first install on a test PC", "NOT established"):
            self.assertIn(needle, section)
        self.assertLess(self.raw.index(heading), self.raw.index("## a."))
        step = self.raw[self.raw.index("## c."):self.raw.index("## d.")]
        self.assertIn("autopkg run -v --override-dir=", step)

    def test_the_readme_states_no_hash(self):
        """A README that states a SHA-256 (64 hex digits) could be taken for a check."""
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.raw))

    def test_the_first_import_names_the_template_the_label_and_the_flags_of_the_package_tool(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        self.assertTrue(match)
        command = re.sub(r"\s+", " ", match.group(1))
        self.assertIn("--name adobereader", command)
        self.assertIn("--version <the label that the first dry run prints>", command)  # an EXE has a label
        for flag in ("--display-name", "--category", "--developer", "--description", "--install-arguments",
                     "--architectures", "--no-prompt", "--directory", "--icon"):
            self.assertIn(flag, command)
        # The form that ran on 2026-10-04: the switch and the architectures were read in the vendor's
        # documentation and in the PE header; the install path was NOT given.
        self.assertIn("--install-arguments '/sAll /rs /msi EULA_ACCEPT=YES'", command)
        self.assertIn("--architectures x86,x64", command)
        self.assertNotIn("--install-path", command)
        step = re.sub(r"\s+", " ", self.raw[self.raw.index("3. **The template item"):self.raw.index("## b.")])
        for needle in ("in the form that ran on 2026-10-04", "**used on 2026-10-04, not tested on a PC**",
                       "from Adobe's documentation for administrators", "the string `/sAll` is in the file",
                       "`--install-path` was left out because the path must be read on a PC after an install",
                       "the template then has no install check", "an item of the kind `choco` is not the template"):
            self.assertIn(needle, step)

    def test_the_status_line_says_what_was_fetched_and_what_was_not(self):
        """This folder was NOT run with AutoPkg. The writer fetched some facts of the source on
        2026-10-02: the README opens with a bold paragraph that lists what was verified and
        what is still not."""
        opening = "**Status. Run on 2026-10-04 under AutoPkg 2.9.0, as follows."
        start = self.raw.index(opening)
        self.assertLess(start, self.raw.index("| Recipe |"))
        self.assertLess(self.raw.index("# Win-AdobeReader"), start)
        end = self.raw.index("**\n", start)
        paragraph = re.sub(r"\s+", " ", self.raw[start:end + 2])
        self.assertTrue(paragraph.startswith(opening))
        self.assertTrue(paragraph.endswith("**"))
        ran, _, fetched = paragraph.partition("Facts of the source that the writer fetched on 2026-10-02, before those runs:")
        self.assertTrue(fetched)
        verified, _, rest = fetched.partition("NOT established:")
        self.assertTrue(rest)
        not_established, _, after = rest.partition("The download is NOT verified")
        self.assertTrue(after)
        for needle in ("an earlier HEAD request got 403, a GET answers 200",
                       "https://rdc.adobe.io/reader/products?lang=en&platformArch=64&site=landing"
                       "&os=Windows%2010&preInstalled=&country=US&nativeOs=Windows%2010"
                       "&api_key=dc-get-adobereader-cdn",
                       "answered 200 with a JSON object", "`products.reader` is a list of one element",
                       "`Reader 2026.002.21931 English for Windows (Recommended)`", "`fileSize` 748.0",
                       "`version` `26.002.21931`", "`products.dcPro` and `addons`", "are not used",
                       "the packed version `2600221931`",
                       "https://ardownload2.adobe.com/pub/adobe/reader/win/AcrobatDC/2600221931/AcroRdrDC2600221931_en_US.exe",
                       "(643995232 bytes)", "AcroRdrDC2600221931_MUI.exe", "(739174432 bytes)", "answered 200",
                       "`x64` (`AcroRdrDCx64...`) answered 404",
                       "the real file `AcroRdrDC2600221931_en_US.exe` (643995232 bytes) was downloaded, with no browser identity",
                       "read with `WindowsExeVersion`", "its ProductVersion is `26.2.21931.0`",
                       "the FileVersion and the numbers of the fixed file information are the same",
                       "the label `version` is `26.2.21931.0`", "its ProductName is `Adobe Self Extractor`",
                       "the outer self-extracting wrapper and not `Adobe Acrobat Reader`",
                       "a check of the product name would mislead",
                       "`26.002.21931` and the file's `26.2.21931.0` are one version by their numbers (26, 2 and 21931)",
                       "the middle part of the products file written with leading zeros"):
            self.assertIn(needle, verified)
        for needle in ("that the products file is stable", "the fixed public key",
                       "that the installer scheme, seen for one version, holds for the next",
                       "whether Adobe offers an installer for x64 under another scheme",
                       "the 32-bit installers", "the silent switch on a PC, the install path and an install check",
                       "the version text that the installed Reader shows after the wrapper has installed it",
                       "that the next release keeps this spelling", "any install on a PC"):
            self.assertIn(needle, not_established)
        for needle in ("the template item `adobereader` exists", "any run with AutoPkg"):
            self.assertNotIn(needle, not_established)
        # What the real file settled is no longer listed as unknown.
        self.assertNotIn("what ProductVersion the installer file carries", not_established)
        self.assertNotIn("leading zeros (`002`)", not_established)
        for needle in ("wrote by hand after the real answer of 2026-10-02",
                       "The first install on a test PC is the check of what is NOT established",
                       "STOP: nothing was written", "correct the processor or the recipe",
                       "and only then look at the trust information",
                       "Never accept new trust information first",
                       "Every override command here carries `--override-dir`"):
            self.assertIn(needle, paragraph)
        self.assertNotRegex(self.text, r"Rehearsed on 20")
        self.assertNotRegex(self.text, r"(?i)\bwas rehearsed\b")
        self.assertNotIn("the network was closed", self.text)
        self.assertIsNone(HEX_64.search(paragraph))

    def test_the_readme_does_not_claim_what_it_did_not_do(self):
        for needle in ("Expected, from the code and the rehearsals of the other folders, NOT printed by this recipe yet",
                       "(Not run: the lines of the output are not known.)",
                       "Expected (not run)"):
            self.assertIn(needle, self.text)
        self.assertNotIn("The rehearsal printed", self.text)
        self.assertNotRegex(self.text, r"(?<!NOT )(?i:rehearsed with)")

    def test_the_readme_says_how_the_label_is_made_and_that_both_versions_are_compared(self):
        for needle in ("`WindowsExeVersion`", "the label for the package tool is the file's own, not the products file's",
                       "**Read the two versions and compare them.**", "`version is <the label>, taken from <where>`",
                       "They are not written in the same way",
                       "so nothing here checks the product name",
                       "the installer file carries `26.2.21931.0` as its ProductVersion (read on 2026-10-02)",
                       "The version that the installed Reader shows is NOT established",
                       "If they do not agree by their numbers, stop and tell the owner"):
            self.assertIn(needle, self.text)

    def test_the_readme_says_what_to_do_when_the_address_scheme_or_the_endpoint_changes(self):
        for needle in ("If the line says that the address answered with a redirect, stop and tell the owner",
                       "the scheme of the addresses has changed", "begins `Adobe's products file`"):
            self.assertIn(needle, self.text)

    def test_the_name_check_and_the_parent_check_are_in_step_b(self):
        b = self.raw.index("## b.")
        c = self.raw.index("## c.")
        step = self.raw[b:c]
        self.assertIn("autopkg list-recipes | grep -i AdobeReader-Win", step)
        self.assertIn("autopkg list-recipes | grep -i AdobeReader.pcman", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.AdobeReader`",
                      re.sub(r"\s+", " ", step))
        self.assertIn("`AdobeReaderInfoProvider`, `WindowsExeVersion`, `PcmanImporter`", re.sub(r"\s+", " ", step))
        self.assertLess(step.index("autopkg list-recipes"), step.index("    autopkg make-override --override-dir="))

    def test_the_readme_names_the_input_and_the_two_installers(self):
        for needle in ("`ADOBE_LANGUAGE` (default `en_US`, English; `MUI`", "`pcman_timeout`",
                       "`AcroRdrDC<packed>_<language>.exe`", "about 640 MB (`en_US`) or 740 MB (`MUI`)"):
            self.assertIn(needle, self.text)


class ChainTests(_pcman_support.ToolTestCase):
    """The chain of this program, with the real processors and a small PE file that stands for
    the installer: the label that reaches the package tool is the file's, and a real run is
    refused because nothing verified the download. The stand-in package tool is used."""

    def setUp(self):
        super().setUp()
        info = version_info(product=FILE_LABEL, file=FILE_LABEL, name=FILE_PRODUCT_NAME,
                            file_numbers=FILE_LABEL_NUMBERS, product_numbers=FILE_LABEL_NUMBERS)
        self.installer = os.path.join(self.downloads, "AcroRdrDC2600221931_en_US.exe")
        with open(self.installer, "wb") as handle:
            handle.write(bytes(build_pe(info).data))

    def run_download_steps(self):
        """What the steps of the download recipe leave in the run: the provider
        (on the hand-written excerpt), then the version step on the file."""
        from unittest import mock
        with mock.patch.object(own, "fetch_text", return_value=read(EXCERPT)):
            provider, _ = _win_support.run_processor(own.AdobeReaderInfoProvider, {})
        run = {"pathname": self.installer, "version": provider.env["version"], "url": provider.env["url"]}
        step = [s for s in load(DOWNLOAD)["Process"] if s["Processor"].endswith("/WindowsExeVersion")][0]
        values = {"%pathname%": self.installer}
        run_env = dict(run)
        run_env.update({k: values.get(v, v) for k, v in step["Arguments"].items()})
        version_step, _ = _win_support.run_processor(_win_support.exe_version.WindowsExeVersion, run_env)
        return provider, version_step

    def importer_env(self, run_env, dry_run):
        if dry_run:
            self.behave(result=_pcman_support.result_file_content(
                "dry-run", name="adobereader", version=run_env["version"]))
        values = {"%pathname%": self.installer, "%PCMAN_TEMPLATE%": load(PCMAN)["Input"]["PCMAN_TEMPLATE"],
                  "%version%": run_env["version"]}
        env = {"pathname": self.installer, "pcman_root": self.root, "pcman_dry_run": dry_run,
               "pcman_path": self.msi_bin}
        steps = [step for step in load(PCMAN)["Process"] if step["Processor"].endswith("/PcmanImporter")]
        self.assertEqual(len(steps), 1)
        for name, value in steps[0]["Arguments"].items():
            env[name] = values.get(value, value)
        return env

    def test_the_label_is_the_files_and_not_the_products_files(self):
        provider, version_step = self.run_download_steps()
        self.assertEqual(provider.env["version"], "26.002.21931")
        self.assertEqual(version_step.env["version"], FILE_LABEL)
        self.assertNotEqual(version_step.env["version"], provider.env["version"])
        self.assertEqual(version_step.env["exe_product_version"], FILE_LABEL)
        self.assertEqual(version_step.env["exe_product_name"], FILE_PRODUCT_NAME)
        self.assertNotIn("Reader", version_step.env["exe_product_name"])  # a check on the name would mislead
        # the url of the provider is the one the downloader would take, and it is not changed
        self.assertEqual(version_step.env["url"], provider.env["url"])

    def test_the_package_tool_is_given_the_files_label_in_a_dry_run_that_says_not_verified(self):
        _, version_step = self.run_download_steps()
        env = self.importer_env(version_step.env, dry_run=True)
        self.assertEqual(env["pcman_version"], FILE_LABEL)
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        argv = self.record()["argv"]
        self.assertIn("--version", argv)
        self.assertEqual(argv[argv.index("--version") + 1], FILE_LABEL)
        self.assertIn("--dry-run", argv)
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"],
                         "dry run, nothing written, NOT verified")
        warnings = [m for level, m in processor.message_levels if m.startswith("WARNING:")]
        self.assertTrue(any("NOT verified" in m or "was NOT verified" in m for m in warnings), warnings)

    def test_a_real_run_is_refused_and_the_package_tool_is_not_started(self):
        _, version_step = self.run_download_steps()
        env = self.importer_env(version_step.env, dry_run=False)
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        self.assertIn("The download was not verified", str(caught.exception))
        self.assertIn("pcman_allow_unverified", str(caught.exception))
        self.assertFalse(self.was_run())

    def test_the_file_name_is_one_that_the_importer_accepts(self):
        self.assertTrue(self.installer.endswith(".exe"))
        _, version_step = self.run_download_steps()
        env = self.importer_env(version_step.env, dry_run=True)
        _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        self.assertTrue(self.was_run())


def _text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class RealRunReadmeTests(unittest.TestCase):
    """What the README says of the first import and the real run of 2026-10-04 (AutoPkg 2.9.0)."""

    def setUp(self):
        self.raw = read(README)
        self.text = re.sub(r"\s+", " ", self.raw)
        self.status = re.sub(r"\s+", " ", [line for line in self.raw.splitlines() if line.startswith("**Status.")][0])

    def test_the_status_line_says_what_ran_and_what_the_refusal_was(self):
        for needle in ("The first import (the command of step a.3 below, run with `--no-prompt` and `--build`) made the template "
                       "`adobereader` (an EXE item, label `26.2.21931.0`, architectures `x86,x64`)",
                       "`make-override` with `--override-dir`, `ParentRecipe` right, `verify-trust-info` OK, `pcman_dry_run` false",
                       "the importer REFUSED the run with `The download was not verified:", "(exit 70)",
                       "`pcman_allow_unverified` was not set",
                       "The override downloaded the file again about ten minutes after the first import, and its hash was the imported file's",
                       "`Nothing new: adobereader <label> exists already ...` with exit 3",
                       "`pcman catalogs` ran once for all the new items together (2026-10-04)",
                       "`All` and `Production`, 106 items each"):
            self.assertIn(needle, self.status)

    def test_what_is_not_established_is_still_said(self):
        for needle in ("was NOT tested on a PC", "has NO install check until a person adds one",
                       "Still NOT established after those runs: that the switch installs silently on a PC; an install check; any install"):
            self.assertIn(needle, self.status)

    def test_nothing_untested_is_called_established(self):
        for claim in ("the switch is established", "installs silently on a PC (tested)", "was tested on a PC"):
            self.assertNotIn(claim, self.text)

    def test_the_chocolatey_item_is_said_to_remain_for_a_person_to_remove(self):
        self.assertIn("went beside the Chocolatey item `adobereader` (version 1.0) without any option of the tool", self.status)
        self.assertIn("the Chocolatey item file and its `adobereader-1.0` pkginfo remain until a person removes them by hand", self.status)
        self.assertIn("`pcman validate` warns that the item has two versions until then", self.status)

    def test_the_second_run_line_is_not_promised_for_a_fresh_override(self):
        self.assertIn("the first run of a fresh override printed the line `Nothing new: ...` after it had downloaded the file again", self.text)
        self.assertIn("a new override gets a new cache folder", self.text)


class FlagNameTests(unittest.TestCase):
    """The cimian recipe's flag for an unverified download is `cimian_allow_unverified`; `pcman_allow_unverified` is the package tool's."""

    def test_the_download_description_names_the_flag_of_each_recipe_correctly(self):
        text = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        self.assertIn("refuses a real run of the cimian recipe unless the override sets cimian_allow_unverified to true "
                      "(pcman_allow_unverified for the package tool's recipe)", text)
        self.assertNotIn("of the cimian recipe unless the override sets pcman_allow_unverified", text)


class CimianRecipeTests(unittest.TestCase):
    """The recipe for any Cimian repository: its only step is CimianImporter, and nothing of the
    package tool is in it. The package tool's recipe is the old recipe under its new name."""

    def test_the_three_recipes_are_property_lists_with_the_keys_that_autopkg_reads(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            with self.subTest(path=os.path.basename(path)):
                result = subprocess.run(["plutil", "-lint", path], capture_output=True, text=True) \
                    if os.path.exists("/usr/bin/plutil") else None
                if result is not None:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                recipe = load(path)
                for key in ("Description", "Identifier", "Input", "MinimumVersion", "Process"):
                    self.assertIn(key, recipe)

    def test_identifiers_and_parents(self):
        download, cimian, pcman = load(DOWNLOAD), load(CIMIAN), load(PCMAN)
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.AdobeReader")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.AdobeReader")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotEqual(cimian["Identifier"], pcman["Identifier"])
        self.assertEqual(cimian["MinimumVersion"], pcman["MinimumVersion"])
        self.assertTrue(CIMIAN.endswith("AdobeReader.cimian.recipe"))
        self.assertTrue(PCMAN.endswith("AdobeReader.pcman.recipe"))

    def test_the_only_step_is_the_cimian_importer(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "CimianImporter"])

    def test_the_inputs_and_the_arguments(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], load(PCMAN)["Input"]["NAME"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], load(PCMAN)["Input"]["PCMAN_TEMPLATE"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], "adobereader")
        self.assertEqual(recipe["Input"]["CIMIAN_SUBDIRECTORY"], "")
        self.assertEqual(sorted(recipe["Input"]), ["CIMIAN_NAME", "CIMIAN_SUBDIRECTORY", "NAME", "pkginfo"])
        self.assertEqual(recipe["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": "%version%"})

    def test_the_pkginfo_gives_only_what_the_readme_states(self):
        self.assertEqual(load(CIMIAN)["Input"]["pkginfo"], {'display_name': 'Adobe Acrobat Reader', 'developer': 'Adobe'})

    def test_the_version_argument_is_the_exes_label_or_empty_for_an_msi(self):
        argument = load(CIMIAN)["Process"][0]["Arguments"]["version"]
        if "exe" == "exe":
            self.assertEqual(argument, "%version%")
        else:
            self.assertEqual(argument, "")  # the MSI's own ProductVersion, not a tag that an earlier step set

    def test_the_package_tool_recipe_is_the_old_recipe_with_the_new_processor_name(self):
        recipe = load(PCMAN)
        steps = [step["Processor"] for step in recipe["Process"]]
        self.assertEqual(steps, [PCMAN_PREFIX + "PcmanImporter"])
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "adobereader")
        arguments = recipe["Process"][0]["Arguments"]
        self.assertEqual(arguments["pathname"], "%pathname%")
        self.assertEqual(arguments["pcman_template"], "%PCMAN_TEMPLATE%")
        self.assertEqual("pcman_version" in arguments, "exe" == "exe")

    def test_nothing_of_the_package_tool_is_in_the_cimian_recipe(self):
        text = _text(CIMIAN).lower()
        for word in ("pcman", "package tool", "template item"):
            self.assertNotIn(word, text)

    def test_every_argument_is_a_declared_input_and_every_required_input_is_given(self):
        declared = _win_support.cimian.CimianImporter.input_variables
        arguments = load(CIMIAN)["Process"][0]["Arguments"]
        for key in arguments:
            self.assertIn(key, declared)
        for key, flags in declared.items():
            if flags.get("required") and "default" not in flags:
                self.assertIn(key, arguments)

    def test_what_the_machine_decides_is_not_in_the_cimian_recipe(self):
        text = _text(CIMIAN)
        for name in ("cimian_repo", "cimian_dry_run", "cimian_allow_unverified", "cimian_path", "cimian_catalogs",
                     "msi_product_code", "msi_upgrade_code", "checksum_verified", "checksum_sha256", "CIMIAN_REPO"):
            self.assertNotIn("<key>%s</key>" % name, text)

    def test_no_stop_on_an_unchanged_download_and_no_latest_only_and_no_blocking_applications(self):
        text = _text(CIMIAN)
        for word in ("StopProcessingIf", "latest_only", "blocking_applications"):
            self.assertNotIn(word, text)

    def test_no_value_of_the_cimian_recipe_is_a_path_a_catalog_or_a_hash(self):
        recipe = load(CIMIAN)
        values = [value for value in recipe["Input"].values() if isinstance(value, str)]
        values.extend(value for value in recipe["Process"][0]["Arguments"].values() if isinstance(value, str))
        for value in values:
            self.assertFalse(value.startswith(("/", "~", ".")), value)
            self.assertNotIn("Production", value)
            self.assertNotIn("Testing", value)
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", _text(CIMIAN)))

    def test_the_description_says_what_a_reader_must_know(self):
        description = load(CIMIAN)["Description"]
        for needle in ("CimianImporter", "dry run", "cimian_dry_run", "CIMIAN_REPO", "says that nothing is new"):
            self.assertIn(needle, description)
        self.assertNotIn("pcman", description)
        self.assertNotIn("package tool", description)

    def test_the_description_says_that_another_upgrade_code_is_refused_where_the_old_one_said_so(self):
        description = load(CIMIAN)["Description"]
        if "refuses an MSI whose upgrade code differs from the template's" in load(PCMAN)["Description"]:
            self.assertIn("It refuses an MSI whose upgrade code differs from the template's unless the override sets "
                          "cimian_allow_product_change to true", description)
        self.assertNotIn("warns when an MSI", description)

    def test_the_description_of_an_unverified_download_says_so_first(self):
        description = load(CIMIAN)["Description"]
        if True:
            self.assertTrue(description.startswith("This import is NOT verified yet:"))
            self.assertIn("cimian_allow_unverified", description)
            self.assertIn("published, NOT verified", description)
        else:
            self.assertNotIn("NOT verified yet", description)

    def test_the_cimian_recipe_names_only_the_shared_importer_and_it_is_in_the_shared_folder(self):
        for step in load(CIMIAN)["Process"]:
            self.assertEqual(step["Processor"], SHARED_PREFIX + "CimianImporter")
            self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, "CimianImporter.py")))


class CimianReadmeTests(unittest.TestCase):
    """The README has two ways, in this order: any Cimian repository, then the package tool."""

    def setUp(self):
        self.raw = _text(os.path.join(RECIPE_DIR, "README.md"))
        self.generic = self.raw[self.raw.index("## With any Cimian repository"):self.raw.index("## With the package tool (pcman)")]
        self.tool = self.raw[self.raw.index("## With the package tool (pcman)"):self.raw.index("\n## Tests")]

    @staticmethod
    def commands(text, name):
        return [line.strip() for line in text.splitlines() if re.match(r"^\s*autopkg %s\b" % name, line)]

    def test_the_sections_come_in_this_order(self):
        positions = [self.raw.index(mark) for mark in (
            "## Run every override with `--override-dir`", "## With any Cimian repository",
            "## With the package tool (pcman)", "## a. ", "## g. ", "## Other facts", "## Tests")]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(len(set(positions)), len(positions))

    def test_the_table_has_the_three_recipes(self):
        for name, identifier in (("AdobeReader.cimian.recipe", "com.github.serrc-techops.cimian.AdobeReader"),
                                 ("AdobeReader.pcman.recipe", "com.github.serrc-techops.pcman.AdobeReader")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)
        self.assertIn("`CimianImporter`", [line for line in self.raw.splitlines() if line.startswith("| `AdobeReader.cimian.recipe`")][0])
        self.assertIn("`pcman`", [line for line in self.raw.splitlines() if line.startswith("| `AdobeReader.pcman.recipe`")][0])

    def test_the_generic_way_has_the_same_steps_as_the_package_tools(self):
        self.assertEqual(len(self.commands(self.generic, "run")), 3)
        self.assertEqual(len(self.commands(self.generic, "verify-trust-info")), 2)
        self.assertEqual(len(self.commands(self.generic, "update-trust-info")), 1)
        self.assertEqual(len(self.commands(self.generic, "make-override")), 1)
        self.assertEqual(len(self.commands(self.generic, "repo-add")), 1)
        for heading in ("### 1. What must exist first", "### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER",
                        "### 3. First try: a dry run", "### 5. The real run, the catalogs, the second run",
                        "### 6. When a recipe or a processor changes upstream", "### A share that is not mounted"):
            self.assertIn(heading, self.generic)
        self.assertIn("### 4. Switch a real run on", self.generic)

    def test_every_command_of_each_way_names_its_own_recipe_and_the_override_dir(self):
        for text, recipe, other in ((self.generic, "AdobeReader.cimian", "AdobeReader.pcman"), (self.tool, "AdobeReader.pcman", "AdobeReader.cimian")):
            for name in ("run", "verify-trust-info", "update-trust-info", "make-override"):
                for command in self.commands(text, name):
                    with self.subTest(command=command):
                        self.assertIn("--override-dir=", command)
                        self.assertIn(recipe, command)
                        self.assertNotIn(other, command)
        self.assertEqual(len(self.commands(self.tool, "run")), 3)
        self.assertEqual(len(self.commands(self.tool, "make-override")), 1)

    def test_the_generic_way_runs_an_override_by_path_and_never_a_recipe_identifier(self):
        for command in self.commands(self.generic, "run"):
            self.assertNotIn("com.github.", command)
            self.assertRegex(command, r"--override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader\.cimian\.recipe$")

    def test_the_generic_way_names_nothing_of_the_package_tool_to_run(self):
        for word in ("pcman import", "pcman catalogs", "pcman versions", "pcman_root", "pcman_python", "PCMAN_TEMPLATE", "PcmanImporter"):
            self.assertNotIn(word, self.generic)
        self.assertIn("no package tool", self.generic)

    def test_the_generic_way_gives_the_preference_the_switch_and_the_catalogs(self):
        for needle in ("defaults write com.github.autopkg CIMIAN_REPO -string", "Add :Input:cimian_dry_run bool false",
                       "Cimian's `makecatalogs`", "`CIMIAN_NAME`", "`CIMIAN_SUBDIRECTORY`", "WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on.",
                       "windowsadmins/cimian", "e10498b", "ParentRecipe"):
            self.assertIn(needle, self.generic)
        self.assertNotIn("-k cimian_dry_run=false instead", self.generic.replace("Do not use `-k cimian_dry_run=false` instead", ""))

    def test_the_lines_that_the_generic_way_quotes_are_in_the_processor(self):
        source = _text(os.path.join(SHARED_DIR, "CimianImporter.py"))
        for fragment in ("WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on.", "Would write ", "No template: the pkginfo is built from the inputs.",
                         "Nothing new: ", "Published ", "Build the catalogs with makecatalogs."):
            self.assertIn(fragment, source)
            self.assertIn(fragment.split(". ")[0] if fragment.startswith("WARNING") else fragment.strip(), self.generic.replace("`", ""))

    def test_the_generic_way_says_what_a_person_completes_by_hand(self):
        if "exe" == "exe":
            self.assertIn("What a person completes by hand for an `.exe`", self.generic)
            self.assertIn("an install check", self.generic)
            self.assertIn("StatusService.cs:194-219", self.generic)
            self.assertIn("does NOT give the silent arguments", self.generic)
            self.assertNotIn("installer: {args: [/S]}", self.generic.replace("`installer: {args: [...]}`", ""))
        else:
            self.assertIn("For an `.msi` nothing needs completing for a silent install", self.generic)
            self.assertIn("InstallerService.cs:936-948", self.generic)
            self.assertIn("`msiinfo`", self.generic)
            self.assertIn("This recipe cannot run without it", self.generic)
            self.assertIn("an argument of a step wins over an override's `Input`", self.generic)
            self.assertIn("`cimian_allow_product_change`", self.generic)
            self.assertIn("or that has none where the template's item had one", self.generic)

    def test_the_recipes_pkginfo_does_not_change_a_template_says_the_generic_way(self):
        for needle in ("The recipe's `pkginfo` does not change a template", "a NOTE names each",
                       "`cimian_pkginfo_wins` set to true in the override", "`cimian_architecture`"):
            self.assertIn(needle, self.generic)

    def test_the_parent_recipe_is_the_recipe_the_override_was_made_from(self):
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.cimian.AdobeReader`**", self.generic.replace("\n", " "))
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.AdobeReader`**", self.tool.replace("\n", " "))
        for text in (self.generic, self.tool):
            self.assertNotIn("it must be `com.github.serrc-techops.download.", text.replace("\n", " "))

    def test_an_override_of_the_old_cimian_recipe_is_to_be_made_again_for_the_package_tool(self):
        self.assertIn("An override that was made from the old `AdobeReader.cimian.recipe`", self.tool)
        self.assertIn("must be made again from `AdobeReader.pcman.recipe`", self.tool)
        self.assertIn("An override that was made from this recipe before the recipes were separated", self.generic)

    def test_the_condition_of_never_overwrites_is_said(self):
        self.assertIn("do not run two runs of one item at the same time", self.generic)

    def test_the_generic_way_states_no_hash_and_no_made_up_label(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.generic))
        self.assertNotIn("Published adobereader", self.generic)

    def test_an_unverified_download_is_said_not_yet_in_the_generic_way(self):
        if True:
            self.assertIn("**The download of this program is NOT verified**", self.generic)
            self.assertIn("### 4. Switch a real run on (NOT YET: see the status line)", self.generic)
            self.assertIn("Add :Input:cimian_allow_unverified bool true", self.generic)
            self.assertIn("**Not yet.**", self.generic)
            self.assertLess(self.generic.index("Add :Input:cimian_dry_run bool false"), self.generic.index("Add :Input:cimian_allow_unverified bool true"))
        else:
            self.assertNotIn("cimian_allow_unverified bool true", self.generic)
            self.assertNotIn("NOT verified", self.generic)

    def test_the_package_tools_way_says_the_tool_is_not_in_this_repository(self):
        self.assertIn("**not part of this repository**", self.tool)
        self.assertIn("`PcmanImporter` of `../Win-PcmanProcessors/`", self.tool)
        self.assertIn("AdobeReader.pcman", self.tool)

    def test_the_processors_are_named_in_their_new_folders(self):
        self.assertNotIn("SharedProcessors/PcmanImporter", self.raw)
        self.assertNotIn("PcmanImporter` is in `../Win-SharedProcessors", self.raw)


class CimianChainTests(_win_support.RepoTestCase):
    """The chain of this program with the real CimianImporter and a temporary repository: the steps of the
    download recipe leave their variables in the run, the recipe's own step reads them."""

    VERIFIED = False

    def run_chain(self, installer, tag="9.9.9", label="1.2.3", **extra):
        """What the recipe's step is given, with the substitutions that AutoPkg makes. `tag` is a version that an
        earlier step of the download recipe may have left in the run (a release tag, say); `label` is what
        WindowsExeVersion leaves in `version` for an .exe."""
        recipe = load(CIMIAN)
        run = {"pathname": installer, "version": label if "exe" == "exe" else tag}
        if self.VERIFIED:
            run["expected_sha256"] = _win_support.sha256_hex(installer)
            verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
            run.update({key: value for key, value in verifier.env.items() if key.startswith("checksum_")})
        run.update(recipe["Input"])
        run["CIMIAN_NAME"] = "Example-Chain"
        arguments = {}
        for name, value in recipe["Process"][0]["Arguments"].items():
            for variable in re.findall(r"%([A-Za-z_]+)%", value):
                value = value.replace("%" + variable + "%", str(run[variable]))
            arguments[name] = value
        env = dict(run)
        env.update({"cimian_repo": self.repo, "cimian_dry_run": False, "cimian_path": self.msi_bin})
        env.update(arguments)
        env.update(extra)
        return _win_support.run_processor(_win_support.cimian.CimianImporter, env)

    def installer(self):
        return self.exe if "exe" == "exe" else self.msi

    @_win_support.needs_yaml
    def test_the_chain_publishes_into_an_empty_repository_as_the_recipes_inputs_say(self):
        if not self.VERIFIED:
            with self.assertRaises(_win_support.ProcessorError):
                self.run_chain(self.installer())
            processor, messages = self.run_chain(self.installer(), cimian_allow_unverified=True)
            self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published, NOT verified")
        else:
            processor, messages = self.run_chain(self.installer())
            self.assertEqual([m for m in messages if m.startswith("WARNING: published WITHOUT")], [])
            self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published")
        new = self.read_pkginfo("Example-Chain-%s.yaml" % processor.env["cimian_version_imported"])
        self.assertEqual(new["name"], "Example-Chain")
        for key, value in load(CIMIAN)["Input"]["pkginfo"].items():
            if isinstance(value, dict):
                for inner, expected in value.items():
                    self.assertEqual(new[key][inner], expected)
            else:
                self.assertEqual(new[key], value)
        self.assertEqual(new["installer"]["type"], "exe")
        self.assertEqual(new["installer"]["hash"], _win_support.sha256_hex(self.installer()))

    @_win_support.needs_yaml
    def test_the_version_is_the_label_of_an_exe_and_the_products_own_for_an_msi(self):
        if "exe" == "exe":
            processor, _ = self.run_chain(self.exe, label="1.2.3", cimian_allow_unverified=True)
            self.assertEqual(processor.env["cimian_version_imported"], "1.2.3")
        else:
            self.msiinfo_says(stdout=_win_support.property_export(version="2.5.0"))
            processor, _ = self.run_chain(self.msi, tag="9.9.9", cimian_allow_unverified=True)
            self.assertEqual(processor.env["cimian_version_imported"], "2.5.0")  # not the tag of the run

    @_win_support.needs_yaml
    def test_the_recipes_pkginfo_does_not_change_an_item_that_the_repository_has(self):
        """A template wins over the recipe's own pkginfo: the display name of the recipe does not rename an
        existing item, and the recipe's arguments are not added beside the template's."""
        head = "display_name: Template Name\nversion: 1.0.0\ncatalogs:\n- Production\ninstaller:\n  location: apps/Example-Chain-1.0.0.exe\n"
        if "exe" == "exe":
            body = ("  hash: " + "a" * 64 + "\n  type: exe\n  switches:\n  - /TEMPLATE-SWITCH\n"
                    "check:\n  file:\n    path: C:" + chr(92) + "Example" + chr(92) + "example.exe\n    version: 1.0.0\nname: Example-Chain\n")
        else:
            body = ("  hash: " + "a" * 64 + "\n  type: msi\ninstalls:\n- type: msi\n  product_code: '{AAAAAAAA-0000-0000-0000-000000000001}'\n"
                    "  upgrade_code: '" + _win_support.UPGRADE_CODE + "'\n  version: 1.0.0\nname: Example-Chain\n")
        self.put_pkginfo("apps/Example-Chain-1.0.0.yaml", head + body)
        template = self.read_pkginfo("apps/Example-Chain-1.0.0.yaml")
        processor, messages = self.run_chain(self.installer(), cimian_allow_unverified=True)
        new = self.read_pkginfo("apps/Example-Chain-%s.yaml" % processor.env["cimian_version_imported"])
        for key, value in load(CIMIAN)["Input"]["pkginfo"].items():
            if key in template:
                self.assertEqual(new[key], template[key], key)
                self.assertTrue(any(m.startswith("NOTE: pkginfo's %s differs from the template's and is not used" % key) for m in messages), key)
            else:
                self.assertEqual(new[key], value, key)
        self.assertEqual(new["display_name"], "Template Name")
        if "exe" == "exe":
            self.assertEqual(new["installer"]["switches"], ["/TEMPLATE-SWITCH"])
            self.assertNotIn("args", new["installer"])

    @_win_support.needs_yaml
    def test_a_second_run_with_the_same_file_has_nothing_new(self):
        self.run_chain(self.installer(), cimian_allow_unverified=True)
        before = self.repo_tree()
        processor, messages = self.run_chain(self.installer(), cimian_allow_unverified=True)
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertEqual(self.repo_tree(), before)


if __name__ == "__main__":
    unittest.main()
