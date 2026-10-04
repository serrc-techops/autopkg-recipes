"""Tests of FoxitInfoProvider: every branch. No test uses the network:
read_location() or open_request() is replaced, or a stand-in handler answers.

THE ANSWERS ARE WRITTEN BY HAND. The processor reads only the Location header
of two answers, so no page was saved. The addresses in this file were written
by hand after the three real answers of 2026-10-02 (301, 307, 302), with the
version and the file name of that day; the signed address of the third answer
is made up and is never fetched. A test that reads them is still a real test
of the parser, but it proves nothing about what Foxit's servers answer today:
the first run on the build Mac is that check.
"""
import email.message
import http.client
import io
import os
import re
import sys
import unittest
import urllib.error
import urllib.request
import urllib.response
from unittest import mock

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.dirname(TESTS_DIR)
SHARED_TESTS_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-SharedProcessors", "tests")
for folder in (SHARED_TESTS_DIR, RECIPE_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

from _win_support import ProcessorError, new_processor, run_processor  # noqa: E402  (installs the autopkglib stand-in)

import FoxitInfoProvider as provider  # noqa: E402

PROVIDER = provider.FoxitInfoProvider

# The three addresses of 2026-10-02, in the form of the real answers.
FIRST = ("https://www.foxit.com/downloads/latest.html?product=Foxit-Reader&platform=Windows"
         "&version=&package_type=exe&language=L10N")
SECOND = ("https://www.foxit.com/downloads/latest/?product=Foxit-Reader&platform=Windows"
          "&version=&package_type=exe&language=L10N")
FINAL_PATH = "/product/reader/desktop/win/2026.2.1/FoxitPDFReader202621_L10N_Setup_Prom_x64.exe"
FINAL = "https://cdn01.foxitsoftware.com" + FINAL_PATH
CDN = "https://cdn01.foxitsoftware.com"


def numbers(*parts):
    """A version of several numbers, built here so that no four numbers stand in
    this file as they are."""
    return ".".join(str(part) for part in parts)


def final_address(version="2026.2.1", digits="202621", language="L10N", host="cdn01.foxitsoftware.com"):
    return "https://%s/product/reader/desktop/win/%s/FoxitPDFReader%s_%s_Setup_Prom_x64.exe" % (
        host, version, digits, language)


def answers(first=SECOND, second=FINAL, record=None):
    """A stand-in for read_location that answers by address and writes down what was asked."""
    def read(url, what):
        if record is not None:
            record.append((url, what))
        if url.startswith(provider.START_URL_BASE + "?"):
            return first
        if url.startswith("https://www.foxit.com/downloads/latest/?") or url == SECOND:
            return second
        raise AssertionError("an address that nobody expected: %s" % url)
    return read


def run_on(first=SECOND, second=FINAL, env=None, record=None):
    with mock.patch.object(provider, "read_location", side_effect=answers(first, second, record)):
        return run_processor(PROVIDER, env or {})


def fails_on(first=SECOND, second=FINAL, env=None):
    """Run the processor on two answers, expect a ProcessorError, return it and the processor."""
    processor, _ = new_processor(PROVIDER, env or {})

    def read(url, what):
        if url.startswith(provider.START_URL_BASE + "?"):
            return first
        return second
    with mock.patch.object(provider, "read_location", side_effect=read):
        try:
            processor.main()
        except ProcessorError as err:
            return err, processor
    raise AssertionError("the processor did not stop")


def headers(*locations):
    message = email.message.Message()
    for location in locations:
        message.add_header("Location", location)
    return message


class FakeResponse(io.BytesIO):
    status = 200
    was_read = False

    def read(self, *args):
        self.was_read = True
        return super().read(*args)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def redirect(code, *locations, url=FIRST):
    return urllib.error.HTTPError(url, code, "Moved", headers(*locations), io.BytesIO(b""))


class HappyPathTests(unittest.TestCase):
    def test_the_three_answers_of_the_real_chain(self):
        processor, messages = run_on()
        self.assertEqual(processor.env["url"], FINAL)
        self.assertEqual(processor.env["foxit_address_version"], "2026.2.1")
        self.assertTrue(any("2026.2.1" in m for m in messages))
        self.assertTrue(any("not the label of the recipe" in m for m in messages))

    def test_exactly_two_requests_the_first_one_the_start_address(self):
        record = []
        run_on(record=record)
        self.assertEqual([item[0] for item in record], [FIRST, SECOND])

    def test_the_second_request_goes_to_the_address_of_the_first_answer(self):
        record = []
        other = "https://www.foxit.com/downloads/latest/?other=1"
        with mock.patch.object(provider, "read_location",
                               side_effect=answers(other, FINAL, record)) as read:
            read.side_effect = lambda url, what: (record.append(url) or (other if url == FIRST else FINAL))
            run_processor(PROVIDER, {})
        self.assertEqual(record, [FIRST, other])

    def test_the_outputs_are_the_two_declared_and_no_hash_and_no_version(self):
        processor, _ = run_on()
        self.assertEqual(sorted(PROVIDER.output_variables), ["foxit_address_version", "url"])
        self.assertNotIn("version", processor.env)
        self.assertNotIn("expected_sha256", processor.env)

    def test_the_declared_defaults_equal_the_values_the_code_uses(self):
        declared = {name: flags["default"] for name, flags in PROVIDER.input_variables.items()}
        self.assertEqual(declared, {"foxit_product": "Foxit-Reader", "foxit_language": "L10N",
                                    "foxit_package_type": "exe"})
        for flags in PROVIDER.input_variables.values():
            self.assertIs(flags["required"], False)
            self.assertTrue(flags["description"])

    def test_the_version_may_have_any_number_of_parts_from_two(self):
        for version, digits in (("2026.2", "20262"), ("2026.2.1", "202621"), (numbers(2026, 2, 1, 5), "2026215")):
            with self.subTest(version=version):
                processor, _ = run_on(second=final_address(version, digits))
                self.assertEqual(processor.env["foxit_address_version"], version)

    def test_the_url_is_built_from_the_fixed_host_and_the_checked_path(self):
        processor, _ = run_on(second=final_address(host="CDN01.FoxitSoftware.com"))
        self.assertEqual(processor.env["url"], FINAL)

    def test_the_language_follows_the_input(self):
        processor, _ = run_on(env={"foxit_language": "en-US"}, second=final_address(language="en-US"),
                              first=SECOND)
        self.assertEqual(processor.env["url"], final_address(language="en-US"))


class StartAddressTests(unittest.TestCase):
    def test_the_defaults_give_the_address_that_foxit_sends(self):
        self.assertEqual(provider.start_url("Foxit-Reader", "L10N", "exe"), FIRST)

    def test_the_inputs_are_in_the_query_and_the_version_stays_empty(self):
        url = provider.start_url("Foxit-Other", "en-US", "msi")
        self.assertEqual(url, "https://www.foxit.com/downloads/latest.html?product=Foxit-Other&platform=Windows"
                              "&version=&package_type=msi&language=en-US")
        self.assertIn("&version=&", url)

    def test_the_processor_asks_for_the_address_of_its_inputs(self):
        record = []
        env = {"foxit_product": "Foxit-Other", "foxit_language": "L10N", "foxit_package_type": "exe"}
        processor, _ = new_processor(PROVIDER, env)
        with mock.patch.object(provider, "read_location", side_effect=lambda url, what: record.append(url) or SECOND):
            with self.assertRaises(ProcessorError):
                processor.main()
        self.assertEqual(record[0], provider.start_url("Foxit-Other", "L10N", "exe"))


class InputTests(unittest.TestCase):
    BAD = ("", " ", "a b", "../x", "a/b", "a" + chr(92) + "b", "a.b", "a_b", "a?b", "a&b=c", "a#b", "a%20b",
           "x\n", "é", "x;y", "\x00", 5, ["x"], {"a": 1}, True)

    def test_a_name_that_is_not_a_name_is_an_error_and_nothing_is_fetched(self):
        for name in ("foxit_product", "foxit_language", "foxit_package_type"):
            for value in self.BAD:
                processor, _ = new_processor(PROVIDER, {name: value})
                with self.subTest(name=name, value=value):
                    with mock.patch.object(provider, "read_location") as read:
                        with self.assertRaises(ProcessorError) as caught:
                            processor.main()
                    read.assert_not_called()
                    self.assertIn(name, str(caught.exception))

    def test_names_that_are_fine(self):
        for value in ("Foxit-Reader", "L10N", "exe", "en-US", "x", "A-1"):
            with self.subTest(value=value):
                self.assertEqual(provider.checked_name(value, "foxit_language", "L10N"), value)
        self.assertEqual(provider.checked_name(None, "foxit_language", "L10N"), "L10N")


class FirstAnswerTests(unittest.TestCase):
    def test_a_first_answer_that_is_not_https_on_the_first_host_is_an_error(self):
        for bad in (
            FINAL,                                               # straight to the cdn host: not the layout read
            "http://www.foxit.com/downloads/latest/?x=1",
            "https://www.foxit.com.example.test/downloads/latest/",
            "https://example.test/https://www.foxit.com/downloads/latest/",
            "https://user@www.foxit.com/downloads/latest/",
            "https://user:pw@www.foxit.com/downloads/latest/",
            "https://www.foxit.com:8443/downloads/latest/",
            "https://www.foxit.com/downloads/latest/#frag",
            "https://foxit.com/downloads/latest/",
            "https://downloads.foxit.com/x",
            "ftp://www.foxit.com/x",
            "file:///etc/passwd",
            "//example.test/x",
        ):
            with self.subTest(bad=bad):
                error, processor = fails_on(first=bad)
                self.assertIn("Foxit's download address", str(error))
                for key in ("url", "foxit_address_version"):
                    self.assertNotIn(key, processor.env)

    def test_the_second_address_is_never_asked_when_the_first_answer_is_wrong(self):
        record = []
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "read_location", side_effect=answers("https://example.test/x", FINAL, record)):
            with self.assertRaises(ProcessorError):
                processor.main()
        self.assertEqual([item[0] for item in record], [FIRST])


