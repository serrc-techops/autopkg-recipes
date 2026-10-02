"""Tests of GitHubAssetDigest: every branch. No test uses the network:
fetch_asset_record() is replaced, or urllib's urlopen is."""
import hashlib
import io
import json
import os
import tempfile
import unittest
import urllib.error
from unittest import mock

from _win_support import ProcessorError, checksum, digest, new_processor, run_processor

DIGESTER = digest.GitHubAssetDigest
URL = "https://api.github.com/repos/example-owner/example-app/releases/assets/123456"
HEX = hashlib.sha256(b"example").hexdigest()


def with_record(record):
    return mock.patch.object(digest, "fetch_asset_record", return_value=record)


class DigestTests(unittest.TestCase):
    def test_the_digest_of_the_record_is_the_expected_hash(self):
        with with_record({"name": "app.exe", "digest": "sha256:" + HEX}) as fetch:
            processor, messages = run_processor(DIGESTER, {"github_asset_api_url": URL})
        fetch.assert_called_once_with(URL)
        self.assertEqual(processor.env["expected_sha256"], HEX)
        self.assertTrue(any(HEX in m for m in messages))

    def test_the_output_is_lower_case_hex_without_prefix(self):
        with with_record({"digest": "SHA256:" + HEX.upper()}):
            processor, _ = run_processor(DIGESTER, {"github_asset_api_url": URL})
        self.assertEqual(processor.env["expected_sha256"], HEX)

    def test_a_record_without_a_usable_digest_is_an_error(self):
        bad = {
            "no key": {"name": "app.exe"},
            "null": {"digest": None},
            "empty": {"digest": ""},
            "not text": {"digest": 5},
            "no colon": {"digest": HEX},
            "another algorithm": {"digest": "sha512:" + "a" * 128},
            "another algorithm, 64 digits": {"digest": "sha3-256:" + HEX},
            "short hex": {"digest": "sha256:" + HEX[:-1]},
            "not hex": {"digest": "sha256:" + "g" * 64},
            "long hex": {"digest": "sha256:" + HEX + "0"},
            "trailing new line": {"digest": "sha256:" + HEX + "\n"},
        }
        for label, record in bad.items():
            with self.subTest(case=label):
                processor, _ = new_processor(DIGESTER, {"github_asset_api_url": URL})
                with with_record(record):
                    with self.assertRaises(ProcessorError):
                        processor.main()
                self.assertNotIn("expected_sha256", processor.env)

    def test_a_record_that_is_not_an_object_is_an_error(self):
        for record in ([], "text", None, 5):
            with self.subTest(record=record):
                with with_record(record):
                    with self.assertRaises(ProcessorError) as caught:
                        run_processor(DIGESTER, {"github_asset_api_url": URL})
                self.assertIn("not a JSON object", str(caught.exception))

    def test_a_failed_fetch_is_an_error_and_the_message_is_kept(self):
        with mock.patch.object(digest, "fetch_asset_record", side_effect=ProcessorError("GitHub answered 403")):
            with self.assertRaises(ProcessorError) as caught:
                run_processor(DIGESTER, {"github_asset_api_url": URL})
        self.assertIn("403", str(caught.exception))

    def test_only_the_api_url_of_an_asset_is_fetched(self):
        bad = [
            None,
            "",
            5,
            "http://api.github.com/repos/o/r/releases/assets/1",
            "https://github.com/o/r/releases/download/v1/app.exe",
            "https://api.github.com/repos/o/r/releases/latest",
            "https://api.github.com/repos/o/r/releases/assets/abc",
            "https://api.github.com/repos/o/r/releases/assets/1/",
            "https://api.github.com/repos/o/r/releases/assets/1?x=1",
            "https://api.github.com.example.test/repos/o/r/releases/assets/1",
            "https://example.test/https://api.github.com/repos/o/r/releases/assets/1",
            "https://user@api.github.com/repos/o/r/releases/assets/1",
            URL + "\nHost: example.test",
            URL + "\n",
            URL + " ",
            "https://api.github.com/repos/o/r/releases/assets/",
            "https://api-github-com/repos/o/r/releases/assets/1",
            "https://apixgithub.com/repos/o/r/releases/assets/1",
            "https://api.github.com/repos/o/r/releases/assets/1#x",
            "https://api.github.com/repos/o/r/extra/releases/assets/1",
            "https://api.github.com/repos/o r/x/releases/assets/1",
            "https://api.github.com/repos/o/r/releases/assets/1/../2",
        ]
        for url in bad:
            with self.subTest(url=url):
                with with_record({"digest": "sha256:" + HEX}) as fetch:
                    env = {} if url is None else {"github_asset_api_url": url}
                    with self.assertRaises(ProcessorError):
                        run_processor(DIGESTER, env)
                fetch.assert_not_called()

    def test_the_digest_feeds_the_checksum_verifier(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "app.exe")
            with open(path, "wb") as handle:
                handle.write(b"example")
            with with_record({"digest": "sha256:" + HEX}):
                processor, _ = run_processor(DIGESTER, {"github_asset_api_url": URL})
            run_processor(
                checksum.ChecksumVerifier,
                {"pathname": path, "expected_sha256": processor.env["expected_sha256"]},
            )

    def test_the_declaration(self):
        self.assertTrue(DIGESTER.input_variables["github_asset_api_url"]["required"])
        self.assertIn("expected_sha256", DIGESTER.output_variables)

    def test_the_digest_reader(self):
        self.assertEqual(digest.digest_to_sha256("sha256:" + HEX), HEX)
        with self.assertRaises(ValueError):
            digest.digest_to_sha256("md5:" + "a" * 32)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FetchTests(unittest.TestCase):
    """fetch_asset_record() with urllib's urlopen replaced."""

    def fetch(self, **kwargs):
        with mock.patch.object(digest, "open_request", **kwargs) as urlopen:
            try:
                return digest.fetch_asset_record(URL), urlopen
            finally:
                self.urlopen = urlopen

    def test_a_good_answer_is_parsed(self):
        record, urlopen = self.fetch(return_value=FakeResponse(json.dumps({"digest": "sha256:x"}).encode()))
        self.assertEqual(record, {"digest": "sha256:x"})

    def test_the_request_has_a_time_limit_and_no_credential(self):
        self.fetch(return_value=FakeResponse(b"{}"))
        request = self.urlopen.call_args.args[0]
        self.assertEqual(request.full_url, URL)
        headers = {k.lower(): v for k, v in request.header_items()}
        self.assertNotIn("authorization", headers)
        self.assertIn("user-agent", headers)
        self.assertIn("accept", headers)

    def test_an_http_error_is_an_error_with_the_status(self):
        error = urllib.error.HTTPError(URL, 404, "Not Found", {}, None)
        with self.assertRaises(ProcessorError) as caught:
            self.fetch(side_effect=error)
        self.assertIn("GitHub answered 404", str(caught.exception))

    def test_a_network_error_is_an_error(self):
        for error in (urllib.error.URLError("no route"), TimeoutError("timed out"), ConnectionResetError("reset")):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(ProcessorError):
                    self.fetch(side_effect=error)

    def test_an_answer_that_is_not_json_is_an_error(self):
        for body in (b"<html>", b"", b"\xff\xfe"):
            with self.subTest(body=body):
                with self.assertRaises(ProcessorError):
                    self.fetch(return_value=FakeResponse(body))

    def test_an_answer_that_is_too_large_is_an_error(self):
        body = b'{"a": "' + b"x" * digest.MAX_RESPONSE_BYTES + b'"}'
        with self.assertRaises(ProcessorError) as caught:
            self.fetch(return_value=FakeResponse(body))
        self.assertIn("larger", str(caught.exception))

    def test_a_processor_run_with_the_real_fetch_uses_only_urlopen(self):
        body = json.dumps({"digest": "sha256:" + HEX}).encode()
        with mock.patch.object(digest, "open_request", return_value=FakeResponse(body)):
            processor, _ = run_processor(DIGESTER, {"github_asset_api_url": URL})
        self.assertEqual(processor.env["expected_sha256"], HEX)


