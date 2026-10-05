"""Tests of the two Bambu Studio recipes. Nothing here runs AutoPkg or uses the network.

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
PATTERN = r"Bambu_Studio_(?:win_public|win|public)[_-]v([0-9]+(?:\.[0-9]+)+)-[0-9]+\.exe$"
# The pattern of the first run with AutoPkg 2.9.0 (2026-10-04): one spelling of the name, and no group.
OLD_PATTERN = r"Bambu_Studio_win_public-v[0-9.]+-[0-9]+\.exe$"
# Names, sizes and digest flags of the newest 28 releases, read from GitHub on 2026-10-04.
RELEASES = os.path.join(TESTS_DIR, "releases_excerpt.json")
# A label of four numbers joined by dots reads as an IPv4 address to the repository's hygiene
# check, so it is built here and never written out in a file of the folder.
TAG_PARTS = ("02", "08", "02", "61")
LABEL = ".".join(TAG_PARTS)
TAG = "v" + LABEL
STAMP = "20260820225108"
ASSET = "Bambu_Studio_win-%s-%s.exe" % (TAG, STAMP)
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "BambuStudio-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "BambuStudio.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "BambuStudio.pcman.recipe")
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


def shared_steps(recipe):
    """The steps that name a processor of this repository, of either folder: (name, arguments)."""
    for step in recipe["Process"]:
        for prefix in (SHARED_PREFIX, PCMAN_PREFIX):
            if step["Processor"].startswith(prefix):
                yield step["Processor"][len(prefix):], step.get("Arguments", {})


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
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.BambuStudio-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".pcman.BambuStudio")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
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
        self.assertEqual(args["github_repo"], "bambulab/BambuStudio")
        self.assertEqual(args["asset_regex"], "%SEARCH_PATTERN%")
        self.assertNotIn("include_prereleases", args)
        self.assertEqual(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"], PATTERN)

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

    def test_the_default_pattern_matches_the_four_spellings_of_the_exe_and_not_the_others(self):
        """The names are those of GitHub's release list of 2026-10-04 (releases_excerpt.json)."""
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        self.assertEqual(pattern.groups, 1)
        for spelling in ("Bambu_Studio_win_public-%s-%s.exe", "Bambu_Studio_win-%s-%s.exe",
                         "Bambu_Studio_win_%s-%s.exe", "Bambu_Studio_public-%s-%s.exe"):
            name = spelling % (TAG, STAMP)
            self.assertTrue(pattern.match(name), name)
            self.assertEqual(pattern.match(name).group(1), LABEL)
        for name in (ASSET[:-4] + ".zip", ASSET + ".sig", ASSET[:-4] + ".msi",
                     "Bambu_Studio_win-%s.exe" % TAG,  # no build date
                     "Bambu_Studio_win-%s-%s_portable.zip" % (TAG, STAMP),
                     "BambuStudio_ubuntu22.04-%s-%s.AppImage" % (TAG, STAMP),
                     "Bambu_Studio_mac-%s-%s.dmg" % (TAG, STAMP),
                     "Bambu_Studio_linux_fedora-%s.AppImage" % TAG,
                     "Bambu_Studio_mac-%s-pre_release.dmg" % TAG,
                     "Bambu_Studio_win-v-%s.exe" % STAMP):
            self.assertIsNone(pattern.match(name), name)

    def test_every_release_of_the_excerpt_has_exactly_one_installer_that_the_pattern_takes(self):
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        self.assertEqual(len(releases()), 28)
        for release in releases():
            hits = [asset["name"] for asset in release["assets"] if pattern.match(asset["name"])]
            self.assertEqual(len(hits), 1, (release["tag_name"], hits))
            self.assertTrue(hits[0].endswith(".exe"))

    def test_the_recipe_takes_the_newest_release_where_the_old_pattern_went_back_to_january(self):
        """The first run (2026-10-04) took a file of January 2026: the old pattern knows one spelling of the
        name, the newer releases use others, and AutoPkg goes on to the next release when none matches."""
        self.assertEqual(selected(OLD_PATTERN), ("v02.05.00.67", "Bambu_Studio_win_public-v02.05.00.66-20260128215914.exe"))
        tag, name = selected(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        self.assertEqual((tag, name), (TAG, ASSET))
        newest = [r["tag_name"] for r in releases() if not r["prerelease"]][0]
        self.assertEqual(tag, newest)

    def test_with_pre_releases_the_recipe_takes_the_newest_of_all(self):
        pattern = load(DOWNLOAD)["Input"]["SEARCH_PATTERN"]
        self.assertEqual(selected(pattern, include_prereleases=True)[0], releases()[0]["tag_name"])
        self.assertTrue(releases()[0]["prerelease"])

    def test_searching_a_name_or_matching_it_from_its_start_gives_the_same_answer(self):
        """AutoPkg 2.9.0 uses `re.match`. For the recipe's pattern, searching a name gives the same
        answer as matching it from its start for every saved name, so a pattern that starts
        elsewhere in a name would not be a way round it."""
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        for release in releases():
            for asset in release["assets"]:
                self.assertEqual(bool(pattern.search(asset["name"])), bool(pattern.match(asset["name"])), asset["name"])

    def test_the_label_is_the_number_in_the_name_and_the_tag_is_not_always_that_number(self):
        """The label of the recipe's last step for each saved release is the version in the installer's name.
        In three releases the tag says another build, and one tag starts with a capital V, which AutoPkg's
        provider does not strip: this is why the tag is not the source."""
        pattern = load(DOWNLOAD)["Input"]["SEARCH_PATTERN"]
        arguments = load(DOWNLOAD)["Process"][-1]["Arguments"]
        differ = []
        for release in releases():
            name = [a["name"] for a in release["assets"] if re.match(pattern, a["name"])][0]
            env = {"pathname": "/cache/downloads/" + name, "version_pattern": pattern, "version": release["tag_name"]}
            self.assertEqual(set(env) - {"version"}, set(arguments))
            processor, _ = _win_support.run_processor(_win_support.version_name.VersionFromName, env)
            label = processor.env["version"]
            self.assertIn("v" + label, name)
            if "v" + label != release["tag_name"]:
                differ.append(release["tag_name"])
        self.assertEqual(differ, ["v02.05.03.62", "v02.05.00.67", "v02.05.00.65", "V02.00.03.54"])

    def test_every_release_has_a_windows_zip_and_the_newer_ones_share_the_installers_name(self):
        """The README says that each release has a Windows .zip of the same build, with the installer's
        name apart from the ending from v02.05.02.51 on, and that the pattern takes none of them."""
        pattern = load(DOWNLOAD)["Input"]["SEARCH_PATTERN"]
        same_stem = []
        for release in releases():
            exe = [a["name"] for a in release["assets"] if re.match(pattern, a["name"])][0]
            zips = [a["name"] for a in release["assets"] if a["name"].lower().endswith(".zip") and "Studio" in a["name"]
                    and a["name"].startswith("Bambu_Studio")]
            self.assertTrue(zips, release["tag_name"])
            for name in zips:
                self.assertIsNone(re.match(pattern, name), name)
            if exe[:-4] + ".zip" in zips:
                same_stem.append(release["tag_name"])
        newer = [r["tag_name"] for r in releases()]
        self.assertEqual(same_stem, newer[:newer.index("v02.05.02.51") + 1])

    def test_a_digest_is_recorded_for_every_installer_from_the_release_of_2025_06_03_and_for_none_before(self):
        pattern = load(DOWNLOAD)["Input"]["SEARCH_PATTERN"]
        flags = {}
        for release in releases():
            flags[release["tag_name"]] = [a["digest_recorded"] for a in release["assets"] if re.match(pattern, a["name"])][0]
        tags = list(flags)
        cut = tags.index("v02.01.00.59")
        self.assertTrue(all(flags[tag] for tag in tags[:cut + 1]))
        self.assertEqual(tags[cut + 1:], ["V02.00.03.54"])
        self.assertFalse(any(flags[tag] for tag in tags[cut + 1:]))
        self.assertEqual([r["published_at"][:10] for r in releases() if r["tag_name"] == "v02.01.00.59"], ["2025-06-03"])

    def test_a_digest_is_recorded_for_the_installer_of_the_release_that_the_recipe_takes(self):
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        tag, name = selected(pattern.pattern)
        release = [r for r in releases() if r["tag_name"] == tag][0]
        self.assertTrue([a for a in release["assets"] if a["name"] == name][0]["digest_recorded"])

    def test_the_download_recipe_names_no_prerelease_and_keeps_the_file_name(self):
        steps = load(DOWNLOAD)["Process"]
        self.assertNotIn("include_prereleases", steps[0]["Arguments"])
        self.assertIs(load(DOWNLOAD)["Input"]["include_prereleases"], False)
        downloader = [step for step in steps if step["Processor"] == "URLDownloader"][0]
        self.assertNotIn("Arguments", downloader)  # URLDownloader: the asset's own file name
        self.assertTrue(ASSET.endswith(".exe"))

    def test_the_tag_without_the_v_has_leading_zeros_and_is_no_longer_the_label(self):
        """AutoPkg 2.9.0 strips a leading v from the tag (read in its source: tag.lstrip("v.")), so
        `version` starts as the tag's four parts with their leading zeros. The last step of the
        download recipe overwrites it with the version in the installer's name, and the cimian
        recipe passes %version% on."""
        self.assertEqual(TAG.lstrip("v."), LABEL)
        self.assertEqual(LABEL.split(".")[0], "02")
        args = load(PCMAN)["Process"][0]["Arguments"]
        self.assertEqual(args["pcman_version"], "%version%")
        steps = load(DOWNLOAD)["Process"]
        self.assertEqual(steps[-1]["Processor"], SHARED_PREFIX + "VersionFromName")

    def test_the_label_step_is_last_and_reads_the_name_of_the_downloaded_file(self):
        steps = load(DOWNLOAD)["Process"]
        names = [step["Processor"] for step in steps]
        self.assertEqual(names[-1], SHARED_PREFIX + "VersionFromName")
        self.assertLess(names.index("EndOfCheckPhase"), names.index(SHARED_PREFIX + "ChecksumVerifier"))
        self.assertLess(names.index(SHARED_PREFIX + "ChecksumVerifier"), len(names) - 1)
        self.assertEqual(steps[-1]["Arguments"], {"pathname": "%pathname%", "version_pattern": "%SEARCH_PATTERN%"})

    def test_no_step_reads_a_version_resource_because_the_installer_has_none(self):
        """The first run with AutoPkg 2.9.0 (2026-10-04) stopped at WindowsExeVersion: the installer has no
        RT_VERSION resource."""
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            for step in load(path)["Process"]:
                self.assertFalse(step["Processor"].endswith("/WindowsExeVersion"), os.path.basename(path))

    def test_the_inputs_of_the_pcman_recipe(self):
        recipe = load(PCMAN)
        self.assertEqual(recipe["Input"]["NAME"], "BambuStudio")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "bambustudio")
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%",
                                "pcman_version": "%version%"})

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
        self.assertIn("takes the version label from the asset's file name", load(DOWNLOAD)["Description"])
        self.assertIn("The installer has no version resource of its own", load(DOWNLOAD)["Description"])
        self.assertNotIn("ProductVersion", load(DOWNLOAD)["Description"])
        self.assertIn("dry run", load(PCMAN)["Description"])
        self.assertIn("pcman_dry_run", load(PCMAN)["Description"])
        self.assertIn("the one that the download recipe took from the installer's file name", load(PCMAN)["Description"])
        self.assertNotIn("release tag without its leading v", load(PCMAN)["Description"])

    def test_the_descriptions_claim_no_rehearsal_and_say_what_is_not_established(self):
        for path in (DOWNLOAD, PCMAN):
            description = load(path)["Description"]
            self.assertNotIn("ehearsed", description)
        self.assertIn("is NOT established", load(DOWNLOAD)["Description"])
        self.assertIn("2026-10-04", load(DOWNLOAD)["Description"])
        self.assertIn("four spellings", load(DOWNLOAD)["Description"])
        self.assertIn("AutoPkg takes the first release that has a matching file however old it is", load(DOWNLOAD)["Description"])
        self.assertIn("the package tool took the label, with its leading zeros, as written on 2026-10-04 (see the README)", load(PCMAN)["Description"])
        self.assertNotIn("has NOT been seen yet", load(PCMAN)["Description"])
        self.assertIn("has NOT been seen yet", load(CIMIAN)["Description"])


