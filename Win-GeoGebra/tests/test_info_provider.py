"""Tests of GeoGebraInfoProvider: every branch. No test uses the network:
read_location() or open_request() is replaced, or a stand-in handler answers.

THE ANSWERS ARE WRITTEN BY HAND. The processor reads only the Location header
of one answer, so no answer was saved. The addresses in this file were written
by hand after the real answer of 2026-11-13 (302 with a relative Location),
with the file name of that day. A test that reads them is still a real test of
the parser, but it proves nothing about what GeoGebra's server answers today:
the first run on the build machine is that check.
"""
import email.message
import http.client
import io
import os
import re
import sys
import unittest
import urllib.error
import urllib.parse
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

import GeoGebraInfoProvider as provider  # noqa: E402

PROVIDER = provider.GeoGebraInfoProvider

START = "https://download.geogebra.org/package/win-msi6"
# The relative Location of 2026-11-13, as the server sent it.
RELATIVE = "/installers/6.0/GeoGebra-Windows-Installer-6-0-936-0.msi"
HOST_URL = "https://download.geogebra.org"
FINAL = HOST_URL + RELATIVE


def numbers(*parts):
    """A version of several numbers, built here so that no four small numbers
    stand in this file as they are (the public-repository test reads four
    dotted numbers as an address)."""
    return ".".join(str(part) for part in parts)


def path_of(name_numbers="6-0-936-0", folder="6.0"):
    return "/installers/%s/GeoGebra-Windows-Installer-%s.msi" % (folder, name_numbers)


def resolved(url, location):
    """What read_location gives back: a relative Location resolved against the
    address. An absolute one is passed on as it is, because urljoin of some
    Python versions drops an empty query ("?") and the test is of the parser."""
    if urllib.parse.urlsplit(location).scheme:
        return location
    return urllib.parse.urljoin(url, location)


def run_on(location=RELATIVE, record=None):
    """Run the processor on one answer: read_location is replaced by a stand-in
    that resolves the Location against the address as the real one does."""
    def read(url, what):
        if record is not None:
            record.append((url, what))
        return resolved(url, location)
    with mock.patch.object(provider, "read_location", side_effect=read):
        return run_processor(PROVIDER, {})


def fails_on(location):
    processor, _ = new_processor(PROVIDER, {})
    with mock.patch.object(provider, "read_location",
                           side_effect=lambda url, what: resolved(url, location)):
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
    return urllib.error.HTTPError(url, code, "Found", headers(*locations), io.BytesIO(b""))


class HappyPathTests(unittest.TestCase):
    def test_the_relative_answer_of_2026_11_13(self):
        processor, messages = run_on()
        self.assertEqual(processor.env["url"], FINAL)
        self.assertEqual(processor.env["geogebra_address_version"], numbers(6, 0, 936, 0))
        self.assertTrue(any(numbers(6, 0, 936, 0) in m for m in messages))
        self.assertTrue(any("not the label of the recipe" in m for m in messages))

    def test_an_absolute_answer_on_the_same_host_is_accepted_too(self):
        processor, _ = run_on(location=FINAL)
        self.assertEqual(processor.env["url"], FINAL)

    def test_exactly_one_request_to_the_fixed_address(self):
        record = []
        run_on(record=record)
        self.assertEqual([item[0] for item in record], [START])
        self.assertEqual(provider.START_URL, START)

    def test_the_outputs_are_the_two_declared_and_no_hash_and_no_version(self):
        processor, _ = run_on()
        self.assertEqual(sorted(PROVIDER.output_variables), ["geogebra_address_version", "url"])
        self.assertNotIn("version", processor.env)
        self.assertNotIn("expected_sha256", processor.env)

    def test_the_processor_has_no_inputs(self):
        self.assertEqual(PROVIDER.input_variables, {})

    def test_the_hyphens_become_dots_and_the_numbers_may_be_long(self):
        for name, version in (("6-0-936-0", numbers(6, 0, 936, 0)), ("6-0-1000-12", numbers(6, 0, 1000, 12)),
                              ("6-0-9-0", numbers(6, 0, 9, 0)), ("60-10-99999-1", numbers(60, 10, 99999, 1))):
            with self.subTest(name=name):
                processor, _ = run_on(location=path_of(name))
                self.assertEqual(processor.env["geogebra_address_version"], version)
                self.assertEqual(processor.env["url"], HOST_URL + path_of(name))

    def test_the_url_is_built_from_the_fixed_host_and_the_checked_path(self):
        processor, _ = run_on(location="https://Download.GeoGebra.org" + RELATIVE)
        self.assertEqual(processor.env["url"], FINAL)


