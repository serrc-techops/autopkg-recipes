"""Tests of the two Slack recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. The step that names our shared
processor is compared with what that processor declares (see
../../Win-SharedProcessors). The shared folder's tests are run separately.

The download of this program has NO hard check (no vendor hash, no signature
check). The tests make sure that nobody can overlook that: the Description of
both recipes and the top of the README say it, and no recipe invents a check.

Nothing of this folder was rehearsed, and the writer could not fetch the vendor's
pages: the README's first paragraph says so, and a test checks it.
"""
import http.server
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
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
DOWNLOAD = os.path.join(RECIPE_DIR, "Slack-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "Slack.cimian.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
# Processors that are part of AutoPkg itself.
CORE_PROCESSORS = ("URLTextSearcher", "URLDownloader", "EndOfCheckPhase")
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
    "Slack.download", "Slack.munki",
)
CURL = shutil.which("curl")
# What the recipe asks of curl for the download: no redirect to anything but https.
CURL_OPTS = ["--proto-redir", "=https"]
SEARCHED_PAGE = "https://slack.com/release-notes/windows"
FILE_ADDRESS = ("https://downloads.slack-edge.com/desktop-releases/windows/x64/"
                "%version%/slack-standalone-%version%.0.msi")


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
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.Slack-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.Slack")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, ["URLTextSearcher", "URLDownloader", "EndOfCheckPhase"])

    def test_the_cimian_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "PcmanImporter"])

    def test_the_searcher_reads_the_release_notes_page_with_the_pattern_of_the_input(self):
        recipe = load(DOWNLOAD)
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"url": "%RELEASE_NOTES_URL%", "re_pattern": "%VERSION_PATTERN%"})
        self.assertEqual(recipe["Input"]["RELEASE_NOTES_URL"], SEARCHED_PAGE)
        self.assertTrue(recipe["Input"]["RELEASE_NOTES_URL"].startswith("https://"))

    def test_the_downloader_takes_the_version_from_the_searcher_in_the_address(self):
        recipe = load(DOWNLOAD)
        args = recipe["Process"][1]["Arguments"]
        self.assertEqual(args, {"url": FILE_ADDRESS, "curl_opts": CURL_OPTS})
        self.assertEqual(args["url"].count("%version%"), 2)
        # no variable of the Input inside another: AutoPkg is not asked to substitute twice
        for value in recipe["Input"].values():
            self.assertNotIn("%", value)

    def test_the_downloader_refuses_a_redirect_that_leads_to_anything_but_https(self):
        """`URLDownloader` of AutoPkg 2.9.0 declares `curl_opts`, an array, and adds each item of it to
        the download's curl command as one argument (`URLGetter.add_curl_common_opts`), so the option
        and its value are two items of the list."""
        args = load(DOWNLOAD)["Process"][1]["Arguments"]
        self.assertEqual(args["curl_opts"], ["--proto-redir", "=https"])
        for item in args["curl_opts"]:
            self.assertIsInstance(item, str)
        self.assertTrue(args["url"].startswith("https://"))
        # the page that gives the version is not covered: its text only chooses the address
        self.assertNotIn("curl_opts", load(DOWNLOAD)["Process"][0]["Arguments"])

    def test_the_file_name_in_the_address_ends_in_msi_and_has_no_query_string(self):
        """URLDownloader names the file after the last part of the address: it must end in .msi."""
        url = load(DOWNLOAD)["Process"][1]["Arguments"]["url"]
        self.assertNotIn("?", url)
        self.assertNotIn("#", url)
        self.assertTrue(url.rsplit("/", 1)[1].endswith(".msi"))
        self.assertNotIn("filename", load(DOWNLOAD)["Process"][1]["Arguments"])

    def test_the_address_asks_for_the_64_bit_per_machine_installer(self):
        url = load(DOWNLOAD)["Process"][1]["Arguments"]["url"]
        self.assertIn("/windows/x64/", url)
        self.assertIn("slack-standalone-", url)
        self.assertNotIn(".msix", url)
        self.assertTrue(url.startswith("https://downloads.slack-edge.com/"))


