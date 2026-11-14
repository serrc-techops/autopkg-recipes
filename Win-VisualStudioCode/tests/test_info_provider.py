"""Tests of VisualStudioCodeInfoProvider: every branch. No test uses the network:
fetch_text() or open_request() is replaced.

THE EXCERPT IS CUT FROM A REAL ANSWER. vscode_sha_excerpt.json holds 5 of the 25
elements of the answer of Microsoft's release file read on 2026-11-13, unchanged
and in their order, and one key "_note" that says so. A test that reads it is a
real test of the parser on an answer of that day, but it proves nothing about
what Microsoft's site answers on a later day: the first run on the build Mac is
that check. The other texts of this file are made up.
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

import VisualStudioCodeInfoProvider as provider  # noqa: E402

PROVIDER = provider.VisualStudioCodeInfoProvider
EXCERPT = os.path.join(TESTS_DIR, "vscode_sha_excerpt.json")
CUT_NOTE = "Cut from the answer of code.visualstudio.com/sha?build=stable read on 2026-11-13"
HEX_A = "a" * 64
HEX_B = "b" * 64
COMMIT = "0123456789abcdef0123456789abcdef01234567"
# A text that the hygiene test would read as an address if it stood here as it is. It is built.
FOUR_NUMBERS = ".".join(["2", "0", "0", "1"])
FIVE_NUMBERS = ".".join(["1", "146", "0", "1", "2"])
DOWNLOAD_BASE = "https://vscode.download.prss.microsoft.com/dbazure/download/stable/"


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def product(os_name="win32-x64", version="1.146.0", commit=COMMIT, sha=HEX_A, build="stable", url=None,
            prettyname="Windows System Installer (x64)"):
    """One element of `products`, made up, of the form that was read on 2026-11-13."""
    if url is None:
        kind = {"win32-x64": "VSCodeSetup-x64", "win32-arm64": "VSCodeSetup-arm64",
                "win32-x64-user": "VSCodeUserSetup-x64"}.get(os_name, "other-" + os_name)
        url = "%s%s/%s-%s.exe" % (DOWNLOAD_BASE, commit, kind, version)
    return {"url": url, "name": version, "version": commit, "productVersion": version, "hash": "c" * 40,
            "timestamp": 1, "sha256hash": sha, "supportsFastUpdate": True, "notes": commit, "build": build,
            "platform": {"os": os_name, "prettyname": prettyname}}


def answer(*products):
    return json.dumps({"products": list(products)})


def fetcher(text, record=None):
    """A stand-in for fetch_text that answers the one address and writes down what was asked."""
    def fetch(url, max_bytes, what):
        if record is not None:
            record.append((url, max_bytes, what))
        if url == provider.SHA_URL:
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
    """The excerpt cut from the answer of 2026-11-13 (see the note at the top of this file)."""

    def setUp(self):
        self.text = read(EXCERPT)
        self.data = json.loads(self.text)

    def test_the_excerpt_says_where_it_is_from(self):
        self.assertTrue(self.data["_note"].startswith(CUT_NOTE))
        self.assertIn("CUT FROM A REAL ANSWER", read(__file__))

    def test_the_excerpt_is_small_and_has_the_kinds_the_tests_need(self):
        self.assertLess(len(self.text), 4000)
        kinds = [element["platform"]["os"] for element in self.data["products"]]
        self.assertEqual(sorted(kinds), sorted(["win32-x64-user", "win32-x64", "win32-x64-archive", "win32-arm64",
                                                "darwin-universal-dmg"]))
        self.assertEqual(kinds.count("win32-x64"), 1)

    def test_the_system_installer_for_x64(self):
        processor, _ = run_on(self.text)
        element = [e for e in self.data["products"] if e["platform"]["os"] == "win32-x64"][0]
        self.assertEqual(processor.env["version"], "1.146.0")
        self.assertEqual(processor.env["url"], element["url"])
        self.assertTrue(processor.env["url"].startswith(DOWNLOAD_BASE + element["version"] + "/"))
        self.assertTrue(processor.env["url"].endswith("/VSCodeSetup-x64-1.146.0.exe"))
        self.assertEqual(processor.env["expected_sha256"], element["sha256hash"].lower())
        self.assertRegex(processor.env["expected_sha256"], r"^[0-9a-f]{64}$")

    def test_the_system_installer_for_arm64_is_another_element(self):
        x64, _ = run_on(self.text)
        arm, _ = run_on(self.text, {"vscode_platform": "win32-arm64"})
        self.assertTrue(arm.env["url"].endswith("/VSCodeSetup-arm64-1.146.0.exe"))
        self.assertNotEqual(arm.env["expected_sha256"], x64.env["expected_sha256"])

    def test_the_hash_is_never_the_hash_of_the_user_installer_or_the_zip(self):
        processor, _ = run_on(self.text)
        others = {e["sha256hash"].lower() for e in self.data["products"] if e["platform"]["os"] != "win32-x64"}
        self.assertNotIn(processor.env["expected_sha256"], others)

    def test_the_one_request_is_the_fixed_address_with_its_limit(self):
        record = []
        run_on(self.text, record=record)
        self.assertEqual(record, [("https://code.visualstudio.com/sha?build=stable", provider.MAX_SHA_BYTES,
                                   "Microsoft's release file")])


class SelectProductTests(unittest.TestCase):
    def test_the_one_element_of_the_platform_is_taken_and_its_hash_is_lower_case(self):
        text = answer(product("win32-x64-user", sha=HEX_B), product(sha=HEX_A.upper()), product("linux-x64", sha=HEX_B))
        url, version, sha = provider.select_product(text, "win32-x64")
        self.assertEqual(sha, HEX_A)
        self.assertEqual(version, "1.146.0")
        self.assertEqual(url, DOWNLOAD_BASE + COMMIT + "/VSCodeSetup-x64-1.146.0.exe")

    def test_no_element_of_the_platform_is_an_error_that_names_it(self):
        for text in (answer(), answer(product("win32-x64-user")), answer(product("win32-x64-archive"))):
            with self.subTest(text=text[:60]):
                with self.assertRaises(ValueError) as caught:
                    provider.select_product(text, "win32-x64")
                self.assertIn("no element with the os win32-x64", str(caught.exception))

    def test_two_elements_of_the_platform_are_an_error_also_when_they_agree(self):
        for second in (product(), product(sha=HEX_B)):
            with self.subTest(sha=second["sha256hash"][:2]):
                with self.assertRaises(ValueError) as caught:
                    provider.select_product(answer(product(), product("linux-x64"), second), "win32-x64")
                self.assertIn("2 elements with the os win32-x64, not exactly one", str(caught.exception))

    def test_the_os_must_match_exactly(self):
        for other in ("win32-x64 ", "Win32-x64", "win32-x64-user", "win32-x86", "win32", "x64", "win32_x64"):
            with self.subTest(other=other):
                with self.assertRaises(ValueError) as caught:
                    provider.select_product(answer(product(other)), "win32-x64")
                self.assertIn("no element with the os", str(caught.exception))

    def test_every_element_is_checked_for_its_os_not_only_ours(self):
        bad = ["text", 5, None, [], {}, {"platform": "win32-x64"}, {"platform": {}}, {"platform": {"os": 5}},
               {"platform": {"os": None}}, {"platform": ["win32-x64"]}]
        for element in bad:
            for order in ((product(), element), (element, product())):
                with self.subTest(element=repr(element)[:40]):
                    with self.assertRaises(ValueError) as caught:
                        provider.select_product(json.dumps({"products": list(order)}), "win32-x64")
                    self.assertRegex(str(caught.exception), r"element [12] of products (is not an object|has no platform)")

    def test_an_answer_that_is_not_what_is_expected(self):
        for text, part in (("", "not JSON"), ("{", "not JSON"), ("<html>", "not JSON"), ("[]", "not a JSON object"),
                           ("null", "not a JSON object"), ('"x"', "not a JSON object"), ("{}", "products is not a list"),
                           ('{"products": {}}', "products is not a list"), ('{"products": null}', "products is not a list")):
            with self.subTest(text=text):
                with self.assertRaises(ValueError) as caught:
                    provider.select_product(text, "win32-x64")
                self.assertIn(part, str(caught.exception))

    def test_the_build_must_be_stable(self):
        for build in ("insider", "Stable", "", None, 1, "stable "):
            with self.subTest(build=build):
                with self.assertRaises(ValueError) as caught:
                    provider.select_product(answer(product(build=build)), "win32-x64")
                self.assertIn("not stable", str(caught.exception))

    def test_the_product_version_must_be_numbers_and_dots(self):
        for version in ("", "1", "1.146.0-insider", "v1.146.0", "1.146.0 ", "1..146", FIVE_NUMBERS, "1.146.x",
                        "../1.146.0", "١.١٤٦.٠", None, 1.146, ["1.146.0"]):
            element = product()
            element["productVersion"] = version
            with self.subTest(version=version):
                with self.assertRaises(ValueError) as caught:
                    provider.select_product(answer(element), "win32-x64")
                self.assertIn("productVersion", str(caught.exception))

    def test_versions_that_are_fine(self):
        for version in ("1.146.0", "1.99", FOUR_NUMBERS, "10.0.12"):
            with self.subTest(version=version):
                self.assertEqual(provider.select_product(answer(product(version=version)), "win32-x64")[1], version)

    def test_the_commit_must_be_40_hex_digits(self):
        for commit in ("", "0" * 39, "0" * 41, "g" * 40, COMMIT.upper(), None, 5, "../" + "0" * 37):
            element = product()
            element["version"] = commit
            with self.subTest(commit=commit):
                with self.assertRaises(ValueError) as caught:
                    provider.select_product(answer(element), "win32-x64")
                self.assertIn("is not 40 hex digits", str(caught.exception))

    def test_the_sha256_must_be_exactly_64_hex_digits(self):
        for sha in ("", "a" * 63, "a" * 65, "g" * 64, " " + "a" * 63, "a" * 64 + "\n", "sha256:" + "a" * 57, None,
                    5, ["a" * 64]):
            with self.subTest(sha=repr(sha)[:20]):
                with self.assertRaises(ValueError) as caught:
                    provider.select_product(answer(product(sha=sha)), "win32-x64")
                self.assertIn("not exactly 64 hex digits", str(caught.exception))

    def test_the_url_must_be_exactly_the_fixed_host_folder_commit_and_name(self):
        good = DOWNLOAD_BASE + COMMIT + "/VSCodeSetup-x64-1.146.0.exe"
        other_commit = "f" * 40
        for url in (
            good.replace("https://", "http://"),
            good.replace("vscode.download.prss.microsoft.com", "example.test"),
            good.replace("vscode.download.prss.microsoft.com", "vscode.download.prss.microsoft.com.example.test"),
            good.replace("vscode.download.prss.microsoft.com", "user@vscode.download.prss.microsoft.com"),
            good.replace("vscode.download.prss.microsoft.com", "vscode.download.prss.microsoft.com:8443"),
            good.replace("/dbazure/", "/other/"),
            good.replace("/stable/", "/insider/"),
            good.replace(COMMIT, other_commit),
            good.replace("VSCodeSetup-x64", "VSCodeUserSetup-x64"),
            good.replace("VSCodeSetup-x64", "VSCodeSetup-arm64"),
            good.replace("1.146.0.exe", "1.145.0.exe"),
            good.replace(".exe", ".zip"),
            good + "?x=1", good + "#frag", good + "/", good.upper(),
            "https://example.test/" + good, "", None, 5,
        ):
            element = product()
            element["url"] = url
            with self.subTest(url=url):
                with self.assertRaises(ValueError) as caught:
                    provider.select_product(answer(element), "win32-x64")
                self.assertIn("url", str(caught.exception))
        self.assertEqual(provider.select_product(answer(product(url=good)), "win32-x64")[0], good)

    def test_the_url_of_the_arm64_installer_names_arm64(self):
        element = product("win32-arm64", url=DOWNLOAD_BASE + COMMIT + "/VSCodeSetup-x64-1.146.0.exe")
        with self.assertRaises(ValueError):
            provider.select_product(answer(element), "win32-arm64")
        url = provider.select_product(answer(product("win32-arm64")), "win32-arm64")[0]
        self.assertTrue(url.endswith("/VSCodeSetup-arm64-1.146.0.exe"))


class CheckDownloadUrlTests(unittest.TestCase):
    def test_the_installer_name(self):
        self.assertEqual(provider.installer_name("x64", "1.146.0"), "VSCodeSetup-x64-1.146.0.exe")

    def test_the_good_address_passes(self):
        provider.check_download_url(DOWNLOAD_BASE + COMMIT + "/VSCodeSetup-x64-1.146.0.exe", COMMIT, "x64", "1.146.0")

    def test_the_constants(self):
        self.assertEqual(provider.DOWNLOAD_HOST, "vscode.download.prss.microsoft.com")
        self.assertEqual(provider.DOWNLOAD_PATH_PREFIX, "/dbazure/download/stable/")
        self.assertEqual(provider.PLATFORMS, {"win32-x64": "x64", "win32-arm64": "arm64"})


class CheckAddressTests(unittest.TestCase):
    def test_only_the_fixed_host_over_https_is_allowed(self):
        for url in (
            "http://code.visualstudio.com/sha?build=stable",
            "https://example.test/sha?build=stable",
            "https://update.code.visualstudio.com/api/update/win32-x64/stable/latest",
            "https://code.visualstudio.com.example.test/x",
            "https://example.test/https://code.visualstudio.com/",
            "https://user@code.visualstudio.com/x",
            "https://user:pw@code.visualstudio.com/x",
            "https://code.visualstudio.com:8443/x",
            "https://code.visualstudio.com/x#frag",
            "https://vscode.download.prss.microsoft.com/x",
            "ftp://code.visualstudio.com/x",
            "file:///etc/passwd",
            "",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    provider.check_address(url)

    def test_the_constants_are_the_vendors_address_over_https(self):
        self.assertEqual(provider.SHA_URL, "https://code.visualstudio.com/sha?build=stable")
        self.assertEqual(provider.ALLOWED_HOST, "code.visualstudio.com")
        provider.check_address(provider.SHA_URL)


class MainTests(unittest.TestCase):
    def test_the_defaults(self):
        processor, messages = run_on(answer(product("win32-x64-user", sha=HEX_B), product()))
        self.assertEqual(processor.env["version"], "1.146.0")
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertEqual(processor.env["url"], DOWNLOAD_BASE + COMMIT + "/VSCodeSetup-x64-1.146.0.exe")
        self.assertTrue(any("1.146.0" in m for m in messages))
        self.assertTrue(any(HEX_A in m for m in messages))

    def test_the_declared_defaults_equal_the_values_the_code_uses(self):
        declared = {name: flags["default"] for name, flags in PROVIDER.input_variables.items()}
        self.assertEqual(declared, {"vscode_platform": "win32-x64"})
        for flags in PROVIDER.input_variables.values():
            self.assertIs(flags["required"], False)
            self.assertTrue(flags["description"])
        self.assertEqual(sorted(PROVIDER.output_variables), ["expected_sha256", "url", "version"])
        self.assertEqual(provider.DEFAULT_PLATFORM, "win32-x64")

    def test_a_none_platform_is_the_default(self):
        processor, _ = run_on(answer(product()), {"vscode_platform": None})
        self.assertTrue(processor.env["url"].endswith("VSCodeSetup-x64-1.146.0.exe"))

    def test_the_user_installer_the_zip_and_anything_else_are_refused_and_nothing_is_fetched(self):
        for value in ("win32-x64-user", "win32-arm64-user", "win32-x64-archive", "win32-arm64-archive",
                      "cli-win32-x64", "linux-x64", "darwin-universal-dmg", "Win32-x64", " win32-x64", "win32-x64 ",
                      "", 5, ["win32-x64"], "win32-x64\n", "x64"):
            processor, _ = new_processor(PROVIDER, {"vscode_platform": value})
            with self.subTest(value=value):
                with mock.patch.object(provider, "fetch_text") as fetch:
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                fetch.assert_not_called()
                self.assertIn("vscode_platform", str(caught.exception))
                self.assertIn("System Installer", str(caught.exception))

    def test_a_bad_answer_is_a_processor_error_and_sets_no_output(self):
        for text, part in (
            ("", "not JSON"), ("[]", "not a JSON object"), ("{}", "products is not a list"),
            (answer(product("win32-x64-user")), "no element with the os win32-x64"),
            (answer(product(), product()), "2 elements"),
            (answer(product(build="insider")), "not stable"),
            (answer(product(sha="z" * 64)), "not exactly 64 hex digits"),
            (answer(product(url="https://example.test/VSCodeSetup-x64-1.146.0.exe")), "url"),
        ):
            processor, _ = new_processor(PROVIDER, {})
            with self.subTest(part=part):
                with mock.patch.object(provider, "fetch_text", side_effect=fetcher(text)):
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                self.assertTrue(str(caught.exception).startswith("Microsoft's release file: "))
                self.assertIn(part, str(caught.exception))
                for key in ("url", "version", "expected_sha256"):
                    self.assertNotIn(key, processor.env)

    def test_a_fetch_error_passes_through_and_sets_no_output(self):
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "fetch_text", side_effect=ProcessorError("down")):
            with self.assertRaises(ProcessorError):
                processor.main()
        self.assertNotIn("url", processor.env)

    def test_the_label_has_only_numbers_and_dots(self):
        for version in ("1.146.0", "1.99", FOUR_NUMBERS):
            with self.subTest(version=version):
                processor, _ = run_on(answer(product(version=version)))
                self.assertRegex(processor.env["version"], r"^[0-9]+(\.[0-9]+){1,3}$")


class FetchTests(unittest.TestCase):
    URL = provider.SHA_URL

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
            for url in ("https://example.test/x", "http://code.visualstudio.com/x"):
                with self.subTest(url=url):
                    with self.assertRaises(ProcessorError) as caught:
                        provider.fetch_text(url, 100, "the file")
                    self.assertIn("not on the fixed host", str(caught.exception))
        opener.assert_not_called()

    def test_a_status_other_than_200_is_an_error_that_names_it(self):
        for code, reason in ((404, "Not Found"), (500, "Server Error"), (429, "Too Many Requests")):
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

    def test_the_limits_are_sensible(self):
        self.assertGreaterEqual(provider.MAX_SHA_BYTES, 64 * 1024)
        self.assertLessEqual(provider.MAX_SHA_BYTES, 2 * 1024 * 1024)
        self.assertGreater(provider.FETCH_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(provider.FETCH_TIMEOUT_SECONDS, 600)


class SourceTests(unittest.TestCase):
    def test_the_module_has_no_other_address_and_no_hash(self):
        text = read(os.path.join(RECIPE_DIR, "VisualStudioCodeInfoProvider.py"))
        hosts = set(re.findall(r"https?://([A-Za-z0-9.-]+)", text))
        self.assertEqual(hosts, {provider.ALLOWED_HOST, provider.DOWNLOAD_HOST})
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", text))
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{40}\b", text))

    def test_the_update_address_that_was_not_read_is_not_used(self):
        text = read(os.path.join(RECIPE_DIR, "VisualStudioCodeInfoProvider.py"))
        self.assertNotIn("update.code.visualstudio.com", text)


if __name__ == "__main__":
    unittest.main()
