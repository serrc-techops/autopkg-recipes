"""Tests of the two Greenshot recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names one of our shared
processors is compared with what that processor declares (see
../../Win-SharedProcessors). The shared folder's tests are run separately.
"""
import json
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
import test_exe_version as exe_tests  # noqa: E402  (builds a small PE file; its tests are not collected here)
import test_public_repository as shared_hygiene  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "Greenshot-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "Greenshot.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "Greenshot.pcman.recipe")
# Names, sizes, pre-release flags and digest flags of the newest twelve releases, read from GitHub on 2026-10-04.
RELEASES = os.path.join(TESTS_DIR, "releases_excerpt.json")
# Required inputs that a recipe must NOT pass: they come from AutoPkg's
# preferences or the override on the machine that runs it.
SUPPLIED_BY_THE_MACHINE = {"PcmanImporter": {"pcman_root"}}
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir")


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def processor_classes():
    import importlib
    classes = {}
    for name in ("PcmanImporter", "CimianImporter", "ChecksumVerifier", "GitHubAssetDigest", "WindowsExeVersion"):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def shared_steps(recipe):
    """The steps that name a processor of this repository, of either folder: (name, arguments)."""
    for step in recipe["Process"]:
        for prefix in (SHARED_PREFIX, PCMAN_PREFIX):
            if step["Processor"].startswith(prefix):
                yield step["Processor"][len(prefix):], step.get("Arguments", {})


def releases():
    with open(RELEASES, "r", encoding="utf-8") as handle:
        return json.load(handle)["releases"]