class VersionPatternTests(unittest.TestCase):
    """The pattern that reads the version from the release notes page. The page
    excerpts here are written by hand, not saved from the real page."""

    def pattern(self):
        return re.compile(load(DOWNLOAD)["Input"]["VERSION_PATTERN"])

    def test_it_matches_the_name_and_a_three_part_version_and_outputs_the_group_version(self):
        match = self.pattern().search("Slack 4.41.105")
        self.assertIsNotNone(match)
        self.assertEqual(match.groupdict(), {"version": "4.41.105"})

    def test_it_does_not_match_a_two_part_version(self):
        self.assertIsNone(self.pattern().search("Slack 4.41"))
        self.assertIsNone(self.pattern().search("Slack 4"))
        self.assertIsNone(self.pattern().search("Slack"))

    def test_it_needs_the_word_slack_before_the_version(self):
        self.assertIsNone(self.pattern().search("Release 4.41.105"))

    def test_the_first_match_of_a_page_with_two_releases_is_the_first_one_on_the_page(self):
        page = "<h2>Slack 4.41.105</h2><p>Fixes.</p><h2>Slack 4.40.128</h2><p>Fixes.</p>"
        self.assertEqual(self.pattern().search(page).group("version"), "4.41.105")

    def test_the_pattern_names_exactly_one_group_and_it_is_version(self):
        self.assertEqual(list(self.pattern().groupindex), ["version"])
        self.assertEqual(self.pattern().groups, 1)

    def test_the_version_in_the_address_is_the_one_that_the_group_gives(self):
        version = self.pattern().search("Slack 4.41.105").group("version")
        url = FILE_ADDRESS.replace("%version%", version)
        self.assertEqual(url, "https://downloads.slack-edge.com/desktop-releases/windows/x64/4.41.105/slack-standalone-4.41.105.0.msi")


