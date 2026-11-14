"""Tests of BlenderInfoProvider: every branch. No test uses the network:
fetch_text() or open_request() is replaced.

release_index.html is a copy of the real index of 2026-11-13 and
series_5.3_listing.html a copy of the real listing of the folder Blender5.3/ of
the same day, each with one comment line added at the top; neither holds a hash.
The hash file of 5.3.0 was read on 2026-11-13: REAL_HASH_FILE_NAMES are its eight
file names in its order, but the hashes in these tests are made up here (the
folder must hold no SHA-256). Every other page is WRITTEN BY HAND. These tests
prove what the parser does with such pages; the first run on the build Mac is
the check of what the server sends then.
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

import BlenderInfoProvider as provider  # noqa: E402

PROVIDER = provider.BlenderInfoProvider
INDEX_COPY = os.path.join(TESTS_DIR, "release_index.html")
LISTING_COPY = os.path.join(TESTS_DIR, "series_5.3_listing.html")
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
# Texts that the hygiene test would read as an address if they stood in this file as they are.
FOUR_NUMBERS = ".".join(["5", "3", "0", "1"])
# The file names of the real blender-5.3.0.sha256 (2026-11-13), in its order.
REAL_HASH_FILE_NAMES = [
    "blender-5.3.0-macos-arm64.dmg",
    "blender-5.3.0-linux-x64.tar.xz",
    "blender-5.3.0-windows-x64.msi",
    "blender-5.3.0-windows-x64.msix",
    "blender-5.3.0-windows-x64.zip",
    "blender-5.3.0-windows-arm64.msi",
    "blender-5.3.0-windows-arm64.msix",
    "blender-5.3.0-windows-arm64.zip",
]


def msi_name(version):
    return "blender-%s-windows-x64.msi" % version


def made_up_hash(number):
    return ("%x" % (number + 1)) * 64


def hash_file(version, msi_sha=HEX_A, others=True, ending="\n"):
    """A hash file of the real file's shape: one line per file of the version,
    64 hex digits, two spaces, the file name. The hashes are MADE UP."""
    lines = []
    for number, name in enumerate(REAL_HASH_FILE_NAMES):
        name = name.replace("5.3.0", version)
        if name == msi_name(version):
            lines.append("%s  %s" % (msi_sha, name))
        elif others:
            lines.append("%s  %s" % (made_up_hash(number)[:64], name))
    return "\n".join(lines) + ending


def index_of(*names):
    """An index page in the layout of the real one, with the given link texts. WRITTEN BY HAND."""
    links = "\n".join('<a href="%s">%s</a>         10-Nov-2026 09:00       -' % (name, name) for name in names)
    return ('<html>\n<head><title>Index of /release/</title></head>\n<body>\n<h1>Index of /release/</h1>'
            '<hr><pre><a href="../">../</a>\n%s\n</pre><hr></body>\n</html>\n' % links)


def listing_of(*versions, extra=()):
    """A series folder's listing with the x64 MSI and the hash file of each version. WRITTEN BY HAND."""
    names = []
    for version in versions:
        names += [msi_name(version), "blender-%s-windows-arm64.msi" % version, "blender-%s.sha256" % version]
    return index_of(*(names + list(extra)))


class FakeServer:
    """Answers fetch_text() for the index, series folders and hash files."""

    def __init__(self, index, folders=None, hashes=None):
        self.index = index
        self.folders = folders or {}
        self.hashes = hashes or {}
        self.calls = []

    def __call__(self, url, max_bytes, what):
        self.calls.append((url, max_bytes, what))
        if url == provider.INDEX_URL:
            return self.index
        for series, text in self.folders.items():
            if url == provider.series_url(series):
                return text
        if url in self.hashes:
            return self.hashes[url]
        raise ProcessorError("The server answered 404 Not Found for %s." % what)


def run_on(server, env=None):
    with mock.patch.object(provider, "fetch_text", side_effect=server):
        processor, messages = run_processor(PROVIDER, env or {})
    return processor, messages


