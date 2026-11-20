"""Tests of the three GeoGebra recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names one of our
processors is compared with what that processor declares: the shared ones
(see ../../Win-SharedProcessors and ../../Win-PcmanProcessors) and this
folder's own GeoGebraInfoProvider (tested in test_info_provider.py).

GeoGebra publishes no hash: the download is verified by its Authenticode signature
(the shared AuthenticodeVerifier, tested in its own folder). The tests make sure that the
step is where it belongs, with GeoGebra's name and the pinned roots, that the
Description of every recipe and the README say what it proves and what not, and that
no recipe invents a checksum. The file is an MSI: no recipe passes a version
label, the importers read the MSI's own ProductVersion.

Nothing of this folder was run with AutoPkg, and no installer was downloaded.
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
import GeoGebraInfoProvider as own  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
OWN_PROCESSOR = "GeoGebraInfoProvider"
DOWNLOAD = os.path.join(RECIPE_DIR, "GeoGebra-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "GeoGebra.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "GeoGebra.pcman.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
PROVIDER_FILE = os.path.join(RECIPE_DIR, OWN_PROCESSOR + ".py")
RECIPES = (DOWNLOAD, CIMIAN, PCMAN)
# Processors that are part of AutoPkg itself.
CORE_PROCESSORS = ("URLDownloader", "EndOfCheckPhase")
# Required inputs that a recipe must NOT pass: they come from AutoPkg's
# preferences or the override on the machine that runs it.
SUPPLIED_BY_THE_MACHINE = {"PcmanImporter": {"pcman_root"}, "CimianImporter": {"cimian_repo"}}
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir", "pcman_timeout",
                     "pcman_allow_unverified", "cimian_repo", "cimian_dry_run", "cimian_allow_unverified",
                     "cimian_path", "cimian_catalogs", "cimian_allow_product_change", "checksum_verified",
                     "checksum_sha256", "CIMIAN_REPO")
# What the earlier steps leave in the run (a step reads these without an argument).
SET_BY_CORE_STEPS = {"pathname", "url"}
HEX_64 = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
# File names that recipes of other public repositories might have for the same program.
# They are the writer's guesses, NOT read in any repository: the check is only a guard,
# and the README's `autopkg list-recipes | grep` is the real check on the build machine.
NAMES_OF_OTHER_REPOSITORIES = (
    "GeoGebra.download", "GeoGebra.munki", "GeoGebra.pkg", "GeoGebraClassic6.download",
    "GeoGebra6.download", "GeoGebra-Win64.download", "GeoGebraClassic.download",
)
ADDRESS = "https://download.geogebra.org/installers/6.0/GeoGebra-Windows-Installer-6-0-936-0.msi"


def numbers(*parts):
    """A version of several numbers, built here so that no four small numbers
    stand in this file as they are."""
    return ".".join(str(part) for part in parts)


ADDRESS_VERSION = numbers(6, 0, 936, 0)


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def flat(text):
    return re.sub(r"\s+", " ", text)


def processor_classes():
    import importlib
    classes = {OWN_PROCESSOR: own.GeoGebraInfoProvider}
    for name in ("PcmanImporter", "CimianImporter", "ChecksumVerifier", "GitHubAssetDigest", "AuthenticodeVerifier"):
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


class RecipeFileTests(unittest.TestCase):
    def test_the_three_files_are_valid_property_lists(self):
        for path in RECIPES:
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
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.GeoGebra-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.GeoGebra")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.GeoGebra")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [OWN_PROCESSOR, "URLDownloader", "EndOfCheckPhase", SHARED_PREFIX + "AuthenticodeVerifier"])

    def test_the_provider_has_no_arguments_and_the_recipe_no_input_but_its_name(self):
        recipe = load(DOWNLOAD)
        self.assertEqual(recipe["Process"][0].get("Arguments", {}), {})
        self.assertEqual(recipe["Input"], {"NAME": "GeoGebra"})

    def test_the_downloader_gets_its_address_from_the_provider(self):
        step = load(DOWNLOAD)["Process"][1]
        self.assertEqual(step["Processor"], "URLDownloader")
        self.assertNotIn("url", step.get("Arguments", {}))
        self.assertIn("url", own.GeoGebraInfoProvider.output_variables)

    def test_the_downloader_stores_the_file_under_a_stable_name_that_ends_in_msi(self):
        step = load(DOWNLOAD)["Process"][1]
        self.assertEqual(step["Arguments"], {"filename": "GeoGebra-Windows-Installer-%geogebra_address_version%.msi"})
        name = step["Arguments"]["filename"]
        for variable in re.findall(r"%([A-Za-z_]+)%", name):
            self.assertIn(variable, own.GeoGebraInfoProvider.output_variables)
        made = name.replace("%geogebra_address_version%", ADDRESS_VERSION)
        self.assertEqual(made, "GeoGebra-Windows-Installer-%s.msi" % ADDRESS_VERSION)
        self.assertNotRegex(made, r"[ %/\\]")

    def test_the_provider_outputs_the_address_version_and_no_label_and_no_hash(self):
        outputs = own.GeoGebraInfoProvider.output_variables
        self.assertEqual(sorted(outputs), ["geogebra_address_version", "url"])
        self.assertNotIn('self.env["version"]', read(PROVIDER_FILE))

    def test_no_recipe_passes_a_version_label_for_the_msi(self):
        """For an MSI both importers take the MSI's own ProductVersion. The cimian recipe
        passes an empty `version` so that nothing else in the run is taken for it."""
        for path in (DOWNLOAD, PCMAN):
            text = read(path)
            self.assertNotIn("pcman_version", text)
            self.assertNotIn("%version%", text)
            self.assertNotIn("<key>version</key>", text)
        self.assertEqual(load(CIMIAN)["Process"][0]["Arguments"]["version"], "")
        self.assertNotIn("%version%", read(CIMIAN))
        self.assertNotIn("WindowsExeVersion", read(DOWNLOAD))
        self.assertNotIn("VersionFromName", read(DOWNLOAD))

    def test_every_variable_a_recipe_uses_is_an_input_or_set_by_an_earlier_step(self):
        for path in RECIPES:
            recipe = load(path)
            known = set(recipe["Input"]) | SET_BY_CORE_STEPS
            if path != DOWNLOAD:
                known |= set(load(DOWNLOAD)["Input"]) | set(own.GeoGebraInfoProvider.output_variables)
            for step in recipe["Process"]:
                for value in step.get("Arguments", {}).values():
                    for name in re.findall(r"%([A-Za-z_]+)%", str(value)):
                        with self.subTest(recipe=os.path.basename(path), variable=name):
                            self.assertIn(name, known)
                known |= set(step.get("Arguments", {}))
                if step["Processor"] == OWN_PROCESSOR:
                    known |= set(own.GeoGebraInfoProvider.output_variables)

    def test_the_inputs_of_the_pcman_recipe(self):
        recipe = load(PCMAN)
        self.assertEqual(recipe["Input"], {"NAME": "GeoGebra", "PCMAN_TEMPLATE": "geogebra"})
        self.assertEqual(recipe["Process"][0]["Arguments"],
                         {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%"})

    def test_no_file_name_of_ours_is_the_name_of_a_recipe_in_another_repository(self):
        ours = [os.path.basename(path)[: -len(".recipe")].casefold() for path in RECIPES]
        others = [other.casefold() for other in NAMES_OF_OTHER_REPOSITORIES]
        for name in ours:
            self.assertNotIn(name, others)

    def test_no_stop_on_an_unchanged_download_no_latest_only_no_blocking_applications(self):
        for path in RECIPES:
            text = read(path)
            for word in ("StopProcessingIf", "latest_only", "blocking_applications"):
                self.assertNotIn(word, text)

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in RECIPES:
            text = read(path)
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text)
            for name in ("catalogs", "catalog", "pcman_catalogs", "path", "repo", "directory"):
                self.assertNotIn("<key>%s</key>" % name, text)

    def test_no_value_of_a_recipe_is_a_path_or_a_catalog(self):
        for path in RECIPES:
            recipe = load(path)
            values = [v for v in recipe["Input"].values() if isinstance(v, str)]
            for step in recipe["Process"]:
                values.extend(v for v in step.get("Arguments", {}).values() if isinstance(v, str))
            for value in values:
                with self.subTest(path=os.path.basename(path), value=value):
                    self.assertFalse(value.startswith(("/", "~", ".")), value)
                    self.assertNotIn("\\", value)
                    self.assertNotIn("Production", value)
                    self.assertNotIn("Testing", value)

    def test_the_download_description_says_what_a_reader_must_know(self):
        text = flat(load(DOWNLOAD)["Description"])
        for needle in ("GeoGebraInfoProvider", "Location header of the one answer", "follows no redirect",
                       "may be relative", "no version label", "MSI's own ProductVersion",
                       "6.0.936.0 and the address said 6-0-936-0", "is NOT established",
                       "read from GeoGebra's server on 2026-11-13", "NOT run with AutoPkg",
                       "GeoGebra Classic 6"):
            self.assertIn(needle, text)

    def test_no_description_claims_a_rehearsal_or_a_run(self):
        for path in RECIPES:
            text = flat(load(path)["Description"])
            self.assertNotRegex(text, r"(?i)\brehearsed\b")
            self.assertNotRegex(text, r"(?i)\bwas tried\b")
            self.assertNotRegex(text, r"(?i)\bran on 20")
            self.assertIn("NOT run with AutoPkg", text)


SIGNER = {"CN": "GeoGebra GmbH", "O": "GeoGebra GmbH", "L": "Linz", "ST": "Ober\u00f6sterreich", "C": "AT"}


class SignatureTests(unittest.TestCase):
    """The download is verified by its signature. The step is the last of the download
    recipe, after EndOfCheckPhase, and the recipes say what it proves."""

    def step(self):
        steps = [step for step in load(DOWNLOAD)["Process"] if step["Processor"].endswith("/AuthenticodeVerifier")]
        self.assertEqual(len(steps), 1)
        return steps[0]

    def test_the_step_checks_the_downloaded_file_with_geogebras_name_and_the_pinned_roots(self):
        import AuthenticodeVerifier
        arguments = self.step()["Arguments"]
        self.assertEqual(arguments["pathname"], "%pathname%")
        self.assertEqual(arguments["expected_signer"], SIGNER)
        self.assertEqual(arguments["code_signing_roots"], ["globalsign-code-signing-root-r45"])
        self.assertEqual(arguments["timestamp_roots"], ["globalsign-root-r6"])
        # the vendor's MSI is signed with SHA-1 only; its timestamp authority signs with SHA-384
        self.assertEqual(arguments["digest_algorithms"], ["sha1", "sha384"])
        for name in arguments["code_signing_roots"] + arguments["timestamp_roots"]:
            self.assertIn(name, AuthenticodeVerifier.PINNED_ROOTS)
        self.assertNotIn("osslsigncode_path", arguments)

    def test_the_step_comes_after_the_check_phase_and_last(self):
        names = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(names.index("EndOfCheckPhase") + 1, names.index(SHARED_PREFIX + "AuthenticodeVerifier"))
        self.assertEqual(names[-1], SHARED_PREFIX + "AuthenticodeVerifier")

    def test_the_signature_pair_is_what_both_importers_accept(self):
        import AuthenticodeVerifier
        import CimianImporter
        import PcmanImporter
        outputs = AuthenticodeVerifier.AuthenticodeVerifier.output_variables
        for module in (CimianImporter, PcmanImporter):
            self.assertIn(module.SIGNATURE_FLAG_VARIABLE, outputs)
            self.assertIn(module.SIGNATURE_HASH_VARIABLE, outputs)

    def test_every_description_says_how_the_download_is_verified(self):
        self.assertIn("verified by its Authenticode signature, not by a hash", first_sentence(load(DOWNLOAD)["Description"]))
        for path in (CIMIAN, PCMAN):
            with self.subTest(path=os.path.basename(path)):
                self.assertIn("verified by the signature step of the download recipe",
                              first_sentence(load(path)["Description"]))

    def test_the_download_description_says_what_is_checked_and_what_is_not(self):
        text = flat(load(DOWNLOAD)["Description"])
        for needle in ("GeoGebra publishes no hash", "AuthenticodeVerifier", "CN and O GeoGebra GmbH, L Linz, ST Ober\u00f6sterreich, C AT, and no OU",
                       "globalsign-code-signing-root-r45", "globalsign-root-r6", "uses SHA-1", "move to SHA-256 when GeoGebra does",
                       "MsiDigitalSignatureEx", "the compound file around the streams is not checked", "verified timestamp", "CRLs",
                       "signature_verified and signature_sha256", "does not prove that a release that GeoGebra itself "
                       "signed is harmless", "not the intermediate's", "needs osslsigncode", "NOT run with AutoPkg"):
            self.assertIn(needle, text)

    def test_the_child_descriptions_name_the_flag_of_each_importer_for_a_run_without_the_step(self):
        cimian = flat(load(CIMIAN)["Description"])
        self.assertIn("Without that step CimianImporter refuses a real run unless the override sets "
                      "cimian_allow_unverified to true", cimian)
        self.assertNotIn("pcman", cimian)
        pcman = flat(load(PCMAN)["Description"])
        self.assertIn("pcman_allow_unverified to true", pcman)
        for text in (cimian, pcman):
            self.assertIn("published, NOT verified", text)
            self.assertIn("upgrade code", text)

    def test_no_recipe_sets_the_allowance_or_a_verified_flag_itself(self):
        for path in RECIPES:
            text = read(path)
            for word in ("<key>pcman_allow_unverified</key>", "<key>cimian_allow_unverified</key>",
                         "<key>checksum_verified</key>", "<key>signature_verified</key>",
                         "<key>signature_sha256</key>", "<key>checksum_sha256</key>"):
                self.assertNotIn(word, text)

    def test_no_recipe_invents_a_checksum_step(self):
        for path in RECIPES:
            text = read(path)
            for word in ("ChecksumVerifier", "GitHubAssetDigest", "expected_sha256", "CodeSignatureVerifier"):
                self.assertNotIn(word, text)
            self.assertIsNone(HEX_64.search(text))

    def test_the_readme_opens_with_a_bold_status_line(self):
        lines = [line for line in read(README).splitlines() if line.strip()]
        self.assertEqual(lines[0], "# Win-GeoGebra")
        self.assertTrue(lines[1].startswith("A Windows recipe pair"))
        status = lines[2]
        self.assertTrue(status.startswith("**Status. First written on 2026-11-13, before any run;"), status[:60])
        self.assertTrue(status.endswith("**"))
        for needle in ("the paragraph \"Results of 2026-11-13\" below is newer and holds where the two differ",
                       "verified by its signature, not by a hash",
                       "`AuthenticodeVerifier`", "That step was NOT run with AutoPkg"):
            self.assertIn(needle, status)

    def test_the_readme_says_what_the_signature_proves_and_what_not(self):
        text = flat(read(README))
        for needle in ("**The download is verified by its signature.**", "`CN=GeoGebra GmbH`", "`O=GeoGebra GmbH`",
                       "`L=Linz`", "`ST=Ober\u00f6sterreich`", "`C=AT`", "and no `OU`", "`globalsign-code-signing-root-r45`", "`globalsign-root-r6`",
                       "**Checked on 2026-11-19**", "the digest is SHA-1", "The recipe should move to SHA-256 when\nGeoGebra does".replace("\n", " "),
                       "a collision needs GeoGebra to sign content that the attacker prepared",
                       "not necessarily every byte of the file", "**An older release, signed for real.**",
                       "It does not refuse an older version", "an older one that is still valid can be handed over",
                       "the step stops the run until a person has looked and changed the recipe",
                       "the same file with one byte changed was refused",
                       "a bad release that GeoGebra itself signed passes",
                       "only the signing certificate's CRL is read",
                       "**The step needs `osslsigncode`**", "The address.",
                       "It does not show what the file at that address is.", "The same product.", "upgrade code",
                       "Without the signature step, an MSI of the right product with other content",
                       "would pass all of these."):
            self.assertIn(needle, text)

    def test_the_real_run_steps_need_only_the_dry_run_switch(self):
        text = read(README)
        self.assertIn("### 4. Switch a real run on\n", text)
        self.assertIn("## d. Switch a real run on\n", text)
        self.assertNotIn("NOT YET", text)
        self.assertIn("That one line is enough: the signature step verifies the download.", flat(text))
        self.assertIn("The signature step verifies the download, so one line in the override is enough", flat(text))

    def test_the_hand_command_uses_the_template_and_no_version(self):
        text = read(README)
        match = re.search(r"\(`(pcman import <the file> --template\s+geogebra)`", text)
        self.assertTrue(match)
        self.assertNotIn("--version", match.group(1))
        first_imports = list(re.finditer(r"pcman import [^`]*?--name", text))
        self.assertEqual(len(first_imports), 1)
        self.assertLess(first_imports[0].start(), text.index("## b."))

    def test_the_override_lines_that_allow_an_unverified_run_are_kept_for_a_run_without_the_step(self):
        text = read(README)
        for needle in ("Add :Input:pcman_dry_run bool false", "Add :Input:pcman_allow_unverified bool true",
                       "Add :Input:cimian_dry_run bool false", "Add :Input:cimian_allow_unverified bool true",
                       "Both lines are needed", "published, NOT verified", "published WITHOUT a verified download",
                       "**Without the signature step**", "**Only when the signature step cannot be used**"):
            self.assertIn(needle, text)
        import PcmanImporter
        refusal = "The download was not verified: %s. Nothing was published." % PcmanImporter.UNVERIFIED_REASON
        self.assertIn(refusal, flat(text))


class ProcessorTests(unittest.TestCase):
    def test_every_named_processor_exists(self):
        for path in RECIPES:
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

    def test_the_stub_identifiers_are_the_prefixes_of_the_processor_names(self):
        self.assertEqual(load(os.path.join(SHARED_DIR, "SharedProcessors.recipe"))["Identifier"] + "/", SHARED_PREFIX)
        self.assertEqual(load(os.path.join(PCMAN_DIR, "PcmanProcessors.recipe"))["Identifier"] + "/", PCMAN_PREFIX)

    def test_every_argument_is_a_declared_input(self):
        classes = processor_classes()
        for path in RECIPES:
            for name, args in named_steps(load(path)):
                for key in args:
                    with self.subTest(recipe=os.path.basename(path), processor=name, argument=key):
                        self.assertIn(key, classes[name].input_variables)

    def test_every_required_input_is_passed_or_comes_from_the_machine(self):
        classes = processor_classes()
        for path in RECIPES:
            for name, args in named_steps(load(path)):
                for key, flags in classes[name].input_variables.items():
                    if not flags.get("required") or "default" in flags:
                        continue
                    with self.subTest(recipe=os.path.basename(path), processor=name, input=key):
                        if key in SUPPLIED_BY_THE_MACHINE.get(name, ()):
                            self.assertNotIn(key, args)
                        else:
                            self.assertIn(key, args)


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
            "GeoGebra-Win.download.recipe", "GeoGebra.cimian.recipe", "GeoGebra.pcman.recipe",
            "GeoGebraInfoProvider.py", "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
            os.path.join("tests", "test_info_provider.py"), os.path.join("tests", "index_excerpt.html"),
        ]))

    def test_no_file_holds_a_hash(self):
        for path in self.files():
            with self.subTest(path=os.path.basename(path)):
                self.assertIsNone(HEX_64.search(read(path)))


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.raw = read(README)
        self.text = flat(self.raw)

    def test_every_make_override_command_names_an_override_folder(self):
        commands = list(re.finditer(r"autopkg make-override([^`\n]*)", self.raw))
        self.assertEqual(len(commands), 2)
        for match in commands:
            self.assertIn("--override-dir=", match.group(1))

    def test_no_run_of_a_recipe_identifier(self):
        runs = list(re.finditer(r"autopkg run([^`\n]*)", self.raw))
        self.assertTrue(runs)
        for match in runs:
            self.assertNotIn("com.github.", match.group(1))

    def operator_commands(self):
        pattern = re.compile(r"^ {4,}(autopkg (?:run|verify-trust-info|update-trust-info)\b.*)$", re.M)
        return [match.group(1) for match in pattern.finditer(self.raw)]

    def test_every_run_and_every_trust_command_carries_the_override_dir_and_the_path(self):
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
                    r"<the Windows overrides folder>/GeoGebra\.(?:cimian|pcman)\.recipe$",
                )

    def test_no_autopkg_command_line_is_missed_by_the_indent_rule(self):
        pattern = r"^[ \t]*autopkg (?:run|verify-trust-info|update-trust-info)\b"
        self.assertEqual(len(re.findall(pattern, self.raw, re.M)), len(self.operator_commands()))
        self.assertEqual(len(re.findall(r"autopkg run ", self.raw)), 6)

    def test_no_prose_line_shows_a_full_command_without_the_option(self):
        for match in re.finditer(r"`(autopkg (?:run|verify-trust-info|update-trust-info)[^`]*<[^`]*)`", self.raw):
            self.assertIn("--override-dir=", match.group(1))

    def test_the_readme_states_no_hash(self):
        self.assertIsNone(HEX_64.search(self.raw))

    def test_a_bold_paragraph_says_why_and_what_to_do_when_the_warning_appears(self):
        i = self.raw.index("## Run every override with `--override-dir`")
        paragraph = flat(self.raw[i:i + 2500])
        for needle in ("**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`",
                       "skips the trust check with one warning line", "is missing trust info",
                       "a changed processor is not caught",
                       "If that line ever appears in a run of an override, stop: the run was not checked.**",
                       "`FAIL_RECIPES_WITHOUT_TRUST_INFO`", "owner's decision"):
            self.assertIn(needle, paragraph)

    def test_the_sections_come_in_the_order_of_the_model(self):
        positions = [self.raw.index(mark) for mark in (
            "**Status.", "| Recipe |", "**Three recipes.**", "How strict the processor is:",
            "## What protects, and what does not",
            "## The label is the MSI's version, and nothing compares it with the address's",
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

    def test_the_status_line_lists_what_was_read_and_what_was_not(self):
        status = flat([line for line in self.raw.splitlines() if line.startswith("**Status.")][0])
        read_part, _, not_established = status.partition("NOT established:")
        self.assertTrue(not_established)
        for needle in ("Read by the writer on 2026-11-13",
                       "`https://download.geogebra.org/package/win-msi6` answered 302 with the relative Location "
                       "`/installers/6.0/GeoGebra-Windows-Installer-6-0-936-0.msi`",
                       "the Classic 5 EXE, which this recipe does not use",
                       "lists four MSIs", "`version.txt`, whose content was `6-0-936-0`",
                       "it lists no hash, checksum or signature file",
                       "`msiexec /i <the MSI> ALLUSERS=2 /qn`", "mass installations of Classic 6 do not update themselves",
                       "GeoGebra non-commercial license", "the licence text itself was NOT read"):
            self.assertIn(needle, read_part)
        for needle in ("whether later MSIs keep the four numbers of their address", "the MSI's UpgradeCode", "the MSI's platform",
                       "without `ALLUSERS=2`", "the install path", "does not update itself",
                       "folder `6.0`",
                       "a run with this recipe's signature step under AutoPkg", "an install through a Cimian client",
                       "wrote by hand after the real answer of 2026-11-13", "STOP: nothing was written",
                       "Never accept new trust information first"):
            self.assertIn(needle, not_established)
        self.assertIsNone(HEX_64.search(status))

    def test_nothing_in_the_readme_claims_a_run_that_did_not_happen(self):
        self.assertNotRegex(self.text, r"(?i)rehearsed on 20")
        self.assertNotRegex(self.text, r"(?i)\bwas rehearsed\b")
        self.assertNotRegex(self.text, r"Run on 20")
        self.assertNotIn("in the form that ran on", self.text)
        for needle in ("Expected, from the code and the runs of other folders, NOT printed by this recipe yet",
                       "(Not run: the lines of the output are not known.)", "Expected (not run)",
                       "(NOT run for this program)"):
            self.assertIn(needle, self.text)

    def test_the_readme_says_how_the_address_is_found_and_how_strict_the_processor_is(self):
        for needle in ("reads the `Location` header of that answer and follows no redirect",
                       "Exactly one request is made", "No body is read",
                       "A relative `Location` is resolved against the fixed address",
                       "`/installers/6.0/GeoGebra-Windows-Installer-<n>-<n>-<n>-<n>.msi`",
                       "no user name, no port, no query and no fragment",
                       "also a new folder such as `6.1`",
                       "It outputs no hash, because GeoGebra publishes none, and no `version`",
                       "`GeoGebra-Windows-Installer-<version of the address>.msi`"):
            self.assertIn(needle, self.text)

    def test_the_readme_tells_the_reader_to_compare_the_two_versions(self):
        section = self.text[self.text.index("## The label is the MSI's version"):self.text.index("## Run every override")]
        for needle in ("No step of this recipe compares it with the four numbers of the address",
                       "On 2026-11-13 the MSI's ProductVersion was `6.0.936.0`", "A person checks it, at the first dry run",
                       "with `-v`", "stop and tell the owner before anything is published",
                       "After the first install on a test PC"):
            self.assertIn(needle, section)
        self.assertIn("**Read the two versions.**", self.text)

    def test_the_readme_says_that_the_redirect_rule_is_a_stop(self):
        for needle in ("`GeoGebra's download address`", "stop and tell the owner",
                       "the recipe never reads an address from another host than GeoGebra's one fixed one"):
            self.assertIn(needle, self.text)

    def test_the_first_import_has_no_version_and_names_the_fields(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        self.assertTrue(match)
        command = flat(match.group(1))
        self.assertIn("--name geogebra", command)
        self.assertNotIn("--version", command)
        self.assertNotIn("--install-path", command)
        self.assertNotIn("--install-arguments", command)
        for flag in ('--display-name "GeoGebra Classic 6"', "--category", '--developer "GeoGebra"', "--description",
                     "--architectures <the MSI's platform>", "--no-prompt", "--icon"):
            self.assertIn(flag, command)

    def test_the_vendors_allusers_property_is_named_and_left_to_a_person(self):
        for needle in ("GeoGebra's page on mass installation adds `ALLUSERS=2` to its silent command",
                       "a person decides after the first test PC whether the item needs `ALLUSERS=2`",
                       "whether the package tool can carry that property for an MSI was NOT established"):
            self.assertIn(needle, self.text)
        for path in RECIPES:
            self.assertNotIn("ALLUSERS", read(path))

    def test_the_name_check_and_the_parent_check_are_in_step_b(self):
        step = self.raw[self.raw.index("## b."):self.raw.index("## c.")]
        self.assertIn("autopkg list-recipes | grep -i GeoGebra-Win", step)
        self.assertIn("autopkg list-recipes | grep -i GeoGebra.pcman", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.GeoGebra`", flat(step))
        self.assertIn("(`GeoGebraInfoProvider`, `PcmanImporter`)", flat(step))


class CimianReadmeTests(unittest.TestCase):
    def setUp(self):
        self.raw = read(README)
        self.generic = self.raw[self.raw.index("## With any Cimian repository"):self.raw.index("## With the package tool (pcman)")]
        self.tool = self.raw[self.raw.index("## With the package tool (pcman)"):self.raw.index("\n## Tests")]

    @staticmethod
    def commands(text, name):
        return [line.strip() for line in text.splitlines() if re.match(r"^\s*autopkg %s\b" % name, line)]

    def test_the_table_has_the_three_recipes(self):
        for name, identifier in (("GeoGebra-Win.download.recipe", "com.github.serrc-techops.download.GeoGebra-Win"),
                                 ("GeoGebra.cimian.recipe", "com.github.serrc-techops.cimian.GeoGebra"),
                                 ("GeoGebra.pcman.recipe", "com.github.serrc-techops.pcman.GeoGebra")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)

    def test_each_way_has_its_steps_and_names_only_its_own_recipe(self):
        for text, recipe, other in ((self.generic, "GeoGebra.cimian", "GeoGebra.pcman"),
                                    (self.tool, "GeoGebra.pcman", "GeoGebra.cimian")):
            self.assertEqual(len(self.commands(text, "run")), 3)
            self.assertEqual(len(self.commands(text, "verify-trust-info")), 2)
            self.assertEqual(len(self.commands(text, "update-trust-info")), 1)
            self.assertEqual(len(self.commands(text, "make-override")), 1)
            self.assertEqual(len(self.commands(text, "repo-add")), 1)
            for name in ("run", "verify-trust-info", "update-trust-info", "make-override"):
                for command in self.commands(text, name):
                    with self.subTest(command=command):
                        self.assertIn("--override-dir=", command)
                        self.assertIn(recipe, command)
                        self.assertNotIn(other, command)

    def test_the_generic_way_names_nothing_of_the_package_tool_to_run(self):
        for word in ("pcman import", "pcman catalogs", "pcman versions", "pcman_root", "pcman_python",
                     "PCMAN_TEMPLATE", "PcmanImporter"):
            self.assertNotIn(word, self.generic)
        self.assertIn("no package tool", self.generic)

    def test_the_generic_way_gives_the_preference_the_switch_the_msi_tool_and_the_catalogs(self):
        for needle in ("defaults write com.github.autopkg CIMIAN_REPO -string", "Add :Input:cimian_dry_run bool false",
                       "Cimian's `makecatalogs`", "`CIMIAN_NAME`, `geogebra`", "`CIMIAN_SUBDIRECTORY`",
                       "`msiinfo`", "This recipe cannot run without it",
                       "an argument of a step wins over an override's `Input`",
                       "For an `.msi` nothing needs completing for a silent install", "InstallerService.cs:936-948",
                       "`cimian_allow_product_change`", "or that has none where the template's item had one",
                       "The recipe's `pkginfo` does not change a template", "`cimian_pkginfo_wins`",
                       "windowsadmins/cimian", "e10498b",
                       "`ParentRecipe`: it must be `com.github.serrc-techops.cimian.GeoGebra`**",
                       "do not run two runs of one item at the same time"):
            self.assertIn(needle, self.generic.replace("\n", " ") if "**" in needle else self.generic)

    def test_the_lines_that_the_generic_way_quotes_are_in_the_processor(self):
        source = read(os.path.join(SHARED_DIR, "CimianImporter.py"))
        for fragment in ("WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on.", "Would write ",
                         "No template: the pkginfo is built from the inputs.", "Nothing new: ", "Published ",
                         "Build the catalogs with makecatalogs."):
            self.assertIn(fragment, source)
            self.assertIn(fragment.strip(), self.generic.replace("`", ""))

    def test_the_generic_way_says_that_the_signature_verifies_and_needs_the_tool(self):
        self.assertIn("**The download of this program is verified by its signature**", self.generic)
        self.assertIn("**`osslsigncode` on the build machine**", self.generic)
        self.assertLess(self.generic.index("Add :Input:cimian_dry_run bool false"),
                        self.generic.index("Add :Input:cimian_allow_unverified bool true"))

    def test_the_package_tools_way_says_the_tool_is_not_in_this_repository(self):
        self.assertIn("**not part of this repository**", self.tool)
        self.assertIn("`PcmanImporter` of `../Win-PcmanProcessors/`", self.tool)


class ChainTests(_pcman_support.ToolTestCase):
    """The chain with the real provider (its answer made up), a file that stands for the
    downloaded MSI, and the real PcmanImporter with the pcman recipe's arguments against
    the stand-in package tool. Nothing is fetched."""

    def provider_run(self):
        with mock.patch.object(own, "read_location",
                               side_effect=lambda url, what: "https://download.geogebra.org"
                               "/installers/6.0/GeoGebra-Windows-Installer-6-0-936-0.msi"):
            processor, _ = _win_support.run_processor(own.GeoGebraInfoProvider, {})
        return processor

    def downloaded_file(self):
        """What URLDownloader would leave, under the recipe's file name."""
        provider = self.provider_run()
        name = load(DOWNLOAD)["Process"][1]["Arguments"]["filename"].replace(
            "%geogebra_address_version%", provider.env["geogebra_address_version"])
        path = os.path.join(self.downloads, name)
        with open(path, "wb") as handle:
            handle.write(b"stands for an MSI")
        return path, provider

    def importer_env(self, path, **extra):
        values = {"%pathname%": path, "%PCMAN_TEMPLATE%": load(PCMAN)["Input"]["PCMAN_TEMPLATE"]}
        result = {"pathname": path, "pcman_root": self.root, "pcman_path": self.msi_bin}
        for name, value in load(PCMAN)["Process"][0]["Arguments"].items():
            result[name] = values.get(value, value)
        result.update(extra)
        return result

    def test_the_provider_gives_the_address_and_the_file_ends_in_msi(self):
        path, provider = self.downloaded_file()
        self.assertEqual(provider.env["url"], ADDRESS)
        self.assertEqual(provider.env["geogebra_address_version"], ADDRESS_VERSION)
        self.assertTrue(path.endswith(".msi"))

    def test_a_real_run_of_the_chain_is_refused_because_nothing_verified_the_file(self):
        path, _ = self.downloaded_file()
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_pcman_support.importer.PcmanImporter, self.importer_env(path, pcman_dry_run=False))
        self.assertIn("The download was not verified", str(caught.exception))
        self.assertIn("pcman_allow_unverified", str(caught.exception))
        self.assertFalse(self.was_run(), "the tool must not start")

    def signed(self, path):
        """What the signature step leaves in the run for this file."""
        return {"signature_verified": True, "signature_sha256": _win_support.sha256_hex(path)}

    def test_a_real_run_with_the_signature_steps_output_publishes_as_verified(self):
        path, _ = self.downloaded_file()
        self.behave(result=_pcman_support.result_file_content(name="geogebra", version="9.9.9"))
        processor, _ = _win_support.run_processor(
            _pcman_support.importer.PcmanImporter, self.importer_env(path, pcman_dry_run=False, **self.signed(path)))
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published")

    def test_the_dry_run_without_the_signature_step_warns_and_passes_no_version(self):
        path, _ = self.downloaded_file()
        self.behave(result=_pcman_support.result_file_content(result="dry-run", name="geogebra", version="9.9.9"))
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, self.importer_env(path))
        warnings = [m for level, m in processor.message_levels if m.startswith("WARNING:")]
        self.assertTrue(any("the download was NOT verified" in m for m in warnings))
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"],
                         "dry run, nothing written, NOT verified")
        argv = self.record()["argv"]
        self.assertIn("--dry-run", argv)
        self.assertNotIn("--version", argv)
        self.assertEqual(argv[argv.index("--template") + 1], "geogebra")

    def test_the_allowed_real_run_publishes_and_says_not_verified(self):
        path, _ = self.downloaded_file()
        self.behave(result=_pcman_support.result_file_content(name="geogebra", version="9.9.9"))
        processor, _ = _win_support.run_processor(
            _pcman_support.importer.PcmanImporter,
            self.importer_env(path, pcman_dry_run=False, pcman_allow_unverified=True))
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published, NOT verified")
        self.assertNotIn("--version", self.record()["argv"])


