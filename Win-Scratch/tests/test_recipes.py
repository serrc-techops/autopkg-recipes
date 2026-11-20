"""Tests of the three Scratch recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names one of our
processors is compared with what that processor declares: the shared ones
(see ../../Win-SharedProcessors), the package tool's importer (see
../../Win-PcmanProcessors) and this folder's own ScratchInfoProvider (tested in
test_info_provider.py). The other folders' tests are run separately.

No hash of this program was found published: the download is verified by its
Authenticode signature (the shared AuthenticodeVerifier, tested in its own folder).
The tests make sure that the step is where it belongs, with the Scratch Foundation's
name and the pinned root, that the Description of every recipe and the README say
what it proves and what not, and that no recipe invents a checksum. The label of the EXE is the version in the
file name that the download address redirects to, set by ScratchInfoProvider;
the file is not read for a version. The tests check the chain as a whole with
the provider's answer made up and a stand-in for the downloaded file.
"""
import importlib
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
import ScratchInfoProvider as own  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
OWN_PROCESSOR = "ScratchInfoProvider"
DOWNLOAD = os.path.join(RECIPE_DIR, "Scratch-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "Scratch.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "Scratch.pcman.recipe")
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
    "Scratch.download", "Scratch.munki", "Scratch.pkg", "Scratch3.download", "ScratchDesktop.download",
    "Scratch-Windows.download", "Scratch3-Win.download",
)
LABEL = "3.32.1"
FINAL = "https://downloads.scratch.mit.edu/desktop/Scratch%203.32.1%20Setup.exe"


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def flat(text):
    return re.sub(r"\s+", " ", text)


def processor_classes():
    classes = {OWN_PROCESSOR: own.ScratchInfoProvider}
    for name in ("PcmanImporter", "CimianImporter", "ChecksumVerifier", "GitHubAssetDigest", "WindowsExeVersion",
                 "AuthenticodeVerifier"):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def named_steps(recipe):
    """(processor name without the prefix, arguments) of every step that is ours."""
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


def status_line():
    return flat([line for line in read(README).splitlines() if line.startswith("**Status.")][0])


