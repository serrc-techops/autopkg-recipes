"""Tests of AdobeReaderInfoProvider: every branch. No test uses the network:
fetch_text() or open_request() is replaced.

THE EXCERPT IS WRITTEN BY HAND. adobe_products_excerpt.json was written by hand
after the real answer of 2026-10-02, not saved from the real server: the shape
of `products.reader` and `products.dcPro` is the real one, the other keys are
cut and the add-on is made up. A test that reads it is still a real test of the
parser, but it proves nothing about what Adobe's endpoint answers today: the
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

import AdobeReaderInfoProvider as provider  # noqa: E402

PROVIDER = provider.AdobeReaderInfoProvider
EXCERPT = os.path.join(TESTS_DIR, "adobe_products_excerpt.json")
HAND_WRITTEN_NOTE = "written by hand after the real answer of 2026-10-02, not saved from the real server"
DOWNLOAD_BASE = "https://ardownload2.adobe.com/pub/adobe/reader/win/AcrobatDC/"
BACKSLASH_PATH = "a" + chr(92) + "b"


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def products_text(version="26.002.21931", **extra):
    data = {
        "products": {
            "reader": [{"displayName": "Reader X", "fileSize": 748.0, "version": version}],
            "dcPro": [{"displayName": "AcrobatProDC", "fileSize": 1194.0, "version": "25.001.20693"}],
        },
        "addons": [],
    }
    data.update(extra)
    return json.dumps(data)


def fetcher(text, record=None):
    """A stand-in for fetch_text that answers the products address and writes down what was asked."""
    def fetch(url, max_bytes, what):
        if record is not None:
            record.append((url, max_bytes, what))
        if url == provider.PRODUCTS_URL:
            return text
        raise AssertionError("an address that nobody expected: %s" % url)
    return fetch


def run_on(text, env=None, record=None):
    with mock.patch.object(provider, "fetch_text", side_effect=fetcher(text, record)):
        return run_processor(PROVIDER, env or {})


def fails_on(text, env=None):
    processor, _ = new_processor(PROVIDER, env or {})
    with mock.patch.object(provider, "fetch_text", side_effect=fetcher(text)):
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
    """The hand-written excerpt (see the note at the top of this file)."""

    def setUp(self):
        self.text = read(EXCERPT)

    def test_the_excerpt_says_that_it_is_written_by_hand(self):
        self.assertEqual(json.loads(self.text)["_written_by_hand"].split(";")[0], HAND_WRITTEN_NOTE)
        self.assertIn("WRITTEN BY HAND", read(__file__))
        self.assertIn("after the real answer of 2026-10-02", read(__file__))

    def test_the_excerpt_is_small(self):
        self.assertLess(len(self.text), 2000)

    def test_the_excerpt_has_the_shape_of_the_real_answer(self):
        data = json.loads(self.text)
        self.assertEqual(sorted(data["products"]), ["dcPro", "reader"])
        self.assertEqual(len(data["products"]["reader"]), 1)
        self.assertEqual(sorted(data["products"]["reader"][0]), ["displayName", "fileSize", "version"])

    def test_the_english_installer(self):
        processor, messages = run_on(self.text)
        self.assertEqual(processor.env["version"], "26.002.21931")
        self.assertEqual(processor.env["adobe_packed_version"], "2600221931")
        self.assertEqual(
            processor.env["url"],
            DOWNLOAD_BASE + "2600221931/AcroRdrDC2600221931_en_US.exe",
        )
        self.assertTrue(any("26.002.21931" in m for m in messages))

    def test_the_installer_for_all_languages(self):
        processor, _ = run_on(self.text, {"adobe_language": "MUI"})
        self.assertEqual(processor.env["url"], DOWNLOAD_BASE + "2600221931/AcroRdrDC2600221931_MUI.exe")
        self.assertEqual(processor.env["version"], "26.002.21931")

    def test_the_other_products_are_not_read(self):
        data = json.loads(self.text)
        data["products"]["dcPro"][0]["version"] = "not a version at all"
        data["addons"] = "not a list"
        processor, _ = run_on(json.dumps(data))
        self.assertEqual(processor.env["version"], "26.002.21931")

    def test_the_request_is_the_fixed_address_with_its_limit(self):
        record = []
        run_on(self.text, record=record)
        self.assertEqual(record, [(provider.PRODUCTS_URL, provider.MAX_PRODUCTS_BYTES, "Adobe's products file")])


class ParseProductsTests(unittest.TestCase):
    def test_the_version_of_the_one_reader(self):
        self.assertEqual(provider.parse_products(products_text("26.002.21931")), "26.002.21931")
        self.assertEqual(provider.parse_products(products_text("99.999.99999")), "99.999.99999")
        self.assertEqual(provider.parse_products(products_text("00.000.00000")), "00.000.00000")

    def test_a_text_that_is_not_the_answer_is_an_error(self):
        for text, part in (
            ("", "not JSON"), ("not json", "not JSON"), ("{", "not JSON"), ("<html>403</html>", "not JSON"),
            ("[]", "not a JSON object"), ('"text"', "not a JSON object"), ("null", "not a JSON object"),
            ("{}", "no object products"), ('{"products": []}', "no object products"),
            ('{"products": null}', "no object products"), ('{"products": {}}', "products.reader is not a list"),
            ('{"products": {"reader": null}}', "products.reader is not a list"),
            ('{"products": {"reader": {"version": "26.002.21931"}}}', "products.reader is not a list"),
            ('{"products": {"reader": "26.002.21931"}}', "products.reader is not a list"),
            ('{"products": {"reader": []}}', "0 elements"),
            ('{"products": {"reader": ["26.002.21931"]}}', "not an object"),
            ('{"products": {"reader": [null]}}', "not an object"),
            ('{"products": {"reader": [{}]}}', "no text version"),
            ('{"products": {"reader": [{"version": null}]}}', "no text version"),
            ('{"products": {"reader": [{"version": 26.002}]}}', "no text version"),
            ('{"products": {"reader": [{"version": ["26.002.21931"]}]}}', "no text version"),
        ):
            with self.subTest(text=text[:50]):
                with self.assertRaises(ValueError) as caught:
                    provider.parse_products(text)
                self.assertIn(part, str(caught.exception))

    def test_two_readers_or_more_are_an_error_also_when_they_agree(self):
        one = {"displayName": "Reader", "fileSize": 1.0, "version": "26.002.21931"}
        for readers in ([one, one], [one, dict(one, version="26.002.21930")], [one, one, one]):
            text = json.dumps({"products": {"reader": readers}})
            with self.subTest(count=len(readers)):
                with self.assertRaises(ValueError) as caught:
                    provider.parse_products(text)
                self.assertIn("%d elements, not exactly one" % len(readers), str(caught.exception))

    def test_a_version_that_is_not_two_three_and_five_digits_is_an_error(self):
        for value in ("", "26", "26.002", "26.2.21931", "26.002.2193", "26.002.219310", "2026.002.21931",
                      "26.002.21931.0", "v26.002.21931", " 26.002.21931", "26.002.21931 ", "26.002.21931\n",
                      "26.002.2193x", "26.002.21931-beta", "26,002,21931", "26.002.21931/../x", "26..21931",
                      "٢٦.٠٠٢.٢١٩٣١", "26.002.21931%20", "../../x"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    provider.parse_products(products_text(value))
                self.assertIn("is not of the form NN.NNN.NNNNN", str(caught.exception))

    def test_the_error_does_not_print_a_long_value(self):
        with self.assertRaises(ValueError) as caught:
            provider.parse_products(products_text("9" * 5000))
        self.assertLess(len(str(caught.exception)), 200)


class PackedVersionTests(unittest.TestCase):
    def test_the_dots_are_removed(self):
        self.assertEqual(provider.packed_version("26.002.21931"), "2600221931")
        self.assertEqual(provider.packed_version("25.001.20693"), "2500120693")
        self.assertEqual(provider.packed_version("00.000.00000"), "0000000000")

    def test_anything_that_is_not_a_version_is_an_error(self):
        for value in ("", "2600221931", "26.002", "26.002.21931.1", None, 26.002, ["26.002.21931"]):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    provider.packed_version(value)


class InstallerAddressTests(unittest.TestCase):
    def test_the_two_installers(self):
        self.assertEqual(provider.installer_url("2600221931", "en_US"),
                         DOWNLOAD_BASE + "2600221931/AcroRdrDC2600221931_en_US.exe")
        self.assertEqual(provider.installer_url("2600221931", "MUI"),
                         DOWNLOAD_BASE + "2600221931/AcroRdrDC2600221931_MUI.exe")

    def test_the_address_is_https_on_the_download_host_and_ends_in_exe(self):
        url = provider.installer_url("2600221931", "en_US")
        self.assertTrue(url.startswith("https://ardownload2.adobe.com/pub/adobe/reader/win/AcrobatDC/"))
        self.assertTrue(url.endswith(".exe"))
        self.assertNotIn(" ", url)
        self.assertNotIn("x64", url)

    def test_a_language_that_is_not_one_of_the_two_is_an_error(self):
        for language in ("", "en_us", "EN_US", "mui", "de_DE", "en", " MUI", "MUI ", "../x", None, 5, ["MUI"]):
            with self.subTest(language=language):
                with self.assertRaises(ValueError):
                    provider.installer_url("2600221931", language)

    def test_a_packed_version_that_is_not_ten_digits_is_an_error(self):
        for packed in ("", "260022193", "26002219311", "26002x1931", "2600221931/", "../2600221931", None):
            with self.subTest(packed=packed):
                with self.assertRaises(ValueError):
                    provider.installer_url(packed, "en_US")


class CheckAddressTests(unittest.TestCase):
    def test_only_the_one_host_over_https_is_allowed(self):
        for url in (
            "http://rdc.adobe.io/reader/products",
            "https://example.test/reader/products",
            "https://ardownload2.adobe.com/pub/adobe/reader/win/AcrobatDC/",
            "https://adobe.io/reader/products",
            "https://rdc.adobe.io.example.test/x",
            "https://example.test/https://rdc.adobe.io/",
            "https://user@rdc.adobe.io/x",
            "https://user:pw@rdc.adobe.io/x",
            "https://rdc.adobe.io:8443/x",
            "https://rdc.adobe.io/x#frag",
            "ftp://rdc.adobe.io/x",
            "file:///etc/passwd",
            "",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    provider.check_address(url)

    def test_the_constants_are_the_vendors_addresses_over_https(self):
        provider.check_address(provider.PRODUCTS_URL)
        self.assertEqual(provider.ALLOWED_HOST, "rdc.adobe.io")
        self.assertTrue(provider.PRODUCTS_URL.startswith("https://rdc.adobe.io/reader/products?"))
        for part in ("lang=en", "platformArch=64", "site=landing", "os=Windows%2010", "preInstalled=",
                     "country=US", "nativeOs=Windows%2010", "api_key=dc-get-adobereader-cdn"):
            self.assertIn(part, provider.PRODUCTS_URL.split("?", 1)[1].split("&"))
        self.assertTrue(provider.DOWNLOAD_BASE_URL.endswith("/"))
        self.assertTrue(provider.DOWNLOAD_BASE_URL.startswith("https://ardownload2.adobe.com/"))


class MainTests(unittest.TestCase):
    def test_the_declared_defaults_equal_the_values_the_code_uses(self):
        declared = {name: flags["default"] for name, flags in PROVIDER.input_variables.items()}
        self.assertEqual(declared, {"adobe_language": "en_US"})
        for flags in PROVIDER.input_variables.values():
            self.assertIs(flags["required"], False)
            self.assertTrue(flags["description"])
        self.assertEqual(sorted(PROVIDER.output_variables), ["adobe_packed_version", "url", "version"])
        self.assertEqual(provider.LANGUAGES, ("en_US", "MUI"))
        self.assertEqual(provider.DEFAULT_LANGUAGE, "en_US")

    def test_a_language_that_is_not_allowed_is_an_error_and_nothing_is_fetched(self):
        for value in ("", "en_us", "de_DE", "MUI ", " MUI", "mui", None, 5, ["MUI"], "MUI\n"):
            processor, _ = new_processor(PROVIDER, {"adobe_language": value})
            with self.subTest(value=value):
                with mock.patch.object(provider, "fetch_text") as fetch:
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                fetch.assert_not_called()
                self.assertIn("adobe_language", str(caught.exception))

    def test_a_products_file_that_is_not_what_is_expected_is_a_processor_error_and_sets_no_output(self):
        for text, part in (
            ("", "not JSON"), ("[]", "not a JSON object"), ("{}", "no object products"),
            (json.dumps({"products": {"reader": []}}), "0 elements"),
            (products_text("26.2.21931"), "is not of the form"),
        ):
            processor, _ = new_processor(PROVIDER, {})
            with self.subTest(text=text[:40]):
                with mock.patch.object(provider, "fetch_text", side_effect=fetcher(text)):
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                self.assertIn("Adobe's products file", str(caught.exception))
                self.assertIn(part, str(caught.exception))
                for key in ("url", "version", "adobe_packed_version"):
                    self.assertNotIn(key, processor.env)

    def test_a_bad_version_never_reaches_an_address(self):
        error, processor = fails_on(products_text("26.002.21931/../../x"))
        self.assertNotIn("url", processor.env)
        self.assertIn("is not of the form", str(error))

    def test_a_fetch_error_passes_through_and_sets_no_output(self):
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "fetch_text", side_effect=ProcessorError("down")):
            with self.assertRaises(ProcessorError):
                processor.main()
        self.assertNotIn("url", processor.env)

    def test_the_output_version_is_the_text_of_the_answer_and_the_packed_one_has_no_dots(self):
        for version in ("26.002.21931", "27.001.20001", "28.010.30123"):
            with self.subTest(version=version):
                processor, _ = run_on(products_text(version))
                self.assertEqual(processor.env["version"], version)
                self.assertEqual(processor.env["adobe_packed_version"], version.replace(".", ""))
                self.assertRegex(processor.env["adobe_packed_version"], r"^[0-9]{10}$")
                self.assertIn("/%s/AcroRdrDC%s_" % (processor.env["adobe_packed_version"],
                                                    processor.env["adobe_packed_version"]), processor.env["url"])


class FetchTests(unittest.TestCase):
    URL = provider.PRODUCTS_URL

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
            for url in ("https://example.test/x", "http://rdc.adobe.io/x"):
                with self.subTest(url=url):
                    with self.assertRaises(ProcessorError) as caught:
                        provider.fetch_text(url, 100, "the file")
                    self.assertIn("not on the fixed host", str(caught.exception))
        opener.assert_not_called()

    def test_a_status_other_than_200_is_an_error_that_names_it(self):
        for code, reason in ((403, "Forbidden"), (404, "Not Found"), (500, "Server Error"), (429, "Too Many Requests")):
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

    def test_the_limits_are_the_ones_of_the_brief(self):
        self.assertEqual(provider.MAX_PRODUCTS_BYTES, 64 * 1024)
        self.assertEqual(provider.FETCH_TIMEOUT_SECONDS, 120)


class SourceTests(unittest.TestCase):
    def test_the_module_fetches_from_one_host_and_holds_no_hash(self):
        text = read(os.path.join(RECIPE_DIR, "AdobeReaderInfoProvider.py"))
        hosts = set(re.findall(r"https?://([A-Za-z0-9.-]+)", text))
        self.assertEqual(hosts, {provider.ALLOWED_HOST, "ardownload2.adobe.com"})
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", text))

    def test_the_module_outputs_no_hash(self):
        self.assertNotIn("expected_sha256", PROVIDER.output_variables)
        self.assertNotIn("expected_sha256", read(os.path.join(RECIPE_DIR, "AdobeReaderInfoProvider.py")))


if __name__ == "__main__":
    unittest.main()