class NewestReleaseGuardTests(unittest.TestCase):
    """The step that stops the run when AutoPkg's provider has gone back to an older release
    (../Win-SharedProcessors/GitHubNewestReleaseGuard.py). The list is this folder's saved one
    (`releases_excerpt.json`: names and flags of the newest releases of the repository, read on
    2026-10-04) in the shape of GitHub's API answer. The provider's choice is AutoPkg 2.9.0's rule
    (`_win_support.provider_select`) and the guard's one request is answered by the list. Nothing
    here uses the network."""

    GUARD = SHARED_PREFIX + "GitHubNewestReleaseGuard"
    # Where the saved list has the newest release that is not a pre-release.
    NEWEST_INDEX = 2
    # The release that the provider goes back to when a vendor renames the file of the newest one.
    OLDER_INDEX = 3

    def repo(self):
        return load(DOWNLOAD)["Process"][0]["Arguments"]["github_repo"]

    def pattern(self):
        return load(DOWNLOAD)["Input"]["SEARCH_PATTERN"]

    def records(self):
        owner, name = self.repo().split("/")
        saved = _win_support.saved_releases(os.path.join(TESTS_DIR, "releases_excerpt.json"))
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
        """Like the pre-release switch: keys of the Input that an override can change. A step's Arguments are
        injected after the override's Input and would beat it, and a `%variable%` that holds a boolean stops
        the whole run with a TypeError, so no step names them."""
        recipe = load(DOWNLOAD)
        self.assertEqual(recipe["Input"]["accepted_newest_release"], "")
        self.assertEqual(recipe["Input"]["release_tag_pattern"], "")
        self.assertIs(recipe["Input"]["include_prereleases"], False)
        self.assertNotIn("allow_older_release", recipe["Input"])
        for step in recipe["Process"]:
            for key in ("accepted_newest_release", "release_tag_pattern", "include_prereleases", "allow_older_release",
                        "sort_by_highest_tag_names", "latest_only"):
                self.assertNotIn(key, step.get("Arguments", {}))
            for key, value in step.get("Arguments", {}).items():
                match = re.fullmatch(r"%([A-Za-z_]+)%", value) if isinstance(value, str) else None
                if match:
                    self.assertNotIsInstance(recipe["Input"].get(match.group(1)), bool, key)

    def test_the_saved_list_has_the_newest_release_that_is_not_a_pre_release_where_this_file_says(self):
        records = self.records()
        first = [number for number, record in enumerate(records) if not record["prerelease"]][0]
        self.assertEqual(first, self.NEWEST_INDEX)
        self.assertTrue(all(record["prerelease"] for record in records[:first]))

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

    def dev_build(self, tag="vNext-1"):
        """A development build on top of the saved list: one zip, no Windows installer file."""
        owner, name = self.repo().split("/")
        return _win_support.fake_release(tag, ["dev-build.zip"], owner=owner, repo=name)

    def test_a_dev_build_without_an_installer_is_accepted_by_its_tag_only_while_it_is_the_newest(self):
        records = self.records()
        listed = [self.dev_build("vNext-1")] + records
        tag, error, asked = _win_support.guard_chain(self.repo(), self.pattern(), listed)
        self.assertEqual(tag, records[self.NEWEST_INDEX]["tag_name"])  # the provider rightly takes the release below it
        self.assertIn("Newest: release 'vNext-1', with the files: dev-build.zip", error)
        self.assertIn("'Set :Input:accepted_newest_release vNext-1' <the override>", error)
        result = _win_support.guard_run(self.repo(), self.pattern(), listed, accepted="vNext-1")
        self.assertEqual((result["tag"], result["error"]), (tag, None))
        self.assertEqual(result["asked"], self.asked())  # the guard still asks GitHub's list
        loud = [text for level, text in result["messages"] if level == 0]
        self.assertEqual(len(loud), 1)
        self.assertIn("An older release is taken on purpose", loud[0])
        self.assertIn("has 1 file (dev-build.zip)", loud[0])
        data = result["summary"]["data"]
        self.assertEqual((data["newest_release"], data["release_taken"]), ("vNext-1", tag))
        # a newer development build on top: the tag that was accepted does not cover it
        newer = [self.dev_build("vNext-2")] + listed
        error = _win_support.guard_chain(self.repo(), self.pattern(), newer, accepted="vNext-1")[1]
        self.assertIn("accepted_newest_release is 'vNext-1', which is not the newest release. ", error)

    def test_a_renamed_installer_cannot_be_accepted_and_no_command_is_offered(self):
        records = self.records()
        renamed = _win_support.renamed_in_newest(records, self.pattern())
        newest = records[self.NEWEST_INDEX]["tag_name"]
        for accepted in (None, newest):
            result = _win_support.guard_run(self.repo(), self.pattern(), renamed, accepted=accepted)
            error = result["error"]
            self.assertEqual(result["tag"], records[self.OLDER_INDEX]["tag_name"])
            self.assertIn("has Windows installer files: release '%s'" % newest, error)
            self.assertIn("That is a renamed installer, not a release without one", error)
            self.assertNotIn("PlistBuddy", error)
            self.assertEqual([text for level, text in result["messages"] if level == 0], [])
            self.assertNotIn("summary", result)
        self.assertIn("but that release has Windows installer files (", error)
        self.assertIn("it is no longer accepted", error)

    def test_an_accepted_dev_build_does_not_excuse_a_rename_below_it(self):
        records = self.records()
        renamed = _win_support.renamed_in_newest(records, self.pattern())
        listed = [self.dev_build("vNext-1")] + renamed
        newest = records[self.NEWEST_INDEX]["tag_name"]
        result = _win_support.guard_run(self.repo(), self.pattern(), listed, accepted="vNext-1")
        error = result["error"]
        self.assertEqual(result["tag"], records[self.OLDER_INDEX]["tag_name"])
        self.assertIn("Between them in the list: release '%s'" % newest, error)
        self.assertIn("renamed-", error)
        self.assertIn("a release between it and the selected one has Windows installer files: an acceptance does not "
                      "cover a rename below it", error)
        self.assertNotIn("PlistBuddy", error)
        self.assertEqual([text for level, text in result["messages"] if level == 0], [])

    def test_the_old_pattern_of_the_first_run_went_back_and_the_guard_stops_it(self):
        """The pattern that sent the first run (2026-10-04) to an old release, on the saved list."""
        records = self.records()
        tag, error, asked = _win_support.guard_chain(self.repo(), OLD_PATTERN, records)
        self.assertEqual(tag, selected(OLD_PATTERN)[0])
        self.assertNotEqual(tag, records[self.NEWEST_INDEX]["tag_name"])
        self.assertEqual(asked, self.asked())
        self.assertIn("Selected: release '%s'" % tag, error)
        self.assertIn("Newest: release '%s'" % records[self.NEWEST_INDEX]["tag_name"], error)

    def test_the_old_pattern_cannot_be_accepted_away(self):
        """The old pattern goes back to an old release because the newest one holds its installer under a new
        name: that is a renamed installer, and the acceptance of its tag is refused."""
        records = self.records()
        newest = records[self.NEWEST_INDEX]["tag_name"]
        result = _win_support.guard_run(self.repo(), OLD_PATTERN, records, accepted=newest)
        self.assertEqual(result["tag"], selected(OLD_PATTERN)[0])
        self.assertIn("it is no longer accepted", result["error"])
        self.assertNotIn("PlistBuddy", result["error"])
        self.assertEqual([text for level, text in result["messages"] if level == 0], [])

    def readme(self):
        with open(os.path.join(RECIPE_DIR, "README.md"), "r", encoding="utf-8") as handle:
            return re.sub(r"\s+", " ", handle.read())

    def test_the_readme_says_what_the_guard_does_and_what_to_do(self):
        text = self.readme()
        for needle in ("The step `GitHubNewestReleaseGuard`, right after it, now stops the run when the release that the "
                       "provider selected is not the newest release that is not a pre-release",
                       "its message names the newest release and its files",
                       "correct `SEARCH_PATTERN` in the override's `Input`",
                       "no Windows installer file (none ending in `.msi`, `.exe` or `.msix`) on purpose",
                       "accept exactly that release with the key `accepted_newest_release` of the override",
                       "offered only for a release without such a file, and not when a release between it and the "
                       "selected one has one",
                       "the run goes on only while that release is the newest, says so in every run, and stops again "
                       "when a newer one appears",
                       "The guard compares positions in GitHub's list, not versions",
                       "It is new and has not run under AutoPkg", "It compares releases, not files",
                       "Read the `Selected asset` line of every dry run"):
            self.assertIn(needle, text)
        self.assertNotIn("the recipe does not stop: it goes back", text)
        self.assertNotIn("allow_older_release", text)

    def test_the_readme_lists_the_stop_of_the_guard_among_the_expected_failures(self):
        text = self.readme()
        self.assertIn("**`GitHubNewestReleaseGuard` stops** (its message names the selected release, the newest release and the files "
                      "of the newest release)", text)
        self.assertIn("The guard now stops this case.", text)
        self.assertIn("purpose (no file ending in `.msi`, `.exe` or `.msix`), accept exactly that release with "
                      "`accepted_newest_release` in the override", text)

    def test_the_readme_counts_the_processors_of_the_trust_information(self):
        """The override of the package tool's recipe carries the trust information of the processors that are
        not part of AutoPkg: the README's sentence must name the right number, now that the guard is one."""
        names = {name for path in (DOWNLOAD, PCMAN) for name, _ in shared_steps(load(path))}
        self.assertEqual(len(names), 5)
        self.assertIn("GitHubNewestReleaseGuard", names)
        self.assertIn('the trust information of the two recipes and the five processors that are not part of AutoPkg itself (`GitHubNewestReleaseGuard`, `GitHubAssetDigest`, `ChecksumVerifier`, `VersionFromName`, `PcmanImporter`)', self.readme())


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
            "GitHubNewestReleaseGuard": set(),
            "PcmanImporter": {"pathname"},
            "VersionFromName": {"pathname"},
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

    def test_nothing_deeper_than_the_tests_folder(self):
        for path in self.files():
            self.assertLessEqual(len(os.path.relpath(path, RECIPE_DIR).split(os.sep)), 2, path)


