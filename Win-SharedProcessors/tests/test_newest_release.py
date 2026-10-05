"""Tests of GitHubNewestReleaseGuard: the rule that picks the newest release, the
request, the errors and the messages. No test uses the network: fetch_releases()
or open_request() is replaced, or a server on the loopback address answers.

The lists of releases are made up (example-owner/example-app) in the shape of
GitHub's API answer; the recipes' own tests run the guard with the real
patterns of their folder."""
import http.client
import http.server
import io
import json
import threading
import time
import unittest
import urllib.error
from unittest import mock

from _win_support import (
    ProcessorError, fake_release, guard_chain, guard_run, new_processor, newest_release, provider_select,
    renamed_in_newest, run_processor,
)

GUARD = newest_release.GitHubNewestReleaseGuard
OWNER, REPO = "example-owner", "example-app"
PATTERN = r"app-[0-9]+\.exe$"


def release(tag, names, **kwargs):
    return fake_release(tag, names, **kwargs)


def selected_env(releases, tag, name, **more):
    """The variables that the provider leaves: the selected asset's API URL and
    download URL."""
    for rel in releases:
        if rel["tag_name"] == tag:
            for asset in rel["assets"]:
                if asset["name"] == name:
                    env = {"github_asset_api_url": asset["url"], "url": asset["browser_download_url"]}
                    env.update(more)
                    return env
    raise AssertionError("no such asset in the made-up list")


class Lines(list):
    """What a processor printed, with the verbosity level of each line in `levels`
    as (level, text)."""

    levels = ()


def run_guard(releases, tag, name, pages=None, **more):
    """Run the guard with fetch_releases() replaced. `pages` are the answers of the
    fetches, one for each call (default: the whole list as page one). Returns
    (messages, the mock of fetch_releases); the messages have `.levels`."""
    env = selected_env(releases, tag, name, **more)
    answers = pages if pages is not None else [releases]
    with mock.patch.object(newest_release, "fetch_releases", side_effect=answers) as fetch:
        processor, messages = new_processor(GUARD, env)
        processor.main()
    lines = Lines(messages)
    lines.levels = list(processor.message_levels)
    return lines, fetch


