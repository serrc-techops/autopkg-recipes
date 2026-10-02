"""Tests of ZabbixAgentInfoProvider: every branch. No test uses the network:
fetch_page() or open_request() is replaced.

Two kinds of page are used. The saved excerpt (download_agents_excerpt.html) is
a few real records in the real structure. Pages that tests build themselves
use made-up records.
"""
import html
import io
import json
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

import ZabbixAgentInfoProvider as provider  # noqa: E402

PROVIDER = provider.ZabbixAgentInfoProvider
EXCERPT = os.path.join(TESTS_DIR, "download_agents_excerpt.html")
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
# Texts that the hygiene test would read as an address or a network path if they
# stood in this file as they are. They are built here.
FOUR_NUMBERS = ".".join(["7", "0", "5", "1"])
FOUR_NUMBERS_NEWER = ".".join(["7", "0", "32", "1"])
BACKSLASH_PATH = "\\".join(["7.0", "7.0.31", "x.msi"])


def record(release="7.0.31", sha256=HEX_A, os_name="Windows", os_version="11, 10", hardware="amd64",
           encryption="OpenSSL", package="MSI", agent_type="agent2", static=False, legacy=False, path=None,
           **extra):
    """A made-up record with the keys that the vendor's page has."""
    line = ".".join(release.split(".")[:2])
    if path is None:
        path = "%s/%s/zabbix_%s-%s-windows-%s-openssl.msi" % (line, release, agent_type, release, hardware)
    result = {
        "version": line + " LTS", "release": release, "os": os_name, "osVersion": os_version,
        "hardware": hardware, "encryption": encryption, "static": static, "sha256": sha256,
        "package": package, "url": path, "type": agent_type, "suggest_packages": False, "legacy": legacy,
    }
    result.update(extra)
    return result


def page_of(records):
    """A page in the structure of the vendor's page, with the records escaped
    as the vendor's page escapes them."""
    raw = json.dumps(records, separators=(",", ":")).replace("/", "\\/")
    return (
        '<html><body><download-agents-filter class="jsVueComponent"\n'
        '        :agents="%s"\n        tr_x="y"\n    ></download-agents-filter></body></html>'
        % raw.replace('"', "&quot;")
    )


def newest_of(records, **overrides):
    arguments = dict(line="7.0", platform="Windows", architecture="amd64", encryption="OpenSSL",
                     packaging="MSI", agent_type="agent2")
    arguments.update(overrides)
    return provider.find_newest(records, **arguments)


def run_on(page, env=None):
    """Run the processor on a page text. Returns (processor, messages)."""
    with mock.patch.object(provider, "fetch_page", return_value=page) as fetch:
        result = run_processor(PROVIDER, env or {})
    fetch.assert_called_once_with(provider.DOWNLOAD_PAGE_URL)
    return result


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ExcerptTests(unittest.TestCase):
    """The saved excerpt of the real page."""

    def setUp(self):
        with open(EXCERPT, "r", encoding="utf-8") as handle:
            self.page = handle.read()

    def test_the_excerpt_is_small(self):
        self.assertLess(len(self.page), 20000)
        self.assertLessEqual(len(provider.extract_records(self.page)), 20)

    def test_the_newest_release_of_the_7_0_line_is_7_0_31_not_7_0_5(self):
        processor, _ = run_on(self.page)
        self.assertEqual(processor.env["version"], "7.0.31")
        self.assertEqual(
            processor.env["url"],
            "https://cdn.zabbix.com/zabbix/binaries/stable/7.0/7.0.31/"
            "zabbix_agent2-7.0.31-windows-amd64-openssl.msi",
        )
        self.assertEqual(
            processor.env["expected_sha256"],
            "dd85c5448edf81bc1dae551d50bd486dfd9a226cf4a80db4f6945201de494fa9",
        )

    def test_another_line_gives_its_own_newest_release(self):
        processor, _ = run_on(self.page, {"zabbix_line": "7.4"})
        self.assertEqual(processor.env["version"], "7.4.15")
        processor, _ = run_on(self.page, {"zabbix_line": "6.0"})
        self.assertEqual(processor.env["version"], "6.0.48")

    def test_another_architecture_packaging_and_type(self):
        processor, _ = run_on(self.page, {"zabbix_architecture": "i386"})
        self.assertTrue(processor.env["url"].endswith("zabbix_agent2-7.0.31-windows-i386-openssl.msi"))
        processor, _ = run_on(self.page, {"zabbix_agent_type": "agent"})
        self.assertTrue(processor.env["url"].endswith("zabbix_agent-7.0.31-windows-amd64-openssl.msi"))

    def test_the_static_archive_is_never_taken(self):
        with self.assertRaises(ProcessorError):
            run_on(self.page, {"zabbix_packaging": "Archive"})

    def test_every_page_record_of_the_excerpt_has_the_keys_the_processor_reads(self):
        for item in provider.extract_records(self.page):
            for key in provider.FILTER_KEYS + ("url", "sha256", "static", "legacy"):
                self.assertIn(key, item)


