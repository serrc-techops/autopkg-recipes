"""Tests of the three Krita recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names one of our
processors is compared with what that processor declares: the shared ones
(see ../../Win-SharedProcessors) and this folder's own KritaInfoProvider
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
import KritaInfoProvider as own  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
OWN_PROCESSOR = "KritaInfoProvider"
DOWNLOAD = os.path.join(RECIPE_DIR, "Krita-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "Krita.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "Krita.pcman.recipe")
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
# A label of four numbers, as a re-issue has (built here: the hygiene check reads
# four numbers joined by dots as an address).
FOUR_NUMBER_LABEL = ".".join(["6", "0", "4", "1"])


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def processor_classes():
    import importlib
    classes = {OWN_PROCESSOR: own.KritaInfoProvider}
    for name in ("PcmanImporter", "CimianImporter", "ChecksumVerifier", "GitHubAssetDigest"):
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
        download, pcman = load(DOWNLOAD), load(PCMAN)
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.Krita-Win")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.Krita")
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [
            OWN_PROCESSOR, "URLDownloader", "EndOfCheckPhase", SHARED_PREFIX + "ChecksumVerifier",
        ])

    def test_the_pcman_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(PCMAN)["Process"]]
        self.assertEqual(steps, [PCMAN_PREFIX + "PcmanImporter"])

    def test_the_hard_check_comes_after_the_download_and_before_anything_is_imported(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertLess(steps.index("URLDownloader"), steps.index(SHARED_PREFIX + "ChecksumVerifier"))
        self.assertEqual(steps[-1], SHARED_PREFIX + "ChecksumVerifier")

    def test_the_provider_has_no_inputs_and_the_recipe_gives_none(self):
        """The provider takes nothing: the host, the folder and the number of folders it
        reads are fixed in its code. The recipe's only input is NAME."""
        recipe = load(DOWNLOAD)
        self.assertNotIn("Arguments", recipe["Process"][0])
        self.assertEqual(own.KritaInfoProvider.input_variables, {})
        self.assertEqual(sorted(recipe["Input"]), ["NAME"])
        self.assertEqual(recipe["Input"]["NAME"], "Krita")

    def test_the_downloader_gets_its_address_from_the_provider_and_keeps_its_name(self):
        """URLDownloader needs `url`, set by the provider. The file name of the address
        (krita-x64-<version>-setup.exe) has no space, so no filename is given."""
        step = load(DOWNLOAD)["Process"][1]
        self.assertEqual(step["Processor"], "URLDownloader")
        self.assertNotIn("Arguments", step)
        self.assertIn("url", own.KritaInfoProvider.output_variables)
        self.assertTrue(own.BASE_URL.startswith("https://download.kde.org/"))

    def test_the_checksum_arguments_are_the_providers_hash(self):
        steps = dict(named_steps(load(DOWNLOAD)))
        self.assertEqual(steps["ChecksumVerifier"],
                         {"pathname": "%pathname%", "expected_sha256": "%expected_sha256%"})
        self.assertIn("expected_sha256", own.KritaInfoProvider.output_variables)

    def test_every_variable_a_recipe_uses_is_an_input_or_set_by_an_earlier_step(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            recipe = load(path)
            known = set(recipe["Input"]) | SET_BY_CORE_STEPS
            if path != DOWNLOAD:
                known |= set(load(DOWNLOAD)["Input"])
            for step in recipe["Process"]:
                for value in step.get("Arguments", {}).values():
                    for name in re.findall(r"%([A-Za-z_]+)%", str(value)):
                        with self.subTest(recipe=os.path.basename(path), variable=name):
                            self.assertIn(name, known)
                known |= set(step.get("Arguments", {}))

    def test_the_inputs_of_the_pcman_recipe(self):
        recipe = load(PCMAN)
        self.assertEqual(recipe["Input"]["NAME"], "Krita")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "krita")
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%",
                                "pcman_version": "%version%"})

    def test_an_exe_recipe_passes_the_label_and_the_provider_makes_it_the_folders_version(self):
        """For an EXE the importer has no version of its own to read: the recipe passes
        `version`, which the provider outputs as the version of the folder it used."""
        self.assertIn("version", own.KritaInfoProvider.output_variables)
        self.assertEqual(load(PCMAN)["Process"][0]["Arguments"]["pcman_version"], "%version%")
        self.assertEqual(load(CIMIAN)["Process"][0]["Arguments"]["version"], "%version%")
        self.assertNotIn("pcman_version", read(DOWNLOAD))

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
            for name in ("catalogs", "catalog", "pcman_catalogs", "path", "repo", "directory",
                         "pcman_allow_unverified", "cimian_allow_unverified"):
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

    def test_the_download_has_no_hash_written_into_it(self):
        for path in (DOWNLOAD, PCMAN):
            self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", read(path)))

    def test_the_download_description_says_where_the_hash_comes_from_and_what_was_not_done(self):
        text = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        for needle in ("SHA-256 that KDE's own download server, download.kde.org, gives for exactly that file",
                       "without following a redirect", "follows its redirect to a mirror",
                       "No signature check is built", "KritaInfoProvider", "at most three folders are read",
                       "the run names the folders it passed over", "was read on 2026-11-13", "NOT run with AutoPkg"):
            self.assertIn(needle, text)
        self.assertEqual(own.MAX_FOLDERS_TRIED, 3)  # the description and the README say "three"
        for path in (CIMIAN, PCMAN):
            description = re.sub(r"\s+", " ", load(path)["Description"])
            with self.subTest(path=os.path.basename(path)):
                for needle in ("EXE", "version label", "a re-issue has a fourth number",
                               "a version of four numbers beside one of three", "NOT established",
                               "NOT run with AutoPkg", "dry run"):
                    self.assertIn(needle, description)
        self.assertIn("pcman_dry_run", load(PCMAN)["Description"])

    def test_no_description_claims_a_rehearsal_or_a_run(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = re.sub(r"\s+", " ", load(path)["Description"])
            self.assertNotRegex(text, r"(?i)\brehearsed\b")
            self.assertNotRegex(text, r"(?i)\bwas tried\b")
            self.assertNotRegex(text, r"(?i)\bran on 20")
            self.assertNotRegex(text, r"(?i)tested on a PC")


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
        text = read(os.path.join(RECIPE_DIR, OWN_PROCESSOR + ".py"))
        self.assertIn("class %s(Processor):" % OWN_PROCESSOR, text)

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

    def test_every_input_of_the_own_processor_has_the_flags_that_autopkg_reads(self):
        for name, flags in own.KritaInfoProvider.input_variables.items():
            self.assertIn("required", flags, name)
            self.assertIn("description", flags, name)

    def test_no_output_of_the_provider_has_the_name_of_an_input(self):
        self.assertFalse(set(own.KritaInfoProvider.output_variables) & set(own.KritaInfoProvider.input_variables))


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

    def test_no_file_names_the_mirror_that_was_seen(self):
        """The mirror of one day and place is not a fact of the recipe."""
        for path in self.files():
            if os.path.basename(path) == "test_recipes.py":
                continue  # this file names the word it looks for
            self.assertNotIn("fcix", read(path).lower(), path)

    def test_nothing_deeper_than_the_tests_folder(self):
        for path in self.files():
            self.assertLessEqual(len(os.path.relpath(path, RECIPE_DIR).split(os.sep)), 2, path)

    def test_the_folder_holds_only_what_is_expected(self):
        names = sorted(os.path.relpath(path, RECIPE_DIR) for path in self.files())
        self.assertEqual(names, sorted([
            "Krita-Win.download.recipe", "Krita.cimian.recipe", "Krita.pcman.recipe", "KritaInfoProvider.py",
            "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
            os.path.join("tests", "test_info_provider.py"),
            os.path.join("tests", "krita_index_excerpt.html"), os.path.join("tests", "krita_folder_excerpt.html"),
        ]))

    def test_the_excerpts_are_small(self):
        for name in ("krita_index_excerpt.html", "krita_folder_excerpt.html"):
            self.assertLess(os.path.getsize(os.path.join(TESTS_DIR, name)), 4000)

    def test_no_recipe_no_readme_and_no_provider_holds_a_hash(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN, README, os.path.join(RECIPE_DIR, OWN_PROCESSOR + ".py")):
            with self.subTest(path=os.path.basename(path)):
                self.assertIsNone(re.search(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", read(path)))


class ReadmeTests(unittest.TestCase):
    """The README must not teach what the rehearsal of 7-Zip showed to be wrong, and must
    say what was NOT done."""

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
                    r"^autopkg (run|verify-trust-info|update-trust-info)( -vv)? "
                    r"--override-dir=<the Windows overrides folder> "
                    r"<the Windows overrides folder>/Krita\.(?:cimian|pcman)\.recipe$",
                )

    def test_no_autopkg_command_line_is_missed_by_the_indent_rule(self):
        pattern = r"^[ \t]*autopkg (?:run|verify-trust-info|update-trust-info)\b"
        self.assertEqual(len(re.findall(pattern, self.raw, re.M)), len(self.operator_commands()))
        self.assertEqual(len(re.findall(r"autopkg run ", self.raw)), 6)

    def test_no_prose_line_shows_a_full_command_without_the_option(self):
        for match in re.finditer(r"`(autopkg (?:run|verify-trust-info|update-trust-info)[^`]*<[^`]*)`", self.raw):
            self.assertIn("--override-dir=", match.group(1))

    def test_the_readme_states_no_hash(self):
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
        for needle in ("pcman catalogs", "pcman versions krita", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string", "make-override"):
            self.assertIn(needle, self.text)

    def test_the_first_import_names_the_template_the_label_and_marks_the_switch_untested(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        self.assertTrue(match)
        command = re.sub(r"\s+", " ", match.group(1))
        self.assertIn("--name krita", command)
        self.assertIn("--version 6.0.4 ", command)  # an EXE has a label
        for flag in ("--display-name Krita", "--category", "--developer 'Krita Foundation'", "--description",
                     "--install-arguments '/S'", "--install-path", "--architectures x64", "--no-prompt"):
            self.assertIn(flag, command)
        i = self.text.index("--install-arguments", self.text.index("3. **The template item"))
        after = self.text[i:i + 1500]
        self.assertIn("(from the writer's knowledge, not read in the installer)", after)
        self.assertIn("**NOT tested**", after)
        self.assertIn("the shell extension", after)

    def test_the_four_number_notation_is_explained_before_it_is_used(self):
        rule = "**A version of four numbers is written in this folder as `6.0.4(.1)`**"
        self.assertIn(rule, self.raw)
        self.assertLess(self.raw.index(rule), self.raw.index("`6.0.4(.1)/`"))
        self.assertIn("hygiene check reads four numbers joined by dots as an address", self.text)

    def test_the_status_line_says_what_was_read_and_what_was_not(self):
        opening = "**Status. New, NOT run with AutoPkg: nothing was downloaded, imported or installed."
        start = self.raw.index(opening)
        self.assertLess(self.raw.index("# Win-Krita"), start)
        self.assertLess(start, self.raw.index("| Recipe |"))
        end = self.raw.index("**\n", start)
        paragraph = re.sub(r"\s+", " ", self.raw[start:end + 2])
        self.assertTrue(paragraph.endswith("**"))
        _, _, rest = paragraph.partition("Facts of the source that the writer read on 2026-11-13:")
        self.assertTrue(rest)
        read_facts, _, not_established = rest.partition("NOT established:")
        self.assertTrue(not_established)
        for needle in ("`https://download.kde.org/stable/krita/` answered 200 with no redirect",
                       "`5.3.4(.1)/`, `6.0.2/`, `6.0.4/` and `6.0.4(.1)/` (each link twice)",
                       "`krita-x64-6.0.4(.1)-setup.exe` (167M, 2026-10-01)",
                       "`krita-x64-6.0.4-setup.exe`, 168M, 2026-09-10",
                       "answered `302` with a `Location` on a mirror host",
                       "answered 200 from download.kde.org itself, with no redirect",
                       "93 bytes, the same form with no new line at the end",
                       "neither folder's index links its `.sha256` file"):
            self.assertIn(needle, read_facts)
        for needle in ("whether a version folder can be without the Windows installer",
                       "NSIS installer and that `/S` installs it silently (the writer's knowledge, not read from the vendor, not tested)",
                       "the install path", "the shell extension that the installer is said to offer (not read)",
                       "whether the file has a version resource and what the installed program reports",
                       "how the Cimian client and the package tool order a version of four numbers beside one of three",
                       "Authenticode signature (not read)", "MirrorBrain, not read", "which mirror a run gets",
                       "any install on a PC"):
            self.assertIn(needle, not_established)
        for needle in ("the hash lines of the tests are made up", "STOP: nothing was written",
                       "correct the processor or the recipe", "Never accept new trust information first",
                       "stop and tell the owner"):
            self.assertIn(needle, paragraph)
        self.assertNotRegex(self.text, r"Rehearsed on 20")
        self.assertNotRegex(self.text, r"(?i)\bwas rehearsed\b")
        self.assertNotRegex(self.text, r"(?i)\bran on 20")
        self.assertNotIn("Run on 20", self.text)

    def test_nothing_in_the_readme_claims_a_run_that_did_not_happen(self):
        for needle in ("Expected, from the code and the rehearsals of the other folders, NOT printed by this recipe yet",
                       "(Not run: the lines of the output are not known.)", "Expected (not run)"):
            self.assertIn(needle, self.text)
        self.assertNotIn("The rehearsal printed", self.text)
        self.assertNotRegex(self.text, r"(?<!NOT )(?i:rehearsed with)")
        for claim in ("was tested on a PC", "the switch is established", "a transfer check, not proof of origin"):
            self.assertNotIn(claim, self.text)

    def test_the_readme_says_how_the_hash_is_fetched_and_what_it_proves(self):
        for needle in ("The `.sha256` file is read from `download.kde.org` itself, without a redirect",
                       "the mirror's file is the file that KDE's own server gives the hash for",
                       "It does not check a signature", "`checksum_verified`",
                       "All three fetches go to `download.kde.org` over https and follow no redirect"):
            self.assertIn(needle, self.text)

    def test_the_readme_says_how_the_folder_is_chosen(self):
        for needle in ("from the highest version down", "so `6.0.4(.1)` is higher than `6.0.4`",
                       "a folder without that link is passed over", "at most three folders are read",
                       "A link of digits and dots that is not such a version (`7.0/`, say) stops the run",
                       "A folder that links to a Windows installer of another version stops the run",
                       "`krita_passed_over`", "A known limit: the older line"):
            self.assertIn(needle, self.text)

    def test_the_readme_says_both_importers_take_four_numbers_and_the_client_order_is_open(self):
        for needle in ("Both shared importers take a label of four numbers",
                       "How the Cimian client orders `6.0.4(.1)` beside `6.0.4` is NOT established"):
            self.assertIn(needle, self.text)

    def test_the_name_check_and_the_parent_check_are_in_step_b(self):
        step = self.raw[self.raw.index("## b."):self.raw.index("## c.")]
        self.assertIn("autopkg list-recipes | grep -i Krita-Win", step)
        self.assertIn("autopkg list-recipes | grep -i Krita.pcman", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Krita`", re.sub(r"\s+", " ", step))

    def test_the_readme_names_no_mirror_host(self):
        self.assertNotIn("fcix", self.raw)
        self.assertNotIn("mirror.example", self.raw)

class ChainTests(_pcman_support.ToolTestCase):
    """The chain of this program counts as verified for the importer: the real
    ChecksumVerifier hashes the file, and the importer hashes it again and
    compares. The stand-in package tool is used; nothing else is run."""

    def chain_env(self, installer):
        """What the steps of the two recipes leave in the run, with the
        arguments of the recipe's own PcmanImporter step."""
        run = {"pathname": installer, "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        values = {"%pathname%": installer, "%PCMAN_TEMPLATE%": load(PCMAN)["Input"]["PCMAN_TEMPLATE"],
                  "%version%": FOUR_NUMBER_LABEL}
        env = {"pathname": installer, "pcman_root": self.root, "pcman_dry_run": False,
               "pcman_path": self.msi_bin}
        env.update({k: v for k, v in verifier.env.items() if k.startswith("checksum_")})
        steps = [step for step in load(PCMAN)["Process"] if step["Processor"].endswith("/PcmanImporter")]
        self.assertEqual(len(steps), 1)
        for name, value in steps[0]["Arguments"].items():
            env[name] = values.get(value, value)
        return env

    def test_the_chain_counts_as_verified_and_nothing_is_warned(self):
        env = self.chain_env(self.exe)
        self.assertEqual(env["checksum_sha256"], _win_support.sha256_hex(self.exe))
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        self.assertIs(processor.env["pcman_repo_changed"], True)
        warnings = [m for level, m in processor.message_levels if m.startswith("WARNING:")]
        self.assertEqual(warnings, [])
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published")
        # The stand-in reports its own fixed result; what the tool was given is in its record.
        argv = self.record()["argv"]
        self.assertIn(FOUR_NUMBER_LABEL, argv)

    def test_the_chain_is_refused_for_another_file(self):
        env = self.chain_env(self.exe)
        other = os.path.join(self.downloads, "other.exe")
        with open(other, "wb") as handle:
            handle.write(b"not the file that was verified")
        env["pathname"] = other
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        self.assertIn("not the file whose checksum was verified", str(caught.exception))
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
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.Krita")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.Krita")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotEqual(cimian["Identifier"], pcman["Identifier"])
        self.assertEqual(cimian["MinimumVersion"], pcman["MinimumVersion"])
        self.assertTrue(CIMIAN.endswith("Krita.cimian.recipe"))
        self.assertTrue(PCMAN.endswith("Krita.pcman.recipe"))

    def test_the_only_step_is_the_cimian_importer(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "CimianImporter"])

    def test_the_inputs_and_the_arguments(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], load(PCMAN)["Input"]["NAME"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], load(PCMAN)["Input"]["PCMAN_TEMPLATE"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], "krita")
        self.assertEqual(recipe["Input"]["CIMIAN_SUBDIRECTORY"], "")
        self.assertEqual(sorted(recipe["Input"]), ["CIMIAN_NAME", "CIMIAN_SUBDIRECTORY", "NAME", "pkginfo"])
        self.assertEqual(recipe["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": "%version%"})

    def test_the_pkginfo_gives_only_what_the_readme_states(self):
        self.assertEqual(load(CIMIAN)["Input"]["pkginfo"], {'display_name': 'Krita', 'developer': 'Krita Foundation'})

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
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "krita")
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
        if False:
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
        for name, identifier in (("Krita.cimian.recipe", "com.github.serrc-techops.cimian.Krita"),
                                 ("Krita.pcman.recipe", "com.github.serrc-techops.pcman.Krita")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)
        self.assertIn("`CimianImporter`", [line for line in self.raw.splitlines() if line.startswith("| `Krita.cimian.recipe`")][0])
        self.assertIn("`pcman`", [line for line in self.raw.splitlines() if line.startswith("| `Krita.pcman.recipe`")][0])

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
        for text, recipe, other in ((self.generic, "Krita.cimian", "Krita.pcman"), (self.tool, "Krita.pcman", "Krita.cimian")):
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
            self.assertRegex(command, r"--override-dir=<the Windows overrides folder> <the Windows overrides folder>/Krita\.cimian\.recipe$")

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
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.cimian.Krita`**", self.generic.replace("\n", " "))
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Krita`**", self.tool.replace("\n", " "))
        for text in (self.generic, self.tool):
            self.assertNotIn("it must be `com.github.serrc-techops.download.", text.replace("\n", " "))

    def test_the_condition_of_never_overwrites_is_said(self):
        self.assertIn("do not run two runs of one item at the same time", self.generic)

    def test_the_generic_way_states_no_hash_and_no_made_up_label(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.generic))
        self.assertNotIn("Published krita", self.generic)

    def test_an_unverified_download_is_said_not_yet_in_the_generic_way(self):
        if False:
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
        self.assertIn("Krita.pcman", self.tool)

    def test_the_processors_are_named_in_their_new_folders(self):
        self.assertNotIn("SharedProcessors/PcmanImporter", self.raw)
        self.assertNotIn("PcmanImporter` is in `../Win-SharedProcessors", self.raw)


class CimianChainTests(_win_support.RepoTestCase):
    """The chain of this program with the real CimianImporter and a temporary repository: the steps of the
    download recipe leave their variables in the run, the recipe's own step reads them."""

    VERIFIED = True

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
    def test_a_label_of_four_numbers_is_taken_as_it_is(self):
        processor, _ = self.run_chain(self.exe, label=FOUR_NUMBER_LABEL)
        self.assertEqual(processor.env["cimian_version_imported"], FOUR_NUMBER_LABEL)
        self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published")

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

    @_win_support.needs_yaml
    def test_the_chain_is_refused_for_another_file(self):
        if not self.VERIFIED:
            self.skipTest("this download has no verification step: the guard refuses every real run (see the first test)")
        installer = self.installer()
        run = {"pathname": installer, "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        other = self.make_installer("other-" + os.path.basename(installer), b"not the file that was verified")
        env = {"pathname": other, "cimian_name": "Example-Chain", "version": "1.2.3", "cimian_repo": self.repo,
               "cimian_dry_run": False, "cimian_path": self.msi_bin}
        env.update({key: value for key, value in verifier.env.items() if key.startswith("checksum_")})
        before = self.repo_tree()
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_win_support.cimian.CimianImporter, env)
        self.assertIn("not the file whose checksum was verified", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)


if __name__ == "__main__":
    unittest.main()