class SelectionTests(unittest.TestCase):
    def test_the_newest_release_holds_the_selected_file(self):
        releases = [release("v2", ["app-2.exe", "notes.txt"]), release("v1", ["app-1.exe"])]
        messages, fetch = run_guard(releases, "v2", "app-2.exe")
        fetch.assert_called_once_with(OWNER, REPO, 1)
        self.assertTrue(any("'v2'" in m and "newest release that is not a pre-release" in m for m in messages))

    def test_a_selected_file_of_an_older_release_stops_the_run(self):
        """The trap: the newest release has the installer under a new name, the provider goes back."""
        releases = [release("v2", ["App-Setup-2.exe", "notes.txt"]), release("v1", ["app-1.exe"])]
        with self.assertRaises(ProcessorError) as caught:
            run_guard(releases, "v1", "app-1.exe")
        text = str(caught.exception)
        for needle in (
            "%s/%s" % (OWNER, REPO), "Selected: release 'v1', file 'app-1.exe'",
            "Newest: release 'v2', with the files: App-Setup-2.exe, notes.txt",
            "however old", "asset_regex", "SEARCH_PATTERN", "accepted_newest_release",
            "correct SEARCH_PATTERN", "That is a renamed installer", "release_tag_pattern",
        ):
            self.assertIn(needle, text)

    def test_the_message_names_the_titles_when_they_differ_from_the_tags(self):
        releases = [release("v2", ["App-Setup-2.exe"], title="Example App 2"), release("v1", ["app-1.exe"], title="Example App 1")]
        with self.assertRaises(ProcessorError) as caught:
            run_guard(releases, "v1", "app-1.exe")
        text = str(caught.exception)
        self.assertIn("release 'v1' (titled 'Example App 1')", text)
        self.assertIn("release 'v2' (titled 'Example App 2')", text)

    def test_a_release_two_places_down_is_not_the_newest_either(self):
        releases = [release("v3", ["new-name.exe"]), release("v2", ["other.exe"]), release("v1", ["app-1.exe"])]
        with self.assertRaises(ProcessorError):
            run_guard(releases, "v1", "app-1.exe")

    def test_pre_releases_on_top_are_skipped(self):
        releases = [release("v4-beta", ["beta.exe"], prerelease=True), release("v3-beta", ["beta.exe"], prerelease=True),
                    release("v2", ["app-2.exe"]), release("v1", ["app-1.exe"])]
        run_guard(releases, "v2", "app-2.exe")
        with self.assertRaises(ProcessorError) as caught:
            run_guard(releases, "v1", "app-1.exe")
        self.assertIn("Newest: release 'v2'", str(caught.exception))

    def test_a_file_of_a_pre_release_is_not_the_selection_the_provider_would_make(self):
        """If a pre-release's file is selected (include_prereleases was true for the provider
        but not for the guard), the guard stops: the newest release that is not a pre-release is another."""
        releases = [release("v3-beta", ["app-3.exe"], prerelease=True), release("v2", ["app-2.exe"])]
        with self.assertRaises(ProcessorError):
            run_guard(releases, "v3-beta", "app-3.exe")

    def test_include_prereleases_lets_a_pre_release_be_the_newest(self):
        releases = [release("v3-beta", ["app-3.exe"], prerelease=True), release("v2", ["app-2.exe"])]
        messages, _ = run_guard(releases, "v3-beta", "app-3.exe", include_prereleases=True)
        self.assertTrue(any("'v3-beta'" in m and "is the newest release." in m for m in messages))
        with self.assertRaises(ProcessorError) as caught:
            run_guard(releases, "v2", "app-2.exe", include_prereleases=True)
        self.assertIn("is not the newest release.", str(caught.exception))
        self.assertNotIn("not a pre-release", str(caught.exception))

    def test_the_switch_is_tested_for_truth_like_the_providers(self):
        """The provider tests `if rel["prerelease"] and not include_prereleases`: any non-empty
        value, the text false included, takes pre-releases. The guard reads the same variable the same way."""
        releases = [release("v3-beta", ["app-3.exe"], prerelease=True), release("v2", ["app-2.exe"])]
        for value in (None, "", 0, False):
            with self.subTest(value=value):
                run_guard(releases, "v2", "app-2.exe", include_prereleases=value)
        for value in (True, "true", "false", "no", 1, "x"):
            with self.subTest(value=value):
                with self.assertRaises(ProcessorError):
                    run_guard(releases, "v2", "app-2.exe", include_prereleases=value)
        # not given at all
        run_guard(releases, "v2", "app-2.exe")

    def test_a_draft_is_never_the_newest_release(self):
        releases = [release("v3", ["app-3.exe"], draft=True), release("v2", ["app-2.exe"])]
        run_guard(releases, "v2", "app-2.exe")
        with self.assertRaises(ProcessorError) as caught:
            run_guard(releases, "v3", "app-3.exe")
        self.assertIn("Newest: release 'v2'", str(caught.exception))
        # a draft is skipped when pre-releases are included too
        run_guard(releases, "v2", "app-2.exe", include_prereleases=True)

    def test_a_draft_that_is_also_a_pre_release_is_skipped(self):
        releases = [release("v3", ["app-3.exe"], draft=True, prerelease=True), release("v2", ["app-2.exe"])]
        run_guard(releases, "v2", "app-2.exe", include_prereleases=True)

    def test_an_empty_list_is_an_error(self):
        releases = [release("v1", ["app-1.exe"])]
        with self.assertRaises(ProcessorError) as caught:
            run_guard(releases, "v1", "app-1.exe", pages=[[]])
        self.assertIn("lists no release", str(caught.exception))

    def test_a_newest_release_without_files_stops_the_run(self):
        releases = [release("v2", []), release("v1", ["app-1.exe"])]
        with self.assertRaises(ProcessorError) as caught:
            run_guard(releases, "v1", "app-1.exe")
        text = str(caught.exception)
        self.assertIn("Newest: release 'v2', with the files: none (the release has no files)", text)
        self.assertIn("accepted_newest_release", text)
        self.assertIn("'Set :Input:accepted_newest_release v2'", text)

    def test_a_release_without_files_further_down_does_not_matter(self):
        releases = [release("v3", ["app-3.exe"]), release("v2", []), release("v1", ["app-1.exe"])]
        run_guard(releases, "v3", "app-3.exe")

    def test_a_release_record_without_the_list_of_files_counts_as_one_without_files(self):
        releases = [release("v2", []), release("v1", ["app-1.exe"])]
        del releases[0]["assets"]
        with self.assertRaises(ProcessorError) as caught:
            run_guard(releases, "v1", "app-1.exe")
        self.assertIn("none (the release has no files)", str(caught.exception))
        releases[0]["assets"] = None
        with self.assertRaises(ProcessorError):
            run_guard(releases, "v1", "app-1.exe")

    def test_the_first_page_with_a_release_that_can_be_taken_ends_the_reading(self):
        releases = [release("v2", ["app-2.exe"])] + [release("v%d-old" % n, ["x.exe"]) for n in range(29)]
        _, fetch = run_guard(releases, "v2", "app-2.exe")
        self.assertEqual(fetch.call_count, 1)

    def test_a_page_of_only_pre_releases_sends_the_guard_to_the_next_page(self):
        page_one = [release("b%d" % n, ["b.exe"], prerelease=True) for n in range(newest_release.RELEASES_PER_PAGE)]
        page_two = [release("v2", ["app-2.exe"]), release("v1", ["app-1.exe"])]
        messages, fetch = run_guard(page_one + page_two, "v2", "app-2.exe", pages=[page_one, page_two])
        self.assertEqual(fetch.call_args_list, [mock.call(OWNER, REPO, 1), mock.call(OWNER, REPO, 2)])
        with self.assertRaises(ProcessorError) as caught:
            run_guard(page_one + page_two, "v1", "app-1.exe", pages=[page_one, page_two])
        self.assertIn("Newest: release 'v2'", str(caught.exception))

    def test_a_short_page_is_the_end_of_the_list(self):
        page_one = [release("b%d" % n, ["b.exe"], prerelease=True) for n in range(3)]
        selected_list = page_one + [release("v1", ["app-1.exe"])]
        with self.assertRaises(ProcessorError) as caught:
            run_guard(selected_list, "v1", "app-1.exe", pages=[page_one])
        self.assertIn("none that the provider could take", str(caught.exception))
        self.assertIn("include_prereleases to true or correct release_tag_pattern", str(caught.exception))

    def test_at_most_max_pages_are_read(self):
        pages = [[release("b%d-%d" % (page, n), ["b.exe"], prerelease=True)
                  for n in range(newest_release.RELEASES_PER_PAGE)] for page in range(newest_release.MAX_PAGES + 2)]
        released = release("v1", ["app-1.exe"])
        with self.assertRaises(ProcessorError) as caught:
            run_guard([released], "v1", "app-1.exe", pages=pages)
        self.assertIn("none that the provider could take", str(caught.exception))
        self.assertIn("%d newest releases" % (newest_release.MAX_PAGES * newest_release.RELEASES_PER_PAGE), str(caught.exception))
        with mock.patch.object(newest_release, "fetch_releases", side_effect=pages) as fetch:
            newest_release.read_releases(OWNER, REPO, False)
        self.assertEqual(fetch.call_count, newest_release.MAX_PAGES)

    def test_a_selected_file_that_is_not_in_the_list_is_named_from_the_download_url(self):
        listed = [release("v2", ["App-Setup-2.exe"]), release("v1.5", ["other.exe"])]
        old = release("v0.1", ["app-1.exe"])
        env = selected_env([old], "v0.1", "app-1.exe")
        with mock.patch.object(newest_release, "fetch_releases", side_effect=[listed]):
            processor, _ = new_processor(GUARD, env)
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        text = str(caught.exception)
        self.assertIn("Selected: release 'v0.1' (not in the list that was read), file 'app-1.exe'", text)
        # without the download URL: the asset's number
        env.pop("url")
        with mock.patch.object(newest_release, "fetch_releases", side_effect=[listed]):
            processor, _ = new_processor(GUARD, env)
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        self.assertIn("Selected: a release that is not in the list that was read, file asset ", str(caught.exception))
        self.assertIn(" (its name is not known). Newest: release 'v2'", str(caught.exception))

    def test_a_selected_file_that_is_newer_than_the_list_says_that_the_list_may_have_changed(self):
        """A race: the provider's request and the guard's are not the same moment, and the guard's is anonymous
        (GitHub may serve it from a cache for a minute). The message must not read as if the release were old."""
        listed = [release("v25.05", ["app-5.exe"]), release("v25.04", ["app-4.exe"])]
        fresh = release("v25.06", ["app-6.exe"])
        env = selected_env([fresh], "v25.06", "app-6.exe")
        with mock.patch.object(newest_release, "fetch_releases", side_effect=[listed]):
            processor, _ = new_processor(GUARD, env)
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        text = str(caught.exception)
        self.assertIn("Selected: release 'v25.06' (not in the list that was read), file 'app-6.exe'", text)
        self.assertIn("The selected file is not in the list that was read: either GitHub's list changed after the "
                      "provider read it (run the recipe again before changing anything), or its release is older "
                      "than the 2 releases that were read.", text)
        self.assertNotIn("not among", text)

    def test_the_note_about_a_changed_list_is_only_for_a_file_that_is_not_in_the_list(self):
        releases = [release("v2", ["App-Setup-2.exe"]), release("v1", ["app-1.exe"])]
        with self.assertRaises(ProcessorError) as caught:
            run_guard(releases, "v1", "app-1.exe")
        self.assertNotIn("not in the list that was read", str(caught.exception))

    def test_the_pass_line_names_the_title_when_it_differs_from_the_tag(self):
        plain = [release("v2", ["app-2.exe"])]
        titled = [release("v2", ["app-2.exe"], title="Example App 2")]
        for releases, release_text in ((plain, "'v2'"), (titled, "'v2' (titled 'Example App 2')")):
            with self.subTest(release=release_text):
                messages, _ = run_guard(releases, "v2", "app-2.exe")
                expected = ("The selected release %s of example-owner/example-app is the newest release "
                            "that is not a pre-release." % release_text)
                self.assertEqual(list(messages), [expected])
                self.assertEqual(newest_release.pass_message(OWNER, REPO, releases[0], False), expected)
        text = newest_release.pass_message(OWNER, REPO, titled[0], True)
        self.assertTrue(text.endswith("is the newest release."))
        pattern = newest_release.parse_tag_pattern("v2")
        self.assertTrue(newest_release.pass_message(OWNER, REPO, plain[0], False, pattern).endswith(
            "is the newest release that is not a pre-release whose tag matches 'v2'."))

    def test_the_files_of_the_newest_release_are_listed_up_to_a_limit(self):
        names = ["file-%02d.bin" % n for n in range(newest_release.MAX_ASSET_NAMES_SHOWN + 10)]
        releases = [release("v2", names), release("v1", ["app-1.exe"])]
        with self.assertRaises(ProcessorError) as caught:
            run_guard(releases, "v1", "app-1.exe")
        text = str(caught.exception)
        self.assertIn("file-00.bin", text)
        self.assertIn("file-%02d.bin" % (newest_release.MAX_ASSET_NAMES_SHOWN - 1), text)
        self.assertNotIn("file-%02d.bin" % newest_release.MAX_ASSET_NAMES_SHOWN, text)
        self.assertIn("and 10 more", text)

    def test_text_from_github_is_shown_printable_and_short(self):
        tag = "v2\nINJECTED \x1b[31m" + "x" * 200
        releases = [release(tag, ["new\r\nname.exe", 5]), release("v1", ["app-1.exe"])]
        with self.assertRaises(ProcessorError) as caught:
            run_guard(releases, "v1", "app-1.exe")
        text = str(caught.exception)
        self.assertNotIn("\n", text)
        self.assertNotIn("\r", text)
        self.assertNotIn("\x1b", text)
        self.assertIn("new??name.exe", text)
        self.assertIn("v2?INJECTED ?[31m", text)
        self.assertNotIn("x" * 100, text)
        self.assertIn("...", text)

    def test_the_pure_rule(self):
        items = [release("p", ["a"], prerelease=True), release("d", ["a"], draft=True), release("n", ["a"])]
        self.assertIs(newest_release.newest_candidate(items, False), items[2])
        self.assertIs(newest_release.newest_candidate(items, True), items[0])
        self.assertIsNone(newest_release.newest_candidate(items[:2], False))
        self.assertIsNone(newest_release.newest_candidate([], True))
        self.assertTrue(newest_release.is_candidate(items[2], False))
        self.assertFalse(newest_release.is_candidate(items[0], False))
        self.assertFalse(newest_release.is_candidate(items[1], True))
        self.assertIs(newest_release.release_with_asset(items, items[1]["assets"][0]["id"]), items[1])
        self.assertIsNone(newest_release.release_with_asset(items, 1))

    def test_an_asset_id_that_is_a_boolean_is_not_an_id(self):
        rel = {"tag_name": "v1", "prerelease": False, "assets": [{"id": True, "name": "a"}]}
        self.assertIsNone(newest_release.release_with_asset([rel], 1))

    def test_a_list_that_is_not_one_is_an_error(self):
        for answer in ({}, "text", None, 5, [1], [[]], [{"assets": {}}], [{"assets": ["a"]}], [{"assets": [1]}]):
            with self.subTest(answer=answer):
                with mock.patch.object(newest_release, "fetch_json", return_value=answer):
                    with self.assertRaises(ProcessorError) as caught:
                        newest_release.fetch_releases(OWNER, REPO, 1)
                self.assertIn("unusable", str(caught.exception))


class ProviderStandInTests(unittest.TestCase):
    """The helpers that the recipes' tests use to say what AutoPkg's provider selects (the rule of
    GitHubReleasesInfoProvider.py, select_asset) and what a vendor's rename does to it."""

    def test_the_provider_takes_the_first_release_with_a_matching_file_however_old(self):
        releases = [release("v3", ["new-name.exe"]), release("v2", ["notes.txt"]), release("v1", ["app-1.exe"])]
        chosen, asset = provider_select(releases, PATTERN)
        self.assertEqual((chosen["tag_name"], asset["name"]), ("v1", "app-1.exe"))

    def test_a_pre_release_is_skipped_unless_it_is_included_and_a_draft_is_not_skipped(self):
        releases = [release("v3-beta", ["app-3.exe"], prerelease=True), release("v2", ["app-2.exe"])]
        self.assertEqual(provider_select(releases, PATTERN)[0]["tag_name"], "v2")
        self.assertEqual(provider_select(releases, PATTERN, include_prereleases=True)[0]["tag_name"], "v3-beta")
        drafts = [release("v3", ["app-3.exe"], draft=True), release("v2", ["app-2.exe"])]
        self.assertEqual(provider_select(drafts, PATTERN)[0]["tag_name"], "v3")

    def test_the_pattern_is_matched_from_the_start_and_a_release_without_files_is_passed(self):
        releases = [release("v3", []), release("v2", ["old-app-2.exe"])]
        self.assertIsNone(provider_select(releases, PATTERN))
        self.assertIsNone(provider_select([], PATTERN))

    def test_a_rename_in_the_newest_release_changes_only_that_release(self):
        releases = [release("v3-beta", ["app-3.exe"], prerelease=True), release("v2", ["app-2.exe", "notes.txt"]),
                    release("v1", ["app-1.exe"])]
        renamed = renamed_in_newest(releases, PATTERN)
        self.assertEqual([[a["name"] for a in r["assets"]] for r in renamed],
                         [["app-3.exe"], ["renamed-app-2.exe", "notes.txt"], ["app-1.exe"]])
        self.assertEqual(releases[1]["assets"][0]["name"], "app-2.exe")  # a copy: the list is not changed
        chosen, asset = provider_select(renamed, PATTERN)
        self.assertEqual((chosen["tag_name"], asset["name"]), ("v1", "app-1.exe"))

    def test_the_chain_of_the_helpers_runs_the_guard_on_the_same_list(self):
        releases = [release("v2", ["App-Setup-2.exe"]), release("v1", ["app-1.exe"])]
        tag, error, asked = guard_chain("example-owner/example-app", PATTERN, releases)
        self.assertEqual(tag, "v1")
        self.assertIn("Newest: release 'v2'", error)
        self.assertEqual(asked, ["https://api.github.com/repos/example-owner/example-app/releases?per_page=30&page=1"])
        zip_only = [release("v2", ["App-2.zip"]), release("v1", ["app-1.exe"])]
        self.assertEqual(guard_chain("example-owner/example-app", PATTERN, zip_only, accepted="v2"),
                         ("v1", None, ["https://api.github.com/repos/example-owner/example-app/releases?per_page=30&page=1"]))
        self.assertEqual(guard_chain("example-owner/example-app", PATTERN, [release("v1", ["x"])]), (None, None, []))


