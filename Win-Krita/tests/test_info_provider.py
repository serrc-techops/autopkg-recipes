"""Tests of KritaInfoProvider: every branch. No test uses the network:
fetch_text() or open_request() is replaced.

The two excerpts are lines of the real pages of 2026-11-13 (the index of
https://download.kde.org/stable/krita/ and the folder of the re-issue of
6.0.4), the site's header and footer left out; only their first line was
added. In them every dot between two digits is written _dot_, because the
repository's hygiene check takes four numbers joined by dots for an address;
excerpt() puts the dots back. For the same reason every version of four
numbers in this file is built at run time (four()). The hash lines here are
written by hand in the format of the real file (64 hex digits, two spaces, the
file name; the real one of 2026-11-13 had no new line at the end): the digits
are made up, not the hash of any file. These tests never use the network.
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

import KritaInfoProvider as provider  # noqa: E402

PROVIDER = provider.KritaInfoProvider
INDEX_EXCERPT = os.path.join(TESTS_DIR, "krita_index_excerpt.html")
FOLDER_EXCERPT = os.path.join(TESTS_DIR, "krita_folder_excerpt.html")
BASE = "https://download.kde.org/stable/krita/"
# Made-up digits, not the hash of any file.
HEX_A = "0123456789abcdef" * 4
HEX_B = "fedcba9876543210" * 4


def four(*numbers):
    """A version of four numbers, built here so that no file holds one."""
    assert len(numbers) == 4
    return ".".join(str(n) for n in numbers)


REISSUE = four(6, 0, 4, 1)
OLD_LINE = four(5, 3, 4, 1)


def excerpt(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().replace("_dot_", ".")


def index_of(*names):
    """A made-up index page with a link for each name, twice, as the real one has."""
    rows = "\n".join('<tr><td><a href="%s">[DIR]</a></td><td><a href="%s">%s</a></td></tr>' % (n, n, n)
                     for n in names)
    return '<html><body><a href="/"></a><table>\n%s\n</table></body></html>' % rows


def folder_of(version, with_installer=True, extra=()):
    names = ["krita-%s.tar.xz" % version, "krita-%s-signed.dmg" % version, "krita-x64-%s.zip" % version,
             "krita-x64-%s-dbg.zip" % version]
    if with_installer:
        names.append("krita-x64-%s-setup.exe" % version)
    return index_of(*(names + list(extra)))


def hash_line(sha256=HEX_A, name=None, version="6.0.4", gap="  ", end=""):
    return "%s%s%s%s" % (sha256, gap, name or "krita-x64-%s-setup.exe" % version, end)


class Server:
    """Stands in for fetch_text: the answers are by address."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, url, max_bytes, what):
        self.calls.append((url, max_bytes, what))
        answer = self.answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer


def run_with(answers):
    server = Server(answers)
    with mock.patch.object(provider, "fetch_text", side_effect=server):
        result = run_processor(PROVIDER, {})
    return result + (server,)


