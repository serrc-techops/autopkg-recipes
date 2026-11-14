"""Tests of GimpInfoProvider: every branch. No test uses the network:
fetch_text(), fetch_sums(), read_answer() or open_request() is replaced.

The two index files are copies of the real pages of 2026-11-13
(gimp_index_excerpt.html leaves some folders and files out;
v3_2_windows_index.html is whole); only their first line was added.
sha256sums_excerpt.txt has the real file names of SHA256SUMS of v3.2 in their
order and made-up digits, not the hash of any file. The real server was read on
2026-11-13 by the person who wrote the processor's address and format rules;
these tests never use the network.
"""
import io
import os
import sys
import unittest
import urllib.error
from email.message import Message
from unittest import mock

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.dirname(TESTS_DIR)
SHARED_TESTS_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-SharedProcessors", "tests")
for folder in (SHARED_TESTS_DIR, RECIPE_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

from _win_support import ProcessorError, new_processor, run_processor  # noqa: E402  (installs the autopkglib stand-in)

import GimpInfoProvider as provider  # noqa: E402

PROVIDER = provider.GimpInfoProvider
TOP_EXCERPT = os.path.join(TESTS_DIR, "gimp_index_excerpt.html")
FOLDER_EXCERPT = os.path.join(TESTS_DIR, "v3_2_windows_index.html")
SUMS_EXCERPT = os.path.join(TESTS_DIR, "sha256sums_excerpt.txt")
# Made-up digits, not the hash of any file.
HEX_A = "0123456789abcdef" * 4
HEX_B = "fedcba9876543210" * 4
TOP_URL = "https://download.gimp.org/gimp/"
SUMS_URL = "https://download.gimp.org/gimp/v3.2/windows/SHA256SUMS"
MIRROR_SUMS = "https://mirror.example.test/gimp/gimp/v3.2/windows/SHA256SUMS"
# Built here: the hygiene test would read four numbers as an address.
FOUR_NUMBERS = ".".join(["3", "2", "9", "1"])


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def index_of(*names):
    """A made-up index page with a link for each name."""
    links = "\n".join('<a href="%s">%s</a>' % (name, name) for name in names)
    return "<html><body><pre>\n%s\n</pre></body></html>" % links


def sums_of(*pairs):
    return "".join("%s  %s\n" % pair for pair in pairs)


class Server:
    """Stands in for fetch_text and fetch_sums: the answers are by address
    (fetch_text) or by series (fetch_sums)."""

    def __init__(self, pages, sums):
        self.pages = pages
        self.sums = sums
        self.calls = []

    def text(self, url, max_bytes, what):
        self.calls.append(("text", url, max_bytes, what))
        answer = self.pages[url]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def sums_for(self, series):
        self.calls.append(("sums", series))
        answer = self.sums[series]
        if isinstance(answer, Exception):
            raise answer
        return answer


def normal_pages():
    return {
        TOP_URL: index_of("../", "v2.10/", "v2.99/", "v3.0/", "v3.1/", "v3.2/", "README"),
        "https://download.gimp.org/gimp/v3.2/windows/": index_of(
            "gimp-3.2.6-setup.exe", "gimp-3.2.8-setup.exe", "gimp-3.2.8-setup.exe.torrent", "SHA256SUMS"),
        "https://download.gimp.org/gimp/v3.0/windows/": index_of(
            "gimp-3.0.8-setup.exe", "gimp-3.0.8-setup-1.exe", "gimp-3.0.8-setup-2.exe", "gimp-3.0.6-setup-3.exe"),
        "https://download.gimp.org/gimp/v3.1/windows/": index_of("gimp-3.1.2-setup.exe", "gimp-3.1.4-setup.exe"),
    }


def normal_sums():
    return {
        "3.2": (sums_of((HEX_B, "gimp-3.2.6-setup.exe"), (HEX_A, "gimp-3.2.8-setup.exe")), "mirror.example.test"),
        "3.0": (sums_of((HEX_B, "gimp-3.0.8-setup-1.exe"), (HEX_A, "gimp-3.0.8-setup-2.exe")), "mirror.example.test"),
        "3.1": (sums_of((HEX_A, "gimp-3.1.4-setup.exe")), "mirror.example.test"),
    }


def run_with(pages=None, sums=None, env=None):
    server = Server(pages or normal_pages(), sums or normal_sums())
    with mock.patch.object(provider, "fetch_text", side_effect=server.text), \
            mock.patch.object(provider, "fetch_sums", side_effect=server.sums_for):
        result = run_processor(PROVIDER, env or {})
    return result + (server,)


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def redirect(url, location, code=302):
    headers = Message()
    if location is not None:
        headers["Location"] = location
    return urllib.error.HTTPError(url, code, "Found", headers, io.BytesIO(b""))


class ExcerptTests(unittest.TestCase):
    """The copies of the real pages of 2026-11-13."""

    def test_the_first_lines_say_what_was_added(self):
        for path in (TOP_EXCERPT, FOLDER_EXCERPT):
            first = read(path).splitlines()[0]
            self.assertIn("of the real index of 2026-11-13", first)
            self.assertIn("Only this first line was added", first)

    def test_the_excerpts_are_small(self):
        for path in (TOP_EXCERPT, FOLDER_EXCERPT, SUMS_EXCERPT):
            self.assertLess(os.path.getsize(path), 4000)

    def test_the_top_index_gives_the_series_and_the_default_is_3_2(self):
        series = provider.extract_series(read(TOP_EXCERPT))
        self.assertEqual(series, ["0.99", "2.0", "2.1", "2.8", "2.9", "2.10", "2.99", "3.0", "3.1", "3.2"])
        self.assertEqual(provider.choose_series(series, "", False), "3.2")
        self.assertEqual(provider.choose_series(series, "3.0", False), "3.0")

    def test_the_folder_index_gives_3_2_8_and_not_a_release_candidate(self):
        self.assertEqual(provider.find_installer(read(FOLDER_EXCERPT), "3.2"),
                         ("3.2.8", 0, "gimp-3.2.8-setup.exe"))
        self.assertIn("gimp-3.2.0-RC3-setup.exe", read(FOLDER_EXCERPT))
        self.assertIn("0.0_LATEST-IS-3.2.8", read(FOLDER_EXCERPT))

    def test_the_sums_excerpt_has_the_one_line_of_the_installer(self):
        self.assertEqual(provider.parse_sums(read(SUMS_EXCERPT), "gimp-3.2.8-setup.exe"), "%064x" % 0x8888)

    def test_the_processor_on_the_copies(self):
        pages = {TOP_URL: read(TOP_EXCERPT), "https://download.gimp.org/gimp/v3.2/windows/": read(FOLDER_EXCERPT)}
        sums = {"3.2": (read(SUMS_EXCERPT), "mirror.example.test")}
        processor, messages, server = run_with(pages, sums)
        self.assertEqual(processor.env["url"], "https://download.gimp.org/gimp/v3.2/windows/gimp-3.2.8-setup.exe")
        self.assertEqual(processor.env["version"], "3.2.8")
        self.assertEqual(processor.env["expected_sha256"], "%064x" % 0x8888)
        self.assertEqual(processor.env["gimp_sha256sums_host"], "mirror.example.test")


class SeriesTests(unittest.TestCase):
    def test_series_are_compared_as_numbers(self):
        self.assertGreater(provider.series_key("2.10"), provider.series_key("2.8"))
        self.assertGreater(provider.series_key("3.0"), provider.series_key("2.99"))

    def test_anything_else_is_not_a_series(self):
        for value in ("3", "3.0.1", "v3.0", "3.0/", "03.0", "3.00", " 3.0", "3.x", "", None, 3.0, ["3.0"]):
            with self.subTest(value=value):
                self.assertIsNone(provider.series_key(value))

    def test_an_odd_second_number_is_development(self):
        self.assertTrue(provider.is_development("3.1"))
        self.assertTrue(provider.is_development("2.99"))
        self.assertFalse(provider.is_development("3.2"))
        self.assertFalse(provider.is_development("2.10"))
        with self.assertRaises(ValueError):
            provider.is_development("3")

    def test_only_links_that_are_exactly_a_series_folder_count(self):
        page = index_of("v3.2/", "v3.3", "/gimp/v3.4/", "v3.6/x", "V3.8/", "v3.10/ ", "v03.12/", "?C=N;O=D")
        self.assertEqual(provider.extract_series(page), ["3.2"])

    def test_no_series_link_is_an_error(self):
        for page in ("", "<html></html>", index_of("README", "help/")):
            with self.subTest(page=page[:20]):
                with self.assertRaises(ValueError) as caught:
                    provider.extract_series(page)
                self.assertIn("no link to a series folder", str(caught.exception))

    def test_the_default_takes_the_highest_even_series(self):
        self.assertEqual(provider.choose_series(["2.10", "2.99", "3.0", "3.1"], "", False), "3.0")
        self.assertEqual(provider.choose_series(["2.10", "3.0", "3.1", "3.2", "3.3"], "", False), "3.2")

    def test_development_allowed_takes_the_highest_of_all(self):
        self.assertEqual(provider.choose_series(["3.0", "3.1"], "", True), "3.1")

    def test_only_development_series_is_an_error(self):
        with self.assertRaises(ValueError) as caught:
            provider.choose_series(["2.99", "3.1"], "", False)
        self.assertIn("no stable series", str(caught.exception))

    def test_a_pinned_series_must_be_in_the_index(self):
        with self.assertRaises(ValueError) as caught:
            provider.choose_series(["3.0", "3.2"], "2.10", False)
        self.assertIn("no folder v2.10/", str(caught.exception))

    def test_a_pinned_odd_series_needs_the_allowance(self):
        with self.assertRaises(ValueError) as caught:
            provider.choose_series(["3.0", "3.1"], "3.1", False)
        self.assertIn("gimp_allow_development", str(caught.exception))
        self.assertEqual(provider.choose_series(["3.0", "3.1"], "3.1", True), "3.1")

    def test_the_folder_address(self):
        self.assertEqual(provider.series_folder_url("3.0"), "https://download.gimp.org/gimp/v3.0/windows/")
        for value in ("3", "../3.0", "3.0/..", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    provider.series_folder_url(value)


class FindInstallerTests(unittest.TestCase):
    def test_the_highest_version_is_taken_by_its_numbers(self):
        page = index_of("gimp-3.2.10-setup.exe", "gimp-3.2.8-setup.exe", "gimp-3.2.9-setup.exe")
        self.assertEqual(provider.find_installer(page, "3.2")[0], "3.2.10")

    def test_the_highest_revision_of_the_highest_version_is_taken(self):
        page = index_of("gimp-3.0.8-setup.exe", "gimp-3.0.8-setup-1.exe", "gimp-3.0.8-setup-2.exe",
                        "gimp-3.0.6-setup-9.exe")
        self.assertEqual(provider.find_installer(page, "3.0"), ("3.0.8", 2, "gimp-3.0.8-setup-2.exe"))

    def test_revisions_are_compared_as_numbers(self):
        page = index_of("gimp-3.0.8-setup-2.exe", "gimp-3.0.8-setup-10.exe")
        self.assertEqual(provider.find_installer(page, "3.0")[1], 10)

    def test_a_newer_version_wins_over_a_revision_of_an_older_one(self):
        page = index_of("gimp-3.0.8-setup-2.exe", "gimp-3.0.10-setup.exe")
        self.assertEqual(provider.find_installer(page, "3.0"), ("3.0.10", 0, "gimp-3.0.10-setup.exe"))

    def test_other_files_are_ignored(self):
        names = ["gimp-3.2.8-setup.exe.torrent", "gimp-3.2.9-RC1-setup.exe", "SHA256SUMS", "SHA512SUMS",
                 "0.0_LATEST-IS-3.2.9", "gimp-3.2.9-setup.msi", "gimp-3.2.9-setup-0.exe", "gimp-3.2.9-setup-01.exe",
                 "/gimp/v3.2/windows/gimp-3.2.9-setup.exe", "gimp-3.2.9-setup.exe?x=1", "GIMP-3.2.9-setup.exe",
                 "gimp-3.2-setup.exe", "gimp-%s-setup.exe" % FOUR_NUMBERS, "gimp-3.2.08-setup.exe", "gimp-3.2.8-setup.exe"]
        self.assertEqual(provider.find_installer(index_of(*names), "3.2"), ("3.2.8", 0, "gimp-3.2.8-setup.exe"))

    def test_no_installer_is_an_error(self):
        for page in ("", index_of("gimp-3.2.0-RC1-setup.exe", "SHA256SUMS")):
            with self.subTest(page=page[:20]):
                with self.assertRaises(ValueError) as caught:
                    provider.find_installer(page, "3.2")
                self.assertIn("no link to gimp-<version>-setup.exe", str(caught.exception))

    def test_an_installer_of_another_series_is_an_error_not_a_skip(self):
        with self.assertRaises(ValueError) as caught:
            provider.find_installer(index_of("gimp-3.2.8-setup.exe", "gimp-3.4.0-setup.exe"), "3.2")
        self.assertIn("another series", str(caught.exception))

    def test_links_with_entities_and_single_quotes_are_read(self):
        self.assertEqual(provider.find_installer("<a href='gimp-3.2.8-setup&#46;exe'>x</a>", "3.2")[0], "3.2.8")
        with self.assertRaises(ValueError):
            provider.find_installer('<a data-href="gimp-3.2.8-setup.exe">x</a>', "3.2")


class ParseSumsTests(unittest.TestCase):
    NAME = "gimp-3.2.8-setup.exe"

    def test_the_line_of_the_file_gives_its_hash_in_lower_case(self):
        text = sums_of((HEX_B, "gimp-3.2.6-setup.exe"), (HEX_A.upper(), self.NAME))
        self.assertEqual(provider.parse_sums(text, self.NAME), HEX_A)

    def test_line_ends_do_not_matter(self):
        for text in (HEX_A + "  " + self.NAME, HEX_A + "  " + self.NAME + "\r\n", "\n" + HEX_A + "  " + self.NAME + "\n\n"):
            with self.subTest(text=repr(text[-4:])):
                self.assertEqual(provider.parse_sums(text, self.NAME), HEX_A)

    def test_the_name_must_match_exactly(self):
        for name in ("gimp-3.2.8-setup-1.exe", "GIMP-3.2.8-setup.exe", "gimp-3.2.8-setup.exe.torrent", "gimp-3.2.80-setup.exe"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError) as caught:
                    provider.parse_sums(sums_of((HEX_A, name)), self.NAME)
                self.assertIn("no line for " + self.NAME, str(caught.exception))

    def test_two_lines_for_the_file_are_an_error(self):
        with self.assertRaises(ValueError) as caught:
            provider.parse_sums(sums_of((HEX_A, self.NAME), (HEX_B, self.NAME)), self.NAME)
        self.assertIn("2 lines for", str(caught.exception))

    def test_a_line_of_another_form_is_an_error_never_skipped(self):
        for bad in (HEX_A + " " + self.NAME, HEX_A + " *" + self.NAME, HEX_A + "   " + self.NAME,
                    HEX_A[:-1] + "  " + self.NAME, "g" + HEX_A[1:] + "  " + self.NAME, HEX_A + "  windows/" + self.NAME,
                    HEX_A + "  a name", "<html>Not Found</html>", HEX_A):
            with self.subTest(bad=bad[-30:]):
                with self.assertRaises(ValueError) as caught:
                    provider.parse_sums(sums_of((HEX_A, self.NAME)) + bad + "\n", self.NAME)
                self.assertIn("is not a SHA-256", str(caught.exception))


class RedirectTargetTests(unittest.TestCase):
    def test_the_mirror_seen_on_2026_11_13_has_the_accepted_shape(self):
        # The real mirror's name is not written here; its path was /gimp/gimp/v3.2/windows/SHA256SUMS.
        self.assertEqual(provider.check_redirect_target(MIRROR_SUMS, "3.2"), MIRROR_SUMS)
        self.assertEqual(provider.check_redirect_target("https://download.gimp.org/gimp/v3.2/windows/SHA256SUMS", "3.2"),
                         "https://download.gimp.org/gimp/v3.2/windows/SHA256SUMS")

    def test_anything_else_is_refused(self):
        for location in ("http://mirror.example.test/gimp/v3.2/windows/SHA256SUMS",
                         "https://mirror.example.test/gimp/v3.0/windows/SHA256SUMS",
                         "https://mirror.example.test/gimp/v3.2/windows/SHA512SUMS",
                         "https://mirror.example.test/gimp/v3.2/windows/SHA256SUMS?x=1",
                         "https://mirror.example.test/gimp/v3.2/windows/SHA256SUMS#x",
                         "https://user@mirror.example.test/gimp/v3.2/windows/SHA256SUMS",
                         "https://mirror.example.test:8443/gimp/v3.2/windows/SHA256SUMS",
                         "https://mirror.example.test/x/../gimp/v3.2/windows/SHA256SUMS",
                         "https://mirror.example.test//gimp/v3.2/windows/SHA256SUMS",
                         "https://mirror/gimp/v3.2/windows/SHA256SUMS",
                         "https://mirror.example.test/gimp/v3.2/windows/SHA256SUMS/",
                         "ftp://mirror.example.test/gimp/v3.2/windows/SHA256SUMS", "", None):
            with self.subTest(location=location):
                with self.assertRaises(ValueError):
                    provider.check_redirect_target(location, "3.2")


class FetchSumsTests(unittest.TestCase):
    """fetch_sums with read_answer's request replaced: the redirect rule."""

    def run_fetch(self, answers, series="3.2"):
        self.urls = []

        def opener(request):
            self.urls.append(request.full_url)
            answer = answers[request.full_url]
            if isinstance(answer, Exception):
                raise answer
            return FakeResponse(answer)
        with mock.patch.object(provider, "open_request", side_effect=opener):
            return provider.fetch_sums(series)

    def test_a_direct_answer_is_from_the_project_host(self):
        self.assertEqual(self.run_fetch({SUMS_URL: b"text"}), ("text", "download.gimp.org"))

    def test_one_redirect_to_a_mirror_is_followed_and_the_mirror_is_named(self):
        text, host = self.run_fetch({SUMS_URL: redirect(SUMS_URL, MIRROR_SUMS), MIRROR_SUMS: b"text"})
        self.assertEqual((text, host), ("text", "mirror.example.test"))
        self.assertEqual(self.urls, [SUMS_URL, MIRROR_SUMS])

    def test_a_second_redirect_is_not_followed(self):
        other = "https://other.example.test/gimp/v3.2/windows/SHA256SUMS"
        with self.assertRaises(ProcessorError) as caught:
            self.run_fetch({SUMS_URL: redirect(SUMS_URL, MIRROR_SUMS), MIRROR_SUMS: redirect(MIRROR_SUMS, other),
                            other: b"text"})
        self.assertIn("only one redirect is followed", str(caught.exception))
        self.assertNotIn(other, self.urls)

    def test_a_redirect_to_another_path_is_refused_before_it_is_asked(self):
        bad = "https://mirror.example.test/gimp/v3.2/windows/gimp-3.2.8-setup.exe"
        with self.assertRaises(ProcessorError) as caught:
            self.run_fetch({SUMS_URL: redirect(SUMS_URL, bad), bad: b"text"})
        self.assertIn("SHA256SUMS:", str(caught.exception))
        self.assertEqual(self.urls, [SUMS_URL])

    def test_a_redirect_without_a_location_is_an_error(self):
        with self.assertRaises(ProcessorError) as caught:
            self.run_fetch({SUMS_URL: redirect(SUMS_URL, None)})
        self.assertIn("no Location", str(caught.exception))

    def test_a_relative_location_is_read_against_the_project_host(self):
        text, host = self.run_fetch({SUMS_URL: redirect(SUMS_URL, "/mirror/gimp/v3.2/windows/SHA256SUMS"),
                                     "https://download.gimp.org/mirror/gimp/v3.2/windows/SHA256SUMS": b"t"})
        self.assertEqual(host, "download.gimp.org")

    def test_an_error_of_the_mirror_is_an_error(self):
        error = urllib.error.HTTPError(MIRROR_SUMS, 404, "Not Found", Message(), io.BytesIO(b""))
        with self.assertRaises(ProcessorError) as caught:
            self.run_fetch({SUMS_URL: redirect(SUMS_URL, MIRROR_SUMS), MIRROR_SUMS: error})
        self.assertIn("answered 404", str(caught.exception))

    def test_the_mirrors_answer_has_the_size_limit(self):
        with self.assertRaises(ProcessorError) as caught:
            self.run_fetch({SUMS_URL: redirect(SUMS_URL, MIRROR_SUMS),
                            MIRROR_SUMS: b"x" * (provider.MAX_SUMS_BYTES + 1)})
        self.assertIn("larger than", str(caught.exception))


class FetchTextTests(unittest.TestCase):
    def fetch_with(self, body=None, error=None, url=TOP_URL, max_bytes=1000):
        def opener(request):
            self.request = request
            if error is not None:
                raise error
            return FakeResponse(body)
        with mock.patch.object(provider, "open_request", side_effect=opener):
            return provider.fetch_text(url, max_bytes, "the thing")

    def test_the_text_is_returned_and_the_request_is_plain(self):
        self.assertEqual(self.fetch_with(body="café".encode("utf-8")), "café")
        self.assertEqual(self.request.get_header("User-agent"), provider.USER_AGENT)
        self.assertIsNone(self.request.data)

    def test_an_address_outside_the_project_folder_is_refused_before_any_request(self):
        for url in ("http://download.gimp.org/gimp/", "https://download.gimp.org.example.test/gimp/",
                    "https://download.gimp.org/pub/", "https://mirror.example.test/gimp/", ""):
            with self.subTest(url=url):
                with mock.patch.object(provider, "open_request") as opener:
                    with self.assertRaises(ProcessorError) as caught:
                        provider.fetch_text(url, 1000, "the thing")
                opener.assert_not_called()
                self.assertIn("outside", str(caught.exception))

    def test_a_redirect_of_an_index_is_an_error_that_says_so(self):
        for code in (301, 302, 307, 308):
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=redirect(TOP_URL, MIRROR_SUMS, code))
                self.assertIn("a redirect is not followed", str(caught.exception))

    def test_a_status_other_than_200_is_an_error(self):
        for code in (404, 500):
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=urllib.error.HTTPError(TOP_URL, code, "x", Message(), io.BytesIO(b"")))
                self.assertIn("answered %d" % code, str(caught.exception))

    def test_a_failed_connection_is_a_processor_error(self):
        for error in (urllib.error.URLError("no route"), TimeoutError("t"), OSError("reset")):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error)
                self.assertIn("could not be fetched", str(caught.exception))

    def test_the_size_limit_and_utf_8(self):
        self.assertEqual(len(self.fetch_with(body=b"x" * 1000)), 1000)
        with self.assertRaises(ProcessorError):
            self.fetch_with(body=b"x" * 1001)
        with self.assertRaises(ProcessorError):
            self.fetch_with(body=b"\xff\xfe")

    def test_the_opener_refuses_redirects_and_has_the_time_limit(self):
        self.assertIsNone(provider.NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://x.test/"))
        with mock.patch.object(provider.urllib.request, "build_opener") as build:
            provider.open_request(object())
        self.assertEqual(build.call_args[0], (provider.NoRedirect,))
        self.assertEqual(build.return_value.open.call_args[1]["timeout"], provider.FETCH_TIMEOUT_SECONDS)

    def test_the_limits_are_sensible(self):
        self.assertEqual(provider.BASE_URL, "https://download.gimp.org/gimp/")
        self.assertLessEqual(provider.MAX_INDEX_BYTES, 8 * 1024 * 1024)
        self.assertLessEqual(provider.MAX_SUMS_BYTES, 1024 * 1024)
        self.assertLessEqual(provider.FETCH_TIMEOUT_SECONDS, 600)


class MainTests(unittest.TestCase):
    def test_the_default_is_the_newest_stable_series(self):
        processor, messages, server = run_with()
        self.assertEqual(processor.env["url"], "https://download.gimp.org/gimp/v3.2/windows/gimp-3.2.8-setup.exe")
        self.assertEqual(processor.env["version"], "3.2.8")
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertEqual(processor.env["gimp_chosen_series"], "3.2")
        self.assertEqual(processor.env["gimp_installer_name"], "gimp-3.2.8-setup.exe")
        self.assertEqual(processor.env["gimp_sha256sums_host"], "mirror.example.test")
        self.assertTrue(any("mirror.example.test" in m and "not proof of origin" in m for m in messages))

    def test_a_pinned_series_and_its_newest_revision_with_the_version_as_label(self):
        processor, _, _ = run_with(env={"gimp_series": "3.0"})
        self.assertEqual(processor.env["url"], "https://download.gimp.org/gimp/v3.0/windows/gimp-3.0.8-setup-2.exe")
        self.assertEqual(processor.env["version"], "3.0.8")
        self.assertEqual(processor.env["expected_sha256"], HEX_A)

    def test_a_development_series_only_with_the_allowance(self):
        processor, _, _ = run_with(env={"gimp_series": "3.1", "gimp_allow_development": True})
        self.assertEqual(processor.env["version"], "3.1.4")
        processor, _ = new_processor(PROVIDER, {"gimp_series": "3.1"})
        server = Server(normal_pages(), normal_sums())
        with mock.patch.object(provider, "fetch_text", side_effect=server.text), \
                mock.patch.object(provider, "fetch_sums", side_effect=server.sums_for):
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        self.assertIn("gimp_allow_development", str(caught.exception))
        self.assertNotIn("url", processor.env)

    def test_the_allowance_as_text(self):
        processor, _, _ = run_with(env={"gimp_allow_development": "true"})
        self.assertEqual(processor.env["gimp_chosen_series"], "3.2")  # no odd series is higher here
        for value in ("maybe", 2, ["true"]):
            processor, _ = new_processor(PROVIDER, {"gimp_allow_development": value})
            with self.subTest(value=value):
                with mock.patch.object(provider, "fetch_text") as fetch:
                    with self.assertRaises(ProcessorError):
                        processor.main()
                fetch.assert_not_called()

    def test_a_bad_series_input_is_an_error_and_nothing_is_fetched(self):
        for value in ("3", "v3.0", "3.0/", "../3.0", 3.0, ["3.0"]):
            processor, _ = new_processor(PROVIDER, {"gimp_series": value})
            with self.subTest(value=value):
                with mock.patch.object(provider, "fetch_text") as fetch:
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                fetch.assert_not_called()
                self.assertIn("gimp_series", str(caught.exception))

    def test_white_space_and_none_mean_the_default(self):
        for value in (" ", None, " 3.2 "):
            with self.subTest(value=value):
                processor, _, _ = run_with(env={"gimp_series": value})
                self.assertEqual(processor.env["version"], "3.2.8")

    def test_the_declared_inputs_and_outputs(self):
        declared = {name: flags["default"] for name, flags in PROVIDER.input_variables.items()}
        self.assertEqual(declared, {"gimp_series": "", "gimp_allow_development": False})
        for flags in PROVIDER.input_variables.values():
            self.assertIs(flags["required"], False)
        self.assertEqual(sorted(PROVIDER.output_variables), ["expected_sha256", "gimp_chosen_series",
                                                             "gimp_installer_name", "gimp_sha256sums_host",
                                                             "url", "version"])

    def failing(self, pages=None, sums=None):
        processor, _ = new_processor(PROVIDER, {})
        server = Server(pages or normal_pages(), sums or normal_sums())
        with mock.patch.object(provider, "fetch_text", side_effect=server.text), \
                mock.patch.object(provider, "fetch_sums", side_effect=server.sums_for):
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        for key in PROVIDER.output_variables:
            self.assertNotIn(key, processor.env)
        return str(caught.exception)

    def test_failures_set_no_output(self):
        pages = normal_pages()
        pages[TOP_URL] = "<html>Maintenance</html>"
        self.assertIn("GIMP index:", self.failing(pages))
        pages = normal_pages()
        pages["https://download.gimp.org/gimp/v3.2/windows/"] = index_of("gimp-3.2.0-RC1-setup.exe")
        self.assertIn("GIMP index of v3.2/windows/:", self.failing(pages))
        sums = normal_sums()
        sums["3.2"] = (sums_of((HEX_A, "gimp-3.2.6-setup.exe")), "mirror.example.test")
        message = self.failing(sums=sums)
        self.assertIn("GIMP SHA256SUMS of v3.2 (served by mirror.example.test)", message)
        sums["3.2"] = ProcessorError("SHA256SUMS: the redirect has no Location.")
        self.assertIn("no Location", self.failing(sums=sums))

    def test_the_requests_have_their_limits(self):
        _, _, server = run_with()
        self.assertEqual(server.calls[0], ("text", TOP_URL, provider.MAX_INDEX_BYTES, "the index of the series"))
        self.assertEqual(server.calls[1][:3], ("text", "https://download.gimp.org/gimp/v3.2/windows/",
                                               provider.MAX_INDEX_BYTES))
        self.assertEqual(server.calls[2], ("sums", "3.2"))


if __name__ == "__main__":
    unittest.main()