class AcceptedTests(unittest.TestCase):
    """accepted_newest_release: the tag of the newest release that carries no installer on purpose.
    The two histories are those of a real repository, with made-up names: a development build that
    has only a zip sat on top for months (the provider rightly took the installer below it), then
    the vendor renamed the installer in a new release."""

    PATTERN = r"tool-[0-9]+\.exe$"
    ZIP_ONLY = [release("v-next-1", ["tool-next-1.zip"]), release("v20", ["tool-20.exe"]),
                release("v19", ["tool-19.exe"])]
    RENAMED = [release("v21", ["Tool.exe", "Tool.zip"])] + ZIP_ONLY
    REPO = "example-owner/example-app"

    def test_a_dev_build_without_an_installer_stops_the_run_and_the_message_gives_the_exact_command(self):
        tag, error, asked = guard_chain(self.REPO, self.PATTERN, self.ZIP_ONLY)
        self.assertEqual(tag, "v20")
        self.assertIn("Newest: release 'v-next-1', with the files: tool-next-1.zip", error)
        self.assertIn("/usr/libexec/PlistBuddy -c 'Set :Input:accepted_newest_release v-next-1' <the override>", error)
        self.assertIn("`Add :Input:accepted_newest_release string v-next-1`", error)
        self.assertIn("only while that release is the newest and has no such file; the next newer release stops it again", error)
        self.assertIn("no file ending in .msi, .exe, .msix", error)

    def test_the_accepted_tag_lets_the_run_go_on_and_says_so_in_every_run(self):
        result = guard_run(self.REPO, self.PATTERN, self.ZIP_ONLY, accepted="v-next-1")
        self.assertEqual((result["tag"], result["error"]), ("v20", None))
        self.assertEqual(len(result["asked"]), 1)  # the guard still looks at GitHub's list
        loud = [text for level, text in result["messages"] if level == 0]
        self.assertEqual(len(loud), 1)
        for needle in ("An older release is taken on purpose", "'v-next-1'", "has 1 file", "accepted_newest_release",
                       "the provider took release 'v20', file 'tool-20.exe'", "A newer release stops the run again"):
            self.assertIn(needle, loud[0])
        self.assertNotIn("\n", loud[0])

    def test_a_later_rename_is_not_hidden_by_the_tag_that_was_accepted_before(self):
        """What the first version's whole switch let through: the vendor renames the installer in v21, the
        provider goes back to v20 without a word, and the guard has to stop."""
        tag, error, asked = guard_chain(self.REPO, self.PATTERN, self.RENAMED, accepted="v-next-1")
        self.assertEqual(tag, "v20")
        self.assertEqual(len(asked), 1)
        self.assertIn("Newest: release 'v21', with the files: Tool.exe, Tool.zip", error)
        self.assertIn("accepted_newest_release is 'v-next-1', which is not the newest release. ", error)
        # v21 holds a Windows installer under a new name: no acceptance is offered for it
        self.assertIn("has Windows installer files: release 'v21' (Tool.exe)", error)
        self.assertNotIn("PlistBuddy", error)
        result = guard_run(self.REPO, self.PATTERN, self.RENAMED, accepted="v-next-1")
        self.assertEqual([text for level, text in result["messages"] if level == 0], [])

    def test_the_tag_must_be_exactly_the_newest_one(self):
        for accepted in ("v-next", "V-NEXT-1", "v-next-10", "v-next-1 v21", "v20"):
            with self.subTest(accepted=accepted):
                self.assertIsNotNone(guard_chain(self.REPO, self.PATTERN, self.ZIP_ONLY, accepted=accepted)[1])
        for accepted in ("v-next-1", " v-next-1 ", "\tv-next-1\n"):
            with self.subTest(accepted=accepted):
                self.assertIsNone(guard_chain(self.REPO, self.PATTERN, self.ZIP_ONLY, accepted=accepted)[1])

    def test_a_tag_that_is_not_needed_is_said_at_the_verbose_level(self):
        releases = [release("v2", ["tool-2.exe"]), release("v1", ["tool-1.exe"])]
        result = guard_run(self.REPO, self.PATTERN, releases, accepted="v-next-1")
        self.assertIsNone(result["error"])
        self.assertEqual([text for level, text in result["messages"] if level == 0], [])
        texts = [text for level, text in result["messages"]]
        self.assertTrue(any("accepted_newest_release is 'v-next-1' but is not needed" in text for text in texts))

    def test_nothing_or_nothing_but_blanks_names_no_release(self):
        for value in (None, "", "   ", "\n"):
            with self.subTest(value=value):
                self.assertIsNotNone(guard_chain(self.REPO, self.PATTERN, self.ZIP_ONLY, accepted=value)[1])
        self.assertIsNone(newest_release.parse_accepted_tag(None))
        self.assertIsNone(newest_release.parse_accepted_tag(" "))
        self.assertEqual(newest_release.parse_accepted_tag(" v1 "), "v1")

    def test_anything_but_text_is_an_error_and_nothing_is_asked(self):
        for value in (True, False, 1, 1.5, [], ["v1"], {"a": 1}):
            with self.subTest(value=value):
                with mock.patch.object(newest_release, "fetch_releases") as fetch:
                    processor, _ = new_processor(
                        GUARD, selected_env(self.ZIP_ONLY, "v20", "tool-20.exe", accepted_newest_release=value))
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                fetch.assert_not_called()
                self.assertIn("accepted_newest_release must be the tag of a release, as text", str(caught.exception))

    def test_the_first_versions_switch_is_refused_with_a_message(self):
        for value in (True, "true", 1, "x"):
            with self.subTest(value=value):
                with mock.patch.object(newest_release, "fetch_releases") as fetch:
                    processor, _ = new_processor(
                        GUARD, selected_env(self.ZIP_ONLY, "v20", "tool-20.exe", allow_older_release=value))
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                fetch.assert_not_called()
                self.assertIn("allow_older_release does not exist any more", str(caught.exception))
                self.assertIn("accepted_newest_release", str(caught.exception))
        for value in (False, "", None, 0):
            with self.subTest(value=value):
                run_guard(self.ZIP_ONLY, "v-next-1", "tool-next-1.zip", allow_older_release=value)

    def test_a_tag_that_a_shell_would_read_gets_no_command(self):
        for tag in ("v1$(touch x)", "v1;x", "v 1", "v1'x", "v1`x`", "v1\"x", "v1&x", "v1|x", "v1<x", "v" + "1" * 90):
            with self.subTest(tag=tag):
                releases = [release(tag, ["tool-next.zip"]), release("v20", ["tool-20.exe"])]
                error = guard_chain(self.REPO, self.PATTERN, releases)[1]
                self.assertNotIn("PlistBuddy", error)
                self.assertNotIn("Set :Input", error)
                self.assertIn("no command is printed", error)
        for tag in ("v1.2-rc+3", "26.03", "release_2026-10"):
            with self.subTest(tag=tag):
                releases = [release(tag, ["tool-next.zip"]), release("v20", ["tool-20.exe"])]
                self.assertIn("'Set :Input:accepted_newest_release %s'" % tag, guard_chain(self.REPO, self.PATTERN, releases)[1])

    def test_the_accepted_tag_does_not_excuse_a_bad_url(self):
        with mock.patch.object(newest_release, "fetch_releases") as fetch:
            with self.assertRaises(ProcessorError):
                run_processor(GUARD, {"github_asset_api_url": "https://example.test/x", "accepted_newest_release": "v1"})
        fetch.assert_not_called()

    def test_the_accepted_tag_goes_with_a_selected_file_that_is_older_than_the_list(self):
        listed = [release("v-next-1", ["tool-next-1.zip"]), release("v21", ["Tool.zip"])]
        old = release("v0.1", ["tool-1.exe"])
        env = selected_env([old], "v0.1", "tool-1.exe", accepted_newest_release="v-next-1")
        with mock.patch.object(newest_release, "fetch_releases", side_effect=[listed]):
            processor, _ = new_processor(GUARD, env)
            processor.main()
        self.assertIn("the provider took release 'v0.1' (not in the list that was read), file 'tool-1.exe'",
                      [text for level, text in processor.message_levels if level == 0][0])

    def test_the_declaration_of_the_input(self):
        flags = GUARD.input_variables["accepted_newest_release"]
        self.assertEqual(flags["default"], "")
        self.assertFalse(flags["required"])
        self.assertNotIn("allow_older_release", GUARD.input_variables)