def hashes_for(*pairs):
    return {provider.hash_url(version): hash_file(version, sha) for version, sha in pairs}


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class RealCopiesTests(unittest.TestCase):
    """The copies of the real pages of 2026-11-13. The hashes used with them are made up."""

    def setUp(self):
        with open(INDEX_COPY, "r", encoding="utf-8") as handle:
            self.index = handle.read()
        with open(LISTING_COPY, "r", encoding="utf-8") as handle:
            self.listing = handle.read()

    def test_the_first_lines_say_that_they_are_copies(self):
        self.assertEqual(
            self.index.splitlines()[0],
            "<!-- A copy of the real index of 2026-11-13 (download.blender.org/release/), "
            "no hash in it. Only this first line was added. -->")
        self.assertEqual(
            self.listing.splitlines()[0],
            "<!-- A copy of the real listing of 2026-11-13 (download.blender.org/release/Blender5.3/), "
            "no hash in it. Only this first line was added. -->")

    def test_the_copies_are_small_and_hold_no_hash(self):
        for page in (self.index, self.listing):
            self.assertLess(len(page), 20000)
            self.assertNotRegex(page, r"(?i)\b[0-9a-f]{64}\b")

    def test_the_series_of_the_real_index(self):
        series = provider.extract_series(self.index)
        self.assertEqual(series[-1], "5.3")
        self.assertEqual(series[-6:], ["4.4", "4.5", "5.0", "5.1", "5.2", "5.3"])
        for ignored in ("2.28a", "2.50alpha", "2.27-newpy", "2.04", "2.56abeta"):
            self.assertNotIn(ignored, series)
        for other in ('href="Blender2.28a/"', 'href="BlenderBenchmark2.0/"', 'href="Blender2.27-newpy/"',
                      'href="Publisher2.25/"', 'href="plugin/"', 'href="GPL-license.txt"', 'href="trace"'):
            self.assertIn(other, self.index)

    def test_the_real_index_has_92_links_that_begin_with_blender_and_74_series_folders_it_accepts(self):
        self.assertEqual(self.index.count('href="Blender'), 92)
        self.assertEqual(len(provider.extract_series(self.index)), 74)  # Blender2.04/ has a leading zero
        self.assertIn('href="Blender2.04/"', self.index)

    def test_the_real_listing_has_one_x64_msi(self):
        self.assertEqual(provider.msi_versions(self.listing, "5.3"), ["5.3.0"])
        for other in ("blender-5.3.0-windows-arm64.msi", "blender-5.3.0-windows-x64.msix",
                      "blender-5.3.0-windows-x64.zip", "blender-5.3.0.sha256", "blender-5.3.0.md5"):
            self.assertIn('href="%s"' % other, self.listing)
        self.assertIn("383557632", self.listing)

    def test_the_processor_reads_the_real_pages_with_three_requests(self):
        server = FakeServer(self.index, {"5.3": self.listing}, hashes_for(("5.3.0", HEX_A)))
        processor, messages = run_on(server)
        self.assertEqual(processor.env["version"], "5.3.0")
        self.assertEqual(processor.env["url"],
                         "https://download.blender.org/release/Blender5.3/blender-5.3.0-windows-x64.msi")
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertEqual([call[0] for call in server.calls], [
            "https://download.blender.org/release/",
            "https://download.blender.org/release/Blender5.3/",
            "https://download.blender.org/release/Blender5.3/blender-5.3.0.sha256",
        ])
        self.assertTrue(any("Folder used: Blender5.3/" in m for m in messages))
        self.assertTrue(any(HEX_A in m for m in messages))


class KeyTests(unittest.TestCase):
    def test_versions_and_series_are_compared_as_numbers(self):
        self.assertGreater(provider.release_key("5.10.0"), provider.release_key("5.9.1"))
        self.assertGreater(provider.release_key("5.3.10"), provider.release_key("5.3.9"))
        self.assertEqual(provider.release_key("5.3.0"), (5, 3, 0))
        self.assertGreater(provider.series_key("5.10"), provider.series_key("5.9"))
        self.assertGreater(provider.series_key("10.0"), provider.series_key("9.9"))
        self.assertEqual(provider.series_key("4.5"), (4, 5))

    def test_anything_else_is_not_a_version(self):
        for value in ("5.3", FOUR_NUMBERS, "5.3.0rc1", "5.3.x", "v5.3.0", "", " 5.3.0", "5.3.0\n",
                      "05.3.0", "5.03.0", "٥.٣.٠", None, 5, ["5.3.0"]):
            with self.subTest(value=value):
                self.assertIsNone(provider.release_key(value))

    def test_anything_else_is_not_a_series(self):
        for value in ("5", "5.3.0", "5.3a", "2.04", "05.3", " 5.3", "5.3/", "5.3\n", "", None, 5.3, ["5.3"]):
            with self.subTest(value=value):
                self.assertIsNone(provider.series_key(value))