class RecipeFileTests(unittest.TestCase):
    def test_the_three_files_are_valid_property_lists(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            with self.subTest(path=os.path.basename(path)):
                result = subprocess.run(["plutil", "-lint", path], capture_output=True, text=True) \
                    if os.path.exists("/usr/bin/plutil") else None
                if result is not None:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                recipe = load(path)
                for key in ("Description", "Identifier", "Input", "MinimumVersion", "Process"):
                    self.assertIn(key, recipe)
                self.assertEqual(recipe["MinimumVersion"], "1.0.0")

    def test_identifiers_and_parents(self):
        download, cimian, pcman = load(DOWNLOAD), load(CIMIAN), load(PCMAN)
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.Scratch-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.Scratch")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.Scratch")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [OWN_PROCESSOR, "URLDownloader", "EndOfCheckPhase", SHARED_PREFIX + "AuthenticodeVerifier",
                                 SHARED_PREFIX + "WindowsExeVersion"])

    def test_the_label_is_the_signed_files_own_and_the_name_is_a_cross_check(self):
        """The label is the version resource of the signed file (WindowsExeVersion, after the signature
        step); the version of the redirect's file name must equal it, and the product and the company
        must be the expected ones."""
        steps = load(DOWNLOAD)["Process"]
        names = [step["Processor"] for step in steps]
        version_step = steps[names.index(SHARED_PREFIX + "WindowsExeVersion")]
        self.assertGreater(names.index(SHARED_PREFIX + "WindowsExeVersion"), names.index(SHARED_PREFIX + "AuthenticodeVerifier"))
        self.assertEqual(version_step["Arguments"], {"pathname": "%pathname%", "expected_product_name": "Scratch 3",
                                                     "expected_company_name": "Scratch Foundation",
                                                     "expected_version": "%version%"})
        self.assertNotIn("set_version", read(DOWNLOAD))
        self.assertNotIn("VersionFromName", read(DOWNLOAD))

    def test_the_provider_takes_no_arguments_and_the_recipe_has_no_input_but_name(self):
        recipe = load(DOWNLOAD)
        self.assertNotIn("Arguments", recipe["Process"][0])
        self.assertEqual(recipe["Input"], {"NAME": "Scratch"})

    def test_the_downloader_gets_its_address_from_the_provider(self):
        """URLDownloader needs `url`. It is set by the provider and passed as no argument."""
        step = load(DOWNLOAD)["Process"][1]
        self.assertEqual(step["Processor"], "URLDownloader")
        self.assertNotIn("url", step.get("Arguments", {}))
        self.assertIn("url", own.ScratchInfoProvider.output_variables)

    def test_the_downloader_stores_the_file_under_a_name_without_spaces_that_ends_in_exe(self):
        step = load(DOWNLOAD)["Process"][1]
        self.assertEqual(step["Arguments"], {"filename": "Scratch-Setup-%version%.exe"})
        name = step["Arguments"]["filename"]
        for variable in re.findall(r"%([A-Za-z_]+)%", name):
            self.assertIn(variable, own.ScratchInfoProvider.output_variables)
        made = name.replace("%version%", LABEL)
        self.assertEqual(made, "Scratch-Setup-3.32.1.exe")
        self.assertNotRegex(made, r"[ %/\\]")
        self.assertTrue(made.endswith(".exe"))

    def test_the_provider_outputs_the_label_and_no_hash(self):
        outputs = own.ScratchInfoProvider.output_variables
        self.assertEqual(sorted(outputs), ["url", "version"])
        self.assertNotIn("expected_sha256", outputs)

    def test_the_label_is_passed_by_both_importer_recipes(self):
        self.assertEqual(load(PCMAN)["Process"][0]["Arguments"]["pcman_version"], "%version%")
        self.assertEqual(load(CIMIAN)["Process"][0]["Arguments"]["version"], "%version%")
        self.assertNotIn("pcman_version", read(DOWNLOAD))

    def test_every_variable_a_recipe_uses_is_an_input_or_set_by_an_earlier_step(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            recipe = load(path)
            known = set(recipe["Input"]) | SET_BY_CORE_STEPS
            if path != DOWNLOAD:
                known |= set(load(DOWNLOAD)["Input"]) | set(own.ScratchInfoProvider.output_variables)
            for step in recipe["Process"]:
                for value in step.get("Arguments", {}).values():
                    for name in re.findall(r"%([A-Za-z_]+)%", str(value)):
                        with self.subTest(recipe=os.path.basename(path), variable=name):
                            self.assertIn(name, known)
                known |= set(step.get("Arguments", {}))
                if step["Processor"] == OWN_PROCESSOR:
                    known |= set(own.ScratchInfoProvider.output_variables)

    def test_the_inputs_of_the_pcman_recipe(self):
        recipe = load(PCMAN)
        self.assertEqual(recipe["Input"], {"NAME": "Scratch", "PCMAN_TEMPLATE": "scratch"})
        self.assertEqual(recipe["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%", "pcman_version": "%version%"})

    def test_no_file_name_of_ours_is_the_name_of_a_recipe_in_another_repository(self):
        ours = [os.path.basename(path)[: -len(".recipe")].casefold() for path in (DOWNLOAD, CIMIAN, PCMAN)]
        others = [other.casefold() for other in NAMES_OF_OTHER_REPOSITORIES]
        for name in ours:
            self.assertNotIn(name, others)

    def test_no_stop_on_an_unchanged_download_no_latest_only_no_blocking_applications(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = read(path)
            for word in ("StopProcessingIf", "latest_only", "blocking_applications"):
                self.assertNotIn(word, text)

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = read(path)
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text)
            for name in ("catalogs", "catalog", "pcman_catalogs", "path", "repo", "directory",
                         "cimian_repo", "cimian_dry_run", "cimian_allow_unverified", "CIMIAN_REPO"):
                self.assertNotIn("<key>%s</key>" % name, text)

    def test_no_value_of_a_recipe_is_a_path_or_a_catalog(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            recipe = load(path)
            values = [value for value in recipe["Input"].values() if isinstance(value, str)]
            for step in recipe["Process"]:
                values.extend(value for value in step.get("Arguments", {}).values() if isinstance(value, str))
            for value in values:
                with self.subTest(path=os.path.basename(path), value=value):
                    self.assertFalse(value.startswith(("/", "~", ".")), value)
                    self.assertNotIn("\\", value)
                    self.assertNotIn("Production", value)
                    self.assertNotIn("Testing", value)

    def test_the_description_says_what_a_reader_must_know(self):
        text = flat(load(DOWNLOAD)["Description"])
        for needle in ("ScratchInfoProvider", "reads the Location header of the one answer", "follows no redirect",
                       "is only a cross-check", "NOT established", "a name without spaces",
                       "were read from the Scratch Foundation's server on 2026-11-13", "NOT run with AutoPkg"):
            self.assertIn(needle, text)
        for path in (CIMIAN, PCMAN):
            text = flat(load(path)["Description"])
            with self.subTest(path=os.path.basename(path)):
                for needle in ("EXE", "version label", "WindowsExeVersion", "signed file's own version resource",
                               "the product Scratch 3 of the company Scratch Foundation", "dry run",
                               "installs for the whole machine when the client runs it as SYSTEM is NOT established"):
                    self.assertIn(needle, text)
        self.assertIn("pcman_dry_run", load(PCMAN)["Description"])
        self.assertIn("cimian_dry_run", load(CIMIAN)["Description"])

    def test_no_description_claims_a_rehearsal(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = flat(load(path)["Description"])
            self.assertNotRegex(text, r"(?i)\brehearsed\b")
            self.assertNotRegex(text, r"(?i)\bwas tried\b")


SIGNER = {"CN": "Scratch Foundation", "O": "Scratch Foundation", "L": "New York", "ST": "New York", "C": "US"}
ROOT = "microsoft-identity-verification-root-2020"


class SignatureTests(unittest.TestCase):
    """The download is verified by its signature. The step is the last of the download
    recipe, after EndOfCheckPhase, and the recipes say what it proves."""

    def step(self):
        steps = [step for step in load(DOWNLOAD)["Process"] if step["Processor"].endswith("/AuthenticodeVerifier")]
        self.assertEqual(len(steps), 1)
        return steps[0]

    def test_the_step_checks_the_downloaded_file_with_the_publishers_name_and_the_pinned_root(self):
        import AuthenticodeVerifier
        arguments = self.step()["Arguments"]
        self.assertEqual(arguments["pathname"], "%pathname%")
        self.assertEqual(arguments["expected_signer"], SIGNER)
        self.assertEqual(arguments["code_signing_roots"], [ROOT])
        self.assertEqual(arguments["timestamp_roots"], [ROOT])
        self.assertIn(ROOT, AuthenticodeVerifier.PINNED_ROOTS)
        self.assertNotIn("osslsigncode_path", arguments)

    def test_the_step_comes_right_after_the_check_phase_and_before_the_version_step(self):
        names = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(names.index("EndOfCheckPhase") + 1, names.index(SHARED_PREFIX + "AuthenticodeVerifier"))
        self.assertEqual(names[-1], SHARED_PREFIX + "WindowsExeVersion")

    def test_every_description_says_how_the_download_is_verified(self):
        self.assertIn("verified by its Authenticode signature, not by a hash",
                      first_sentence(load(DOWNLOAD)["Description"]))
        for path in (CIMIAN, PCMAN):
            with self.subTest(path=os.path.basename(path)):
                self.assertIn("verified by the signature step of the download recipe",
                              first_sentence(load(path)["Description"]))

    def test_the_download_description_says_what_is_checked_and_what_is_not(self):
        text = flat(load(DOWNLOAD)["Description"])
        for needle in ("publishes no hash", "AuthenticodeVerifier", "CN and O Scratch Foundation, L and ST New York, C US, and no OU", "WindowsExeVersion", "ProductName must be Scratch 3", ROOT,
                       "valid only through its timestamp", "CRLs", "signature_verified and signature_sha256",
                       "does not prove that a release that the Scratch Foundation itself signed is harmless",
                       "the root issues for many publishers", "not the intermediates'", "needs osslsigncode",
                       "NOT run with AutoPkg"):
            self.assertIn(needle, text)

    def test_the_importer_descriptions_name_the_flag_for_a_run_without_the_step(self):
        for path, flag in ((CIMIAN, "cimian_allow_unverified"), (PCMAN, "pcman_allow_unverified")):
            text = flat(load(path)["Description"])
            with self.subTest(path=os.path.basename(path)):
                self.assertIn("Without that step", text)
                self.assertIn(flag, text)
                self.assertIn("published, NOT verified", text)
        self.assertNotIn("upgrade code", load(PCMAN)["Description"])  # that check is an MSI's
        self.assertIn("whether the package tool checks that an EXE is the same product as the template was NOT "
                      "established", flat(load(PCMAN)["Description"]))

    def test_no_recipe_sets_the_allowance_or_a_verified_flag_itself(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = read(path)
            for word in ("<key>pcman_allow_unverified</key>", "<key>cimian_allow_unverified</key>",
                         "<key>checksum_verified</key>", "<key>signature_verified</key>",
                         "<key>signature_sha256</key>", "<key>checksum_sha256</key>"):
                self.assertNotIn(word, text)

    def test_no_recipe_invents_a_checksum_step(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = read(path)
            for word in ("ChecksumVerifier", "GitHubAssetDigest", "expected_sha256", "CodeSignatureVerifier"):
                self.assertNotIn(word, text)
            self.assertIsNone(HEX_64.search(text))

    def test_the_readme_opens_with_a_bold_status_line(self):
        lines = [line for line in read(README).splitlines() if line.strip()]
        self.assertEqual(lines[0], "# Win-Scratch")
        self.assertTrue(lines[1].startswith("A Windows recipe pair"))
        self.assertTrue(lines[2].startswith("**Status."))
        self.assertTrue(lines[2].endswith("**"))
        for needle in ("verified by its signature, not by a hash", "`AuthenticodeVerifier`",
                       "That step was NOT run with AutoPkg"):
            self.assertIn(needle, status_line())

    def test_the_readme_says_what_the_signature_proves_and_what_not(self):
        text = flat(read(README))
        for needle in ("**The download is verified by its signature.**", "`CN=Scratch Foundation`",
                       "`O=Scratch Foundation`", "`C=US`", "and no `OU`", "`%s`" % ROOT, "lived from 2026-06-08 to 2026-06-11",
                       "valid only through its timestamp", "**Checked on 2026-11-19**",
                       "the same file with one byte changed was refused",
                       "a bad release that the Scratch Foundation itself signed passes",
                       "only the signing certificate's CRL is read", "for many publishers",
                       "**The step needs `osslsigncode`**", "The address.",
                       "It does not show what the file at that address is.",
                       "Whether it has an equivalent check for an EXE was NOT established by the writer",
                       "**The product and the version come from the signed file.**", "`L=New York`", "`ST=New York`",
                       "**An older release, signed for real.**", "It does not refuse an older version",
                       "the step stops the run until a person has looked and changed the recipe",
                       "Without the signature step, an installer of another content under the same address would "
                       "pass all of these."):
            self.assertIn(needle, text)

    def test_the_real_run_steps_need_only_the_dry_run_switch(self):
        text = read(README)
        self.assertIn("## d. Switch a real run on\n", text)
        self.assertIn("### 4. Switch a real run on\n", text)
        self.assertNotIn("NOT YET", text)
        self.assertLess(text.index("**Status."), text.index("## a."))
        self.assertIn("That one line is enough: the signature step verifies the download.", flat(text))

    def test_the_hand_command_uses_the_template_and_a_label(self):
        """After the template exists, `pcman import` without --template would make a second item."""
        text = read(README)
        match = re.search(r"\n    (pcman import <the file> --template scratch[^\n]*)\n", text)
        self.assertTrue(match)
        self.assertIn("--version <the label>", match.group(1))
        self.assertNotIn("--name", match.group(1))
        self.assertNotIn("--build", match.group(1))
        self.assertIn("It uses the template, so it makes no second item", flat(text))
        first_imports = list(re.finditer(r"pcman import [^`]*?--name", text))
        self.assertEqual(len(first_imports), 1)
        self.assertLess(first_imports[0].start(), text.index("## b."))

    def test_the_override_lines_that_allow_an_unverified_run_are_two_and_marked(self):
        text = read(README)
        for needle in ("Add :Input:pcman_dry_run bool false", "Add :Input:pcman_allow_unverified bool true",
                       "Both lines are needed", "Add :Input:cimian_allow_unverified bool true",
                       "published, NOT verified", "published WITHOUT a verified download",
                       "**Without the signature step**", "**Only when the signature step cannot be used**"):
            self.assertIn(needle, text)
        import PcmanImporter
        refusal = "The download was not verified: %s. Nothing was published." % PcmanImporter.UNVERIFIED_REASON
        self.assertIn(refusal, flat(text))


class PerMachineTests(unittest.TestCase):
    """The installer may install per user: under SYSTEM nobody would get the program. That is the
    first thing a person proves, and the README says it first."""

    def test_the_status_line_begins_with_the_per_machine_question(self):
        status = status_line()
        self.assertTrue(status.startswith("**Status. First thing to prove on a test PC: whether this installer installs "
                                          "for the whole machine when the Cimian client runs it as SYSTEM."))
        for needle in ("NOT read from the vendor, NOT tested", "electron-builder", "`/S`", "`/allusers`", "PER USER",
                       "SYSTEM's profile", "must NOT go into a manifest",
                       "a signed-in standard user gets Scratch after an install by SYSTEM"):
            self.assertIn(needle, status)
        self.assertLess(status.index("PER USER"), status.index("This recipe set is new"))

    def test_the_first_import_marks_the_switches_as_the_writers_knowledge(self):
        raw = read(README)
        command = flat(re.search(r"pcman import ([^`]*?--build)", raw, re.S).group(1))
        self.assertIn("--name scratch", command)
        self.assertIn("--install-arguments '/S /allusers'", command)
        self.assertIn('--display-name "Scratch 3"', command)
        self.assertIn('--developer "Scratch Foundation"', command)
        self.assertIn("--version <the label that the first dry run prints>", command)
        for flag in ("--install-path", "--architectures"):
            self.assertNotIn(flag, command)
        self.assertIn("**writer's knowledge of electron-builder's NSIS installers, NOT read from the vendor and NOT "
                      "tested on a PC**", flat(raw))

    def test_no_recipe_gives_switches(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = read(path)
            for word in ("/allusers", "<key>args</key>", "<key>installer</key>", "/S<"):
                self.assertNotIn(word, text)

    def test_nothing_that_was_not_tested_is_called_tested(self):
        text = flat(read(README))
        for claim in ("was tested on a PC", "the switch is established", "installs per machine.",
                      "Rehearsed on 20", "The rehearsal printed"):
            self.assertNotIn(claim, text)


class ProcessorTests(unittest.TestCase):
    def test_every_named_processor_exists(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            for step in load(path)["Process"]:
                name = step["Processor"]
                if name.startswith(SHARED_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, name[len(SHARED_PREFIX):] + ".py")), name)
                elif name.startswith(PCMAN_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(PCMAN_DIR, name[len(PCMAN_PREFIX):] + ".py")), name)
                elif name not in CORE_PROCESSORS:
                    self.assertTrue(os.path.isfile(os.path.join(RECIPE_DIR, name + ".py")), name)

    def test_the_own_processor_has_no_prefix_and_a_class_of_the_same_name(self):
        self.assertIn("class %s(Processor):" % OWN_PROCESSOR, read(PROVIDER_FILE))
        self.assertEqual(load(DOWNLOAD)["Process"][0]["Processor"], OWN_PROCESSOR)

    def test_the_stub_identifier_is_the_prefix_of_the_processor_names(self):
        stub = load(os.path.join(SHARED_DIR, "SharedProcessors.recipe"))
        self.assertEqual(stub["Identifier"] + "/", SHARED_PREFIX)

    def test_every_argument_is_a_declared_input(self):
        classes = processor_classes()
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            for name, args in named_steps(load(path)):
                for key in args:
                    with self.subTest(recipe=os.path.basename(path), processor=name, argument=key):
                        self.assertIn(key, classes[name].input_variables)

    def test_every_required_input_is_passed_or_comes_from_the_machine(self):
        classes = processor_classes()
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            for name, args in named_steps(load(path)):
                for key, flags in classes[name].input_variables.items():
                    if not flags.get("required") or "default" in flags:
                        continue
                    with self.subTest(recipe=os.path.basename(path), processor=name, input=key):
                        if key in SUPPLIED_BY_THE_MACHINE.get(name, ()):
                            self.assertNotIn(key, args)
                        else:
                            self.assertIn(key, args)

    def test_the_cimian_recipe_names_only_the_shared_importer_and_nothing_of_the_package_tool(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "CimianImporter"])
        text = read(CIMIAN).lower()
        for word in ("pcman", "package tool", "template item"):
            self.assertNotIn(word, text)
        self.assertEqual([step["Processor"] for step in load(PCMAN)["Process"]], [PCMAN_PREFIX + "PcmanImporter"])

    def test_the_inputs_of_the_cimian_recipe(self):
        recipe = load(CIMIAN)
        self.assertEqual(sorted(recipe["Input"]), ["CIMIAN_NAME", "CIMIAN_SUBDIRECTORY", "NAME", "pkginfo"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], "scratch")
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], load(PCMAN)["Input"]["PCMAN_TEMPLATE"])
        self.assertEqual(recipe["Input"]["CIMIAN_SUBDIRECTORY"], "")
        self.assertEqual(recipe["Input"]["NAME"], "Scratch")
        self.assertEqual(recipe["Input"]["pkginfo"], {"display_name": "Scratch 3", "developer": "Scratch Foundation"})
        self.assertEqual(recipe["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": "%version%"})


class HygieneTests(unittest.TestCase):
    def files(self):
        for folder, dirs, files in os.walk(RECIPE_DIR):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if not name.endswith(".pyc"):
                    yield os.path.join(folder, name)

    def test_no_file_holds_a_value_that_belongs_to_one_site(self):
        for path in self.files():
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
            "Scratch-Win.download.recipe", "Scratch.cimian.recipe", "Scratch.pcman.recipe", "ScratchInfoProvider.py",
            "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
            os.path.join("tests", "test_info_provider.py"),
        ]))

    def test_no_file_holds_a_hash(self):
        for path in self.files():
            with self.subTest(path=os.path.relpath(path, RECIPE_DIR)):
                self.assertIsNone(HEX_64.search(read(path)))


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.raw = read(README)
        self.text = flat(self.raw)
        self.generic = self.raw[self.raw.index("## With any Cimian repository"):self.raw.index("## With the package tool (pcman)")]
        self.tool = self.raw[self.raw.index("## With the package tool (pcman)"):self.raw.index("\n## Tests")]

    @staticmethod
    def commands(text, name):
        return [line.strip() for line in text.splitlines() if re.match(r"^\s*autopkg %s\b" % name, line)]

    def test_every_make_override_command_names_an_override_folder(self):
        commands = list(re.finditer(r"autopkg make-override([^`\n]*)", self.raw))
        self.assertEqual(len(commands), 2)
        for match in commands:
            self.assertIn("--override-dir=", match.group(1))

    def test_every_run_and_every_trust_command_carries_the_override_dir_and_the_path(self):
        pattern = re.compile(r"^[ \t]*(autopkg (?:run|verify-trust-info|update-trust-info)\b.*)$", re.M)
        commands = [match.group(1) for match in pattern.finditer(self.raw)]
        self.assertEqual(len([c for c in commands if c.startswith("autopkg run")]), 6)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg verify-trust-info")]), 4)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg update-trust-info")]), 2)
        for command in commands:
            with self.subTest(command=command):
                self.assertRegex(
                    command,
                    r"^autopkg (run|verify-trust-info|update-trust-info)( -vv?)? "
                    r"--override-dir=<the Windows overrides folder> "
                    r"<the Windows overrides folder>/Scratch\.(?:cimian|pcman)\.recipe$",
                )
                self.assertNotIn("com.github.", command)

    def test_no_prose_line_shows_a_full_command_without_the_option(self):
        for match in re.finditer(r"`(autopkg (?:run|verify-trust-info|update-trust-info)[^`]*<[^`]*)`", self.raw):
            self.assertIn("--override-dir=", match.group(1))

    def test_every_command_of_each_way_names_its_own_recipe(self):
        for text, recipe, other in ((self.generic, "Scratch.cimian", "Scratch.pcman"),
                                    (self.tool, "Scratch.pcman", "Scratch.cimian")):
            for name in ("run", "verify-trust-info", "update-trust-info", "make-override"):
                for command in self.commands(text, name):
                    with self.subTest(command=command):
                        self.assertIn(recipe, command)
                        self.assertNotIn(other, command)
            self.assertEqual(len(self.commands(text, "run")), 3)
            self.assertEqual(len(self.commands(text, "make-override")), 1)
            self.assertEqual(len(self.commands(text, "repo-add")), 1)

    def test_the_sections_come_in_the_order_of_the_model(self):
        positions = [self.raw.index(mark) for mark in (
            "**Status.", "| Recipe |", "## What protects, and what does not",
            "## The label is the signed file's version, and the file name is a cross-check",
            "## Run every override with `--override-dir`", "## With any Cimian repository",
            "### 1. What must exist first", "### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER",
            "### 3. First try: a dry run", "### 4. Switch a real run on", "### 5. The real run, the catalogs, the second run",
            "### 6. When a recipe or a processor changes upstream", "### A share that is not mounted",
            "## With the package tool (pcman)", "## a. What must exist first",
            "## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER", "## c. First try: a dry run",
            "## d. Switch a real run on", "## e. The real run, the catalogs, the second run",
            "## f. When a recipe or a processor changes upstream", "## g. A share that is not mounted",
            "## Other facts", "## Tests")]
        self.assertEqual(positions, sorted(positions))

    def test_the_table_has_the_three_recipes(self):
        for name, identifier, word in (
                ("Scratch-Win.download.recipe", "com.github.serrc-techops.download.Scratch-Win", "ScratchInfoProvider"),
                ("Scratch.cimian.recipe", "com.github.serrc-techops.cimian.Scratch", "CimianImporter"),
                ("Scratch.pcman.recipe", "com.github.serrc-techops.pcman.Scratch", "pcman")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)
            self.assertIn(word, rows[0])

    def test_the_parent_recipe_check_names_the_recipe_the_override_was_made_from(self):
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.cimian.Scratch`**", flat(self.generic))
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Scratch`**", flat(self.tool))
        self.assertIn("autopkg list-recipes | grep -i Scratch-Win", self.generic)
        self.assertIn("autopkg list-recipes | grep -i Scratch.pcman", self.tool)

    def test_the_generic_way_names_nothing_of_the_package_tool_to_run(self):
        for word in ("pcman import", "pcman catalogs", "pcman versions", "pcman_root", "pcman_python",
                     "PCMAN_TEMPLATE", "PcmanImporter"):
            self.assertNotIn(word, self.generic)
        self.assertIn("no package tool", self.generic)
        for needle in ("defaults write com.github.autopkg CIMIAN_REPO -string", "Add :Input:cimian_dry_run bool false",
                       "Cimian's `makecatalogs`", "What a person completes by hand for an `.exe`",
                       "StatusService.cs:194-219", "does NOT give the silent arguments",
                       "**The download of this program is verified by its signature**",
                       "**`osslsigncode` on the build machine**"):
            self.assertIn(needle, self.generic)

    def test_the_lines_that_the_generic_way_quotes_are_in_the_processor(self):
        source = read(os.path.join(SHARED_DIR, "CimianImporter.py"))
        for fragment in ("WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on.", "Would write ",
                         "No template: the pkginfo is built from the inputs.", "Nothing new: ", "Published ",
                         "Build the catalogs with makecatalogs."):
            self.assertIn(fragment, source)
            self.assertIn(fragment.strip(), self.generic.replace("`", ""))

    def test_the_lines_that_the_dry_run_quotes_are_the_providers(self):
        processor, messages = _provider_run()
        step = self.raw[self.raw.index("## c."):self.raw.index("## d.")]
        for message in messages:
            self.assertIn(message, step)
        self.assertIn("autopkg run -v --override-dir=", step)
        self.assertIn("`Scratch's download address`", self.text)
        self.assertIn("the recipe never reads an address from another host than `downloads.scratch.mit.edu`", self.text)

    def test_the_label_section_says_where_the_label_comes_from(self):
        heading = "## The label is the signed file's version, and the file name is a cross-check"
        start = self.text.index(heading)
        section = self.text[start:self.text.index("## Run every override")]
        for needle in ("The label that the importers get is the `ProductVersion` of the downloaded file",
                       "after the signature step", "must equal it", "On 2026-11-13 both were `3.32.1`",
                       "NOT established", "A first part of `3` meets neither rule"):
            self.assertIn(needle, section)

    def test_the_readme_says_how_the_address_is_found_and_why_the_name_has_no_space(self):
        for needle in ("reads the `Location` header of that answer and follows no redirect",
                       "Exactly one request is made", "No body is read",
                       "`/desktop/Scratch%20<version>%20Setup.exe`",
                       "no user name, no port, no query and no fragment",
                       "`Scratch-Setup-<version>.exe`", "no space and no `%20` in its name",
                       "`Scratch%203.32.1%20Setup.exe`"):
            self.assertIn(needle, self.text)

    def test_the_status_line_says_what_was_read_and_what_was_not(self):
        status = status_line()
        verified, _, not_established = status.partition("NOT established:")
        self.assertTrue(not_established)
        for needle in ("This recipe set is new and NOT rehearsed: nothing was run under AutoPkg, nothing was downloaded, "
                       "nothing was imported into any repository and nothing was installed on a PC.",
                       "Read on 2026-11-13",
                       "`https://downloads.scratch.mit.edu/desktop/Scratch%20Setup.exe` answered `301` with "
                       "`location: https://downloads.scratch.mit.edu/desktop/Scratch%203.32.1%20Setup.exe`",
                       "`Content-Length` 204843840", "`Last-Modified` 2026-08-12",
                       "`download.bundle.js`", "No hash for the file was found"):
            self.assertIn(needle, verified)
        for needle in ("the version that the installed program reports",
                       "the architecture of the EXE", "any install check",
                       "any install on a PC", "wrote by hand after the real answer of 2026-11-13",
                       "STOP: nothing was written", "Never accept new trust information first"):
            self.assertIn(needle, not_established)
        self.assertIsNone(HEX_64.search(status))

    def test_nothing_in_the_readme_claims_a_run_that_did_not_happen(self):
        for needle in ("NOT printed by this recipe yet", "(Not run: the lines of the output are not known.)",
                       "Expected (not run)", "as a proposal that was NOT run"):
            self.assertIn(needle, self.text)
        self.assertNotRegex(self.text, r"(?i)\bwas rehearsed\b")
        self.assertNotIn("in the form that ran on", self.text)


