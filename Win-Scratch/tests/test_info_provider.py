"""Tests of ScratchInfoProvider: every branch. No test uses the network:
read_location() or open_request() is replaced, or a stand-in handler answers.

THE ANSWERS ARE WRITTEN BY HAND. The processor reads only the Location header
of one answer, so no page was saved. The addresses in this file were written
by hand after the real answer of 2026-11-13 (301), with the version and the
file name of that day. A test that reads them is still a real test of the
parser, but it proves nothing about what the server answers today: the first
run on the build Mac is that check.
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

import ScratchInfoProvider as provider  # noqa: E402

PROVIDER = provider.ScratchInfoProvider

# The two addresses of 2026-11-13, in the form of the real answer.
START = "https://downloads.scratch.mit.edu/desktop/Scratch%20Setup.exe"
FINAL_PATH = "/desktop/Scratch%203.32.1%20Setup.exe"
FINAL = "https://downloads.scratch.mit.edu" + FINAL_PATH
HOST = "https://downloads.scratch.mit.edu"


def numbers(*parts):
    """A version of several numbers, built here so that no four numbers stand in
    this file as they are."""
    return ".".join(str(part) for part in parts)


def final_address(version="3.32.1", host="downloads.scratch.mit.edu"):
    return "https://%s/desktop/Scratch%%20%s%%20Setup.exe" % (host, version)


def run_on(location=FINAL, record=None):
    def read(url, what):
        if record is not None:
            record.append((url, what))
        return location
    with mock.patch.object(provider, "read_location", side_effect=read):
        return run_processor(PROVIDER, {})


def fails_on(location):
    """Run the processor on one answer, expect a ProcessorError, return it and the processor."""
    processor, _ = new_processor(PROVIDER, {})
    with mock.patch.object(provider, "read_location", return_value=location):
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


def redirect(code, *locations, url=START):
    return urllib.error.HTTPError(url, code, "Moved", headers(*locations), io.BytesIO(b""))


class HappyPathTests(unittest.TestCase):
    def test_the_answer_of_the_real_address(self):
        processor, messages = run_on()
        self.assertEqual(processor.env["url"], FINAL)
        self.assertEqual(processor.env["version"], "3.32.1")
        self.assertTrue(any("3.32.1" in m for m in messages))
        self.assertTrue(any("were not compared with it" in m for m in messages))

    def test_exactly_one_request_to_the_fixed_address(self):
        record = []
        run_on(record=record)
        self.assertEqual([item[0] for item in record], [START])
        self.assertEqual(provider.START_URL, START)

    def test_the_outputs_are_the_two_declared_and_no_hash(self):
        processor, _ = run_on()
        self.assertEqual(sorted(PROVIDER.output_variables), ["url", "version"])
        self.assertNotIn("expected_sha256", processor.env)
        self.assertEqual(PROVIDER.input_variables, {})

    def test_the_version_may_have_two_to_four_parts(self):
        for version in ("3.32", "3.32.1", numbers(3, 32, 1, 7), "10.0", "03.32.1"):
            with self.subTest(version=version):
                processor, _ = run_on(final_address(version))
                self.assertEqual(processor.env["version"], version)

    def test_the_url_is_built_from_the_fixed_host_and_the_checked_path(self):
        processor, _ = run_on(final_address(host="Downloads.Scratch.MIT.edu"))
        self.assertEqual(processor.env["url"], FINAL)


class AnswerTests(unittest.TestCase):
    def test_an_answer_on_another_host_or_scheme_is_an_error(self):
        for bad in (
            "http://downloads.scratch.mit.edu" + FINAL_PATH,
            "https://scratch.mit.edu" + FINAL_PATH,
            "https://download.scratch.mit.edu" + FINAL_PATH,
            "https://downloads.scratch.mit.edu.example.test" + FINAL_PATH,
            "https://example.test" + FINAL_PATH,
            "https://example.test/https://downloads.scratch.mit.edu" + FINAL_PATH,
            "https://user@downloads.scratch.mit.edu" + FINAL_PATH,
            "https://user:pw@downloads.scratch.mit.edu" + FINAL_PATH,
            "https://downloads.scratch.mit.edu:8443" + FINAL_PATH,
            "https://downloads.scratch.mit.edu:abc" + FINAL_PATH,
            FINAL + "#frag",
            FINAL + "?token=1",
            FINAL + "?",
            "ftp://downloads.scratch.mit.edu" + FINAL_PATH,
            "file:///etc/passwd",
            "//example.test/x",
        ):
            with self.subTest(bad=bad):
                error, processor = fails_on(bad)
                self.assertIn("Scratch's download address", str(error))
                for key in ("url", "version"):
                    self.assertNotIn(key, processor.env)

    def test_a_path_that_is_not_the_expected_one_is_an_error(self):
        for path in (
            "",
            "/",
            "/desktop/Scratch%20Setup.exe",                      # the fixed address itself: a loop
            FINAL_PATH + "/",
            FINAL_PATH + "x",
            FINAL_PATH.replace(".exe", ".msi"),
            FINAL_PATH.replace(".exe", ".EXE"),
            FINAL_PATH.replace(".exe", ".dmg"),
            FINAL_PATH.replace("Setup", "setup"),
            FINAL_PATH.replace("Scratch%20", "scratch%20"),
            FINAL_PATH.replace("Scratch%20", "Scratch "),
            FINAL_PATH.replace("Scratch%20", "Scratch+"),
            FINAL_PATH.replace("%20Setup", "-Setup"),
            FINAL_PATH.replace("%20Setup", "%2520Setup"),
            FINAL_PATH.replace("/desktop/", "/link/"),
            FINAL_PATH.replace("/desktop/", "/desktop/x/"),
            FINAL_PATH.replace("/desktop/", "/desktop//"),
            "/x" + FINAL_PATH,
            "/desktop/../desktop/Scratch%203.32.1%20Setup.exe",
            "/desktop/Scratch.dmg",
        ):
            with self.subTest(path=path):
                error, _ = fails_on(HOST + path)
                self.assertIn("Scratch's download address", str(error))

    def test_a_version_that_is_not_two_to_four_numbers_is_an_error(self):
        for version in ("3", "3.", ".3.32", "3..32", "v3.32.1", "3.32.1b", "3.32.x", "3.32.1-beta",
                        "", "latest", "３.32.1", "3.32.1%20", "%203.32.1", numbers(3, 32, 1, 7, 0),
                        "1234567890.1", "0.0", numbers(0, 0, 0)):
            with self.subTest(version=version):
                error, processor = fails_on(final_address(version=version))
                self.assertIn("Scratch's download address", str(error))
                self.assertNotIn("version", processor.env)

    def test_a_version_of_zeros_names_why(self):
        error, _ = fails_on(final_address(version="0.0"))
        self.assertIn("no digit other than zero", str(error))

    def test_a_fetch_error_passes_through_and_sets_no_output(self):
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "read_location", side_effect=ProcessorError("down")):
            with self.assertRaises(ProcessorError):
                processor.main()
        self.assertNotIn("url", processor.env)
        self.assertNotIn("version", processor.env)


class ParseAddressTests(unittest.TestCase):
    def test_the_real_address(self):
        self.assertEqual(provider.parse_address(FINAL), ("3.32.1", FINAL))

    def test_a_port_that_is_not_a_number_is_refused(self):
        with self.assertRaises(ValueError):
            provider.parse_address("https://downloads.scratch.mit.edu:abc" + FINAL_PATH)

    def test_the_message_names_the_path_it_refused(self):
        with self.assertRaises(ValueError) as caught:
            provider.parse_address(HOST + "/desktop/Other.exe")
        self.assertIn("'/desktop/Other.exe'", str(caught.exception))


class ReadLocationTests(unittest.TestCase):
    URL = START

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
                self.assertEqual(self.read_with(error=redirect(code, FINAL)), FINAL)

    def test_a_relative_location_is_made_absolute(self):
        self.assertEqual(self.read_with(error=redirect(301, FINAL_PATH)), FINAL)
        self.assertEqual(self.read_with(error=redirect(301, "//example.test/x")), "https://example.test/x")

    def test_the_request_is_plain(self):
        self.read_with(error=redirect(301, FINAL))
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
            error = urllib.error.HTTPError(self.URL, code, reason, headers(FINAL), io.BytesIO(b""))
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.read_with(error=error)
                self.assertIn("answered %d" % code, str(caught.exception))
                self.assertIn("not a redirect", str(caught.exception))

    def test_a_200_answer_is_an_error_and_its_body_is_never_read(self):
        with self.assertRaises(ProcessorError) as caught:
            self.read_with(body=b"MZ an installer")
        self.assertIn("answered 200, not a redirect", str(caught.exception))
        self.assertFalse(self.response.was_read)
        self.assertTrue(self.response.closed)

    def test_the_answer_of_a_redirect_is_closed_and_its_body_is_not_read(self):
        error = redirect(301, FINAL)
        body = FakeResponse(b"x" * 100)
        error.fp = body
        self.read_with(error=error)
        self.assertFalse(body.was_read)

    def test_a_redirect_without_a_location_or_with_two_is_an_error(self):
        for locations, part in (((), "0 Location headers"), ((FINAL, FINAL), "2 Location headers"),
                                ((FINAL, final_address("3.33.0")), "2 Location headers")):
            with self.subTest(count=len(locations)):
                with self.assertRaises(ProcessorError) as caught:
                    self.read_with(error=redirect(301, *locations))
                self.assertIn(part, str(caught.exception))
                self.assertIn("not exactly one", str(caught.exception))

    def test_a_location_that_is_empty_too_long_or_has_a_space_or_a_control_character_is_an_error(self):
        too_long = HOST + "/" + "a" * provider.MAX_LOCATION_CHARS
        for location, part in (("", "empty or longer"), (too_long, "empty or longer"),
                               (HOST + "/desktop/Scratch 3.32.1 Setup.exe", "a space or a control"),
                               (" " + FINAL, "a space or a control"),
                               (FINAL + "\t", "a space or a control"),
                               (FINAL + "\x01", "a space or a control"),
                               (FINAL + "\x7f", "a space or a control")):
            with self.subTest(location=location[:30]):
                with self.assertRaises(ProcessorError) as caught:
                    self.read_with(error=redirect(301, location))
                self.assertIn(part, str(caught.exception))

    def test_a_location_of_exactly_the_limit_is_accepted(self):
        location = HOST + "/" + "a" * (provider.MAX_LOCATION_CHARS - len(HOST + "/"))
        self.assertEqual(len(location), provider.MAX_LOCATION_CHARS)
        self.assertEqual(self.read_with(error=redirect(301, location)), location)

    def test_headers_as_a_plain_dict_are_read_too(self):
        error = urllib.error.HTTPError(self.URL, 301, "Moved", {"Location": FINAL}, io.BytesIO(b""))
        self.assertEqual(self.read_with(error=error), FINAL)
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
        self.assertIsNone(handler.redirect_request(None, None, 301, "Moved", {}, "https://example.test/"))

    def test_the_real_opener_is_built_with_the_redirect_refusing_handler_and_a_time_limit(self):
        with mock.patch.object(provider.urllib.request, "build_opener") as build:
            provider.open_request(object())
        handlers = build.call_args[0]
        self.assertEqual(len(handlers), 1)
        self.assertIs(handlers[0], provider.NoRedirect)
        build.return_value.open.assert_called_once()
        self.assertEqual(build.return_value.open.call_args[1]["timeout"], provider.FETCH_TIMEOUT_SECONDS)

    def test_a_stand_in_server_that_answers_301_gives_the_location_and_is_not_followed(self):
        """The whole urllib stack with the real NoRedirect handler, and a handler
        that stands in for the network: a 301 with a Location reaches the
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
                message["Location"] = FINAL
                response = urllib.response.addinfourl(io.BytesIO(b""), message, request.full_url, 301)
                response.msg = "Moved Permanently"
                return response

        def build(*handlers):
            return real_build_opener(*handlers, StandIn())

        with mock.patch.object(provider.urllib.request, "build_opener", side_effect=build):
            location = provider.read_location(START, "the address")
        self.assertEqual(location, FINAL)
        self.assertEqual(opened, [START])

    def test_the_limits_are_sensible(self):
        self.assertGreater(provider.FETCH_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(provider.FETCH_TIMEOUT_SECONDS, 600)
        self.assertLessEqual(provider.MAX_LOCATION_CHARS, 4096)
        self.assertEqual(provider.REDIRECT_CODES, (301, 302, 303, 307, 308))

    def test_the_constants_are_the_vendors_host_over_https(self):
        self.assertEqual(provider.HOST, "downloads.scratch.mit.edu")
        self.assertTrue(provider.START_URL.startswith("https://downloads.scratch.mit.edu/"))


class SourceTests(unittest.TestCase):
    def test_the_module_has_no_other_host_and_no_hash(self):
        with open(os.path.join(RECIPE_DIR, "ScratchInfoProvider.py"), "r", encoding="utf-8") as handle:
            text = handle.read()
        hosts = set(re.findall(r"https?://([A-Za-z0-9.-]+)", text))
        self.assertEqual(hosts, {provider.HOST})
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", text))

    def test_the_module_reads_no_body(self):
        with open(os.path.join(RECIPE_DIR, "ScratchInfoProvider.py"), "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn(".read(", text)

    def test_the_file_says_that_it_is_written_by_hand(self):
        with open(__file__, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertTrue(text.startswith('"""Tests of ScratchInfoProvider'))
        self.assertIn("THE ANSWERS ARE WRITTEN BY HAND", text.split('"""')[1])


if __name__ == "__main__":
    unittest.main()