class ExtractSeriesTests(unittest.TestCase):
    def test_the_series_folders_are_read_and_sorted_by_their_numbers(self):
        page = index_of("Blender5.3/", "Blender5.10/", "Blender4.5/", "Blender10.0/")
        self.assertEqual(provider.extract_series(page), ["4.5", "5.3", "5.10", "10.0"])

    def test_a_folder_listed_twice_counts_once(self):
        self.assertEqual(provider.extract_series(index_of("Blender5.3/", "Blender5.3/")), ["5.3"])

    def test_other_links_are_ignored(self):
        page = index_of("Blender5.3/", "Blender5.4a/", "Blender5.5alpha/", "Blender5.6-newpy/",
                        "BlenderBenchmark9.0/", "Blender5.7", "Blender5.8.0/", "blender5.9/", "Blender6/",
                        "Blender05.9/", "../Blender6.0/", "/release/Blender6.0/", "https://example.test/Blender6.0/",
                        "Blender6.0//", "Blender6.0/ ", "trace", "GPL-license.txt")
        self.assertEqual(provider.extract_series(page), ["5.3"])

    def test_the_text_of_a_link_is_not_read_only_its_address(self):
        page = '<a href="plugin/">Blender9.0/</a><a href="Blender5.3/">next</a>'
        self.assertEqual(provider.extract_series(page), ["5.3"])

    def test_a_page_without_a_series_folder_is_refused(self):
        for text in ("", "<html></html>", index_of("plugin/", "trace"), "<a>Blender5.3/</a>",
                     "<a href='Blender5.3/'>x</a>"):
            with self.subTest(text=text[:40]):
                with self.assertRaises(ValueError) as caught:
                    provider.extract_series(text)
                self.assertIn("no link to a series folder", str(caught.exception))


class MsiVersionsTests(unittest.TestCase):
    def test_the_x64_msis_are_read_and_sorted_by_their_numbers(self):
        page = listing_of("5.2.4", "5.2.10", "5.2.0")
        self.assertEqual(provider.msi_versions(page, "5.2"), ["5.2.0", "5.2.4", "5.2.10"])

    def test_names_of_another_shape_are_ignored_not_an_error(self):
        page = index_of("blender-5.4.0-rc1-windows-x64.msi", "blender-5.4.0rc1-windows-x64.msi",
                        "blender-5.4-windows-x64.msi", "blender-%s-windows-x64.msi" % ".".join(["5", "4", "0", "1"]),
                        "blender-5.4.0-windows-arm64.msi", "blender-5.4.0-windows-x64.msix",
                        "blender-5.4.0-windows-x64.zip", "Blender-5.4.0-windows-x64.msi",
                        "blender-5.4.0-windows-x64.msi.sha256", "blender-05.4.0-windows-x64.msi",
                        "../blender-5.4.0-windows-x64.msi", "blender-5.4.0.sha256")
        self.assertEqual(provider.msi_versions(page, "5.4"), [])

    def test_an_empty_folder_gives_an_empty_list(self):
        self.assertEqual(provider.msi_versions(index_of(), "5.4"), [])

    def test_a_release_of_another_series_is_an_error(self):
        with self.assertRaises(ValueError) as caught:
            provider.msi_versions(listing_of("5.3.0", "5.2.4"), "5.3")
        self.assertIn("another series", str(caught.exception))

    def test_a_series_that_is_not_two_numbers_is_an_error(self):
        with self.assertRaises(ValueError):
            provider.msi_versions(listing_of("5.3.0"), "5.3.0")