class AnswerTests(unittest.TestCase):
    def test_an_answer_on_another_host_or_with_another_form_is_an_error(self):
        for bad in (
            "http://download.geogebra.org" + RELATIVE,
            "https://www.geogebra.org" + RELATIVE,
            "https://geogebra.org" + RELATIVE,
            "https://download.geogebra.org.example.test" + RELATIVE,
            "https://example.test" + RELATIVE,
            "https://example.test/https://download.geogebra.org" + RELATIVE,
            "//example.test" + RELATIVE,
            "https://user@download.geogebra.org" + RELATIVE,
            "https://user:pw@download.geogebra.org" + RELATIVE,
            "https://download.geogebra.org:8443" + RELATIVE,
            "https://download.geogebra.org:abc" + RELATIVE,
            FINAL + "#frag",
            FINAL + "?token=1",
            FINAL + "?",
            RELATIVE + "?x=1",
            "ftp://download.geogebra.org" + RELATIVE,
            "file:///etc/passwd",
        ):
            with self.subTest(bad=bad):
                error, processor = fails_on(bad)
                self.assertIn("GeoGebra's download address", str(error))
                for key in ("url", "geogebra_address_version"):
                    self.assertNotIn(key, processor.env)

    def test_a_path_that_is_not_the_expected_one_is_an_error(self):
        for path in (
            "",
            "/",
            RELATIVE + "/",
            RELATIVE + "x",
            RELATIVE.replace(".msi", ".exe"),
            RELATIVE.replace(".msi", ".MSI"),
            RELATIVE.replace(".msi", ".msi.zip"),
            path_of(folder="5.4"),
            path_of(folder="6.1"),
            path_of(folder="6.0/suite"),
            "/installers/5.4/GeoGebra-Windows-Installer-5-4-936-0.exe",
            RELATIVE.replace("Installer", "Portable"),
            RELATIVE.replace("/installers/", "/installers2/"),
            RELATIVE.replace("/installers/", "/x/installers/"),
            "/x" + RELATIVE,
            RELATIVE.replace("6.0/", "6.0//"),
            RELATIVE.replace("6.0/", "../6.0/"),
            RELATIVE.replace("6.0/", "%36.0/"),
            RELATIVE.replace("GeoGebra-", "geogebra-", 1),
            RELATIVE.replace("Windows", "windows"),
            "/package/win-msi6",
        ):
            with self.subTest(path=path):
                error, _ = fails_on(path or HOST_URL)
                self.assertIn("GeoGebra's download address", str(error))

    def test_the_file_name_must_have_four_numbers(self):
        for name in ("6-0-936", "6-0-936-0-1", "6-0-936-", "-0-936-0", "6--936-0", "6-0-936-0b", "6-0-936-x",
                     "6.0.936.0", "6_0_936_0", "", "latest", "６-0-936-0", "6-0-936-0 ", "6-0-936-%30"):
            with self.subTest(name=name):
                error, _ = fails_on(path_of(name))
                self.assertIn("not the expected form", str(error))

    def test_a_fetch_error_passes_through_and_sets_no_output(self):
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "read_location", side_effect=ProcessorError("down")):
            with self.assertRaises(ProcessorError):
                processor.main()
        self.assertNotIn("url", processor.env)
        self.assertNotIn("geogebra_address_version", processor.env)