class TagPatternTests(unittest.TestCase):
    """release_tag_pattern: the line of releases that the recipe follows, for a vendor that publishes two
    lines side by side (the real history: Greenshot's 1.3 releases between its 1.4 builds)."""

    REPO = "example-owner/example-app"
    NEW_LINE = r"tool-1\.4\.[0-9]+\.exe$"
    BOTH_LINES = r"tool-[0-9.]+\.exe$"
    LINES = [release("v1.3.320", ["tool-1.3.320.exe"]), release("v1.4.1", ["tool-1.4.1.exe"]),
             release("v1.4.0", ["tool-1.4.0.exe"]), release("v1.3.319", ["tool-1.3.319.exe"])]

    def test_without_the_pattern_a_release_of_the_other_line_on_top_stops_a_run_that_is_right(self):
        tag, error, asked = guard_chain(self.REPO, self.NEW_LINE, self.LINES)
        self.assertEqual(tag, "v1.4.1")  # the provider follows the new line, by its file pattern
        self.assertIn("Newest: release 'v1.3.320'", error)
        self.assertIn("release_tag_pattern", error)

    def test_with_the_pattern_the_newest_release_of_the_line_is_the_one_that_counts(self):
        result = guard_run(self.REPO, self.NEW_LINE, self.LINES, tag_pattern=r"v1\.4\.")
        self.assertEqual((result["tag"], result["error"]), ("v1.4.1", None))
        self.assertEqual(len(result["asked"]), 1)
        lines = [text for level, text in result["messages"] if level != 0]
        self.assertEqual(lines, ["The selected release 'v1.4.1' of example-owner/example-app is the newest release "
                                 "that is not a pre-release whose tag matches 'v1\\.4\\.'."])
        loud = [text for level, text in result["messages"] if level == 0]  # the pattern left a release out: said
        self.assertEqual(len(loud), 1)
        self.assertIn("left out 1 newer release of example-owner/example-app: 'v1.3.320'", loud[0])

    def test_a_release_of_the_older_line_published_after_the_new_one_is_not_seen_without_the_pattern(self):
        """The limit that the README names: the guard compares positions in the list, not versions."""
        lines = [release("v1.3.321", ["tool-1.3.321.exe"]), release("v1.4.0", ["tool-1.4.0.exe"])]
        tag, error, asked = guard_chain(self.REPO, self.BOTH_LINES, lines)
        self.assertEqual((tag, error), ("v1.3.321", None))  # the provider takes the old line and nothing says so

    def test_with_the_pattern_the_same_backport_stops_the_run(self):
        lines = [release("v1.3.321", ["tool-1.3.321.exe"]), release("v1.4.0", ["tool-1.4.0.exe"])]
        tag, error, asked = guard_chain(self.REPO, self.BOTH_LINES, lines, tag_pattern=r"v1\.4\.")
        self.assertEqual(tag, "v1.3.321")
        self.assertIn("Selected: release 'v1.3.321', file 'tool-1.3.321.exe'", error)
        self.assertIn("Newest: release 'v1.4.0'", error)
        self.assertIn("newest release that is not a pre-release whose tag matches 'v1\\.4\\.'", error)

    def test_the_pattern_is_matched_from_the_start_like_the_providers(self):
        self.assertIsNone(newest_release.newest_candidate(self.LINES, False, newest_release.parse_tag_pattern(r"1\.4")))
        self.assertIsNotNone(newest_release.newest_candidate(self.LINES, False, newest_release.parse_tag_pattern(r".*1\.4")))
        error = guard_chain(self.REPO, self.NEW_LINE, self.LINES, tag_pattern=r"1\.4")[1]
        self.assertIn("none that the provider could take", error)
        self.assertIn("release_tag_pattern", error)

    def test_the_other_rules_still_apply_inside_the_line(self):
        releases = [release("v1.4.2-beta", ["tool-1.4.2.exe"], prerelease=True), release("v1.4.1", ["tool-1.4.1.exe"]),
                    release("v1.4.0", ["tool-1.4.0.exe"], draft=True)]
        pattern = newest_release.parse_tag_pattern(r"v1\.4\.")
        self.assertIs(newest_release.newest_candidate(releases, False, pattern), releases[1])
        self.assertIs(newest_release.newest_candidate(releases, True, pattern), releases[0])
        self.assertFalse(newest_release.is_candidate(releases[2], True, pattern))
        self.assertTrue(newest_release.is_candidate(releases[1], False, None))

    def test_a_release_without_a_tag_is_not_of_a_line(self):
        pattern = newest_release.parse_tag_pattern("v")
        for release_record in ({}, {"tag_name": None}, {"tag_name": 5}):
            self.assertFalse(newest_release.is_candidate(release_record, False, pattern))
            self.assertTrue(newest_release.is_candidate(release_record, False, None))

    def test_a_page_with_only_the_other_line_sends_the_guard_to_the_next_page(self):
        page_one = [release("v1.3.%d" % n, ["tool-1.3.%d.exe" % n]) for n in range(newest_release.RELEASES_PER_PAGE)]
        page_two = [release("v1.4.0", ["tool-1.4.0.exe"])]
        everything = page_one + page_two
        env = selected_env(everything, "v1.4.0", "tool-1.4.0.exe", release_tag_pattern=r"v1\.4\.")
        with mock.patch.object(newest_release, "fetch_releases", side_effect=[page_one, page_two]) as fetch:
            processor, _ = new_processor(GUARD, env)
            processor.main()
        self.assertEqual(fetch.call_args_list, [mock.call(OWNER, REPO, 1), mock.call(OWNER, REPO, 2)])

    def test_a_blank_pattern_is_none_and_a_bad_one_is_an_error_before_anything_is_asked(self):
        for value in (None, "", "  "):
            self.assertIsNone(newest_release.parse_tag_pattern(value))
        for value, needle in (("(", "not a regular expression"), ("[", "not a regular expression"),
                              (5, "must be a regular expression"), (True, "must be a regular expression"),
                              (["v"], "must be a regular expression")):
            with self.subTest(value=value):
                with mock.patch.object(newest_release, "fetch_releases") as fetch:
                    processor, _ = new_processor(
                        GUARD, selected_env(self.LINES, "v1.4.1", "tool-1.4.1.exe", release_tag_pattern=value))
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                fetch.assert_not_called()
                self.assertIn(needle, str(caught.exception))

    def test_the_declaration_of_the_input(self):
        flags = GUARD.input_variables["release_tag_pattern"]
        self.assertEqual(flags["default"], "")
        self.assertFalse(flags["required"])


class UnsupportedInputTests(unittest.TestCase):
    """sort_by_highest_tag_names and latest_only change which release the provider takes
    (GitHubReleasesInfoProvider.py:222-225 and :148-149). The guard refuses a recipe that sets either:
    there is no silent difference between its idea of the newest release and the provider's."""

    RELEASES = [release("v1.3.320", ["tool-1.3.320.exe"]), release("v1.4.0", ["tool-1.4.0.exe"])]

    def refuse(self, name, value, **more):
        with mock.patch.object(newest_release, "fetch_releases") as fetch:
            processor, _ = new_processor(GUARD, selected_env(self.RELEASES, "v1.4.0", "tool-1.4.0.exe", **{name: value}, **more))
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        fetch.assert_not_called()
        return str(caught.exception)

    def test_a_true_value_of_either_input_is_refused_before_anything_is_asked(self):
        for name in ("sort_by_highest_tag_names", "latest_only"):
            for value in (True, "true", "false", 1, "x"):
                with self.subTest(name=name, value=value):
                    text = self.refuse(name, value)
                    self.assertIn("does not support the provider's input %s" % name, text)
                    self.assertIn("Remove it from the override's Input", text)
                    self.assertIn("release_tag_pattern", text)

    def test_the_refusal_has_no_way_round_it(self):
        text = self.refuse("sort_by_highest_tag_names", True, accepted_newest_release="v1.4.0")
        self.assertIn("does not support", text)
        text = self.refuse("latest_only", True, release_tag_pattern="v")
        self.assertIn("does not support", text)

    def test_an_empty_value_is_not_set(self):
        for name in ("sort_by_highest_tag_names", "latest_only"):
            for value in (False, "", None, 0):
                with self.subTest(name=name, value=value):
                    messages, fetch = run_guard(self.RELEASES[::-1], "v1.4.0", "tool-1.4.0.exe", **{name: value})
                    self.assertEqual(fetch.call_count, 1)

    def test_the_two_inputs_are_declared_as_not_supported(self):
        for name in ("sort_by_highest_tag_names", "latest_only"):
            flags = GUARD.input_variables[name]
            self.assertFalse(flags["required"])
            self.assertIn("Not supported", flags["description"])
        self.assertEqual(newest_release.UNSUPPORTED_PROVIDER_INPUTS, ("sort_by_highest_tag_names", "latest_only"))


