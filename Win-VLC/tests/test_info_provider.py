"""Tests of VideoLANVlcInfoProvider: every branch. No test uses the network:
fetch_text() or open_request() is replaced.

The index excerpt (last_win64_index_excerpt.html) is a copy of the real index of
2026-10-02 (real file names, dates and sizes, no hash); only its first line was
added. The hash lines here are written by hand in the
format of the real file (64 hex digits, two spaces, the file name, a new line):
the digits are made up, not the hash of any file. The real server was read on
2026-10-02 by the person who wrote the processor's address and format rules;
these tests never use the network.
"""
import io
import os
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

import VideoLANVlcInfoProvider as provider  # noqa: E402

PROVIDER = provider.VideoLANVlcInfoProvider
EXCERPT = os.path.join(TESTS_DIR, "last_win64_index_excerpt.html")
# Made-up digits, not the hash of any file.
HEX_A = "0123456789abcdef" * 4
HEX_B = "fedcba9876543210" * 4
INDEX_URL = "https://download.videolan.org/vlc/last/win64/"
# Texts that the hygiene test would read as an address if they stood in this
# file as they are. They are built here.
FOUR_NUMBERS = ".".join(["3", "0", "11", "1"])
FOUR_NUMBERS_NEWER = ".".join(["3", "0", "21", "1"])
FIVE_NUMBERS = ".".join(["3", "0", "21", "1", "1"])


def index_of(*names):
    """A made-up index page with a link for each name."""
    links = "\n".join('<a href="%s">%s</a>' % (name, name) for name in names)
    return "<html><body><h1>Index of /vlc/last/win64/</h1><pre>\n%s\n</pre></body></html>" % links


def hash_line(sha256=HEX_A, name="vlc-3.0.21-win64.msi", gap="  ", end="\n"):
    return "%s%s%s%s" % (sha256, gap, name, end)


