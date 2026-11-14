"""Tests of WizTreeInfoProvider: every branch. No test uses the network:
fetch_text() or open_request() is replaced.

The excerpt (download_page_excerpt.html) is made of lines cut unchanged from the
real page of 2026-11-13, with its real hashes; only its first line was added.
The other pages here are written by hand in the shape of the real one: their
hex digits are made up, not the hash of any file.
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

from _win_support import ProcessorError, run_processor  # noqa: E402  (installs the autopkglib stand-in)

import WizTreeInfoProvider as provider  # noqa: E402

PROVIDER = provider.WizTreeInfoProvider
EXCERPT = os.path.join(TESTS_DIR, "download_page_excerpt.html")
PAGE_URL = "https://diskanalyzer.com/download"
# The real hashes of the page of 2026-11-13: the installer's and the portable zip's.
REAL_INSTALLER_SHA = "3c56dfc08f06c58b9a9133a137c8559e016749e1605cf81e1b1d6b1deead2ff1"
REAL_PORTABLE_SHA = "38b30aab08710613d8a06a7d3dfb777e43ed436cfd7d1ff8bd33d0b5b6bd2c6d"
# Made-up digits, not the hash of any file.
HEX_A = "0123456789abcdef" * 4
HEX_B = "fedcba9876543210" * 4


def button(href, sha=HEX_A, release="4.33", title_sha=None, extra=""):
    """One link in the shape of the real page's buttons."""
    title_sha = sha if title_sha is None else title_sha
    return (
        '<a style="margin-bottom:7px" href="%s" class="orange btn">\r\n'
        '<svg viewBox="0 0 448 512"><path d="M0 93.7l183.6-25.3v177.4H0V93.7z"/></svg>\r\n'
        '&nbsp;<big>DOWNLOAD</big><br>\r\n'
        '<div style="font-weight:normal">V&nbsp;%s&nbsp;16 September 2026 [4.9MB]</div>\r\n'
        '<div class="shacopy" data-sha="%s" title="SHA-256: %s (click to copy)">SHA256: %s…%s</div>%s</a>\r\n'
        % (href, release, sha, title_sha, sha[:8], sha[-8:], extra)
    )


def page(*parts):
    return '<html><head><base href="/" /></head><body>\r\n%s\r\n</body></html>' % "".join(parts)


def normal_page(version_name="4_33", release="4.33", sha=HEX_A, portable_sha=HEX_B):
    return page(
        button("files/wiztree_%s_setup.exe" % version_name, sha, release),
        button("files/wiztree_%s_portable.zip" % version_name, portable_sha, release),
        "<h4>WizTree 4.33 <span>(16 September 2026)</span></h4>\r\n",
        "<h4>WizTree 3.33 <span>(14 May 2020)</span></h4>\r\n",
    )


