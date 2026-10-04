"""Tests of AdoptiumInfoProvider: every branch. No test uses the network:
fetch_text() or open_request() is replaced.

THE EXCERPT IS WRITTEN BY HAND. adoptium_latest_excerpt.json was written by hand
after the real answer of 2026-10-02 (the API answered an array of one element in
this shape), not saved from the real server. Its digits are made up. A test that
reads it is still a real test of the parser, but it proves nothing about what the
project's API answers today: the first run on the build Mac is that check.
"""
import copy
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

import AdoptiumInfoProvider as provider  # noqa: E402

PROVIDER = provider.AdoptiumInfoProvider
EXCERPT = os.path.join(TESTS_DIR, "adoptium_latest_excerpt.json")
HAND_WRITTEN_NOTE = "written by hand after the real answer of 2026-10-02, with made-up digits for the checksums"
HEX_A = "a" * 64
HEX_B = "b" * 64
RELEASE_DOWNLOAD = "https://github.com/adoptium/temurin8-binaries/releases/download/"
API_ADDRESS = ("https://api.adoptium.net/v3/assets/latest/8/hotspot"
               "?os=windows&architecture=x64&image_type=jre&vendor=eclipse")
MSI_NAME = "OpenJDK8U-jre_x64_windows_hotspot_8u504b01.msi"
BACKSLASH_PATH = "a" + chr(92) + "b"


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def element(release_name="jdk8u504-b01", feature="8", image_type="jre", architecture="x64", os_name="windows",
            name=None, link=None, checksum=HEX_A, **binary_extra):
    """A made-up element in the shape of the project's answer."""
    if name is None:
        name = "OpenJDK%sU-%s_%s_%s_hotspot_8u504b01.msi" % (feature, image_type, architecture, os_name)
    if link is None:
        link = "https://github.com/adoptium/temurin%s-binaries/releases/download/%s/%s" % (feature, release_name, name)
    binary = {
        "os": os_name, "architecture": architecture, "image_type": image_type,
        "installer": {"name": name, "size": 1234, "link": link, "checksum": checksum},
        "package": {"name": name[:-4] + ".zip", "link": link[:-4] + ".zip", "checksum": HEX_B},
    }
    binary.update(binary_extra)
    return {"release_name": release_name, "version": {"semver": "8.0.504+1"}, "binary": binary}


def answer(*elements):
    return json.dumps(list(elements))


def run_on(text, env=None, record=None):
    """Run the processor on the text of an answer. Returns (processor, messages)."""
    def fetch(url, max_bytes, what):
        if record is not None:
            record.append((url, max_bytes, what))
        return text
    with mock.patch.object(provider, "fetch_text", side_effect=fetch):
        return run_processor(PROVIDER, env or {})


def fails_on(text, env=None):
    """Run the processor, expect a ProcessorError, return it and the processor."""
    processor, _ = new_processor(PROVIDER, env or {})
    with mock.patch.object(provider, "fetch_text", return_value=text):
        try:
            processor.main()
        except ProcessorError as err:
            return err, processor
    raise AssertionError("the processor did not stop")


