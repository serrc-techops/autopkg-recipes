"""Tests of the two Firefox recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names one of our
processors is compared with what that processor declares: the shared ones
(see ../../Win-SharedProcessors) and this folder's own MozillaFirefoxInfoProvider
(tested in test_info_provider.py). The shared folder's tests are run separately.
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
import MozillaFirefoxInfoProvider as own  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
OWN_PROCESSOR = "MozillaFirefoxInfoProvider"
DOWNLOAD = os.path.join(RECIPE_DIR, "Firefox-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "Firefox.cimian.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
# Processors that are part of AutoPkg itself.
CORE_PROCESSORS = ("URLDownloader", "EndOfCheckPhase")
# Required inputs that a recipe must NOT pass: they come from AutoPkg's
# preferences or the override on the machine that runs it.
SUPPLIED_BY_THE_MACHINE = {"PcmanImporter": {"pcman_root"}}
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir", "pcman_timeout")
# What the earlier steps leave in the run (a step reads these without an argument).
SET_BY_CORE_STEPS = {"pathname", "url", "version", "expected_sha256"}


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def processor_classes():
    import importlib
    classes = {OWN_PROCESSOR: own.MozillaFirefoxInfoProvider}
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

    def test_identifiers_and_parent(self):
        download, cimian = load(DOWNLOAD), load(CIMIAN)
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.Firefox-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.Firefox")
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
        self.assertEqual(args, {
            "firefox_channel": "%FIREFOX_CHANNEL%",
            "firefox_platform": "%FIREFOX_PLATFORM%",
            "firefox_locale": "%FIREFOX_LOCALE%",
        })
        for value in args.values():
            match = re.fullmatch(r"%([A-Z_]+)%", value)
            self.assertTrue(match)
            self.assertIn(match.group(1), recipe["Input"])

    def test_the_defaults_of_the_recipe_are_the_defaults_of_the_processor(self):
        inputs = load(DOWNLOAD)["Input"]
        flags = own.MozillaFirefoxInfoProvider.input_variables
        self.assertEqual(inputs["FIREFOX_CHANNEL"], "release")
        self.assertEqual(inputs["FIREFOX_CHANNEL"], flags["firefox_channel"]["default"])
        self.assertEqual(inputs["FIREFOX_PLATFORM"], "win64")
        self.assertEqual(inputs["FIREFOX_PLATFORM"], flags["firefox_platform"]["default"])
        self.assertEqual(inputs["FIREFOX_LOCALE"], "en-US")
        self.assertEqual(inputs["FIREFOX_LOCALE"], flags["firefox_locale"]["default"])
        self.assertEqual(inputs["NAME"], "Firefox")
        self.assertIn(inputs["FIREFOX_CHANNEL"], own.CHANNELS)

    def test_the_downloader_gets_its_address_from_the_provider(self):
        """URLDownloader needs `url`. It is set by the provider and passed as no argument."""
        step = load(DOWNLOAD)["Process"][1]
        self.assertEqual(step["Processor"], "URLDownloader")
        self.assertNotIn("url", step.get("Arguments", {}))
        self.assertIn("url", own.MozillaFirefoxInfoProvider.output_variables)

    def test_the_downloader_stores_the_file_under_a_name_without_a_space(self):
        """The file on the server is named `Firefox Setup <version>.exe`. The recipe gives
        the cached file another name: no space, no %20, ending in .exe."""
        step = load(DOWNLOAD)["Process"][1]
        self.assertEqual(step["Arguments"],
                         {"filename": "Firefox-Setup-%version%-%firefox_platform%-%firefox_locale%.exe"})
        name = step["Arguments"]["filename"]
        self.assertTrue(name.endswith(".exe"))
        self.assertNotIn(" ", name)
        self.assertNotIn("%20", name)
        for variable in re.findall(r"%([A-Za-z_]+)%", name):
            self.assertTrue(variable in own.MozillaFirefoxInfoProvider.output_variables
                            or variable in own.MozillaFirefoxInfoProvider.input_variables, variable)
        # What the name becomes for the defaults, and for the values a person might give.
        for values in ({"version": "141.0", "firefox_platform": "win64", "firefox_locale": "en-US"},
                       {"version": "141.0.1", "firefox_platform": "win64-aarch64", "firefox_locale": "pt_BR"}):
            made = name
            for key, value in values.items():
                made = made.replace("%" + key + "%", value)
            self.assertNotRegex(made, r"[ %/\\]")

    def test_the_checksum_arguments_are_the_pages_hash(self):
        steps = dict(named_steps(load(DOWNLOAD)))
        self.assertEqual(steps["ChecksumVerifier"],
                         {"pathname": "%pathname%", "expected_sha256": "%expected_sha256%"})
        self.assertIn("expected_sha256", own.MozillaFirefoxInfoProvider.output_variables)

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
                # AutoPkg keeps the arguments of a step in the run: a later step reads them.
                known |= set(step.get("Arguments", {}))

    def test_the_inputs_of_the_cimian_recipe(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], "Firefox")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "firefox")
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%",
                                "pcman_version": "%version%"})

    def test_the_template_keeps_the_name_of_the_item_it_replaces(self):
        self.assertEqual(load(CIMIAN)["Input"]["PCMAN_TEMPLATE"], "firefox")

    def test_an_exe_recipe_passes_the_label_and_the_provider_makes_it_of_numbers(self):
        """For an EXE the package tool has no version of its own to read: the recipe passes
        `version`, which the provider outputs as numbers separated by dots."""
        self.assertIn("version", own.MozillaFirefoxInfoProvider.output_variables)
        self.assertEqual(load(CIMIAN)["Process"][0]["Arguments"]["pcman_version"], "%version%")
        self.assertNotIn("pcman_version", read(DOWNLOAD))
        # The file the URLDownloader stores is an .exe: PcmanImporter takes `.msi` or `.exe`.
        self.assertTrue(load(DOWNLOAD)["Process"][1]["Arguments"]["filename"].endswith(".exe"))

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

    def test_the_download_has_no_hash_written_into_it(self):
        for path in (DOWNLOAD, CIMIAN):
            self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", read(path)))

    def test_the_description_says_what_a_reader_must_know(self):
        text = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        self.assertIn("SHA256SUMS", text)
        self.assertIn("SHA-256", text)
        self.assertIn("MozillaFirefoxInfoProvider", text)
        self.assertIn("was read from the servers on 2026-10-02", text)
        self.assertIn("NOT run with AutoPkg", text)
        cimian = re.sub(r"\s+", " ", load(CIMIAN)["Description"])
        self.assertIn("EXE", cimian)
        self.assertIn("version label", cimian)
        self.assertIn("dry run", cimian)
        self.assertIn("pcman_dry_run", cimian)

    def test_no_description_claims_a_rehearsal(self):
        for path in (DOWNLOAD, CIMIAN):
            text = re.sub(r"\s+", " ", load(path)["Description"])
            self.assertNotRegex(text, r"(?i)\brehearsed\b")
            self.assertNotRegex(text, r"(?i)\bwas tried\b")


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
        for name, flags in own.MozillaFirefoxInfoProvider.input_variables.items():
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
            "Firefox-Win.download.recipe", "Firefox.cimian.recipe", "MozillaFirefoxInfoProvider.py",
            "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
            os.path.join("tests", "test_info_provider.py"),
            os.path.join("tests", "firefox_versions_excerpt.json"), os.path.join("tests", "sha256sums_excerpt.txt"),
        ]))

    def test_the_hand_written_excerpts_are_small(self):
        for name in ("firefox_versions_excerpt.json", "sha256sums_excerpt.txt"):
            self.assertLess(os.path.getsize(os.path.join(TESTS_DIR, name)), 4000)

    def test_no_recipe_no_readme_and_no_provider_holds_a_hash(self):
        for path in (DOWNLOAD, CIMIAN, README, os.path.join(RECIPE_DIR, OWN_PROCESSOR + ".py")):
            with self.subTest(path=os.path.basename(path)):
                self.assertIsNone(re.search(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", read(path)))


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
                    r"<the Windows overrides folder>/Firefox\.cimian\.recipe$",
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

    def test_the_steps_of_the_model_folders_are_there(self):
        for needle in ("pcman catalogs", "pcman versions firefox", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string", "make-override"):
            self.assertIn(needle, self.text)

    def test_the_first_import_names_the_template_the_label_and_the_flags_of_the_package_tool(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        self.assertTrue(match)
        command = re.sub(r"\s+", " ", match.group(1))
        self.assertIn("--name firefox", command)
        self.assertIn("--version 141.0", command)  # an EXE has a label
        for flag in ("--display-name", "--category", "--developer", "--description", "--install-arguments /S",
                     "--install-path", "--architectures x64", "--no-prompt"):
            self.assertIn(flag, command)
        # The silent switch and the install path are facts of the installer, from knowledge.
        i = self.text.index("--install-arguments /S")
        self.assertIn("(from the writer's knowledge, not read in the installer)", self.text[i:i + 1500])

    def test_the_status_line_says_what_was_fetched_and_what_was_not(self):
        """The models say "Rehearsed on ...". This folder was NOT run with AutoPkg. The writer fetched
        the source's facts on 2026-10-02: the README opens with a bold paragraph that lists what was
        verified and what is still not."""
        opening = "**Status. NOT rehearsed with AutoPkg. The facts of the source were fetched by the writer on 2026-10-02:"
        start = self.raw.index(opening)
        self.assertLess(start, self.raw.index("| Recipe |"))
        self.assertLess(self.raw.index("# Win-Firefox"), start)
        end = self.raw.index("**\n", start)
        paragraph = re.sub(r"\s+", " ", self.raw[start:end + 2])
        self.assertTrue(paragraph.startswith(opening))
        self.assertTrue(paragraph.endswith("**"))
        verified, _, not_established = paragraph.partition("NOT established:")
        self.assertTrue(not_established)
        for needle in ("no run of AutoPkg was made",
                       "https://product-details.mozilla.org/1.0/firefox_versions.json",
                       "answered 200 with no redirect", "`LATEST_FIREFOX_VERSION` (`157.0`)",
                       "`FIREFOX_ESR` (`140.17.0esr`, so the ESR value does end in `esr`)",
                       "https://download-installer.cdn.mozilla.net/pub/firefox/releases/157.0/SHA256SUMS",
                       "every one of its lines is 64 hex digits, two spaces and a path",
                       "`win64/en-US/Firefox Setup 157.0.exe` and `win64/en-US/Firefox Setup 157.0.msi`",
                       "the processor takes the `.exe` line only",
                       "https://download-installer.cdn.mozilla.net/pub/firefox/releases/157.0/win64/en-US/Firefox%20Setup%20157.0.exe",
                       "a HEAD request"):
            self.assertIn(needle, verified)
        for needle in ("the ESR release folder and its file carry the suffix",
                       "the version label `157.0` is what the installer itself shows",
                       "the silent switch `/S`", "distribution\\policies.json",
                       "the template item `firefox` exists", "`pcman catalogs`", "any run with AutoPkg"):
            self.assertIn(needle, not_established)
        for needle in ("wrote by hand after the real files of 2026-10-02, with made-up digits",
                       "The first run on the build Mac is the check of everything that is NOT established",
                       "STOP: nothing was written", "correct the processor or the recipe",
                       "and only then look at the trust information",
                       "Never accept new trust information first"):
            self.assertIn(needle, paragraph)
        self.assertNotRegex(self.text, r"Rehearsed on 20")
        self.assertNotRegex(self.text, r"(?i)\bwas rehearsed\b")
        self.assertNotIn("the network was closed", self.text)
        # No real digest in the status: only made-up ones in the tests.
        self.assertIsNone(re.search(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", paragraph))

    def test_nothing_in_the_readme_claims_a_run_that_did_not_happen(self):
        for needle in ("Expected, from the code and the rehearsals of the other folders, NOT printed by this recipe yet",
                       "(Not run: the lines of the output are not known.)",
                       "Expected (not run)"):
            self.assertIn(needle, self.text)
        self.assertNotIn("The rehearsal printed", self.text)
        self.assertNotRegex(self.text, r"(?<!NOT )(?i:rehearsed with)")

    def test_the_readme_says_how_the_file_is_checked_against_the_hash_file(self):
        for needle in ("`<platform>/<locale>/Firefox Setup <version>.exe`", "no line, or more than one,",
                       "A redirect is not followed", "`checksum_verified`",
                       "`Firefox-Setup-<version>-<platform>-<locale>.exe`",
                       "no `%20` in its name"):
            self.assertIn(needle, self.text)

    def test_the_name_check_and_the_parent_check_are_in_step_b(self):
        b = self.raw.index("## b.")
        c = self.raw.index("## c.")
        step = self.raw[b:c]
        self.assertIn("autopkg list-recipes | grep -i Firefox-Win", step)
        self.assertIn("autopkg list-recipes | grep -i Firefox.cimian", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.download.Firefox-Win`",
                      re.sub(r"\s+", " ", step))

    def test_the_readme_says_that_the_label_is_the_version_of_the_version_file_and_is_not_established(self):
        self.assertIn("141.0", self.text)
        self.assertIn("is NOT established", self.text)
        self.assertIn("the label must then be what the installer itself shows", self.text)
        self.assertIn("On the ESR channel the suffix `esr` is left out", self.text)

    def test_the_readme_says_that_the_redirect_rule_is_a_stop(self):
        self.assertIn("If the line says that an address answered with a redirect, stop and tell the owner", self.text)


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
                  "%version%": "141.0"}
        env = {"pathname": installer, "pcman_root": self.root, "pcman_dry_run": False,
               "pcman_path": self.msi_bin}
        env.update({k: v for k, v in verifier.env.items() if k.startswith("checksum_")})
        steps = [step for step in load(CIMIAN)["Process"] if step["Processor"].endswith("/PcmanImporter")]
        self.assertEqual(len(steps), 1)
        for name, value in steps[0]["Arguments"].items():
            env[name] = values.get(value, value)
        return env

    def test_the_chain_counts_as_verified_and_nothing_is_warned(self):
        env = self.chain_env(self.exe)
        self.assertEqual(env["checksum_sha256"], _win_support.sha256_hex(self.exe))
        processor, _ = _win_support.run_processor(_win_support.importer.PcmanImporter, env)
        self.assertIs(processor.env["pcman_repo_changed"], True)
        warnings = [m for level, m in processor.message_levels if m.startswith("WARNING:")]
        self.assertEqual(warnings, [])
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published")

    def test_the_chain_is_refused_for_another_file(self):
        env = self.chain_env(self.exe)
        other = os.path.join(self.downloads, "other.exe")
        with open(other, "wb") as handle:
            handle.write(b"not the file that was verified")
        env["pathname"] = other
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_win_support.importer.PcmanImporter, env)
        self.assertIn("not the file whose checksum was verified", str(caught.exception))
        self.assertFalse(self.was_run())


if __name__ == "__main__":
    unittest.main()