class InstallerRuleTests(unittest.TestCase):
    """R1: a release that has a Windows installer file (a name ending in .msi, .exe or .msix) is a renamed
    installer, not a release without one: no acceptance is offered for it and none is honoured."""

    PATTERN = r"tool-[0-9]+\.exe$"
    REPO = "example-owner/example-app"
    OLD = [release("v20", ["tool-20.exe"]), release("v19", ["tool-19.exe"])]

    def test_the_extensions_are_a_named_constant(self):
        self.assertEqual(newest_release.INSTALLER_EXTENSIONS, (".msi", ".exe", ".msix"))

    def test_the_installer_files_of_a_release(self):
        names = ["a.msi", "B.MSI", "c.Exe", "d.msix", "e.MsiX", "f.zip", "g.msi.asc", "h.exe.sig", "i.msixbundle",
                 "j.dmg", "msi", "k.exe ", "l.exe\n"]
        found = newest_release.installer_files(release("v1", names))
        self.assertEqual(found, ["a.msi", "B.MSI", "c.Exe", "d.msix", "e.MsiX"])
        self.assertEqual(newest_release.installer_files(release("v1", [])), [])
        self.assertEqual(newest_release.installer_files({"assets": None}), [])
        self.assertEqual(newest_release.installer_files({"assets": [{"name": 5}, {}]}), [])

    def test_a_newest_release_with_an_installer_gets_no_acceptance_command_and_the_message_says_why(self):
        for name in ("Tool-Setup.msi", "Tool-Setup.exe", "TOOL.MSIX"):
            with self.subTest(name=name):
                releases = [release("v21", [name, "Tool.zip"])] + self.OLD
                tag, error, asked = guard_chain(self.REPO, self.PATTERN, releases)
                self.assertEqual(tag, "v20")
                self.assertIn("has Windows installer files: release 'v21' (%s)" % name, error)
                self.assertIn("That is a renamed installer, not a release without one", error)
                self.assertIn("correct SEARCH_PATTERN", error)
                self.assertIn("No acceptance is offered for it", error)
                self.assertNotIn("PlistBuddy", error)
                self.assertNotIn("Set :Input", error)

    def test_an_accepted_tag_stops_passing_when_an_installer_is_added_to_that_release_later(self):
        """A release that is being filled in: zip only when it was accepted, an installer under a new name
        some days later. The run passes before and stops after."""
        zip_only = [release("v21", ["Tool.zip"])] + self.OLD
        self.assertIsNone(guard_chain(self.REPO, self.PATTERN, zip_only, accepted="v21")[1])
        filled = [release("v21", ["Tool.zip", "Tool-Setup.msi"])] + self.OLD
        tag, error, asked = guard_chain(self.REPO, self.PATTERN, filled, accepted="v21")
        self.assertEqual(tag, "v20")
        self.assertIn("accepted_newest_release is 'v21', but that release has Windows installer files (Tool-Setup.msi): "
                      "it is no longer accepted.", error)
        self.assertNotIn("PlistBuddy", error)
        result = guard_run(self.REPO, self.PATTERN, filled, accepted="v21")
        self.assertEqual([text for level, text in result["messages"] if level == 0], [])
        self.assertNotIn("summary", result)  # nothing is reported as accepted

    def test_the_installer_names_in_the_advice_are_limited(self):
        names = ["Tool-%d.msi" % n for n in range(newest_release.MAX_INSTALLER_NAMES_SHOWN + 3)]
        advice = newest_release.what_to_do(release("v21", names))
        self.assertIn("Tool-0.msi", advice)
        self.assertIn("and 3 more", advice)
        self.assertNotIn("Tool-%d.msi" % newest_release.MAX_INSTALLER_NAMES_SHOWN, advice)

    def test_the_accepted_line_names_the_files_of_the_accepted_release(self):
        zip_only = [release("v21", ["Tool.zip", "Tool.tar.gz"])] + self.OLD
        result = guard_run(self.REPO, self.PATTERN, zip_only, accepted="v21")
        loud = [text for level, text in result["messages"] if level == 0]
        self.assertEqual(len(loud), 1)
        self.assertIn("has 2 files (Tool.zip, Tool.tar.gz) and the override accepts it", loud[0])
        empty = [release("v21", [])] + self.OLD
        loud = [text for level, text in guard_run(self.REPO, self.PATTERN, empty, accepted="v21")["messages"] if level == 0]
        self.assertIn("has no files and the override accepts it", loud[0])


class BetweenTests(unittest.TestCase):
    """R3: an acceptance covers the newest release only. A release between it and the selected one
    that has a Windows installer file is a rename below it, and the stop names it."""

    PATTERN = r"tool-[0-9]+\.exe$"
    REPO = "example-owner/example-app"

    def test_a_rename_just_below_an_accepted_dev_build_is_not_excused(self):
        """The reader's case: a dev build on top, the renamed release below it, the old installer below that."""
        releases = [release("vNext-2", ["Tool-next-2.zip"]), release("v21", ["Tool-Setup.msi"]),
                    release("v20", ["tool-20.exe"])]
        result = guard_run(self.REPO, self.PATTERN, releases, accepted="vNext-2")
        self.assertEqual(result["tag"], "v20")
        text = result["error"]
        self.assertIn("Between them in the list: release 'v21', with the files: Tool-Setup.msi", text)
        self.assertIn("a release between it and the selected one has Windows installer files: an acceptance does "
                      "not cover a rename below it", text)
        self.assertIn("release 'v21' (Tool-Setup.msi)", text)  # the advice names it
        self.assertNotIn("PlistBuddy", text)
        self.assertEqual([t for level, t in result["messages"] if level == 0], [])

    def test_the_plain_stop_names_the_releases_between_the_newest_and_the_selected_one(self):
        releases = [release("v22", ["Tool-22.zip"]), release("v21", ["Tool-Setup.msi"]), release("v20", ["tool-20.exe"])]
        error = guard_chain(self.REPO, self.PATTERN, releases)[1]
        self.assertIn("Newest: release 'v22', with the files: Tool-22.zip. Between them in the list: release 'v21', "
                      "with the files: Tool-Setup.msi. ", error)

    def test_two_releases_without_an_installer_in_a_row_are_accepted_by_the_tag_of_the_newest(self):
        releases = [release("vNext-2", ["Tool-next-2.zip"]), release("vNext-1", ["Tool-next-1.zip"]),
                    release("v20", ["tool-20.exe"])]
        result = guard_run(self.REPO, self.PATTERN, releases, accepted="vNext-2")
        self.assertEqual((result["tag"], result["error"]), ("v20", None))
        # the second one alone does not do: it is not the newest
        error = guard_chain(self.REPO, self.PATTERN, releases, accepted="vNext-1")[1]
        self.assertIn("accepted_newest_release is 'vNext-1', which is not the newest release. ", error)

    def test_releases_that_are_not_candidates_between_do_not_count(self):
        releases = [release("vNext-2", ["Tool-next-2.zip"]),
                    release("v21-beta", ["Tool-Setup.msi"], prerelease=True),
                    release("v21-draft", ["Tool-Setup.msi"], draft=True),
                    release("v20", ["tool-20.exe"])]
        self.assertIsNone(guard_chain(self.REPO, self.PATTERN, releases, accepted="vNext-2")[1])
        # with pre-releases included the renamed one counts
        error = guard_chain(self.REPO, self.PATTERN, releases, include_prereleases=True, accepted="vNext-2")[1]
        self.assertIn("Between them in the list: release 'v21-beta'", error)

    def test_only_releases_of_the_line_count_between(self):
        releases = [release("v1.4.9", ["Tool-next.zip"]), release("v1.3.9", ["Tool-Setup.msi"]),
                    release("v1.4.1", ["tool-1.exe"])]
        self.assertIsNone(guard_chain(self.REPO, r"tool-[0-9]+\.exe$", releases, accepted="v1.4.9", tag_pattern=r"v1\.4\.")[1])
        error = guard_chain(self.REPO, r"tool-[0-9]+\.exe$", releases, accepted="v1.4.9")[1]
        self.assertIn("Between them in the list: release 'v1.3.9'", error)

    def test_a_selected_release_that_is_listed_above_the_newest_is_not_an_older_release(self):
        """With a tag pattern the provider can take a release of another line that is listed above the newest
        release of the line: an acceptance does not cover that."""
        releases = [release("v1.3.9", ["tool-9.exe"]), release("v1.4.0", ["Tool-next.zip"])]
        error = guard_chain(self.REPO, self.PATTERN, releases, accepted="v1.4.0", tag_pattern=r"v1\.4\.")[1]
        self.assertIn("the provider took a release that is listed above it: an acceptance covers an older release only", error)

    def test_a_selected_release_that_the_list_does_not_hold_counts_every_release_read(self):
        listed = [release("vNext-1", ["Tool-next.zip"]), release("v21", ["Tool-Setup.msi"])]
        old = release("v0.1", ["tool-1.exe"])
        env = selected_env([old], "v0.1", "tool-1.exe", accepted_newest_release="vNext-1")
        with mock.patch.object(newest_release, "fetch_releases", side_effect=[listed]):
            processor, _ = new_processor(GUARD, env)
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        self.assertIn("Between them in the list: release 'v21'", str(caught.exception))
        listed[1] = release("v21", ["Tool.zip"])
        with mock.patch.object(newest_release, "fetch_releases", side_effect=[listed]):
            processor, _ = new_processor(GUARD, env)
            processor.main()

    def test_the_between_list_is_limited(self):
        between = [release("b%d" % n, ["Tool-%d.zip" % n]) for n in range(newest_release.MAX_BETWEEN_SHOWN + 4)]
        text = newest_release.between_text(between)
        self.assertIn("release 'b0'", text)
        self.assertNotIn("release 'b%d'" % newest_release.MAX_BETWEEN_SHOWN, text)
        self.assertTrue(text.endswith("and 4 more"))

    def test_the_pure_helpers(self):
        a, b, c, d = release("a", []), release("b", []), release("c", [], prerelease=True), release("d", [])
        listed = [a, b, c, d]
        self.assertEqual(newest_release.releases_between(listed, a, d, False), [b])
        self.assertEqual(newest_release.releases_between(listed, a, d, True), [b, c])
        self.assertEqual(newest_release.releases_between(listed, a, None, False), [b, d])
        self.assertEqual(newest_release.releases_between(listed, b, a, False), [d])  # selected above: to the end
        self.assertTrue(newest_release.listed_above(listed, b, a))
        self.assertFalse(newest_release.listed_above(listed, a, b))
        self.assertFalse(newest_release.listed_above(listed, a, None))
        with_msi = release("x", ["a.msi"])
        self.assertEqual(newest_release.with_installers(a, [with_msi, b]), [with_msi])
        newest_with = release("n", ["n.msix"])
        self.assertEqual(newest_release.with_installers(newest_with, [b]), [newest_with])
        self.assertEqual(newest_release.with_installers(a, [b]), [])


