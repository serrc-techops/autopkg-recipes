"""Tests of the two LibreOffice recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names one of our
processors is compared with what that processor declares: the shared ones
(see ../../Win-SharedProcessors) and this folder's own LibreOfficeInfoProvider
(tested in test_info_provider.py). The shared folder's tests are run separately.

Nothing in this folder was run with AutoPkg, and the hash file of the vendor's server
was not read when it was written. The README says so, and a test here keeps it saying so.
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
for folder in (SHARED_TESTS_DIR, RECIPE_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import _win_support  # noqa: E402,F401  (installs the autopkglib stand-in, imports the processors)
import test_public_repository as shared_hygiene  # noqa: E402
import LibreOfficeInfoProvider as own  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
OWN_PROCESSOR = "LibreOfficeInfoProvider"
DOWNLOAD = os.path.join(RECIPE_DIR, "LibreOffice-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "LibreOffice.cimian.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
# Processors that are part of AutoPkg itself.
CORE_PROCESSORS = ("URLDownloader", "EndOfCheckPhase")
# Required inputs that a recipe must NOT pass: they come from AutoPkg's
# preferences or the override on the machine that runs it.
SUPPLIED_BY_THE_MACHINE = {"PcmanImporter": {"pcman_root"}}
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir", "pcman_timeout",
                     "pcman_allow_unverified", "checksum_verified")
# What the earlier steps leave in the run (a step reads these without an argument).
SET_BY_CORE_STEPS = {"pathname", "url", "version", "expected_sha256"}
HASH_PATTERN = re.compile(r"(?i)\b[0-9a-f]{64}\b")


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def processor_classes():
    import importlib
    classes = {OWN_PROCESSOR: own.LibreOfficeInfoProvider}
    for name in ("PcmanImporter", "ChecksumVerifier", "GitHubAssetDigest"):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def named_steps(recipe):
    """(processor name without the shared prefix, arguments) of every step
    that is ours: a shared processor or this folder's own."""
    for step in recipe["Process"]:
        name = step["Processor"]
        if name.startswith(SHARED_PREFIX):
            yield name[len(SHARED_PREFIX):], step.get("Arguments", {})
        elif name == OWN_PROCESSOR:
            yield name, step.get("Arguments", {})


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
                self.assertEqual(recipe["MinimumVersion"], "1.0.0")

    def test_identifiers_and_parent(self):
        download, cimian = load(DOWNLOAD), load(CIMIAN)
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.LibreOffice-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.LibreOffice")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [
            OWN_PROCESSOR, "URLDownloader", "EndOfCheckPhase", SHARED_PREFIX + "ChecksumVerifier",
        ])

    def test_the_cimian_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "PcmanImporter"])

    def test_the_hard_check_comes_after_the_download_and_before_anything_is_imported(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertLess(steps.index("URLDownloader"), steps.index(SHARED_PREFIX + "ChecksumVerifier"))
        self.assertEqual(steps[-1], SHARED_PREFIX + "ChecksumVerifier")

    def test_the_provider_arguments_are_the_recipes_inputs(self):
        recipe = load(DOWNLOAD)
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"libreoffice_line": "%LIBREOFFICE_LINE%"})
        for value in args.values():
            match = re.fullmatch(r"%([A-Z_]+)%", value)
            if match:
                self.assertIn(match.group(1), recipe["Input"])

    def test_the_defaults_of_the_recipe_are_the_defaults_of_the_processor(self):
        inputs = load(DOWNLOAD)["Input"]
        flags = own.LibreOfficeInfoProvider.input_variables
        self.assertEqual(inputs["LIBREOFFICE_LINE"], "fresh")
        self.assertEqual(inputs["LIBREOFFICE_LINE"], flags["libreoffice_line"]["default"])
        self.assertEqual(inputs["NAME"], "LibreOffice")

    def test_the_downloader_gets_its_address_from_the_provider(self):
        """URLDownloader needs `url`. It is set by the provider and passed as no argument."""
        step = load(DOWNLOAD)["Process"][1]
        self.assertEqual(step["Processor"], "URLDownloader")
        self.assertNotIn("Arguments", step)
        self.assertIn("url", own.LibreOfficeInfoProvider.output_variables)

    def test_the_checksum_arguments_are_the_hash_files_hash(self):
        steps = dict(named_steps(load(DOWNLOAD)))
        self.assertEqual(steps["ChecksumVerifier"],
                         {"pathname": "%pathname%", "expected_sha256": "%expected_sha256%"})
        self.assertIn("expected_sha256", own.LibreOfficeInfoProvider.output_variables)

    def test_every_variable_a_recipe_uses_is_an_input_or_set_by_an_earlier_step(self):
        for path in (DOWNLOAD, CIMIAN):
            recipe = load(path)
            known = set(recipe["Input"]) | SET_BY_CORE_STEPS
            if path == CIMIAN:
                known |= set(load(DOWNLOAD)["Input"])
            for step in recipe["Process"]:
                for value in step.get("Arguments", {}).values():
                    for name in re.findall(r"%([A-Za-z_]+)%", str(value)):
                        with self.subTest(recipe=os.path.basename(path), variable=name):
                            self.assertIn(name, known)

    def test_the_inputs_of_the_cimian_recipe(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], "LibreOffice")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "libreoffice-fresh")
        self.assertEqual(sorted(recipe["Input"]), ["NAME", "PCMAN_TEMPLATE"])
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%"})

    def test_the_template_keeps_the_name_of_the_item_it_replaces(self):
        self.assertEqual(load(CIMIAN)["Input"]["PCMAN_TEMPLATE"], "libreoffice-fresh")

    def test_no_pcman_version_in_an_msi_recipe(self):
        """For an MSI the package tool takes the MSI's own ProductVersion. The
        release's three numbers would be a wrong label."""
        for path in (DOWNLOAD, CIMIAN):
            self.assertNotIn("pcman_version", read(path))
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

    def test_the_recipes_have_no_hash_written_into_them(self):
        for path in (DOWNLOAD, CIMIAN):
            self.assertIsNone(HASH_PATTERN.search(read(path)))

    def test_the_description_says_what_a_reader_must_know(self):
        text = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        self.assertIn("comparing the numbers of each version", text)
        self.assertIn("SHA-256", text)
        self.assertIn("LibreOfficeInfoProvider", text)
        self.assertIn("fresh", text)
        self.assertIn("still", text)
        cimian = re.sub(r"\s+", " ", load(CIMIAN)["Description"])
        self.assertIn("the MSI's own ProductVersion", cimian)
        self.assertIn("dry run", cimian)
        self.assertIn("pcman_dry_run", cimian)

    def test_no_description_claims_a_rehearsal(self):
        """The writer ran nothing. A description that says it was rehearsed or tested would be false."""
        for path in (DOWNLOAD, CIMIAN):
            text = re.sub(r"\s+", " ", load(path)["Description"])
            for word in ("rehearsed", "Rehearsed", "was tested", "has been tested", "verified on"):
                self.assertNotIn(word, text)
        self.assertIn("NOT run when it was written", re.sub(r"\s+", " ", load(DOWNLOAD)["Description"]))