class SecondAnswerTests(unittest.TestCase):
    def test_a_second_answer_on_another_host_or_with_another_form_is_an_error(self):
        for bad in (
            "http://cdn01.foxitsoftware.com" + FINAL_PATH,
            "https://cdn02.foxitsoftware.com" + FINAL_PATH,
            "https://cdn01.foxitsoftware.com.example.test" + FINAL_PATH,
            "https://example.test" + FINAL_PATH,
            "https://www.foxit.com" + FINAL_PATH,
            "https://example.test/https://cdn01.foxitsoftware.com" + FINAL_PATH,
            "https://user@cdn01.foxitsoftware.com" + FINAL_PATH,
            "https://user:pw@cdn01.foxitsoftware.com" + FINAL_PATH,
            "https://cdn01.foxitsoftware.com:8443" + FINAL_PATH,
            FINAL + "#frag",
            FINAL + "?token=1",
            FINAL + "?",
            "file:///etc/passwd",
        ):
            with self.subTest(bad=bad):
                error, processor = fails_on(second=bad)
                self.assertIn("Foxit's second download address", str(error))
                for key in ("url", "foxit_address_version"):
                    self.assertNotIn(key, processor.env)

    def test_a_path_that_is_not_the_expected_one_is_an_error(self):
        base = "/product/reader/desktop/win/2026.2.1/FoxitPDFReader202621_L10N_Setup_Prom_x64.exe"
        for path in (
            "",
            "/",
            base + "/",
            base + "x",
            base.replace(".exe", ".msi"),
            base.replace(".exe", ".EXE"),
            base.replace("x64", "x86"),
            base.replace("Prom_x64", "x64"),
            base.replace("Setup_Prom", "Setup"),
            base.replace("/win/", "/mac/"),
            base.replace("/reader/", "/phantom/"),
            base.replace("/desktop/", "/server/"),
            "/product" + base[len("/product"):] + "/../x",
            "/x" + base,
            base.replace("/win/", "/win/extra/"),
            base.replace("2026.2.1/", "2026.2.1//"),
            base.replace("FoxitPDFReader", "FoxitPDFReader-"),
            base.replace("FoxitPDFReader202621", "FoxitPDFReader"),
            base.replace("FoxitPDFReader202621", "FoxitPDFReaderab"),
            base.replace("FoxitPDFReader202621", "foxitpdfreader202621"),
            base.replace("_L10N_", "__"),
            base.replace("_L10N_", "_L10N _"),
            base.replace("2026.2.1/", "%32026.2.1/"),
            base.replace("2026.2.1/", "../2026.2.1/"),
        ):
            with self.subTest(path=path):
                error, _ = fails_on(second=CDN + path)
                self.assertIn("Foxit's second download address", str(error))

    def test_a_version_that_is_not_numbers_and_dots_is_an_error(self):
        for version in ("2026", "2026.", ".2026.2", "2026..2", "v2026.2.1", "2026.2.1b", "2026.2.x", "2026.2.1-beta",
                        "", "latest", "２０２６.2.1", "2026.2.1 ", "2026 .2.1", "2026.2.1/x", "2026.2.1%20"):
            with self.subTest(version=version):
                error, _ = fails_on(second=final_address(version=version, digits="202621"))
                self.assertIn("not the expected form", str(error))

    def test_the_digits_must_be_numbers(self):
        for digits in ("", "20262a", "2026.21", "٢٠٢٦", "-202621", " 202621"):
            with self.subTest(digits=digits):
                error, _ = fails_on(second=final_address(digits=digits))
                self.assertIn("Foxit's second download address", str(error))

    def test_a_language_that_is_not_the_asked_one_is_an_error_and_names_both(self):
        error, _ = fails_on(second=final_address(language="en-US"))
        self.assertIn("names the language 'en-US', not the asked 'L10N'", str(error))
        error, _ = fails_on(second=final_address(language="l10n"))
        self.assertIn("not the asked 'L10N'", str(error))

    def test_a_language_with_a_bad_form_in_the_address_is_an_error(self):
        for language in ("L10N/x", "L10N.x", "", "L10N x", "L 10N"):
            with self.subTest(language=language):
                error, _ = fails_on(second=final_address(language=language))
                self.assertIn("Foxit's second download address", str(error))

    def test_a_fetch_error_passes_through_and_sets_no_output(self):
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "read_location", side_effect=ProcessorError("down")):
            with self.assertRaises(ProcessorError):
                processor.main()
        self.assertNotIn("url", processor.env)
        self.assertNotIn("foxit_address_version", processor.env)

    def test_a_fetch_error_of_the_second_request_sets_no_output(self):
        calls = []

        def read(url, what):
            calls.append(url)
            if len(calls) == 2:
                raise ProcessorError("down")
            return SECOND
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "read_location", side_effect=read):
            with self.assertRaises(ProcessorError):
                processor.main()
        self.assertEqual(calls, [FIRST, SECOND])
        self.assertNotIn("url", processor.env)