class SkippedByPatternTests(unittest.TestCase):
    """R2: a release_tag_pattern hides the releases it leaves out, so every run names the newer ones."""

    REPO = "example-owner/example-app"
    NEW_LINE = r"tool-1\.4\.[0-9]+\.exe$"
    LINES = [release("v2.0.0", ["Tool-Setup-2.0.0.exe"]), release("v1.3.9", ["tool-1.3.9.exe"]),
             release("v1.4.5", ["tool-1.4.5.exe"]), release("v1.4.4", ["tool-1.4.4.exe"])]

    def test_a_pattern_that_leaves_a_rename_out_says_so_in_every_run(self):
        """The reader's case 2: the next line changes the tag and the file name. The pattern passes the run;
        the line says which releases it left out."""
        result = guard_run(self.REPO, self.NEW_LINE, self.LINES, tag_pattern=r"v1\.4\.")
        self.assertEqual((result["tag"], result["error"]), ("v1.4.5", None))
        loud = [text for level, text in result["messages"] if level == 0]
        self.assertEqual(loud, ["release_tag_pattern 'v1\\.4\\.' left out 2 newer releases of example-owner/example-app: "
                                "'v2.0.0', 'v1.3.9'. If one of them carries the installer that this recipe should take, "
                                "the pattern hides a rename."])

    def test_the_line_is_printed_when_the_run_stops_and_when_it_accepts_too(self):
        stopped = guard_run(self.REPO, self.NEW_LINE, self.LINES, tag_pattern=r"v1\.4\.", accepted="v1.4.4")
        self.assertIn("left out 2 newer releases", [text for level, text in stopped["messages"] if level == 0][0])
        releases = [release("v2.0.0", ["Tool-2.zip"]), release("v1.4.9", ["Tool-next.zip"]), release("v1.4.1", ["tool-1.4.1.exe"])]
        accepted = guard_run(self.REPO, self.NEW_LINE, releases, tag_pattern=r"v1\.4\.", accepted="v1.4.9")
        self.assertIsNone(accepted["error"])
        loud = [text for level, text in accepted["messages"] if level == 0]
        self.assertEqual(len(loud), 2)
        self.assertIn("left out 1 newer release of", loud[0])
        self.assertIn("An older release is taken on purpose", loud[1])

    def test_nothing_is_said_when_the_pattern_left_nothing_out(self):
        result = guard_run(self.REPO, self.NEW_LINE, self.LINES[2:], tag_pattern=r"v1\.4\.")
        self.assertEqual([text for level, text in result["messages"] if level == 0], [])
        self.assertNotIn("left out", " ".join(text for level, text in result["messages"]))

    def test_only_releases_that_would_count_are_named(self):
        releases = [release("v3-beta", ["Tool-3.exe"], prerelease=True), release("v3-draft", ["Tool-3.exe"], draft=True),
                    release("v2.0.0", ["Tool-2.exe"]), release("v1.4.5", ["tool-1.4.5.exe"])]
        loud = [t for level, t in guard_run(self.REPO, self.NEW_LINE, releases, tag_pattern=r"v1\.4\.")["messages"] if level == 0]
        self.assertEqual(len(loud), 1)
        self.assertIn("left out 1 newer release of example-owner/example-app: 'v2.0.0'", loud[0])
        loud = [t for level, t in guard_run(self.REPO, self.NEW_LINE, releases, include_prereleases=True, tag_pattern=r"v1\.4\.")["messages"] if level == 0]
        self.assertIn("left out 2 newer releases of example-owner/example-app: 'v3-beta', 'v2.0.0'", loud[0])

    def test_the_tags_are_limited_and_the_rest_is_counted(self):
        others = [release("w%d" % n, ["Tool-%d.exe" % n]) for n in range(newest_release.MAX_SKIPPED_TAGS_SHOWN + 3)]
        releases = others + [release("v1.4.5", ["tool-1.4.5.exe"])]
        loud = [t for level, t in guard_run(self.REPO, self.NEW_LINE, releases, tag_pattern=r"v1\.4\.")["messages"] if level == 0]
        self.assertIn("left out %d newer releases" % (newest_release.MAX_SKIPPED_TAGS_SHOWN + 3), loud[0])
        self.assertIn("'w0'", loud[0])
        self.assertNotIn("'w%d'" % newest_release.MAX_SKIPPED_TAGS_SHOWN, loud[0])
        self.assertIn("and 3 more.", loud[0])

    def test_the_pattern_is_not_recommended_as_a_cure_for_a_rename(self):
        releases = [release("v21", ["Tool.zip"]), release("v20", ["tool-20.exe"])]
        error = guard_chain(self.REPO, r"tool-[0-9]+\.exe$", releases)[1]
        self.assertIn("and only then, name the line you follow with release_tag_pattern", error)
        self.assertIn("it is not a cure for a rename; every run says which ones it left out", error)

    def test_the_helper_and_the_summary_row(self):
        listed = [release("a", []), release("b", [], prerelease=True), release("c", [])]
        pattern = newest_release.parse_tag_pattern("c")
        self.assertEqual(newest_release.skipped_by_pattern(listed, listed[2], False), [listed[0]])
        self.assertEqual(newest_release.skipped_by_pattern(listed, listed[2], True), [listed[0], listed[1]])
        self.assertEqual(newest_release.skipped_by_pattern(listed, listed[0], True), [])
        result = guard_run(self.REPO, self.NEW_LINE, self.LINES, tag_pattern=r"v1\.4\.")
        self.assertIn("release_tag_pattern left out 2 newer releases", result["summary"]["data"]["reason"])


class SummaryTests(unittest.TestCase):
    """R4: what a person should look at goes into AutoPkg's end-of-run table and report plist."""

    PATTERN = r"tool-[0-9]+\.exe$"
    REPO = "example-owner/example-app"
    ZIP_ONLY = [release("v-next-1", ["tool-next-1.zip"]), release("v20", ["tool-20.exe"])]

    def test_an_accepted_older_release_sets_the_summary(self):
        result = guard_run(self.REPO, self.PATTERN, self.ZIP_ONLY, accepted="v-next-1")
        summary = result["summary"]
        self.assertEqual(summary["summary_text"], "The release guard let a run go on with something to look at:")
        self.assertEqual(summary["report_fields"], ["repository", "newest_release", "release_taken", "reason"])
        self.assertEqual(summary["data"], {
            "repository": "example-owner/example-app", "newest_release": "v-next-1", "release_taken": "v20",
            "reason": "accepted_newest_release: an older release is taken on purpose"})

    def test_a_plain_pass_and_a_stop_set_nothing(self):
        passing = [release("v20", ["tool-20.exe"]), release("v19", ["tool-19.exe"])]
        self.assertNotIn("summary", guard_run(self.REPO, self.PATTERN, passing))
        self.assertNotIn("summary", guard_run(self.REPO, self.PATTERN, self.ZIP_ONLY))

    def test_a_pattern_that_left_releases_out_sets_the_summary_even_when_the_run_passes(self):
        releases = [release("v2.0.0", ["Tool-2.exe"]), release("v1.4.5", ["tool-1.4.5.exe"])]
        summary = guard_run(self.REPO, r"tool-1\.4\.[0-9]+\.exe$", releases, tag_pattern=r"v1\.4\.")["summary"]
        self.assertEqual(summary["data"]["newest_release"], "v1.4.5")
        self.assertEqual(summary["data"]["release_taken"], "v1.4.5")
        self.assertEqual(summary["data"]["reason"], "release_tag_pattern left out 1 newer release")

    def test_both_reasons_are_in_one_row(self):
        releases = [release("v2.0.0", ["Tool-2.exe"]), release("v1.4.9", ["Tool-next.zip"]), release("v1.4.1", ["tool-1.4.1.exe"])]
        data = guard_run(self.REPO, r"tool-1\.4\.[0-9]+\.exe$", releases, tag_pattern=r"v1\.4\.", accepted="v1.4.9")["summary"]["data"]
        self.assertEqual(data["reason"], "release_tag_pattern left out 1 newer release; accepted_newest_release: an "
                                         "older release is taken on purpose")

    def test_the_variable_is_declared_and_has_the_shape_that_autopkg_collects(self):
        """AutoPkg (autopkg `run_recipes`) collects the output variables that end in _summary_result, needs a
        non-empty `data` dict, builds its table from `report_fields`, and takes len() of each cell."""
        self.assertTrue(newest_release.SUMMARY_KEY.endswith("_summary_result"))
        self.assertIn(newest_release.SUMMARY_KEY, GUARD.output_variables)
        self.assertEqual(set(GUARD.output_variables), {newest_release.SUMMARY_KEY})
        summary = guard_run(self.REPO, self.PATTERN, self.ZIP_ONLY, accepted="v-next-1")["summary"]
        self.assertTrue(summary["data"])
        for field in summary["report_fields"]:
            self.assertIsInstance(summary["data"][field], str)
            self.assertTrue(summary["data"][field])
            len(summary["data"][field])
        self.assertEqual(set(summary["data"]), set(summary["report_fields"]))
        self.assertEqual(set(summary), {"summary_text", "report_fields", "data"})

    def test_autopkg_would_keep_it_in_the_receipt_only_when_it_is_declared_and_true(self):
        """AutoPackager.process copies a variable into the step's Output when it is in output_variables
        and truthy: simulate that on a run that sets it and on one that does not."""
        for releases, accepted, expected in ((self.ZIP_ONLY, "v-next-1", True), (self.ZIP_ONLY[1:], None, False)):
            env = selected_env(releases, releases[-1]["tag_name"], releases[-1]["assets"][0]["name"])
            if accepted:
                env["accepted_newest_release"] = accepted
            with mock.patch.object(newest_release, "fetch_releases", side_effect=[releases]):
                processor, _ = new_processor(GUARD, env)
                processor.main()
            output = {key: processor.env[key] for key in processor.output_variables if processor.env.get(key)}
            self.assertEqual(newest_release.SUMMARY_KEY in output, expected)

    def test_a_result_of_an_earlier_recipe_is_not_reported_again(self):
        passing = [release("v20", ["tool-20.exe"])]
        env = selected_env(passing, "v20", "tool-20.exe")
        env[newest_release.SUMMARY_KEY] = {"summary_text": "old", "data": {"x": "y"}}
        with mock.patch.object(newest_release, "fetch_releases", side_effect=[passing]):
            processor, _ = new_processor(GUARD, env)
            processor.main()
        self.assertNotIn(newest_release.SUMMARY_KEY, processor.env)

    def test_the_row_holds_tags_and_a_reason_only(self):
        releases = [release("v-next-1", ["tool-next-1.zip"]), release("v20", ["tool-20.exe"])]
        text = repr(guard_run(self.REPO, self.PATTERN, releases, accepted="v-next-1")["summary"])
        for word in ("http", "token", "Authorization", "/Users", "tool-20.exe", "tool-next-1.zip"):
            self.assertNotIn(word, text)