def selected(pattern, include_prereleases=False):
    """How the download recipe chooses its file in AutoPkg 2.9.0 (`GitHubReleasesInfoProvider.py`,
    `select_asset`): the releases in the order that GitHub lists them (newest first), a pre-release
    skipped unless `include_prereleases` is true, and in a release the first asset whose name the
    pattern matches from its start (`re.match`). Returns (tag, asset name) or None."""
    for release in releases():
        if release["prerelease"] and not include_prereleases:
            continue
        for asset in release["assets"]:
            if re.match(pattern, asset["name"]):
                return release["tag_name"], asset["name"]
    return None


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
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.Greenshot-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".pcman.Greenshot")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [
            "GitHubReleasesInfoProvider", "URLDownloader", "EndOfCheckPhase",
            SHARED_PREFIX + "GitHubAssetDigest", SHARED_PREFIX + "ChecksumVerifier",
            SHARED_PREFIX + "WindowsExeVersion",
        ])

    def test_the_pcman_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(PCMAN)["Process"]]
        self.assertEqual(steps, [PCMAN_PREFIX + "PcmanImporter"])

    def test_the_provider_arguments(self):
        args = load(DOWNLOAD)["Process"][0]["Arguments"]
        self.assertEqual(args["github_repo"], "greenshot/greenshot")
        self.assertEqual(args["asset_regex"], "%SEARCH_PATTERN%")
        self.assertNotIn("include_prereleases", args)
        self.assertEqual(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"], r"Greenshot-INSTALLER-[0-9.]+-RELEASE\.exe$")

    def test_pre_releases_are_a_switch_of_the_input_that_an_override_can_change(self):
        """AutoPkg 2.9.0 puts the Input of the recipe and of the override into the run first and
        injects the Arguments of each step after them (`autopkglib/__init__.py`:
        `process_cli_overrides`, then `Processor.inject`), so a value in the Arguments would beat
        the override. The switch is therefore a key of the Input, with the name of the provider's
        own input variable. The provider reads it from the run and tests its truth
        (`GitHubReleasesInfoProvider.py`, `select_asset`), so the text `false` counts as true and
        the value is a boolean. A `%variable%` that holds a boolean stops the whole run with a
        TypeError (`update_data` in `autopkglib/__init__.py`, where only a KeyError is caught), so
        no step names the key; the last loop of this test keeps every such reference away from the
        booleans of the Input."""
        recipe = load(DOWNLOAD)
        self.assertIs(recipe["Input"]["include_prereleases"], False)
        arguments = recipe["Process"][0]["Arguments"]
        self.assertNotIn("include_prereleases", arguments)
        for override_input, wanted in (({}, False), ({"include_prereleases": True}, True)):
            run = dict(recipe["Input"])  # the recipe's Input
            run.update(override_input)  # then the override's Input
            run.update(arguments)  # then the Arguments of the step
            self.assertIs(run["include_prereleases"], wanted)
        for step in recipe["Process"]:
            for key, value in step.get("Arguments", {}).items():
                match = re.fullmatch(r"%([A-Za-z_]+)%", value) if isinstance(value, str) else None
                if match:
                    self.assertNotIsInstance(recipe["Input"].get(match.group(1)), bool, key)

    def test_the_default_pattern_takes_the_installer_and_not_the_other_files(self):
        """The names are those of GitHub's release list of 2026-10-04 (releases_excerpt.json); the
        last two of the names that must not match are made up."""
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        for name in ("Greenshot-INSTALLER-1.3.315-RELEASE.exe", "Greenshot-INSTALLER-1.3.312-RELEASE.exe",
                     "Greenshot-INSTALLER-1.3.311-RELEASE.exe"):
            self.assertTrue(pattern.match(name), name)
        for name in ("Greenshot-PORTABLE-1.3.315-RELEASE.zip", "Greenshot-INSTALLER-1.3.315-RELEASE.exe.sha256",
                     "Greenshot-INSTALLER-1.3.315-RELEASE.msi", "Greenshot-1.3.315-RELEASE.exe",
                     "Greenshot-INSTALLER-RELEASE.exe", "Greenshot-INSTALLER-1.3.315-UNSTABLE.exe",
                     "Greenshot-INSTALLER-1.3.319-UNSTABLE-UNSIGNED.exe",
                     "Greenshot-INSTALLER-1.4.289-g7bee683e93-UNSTABLE-UNSIGNED.exe",
                     "Greenshot-Light-INSTALLER-1.4.289-g7bee683e93-UNSTABLE-UNSIGNED.exe",
                     "Greenshot-Light-INSTALLER-1.3.315-RELEASE.exe"):
            self.assertIsNone(pattern.match(name), name)

    def test_the_pattern_takes_exactly_the_installer_of_each_release_that_is_not_flagged(self):
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        self.assertEqual(len(releases()), 12)
        unflagged = 0
        for release in releases():
            hits = [asset["name"] for asset in release["assets"] if pattern.match(asset["name"])]
            with self.subTest(release=release["tag_name"]):
                if release["prerelease"]:
                    self.assertEqual(hits, [])
                else:
                    unflagged += 1
                    self.assertEqual(hits, ["Greenshot-INSTALLER-%s-RELEASE.exe" % release["tag_name"][1:]])
        self.assertEqual(unflagged, 3)

    def test_no_unstable_or_light_name_of_the_excerpt_matches(self):
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        names = [asset["name"] for release in releases() for asset in release["assets"]
                 if "UNSTABLE" in asset["name"] or "Light" in asset["name"]]
        self.assertGreater(len(names), 10)
        for name in names:
            self.assertIsNone(pattern.match(name), name)

    def test_the_flags_of_the_excerpt_are_what_the_readme_says(self):
        flags = {release["tag_name"]: release["prerelease"] for release in releases()}
        self.assertEqual([tag for tag, flagged in flags.items() if not flagged], ["v1.3.315", "v1.3.312", "v1.3.311"])
        for tag, flagged in flags.items():
            if tag.startswith("v1.4."):
                self.assertTrue(flagged, tag)
        for release in releases():
            if any("UNSTABLE" in asset["name"] for asset in release["assets"]):
                self.assertTrue(release["prerelease"], release["tag_name"])

    def test_with_pre_releases_skipped_the_recipe_takes_the_installer_of_v1_3_315(self):
        pattern = load(DOWNLOAD)["Input"]["SEARCH_PATTERN"]
        self.assertIs(load(DOWNLOAD)["Input"]["include_prereleases"], False)
        self.assertEqual(selected(pattern), ("v1.3.315", "Greenshot-INSTALLER-1.3.315-RELEASE.exe"))

    def test_with_pre_releases_allowed_the_recipe_still_takes_no_1_4_file(self):
        pattern = load(DOWNLOAD)["Input"]["SEARCH_PATTERN"]
        self.assertEqual(selected(pattern, include_prereleases=True),
                         ("v1.3.315", "Greenshot-INSTALLER-1.3.315-RELEASE.exe"))
        for release in releases():
            for asset in release["assets"]:
                if "-1.4." in asset["name"]:
                    self.assertIsNone(re.match(pattern, asset["name"]), asset["name"])

    def test_the_chosen_asset_and_every_exe_of_the_excerpt_have_a_digest(self):
        pattern = load(DOWNLOAD)["Input"]["SEARCH_PATTERN"]
        tag, name = selected(pattern)
        chosen = [asset for release in releases() if release["tag_name"] == tag
                  for asset in release["assets"] if asset["name"] == name]
        self.assertEqual(len(chosen), 1)
        self.assertIs(chosen[0]["digest_recorded"], True)
        exes = [asset for release in releases() for asset in release["assets"] if asset["name"].endswith(".exe")]
        self.assertEqual(len(exes), 14)  # 12 installers, and a second one in each of the two newest 1.4 builds
        for asset in exes:
            self.assertIs(asset["digest_recorded"], True, asset["name"])

    def test_searching_a_name_or_matching_it_from_its_start_gives_the_same_answer(self):
        """AutoPkg 2.9.0 uses `re.match`. For the recipe's pattern, searching a name gives the same
        answer as matching it from its start for every saved name, so a pattern that starts
        elsewhere in a name would not be a way round it."""
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        for release in releases():
            for asset in release["assets"]:
                self.assertEqual(bool(pattern.search(asset["name"])), bool(pattern.match(asset["name"])),
                                 asset["name"])

    def test_the_inputs_of_the_pcman_recipe(self):
        recipe = load(PCMAN)
        self.assertEqual(recipe["Input"]["NAME"], "Greenshot")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "greenshot")
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%",
                                "pcman_version": "%version%"})

    def test_the_exe_version_step_is_last_and_reads_the_downloaded_file(self):
        steps = load(DOWNLOAD)["Process"]
        names = [step["Processor"] for step in steps]
        self.assertEqual(names[-1], SHARED_PREFIX + "WindowsExeVersion")
        self.assertLess(names.index("EndOfCheckPhase"), names.index(SHARED_PREFIX + "ChecksumVerifier"))
        self.assertLess(names.index(SHARED_PREFIX + "ChecksumVerifier"), len(names) - 1)
        self.assertEqual(steps[-1]["Arguments"], {"pathname": "%pathname%"})  # set_version stays at its default

    def test_the_digest_and_the_checksum_arguments(self):
        steps = dict(shared_steps(load(DOWNLOAD)))
        self.assertEqual(steps["GitHubAssetDigest"], {"github_asset_api_url": "%asset_url%"})
        self.assertEqual(steps["ChecksumVerifier"],
                         {"pathname": "%pathname%", "expected_sha256": "%expected_sha256%"})

    def test_no_stop_on_an_unchanged_download_and_no_latest_only(self):
        for path in (DOWNLOAD, PCMAN):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.assertNotIn("StopProcessingIf", text)
            self.assertNotIn("latest_only", text)

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in (DOWNLOAD, PCMAN):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text)

    def test_the_description_says_what_a_reader_must_know(self):
        self.assertIn("newest non-pre-release", load(DOWNLOAD)["Description"])
        self.assertIn("matching file", load(DOWNLOAD)["Description"])
        self.assertIn("NOT rehearsed", load(DOWNLOAD)["Description"])
        self.assertIn("ProductVersion", load(DOWNLOAD)["Description"])
        self.assertIn("read from GitHub's release list on 2026-10-04 (the newest twelve releases)", load(DOWNLOAD)["Description"])
        self.assertIn("named like Greenshot-INSTALLER-1.3.315-RELEASE.exe", load(DOWNLOAD)["Description"])
        self.assertIn("the first run on the build Mac is the check of the rest", load(DOWNLOAD)["Description"])
        self.assertIn("dry run", load(PCMAN)["Description"])
        self.assertIn("pcman_dry_run", load(PCMAN)["Description"])