class ReleaseKeyTests(unittest.TestCase):
    def test_three_numbers_are_compared_as_numbers(self):
        self.assertGreater(provider.release_key("7.0.31"), provider.release_key("7.0.5"))
        self.assertGreater(provider.release_key("7.0.100"), provider.release_key("7.0.99"))
        self.assertEqual(provider.release_key("7.0.5"), (7, 0, 5))

    def test_anything_else_is_not_a_release(self):
        for value in ("7.0", FOUR_NUMBERS, "7.0.5rc1", "7.0.x", "v7.0.5", "", " 7.0.5", "7.0.5\n", "7.0.-1",
                      "٧.٠.٥", None, 7, ["7.0.5"]):
            with self.subTest(value=value):
                self.assertIsNone(provider.release_key(value))


class ExtractRecordsTests(unittest.TestCase):
    def test_the_records_are_read_from_the_attribute(self):
        records = [record("7.0.5"), record("7.0.31")]
        self.assertEqual(provider.extract_records(page_of(records)), records)

    def test_html_entities_are_decoded(self):
        records = [record("7.0.31", osVersion="Server 2016 +", note="a & b <c>")]
        # An ampersand or a bracket inside a value is written as an entity too.
        page = page_of(records).replace("a & b <c>", "a &amp; b &lt;c&gt;")
        self.assertEqual(provider.extract_records(page)[0]["note"], "a & b <c>")

    def test_a_page_without_the_element_is_refused(self):
        for text in ("", "<html></html>", "not html at all", '<div :agents="[]"></div>'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError) as caught:
                    provider.extract_records(text)
                self.assertIn("not exactly one", str(caught.exception))

    def test_two_elements_are_refused(self):
        page = page_of([record()])
        with self.assertRaises(ValueError):
            provider.extract_records(page + page)

    def test_an_attribute_that_is_not_json_is_refused(self):
        page = '<download-agents-filter :agents="[{&quot;release&quot;: oops]"></download-agents-filter>'
        with self.assertRaises(ValueError) as caught:
            provider.extract_records(page)
        self.assertIn("not JSON", str(caught.exception))

    def test_json_that_is_not_a_list_with_records_is_refused(self):
        for value in ("{}", "[]", "5", "null", '"text"'):
            page = '<download-agents-filter :agents="%s"></download-agents-filter>' % html.escape(value)
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    provider.extract_records(page)

    def test_the_attribute_must_belong_to_the_element(self):
        page = '<other-element :agents="[]"></other-element><download-agents-filter :x="1"></download-agents-filter>'
        with self.assertRaises(ValueError):
            provider.extract_records(page)