class Server:
    """Stands in for fetch_text: the answers are by address."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, url, max_bytes, what):
        self.calls.append((url, max_bytes, what))
        answer = self.answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer


def run_with(answers, env=None):
    server = Server(answers)
    with mock.patch.object(provider, "fetch_text", side_effect=server):
        result = run_processor(PROVIDER, env or {})
    return result + (server,)


def normal_answers(version="3.0.21", architecture="win64", sha256=HEX_A):
    name = "vlc-%s-%s.msi" % (version, architecture)
    return {
        "https://download.videolan.org/vlc/last/%s/" % architecture: index_of(
            "vlc-%s-%s.exe" % (version, architecture), name, name + ".sha256", "vlc-%s-%s.zip" % (version, architecture)),
        "https://download.videolan.org/vlc/%s/%s/%s.sha256" % (version, architecture, name): hash_line(sha256, name),
    }


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ExcerptTests(unittest.TestCase):
    """The excerpt that was written by hand."""

    def setUp(self):
        with open(EXCERPT, "r", encoding="utf-8") as handle:
            self.page = handle.read()

    def test_the_first_line_says_it_was_written_by_hand(self):
        self.assertIn("A copy of the real index of 2026-10-02",
                      self.page.splitlines()[0])
        self.assertIn("Only this first line was added", self.page.splitlines()[0])

    def test_the_excerpt_is_small(self):
        self.assertLess(len(self.page), 20000)

    def test_the_one_version_of_the_msi_is_found_among_the_other_files(self):
        self.assertEqual(provider.find_version(self.page, "win64"), "3.0.24")

    def test_the_processor_gives_the_msi_of_the_versioned_folder_and_its_hash(self):
        answers = {
            INDEX_URL: self.page,
            "https://download.videolan.org/vlc/3.0.24/win64/vlc-3.0.24-win64.msi.sha256": hash_line(HEX_A, "vlc-3.0.24-win64.msi"),
        }
        processor, messages, server = run_with(answers)
        self.assertEqual(processor.env["version"], "3.0.24")
        self.assertEqual(processor.env["url"], "https://download.videolan.org/vlc/3.0.24/win64/vlc-3.0.24-win64.msi")
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertEqual([call[0] for call in server.calls], list(answers))

    def test_the_debug_symbol_files_and_the_parent_link_are_not_the_msi(self):
        self.assertIn("vlc-3.0.24-win64-debugsym.7z", self.page)
        self.assertIn('href="../"', self.page)
        self.assertEqual(len(provider.LINK_PATTERN.findall(self.page)), 25)

    def test_the_32_bit_msi_is_not_in_the_64_bit_index(self):
        with self.assertRaises(ValueError) as caught:
            provider.find_version(self.page, "win32")
        self.assertIn("no link", str(caught.exception))


class VersionKeyTests(unittest.TestCase):
    def test_numbers_are_compared_as_numbers(self):
        self.assertGreater(provider.version_key("3.0.21"), provider.version_key("3.0.9"))
        self.assertGreater(provider.version_key(FOUR_NUMBERS_NEWER), provider.version_key("3.0.21"))
        self.assertEqual(provider.version_key("3.0.21"), (3, 0, 21))
        self.assertEqual(provider.version_key(FOUR_NUMBERS), (3, 0, 11, 1))

    def test_anything_else_is_not_a_version(self):
        for value in ("3.0", "3", FIVE_NUMBERS, "3.0.21rc1", "3.0.x", "v3.0.21", "", " 3.0.21", "3.0.21\n", "3..21",
                      "3.0.-1", "٣.٠.٢١", None, 3, ["3.0.21"]):
            with self.subTest(value=value):
                self.assertIsNone(provider.version_key(value))


class NameAndAddressTests(unittest.TestCase):
    def test_the_name_of_the_msi(self):
        self.assertEqual(provider.msi_file_name("3.0.21", "win64"), "vlc-3.0.21-win64.msi")
        self.assertEqual(provider.msi_file_name("3.0.21", "win32"), "vlc-3.0.21-win32.msi")
        self.assertEqual(provider.msi_file_name(FOUR_NUMBERS, "win64"), "vlc-%s-win64.msi" % FOUR_NUMBERS)

    def test_a_name_is_not_built_from_something_that_is_not_a_version_or_an_architecture(self):
        for version, architecture in (("3.0", "win64"), ("../3.0.21", "win64"), ("3.0.21/x", "win64"), ("", "win64"),
                                      (None, "win64"), ("3.0.21", "arm64"), ("3.0.21", "../win64"), ("3.0.21", ""),
                                      ("3.0.21", "WIN64")):
            with self.subTest(version=version, architecture=architecture):
                with self.assertRaises(ValueError):
                    provider.msi_file_name(version, architecture)

    def test_the_addresses(self):
        self.assertEqual(provider.index_url("win64"), "https://download.videolan.org/vlc/last/win64/")
        self.assertEqual(provider.index_url("win32"), "https://download.videolan.org/vlc/last/win32/")
        self.assertEqual(provider.folder_url("3.0.21", "win64"), "https://download.videolan.org/vlc/3.0.21/win64/")

    def test_an_address_is_not_built_for_another_architecture(self):
        for architecture in ("arm64", "", "win64/../x", "../x"):
            with self.subTest(architecture=architecture):
                with self.assertRaises(ValueError):
                    provider.index_url(architecture)
                with self.assertRaises(ValueError):
                    provider.folder_url("3.0.21", architecture)

    def test_the_constants_are_the_publishers_own_server_over_https_not_the_redirecting_one(self):
        self.assertEqual(provider.BASE_URL, "https://download.videolan.org/vlc/")
        self.assertNotIn("get.", provider.BASE_URL)
        self.assertTrue(provider.BASE_URL.endswith("/"))


class FindVersionTests(unittest.TestCase):
    def test_one_link_gives_its_version(self):
        self.assertEqual(provider.find_version(index_of("vlc-3.0.21-win64.msi"), "win64"), "3.0.21")

    def test_the_other_files_of_the_release_are_ignored(self):
        names = ["vlc-3.0.21-win64.exe", "vlc-3.0.21-win64.7z", "vlc-3.0.21-win64.zip", "vlc-3.0.21-win64.exe.sha256",
                 "vlc-3.0.21-win64.msi.sha256", "vlc-3.0.21-win64.msi.asc", "vlc-3.0.21-win64.msi.md5",
                 "vlc-3.0.21-win64.msi.sha1", "vlc-3.0.21-win64.msi", "?C=N;O=D", "/vlc/last/"]
        self.assertEqual(provider.find_version(index_of(*names), "win64"), "3.0.21")

    def test_a_link_to_the_hash_file_alone_is_not_the_msi(self):
        with self.assertRaises(ValueError) as caught:
            provider.find_version(index_of("vlc-3.0.21-win64.msi.sha256"), "win64")
        self.assertIn("no link", str(caught.exception))

    def test_the_same_link_twice_is_one_version(self):
        self.assertEqual(provider.find_version(index_of("vlc-3.0.21-win64.msi", "vlc-3.0.21-win64.msi"), "win64"), "3.0.21")

    def test_two_versions_are_an_error_that_names_both_in_order_of_their_numbers(self):
        with self.assertRaises(ValueError) as caught:
            provider.find_version(index_of("vlc-3.0.9-win64.msi", "vlc-3.0.21-win64.msi"), "win64")
        message = str(caught.exception)
        self.assertIn("2 different versions", message)
        self.assertIn("3.0.9, 3.0.21", message)
        self.assertIn("not exactly one", message)

    def test_no_link_is_an_error(self):
        for page in ("", "<html></html>", "not html at all", index_of("vlc-3.0.21-win64.exe"), index_of("readme.txt"),
                     index_of("vlc-3.0.21-win32.msi")):
            with self.subTest(page=page[:30]):
                with self.assertRaises(ValueError) as caught:
                    provider.find_version(page, "win64")
                self.assertIn("no link to vlc-<version>-win64.msi", str(caught.exception))

    def test_the_text_of_the_link_without_an_address_does_not_count(self):
        page = "<html><body>vlc-3.0.21-win64.msi <a name='x'>vlc-3.0.21-win64.msi</a></body></html>"
        with self.assertRaises(ValueError):
            provider.find_version(page, "win64")

    def test_only_the_bare_file_name_is_a_match(self):
        for address in ("/vlc/3.0.21/win64/vlc-3.0.21-win64.msi", "./vlc-3.0.21-win64.msi",
                        "https://download.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.msi",
                        "vlc-3.0.21-win64.msi?x=1", " vlc-3.0.21-win64.msi", "vlc-3.0.21-win64.msi ",
                        "xvlc-3.0.21-win64.msi", "VLC-3.0.21-win64.msi", "vlc-3.0.21-WIN64.msi", "vlc-3.0.21-win64.MSI",
                        "vlc-3.0.21-win64.msi/", "vlc-3.0.21-win64-extra.msi"):
            with self.subTest(address=address):
                with self.assertRaises(ValueError):
                    provider.find_version(index_of(address), "win64")

    def test_the_address_is_read_with_its_html_entities_decoded(self):
        page = '<a href="vlc-3.0.21-win64&#46;msi">x</a>'
        self.assertEqual(provider.find_version(page, "win64"), "3.0.21")

    def test_single_quoted_and_spaced_attributes_are_read(self):
        for page in ("<a href='vlc-3.0.21-win64.msi'>x</a>", '<A HREF="vlc-3.0.21-win64.msi">x</A>',
                     '<a class="f" href = "vlc-3.0.21-win64.msi" title="y">x</a>',
                     '<a\n  href="vlc-3.0.21-win64.msi">x</a>'):
            with self.subTest(page=page):
                self.assertEqual(provider.find_version(page, "win64"), "3.0.21")

    def test_an_attribute_that_only_ends_in_href_is_not_read(self):
        for page in ('<a data-href="vlc-3.0.21-win64.msi">x</a>', '<a xhref="vlc-3.0.21-win64.msi">x</a>'):
            with self.subTest(page=page):
                with self.assertRaises(ValueError):
                    provider.find_version(page, "win64")

    def test_four_numbers_are_accepted_and_compared_as_the_one_version(self):
        self.assertEqual(provider.find_version(index_of("vlc-%s-win64.msi" % FOUR_NUMBERS), "win64"), FOUR_NUMBERS)

    def test_a_link_with_a_version_that_is_not_numbers_is_an_error_not_a_skip(self):
        for version in ("3.0", "3", "3..21", "3.0.", ".3.0.21", FIVE_NUMBERS, "...", "3"):
            with self.subTest(version=version):
                with self.assertRaises(ValueError) as caught:
                    provider.find_version(index_of("vlc-%s-win64.msi" % version, "vlc-3.0.21-win64.msi"), "win64")
                self.assertIn("not three or four numbers", str(caught.exception))

    def test_a_link_with_letters_in_the_version_is_not_the_msi(self):
        self.assertEqual(provider.find_version(index_of("vlc-3.0.22-rc1-win64.msi", "vlc-3.0.21-win64.msi"), "win64"),
                         "3.0.21")

    def test_the_architecture_chooses_the_links(self):
        page = index_of("vlc-3.0.21-win64.msi", "vlc-3.0.20-win32.msi")
        self.assertEqual(provider.find_version(page, "win64"), "3.0.21")
        self.assertEqual(provider.find_version(page, "win32"), "3.0.20")

    def test_another_architecture_is_an_error(self):
        for architecture in ("arm64", "", "win.*"):
            with self.subTest(architecture=architecture):
                with self.assertRaises(ValueError):
                    provider.find_version(index_of("vlc-3.0.21-win64.msi"), architecture)


class ParseHashLineTests(unittest.TestCase):
    NAME = "vlc-3.0.21-win64.msi"

    def test_the_line_gives_the_hash(self):
        self.assertEqual(provider.parse_hash_line(hash_line(HEX_A), self.NAME), HEX_A)

    def test_the_hash_is_returned_in_lower_case(self):
        self.assertEqual(provider.parse_hash_line(hash_line(HEX_A.upper()), self.NAME), HEX_A)

    def test_the_end_of_the_line_does_not_matter(self):
        for end in ("", "\n", "\r\n", "\n\n", "\n \n"):
            with self.subTest(end=repr(end)):
                self.assertEqual(provider.parse_hash_line(hash_line(end=end), self.NAME), HEX_A)

    def test_no_line_or_two_lines_is_an_error(self):
        for text in ("", "\n", "  \n", hash_line() + hash_line(HEX_B), hash_line() + "x\n"):
            with self.subTest(text=text[:20]):
                with self.assertRaises(ValueError) as caught:
                    provider.parse_hash_line(text, self.NAME)
                self.assertIn("not exactly one", str(caught.exception))

    def test_a_line_that_is_not_hash_two_spaces_and_a_name_is_an_error(self):
        for text in (
            HEX_A + " " + self.NAME,                  # one space
            HEX_A + " *" + self.NAME,                 # the binary marker
            HEX_A + "   " + self.NAME,                # three spaces: the name would start with a space
            HEX_A + "\t" + self.NAME,
            HEX_A[:-1] + "  " + self.NAME,            # 63 digits
            HEX_A + "0  " + self.NAME,                # 65 digits
            "g" + HEX_A[1:] + "  " + self.NAME,       # not hex
            "  " + self.NAME,
            HEX_A,
            HEX_A + "  ",
            self.NAME,
            " " + HEX_A + "  " + self.NAME,
        ):
            with self.subTest(text=text[:30]):
                with self.assertRaises(ValueError):
                    provider.parse_hash_line(text + "\n", self.NAME)

    def test_a_line_for_another_file_is_an_error(self):
        for name in ("vlc-3.0.21-win64.exe", "vlc-3.0.20-win64.msi", "vlc-3.0.21-win32.msi", "VLC-3.0.21-win64.msi",
                     "vlc-3.0.21-win64.msi.sha256", "x/vlc-3.0.21-win64.msi", "vlc-3.0.21-win64.msi ", "a"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError) as caught:
                    provider.parse_hash_line(hash_line(name=name), self.NAME)
                self.assertIn("not " + self.NAME, str(caught.exception))


class MainTests(unittest.TestCase):
    def test_the_defaults_are_the_64_bit_msi(self):
        processor, messages, server = run_with(normal_answers())
        self.assertEqual(processor.env["version"], "3.0.21")
        self.assertEqual(processor.env["url"], "https://download.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.msi")
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertTrue(any("3.0.21" in m for m in messages))
        self.assertTrue(any(HEX_A in m for m in messages))

    def test_the_file_is_in_the_versioned_folder_not_in_last(self):
        processor, _, server = run_with(normal_answers("3.0.20"))
        self.assertNotIn("/last/", processor.env["url"])
        self.assertIn("/vlc/3.0.20/win64/", processor.env["url"])
        self.assertEqual(server.calls[1][0], processor.env["url"] + ".sha256")

    def test_the_declared_defaults_equal_the_values_the_code_uses(self):
        declared = {name: flags["default"] for name, flags in PROVIDER.input_variables.items()}
        self.assertEqual(declared, {"vlc_architecture": "win64"})
        self.assertEqual(provider.DEFAULT_ARCHITECTURE, "win64")
        for flags in PROVIDER.input_variables.values():
            self.assertIs(flags["required"], False)
            self.assertIn("description", flags)
        self.assertEqual(sorted(PROVIDER.output_variables), ["expected_sha256", "url", "version"])

    def test_the_32_bit_msi(self):
        processor, _, server = run_with(normal_answers("3.0.20", "win32", HEX_B), {"vlc_architecture": "win32"})
        self.assertEqual(processor.env["url"], "https://download.videolan.org/vlc/3.0.20/win32/vlc-3.0.20-win32.msi")
        self.assertEqual(processor.env["expected_sha256"], HEX_B)
        self.assertEqual(server.calls[0][0], "https://download.videolan.org/vlc/last/win32/")

    def test_white_space_around_the_input_is_ignored(self):
        processor, _, _ = run_with(normal_answers(), {"vlc_architecture": " win64\n"})
        self.assertEqual(processor.env["version"], "3.0.21")

    def test_an_input_that_is_empty_or_not_text_is_an_error_and_nothing_is_fetched(self):
        for value in ("", "  ", None, 7, ["win64"]):
            processor, _ = new_processor(PROVIDER, {"vlc_architecture": value})
            with self.subTest(value=value):
                with mock.patch.object(provider, "fetch_text") as fetch:
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                fetch.assert_not_called()
                self.assertIn("vlc_architecture", str(caught.exception))

    def test_an_architecture_other_than_the_two_is_an_error_and_nothing_is_fetched(self):
        for value in ("arm64", "x64", "WIN64", "win64/../x", "last", "win64\nwin32", "../win64"):
            processor, _ = new_processor(PROVIDER, {"vlc_architecture": value})
            with self.subTest(value=value):
                with mock.patch.object(provider, "fetch_text") as fetch:
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                fetch.assert_not_called()
                self.assertIn("vlc_architecture must be one of win64, win32", str(caught.exception))

    def test_the_requests_have_their_limits_and_names(self):
        _, _, server = run_with(normal_answers())
        self.assertEqual(server.calls[0][1:], (provider.MAX_INDEX_BYTES, "the index of the current release"))
        self.assertEqual(server.calls[1][1:], (provider.MAX_HASH_FILE_BYTES, "the hash file"))

    def failing(self, answers):
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "fetch_text", side_effect=Server(answers)):
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        for key in ("url", "version", "expected_sha256"):
            self.assertNotIn(key, processor.env)
        return str(caught.exception)

    def test_an_index_that_is_not_what_is_expected_is_an_error_and_sets_no_output(self):
        for page in ("", "<html>Maintenance</html>", index_of("vlc-3.0.21-win64.exe"),
                     index_of("vlc-3.0.9-win64.msi", "vlc-3.0.21-win64.msi")):
            with self.subTest(page=page[:30]):
                self.assertIn("VideoLAN index:", self.failing({INDEX_URL: page}))

    def test_a_hash_file_that_is_not_what_is_expected_is_an_error_and_sets_no_output(self):
        name = "vlc-3.0.21-win64.msi"
        address = "https://download.videolan.org/vlc/3.0.21/win64/%s.sha256" % name
        for text in ("", "<html>Not Found</html>", hash_line(name="vlc-3.0.21-win64.exe"), hash_line(gap=" "),
                     hash_line() + hash_line(HEX_B)):
            answers = normal_answers()
            answers[address] = text
            with self.subTest(text=text[:30]):
                self.assertIn("VideoLAN hash file:", self.failing(answers))

    def test_a_failure_of_the_second_request_does_not_leave_a_half_answer(self):
        answers = normal_answers()
        answers["https://download.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.msi.sha256"] = ProcessorError("the server said no")
        self.assertIn("the server said no", self.failing(answers))

    def test_a_failure_of_the_first_request_asks_for_nothing_more(self):
        server = Server({INDEX_URL: ProcessorError("the server said no")})
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "fetch_text", side_effect=server):
            with self.assertRaises(ProcessorError):
                processor.main()
        self.assertEqual(len(server.calls), 1)


class FetchTests(unittest.TestCase):
    URL = provider.BASE_URL + "last/win64/"

    def fetch_with(self, body=None, error=None, url=None, max_bytes=1000):
        def opener(request):
            self.request = request
            if error is not None:
                raise error
            return FakeResponse(body)
        with mock.patch.object(provider, "open_request", side_effect=opener):
            return provider.fetch_text(url or self.URL, max_bytes, "the thing")

    def test_the_text_is_returned_and_the_request_is_plain(self):
        text = self.fetch_with(body="café".encode("utf-8"))
        self.assertEqual(text, "café")
        self.assertEqual(self.request.full_url, self.URL)
        self.assertEqual(self.request.get_header("User-agent"), provider.USER_AGENT)
        self.assertIsNone(self.request.data)
        self.assertFalse(self.request.has_header("Authorization"))

    def test_an_address_outside_the_fixed_host_is_refused_before_any_request(self):
        for url in ("https://example.test/vlc/last/win64/", "http://download.videolan.org/vlc/last/win64/",
                    "https://get.videolan.org/vlc/last/win64/",
                    "https://get.videolan.org/vlc/3.0.24/win64/vlc-3.0.24-win64.msi.sha256",
                    "https://download.videolan.org.example.test/vlc/", "https://download.videolan.org/other/",
                    "https://download.videolan.org@example.test/vlc/", ""):
            with self.subTest(url=url):
                with mock.patch.object(provider, "open_request") as opener:
                    with self.assertRaises(ProcessorError) as caught:
                        provider.fetch_text(url, 1000, "the thing")
                opener.assert_not_called()
                self.assertIn("outside", str(caught.exception))

    def test_a_status_other_than_200_is_an_error_that_names_it(self):
        for code, reason in ((404, "Not Found"), (500, "Server Error"), (429, "Too Many Requests")):
            error = urllib.error.HTTPError(self.URL, code, reason, {}, io.BytesIO(b""))
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error)
                self.assertIn("answered %d" % code, str(caught.exception))
                self.assertIn("the thing", str(caught.exception))
                self.assertNotIn("redirect", str(caught.exception))

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

    def test_the_real_opener_is_built_with_the_redirect_refusing_handler(self):
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
                self.assertIn("could not be asked for the thing", str(caught.exception))

    def test_an_answer_larger_than_the_limit_is_an_error(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(body=b"x" * 1001)
        self.assertIn("larger than 1000 bytes", str(caught.exception))

    def test_an_answer_of_exactly_the_limit_is_accepted(self):
        self.assertEqual(len(self.fetch_with(body=b"x" * 1000)), 1000)

    def test_an_answer_that_is_not_utf_8_is_an_error(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(body=b"\xff\xfe\x00bad")
        self.assertIn("not UTF-8", str(caught.exception))

    def test_the_limits_are_sensible(self):
        self.assertGreaterEqual(provider.MAX_INDEX_BYTES, 256 * 1024)
        self.assertLessEqual(provider.MAX_INDEX_BYTES, 8 * 1024 * 1024)
        self.assertGreaterEqual(provider.MAX_HASH_FILE_BYTES, 1024)
        self.assertLessEqual(provider.MAX_HASH_FILE_BYTES, 1024 * 1024)
        self.assertGreater(provider.FETCH_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(provider.FETCH_TIMEOUT_SECONDS, 600)


if __name__ == "__main__":
    unittest.main()