class SharedProcessorTests(unittest.TestCase):
    def test_every_named_shared_processor_is_a_file_of_the_shared_folder(self):
        for path in (DOWNLOAD, PCMAN):
            for name, _ in shared_steps(load(path)):
                self.assertTrue(os.path.isfile(os.path.join(PCMAN_DIR if name == "PcmanImporter" else SHARED_DIR, name + ".py")), name)

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

    def test_every_required_input_is_passed_or_has_a_default(self):
        """Inputs of a processor come from its arguments or from variables that
        earlier steps and the parent recipe set. The variable of the same name
        must then exist; pcman_root comes from the machine."""
        classes = processor_classes()
        provided = {  # what the earlier steps leave in the run
            "ChecksumVerifier": {"pathname", "expected_sha256"},
            "GitHubAssetDigest": set(),
            "PcmanImporter": {"pathname"},
            "WindowsExeVersion": {"pathname"},
        }
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
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            for kind, pattern in shared_hygiene.FORBIDDEN_PATTERNS.items():
                with self.subTest(file=os.path.relpath(path, RECIPE_DIR), kind=kind):
                    self.assertIsNone(pattern.search(text))

    def test_the_folder_holds_only_what_is_expected(self):
        names = sorted(os.path.relpath(path, RECIPE_DIR) for path in self.files())
        self.assertEqual(names, sorted([
            "Greenshot-Win.download.recipe", "Greenshot.cimian.recipe", "Greenshot.pcman.recipe", "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "releases_excerpt.json"),
            os.path.join("tests", "test_recipes.py"),
        ]))

    def test_no_file_holds_text_that_looks_like_an_address(self):
        """The hygiene pattern for an IPv4 address also matches a version of four numbers;
        nothing of the folder may hold one (see the pattern test)."""
        for path in self.files():
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                self.assertIsNone(re.search(r"\b\d+\.\d+\.\d+\.\d+\b", handle.read()), path)

    def test_nothing_deeper_than_the_tests_folder(self):
        for path in self.files():
            self.assertLessEqual(len(os.path.relpath(path, RECIPE_DIR).split(os.sep)), 2, path)