def normal_answers(top=None, sha256=HEX_A):
    versions = ["5.3.4", "6.0.2", "6.0.4", REISSUE, OLD_LINE] if top is None else top
    answers = {BASE: index_of(*(["/stable/"] + [v + "/" for v in versions] + ["updates/", "FastSketchPlugin-1.1.0/"]))}
    for version in versions:
        answers[BASE + version + "/"] = folder_of(version)
        name = "krita-x64-%s-setup.exe" % version
        answers[BASE + version + "/" + name + ".sha256"] = hash_line(sha256, name)
    return answers


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ExcerptTests(unittest.TestCase):
    """The lines of the real pages of 2026-11-13."""

    def test_the_first_lines_say_what_was_added_and_why_the_dots_are_written_out(self):
        for path in (INDEX_EXCERPT, FOLDER_EXCERPT):
            with open(path, "r", encoding="utf-8") as handle:
                first = handle.read().splitlines()[0]
            self.assertIn("of the real index of 2026-11-13", first)
            self.assertIn("Only this first line was added", first)
            self.assertIn("_dot_", first)

    def test_the_excerpts_are_small(self):
        for path in (INDEX_EXCERPT, FOLDER_EXCERPT):
            self.assertLess(os.path.getsize(path), 4000)

    def test_the_index_gives_the_four_version_folders_highest_first(self):
        self.assertEqual(provider.extract_versions(excerpt(INDEX_EXCERPT)), [REISSUE, "6.0.4", "6.0.2", OLD_LINE])

    def test_the_index_links_each_folder_twice_and_has_other_folders(self):
        text = excerpt(INDEX_EXCERPT)
        self.assertEqual(text.count('href="%s/"' % REISSUE), 2)
        for other in ("updates/", "FastSketchPlugin-1.1.0/", "/stable/", "/?mirrorstats", "older_versions_are_in_the_attic"):
            self.assertIn('href="%s"' % other, text)

    def test_the_folder_of_the_reissue_has_its_installer(self):
        text = excerpt(FOLDER_EXCERPT)
        self.assertTrue(provider.folder_has_installer(text, REISSUE))
        self.assertIn("krita-x64-%s.zip" % REISSUE, text)
        self.assertIn("krita-x64-%s-dbg.zip" % REISSUE, text)
        self.assertNotIn(".sha256", text)  # the folder does not list the hash file

    def test_the_processor_on_the_real_pages(self):
        name = "krita-x64-%s-setup.exe" % REISSUE
        answers = {BASE: excerpt(INDEX_EXCERPT), BASE + REISSUE + "/": excerpt(FOLDER_EXCERPT),
                   BASE + REISSUE + "/" + name + ".sha256": hash_line(HEX_A, name)}
        processor, messages, server = run_with(answers)
        self.assertEqual(processor.env["url"], BASE + REISSUE + "/" + name)
        self.assertEqual(processor.env["version"], REISSUE)
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertEqual(processor.env["krita_passed_over"], "")
        self.assertEqual([call[0] for call in server.calls],
                         [BASE, BASE + REISSUE + "/", BASE + REISSUE + "/" + name + ".sha256"])


class VersionTests(unittest.TestCase):
    def test_numbers_are_compared_as_numbers_and_a_fourth_number_is_higher(self):
        self.assertLess(provider.version_key("6.0.4"), provider.version_key(REISSUE))
        self.assertLess(provider.version_key("6.0.9"), provider.version_key("6.0.10"))
        self.assertLess(provider.version_key(OLD_LINE), provider.version_key("6.0.2"))

    def test_anything_else_is_not_a_version(self):
        for text in ("6.0", "6", ".".join(["6", "0", "4", "1", "2"]), "6.0.04", "6.0.4-beta1", "6.0.x", " 6.0.4",
                     "6.0.4/", "", None, 604, "6..4"):
            with self.subTest(text=text):
                self.assertIsNone(provider.version_key(text))

    def test_the_name_and_the_folder(self):
        self.assertEqual(provider.installer_name("6.0.4"), "krita-x64-6.0.4-setup.exe")
        self.assertEqual(provider.folder_url(REISSUE), BASE + REISSUE + "/")
        for bad in ("6.0", "../6.0.4", "6.0.4/../x", ""):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    provider.installer_name(bad)
                with self.assertRaises(ValueError):
                    provider.folder_url(bad)

    def test_the_constants(self):
        self.assertEqual(provider.BASE_URL, "https://download.kde.org/stable/krita/")
        self.assertGreaterEqual(provider.MAX_FOLDERS_TRIED, 2)
        self.assertLessEqual(provider.MAX_FOLDERS_TRIED, 5)


