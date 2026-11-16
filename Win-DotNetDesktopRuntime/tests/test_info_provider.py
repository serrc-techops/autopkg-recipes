"""Tests of DotNetDesktopRuntimeInfoProvider and Sha512ChecksumVerifier. No test uses the network:
fetch_json() or open_request() is replaced.

releases_excerpt.json has the structure of the real metadata read on 2026-11-16 (two releases, the
files of each), with invented hash digits: they are not the hash of any file.
"""
import copy
import hashlib
import io
import json
import os
import sys
import tempfile
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

import DotNetDesktopRuntimeInfoProvider as provider  # noqa: E402
import Sha512ChecksumVerifier as verifier  # noqa: E402

PROVIDER = provider.DotNetDesktopRuntimeInfoProvider
EXCERPT = os.path.join(TESTS_DIR, "releases_excerpt.json")
URL_15 = "https://builds.dotnet.microsoft.com/dotnet/WindowsDesktop/10.0.15/windowsdesktop-runtime-10.0.15-win-x64.exe"


def excerpt():
    with open(EXCERPT, "r", encoding="utf-8") as handle:
        return json.load(handle)


def x64_file(data, release=0):
    for entry in data["releases"][release]["windowsdesktop"]["files"]:
        if entry["name"] == "windowsdesktop-runtime-win-x64.exe":
            return entry
    raise AssertionError("fixture has no x64 exe")