class ReadmeTests(unittest.TestCase):
    """The README must say that nothing was rehearsed or fetched, and must not teach a command that loses the trust check."""

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
                    r"<the Windows overrides folder>/BambuStudio\.(?:cimian|pcman)\.recipe$",
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
        self.assertIn("autopkg list-recipes | grep -i BambuStudio-Win", step)
        self.assertIn("autopkg list-recipes | grep -i BambuStudio.pcman", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.BambuStudio`",
                      re.sub(r"\s+", " ", step))
        self.assertLess(step.index("list-recipes"), step.index("autopkg make-override"))

    def test_the_readme_says_how_to_take_pre_releases_and_that_the_switch_is_a_boolean(self):
        start = self.text.index("**Pre-releases.**")
        paragraph = self.text[start:self.text.index("Below, `pcman` stands for")]
        for needle in ("the key `include_prereleases` in the recipe's `Input`, a boolean that is `false`",
                       "`make-override` copies it into the override", "never in the recipe",
                       "Set :Input:include_prereleases true",
                       "<the Windows overrides folder>/BambuStudio.cimian.recipe",
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

    def test_the_steps_of_the_operator_are_there(self):
        for needle in ("pcman catalogs", "pcman versions bambustudio", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string"):
            self.assertIn(needle, self.text)

    def test_the_status_line_says_what_was_read_and_what_was_not(self):
        opening = "**Status. Changed after the first dry run with AutoPkg 2.9.0, and run again after the change (2026-10-04)."
        self.assertIn(opening, self.raw)
        i = self.raw.index(opening)
        self.assertLess(i, self.raw.index("## a."))
        self.assertLess(i, self.raw.index("| Recipe |"))
        self.assertEqual(self.raw.index("# Win-BambuStudio"), 0)
        paragraph = re.sub(r"\s+", " ", self.raw[i:self.raw.index("\n\n", i)])
        self.assertTrue(paragraph.endswith("**"))
        self.assertIn("a file of January 2026", paragraph)
        for needle in ("2026-10-04", "a file of January 2026",
                       "`WindowsExeVersion`: the file has no version resource (RT_VERSION)",
                       "`VersionFromName`",
                       "the first release (in GitHub's order, newest first, a pre-release skipped) that has a file whose name the pattern matches from its start",
                       "`select_asset`", "`re.match`", "however old",
                       "the old pattern takes that January file and the new one takes the newest",
                       "`https://api.github.com/repos/bambulab/BambuStudio/releases`", "the newest 28 releases",
                       "no file was downloaded",
                       "flags its betas as pre-releases", "`v02.08.02.61` (published 2026-08-21)",
                       "429020440 bytes", "and a Windows `.zip` of the same build", "nobody opened",
                       "four spellings of the installer's name",
                       "`Bambu_Studio_win_public-v<version>-<stamp>.exe`", "`Bambu_Studio_win-v<version>-<stamp>.exe`",
                       "`Bambu_Studio_win_v<version>-<stamp>.exe`", "`Bambu_Studio_public-v<version>-<stamp>.exe`",
                       "`Bambu_Studio_(?:win_public|win|public)[_-]v([0-9]+(?:\\.[0-9]+)+)-[0-9]+\\.exe$`",
                       "exactly one file in each of the 28 releases", "its one group is the label",
                       "`v02.05.03.62` holds an installer whose name says `v02.05.03.61`",
                       "`v02.05.00.67` one that says `v02.05.00.66`", "`v02.05.00.65` one that says `v02.05.00.64`",
                       "`V02.00.03.54`", "it strips a lower-case `v` only",
                       "so the label is taken from the name and not from the tag",
                       "from `v02.01.00.59` (2025-06-03) to the newest",
                       "none of `V02.00.03.54` (2025-04-24) and older",
                       "After the change a dry run under AutoPkg 2.9.0 selected `Bambu_Studio_win-v02.08.02.61-20260820225108.exe` of `v02.08.02.61`, the newest release that is not a pre-release, passed the digest and checksum steps",
                       "took the label from the file name (`VersionFromName`): the four parts of `v02.08.02.61` without the `v`, leading zeros kept",
                       "the first import with the package tool (the command of step a.3 below, run with `--no-prompt` and `--build`) made the item `bambustudio` "
                       "(an EXE item, label the four parts of `v02.08.02.61` without the `v`, `--install-arguments /S`, architectures `x64`, the catalog `Production`, no install path)",
                       "`PcmanImporter: Nothing new: bambustudio <the label> is in the repository already. Nothing was written.`",
                       "went beside the Chocolatey item `bambustudio` (version 1.0) without any option of the tool",
                       "the Chocolatey item file and its `bambustudio-1.0` pkginfo remain until a person removes them by hand",
                       "`pcman catalogs` ran a second time later on 2026-10-04", "110 items each (106 before)",
                       "**The package tool took the label with its leading zeros as written**: no refusal, no WARNING and no note in the dry run or the real import",
                       "it keeps the spelling in the item file, in the pkginfo and in both file names",
                       "it ranks it above the Chocolatey item's `1.0` (`pcman versions` lists it first)",
                       "its `--if-new` found it as \"Nothing new\"",
                       "writes the new version first, as `<the label>, 1.0`", "looks like a sort of the text",
                       "The Cimian client compares the parts of a version as numbers",
                       "**The installer is an NSIS installer**", "\"Nullsoft\" and \"NSIS\" strings and NSIS's `.ndata` section",
                       "the `/S` of this README is the right kind of switch", "**used on 2026-10-04, not tested on a PC**",
                       "has NO install check until a person adds one", "Nothing has been installed on a PC",
                       "NOT established: that the switch `/S` installs silently on a PC; the install path and the architecture of the installed program",
                       "the version that the installed program reports about itself",
                       "leading zeros of the label",
                       "that the next release keeps one of the four spellings",
                       "any install on a PC", "An install on a test PC is the check of each of them",
                       "stop. Nothing was written.",
                       "correct the recipe", "Never change the trust information first",
                       "The real run of 2026-10-04 published nothing, because the item was there already"):
            self.assertIn(needle, paragraph)
        for gone in ("NOT rehearsed since", "any run with AutoPkg after this change", "whether the package tool accepts a part with a leading zero",
                     "A real run has NOT been run by anyone", "the writer's knowledge, the installer was not opened"):
            self.assertNotIn(gone, paragraph)
        self.assertNotIn("the network was closed", self.text)
        self.assertNotIn("NOT fetched by the writer", self.raw)

    def test_the_readme_does_not_claim_a_rehearsal(self):
        self.assertNotIn("Rehearsed on", self.raw)
        self.assertNotIn("rehearsal printed", self.raw)
        self.assertNotIn("The rehearsal", self.raw)

    def test_the_label_is_never_written_out_alone_and_the_command_names_the_exe_only_flags(self):
        # Only inside the asset name (v<label>-<build date>) may it appear: alone it reads as an address.
        self.assertIsNone(re.search(r"(?<![vV0-9])" + re.escape(LABEL), self.raw))
        self.assertIsNone(re.search(r"(?<![vV0-9.])0[0-9]\.[0-9]{2}\.[0-9]{2}\.[0-9]{2}", self.raw))
        self.assertIn("## The version label", self.raw)
        step = self.raw[self.raw.index("3. **The template item"):self.raw.index("## b.")]
        command = step[step.index("pcman import"):step.index("--build") + len("--build")]
        for flag in ("--name bambustudio", "--version <label>", "--display-name", "--category", "--developer",
                     "--description", "--install-arguments /S", "--architectures x64", "--icon",
                     "--no-prompt"):
            self.assertIn(flag, command)
        self.assertNotIn("--install-path", command)  # the install path was not read: it is left out
        flat = re.sub(r"\s+", " ", step)
        for needle in ("in the form that ran on 2026-10-04 (it worked as written)", "The installer is an NSIS installer",
                       "so `/S` is the right kind of switch", "**used on 2026-10-04, not tested on a PC**",
                       "**Still to fill in:** the architecture and the install path",
                       "`--install-path` was left out because the path must be read on a PC after a hand install"):
            self.assertIn(needle, flat)
        self.assertIn("`--version <label>` is for an EXE only", re.sub(r"\s+", " ", step))

    def test_the_first_dry_run_names_what_can_stop_it(self):
        step = re.sub(r"\s+", " ", self.raw[self.raw.index("## c."):self.raw.index("## d.")])
        for needle in ("No asset matches", "`GitHubAssetDigest` stops with its error",
                       "a hand import", "The package tool refuses the label",
                       "compare it with the version that the installed program shows",
                       "`VersionFromName` stops", "is not two to four numbers joined by dots",
                       "The run goes on, but with an old release", "`Selected asset ... from release ...`",
                       "This is what happened on 2026-10-04"):
            self.assertIn(needle, step)
        self.assertNotIn("WindowsExeVersion", step)
        self.assertIn("autopkg run -v --override-dir=", step)
        self.assertIn("`-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the repository among them, "
                      "and such a log would have to be kept private", re.sub(r"\s+", " ", step))

    def test_the_version_label_section_says_where_the_label_comes_from(self):
        section = self.raw[self.raw.index("## The version label"):self.raw.index("## Run every override")]
        text = re.sub(r"\s+", " ", section)
        for needle in ("`WindowsExeVersion` stopped on a Bambu Studio installer", "no version resource",
                       "So the label is the version in the file's name", "`VersionFromName`", "`SEARCH_PATTERN`",
                       "whose one group is the label", "two to four numbers joined by dots",
                       "overwrites `version` with it", "keeps the leading zeros of the name",
                       "belongs to the release and not to the file", "three tags in the list hold installers that name another build",
                       "It is not the file's own version (the file has none)",
                       "what the installed program says about itself: that is NOT established",
                       "**Answered: the package tool accepts a part with a leading zero.**", "It took the label as written: no refusal, no WARNING and no note",
                       "**Open: does the Cimian client order that label as the program's own version?**",
                       "a part `02` is `2`", "`CatalogService.CompareVersions`, `CatalogService.cs:260-292`, and `ParseVersionPart`, `:374-389`",
                       "`VersionService.ParseVersion`",
                       "commit `3cf02c4` of `windowsadmins/cimian` on 2026-10-04, and a second reader found the same code at `e10498b`",
                       "two rules that read a label as a build time, and this label, which has four parts and starts with `02`, meets neither",
                       "`VersionService.TryParseCalendarBuildStamp` needs a first part that is a year of four digits",
                       "`CatalogService.ExpandBuildTimestamp` (the code of the catalog order and of the check of installed versions) reads a label of exactly three parts, `yy.M.ddHH`, "
                       "with `yy` from 20 to 99, a month from 1 to 12 and a third part of three or four digits, as a build time",
                       "the cimian recipe to `CimianImporter` (`version` is `%version%`)",
                       "stop and tell the owner", "`Selected asset ... from release ...`",
                       "`version is ..., taken from the file name ...`", "**Read them first**",
                       "the selected release must be the newest that is not a pre-release"):
            self.assertIn(needle, text)
        for needle in ("`ProductVersion`", "numbers and dots only", "a label of zeros stops the run", "published under the tag"):
            self.assertNotIn(needle, text)

    def test_the_readme_says_that_the_provider_goes_back_when_a_name_changes(self):
        self.assertIn("takes the first release, newest first, that has a file whose name matches `SEARCH_PATTERN`, however old",
                      self.text)
        self.assertIn("Read the `Selected asset` line of every dry run", self.text)