import http.client  # noqa: E402
import http.server  # noqa: E402
import threading  # noqa: E402


class MoreFetchTests(unittest.TestCase):
    def test_the_time_limit_of_the_fetch_is_thirty_seconds_and_is_used(self):
        self.assertEqual(digest.FETCH_TIMEOUT_SECONDS, 30)
        opener = mock.Mock()
        opener.open.return_value = FakeResponse(b"{}")
        with mock.patch.object(digest.urllib.request, "build_opener", return_value=opener):
            digest.fetch_asset_record(URL)
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 30)

    def test_every_failure_of_the_request_is_a_processor_error(self):
        errors = [
            http.client.InvalidURL("bad url"),
            http.client.IncompleteRead(b"par", 10),
            http.client.BadStatusLine("junk"),
            http.client.RemoteDisconnected("closed"),
            ValueError("embedded null"),
            ConnectionResetError("reset"),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with mock.patch.object(digest, "open_request", side_effect=error):
                    with self.assertRaises(ProcessorError):
                        digest.fetch_asset_record(URL)

    def test_a_failure_while_the_answer_is_read_is_a_processor_error(self):
        class Broken(FakeResponse):
            def read(self, size=-1):
                raise http.client.IncompleteRead(b"par", 10)

        with mock.patch.object(digest, "open_request", return_value=Broken(b"")):
            with self.assertRaises(ProcessorError):
                digest.fetch_asset_record(URL)

    def test_an_answer_that_is_not_utf8_is_an_error_even_if_latin1_would_read_it(self):
        body = b'{"digest": "sha256:\xe9"}'
        with mock.patch.object(digest, "open_request", return_value=FakeResponse(body)):
            with self.assertRaises(ProcessorError):
                digest.fetch_asset_record(URL)

    def test_a_bad_url_is_a_processor_error_whole_run(self):
        with mock.patch.object(digest, "open_request", side_effect=http.client.InvalidURL("x")):
            with self.assertRaises(ProcessorError):
                run_processor(DIGESTER, {"github_asset_api_url": URL})


class RedirectTests(unittest.TestCase):
    """A local server on the loopback address (no network). A redirect is an
    error and the second address is never asked."""

    def setUp(self):
        asked = self.asked = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                asked.append(self.path)
                if self.path.startswith("/code"):
                    self.send_response(int(self.path[len("/code"):]))
                    self.send_header("Location", "/elsewhere")
                    self.end_headers()
                elif self.path == "/asset":
                    self.send_response(301)
                    self.send_header("Location", "/elsewhere")
                    self.end_headers()
                elif self.path == "/plain":
                    body = b'{"digest": "sha256:%s"}' % HEX.encode()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"{}")

            def log_message(self, *args):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def test_a_redirect_is_an_error_that_names_the_status(self):
        with self.assertRaises(ProcessorError) as caught:
            digest.fetch_asset_record("http://127.0.0.1:%d/asset" % self.port)
        self.assertIn("301", str(caught.exception))
        self.assertIn("redirect", str(caught.exception))
        self.assertEqual(self.asked, ["/asset"])

    def test_every_kind_of_redirect_is_an_error(self):
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                del self.asked[:]
                with self.assertRaises(ProcessorError) as caught:
                    digest.fetch_asset_record("http://127.0.0.1:%d/code%d" % (self.port, code))
                self.assertIn(str(code), str(caught.exception))
                self.assertIn("redirect", str(caught.exception))
                self.assertEqual(self.asked, ["/code%d" % code])

    def test_a_plain_answer_is_read(self):
        record = digest.fetch_asset_record("http://127.0.0.1:%d/plain" % self.port)
        self.assertEqual(record["digest"], "sha256:" + HEX)


if __name__ == "__main__":
    unittest.main()