class ProcessorTests(unittest.TestCase):
    def test_every_named_processor_exists(self):
        for path in (DOWNLOAD, CIMIAN):
            for step in load(path)["Process"]:
                name = step["Processor"]
                if name.startswith(SHARED_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, name[len(SHARED_PREFIX):] + ".py")), name)
                elif name not in CORE_PROCESSORS:
                    self.assertTrue(os.path.isfile(os.path.join(RECIPE_DIR, name + ".py")), name)

    def test_the_own_processor_has_no_prefix_and_a_class_of_the_same_name(self):
        text = read(os.path.join(RECIPE_DIR, OWN_PROCESSOR + ".py"))
        self.assertIn("class %s(Processor):" % OWN_PROCESSOR, text)

    def test_the_stub_identifier_is_the_prefix_of_the_processor_names(self):
        stub = load(os.path.join(SHARED_DIR, "SharedProcessors.recipe"))
        self.assertEqual(stub["Identifier"] + "/", SHARED_PREFIX)

    def test_every_argument_is_a_declared_input(self):
        classes = processor_classes()
        for path in (DOWNLOAD, CIMIAN):
            for name, args in named_steps(load(path)):
                for key in args:
                    with self.subTest(recipe=os.path.basename(path), processor=name, argument=key):
                        self.assertIn(key, classes[name].input_variables)

    def test_every_required_input_is_passed_or_comes_from_the_machine(self):
        classes = processor_classes()
        for path in (DOWNLOAD, CIMIAN):
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
        for name, flags in own.LibreOfficeInfoProvider.input_variables.items():
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

    def test_no_file_of_the_folder_holds_a_sha_256(self):
        """64 hex digits anywhere in the folder: a hash written down could be taken for a check.
        The tests build their hashes while they run."""
        for path in self.files():
            with self.subTest(file=os.path.relpath(path, RECIPE_DIR)):
                self.assertIsNone(HASH_PATTERN.search(read(path)))

    def test_nothing_deeper_than_the_tests_folder(self):
        for path in self.files():
            self.assertLessEqual(len(os.path.relpath(path, RECIPE_DIR).split(os.sep)), 2, path)

    def test_the_folder_holds_only_what_is_expected(self):
        names = sorted(os.path.relpath(path, RECIPE_DIR) for path in self.files())
        self.assertEqual(names, sorted([
            "LibreOffice-Win.download.recipe", "LibreOffice.cimian.recipe", "LibreOfficeInfoProvider.py",
            "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
            os.path.join("tests", "test_info_provider.py"), os.path.join("tests", "stable_index_excerpt.html"),
        ]))

    def test_the_saved_page_is_a_copy_of_the_real_index_with_one_line_added(self):
        path = os.path.join(TESTS_DIR, "stable_index_excerpt.html")
        self.assertLess(os.path.getsize(path), 20000)
        first_line = read(path).splitlines()[0]
        self.assertIn("A copy of the real index of 2026-10-02 (download.documentfoundation.org/libreoffice/stable/), "
                      "no hash in it. Only this first line was added.", first_line)