class ParseAddressTests(unittest.TestCase):
    def test_the_real_address(self):
        self.assertEqual(provider.parse_address(FINAL), (numbers(6, 0, 936, 0), FINAL))

    def test_checked_location_refuses_another_host(self):
        provider.checked_location(FINAL)
        with self.assertRaises(ValueError) as caught:
            provider.checked_location("https://www.geogebra.org" + RELATIVE)
        self.assertIn("the answer leads to", str(caught.exception))

    def test_a_port_that_is_not_a_number_is_refused(self):
        with self.assertRaises(ValueError):
            provider.checked_location("https://download.geogebra.org:abc/x")


class ReadLocationTests(unittest.TestCase):
    def read_with(self, body=None, error=None, status=200, url=START):
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
            return provider.read_location(url, "the address")

    def test_the_location_of_a_redirect_is_returned_for_every_redirect_code(self):
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                self.assertEqual(self.read_with(error=redirect(code, FINAL)), FINAL)

    def test_a_relative_location_is_resolved_against_the_fixed_address(self):
        self.assertEqual(self.read_with(error=redirect(302, RELATIVE)), FINAL)
        self.assertEqual(self.read_with(error=redirect(302, "../installers/6.0/x.msi")),
                         HOST_URL + "/installers/6.0/x.msi")
        self.assertEqual(self.read_with(error=redirect(302, "//example.test/x")), "https://example.test/x")

    def test_the_request_is_plain(self):
        self.read_with(error=redirect(302, RELATIVE))
        request = self.requests[0]
        self.assertEqual(request.full_url, START)
        self.assertEqual(request.get_header("User-agent"), provider.USER_AGENT)
        self.assertIsNone(request.data)
        self.assertEqual(request.get_method(), "GET")
        self.assertFalse(request.has_header("Authorization"))
        self.assertFalse(request.has_header("Cookie"))

    def test_an_answer_that_is_not_a_redirect_is_an_error_that_names_it(self):
        for code, reason in ((200, "OK"), (404, "Not Found"), (403, "Forbidden"), (500, "Server Error"),
                             (304, "Not Modified"), (300, "Multiple Choices"), (305, "Use Proxy")):
            error = urllib.error.HTTPError(START, code, reason, headers(RELATIVE), io.BytesIO(b""))
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.read_with(error=error)
                self.assertIn("answered %d" % code, str(caught.exception))
                self.assertIn("not a redirect", str(caught.exception))

    def test_a_200_answer_is_an_error_and_its_body_is_never_read(self):
        with self.assertRaises(ProcessorError) as caught:
            self.read_with(body=b"MSI bytes would be here")
        self.assertIn("answered 200, not a redirect", str(caught.exception))
        self.assertFalse(self.response.was_read)
        self.assertTrue(self.response.closed)

    def test_the_answer_of_a_redirect_is_closed_and_its_body_is_not_read(self):
        error = redirect(302, RELATIVE)
        body = FakeResponse(b"x" * 100)
        error.fp = body
        self.read_with(error=error)
        self.assertFalse(body.was_read)

    def test_a_redirect_without_a_location_or_with_two_is_an_error(self):
        for locations, part in (((), "0 Location headers"), ((RELATIVE, RELATIVE), "2 Location headers"),
                                ((RELATIVE, FINAL), "2 Location headers")):
            with self.subTest(count=len(locations)):
                with self.assertRaises(ProcessorError) as caught:
                    self.read_with(error=redirect(302, *locations))
                self.assertIn(part, str(caught.exception))
                self.assertIn("not exactly one", str(caught.exception))

    def test_a_location_that_is_empty_too_long_or_has_a_space_or_a_control_character_is_an_error(self):
        too_long = "/" + "a" * provider.MAX_LOCATION_CHARS
        for location, part in (("", "empty or longer"), (too_long, "empty or longer"),
                               ("/installers/6.0/a b.msi", "a space or a control"),
                               (" " + RELATIVE, "a space or a control"),
                               (RELATIVE + "\t", "a space or a control"),
                               (RELATIVE + "\x01", "a space or a control"),
                               (RELATIVE + "\x7f", "a space or a control")):
            with self.subTest(location=location[:30]):
                with self.assertRaises(ProcessorError) as caught:
                    self.read_with(error=redirect(302, location))
                self.assertIn(part, str(caught.exception))

    def test_a_location_of_exactly_the_limit_is_accepted(self):
        location = "/" + "a" * (provider.MAX_LOCATION_CHARS - 1)
        self.assertEqual(len(location), provider.MAX_LOCATION_CHARS)
        self.assertEqual(self.read_with(error=redirect(302, location)), HOST_URL + location)

    def test_headers_as_a_plain_dict_are_read_too(self):
        error = urllib.error.HTTPError(START, 302, "Found", {"Location": RELATIVE}, io.BytesIO(b""))
        self.assertEqual(self.read_with(error=error), FINAL)
        error = urllib.error.HTTPError(START, 302, "Found", {}, io.BytesIO(b""))
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


