"""Tests of InkscapeInfoProvider: every branch. No test uses the network:
fetch_location(), fetch_text() or open_request() is replaced.

The two page excerpts (download_page_excerpt.html and gallery_page_excerpt.html)
were written by hand from the real pages of 2026-10-02: the real link lines,
with everything else cut. They were not saved from the pages. The hash lines
here are written by hand in the format of the real file (64 hex digits, two
spaces, the file name, a new line): the digits are made up, not the hash of any
file. The real site was read on 2026-10-02 by the person who wrote the
processor's address and format rules; these tests never use the network.
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

import InkscapeInfoProvider as provider  # noqa: E402

PROVIDER = provider.InkscapeInfoProvider
DL_EXCERPT = os.path.join(TESTS_DIR, "download_page_excerpt.html")
ITEM_EXCERPT = os.path.join(TESTS_DIR, "gallery_page_excerpt.html")
# Made-up digits, not the hash of any file.
HEX_A = "0123456789abcdef" * 4
HEX_B = "fedcba9876543210" * 4
# Texts that the hygiene test would read as an address if they stood in this
# file as they are. They are built here.
FOUR_NUMBERS = ".".join(["1", "4", "4", "1"])
FIVE_NUMBERS = ".".join(["1", "4", "4", "4", "4"])

VERSION = "1.4.4"
ITEM_ID = "59504"
FILE_NAME = "inkscape-1.4.4_2026-05-05_dcaf3e7-x64.signed_xMx7DJV.msi"
HASHED_NAME = "inkscape-1.4.4_2026-05-05_dcaf3e7-x64.signed.msi"
SIG_NAME = "inkscape-1.4.4_2026-05-05_dcaf3e7-x64.signed.msi_PujJ1ID.sha256"
SIG_URL = "https://media.inkscape.org/media/resources/sigs/" + SIG_NAME

RELEASE_URL = "https://inkscape.org/release/"
RELEASE_LOCATION = "https://inkscape.org/release/inkscape-1.4.4/"
DL_URL = "https://inkscape.org/release/inkscape-1.4.4/windows/64-bit/msi/dl/"
ITEM_URL = "https://inkscape.org/gallery/item/59504/"
MEDIA_URL = "https://media.inkscape.org/dl/resources/file/" + FILE_NAME


def page_of(*addresses):
    """A made-up page with a link for each address."""
    links = "\n".join('<a href="%s">x</a>' % address for address in addresses)
    return "<html><body>\n%s\n</body></html>" % links


def gallery_link(item_id=ITEM_ID, name=FILE_NAME):
    return "/gallery/item/%s/%s" % (item_id, name)


def hash_line(sha256=HEX_A, name=HASHED_NAME, gap="  ", end="\n"):
    return "%s%s%s%s" % (sha256, gap, name, end)


class Server:
    """Stands in for fetch_location and fetch_text: the answers are by address."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def answer(self, url):
        answer = self.answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def location(self, url, what):
        self.calls.append((url, None, what))
        return self.answer(url)

    def text(self, url, max_bytes, what):
        self.calls.append((url, max_bytes, what))
        return self.answer(url)


def patched(server):
    return mock.patch.multiple(provider, fetch_location=server.location, fetch_text=server.text)


def run_with(answers, env=None):
    server = Server(answers)
    with patched(server):
        result = run_processor(PROVIDER, env or {})
    return result + (server,)