class ReadmeTests(unittest.TestCase):
    """The README must not teach what the rehearsal of 7-Zip showed to be wrong,
    and must say that this program was not rehearsed."""

    def setUp(self):
        self.raw = read(README)
        self.text = re.sub(r"\s+", " ", self.raw)

    def test_every_make_override_command_names_an_override_folder(self):
        commands = list(re.finditer(r"autopkg make-override([^`\n]*(?:\n[ \t]+--[^\n`]*)?)", self.raw))
        self.assertTrue(commands)
        for match in commands:
            self.assertIn("--override-dir=", match.group(1))
            self.assertIn("LibreOffice.cimian", match.group(1))

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
                    r"<the Windows overrides folder>/LibreOffice\.cimian\.recipe$",
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

    def test_the_readme_states_no_hash(self):
        """A README that states a SHA-256 (64 hex digits) could be taken for a check."""
        self.assertIsNone(HASH_PATTERN.search(self.raw))

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
            "## c. First try: a dry run", "## d. Switch a real run on",
            "## e. The real run, the catalogs, the second run",
            "## f. When a recipe or a processor changes upstream", "## g. A share that is not mounted")]
        self.assertEqual(positions, sorted(positions))

    def test_the_steps_of_the_run_are_there(self):
        for needle in ("pcman catalogs", "pcman versions libreoffice-fresh", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string", "make-override"):
            self.assertIn(needle, self.text)

    def test_the_first_import_has_no_version_and_keeps_the_template_name(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        self.assertTrue(match)
        command = re.sub(r"\s+", " ", match.group(1))
        self.assertIn("--name libreoffice-fresh", command)
        self.assertNotIn("--version", command)
        self.assertNotIn("--install-arguments", command)
        self.assertIn("--architectures x64", command)
        self.assertIn("--no-prompt", command)
        for flag in ("--display-name", "--category", "--developer", "--description"):
            self.assertIn(flag, command)

    def test_the_status_line_says_what_was_fetched_and_what_was_not(self):
        self.assertTrue(self.raw.index("**Status.") < self.raw.index("## a."))
        self.assertIn("**Status. NOT rehearsed with AutoPkg. Some facts of the source were fetched by the writer on 2026-10-02:",
                      self.text)
        i = self.text.index("**Status.")
        paragraph = self.text[i:self.text.index("| Recipe |", i)]
        self.assertTrue(paragraph.rstrip().endswith("**"))
        verified, not_verified = paragraph.split("NOT VERIFIED:")
        for needle in ("VERIFIED:", "https://download.documentfoundation.org/libreoffice/stable/",
                       "answered 200 with no redirect", "mirrorbrain HTML index",
                       "`25.8.7/`, `26.2.5/`, `26.2.6/`, `26.8.0/` and `26.8.1/`",
                       "three lines at once", "`?C=N;O=D`", "`/libreoffice/`", "`/mirrorbrain.css`", "a mailto",
                       "`http://mirrorbrain.org/`", "`fresh` 26.8.1 and `still` 26.2.6",
                       "`.../stable/26.8.1/win/` answered 200", "`aarch64/`, `x86/` and `x86_64/`",
                       "`LibreOffice_26.8.1_Win_x86-64.msi`", "`...msi.mirrorlist`", "`...msi.asc`",
                       "`...msi.asc.mirrorlist`", "`_sdk.msi` set",
                       "**THE HASH FILE THAT THE PROVIDER EXPECTS DOES NOT EXIST:",
                       "there is no `.sha256`, `.md5` or `.sha1` file in that folder.**",
                       "answered 404 once and 500 once",
                       "a `.mirrorlist` page per file (mirrorbrain, which usually shows the file's hashes on that page)",
                       "a `.asc` signature",
                       "Until the owner reads the `.mirrorlist` page of the MSI on the build Mac",
                       "the provider is changed to read the hash from wherever it is shown",
                       "this recipe stays a dry run that fails at the provider",
                       "LibreOffice stays a hand import"):
            self.assertIn(needle, verified)
        for needle in ("a `.meta4` address never answered", "a HEAD of the MSI answered 500 once",
                       "ProductVersion and UpgradeCode", "the template",
                       "`pcman catalogs`", "any run with AutoPkg",
                       "stop: nothing was written", "correct the recipe",
                       "never accept the trust information first",
                       "tell the owner", "a hash read from a mirror is not the publisher's",
                       "carries `--override-dir`"):
            self.assertIn(needle, not_verified)
        for word in ("Rehearsed on", "was rehearsed with", "the provider read the vendor's real page",
                     "the network was closed", "NOT fetched by the writer",
                     "corrects `expected_file_name`"):
            self.assertNotIn(word, paragraph)
        self.assertNotIn("NOT been run by anyone", self.text)

    def test_the_missing_hash_file_is_said_in_the_description_the_checks_and_the_provider(self):
        description = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        self.assertTrue(description.startswith("NOT WORKING (expected). "))
        first_sentence = description.split(". ")[2]  # the one after the mark and its explanation
        self.assertIn("The hash file that this recipe's provider reads does not exist on the vendor's server (checked 2026-10-02)",
                      first_sentence)
        self.assertIn("LibreOffice stays a hand import", first_sentence)
        i = self.raw.index("## What the checks prove")
        checks = re.sub(r"\s+", " ", self.raw[i:self.raw.index("## Run every override")])
        self.assertIn("The hash file that the provider reads does not exist on the vendor's server (2026-10-02)", checks)
        self.assertIn("LibreOffice stays a hand import", checks)
        docstring = re.sub(r"\s+", " ", own.__doc__)
        self.assertIn("THE HASH FILE DOES NOT EXIST (checked 2026-10-02)", docstring)
        self.assertIn("no .sha256, .md5 or .sha1 file", docstring)
        self.assertIn(".mirrorlist", docstring)

    def test_the_pair_is_marked_as_not_working_in_the_readme_and_in_both_descriptions(self):
        """The pair stops at its first run (the provider's hash file was not found) and the owner
        decides at the merge whether it stays. The mark comes first, before the status line."""
        mark = self.text.index("**NOT WORKING (expected). This recipe pair is expected to stop at its first run and publish nothing.")
        self.assertLess(mark, self.text.index("**Status."))
        self.assertLess(self.text.index("# Win-LibreOffice"), mark)
        paragraph = self.text[mark:self.text.index("**Status.")]
        self.assertTrue(paragraph.rstrip().endswith("**"))
        for needle in ("`LibreOfficeInfoProvider`", "404 once and 500 once", "hand import", "the owner's decision at the merge",
                       "is expected to fail at"):
            self.assertIn(needle, paragraph)
        download = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        self.assertTrue(download.startswith("NOT WORKING (expected). This recipe is expected to stop at its first run and publish nothing"))
        self.assertIn("whether it stays in the repository is the owner's decision", download)
        cimian = re.sub(r"\s+", " ", load(CIMIAN)["Description"])
        self.assertTrue(cimian.startswith("NOT WORKING (expected). Its parent, the download recipe, is expected to stop at its first run"))

    def test_the_readme_says_how_the_index_and_the_hash_file_are_read(self):
        for needle in ("**by their numbers**", "`25.10.0` is newer than `25.8.1`",
                       "no `still`", "not a fall back to `fresh`",
                       "**no redirect**", "exactly the name of the MSI",
                       "`LibreOffice download index:`", "`LibreOffice hash file:`",
                       "`checksum_verified`"):
            self.assertIn(needle, self.text)

    def test_the_name_check_and_the_parent_check_are_in_step_b(self):
        b = self.raw.index("## b.")
        c = self.raw.index("## c.")
        step = self.raw[b:c]
        self.assertIn("autopkg list-recipes | grep -i LibreOffice-Win", step)
        self.assertIn("autopkg list-recipes | grep -i LibreOffice.cimian", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.download.LibreOffice-Win`",
                      re.sub(r"\s+", " ", step))

    def test_the_readme_says_that_the_version_is_the_msis_own(self):
        self.assertIn("takes the MSI's own ProductVersion", self.text)
        self.assertIn("A label of three numbers could be refused", self.text)

    def test_the_readme_says_that_still_has_a_template_of_its_own(self):
        self.assertIn("`still` needs its own template", self.text)
        self.assertIn("libreoffice-still", self.text)

    def test_the_install_switch_is_marked_as_from_knowledge_when_it_is_named(self):
        """The first import gives no install arguments for an MSI. The properties of the
        vendor's MSI are named only with the mark that they were not read in the installer."""
        self.assertIn("from the writer's knowledge, not read in the installer", self.text)

    def test_the_example_of_the_summary_table_does_not_claim_a_printed_line(self):
        self.assertIn("this program was NOT run", self.text)


class ChainTests(_win_support.ToolTestCase):
    """The chain of this program counts as verified for the importer: the real
    ChecksumVerifier hashes the file, and the importer hashes it again and
    compares. The stand-in package tool is used; nothing else is run."""

    def chain_env(self, installer):
        """What the steps of the two recipes leave in the run, with the
        arguments of the recipe's own PcmanImporter step."""
        run = {"pathname": installer, "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        values = {"%pathname%": installer, "%PCMAN_TEMPLATE%": load(CIMIAN)["Input"]["PCMAN_TEMPLATE"],
                  "%version%": ""}
        env = {"pathname": installer, "pcman_root": self.root, "pcman_dry_run": False,
               "pcman_path": self.msi_bin}
        env.update({k: v for k, v in verifier.env.items() if k.startswith("checksum_")})
        steps = [step for step in load(CIMIAN)["Process"] if step["Processor"].endswith("/PcmanImporter")]
        self.assertEqual(len(steps), 1)
        for name, value in steps[0]["Arguments"].items():
            env[name] = values.get(value, value)
        return env

    def test_the_chain_counts_as_verified_and_nothing_is_warned(self):
        env = self.chain_env(self.msi)
        self.assertEqual(env["checksum_sha256"], _win_support.sha256_hex(self.msi))
        processor, _ = _win_support.run_processor(_win_support.importer.PcmanImporter, env)
        self.assertIs(processor.env["pcman_repo_changed"], True)
        warnings = [m for level, m in processor.message_levels if m.startswith("WARNING:")]
        self.assertEqual(warnings, [])
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published")

    def test_the_chain_is_refused_for_another_file(self):
        env = self.chain_env(self.msi)
        other = os.path.join(self.downloads, "other.msi")
        with open(other, "wb") as handle:
            handle.write(b"not the file that was verified")
        env["pathname"] = other
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_win_support.importer.PcmanImporter, env)
        self.assertIn("not the file whose checksum was verified", str(caught.exception))
        self.assertFalse(self.was_run())


if __name__ == "__main__":
    unittest.main()