def run_with(text):
    calls = []

    def fake(url, max_bytes, what):
        calls.append((url, max_bytes, what))
        if isinstance(text, Exception):
            raise text
        return text

    with mock.patch.object(provider, "fetch_text", side_effect=fake):
        result = run_processor(PROVIDER, {})
    return result + (calls,)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ExcerptTests(unittest.TestCase):
    """The lines cut from the real page."""

    def setUp(self):
        with open(EXCERPT, "r", encoding="utf-8") as handle:
            self.page = handle.read()

    def test_the_first_line_says_what_the_excerpt_is(self):
        first = self.page.splitlines()[0]
        self.assertIn("A copy of parts of the real page of 2026-11-13", first)
        self.assertIn("Only this first line was added", first)

    def test_the_excerpt_is_small(self):
        self.assertLess(len(self.page), 20000)

    def test_the_installer_its_label_and_its_own_hash_are_found(self):
        self.assertEqual(provider.find_installer(self.page),
                         ("wiztree_4_33_setup.exe", "4.33", REAL_INSTALLER_SHA))

    def test_the_excerpt_holds_the_portable_zip_and_its_hash_which_are_not_taken(self):
        self.assertIn('href="files/wiztree_4_33_portable.zip"', self.page)
        self.assertIn(REAL_PORTABLE_SHA, self.page)
        self.assertNotEqual(provider.find_installer(self.page)[2], REAL_PORTABLE_SHA)

    def test_the_history_and_an_old_file_name_in_the_text_are_not_a_link(self):
        self.assertIn("<h4>WizTree 3.33", self.page)
        self.assertIn("wiztree_4_14_setup.exe /DIR=", self.page)  # a <samp>, not a link
        self.assertIn("/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-", self.page)

    def test_the_processor_gives_the_address_the_label_and_the_hash(self):
        processor, messages, calls = run_with(self.page)
        self.assertEqual(processor.env["url"], "https://diskanalyzer.com/files/wiztree_4_33_setup.exe")
        self.assertEqual(processor.env["version"], "4.33")
        self.assertEqual(processor.env["expected_sha256"], REAL_INSTALLER_SHA)
        self.assertEqual(calls, [(PAGE_URL, provider.MAX_PAGE_BYTES, "the download page")])

    def test_an_old_installer_linked_in_the_history_stops_the_run(self):
        """If the publisher ever links old installers on this page, the run stops instead of choosing."""
        old = self.page + '<a href="files/wiztree_3_33_setup.exe">old</a>'
        with self.assertRaises(ValueError) as caught:
            provider.find_installer(old)
        self.assertIn("2 links to a WizTree .exe, not exactly one", str(caught.exception))