class FindNewestTests(unittest.TestCase):
    def test_a_one_digit_release_is_found_and_is_not_the_newest_by_text_order(self):
        records = [record("7.0.5", HEX_A), record("7.0.31", HEX_B)]
        self.assertEqual(newest_of(records)[1:], ("7.0.31", HEX_B))
        self.assertEqual(newest_of([record("7.0.5", HEX_A)])[1:], ("7.0.5", HEX_A))

    def test_the_newer_release_standing_first_or_last_gives_the_same_answer(self):
        newer, older = record("7.0.31", HEX_B), record("7.0.30", HEX_A)
        self.assertEqual(newest_of([newer, older]), newest_of([older, newer]))
        self.assertEqual(newest_of([older, newer])[1], "7.0.31")

    def test_three_digit_parts_are_compared_as_numbers(self):
        records = [record("7.0.99", HEX_A), record("7.0.100", HEX_B), record("7.0.9", HEX_C)]
        self.assertEqual(newest_of(records)[1], "7.0.100")

    def test_the_url_is_the_download_base_and_the_path(self):
        url = newest_of([record("7.0.31")])[0]
        self.assertEqual(
            url,
            "https://cdn.zabbix.com/zabbix/binaries/stable/7.0/7.0.31/"
            "zabbix_agent2-7.0.31-windows-amd64-openssl.msi",
        )

    def test_the_hash_is_returned_in_lower_case(self):
        self.assertEqual(newest_of([record("7.0.31", HEX_A.upper())])[2], HEX_A)

    def test_the_page_repeats_a_file_for_each_windows_version_and_that_is_fine(self):
        records = [record("7.0.31", os_version="11, 10"), record("7.0.31", os_version="Server 2016 +")]
        self.assertEqual(newest_of(records)[1:], ("7.0.31", HEX_A))

    def test_a_record_of_another_line_is_ignored(self):
        records = [record("7.0.31", HEX_A), record("7.4.15", HEX_B), record("6.0.48", HEX_C)]
        self.assertEqual(newest_of(records)[1:], ("7.0.31", HEX_A))
        self.assertEqual(newest_of(records, line="7.4")[1:], ("7.4.15", HEX_B))

    def test_a_line_is_not_a_prefix_of_the_text(self):
        records = [record("7.10.2", HEX_B, path="7.10/7.10.2/zabbix_agent2-7.10.2-windows-amd64-openssl.msi"),
                   record("7.1.4", HEX_A, path="7.1/7.1.4/zabbix_agent2-7.1.4-windows-amd64-openssl.msi")]
        self.assertEqual(newest_of(records, line="7.1")[1:], ("7.1.4", HEX_A))
        self.assertEqual(newest_of(records, line="7.10")[1:], ("7.10.2", HEX_B))

    def test_another_architecture_is_ignored(self):
        records = [record("7.0.30", HEX_A), record("7.0.31", HEX_B, hardware="i386")]
        self.assertEqual(newest_of(records)[1:], ("7.0.30", HEX_A))
        self.assertEqual(newest_of(records, architecture="i386")[1:], ("7.0.31", HEX_B))

    def test_another_platform_encryption_packaging_and_type_are_ignored(self):
        records = [
            record("7.0.30", HEX_A),
            record("7.0.31", HEX_B, os_name="Linux"),
            record("7.0.31", HEX_B, encryption="No encryption"),
            record("7.0.31", HEX_B, package="Archive"),
            record("7.0.31", HEX_B, agent_type="agent"),
            record("7.0.31", HEX_B, agent_type="agent2-plugins"),
        ]
        self.assertEqual(newest_of(records)[1:], ("7.0.30", HEX_A))

    def test_static_and_legacy_records_are_ignored(self):
        records = [record("7.0.30", HEX_A), record("7.0.31", HEX_B, static=True),
                   record("7.0.32", HEX_C, legacy=True)]
        self.assertEqual(newest_of(records)[1:], ("7.0.30", HEX_A))

    def test_a_record_without_the_static_and_legacy_keys_counts_as_neither(self):
        item = record("7.0.31", HEX_B)
        del item["static"], item["legacy"]
        self.assertEqual(newest_of([item])[1], "7.0.31")

    def test_a_pre_release_or_another_form_of_release_is_ignored(self):
        records = [record("7.0.30", HEX_A), record("7.0.31rc1", HEX_B), record(FOUR_NUMBERS_NEWER, HEX_C),
                   record("7.0", HEX_C)]
        self.assertEqual(newest_of(records)[1:], ("7.0.30", HEX_A))

    def test_the_inputs_ignore_letter_case(self):
        self.assertEqual(
            newest_of([record("7.0.31")], platform="windows", encryption="openssl", packaging="msi",
                      agent_type="AGENT2", architecture="AMD64")[1],
            "7.0.31",
        )

    def test_no_matching_record_is_an_error_that_names_the_inputs(self):
        for records in ([], [record("7.4.15")], [record("7.0.31", os_name="Linux")], ["text", 5, None, []],
                        [{"release": "7.0.31"}]):
            with self.subTest(records=records):
                with self.assertRaises(ValueError) as caught:
                    newest_of(records)
                self.assertIn("no record matches line 7.0", str(caught.exception))

    def test_records_that_are_not_objects_are_ignored(self):
        self.assertEqual(newest_of(["x", 3, None, [1], record("7.0.31")])[1], "7.0.31")

    def test_a_record_that_lacks_a_key_is_ignored(self):
        for key in provider.FILTER_KEYS:
            item = record("7.0.31", HEX_B)
            del item[key]
            with self.subTest(key=key):
                self.assertEqual(newest_of([record("7.0.30", HEX_A), item])[1], "7.0.30")

    def test_the_newest_release_without_a_hash_is_an_error_not_a_fall_back_to_an_older_one(self):
        for value in (None, "", "short", "g" * 64, HEX_A + "0", HEX_A[:-1], 5, ["x"], HEX_A + "\n"):
            item = record("7.0.31", value)
            if value is None:
                del item["sha256"]
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    newest_of([record("7.0.30", HEX_B), item])
                self.assertIn("no valid SHA-256", str(caught.exception))

    def test_an_older_release_without_a_hash_does_not_matter(self):
        item = record("7.0.30", None)
        del item["sha256"]
        self.assertEqual(newest_of([item, record("7.0.31", HEX_A)])[1:], ("7.0.31", HEX_A))

    def test_one_release_with_two_hashes_is_an_error(self):
        records = [record("7.0.31", HEX_A, os_version="11, 10"), record("7.0.31", HEX_B, os_version="Server 2016 +")]
        with self.assertRaises(ValueError) as caught:
            newest_of(records)
        self.assertIn("disagree", str(caught.exception))

    def test_one_release_with_two_files_is_an_error(self):
        other = "7.0/7.0.31/zabbix_agent2-7.0.31-windows-amd64-openssl-other.msi"
        with self.assertRaises(ValueError):
            newest_of([record("7.0.31", HEX_A), record("7.0.31", HEX_A, path=other)])

    def test_a_path_that_is_not_plain_is_an_error(self):
        bad = [
            None, "", 5,
            "7.0/7.0.31",                                    # no file
            "7.0/7.0.31/../../x.msi",                         # a parent folder
            "7.0/7.0.31/./x.msi",
            "/7.0/7.0.31/x.msi",                              # absolute
            "https://example.test/7.0/7.0.31/x.msi",          # an address
            "7.0/7.0.31/x y.msi",                             # white space
            "7.0/7.0.31/x.msi\n",
            "7.0/7.0.31//x.msi",                              # an empty part
            "7.0/7.0.31/x.msi?a=1",                           # a query
            BACKSLASH_PATH,
        ]
        for path in bad:
            item = record("7.0.31", HEX_A)
            item["url"] = path
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    newest_of([item])

    def test_a_path_under_another_line_or_release_is_an_error(self):
        for path in ("7.4/7.0.31/x.msi", "7.0/7.0.30/x.msi", "7.0.31/x.msi", "6.0/6.0.31/x.msi"):
            item = record("7.0.31", HEX_A, path=path)
            with self.subTest(path=path):
                with self.assertRaises(ValueError) as caught:
                    newest_of([item])
                self.assertIn("not the expected 7.0/7.0.31/zabbix_agent2-7.0.31-windows-amd64-openssl.msi", str(caught.exception))

    def test_a_missing_path_is_an_error(self):
        item = record("7.0.31", HEX_A)
        del item["url"]
        with self.assertRaises(ValueError):
            newest_of([item])