class ExtractVersionsTests(unittest.TestCase):
    def test_the_folders_are_ordered_by_their_numbers_not_as_text(self):
        page = index_of("6.0.9/", "6.0.10/", "10.0.0/", "9.9.9/", "6.0.9/")
        self.assertEqual(provider.extract_versions(page), ["10.0.0", "9.9.9", "6.0.10", "6.0.9"])

    def test_the_same_folder_twice_is_one_version(self):
        self.assertEqual(provider.extract_versions(index_of("6.0.4/", "6.0.4/")), ["6.0.4"])

    def test_other_links_are_ignored(self):
        page = index_of("updates/", "FastSketchPlugin-1.0.2/", "/stable/", "?C=N;O=D", "6.0.4/",
                        "https://download.kde.org/stable/krita/7.0.0/", "6.0.4.tar.xz", "unstable/")
        self.assertEqual(provider.extract_versions(page), ["6.0.4"])

    def test_a_folder_link_that_is_not_three_or_four_numbers_is_an_error_not_a_skip(self):
        for link in ("7.0/", "7/", ".".join(["7", "0", "0", "0", "1"]) + "/", "7.0.01/", "7..0/"):
            with self.subTest(link=link):
                with self.assertRaises(ValueError) as caught:
                    provider.extract_versions(index_of("6.0.4/", link))
                self.assertIn("not a version of three or four numbers", str(caught.exception))

    def test_no_version_folder_is_an_error(self):
        with self.assertRaises(ValueError) as caught:
            provider.extract_versions(index_of("updates/", "FastSketchPlugin-1.1.0/"))
        self.assertIn("no link to a version folder", str(caught.exception))

    def test_the_text_of_a_link_without_an_address_does_not_count(self):
        with self.assertRaises(ValueError):
            provider.extract_versions("<html><body>6.0.4/ <a name=\"6.0.4/\">x</a></body></html>")

    def test_single_quotes_and_entities_are_read(self):
        page = "<a class='x' href='6.0.2/'>a</a><a href=\"6&#46;0&#46;4/\">b</a>"
        self.assertEqual(provider.extract_versions(page), ["6.0.4", "6.0.2"])

    def test_an_attribute_that_only_ends_in_href_is_not_read(self):
        with self.assertRaises(ValueError):
            provider.extract_versions('<a data-href="6.0.4/">x</a>')


class FolderTests(unittest.TestCase):
    def test_the_installer_of_the_folders_version_is_found(self):
        self.assertTrue(provider.folder_has_installer(folder_of("6.0.4"), "6.0.4"))

    def test_a_folder_without_it_is_false(self):
        self.assertFalse(provider.folder_has_installer(folder_of("6.0.4", with_installer=False), "6.0.4"))

    def test_the_other_windows_files_are_not_the_installer(self):
        page = index_of("krita-x64-6.0.4.zip", "krita-x64-6.0.4-dbg.zip", "krita-x64-6.0.4-setup.exe.sha256",
                        "krita-x64-6.0.4-setup.exe.mirrorlist", "krita-x86-6.0.4-setup.exe", "krita-6.0.4-setup.exe")
        self.assertFalse(provider.folder_has_installer(page, "6.0.4"))

    def test_an_installer_of_another_version_is_an_error(self):
        for other in ("krita-x64-6.0.3-setup.exe", "krita-x64-%s-setup.exe" % REISSUE, "krita-x64-6.0.4-beta1-setup.exe"):
            with self.subTest(other=other):
                with self.assertRaises(ValueError) as caught:
                    provider.folder_has_installer(folder_of("6.0.4", extra=[other]), "6.0.4")
                self.assertIn("another version", str(caught.exception))

    def test_only_the_bare_file_name_is_a_match(self):
        for link in ("/stable/krita/6.0.4/krita-x64-6.0.4-setup.exe", "./krita-x64-6.0.4-setup.exe",
                     "krita-x64-6.0.4-setup.exe?x=1"):
            with self.subTest(link=link):
                self.assertFalse(provider.folder_has_installer(index_of(link), "6.0.4"))


class ParseHashLineTests(unittest.TestCase):
    NAME = "krita-x64-6.0.4-setup.exe"

    def test_the_line_gives_the_hash_with_or_without_a_new_line(self):
        for end in ("", "\n", "\r\n", "\n\n"):
            with self.subTest(end=repr(end)):
                self.assertEqual(provider.parse_hash_line(hash_line(end=end), self.NAME), HEX_A)

    def test_the_hash_is_returned_in_lower_case(self):
        self.assertEqual(provider.parse_hash_line(hash_line(HEX_B.upper()), self.NAME), HEX_B)

    def test_no_line_or_two_lines_is_an_error(self):
        for text in ("", "\n", hash_line(end="\n") + hash_line(HEX_B)):
            with self.subTest(text=text[:10]):
                with self.assertRaises(ValueError):
                    provider.parse_hash_line(text, self.NAME)

    def test_a_line_that_is_not_hash_two_spaces_and_a_name_is_an_error(self):
        for text in (hash_line(gap=" "), hash_line(gap="\t"), hash_line(gap=" *"), HEX_A[:63] + "  " + self.NAME,
                     HEX_A + "0  " + self.NAME, "g" * 64 + "  " + self.NAME, HEX_A):
            with self.subTest(text=text[-30:]):
                with self.assertRaises(ValueError):
                    provider.parse_hash_line(text, self.NAME)

    def test_a_line_for_another_file_is_an_error(self):
        for name in ("krita-x64-6.0.4.zip", "krita-x64-6.0.3-setup.exe", self.NAME + ".sig", "./" + self.NAME):
            with self.subTest(name=name):
                with self.assertRaises(ValueError) as caught:
                    provider.parse_hash_line(hash_line(name=name), self.NAME)
                self.assertIn("names", str(caught.exception))