def _provider_run():
    with mock.patch.object(own, "read_location", return_value=FINAL):
        return _win_support.run_processor(own.ScratchInfoProvider, {})


class ChainTests(_pcman_support.ToolTestCase):
    """The chain with the real processors and the stand-in package tool: the provider (its
    answer made up), a file that stands for the download under the recipe's file name, and
    the importer with the pcman recipe's arguments. Nothing is fetched."""

    def downloaded_file(self, env):
        name = load(DOWNLOAD)["Process"][1]["Arguments"]["filename"].replace("%version%", env["version"])
        path = os.path.join(self.downloads, name)
        with open(path, "wb") as handle:
            handle.write(b"MZ stands for the installer")
        return path

    def steps_run(self):
        processor, _ = _provider_run()
        env = {k: processor.env[k] for k in own.ScratchInfoProvider.output_variables}
        env["pathname"] = self.downloaded_file(env)
        return env

    def importer_env(self, env, **extra):
        values = {"%pathname%": env["pathname"], "%PCMAN_TEMPLATE%": load(PCMAN)["Input"]["PCMAN_TEMPLATE"],
                  "%version%": env["version"]}
        result = {"pathname": env["pathname"], "pcman_root": self.root, "pcman_path": self.msi_bin}
        for name, value in load(PCMAN)["Process"][0]["Arguments"].items():
            result[name] = values.get(value, value)
        result.update(extra)
        return result

    def test_the_label_is_the_version_of_the_file_name(self):
        env = self.steps_run()
        self.assertEqual(env["version"], LABEL)
        self.assertEqual(env["url"], FINAL)
        self.assertEqual(os.path.basename(env["pathname"]), "Scratch-Setup-3.32.1.exe")

    def test_a_real_run_of_the_chain_is_refused_because_nothing_verified_the_file(self):
        run = self.importer_env(self.steps_run(), pcman_dry_run=False)
        self.assertNotIn("checksum_verified", run)
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_pcman_support.importer.PcmanImporter, run)
        self.assertIn("The download was not verified", str(caught.exception))
        self.assertIn("pcman_allow_unverified", str(caught.exception))
        self.assertFalse(self.was_run(), "the tool must not start")

    def test_a_real_run_with_the_signature_steps_output_publishes_as_verified(self):
        self.behave(result=_pcman_support.result_file_content(name="scratch", version=LABEL))
        env = self.steps_run()
        run = self.importer_env(env, pcman_dry_run=False, signature_verified=True,
                                signature_sha256=_win_support.sha256_hex(env["pathname"]))
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, run)
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published")

    def test_the_dry_run_of_the_chain_warns_and_passes_the_label_to_the_tool(self):
        self.behave(result=_pcman_support.result_file_content(result="dry-run", name="scratch", version=LABEL))
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter,
                                                  self.importer_env(self.steps_run()))
        warnings = [m for level, m in processor.message_levels if m.startswith("WARNING:")]
        self.assertTrue(any("the download was NOT verified" in m for m in warnings))
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"],
                         "dry run, nothing written, NOT verified")
        argv = self.record()["argv"]
        self.assertIn("--dry-run", argv)
        self.assertEqual(argv[argv.index("--version") + 1], LABEL)
        self.assertEqual(argv[argv.index("--template") + 1], "scratch")

    def test_the_allowed_real_run_publishes_with_the_label_and_says_not_verified(self):
        self.behave(result=_pcman_support.result_file_content(name="scratch", version=LABEL))
        run = self.importer_env(self.steps_run(), pcman_dry_run=False, pcman_allow_unverified=True)
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, run)
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published, NOT verified")
        argv = self.record()["argv"]
        self.assertEqual(argv[argv.index("--version") + 1], LABEL)