class SelectTests(unittest.TestCase):
    def select(self, data, **kwargs):
        return provider.select_installer(data, kwargs.pop("channel", "10.0"), kwargs.pop("rid", "win-x64"), **kwargs)

    def test_the_latest_release_and_its_x64_exe(self):
        chosen = self.select(excerpt())
        self.assertEqual(chosen["url"], URL_15)
        self.assertEqual(chosen["version"], "10.0.15")
        self.assertEqual(chosen["filename"], "windowsdesktop-runtime-10.0.15-win-x64.exe")
        self.assertEqual(chosen["expected_sha512"], x64_file(excerpt())["hash"])
        self.assertEqual(chosen["release_date"], "2026-11-10")

    def test_the_other_rids(self):
        for rid in ("win-x86", "win-arm64"):
            chosen = self.select(excerpt(), rid=rid)
            self.assertTrue(chosen["url"].endswith("windowsdesktop-runtime-10.0.15-%s.exe" % rid))

    def test_the_release_is_the_one_named_latest_not_the_first_of_the_list(self):
        data = excerpt()
        data["releases"].reverse()
        self.assertEqual(self.select(data)["version"], "10.0.15")
        data = excerpt()
        data["latest-release"] = "10.0.14"
        chosen = self.select(data)
        self.assertEqual(chosen["version"], "10.0.14")
        self.assertEqual(chosen["expected_sha512"], x64_file(excerpt(), 1)["hash"])

    def refuses(self, data, text, **kwargs):
        with self.assertRaises(ValueError) as caught:
            self.select(data, **kwargs)
        self.assertIn(text, str(caught.exception))

    def test_a_hash_in_capitals_is_returned_in_lower_case(self):
        data = excerpt()
        x64_file(data)["hash"] = "ab" * 64
        x64_file(data)["hash"] = x64_file(data)["hash"].upper()
        self.assertEqual(self.select(data)["expected_sha512"], "ab" * 64)

    def test_a_channel_that_is_not_two_numbers(self):
        for bad in ("10", "10.0.1", "x.0", "10.0 ", "../10.0", "", None, 10.0):
            with self.subTest(channel=bad):
                with self.assertRaises(ValueError):
                    provider.metadata_url(bad)
        self.assertEqual(provider.metadata_url("10.0"),
                         "https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json")

    def test_a_rid_that_is_not_allowed(self):
        for bad in ("linux-x64", "win-arm", "WIN-X64", "", None):
            with self.subTest(rid=bad):
                with self.assertRaises(ValueError):
                    provider.validate_rid(bad)

    def test_the_metadata_of_another_channel(self):
        data = excerpt()
        data["channel-version"] = "9.0"
        self.refuses(data, "is of channel")

    def test_support_phases(self):
        for phase, allowed in (("active", True), ("maintenance", True), ("eol", False), ("preview", False),
                               ("go-live", False), (None, False)):
            data = excerpt()
            data["support-phase"] = phase
            with self.subTest(phase=phase):
                if allowed:
                    self.select(data)
                else:
                    with self.assertRaises(ValueError):
                        self.select(data)

    def test_eol_only_with_the_input(self):
        data = excerpt()
        data["support-phase"] = "eol"
        self.refuses(data, "end of life")
        self.assertEqual(self.select(data, allow_eol=True)["version"], "10.0.15")
        data["support-phase"] = "preview"
        self.refuses(data, "support-phase", allow_eol=True)

    def test_a_preview_or_candidate_is_refused(self):
        for bad in ("10.0.0-rc.2.25502.107", "10.0.0-preview.7", "10.0", ".".join(["10", "0", "15", "1"]), "10.0.015", "11.0.1", "v10.0.1"):
            data = excerpt()
            data["latest-release"] = bad
            with self.subTest(latest=bad):
                with self.assertRaises(ValueError):
                    self.select(data)

    def test_a_runtime_version_that_differs_from_a_plain_version(self):
        data = excerpt()
        data["releases"][0]["windowsdesktop"]["version"] = "10.0.15-servicing.1"
        self.refuses(data, "windowsdesktop version")

    def test_the_latest_release_missing_or_twice(self):
        data = excerpt()
        data["latest-release"] = "10.0.99"
        self.refuses(data, "0 times")
        data = excerpt()
        data["releases"].append(copy.deepcopy(data["releases"][0]))
        self.refuses(data, "2 times")

    def test_missing_sections(self):
        data = excerpt()
        del data["releases"][0]["windowsdesktop"]
        self.refuses(data, "no windowsdesktop")
        data = excerpt()
        data["releases"][0]["windowsdesktop"]["files"] = [
            f for f in data["releases"][0]["windowsdesktop"]["files"] if not f["name"].endswith("win-x64.exe")]
        self.refuses(data, "has no file windowsdesktop-runtime-win-x64.exe")
        data = excerpt()
        data["releases"] = {}
        self.refuses(data, "no list of releases")
        self.refuses([], "not a JSON object")

    def test_the_exe_listed_twice_or_with_another_rid(self):
        data = excerpt()
        data["releases"][0]["windowsdesktop"]["files"].append(copy.deepcopy(x64_file(data)))
        self.refuses(data, "2 times")
        data = excerpt()
        x64_file(data)["rid"] = "win-x86"
        self.refuses(data, "names the rid")

    def test_an_address_that_is_not_the_expected_one(self):
        bad_urls = (
            "http://builds.dotnet.microsoft.com/dotnet/WindowsDesktop/10.0.15/windowsdesktop-runtime-10.0.15-win-x64.exe",
            "https://example.org/dotnet/WindowsDesktop/10.0.15/windowsdesktop-runtime-10.0.15-win-x64.exe",
            "https://builds.dotnet.microsoft.com.example.org/dotnet/WindowsDesktop/10.0.15/windowsdesktop-runtime-10.0.15-win-x64.exe",
            "https://user@builds.dotnet.microsoft.com/dotnet/WindowsDesktop/10.0.15/windowsdesktop-runtime-10.0.15-win-x64.exe",
            URL_15 + "?x=1",
            URL_15 + "#x",
            URL_15.replace("10.0.15/windowsdesktop", "10.0.14/windowsdesktop"),
            URL_15.replace("win-x64.exe", "win-x86.exe"),
            URL_15.replace("/WindowsDesktop/", "/Runtime/"),
            "https://aka.ms/dotnet/10.0/windowsdesktop-runtime-win-x64.exe",
            None, 5,
        )
        for url in bad_urls:
            data = excerpt()
            x64_file(data)["url"] = url
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    self.select(data)

    def test_a_hash_that_is_not_a_sha512(self):
        good = x64_file(excerpt())["hash"]
        for bad in (good[:64], good + "0", good[:-1] + "g", "", None, 5, "sha512:" + good):
            data = excerpt()
            x64_file(data)["hash"] = bad
            with self.subTest(hash=str(bad)[:20]):
                with self.assertRaises(ValueError):
                    self.select(data)

    def test_the_release_date_is_empty_when_it_is_not_a_plain_date(self):
        data = excerpt()
        data["releases"][0]["release-date"] = "x y"
        self.assertEqual(self.select(data)["release_date"], "")
        del data["releases"][0]["release-date"]
        self.assertEqual(self.select(data)["release_date"], "")


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class FetchTests(unittest.TestCase):
    URL = provider.metadata_url("10.0")

    def fetch(self, body=b"{}", status=200):
        response = FakeResponse(body)
        response.status = status
        with mock.patch.object(provider, "open_request", return_value=response) as opened:
            result = provider.fetch_json(self.URL)
        return result, opened

    def test_json_comes_back_and_the_request_has_no_redirect_handler_problem(self):
        result, opened = self.fetch(b'{"a": 1}')
        self.assertEqual(result, {"a": 1})
        self.assertEqual(opened.call_args[0][0].full_url, self.URL)

    def test_an_address_outside_the_host_is_refused_before_a_request(self):
        with mock.patch.object(provider, "open_request") as opened:
            for url in ("https://example.org/x", "http://builds.dotnet.microsoft.com/x", None):
                with self.assertRaises(ProcessorError):
                    provider.fetch_json(url)
        opened.assert_not_called()

    def test_not_200_too_large_not_json_not_utf8(self):
        with self.assertRaises(ProcessorError):
            self.fetch(status=204)
        with mock.patch.object(provider, "open_request", return_value=FakeResponse(b"x" * 20)):
            with self.assertRaises(ProcessorError) as caught:
                provider.fetch_json(self.URL, max_bytes=10)
        self.assertIn("larger", str(caught.exception))
        with self.assertRaises(ProcessorError):
            self.fetch(b"not json")
        with self.assertRaises(ProcessorError):
            self.fetch(b"\xff\xfe")

    def test_a_redirect_and_a_network_error_are_errors(self):
        err = urllib.error.HTTPError(self.URL, 302, "Found", {}, io.BytesIO(b""))
        with mock.patch.object(provider, "open_request", side_effect=err):
            with self.assertRaises(ProcessorError) as caught:
                provider.fetch_json(self.URL)
        self.assertIn("redirect is not followed", str(caught.exception))
        with mock.patch.object(provider, "open_request", side_effect=urllib.error.URLError("down")):
            with self.assertRaises(ProcessorError):
                provider.fetch_json(self.URL)

    def test_the_redirect_handler_returns_no_new_request(self):
        self.assertIsNone(provider.NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://example.org/"))


class ProcessorTests(unittest.TestCase):
    def run_provider(self, data=None, **env):
        with mock.patch.object(provider, "fetch_json", return_value=data if data is not None else excerpt()) as fetched:
            processor, messages = run_processor(PROVIDER, env)
        return processor, fetched

    def test_the_defaults_and_the_outputs(self):
        processor, fetched = self.run_provider()
        fetched.assert_called_once_with("https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json")
        self.assertEqual(processor.env["url"], URL_15)
        self.assertEqual(processor.env["version"], "10.0.15")
        self.assertEqual(processor.env["filename"], "windowsdesktop-runtime-10.0.15-win-x64.exe")
        self.assertEqual(processor.env["expected_sha512"], x64_file(excerpt())["hash"])
        self.assertEqual(processor.env["dotnet_release_date"], "2026-11-10")

    def test_the_inputs_are_used(self):
        processor, _ = self.run_provider(dotnet_rid="win-arm64")
        self.assertTrue(processor.env["url"].endswith("-win-arm64.exe"))

    def test_bad_inputs_stop_before_any_fetch(self):
        for env in ({"dotnet_channel": "ten"}, {"dotnet_rid": "linux-x64"}, {"dotnet_allow_eol": "true"}):
            with self.subTest(env=env):
                with mock.patch.object(provider, "fetch_json") as fetched:
                    with self.assertRaises(ProcessorError):
                        run_processor(PROVIDER, env)
                fetched.assert_not_called()

    def test_a_refusal_sets_no_output(self):
        data = excerpt()
        data["support-phase"] = "eol"
        with mock.patch.object(provider, "fetch_json", return_value=data):
            processor, _ = provider_new({})
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        self.assertIn("channel 10.0", str(caught.exception))
        for key in ("url", "version", "expected_sha512", "filename"):
            self.assertNotIn(key, processor.env)

    def test_the_inputs_have_the_flags_that_autopkg_reads_and_the_outputs_never_share_a_name(self):
        for name, flags in PROVIDER.input_variables.items():
            self.assertIn("required", flags, name)
            self.assertIn("description", flags, name)
        self.assertFalse(set(PROVIDER.output_variables) & set(PROVIDER.input_variables))
        for name in ("url", "version", "expected_sha512", "filename"):
            self.assertIn(name, PROVIDER.output_variables)


def provider_new(env):
    from _win_support import new_processor
    processor, _ = new_processor(PROVIDER, env)
    return processor, _


class Sha512Tests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "installer.exe")
        with open(self.path, "wb") as handle:
            handle.write(b"made-up installer bytes" * 1000)
        self.sha512 = hashlib.sha512(b"made-up installer bytes" * 1000).hexdigest()
        self.sha256 = hashlib.sha256(b"made-up installer bytes" * 1000).hexdigest()

    def run_verifier(self, expected, path=None):
        return run_processor(verifier.Sha512ChecksumVerifier, {"pathname": path or self.path, "expected_sha512": expected})

    def test_a_match_sets_both_outputs(self):
        processor, _ = self.run_verifier(self.sha512)
        self.assertIs(processor.env["checksum_verified"], True)
        self.assertEqual(processor.env["checksum_sha256"], self.sha256)

    def test_letter_case_and_prefix_are_accepted(self):
        for value in (self.sha512.upper(), "sha512:" + self.sha512, " SHA512: " + self.sha512 + "\n"):
            with self.subTest(value=value[:12]):
                processor, _ = self.run_verifier(value)
                self.assertIs(processor.env["checksum_verified"], True)

    def test_a_mismatch_stops_and_sets_nothing(self):
        other = ("0" if self.sha512[0] != "0" else "1") + self.sha512[1:]
        with self.assertRaises(ProcessorError) as caught:
            processor, _ = self.run_verifier(other)
        self.assertIn("SHA-512 mismatch", str(caught.exception))
        from _win_support import new_processor
        processor, _ = new_processor(verifier.Sha512ChecksumVerifier, {"pathname": self.path, "expected_sha512": other})
        with self.assertRaises(ProcessorError):
            processor.main()
        self.assertNotIn("checksum_verified", processor.env)
        self.assertNotIn("checksum_sha256", processor.env)

    def test_a_sha256_is_not_a_sha512(self):
        with self.assertRaises(ProcessorError):
            self.run_verifier(self.sha256)

    def test_malformed_values(self):
        for bad in ("", "   ", "sha512:", self.sha512[:-1], self.sha512 + "0", self.sha512[:-1] + "g", None, 5,
                    self.sha512 + " installer.exe", "sha256:" + self.sha512):
            with self.subTest(value=str(bad)[:20]):
                with self.assertRaises(ProcessorError):
                    self.run_verifier(bad)

    def test_a_missing_file(self):
        with self.assertRaises(ProcessorError):
            self.run_verifier(self.sha512, path=os.path.join(self.dir.name, "nope.exe"))
        with self.assertRaises(ProcessorError):
            self.run_verifier(self.sha512, path=self.dir.name)

    def test_the_message_does_not_print_the_whole_hash(self):
        other = ("0" if self.sha512[0] != "0" else "1") + self.sha512[1:]
        with self.assertRaises(ProcessorError) as caught:
            self.run_verifier(other)
        self.assertNotIn(other, str(caught.exception))
        self.assertNotIn(self.sha512, str(caught.exception))

    def test_the_declared_outputs_are_the_two_that_the_shared_verifier_declares(self):
        from _win_support import checksum
        self.assertEqual(set(verifier.Sha512ChecksumVerifier.output_variables),
                         set(checksum.ChecksumVerifier.output_variables))


if __name__ == "__main__":
    unittest.main()