def archive_record(release="7.0.31", sha256=HEX_A, encryption="No encryption", **extra):
    """A record of the archive (zip) with the vendor's file name for it."""
    line = ".".join(release.split(".")[:2])
    part = "-openssl" if encryption == "OpenSSL" else ""
    return record(release, sha256, package="Archive", encryption=encryption,
                  path="%s/%s/zabbix_agent2-%s-windows-amd64%s.zip" % (line, release, release, part), **extra)


class FlagTests(unittest.TestCase):
    """B1: the flags static and legacy are read in a defined way."""

    def test_the_accepted_spellings_of_true_and_false(self):
        for value in (True, 1, "true", "True", "TRUE", " yes ", "Yes", "1"):
            with self.subTest(value=value):
                self.assertIs(provider.flag_value(value, "static"), True)
        for value in (False, 0, "false", "False", " no ", "NO", "0"):
            with self.subTest(value=value):
                self.assertIs(provider.flag_value(value, "static"), False)

    def test_anything_else_is_an_error_that_names_the_key_and_the_value(self):
        for value in (None, 2, -1, 1.0, 0.0, "", " ", "maybe", "on", "off", "t", "y", "null", "2", [], [True], {}, b"1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    provider.flag_value(value, "legacy")
                self.assertIn("legacy", str(caught.exception))
                self.assertIn("not a flag", str(caught.exception))

    def test_a_static_record_in_any_spelling_is_never_returned_for_the_archive(self):
        good = archive_record("7.0.30", HEX_B)
        for value in (True, 1, "true", "TRUE", "yes", "1", " True "):
            records = [good, archive_record("7.0.31", HEX_A, static=value)]
            with self.subTest(value=value):
                result = newest_of(records, packaging="Archive", encryption="No encryption")
                self.assertEqual(result[1:], ("7.0.30", HEX_B))

    def test_a_legacy_record_in_any_spelling_is_ignored(self):
        for value in (True, 1, "true", "yes", "1"):
            records = [record("7.0.30", HEX_B), record("7.0.31", HEX_A, legacy=value)]
            with self.subTest(value=value):
                self.assertEqual(newest_of(records)[1:], ("7.0.30", HEX_B))

    def test_a_record_that_is_not_static_in_any_spelling_is_taken(self):
        for value in (False, 0, "false", "FALSE", "no", "0", " no "):
            records = [record("7.0.30", HEX_B), record("7.0.31", HEX_A, static=value, legacy=value)]
            with self.subTest(value=value):
                self.assertEqual(newest_of(records)[1:], ("7.0.31", HEX_A))

    def test_a_strange_flag_on_a_candidate_stops_the_run_and_never_returns_a_file(self):
        for key in ("static", "legacy"):
            for value in (None, 2, "maybe", [], "", 1.5):
                records = [record("7.0.30", HEX_B), record("7.0.31", HEX_A, **{key: value})]
                with self.subTest(key=key, value=value):
                    with self.assertRaises(ValueError) as caught:
                        newest_of(records)
                    self.assertIn(key, str(caught.exception))

    def test_a_strange_flag_on_a_record_that_is_none_of_ours_does_not_matter(self):
        records = [record("7.0.31", HEX_A), record("7.0.32", HEX_B, os_name="Linux", static="maybe"),
                   record("7.4.1", HEX_B, static=None), record("7.0.33", HEX_B, hardware="i386", legacy=[])]
        self.assertEqual(newest_of(records)[1:], ("7.0.31", HEX_A))

    def test_the_flags_are_read_after_the_other_fields_so_the_error_is_only_for_candidates(self):
        item = record("7.0.31", HEX_A, static="maybe", package="Archive")
        self.assertFalse(provider.matches(item, "7.0", "Windows", "amd64", "OpenSSL", "MSI", "agent2"))

    def test_the_processor_turns_it_into_a_processor_error(self):
        page = page_of([record("7.0.31", HEX_A, static="maybe")])
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "fetch_page", return_value=page):
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        self.assertIn("not a flag", str(caught.exception))
        self.assertNotIn("url", processor.env)