class RecipeContentTests(unittest.TestCase):

    def test_the_download_recipe_has_no_parent_and_says_what_was_not_fetched(self):
        text = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        self.assertNotIn("ParentRecipe", read(DOWNLOAD))
        self.assertIn("were NOT fetched by the writer and this recipe was NOT rehearsed", text)
        self.assertIn("the first run on the build machine is the check of them", text)

    def test_no_description_claims_a_rehearsal(self):
        for path in (DOWNLOAD, CIMIAN):
            text = load(path)["Description"]
            self.assertNotIn("Rehearsed", text)
            self.assertNotIn("rehearsed on", text)

    def test_the_inputs_of_the_cimian_recipe(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], "Slack")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "slack")
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%"})

    def test_no_file_name_of_ours_is_the_name_of_a_recipe_in_another_repository(self):
        ours = [name[: -len(".recipe")].casefold() for name in (os.path.basename(DOWNLOAD), os.path.basename(CIMIAN))]
        for other in NAMES_OF_OTHER_REPOSITORIES:
            self.assertNotIn(other.casefold(), ours)
        for name in ours:
            self.assertNotIn(name, [other.casefold() for other in NAMES_OF_OTHER_REPOSITORIES])

    def test_the_template_keeps_the_name_of_the_item_it_replaces(self):
        self.assertEqual(load(CIMIAN)["Input"]["PCMAN_TEMPLATE"], "slack")

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
                if value == recipe["Input"].get("VERSION_PATTERN"):
                    continue  # a regular expression: its backslashes are not a path
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

    def test_the_readme_opens_with_a_status_line_and_a_not_verified_line_both_bold(self):
        lines = [line for line in read(README).splitlines() if line.strip()]
        self.assertTrue(lines[0].startswith("# "))
        self.assertTrue(lines[1].startswith("A Windows recipe pair"))
        status, not_verified = lines[2], lines[3]
        self.assertTrue(status.startswith("**Status. NOT rehearsed, and the facts of the source NOT fetched by the writer:"),
                        status[:80])
        self.assertTrue(status.endswith("**"))
        self.assertTrue(not_verified.startswith("**Not verified. The download is NOT verified:"), not_verified[:60])
        self.assertTrue(not_verified.endswith("**"))
        for needle in ("signature check", "REFUSES a real run", "pcman_allow_unverified",
                       "Do not set it before the signature check exists",
                       "pcman import <file> --template slack", "no `--version` for an MSI",
                       "has NOT been run by anyone"):
            self.assertIn(needle, not_verified)

    def test_the_status_line_says_what_was_not_done(self):
        status = [line for line in read(README).splitlines() if line.startswith("**Status.")][0]
        text = re.sub(r"\s+", " ", status)
        for needle in (
                "the writer had no network and read neither Slack's pages nor its download server",
                "Nothing in this folder has run with AutoPkg",
                "https://slack.com/release-notes/windows",
                "taken from the Cimian authors' own recipe for Slack",
                "the FIRST match on that page is the newest release",
                "may also be built by script",
                "outputs a named group of the pattern under its own name, here `version`",
                "https://downloads.slack-edge.com/desktop-releases/windows/x64/<version>/slack-standalone-<version>.0.msi",
                "Slack.msix", "does not take an MSIX",
                "The first run on the build Mac is the check of every one of them",
                "When it fails, stop: nothing was written",
                "correct the recipe, never the trust information first"):
            self.assertIn(needle, text)
        self.assertNotIn("Rehearsed on", read(README))
        # the pattern in the status line is the one in the recipe
        self.assertIn(load(DOWNLOAD)["Input"]["VERSION_PATTERN"], status)

    def test_the_readme_says_what_still_protects_and_that_it_is_not_enough(self):
        text = re.sub(r"\s+", " ", read(README))
        self.assertIn("The same product", text)
        self.assertIn("refuses an MSI whose upgrade code differs from the template's", text)
        self.assertIn("refuses a label that is not the MSI's own version", text)
        self.assertIn("They do not replace a verification", text)
        self.assertIn("a real run is refused before the package tool starts", text)

    def test_the_readme_says_that_there_is_no_hash_source_and_that_a_redirect_to_plain_http_is_refused(self):
        text = re.sub(r"\s+", " ", read(README))
        section = text[text.index("**No hash source.**"):text.index("## Run every override")]
        for needle in ("Slack publishes no hash for the file", "the recipe has no other source for one",
                       "TLS to the vendor's host", "refuses a redirect that leads to anything but https",
                       "`--proto-redir` `=https`", "plain HTTP", "stops the run with curl's error",
                       "nothing is written", "is not checked against anything",
                       "The page that gives the version is fetched without the rule",
                       "`URLDownloader` of AutoPkg 2.9.0 declares `curl_opts`",
                       "`prepare_download_curl_cmd`", "ignores an argument that it does not know"):
            self.assertIn(needle, section)
        self.assertNotIn("processor-info", text)
        self.assertLess(text.index("## What protects, and what does not"), text.index("**No hash source.**"))

    def test_the_readme_says_that_nothing_compares_the_msis_version_with_the_pages_and_what_to_read(self):
        text = re.sub(r"\s+", " ", read(README))
        section = text[text.index("**The page's version and the MSI's own version.**"):text.index("## Run every override")]
        for needle in ("Nothing compares them", "only chooses the address",
                       "`URLTextSearcher: Found matching text (version): ...`", "in its Version column",
                       "the MSI's own ProductVersion", "at the first dry run", "Compare their numbers",
                       "stop and tell the owner", "does not repeat the comparison at later runs"):
            self.assertIn(needle, section)
        step = read(README)[read(README).index("## c."):read(README).index("## d.")]
        self.assertIn("autopkg run -v --override-dir=", step)
        self.assertIn("`-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the repository among them, "
                      "and such a log would have to be kept private", re.sub(r"\s+", " ", step))

    def test_the_real_run_step_says_not_yet(self):
        text = read(README)
        self.assertIn("## d. Switch a real run on (NOT YET: see the second paragraph at the top)", text)
        self.assertLess(text.index("**Status."), text.index("**Not verified."))
        self.assertLess(text.index("**Not verified."), text.index("## a."))

    def test_the_hand_command_uses_the_template_and_no_version(self):
        """S2: after the template exists, `pcman import` without --template would make a second item."""
        text = read(README)
        self.assertNotIn("with the same command", text)
        match = re.search(r"\n    (pcman import <the file> --template slack[^\n]*)\n", text)
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