def normal_answers(version=VERSION, item_id=ITEM_ID, sha256=HEX_A):
    name = "inkscape-%s_2026-05-05_dcaf3e7-x64.signed_xMx7DJV.msi" % version
    hashed = "inkscape-%s_2026-05-05_dcaf3e7-x64.signed.msi" % version
    sig = "https://media.inkscape.org/media/resources/sigs/%s.msi_PujJ1ID.sha256" % hashed[:-4]
    return {
        RELEASE_URL: "https://inkscape.org/release/inkscape-%s/" % version,
        "https://inkscape.org/release/inkscape-%s/windows/64-bit/msi/dl/" % version: page_of(gallery_link(item_id, name)),
        "https://inkscape.org/gallery/item/%s/" % item_id: page_of(gallery_link(item_id, name), sig),
        sig: hash_line(sha256, hashed),
    }


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ExcerptTests(unittest.TestCase):
    """The two excerpts that were written by hand."""

    def setUp(self):
        with open(DL_EXCERPT, "r", encoding="utf-8") as handle:
            self.dl_page = handle.read()
        with open(ITEM_EXCERPT, "r", encoding="utf-8") as handle:
            self.item_page = handle.read()

    def test_the_first_line_of_each_says_it_was_written_by_hand(self):
        for page in (self.dl_page, self.item_page):
            first = page.splitlines()[0]
            self.assertIn("Written by hand from the real page of 2026-10-02", first)
            self.assertIn("the real link lines, with everything else cut", first)
            self.assertIn("Not saved from the page", first)

    def test_the_excerpts_are_small(self):
        self.assertLess(len(self.dl_page), 4000)
        self.assertLess(len(self.item_page), 4000)

    def test_the_one_gallery_link_is_found_among_the_other_links(self):
        self.assertEqual(provider.find_download_link(self.dl_page, VERSION), (ITEM_ID, FILE_NAME))

    def test_the_meta_refresh_and_the_language_links_are_not_gallery_links(self):
        self.assertIn('content="2; url=/gallery/item/', self.dl_page)
        self.assertIn('href="/de/release/', self.dl_page)
        self.assertEqual(len(provider.links_of(self.dl_page)), 5)

    def test_the_gallery_page_has_the_gallery_link_twice_and_one_hash_link(self):
        links = provider.links_of(self.item_page)
        self.assertEqual(links.count(gallery_link()), 2)
        self.assertEqual(provider.find_hash_link(self.item_page), SIG_URL)
        self.assertIn("/de/gallery/item/59504/", links)

    def test_the_processor_gives_the_media_address_the_version_and_the_hash(self):
        answers = {
            RELEASE_URL: RELEASE_LOCATION,
            DL_URL: self.dl_page,
            ITEM_URL: self.item_page,
            SIG_URL: hash_line(HEX_A),
        }
        processor, messages, server = run_with(answers)
        self.assertEqual(processor.env["version"], "1.4.4")
        self.assertEqual(processor.env["url"], MEDIA_URL)
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertEqual([call[0] for call in server.calls], list(answers))


class VersionKeyTests(unittest.TestCase):
    def test_numbers_are_compared_as_numbers(self):
        self.assertGreater(provider.version_key("1.4.10"), provider.version_key("1.4.9"))
        self.assertEqual(provider.version_key("1.4.4"), (1, 4, 4))
        self.assertEqual(provider.version_key("1.4"), (1, 4))

    def test_anything_else_is_not_a_version(self):
        for value in ("1", FIVE_NUMBERS, "1.4.4rc1", "1.x", "v1.4.4", "", " 1.4.4", "1.4.4\n", "1..4", "1.-4",
                      "١.٤.٤", None, 1, ["1.4.4"]):
            with self.subTest(value=value):
                self.assertIsNone(provider.version_key(value))


class ReleaseLocationTests(unittest.TestCase):
    def test_the_real_location(self):
        self.assertEqual(provider.parse_release_location(RELEASE_LOCATION), "1.4.4")

    def test_two_and_four_numbers(self):
        self.assertEqual(provider.parse_release_location("https://inkscape.org/release/inkscape-1.5/"), "1.5")
        self.assertEqual(provider.parse_release_location("https://inkscape.org/release/inkscape-%s/" % FOUR_NUMBERS), FOUR_NUMBERS)

    def test_a_location_that_is_not_the_expected_address_is_an_error(self):
        for location in (
            "http://inkscape.org/release/inkscape-1.4.4/",            # not https
            "https://www.inkscape.org/release/inkscape-1.4.4/",       # another host
            "https://media.inkscape.org/release/inkscape-1.4.4/",
            "https://inkscape.org.example.test/release/inkscape-1.4.4/",
            "https://inkscape.org@example.test/release/inkscape-1.4.4/",
            "https://example.test@inkscape.org/release/inkscape-1.4.4/",
            "https://inkscape.org:8443/release/inkscape-1.4.4/",
            "https://inkscape.org/release/inkscape-1.4.4",            # no closing slash
            "https://inkscape.org/release/inkscape-1.4.4/windows/",
            "https://inkscape.org/release/inkscape-1.4.4//",
            "https://inkscape.org/de/release/inkscape-1.4.4/",
            "https://inkscape.org/release/inkscape-1.4.4/?x=1",
            "https://inkscape.org/release/inkscape-1.4.4/#x",
            "https://inkscape.org/release/Inkscape-1.4.4/",
            "https://inkscape.org/release/inkscape-1.4.4rc1/",
            "https://inkscape.org/release/inkscape-1/",
            "https://inkscape.org/release/inkscape-1..4/",
            "https://inkscape.org/release/inkscape-/",
            "https://inkscape.org/release/",
            "https://inkscape.org/",
            "", None, 7,
        ):
            with self.subTest(location=location):
                with self.assertRaises(ValueError):
                    provider.parse_release_location(location)