class ChainTests(_pcman_support.ToolTestCase):
    """The chain of this program counts as verified for the importer: the real
    ChecksumVerifier hashes the file, and the importer hashes it again and
    compares. The stand-in package tool is used; nothing else is run. The
    installer of these tests has the name of the real one and, like the real
    one, no version resource."""

    def setUp(self):
        super().setUp()
        built = exe_tests.build_pe(exe_tests.version_info(), types=(3,))  # a resource, but not RT_VERSION
        self.exe = os.path.join(self.downloads, ASSET)
        with open(self.exe, "wb") as handle:
            handle.write(bytes(built.data))

    def chain_env(self, installer):
        """What the steps of the two recipes leave in the run, with the
        arguments of the recipe's own steps. The download recipe's last step
        is run with the recipe's own arguments and the recipe's own pattern."""
        run = {"pathname": installer, "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        steps = {step["Processor"][len(SHARED_PREFIX):]: step.get("Arguments", {})
                 for step in load(DOWNLOAD)["Process"] if step["Processor"].startswith(SHARED_PREFIX)}
        values = {"%pathname%": installer, "%SEARCH_PATTERN%": load(DOWNLOAD)["Input"]["SEARCH_PATTERN"]}
        reader_env = {name: values.get(value, value) for name, value in steps["VersionFromName"].items()}
        reader_env["version"] = "the tag of the release"
        reader, _ = _win_support.run_processor(_win_support.version_name.VersionFromName, reader_env)
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

    def test_the_installer_has_no_version_resource_and_the_old_step_stopped_on_it(self):
        """The first run with AutoPkg 2.9.0 (2026-10-04): the step that reads the file's version stops."""
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_win_support.exe_version.WindowsExeVersion, {"pathname": self.exe})
        self.assertIn("the file has no version resource (RT_VERSION)", str(caught.exception))

    def test_the_label_is_the_version_in_the_file_name_with_its_leading_zeros(self):
        env = self.chain_env(self.exe)
        self.assertEqual(env["pcman_version"], LABEL)
        self.assertEqual(LABEL.split(".")[0], "02")
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