class ParseFinalAddressTests(unittest.TestCase):
    def test_the_real_address(self):
        self.assertEqual(provider.parse_final_address(FINAL, "L10N"), ("2026.2.1", "202621", FINAL))

    def test_checked_location_names_what_it_checked(self):
        provider.checked_location(SECOND, "www.foxit.com", "the first answer")
        with self.assertRaises(ValueError) as caught:
            provider.checked_location(FINAL, "www.foxit.com", "the first answer")
        self.assertIn("the first answer leads to", str(caught.exception))

    def test_a_port_that_is_not_a_number_is_refused(self):
        with self.assertRaises(ValueError):
            provider.checked_location("https://www.foxit.com:abc/x", "www.foxit.com", "the first answer")


class ReadLocationTests(unittest.TestCase):
    URL = FIRST

    def read_with(self, body=None, error=None, status=200, url=None):
        self.requests = []

        def opener(request):
            self.requests.append(request)
            if error is not None:
                raise error
            response = FakeResponse(body if body is not None else b"")
            response.status = status
            self.response = response
            return response
        with mock.patch.object(provider, "open_request", side_effect=opener):
            return provider.read_location(url or self.URL, "the address")

    def test_the_location_of_a_redirect_is_returned_for_every_redirect_code(self):
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                self.assertEqual(self.read_with(error=redirect(code, SECOND)), SECOND)

    def test_a_relative_location_is_made_absolute(self):
        self.assertEqual(self.read_with(error=redirect(301, "/downloads/latest/?product=Foxit-Reader")),
                         "https://www.foxit.com/downloads/latest/?product=Foxit-Reader")
        self.assertEqual(self.read_with(error=redirect(301, "//example.test/x")), "https://example.test/x")

    def test_the_request_is_plain(self):
        self.read_with(error=redirect(301, SECOND))
        request = self.requests[0]
        self.assertEqual(request.full_url, self.URL)
        self.assertEqual(request.get_header("User-agent"), provider.USER_AGENT)
        self.assertIsNone(request.data)
        self.assertEqual(request.get_method(), "GET")
        self.assertFalse(request.has_header("Authorization"))
        self.assertFalse(request.has_header("Cookie"))

    def test_an_answer_that_is_not_a_redirect_is_an_error_that_names_it(self):
        for code, reason in ((200, "OK"), (404, "Not Found"), (403, "Forbidden"), (500, "Server Error"),
                             (304, "Not Modified"), (300, "Multiple Choices"), (305, "Use Proxy")):
            error = urllib.error.HTTPError(self.URL, code, reason, headers(SECOND), io.BytesIO(b""))
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.read_with(error=error)
                self.assertIn("answered %d" % code, str(caught.exception))
                self.assertIn("not a redirect", str(caught.exception))

    def test_a_200_answer_is_an_error_and_its_body_is_never_read(self):
        with self.assertRaises(ProcessorError) as caught:
            self.read_with(body=b"<html>a page</html>")
        self.assertIn("answered 200, not a redirect", str(caught.exception))
        self.assertFalse(self.response.was_read)
        self.assertTrue(self.response.closed)

    def test_the_answer_of_a_redirect_is_closed_and_its_body_is_not_read(self):
        error = redirect(301, SECOND)
        body = FakeResponse(b"x" * 100)
        error.fp = body
        self.read_with(error=error)
        self.assertFalse(body.was_read)

    def test_a_redirect_without_a_location_or_with_two_is_an_error(self):
        for locations, part in (((), "0 Location headers"), ((SECOND, SECOND), "2 Location headers"),
                                ((SECOND, FINAL), "2 Location headers")):
            with self.subTest(count=len(locations)):
                with self.assertRaises(ProcessorError) as caught:
                    self.read_with(error=redirect(301, *locations))
                self.assertIn(part, str(caught.exception))
                self.assertIn("not exactly one", str(caught.exception))

    def test_a_location_that_is_empty_too_long_or_has_a_space_or_a_control_character_is_an_error(self):
        too_long = "https://www.foxit.com/" + "a" * provider.MAX_LOCATION_CHARS
        for location, part in (("", "empty or longer"), (too_long, "empty or longer"),
                               ("https://www.foxit.com/a b", "a space or a control"),
                               (" https://www.foxit.com/a", "a space or a control"),
                               ("https://www.foxit.com/a\t", "a space or a control"),
                               ("https://www.foxit.com/a\x01", "a space or a control"),
                               ("https://www.foxit.com/a\x7f", "a space or a control")):
            with self.subTest(location=location[:30]):
                with self.assertRaises(ProcessorError) as caught:
                    self.read_with(error=redirect(301, location))
                self.assertIn(part, str(caught.exception))

    def test_a_location_of_exactly_the_limit_is_accepted(self):
        location = "https://www.foxit.com/" + "a" * (provider.MAX_LOCATION_CHARS - len("https://www.foxit.com/"))
        self.assertEqual(len(location), provider.MAX_LOCATION_CHARS)
        self.assertEqual(self.read_with(error=redirect(301, location)), location)

    def test_headers_as_a_plain_dict_are_read_too(self):
        error = urllib.error.HTTPError(self.URL, 301, "Moved", {"Location": SECOND}, io.BytesIO(b""))
        self.assertEqual(self.read_with(error=error), SECOND)
        error = urllib.error.HTTPError(self.URL, 301, "Moved", {}, io.BytesIO(b""))
        with self.assertRaises(ProcessorError):
            self.read_with(error=error)

    def test_location_values(self):
        self.assertEqual(provider.location_values(None), [])
        self.assertEqual(provider.location_values(headers()), [])
        self.assertEqual(provider.location_values(headers("a", "b")), ["a", "b"])
        self.assertEqual(provider.location_values({"Location": "a"}), ["a"])

    def test_a_failed_connection_is_a_processor_error(self):
        for error in (urllib.error.URLError("no route"), TimeoutError("timed out"), OSError("reset"),
                      ValueError("bad url"), http.client.HTTPException("bad line")):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(ProcessorError) as caught:
                    self.read_with(error=error)
                self.assertIn("could not be fetched", str(caught.exception))