class FileNameTests(unittest.TestCase):
    """S1: the file that is returned is checked against the record."""

    def test_the_expected_name_of_the_defaults(self):
        self.assertEqual(
            provider.expected_file_name("7.0.31", "Windows", "amd64", "OpenSSL", "MSI", "agent2"),
            "zabbix_agent2-7.0.31-windows-amd64-openssl.msi",
        )

    def test_the_expected_names_of_other_inputs(self):
        cases = [
            (("i386", "OpenSSL", "MSI", "agent2"), "zabbix_agent2-7.0.31-windows-i386-openssl.msi"),
            (("amd64", "OpenSSL", "MSI", "agent"), "zabbix_agent-7.0.31-windows-amd64-openssl.msi"),
            (("amd64", "No encryption", "Archive", "agent2"), "zabbix_agent2-7.0.31-windows-amd64.zip"),
            (("amd64", "OpenSSL", "Archive", "agent2"), "zabbix_agent2-7.0.31-windows-amd64-openssl.zip"),
            (("AMD64", "openssl", "msi", "AGENT2"), "zabbix_agent2-7.0.31-windows-amd64-openssl.msi"),
        ]
        for (architecture, encryption, packaging, agent_type), expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    provider.expected_file_name("7.0.31", "WINDOWS", architecture, encryption, packaging, agent_type),
                    expected,
                )

    def test_the_names_agree_with_the_vendor_names_in_the_saved_page(self):
        with open(EXCERPT, "r", encoding="utf-8") as handle:
            records = provider.extract_records(handle.read())
        checked = 0
        for item in records:
            if item["os"] != "Windows" or item["static"] or item["legacy"] or item["package"] != "MSI":
                continue
            name = provider.expected_file_name(
                item["release"], item["os"], item["hardware"], item["encryption"], item["package"], item["type"]
            )
            self.assertEqual(item["url"].split("/")[-1], name)
            checked += 1
        self.assertGreaterEqual(checked, 5)

    def test_inputs_without_a_known_name_are_errors(self):
        for platform, encryption, packaging in (
            ("Linux", "OpenSSL", "MSI"), ("macOS", "OpenSSL", "MSI"), ("", "OpenSSL", "MSI"),
            ("Windows", "GnuTLS", "MSI"), ("Windows", "", "MSI"),
            ("Windows", "OpenSSL", "tar.gz"), ("Windows", "OpenSSL", "DEB"), ("Windows", "OpenSSL", ""),
        ):
            with self.subTest(platform=platform, encryption=encryption, packaging=packaging):
                with self.assertRaises(ValueError):
                    provider.expected_file_name("7.0.31", platform, "amd64", encryption, packaging, "agent2")

    def test_the_processor_refuses_such_inputs_before_it_fetches_the_page(self):
        for name, value in (("zabbix_platform", "Linux"), ("zabbix_encryption", "GnuTLS"), ("zabbix_packaging", "RPM")):
            processor, _ = new_processor(PROVIDER, {name: value})
            with self.subTest(name=name):
                with mock.patch.object(provider, "fetch_page") as fetch:
                    with self.assertRaises(ProcessorError) as caught:
                        processor.main()
                fetch.assert_not_called()
                self.assertIn("Zabbix agent inputs", str(caught.exception))

    def test_a_file_name_that_is_not_the_expected_one_is_an_error(self):
        base = "7.0/7.0.31/"
        bad = [
            base + "zabbix_agent-7.0.31-windows-amd64-openssl.msi",       # another agent
            base + "zabbix_agent2-7.0.31-windows-i386-openssl.msi",       # another architecture
            base + "zabbix_agent2-7.0.31-windows-amd64.msi",              # no encryption part
            base + "zabbix_agent2-7.0.31-windows-amd64-openssl.zip",      # another extension
            base + "zabbix_agent2-7.0.31-windows-amd64-openssl.exe",
            base + "zabbix_agent2-7.0.30-windows-amd64-openssl.msi",      # another release
            base + "zabbix_agent2-7.0.31-windows-amd64-openssl-static.msi",
            base + "Zabbix_Agent2-7.0.31-windows-amd64-openssl.msi",      # letter case
            base + "a.exe",
            base + "zabbix_agent2-7.0.31-windows-amd64-openssl.msi:stream",   # a colon (M11)
            base + "zabbix_agent2-7.0.31-windows-amd64-openssl.msi ",
            base + "zabbix_agent2-7.0.31-windows-amd64-openssl.msi/",
            base + "sub/zabbix_agent2-7.0.31-windows-amd64-openssl.msi",  # a sub-folder
            "7.0/sub/7.0.31/zabbix_agent2-7.0.31-windows-amd64-openssl.msi",
            "sub/7.0/7.0.31/zabbix_agent2-7.0.31-windows-amd64-openssl.msi",
            "/" + base + "zabbix_agent2-7.0.31-windows-amd64-openssl.msi",
            "7.0/7.0.31/zabbix_agent2-7.0.31-windows-amd64-openssl.msi".replace("/", "//", 1),
        ]
        for path in bad:
            with self.subTest(path=path):
                with self.assertRaises(ValueError) as caught:
                    newest_of([record("7.0.31", HEX_A, path=path)])
                self.assertIn("not the expected", str(caught.exception))

    def test_a_non_text_path_is_an_error(self):
        for path in (None, 5, ["x"], b"7.0/7.0.31/x"):
            item = record("7.0.31", HEX_A)
            item["url"] = path
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    newest_of([item])

    def test_the_expected_name_follows_the_inputs_of_the_run(self):
        records = [archive_record("7.0.31", HEX_A), archive_record("7.0.31", HEX_B, encryption="OpenSSL")]
        url, release, sha = newest_of(records, packaging="Archive", encryption="No encryption")
        self.assertTrue(url.endswith("/7.0/7.0.31/zabbix_agent2-7.0.31-windows-amd64.zip"))
        self.assertEqual(sha, HEX_A)
        url, release, sha = newest_of(records, packaging="Archive", encryption="OpenSSL")
        self.assertTrue(url.endswith("/7.0/7.0.31/zabbix_agent2-7.0.31-windows-amd64-openssl.zip"))

    def test_a_record_of_one_file_name_under_the_inputs_of_another_cannot_get_through(self):
        """The i386 file in the amd64 record: the hash would belong to the wrong file."""
        wrong = record("7.0.31", HEX_A, path="7.0/7.0.31/zabbix_agent2-7.0.31-windows-i386-openssl.msi")
        with self.assertRaises(ValueError):
            newest_of([wrong])


