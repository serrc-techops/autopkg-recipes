"""Tests of the Stellarium recipes. Nothing here runs AutoPkg or uses the network.

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
PATTERN = r"stellarium-([0-9]+(?:\.[0-9]+)+)-qt6-win64\.exe$"
# Names, sizes and digest flags of the newest 30 releases, read from GitHub on 2026-11-13.
RELEASES = os.path.join(TESTS_DIR, "releases_excerpt.json")
LABEL = "26.3"
TAG = "v" + LABEL
ASSET = "stellarium-%s-qt6-win64.exe" % LABEL
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "Stellarium-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "Stellarium.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "Stellarium.pcman.recipe")
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
    for name in ("PcmanImporter", "CimianImporter", "ChecksumVerifier", "GitHubAssetDigest", "GitHubNewestReleaseGuard", "VersionFromName",
                 "WindowsExeVersion"):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def releases():
    with open(RELEASES, "r", encoding="utf-8") as handle:
        return json.loads(handle.read().replace("_dot_", "."))["releases"]


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


def shared_steps(recipe):
    """The steps that name a processor of this repository, of either folder: (name, arguments)."""
    for step in recipe["Process"]:
        for prefix in (SHARED_PREFIX, PCMAN_PREFIX):
            if step["Processor"].startswith(prefix):
                yield step["Processor"][len(prefix):], step.get("Arguments", {})


def _text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class RecipeFileTests(unittest.TestCase):
    def test_all_files_are_valid_property_lists(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
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
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.Stellarium-Win")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.Stellarium")
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [
            "GitHubReleasesInfoProvider", SHARED_PREFIX + "GitHubNewestReleaseGuard", "URLDownloader",
            "EndOfCheckPhase",
            SHARED_PREFIX + "GitHubAssetDigest", SHARED_PREFIX + "ChecksumVerifier",
            SHARED_PREFIX + "VersionFromName",
        ])

    def test_the_pcman_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(PCMAN)["Process"]]
        self.assertEqual(steps, [PCMAN_PREFIX + "PcmanImporter"])

    def test_the_provider_arguments(self):
        args = load(DOWNLOAD)["Process"][0]["Arguments"]
        self.assertEqual(args["github_repo"], "Stellarium/stellarium")
        self.assertEqual(args["asset_regex"], "%SEARCH_PATTERN%")
        self.assertNotIn("include_prereleases", args)
        self.assertEqual(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"], PATTERN)

    def test_pre_releases_are_a_switch_of_the_input_that_an_override_can_change(self):
        """AutoPkg 2.9.0 puts the Input of the recipe and of the override into the run first and
        injects the Arguments of each step after them, so a value in the Arguments would beat
        the override. The switch is therefore a key of the Input, with the name of the provider's
        own input variable, and a boolean: the text `false` counts as true, and a `%variable%`
        that holds a boolean stops the whole run with a TypeError, so no step names the key."""
        recipe = load(DOWNLOAD)
        self.assertIs(recipe["Input"]["include_prereleases"], False)
        arguments = recipe["Process"][0]["Arguments"]
        self.assertNotIn("include_prereleases", arguments)
        for override_input, wanted in (({}, False), ({"include_prereleases": True}, True)):
            run = dict(recipe["Input"])
            run.update(override_input)
            run.update(arguments)
            self.assertIs(run["include_prereleases"], wanted)
        for step in recipe["Process"]:
            for key, value in step.get("Arguments", {}).items():
                match = re.fullmatch(r"%([A-Za-z_]+)%", value) if isinstance(value, str) else None
                if match:
                    self.assertNotIsInstance(recipe["Input"].get(match.group(1)), bool, key)

    def test_the_pattern_takes_the_qt6_x64_installer_and_not_the_other_files(self):
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        self.assertEqual(pattern.groups, 1)
        self.assertEqual(pattern.match(ASSET).group(1), LABEL)
        self.assertEqual(pattern.match("stellarium-1.1.1-qt6-win64.exe").group(1), "1.1.1")
        for name in ("stellarium-26.3-qt5-win64.exe", "stellarium-26.3-qt6-arm64.exe", "stellarium-25.2-qt5.15-win64.exe",
                     "stellarium-24.4-qt5-win32.exe", ASSET + ".asc", ASSET[:-4] + ".zip", "stellarium-26.3.zip",
                     "Stellarium-26.3-qt6-macOS.zip", "Stellarium-26.3-qt6-x86_64.AppImage",
                     "stellarium-qt6-win64.exe", "stellarium--qt6-win64.exe", "xstellarium-26.3-qt6-win64.exe"):
            self.assertIsNone(pattern.match(name), name)

    def test_the_saved_list_has_no_pre_release_and_no_draft(self):
        self.assertEqual(len(releases()), 30)
        self.assertFalse([r["tag_name"] for r in releases() if r["prerelease"]])

    def test_exactly_one_installer_in_each_release_that_has_one_and_none_in_the_old_ones(self):
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        with_one, without = [], []
        for release in releases():
            hits = [asset["name"] for asset in release["assets"] if pattern.match(asset["name"])]
            self.assertLessEqual(len(hits), 1, (release["tag_name"], hits))
            (with_one if hits else without).append(release["tag_name"])
        tags = [r["tag_name"] for r in releases()]
        self.assertEqual(len(with_one), 17)
        self.assertEqual(with_one, tags[:17])
        self.assertEqual(with_one[-1], "v1.1")
        self.assertEqual(without, tags[17:])
        self.assertEqual(without[0], "v1.0")

    def test_the_recipe_takes_the_newest_release(self):
        tag, name = selected(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        self.assertEqual((tag, name), (TAG, ASSET))
        self.assertEqual(tag, releases()[0]["tag_name"])

    def test_searching_a_name_or_matching_it_from_its_start_gives_the_same_answer(self):
        """AutoPkg 2.9.0 uses `re.match`. For this pattern, searching gives the same answer for
        every saved name, so a pattern that starts elsewhere in a name would not be a way round it."""
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        for release in releases():
            for asset in release["assets"]:
                self.assertEqual(bool(pattern.search(asset["name"])), bool(pattern.match(asset["name"])), asset["name"])

    def test_the_label_is_the_number_in_the_name_and_only_one_tag_differs_from_it(self):
        pattern = load(DOWNLOAD)["Input"]["SEARCH_PATTERN"]
        arguments = load(DOWNLOAD)["Process"][-1]["Arguments"]
        differ = []
        for release in releases():
            names = [a["name"] for a in release["assets"] if re.match(pattern, a["name"])]
            if not names:
                continue
            env = {"pathname": "/cache/downloads/" + names[0], "version_pattern": pattern, "version": release["tag_name"]}
            self.assertEqual(set(env) - {"version"}, set(arguments))
            processor, _ = _win_support.run_processor(_win_support.version_name.VersionFromName, env)
            label = processor.env["version"]
            self.assertIn("-" + label + "-", names[0])
            if "v" + label != release["tag_name"]:
                differ.append((release["tag_name"], label))
        self.assertEqual(differ, [("v1.1", "1.1.1")])

    def test_the_labels_are_two_numbers_apart_from_the_oldest(self):
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        labels = [pattern.match(a["name"]).group(1) for r in releases() for a in r["assets"] if pattern.match(a["name"])]
        self.assertEqual([label for label in labels if label.count(".") != 1], ["1.1.1"])

    def test_a_digest_is_recorded_from_v25_2_to_the_newest_and_for_none_before(self):
        pattern = load(DOWNLOAD)["Input"]["SEARCH_PATTERN"]
        flags = {}
        for release in releases():
            hit = [a["digest_recorded"] for a in release["assets"] if re.match(pattern, a["name"])]
            if hit:
                flags[release["tag_name"]] = hit[0]
        tags = list(flags)
        cut = tags.index("v25.2")
        self.assertEqual(cut, 5)
        self.assertTrue(all(flags[tag] for tag in tags[:cut + 1]))
        self.assertFalse(any(flags[tag] for tag in tags[cut + 1:]))
        self.assertEqual([r["published_at"][:10] for r in releases() if r["tag_name"] == "v25.2"], ["2025-06-22"])

    def test_a_digest_is_recorded_for_the_installer_of_the_release_that_the_recipe_takes(self):
        tag, name = selected(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        release = [r for r in releases() if r["tag_name"] == tag][0]
        asset = [a for a in release["assets"] if a["name"] == name][0]
        self.assertTrue(asset["digest_recorded"])
        self.assertEqual(asset["size"], 489006448)

    def test_the_download_recipe_names_no_prerelease_and_keeps_the_file_name(self):
        steps = load(DOWNLOAD)["Process"]
        downloader = [step for step in steps if step["Processor"] == "URLDownloader"][0]
        self.assertNotIn("Arguments", downloader)  # URLDownloader: the asset's own file name

    def test_the_label_step_is_last_and_reads_the_name_of_the_downloaded_file(self):
        steps = load(DOWNLOAD)["Process"]
        names = [step["Processor"] for step in steps]
        self.assertEqual(names[-1], SHARED_PREFIX + "VersionFromName")
        self.assertLess(names.index("EndOfCheckPhase"), names.index(SHARED_PREFIX + "ChecksumVerifier"))
        self.assertLess(names.index(SHARED_PREFIX + "ChecksumVerifier"), len(names) - 1)
        self.assertEqual(steps[-1]["Arguments"], {"pathname": "%pathname%", "version_pattern": "%SEARCH_PATTERN%"})

    def test_no_step_reads_a_version_resource_because_none_was_read(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            for step in load(path)["Process"]:
                self.assertFalse(step["Processor"].endswith("/WindowsExeVersion"), os.path.basename(path))

    def test_the_pcman_version_is_the_label_step_s_version(self):
        args = load(PCMAN)["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%", "pcman_version": "%version%"})
        self.assertEqual(load(PCMAN)["Input"]["NAME"], "Stellarium")
        self.assertEqual(load(PCMAN)["Input"]["PCMAN_TEMPLATE"], "stellarium")

    def test_the_digest_and_the_checksum_arguments(self):
        steps = dict(shared_steps(load(DOWNLOAD)))
        self.assertEqual(steps["GitHubAssetDigest"], {"github_asset_api_url": "%asset_url%"})
        self.assertEqual(steps["ChecksumVerifier"], {"pathname": "%pathname%", "expected_sha256": "%expected_sha256%"})

    def test_no_stop_on_an_unchanged_download_and_no_latest_only(self):
        for path in (DOWNLOAD, PCMAN):
            text = _text(path)
            self.assertNotIn("StopProcessingIf", text)
            self.assertNotIn("latest_only", text)

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in (DOWNLOAD, PCMAN):
            text = _text(path)
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text)

    def test_the_descriptions_say_what_a_reader_must_know_and_claim_no_run(self):
        download = load(DOWNLOAD)["Description"]
        for needle in ("newest non-pre-release", "matching file", "takes the version label from the asset's file name",
                       "Qt6 build for 64-bit Windows", "NOT read (nothing was downloaded)", "is NOT established",
                       "2026-11-13", "AutoPkg takes the first release that has a matching file however old it is"):
            self.assertIn(needle, download)
        self.assertNotIn("ProductVersion", download)
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            description = load(path)["Description"]
            self.assertNotIn("ehearsed", description)
            self.assertNotIn("2026-10", description)
        self.assertIn("dry run", load(PCMAN)["Description"])
        self.assertIn("pcman_dry_run", load(PCMAN)["Description"])
        self.assertIn("the one that the download recipe took from the installer's file name", load(PCMAN)["Description"])
        self.assertIn("has NOT been seen yet", load(PCMAN)["Description"])
        self.assertIn("has NOT been seen yet", load(CIMIAN)["Description"])


class NewestReleaseGuardTests(unittest.TestCase):
    """The step that stops the run when AutoPkg's provider has gone back to an older release
    (../Win-SharedProcessors/GitHubNewestReleaseGuard.py). The list is this folder's saved one
    in the shape of GitHub's API answer; the provider's choice is AutoPkg 2.9.0's rule
    (`_win_support.provider_select`) and the guard's one request is answered by the list."""

    GUARD = SHARED_PREFIX + "GitHubNewestReleaseGuard"
    NEWEST_INDEX = 0  # no release of the saved list is a pre-release
    OLDER_INDEX = 1  # where the provider goes back to when a vendor renames the file of the newest one

    def repo(self):
        return load(DOWNLOAD)["Process"][0]["Arguments"]["github_repo"]

    def pattern(self):
        return load(DOWNLOAD)["Input"]["SEARCH_PATTERN"]

    def records(self):
        owner, name = self.repo().split("/")
        saved = _win_support.saved_releases(RELEASES)
        return _win_support.records_from_saved(saved, owner, name)

    def asked(self):
        return ["https://api.github.com/repos/%s/releases?per_page=30&page=1" % self.repo()]

    def test_the_step_comes_right_after_the_provider_and_before_the_download(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps[:3], ["GitHubReleasesInfoProvider", self.GUARD, "URLDownloader"])
        self.assertEqual(steps.count(self.GUARD), 1)
        self.assertLess(steps.index(self.GUARD), steps.index("EndOfCheckPhase"))

    def test_the_step_passes_the_asset_url_and_nothing_else(self):
        self.assertEqual(load(DOWNLOAD)["Process"][1]["Arguments"], {"github_asset_api_url": "%asset_url%"})

    def test_only_an_override_can_accept_a_release_or_name_a_line(self):
        recipe = load(DOWNLOAD)
        self.assertEqual(recipe["Input"]["accepted_newest_release"], "")
        self.assertEqual(recipe["Input"]["release_tag_pattern"], "")
        self.assertIs(recipe["Input"]["include_prereleases"], False)
        self.assertNotIn("allow_older_release", recipe["Input"])
        for step in recipe["Process"]:
            for key in ("accepted_newest_release", "release_tag_pattern", "include_prereleases", "allow_older_release",
                        "sort_by_highest_tag_names", "latest_only"):
                self.assertNotIn(key, step.get("Arguments", {}))

    def test_the_guard_lets_the_run_go_on_when_the_provider_takes_the_newest_release(self):
        records = self.records()
        tag, error, asked = _win_support.guard_chain(self.repo(), self.pattern(), records)
        self.assertIsNone(error)
        self.assertEqual(tag, records[self.NEWEST_INDEX]["tag_name"])
        self.assertEqual(asked, self.asked())

    def test_a_renamed_file_in_the_newest_release_stops_the_run_where_the_provider_goes_back(self):
        records = self.records()
        renamed = _win_support.renamed_in_newest(records, self.pattern())
        tag, error, asked = _win_support.guard_chain(self.repo(), self.pattern(), renamed)
        self.assertEqual(tag, records[self.OLDER_INDEX]["tag_name"])
        self.assertEqual(asked, self.asked())
        for needle in ("Selected: release '%s'" % tag, "Newest: release '%s'" % records[self.NEWEST_INDEX]["tag_name"],
                       "renamed-", "SEARCH_PATTERN", "accepted_newest_release", "release_tag_pattern"):
            self.assertIn(needle, error)

    def test_a_renamed_installer_cannot_be_accepted_away(self):
        records = self.records()
        renamed = _win_support.renamed_in_newest(records, self.pattern())
        newest = records[self.NEWEST_INDEX]["tag_name"]
        result = _win_support.guard_run(self.repo(), self.pattern(), renamed, accepted=newest)
        self.assertEqual(result["tag"], records[self.OLDER_INDEX]["tag_name"])
        self.assertIn("That is a renamed installer, not a release without one", result["error"])
        self.assertIn("it is no longer accepted", result["error"])
        self.assertEqual([text for level, text in result["messages"] if level == 0], [])

    def test_a_dev_build_without_an_installer_is_accepted_by_its_tag_only_while_it_is_the_newest(self):
        owner, name = self.repo().split("/")
        records = self.records()
        dev = _win_support.fake_release("vNext-1", ["dev-build.zip"], owner=owner, repo=name)
        listed = [dev] + records
        tag, error, asked = _win_support.guard_chain(self.repo(), self.pattern(), listed)
        self.assertEqual(tag, records[self.NEWEST_INDEX]["tag_name"])
        self.assertIn("Newest: release 'vNext-1', with the files: dev-build.zip", error)
        result = _win_support.guard_run(self.repo(), self.pattern(), listed, accepted="vNext-1")
        self.assertEqual((result["tag"], result["error"]), (tag, None))
        newer = [_win_support.fake_release("vNext-2", ["dev-build.zip"], owner=owner, repo=name)] + listed
        error = _win_support.guard_chain(self.repo(), self.pattern(), newer, accepted="vNext-1")[1]
        self.assertIn("accepted_newest_release is 'vNext-1', which is not the newest release. ", error)

    def test_a_pattern_for_the_qt5_installer_would_also_pass_the_guard(self):
        """The guard compares releases, not files: it cannot tell the Qt6 build from the Qt5 one."""
        records = self.records()
        tag, error, _ = _win_support.guard_chain(self.repo(), r"stellarium-([0-9.]+)-qt5-win64\.exe$", records)
        self.assertIsNone(error)
        self.assertEqual(tag, records[self.NEWEST_INDEX]["tag_name"])


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
            text = _text(path)
            for kind, pattern in shared_hygiene.FORBIDDEN_PATTERNS.items():
                with self.subTest(file=os.path.relpath(path, RECIPE_DIR), kind=kind):
                    self.assertIsNone(pattern.search(text))

    def test_nothing_deeper_than_the_tests_folder(self):
        for path in self.files():
            self.assertLessEqual(len(os.path.relpath(path, RECIPE_DIR).split(os.sep)), 2, path)