class OpenerTests(unittest.TestCase):
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

    def test_a_stand_in_server_that_answers_302_gives_the_location_and_is_not_followed(self):
        """The whole urllib stack with the real NoRedirect handler, and a handler
        that stands in for the network: a 302 with a Location reaches the
        processor as an HTTPError, and the address in it is never opened."""
        opened = []
        real_build_opener = urllib.request.build_opener

        class StandIn(urllib.request.BaseHandler):
            handler_order = 100

            def http_open(self, request):
                return self.answer(request)

            def https_open(self, request):
                return self.answer(request)

            @staticmethod
            def answer(request):
                opened.append(request.full_url)
                message = email.message.Message()
                message["Location"] = "https://example.test/next"
                response = urllib.response.addinfourl(io.BytesIO(b""), message, request.full_url, 302)
                response.msg = "Found"
                return response

        def build(*handlers):
            return real_build_opener(*handlers, StandIn())

        with mock.patch.object(provider.urllib.request, "build_opener", side_effect=build):
            location = provider.read_location("https://www.foxit.com/downloads/latest.html?x=1", "the address")
        self.assertEqual(location, "https://example.test/next")
        self.assertEqual(opened, ["https://www.foxit.com/downloads/latest.html?x=1"])

    def test_the_limits_are_sensible(self):
        self.assertGreater(provider.FETCH_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(provider.FETCH_TIMEOUT_SECONDS, 600)
        self.assertLessEqual(provider.MAX_LOCATION_CHARS, 4096)
        self.assertEqual(provider.REDIRECT_CODES, (301, 302, 303, 307, 308))

    def test_the_constants_are_the_vendors_hosts_over_https(self):
        self.assertEqual(provider.START_HOST, "www.foxit.com")
        self.assertEqual(provider.FINAL_HOST, "cdn01.foxitsoftware.com")
        self.assertTrue(provider.START_URL_BASE.startswith("https://www.foxit.com/"))


class SourceTests(unittest.TestCase):
    def test_the_module_has_no_other_host_and_no_hash(self):
        with open(os.path.join(RECIPE_DIR, "FoxitInfoProvider.py"), "r", encoding="utf-8") as handle:
            text = handle.read()
        hosts = set(re.findall(r"https?://([A-Za-z0-9.-]+)", text))
        self.assertEqual(hosts, {provider.START_HOST, provider.FINAL_HOST})
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", text))

    def test_the_module_reads_no_body(self):
        with open(os.path.join(RECIPE_DIR, "FoxitInfoProvider.py"), "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn(".read(", text)

    def test_the_file_says_that_it_is_written_by_hand(self):
        with open(__file__, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertTrue(text.startswith('"""Tests of FoxitInfoProvider'))
        self.assertIn("THE ANSWERS ARE WRITTEN BY HAND", text.split('"""')[1])


if __name__ == "__main__":
    unittest.main()