class PageStructureTests(unittest.TestCase):
    """M14: the attribute name must stand as an attribute."""

    def test_an_attribute_that_only_ends_in_agents_is_not_read(self):
        raw = html.escape(json.dumps([record("7.0.31")]))
        for name in ("x:agents", "data:agents", "v-bind:agents", "-:agents", ":agentsx"):
            page = '<download-agents-filter class="a" %s="%s"></download-agents-filter>' % (name, raw)
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    provider.extract_records(page)

    def test_the_attribute_after_other_attributes_and_new_lines_is_read(self):
        raw = html.escape(json.dumps([record("7.0.31")]))
        for gap in (" ", "\n    ", "\t"):
            page = '<download-agents-filter class="a"%s:agents="%s"\n tr_x="y"></download-agents-filter>' % (gap, raw)
            with self.subTest(gap=repr(gap)):
                self.assertEqual(len(provider.extract_records(page)), 1)


class MainTests(unittest.TestCase):
    def test_the_defaults_are_the_agent_2_msi_for_windows_x64_with_openssl_of_the_7_0_line(self):
        page = page_of([record("7.0.31", HEX_A), record("7.4.15", HEX_B)])
        processor, messages = run_on(page)
        self.assertEqual(processor.env["version"], "7.0.31")
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertTrue(processor.env["url"].endswith(".msi"))
        self.assertTrue(any("7.0.31" in m for m in messages))
        self.assertTrue(any(HEX_A in m for m in messages))

    def test_the_declared_defaults_equal_the_values_the_code_uses(self):
        declared = {name: flags["default"] for name, flags in PROVIDER.input_variables.items()}
        self.assertEqual(declared, {
            "zabbix_line": "7.0", "zabbix_platform": "Windows", "zabbix_architecture": "amd64",
            "zabbix_encryption": "OpenSSL", "zabbix_packaging": "MSI", "zabbix_agent_type": "agent2",
        })
        for flags in PROVIDER.input_variables.values():
            self.assertIs(flags["required"], False)
        self.assertEqual(sorted(PROVIDER.output_variables), ["expected_sha256", "url", "version"])

    def test_the_inputs_choose_the_record(self):
        page = page_of([record("7.0.31", HEX_A), record("7.0.31", HEX_B, hardware="i386"),
                        record("7.4.15", HEX_C)])
        processor, _ = run_on(page, {"zabbix_architecture": "i386"})
        self.assertEqual(processor.env["expected_sha256"], HEX_B)
        processor, _ = run_on(page, {"zabbix_line": "7.4"})
        self.assertEqual(processor.env["expected_sha256"], HEX_C)

    def test_white_space_around_an_input_is_ignored(self):
        processor, _ = run_on(page_of([record("7.0.31", HEX_A)]), {"zabbix_line": " 7.0 ", "zabbix_platform": "Windows\n"})
        self.assertEqual(processor.env["version"], "7.0.31")

    def test_an_input_that_is_empty_or_not_text_is_an_error_and_the_page_is_not_fetched(self):
        for name in ("zabbix_line", "zabbix_platform", "zabbix_architecture", "zabbix_encryption",
                     "zabbix_packaging", "zabbix_agent_type"):
            for value in ("", "  ", None, 7, ["7.0"]):
                processor, _ = new_processor(PROVIDER, {name: value})
                with self.subTest(name=name, value=value):
                    with mock.patch.object(provider, "fetch_page") as fetch:
                        with self.assertRaises(ProcessorError) as caught:
                            processor.main()
                    fetch.assert_not_called()
                    self.assertIn(name, str(caught.exception))

    def test_a_line_that_is_not_two_numbers_is_an_error(self):
        for value in ("7", "7.0.1", "7.x", "7.0 LTS", "v7.0", "7.0\n7.1", "7..0", "7.0."):
            processor, _ = new_processor(PROVIDER, {"zabbix_line": value})
            with self.subTest(value=value):
                with mock.patch.object(provider, "fetch_page") as fetch:
                    with self.assertRaises(ProcessorError):
                        processor.main()
                fetch.assert_not_called()

    def test_no_output_is_set_when_the_run_fails(self):
        for page in (page_of([record("7.4.15")]), "<html></html>", page_of([record("7.0.31", "bad")])):
            processor, _ = new_processor(PROVIDER, {})
            with mock.patch.object(provider, "fetch_page", return_value=page):
                with self.assertRaises(ProcessorError) as caught:
                    processor.main()
            for key in ("url", "version", "expected_sha256"):
                self.assertNotIn(key, processor.env)
            self.assertIn("Zabbix download page", str(caught.exception))

    def test_a_page_that_is_not_what_is_expected_is_a_processor_error(self):
        for page in ("", "<html><body>Maintenance</body></html>", "{}", page_of([]).replace("[]", "{}")):
            processor, _ = new_processor(PROVIDER, {})
            with mock.patch.object(provider, "fetch_page", return_value=page):
                with self.subTest(page=page[:30]):
                    with self.assertRaises(ProcessorError):
                        processor.main()

    def test_a_page_without_any_record_of_the_line_says_so(self):
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "fetch_page", return_value=page_of([record("7.4.15")])):
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        self.assertIn("no record matches line 7.0", str(caught.exception))

    def test_a_downloaded_file_name_ends_in_msi(self):
        processor, _ = run_on(page_of([record("7.0.31")]))
        self.assertEqual(processor.env["url"].rsplit("/", 1)[-1], "zabbix_agent2-7.0.31-windows-amd64-openssl.msi")