class WordingTests(unittest.TestCase):
    """R5 and R6."""

    PATTERN = r"tool-[0-9]+\.exe$"
    REPO = "example-owner/example-app"

    def test_a_mistyped_tag_is_not_called_a_former_newest_release(self):
        releases = [release("v-next-1", ["tool-next-1.zip"]), release("v20", ["tool-20.exe"])]
        error = guard_chain(self.REPO, self.PATTERN, releases, accepted="v-next-9")[1]
        self.assertIn("accepted_newest_release is 'v-next-9', which is not the newest release. ", error)
        self.assertNotIn("any more", error)

    def test_a_tag_that_a_shell_reads_is_to_be_copied_from_the_vendors_page(self):
        releases = [release("v1$(id)", ["tool-next.zip"]), release("v20", ["tool-20.exe"])]
        error = guard_chain(self.REPO, self.PATTERN, releases)[1]
        self.assertIn("no command is printed; copy the tag exactly as the vendor's release page writes it, because the tag "
                      "above is cleaned and cut for printing", error)
        self.assertNotIn("as written above", error)

    def test_backticks_from_github_are_not_let_into_a_message(self):
        releases = [release("v21", ["Tool.zip"], title="Tool `rm -rf` 21"), release("v20", ["tool-20.exe"])]
        error = guard_chain(self.REPO, self.PATTERN, releases)[1]
        self.assertIn("(titled 'Tool 'rm -rf' 21')", error)
        self.assertEqual(newest_release.shown("a`b`c"), "a'b'c")
        # the commands of the advice keep their backticks: they are the processor's own
        self.assertIn("`/usr/libexec/PlistBuddy", error)
        names = [release("v21", ["Tool`x`.zip"]), release("v20", ["tool-20.exe"])]
        self.assertIn("Tool'x'.zip", guard_chain(self.REPO, self.PATTERN, names)[1])

    def test_a_tag_with_shell_syntax_but_no_other_refused_character_gets_no_command(self):
        """The reader's R6: every unsafe tag of the earlier test also held a space or a quote."""
        for tag in ("v1$(id)", "v1$id", "v1${HOME}", "v1{a,b}", "v1(x)", "v1)", "v1$", "v1!", "v1*", "v1?", "v1#x",
                    "v1~", "v1=x", "v1%x", "v1@x", "v1^x", "v1[x]", "v1" + chr(92) + "x", "v1/x", "v1:x", "v1,x"):
            with self.subTest(tag=tag):
                releases = [release(tag, ["tool-next.zip"]), release("v20", ["tool-20.exe"])]
                error = guard_chain(self.REPO, self.PATTERN, releases)[1]
                self.assertNotIn("PlistBuddy", error)
                self.assertIn("no command is printed", error)
                self.assertFalse(newest_release.SAFE_TAG_PATTERN.fullmatch(tag))


class UrlTests(unittest.TestCase):
    def test_the_owner_and_the_repository_come_from_the_url_of_the_asset(self):
        self.assertEqual(
            newest_release.parse_asset_url("https://api.github.com/repos/Some-Owner/some.repo_1/releases/assets/0042"),
            ("Some-Owner", "some.repo_1", 42),
        )

    def test_the_address_that_is_asked_is_built_from_constants_and_the_parsed_names(self):
        self.assertEqual(
            newest_release.releases_url("o", "r", 2),
            "https://api.github.com/repos/o/r/releases?per_page=30&page=2",
        )
        self.assertEqual(newest_release.RELEASES_PER_PAGE, 30)

    def test_only_the_api_url_of_an_asset_is_accepted(self):
        good = "https://api.github.com/repos/o/r/releases/assets/1"
        bad = [
            None, "", 5, [],
            "http://api.github.com/repos/o/r/releases/assets/1",
            "https://github.com/o/r/releases/download/v1/app.exe",
            "https://api.github.com/repos/o/r/releases/latest",
            "https://api.github.com/repos/o/r/releases/assets/abc",
            "https://api.github.com/repos/o/r/releases/assets/1/",
            "https://api.github.com/repos/o/r/releases/assets/1?x=1",
            "https://api.github.com.example.test/repos/o/r/releases/assets/1",
            "https://example.test/https://api.github.com/repos/o/r/releases/assets/1",
            "https://user@api.github.com/repos/o/r/releases/assets/1",
            good + "\nHost: example.test",
            good + "\n",
            good + " ",
            "https://api.github.com/repos/o/r/releases/assets/",
            "https://api.github.com/repos/o/r/releases/assets/1#x",
            "https://api.github.com/repos/o/r/extra/releases/assets/1",
            "https://api.github.com/repos/o r/x/releases/assets/1",
            "https://api.github.com/repos/o/r/releases/assets/1/../2",
            "https://api.github.com/repos/../r/releases/assets/1",
            "https://api.github.com/repos/o/../releases/assets/1",
            "https://api.github.com/repos/./r/releases/assets/1",
            "https://api.github.com/repos/o/./releases/assets/1",
            "https://api.github.com/repos/o%2Fx/r/releases/assets/1",
            # a host that a looser pattern would let through (a prefix before github.com, unescaped dots, a port)
            "https://uploads.github.com/repos/o/r/releases/assets/1",
            "https://evilgithub.com/repos/o/r/releases/assets/1",
            "https://apiXgithubXcom/repos/o/r/releases/assets/1",
            "https://api.githubXcom/repos/o/r/releases/assets/1",
            "https://apiXgithub.com/repos/o/r/releases/assets/1",
            "https://api.github.com:8443/repos/o/r/releases/assets/1",
            "https://API.github.com/repos/o/r/releases/assets/1",
            "https://api.github.com./repos/o/r/releases/assets/1",
        ]
        self.assertEqual(newest_release.parse_asset_url(good), ("o", "r", 1))
        for url in bad:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    newest_release.parse_asset_url(url)
                with mock.patch.object(newest_release, "fetch_json") as fetch, \
                        mock.patch.object(newest_release, "open_request") as opened:
                    env = {} if url is None else {"github_asset_api_url": url}
                    with self.assertRaises(ProcessorError):
                        run_processor(GUARD, env)
                fetch.assert_not_called()
                opened.assert_not_called()

    def test_the_names_that_the_download_url_gives(self):
        self.assertEqual(
            newest_release.names_from_download_url("https://github.com/o/r/releases/download/v1%2B2/app%20setup.exe"),
            ("v1+2", "app setup.exe"),
        )
        for url in (None, "", 5, "https://example.test/o/r/releases/download/v1/app.exe",
                    "https://github.com/o/r/releases/download/v1/app.exe/extra",
                    "https://github.com/o/r/releases/latest"):
            self.assertEqual(newest_release.names_from_download_url(url), (None, None))


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def page_of(releases):
    return json.dumps(releases).encode()


def http_error(code, reason, **headers):
    message = http.client.HTTPMessage()
    for key, value in headers.items():
        message[key.replace("_", "-")] = str(value)
    # A real answer has a body. Without one, closing the error raised a KeyError on Python 3.9.
    return urllib.error.HTTPError("https://api.github.com/x", code, reason, message, io.BytesIO(b'{"message": "x"}'))


