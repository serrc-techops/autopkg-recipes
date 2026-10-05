"""Tests of the two Foxit PDF Reader recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names one of our
processors is compared with what that processor declares: the shared ones
(see ../../Win-SharedProcessors) and this folder's own FoxitInfoProvider
(tested in test_info_provider.py). The shared folder's tests are run separately.

The download of this program has NO hard check (Foxit publishes no hash, and a
check of the signature is not built). The tests make sure that nobody can
overlook that: the Description of both recipes and the top of the README say
it, and no recipe invents a check. The label of the EXE is read from the file
itself by the shared WindowsExeVersion step; the tests check its place in the
chain and, with a small PE file built in a temporary folder, the chain as a whole.
"""
import os
import plistlib
import re
import subprocess
import sys
import unittest
from unittest import mock

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
import test_exe_version as exe_builder  # noqa: E402  (builds a small PE file)
import FoxitInfoProvider as own  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
OWN_PROCESSOR = "FoxitInfoProvider"
DOWNLOAD = os.path.join(RECIPE_DIR, "FoxitReader-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "FoxitReader.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "FoxitReader.pcman.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
PROVIDER_FILE = os.path.join(RECIPE_DIR, OWN_PROCESSOR + ".py")
# Processors that are part of AutoPkg itself.
CORE_PROCESSORS = ("URLDownloader", "EndOfCheckPhase")
# Required inputs that a recipe must NOT pass: they come from AutoPkg's
# preferences or the override on the machine that runs it.
SUPPLIED_BY_THE_MACHINE = {"PcmanImporter": {"pcman_root"}}
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir", "pcman_timeout")
# What the earlier steps leave in the run (a step reads these without an argument).
SET_BY_CORE_STEPS = {"pathname", "url"}
HEX_64 = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
# File names that recipes of other public repositories might have for the same program.
# They are the writer's guesses, NOT read in any repository: the check is only a guard,
# and the README's step b (`autopkg list-recipes | grep`) is the real check on the build
# machine. AutoPkg takes the first match by name and says nothing.
NAMES_OF_OTHER_REPOSITORIES = (
    "FoxitReader.download", "FoxitReader.munki", "Foxit.download",
    "FoxitReader.pkg", "FoxitPDFReader.download", "FoxitPDFReader-Win.download", "FoxitReader-Win64.download",
)
LABEL = "2026.2.1.39815"
ADDRESS_VERSION = "2026.2.1"


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def processor_classes():
    import importlib
    classes = {OWN_PROCESSOR: own.FoxitInfoProvider}
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
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.FoxitReader-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".pcman.FoxitReader")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [OWN_PROCESSOR, "URLDownloader", "EndOfCheckPhase",
                                 SHARED_PREFIX + "WindowsExeVersion"])

    def test_the_pcman_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(PCMAN)["Process"]]
        self.assertEqual(steps, [PCMAN_PREFIX + "PcmanImporter"])

    def test_the_version_step_comes_after_the_end_of_the_check_phase(self):
        """It reads the downloaded file, which exists only after the check phase."""
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertGreater(steps.index(SHARED_PREFIX + "WindowsExeVersion"), steps.index("EndOfCheckPhase"))
        self.assertGreater(steps.index(SHARED_PREFIX + "WindowsExeVersion"), steps.index("URLDownloader"))
        self.assertEqual(steps[-1], SHARED_PREFIX + "WindowsExeVersion")

    def test_the_version_step_has_the_one_argument_pathname(self):
        steps = dict(named_steps(load(DOWNLOAD)))
        self.assertEqual(steps["WindowsExeVersion"], {"pathname": "%pathname%"})
        self.assertNotIn("set_version", read(DOWNLOAD))

    def test_the_provider_arguments_are_the_recipes_inputs(self):
        recipe = load(DOWNLOAD)
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {
            "foxit_product": "%FOXIT_PRODUCT%",
            "foxit_language": "%FOXIT_LANGUAGE%",
            "foxit_package_type": "%FOXIT_PACKAGE_TYPE%",
        })
        for value in args.values():
            match = re.fullmatch(r"%([A-Z_]+)%", value)
            self.assertTrue(match)
            self.assertIn(match.group(1), recipe["Input"])

    def test_the_defaults_of_the_recipe_are_the_defaults_of_the_processor(self):
        inputs = load(DOWNLOAD)["Input"]
        flags = own.FoxitInfoProvider.input_variables
        self.assertEqual(inputs["FOXIT_PRODUCT"], "Foxit-Reader")
        self.assertEqual(inputs["FOXIT_PRODUCT"], flags["foxit_product"]["default"])
        self.assertEqual(inputs["FOXIT_LANGUAGE"], "L10N")
        self.assertEqual(inputs["FOXIT_LANGUAGE"], flags["foxit_language"]["default"])
        self.assertEqual(inputs["FOXIT_PACKAGE_TYPE"], "exe")
        self.assertEqual(inputs["FOXIT_PACKAGE_TYPE"], flags["foxit_package_type"]["default"])
        self.assertEqual(inputs["NAME"], "FoxitReader")

    def test_the_downloader_gets_its_address_from_the_provider(self):
        """URLDownloader needs `url`. It is set by the provider and passed as no argument."""
        step = load(DOWNLOAD)["Process"][1]
        self.assertEqual(step["Processor"], "URLDownloader")
        self.assertNotIn("url", step.get("Arguments", {}))
        self.assertIn("url", own.FoxitInfoProvider.output_variables)

    def test_the_downloader_stores_the_file_under_a_stable_name_that_ends_in_exe(self):
        step = load(DOWNLOAD)["Process"][1]
        self.assertEqual(step["Arguments"],
                         {"filename": "FoxitPDFReader-%foxit_address_version%-%foxit_language%-x64.exe"})
        name = step["Arguments"]["filename"]
        self.assertTrue(name.endswith(".exe"))
        for variable in re.findall(r"%([A-Za-z_]+)%", name):
            self.assertTrue(variable in own.FoxitInfoProvider.output_variables
                            or variable in own.FoxitInfoProvider.input_variables, variable)
        # What the name becomes for the defaults, and for the values a person might give.
        for values in ({"foxit_address_version": ADDRESS_VERSION, "foxit_language": "L10N"},
                       {"foxit_address_version": "2027.1", "foxit_language": "en-US"}):
            made = name
            for key, value in values.items():
                made = made.replace("%" + key + "%", value)
            self.assertNotRegex(made, r"[ %/\\]")
        self.assertEqual(name.replace("%foxit_address_version%", ADDRESS_VERSION).replace("%foxit_language%", "L10N"),
                         "FoxitPDFReader-2026.2.1-L10N-x64.exe")

    def test_the_provider_outputs_the_address_version_and_no_label_and_no_hash(self):
        outputs = own.FoxitInfoProvider.output_variables
        self.assertEqual(sorted(outputs), ["foxit_address_version", "url"])
        self.assertNotIn("version", outputs)
        self.assertNotIn("expected_sha256", outputs)

    def test_the_label_is_set_by_the_exe_step_and_passed_by_the_pcman_recipe(self):
        """For an EXE the package tool has no version of its own to read: the recipe
        passes `version`, which WindowsExeVersion sets from the file."""
        classes = processor_classes()
        self.assertIn("version", classes["WindowsExeVersion"].output_variables)
        self.assertEqual(load(PCMAN)["Process"][0]["Arguments"]["pcman_version"], "%version%")
        self.assertNotIn("pcman_version", read(DOWNLOAD))
        # The file the URLDownloader stores is an .exe: PcmanImporter takes `.msi` or `.exe`.
        self.assertTrue(load(DOWNLOAD)["Process"][1]["Arguments"]["filename"].endswith(".exe"))

    def test_the_provider_does_not_set_version_so_that_only_the_file_does(self):
        text = read(PROVIDER_FILE)
        self.assertNotIn('self.env["version"]', text)

    def test_every_variable_a_recipe_uses_is_an_input_or_set_by_an_earlier_step(self):
        classes = processor_classes()
        for path in (DOWNLOAD, PCMAN):
            recipe = load(path)
            known = set(recipe["Input"]) | SET_BY_CORE_STEPS
            if path == PCMAN:
                known |= set(load(DOWNLOAD)["Input"]) | set(own.FoxitInfoProvider.output_variables)
                known |= set(classes["WindowsExeVersion"].output_variables)
            for step in recipe["Process"]:
                for value in step.get("Arguments", {}).values():
                    for name in re.findall(r"%([A-Za-z_]+)%", str(value)):
                        with self.subTest(recipe=os.path.basename(path), variable=name):
                            self.assertIn(name, known)
                # AutoPkg keeps the arguments of a step in the run: a later step reads them.
                known |= set(step.get("Arguments", {}))
                if step["Processor"] == OWN_PROCESSOR:
                    known |= set(own.FoxitInfoProvider.output_variables)
                if step["Processor"].endswith("/WindowsExeVersion"):
                    known |= set(classes["WindowsExeVersion"].output_variables)

    def test_the_inputs_of_the_pcman_recipe(self):
        recipe = load(PCMAN)
        self.assertEqual(recipe["Input"]["NAME"], "FoxitReader")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "foxitreader")
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%",
                                "pcman_version": "%version%"})

    def test_the_template_keeps_the_name_of_the_item_it_replaces(self):
        self.assertEqual(load(PCMAN)["Input"]["PCMAN_TEMPLATE"], "foxitreader")

    def test_no_file_name_of_ours_is_the_name_of_a_recipe_in_another_repository(self):
        ours = [name[: -len(".recipe")].casefold() for name in (os.path.basename(DOWNLOAD), os.path.basename(PCMAN))]
        others = [other.casefold() for other in NAMES_OF_OTHER_REPOSITORIES]
        for name in ours:
            self.assertNotIn(name, others)

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

    def test_the_description_says_what_a_reader_must_know(self):
        text = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        self.assertIn("FoxitInfoProvider", text)
        self.assertIn("Location header of the first two answers", text)
        self.assertIn("follows no redirect", text)
        self.assertIn("WindowsExeVersion", text)
        self.assertIn("2026.2.1.39815", text)
        self.assertIn("first three parts", text)
        self.assertIn("were read from Foxit's servers on 2026-10-02", text)
        self.assertIn("NOT run with AutoPkg", text)
        cimian = re.sub(r"\s+", " ", load(PCMAN)["Description"])
        self.assertIn("EXE", cimian)
        self.assertIn("version label", cimian)
        self.assertIn("WindowsExeVersion", cimian)
        self.assertIn("ProductVersion", cimian)
        self.assertIn("dry run", cimian)
        self.assertIn("pcman_dry_run", cimian)

    def test_no_description_claims_a_rehearsal(self):
        for path in (DOWNLOAD, PCMAN):
            text = re.sub(r"\s+", " ", load(path)["Description"])
            self.assertNotRegex(text, r"(?i)\brehearsed\b")
            self.assertNotRegex(text, r"(?i)\bwas tried\b")


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

    def test_the_pcman_description_names_what_is_not_established_for_an_exe(self):
        text = re.sub(r"\s+", " ", load(PCMAN)["Description"])
        self.assertIn("whether the package tool checks that an EXE is the same product as the template was NOT established", text)
        self.assertNotIn("upgrade code", text)  # that check is an MSI's
        self.assertIn("pcman_dry_run", text)

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

    def test_no_step_of_the_chain_sets_the_verified_flag(self):
        """The importer refuses a real run unless a step set checksum_verified: none of the
        steps of this chain is one that does."""
        classes = processor_classes()
        names = [step["Processor"].rsplit("/", 1)[-1] for step in load(DOWNLOAD)["Process"] + load(PCMAN)["Process"]]
        for name in names:
            if name in classes:
                self.assertNotIn("checksum_verified", classes[name].output_variables, name)
                self.assertNotIn("checksum_sha256", classes[name].output_variables, name)
        self.assertNotIn("ChecksumVerifier", names)

    def test_no_recipe_invents_a_checksum_step(self):
        for path in (DOWNLOAD, PCMAN):
            text = read(path)
            self.assertNotIn("ChecksumVerifier", text)
            self.assertNotIn("GitHubAssetDigest", text)
            self.assertNotIn("expected_sha256", text)
            self.assertNotIn("sha256", text.lower())
            self.assertIsNone(HEX_64.search(text))
            self.assertNotIn("CodeSignatureVerifier", text)

    def test_the_readme_opens_with_a_bold_status_line(self):
        lines = [line for line in read(README).splitlines() if line.strip()]
        self.assertTrue(lines[0].startswith("# "))
        status = lines[2] if lines[1].startswith("A Windows recipe pair") else lines[1]
        self.assertTrue(status.startswith("**Status."), status[:60])
        self.assertTrue(status.endswith("**"))
        for needle in ("NOT verified", "signature", "REFUSES a real run", "pcman_allow_unverified",
                       "Do not set it before the signature check exists",
                       "pcman import <file> --template foxitreader --version <the label>",
                       "an EXE needs `--version`"):
            self.assertIn(needle, status)

    def test_the_readme_says_what_still_protects_and_that_it_is_not_enough(self):
        text = re.sub(r"\s+", " ", read(README))
        self.assertIn("The address.", text)
        self.assertIn("It does not show what the signed address that follows it serves.", text)
        self.assertIn("Whether it has an equivalent check for an EXE was NOT established by the writer.", text)
        self.assertIn("do not replace a verification", text)
        self.assertIn("a real run is refused before the package tool starts", text)
        self.assertIn("An installer of another content under the same address would pass all of these.", text)

    def test_the_real_run_step_says_not_yet(self):
        text = read(README)
        self.assertIn("## d. Switch a real run on (NOT YET: see the status line)", text)
        self.assertLess(text.index("**Status."), text.index("## a."))

    def test_the_hand_command_uses_the_template_and_a_label(self):
        """After the template exists, `pcman import` without --template would make a second item."""
        text = read(README)
        match = re.search(r"\n    (pcman import <the file> --template foxitreader[^\n]*)\n", text)
        self.assertTrue(match)
        self.assertIn("--version <the label>", match.group(1))  # an EXE needs one
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
        self.assertIn("The download was not verified: no step of the recipe set checksum_verified", text)
        # the real text of the refusal, as the shared importer gives it
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
        text = read(PROVIDER_FILE)
        self.assertIn("class %s(Processor):" % OWN_PROCESSOR, text)
        for step in load(DOWNLOAD)["Process"]:
            if step["Processor"] == OWN_PROCESSOR:
                break
        else:
            self.fail("the own processor is not a step")

    def test_the_stub_identifier_is_the_prefix_of_the_processor_names(self):
        stub = load(os.path.join(SHARED_DIR, "SharedProcessors.recipe"))
        self.assertEqual(stub["Identifier"] + "/", SHARED_PREFIX)

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

    def test_the_exe_version_step_is_among_the_processors_the_tests_compare(self):
        self.assertIn("WindowsExeVersion", processor_classes())
        names = [name for name, _ in named_steps(load(DOWNLOAD))]
        self.assertIn("WindowsExeVersion", names)

    def test_every_input_of_the_own_processor_has_the_flags_that_autopkg_reads(self):
        for name, flags in own.FoxitInfoProvider.input_variables.items():
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
            "FoxitReader-Win.download.recipe", "FoxitReader.cimian.recipe", "FoxitReader.pcman.recipe", "FoxitInfoProvider.py",
            "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
            os.path.join("tests", "test_info_provider.py"),
        ]))

    def test_no_recipe_no_readme_and_no_provider_holds_a_hash(self):
        for path in (DOWNLOAD, PCMAN, README, PROVIDER_FILE, os.path.join(TESTS_DIR, "test_info_provider.py")):
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
                    r"<the Windows overrides folder>/FoxitReader\.(?:cimian|pcman)\.recipe$",
                )

    def test_no_autopkg_command_line_is_missed_by_the_indent_rule(self):
        """An operator's command that is not indented four spaces (or is indented
        less) must still be counted: every line that begins with an autopkg
        command is one of the lines checked above, and `autopkg run ` occurs
        three times in the whole file."""
        pattern = r"^[ \t]*autopkg (?:run|verify-trust-info|update-trust-info)\b"
        at_line_start = re.findall(pattern, self.raw, re.M)
        self.assertEqual(len(at_line_start), len(self.operator_commands()))
        self.assertEqual(len(re.findall(r"autopkg run ", self.raw)), 6)

    def test_no_prose_line_shows_a_full_command_without_the_option(self):
        for match in re.finditer(r"`(autopkg (?:run|verify-trust-info|update-trust-info)[^`]*<[^`]*)`", self.raw):
            self.assertIn("--override-dir=", match.group(1))

    def test_the_readme_says_that_the_label_is_the_installers_version_and_nothing_compares_it(self):
        heading = "## The label is the installer's version, and nothing compares it with the product's"
        self.assertIn(heading, self.raw)
        start = self.text.index(heading)
        section = self.text[start:self.text.index("## Run every override")]
        for needle in ("the `ProductVersion` of the downloaded setup file",
                       "No step of this recipe compares the two",
                       "nothing compares it with the label",
                       "the version that the installed Reader shows has not been read by anyone",
                       "would still publish under the setup file's number",
                       "that number orders the versions in the repository",
                       "does not check this at any run", "A person checks it, at the first dry run",
                       "with `-v`", "The label must begin with the address's version",
                       "`2026.2.1` and `2026.2.1.39815`", "stop and tell the owner before anything is published",
                       "After the first install on a test PC", "NOT established"):
            self.assertIn(needle, section)
        self.assertLess(self.raw.index(heading), self.raw.index("## a."))
        step = self.raw[self.raw.index("## c."):self.raw.index("## d.")]
        self.assertIn("autopkg run -v --override-dir=", step)

    def test_the_readme_states_no_hash(self):
        """A README that states a SHA-256 (64 hex digits) could be taken for a check."""
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.raw))

    def test_a_bold_paragraph_says_why_and_what_to_do_when_the_warning_appears(self):
        self.assertIn("## Run every override with `--override-dir`", self.raw)
        i = self.raw.index("## Run every override with `--override-dir`")
        paragraph = re.sub(r"\s+", " ", self.raw[i:i + 2500])
        for needle in ("**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`",
                       "skips the trust check with one warning line", "is missing trust info",
                       "a changed processor is not caught", "If that line ever appears in a run of an override, stop: the run was not checked.**",
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
        for needle in ("pcman catalogs", "pcman versions foxitreader", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string", "make-override"):
            self.assertIn(needle, self.text)

    def test_the_first_import_names_the_template_the_label_and_the_flags_of_the_package_tool(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        self.assertTrue(match)
        command = re.sub(r"\s+", " ", match.group(1))
        self.assertIn("--name foxitreader", command)
        self.assertIn("--version <the ProductVersion that the file's properties show>", command)  # an EXE has a label
        for flag in ("--display-name", "--category", "--developer", "--description", "--install-arguments",
                     "--install-path", "--architectures x64", "--no-prompt"):
            self.assertIn(flag, command)

    def test_the_silent_switch_and_the_install_path_are_placeholders_not_values(self):
        """The Foxit installer's silent switch was NOT read: the README does not invent one."""
        command = re.sub(r"\s+", " ", re.search(r"pcman import ([^`]*?--build)", self.raw, re.S).group(1))
        self.assertIn("--install-arguments <the installer's silent switch, read in the vendor's documentation first>", command)
        self.assertIn("--install-path <the path of the installed program, read on one PC after an install>", command)
        self.assertNotIn("/S ", command)
        self.assertNotIn("/VERYSILENT", command)
        self.assertNotIn("/quiet", command)
        i = self.text.index("The silent switch and the install path are facts of the installer.")
        self.assertIn("The writer did NOT read them", self.text[i:i + 300])

    def test_the_status_line_says_what_was_fetched_and_what_was_not(self):
        """The models say "Rehearsed on ...". This folder was NOT run with AutoPkg. The writer's
        facts were fetched on 2026-10-02: the README opens with a bold paragraph that lists what
        was verified and what is still not."""
        opening = "**Status. NOT rehearsed with AutoPkg. Some facts of the source were fetched by the writer on 2026-10-02:"
        start = self.raw.index(opening)
        self.assertLess(start, self.raw.index("| Recipe |"))
        self.assertLess(self.raw.index("# Win-FoxitReader"), start)
        end = self.raw.index("**\n", start)
        paragraph = re.sub(r"\s+", " ", self.raw[start:end + 2])
        self.assertTrue(paragraph.startswith(opening))
        self.assertTrue(paragraph.endswith("**"))
        verified, _, not_established = paragraph.partition("NOT established:")
        self.assertTrue(not_established)
        for needle in ("no run of AutoPkg was made",
                       "with no browser identity",
                       "answered 301 to `https://www.foxit.com/downloads/latest/?product=...` (the same query)",
                       "that address answered 307 to `https://cdn01.foxitsoftware.com/product/reader/desktop/win/2026.2.1/FoxitPDFReader202621_L10N_Setup_Prom_x64.exe`",
                       "that address answered 302 to a signed, short-lived address on a cloud storage host",
                       "downloaded through its signed redirect (291221048 bytes)",
                       "was read with the shared `WindowsExeVersion`",
                       "`ProductVersion` `2026.2.1.39815`", "`FileVersion` the same",
                       "the numbers of the fixed file information the same",
                       "`ProductName` `Foxit PDF Reader`",
                       "the label that the recipe passes is `2026.2.1.39815`",
                       "the version in the address, `2026.2.1`, is its first three parts (one release was compared)"):
            self.assertIn(needle, verified)
        for needle in ("that the next release keeps that relation between the address and the file",
                       "that the signature of the file is valid (nothing checks it)",
                       "the host and the lifetime of the signed address",
                       "that another product, language or package type than the defaults has the same layout",
                       "the silent switch and the install path of the installer",
                       "that the template item `foxitreader` exists", "`pcman catalogs`", "any run with AutoPkg"):
            self.assertIn(needle, not_established)
        for needle in ("wrote by hand after the real addresses of 2026-10-02",
                       "The first run on the build Mac is the check of everything that is NOT established",
                       "STOP: nothing was written", "correct the processor or the recipe",
                       "and only then look at the trust information",
                       "Never accept new trust information first"):
            self.assertIn(needle, not_established)
        self.assertNotRegex(self.text, r"Rehearsed on 20")
        self.assertNotRegex(self.text, r"(?i)\bwas rehearsed\b")
        self.assertNotIn("the network was closed", self.text)
        # The label's equality with the address is no longer said to be unknown: it was read.
        self.assertNotIn("equals `2026.2.1` (the first run shows both", paragraph)
        # No real digest in the status.
        self.assertIsNone(HEX_64.search(paragraph))

    def test_nothing_in_the_readme_claims_a_run_that_did_not_happen(self):
        for needle in ("Expected, from the code and the rehearsals of the other folders, NOT printed by this recipe yet",
                       "(Not run: the lines of the output are not known.)",
                       "Expected (not run)"):
            self.assertIn(needle, self.text)
        self.assertNotIn("The rehearsal printed", self.text)
        self.assertNotRegex(self.text, r"(?<!NOT )(?i:rehearsed with)")

    def test_the_readme_says_how_the_address_is_found_and_how_strict_the_processor_is(self):
        for needle in ("reads the `Location` header of the first two answers and follows no redirect",
                       "Exactly two requests are made", "No body is read",
                       "`/product/reader/desktop/win/<version>/FoxitPDFReader<digits>_<language>_Setup_Prom_x64.exe`",
                       "no user name, no port, no query and no fragment",
                       "It outputs no hash, because Foxit publishes none, and no `version`",
                       "`FoxitPDFReader-<version of the address>-<language>-x64.exe`",
                       "The downloader follows the third redirect, to the signed address."):
            self.assertIn(needle, self.text)

    def test_the_name_check_and_the_parent_check_are_in_step_b(self):
        b = self.raw.index("## b.")
        c = self.raw.index("## c.")
        step = self.raw[b:c]
        self.assertIn("autopkg list-recipes | grep -i FoxitReader-Win", step)
        self.assertIn("autopkg list-recipes | grep -i FoxitReader.pcman", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.FoxitReader`",
                      re.sub(r"\s+", " ", step))
        self.assertLess(step.index("autopkg list-recipes"), step.index("    autopkg make-override --override-dir="))
        self.assertIn("`FoxitInfoProvider`, `WindowsExeVersion`, `PcmanImporter`", re.sub(r"\s+", " ", step))

    def test_the_readme_tells_the_reader_to_compare_the_two_versions(self):
        for needle in ("**Read the two versions.**", "`version is ...`", "`2026.2.1` and `2026.2.1.39815`",
                       "the address's version is the first three parts of the label",
                       "if the label does not begin with it, stop and tell the owner before anything is published"):
            self.assertIn(needle, self.text)

    def test_the_readme_says_that_the_redirect_rule_is_a_stop(self):
        for needle in ("`Foxit's download address`", "`Foxit's second download address`",
                       "stop and tell the owner",
                       "the recipe never reads an address from another host than Foxit's two fixed ones"):
            self.assertIn(needle, self.text)

    def test_the_readme_names_the_shared_processor_and_the_label(self):
        for needle in ("`WindowsExeVersion`", "2026.2.1.39815", "the `ProductVersion` string when it is numbers and dots",
                       "otherwise the four numbers of the fixed file information"):
            self.assertIn(needle, self.text)


class ChainTests(_pcman_support.ToolTestCase):
    """The chain of this program, run with the real processors and the stand-in
    package tool: the provider (its two answers made up), a small PE file that
    stands for the download, WindowsExeVersion with the recipe's own arguments,
    and the importer with the cimian recipe's arguments. Nothing is fetched."""

    FINAL = "https://cdn01.foxitsoftware.com/product/reader/desktop/win/2026.2.1/FoxitPDFReader202621_L10N_Setup_Prom_x64.exe"
    SECOND = "https://www.foxit.com/downloads/latest/?product=Foxit-Reader"

    def provider_run(self):
        answers = iter([self.SECOND, self.FINAL])
        with mock.patch.object(own, "read_location", side_effect=lambda url, what: next(answers)):
            processor, _ = _win_support.run_processor(own.FoxitInfoProvider, {})
        return processor

    def downloaded_file(self, product="2026.2.1.39815", numbers=(2026, 2, 1, 39815)):
        """What URLDownloader would leave: a small PE file under the recipe's file name."""
        pe = exe_builder.build_pe(exe_builder.version_info(
            product=product, file=product, name="Foxit PDF Reader", file_numbers=numbers, product_numbers=numbers,
        ))
        path = os.path.join(self.downloads, "FoxitPDFReader-2026.2.1-L10N-x64.exe")
        with open(path, "wb") as handle:
            handle.write(bytes(pe.data))
        return path

    def steps_run(self, path):
        """Run the download recipe's steps that are not the core's, and return the env of the run."""
        env = {"pathname": path}
        provider = self.provider_run()
        env.update({k: provider.env[k] for k in own.FoxitInfoProvider.output_variables})
        step = [s for s in load(DOWNLOAD)["Process"] if s["Processor"].endswith("/WindowsExeVersion")][0]
        arguments = {name: env[value.strip("%")] for name, value in step["Arguments"].items()}
        processor, _ = _win_support.run_processor(_win_support.exe_version.WindowsExeVersion, arguments)
        env.update(processor.env)
        return env

    def importer_env(self, env, **extra):
        values = {"%pathname%": env["pathname"], "%PCMAN_TEMPLATE%": load(PCMAN)["Input"]["PCMAN_TEMPLATE"],
                  "%version%": env["version"]}
        result = {"pathname": env["pathname"], "pcman_root": self.root, "pcman_path": self.msi_bin}
        step = load(PCMAN)["Process"][0]
        for name, value in step["Arguments"].items():
            result[name] = values.get(value, value)
        result.update(extra)
        return result

    def test_the_label_is_the_exe_s_own_version_and_the_address_version_is_a_prefix_of_it(self):
        env = self.steps_run(self.downloaded_file())
        self.assertEqual(env["foxit_address_version"], ADDRESS_VERSION)
        self.assertEqual(env["version"], LABEL)
        self.assertEqual(env["exe_product_version"], LABEL)
        self.assertEqual(env["exe_product_name"], "Foxit PDF Reader")
        self.assertTrue(env["version"].startswith(env["foxit_address_version"] + "."))
        self.assertEqual(env["url"], self.FINAL)

    def test_the_label_is_the_exe_s_and_not_the_address_s_when_they_differ(self):
        env = self.steps_run(self.downloaded_file(product="2026.3.0.1", numbers=(2026, 3, 0, 1)))
        self.assertEqual(env["foxit_address_version"], ADDRESS_VERSION)
        self.assertEqual(env["version"], "2026.3.0.1")

    def test_a_real_run_of_the_chain_is_refused_because_nothing_verified_the_file(self):
        env = self.steps_run(self.downloaded_file())
        run = self.importer_env(env, pcman_dry_run=False)
        self.assertNotIn("checksum_verified", run)
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_pcman_support.importer.PcmanImporter, run)
        self.assertIn("The download was not verified", str(caught.exception))
        self.assertIn("pcman_allow_unverified", str(caught.exception))
        self.assertFalse(self.was_run(), "the tool must not start")

    def test_the_dry_run_of_the_chain_warns_and_passes_the_label_to_the_tool(self):
        env = self.steps_run(self.downloaded_file())
        self.behave(result=_pcman_support.result_file_content(result="dry-run", name="foxitreader", version=LABEL))
        run = self.importer_env(env)
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, run)
        warnings = [m for level, m in processor.message_levels if m.startswith("WARNING:")]
        self.assertTrue(any("the download was NOT verified" in m for m in warnings))
        data = processor.env["pcman_importer_summary_result"]["data"]
        self.assertEqual(data["result"], "dry run, nothing written, NOT verified")
        self.assertIs(processor.env["pcman_repo_changed"], False)
        self.assertIn("--dry-run", self.record()["argv"])
        argv = self.record()["argv"]
        self.assertEqual(argv[argv.index("--version") + 1], LABEL)
        self.assertEqual(argv[argv.index("--template") + 1], "foxitreader")

    def test_the_allowed_real_run_publishes_with_the_label_and_says_not_verified(self):
        env = self.steps_run(self.downloaded_file())
        self.behave(result=_pcman_support.result_file_content(name="foxitreader", version=LABEL))
        run = self.importer_env(env, pcman_dry_run=False, pcman_allow_unverified=True)
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, run)
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published, NOT verified")
        argv = self.record()["argv"]
        self.assertEqual(argv[argv.index("--version") + 1], LABEL)

    def test_a_file_that_is_not_a_pe_file_stops_the_chain_before_the_importer(self):
        path = os.path.join(self.downloads, "FoxitPDFReader-2026.2.1-L10N-x64.exe")
        with open(path, "wb") as handle:
            handle.write(b"<html>an error page</html>" + b" " * 200)
        with self.assertRaises(_win_support.ProcessorError) as caught:
            self.steps_run(path)
        self.assertIn("not a PE file", str(caught.exception))
        self.assertFalse(self.was_run())


def _text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


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
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.FoxitReader")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.FoxitReader")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotEqual(cimian["Identifier"], pcman["Identifier"])
        self.assertEqual(cimian["MinimumVersion"], pcman["MinimumVersion"])
        self.assertTrue(CIMIAN.endswith("FoxitReader.cimian.recipe"))
        self.assertTrue(PCMAN.endswith("FoxitReader.pcman.recipe"))

    def test_the_only_step_is_the_cimian_importer(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "CimianImporter"])

    def test_the_inputs_and_the_arguments(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], load(PCMAN)["Input"]["NAME"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], load(PCMAN)["Input"]["PCMAN_TEMPLATE"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], "foxitreader")
        self.assertEqual(recipe["Input"]["CIMIAN_SUBDIRECTORY"], "")
        self.assertEqual(sorted(recipe["Input"]), ["CIMIAN_NAME", "CIMIAN_SUBDIRECTORY", "NAME", "pkginfo"])
        self.assertEqual(recipe["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": "%version%"})

    def test_the_pkginfo_gives_only_what_the_readme_states(self):
        self.assertEqual(load(CIMIAN)["Input"]["pkginfo"], {'display_name': 'Foxit PDF Reader', 'developer': 'Foxit Software'})

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
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "foxitreader")
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
        for name, identifier in (("FoxitReader.cimian.recipe", "com.github.serrc-techops.cimian.FoxitReader"),
                                 ("FoxitReader.pcman.recipe", "com.github.serrc-techops.pcman.FoxitReader")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)
        self.assertIn("`CimianImporter`", [line for line in self.raw.splitlines() if line.startswith("| `FoxitReader.cimian.recipe`")][0])
        self.assertIn("`pcman`", [line for line in self.raw.splitlines() if line.startswith("| `FoxitReader.pcman.recipe`")][0])

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
        for text, recipe, other in ((self.generic, "FoxitReader.cimian", "FoxitReader.pcman"), (self.tool, "FoxitReader.pcman", "FoxitReader.cimian")):
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
            self.assertRegex(command, r"--override-dir=<the Windows overrides folder> <the Windows overrides folder>/FoxitReader\.cimian\.recipe$")

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
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.cimian.FoxitReader`**", self.generic.replace("\n", " "))
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.FoxitReader`**", self.tool.replace("\n", " "))
        for text in (self.generic, self.tool):
            self.assertNotIn("it must be `com.github.serrc-techops.download.", text.replace("\n", " "))

    def test_an_override_of_the_old_cimian_recipe_is_to_be_made_again_for_the_package_tool(self):
        self.assertIn("An override that was made from the old `FoxitReader.cimian.recipe`", self.tool)
        self.assertIn("must be made again from `FoxitReader.pcman.recipe`", self.tool)
        self.assertIn("An override that was made from this recipe before the recipes were separated", self.generic)

    def test_the_condition_of_never_overwrites_is_said(self):
        self.assertIn("do not run two runs of one item at the same time", self.generic)

    def test_the_generic_way_states_no_hash_and_no_made_up_label(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.generic))
        self.assertNotIn("Published foxitreader", self.generic)

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
        self.assertIn("FoxitReader.pcman", self.tool)

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