class LabelTests(unittest.TestCase):
    def test_underscores_become_dots_and_leading_zeros_stay(self):
        self.assertEqual(provider.label_from_name("wiztree_4_33_setup.exe"), "4.33")
        self.assertEqual(provider.label_from_name("wiztree_4_09_setup.exe"), "4.09")
        self.assertEqual(provider.label_from_name("wiztree_4_00_setup.exe"), "4.00")
        self.assertEqual(provider.label_from_name("wiztree_4_14_0_1_setup.exe"), ".".join(["4", "14", "0", "1"]))

    def test_any_other_name_is_refused(self):
        for name in ("wiztree_4_setup.exe", "wiztree_4_33_portable.zip", "WizTree_4_33_setup.exe",
                     "wiztree_4_33_setup.msi", "wiztree_4.33_setup.exe", "wiztree_4_33_1_2_3_setup.exe",
                     "wiztree_4_x_setup.exe", "", None, "../wiztree_4_33_setup.exe"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    provider.label_from_name(name)

    def test_the_client_orders_the_publishers_numbers_as_numbers(self):
        """4.09 comes before 4.10, and 4.04 before 4.33, as the history on the page has them."""
        key = provider.version_key
        self.assertLess(key("4.09"), key("4.10"))
        self.assertLess(key("4.04"), key("4.33"))
        self.assertLess(key("3.41"), key("4.00"))
        self.assertLess(key("4.14"), key(".".join(["4", "14", "0", "1"])))
        self.assertIsNone(key("4"))
        self.assertIsNone(key("v4.33"))


class PageTests(unittest.TestCase):
    def test_a_normal_page_gives_the_installer_and_not_the_zip(self):
        self.assertEqual(provider.find_installer(normal_page()), ("wiztree_4_33_setup.exe", "4.33", HEX_A))

    def test_the_zip_first_does_not_change_the_answer(self):
        text = page(button("files/wiztree_4_33_portable.zip", HEX_B), button("files/wiztree_4_33_setup.exe", HEX_A))
        self.assertEqual(provider.find_installer(text)[2], HEX_A)

    def test_single_quotes_and_entities_in_the_address_are_read(self):
        text = page(button("files/wiztree_4_33_setup.exe", HEX_A).replace('href="files/wiztree_4_33_setup.exe"',
                                                                        "href='files/wiztree&#95;4_33_setup.exe'"))
        self.assertEqual(provider.find_installer(text)[0], "wiztree_4_33_setup.exe")

    def test_no_installer_link_stops(self):
        text = page(button("files/wiztree_4_33_portable.zip", HEX_B))
        with self.assertRaises(ValueError) as caught:
            provider.find_installer(text)
        self.assertIn("no link to files/wiztree_<numbers>_setup.exe", str(caught.exception))

    def test_the_same_link_twice_stops(self):
        text = page(button("files/wiztree_4_33_setup.exe", HEX_A), button("files/wiztree_4_33_setup.exe", HEX_A))
        with self.assertRaises(ValueError) as caught:
            provider.find_installer(text)
        self.assertIn("2 links to a WizTree .exe", str(caught.exception))

    def test_a_link_in_another_form_stops(self):
        for href in ("https://diskanalyzer.com/files/wiztree_4_33_setup.exe", "/files/wiztree_4_33_setup.exe",
                     "other/wiztree_4_33_setup.exe", "files/wiztree_4_33_setup_x64.exe", "files/WizTree_4_33_Setup.exe",
                     "files/wiztree_4_33_setup.exe?x=1"):
            with self.subTest(href=href):
                text = page(button(href, HEX_A), button("files/wiztree_4_33_setup.exe", HEX_A))
                with self.assertRaises(ValueError) as caught:
                    provider.find_installer(text)
                self.assertIn("in another form", str(caught.exception))

    def test_a_link_without_its_end_stops(self):
        text = page(button("files/wiztree_4_33_setup.exe", HEX_A).replace("</a>", ""))
        with self.assertRaises(ValueError) as caught:
            provider.find_installer(text)
        self.assertIn("has no </a>", str(caught.exception))

    def test_another_link_inside_the_installers_link_stops(self):
        """Without its own </a> the content would run into the zip's link and its hash."""
        text = page(button("files/wiztree_4_33_setup.exe", HEX_A).replace("</a>", ""),
                    button("files/wiztree_4_33_portable.zip", HEX_B))
        with self.assertRaises(ValueError) as caught:
            provider.find_installer(text)
        self.assertIn("holds another <a> element", str(caught.exception))

    def test_no_hash_inside_the_link_stops(self):
        block = button("files/wiztree_4_33_setup.exe", HEX_A).replace('data-sha="%s"' % HEX_A, "")
        block = block.replace("SHA-256: %s" % HEX_A, "SHA-256: none")
        with self.assertRaises(ValueError) as caught:
            provider.find_installer(page(block, button("files/wiztree_4_33_portable.zip", HEX_B)))
        self.assertIn("0 data-sha hashes", str(caught.exception))

    def test_two_hashes_inside_the_link_stop(self):
        block = button("files/wiztree_4_33_setup.exe", HEX_A, extra='<div data-sha="%s"></div>' % HEX_B)
        with self.assertRaises(ValueError) as caught:
            provider.find_installer(page(block))
        self.assertIn("2 data-sha hashes", str(caught.exception))

    def test_a_title_that_names_another_hash_stops(self):
        block = button("files/wiztree_4_33_setup.exe", HEX_A, title_sha=HEX_B)
        with self.assertRaises(ValueError) as caught:
            provider.find_installer(page(block))
        self.assertIn("2 different SHA-256 values", str(caught.exception))

    def test_a_hash_that_is_not_64_hex_digits_is_not_a_hash(self):
        block = button("files/wiztree_4_33_setup.exe", HEX_A[:63])
        with self.assertRaises(ValueError):
            provider.find_installer(page(block))

    def test_a_release_text_that_is_not_the_file_names_label_stops(self):
        with self.assertRaises(ValueError) as caught:
            provider.find_installer(normal_page(release="4.32"))
        self.assertIn("says release 4.32, not 4.33", str(caught.exception))

    def test_no_release_text_stops(self):
        block = button("files/wiztree_4_33_setup.exe", HEX_A).replace("V&nbsp;4.33&nbsp;", "")
        with self.assertRaises(ValueError) as caught:
            provider.find_installer(page(block))
        self.assertIn("0 release texts", str(caught.exception))

    def test_two_release_texts_stop(self):
        block = button("files/wiztree_4_33_setup.exe", HEX_A, extra="<div>V&nbsp;4.33&nbsp;again</div>")
        with self.assertRaises(ValueError) as caught:
            provider.find_installer(page(block))
        self.assertIn("2 release texts", str(caught.exception))

    def test_a_label_with_a_leading_zero_is_kept(self):
        text = normal_page(version_name="4_09", release="4.09")
        self.assertEqual(provider.find_installer(text)[1], "4.09")


class ProcessorTests(unittest.TestCase):
    def test_a_page_error_stops_the_recipe_with_a_clear_message(self):
        with self.assertRaises(ProcessorError) as caught:
            run_with(page())
        self.assertIn("WizTree download page: the page has no link", str(caught.exception))

    def test_a_fetch_error_is_passed_on(self):
        with self.assertRaises(ProcessorError) as caught:
            run_with(ProcessorError("The server answered 503 x for the download page."))
        self.assertIn("503", str(caught.exception))

    def test_the_outputs_and_no_inputs(self):
        self.assertEqual(sorted(PROVIDER.output_variables), ["expected_sha256", "url", "version"])
        self.assertEqual(PROVIDER.input_variables, {})
        processor, messages, _ = run_with(normal_page())
        self.assertEqual(processor.env["url"], "https://diskanalyzer.com/files/wiztree_4_33_setup.exe")
        self.assertTrue(any("label 4.33" in message for message in messages))


class FetchTests(unittest.TestCase):
    def test_only_the_page_address_is_fetched(self):
        for url in ("https://diskanalyzer.com/files/wiztree_4_33_setup.exe", "http://diskanalyzer.com/download",
                    "https://example.com/download", "https://diskanalyzer.com/download/"):
            with self.subTest(url=url):
                with mock.patch.object(provider, "open_request") as opened:
                    with self.assertRaises(ProcessorError):
                        provider.fetch_text(url, 100, "the download page")
                    opened.assert_not_called()

    def test_the_answer_is_read_as_utf_8_with_the_agent_of_the_processor(self):
        with mock.patch.object(provider, "open_request", return_value=FakeResponse("café".encode("utf-8"))) as opened:
            self.assertEqual(provider.fetch_text(PAGE_URL, 100, "the download page"), "café")
        request = opened.call_args[0][0]
        self.assertEqual(request.get_header("User-agent"), provider.USER_AGENT)
        self.assertEqual(request.full_url, PAGE_URL)

    def test_an_answer_over_the_limit_stops(self):
        with mock.patch.object(provider, "open_request", return_value=FakeResponse(b"x" * 101)):
            with self.assertRaises(ProcessorError) as caught:
                provider.fetch_text(PAGE_URL, 100, "the download page")
        self.assertIn("larger than 100 bytes", str(caught.exception))

    def test_an_answer_that_is_not_utf_8_stops(self):
        with mock.patch.object(provider, "open_request", return_value=FakeResponse(b"\xff\xfe")):
            with self.assertRaises(ProcessorError) as caught:
                provider.fetch_text(PAGE_URL, 100, "the download page")
        self.assertIn("not UTF-8", str(caught.exception))

    def test_a_redirect_is_an_error_and_not_followed(self):
        error = urllib.error.HTTPError(PAGE_URL, 301, "Moved Permanently", {}, io.BytesIO(b""))
        with mock.patch.object(provider, "open_request", side_effect=error):
            with self.assertRaises(ProcessorError) as caught:
                provider.fetch_text(PAGE_URL, 100, "the download page")
        self.assertIn("301", str(caught.exception))
        self.assertIn("a redirect is not followed", str(caught.exception))

    def test_a_network_error_stops(self):
        with mock.patch.object(provider, "open_request", side_effect=urllib.error.URLError("no route")):
            with self.assertRaises(ProcessorError) as caught:
                provider.fetch_text(PAGE_URL, 100, "the download page")
        self.assertIn("could not be asked", str(caught.exception))

    def test_the_redirect_handler_follows_nothing(self):
        handler = provider.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 301, "Moved", {}, "https://example.com/"))

    def test_the_limits(self):
        self.assertEqual(provider.MAX_PAGE_BYTES, 512 * 1024)
        self.assertEqual(provider.FETCH_TIMEOUT_SECONDS, 120)
        self.assertTrue(provider.PAGE_URL.startswith("https://"))


if __name__ == "__main__":
    unittest.main()