class NameAndAddressTests(unittest.TestCase):
    def test_the_addresses(self):
        self.assertEqual(provider.dl_page_url("1.4.4", "64-bit"), DL_URL)
        self.assertEqual(provider.item_page_url("59504"), ITEM_URL)
        self.assertEqual(provider.media_url(FILE_NAME), MEDIA_URL)

    def test_an_address_is_not_built_from_something_that_is_not_a_version_or_an_architecture(self):
        for version, architecture in (("1", "64-bit"), ("../1.4.4", "64-bit"), ("1.4.4/x", "64-bit"), ("", "64-bit"),
                                      (None, "64-bit"), ("1.4.4", "32-bit"), ("1.4.4", "../64-bit"), ("1.4.4", ""),
                                      ("1.4.4", "64-BIT")):
            with self.subTest(version=version, architecture=architecture):
                with self.assertRaises(ValueError):
                    provider.dl_page_url(version, architecture)

    def test_an_item_number_is_digits_only(self):
        for value in ("", "59504/", "../1", "a", "5 9", None, 59504, "59504\n"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    provider.item_page_url(value)

    def test_a_media_address_is_built_only_for_the_name_of_an_msi(self):
        for name in ("", "x.exe", "../x.msi", "a/b.msi", "a b.msi", "x.msi?y=1", "x.msi/", None, "x.MSI"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    provider.media_url(name)

    def test_the_constants_are_the_publishers_own_hosts_over_https(self):
        self.assertEqual(provider.SITE_URL, "https://inkscape.org/")
        self.assertEqual(provider.MEDIA_DOWNLOAD_URL, "https://media.inkscape.org/dl/resources/file/")
        for prefix in provider.ALLOWED_PREFIXES:
            self.assertTrue(prefix.startswith("https://"))
            self.assertTrue(prefix.endswith("/"))
        self.assertEqual(provider.ALLOWED_PREFIXES, ("https://inkscape.org/", "https://media.inkscape.org/media/resources/sigs/"))


class FindDownloadLinkTests(unittest.TestCase):
    def test_one_link_gives_its_id_and_name(self):
        self.assertEqual(provider.find_download_link(page_of(gallery_link()), VERSION), (ITEM_ID, FILE_NAME))

    def test_the_same_link_twice_is_one_link(self):
        page = page_of(gallery_link(), gallery_link())
        self.assertEqual(provider.find_download_link(page, VERSION), (ITEM_ID, FILE_NAME))

    def test_other_links_are_ignored(self):
        page = page_of("/", "/user/login/?next=/gallery/item/59504/", "/de/gallery/item/59504/",
                       "/de" + gallery_link(), "https://inkscape.org" + gallery_link(),
                       "/gallery/item/59504/", "/gallery/item/59504/readme.txt", "/release/inkscape-1.4.4/",
                       "https://media.inkscape.org/media/resources/sigs/" + SIG_NAME, gallery_link())
        self.assertEqual(provider.find_download_link(page, VERSION), (ITEM_ID, FILE_NAME))

    def test_a_language_prefix_makes_a_link_that_is_not_a_gallery_link(self):
        with self.assertRaises(ValueError) as caught:
            provider.find_download_link(page_of("/de" + gallery_link()), VERSION)
        self.assertIn("no gallery link", str(caught.exception))

    def test_no_link_is_an_error(self):
        for page in ("", "<html></html>", "not html at all", page_of("/gallery/item/59504/")):
            with self.subTest(page=page[:30]):
                with self.assertRaises(ValueError) as caught:
                    provider.find_download_link(page, VERSION)
                self.assertIn("no gallery link to an MSI of release 1.4.4", str(caught.exception))

    def test_the_text_of_the_link_without_an_address_does_not_count(self):
        page = "<html><body>%s <a name='x'>%s</a> <meta content='url=%s'></body></html>" % (
            gallery_link(), gallery_link(), gallery_link())
        with self.assertRaises(ValueError):
            provider.find_download_link(page, VERSION)

    def test_two_different_links_are_an_error(self):
        page = page_of(gallery_link(), gallery_link("59505", FILE_NAME))
        with self.assertRaises(ValueError) as caught:
            provider.find_download_link(page, VERSION)
        self.assertIn("2 different gallery links", str(caught.exception))
        self.assertIn("not exactly one", str(caught.exception))
        page = page_of(gallery_link(), gallery_link(name=FILE_NAME.replace("xMx7DJV", "Other1")))
        with self.assertRaises(ValueError):
            provider.find_download_link(page, VERSION)

    def test_a_link_to_an_msi_of_another_form_is_an_error_not_a_skip(self):
        for name in (
            "inkscape-1.4.4_2026-05-05_dcaf3e7-x86.signed_xMx7DJV.msi",    # another architecture
            "inkscape-1.4.4_2026-05-05_dcaf3e7-x64_xMx7DJV.msi",           # not signed
            "inkscape-1.4.4_2026-05-05_dcaf3e7-x64.signed.msi",            # no token
            "inkscape-1.4.4_2026-05-05_dcaf3e7-x64.signed_xMx-7DJV.msi",   # a token with a dash
            "inkscape-1.4.4_2026-05-05_dcaf3e7-x64.signed_xMx7DJV.exe.msi",
            "inkscape-1.4.3_2026-05-05_dcaf3e7-x64.signed_xMx7DJV.msi",    # another version
            "inkscape-1.4.40_2026-05-05_dcaf3e7-x64.signed_xMx7DJV.msi",
            "Inkscape-1.4.4_2026-05-05_dcaf3e7-x64.signed_xMx7DJV.msi",
            "inkscape-1.4.4-2026-05-05_dcaf3e7-x64.signed_xMx7DJV.msi",    # no underscore after the version
            "inkscape-1.4.4__x64.signed_xMx7DJV.msi",                      # nothing between
            "other-1.4.4_2026-05-05_dcaf3e7-x64.signed_xMx7DJV.msi",
            "inkscape-1.4.4_2026 05-05_dcaf3e7-x64.signed_xMx7DJV.msi",
        ):
            with self.subTest(name=name):
                with self.assertRaises(ValueError) as caught:
                    provider.find_download_link(page_of(gallery_link(name=name), gallery_link()), VERSION)
                self.assertIn("is not inkscape-1.4.4_", str(caught.exception))

    def test_the_address_is_read_with_its_html_entities_decoded(self):
        page = '<a href="/gallery/item/59504/%s">x</a>' % FILE_NAME.replace(".msi", "&#46;msi")
        self.assertEqual(provider.find_download_link(page, VERSION), (ITEM_ID, FILE_NAME))

    def test_single_quoted_and_spaced_attributes_are_read(self):
        address = gallery_link()
        for page in ("<a href='%s'>x</a>" % address, '<A HREF="%s">x</A>' % address,
                     '<a class="f" href = "%s" title="y">x</a>' % address, '<a\n  href="%s">x</a>' % address):
            with self.subTest(page=page):
                self.assertEqual(provider.find_download_link(page, VERSION), (ITEM_ID, FILE_NAME))

    def test_an_attribute_that_only_ends_in_href_is_not_read(self):
        for page in ('<a data-href="%s">x</a>' % gallery_link(), '<a xhref="%s">x</a>' % gallery_link()):
            with self.subTest(page=page):
                with self.assertRaises(ValueError):
                    provider.find_download_link(page, VERSION)

    def test_the_version_chooses_the_file_name(self):
        name = FILE_NAME.replace("1.4.4", "1.5")
        self.assertEqual(provider.find_download_link(page_of(gallery_link(name=name)), "1.5"), (ITEM_ID, name))
        with self.assertRaises(ValueError):
            provider.find_download_link(page_of(gallery_link(name=name)), "1.4.4")

    def test_the_dots_of_the_version_are_not_wildcards(self):
        name = FILE_NAME.replace("1.4.4", "1x4x4")
        with self.assertRaises(ValueError):
            provider.find_download_link(page_of(gallery_link(name=name)), "1.4.4")


class FindHashLinkTests(unittest.TestCase):
    def test_one_link_gives_its_address(self):
        self.assertEqual(provider.find_hash_link(page_of(SIG_URL)), SIG_URL)

    def test_the_same_link_twice_is_one_link(self):
        self.assertEqual(provider.find_hash_link(page_of(SIG_URL, SIG_URL)), SIG_URL)

    def test_other_links_are_ignored(self):
        page = page_of("/", gallery_link(), "https://media.inkscape.org/media/resources/render/inkscape_FsN3YsO.png",
                       "https://media.inkscape.org/media/resources/sigs/x.asc", SIG_URL)
        self.assertEqual(provider.find_hash_link(page), SIG_URL)

    def test_no_link_is_an_error(self):
        for page in ("", "<html></html>", page_of(gallery_link()), SIG_URL):
            with self.subTest(page=page[:30]):
                with self.assertRaises(ValueError) as caught:
                    provider.find_hash_link(page)
                self.assertIn("no link to a .sha256 file", str(caught.exception))

    def test_two_different_links_are_an_error(self):
        with self.assertRaises(ValueError) as caught:
            provider.find_hash_link(page_of(SIG_URL, SIG_URL.replace("PujJ1ID", "Other1")))
        self.assertIn("2 different links", str(caught.exception))
        self.assertIn("not exactly one", str(caught.exception))

    def test_a_link_that_ends_in_sha256_but_is_not_of_the_expected_form_is_an_error_not_a_skip(self):
        base = "https://media.inkscape.org/media/resources/sigs/"
        for address in (
            "http://media.inkscape.org/media/resources/sigs/" + SIG_NAME,           # not https
            "https://inkscape.org/media/resources/sigs/" + SIG_NAME,                # another host
            "https://example.test/media/resources/sigs/" + SIG_NAME,
            "https://media.inkscape.org.example.test/media/resources/sigs/" + SIG_NAME,
            "https://media.inkscape.org@example.test/media/resources/sigs/" + SIG_NAME,
            "https://example.test@media.inkscape.org/media/resources/sigs/" + SIG_NAME,
            "https://media.inkscape.org:8443/media/resources/sigs/" + SIG_NAME,
            "https://media.inkscape.org/media/resources/other/" + SIG_NAME,         # another folder
            "https://media.inkscape.org/media/resources/sigs/sub/" + SIG_NAME,      # a sub-folder
            base + "../" + SIG_NAME,
            base + SIG_NAME + "?x=1.sha256",
            base + "a b.sha256",
            "/media/resources/sigs/" + SIG_NAME,                                    # not absolute
            base[:-1] + SIG_NAME,                                                    # no slash before the name
        ):
            with self.subTest(address=address):
                with self.assertRaises(ValueError) as caught:
                    provider.find_hash_link(page_of(SIG_URL, address))
                self.assertIn("is not https://media.inkscape.org/media/resources/sigs/<name>.sha256", str(caught.exception))

    def test_a_fragment_is_refused(self):
        with self.assertRaises(ValueError):
            provider.find_hash_link(page_of(SIG_URL + "#x.sha256"))


class HashFileNameTests(unittest.TestCase):
    def test_the_token_is_removed_before_msi(self):
        self.assertEqual(provider.hash_file_name(FILE_NAME), HASHED_NAME)

    def test_only_the_token_is_removed(self):
        name = "inkscape-1.5_2027-01-02_abcdef1-x64.signed_Tok3n.msi"
        self.assertEqual(provider.hash_file_name(name), "inkscape-1.5_2027-01-02_abcdef1-x64.signed.msi")

    def test_a_name_that_is_not_a_download_name_is_an_error(self):
        for name in (HASHED_NAME, "", None, "x.msi", FILE_NAME + "x", "x" + FILE_NAME[1:], FILE_NAME.replace("-x64", "-x86"),
                     FILE_NAME.replace(".msi", ".exe")):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    provider.hash_file_name(name)


class ParseHashLineTests(unittest.TestCase):
    def test_the_line_gives_the_hash(self):
        self.assertEqual(provider.parse_hash_line(hash_line(HEX_A), FILE_NAME), HEX_A)

    def test_the_hash_is_returned_in_lower_case(self):
        self.assertEqual(provider.parse_hash_line(hash_line(HEX_A.upper()), FILE_NAME), HEX_A)

    def test_the_end_of_the_line_does_not_matter(self):
        for end in ("", "\n", "\r\n", "\n\n", "\n \n"):
            with self.subTest(end=repr(end)):
                self.assertEqual(provider.parse_hash_line(hash_line(end=end), FILE_NAME), HEX_A)

    def test_no_line_or_two_lines_is_an_error(self):
        for text in ("", "\n", "  \n", hash_line() + hash_line(HEX_B), hash_line() + "x\n"):
            with self.subTest(text=text[:20]):
                with self.assertRaises(ValueError) as caught:
                    provider.parse_hash_line(text, FILE_NAME)
                self.assertIn("not exactly one", str(caught.exception))

    def test_a_line_that_is_not_hash_two_spaces_and_a_name_is_an_error(self):
        for text in (
            HEX_A + " " + HASHED_NAME,                  # one space
            HEX_A + " *" + HASHED_NAME,                 # the binary marker
            HEX_A + "   " + HASHED_NAME,                # three spaces: the name would start with a space
            HEX_A + "\t" + HASHED_NAME,
            HEX_A[:-1] + "  " + HASHED_NAME,            # 63 digits
            HEX_A + "0  " + HASHED_NAME,                # 65 digits
            "g" + HEX_A[1:] + "  " + HASHED_NAME,       # not hex
            "  " + HASHED_NAME,
            HEX_A,
            HEX_A + "  ",
            HASHED_NAME,
            " " + HEX_A + "  " + HASHED_NAME,
        ):
            with self.subTest(text=text[:30]):
                with self.assertRaises(ValueError):
                    provider.parse_hash_line(text + "\n", FILE_NAME)

    def test_a_line_for_another_file_is_an_error(self):
        for name in (FILE_NAME,                                               # the name WITH the token
                     HASHED_NAME.replace("1.4.4", "1.4.3"), HASHED_NAME.replace("x64", "x86"),
                     HASHED_NAME.replace("inkscape", "Inkscape"), HASHED_NAME.replace(".msi", ".exe"),
                     "x/" + HASHED_NAME, HASHED_NAME + " ", "a",
                     HASHED_NAME.replace("signed.msi", "signed.msi_PujJ1ID")):
            with self.subTest(name=name):
                with self.assertRaises(ValueError) as caught:
                    provider.parse_hash_line(hash_line(name=name), FILE_NAME)
                self.assertIn("not " + HASHED_NAME, str(caught.exception))

    def test_a_download_name_that_has_no_token_is_an_error(self):
        with self.assertRaises(ValueError):
            provider.parse_hash_line(hash_line(), HASHED_NAME)


class MainTests(unittest.TestCase):
    def test_the_defaults_are_the_64_bit_msi(self):
        processor, messages, server = run_with(normal_answers())
        self.assertEqual(processor.env["version"], "1.4.4")
        self.assertEqual(processor.env["url"], MEDIA_URL)
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertTrue(any("1.4.4" in m for m in messages))
        self.assertTrue(any(HEX_A in m for m in messages))

    def test_another_release_changes_every_address(self):
        processor, _, server = run_with(normal_answers("1.5", "61000", HEX_B))
        self.assertEqual(processor.env["version"], "1.5")
        self.assertEqual(processor.env["url"],
                         "https://media.inkscape.org/dl/resources/file/inkscape-1.5_2026-05-05_dcaf3e7-x64.signed_xMx7DJV.msi")
        self.assertEqual(processor.env["expected_sha256"], HEX_B)
        self.assertEqual(server.calls[1][0], "https://inkscape.org/release/inkscape-1.5/windows/64-bit/msi/dl/")
        self.assertEqual(server.calls[2][0], "https://inkscape.org/gallery/item/61000/")

    def test_the_file_is_never_fetched_and_the_url_is_the_media_address_not_the_gallery_one(self):
        processor, _, server = run_with(normal_answers())
        self.assertNotIn(processor.env["url"], [call[0] for call in server.calls])
        self.assertTrue(processor.env["url"].startswith("https://media.inkscape.org/dl/resources/file/"))
        self.assertNotIn("/gallery/", processor.env["url"])

    def test_the_declared_defaults_equal_the_values_the_code_uses(self):
        declared = {name: flags["default"] for name, flags in PROVIDER.input_variables.items()}
        self.assertEqual(declared, {"inkscape_architecture": "64-bit"})
        self.assertEqual(provider.DEFAULT_ARCHITECTURE, "64-bit")
        for flags in PROVIDER.input_variables.values():
            self.assertIs(flags["required"], False)
            self.assertIn("description", flags)
        self.assertEqual(sorted(PROVIDER.output_variables), ["expected_sha256", "url", "version"])

    def test_white_space_around_the_input_is_ignored(self):
        processor, _, _ = run_with(normal_answers(), {"inkscape_architecture": " 64-bit\n"})
        self.assertEqual(processor.env["version"], "1.4.4")

    def test_an_input_that_is_empty_or_not_text_is_an_error_and_nothing_is_fetched(self):
        for value in ("", "  ", None, 7, ["64-bit"]):
            processor, _ = new_processor(PROVIDER, {"inkscape_architecture": value})
            with self.subTest(value=value):
                with mock.patch.object(provider, "fetch_text") as text, mock.patch.object(provider, "fetch_location") as loc:
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                text.assert_not_called()
                loc.assert_not_called()
                self.assertIn("inkscape_architecture", str(caught.exception))

    def test_32_bit_is_refused_with_a_clear_message_and_nothing_is_fetched(self):
        processor, _ = new_processor(PROVIDER, {"inkscape_architecture": "32-bit"})
        with mock.patch.object(provider, "fetch_text") as text, mock.patch.object(provider, "fetch_location") as loc:
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        text.assert_not_called()
        loc.assert_not_called()
        message = str(caught.exception)
        self.assertIn("32-bit is not supported", message)
        self.assertIn("file names of the 32-bit installer were not read", message)

    def test_any_other_architecture_is_an_error_and_nothing_is_fetched(self):
        for value in ("x64", "64", "64-BIT", "64-bit/../x", "arm64", "64-bit\n32-bit", "../64-bit"):
            processor, _ = new_processor(PROVIDER, {"inkscape_architecture": value})
            with self.subTest(value=value):
                with mock.patch.object(provider, "fetch_text") as text, mock.patch.object(provider, "fetch_location") as loc:
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                text.assert_not_called()
                loc.assert_not_called()
                self.assertIn("inkscape_architecture", str(caught.exception))

    def test_the_requests_have_their_limits_and_names(self):
        _, _, server = run_with(normal_answers())
        self.assertEqual(server.calls[0], (RELEASE_URL, None, "the current release"))
        self.assertEqual(server.calls[1][1:], (provider.MAX_PAGE_BYTES, "the download page"))
        self.assertEqual(server.calls[2][1:], (provider.MAX_PAGE_BYTES, "the gallery page of the file"))
        self.assertEqual(server.calls[3][1:], (provider.MAX_HASH_FILE_BYTES, "the hash file"))
        self.assertEqual(len(server.calls), 4)

    def test_the_hash_file_is_the_one_the_gallery_page_links(self):
        _, _, server = run_with(normal_answers())
        self.assertEqual(server.calls[3][0], SIG_URL)

    def failing(self, answers):
        processor, _ = new_processor(PROVIDER, {})
        with patched(Server(answers)):
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        for key in ("url", "version", "expected_sha256"):
            self.assertNotIn(key, processor.env)
        return str(caught.exception)

    def test_a_redirect_that_is_not_the_expected_address_is_an_error_and_sets_no_output(self):
        for location in ("https://example.test/release/inkscape-1.4.4/", "https://inkscape.org/release/", "",
                         "https://inkscape.org/release/inkscape-1.4.4/windows/"):
            with self.subTest(location=location):
                self.assertIn("Inkscape release address:", self.failing({RELEASE_URL: location}))

    def test_a_download_page_that_is_not_what_is_expected_is_an_error_and_sets_no_output(self):
        for page in ("", "<html>Maintenance</html>", page_of(gallery_link(name="x.msi")),
                     page_of(gallery_link(), gallery_link("59505"))):
            answers = normal_answers()
            answers[DL_URL] = page
            with self.subTest(page=page[:30]):
                self.assertIn("Inkscape download page:", self.failing(answers))

    def test_a_gallery_page_that_is_not_what_is_expected_is_an_error_and_sets_no_output(self):
        for page in ("", "<html>Maintenance</html>", page_of(SIG_URL, SIG_URL.replace("PujJ1ID", "Other1")),
                     page_of("http://media.inkscape.org/media/resources/sigs/" + SIG_NAME)):
            answers = normal_answers()
            answers[ITEM_URL] = page
            with self.subTest(page=page[:30]):
                self.assertIn("Inkscape gallery page:", self.failing(answers))

    def test_a_hash_file_that_is_not_what_is_expected_is_an_error_and_sets_no_output(self):
        for text in ("", "<html>Not Found</html>", hash_line(name=FILE_NAME), hash_line(gap=" "),
                     hash_line() + hash_line(HEX_B)):
            answers = normal_answers()
            answers[SIG_URL] = text
            with self.subTest(text=text[:30]):
                self.assertIn("Inkscape hash file:", self.failing(answers))

    def test_a_failure_of_a_request_does_not_leave_a_half_answer_and_asks_for_nothing_more(self):
        order = [RELEASE_URL, DL_URL, ITEM_URL, SIG_URL]
        for index, url in enumerate(order):
            answers = normal_answers()
            answers[url] = ProcessorError("the server said no")
            server = Server(answers)
            processor, _ = new_processor(PROVIDER, {})
            with self.subTest(url=url):
                with patched(server):
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                self.assertIn("the server said no", str(caught.exception))
                self.assertEqual(len(server.calls), index + 1)
                self.assertNotIn("url", processor.env)

    def test_the_version_of_the_redirect_is_the_version_of_the_file_name(self):
        answers = normal_answers()
        answers[RELEASE_URL] = "https://inkscape.org/release/inkscape-1.4.5/"
        answers["https://inkscape.org/release/inkscape-1.4.5/windows/64-bit/msi/dl/"] = answers.pop(DL_URL)
        self.assertIn("Inkscape download page:", self.failing(answers))


class FetchLocationTests(unittest.TestCase):
    URL = provider.RELEASE_URL

    def fetch_with(self, error=None, response=None, url=None):
        def opener(request):
            self.request = request
            if error is not None:
                raise error
            return response
        with mock.patch.object(provider, "open_request", side_effect=opener):
            return provider.fetch_location(url or self.URL, "the thing")

    def redirect(self, code, location, url=None):
        return urllib.error.HTTPError(url or self.URL, code, "Found", {"Location": location} if location is not None else {},
                                      io.BytesIO(b""))

    def test_the_location_of_the_redirect_is_returned_and_not_followed(self):
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                self.assertEqual(self.fetch_with(error=self.redirect(code, RELEASE_LOCATION)), RELEASE_LOCATION)
        self.assertEqual(self.request.full_url, self.URL)
        self.assertEqual(self.request.get_header("User-agent"), provider.USER_AGENT)
        self.assertIsNone(self.request.data)
        self.assertFalse(self.request.has_header("Authorization"))

    def test_a_relative_location_is_made_absolute_and_is_then_checked_like_any_other(self):
        location = self.fetch_with(error=self.redirect(302, "/release/inkscape-1.4.4/"))
        self.assertEqual(location, RELEASE_LOCATION)
        self.assertEqual(provider.parse_release_location(location), "1.4.4")

    def test_a_redirect_without_a_location_is_an_error(self):
        for location in (None, "", "  "):
            with self.subTest(location=location):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=self.redirect(302, location))
                self.assertIn("has no Location header", str(caught.exception))

    def test_an_answer_that_is_not_a_redirect_is_an_error(self):
        for code, reason in ((404, "Not Found"), (500, "Server Error"), (304, "Not Modified")):
            error = urllib.error.HTTPError(self.URL, code, reason, {"Location": RELEASE_LOCATION}, io.BytesIO(b""))
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error)
                self.assertIn("answered %d" % code, str(caught.exception))
                self.assertIn("not with a redirect", str(caught.exception))

    def test_a_page_instead_of_a_redirect_is_an_error(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(response=FakeResponse(b"<html></html>"))
        self.assertIn("not with a redirect", str(caught.exception))
        self.assertIn("200", str(caught.exception))

    def test_a_failed_connection_is_a_processor_error(self):
        for error in (urllib.error.URLError("no route"), TimeoutError("timed out"), OSError("reset"), ValueError("bad url")):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error)
                self.assertIn("could not be asked for the thing", str(caught.exception))

    def test_an_address_outside_the_fixed_hosts_is_refused_before_any_request(self):
        for url in ("https://example.test/release/", "http://inkscape.org/release/", "https://www.inkscape.org/release/",
                    "https://inkscape.org.example.test/release/", "https://inkscape.org@example.test/release/",
                    "https://media.inkscape.org/release/", "https://media.inkscape.org/media/resources/other/x", ""):
            with self.subTest(url=url):
                with mock.patch.object(provider, "open_request") as opener:
                    with self.assertRaises(ProcessorError) as caught:
                        provider.fetch_location(url, "the thing")
                opener.assert_not_called()
                self.assertIn("outside", str(caught.exception))


