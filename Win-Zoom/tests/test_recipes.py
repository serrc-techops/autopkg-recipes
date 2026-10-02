"""Tests of the two Zoom recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. The step that names our shared
processor is compared with what that processor declares (see
../../Win-SharedProcessors). The shared folder's tests are run separately.

The download of this program has NO hard check (no vendor hash, no signature
check). The tests make sure that nobody can overlook that: the Description of
both recipes and the top of the README say it, and no recipe invents a check.
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
if SHARED_TESTS_DIR not in sys.path:
    sys.path.insert(0, SHARED_TESTS_DIR)

import _win_support  # noqa: E402,F401  (installs the autopkglib stand-in, imports the processors)
import test_public_repository as shared_hygiene  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "ZoomWorkplaceX64-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "Zoom.cimian.recipe")
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
    for name in ("PcmanImporter", "ChecksumVerifier", "GitHubAssetDigest"):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def shared_steps(recipe):
    for step in recipe["Process"]:
        if step["Processor"].startswith(SHARED_PREFIX):
            yield step["Processor"][len(SHARED_PREFIX):], step.get("Arguments", {})


def first_sentence(text):
    return re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]


class RecipeFileTests(unittest.TestCase):
    def test_both_files_are_valid_property_lists(self):
        for path in (DOWNLOAD, CIMIAN):
            with self.subTest(path=os.path.basename(path)):
                result = subprocess.run(["plutil", "-lint", path], capture_output=True, text=True) \
                    if os.path.exists("/usr/bin/plutil") else None
                if result is not None:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                recipe = load(path)
                for key in ("Description", "Identifier", "Input", "MinimumVersion", "Process"):
                    self.assertIn(key, recipe)

    def test_identifiers_and_parent(self):
        download, cimian = load(DOWNLOAD), load(CIMIAN)
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.ZoomWorkplaceX64-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.Zoom")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, ["URLDownloader", "EndOfCheckPhase"])

    def test_the_cimian_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "PcmanImporter"])

    def test_the_downloader_arguments(self):
        recipe = load(DOWNLOAD)
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args["url"], "%DOWNLOAD_URL%")
        self.assertEqual(recipe["Input"]["DOWNLOAD_URL"], "https://zoom.us/client/latest/ZoomInstallerFull.msi?archType=x64")
        self.assertTrue(recipe["Input"]["DOWNLOAD_URL"].startswith("https://"))

    def test_the_file_name_ends_in_msi_because_the_address_has_a_query_string(self):
        recipe = load(DOWNLOAD)
        self.assertIn("?", recipe["Input"]["DOWNLOAD_URL"])
        self.assertEqual(recipe["Process"][0]["Arguments"]["filename"], "%DOWNLOAD_FILENAME%")
        self.assertTrue(recipe["Input"]["DOWNLOAD_FILENAME"].endswith(".msi"))
        self.assertNotIn("?", recipe["Input"]["DOWNLOAD_FILENAME"])
        self.assertNotIn("/", recipe["Input"]["DOWNLOAD_FILENAME"])

    def test_the_address_asks_for_the_64_bit_installer(self):
        self.assertIn("archType=x64", load(DOWNLOAD)["Input"]["DOWNLOAD_URL"])
        self.assertIn("ZoomInstallerFull.msi", load(DOWNLOAD)["Input"]["DOWNLOAD_URL"])

    def test_the_description_says_why_the_shared_recipe_is_not_the_parent(self):
        text = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        self.assertIn("Zoom64-Win.download is not the parent", text)
        self.assertIn("a parent outside this repository changes without us", text)
        self.assertNotIn("ParentRecipe", read(DOWNLOAD))

    def test_the_inputs_of_the_cimian_recipe(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], "Zoom")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "zoom")
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%"})

    def test_no_file_name_of_ours_is_the_name_of_a_recipe_in_another_repository(self):
        ours = [name[: -len(".recipe")].casefold() for name in (os.path.basename(DOWNLOAD), os.path.basename(CIMIAN))]
        for other in NAMES_OF_OTHER_REPOSITORIES:
            self.assertNotIn(other.casefold(), ours)
        for name in ours:
            self.assertNotIn(name, [other.casefold() for other in NAMES_OF_OTHER_REPOSITORIES])

    def test_the_template_keeps_the_name_of_the_item_it_replaces(self):
        self.assertEqual(load(CIMIAN)["Input"]["PCMAN_TEMPLATE"], "zoom")

    def test_no_pcman_version_in_an_msi_recipe(self):
        """For an MSI the package tool takes the MSI's own ProductVersion. A
        label from the recipe would be refused or would hide the real version."""
        for path in (DOWNLOAD, CIMIAN):
            text = read(path)
            self.assertNotIn("pcman_version", text)
            self.assertNotIn("<key>version</key>", text)
        for step in load(CIMIAN)["Process"]:
            self.assertNotIn("pcman_version", step.get("Arguments", {}))
            self.assertNotIn("%version%", str(step.get("Arguments", {})))

    def test_no_stop_on_an_unchanged_download_and_no_latest_only(self):
        for path in (DOWNLOAD, CIMIAN):
            text = read(path)
            self.assertNotIn("StopProcessingIf", text)
            self.assertNotIn("latest_only", text)

    def test_no_blocking_applications(self):
        for path in (DOWNLOAD, CIMIAN):
            self.assertNotIn("blocking_applications", read(path))

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in (DOWNLOAD, CIMIAN):
            text = read(path)
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text)
            for name in ("catalogs", "catalog", "pcman_catalogs", "path", "repo", "directory"):
                self.assertNotIn("<key>%s</key>" % name, text)

    def test_no_value_of_a_recipe_is_a_path_or_a_catalog(self):
        for path in (DOWNLOAD, CIMIAN):
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
        for path in (DOWNLOAD, CIMIAN):
            with self.subTest(path=os.path.basename(path)):
                sentence = first_sentence(load(path)["Description"])
                self.assertIn("NOT verified yet", sentence)

    def test_the_download_description_names_the_two_missing_checks(self):
        sentence = first_sentence(load(DOWNLOAD)["Description"])
        self.assertIn("no hash", sentence)
        self.assertIn("signature", sentence)

    def test_the_cimian_description_names_what_still_protects(self):
        text = re.sub(r"\s+", " ", load(CIMIAN)["Description"])
        self.assertIn("upgrade code", text)
        self.assertIn("a label that is not the MSI's own version", text)
        self.assertIn("pcman_dry_run", text)
        self.assertIn("dry run", text)

    def test_the_descriptions_say_that_a_real_run_is_refused_unless_the_override_allows_it(self):
        for path in (DOWNLOAD, CIMIAN):
            text = re.sub(r"\s+", " ", load(path)["Description"])
            with self.subTest(path=os.path.basename(path)):
                self.assertIn("refuses a real run" if path == DOWNLOAD else "A real run is refused", text)
                self.assertIn("pcman_allow_unverified", text)
                self.assertIn("true", text)

    def test_no_recipe_sets_the_allowance_or_a_verified_flag_itself(self):
        for path in (DOWNLOAD, CIMIAN):
            text = read(path)
            self.assertNotIn("<key>pcman_allow_unverified</key>", text)
            self.assertNotIn("checksum_verified", text)
            self.assertNotIn("signature_verified", text)

    def test_the_importer_would_refuse_a_real_run_of_this_chain(self):
        """The download recipe has no step that sets a verified flag, so the
        shared importer refuses a real run: read here from the steps."""
        setters = {"ChecksumVerifier": "checksum_verified"}
        names = [step["Processor"].rsplit("/", 1)[-1] for step in load(DOWNLOAD)["Process"] + load(CIMIAN)["Process"]]
        self.assertFalse(set(names) & set(setters))

    def test_no_recipe_invents_a_checksum_step(self):
        for path in (DOWNLOAD, CIMIAN):
            text = read(path)
            self.assertNotIn("ChecksumVerifier", text)
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
        for needle in ("NOT verified", "signature check", "REFUSES a real run", "pcman_allow_unverified",
                       "Do not set it before the signature check exists",
                       "pcman import <file> --template zoom", "no `--version` for an MSI",
                       "has NOT been run by anyone"):
            self.assertIn(needle, status)

    def test_the_readme_says_what_still_protects_and_that_it_is_not_enough(self):
        text = re.sub(r"\s+", " ", read(README))
        self.assertIn("The same product", text)
        self.assertIn("refuses an MSI whose upgrade code differs from the template's", text)
        self.assertIn("refuses a label that is not the MSI's own version", text)
        self.assertIn("They do not replace a verification", text)
        self.assertIn("a real run is refused before the package tool starts", text)

    def test_the_real_run_step_says_not_yet(self):
        text = read(README)
        self.assertIn("## d. Switch a real run on (NOT YET: see the status line)", text)
        self.assertLess(text.index("**Status."), text.index("## a."))

    def test_the_hand_command_uses_the_template_and_no_version(self):
        """S2: after the template exists, `pcman import` without --template would make a second item."""
        text = read(README)
        self.assertNotIn("with the same command", text)
        match = re.search(r"\n    (pcman import <the file> --template zoom[^\n]*)\n", text)
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
        for path in (DOWNLOAD, CIMIAN):
            for step in load(path)["Process"]:
                name = step["Processor"]
                if name.startswith(SHARED_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, name[len(SHARED_PREFIX):] + ".py")), name)
                elif name not in CORE_PROCESSORS:
                    self.assertTrue(os.path.isfile(os.path.join(RECIPE_DIR, name + ".py")), name)

    def test_the_stub_identifier_is_the_prefix_of_the_processor_names(self):
        stub = load(os.path.join(SHARED_DIR, "SharedProcessors.recipe"))
        self.assertEqual(stub["Identifier"] + "/", SHARED_PREFIX)

    def test_every_argument_is_a_declared_input(self):
        classes = processor_classes()
        for path in (DOWNLOAD, CIMIAN):
            for name, args in shared_steps(load(path)):
                for key in args:
                    with self.subTest(recipe=os.path.basename(path), processor=name, argument=key):
                        self.assertIn(key, classes[name].input_variables)

    def test_every_required_input_is_passed_or_comes_from_the_machine(self):
        classes = processor_classes()
        for path in (DOWNLOAD, CIMIAN):
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
            "ZoomWorkplaceX64-Win.download.recipe", "Zoom.cimian.recipe", "README.md",
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
        self.assertEqual(len([c for c in commands if c.startswith("autopkg run")]), 3)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg verify-trust-info")]), 2)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg update-trust-info")]), 1)
        for command in commands:
            with self.subTest(command=command):
                self.assertRegex(
                    command,
                    r"^autopkg (run|verify-trust-info|update-trust-info)( -vv)? "
                    r"--override-dir=<the Windows overrides folder> "
                    r"<the Windows overrides folder>/Zoom\.cimian\.recipe$",
                )

    def test_no_autopkg_command_line_is_missed_by_the_indent_rule(self):
        """An operator's command that is not indented four spaces (or is indented
        less) must still be counted: every line that begins with an autopkg
        command is one of the lines checked above, and `autopkg run ` occurs
        three times in the whole file."""
        pattern = r"^[ \t]*autopkg (?:run|verify-trust-info|update-trust-info)\b"
        at_line_start = re.findall(pattern, self.raw, re.M)
        self.assertEqual(len(at_line_start), len(self.operator_commands()))
        self.assertEqual(len(re.findall(r"autopkg run ", self.raw)), 3)

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
        for needle in ("pcman catalogs", "pcman versions zoom", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string", "make-override"):
            self.assertIn(needle, self.text)

    def test_the_name_check_comes_before_the_override_and_the_parent_is_read_after_it(self):
        text = read(README)
        check = text.index("autopkg list-recipes | grep -i ZoomWorkplaceX64")
        override = text.index("    autopkg make-override --override-dir=")
        self.assertLess(check, override)
        self.assertIn("First check that no other recipe has the same name.", text)
        self.assertIn("Each name must be listed once, from this repository.", text)
        self.assertIn("autopkg list-recipes | grep -i Zoom.cimian", text)
        self.assertIn("read\n`ParentRecipe`", text)
        step = re.sub(r"\s+", " ", text[override:])
        self.assertIn(
            "**Open the written file and read `ParentRecipe`: it must be "
            "`com.github.serrc-techops.download.ZoomWorkplaceX64-Win`.**",
            step,
        )
        self.assertIn("com.github.serrc-techops.download.ZoomWorkplaceX64-Win", text[override:])

    def test_the_readme_states_no_hash(self):
        """S7: a README that states a SHA-256 (64 hex digits) could be taken for a check."""
        self.assertIsNone(HEX_64.search(self.raw))

    def test_the_first_import_has_no_version_and_keeps_the_template_name(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        self.assertTrue(match)
        command = re.sub(r"\s+", " ", match.group(1))
        self.assertIn("--name zoom", command)
        self.assertNotIn("--version", command)
        self.assertIn("--architectures x64", command)
        self.assertIn("--no-prompt", command)

    def test_the_status_line_says_what_was_rehearsed_and_what_was_not(self):
        for needle in ("On 2026-10-01 it ran with the real AutoPkg 2.9.0 in a scratch folder up to \"Nothing new\"",
                       "against a template of the same version", "carries `--override-dir`",
                       "A real run of this recipe has NOT been run by anyone, not against a share and not on a PC"):
            self.assertIn(needle, self.text)
        self.assertIn("`pcman catalogs` was NOT rehearsed", self.text)
        self.assertNotIn("Rehearsed on", self.raw)


if __name__ == "__main__":
    unittest.main()