class ReadmeTests(unittest.TestCase):
    """The README must say that nothing was rehearsed or fetched, and must not teach a command that loses the trust check."""

    def setUp(self):
        self.raw = _text(os.path.join(RECIPE_DIR, "README.md"))
        self.text = re.sub(r"\s+", " ", self.raw)

    def operator_commands(self):
        pattern = re.compile(r"^ {4,}(autopkg (?:run|verify-trust-info|update-trust-info)\b.*)$", re.M)
        return [match.group(1) for match in pattern.finditer(self.raw)]

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
                    r"<the Windows overrides folder>/Stellarium\.(?:cimian|pcman)\.recipe$",
                )

    def test_no_autopkg_command_line_is_missed_by_the_indent_rule(self):
        pattern = r"^[ \t]*autopkg (?:run|verify-trust-info|update-trust-info)\b"
        self.assertEqual(len(re.findall(pattern, self.raw, re.M)), len(self.operator_commands()))
        self.assertEqual(len(re.findall(r"autopkg run ", self.raw)), 6)

    def test_no_prose_line_shows_a_full_command_without_the_option(self):
        for match in re.finditer(r"`(autopkg (?:run|verify-trust-info|update-trust-info)[^`]*<[^`]*)`", self.raw):
            self.assertIn("--override-dir=", match.group(1))

    def test_the_name_check_and_the_parent_check_are_in_step_b(self):
        step = self.raw[self.raw.index("## b."):self.raw.index("## c.")]
        self.assertIn("First check that no other recipe has the same name.", step)
        self.assertIn("autopkg list-recipes | grep -i Stellarium-Win", step)
        self.assertIn("autopkg list-recipes | grep -i Stellarium.pcman", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Stellarium`", re.sub(r"\s+", " ", step))
        self.assertLess(step.index("list-recipes"), step.index("autopkg make-override"))

    def test_the_readme_says_how_to_take_pre_releases_and_that_the_switch_is_a_boolean(self):
        start = self.text.index("**Pre-releases.**")
        paragraph = self.text[start:self.text.index("Below, `pcman` stands for")]
        for needle in ("the key `include_prereleases` in the recipe's `Input`, a boolean that is `false`",
                       "`make-override` copies it into the override", "never in the recipe",
                       "Set :Input:include_prereleases true", "<the Windows overrides folder>/Stellarium.cimian.recipe",
                       "`Add :Input:include_prereleases bool true`", "Keep it a boolean", "the text `false` would count as true",
                       "applies the arguments of a step after the override's `Input`"):
            self.assertIn(needle, paragraph)
        self.assertLess(self.raw.index("**Pre-releases.**"), self.raw.index("## a."))

    def test_the_readme_states_no_hash(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.raw))

    def test_a_bold_paragraph_says_why_and_what_to_do_when_the_warning_appears(self):
        i = self.raw.index("## Run every override with `--override-dir`")
        paragraph = re.sub(r"\s+", " ", self.raw[i:i + 2500])
        for needle in ("**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`",
                       "skips the trust check with one warning line", "is missing trust info",
                       "a changed processor is not caught", "If that line ever appears in a run of an override, stop: the run was not checked.**",
                       "`FAIL_RECIPES_WITHOUT_TRUST_INFO`", "owner's decision"):
            self.assertIn(needle, paragraph)
        self.assertLess(i, self.raw.index("## a."))

    def test_the_steps_of_the_operator_are_there(self):
        for needle in ("pcman catalogs", "pcman versions stellarium", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string"):
            self.assertIn(needle, self.text)

    def test_the_status_line_says_what_was_read_and_what_was_not(self):
        opening = "**Status. New. Nothing in this folder has run under AutoPkg"
        self.assertIn(opening, self.raw)
        i = self.raw.index(opening)
        self.assertEqual(self.raw.index("# Win-Stellarium"), 0)
        self.assertLess(i, self.raw.index("| Recipe |"))
        self.assertLess(i, self.raw.index("## a."))
        paragraph = re.sub(r"\s+", " ", self.raw[i:self.raw.index("\n\n", i)])
        self.assertTrue(paragraph.endswith("**"))
        for needle in (
                "no dry run, no real run, no import with the package tool, no catalog build, and nothing was installed on a PC",
                "No file was downloaded; the installer was never opened",
                "2026-11-13", "`https://api.github.com/repos/Stellarium/stellarium/releases`", "the newest 30 releases; read only",
                "`v26.3` (published 2026-09-28, the newest)", "none of the 30 releases is flagged as a pre-release",
                "`stellarium-26.3-qt6-win64.exe`, 489006448 bytes, about 466 MiB",
                "a Qt5 build for 64-bit Windows", "a Qt6 build for ARM64", "`stellarium-25.2-qt5.15-win64.exe`",
                "the releases up to `v24.4` also have 32-bit installers",
                "`stellarium-([0-9]+(?:\\.[0-9]+)+)-qt6-win64\\.exe$`", "its one group is the label",
                "exactly one file in each of 17 of the 30 releases (`v26.3` back to `v1.1`) and none in the 13 older ones",
                "the release `v1.1` holds an installer whose name says `1.1.1`",
                "from `v25.2` (2025-06-22) to the newest", "none of `v25.1` (2025-03-23) and older",
                "NOT established", "which Windows versions the Qt6 build supports was NOT read",
                "whether the installer has a version resource (nothing was downloaded",
                "**the installer is an Inno Setup installer by the writer's knowledge, which was NOT read from the vendor and NOT checked in the file**",
                "`/VERYSILENT /NORESTART /SUPPRESSMSGBOXES`", "**NOT tested on a PC**",
                "the install path and the architecture of the installed program",
                "that the next release keeps the file's name", "about 466 MiB",
                "The template item has NO install check until a person adds one",
                "Never change the trust information first"):
            self.assertIn(needle, paragraph)
        for gone in ("Rehearsed", "rehearsal", "Run on 2026-", "110 items", "NSIS"):
            self.assertNotIn(gone, self.raw)
        self.assertNotIn("Bambu", paragraph)

    def test_the_label_is_taken_from_the_name_and_the_three_part_case_is_answered_from_the_other_readme(self):
        section = self.raw[self.raw.index("## The version label"):self.raw.index("## Run every override")]
        text = re.sub(r"\s+", " ", section)
        for needle in ("Whether this installer has a version resource was NOT read", "`VersionFromName`", "`SEARCH_PATTERN`",
                       "whose one group is the label", "two to four numbers joined by dots", "overwrites `version` with it",
                       "The tag is not the source", "**Two parts.**", "like `26.3`",
                       "The README of `Win-BambuStudio` states", "not read again for this folder",
                       "`VersionService.TryParseCalendarBuildStamp`", "`CatalogService.ExpandBuildTimestamp`",
                       "a third part of three or four digits", "A label like `26.3` has two parts and meets neither rule",
                       "**A third part.**", "`26.3.1`", "the shape `yy.M.x`", "`26.3.1` (one digit) is not",
                       "`26.3.100` or `26.3.1000` would be", "how the client treats the missing third part of `26.3` was NOT read here",
                       "stop and tell the owner", "`Selected asset ... from release ...`", "**Read them first**"):
            self.assertIn(needle, text)
        for needle in ("`ProductVersion`", "Answered:"):
            self.assertNotIn(needle, text)

    def test_the_label_is_never_a_four_number_address_and_the_command_names_the_exe_only_flags(self):
        self.assertIsNone(re.search(r"(?<![0-9.])[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(?![0-9])", self.raw))
        step = self.raw[self.raw.index("3. **The template item"):self.raw.index("## b.")]
        command = step[step.index("pcman import"):step.index("--build") + len("--build")]
        for flag in ("--name stellarium", "--version <label>", "--display-name", "--category", "--developer \"Stellarium team\"",
                     "--description", "--install-arguments", "--architectures x64", "--icon", "--no-prompt"):
            self.assertIn(flag, command)
        self.assertNotIn("--install-path", command)
        flat = re.sub(r"\s+", " ", step)
        for needle in ("is a **proposal, NOT run**", "an Inno Setup installer, which was NOT read from the vendor and NOT checked in the file",
                       "**they are NOT tested on a PC**", "How `pcman import` wants several switches written", "was NOT read: read its help",
                       "**Still to fill in:** the architecture and the install path",
                       "`--install-path` is left out because the path must be read on a PC after a hand install",
                       "`--version <label>` is for an EXE only"):
            self.assertIn(needle, flat)

    def test_the_first_dry_run_names_what_can_stop_it(self):
        step = re.sub(r"\s+", " ", self.raw[self.raw.index("## c."):self.raw.index("## d.")])
        for needle in ("No asset matches", "`GitHubAssetDigest` stops with its error", "a hand import",
                       "The package tool refuses the label", "compare it with the version that the installed program shows",
                       "`VersionFromName` stops", "is not two to four numbers joined by dots",
                       "The run goes on, but with an old release", "`Selected asset ... from release ...`"):
            self.assertIn(needle, step)
        self.assertNotIn("WindowsExeVersion", step)
        self.assertNotIn("This is what happened", step)
        self.assertIn("autopkg run -v --override-dir=", step)
        self.assertIn("`-vv` would add every processor's inputs and outputs to the log", step)

    def test_the_readme_says_that_the_provider_goes_back_when_a_name_changes(self):
        self.assertIn("takes the first release, newest first, that has a file whose name matches `SEARCH_PATTERN`, however old", self.text)
        self.assertIn("Read the `Selected asset` line of every dry run", self.text)
        self.assertIn("The guard compares positions in GitHub's list, not versions", self.text)
        self.assertIn("It compares releases, not files", self.text)
        self.assertIn("the trust information of the two recipes and the five processors that are not part of AutoPkg itself", self.text)

    def test_the_catalogs_step_claims_no_run(self):
        i = self.text.index("3. **Build the catalogs: `pcman catalogs`.**")
        step = self.text[i:self.text.index("4. The second run, by path again:", i)]
        self.assertIn("(Not run.", step)


class ChainTests(_pcman_support.ToolTestCase):
    """The chain of this program counts as verified for the importer: the real
    ChecksumVerifier hashes the file, and the importer hashes it again and
    compares. The stand-in package tool is used; nothing else is run. The
    installer of these tests has the name of the real one and no version resource."""

    def setUp(self):
        super().setUp()
        built = exe_tests.build_pe(exe_tests.version_info(), types=(3,))  # a resource, but not RT_VERSION
        self.exe = os.path.join(self.downloads, ASSET)
        with open(self.exe, "wb") as handle:
            handle.write(bytes(built.data))

    def chain_env(self, installer):
        """What the steps of the two recipes leave in the run, with the arguments of the recipe's own steps."""
        run = {"pathname": installer, "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        steps = {step["Processor"][len(SHARED_PREFIX):]: step.get("Arguments", {})
                 for step in load(DOWNLOAD)["Process"] if step["Processor"].startswith(SHARED_PREFIX)}
        values = {"%pathname%": installer, "%SEARCH_PATTERN%": load(DOWNLOAD)["Input"]["SEARCH_PATTERN"]}
        reader_env = {name: values.get(value, value) for name, value in steps["VersionFromName"].items()}
        reader_env["version"] = "the tag of the release"
        reader, _ = _win_support.run_processor(_win_support.version_name.VersionFromName, reader_env)
        values.update({"%PCMAN_TEMPLATE%": load(PCMAN)["Input"]["PCMAN_TEMPLATE"], "%version%": reader.env["version"]})
        env = {"pathname": installer, "pcman_root": self.root, "pcman_dry_run": False, "pcman_path": self.msi_bin}
        env.update({k: v for k, v in verifier.env.items() if k.startswith("checksum_")})
        steps = [step for step in load(PCMAN)["Process"] if step["Processor"].endswith("/PcmanImporter")]
        self.assertEqual(len(steps), 1)
        for name, value in steps[0]["Arguments"].items():
            env[name] = values.get(value, value)
        return env

    def test_a_file_without_a_version_resource_stops_the_exe_version_step_which_the_recipe_does_not_use(self):
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_win_support.exe_version.WindowsExeVersion, {"pathname": self.exe})
        self.assertIn("the file has no version resource (RT_VERSION)", str(caught.exception))

    def test_the_label_is_the_version_in_the_file_name(self):
        env = self.chain_env(self.exe)
        self.assertEqual(env["pcman_version"], LABEL)
        _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        argv = self.record()["argv"]
        self.assertEqual(argv[argv.index("--version") + 1], LABEL)

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
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.Stellarium")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.Stellarium")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotEqual(cimian["Identifier"], pcman["Identifier"])
        self.assertEqual(cimian["MinimumVersion"], pcman["MinimumVersion"])
        self.assertTrue(CIMIAN.endswith("Stellarium.cimian.recipe"))
        self.assertTrue(PCMAN.endswith("Stellarium.pcman.recipe"))

    def test_the_only_step_is_the_cimian_importer(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "CimianImporter"])

    def test_the_inputs_and_the_arguments(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], load(PCMAN)["Input"]["NAME"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], load(PCMAN)["Input"]["PCMAN_TEMPLATE"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], "stellarium")
        self.assertEqual(recipe["Input"]["CIMIAN_SUBDIRECTORY"], "")
        self.assertEqual(sorted(recipe["Input"]), ["CIMIAN_NAME", "CIMIAN_SUBDIRECTORY", "NAME", "pkginfo"])
        self.assertEqual(recipe["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": "%version%"})

    def test_the_pkginfo_gives_only_what_the_readme_states(self):
        self.assertEqual(load(CIMIAN)["Input"]["pkginfo"], {'display_name': 'Stellarium', 'developer': 'Stellarium team'})

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
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "stellarium")
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
        for name, identifier in (("Stellarium.cimian.recipe", "com.github.serrc-techops.cimian.Stellarium"),
                                 ("Stellarium.pcman.recipe", "com.github.serrc-techops.pcman.Stellarium")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)
        self.assertIn("`CimianImporter`", [line for line in self.raw.splitlines() if line.startswith("| `Stellarium.cimian.recipe`")][0])
        self.assertIn("`pcman`", [line for line in self.raw.splitlines() if line.startswith("| `Stellarium.pcman.recipe`")][0])

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
        for text, recipe, other in ((self.generic, "Stellarium.cimian", "Stellarium.pcman"), (self.tool, "Stellarium.pcman", "Stellarium.cimian")):
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
            self.assertRegex(command, r"--override-dir=<the Windows overrides folder> <the Windows overrides folder>/Stellarium\.cimian\.recipe$")

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
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.cimian.Stellarium`**", self.generic.replace("\n", " "))
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Stellarium`**", self.tool.replace("\n", " "))
        for text in (self.generic, self.tool):
            self.assertNotIn("it must be `com.github.serrc-techops.download.", text.replace("\n", " "))

    def test_an_override_of_the_old_cimian_recipe_is_to_be_made_again_for_the_package_tool(self):
        self.assertIn("An override that was made from the old `Stellarium.cimian.recipe`", self.tool)
        self.assertIn("must be made again from `Stellarium.pcman.recipe`", self.tool)
        self.assertIn("An override that was made from this recipe before the recipes were separated", self.generic)

    def test_the_condition_of_never_overwrites_is_said(self):
        self.assertIn("do not run two runs of one item at the same time", self.generic)

    def test_the_generic_way_states_no_hash_and_no_made_up_label(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.generic))
        self.assertNotIn("Published stellarium", self.generic)

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
        self.assertIn("Stellarium.pcman", self.tool)

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
        VersionFromName leaves in `version` for an .exe."""
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