def _text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class CatalogsStepReadmeTests(unittest.TestCase):
    """The step that builds the catalogs says what happened on 2026-10-04 and no longer says "Not rehearsed"."""

    def test_the_catalogs_step_names_the_run_of_2026_10_04(self):
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md"), "r", encoding="utf-8") as handle:
            text = re.sub(r"\s+", " ", handle.read())
        i = text.index("3. **Build the catalogs: `pcman catalogs`.**")
        step = text[i:text.index("4. The second run, by path again:", i)]
        for needle in ("(Run on 2026-10-04: `pcman catalogs` ran twice that day, the second time after the first imports of this and three other programs.",
                       "The tool's configured command ran `makecatalogs` on the repository's server",
                       "wrote the catalogs `All` and `Production`, 110 items each in the second run, with exit 0",
                       "The package tool prints \"nothing to run\" when its catalogs command is not set"):
            self.assertIn(needle, step)
        self.assertNotIn("Not rehearsed", step)
        self.assertNotIn("for no program", step)


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
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.BambuStudio")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.BambuStudio")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotEqual(cimian["Identifier"], pcman["Identifier"])
        self.assertEqual(cimian["MinimumVersion"], pcman["MinimumVersion"])
        self.assertTrue(CIMIAN.endswith("BambuStudio.cimian.recipe"))
        self.assertTrue(PCMAN.endswith("BambuStudio.pcman.recipe"))

    def test_the_only_step_is_the_cimian_importer(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "CimianImporter"])

    def test_the_inputs_and_the_arguments(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], load(PCMAN)["Input"]["NAME"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], load(PCMAN)["Input"]["PCMAN_TEMPLATE"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], "bambustudio")
        self.assertEqual(recipe["Input"]["CIMIAN_SUBDIRECTORY"], "")
        self.assertEqual(sorted(recipe["Input"]), ["CIMIAN_NAME", "CIMIAN_SUBDIRECTORY", "NAME", "pkginfo"])
        self.assertEqual(recipe["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": "%version%"})

    def test_the_pkginfo_gives_only_what_the_readme_states(self):
        self.assertEqual(load(CIMIAN)["Input"]["pkginfo"], {'display_name': 'Bambu Studio', 'developer': 'Bambu Lab'})

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
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "bambustudio")
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
        for name, identifier in (("BambuStudio.cimian.recipe", "com.github.serrc-techops.cimian.BambuStudio"),
                                 ("BambuStudio.pcman.recipe", "com.github.serrc-techops.pcman.BambuStudio")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)
        self.assertIn("`CimianImporter`", [line for line in self.raw.splitlines() if line.startswith("| `BambuStudio.cimian.recipe`")][0])
        self.assertIn("`pcman`", [line for line in self.raw.splitlines() if line.startswith("| `BambuStudio.pcman.recipe`")][0])

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
        for text, recipe, other in ((self.generic, "BambuStudio.cimian", "BambuStudio.pcman"), (self.tool, "BambuStudio.pcman", "BambuStudio.cimian")):
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
            self.assertRegex(command, r"--override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio\.cimian\.recipe$")

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
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.cimian.BambuStudio`**", self.generic.replace("\n", " "))
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.BambuStudio`**", self.tool.replace("\n", " "))
        for text in (self.generic, self.tool):
            self.assertNotIn("it must be `com.github.serrc-techops.download.", text.replace("\n", " "))

    def test_an_override_of_the_old_cimian_recipe_is_to_be_made_again_for_the_package_tool(self):
        self.assertIn("An override that was made from the old `BambuStudio.cimian.recipe`", self.tool)
        self.assertIn("must be made again from `BambuStudio.pcman.recipe`", self.tool)
        self.assertIn("An override that was made from this recipe before the recipes were separated", self.generic)

    def test_the_condition_of_never_overwrites_is_said(self):
        self.assertIn("do not run two runs of one item at the same time", self.generic)

    def test_the_generic_way_states_no_hash_and_no_made_up_label(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.generic))
        self.assertNotIn("Published bambustudio", self.generic)

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
        self.assertIn("BambuStudio.pcman", self.tool)

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
