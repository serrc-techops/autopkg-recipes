"""Tests of LibreOfficeInfoProvider: every branch. No test uses the network:
fetch_text() or open_request() is replaced.

The index (stable_index_excerpt.html) is a copy of the real index of 2026-10-02,
with one comment line added at the top and no hash in it. Every other page, and
every hash file, is WRITTEN BY HAND: the hash file's name, path and format were
NOT read on the real server (the one answer it gave on 2026-10-02 was a 404), and
its lines are built in this file from made-up hashes. These tests prove what the
parser does with such pages. They prove nothing about what the vendor's server
really sends for a hash file: the first run on the build Mac is that check.
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

import LibreOfficeInfoProvider as provider  # noqa: E402

PROVIDER = provider.LibreOfficeInfoProvider
EXCERPT = os.path.join(TESTS_DIR, "stable_index_excerpt.html")
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
# Texts that the hygiene test would read as an address if they stood in this file as they are.
FOUR_NUMBERS = ".".join(["25", "8", "1", "2"])
INDEX = provider.INDEX_URL


def msi_name(version):
    return "LibreOffice_%s_Win_x86-64.msi" % version


def hash_file(version, sha=HEX_A, name=None, ending="\n"):
    """A hash file in the format the writer knows: 64 hex digits, two spaces,
    the file name, one line. WRITTEN BY HAND, not saved from the server."""
    return "%s  %s%s" % (sha, name if name is not None else msi_name(version), ending)


def index_of(*names, extra=""):
    """An index page in the layout the writer knows, with the given link texts.
    WRITTEN BY HAND."""
    links = "\n".join('<a href="%s">%s</a>   2026-01-01 10:00    -' % (name, name) for name in names)
    return ('<html><head><title>Index of /libreoffice/stable</title></head><body><h1>Index of /libreoffice/stable</h1>'
            '<pre><a href="?C=N;O=D">Name</a>\n<hr><a href="/libreoffice/">Parent Directory</a>\n%s\n%s</pre>'
            '</body></html>' % (links, extra))


class FakeServer:
    """Answers fetch_text() for the index and for the hash files of versions."""

    def __init__(self, index, hashes=None):
        self.index = index
        self.hashes = hashes or {}
        self.calls = []

    def __call__(self, url, max_bytes, what):
        self.calls.append((url, max_bytes, what))
        if url == provider.INDEX_URL:
            return self.index
        if url in self.hashes:
            return self.hashes[url]
        raise ProcessorError("The server answered 404 Not Found for %s." % what)


def run_on(index, hashes, env=None):
    """Run the processor against the fake server. Returns (processor, messages, server)."""
    server = FakeServer(index, hashes)
    with mock.patch.object(provider, "fetch_text", side_effect=server):
        processor, messages = run_processor(PROVIDER, env or {})
    return processor, messages, server


def hashes_for(*pairs):
    return {provider.hash_url(version): hash_file(version, sha) for version, sha in pairs}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ExcerptTests(unittest.TestCase):
    """The copy of the real index of 2026-10-02. The hash files used with it are made up."""

    VERSIONS = ["25.8.7", "26.2.5", "26.2.6", "26.8.0", "26.8.1"]

    def setUp(self):
        with open(EXCERPT, "r", encoding="utf-8") as handle:
            self.page = handle.read()

    def test_the_first_line_says_that_it_is_a_copy_of_the_real_index(self):
        self.assertEqual(
            self.page.splitlines()[0],
            "<!-- A copy of the real index of 2026-10-02 (download.documentfoundation.org/libreoffice/stable/), "
            "no hash in it. Only this first line was added. -->",
        )

    def test_the_excerpt_is_small_and_holds_no_hash(self):
        self.assertLess(len(self.page), 20000)
        self.assertNotRegex(self.page, r"(?i)\b[0-9a-f]{64}\b")

    def test_the_versions_are_the_five_folders_and_no_other_link(self):
        """The page also links to the sort columns, the parent folder, the style sheet,
        a mailto and two sites: none of them is a version folder."""
        self.assertEqual(provider.extract_versions(self.page), self.VERSIONS)
        for other in ("?C=N;O=D", 'href="/libreoffice/"', "/mirrorbrain.css", "mailto:", "http://mirrorbrain.org/"):
            self.assertIn(other, self.page)

    def test_three_lines_at_once_with_two_versions_in_two_of_them(self):
        keys = [provider.release_key(v) for v in self.VERSIONS]
        self.assertEqual(sorted({key[:2] for key in keys}), [(25, 8), (26, 2), (26, 8)])
        self.assertEqual(len(keys), 5)

    def test_fresh_is_the_highest_version_of_the_highest_line_and_still_the_next_lower_line(self):
        versions = provider.extract_versions(self.page)
        self.assertEqual(provider.choose_version(versions, "fresh"), "26.8.1")
        self.assertEqual(provider.choose_version(versions, "still"), "26.2.6")

    def test_the_addresses_of_the_fresh_version(self):
        self.assertEqual(
            provider.file_url("26.8.1"),
            "https://download.documentfoundation.org/libreoffice/stable/26.8.1/win/x86_64/"
            "LibreOffice_26.8.1_Win_x86-64.msi",
        )
        self.assertEqual(provider.hash_url("26.8.1"), provider.file_url("26.8.1") + ".sha256")
        self.assertEqual(provider.expected_file_name("26.8.1"), "LibreOffice_26.8.1_Win_x86-64.msi")

    def test_the_processor_gives_url_version_and_hash_for_fresh(self):
        hashes = hashes_for(("26.8.1", HEX_A), ("26.2.6", HEX_B))
        processor, messages, server = run_on(self.page, hashes)
        self.assertEqual(processor.env["version"], "26.8.1")
        self.assertEqual(
            processor.env["url"],
            "https://download.documentfoundation.org/libreoffice/stable/26.8.1/win/x86_64/"
            "LibreOffice_26.8.1_Win_x86-64.msi",
        )
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertTrue(any("26.8.1" in m for m in messages))
        self.assertTrue(any(HEX_A in m for m in messages))
        self.assertEqual([call[0] for call in server.calls],
                         [provider.INDEX_URL, provider.hash_url("26.8.1")])

    def test_the_processor_gives_the_next_lower_line_for_still(self):
        hashes = hashes_for(("26.8.1", HEX_A), ("26.2.6", HEX_B))
        processor, _, server = run_on(self.page, hashes, {"libreoffice_line": "still"})
        self.assertEqual(processor.env["version"], "26.2.6")
        self.assertEqual(processor.env["expected_sha256"], HEX_B)
        self.assertTrue(processor.env["url"].endswith("/26.2.6/win/x86_64/LibreOffice_26.2.6_Win_x86-64.msi"))
        self.assertEqual([call[0] for call in server.calls],
                         [provider.INDEX_URL, provider.hash_url("26.2.6")])


class ReleaseKeyTests(unittest.TestCase):
    def test_three_numbers_are_compared_as_numbers(self):
        self.assertGreater(provider.release_key("25.10.0"), provider.release_key("25.8.1"))
        self.assertGreater(provider.release_key("25.8.10"), provider.release_key("25.8.9"))
        self.assertGreater(provider.release_key("100.0.0"), provider.release_key("25.8.1"))
        self.assertEqual(provider.release_key("25.8.1"), (25, 8, 1))
        self.assertEqual(provider.release_key("25.0.0"), (25, 0, 0))

    def test_anything_else_is_not_a_version(self):
        for value in ("25.8", FOUR_NUMBERS, "25.8.1rc1", "25.8.x", "v25.8.1", "", " 25.8.1", "25.8.1\n",
                      "25.8.-1", "025.8.1", "25.08.1", "25.8.01", "٢٥.٨.١", "25.8.1/", None, 25,
                      ["25.8.1"]):
            with self.subTest(value=value):
                self.assertIsNone(provider.release_key(value))


class ExtractVersionsTests(unittest.TestCase):
    def test_the_version_folders_are_read_and_sorted_by_their_numbers(self):
        page = index_of("25.8.1/", "25.2.6/", "25.10.0/", "9.9.9/")
        self.assertEqual(provider.extract_versions(page), ["9.9.9", "25.2.6", "25.8.1", "25.10.0"])

    def test_a_folder_that_is_listed_twice_counts_once(self):
        self.assertEqual(provider.extract_versions(index_of("25.8.1/", "25.8.1/")), ["25.8.1"])

    def test_other_links_are_ignored(self):
        page = index_of("25.8.1/", "README", "testing/", "latest/", "25.8.1", "25.8.2.tar.gz", "25.2/", FOUR_NUMBERS + "/",
                        "025.8.1/", "25.8.1//", "../25.9.0/", "/libreoffice/stable/25.9.0/", "25.8.1/ ",
                        "http://example.test/25.9.0/")
        self.assertEqual(provider.extract_versions(page), ["25.8.1"])

    def test_the_text_of_a_link_is_not_read_only_its_address(self):
        page = '<a href="testing/">25.9.0/</a><a href="25.8.1/">next</a>'
        self.assertEqual(provider.extract_versions(page), ["25.8.1"])

    def test_the_link_may_have_other_attributes_and_any_letter_case(self):
        page = '<A CLASS="x" HREF="25.8.1/">25.8.1/</A>\n<a\n  title="t"\n  href="25.2.6/">25.2.6/</a>'
        self.assertEqual(provider.extract_versions(page), ["25.2.6", "25.8.1"])

    def test_a_page_without_a_version_folder_is_refused(self):
        for text in ("", "<html></html>", "not html at all", index_of("README", "testing/"),
                     "Maintenance 25.8.1/", "<a>25.8.1/</a>", "<a href='25.8.1/'>x</a>"):
            with self.subTest(text=text[:40]):
                with self.assertRaises(ValueError) as caught:
                    provider.extract_versions(text)
                self.assertIn("no link to a version folder", str(caught.exception))


class ChooseVersionTests(unittest.TestCase):
    def test_fresh_and_still_with_two_lines(self):
        versions = ["25.2.6", "25.8.1"]
        self.assertEqual(provider.choose_version(versions, "fresh"), "25.8.1")
        self.assertEqual(provider.choose_version(versions, "still"), "25.2.6")

    def test_the_order_of_the_list_does_not_matter(self):
        self.assertEqual(provider.choose_version(["25.8.1", "25.2.6"], "fresh"), "25.8.1")
        self.assertEqual(provider.choose_version(["25.8.1", "25.2.6"], "still"), "25.2.6")

    def test_lines_are_compared_by_numbers_not_by_text(self):
        versions = ["25.8.1", "25.10.0", "9.1.0"]
        self.assertEqual(provider.choose_version(versions, "fresh"), "25.10.0")
        self.assertEqual(provider.choose_version(versions, "still"), "25.8.1")

    def test_a_major_number_with_more_digits_is_higher(self):
        self.assertEqual(provider.choose_version(["9.9.9", "10.0.0"], "fresh"), "10.0.0")

    def test_the_highest_version_of_a_line_is_taken_and_two_versions_of_a_line_are_one_line(self):
        versions = ["25.8.1", "25.8.10", "25.8.9", "25.2.6", "25.2.12"]
        self.assertEqual(provider.choose_version(versions, "fresh"), "25.8.10")
        self.assertEqual(provider.choose_version(versions, "still"), "25.2.12")

    def test_three_lines_give_the_highest_and_the_middle_one(self):
        versions = ["24.8.7", "25.2.6", "25.8.1"]
        self.assertEqual(provider.choose_version(versions, "fresh"), "25.8.1")
        self.assertEqual(provider.choose_version(versions, "still"), "25.2.6")

    def test_one_line_has_no_still_and_there_is_no_fall_back_to_fresh(self):
        with self.assertRaises(ValueError) as caught:
            provider.choose_version(["25.8.1", "25.8.0"], "still")
        self.assertIn("no still line", str(caught.exception))
        self.assertEqual(provider.choose_version(["25.8.1", "25.8.0"], "fresh"), "25.8.1")

    def test_no_version_at_all_is_an_error_for_both_lines(self):
        for choice in ("fresh", "still"):
            with self.subTest(choice=choice):
                with self.assertRaises(ValueError):
                    provider.choose_version([], choice)

    def test_another_line_name_is_an_error(self):
        for choice in ("", "Fresh", "STILL", "latest", "25.8", None, 1, " fresh"):
            with self.subTest(choice=choice):
                with self.assertRaises(ValueError) as caught:
                    provider.choose_version(["25.2.6", "25.8.1"], choice)
                self.assertIn("fresh, still", str(caught.exception))

    def test_a_version_that_is_not_three_numbers_is_an_error(self):
        with self.assertRaises(ValueError):
            provider.choose_version(["25.8.1", "25.8"], "fresh")


class FileNameTests(unittest.TestCase):
    def test_the_name_and_the_addresses(self):
        self.assertEqual(provider.expected_file_name("25.8.1"), "LibreOffice_25.8.1_Win_x86-64.msi")
        self.assertEqual(
            provider.file_url("25.8.1"),
            "https://download.documentfoundation.org/libreoffice/stable/25.8.1/win/x86_64/"
            "LibreOffice_25.8.1_Win_x86-64.msi",
        )
        self.assertEqual(provider.hash_url("25.8.1"), provider.file_url("25.8.1") + ".sha256")

    def test_every_address_is_under_the_fixed_prefix(self):
        for version in ("25.8.1", "9.0.0", "100.20.300"):
            self.assertTrue(provider.file_url(version).startswith(provider.ALLOWED_PREFIX))
            self.assertTrue(provider.hash_url(version).startswith(provider.ALLOWED_PREFIX))

    def test_a_text_that_is_not_a_version_gives_no_name_and_no_address(self):
        for value in ("25.8", "../1.1.1", "25.8.1/../../x", "25.8.1 ", "", None, "25.8.1?a=1", "25.8.1#x"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    provider.expected_file_name(value)
                with self.assertRaises(ValueError):
                    provider.file_url(value)
                with self.assertRaises(ValueError):
                    provider.hash_url(value)


class ParseHashFileTests(unittest.TestCase):
    """The format of the hash file is the writer's knowledge: one line, 64 hex
    digits, two spaces, the file name."""

    def test_the_line_is_read(self):
        self.assertEqual(provider.parse_hash_file(hash_file("25.8.1", HEX_A), "25.8.1"), HEX_A)

    def test_the_hash_is_returned_in_lower_case(self):
        self.assertEqual(provider.parse_hash_file(hash_file("25.8.1", HEX_A.upper()), "25.8.1"), HEX_A)

    def test_a_missing_final_new_line_and_a_windows_line_end_are_fine(self):
        for ending in ("", "\n", "\r\n", "\n\n", "\n \n"):
            with self.subTest(ending=repr(ending)):
                self.assertEqual(provider.parse_hash_file(hash_file("25.8.1", HEX_B, ending=ending), "25.8.1"), HEX_B)

    def test_no_line_or_two_lines_are_refused(self):
        line = hash_file("25.8.1", HEX_A, ending="")
        for text in ("", "\n", "  \n", line + "\n" + line, line + "\n" + hash_file("25.8.1", HEX_B, ending="")):
            with self.subTest(text=text[:20]):
                with self.assertRaises(ValueError) as caught:
                    provider.parse_hash_file(text, "25.8.1")
                self.assertIn("not exactly one", str(caught.exception))

    def test_a_line_that_is_not_hash_two_spaces_name_is_refused(self):
        name = msi_name("25.8.1")
        bad = [
            HEX_A[:-1] + "  " + name,           # 63 digits
            HEX_A + "0  " + name,               # 65 digits
            "g" + HEX_A[1:] + "  " + name,      # not hex
            HEX_A + " " + name,                 # one space
            HEX_A + "   " + name,               # three spaces
            HEX_A + " *" + name,                # the binary-mode marker
            HEX_A + "\t" + name,                # a tab
            HEX_A,                              # no name
            " " + HEX_A + "  " + name,          # leading space
            HEX_A + "  " + name + " ",          # trailing space
            "sha256:" + HEX_A + "  " + name,    # a prefix
            "SHA256 (" + name + ") = " + HEX_A, # another tool's format
            name + "  " + HEX_A,                # reversed
            HEX_A + "  " + name + " x",         # more after the name
            "٠" * 64 + "  " + name,             # other digits
        ]
        for text in bad:
            with self.subTest(text=text[:30]):
                with self.assertRaises(ValueError):
                    provider.parse_hash_file(text + "\n", "25.8.1")

    def test_a_name_that_is_not_the_msi_of_this_version_is_refused(self):
        wrong = [
            msi_name("25.2.6"),                                     # another version
            "LibreOffice_25.8.1_Win_x86-64_langpack_de.msi",       # another file
            "LibreOffice_25.8.1_Win_x86-64_helppack_de.msi",
            "LibreOffice_25.8.1_Win_x86.msi",                      # 32-bit
            "LibreOffice_25.8.1_Win_x86-64.msi.asc",
            "libreoffice_25.8.1_win_x86-64.msi",                   # letter case
            "win/x86_64/" + msi_name("25.8.1"),                     # a path
            "../" + msi_name("25.8.1"),
            "LibreOffice_25.8.1_Win_x86-64.exe",
            "LibreOffice_25.8.1_Win_x86-64.msi:stream",
        ]
        for name in wrong:
            with self.subTest(name=name):
                with self.assertRaises(ValueError) as caught:
                    provider.parse_hash_file(hash_file("25.8.1", HEX_A, name=name), "25.8.1")
                self.assertIn("not the expected", str(caught.exception))

    def test_a_version_that_is_not_three_numbers_is_refused(self):
        with self.assertRaises(ValueError):
            provider.parse_hash_file(hash_file("25.8.1", HEX_A), "25.8")


class MainTests(unittest.TestCase):
    INDEX = index_of("25.2.6/", "25.8.1/")
    HASHES = hashes_for(("25.8.1", HEX_A), ("25.2.6", HEX_B))

    def test_the_default_is_the_fresh_line(self):
        processor, _, _ = run_on(self.INDEX, self.HASHES)
        self.assertEqual(processor.env["version"], "25.8.1")
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertTrue(processor.env["url"].endswith(".msi"))

    def test_the_declared_defaults_equal_the_values_the_code_uses(self):
        declared = {name: flags["default"] for name, flags in PROVIDER.input_variables.items()}
        self.assertEqual(declared, {"libreoffice_line": "fresh"})
        for flags in PROVIDER.input_variables.values():
            self.assertIs(flags["required"], False)
        self.assertEqual(sorted(PROVIDER.output_variables), ["expected_sha256", "url", "version"])

    def test_the_input_chooses_the_line(self):
        processor, _, _ = run_on(self.INDEX, self.HASHES, {"libreoffice_line": "still"})
        self.assertEqual(processor.env["expected_sha256"], HEX_B)
        processor, _, _ = run_on(self.INDEX, self.HASHES, {"libreoffice_line": "fresh"})
        self.assertEqual(processor.env["expected_sha256"], HEX_A)

    def test_white_space_around_the_input_is_ignored(self):
        processor, _, _ = run_on(self.INDEX, self.HASHES, {"libreoffice_line": " still\n"})
        self.assertEqual(processor.env["version"], "25.2.6")

    def test_an_input_that_is_not_one_of_the_two_lines_is_an_error_and_nothing_is_fetched(self):
        for value in ("", "  ", "Fresh", "latest", "25.8", None, 7, ["fresh"], True):
            processor, _ = new_processor(PROVIDER, {"libreoffice_line": value})
            with self.subTest(value=value):
                with mock.patch.object(provider, "fetch_text") as fetch:
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                fetch.assert_not_called()
                self.assertIn("libreoffice_line", str(caught.exception))

    def test_the_hash_file_of_the_chosen_version_only_is_fetched(self):
        _, _, server = run_on(self.INDEX, self.HASHES)
        urls = [call[0] for call in server.calls]
        self.assertEqual(urls, [provider.INDEX_URL, provider.hash_url("25.8.1")])
        self.assertEqual(server.calls[0][1:], (provider.MAX_INDEX_BYTES, "the index"))
        self.assertEqual(server.calls[1][1:], (provider.MAX_HASH_FILE_BYTES, "the hash file"))

    def test_no_output_is_set_when_the_run_fails(self):
        cases = [
            (index_of("README"), self.HASHES, "LibreOffice download index"),
            (index_of("25.8.1/"), self.HASHES, "no still line"),
            (self.INDEX, {provider.hash_url("25.8.1"): "not a hash line\n"}, "LibreOffice hash file"),
            (self.INDEX, {provider.hash_url("25.8.1"): hash_file("25.8.1", HEX_A, name=msi_name("25.2.6"))},
             "LibreOffice hash file"),
            (self.INDEX, {provider.hash_url("25.8.1"): ""}, "LibreOffice hash file"),
        ]
        for index, hashes, expected in cases:
            env = {"libreoffice_line": "still"} if "no still line" in expected else {}
            processor, _ = new_processor(PROVIDER, env)
            server = FakeServer(index, hashes)
            with self.subTest(expected=expected, index=index[:30]):
                with mock.patch.object(provider, "fetch_text", side_effect=server):
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                for key in ("url", "version", "expected_sha256"):
                    self.assertNotIn(key, processor.env)
                self.assertIn(expected, str(caught.exception))

    def test_a_hash_file_that_cannot_be_fetched_stops_the_run_and_sets_nothing(self):
        processor, _ = new_processor(PROVIDER, {})
        server = FakeServer(self.INDEX, {})
        with mock.patch.object(provider, "fetch_text", side_effect=server):
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        self.assertIn("404", str(caught.exception))
        self.assertNotIn("url", processor.env)

    def test_a_page_that_is_not_what_is_expected_is_a_processor_error(self):
        for page in ("", "<html><body>Maintenance</body></html>", "{}", "25.8.1/"):
            processor, _ = new_processor(PROVIDER, {})
            with mock.patch.object(provider, "fetch_text", return_value=page):
                with self.subTest(page=page[:30]):
                    with self.assertRaises(ProcessorError):
                        processor.main()

    def test_the_url_is_in_the_versioned_folder_not_a_moving_one(self):
        processor, _, _ = run_on(self.INDEX, self.HASHES)
        self.assertIn("/25.8.1/win/x86_64/", processor.env["url"])
        self.assertEqual(processor.env["url"].rsplit("/", 1)[-1], "LibreOffice_25.8.1_Win_x86-64.msi")
        self.assertEqual(processor.env["url"], provider.file_url(processor.env["version"]))

    def test_the_provider_follows_the_numbers_when_the_text_order_would_be_wrong(self):
        index = index_of("25.8.1/", "25.10.0/")
        hashes = hashes_for(("25.10.0", HEX_C), ("25.8.1", HEX_A))
        processor, _, _ = run_on(index, hashes)
        self.assertEqual(processor.env["version"], "25.10.0")
        self.assertEqual(processor.env["expected_sha256"], HEX_C)
        processor, _, _ = run_on(index, hashes, {"libreoffice_line": "still"})
        self.assertEqual(processor.env["version"], "25.8.1")


class FetchTests(unittest.TestCase):
    def fetch_with(self, body=None, error=None, url=provider.INDEX_URL, max_bytes=provider.MAX_INDEX_BYTES,
                   what="the index"):
        def opener(request):
            self.request = request
            if error is not None:
                raise error
            return FakeResponse(body)
        with mock.patch.object(provider, "open_request", side_effect=opener):
            return provider.fetch_text(url, max_bytes, what)

    def test_the_text_is_returned_and_the_request_is_plain(self):
        text = self.fetch_with(body="café page".encode("utf-8"))
        self.assertEqual(text, "café page")
        self.assertEqual(self.request.full_url, "https://download.documentfoundation.org/libreoffice/stable/")
        self.assertEqual(self.request.get_header("User-agent"), provider.USER_AGENT)
        self.assertIsNone(self.request.data)
        self.assertFalse(self.request.has_header("Authorization"))

    def test_an_address_outside_the_fixed_prefix_is_refused_before_any_request(self):
        for url in ("https://example.test/libreoffice/stable/", "http://download.documentfoundation.org/libreoffice/stable/",
                    "https://download.documentfoundation.org/libreoffice/", "https://download.documentfoundation.org.example.test/libreoffice/stable/",
                    "https://download.documentfoundation.org@example.test/libreoffice/stable/",
                    "ftp://download.documentfoundation.org/libreoffice/stable/", "", None, 5):
            with self.subTest(url=url):
                with mock.patch.object(provider, "open_request") as opener:
                    with self.assertRaises(ProcessorError) as caught:
                        provider.fetch_text(url, 100, "the index")
                opener.assert_not_called()
                self.assertIn("is not under", str(caught.exception))

    def test_a_status_other_than_200_is_an_error_that_names_it(self):
        for code, reason in ((404, "Not Found"), (500, "Server Error"), (429, "Too Many Requests")):
            error = urllib.error.HTTPError(provider.INDEX_URL, code, reason, {}, io.BytesIO(b""))
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error)
                self.assertIn("answered %d" % code, str(caught.exception))
                self.assertIn("the index", str(caught.exception))
                self.assertNotIn("redirect", str(caught.exception))

    def test_a_redirect_is_an_error_that_says_so_and_tells_the_owner(self):
        for code in (301, 302, 307, 308):
            error = urllib.error.HTTPError(provider.hash_url("25.8.1"), code, "Moved", {}, io.BytesIO(b""))
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error, url=provider.hash_url("25.8.1"),
                                    max_bytes=provider.MAX_HASH_FILE_BYTES, what="the hash file")
                message = str(caught.exception)
                self.assertIn("answered %d" % code, message)
                self.assertIn("the hash file", message)
                self.assertIn("a redirect is not followed", message)
                self.assertIn("a hash read from a mirror is not the publisher's", message)
                self.assertIn("tell the owner", message)

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
                self.assertIn("could not be fetched", str(caught.exception))
                self.assertTrue(str(caught.exception).startswith("The index"))

    def test_a_page_larger_than_the_limit_is_an_error(self):
        body = b"x" * (provider.MAX_INDEX_BYTES + 1)
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(body=body)
        self.assertIn("larger than", str(caught.exception))

    def test_a_page_of_exactly_the_limit_is_accepted(self):
        self.assertEqual(len(self.fetch_with(body=b"x" * provider.MAX_INDEX_BYTES)), provider.MAX_INDEX_BYTES)

    def test_the_read_never_asks_for_more_than_the_limit_plus_one(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"ok"
        with mock.patch.object(provider, "open_request", return_value=response):
            provider.fetch_text(provider.INDEX_URL, 100, "the index")
        response.read.assert_called_once_with(101)

    def test_a_hash_file_larger_than_its_small_limit_is_an_error(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(body=b"x" * (provider.MAX_HASH_FILE_BYTES + 1), url=provider.hash_url("25.8.1"),
                            max_bytes=provider.MAX_HASH_FILE_BYTES, what="the hash file")
        self.assertIn("The hash file is larger than", str(caught.exception))

    def test_a_page_that_is_not_utf_8_is_an_error(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(body=b"\xff\xfe\x00bad")
        self.assertIn("not UTF-8", str(caught.exception))

    def test_the_constants_are_the_vendors_address_over_https(self):
        self.assertEqual(provider.INDEX_URL, "https://download.documentfoundation.org/libreoffice/stable/")
        self.assertTrue(provider.INDEX_URL.endswith("/"))
        self.assertEqual(provider.ALLOWED_PREFIX, provider.INDEX_URL)

    def test_the_limits_are_sensible(self):
        self.assertGreater(provider.MAX_INDEX_BYTES, 64 * 1024)
        self.assertLess(provider.MAX_HASH_FILE_BYTES, 64 * 1024)
        self.assertGreater(provider.MAX_HASH_FILE_BYTES, 512)
        self.assertGreater(provider.FETCH_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(provider.FETCH_TIMEOUT_SECONDS, 600)


if __name__ == "__main__":
    unittest.main()