class FetchTests(unittest.TestCase):
    URL = DL_URL

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

    def test_both_fixed_hosts_are_allowed(self):
        self.assertEqual(self.fetch_with(body=b"x", url=ITEM_URL), "x")
        self.assertEqual(self.fetch_with(body=b"x", url=SIG_URL), "x")

    def test_an_address_outside_the_fixed_hosts_is_refused_before_any_request(self):
        for url in ("https://example.test/release/", "http://inkscape.org/release/", "https://www.inkscape.org/release/",
                    "https://inkscape.org.example.test/release/", "https://inkscape.org@example.test/release/",
                    "https://media.inkscape.org/dl/resources/file/" + FILE_NAME,
                    "https://media.inkscape.org/media/resources/render/x.png",
                    "https://media.inkscape.org.example.test/media/resources/sigs/x.sha256",
                    "https://media.inkscape.org@example.test/media/resources/sigs/x.sha256", ""):
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
            error = urllib.error.HTTPError(self.URL, code, "Moved", {"Location": "https://example.test/"}, io.BytesIO(b""))
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error)
                self.assertIn("a redirect is not followed", str(caught.exception))
                self.assertNotIn("example.test", str(caught.exception))

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

    def test_a_real_opener_turns_a_302_into_an_error_that_holds_the_location(self):
        """The refusing handler and urllib together, against a server of this machine (127.0.0.1,
        no other host): the answer of a 302 reaches the caller as an HTTPError whose headers hold
        the Location, and the Location is not requested."""
        import http.server
        import threading
        requested = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                requested.append(self.path)
                self.send_response(302)
                self.send_header("Location", RELEASE_LOCATION)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        no_proxy_env = {key: "" for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")}
        try:
            request = provider.urllib.request.Request("http://127.0.0.1:%d/release/" % server.server_address[1])
            with mock.patch.dict(os.environ, no_proxy_env):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    provider.open_request(request)
            self.assertEqual(caught.exception.code, 302)
            self.assertEqual(caught.exception.headers.get("Location"), RELEASE_LOCATION)
            caught.exception.close()
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(requested, ["/release/"])

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

    def test_the_limits_are_the_ones_of_the_design(self):
        self.assertEqual(provider.MAX_PAGE_BYTES, 256 * 1024)
        self.assertEqual(provider.MAX_HASH_FILE_BYTES, 4 * 1024)
        self.assertEqual(provider.FETCH_TIMEOUT_SECONDS, 120)


if __name__ == "__main__":
    unittest.main()