class RequestTests(unittest.TestCase):
    """fetch_releases() with open_request() replaced."""

    def fetch(self, **kwargs):
        with mock.patch.object(newest_release, "open_request", **kwargs) as opened:
            try:
                return newest_release.fetch_releases(OWNER, REPO, 1)
            finally:
                self.opened = opened

    def test_the_address_is_the_release_list_of_the_repository_on_the_fixed_host(self):
        self.fetch(return_value=FakeResponse(page_of([])))
        request = self.opened.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.github.com/repos/example-owner/example-app/releases?per_page=30&page=1")
        with mock.patch.object(newest_release, "open_request", return_value=FakeResponse(page_of([]))) as opened:
            newest_release.fetch_releases("a.b", "c_d-e", 3)
        self.assertEqual(opened.call_args.args[0].full_url, "https://api.github.com/repos/a.b/c_d-e/releases?per_page=30&page=3")

    def test_a_whole_run_asks_one_address_and_only_that_one(self):
        releases = [release("v2", ["app-2.exe"]), release("v1", ["app-1.exe"])]
        env = selected_env(releases, "v2", "app-2.exe")
        with mock.patch.object(newest_release, "open_request", return_value=FakeResponse(page_of(releases))) as opened:
            run_processor(GUARD, env)
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(opened.call_args.args[0].full_url, "https://api.github.com/repos/example-owner/example-app/releases?per_page=30&page=1")

    def test_the_request_carries_no_credential_and_names_itself(self):
        self.fetch(return_value=FakeResponse(page_of([])))
        request = self.opened.call_args.args[0]
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(set(headers), {"accept", "user-agent"})
        self.assertEqual(headers["user-agent"], newest_release.USER_AGENT)
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)

    def test_the_processor_reads_no_credential_and_no_environment(self):
        with open(newest_release.__file__.replace(".pyc", ".py"), "r", encoding="utf-8") as handle:
            text = handle.read()
        for word in ("Authorization", "GITHUB_TOKEN", "autopkg_gh_token", "os.environ", "getenv", "get_pref", "import os"):
            self.assertNotIn(word, text)

    def test_the_answer_is_read_up_to_a_limit(self):
        class Recording(FakeResponse):
            sizes = []

            def read(self, size=-1):
                self.sizes.append(size)
                return super().read(size)

        Recording.sizes = []
        self.fetch(return_value=Recording(page_of([])))
        self.assertEqual(Recording.sizes, [newest_release.MAX_RESPONSE_BYTES + 1])

    def test_an_answer_that_is_too_large_is_an_error(self):
        body = b'[{"body": "' + b"x" * newest_release.MAX_RESPONSE_BYTES + b'"}]'
        with self.assertRaises(ProcessorError) as caught:
            self.fetch(return_value=FakeResponse(body))
        self.assertIn("larger than %d bytes" % newest_release.MAX_RESPONSE_BYTES, str(caught.exception))

    def test_the_limit_leaves_room_for_the_largest_page_that_was_seen(self):
        """A page of thirty releases of the first eight repositories was at most 0.83 MB (2026-10-04)."""
        self.assertGreaterEqual(newest_release.MAX_RESPONSE_BYTES, 5 * 830000)

    def test_a_good_answer_is_a_list_of_releases(self):
        releases = [release("v1", ["app-1.exe"])]
        self.assertEqual(self.fetch(return_value=FakeResponse(page_of(releases))), releases)

    def test_a_404_says_that_the_repository_has_none_and_names_it(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch(side_effect=http_error(404, "Not Found"))
        text = str(caught.exception)
        self.assertIn("404", text)
        self.assertIn("the release list of example-owner/example-app", text)
        self.assertIn("does not exist or is not public", text)
        self.assertNotIn("no releases", text)  # a repository without releases answers 200 with an empty list

    def test_a_403_that_is_the_rate_limit_is_said_as_such_with_the_time_it_ends(self):
        reset = 1791200000
        expected = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(reset))
        error = http_error(403, "rate limit exceeded", X_RateLimit_Remaining=0, X_RateLimit_Limit=60, X_RateLimit_Reset=reset)
        with self.assertRaises(ProcessorError) as caught:
            self.fetch(side_effect=error)
        text = str(caught.exception)
        self.assertIn("limit for anonymous requests is used up", text)
        self.assertIn("403", text)
        self.assertIn("sends no credential", text)
        self.assertIn("resets at " + expected, text)
        self.assertIn("again later", text)

    def test_a_429_and_a_retry_after_are_the_rate_limit_too(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch(side_effect=http_error(429, "Too Many Requests", Retry_After=120))
        self.assertIn("limit for anonymous requests is used up", str(caught.exception))
        self.assertIn("wait 120 seconds", str(caught.exception))
        with self.assertRaises(ProcessorError) as caught:
            self.fetch(side_effect=http_error(403, "Forbidden", Retry_After=60))
        self.assertIn("limit for anonymous requests is used up", str(caught.exception))
        with self.assertRaises(ProcessorError) as caught:
            self.fetch(side_effect=http_error(403, "Forbidden", X_RateLimit_Remaining=0))
        self.assertIn("limit for anonymous requests is used up", str(caught.exception))

    def test_a_rate_limit_header_that_makes_no_sense_does_not_break_the_message(self):
        for headers in ({"X_RateLimit_Remaining": 0, "X_RateLimit_Reset": "soon"},
                        {"X_RateLimit_Remaining": 0, "X_RateLimit_Reset": 10 ** 30},
                        {"Retry_After": "later"}):
            with self.subTest(headers=headers):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch(side_effect=http_error(403, "Forbidden", **headers))
                self.assertIn("limit for anonymous requests is used up", str(caught.exception))

    def test_a_403_that_is_not_the_rate_limit_is_a_plain_refusal(self):
        for error in (http_error(403, "Forbidden"), http_error(403, "Forbidden", X_RateLimit_Remaining=7),
                      http_error(429, "Too Many Requests", X_RateLimit_Remaining=7)):
            with self.subTest(code=error.code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch(side_effect=error)
                text = str(caught.exception)
                self.assertIn("GitHub answered %d" % error.code, text)
                self.assertNotIn("limit for anonymous", text)

    def test_an_error_without_headers_is_a_plain_refusal(self):
        error = urllib.error.HTTPError("https://api.github.com/x", 403, "Forbidden", None, io.BytesIO(b"{}"))
        with self.assertRaises(ProcessorError) as caught:
            self.fetch(side_effect=error)
        self.assertIn("GitHub answered 403 Forbidden", str(caught.exception))

    def test_another_status_is_an_error_that_names_it(self):
        for code, reason in ((500, "Internal Server Error"), (502, "Bad Gateway"), (401, "Unauthorized"), (301, "Moved")):
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch(side_effect=http_error(code, reason))
                text = str(caught.exception)
                self.assertIn("GitHub answered %d %s" % (code, reason), text)
                self.assertEqual("redirect" in text, code == 301)

    def test_a_network_error_is_an_error(self):
        errors = [
            urllib.error.URLError("no route"), TimeoutError("timed out"), ConnectionResetError("reset"),
            http.client.InvalidURL("bad url"), http.client.IncompleteRead(b"par", 10),
            http.client.BadStatusLine("junk"), http.client.RemoteDisconnected("closed"), ValueError("embedded null"),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch(side_effect=error)
                self.assertIn("could not be fetched", str(caught.exception))

    def test_a_failure_while_the_answer_is_read_is_an_error(self):
        class Broken(FakeResponse):
            def read(self, size=-1):
                raise http.client.IncompleteRead(b"par", 10)

        with self.assertRaises(ProcessorError):
            self.fetch(return_value=Broken(b""))

    def test_an_answer_that_is_not_json_is_an_error(self):
        for body in (b"<html>", b"", b"\xff\xfe", b'{"a": '):
            with self.subTest(body=body):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch(return_value=FakeResponse(body))
                self.assertIn("not JSON", str(caught.exception))

    def test_an_answer_that_is_not_utf8_is_an_error_even_if_latin1_would_read_it(self):
        with self.assertRaises(ProcessorError):
            self.fetch(return_value=FakeResponse(b'[{"name": "\xe9"}]'))

    def test_the_time_limit_is_thirty_seconds_and_is_used(self):
        self.assertEqual(newest_release.FETCH_TIMEOUT_SECONDS, 30)
        opener = mock.Mock()
        opener.open.return_value = FakeResponse(page_of([]))
        with mock.patch.object(newest_release.urllib.request, "build_opener", return_value=opener) as build:
            newest_release.fetch_releases(OWNER, REPO, 1)
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 30)
        self.assertTrue(any(issubclass(handler, newest_release.NoRedirect) for handler in build.call_args.args))

    def test_a_processor_run_with_the_real_fetch_stops_on_a_failed_request(self):
        releases = [release("v1", ["app-1.exe"])]
        with mock.patch.object(newest_release, "open_request", side_effect=http_error(500, "Server Error")):
            with self.assertRaises(ProcessorError) as caught:
                run_processor(GUARD, selected_env(releases, "v1", "app-1.exe"))
        self.assertIn("500", str(caught.exception))


class RedirectTests(unittest.TestCase):
    """A local server on the loopback address (no network). A redirect is an
    error and the second address is never asked."""

    def setUp(self):
        asked = self.asked = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                asked.append(self.path)
                if self.path.startswith("/code"):
                    self.send_response(int(self.path[len("/code"):]))
                    self.send_header("Location", "/elsewhere")
                    self.end_headers()
                elif self.path == "/plain":
                    body = b"[]"
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"[]")

            def log_message(self, *args):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def test_every_kind_of_redirect_is_an_error_that_names_the_status(self):
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                del self.asked[:]
                with self.assertRaises(ProcessorError) as caught:
                    newest_release.fetch_json("http://127.0.0.1:%d/code%d" % (self.port, code), "the list")
                self.assertIn(str(code), str(caught.exception))
                self.assertIn("redirect is not followed", str(caught.exception))
                self.assertEqual(self.asked, ["/code%d" % code])

    def test_a_plain_answer_is_read(self):
        self.assertEqual(newest_release.fetch_json("http://127.0.0.1:%d/plain" % self.port, "the list"), [])
        self.assertEqual(newest_release.fetch_json("http://127.0.0.1:%d/other" % self.port, "the list"), [])


class DeclarationTests(unittest.TestCase):
    def test_the_declaration(self):
        variables = GUARD.input_variables
        self.assertTrue(variables["github_asset_api_url"]["required"])
        for name in ("include_prereleases", "accepted_newest_release", "release_tag_pattern", "sort_by_highest_tag_names",
                     "latest_only", "url"):
            self.assertFalse(variables[name].get("required"), name)
        self.assertEqual(set(variables), {"github_asset_api_url", "include_prereleases", "accepted_newest_release",
                                          "release_tag_pattern", "sort_by_highest_tag_names", "latest_only", "url"})
        for name, flags in variables.items():  # AutoPkg reads flags["required"] of every input
            self.assertIn("required", flags, name)
        self.assertEqual(set(GUARD.output_variables), {newest_release.SUMMARY_KEY})
        self.assertIs(GUARD.description, newest_release.__doc__)

    def test_the_module_names_what_it_offers(self):
        for name in newest_release.__all__:
            self.assertTrue(hasattr(newest_release, name), name)
        self.assertEqual(GUARD.__name__, "GitHubNewestReleaseGuard")


class MoreMessageTests(unittest.TestCase):
    def test_the_message_for_a_newest_release_that_pre_releases_may_be(self):
        newest = release("v3-beta", ["a.exe"], prerelease=True)
        text = newest_release.stop_message(OWNER, REPO, True, newest, [newest], 1, None)
        self.assertIn("is not the newest release. ", text)
        text = newest_release.stop_message(OWNER, REPO, False, newest, [newest], 1, None)
        self.assertIn("is not the newest release that is not a pre-release. ", text)

    def test_a_release_label_without_a_tag_is_still_text(self):
        self.assertEqual(newest_release.release_label({}), "'?'")

    def test_the_rate_limit_text_is_none_for_other_answers(self):
        headers = http.client.HTTPMessage()
        self.assertIsNone(newest_release.rate_limit_message(404, headers))
        self.assertIsNone(newest_release.rate_limit_message(403, headers))
        self.assertIsNone(newest_release.rate_limit_message(403, None))


if __name__ == "__main__":
    unittest.main()