def choose(text, feature="8", image_type="jre", architecture="x64", operating_system="windows"):
    return provider.choose_installer(text, feature, image_type, architecture, operating_system)


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
        self.assertEqual(json.loads(self.text)[0]["_written_by_hand"], HAND_WRITTEN_NOTE)
        self.assertIn("WRITTEN BY HAND", read(__file__))
        self.assertIn("after the real answer of 2026-10-02", read(__file__))

    def test_the_excerpt_is_small_and_an_array_of_one_element(self):
        self.assertLess(len(self.text), 4000)
        self.assertEqual(len(json.loads(self.text)), 1)

    def test_the_outputs(self):
        processor, messages = run_on(self.text)
        self.assertEqual(processor.env["version"], "jdk8u504-b01")
        self.assertEqual(processor.env["url"], RELEASE_DOWNLOAD + "jdk8u504-b01/" + MSI_NAME)
        data = json.loads(self.text)[0]["binary"]["installer"]
        self.assertEqual(processor.env["expected_sha256"], data["checksum"])
        self.assertRegex(processor.env["expected_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(any("jdk8u504-b01" in m for m in messages))
        self.assertTrue(any(data["checksum"] in m for m in messages))

    def test_the_installer_is_taken_and_the_zip_package_never(self):
        processor, _ = run_on(self.text)
        package = json.loads(self.text)[0]["binary"]["package"]
        self.assertTrue(processor.env["url"].endswith(".msi"))
        self.assertNotEqual(processor.env["url"], package["link"])
        self.assertNotEqual(processor.env["expected_sha256"], package["checksum"])

    def test_the_request_is_the_fixed_address_with_its_limit(self):
        record = []
        run_on(self.text, record=record)
        self.assertEqual(record, [(API_ADDRESS, provider.MAX_ANSWER_BYTES, "The Adoptium API")])


class AddressTests(unittest.TestCase):
    def test_the_api_address_of_the_defaults(self):
        self.assertEqual(provider.api_address("8", "jre", "x64", "windows"), API_ADDRESS)

    def test_the_api_address_follows_the_inputs(self):
        self.assertEqual(
            provider.api_address("17", "jdk", "aarch64", "windows"),
            "https://api.adoptium.net/v3/assets/latest/17/hotspot"
            "?os=windows&architecture=aarch64&image_type=jdk&vendor=eclipse",
        )

    def test_the_link_prefix_follows_the_feature_version(self):
        self.assertEqual(provider.link_prefix("8"), RELEASE_DOWNLOAD)
        self.assertEqual(provider.link_prefix("21"), "https://github.com/adoptium/temurin21-binaries/releases/download/")

    def test_only_the_fixed_host_over_https_is_allowed(self):
        provider.check_address(API_ADDRESS)
        for url in (
            "http://api.adoptium.net/v3/assets/latest/8/hotspot",
            "https://example.test/v3/assets/latest/8/hotspot",
            "https://github.com/adoptium/temurin8-binaries/",
            "https://api.adoptium.net.example.test/x",
            "https://example.test/https://api.adoptium.net/",
            "https://user@api.adoptium.net/x",
            "https://user:pw@api.adoptium.net/x",
            "https://api.adoptium.net:8443/x",
            "https://api.adoptium.net/x#frag",
            "ftp://api.adoptium.net/x",
            "file:///etc/passwd",
            "",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    provider.check_address(url)

    def test_the_constants_are_the_projects_address_over_https(self):
        self.assertEqual(provider.API_BASE_URL, "https://api.adoptium.net/v3/assets/latest/")
        self.assertEqual(provider.ALLOWED_HOSTS, ("api.adoptium.net",))
        provider.check_address(provider.API_BASE_URL)


class ChooseInstallerTests(unittest.TestCase):
    def test_a_good_answer(self):
        url, release, sha256 = choose(answer(element()))
        self.assertEqual(url, RELEASE_DOWNLOAD + "jdk8u504-b01/" + MSI_NAME)
        self.assertEqual(release, "jdk8u504-b01")
        self.assertEqual(sha256, HEX_A)

    def test_the_hash_is_returned_in_lower_case(self):
        self.assertEqual(choose(answer(element(checksum="A" * 64)))[2], HEX_A)

    def test_other_inputs_choose_other_names_and_links(self):
        for feature, image_type, architecture in (("17", "jre", "x64"), ("8", "jdk", "x64"), ("11", "jre", "aarch64"),
                                                  ("21", "jdk", "x86")):
            with self.subTest(feature=feature, image_type=image_type, architecture=architecture):
                item = element(feature=feature, image_type=image_type, architecture=architecture)
                url, _, _ = choose(answer(item), feature, image_type, architecture)
                self.assertTrue(url.startswith(provider.link_prefix(feature)))
                self.assertTrue(url.endswith(".msi"))

    def test_a_release_name_with_a_plus_and_its_encoded_link_are_accepted(self):
        item = element(release_name="jdk-17.0.9+9", feature="17",
                       link="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.9%2B9/"
                            "OpenJDK17U-jre_x64_windows_hotspot_17.0.9_9.msi",
                       name="OpenJDK17U-jre_x64_windows_hotspot_17.0.9_9.msi")
        url, release, _ = choose(answer(item), feature="17")
        self.assertEqual(release, "jdk-17.0.9+9")
        self.assertIn("jdk-17.0.9%2B9", url)

    def test_the_answer_must_be_json_in_an_array_of_exactly_one_element(self):
        for text, part in (
            ("", "not JSON"), ("not json", "not JSON"), ("[", "not JSON"), ("<html>Bad Gateway</html>", "not JSON"),
            ("{}", "not a JSON array"), ('"text"', "not a JSON array"), ("null", "not a JSON array"),
            ("[]", "0 elements"), (answer(element(), element()), "2 elements"),
            ("[null]", "not a JSON object"), ('["x"]', "not a JSON object"), ("[[]]", "not a JSON object"),
        ):
            with self.subTest(text=text[:30]):
                with self.assertRaises(ValueError) as caught:
                    choose(text)
                self.assertIn(part, str(caught.exception))

    def test_two_elements_are_refused_also_when_they_agree(self):
        with self.assertRaises(ValueError):
            choose(answer(element(), element()))

    def test_the_release_name_must_have_the_form_of_a_release_name(self):
        for value in (None, 5, "", [], "a b", "../x", "a/b", BACKSLASH_PATH, "x" * 65, "a\n", "é", "a;b", "a?b", ".", "..",
                      "-x", "+x", ".x"):
            item = element()
            item["release_name"] = value
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    choose(answer(item))
                self.assertIn("release_name", str(caught.exception))
        item = element()
        del item["release_name"]
        with self.assertRaises(ValueError):
            choose(answer(item))

    def test_the_binary_must_be_an_object(self):
        for value in (None, [], "x", 5):
            item = element()
            item["binary"] = value
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    choose(answer(item))
                self.assertIn("no binary", str(caught.exception))
        item = element()
        del item["binary"]
        with self.assertRaises(ValueError):
            choose(answer(item))

    def test_the_os_the_architecture_and_the_image_type_must_equal_the_inputs(self):
        for key, value in (("os", "linux"), ("os", "Windows"), ("os", None), ("architecture", "aarch64"),
                           ("architecture", "x64 "), ("image_type", "jdk"), ("image_type", "JRE"),
                           ("image_type", None), ("image_type", ["jre"])):
            item = element()
            item["binary"][key] = value
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError) as caught:
                    choose(answer(item))
                self.assertIn("its binary has %s" % key, str(caught.exception))
        for key in ("os", "architecture", "image_type"):
            item = element()
            del item["binary"][key]
            with self.subTest(missing=key):
                with self.assertRaises(ValueError):
                    choose(answer(item))

    def test_an_answer_for_other_inputs_is_refused(self):
        with self.assertRaises(ValueError):
            choose(answer(element(image_type="jdk")), image_type="jre")
        with self.assertRaises(ValueError):
            choose(answer(element(architecture="x86")), architecture="x64")

    def test_the_installer_must_be_an_object(self):
        for value in (None, [], "x", 5):
            item = element()
            item["binary"]["installer"] = value
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    choose(answer(item))
                self.assertIn("no installer", str(caught.exception))
        item = element()
        del item["binary"]["installer"]
        with self.assertRaises(ValueError):
            choose(answer(item))

    def test_a_missing_installer_never_falls_back_to_the_zip_package(self):
        item = element()
        del item["binary"]["installer"]
        with self.assertRaises(ValueError) as caught:
            choose(answer(item))
        self.assertIn("no installer", str(caught.exception))

    def test_the_installer_name_must_end_in_msi(self):
        for name in ("OpenJDK8U-jre_x64_windows_hotspot_8u504b01.zip", "x.msi.exe", "x.MSI", ".msi", "msi", "",
                     "a b.msi", "a/b.msi", BACKSLASH_PATH + ".msi", "a%2Fb.msi", "a\n.msi", "..msi", "-x.msi", None, 5, ["x.msi"],
                     "a" * 130 + ".msi"):
            item = element()
            item["binary"]["installer"]["name"] = name
            with self.subTest(name=name):
                with self.assertRaises(ValueError) as caught:
                    choose(answer(item))
                self.assertIn("name that ends in .msi", str(caught.exception))

    def test_the_link_must_begin_with_the_projects_release_folder_of_the_feature(self):
        for link in (
            "http://github.com/adoptium/temurin8-binaries/releases/download/jdk8u504-b01/" + MSI_NAME,
            "https://example.test/adoptium/temurin8-binaries/releases/download/jdk8u504-b01/" + MSI_NAME,
            "https://github.com.example.test/adoptium/temurin8-binaries/releases/download/jdk8u504-b01/" + MSI_NAME,
            "https://github.com/other/temurin8-binaries/releases/download/jdk8u504-b01/" + MSI_NAME,
            "https://github.com/adoptium/temurin17-binaries/releases/download/jdk8u504-b01/" + MSI_NAME,
            "https://github.com/adoptium/temurin8-binaries/releases/latest/download/" + MSI_NAME,
            "https://user@github.com/adoptium/temurin8-binaries/releases/download/jdk8u504-b01/" + MSI_NAME,
            "https://github.com:8443/adoptium/temurin8-binaries/releases/download/jdk8u504-b01/" + MSI_NAME,
            MSI_NAME, "", "/adoptium/temurin8-binaries/releases/download/jdk8u504-b01/" + MSI_NAME,
        ):
            item = element(link=link)
            with self.subTest(link=link):
                with self.assertRaises(ValueError):
                    choose(answer(item))

    def test_the_link_is_exactly_one_folder_and_the_installer_name(self):
        base = RELEASE_DOWNLOAD
        for link in (
            base + MSI_NAME,                                     # no folder
            base + "jdk8u504-b01/extra/" + MSI_NAME,             # a second folder
            base + "../" + MSI_NAME,                             # a way up
            base + "jdk8u504-b01/../" + MSI_NAME,
            base + "./" + MSI_NAME,                              # the folder is a dot
            base + "%2e%2e/" + MSI_NAME,                         # an encoded way up
            base + "%2E%2E/" + MSI_NAME,
            base + "jdk8u504-b01%2F/" + MSI_NAME,                # an encoded slash
            base + "-x/" + MSI_NAME,
            base + "jdk8u504-b01//" + MSI_NAME,
            base + "jdk8u504-b01/" + MSI_NAME + "?x=1",          # a query
            base + "jdk8u504-b01/" + MSI_NAME + "#x",            # a fragment
            base + "jdk8u504-b01/" + MSI_NAME + "/",
            base + "jdk8u504-b01/other.msi",                     # another file than the named one
            base + "jdk8u504-b01 /" + MSI_NAME,
            base + "jdk8u504-b01/" + MSI_NAME + " ",
            base + "/" + MSI_NAME,
            base + "jdk8u504-b01/",
            base,
        ):
            item = element(link=link)
            with self.subTest(link=link):
                with self.assertRaises(ValueError) as caught:
                    choose(answer(item))
                self.assertIn("link of the installer", str(caught.exception))

    def test_a_link_that_is_not_text_is_an_error(self):
        for value in (None, 5, [], {"a": "b"}):
            item = element()
            item["binary"]["installer"]["link"] = value
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    choose(answer(item))
                self.assertIn("no link", str(caught.exception))
        item = element()
        del item["binary"]["installer"]["link"]
        with self.assertRaises(ValueError):
            choose(answer(item))

    def test_the_checksum_must_be_64_hex_digits(self):
        for value in (None, 5, "", "a" * 63, "a" * 65, "z" * 64, "sha256:" + HEX_A, HEX_A + "\n", " " + HEX_A,
                      HEX_A + "  " + MSI_NAME, [HEX_A], "a" * 32 + " " + "a" * 31):
            item = element()
            item["binary"]["installer"]["checksum"] = value
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    choose(answer(item))
                self.assertIn("checksum of 64 hex digits", str(caught.exception))
        item = element()
        del item["binary"]["installer"]["checksum"]
        with self.assertRaises(ValueError):
            choose(answer(item))

    def test_the_checksum_of_the_package_is_never_a_substitute(self):
        item = element()
        del item["binary"]["installer"]["checksum"]
        self.assertIn("checksum", item["binary"]["package"])
        with self.assertRaises(ValueError):
            choose(answer(item))

    def test_the_errors_do_not_echo_long_text(self):
        item = element()
        item["binary"]["os"] = "x" * 500
        with self.assertRaises(ValueError) as caught:
            choose(answer(item))
        self.assertLess(len(str(caught.exception)), 200)

    def test_the_input_element_is_not_changed(self):
        item = element()
        before = copy.deepcopy(item)
        choose(answer(item))
        self.assertEqual(item, before)


class MainTests(unittest.TestCase):
    def test_the_defaults(self):
        processor, messages = run_on(answer(element()))
        self.assertEqual(processor.env["version"], "jdk8u504-b01")
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertEqual(processor.env["url"], RELEASE_DOWNLOAD + "jdk8u504-b01/" + MSI_NAME)
        self.assertTrue(any("jdk8u504-b01" in m for m in messages))
        self.assertTrue(any(HEX_A in m for m in messages))

    def test_the_declared_defaults_equal_the_values_the_code_uses(self):
        declared = {name: flags["default"] for name, flags in PROVIDER.input_variables.items()}
        self.assertEqual(declared, {"temurin_feature_version": "8", "temurin_image_type": "jre",
                                    "temurin_architecture": "x64", "temurin_os": "windows"})
        self.assertEqual(declared["temurin_feature_version"], provider.DEFAULT_FEATURE_VERSION)
        self.assertEqual(declared["temurin_image_type"], provider.DEFAULT_IMAGE_TYPE)
        self.assertEqual(declared["temurin_architecture"], provider.DEFAULT_ARCHITECTURE)
        self.assertEqual(declared["temurin_os"], provider.DEFAULT_OS)
        for flags in PROVIDER.input_variables.values():
            self.assertIs(flags["required"], False)
            self.assertTrue(flags["description"])
        self.assertEqual(sorted(PROVIDER.output_variables), ["expected_sha256", "url", "version"])
        self.assertEqual(provider.IMAGE_TYPES, ("jre", "jdk"))
        self.assertEqual(provider.ARCHITECTURES, ("x64", "x86", "aarch64"))
        self.assertEqual(provider.OPERATING_SYSTEMS, ("windows",))

    def test_the_inputs_choose_the_address_and_the_answer_they_expect(self):
        for env, address in (
            ({"temurin_feature_version": "17"},
             "https://api.adoptium.net/v3/assets/latest/17/hotspot?os=windows&architecture=x64&image_type=jre&vendor=eclipse"),
            ({"temurin_image_type": "jdk"},
             "https://api.adoptium.net/v3/assets/latest/8/hotspot?os=windows&architecture=x64&image_type=jdk&vendor=eclipse"),
            ({"temurin_architecture": "aarch64"},
             "https://api.adoptium.net/v3/assets/latest/8/hotspot?os=windows&architecture=aarch64&image_type=jre&vendor=eclipse"),
        ):
            feature = env.get("temurin_feature_version", "8")
            image_type = env.get("temurin_image_type", "jre")
            architecture = env.get("temurin_architecture", "x64")
            record = []
            with self.subTest(env=env):
                processor, _ = run_on(answer(element(feature=feature, image_type=image_type,
                                                     architecture=architecture)), env, record)
                self.assertEqual(record[0][0], address)
                self.assertTrue(processor.env["url"].startswith(provider.link_prefix(feature)))

    def test_an_answer_for_other_inputs_is_a_processor_error(self):
        error, processor = fails_on(answer(element(image_type="jdk")))
        self.assertIn("The Adoptium API answer:", str(error))
        self.assertIn("image_type", str(error))
        self.assertNotIn("url", processor.env)

    def test_a_feature_version_that_is_not_digits_is_an_error_and_nothing_is_fetched(self):
        for value in ("", " ", "8 ", " 8", "0", "08", "1000", "8.0", "8u", "../8", "8/x", "8?x", "8&os=linux", "latest",
                      "-8", "٨", "8\n", None, 8, ["8"]):
            processor, _ = new_processor(PROVIDER, {"temurin_feature_version": value})
            with self.subTest(value=value):
                with mock.patch.object(provider, "fetch_text") as fetch:
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                fetch.assert_not_called()
                self.assertIn("temurin_feature_version", str(caught.exception))

    def test_features_that_are_fine(self):
        for value in ("8", "11", "17", "21", "25", "100"):
            with self.subTest(value=value):
                processor, _ = run_on(answer(element(feature=value)), {"temurin_feature_version": value})
                self.assertTrue(processor.env["url"].startswith(provider.link_prefix(value)))

    def test_a_choice_that_is_not_allowed_is_an_error_and_nothing_is_fetched(self):
        for name, values in (
            ("temurin_image_type", ("", "JRE", "jre ", "jdk\n", "jre,jdk", "testimage", "debugimage", "sources",
                                    "staticlibs", None, 5, ["jre"])),
            ("temurin_architecture", ("", "X64", "amd64", "arm64", "x64 ", "x64&os=linux", "x32", "ppc64le", None)),
            ("temurin_os", ("", "Windows", "linux", "mac", "windows ", "windows&x=1", "../windows", None, 5)),
        ):
            for value in values:
                processor, _ = new_processor(PROVIDER, {name: value})
                with self.subTest(name=name, value=value):
                    with mock.patch.object(provider, "fetch_text") as fetch:
                        with self.assertRaises(ProcessorError) as caught:
                            processor.main()
                    fetch.assert_not_called()
                    self.assertIn(name, str(caught.exception))

    def test_an_answer_that_is_not_what_is_expected_is_a_processor_error_and_sets_no_output(self):
        for text in ("", "not json", "[]", answer(element(), element()), "{}", answer({}),
                     answer(element(checksum="x"))):
            processor, _ = new_processor(PROVIDER, {})
            with self.subTest(text=text[:30]):
                with mock.patch.object(provider, "fetch_text", return_value=text):
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                self.assertIn("The Adoptium API answer:", str(caught.exception))
                for key in ("url", "version", "expected_sha256"):
                    self.assertNotIn(key, processor.env)

    def test_a_fetch_error_passes_through_and_sets_no_output(self):
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "fetch_text", side_effect=ProcessorError("down")):
            with self.assertRaises(ProcessorError):
                processor.main()
        for key in ("url", "version", "expected_sha256"):
            self.assertNotIn(key, processor.env)


class FetchTests(unittest.TestCase):
    URL = API_ADDRESS

    def fetch_with(self, body=None, error=None, status=200, url=None, max_bytes=1000):
        def opener(request):
            self.request = request
            if error is not None:
                raise error
            response = FakeResponse(body)
            response.status = status
            return response
        with mock.patch.object(provider, "open_request", side_effect=opener):
            return provider.fetch_text(url or self.URL, max_bytes, "the answer")

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
            for url in ("https://example.test/x", "http://api.adoptium.net/x", RELEASE_DOWNLOAD + "x"):
                with self.subTest(url=url):
                    with self.assertRaises(ProcessorError) as caught:
                        provider.fetch_text(url, 100, "the answer")
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
        self.assertEqual(provider.MAX_ANSWER_BYTES, 1024 * 1024)
        self.assertEqual(provider.FETCH_TIMEOUT_SECONDS, 120)

    def test_the_processor_asks_for_the_limit_it_declares(self):
        record = []
        run_on(read(EXCERPT), record=record)
        self.assertEqual(record[0][1:], (provider.MAX_ANSWER_BYTES, "The Adoptium API"))


class SourceTests(unittest.TestCase):
    def test_the_module_has_no_other_host_and_no_hash(self):
        text = read(os.path.join(RECIPE_DIR, "AdoptiumInfoProvider.py"))
        hosts = set(re.findall(r"https?://([A-Za-z0-9.-]+)", text))
        self.assertEqual(hosts, {"api.adoptium.net", "github.com"})
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", text))

    def test_the_module_never_reads_the_package_key(self):
        """The zip package is not an installer: the code must not look at it."""
        code = re.sub(r'""".*?"""', "", read(os.path.join(RECIPE_DIR, "AdoptiumInfoProvider.py")), flags=re.S)
        code = re.sub(r"#[^\n]*", "", code)
        self.assertNotIn('"package"', code)
        self.assertNotIn("'package'", code)


if __name__ == "__main__":
    unittest.main()