class AddressTests(unittest.TestCase):
    def test_the_addresses(self):
        self.assertEqual(provider.expected_file_name("5.3.0"), "blender-5.3.0-windows-x64.msi")
        self.assertEqual(provider.series_url("4.5"), "https://download.blender.org/release/Blender4.5/")
        self.assertEqual(provider.file_url("5.2.4"),
                         "https://download.blender.org/release/Blender5.2/blender-5.2.4-windows-x64.msi")
        self.assertEqual(provider.hash_url("5.2.4"),
                         "https://download.blender.org/release/Blender5.2/blender-5.2.4.sha256")

    def test_every_address_is_under_the_fixed_prefix(self):
        for version in ("5.3.0", "0.0.0", "100.20.300"):
            self.assertTrue(provider.file_url(version).startswith(provider.ALLOWED_PREFIX))
            self.assertTrue(provider.hash_url(version).startswith(provider.ALLOWED_PREFIX))

    def test_a_text_that_is_not_a_version_gives_no_name_and_no_address(self):
        for value in ("5.3", "../1.1.1", "5.3.0/../../x", "5.3.0 ", "", None, "5.3.0?a=1", "5.3.0#x"):
            with self.subTest(value=value):
                for function in (provider.expected_file_name, provider.file_url, provider.hash_url):
                    with self.assertRaises(ValueError):
                        function(value)
        for value in ("5.3.0", "../5.3", "5.3/..", "", None):
            with self.subTest(series=value):
                with self.assertRaises(ValueError):
                    provider.series_url(value)


