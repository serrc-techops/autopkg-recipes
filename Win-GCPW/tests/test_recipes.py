"""Tests of the two GCPW recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. The step that names our shared
processor is compared with what that processor declares (see
../../Win-SharedProcessors). The shared folder's tests are run separately.

The download of this program has NO hard check (no vendor hash, no signature
check). The tests make sure that nobody can overlook that: the Description of
both recipes and the top of the README say it, and no recipe invents a check.

Nothing of this folder was rehearsed with AutoPkg. Some facts of the source were
fetched by the writer on 2026-10-02 (the address, the size of the two files): the
README's first paragraph says which, and a test checks it.
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
if SHARED_TESTS_DIR not in sys.path:
    sys.path.insert(0, SHARED_TESTS_DIR)

if PCMAN_TESTS_DIR not in sys.path:
    sys.path.insert(0, PCMAN_TESTS_DIR)

import _win_support  # noqa: E402,F401  (installs the autopkglib stand-in, imports the processors)
import _pcman_support  # noqa: E402,F401  (the stand-in for the package tool, and its processor)
import test_public_repository as shared_hygiene  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "GCPW-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "GCPW.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "GCPW.pcman.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
# Processors that are part of AutoPkg itself.
CORE_PROCESSORS = ("URLDownloader", "EndOfCheckPhase")
# Required inputs that a recipe must NOT pass: they come from AutoPkg's
# preferences or the override on the machine that runs it.
SUPPLIED_BY_THE_MACHINE = {"PcmanImporter": {"pcman_root"}}
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir", "pcman_timeout")
HEX_64 = re.compile(r"(?i)\b[0-9a-f]{64}\b")
# File names of recipes in repositories that the build machine has (read in the
# survey of the earlier readings). AutoPkg takes the first match by name and says
# nothing, so none of our file names may be one of these.
NAMES_OF_OTHER_REPOSITORIES = (
    "Zoom-Win.download", "Zoom64-Win.download", "GoogleChrome-Win.download", "GoogleChrome-Win64.download",
    "7zip-Win64.download", "Zoom.munki", "GoogleChrome.munki", "Zoom.download", "GoogleChrome.download",
    "GCPW.download", "GCPW.munki", "GoogleCredentialProviderforWindows.download",
)


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def processor_classes():
    import importlib
    classes = {}
    for name in ("PcmanImporter", "CimianImporter", "ChecksumVerifier", "GitHubAssetDigest"):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def shared_steps(recipe):
    """The steps that name a processor of this repository, of either folder: (name, arguments)."""
    for step in recipe["Process"]:
        for prefix in (SHARED_PREFIX, PCMAN_PREFIX):
            if step["Processor"].startswith(prefix):
                yield step["Processor"][len(prefix):], step.get("Arguments", {})


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

    def test_identifiers_and_parent(self):
        download, cimian = load(DOWNLOAD), load(PCMAN)
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.GCPW-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".pcman.GCPW")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, ["URLDownloader", "EndOfCheckPhase"])

    def test_the_pcman_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(PCMAN)["Process"]]
        self.assertEqual(steps, [PCMAN_PREFIX + "PcmanImporter"])

    def test_the_downloader_arguments(self):
        recipe = load(DOWNLOAD)
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args["url"], "%DOWNLOAD_URL%")
        self.assertEqual(recipe["Input"]["DOWNLOAD_URL"], "https://dl.google.com/credentialprovider/gcpwstandaloneenterprise64.msi")
        self.assertTrue(recipe["Input"]["DOWNLOAD_URL"].startswith("https://"))

    def test_the_file_name_of_the_address_ends_in_msi_so_no_file_name_is_set(self):
        recipe = load(DOWNLOAD)
        url = recipe["Input"]["DOWNLOAD_URL"]
        self.assertNotIn("?", url)
        self.assertTrue(url.rsplit("/", 1)[-1].endswith(".msi"))
        self.assertNotIn("filename", recipe["Process"][0]["Arguments"])

    def test_the_address_is_the_64_bit_enterprise_installer_and_not_the_32_bit_one(self):
        url = load(DOWNLOAD)["Input"]["DOWNLOAD_URL"]
        self.assertEqual(url.rsplit("/", 1)[-1], "gcpwstandaloneenterprise64.msi")
        self.assertTrue(url.startswith("https://dl.google.com/credentialprovider/"))
        self.assertNotEqual(url.rsplit("/", 1)[-1], "gcpwstandaloneenterprise.msi")

    def test_the_download_recipe_has_no_parent(self):
        self.assertNotIn("ParentRecipe", read(DOWNLOAD))

    def test_the_download_description_says_what_was_fetched_and_what_was_not_rehearsed(self):
        text = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        self.assertIn("The address and the size of the file were read by the writer on 2026-10-02", text)
        self.assertIn("this recipe was NOT rehearsed with AutoPkg", text)
        self.assertIn("the first run on the build machine is the check of the rest", text)

    def test_the_pcman_description_says_that_the_template_name_is_a_placeholder(self):
        text = re.sub(r"\s+", " ", load(PCMAN)["Description"])
        self.assertIn("The template name in this recipe, gcpw, is a placeholder", text)
        self.assertIn("the override's PCMAN_TEMPLATE must name it", text)
        self.assertIn("This recipe was NOT rehearsed with AutoPkg", text)

    def test_no_description_claims_a_rehearsal(self):
        for path in (DOWNLOAD, PCMAN):
            text = load(path)["Description"]
            self.assertNotIn("Rehearsed", text)
            self.assertNotIn("rehearsed on", text)

    def test_the_inputs_of_the_pcman_recipe(self):
        recipe = load(PCMAN)
        self.assertEqual(recipe["Input"]["NAME"], "GCPW")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "gcpw")
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%"})

    def test_no_file_name_of_ours_is_the_name_of_a_recipe_in_another_repository(self):
        ours = [name[: -len(".recipe")].casefold() for name in (os.path.basename(DOWNLOAD), os.path.basename(PCMAN))]
        for other in NAMES_OF_OTHER_REPOSITORIES:
            self.assertNotIn(other.casefold(), ours)
        for name in ours:
            self.assertNotIn(name, [other.casefold() for other in NAMES_OF_OTHER_REPOSITORIES])

    def test_the_template_name_is_the_placeholder_that_the_readme_names(self):
        self.assertEqual(load(PCMAN)["Input"]["PCMAN_TEMPLATE"], "gcpw")

    def test_no_pcman_version_in_an_msi_recipe(self):
        """For an MSI the package tool takes the MSI's own ProductVersion. A
        label from the recipe would be refused or would hide the real version."""
        for path in (DOWNLOAD, PCMAN):
            text = read(path)
            self.assertNotIn("pcman_version", text)
            self.assertNotIn("<key>version</key>", text)
        for step in load(PCMAN)["Process"]:
            self.assertNotIn("pcman_version", step.get("Arguments", {}))
            self.assertNotIn("%version%", str(step.get("Arguments", {})))

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

    def test_the_pcman_description_names_what_still_protects(self):
        text = re.sub(r"\s+", " ", load(PCMAN)["Description"])
        self.assertIn("upgrade code", text)
        self.assertIn("a label that is not the MSI's own version", text)
        self.assertIn("pcman_dry_run", text)
        self.assertIn("dry run", text)

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

    def test_no_recipe_invents_a_checksum_step(self):
        for path in (DOWNLOAD, PCMAN):
            text = read(path)
            self.assertNotIn("ChecksumVerifier", text)
            self.assertNotIn("expected_sha256", text)
            self.assertNotIn("sha256", text.lower())
            self.assertIsNone(HEX_64.search(text))
            self.assertNotIn("CodeSignatureVerifier", text)

    def test_the_readme_opens_with_a_status_line_and_a_not_verified_line_both_bold(self):
        lines = [line for line in read(README).splitlines() if line.strip()]
        self.assertTrue(lines[0].startswith("# "))
        self.assertTrue(lines[1].startswith("A Windows recipe pair"))
        status, not_verified = lines[2], lines[3]
        self.assertTrue(status.startswith("**Status. Run on 2026-10-04 under AutoPkg 2.9.0, as follows."), status[:100])
        self.assertTrue(status.endswith("**"))
        self.assertTrue(not_verified.startswith("**Not verified. The download is NOT verified:"), not_verified[:60])
        self.assertTrue(not_verified.endswith("**"))
        for needle in ("signature check", "REFUSES a real run", "pcman_allow_unverified",
                       "Do not set it before the signature check exists",
                       "pcman import <file> --template gcpw", "no `--version` for an MSI",
                       "A real run of this recipe was REFUSED on 2026-10-04 (see the status line above), and nothing has been installed on a PC"):
            self.assertIn(needle, not_verified)
        self.assertNotIn("has NOT been run by anyone", status)
        self.assertNotIn("has NOT been run by anyone", not_verified)

    def test_the_status_line_says_what_was_fetched_and_what_was_not_established(self):
        status = [line for line in read(README).splitlines() if line.startswith("**Status.")][0]
        text = re.sub(r"\s+", " ", status)
        for needle in (
                "Some facts of the source were fetched by the writer on 2026-10-02, before those runs:",
                "`https://dl.google.com/credentialprovider/gcpwstandaloneenterprise64.msi` answered 200 with no redirect, "
                "47382528 bytes, last modified 2026-10-02 08:45 GMT",
                "`gcpwstandaloneenterprise.msi`, is 25264128 bytes",
                "the recipe takes the 64-bit file only",
                "NOT established: that Google publishes no hash for this file",
                "that Google publishes no hash for this file",
                "the writer knows of none",
                "that Google's server answers the questions that AutoPkg asks about a changed file",
                "the silent install of the MSI on a PC",
                "The first install on a test PC is the check of what is NOT established",
                "When a run fails, STOP: nothing was written",
                "correct the recipe, and only then look at the trust information",
                "Never accept new trust information first"):
            self.assertIn(needle, text)
        self.assertNotIn("Rehearsed on", read(README))
        for gone in ("its name is not known to the writer", "`gcpw` in the recipe is a PLACEHOLDER", "any run with AutoPkg"):
            self.assertNotIn(gone, text)

    def test_the_readme_says_how_to_find_and_set_the_real_template_name(self):
        text = re.sub(r"\s+", " ", read(README))
        self.assertIn("Find out first whether one exists now", text)
        self.assertIn("pcman versions <a name>", text)
        self.assertIn("do not make a second item", text)
        self.assertIn("Set :Input:PCMAN_TEMPLATE <the name of the item>", text)
        self.assertIn("set it in the override, not in the recipe", text)
        self.assertLess(text.index("Find out first whether one exists now"), text.index("## b."))
        self.assertGreater(text.index("Set :Input:PCMAN_TEMPLATE"), text.index("## b."))
        self.assertLess(text.index("Set :Input:PCMAN_TEMPLATE"), text.index("## c."))

    def test_the_readme_says_what_still_protects_and_that_it_is_not_enough(self):
        text = re.sub(r"\s+", " ", read(README))
        self.assertIn("The same product", text)
        self.assertIn("refuses an MSI whose upgrade code differs from the template's", text)
        self.assertIn("refuses a label that is not the MSI's own version", text)
        self.assertIn("They do not replace a verification", text)
        self.assertIn("a real run is refused before the package tool starts", text)

    def test_the_real_run_step_says_not_yet(self):
        text = read(README)
        self.assertIn("## d. Switch a real run on (NOT YET: see the second paragraph at the top)", text)
        self.assertLess(text.index("**Status."), text.index("**Not verified."))
        self.assertLess(text.index("**Not verified."), text.index("## a."))

    def test_the_hand_command_uses_the_template_and_no_version(self):
        """S2: after the template exists, `pcman import` without --template would make a second item."""
        text = read(README)
        self.assertNotIn("with the same command", text)
        match = re.search(r"\n    (pcman import <the file> --template gcpw[^\n]*)\n", text)
        self.assertTrue(match)
        self.assertNotIn("--version", match.group(1))
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


class SharedProcessorTests(unittest.TestCase):
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

    def test_the_stub_identifier_is_the_prefix_of_the_processor_names(self):
        stub = load(os.path.join(SHARED_DIR, "SharedProcessors.recipe"))
        self.assertEqual(stub["Identifier"] + "/", SHARED_PREFIX)

    def test_every_argument_is_a_declared_input(self):
        classes = processor_classes()
        for path in (DOWNLOAD, PCMAN):
            for name, args in shared_steps(load(path)):
                for key in args:
                    with self.subTest(recipe=os.path.basename(path), processor=name, argument=key):
                        self.assertIn(key, classes[name].input_variables)

    def test_every_required_input_is_passed_or_comes_from_the_machine(self):
        classes = processor_classes()
        for path in (DOWNLOAD, PCMAN):
            for name, args in shared_steps(load(path)):
                for key, flags in classes[name].input_variables.items():
                    if not flags.get("required") or "default" in flags:
                        continue
                    with self.subTest(recipe=os.path.basename(path), processor=name, input=key):
                        if key in SUPPLIED_BY_THE_MACHINE.get(name, ()):
                            self.assertNotIn(key, args)
                        else:
                            self.assertIn(key, args)

    def test_the_input_that_a_core_processor_needs_is_there(self):
        """URLDownloader needs `url`; the recipe passes it."""
        self.assertIn("url", load(DOWNLOAD)["Process"][0]["Arguments"])


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
            "GCPW-Win.download.recipe", "GCPW.cimian.recipe", "GCPW.pcman.recipe", "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
        ]))


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
        self.assertEqual(len([c for c in commands if c.startswith("autopkg verify-trust-info")]), 5)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg update-trust-info")]), 2)
        for command in commands:
            with self.subTest(command=command):
                self.assertRegex(
                    command,
                    r"^autopkg (run|verify-trust-info|update-trust-info)( -vv)? "
                    r"--override-dir=<the Windows overrides folder> "
                    r"<the Windows overrides folder>/GCPW\.(?:cimian|pcman)\.recipe$",
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

    def test_the_steps_of_the_rehearsal_are_there(self):
        for needle in ("pcman catalogs", "pcman versions gcpw", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string", "make-override"):
            self.assertIn(needle, self.text)

    def test_the_name_check_comes_before_the_override_and_the_parent_is_read_after_it(self):
        text = read(README)
        check = text.index("autopkg list-recipes | grep -i GCPW-Win")
        override = text.index("    autopkg make-override --override-dir=")
        self.assertLess(check, override)
        self.assertIn("First check that no other recipe has the same name.", text)
        self.assertIn("Each name must be listed once, from this repository.", text)
        self.assertIn("autopkg list-recipes | grep -i GCPW.pcman", text)
        self.assertIn("read\n`ParentRecipe`", text)
        step = re.sub(r"\s+", " ", text[override:])
        self.assertIn(
            "**Open the written file and read `ParentRecipe`: it must be "
            "`com.github.serrc-techops.pcman.GCPW`**",
            step,
        )
        self.assertIn("com.github.serrc-techops.pcman.GCPW", text[override:])

    def test_the_readme_states_no_hash(self):
        """S7: a README that states a SHA-256 (64 hex digits) could be taken for a check."""
        self.assertIsNone(HEX_64.search(self.raw))

    def test_the_first_import_has_no_version_and_keeps_the_template_name(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        self.assertTrue(match)
        command = re.sub(r"\s+", " ", match.group(1))
        self.assertIn("--name gcpw", command)
        self.assertNotIn("--version", command)
        self.assertIn("--architectures x64", command)
        self.assertIn("--no-prompt", command)

    def test_the_first_import_names_the_fields_of_the_item_and_no_install_arguments_for_an_msi(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        command = re.sub(r"\s+", " ", match.group(1))
        for flag in ("--display-name", "--category", "--developer", "--description", "--directory"):
            self.assertIn(flag, command)
        self.assertNotIn("--install-arguments", command)
        self.assertNotIn("--install-path", command)

    def test_the_readme_does_not_claim_a_rehearsal_of_this_folder(self):
        self.assertNotIn("Rehearsed on", self.raw)
        self.assertNotIn("`pcman catalogs` was NOT run either", self.text)
        self.assertIn("carries `--override-dir`", self.text)
        self.assertIn("A real run of this recipe was REFUSED on 2026-10-04 (see the status line above), and nothing has been installed on a PC", self.text)
        self.assertNotIn("has NOT been run by anyone", self.text)
        self.assertIn("they were NOT seen for this recipe", self.text)

    def test_the_readme_says_what_to_do_when_the_server_does_not_answer_the_changed_file_question(self):
        self.assertIn("whether this server answers that question is NOT established", self.text)
        self.assertIn("If the address answers \"not found\" or \"access denied\", Google moved the file", self.text)


def _text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class RealRunReadmeTests(unittest.TestCase):
    """What the README says of the first import and the real run of 2026-10-04 (AutoPkg 2.9.0). """

    def setUp(self):
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md"), "r", encoding="utf-8") as handle:
            self.raw = handle.read()
        self.text = re.sub(r"\s+", " ", self.raw)
        self.status = re.sub(r"\s+", " ", [line for line in self.raw.splitlines() if line.startswith("**Status.")][0])

    def test_the_status_line_says_what_ran_on_2026_10_04(self):
        for needle in ("No item with the GCPW installer existed in the package tool's repository, so the first import (the command of step a.3 below, run with `--no-prompt` and `--build`) made the item `gcpw` (an MSI item, version `150.0.7871.100` read from the MSI, architectures `x64`, no icon because the repository had none for it)", '`gcpw` was the right name, and the override needed no change of `PCMAN_TEMPLATE`', '`make-override` with `--override-dir`, `ParentRecipe` right, `verify-trust-info` OK, `pcman_dry_run` false', 'the importer REFUSED the run with `The download was not verified:', '(exit 70)', '`pcman_allow_unverified` was not set', "The override downloaded the file again about ten minutes after the first import, and its hash was the imported file's", '`Nothing new: gcpw <version> exists already ...` with exit 3', '`pcman catalogs` ran once for all the new items together (2026-10-04)', '`All` and `Production`, 106 items each', "the silent install is the client's (`/qn /norestart` for an MSI) and was NOT tested on a PC", 'Still NOT established after those runs: that the MSI installs silently on a PC; any install'):
            self.assertIn(needle, self.status)

    def test_the_readme_says_the_rest_of_it(self):
        for needle in ('the name of the item that the first import of 2026-10-04 made; no GCPW item existed before', '`PCMAN_TEMPLATE` in the recipe is `gcpw`, the name of the item that the first import of 2026-10-04 made, and the override of that day needed no change of it'):
            self.assertIn(needle, self.text)

    def test_the_first_import_step_says_what_worked(self):
        step = re.sub(r"\s+", " ", self.raw[self.raw.index("3. **The template item"):self.raw.index("## b.")])
        for needle in ('On 2026-10-04 none existed, and the first import below made `gcpw`', 'This is the form that ran on 2026-10-04 (it worked as written)', 'the client runs `msiexec /i <file> /qn /norestart` itself (not tested on a PC)', 'No icon was given because the repository had none for this item'):
            self.assertIn(needle, step)

    def test_nothing_that_was_not_tested_is_called_tested(self):
        for claim in ('was tested on a PC', '`gcpw` in the recipe is a PLACEHOLDER'):
            self.assertNotIn(claim, self.text)

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
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.GCPW")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.GCPW")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotEqual(cimian["Identifier"], pcman["Identifier"])
        self.assertEqual(cimian["MinimumVersion"], pcman["MinimumVersion"])
        self.assertTrue(CIMIAN.endswith("GCPW.cimian.recipe"))
        self.assertTrue(PCMAN.endswith("GCPW.pcman.recipe"))

    def test_the_only_step_is_the_cimian_importer(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "CimianImporter"])

    def test_the_inputs_and_the_arguments(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], load(PCMAN)["Input"]["NAME"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], load(PCMAN)["Input"]["PCMAN_TEMPLATE"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], "gcpw")
        self.assertEqual(recipe["Input"]["CIMIAN_SUBDIRECTORY"], "")
        self.assertEqual(sorted(recipe["Input"]), ["CIMIAN_NAME", "CIMIAN_SUBDIRECTORY", "NAME", "pkginfo"])
        self.assertEqual(recipe["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": ""})

    def test_the_pkginfo_gives_only_what_the_readme_states(self):
        self.assertEqual(load(CIMIAN)["Input"]["pkginfo"], {'display_name': 'Google Credential Provider for Windows', 'developer': 'Google'})

    def test_the_version_argument_is_the_exes_label_or_empty_for_an_msi(self):
        argument = load(CIMIAN)["Process"][0]["Arguments"]["version"]
        if "msi" == "exe":
            self.assertEqual(argument, "%version%")
        else:
            self.assertEqual(argument, "")  # the MSI's own ProductVersion, not a tag that an earlier step set

    def test_the_package_tool_recipe_is_the_old_recipe_with_the_new_processor_name(self):
        recipe = load(PCMAN)
        steps = [step["Processor"] for step in recipe["Process"]]
        self.assertEqual(steps, [PCMAN_PREFIX + "PcmanImporter"])
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "gcpw")
        arguments = recipe["Process"][0]["Arguments"]
        self.assertEqual(arguments["pathname"], "%pathname%")
        self.assertEqual(arguments["pcman_template"], "%PCMAN_TEMPLATE%")
        self.assertEqual("pcman_version" in arguments, "msi" == "exe")

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
        for name, identifier in (("GCPW.cimian.recipe", "com.github.serrc-techops.cimian.GCPW"),
                                 ("GCPW.pcman.recipe", "com.github.serrc-techops.pcman.GCPW")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)
        self.assertIn("`CimianImporter`", [line for line in self.raw.splitlines() if line.startswith("| `GCPW.cimian.recipe`")][0])
        self.assertIn("`pcman`", [line for line in self.raw.splitlines() if line.startswith("| `GCPW.pcman.recipe`")][0])

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
        for text, recipe, other in ((self.generic, "GCPW.cimian", "GCPW.pcman"), (self.tool, "GCPW.pcman", "GCPW.cimian")):
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
            self.assertRegex(command, r"--override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW\.cimian\.recipe$")

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
        if "msi" == "exe":
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
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.cimian.GCPW`**", self.generic.replace("\n", " "))
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.GCPW`**", self.tool.replace("\n", " "))
        for text in (self.generic, self.tool):
            self.assertNotIn("it must be `com.github.serrc-techops.download.", text.replace("\n", " "))

    def test_an_override_of_the_old_cimian_recipe_is_to_be_made_again_for_the_package_tool(self):
        self.assertIn("An override that was made from the old `GCPW.cimian.recipe`", self.tool)
        self.assertIn("must be made again from `GCPW.pcman.recipe`", self.tool)
        self.assertIn("An override that was made from this recipe before the recipes were separated", self.generic)

    def test_the_condition_of_never_overwrites_is_said(self):
        self.assertIn("do not run two runs of one item at the same time", self.generic)

    def test_the_generic_way_states_no_hash_and_no_made_up_label(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.generic))
        self.assertNotIn("Published gcpw", self.generic)

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
        self.assertIn("GCPW.pcman", self.tool)

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
        run = {"pathname": installer, "version": label if "msi" == "exe" else tag}
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
        return self.exe if "msi" == "exe" else self.msi

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
        self.assertEqual(new["installer"]["type"], "msi")
        self.assertEqual(new["installer"]["hash"], _win_support.sha256_hex(self.installer()))

    @_win_support.needs_yaml
    def test_the_version_is_the_label_of_an_exe_and_the_products_own_for_an_msi(self):
        if "msi" == "exe":
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
        head = "display_name: Template Name\nversion: 1.0.0\ncatalogs:\n- Production\ninstaller:\n  location: apps/Example-Chain-1.0.0.msi\n"
        if "msi" == "exe":
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
        if "msi" == "exe":
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