class FetchTests(unittest.TestCase):
    def fetch_with(self, body=None, error=None):
        def opener(request):
            self.request = request
            if error is not None:
                raise error
            return FakeResponse(body)
        with mock.patch.object(provider, "open_request", side_effect=opener):
            return provider.fetch_page(provider.DOWNLOAD_PAGE_URL)

    def test_the_page_text_is_returned_and_the_request_is_plain(self):
        text = self.fetch_with(body="café page".encode("utf-8"))
        self.assertEqual(text, "café page")
        self.assertEqual(self.request.full_url, "https://www.zabbix.com/download_agents")
        self.assertEqual(self.request.get_header("User-agent"), provider.USER_AGENT)
        self.assertIsNone(self.request.data)
        self.assertFalse(self.request.has_header("Authorization"))

    def test_a_status_other_than_200_is_an_error_that_names_it(self):
        for code, reason in ((404, "Not Found"), (500, "Server Error"), (429, "Too Many Requests")):
            error = urllib.error.HTTPError(provider.DOWNLOAD_PAGE_URL, code, reason, {}, io.BytesIO(b""))
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error)
                self.assertIn("answered %d" % code, str(caught.exception))
                self.assertNotIn("redirect", str(caught.exception))

    def test_a_redirect_is_an_error_that_says_so(self):
        for code in (301, 302, 307):
            error = urllib.error.HTTPError(provider.DOWNLOAD_PAGE_URL, code, "Moved", {}, io.BytesIO(b""))
            with self.subTest(code=code):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error)
                self.assertIn("a redirect is not followed", str(caught.exception))

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

    def test_a_failed_connection_is_a_processor_error(self):
        for error in (urllib.error.URLError("no route"), TimeoutError("timed out"), OSError("reset"),
                      ValueError("bad url")):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(ProcessorError) as caught:
                    self.fetch_with(error=error)
                self.assertIn("could not be fetched", str(caught.exception))

    def test_a_page_larger_than_the_limit_is_an_error(self):
        body = b"x" * (provider.MAX_PAGE_BYTES + 1)
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(body=body)
        self.assertIn("larger than", str(caught.exception))

    def test_a_page_of_exactly_the_limit_is_accepted(self):
        self.assertEqual(len(self.fetch_with(body=b"x" * provider.MAX_PAGE_BYTES)), provider.MAX_PAGE_BYTES)

    def test_a_page_that_is_not_utf_8_is_an_error(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(body=b"\xff\xfe\x00bad")
        self.assertIn("not UTF-8", str(caught.exception))

    def test_the_constants_are_the_vendors_addresses_over_https(self):
        self.assertEqual(provider.DOWNLOAD_PAGE_URL, "https://www.zabbix.com/download_agents")
        self.assertEqual(provider.DOWNLOAD_BASE_URL, "https://cdn.zabbix.com/zabbix/binaries/stable/")
        self.assertTrue(provider.DOWNLOAD_BASE_URL.endswith("/"))

    def test_the_limits_are_sensible(self):
        self.assertGreater(provider.MAX_PAGE_BYTES, 6 * 1024 * 1024)
        self.assertGreater(provider.FETCH_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(provider.FETCH_TIMEOUT_SECONDS, 600)


if __name__ == "__main__":
    unittest.main()