@unittest.skipUnless(CURL, "curl is not installed")
class RedirectRefusalTests(unittest.TestCase):
    """The curl command that `URLDownloader` of AutoPkg 2.9.0 builds (`prepare_base_curl_cmd`, then
    `--fail --output <file>` and the `curl_opts`, in `prepare_download_curl_cmd`), run with the
    recipe's own `curl_opts` against a server of this machine that redirects to plain HTTP. (Only
    the redirect is restricted, so a server without TLS can be used for the first request.)"""

    def setUp(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(handler):
                if handler.path == "/redirect":
                    handler.send_response(302)
                    handler.send_header("Location", "http://127.0.0.1:%d/file.msi" % handler.server.server_address[1])
                    handler.end_headers()
                else:
                    body = b"not a real installer"
                    handler.send_response(200)
                    handler.send_header("Content-Length", str(len(body)))
                    handler.end_headers()
                    handler.wfile.write(body)

            def log_message(handler, *args):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self._tmp = tempfile.TemporaryDirectory(prefix="slack-redirect-")
        self.addCleanup(self._tmp.cleanup)
        self.output = os.path.join(self._tmp.name, "download.tmp")

    def download(self, path, options):
        command = [CURL, "--silent", "--show-error", "--no-buffer", "--dump-header", "-", "--speed-time", "30",
                   "--location", "--url", "http://127.0.0.1:%d%s" % (self.port, path), "--fail",
                   "--output", self.output] + list(options)
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        size = os.path.getsize(self.output) if os.path.exists(self.output) else None
        return result, size

    def test_without_the_option_curl_follows_a_redirect_to_plain_http(self):
        result, size = self.download("/redirect", [])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(size, len(b"not a real installer"))

    def test_with_the_options_of_the_recipe_a_redirect_to_plain_http_is_refused_and_nothing_is_written(self):
        options = load(DOWNLOAD)["Process"][1]["Arguments"]["curl_opts"]
        result, size = self.download("/redirect", options)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(size)
        self.assertIn("http", result.stderr.lower())

    def test_the_options_do_not_restrict_the_first_request(self):
        options = load(DOWNLOAD)["Process"][1]["Arguments"]["curl_opts"]
        result, size = self.download("/file.msi", options)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(size, len(b"not a real installer"))


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
        """URLTextSearcher needs `url` and `re_pattern`, URLDownloader needs `url`; the recipe passes them."""
        self.assertIn("url", load(DOWNLOAD)["Process"][0]["Arguments"])
        self.assertIn("re_pattern", load(DOWNLOAD)["Process"][0]["Arguments"])
        self.assertIn("url", load(DOWNLOAD)["Process"][1]["Arguments"])


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
            "Slack-Win.download.recipe", "Slack.cimian.recipe", "README.md",
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
                    r"^autopkg (run|verify-trust-info|update-trust-info)( -vv?)? "
                    r"--override-dir=<the Windows overrides folder> "
                    r"<the Windows overrides folder>/Slack\.cimian\.recipe$",
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
        for needle in ("pcman catalogs", "pcman versions slack", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string", "make-override"):
            self.assertIn(needle, self.text)

    def test_the_name_check_comes_before_the_override_and_the_parent_is_read_after_it(self):
        text = read(README)
        check = text.index("autopkg list-recipes | grep -i Slack-Win")
        override = text.index("    autopkg make-override --override-dir=")
        self.assertLess(check, override)
        self.assertIn("First check that no other recipe has the same name.", text)
        self.assertIn("Each name must be listed once, from this repository.", text)
        self.assertIn("autopkg list-recipes | grep -i Slack.cimian", text)
        self.assertIn("read\n`ParentRecipe`", text)
        step = re.sub(r"\s+", " ", text[override:])
        self.assertIn(
            "**Open the written file and read `ParentRecipe`: it must be "
            "`com.github.serrc-techops.download.Slack-Win`.**",
            step,
        )
        self.assertIn("com.github.serrc-techops.download.Slack-Win", text[override:])

    def test_the_readme_states_no_hash(self):
        """S7: a README that states a SHA-256 (64 hex digits) could be taken for a check."""
        self.assertIsNone(HEX_64.search(self.raw))

    def test_the_first_import_has_no_version_and_keeps_the_template_name(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        self.assertTrue(match)
        command = re.sub(r"\s+", " ", match.group(1))
        self.assertIn("--name slack", command)
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
        self.assertIn("`pcman catalogs` was NOT run either", self.text)
        self.assertIn("carries `--override-dir`", self.text)
        self.assertIn("A real run of this recipe has NOT been run by anyone, not against a share and not on a PC, "
                      "and neither has a dry run", self.text)
        self.assertIn("they were NOT seen for this recipe", self.text)

    def test_the_readme_tells_what_to_read_when_the_pattern_or_the_address_fails(self):
        self.assertIn("If the pattern finds nothing", self.text)
        self.assertIn("If the address of the file answers", self.text)
        self.assertIn("It\nis not passed to the package tool", self.raw)


if __name__ == "__main__":
    unittest.main()