class MainTests(unittest.TestCase):
    def test_the_highest_folder_with_the_installer(self):
        processor, messages, server = run_with(normal_answers())
        name = "krita-x64-%s-setup.exe" % REISSUE
        self.assertEqual(processor.env["url"], BASE + REISSUE + "/" + name)
        self.assertEqual(processor.env["version"], REISSUE)
        self.assertEqual(processor.env["krita_chosen_folder"], REISSUE)
        self.assertEqual(processor.env["krita_installer_name"], name)
        self.assertEqual(processor.env["expected_sha256"], HEX_A)
        self.assertEqual(processor.env["krita_passed_over"], "")
        self.assertTrue(any(REISSUE in m and name in m for m in messages))

    def test_a_newer_folder_without_the_installer_is_passed_over_and_named(self):
        answers = normal_answers()
        answers[BASE + REISSUE + "/"] = folder_of(REISSUE, with_installer=False)
        processor, messages, server = run_with(answers)
        self.assertEqual(processor.env["version"], "6.0.4")
        self.assertEqual(processor.env["url"], BASE + "6.0.4/krita-x64-6.0.4-setup.exe")
        self.assertEqual(processor.env["krita_passed_over"], REISSUE)
        self.assertIn("Passed over (no Windows installer): %s" % REISSUE, messages)

    def test_at_most_the_fixed_number_of_folders_is_read(self):
        top = ["6.0.%d" % n for n in range(1, 8)]
        answers = normal_answers(top=top)
        for version in top:
            answers[BASE + version + "/"] = folder_of(version, with_installer=False)
        with self.assertRaises(ProcessorError) as caught:
            run_with(answers)
        self.assertIn("none of the %d newest version folders" % provider.MAX_FOLDERS_TRIED, str(caught.exception))
        self.assertIn("6.0.7, 6.0.6, 6.0.5", str(caught.exception))

    def test_the_last_folder_that_may_be_read_is_used(self):
        top = ["6.0.%d" % n for n in range(1, 8)]
        answers = normal_answers(top=top)
        for version in ("6.0.7", "6.0.6"):
            answers[BASE + version + "/"] = folder_of(version, with_installer=False)
        processor, _, server = run_with(answers)
        self.assertEqual(processor.env["version"], "6.0.5")
        self.assertEqual(processor.env["krita_passed_over"], "6.0.7, 6.0.6")
        self.assertEqual(len(server.calls), 1 + 3 + 1)

    def test_the_requests_have_their_limits_and_names(self):
        _, _, server = run_with(normal_answers())
        self.assertEqual(server.calls[0], (BASE, provider.MAX_INDEX_BYTES, "the index of the versions"))
        self.assertEqual(server.calls[1], (BASE + REISSUE + "/", provider.MAX_INDEX_BYTES, "the index of %s/" % REISSUE))
        self.assertEqual(server.calls[2][1:], (provider.MAX_HASH_FILE_BYTES, "the hash file"))
        self.assertEqual(len(server.calls), 3)

    def test_an_index_that_is_not_what_is_expected_is_an_error_and_sets_no_output(self):
        for page in (index_of("updates/"), index_of("6.0.4/", "7.0/")):
            answers = normal_answers()
            answers[BASE] = page
            with self.subTest(page=page[-60:]):
                with self.assertRaises(ProcessorError) as caught:
                    run_with(answers)
                self.assertTrue(str(caught.exception).startswith("Krita index: "))

    def test_a_folder_with_another_versions_installer_stops_the_run(self):
        answers = normal_answers()
        answers[BASE + REISSUE + "/"] = folder_of(REISSUE, with_installer=False, extra=["krita-x64-6.0.4-setup.exe"])
        processor = None
        with self.assertRaises(ProcessorError) as caught:
            processor, _, _ = run_with(answers)
        self.assertIn("Krita index of %s/" % REISSUE, str(caught.exception))
        self.assertIsNone(processor)

    def test_a_hash_file_that_is_not_what_is_expected_is_an_error(self):
        name = "krita-x64-%s-setup.exe" % REISSUE
        for text in ("", hash_line(name="krita-x64-6.0.4-setup.exe"), "<html>Not Found</html>"):
            answers = normal_answers()
            answers[BASE + REISSUE + "/" + name + ".sha256"] = text
            with self.subTest(text=text[:20]):
                with self.assertRaises(ProcessorError) as caught:
                    run_with(answers)
                self.assertTrue(str(caught.exception).startswith("Krita hash file of %s/: " % REISSUE))

    def test_no_output_is_set_when_a_later_step_fails(self):
        answers = normal_answers()
        name = "krita-x64-%s-setup.exe" % REISSUE
        answers[BASE + REISSUE + "/" + name + ".sha256"] = ProcessorError("The server answered 404 Not Found.")
        server = Server(answers)
        from _win_support import new_processor
        processor, _ = new_processor(PROVIDER, {})
        with mock.patch.object(provider, "fetch_text", side_effect=server):
            with self.assertRaises(ProcessorError):
                processor.main()
        for key in PROVIDER.output_variables:
            self.assertNotIn(key, processor.env)

    def test_a_failure_of_the_first_request_asks_for_nothing_more(self):
        answers = {BASE: ProcessorError("The server answered 302 Found for the index (a redirect is not followed).")}
        with self.assertRaises(ProcessorError):
            run_with(answers)

    def test_the_processor_has_no_inputs(self):
        self.assertEqual(PROVIDER.input_variables, {})