class Sha256OfTests(unittest.TestCase):
    def test_the_msis_line_is_taken_among_the_eight(self):
        self.assertEqual(provider.sha256_of(hash_file("5.3.0", HEX_A), "5.3.0"), HEX_A)
        self.assertEqual(len(hash_file("5.3.0").splitlines()), 8)

    def test_the_hash_is_returned_in_lower_case(self):
        self.assertEqual(provider.sha256_of(hash_file("5.3.0", HEX_A.upper()), "5.3.0"), HEX_A)

    def test_line_ends(self):
        for ending in ("", "\n", "\r\n"):
            with self.subTest(ending=repr(ending)):
                text = hash_file("5.3.0", HEX_B, ending=ending)
                if ending == "\r\n":
                    text = text.replace("\n", "\r\n").replace("\r\r\n", "\r\n")
                self.assertEqual(provider.sha256_of(text, "5.3.0"), HEX_B)

    def test_no_line_for_the_msi_is_refused(self):
        text = hash_file("5.3.0").replace(msi_name("5.3.0"), "blender-5.3.0-windows-x64.msi.bak")
        for bad in (text, "", "\n", hash_file("5.2.4")):
            with self.subTest(text=bad[:20]):
                with self.assertRaises(ValueError) as caught:
                    provider.sha256_of(bad, "5.3.0")
                self.assertIn("no line for blender-5.3.0-windows-x64.msi", str(caught.exception))

    def test_two_lines_for_the_msi_are_refused_even_with_the_same_hash(self):
        line = "%s  %s" % (HEX_A, msi_name("5.3.0"))
        for text in (hash_file("5.3.0") + line + "\n", hash_file("5.3.0") + "%s  %s\n" % (HEX_C, msi_name("5.3.0"))):
            with self.assertRaises(ValueError) as caught:
                provider.sha256_of(text, "5.3.0")
            self.assertIn("2 lines", str(caught.exception))

    def test_any_line_of_another_form_is_an_error_not_skipped(self):
        name = "blender-5.3.0-windows-arm64.zip"
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
            HEX_A + "  dir/" + name,            # a path
            HEX_A + "  dir\\" + name,           # a Windows path
            "SHA256 (" + name + ") = " + HEX_A, # another tool's format
            "٠" * 64 + "  " + name,             # other digits
            "# a comment",
        ]
        for line in bad:
            with self.subTest(line=line[:30]):
                with self.assertRaises(ValueError) as caught:
                    provider.sha256_of(hash_file("5.3.0") + line + "\n", "5.3.0")
                self.assertIn("line 9 is not", str(caught.exception))

    def test_a_name_that_is_only_like_the_msis_does_not_count(self):
        for name in ("Blender-5.3.0-windows-x64.msi", "blender-5.3.0-windows-x64.MSI", "blender-5.3.0-windows-x64.msix",
                     "blender-5.3.0-windows-arm64.msi", "blender-5.3.1-windows-x64.msi"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    provider.sha256_of("%s  %s\n" % (HEX_A, name), "5.3.0")

    def test_a_version_that_is_not_three_numbers_is_refused(self):
        with self.assertRaises(ValueError):
            provider.sha256_of(hash_file("5.3.0"), "5.3")


class MainTests(unittest.TestCase):
    INDEX = index_of("Blender5.1/", "Blender5.2/", "Blender5.3/")
    FOLDERS = {"5.1": listing_of("5.1.0", "5.1.1"), "5.2": listing_of("5.2.0", "5.2.4"), "5.3": listing_of("5.3.0")}
    HASHES = hashes_for(("5.3.0", HEX_A), ("5.2.4", HEX_B), ("5.1.1", HEX_C))

    def server(self, index=None, folders=None, hashes=None):
        return FakeServer(index or self.INDEX, self.FOLDERS if folders is None else folders,
                          self.HASHES if hashes is None else hashes)

    def test_the_default_is_the_newest_series(self):
        server = self.server()
        processor, messages = run_on(server)
        self.assertEqual(processor.env["version"], "5.3.0")
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertEqual(len(server.calls), 3)
        self.assertEqual(server.calls[0][1:], (provider.MAX_INDEX_BYTES, "the index"))
        self.assertEqual(server.calls[1][1:], (provider.MAX_FOLDER_BYTES, "the folder Blender5.3/"))
        self.assertEqual(server.calls[2][1:], (provider.MAX_HASH_FILE_BYTES, "the hash file"))
        self.assertTrue(any(m == "Folder used: Blender5.3/ (newest)" for m in messages))

    def test_the_declared_defaults_equal_the_values_the_code_uses(self):
        declared = {name: flags["default"] for name, flags in PROVIDER.input_variables.items()}
        self.assertEqual(declared, {"blender_series": ""})
        for flags in PROVIDER.input_variables.values():
            self.assertIs(flags["required"], False)
        self.assertEqual(sorted(PROVIDER.output_variables), ["expected_sha256", "url", "version"])

    def test_the_highest_version_of_the_folder_is_taken(self):
        processor, _ = run_on(self.server(), {"blender_series": "5.2"})
        self.assertEqual(processor.env["version"], "5.2.4")
        self.assertEqual(processor.env["expected_sha256"], HEX_B)
        self.assertEqual(processor.env["url"],
                         "https://download.blender.org/release/Blender5.2/blender-5.2.4-windows-x64.msi")

    def test_a_newest_folder_without_an_msi_is_passed_over_and_the_output_says_so(self):
        folders = dict(self.FOLDERS)
        folders["5.4"] = index_of("blender-5.4.0-rc1-windows-x64.msi", "blender-5.4.0-linux-x64.tar.xz")
        index = index_of("Blender5.2/", "Blender5.3/", "Blender5.4/")
        server = self.server(index=index, folders=folders)
        processor, messages = run_on(server)
        self.assertEqual(processor.env["version"], "5.3.0")
        self.assertEqual([call[0] for call in server.calls], [
            provider.INDEX_URL, provider.series_url("5.4"), provider.series_url("5.3"), provider.hash_url("5.3.0")])
        self.assertIn("Folder Blender5.4/ has no x64 MSI: the next lower series was read.", messages)
        self.assertIn("Folder used: Blender5.3/ (newest)", messages)

    def test_no_more_than_the_limit_of_folders_is_read(self):
        index = index_of("Blender5.0/", "Blender5.1/", "Blender5.2/", "Blender5.3/", "Blender5.4/")
        folders = {"5.4": index_of(), "5.3": index_of(), "5.2": index_of(), "5.1": listing_of("5.1.1"),
                   "5.0": listing_of("5.0.0")}
        processor, _ = new_processor(PROVIDER, {})
        server = self.server(index=index, folders=folders)
        with mock.patch.object(provider, "fetch_text", side_effect=server):
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        self.assertEqual(provider.MAX_SERIES_TRIED, 3)
        self.assertEqual(len(server.calls), 1 + provider.MAX_SERIES_TRIED)
        self.assertIn("Blender5.4/, Blender5.3/, Blender5.2/", str(caught.exception))
        self.assertNotIn("url", processor.env)

    def test_a_pinned_series_reads_only_its_folder_and_never_falls_back(self):
        server = self.server()
        processor, messages = run_on(server, {"blender_series": "5.1"})
        self.assertEqual(processor.env["version"], "5.1.1")
        self.assertEqual([call[0] for call in server.calls],
                         [provider.INDEX_URL, provider.series_url("5.1"), provider.hash_url("5.1.1")])
        self.assertIn("Folder used: Blender5.1/ (pinned)", messages)
        folders = dict(self.FOLDERS)
        folders["5.1"] = index_of()
        processor, _ = new_processor(PROVIDER, {"blender_series": "5.1"})
        server = self.server(folders=folders)
        with mock.patch.object(provider, "fetch_text", side_effect=server):
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        self.assertEqual(len(server.calls), 2)
        self.assertIn("Blender5.1/", str(caught.exception))
        self.assertNotIn("url", processor.env)

    def test_a_pinned_series_that_the_index_lacks_is_an_error(self):
        processor, _ = new_processor(PROVIDER, {"blender_series": "4.5"})
        server = self.server()
        with mock.patch.object(provider, "fetch_text", side_effect=server):
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        self.assertIn("no folder Blender4.5/", str(caught.exception))
        self.assertEqual(len(server.calls), 1)

    def test_white_space_around_the_input_is_ignored(self):
        processor, _ = run_on(self.server(), {"blender_series": " 5.2\n"})
        self.assertEqual(processor.env["version"], "5.2.4")
        processor, _ = run_on(self.server(), {"blender_series": "  "})
        self.assertEqual(processor.env["version"], "5.3.0")

    def test_an_input_that_is_not_a_series_is_an_error_and_nothing_is_fetched(self):
        for value in ("5", "5.3.0", "latest", "lts", "5.3a", "../5.3", "05.3", None, 7, ["5.3"], True):
            processor, _ = new_processor(PROVIDER, {"blender_series": value})
            with self.subTest(value=value):
                with mock.patch.object(provider, "fetch_text") as fetch:
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                fetch.assert_not_called()
                self.assertIn("blender_series", str(caught.exception))

    def test_no_output_is_set_when_the_run_fails(self):
        cases = [
            ({"index": index_of("plugin/")}, "Blender download index"),
            ({"folders": {"5.3": listing_of("5.3.0", "5.2.4")}}, "Blender folder Blender5.3/"),
            ({"hashes": {provider.hash_url("5.3.0"): "not a hash line\n"}}, "Blender hash file of 5.3.0"),
            ({"hashes": {provider.hash_url("5.3.0"): hash_file("5.2.4")}}, "Blender hash file of 5.3.0"),
            ({"hashes": {provider.hash_url("5.3.0"): ""}}, "Blender hash file of 5.3.0"),
            ({"hashes": {}}, "404"),
        ]
        for kwargs, expected in cases:
            processor, _ = new_processor(PROVIDER, {})
            server = self.server(**kwargs)
            with self.subTest(expected=expected):
                with mock.patch.object(provider, "fetch_text", side_effect=server):
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                for key in ("url", "version", "expected_sha256"):
                    self.assertNotIn(key, processor.env)
                self.assertIn(expected, str(caught.exception))

    def test_the_provider_follows_the_numbers_when_the_text_order_would_be_wrong(self):
        index = index_of("Blender5.10/", "Blender5.9/")
        folders = {"5.10": listing_of("5.10.0"), "5.9": listing_of("5.9.2", "5.9.10")}
        hashes = hashes_for(("5.10.0", HEX_C), ("5.9.10", HEX_B))
        processor, _ = run_on(FakeServer(index, folders, hashes))
        self.assertEqual(processor.env["version"], "5.10.0")
        processor, _ = run_on(FakeServer(index, folders, hashes), {"blender_series": "5.9"})
        self.assertEqual(processor.env["version"], "5.9.10")
        self.assertEqual(processor.env["expected_sha256"], HEX_B)


class FetchTests(unittest.TestCase):
    def fetch_with(self, body=None, error=None, url=provider.INDEX_URL, max_bytes=provider.MAX_INDEX_BYTES,
                   what="the index", status=200):
        def opener(request):
            self.request = request
            if error is not None:
                raise error
            response = FakeResponse(body)
            response.status = status
            return response
        with mock.patch.object(provider, "open_request", side_effect=opener):
            return provider.fetch_text(url, max_bytes, what)

    def test_the_text_is_returned_and_the_request_is_plain(self):
        self.assertEqual(self.fetch_with(body="café page".encode("utf-8")), "café page")
        self.assertEqual(self.request.full_url, "https://download.blender.org/release/")
        self.assertEqual(self.request.get_header("User-agent"), provider.USER_AGENT)
        self.assertIsNone(self.request.data)
        self.assertFalse(self.request.has_header("Authorization"))

    def test_an_address_outside_the_fixed_prefix_is_refused_before_any_request(self):
        for url in ("https://example.test/release/", "http://download.blender.org/release/",
                    "https://download.blender.org/", "https://download.blender.org.example.test/release/",
                    "https://download.blender.org@example.test/release/", "https://www.blender.org/release/",
                    "ftp://download.blender.org/release/", "", None, 5):
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

    def test_a_success_status_other_than_200_is_an_error(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(body=b"partial", status=206)
        self.assertIn("206, not 200", str(caught.exception))

    def test_a_redirect_is_an_error_that_says_so_and_tells_the_owner(self):
        for code in (301, 302, 307, 308):
            error = urllib.error.HTTPError(provider.hash_url("5.3.0"), code, "Moved", {}, io.BytesIO(b""))
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error, url=provider.hash_url("5.3.0"),
                                    max_bytes=provider.MAX_HASH_FILE_BYTES, what="the hash file")
                message = str(caught.exception)
                self.assertIn("answered %d" % code, message)
                self.assertIn("a redirect is not followed", message)
                self.assertIn("tell the owner", message)

    def test_the_redirect_handler_refuses_to_redirect(self):
        self.assertIsNone(provider.NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://example.test/"))

    def test_the_real_opener_is_built_with_the_redirect_refusing_handler(self):
        with mock.patch.object(provider.urllib.request, "build_opener") as build:
            provider.open_request(object())
        handlers = build.call_args[0]
        self.assertEqual(handlers, (provider.NoRedirect,))
        self.assertEqual(build.return_value.open.call_args[1]["timeout"], provider.FETCH_TIMEOUT_SECONDS)

    def test_a_failed_connection_is_a_processor_error(self):
        for error in (urllib.error.URLError("no route"), TimeoutError("timed out"), OSError("reset"),
                      ValueError("bad url")):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error)
                self.assertTrue(str(caught.exception).startswith("The index could not be fetched"))

    def test_a_page_larger_than_the_limit_is_an_error_and_exactly_the_limit_is_accepted(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(body=b"x" * (provider.MAX_INDEX_BYTES + 1))
        self.assertIn("larger than", str(caught.exception))
        self.assertEqual(len(self.fetch_with(body=b"x" * provider.MAX_INDEX_BYTES)), provider.MAX_INDEX_BYTES)

    def test_the_read_never_asks_for_more_than_the_limit_plus_one(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b"ok"
        with mock.patch.object(provider, "open_request", return_value=response):
            provider.fetch_text(provider.INDEX_URL, 100, "the index")
        response.read.assert_called_once_with(101)

    def test_a_page_that_is_not_utf_8_is_an_error(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(body=b"\xff\xfe\x00bad")
        self.assertIn("not UTF-8", str(caught.exception))

    def test_the_constants(self):
        self.assertEqual(provider.INDEX_URL, "https://download.blender.org/release/")
        self.assertEqual(provider.ALLOWED_PREFIX, provider.INDEX_URL)
        self.assertGreater(provider.MAX_INDEX_BYTES, 64 * 1024)
        self.assertGreater(provider.MAX_FOLDER_BYTES, 64 * 1024)
        self.assertLess(provider.MAX_HASH_FILE_BYTES, 64 * 1024)
        self.assertGreater(provider.MAX_HASH_FILE_BYTES, 777)
        self.assertGreater(provider.FETCH_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(provider.FETCH_TIMEOUT_SECONDS, 600)


if __name__ == "__main__":
    unittest.main()