class CimianChainTests(_win_support.RepoTestCase):
    """The chain with the real CimianImporter and a temporary repository."""

    def run_chain(self, tag="9.9.9", **extra):
        """What the recipe's step is given, with the substitutions that AutoPkg makes. `tag` is
        a `version` that something earlier may have left in the run: the empty argument wins."""
        recipe = load(CIMIAN)
        run = {"pathname": self.msi, "version": tag}
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
    def test_a_real_run_with_the_signature_steps_output_publishes_as_verified(self):
        processor, messages = self.run_chain(signature_verified=True, signature_sha256=_win_support.sha256_hex(self.msi))
        self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published")
        self.assertFalse([m for m in messages if "NOT verified" in m or "WITHOUT a verified" in m])

    @_win_support.needs_yaml
    def test_a_real_run_is_refused_and_the_allowed_one_publishes_not_verified(self):
        with self.assertRaises(_win_support.ProcessorError) as caught:
            self.run_chain()
        self.assertIn("The download was not verified", str(caught.exception))
        processor, _ = self.run_chain(cimian_allow_unverified=True)
        self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published, NOT verified")
        new = self.read_pkginfo("Example-Chain-%s.yaml" % processor.env["cimian_version_imported"])
        self.assertEqual(new["name"], "Example-Chain")
        self.assertEqual(new["display_name"], "GeoGebra Classic 6")
        self.assertEqual(new["developer"], "GeoGebra")
        self.assertEqual(new["installer"]["type"], "msi")
        self.assertEqual(new["installer"]["hash"], _win_support.sha256_hex(self.msi))

    @_win_support.needs_yaml
    def test_the_version_is_the_msis_own_and_not_what_the_run_held(self):
        self.msiinfo_says(stdout=_win_support.property_export(version="2.5.0"))
        processor, _ = self.run_chain(tag="9.9.9", cimian_allow_unverified=True)
        self.assertEqual(processor.env["cimian_version_imported"], "2.5.0")

    @_win_support.needs_yaml
    def test_a_second_run_with_the_same_file_has_nothing_new(self):
        self.run_chain(cimian_allow_unverified=True)
        before = self.repo_tree()
        processor, _ = self.run_chain(cimian_allow_unverified=True)
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertEqual(self.repo_tree(), before)


if __name__ == "__main__":
    unittest.main()