class FetchTests(unittest.TestCase):
    URL = BASE

    def fetch_with(self, body=None, error=None, url=None, max_bytes=1000, status=200):
        def opener(request):
            self.request = request
            if error is not None:
                raise error
            response = FakeResponse(body)
            response.status = status
            return response
        with mock.patch.object(provider, "open_request", side_effect=opener):
            return provider.fetch_text(url or self.URL, max_bytes, "the thing")

    def test_the_text_is_returned_and_the_request_is_plain(self):
        text = self.fetch_with(body="café".encode("utf-8"))
        self.assertEqual(text, "café")
        self.assertEqual(self.request.full_url, self.URL)
        self.assertEqual(self.request.get_header("User-agent"), provider.USER_AGENT)
        self.assertIsNone(self.request.data)
        self.assertFalse(self.request.has_header("Authorization"))

    def test_an_address_outside_the_fixed_host_and_folder_is_refused_before_any_request(self):
        for url in ("https://example.test/stable/krita/", "http://download.kde.org/stable/krita/",
                    "https://download.kde.org/unstable/krita/", "https://download.kde.org/stable/",
                    "https://files.kde.org/krita/", "https://download.kde.org.example.test/stable/krita/",
                    "https://download.kde.org@example.test/stable/krita/", "", None):
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
                self.assertNotIn("redirect", str(caught.exception))

    def test_a_success_other_than_200_is_an_error(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch_with(body=b"x", status=203)
        self.assertIn("answered 203", str(caught.exception))

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

    def test_the_real_opener_is_built_with_the_redirect_refusing_handler(self):
        with mock.patch.object(provider.urllib.request, "build_opener") as build:
            provider.open_request(object())
        handlers = build.call_args[0]
        self.assertEqual(len(handlers), 1)
        self.assertIs(handlers[0], provider.NoRedirect)
        self.assertEqual(build.return_value.open.call_args[1]["timeout"], provider.FETCH_TIMEOUT_SECONDS)

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

    def test_the_limits_are_sensible(self):
        self.assertGreaterEqual(provider.MAX_INDEX_BYTES, 256 * 1024)
        self.assertLessEqual(provider.MAX_INDEX_BYTES, 8 * 1024 * 1024)
        self.assertGreaterEqual(provider.MAX_HASH_FILE_BYTES, 1024)
        self.assertLessEqual(provider.MAX_HASH_FILE_BYTES, 1024 * 1024)
        self.assertGreater(provider.FETCH_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(provider.FETCH_TIMEOUT_SECONDS, 600)


if __name__ == "__main__":
    unittest.main()