class ReadmeTests(unittest.TestCase):
    """The README must say what was not done and must not teach a wrong command."""

    def setUp(self):
        import re
        self.re = re
        with open(os.path.join(RECIPE_DIR, "README.md"), "r", encoding="utf-8") as handle:
            self.raw = handle.read()
        self.text = re.sub(r"\s+", " ", self.raw)

    def test_every_make_override_command_names_an_override_folder(self):
        commands = list(self.re.finditer(r"autopkg make-override([^`\n]*(?:\n[ \t]+--[^\n`]*)?)", self.raw))
        self.assertTrue(commands)
        for match in commands:
            self.assertIn("--override-dir=", match.group(1))

    def test_no_run_of_a_recipe_identifier(self):
        runs = list(self.re.finditer(r"autopkg run([^`\n]*)", self.raw))
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
                    r"<the Windows overrides folder>/Greenshot\.(?:cimian|pcman)\.recipe$",
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

    def test_the_name_check_and_the_parent_check_are_in_step_b(self):
        step = self.raw[self.raw.index("## b."):self.raw.index("## c.")]
        self.assertIn("First check that no other recipe has the same name.", step)
        self.assertIn("autopkg list-recipes | grep -i Greenshot-Win", step)
        self.assertIn("autopkg list-recipes | grep -i Greenshot.pcman", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Greenshot`",
                      re.sub(r"\s+", " ", step))
        self.assertLess(step.index("list-recipes"), step.index("autopkg make-override"))

    def test_the_readme_says_how_to_take_pre_releases_and_that_the_switch_is_a_boolean(self):
        start = self.text.index("**Pre-releases.**")
        paragraph = self.text[start:self.text.index("Below, `pcman` stands for")]
        for needle in ("the key `include_prereleases` in the recipe's `Input`, a boolean that is `false`",
                       "`make-override` copies it into the override", "never in the recipe",
                       "Set :Input:include_prereleases true",
                       "<the Windows overrides folder>/Greenshot.cimian.recipe",
                       "`Add :Input:include_prereleases bool true`",
                       "Keep it a boolean", "the text `false` would count as true",
                       "applies the arguments of a step after the override's `Input`"):
            self.assertIn(needle, paragraph)
        self.assertLess(self.raw.index("**Pre-releases.**"), self.raw.index("## a."))

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

    def test_the_steps_are_there(self):
        for needle in ("pcman catalogs", "pcman versions greenshot", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string"):
            self.assertIn(needle, self.text)

    def test_the_status_line_says_what_was_read_and_what_was_not(self):
        """Run on 2026-10-04 under AutoPkg 2.9.0; the facts of the source read from GitHub's release list
        the same day (read only)."""
        opening = "**Status. Run on 2026-10-04 under AutoPkg 2.9.0, as follows."
        self.assertLess(self.raw.index(opening), self.raw.index("## a."))
        start = self.raw.index(opening)
        paragraph = re.sub(r"\s+", " ", self.raw[start:self.raw.index("\n\n", start)])
        self.assertTrue(paragraph.startswith(opening))
        self.assertTrue(paragraph.endswith("**"))
        for needle in ("2026-10-04", "`https://api.github.com/repos/greenshot/greenshot/releases`",
                       "the newest twelve releases", "no file was downloaded",
                       "`v1.3.315` (published 2026-03-20", "`v1.3.312` and `v1.3.311`", "2026-01-07",
                       "the other nine of the twelve are flagged as pre-releases", "every `v1.4.` build",
                       "`v1.4.289-g7bee683e93`", "`-UNSTABLE-UNSIGNED`",
                       "`Greenshot-INSTALLER-1.3.315-RELEASE.exe` (3967064 bytes)",
                       "`Greenshot-PORTABLE-1.3.315-RELEASE.zip` (3722113 bytes)",
                       "`Greenshot-Light-INSTALLER-...`", "`Greenshot-INSTALLER-[0-9.]+-RELEASE\\.exe$`",
                       "no other file of the twelve releases",
                       "records a SHA-256 digest for every file of the twelve releases",
                       "AutoPkg 2.9.0 (which takes the first release", "`select_asset`", "`re.match`",
                       "took `Greenshot-INSTALLER-1.3.315-RELEASE.exe` of `v1.3.315` in the runs of 2026-10-04",
                       "`GitHubAssetDigest` found its digest",
                       "Still NOT established after those runs: that the switches install silently on a PC",
                       "the architecture of the installed program", "that the next release keeps these names",
                       "`/VERYSILENT /NORESTART`", "writer's knowledge",
                       "An install on a test PC is the check of what is NOT established",
                       "stop; nothing was written", "never the trust information first", "carries `--override-dir`"):
            self.assertIn(needle, paragraph)
        for gone in ("is expected to take `Greenshot-INSTALLER", "any run with AutoPkg", "first run on the build Mac",
                     "that the installer has a version resource, and what its `ProductVersion` text is"):
            self.assertNotIn(gone, paragraph)
        for old in ("fetched by the writer", "through git and tags only", "1.2", "2017", "predate",
                    "names of the 1.4 assets were NOT seen", "hand import", "owner's decision"):
            self.assertNotIn(old, paragraph)
        self.assertNotIn("Rehearsed on", self.raw)

    def test_the_pair_is_not_marked_as_not_working_anywhere(self):
        """By the release list of 2026-10-04 the pair is expected to find `v1.3.315` and go on. A mark
        that says that it stops, or a sentence from the time when a release of 2017 was believed to be
        the only match, must not come back, in the README or in either Description."""
        texts = {"README": self.raw, "download Description": load(DOWNLOAD)["Description"],
                 "cimian Description": load(PCMAN)["Description"]}
        for where, text in texts.items():
            flat = re.sub(r"\s+", " ", text)
            for phrase in ("NOT WORKING", "not working", "expected to stop", "stop at its first run",
                           "stops at its first run", "publish nothing", "2017",
                           "predate", "nobody has seen", "1.2 line", "last 1.2 release",
                           "decision at the merge", "whether it stays in the repository"):
                with self.subTest(where=where, phrase=phrase):
                    self.assertNotIn(phrase, flat)

    def test_the_readme_names_the_size_and_name_of_each_file_that_it_talks_about(self):
        sizes = {asset["name"]: asset["size"] for release in releases() for asset in release["assets"]}
        for name in ("Greenshot-INSTALLER-1.3.315-RELEASE.exe", "Greenshot-PORTABLE-1.3.315-RELEASE.zip"):
            self.assertIn("`%s` (%d bytes)" % (name, sizes[name]), self.text)
        titles = {release["tag_name"]: (release["name"], release["published_at"][:10]) for release in releases()}
        self.assertEqual(titles["v1.3.315"], ("Greenshot 1.3.315", "2026-03-20"))
        self.assertEqual(titles["v1.3.312"][1], "2026-01-07")
        self.assertEqual(titles["v1.3.311"][1], "2026-01-07")
        self.assertEqual(titles["v1.4.289-g7bee683e93"][1], "2026-10-04")
        self.assertIn("titled \"Greenshot 1.3.315\"", self.text)

    def test_the_readme_says_what_taking_the_1_4_line_would_need_and_does_not_do_it(self):
        start = self.text.index("**The 1.4 line.**")
        paragraph = self.text[start:self.text.index("Below, `pcman` stands for")]
        for needle in ("published only as pre-releases", "do not match the pattern",
                       "With `include_prereleases` set to true and nothing else changed, the recipe still takes "
                       "`Greenshot-INSTALLER-1.3.315-RELEASE.exe` of `v1.3.315`",
                       "two changes in the override's `Input`, and the recipe makes neither",
                       "`include_prereleases` true", "`SEARCH_PATTERN` changed",
                       "not the `Greenshot-Light-INSTALLER-...` file beside it", "the owner's decision"):
            self.assertIn(needle, paragraph)
        self.assertLess(self.raw.index("**The 1.4 line.**"), self.raw.index("## a."))
        # the example in the README takes the 1.4 installer of each 1.4 build and no other file of the excerpt
        example = re.search(r"for example `([^`]+)`", paragraph).group(1)
        for release in releases():
            hits = [asset["name"] for asset in release["assets"] if re.match(example, asset["name"])]
            with self.subTest(release=release["tag_name"]):
                if release["tag_name"].startswith("v1.4."):
                    self.assertEqual(hits, ["Greenshot-INSTALLER-%s-UNSTABLE-UNSIGNED.exe" % release["tag_name"][1:]])
                else:
                    self.assertEqual(hits, [])
        # and the recipe itself makes neither change
        self.assertEqual(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"], r"Greenshot-INSTALLER-[0-9.]+-RELEASE\.exe$")
        self.assertIs(load(DOWNLOAD)["Input"]["include_prereleases"], False)

    def test_the_first_import_is_for_an_exe_and_marks_what_is_from_knowledge(self):
        step = self.raw[self.raw.index("## a."):self.raw.index("## b.")]
        text = re.sub(r"\s+", " ", step)
        for needle in ("--name greenshot", "--version <the label that the first dry run prints>",
                       "--display-name", "--category", "--developer",
                       "--description", "--install-arguments '/VERYSILENT /NORESTART'", "--icon", "in the form that ran on 2026-10-04",
                       "**used on 2026-10-04, not tested on a PC**", "the file has \"Inno Setup\"",
                       "`--architectures x64` is an expectation, not a fact",
                       "architecture of the installed program is NOT established",
                       "`--install-path` was left out because the path must be read on that PC after a test install"):
            self.assertIn(needle, text)
        self.assertNotIn("--install-path '", text)
        self.assertEqual(len(re.findall(r"--version ", text)), 1)

    def test_the_label_section_says_where_the_label_comes_from(self):
        section = self.raw[self.raw.index("## The label"):self.raw.index("## Run every override")]
        text = re.sub(r"\s+", " ", section)
        for needle in ("`v1.3.315`, which gives `1.3.315`", "`v1.4.289-g7bee683e93` gives `1.4.289-g7bee683e93`",
                       "which is not a label", "`WindowsExeVersion`",
                       "`ProductVersion`", "overwrites `version`", "`pcman_version`",
                       "numbers and dots only", "four numbers", "the first import (step a)",
                       "is NOT established"):
            self.assertIn(needle, text)
        self.assertNotIn("1.4.280", text)

    def test_the_dry_run_step_says_to_read_the_label_lines_and_the_selected_asset(self):
        step = self.raw[self.raw.index("## c."):self.raw.index("## d.")]
        text = re.sub(r"\s+", " ", step)
        self.assertIn("autopkg run -v --override-dir=", step)  # -v prints the lines of the label step
        self.assertIn("`-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the repository among them, "
                      "and such a log would have to be kept private", re.sub(r"\s+", " ", step))
        self.assertIn("version is ..., taken from ...", text)
        for needle in ("`Selected asset '...' from release '...'`", "`select_asset`",
                       "names `Greenshot-INSTALLER-1.3.315-RELEASE.exe` and `Greenshot 1.3.315`",
                       "If it names a file with `UNSTABLE`, `Light` or `PORTABLE` in its name, stop and tell the owner"):
            self.assertIn(needle, text)
        self.assertNotIn("begins `1.2.`", text)
        self.assertNotIn("2017", text)

    def test_no_label_is_invented(self):
        """The label is read from the file at the first run; the README gives a placeholder."""
        self.assertNotRegex(self.raw, r"greenshot\s+[0-9]")
        self.assertNotRegex(self.raw, r"--version [0-9]")


class ChainTests(_pcman_support.ToolTestCase):
    """The chain of this program counts as verified for the importer: the real
    ChecksumVerifier hashes the file, and the importer hashes it again and
    compares. The stand-in package tool is used; nothing else is run."""

    TAG_VERSION = "1.3.315"              # what the provider makes of the tag v1.3.315
    PRODUCT_VERSION = "9.8.7"            # made up: the real ProductVersion is NOT known

    def setUp(self):
        super().setUp()
        # The installer is a small PE file with a version resource, so that the
        # recipe's own WindowsExeVersion step can read it.
        built = exe_tests.build_pe(exe_tests.version_info(
            product=self.PRODUCT_VERSION, file=self.PRODUCT_VERSION, name="Example App",
            file_numbers=(9, 8, 7, 0), product_numbers=(9, 8, 7, 0)))
        with open(self.exe, "wb") as handle:
            handle.write(bytes(built.data))

    def chain_env(self, installer):
        """What the steps of the two recipes leave in the run, with the
        arguments of the recipe's own steps. The download recipe's last step
        is run with the recipe's own arguments."""
        run = {"pathname": installer, "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        steps = {step["Processor"][len(SHARED_PREFIX):]: step.get("Arguments", {})
                 for step in load(DOWNLOAD)["Process"] if step["Processor"].startswith(SHARED_PREFIX)}
        values = {"%pathname%": installer}
        reader_env = {name: values.get(value, value) for name, value in steps["WindowsExeVersion"].items()}
        reader_env["version"] = self.TAG_VERSION
        reader, _ = _win_support.run_processor(_win_support.exe_version.WindowsExeVersion, reader_env)
        values.update({"%PCMAN_TEMPLATE%": load(PCMAN)["Input"]["PCMAN_TEMPLATE"],
                       "%version%": reader.env["version"]})
        env = {"pathname": installer, "pcman_root": self.root, "pcman_dry_run": False,
               "pcman_path": self.msi_bin}
        env.update({k: v for k, v in verifier.env.items() if k.startswith("checksum_")})
        cimian_steps = [step for step in load(PCMAN)["Process"] if step["Processor"].endswith("/PcmanImporter")]
        self.assertEqual(len(cimian_steps), 1)
        for name, value in cimian_steps[0]["Arguments"].items():
            env[name] = values.get(value, value)
        return env

    def test_the_label_is_the_exe_s_own_version_and_not_the_tag(self):
        env = self.chain_env(self.exe)
        self.assertEqual(env["pcman_version"], self.PRODUCT_VERSION)
        self.assertNotEqual(env["pcman_version"], self.TAG_VERSION)
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        argv = self.record()["argv"]
        self.assertEqual(argv[argv.index("--version") + 1], self.PRODUCT_VERSION)

    def test_the_chain_counts_as_verified_and_nothing_is_warned(self):
        env = self.chain_env(self.exe)
        self.assertEqual(env["checksum_sha256"], _win_support.sha256_hex(self.exe))
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
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
            _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        self.assertIn("not the file whose checksum was verified", str(caught.exception))
        self.assertFalse(self.was_run())


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
        for needle in ("The first import (the command of step a.3 below, run with `--no-prompt` and `--build`) made the template `greenshot` (an EXE item, label `1.3.315` with a fourth part `0`, `--install-arguments '/VERYSILENT /NORESTART'`, architectures `x64`)", '`make-override` with `--override-dir`, `ParentRecipe` right, `verify-trust-info` OK, `pcman_dry_run` false', 'the provider took `Greenshot-INSTALLER-1.3.315-RELEASE.exe` of `v1.3.315`, `GitHubAssetDigest` found its digest, the checksum and the label step passed', '`PcmanImporter: Nothing new: greenshot <the label> is in the repository already. Nothing was written.`', 'went beside the Chocolatey item `greenshot` (version 1.0) without any option of the tool', 'the Chocolatey item file and its `greenshot-1.0` pkginfo remain until a person removes them by hand', '`pcman validate` warns that the item has two versions until then', '`pcman catalogs` ran once for all the new items together (2026-10-04)', '`All` and `Production`, 106 items each', 'whose `ProductVersion` text is `1.3.315+420b08b2a9`, which is not numbers and dots only', 'took the four numbers of the fixed file information (`1.3.315` and a fourth part `0`) as the label', 'the file has "Inno Setup" strings, so it is an Inno Setup installer', 'has NO install check until a person adds one', '**used on 2026-10-04, not tested on a PC**'):
            self.assertIn(needle, self.status)

    def test_the_readme_says_the_rest_of_it(self):
        for needle in ("On 2026-10-04 the `ProductVersion` string was `1.3.315+420b08b2a9` (not numbers and dots only), so the label is the fixed file information's `1.3.315` with a fourth part `0`",):
            self.assertIn(needle, self.text)

    def test_the_first_import_step_says_what_worked(self):
        step = re.sub(r"\s+", " ", self.raw[self.raw.index("3. **The template item"):self.raw.index("## b.")])
        for needle in ('in the form that ran on 2026-10-04', "--install-arguments '/VERYSILENT /NORESTART'", '--icon'):
            self.assertIn(needle, step)

    def test_nothing_that_was_not_tested_is_called_tested(self):
        for claim in ('was tested on a PC', 'the switch is established'):
            self.assertNotIn(claim, self.text)

    def test_the_second_run_line_is_not_promised_for_a_fresh_override(self):
        self.assertIn("the first run of a fresh override printed the line `Nothing new: ...` after it had downloaded the file again", self.text)
        self.assertIn("a new override gets a new cache folder", self.text)


class CatalogsStepReadmeTests(unittest.TestCase):
    """The step that builds the catalogs says what happened on 2026-10-04 and no longer says "Not rehearsed"."""

    def test_the_catalogs_step_names_the_run_of_2026_10_04(self):
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md"), "r", encoding="utf-8") as handle:
            text = re.sub(r"\s+", " ", handle.read())
        i = text.index("3. **Build the catalogs: `pcman catalogs`.**")
        step = text[i:text.index("4. The second run, by path again:", i)]
        for needle in ('(Run on 2026-10-04 for all the new items of that day together, this one among them:', "the tool's configured command ran `makecatalogs` on the repository's server",
                       "wrote the catalogs `All` and `Production`, with exit 0",
                       "The package tool prints \"nothing to run\" when its catalogs command is not set"):
            self.assertIn(needle, step)
        self.assertNotIn("Not rehearsed", step)
        self.assertNotIn("for no program", step)


class CimianVersionArgumentTextTests(unittest.TestCase):
    """The cimian recipe passes the label to `CimianImporter` as `version`; only the pcman recipe passes `pcman_version`."""

    def test_no_sentence_says_that_the_cimian_recipe_passes_pcman_version(self):
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md"), "r", encoding="utf-8") as handle:
            text = re.sub(r"\s+", " ", handle.read())
        for sentence in re.split(r"(?<=[.;])\s", text):
            if re.search(r"cimian recipe passes", sentence) and "pcman_version" in sentence:
                self.assertIn("pcman recipe", sentence)  # `pcman_version` is named only as the pcman recipe's argument
        self.assertEqual(text.count("the cimian recipe passes that `version` as `pcman_version`"), 0)


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
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.Greenshot")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.Greenshot")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotEqual(cimian["Identifier"], pcman["Identifier"])
        self.assertEqual(cimian["MinimumVersion"], pcman["MinimumVersion"])
        self.assertTrue(CIMIAN.endswith("Greenshot.cimian.recipe"))
        self.assertTrue(PCMAN.endswith("Greenshot.pcman.recipe"))

    def test_the_only_step_is_the_cimian_importer(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "CimianImporter"])

    def test_the_inputs_and_the_arguments(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], load(PCMAN)["Input"]["NAME"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], load(PCMAN)["Input"]["PCMAN_TEMPLATE"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], "greenshot")
        self.assertEqual(recipe["Input"]["CIMIAN_SUBDIRECTORY"], "")
        self.assertEqual(sorted(recipe["Input"]), ["CIMIAN_NAME", "CIMIAN_SUBDIRECTORY", "NAME", "pkginfo"])
        self.assertEqual(recipe["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": "%version%"})

    def test_the_pkginfo_gives_only_what_the_readme_states(self):
        self.assertEqual(load(CIMIAN)["Input"]["pkginfo"], {'display_name': 'Greenshot', 'developer': 'Greenshot'})

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
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "greenshot")
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
        for name, identifier in (("Greenshot.cimian.recipe", "com.github.serrc-techops.cimian.Greenshot"),
                                 ("Greenshot.pcman.recipe", "com.github.serrc-techops.pcman.Greenshot")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)
        self.assertIn("`CimianImporter`", [line for line in self.raw.splitlines() if line.startswith("| `Greenshot.cimian.recipe`")][0])
        self.assertIn("`pcman`", [line for line in self.raw.splitlines() if line.startswith("| `Greenshot.pcman.recipe`")][0])

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
        for text, recipe, other in ((self.generic, "Greenshot.cimian", "Greenshot.pcman"), (self.tool, "Greenshot.pcman", "Greenshot.cimian")):
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
            self.assertRegex(command, r"--override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot\.cimian\.recipe$")

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
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.cimian.Greenshot`**", self.generic.replace("\n", " "))
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Greenshot`**", self.tool.replace("\n", " "))
        for text in (self.generic, self.tool):
            self.assertNotIn("it must be `com.github.serrc-techops.download.", text.replace("\n", " "))

    def test_an_override_of_the_old_cimian_recipe_is_to_be_made_again_for_the_package_tool(self):
        self.assertIn("An override that was made from the old `Greenshot.cimian.recipe`", self.tool)
        self.assertIn("must be made again from `Greenshot.pcman.recipe`", self.tool)
        self.assertIn("An override that was made from this recipe before the recipes were separated", self.generic)

    def test_the_condition_of_never_overwrites_is_said(self):
        self.assertIn("do not run two runs of one item at the same time", self.generic)

    def test_the_generic_way_states_no_hash_and_no_made_up_label(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.generic))
        self.assertNotIn("Published greenshot", self.generic)

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
        self.assertIn("Greenshot.pcman", self.tool)

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
