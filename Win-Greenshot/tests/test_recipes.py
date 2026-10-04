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
if SHARED_TESTS_DIR not in sys.path:
    sys.path.insert(0, SHARED_TESTS_DIR)

import _win_support  # noqa: E402,F401  (installs the autopkglib stand-in, imports the processors)
import test_exe_version as exe_tests  # noqa: E402  (builds a small PE file; its tests are not collected here)
import test_public_repository as shared_hygiene  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "Greenshot-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "Greenshot.cimian.recipe")
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
    for name in ("PcmanImporter", "ChecksumVerifier", "GitHubAssetDigest", "WindowsExeVersion"):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def shared_steps(recipe):
    for step in recipe["Process"]:
        if step["Processor"].startswith(SHARED_PREFIX):
            yield step["Processor"][len(SHARED_PREFIX):], step.get("Arguments", {})


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
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.Greenshot-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.Greenshot")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [
            "GitHubReleasesInfoProvider", "URLDownloader", "EndOfCheckPhase",
            SHARED_PREFIX + "GitHubAssetDigest", SHARED_PREFIX + "ChecksumVerifier",
            SHARED_PREFIX + "WindowsExeVersion",
        ])

    def test_the_cimian_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "PcmanImporter"])

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

    def test_the_inputs_of_the_cimian_recipe(self):
        recipe = load(CIMIAN)
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
        for path in (DOWNLOAD, CIMIAN):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.assertNotIn("StopProcessingIf", text)
            self.assertNotIn("latest_only", text)

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in (DOWNLOAD, CIMIAN):
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
        self.assertIn("dry run", load(CIMIAN)["Description"])
        self.assertIn("pcman_dry_run", load(CIMIAN)["Description"])


class SharedProcessorTests(unittest.TestCase):
    def test_every_named_shared_processor_is_a_file_of_the_shared_folder(self):
        for path in (DOWNLOAD, CIMIAN):
            for name, _ in shared_steps(load(path)):
                self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, name + ".py")), name)

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
            "Greenshot-Win.download.recipe", "Greenshot.cimian.recipe", "README.md",
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
        self.assertEqual(len([c for c in commands if c.startswith("autopkg run")]), 3)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg verify-trust-info")]), 2)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg update-trust-info")]), 1)
        for command in commands:
            with self.subTest(command=command):
                self.assertRegex(
                    command,
                    r"^autopkg (run|verify-trust-info|update-trust-info)( -vv?)? "
                    r"--override-dir=<the Windows overrides folder> "
                    r"<the Windows overrides folder>/Greenshot\.cimian\.recipe$",
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

    def test_the_name_check_and_the_parent_check_are_in_step_b(self):
        step = self.raw[self.raw.index("## b."):self.raw.index("## c.")]
        self.assertIn("First check that no other recipe has the same name.", step)
        self.assertIn("autopkg list-recipes | grep -i Greenshot-Win", step)
        self.assertIn("autopkg list-recipes | grep -i Greenshot.cimian", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.download.Greenshot-Win`",
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
        """Read from GitHub's release list on 2026-10-04 (read only); nothing was run."""
        self.assertLess(self.raw.index("**Status. NOT rehearsed"), self.raw.index("## a."))
        start = self.raw.index("**Status. NOT rehearsed")
        paragraph = re.sub(r"\s+", " ", self.raw[start:self.raw.index("\n\n", start)])
        self.assertTrue(paragraph.startswith(
            "**Status. NOT rehearsed with AutoPkg: nothing in this folder has run with AutoPkg"))
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
                       "is expected to take `Greenshot-INSTALLER-1.3.315-RELEASE.exe` of `v1.3.315`",
                       "`GitHubAssetDigest` is expected to find its digest",
                       "NOT established:", "that the installer has a version resource",
                       "what its `ProductVersion` text is", "`WindowsExeVersion` overwrites `version`",
                       "`/VERYSILENT /NORESTART`", "writer's knowledge", "its architecture", "the template item",
                       "`pcman catalogs`", "any run with AutoPkg", "first run on the build Mac",
                       "stop; nothing was written", "never the trust information first", "carries `--override-dir`"):
            self.assertIn(needle, paragraph)
        for old in ("fetched by the writer", "through git and tags only", "1.2", "2017", "predate",
                    "names of the 1.4 assets were NOT seen", "hand import", "owner's decision"):
            self.assertNotIn(old, paragraph)
        self.assertNotIn("Rehearsed on", self.raw)

    def test_the_pair_is_not_marked_as_not_working_anywhere(self):
        """By the release list of 2026-10-04 the pair is expected to find `v1.3.315` and go on. A mark
        that says that it stops, or a sentence from the time when a release of 2017 was believed to be
        the only match, must not come back, in the README or in either Description."""
        texts = {"README": self.raw, "download Description": load(DOWNLOAD)["Description"],
                 "cimian Description": load(CIMIAN)["Description"]}
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
        for needle in ("--name greenshot", "--version <the installer's own ProductVersion",
                       "--display-name", "--category", "--developer",
                       "--description", "--install-arguments", "/VERYSILENT /NORESTART",
                       "(from the writer's knowledge, not read in the installer)",
                       "`--architectures x64` is an expectation, not a fact",
                       "its architecture is NOT established"):
            self.assertIn(needle, text)
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


class ChainTests(_win_support.ToolTestCase):
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
        values.update({"%PCMAN_TEMPLATE%": load(CIMIAN)["Input"]["PCMAN_TEMPLATE"],
                       "%version%": reader.env["version"]})
        env = {"pathname": installer, "pcman_root": self.root, "pcman_dry_run": False,
               "pcman_path": self.msi_bin}
        env.update({k: v for k, v in verifier.env.items() if k.startswith("checksum_")})
        cimian_steps = [step for step in load(CIMIAN)["Process"] if step["Processor"].endswith("/PcmanImporter")]
        self.assertEqual(len(cimian_steps), 1)
        for name, value in cimian_steps[0]["Arguments"].items():
            env[name] = values.get(value, value)
        return env

    def test_the_label_is_the_exe_s_own_version_and_not_the_tag(self):
        env = self.chain_env(self.exe)
        self.assertEqual(env["pcman_version"], self.PRODUCT_VERSION)
        self.assertNotEqual(env["pcman_version"], self.TAG_VERSION)
        processor, _ = _win_support.run_processor(_win_support.importer.PcmanImporter, env)
        argv = self.record()["argv"]
        self.assertEqual(argv[argv.index("--version") + 1], self.PRODUCT_VERSION)

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