class CimianChainTests(_win_support.RepoTestCase):
    """The chain with the real CimianImporter and a temporary repository."""

    def run_chain(self, label=LABEL, **extra):
        recipe = load(CIMIAN)
        run = {"pathname": self.exe, "version": label}
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

    @_win_support.needs_yaml
    def test_the_chain_with_the_signature_steps_output_publishes_as_verified(self):
        processor, messages = self.run_chain(signature_verified=True, signature_sha256=_win_support.sha256_hex(self.exe))
        self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published")
        self.assertFalse([m for m in messages if "NOT verified" in m or "WITHOUT a verified" in m])

    @_win_support.needs_yaml
    def test_the_chain_is_refused_and_then_publishes_when_allowed(self):
        with self.assertRaises(_win_support.ProcessorError):
            self.run_chain()
        processor, _ = self.run_chain(cimian_allow_unverified=True)
        self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published, NOT verified")
        self.assertEqual(processor.env["cimian_version_imported"], LABEL)
        new = self.read_pkginfo("Example-Chain-%s.yaml" % LABEL)
        self.assertEqual(new["name"], "Example-Chain")
        self.assertEqual(new["display_name"], "Scratch 3")
        self.assertEqual(new["developer"], "Scratch Foundation")
        self.assertEqual(new["installer"]["type"], "exe")
        self.assertEqual(new["installer"]["hash"], _win_support.sha256_hex(self.exe))
        self.assertNotIn("args", new["installer"])

    @_win_support.needs_yaml
    def test_a_second_run_with_the_same_file_has_nothing_new(self):
        self.run_chain(cimian_allow_unverified=True)
        before = self.repo_tree()
        processor, _ = self.run_chain(cimian_allow_unverified=True)
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertEqual(self.repo_tree(), before)


if __name__ == "__main__":
    unittest.main()
