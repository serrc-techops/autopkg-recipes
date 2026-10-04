"""Tests of MozillaFirefoxInfoProvider: every branch. No test uses the network:
fetch_text() or open_request() is replaced.

THE EXCERPTS ARE WRITTEN BY HAND. firefox_versions_excerpt.json and
sha256sums_excerpt.txt were written by hand after the real files of 2026-10-02,
not saved from the real servers. Their digits are made up, and the version
numbers are not the real ones of that day. A test that reads them is still a real test of the
parser, but it proves nothing about what Mozilla's servers answer today: the
first run on the build Mac is that check.
"""
import io
import json
import os
import re
import sys
import unittest
import urllib.error
from unittest import mock

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.dirname(TESTS_DIR)
SHARED_TESTS_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-SharedProcessors", "tests")
for folder in (SHARED_TESTS_DIR, RECIPE_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

from _win_support import ProcessorError, new_processor, run_processor  # noqa: E402  (installs the autopkglib stand-in)

import MozillaFirefoxInfoProvider as provider  # noqa: E402

PROVIDER = provider.MozillaFirefoxInfoProvider
VERSIONS_EXCERPT = os.path.join(TESTS_DIR, "firefox_versions_excerpt.json")
SUMS_EXCERPT = os.path.join(TESTS_DIR, "sha256sums_excerpt.txt")
HAND_WRITTEN_NOTE = "written by hand after the real files of 2026-10-02, with made-up digits"
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
# Texts that the hygiene test would read as an address or a network path if they
# stood in this file as they are. They are built here.
FOUR_NUMBERS = ".".join(["141", "0", "1", "2"])
BACKSLASH_PATH = "a" + chr(92) + "b"
RELEASE_BASE = "https://download-installer.cdn.mozilla.net/pub/firefox/releases/"


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def sums_line(path, sha256=HEX_A):
    return "%s  %s\n" % (sha256, path)


def versions_text(release="141.0", esr="128.13.0esr", **extra):
    data = {"LATEST_FIREFOX_VERSION": release, "FIREFOX_ESR": esr, "FIREFOX_DEVEDITION": "142.0b4"}
    data.update(extra)
    return json.dumps(data)


def fetcher(versions, sums, record=None):
    """A stand-in for fetch_text that answers by address and writes down what was asked."""
    def fetch(url, max_bytes, what):
        if record is not None:
            record.append((url, max_bytes, what))
        if url == provider.VERSIONS_URL:
            return versions
        if url.endswith("/SHA256SUMS"):
            return sums
        raise AssertionError("an address that nobody expected: %s" % url)
    return fetch


def run_on(versions, sums, env=None, record=None):
    """Run the processor on two texts. Returns (processor, messages)."""
    with mock.patch.object(provider, "fetch_text", side_effect=fetcher(versions, sums, record)):
        return run_processor(PROVIDER, env or {})


def fails_on(versions, sums, env=None):
    """Run the processor, expect a ProcessorError, return it and the processor."""
    processor, _ = new_processor(PROVIDER, env or {})
    with mock.patch.object(provider, "fetch_text", side_effect=fetcher(versions, sums)):
        try:
            processor.main()
        except ProcessorError as err:
            return err, processor
    raise AssertionError("the processor did not stop")


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ExcerptTests(unittest.TestCase):
    """The two hand-written excerpts (see the note at the top of this file)."""

    def setUp(self):
        self.versions = read(VERSIONS_EXCERPT)
        self.sums = read(SUMS_EXCERPT)

    def test_the_excerpts_say_that_they_are_written_by_hand(self):
        self.assertEqual(json.loads(self.versions)["_written_by_hand"], HAND_WRITTEN_NOTE)
        self.assertIn("WRITTEN BY HAND", read(__file__))
        self.assertIn("after the real files of 2026-10-02", read(__file__))

    def test_the_excerpts_are_small(self):
        self.assertLess(len(self.versions), 4000)
        self.assertLess(len(self.sums), 4000)

    def test_the_release_channel(self):
        processor, _ = run_on(self.versions, self.sums)
        self.assertEqual(processor.env["version"], "141.0")
        self.assertEqual(
            processor.env["url"],
            RELEASE_BASE + "141.0/win64/en-US/Firefox%20Setup%20141.0.exe",
        )
        expected = [line.split("  ")[0] for line in self.sums.split("\n")
                    if line.endswith("  win64/en-US/Firefox Setup 141.0.exe")]
        self.assertEqual(len(expected), 1)
        self.assertEqual(processor.env["expected_sha256"], expected[0])
        self.assertRegex(processor.env["expected_sha256"], r"^[0-9a-f]{64}$")

    def test_the_hash_is_the_hash_of_the_line_of_the_inputs_and_of_no_other(self):
        seen = set()
        for platform, locale in (("win64", "en-US"), ("win64", "de"), ("win32", "en-US"),
                                 ("win64-aarch64", "en-US")):
            processor, _ = run_on(self.versions, self.sums,
                                  {"firefox_platform": platform, "firefox_locale": locale})
            seen.add(processor.env["expected_sha256"])
            self.assertIn("/%s/%s/" % (platform, locale), processor.env["url"])
        self.assertEqual(len(seen), 4)

    def test_a_locale_that_is_not_in_the_file_is_an_error(self):
        error, _ = fails_on(self.versions, self.sums, {"firefox_locale": "fr"})
        self.assertIn("no line for win64/fr/Firefox Setup 141.0.exe", str(error))

    def test_the_esr_channel_takes_the_esr_key_and_leaves_the_suffix_out_of_the_label(self):
        text = self.sums.replace("141.0", "128.13.0esr")
        processor, _ = run_on(self.versions, text, {"firefox_channel": "esr"})
        self.assertEqual(processor.env["version"], "128.13.0")
        self.assertEqual(
            processor.env["url"],
            RELEASE_BASE + "128.13.0esr/win64/en-US/Firefox%20Setup%20128.13.0esr.exe",
        )

    def test_the_two_requests_are_the_fixed_addresses_with_their_limits(self):
        record = []
        run_on(self.versions, self.sums, record=record)
        self.assertEqual([item[0] for item in record], [
            "https://product-details.mozilla.org/1.0/firefox_versions.json",
            RELEASE_BASE + "141.0/SHA256SUMS",
        ])
        self.assertEqual([item[1] for item in record], [provider.MAX_VERSIONS_BYTES, provider.MAX_SUMS_BYTES])


class ParseVersionTests(unittest.TestCase):
    def test_a_release_version_is_two_or_three_numbers(self):
        self.assertEqual(provider.parse_version("141.0", "release"), ("141.0", "141.0"))
        self.assertEqual(provider.parse_version("141.0.1", "release"), ("141.0.1", "141.0.1"))
        self.assertEqual(provider.parse_version("99.10.100", "release"), ("99.10.100", "99.10.100"))

    def test_the_esr_version_may_have_the_suffix_and_the_label_has_not(self):
        self.assertEqual(provider.parse_version("128.13.0esr", "esr"), ("128.13.0esr", "128.13.0"))
        self.assertEqual(provider.parse_version("128.13.0", "esr"), ("128.13.0", "128.13.0"))
        self.assertEqual(provider.parse_version("140.1esr", "esr"), ("140.1esr", "140.1"))

    def test_anything_else_is_not_a_version(self):
        for value in ("", "141", "141.0b4", "143.0a1", "141.0esr", "v141.0", FOUR_NUMBERS, "141.0 ", " 141.0",
                      "141.0\n", "141.0/../x", "141.0%20", "١٤١.٠", "141.x", "141..0", "..", "esr", None, 141.0,
                      ["141.0"], {"a": 1}):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    provider.parse_version(value, "release")

    def test_a_release_with_the_esr_suffix_is_refused_and_so_is_other_text_for_esr(self):
        for value in ("141.0 esr", "esr141.0", "128.13.0ESR", "128.13.0esr2", "128.13.0-esr", "128.13.0b1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    provider.parse_version(value, "esr")
        with self.assertRaises(ValueError):
            provider.parse_version("141.0esr", "release")


class InstallerAddressTests(unittest.TestCase):
    def test_the_name_has_spaces_and_the_address_has_percent_20(self):
        self.assertEqual(provider.installer_name("141.0"), "Firefox Setup 141.0.exe")
        url = provider.installer_url("141.0.1", "win64", "en-US")
        self.assertEqual(url, RELEASE_BASE + "141.0.1/win64/en-US/Firefox%20Setup%20141.0.1.exe")
        self.assertNotIn(" ", url)

    def test_the_address_and_the_looked_up_path_are_the_same_file(self):
        import urllib.parse
        url = provider.installer_url("141.0", "win64", "de")
        relative = urllib.parse.unquote(url[len(RELEASE_BASE):])
        self.assertEqual(relative, "141.0/win64/de/Firefox Setup 141.0.exe")

    def test_the_address_passes_the_host_check(self):
        provider.check_address(provider.installer_url("141.0", "win64", "en-US"))
        provider.check_address(provider.VERSIONS_URL)
        provider.check_address(RELEASE_BASE + "141.0/SHA256SUMS")


class CheckAddressTests(unittest.TestCase):
    def test_only_the_two_hosts_over_https_are_allowed(self):
        for url in (
            "http://product-details.mozilla.org/1.0/firefox_versions.json",
            "https://example.test/1.0/firefox_versions.json",
            "https://download.mozilla.org/x",
            "https://product-details.mozilla.org.example.test/x",
            "https://example.test/https://product-details.mozilla.org/",
            "https://user@product-details.mozilla.org/x",
            "https://user:pw@product-details.mozilla.org/x",
            "https://product-details.mozilla.org:8443/x",
            "https://product-details.mozilla.org/x#frag",
            "ftp://product-details.mozilla.org/x",
            "file:///etc/passwd",
            "",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    provider.check_address(url)

    def test_the_constants_are_the_vendors_addresses_over_https(self):
        self.assertEqual(provider.VERSIONS_URL, "https://product-details.mozilla.org/1.0/firefox_versions.json")
        self.assertEqual(provider.RELEASES_BASE_URL, RELEASE_BASE)
        self.assertEqual(sorted(provider.ALLOWED_HOSTS),
                         ["download-installer.cdn.mozilla.net", "product-details.mozilla.org"])
        self.assertTrue(provider.RELEASES_BASE_URL.endswith("/"))
        for url in (provider.VERSIONS_URL, provider.RELEASES_BASE_URL):
            provider.check_address(url)


class Sha256OfTests(unittest.TestCase):
    PATH = "win64/en-US/Firefox Setup 141.0.exe"

    def test_the_one_line_of_the_path_is_taken_and_its_hash_is_lower_case(self):
        text = sums_line("win32/en-US/Firefox Setup 141.0.exe", HEX_B) + sums_line(self.PATH, HEX_A.upper())
        self.assertEqual(provider.sha256_of(text, self.PATH), HEX_A)

    def test_the_path_must_match_exactly(self):
        for other in (
            "win64/en-US/Firefox Setup 141.0.exe.sig", "xwin64/en-US/Firefox Setup 141.0.exe",
            "win64/en-US/Firefox Setup 141.0.exe ", "win64/en-US/firefox setup 141.0.exe",
            "win64/en-US/Firefox Setup 141.0.msi", "Win64/en-US/Firefox Setup 141.0.exe",
            "win64/en-US/Firefox Setup 141.0.0.exe", "win64/en-US/Firefox  Setup 141.0.exe",
            "./win64/en-US/Firefox Setup 141.0.exe", "win64//en-US/Firefox Setup 141.0.exe",
        ):
            with self.subTest(other=other):
                text = sums_line(other, HEX_B)
                with self.assertRaises(ValueError) as caught:
                    provider.sha256_of(text, self.PATH)
                self.assertTrue("no line for" in str(caught.exception) or "not a SHA-256" in str(caught.exception))

    def test_no_line_is_an_error_that_names_the_path(self):
        for text in ("", "\n", sums_line("mac/en-US/Firefox 141.0.dmg")):
            with self.subTest(text=text):
                with self.assertRaises(ValueError) as caught:
                    provider.sha256_of(text, self.PATH)
                self.assertIn("no line for " + self.PATH, str(caught.exception))

    def test_two_lines_for_the_path_are_an_error_also_when_they_agree(self):
        for second in (HEX_A, HEX_B):
            text = sums_line(self.PATH, HEX_A) + sums_line("mac/x", HEX_C) + sums_line(self.PATH, second)
            with self.subTest(second=second[:2]):
                with self.assertRaises(ValueError) as caught:
                    provider.sha256_of(text, self.PATH)
                self.assertIn("2 lines for", str(caught.exception))
                self.assertIn("not exactly one", str(caught.exception))

    def test_every_line_is_checked_not_only_ours(self):
        good = sums_line(self.PATH, HEX_A)
        bad_lines = [
            "not a line at all",
            HEX_B + " single/space/path",                         # one space (a name that begins with it)
            HEX_B + " *win32/x.exe",                              # the binary mode of sha256sum
            HEX_B + "   three/spaces",                            # three spaces: the path would start with a space
            HEX_B[:-1] + "  short/hash",
            HEX_B + "0  long/hash",
            "g" * 64 + "  not/hex",
            HEX_B + "  ",                                         # no path
            HEX_B + "  win32/x.exe\r",                            # a carriage return
            HEX_B + "  win32/x\x00.exe",
            HEX_B + "  win32/x\t.exe",
            " " + HEX_B + "  win32/x.exe",
            "sha256:" + HEX_B + "  win32/x.exe",
        ]
        for bad in bad_lines:
            for text in (good + bad + "\n", bad + "\n" + good):
                with self.subTest(bad=bad):
                    with self.assertRaises(ValueError) as caught:
                        provider.sha256_of(text, self.PATH)
                    self.assertIn("is not a SHA-256, two spaces and a path", str(caught.exception))

    def test_the_error_names_the_line_number(self):
        text = sums_line("a/b") + sums_line("c/d") + "oops\n"
        with self.assertRaises(ValueError) as caught:
            provider.sha256_of(text, self.PATH)
        self.assertIn("line 3 ", str(caught.exception))

    def test_empty_lines_and_a_missing_final_line_break_are_fine(self):
        text = "\n" + sums_line(self.PATH, HEX_A) + "\n\n"
        self.assertEqual(provider.sha256_of(text, self.PATH), HEX_A)
        self.assertEqual(provider.sha256_of(HEX_A + "  " + self.PATH, self.PATH), HEX_A)

    def test_a_path_with_spaces_and_unicode_text_is_one_path(self):
        path = "win64/en-US/Firefox Setup 141.0.exe"
        self.assertEqual(provider.sha256_of(sums_line(path, HEX_C) + sums_line("x/é y", HEX_B), path), HEX_C)


class MainTests(unittest.TestCase):
    def good_sums(self, release="141.0", platform="win64", locale="en-US", sha=HEX_A):
        return sums_line("%s/%s/Firefox Setup %s.exe" % (platform, locale, release), sha)

    def test_the_defaults(self):
        processor, messages = run_on(versions_text("141.0.1"), self.good_sums("141.0.1"))
        self.assertEqual(processor.env["version"], "141.0.1")
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertEqual(processor.env["url"], RELEASE_BASE + "141.0.1/win64/en-US/Firefox%20Setup%20141.0.1.exe")
        self.assertTrue(any("141.0.1" in m for m in messages))
        self.assertTrue(any(HEX_A in m for m in messages))

    def test_the_declared_defaults_equal_the_values_the_code_uses(self):
        declared = {name: flags["default"] for name, flags in PROVIDER.input_variables.items()}
        self.assertEqual(declared, {"firefox_channel": "release", "firefox_platform": "win64",
                                    "firefox_locale": "en-US"})
        for flags in PROVIDER.input_variables.values():
            self.assertIs(flags["required"], False)
            self.assertTrue(flags["description"])
        self.assertEqual(sorted(PROVIDER.output_variables), ["expected_sha256", "url", "version"])
        self.assertEqual(provider.CHANNELS, {"release": "LATEST_FIREFOX_VERSION", "esr": "FIREFOX_ESR"})

    def test_the_release_channel_ignores_the_esr_key_and_the_other_way_round(self):
        versions = versions_text("141.0", "128.13.0esr")
        processor, _ = run_on(versions, self.good_sums("141.0"))
        self.assertEqual(processor.env["version"], "141.0")
        processor, _ = run_on(versions, self.good_sums("128.13.0esr"), {"firefox_channel": "esr"})
        self.assertEqual(processor.env["version"], "128.13.0")

    def test_the_esr_without_a_suffix_is_taken_as_it_is_written(self):
        processor, _ = run_on(versions_text(esr="128.13.0"), self.good_sums("128.13.0"), {"firefox_channel": "esr"})
        self.assertEqual(processor.env["url"], RELEASE_BASE + "128.13.0/win64/en-US/Firefox%20Setup%20128.13.0.exe")

    def test_the_inputs_choose_the_line(self):
        sums = self.good_sums(sha=HEX_A) + self.good_sums(locale="de", sha=HEX_B) + \
            self.good_sums(platform="win32", sha=HEX_C)
        for env, expected in (({}, HEX_A), ({"firefox_locale": "de"}, HEX_B), ({"firefox_platform": "win32"}, HEX_C)):
            with self.subTest(env=env):
                processor, _ = run_on(versions_text(), sums, env)
                self.assertEqual(processor.env["expected_sha256"], expected)

    def test_a_channel_that_is_not_release_or_esr_is_an_error_and_nothing_is_fetched(self):
        for value in ("beta", "nightly", "Release", "ESR", " release", "release ", "", None, 5, ["release"],
                      "release\n", "LATEST_FIREFOX_VERSION"):
            processor, _ = new_processor(PROVIDER, {"firefox_channel": value})
            with self.subTest(value=value):
                with mock.patch.object(provider, "fetch_text") as fetch:
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                fetch.assert_not_called()
                self.assertIn("firefox_channel", str(caught.exception))

    def test_a_platform_or_a_locale_that_is_not_a_name_is_an_error_and_nothing_is_fetched(self):
        bad = ("", " ", "win64 ", " en-US", "../x", "a/b", BACKSLASH_PATH, "a.b", "en-US/", "en US", "win64\n", "%2e%2e",
               "a:b", "é", "x;y", "x?y", "x#y", "x@y", 5, ["x"], "\x00")
        for name in ("firefox_platform", "firefox_locale"):
            for value in bad:
                processor, _ = new_processor(PROVIDER, {name: value})
                with self.subTest(name=name, value=value):
                    with mock.patch.object(provider, "fetch_text") as fetch:
                        with self.assertRaises(ProcessorError) as caught:
                            processor.main()
                    fetch.assert_not_called()
                    self.assertIn(name, str(caught.exception))

    def test_names_that_are_fine(self):
        for value in ("win64", "win64-aarch64", "en-US", "pt_BR", "ja-JP-mac", "x"):
            with self.subTest(value=value):
                self.assertEqual(provider.checked_text(value, "firefox_locale", "en-US"), value)
        self.assertEqual(provider.checked_text(None, "firefox_locale", "en-US"), "en-US")

    def test_a_version_file_that_is_not_what_is_expected_is_a_processor_error(self):
        for text, part in (
            ("", "not JSON"), ("not json", "not JSON"), ("{", "not JSON"), ("[]", "not a JSON object"),
            ('"text"', "not a JSON object"), ("null", "not a JSON object"), ("{}", "no key LATEST_FIREFOX_VERSION"),
            (json.dumps({"FIREFOX_ESR": "128.13.0esr"}), "no key LATEST_FIREFOX_VERSION"),
            (json.dumps({"LATEST_FIREFOX_VERSION": None}), "not text"),
            (json.dumps({"LATEST_FIREFOX_VERSION": 141.0}), "not text"),
            (json.dumps({"LATEST_FIREFOX_VERSION": ""}), "does not have the form"),
            (json.dumps({"LATEST_FIREFOX_VERSION": "141.0b4"}), "does not have the form"),
            (json.dumps({"LATEST_FIREFOX_VERSION": "../../x"}), "does not have the form"),
            (json.dumps({"LATEST_FIREFOX_VERSION": "141.0/../../x"}), "does not have the form"),
        ):
            processor, _ = new_processor(PROVIDER, {})
            with self.subTest(text=text[:40]):
                with mock.patch.object(provider, "fetch_text", side_effect=fetcher(text, "")) as fetch:
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                self.assertIn("Mozilla's version file", str(caught.exception))
                self.assertIn(part, str(caught.exception))
                self.assertEqual(fetch.call_count, 1)  # SHA256SUMS is never fetched for a bad version
                for key in ("url", "version", "expected_sha256"):
                    self.assertNotIn(key, processor.env)

    def test_a_bad_version_never_reaches_an_address(self):
        record = []
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "fetch_text", side_effect=fetcher(versions_text("1.0/../../x"), "", record)):
            with self.assertRaises(ProcessorError):
                processor.main()
        self.assertEqual([item[0] for item in record], [provider.VERSIONS_URL])

    def test_a_sums_file_that_does_not_have_the_line_is_a_processor_error_and_sets_no_output(self):
        for sums, part in (
            ("", "no line for win64/en-US/Firefox Setup 141.0.exe"),
            (sums_line("win32/en-US/Firefox Setup 141.0.exe"), "no line for"),
            ("<html>Not Found</html>", "not a SHA-256"),
            (self.good_sums() * 2, "2 lines"),
            (self.good_sums() + "garbage\n", "line 2 "),
            (self.good_sums(sha="z" * 64), "not a SHA-256"),
        ):
            processor, _ = new_processor(PROVIDER, {})
            with self.subTest(part=part):
                with mock.patch.object(provider, "fetch_text", side_effect=fetcher(versions_text(), sums)):
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                self.assertIn("Mozilla's SHA256SUMS of 141.0", str(caught.exception))
                self.assertIn(part, str(caught.exception))
                for key in ("url", "version", "expected_sha256"):
                    self.assertNotIn(key, processor.env)

    def test_the_sums_file_of_another_release_is_not_trusted(self):
        """A line for the right path of an OTHER version is not the line of this one."""
        error, _ = fails_on(versions_text("141.0.1"), self.good_sums("141.0"))
        self.assertIn("no line for win64/en-US/Firefox Setup 141.0.1.exe", str(error))

    def test_a_fetch_error_passes_through_and_sets_no_output(self):
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "fetch_text", side_effect=ProcessorError("down")):
            with self.assertRaises(ProcessorError):
                processor.main()
        self.assertNotIn("url", processor.env)

    def test_the_label_has_only_numbers_and_dots(self):
        for release, esr in (("141.0", "128.13.0esr"), ("141.0.1", "140.1esr"), ("99.99.99", "128.0")):
            for channel, text in (("release", release), ("esr", esr)):
                with self.subTest(channel=channel, text=text):
                    processor, _ = run_on(versions_text(release, esr), self.good_sums(text), {"firefox_channel": channel})
                    self.assertRegex(processor.env["version"], r"^[0-9]+\.[0-9]+(\.[0-9]+)?$")


class FetchTests(unittest.TestCase):
    URL = provider.VERSIONS_URL

    def fetch_with(self, body=None, error=None, status=200, url=None, max_bytes=1000):
        def opener(request):
            self.request = request
            if error is not None:
                raise error
            response = FakeResponse(body)
            response.status = status
            return response
        with mock.patch.object(provider, "open_request", side_effect=opener):
            return provider.fetch_text(url or self.URL, max_bytes, "the file")

    def test_the_text_is_returned_and_the_request_is_plain(self):
        text = self.fetch_with(body="café".encode("utf-8"))
        self.assertEqual(text, "café")
        self.assertEqual(self.request.full_url, self.URL)
        self.assertEqual(self.request.get_header("User-agent"), provider.USER_AGENT)
        self.assertIsNone(self.request.data)
        self.assertFalse(self.request.has_header("Authorization"))
        self.assertFalse(self.request.has_header("Cookie"))

    def test_an_address_on_another_host_is_refused_before_any_request(self):
        with mock.patch.object(provider, "open_request") as opener:
            for url in ("https://example.test/x", "http://product-details.mozilla.org/x"):
                with self.subTest(url=url):
                    with self.assertRaises(ProcessorError) as caught:
                        provider.fetch_text(url, 100, "the file")
                    self.assertIn("not on a fixed host", str(caught.exception))
        opener.assert_not_called()

    def test_a_status_other_than_200_is_an_error_that_names_it(self):
        for code, reason in ((404, "Not Found"), (500, "Server Error"), (429, "Too Many Requests")):
            error = urllib.error.HTTPError(self.URL, code, reason, {}, io.BytesIO(b""))
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error)
                self.assertIn("answered %d" % code, str(caught.exception))
                self.assertNotIn("redirect", str(caught.exception))

    def test_a_success_status_that_is_not_200_is_an_error(self):
        for status in (201, 204, 206):
            with self.subTest(status=status):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(body=b"x", status=status)
                self.assertIn("not 200", str(caught.exception))

    def test_a_redirect_is_an_error_that_says_so(self):
        for code in (301, 302, 307, 308):
            error = urllib.error.HTTPError(self.URL, code, "Moved", {}, io.BytesIO(b""))
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error)
                self.assertIn("a redirect is not followed", str(caught.exception))

    def test_the_redirect_handler_refuses_to_redirect(self):
        handler = provider.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, "https://example.test/"))

    def test_the_real_opener_is_built_with_the_redirect_refusing_handler_and_a_time_limit(self):
        with mock.patch.object(provider.urllib.request, "build_opener") as build:
            provider.open_request(object())
        handlers = build.call_args[0]
        self.assertEqual(len(handlers), 1)
        self.assertIs(handlers[0], provider.NoRedirect)
        build.return_value.open.assert_called_once()
        self.assertEqual(build.return_value.open.call_args[1]["timeout"], provider.FETCH_TIMEOUT_SECONDS)

    def test_a_failed_connection_is_a_processor_error(self):
        for error in (urllib.error.URLError("no route"), TimeoutError("timed out"), OSError("reset"),
                      ValueError("bad url")):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error)
                self.assertIn("could not be fetched", str(caught.exception))

    def test_an_answer_larger_than_the_limit_is_an_error_and_one_of_exactly_the_limit_is_not(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(body=b"x" * 1001)
        self.assertIn("larger than 1000", str(caught.exception))
        self.assertEqual(len(self.fetch_with(body=b"x" * 1000)), 1000)

    def test_an_answer_that_is_not_utf_8_is_an_error(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(body=b"\xff\xfe\x00bad")
        self.assertIn("not UTF-8", str(caught.exception))

    def test_the_limits_are_sensible(self):
        self.assertGreaterEqual(provider.MAX_SUMS_BYTES, 8 * 1024 * 1024)
        self.assertLessEqual(provider.MAX_VERSIONS_BYTES, 2 * 1024 * 1024)
        self.assertGreater(provider.MAX_SUMS_BYTES, provider.MAX_VERSIONS_BYTES)
        self.assertGreater(provider.FETCH_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(provider.FETCH_TIMEOUT_SECONDS, 600)

    def test_the_processor_asks_for_the_limits_it_declares(self):
        record = []
        run_on(read(VERSIONS_EXCERPT), read(SUMS_EXCERPT), record=record)
        self.assertEqual(record[0][1:], (provider.MAX_VERSIONS_BYTES, "Mozilla's version file"))
        self.assertEqual(record[1][1:], (provider.MAX_SUMS_BYTES, "Mozilla's SHA256SUMS"))


class SourceTests(unittest.TestCase):
    def test_the_module_has_no_other_address_and_no_hash(self):
        text = read(os.path.join(RECIPE_DIR, "MozillaFirefoxInfoProvider.py"))
        hosts = set(re.findall(r"https?://([A-Za-z0-9.-]+)", text))
        self.assertEqual(hosts, set(provider.ALLOWED_HOSTS))
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", text))


if __name__ == "__main__":
    unittest.main()