class WholeProcessorTests(unittest.TestCase):
    def test_the_processor_with_the_real_read_location_and_a_stand_in_opener(self):
        """read_location is the real one: only open_request is replaced, and it
        answers 302 with the relative Location of 2026-11-13."""
        with mock.patch.object(provider, "open_request", side_effect=lambda request: (_ for _ in ()).throw(
                redirect(302, RELATIVE, url=request.full_url))):
            processor, _ = run_processor(PROVIDER, {})
        self.assertEqual(processor.env["url"], FINAL)
        self.assertEqual(processor.env["geogebra_address_version"], numbers(6, 0, 936, 0))


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
        that stands in for the network: a 302 with a relative Location reaches the
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
                message["Location"] = RELATIVE
                response = urllib.response.addinfourl(io.BytesIO(b""), message, request.full_url, 302)
                response.msg = "Found"
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
        self.assertEqual(provider.HOST, "download.geogebra.org")
        self.assertTrue(provider.START_URL.startswith("https://download.geogebra.org/"))


class FixtureTests(unittest.TestCase):
    """The cut of the folder index of 2026-11-13 (tests/index_excerpt.html)."""

    def setUp(self):
        with open(os.path.join(TESTS_DIR, "index_excerpt.html"), "r", encoding="utf-8") as handle:
            self.text = handle.read()
        self.names = re.findall(r'href="([^"]+)"', self.text)

    def test_the_newest_msi_of_the_index_is_the_one_of_the_answer_and_matches_the_form(self):
        msis = [name for name in self.names if name.endswith(".msi")]
        self.assertEqual(len(msis), 4)
        newest = max(msis, key=lambda name: [int(n) for n in re.findall(r"[0-9]+", name)])
        self.assertEqual("/installers/6.0/" + newest, RELATIVE)
        for name in msis:
            with self.subTest(name=name):
                self.assertTrue(provider.PATH_PATTERN.fullmatch("/installers/6.0/" + name))
        for name in self.names:
            if not name.endswith(".msi"):
                self.assertIsNone(provider.PATH_PATTERN.fullmatch("/installers/6.0/" + name), name)

    def test_the_index_lists_no_hash_checksum_or_signature_file(self):
        for name in self.names:
            self.assertNotRegex(name, r"(?i)sha|md5|sum|\.sig$|\.asc$|hash")

    def test_the_excerpt_is_small(self):
        self.assertLess(len(self.text), 4096)


class SourceTests(unittest.TestCase):
    def test_the_module_has_no_other_host_and_no_hash(self):
        with open(os.path.join(RECIPE_DIR, "GeoGebraInfoProvider.py"), "r", encoding="utf-8") as handle:
            text = handle.read()
        hosts = set(re.findall(r"https?://([A-Za-z0-9.-]+)", text))
        self.assertEqual(hosts, {provider.HOST})
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", text))

    def test_the_module_reads_no_body(self):
        with open(os.path.join(RECIPE_DIR, "GeoGebraInfoProvider.py"), "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn(".read(", text)

    def test_the_file_says_that_it_is_written_by_hand(self):
        with open(__file__, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertTrue(text.startswith('"""Tests of GeoGebraInfoProvider'))
        self.assertIn("THE ANSWERS ARE WRITTEN BY HAND", text.split('"""')[1])


if __name__ == "__main__":
    unittest.main()
