"""Tests of AuthenticodeVerifier.

The tests that sign and verify files build everything at test time in a temporary
folder: throwaway roots, signing and timestamp certificates (openssl), a small PE file
(built here), and signatures with a local timestamp (osslsigncode's -TSA-certs,
-TSA-key and -TSA-time, so no timestamp server is asked). The CRLs are served by a
server on the loopback address. No real installer and no network are used. Those
tests need osslsigncode and OpenSSL 3.4 or later (for -not_before) and are skipped,
with the reason, where either is missing. No MSI is built: there is no tool here that
writes one; the real MSI files of the README's checks are the only MSI evidence.

The tests that read the processor's inputs, the pinned roots, the DER reader and the
tool's output need no tool.
"""
import calendar
import hashlib
import http.server
import os
import re
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from _win_support import PROCESSOR_DIR, ProcessorError, new_processor, sha256_hex

import AuthenticodeVerifier as authenticode  # noqa: E402

PROCESSOR = authenticode.AuthenticodeVerifier
OPENSSL_CANDIDATES = ("/opt/homebrew/bin/openssl", "/usr/local/bin/openssl")
# Every signature of the fixtures is timestamped at this moment (2025-01-02 12:00 UTC).
TIMESTAMP_TIME = calendar.timegm((2025, 1, 2, 12, 0, 0))
LONG_VALIDITY = ("20240101000000Z", "20400101000000Z")
# A signing certificate that lived three days around the timestamp, and has expired since.
SHORT_VALIDITY = ("20250101000000Z", "20250104000000Z")
O_UMLAUT = "ö"
EXPECTED = {"CN": "Example, Inc.", "O": "Example, Inc.", "L": "Linz", "ST": "Ober" + O_UMLAUT + "sterreich", "C": "AT"}
EXPECTED_SUBJECT = "/C=AT/ST=Ober%ssterreich/L=Linz/O=Example, Inc./CN=Example, Inc." % O_UMLAUT
OTHER_SUBJECT = "/C=AT/O=Example Other Publisher/CN=Example Other Publisher"
MIN_CONFIG = "[req]\ndistinguished_name=dn\n[dn]\n"


def find_openssl():
    for candidate in OPENSSL_CANDIDATES + tuple(filter(None, [shutil.which("openssl")])):
        if not os.path.isfile(candidate):
            continue
        try:
            text = subprocess.run([candidate, "version"], capture_output=True, text=True, timeout=30).stdout
        except OSError:
            continue
        match = re.match(r"OpenSSL (\d+)\.(\d+)", text)
        if match and (int(match.group(1)), int(match.group(2))) >= (3, 4):
            return candidate
    return None


def find_osslsigncode():
    try:
        return authenticode.find_tool()
    except ProcessorError:
        return None


OPENSSL = find_openssl()
OSSLSIGNCODE = find_osslsigncode()
needs_tools = unittest.skipUnless(
    OPENSSL and OSSLSIGNCODE,
    "needs osslsigncode and OpenSSL 3.4 or later (brew install osslsigncode openssl); not found",
)


def build_pe():
    """A small PE32 file with one code section, enough for osslsigncode to sign."""
    pe_offset = 0x80
    optional = bytearray(96)
    struct.pack_into("<H", optional, 0, 0x10B)
    struct.pack_into("<I", optional, 28, 0x400000)
    struct.pack_into("<II", optional, 32, 0x1000, 0x200)
    struct.pack_into("<HH", optional, 40, 6, 0)
    struct.pack_into("<HH", optional, 48, 6, 0)
    struct.pack_into("<I", optional, 56, 0x2000)
    struct.pack_into("<I", optional, 60, 0x200)
    struct.pack_into("<H", optional, 68, 3)
    struct.pack_into("<I", optional, 92, 16)
    optional = bytes(optional) + bytes(16 * 8)
    text = b"\xc3" * 16
    section = struct.pack("<8sIIIIIIHHI", b".text\0\0\0", len(text), 0x1000, 0x200, 0x200, 0, 0, 0, 0, 0x60000020)
    coff = struct.pack("<HHIIIHH", 0x14C, 1, 0, 0, 0, len(optional), 0x0102)
    dos = bytearray(pe_offset)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, pe_offset)
    headers = bytes(dos) + b"PE\0\0" + coff + optional + section
    headers += b"\0" * (0x200 - len(headers))
    return headers + text + b"\0" * (0x200 - len(text))


class CrlServer:
    """Serves CRLs (by path) on the loopback address."""

    def __init__(self):
        self.files = {}
        files = self.files

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = files.get(self.path)
                if body is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def url(self, name):
        return "http://127.0.0.1:%d/%s.crl" % (self.port, name)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def closed_port():
    """A loopback port that nothing listens on."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Pki:
    """Throwaway roots and certificates, made with openssl."""

    def __init__(self, folder, server):
        self.folder = folder
        self.server = server
        with open(self.path("min.cnf"), "w") as handle:
            handle.write(MIN_CONFIG)

    def path(self, name):
        return os.path.join(self.folder, name)

    def openssl(self, *arguments):
        subprocess.run([OPENSSL] + list(arguments), check=True, capture_output=True, timeout=120)

    def root(self, name, common_name):
        self.openssl("req", "-x509", "-config", self.path("min.cnf"), "-newkey", "rsa:2048", "-nodes",
                     "-keyout", self.path(name + ".key"), "-out", self.path(name + ".pem"),
                     "-subj", "/O=Example Test/CN=%s" % common_name,
                     "-not_before", LONG_VALIDITY[0], "-not_after", LONG_VALIDITY[1],
                     "-addext", "basicConstraints=critical,CA:true",
                     "-addext", "keyUsage=critical,keyCertSign,cRLSign",
                     "-addext", "subjectKeyIdentifier=hash")
        folder = self.path("ca-" + name)
        os.makedirs(folder)
        open(os.path.join(folder, "index.txt"), "w").close()
        with open(os.path.join(folder, "crlnumber"), "w") as handle:
            handle.write("1000\n")
        with open(os.path.join(folder, "ca.cnf"), "w") as handle:
            handle.write("[ca]\ndefault_ca=x\n[x]\ndatabase=%s\ncrlnumber=%s\ndefault_md=sha256\n"
                         "default_crl_days=30\n" % (os.path.join(folder, "index.txt"), os.path.join(folder, "crlnumber")))
        self.publish_crl(name)
        return self.path(name + ".pem")

    def publish_crl(self, root):
        config = self.path(os.path.join("ca-" + root, "ca.cnf"))
        self.openssl("ca", "-config", config, "-gencrl", "-cert", self.path(root + ".pem"),
                     "-keyfile", self.path(root + ".key"), "-out", self.path(root + ".crl.pem"))
        self.openssl("crl", "-in", self.path(root + ".crl.pem"), "-outform", "DER", "-out", self.path(root + ".crl"))
        with open(self.path(root + ".crl"), "rb") as handle:
            self.server.files["/%s.crl" % root] = handle.read()

    def revoke(self, root, certificate):
        config = self.path(os.path.join("ca-" + root, "ca.cnf"))
        self.openssl("ca", "-config", config, "-revoke", certificate, "-cert", self.path(root + ".pem"),
                     "-keyfile", self.path(root + ".key"))
        self.publish_crl(root)

    def issue(self, name, issuer, subject, serial, usage="codeSigning", validity=LONG_VALIDITY, crl_url="issuer"):
        """A certificate for the key `name`.key (made when missing), issued by the root `issuer`."""
        key = self.path(name + ".key")
        if not os.path.exists(key):
            self.openssl("genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", key)
        self.openssl("req", "-new", "-config", self.path("min.cnf"), "-utf8", "-key", key, "-subj", subject,
                     "-out", self.path(name + ".csr"))
        lines = ["[ext]", "basicConstraints=critical,CA:false", "keyUsage=critical,digitalSignature",
                 "extendedKeyUsage=%s%s" % ("critical," if usage == "timeStamping" else "", usage),
                 "authorityKeyIdentifier=keyid"]
        if crl_url == "issuer":
            crl_url = self.server.url(issuer)
        if crl_url:
            lines.append("crlDistributionPoints=URI:%s" % crl_url)
        with open(self.path(name + ".ext"), "w") as handle:
            handle.write("\n".join(lines) + "\n")
        self.openssl("x509", "-req", "-in", self.path(name + ".csr"), "-CA", self.path(issuer + ".pem"),
                     "-CAkey", self.path(issuer + ".key"), "-set_serial", str(serial),
                     "-not_before", validity[0], "-not_after", validity[1],
                     "-extfile", self.path(name + ".ext"), "-extensions", "ext", "-out", self.path(name + ".pem"))
        return self.path(name + ".pem")


def setUpModule():
    global FIXTURE
    FIXTURE = None
    if not (OPENSSL and OSSLSIGNCODE):
        return
    FIXTURE = Fixture()


def tearDownModule():
    if FIXTURE is not None:
        FIXTURE.close()


class Fixture:
    """The PKI and the signed files that the tests share. Built once."""

    def __init__(self):
        self.folder = tempfile.mkdtemp(prefix="authenticode-test-")
        self.server = CrlServer()
        pki = self.pki = Pki(self.folder, self.server)
        pki.root("root", "Example Test Root")
        pki.root("tsaroot", "Example Test Timestamp Root")
        pki.root("otherroot", "Example Unpinned Root")
        pki.issue("tsa", "tsaroot", "/O=Example Test/CN=Example Test Timestamps", 2001, usage="timeStamping")
        with open(pki.path("tsa-chain.pem"), "w") as out:
            for name in ("tsa", "tsaroot"):
                with open(pki.path(name + ".pem")) as handle:
                    out.write(handle.read())
        pki.issue("good", "root", EXPECTED_SUBJECT, 1001)
        pki.issue("short", "root", EXPECTED_SUBJECT, 1002, validity=SHORT_VALIDITY)
        pki.issue("other", "root", OTHER_SUBJECT, 1003)
        pki.issue("unpinned", "otherroot", EXPECTED_SUBJECT, 1004)
        pki.issue("revoked", "root", EXPECTED_SUBJECT, 1005)
        pki.issue("nocrl", "root", EXPECTED_SUBJECT, 1006, crl_url=None)
        pki.issue("deadcrl", "root", EXPECTED_SUBJECT, 1007,
                  crl_url="http://127.0.0.1:%d/root.crl" % closed_port())
        # Extra certificates that a forger could add to a signature's bag.
        pki.issue("decoy", "otherroot", EXPECTED_SUBJECT, 3001)
        pki.issue("twin", "otherroot", EXPECTED_SUBJECT, 1003)  # the serial number of "other"
        pki.revoke("root", pki.path("revoked.pem"))
        self.unsigned = os.path.join(self.folder, "app.exe")
        with open(self.unsigned, "wb") as handle:
            handle.write(build_pe())
        self.count = 0

    def sign(self, signer="good", source=None, timestamp=True, extra=None, nest=False, digest="sha256"):
        self.count += 1
        target = os.path.join(self.folder, "signed-%d.exe" % self.count)
        arguments = [OSSLSIGNCODE, "sign", "-certs", self.pki.path(signer + ".pem"),
                     "-key", self.pki.path(signer + ".key"), "-h", digest]
        if timestamp:
            arguments += ["-TSA-certs", self.pki.path("tsa-chain.pem"), "-TSA-key", self.pki.path("tsa.key"),
                          "-TSA-time", str(TIMESTAMP_TIME)]
        if extra:
            arguments += ["-ac", self.pki.path(extra + ".pem")]
        if nest:
            arguments.append("-nest")
        arguments += ["-in", source or self.unsigned, "-out", target]
        subprocess.run(arguments, check=True, capture_output=True, timeout=120)
        return target

    def close(self):
        self.server.stop()
        shutil.rmtree(self.folder, ignore_errors=True)


def pinned_test_roots():
    """A table of pinned roots with the fixture's two roots, with their real hashes."""
    table = {}
    for name in ("root", "tsaroot"):
        with open(FIXTURE.pki.path(name + ".pem")) as handle:
            der = ssl.PEM_cert_to_DER_cert(handle.read())
        table["example-" + name] = (name + ".pem", hashlib.sha256(der).hexdigest())
    return table


class SigningTestCase(unittest.TestCase):
    def setUp(self):
        if FIXTURE is None:
            self.skipTest("needs osslsigncode and OpenSSL 3.4 or later")
        patches = [mock.patch.object(authenticode, "PINNED_ROOTS", pinned_test_roots()),
                   mock.patch.object(authenticode, "ROOTS_FOLDER", FIXTURE.folder)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def env(self, path, **overrides):
        values = {"pathname": path, "expected_signer": dict(EXPECTED), "code_signing_roots": ["example-root"],
                  "timestamp_roots": ["example-tsaroot"]}
        values.update(overrides)
        return values

    def verify(self, path, **overrides):
        processor, messages = new_processor(PROCESSOR, self.env(path, **overrides))
        processor.main()
        return processor, messages

    def refused(self, path, fragment, **overrides):
        processor, _ = new_processor(PROCESSOR, self.env(path, **overrides))
        with self.assertRaises(ProcessorError) as caught:
            processor.main()
        message = str(caught.exception)
        self.assertIn(fragment, message)
        self.assertIn(os.path.basename(path), message)
        for key in PROCESSOR.output_variables:
            self.assertNotIn(key, processor.env)
        return message


@needs_tools
class GoodSignatureTests(SigningTestCase):
    def test_a_good_signature_under_a_pinned_root_passes(self):
        path = FIXTURE.sign()
        processor, messages = self.verify(path)
        self.assertIs(processor.env["signature_verified"], True)
        self.assertEqual(processor.env["signature_sha256"], sha256_hex(path))
        self.assertEqual(processor.env["authenticode_signer"],
                         "CN=Example, Inc., O=Example, Inc., L=Linz, ST=Ober%ssterreich, C=AT" % O_UMLAUT)
        self.assertEqual(processor.env["authenticode_signing_time"], "Jan  2 12:00:00 2025 GMT")
        self.assertTrue(processor.env["authenticode_tool"].startswith("osslsigncode "))
        self.assertTrue(messages[0].startswith("Signature verified: %s, signed by" % os.path.basename(path)))

    def test_a_field_that_the_recipe_does_not_name_must_be_absent(self):
        path = FIXTURE.sign()
        for field in ("L", "ST"):
            with self.subTest(field=field):
                expected = {key: value for key, value in EXPECTED.items() if key != field}
                self.refused(path, "has a field %s, which the recipe does not name" % field, expected_signer=expected)

    def test_an_expired_short_lived_certificate_passes_through_its_timestamp(self):
        self.verify(FIXTURE.sign("short"))

    def test_two_nested_signatures_of_the_publisher_pass(self):
        path = FIXTURE.sign(source=FIXTURE.sign(), nest=True, digest="sha1")
        _, messages = self.verify(path, digest_algorithms=["sha256", "sha1"])
        self.assertIn("(2 signatures)", messages[0])

    def test_the_same_certificate_twice_in_the_bag_is_one_certificate(self):
        self.verify(FIXTURE.sign(extra="good"))

    def test_roots_may_be_given_as_one_text_with_commas(self):
        self.verify(FIXTURE.sign(), code_signing_roots="example-root, example-tsaroot")

    def test_the_input_file_is_not_changed_and_nothing_is_left_in_the_temporary_folder(self):
        path = FIXTURE.sign()
        before = sha256_hex(path)
        made = []
        real = tempfile.mkdtemp

        def recording(*args, **kwargs):
            made.append(real(*args, **kwargs))
            return made[-1]
        with mock.patch.object(authenticode.tempfile, "mkdtemp", recording):
            self.verify(path)
        self.assertEqual(sha256_hex(path), before)
        self.assertEqual(len(made), 1)
        self.assertFalse(os.path.exists(made[0]))


@needs_tools
class RefusalTests(SigningTestCase):
    def test_a_file_changed_after_signing_is_refused(self):
        path = FIXTURE.sign()
        with open(path, "r+b") as handle:
            handle.seek(0x205)
            byte = handle.read(1)
            handle.seek(0x205)
            handle.write(bytes([byte[0] ^ 1]))
        self.refused(path, "refused the signature")

    def test_another_publisher_is_refused(self):
        message = self.refused(FIXTURE.sign("other"), "is not signed by the expected publisher")
        self.assertIn("the signer's CN is 'Example Other Publisher'", message)

    def test_a_wrong_o_or_cn_or_country_is_refused(self):
        path = FIXTURE.sign()
        for field, value in (("O", "Example Inc."), ("CN", "Example, Inc"), ("C", "DE"), ("L", "linz"),
                             ("ST", "Oberosterreich")):
            with self.subTest(field=field):
                expected = dict(EXPECTED)
                expected[field] = value
                self.refused(path, "the signer's %s is" % field, expected_signer=expected)

    def test_a_field_that_the_name_lacks_is_refused(self):
        expected = dict(EXPECTED)
        expected["OU"] = "Example Unit"
        self.refused(FIXTURE.sign(), "has 0 fields OU", expected_signer=expected)

    def test_a_chain_to_a_root_that_is_not_pinned_for_the_recipe_is_refused(self):
        self.assertIn("unable to get local issuer certificate",
                      self.refused(FIXTURE.sign("unpinned"), "refused the signature"))

    def test_the_timestamp_root_does_not_count_for_the_code_signature(self):
        self.refused(FIXTURE.sign(), "refused the signature", code_signing_roots=["example-tsaroot"])

    def test_the_code_root_does_not_count_for_the_timestamp(self):
        self.refused(FIXTURE.sign(), "refused the signature", timestamp_roots=["example-root"])

    def test_a_signature_without_a_timestamp_is_refused(self):
        self.refused(FIXTURE.sign(timestamp=False), "has no timestamp")

    def test_a_revoked_signing_certificate_is_refused(self):
        self.assertIn("certificate revoked", self.refused(FIXTURE.sign("revoked"), "refused the signature"))

    def test_a_crl_that_cannot_be_fetched_is_refused(self):
        self.assertIn("Failed to get CRL", self.refused(FIXTURE.sign("deadcrl"), "refused the signature"))

    def test_a_signing_certificate_that_names_no_crl_is_refused(self):
        self.refused(FIXTURE.sign("nocrl"), "'Signature CRL verification: ok'")

    def test_a_decoy_with_the_expected_name_in_the_bag_does_not_make_another_publisher_pass(self):
        path = FIXTURE.sign("other", extra="decoy")
        message = self.refused(path, "is not signed by the expected publisher")
        self.assertIn("'Example Other Publisher'", message)

    def test_a_second_certificate_with_the_signers_serial_number_is_refused(self):
        self.refused(FIXTURE.sign("other", extra="twin"),
                     "2 different certificates with the signer's serial number")

    def test_a_nested_signature_of_another_publisher_is_refused(self):
        path = FIXTURE.sign("other", source=FIXTURE.sign(), nest=True)
        self.refused(path, "signature 1: the signer's CN is 'Example Other Publisher'")

    def test_an_unsigned_file_is_refused(self):
        copy = os.path.join(FIXTURE.folder, "unsigned-copy.exe")
        shutil.copyfile(FIXTURE.unsigned, copy)
        self.refused(copy, "has no Authenticode signature")

    def test_a_pinned_root_file_that_was_changed_is_refused(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        for name in ("root.pem", "tsaroot.pem"):
            shutil.copyfile(os.path.join(FIXTURE.folder, name), os.path.join(folder, name))
        shutil.copyfile(os.path.join(FIXTURE.folder, "otherroot.pem"), os.path.join(folder, "root.pem"))
        with mock.patch.object(authenticode, "ROOTS_FOLDER", folder):
            self.refused(FIXTURE.sign(), "does not have the SHA-256 written for example-root")


@needs_tools
class ToolOutputTests(SigningTestCase):
    """The checks of the tool's output, with a stand-in that prints the real tool's
    output for a good file, changed in one place."""

    def stand_in(self, path, change):
        code, out, _ = authenticode.run_tool(
            OSSLSIGNCODE, ["verify", "-in", path, "-CAfile", FIXTURE.pki.path("root.pem"),
                           "-TSA-CAfile", FIXTURE.pki.path("tsaroot.pem")], 120)
        self.assertEqual(code, 0)
        changed = change(out)
        self.assertNotEqual(changed, out)
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        with open(os.path.join(folder, "verify.txt"), "w", encoding="utf-8") as handle:
            handle.write(changed)
        script = os.path.join(folder, "osslsigncode")
        with open(script, "w") as handle:
            handle.write("#!%s\nimport os, subprocess, sys\nif sys.argv[1] == 'verify':\n"
                         "    sys.stdout.write(open(%r, encoding='utf-8').read())\n    sys.exit(0)\n"
                         "sys.exit(subprocess.run([%r] + sys.argv[1:]).returncode)\n"
                         % (sys.executable, os.path.join(folder, "verify.txt"), OSSLSIGNCODE))
        os.chmod(script, 0o755)
        patch = mock.patch.object(authenticode, "TOOL_FOLDERS", (folder,))
        patch.start()
        self.addCleanup(patch.stop)

    def test_the_real_output_passes_through_the_stand_in(self):
        path = FIXTURE.sign()
        self.stand_in(path, lambda out: out + "\n")
        self.verify(path)

    def test_a_missing_crl_line_is_refused(self):
        path = FIXTURE.sign()
        self.stand_in(path, lambda out: out.replace("Signature CRL verification: ok\n", "", 1)
                               if "\nSignature CRL verification: ok\n" in out else out + "x")
        self.refused(path, "did not print")

    def test_another_count_of_signatures_is_refused(self):
        path = FIXTURE.sign()
        self.stand_in(path, lambda out: out.replace("Number of verified signatures: 1",
                                                             "Number of verified signatures: 2"))
        self.refused(path, "did not report 1 verified signature")

    def test_a_chain_verified_for_another_certificate_is_refused(self):
        path = FIXTURE.sign()

        def other_leaf(out):
            head, _, tail = out.partition(authenticode.CODE_CHAIN_HEADER)
            return head + authenticode.CODE_CHAIN_HEADER + tail.replace("Serial : 03E9", "Serial : 03EA", 1)
        self.stand_in(path, other_leaf)
        self.refused(path, "is not the one that the signature names as its signer")

    def test_a_chain_that_ends_in_another_root_is_refused(self):
        path = FIXTURE.sign()
        with open(FIXTURE.pki.path("root.pem")) as handle:
            serial = authenticode.certificate_serial(ssl.PEM_cert_to_DER_cert(handle.read()))
        shown = "%X" % serial
        shown = ("0" if len(shown) % 2 else "") + shown

        def other_root(out):
            head, _, tail = out.partition(authenticode.CODE_CHAIN_HEADER)
            return head + authenticode.CODE_CHAIN_HEADER + tail.replace("Serial : " + shown, "Serial : 01", 1)
        self.stand_in(path, other_root)
        self.refused(path, "the signing chain does not end in one of example-root")

    def test_a_last_line_other_than_succeeded_is_refused(self):
        path = FIXTURE.sign()
        self.stand_in(path, lambda out: out.rstrip() + "\nFailed\n")
        self.refused(path, "the tool's last line is not 'Succeeded'")


def security_directory(data):
    """(position of the security directory entry, its offset, its size) of a PE32 file."""
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    entry = optional + (96 if magic == 0x10B else 112) + 8 * 4
    offset, size = struct.unpack_from("<II", data, entry)
    return entry, offset, size


@needs_tools
class LayoutTests(SigningTestCase):
    """No byte of a PE file may lie outside what the signature covers: the certificate table
    is the one part that it does not cover."""

    def changed(self, change):
        data = bytearray(open(FIXTURE.sign(), "rb").read())
        change(data)
        path = os.path.join(FIXTURE.folder, "changed-%d.exe" % len(os.listdir(FIXTURE.folder)))
        with open(path, "wb") as handle:
            handle.write(bytes(data))
        return path

    def test_the_fixture_has_one_entry_that_ends_at_the_end_of_the_file(self):
        data = open(FIXTURE.sign(), "rb").read()
        _, offset, size = security_directory(data)
        self.assertEqual(offset + size, len(data))

    def test_bytes_appended_after_the_table_are_refused(self):
        # The reader's E5a: the headers unchanged, bytes after the table.
        path = self.changed(lambda data: data.extend(b"EVILPAYLOAD" * 100))
        with open(path, "rb") as handle:
            self.assertTrue(handle.read().endswith(b"EVILPAYLOAD"))
        processor, _ = new_processor(PROCESSOR, self.env(path))
        with self.assertRaises(ProcessorError):
            processor.main()

    def test_bytes_inside_the_entry_are_refused(self):
        # The reader's E5b: dwLength and the directory grown, bytes after the PKCS#7.
        def grow(data):
            entry, offset, size = security_directory(data)
            pad = b"EVILPAYLOAD!" * 64
            data.extend(pad)
            struct.pack_into("<I", data, entry + 4, size + len(pad))
            struct.pack_into("<I", data, offset, struct.unpack_from("<I", data, offset)[0] + len(pad))
        self.refused(self.changed(grow), "it holds bytes that the signature does not cover")

    def test_zero_padding_beyond_8_bytes_is_refused_too(self):
        def grow(data):
            entry, offset, size = security_directory(data)
            data.extend(b"\0" * 64)
            struct.pack_into("<I", data, entry + 4, size + 64)
            struct.pack_into("<I", data, offset, struct.unpack_from("<I", data, offset)[0] + 64)
        self.refused(self.changed(grow), "it holds bytes that the signature does not cover")

    def test_a_second_entry_is_refused(self):
        # The reader's E5c.
        def second(data):
            entry, offset, size = security_directory(data)
            pad = b"EVILPAYLOAD!" * 64
            data.extend(struct.pack("<IHH", 8 + len(pad), 0x0200, 0x0002) + pad)
            struct.pack_into("<I", data, entry + 4, size + 8 + len(pad))
        self.refused(self.changed(second), "it holds bytes that the signature does not cover")

    def test_non_zero_bytes_in_the_padding_are_refused(self):
        data = bytearray(open(FIXTURE.sign(), "rb").read())
        _, offset, size = security_directory(data)
        end = authenticode.read_element(bytes(data), offset + 8, len(data))[2]
        if offset + size == end:
            self.skipTest("this fixture's signature needs no padding (its length is a multiple of 8)")
        data[end] = 0x41
        path = os.path.join(FIXTURE.folder, "poked.exe")
        with open(path, "wb") as handle:
            handle.write(bytes(data))
        self.refused(path, "bytes after the signature that are not zero padding")

    def test_an_entry_of_another_type_is_refused(self):
        def retype(data):
            _, offset, _ = security_directory(data)
            struct.pack_into("<H", data, offset + 6, 0x0001)
        path = self.changed(retype)
        processor, _ = new_processor(PROCESSOR, self.env(path))
        with self.assertRaises(ProcessorError):
            processor.main()

    def test_the_layout_check_alone(self):
        good = FIXTURE.sign()
        der = self.extracted(good)
        authenticode.check_pe_layout(good, der)
        data = bytearray(open(good, "rb").read())
        _, offset, _ = security_directory(data)
        cases = {
            "another type": lambda d: struct.pack_into("<H", d, offset + 6, 0x0001),
            "another revision": lambda d: struct.pack_into("<H", d, offset + 4, 0x0100),
            "a length too short": lambda d: struct.pack_into("<I", d, offset, 8),
            "another signature": lambda d: d.__setitem__(offset + 20, d[offset + 20] ^ 1),
            "a table that does not end the file": lambda d: d.extend(b"\0" * 8),
            "too few data directories": lambda d: struct.pack_into(
                "<I", d, struct.unpack_from("<I", d, 0x3C)[0] + 24 + 92, 4),
        }
        for name, change in cases.items():
            with self.subTest(case=name):
                copy = bytearray(data)
                change(copy)
                path = os.path.join(FIXTURE.folder, "layout.exe")
                with open(path, "wb") as handle:
                    handle.write(bytes(copy))
                with self.assertRaises(authenticode.DerError):
                    authenticode.check_pe_layout(path, der)

    def test_a_table_that_does_not_start_on_8_bytes_is_refused(self):
        good = FIXTURE.sign()
        der = self.extracted(good)
        data = bytearray(open(good, "rb").read())
        entry, offset, size = security_directory(data)
        # Four bytes before the table: everything else of the table stays as it was.
        moved = data[:offset] + b"\0" * 4 + data[offset:]
        struct.pack_into("<I", moved, entry, offset + 4)
        path = os.path.join(FIXTURE.folder, "unaligned.exe")
        with open(path, "wb") as handle:
            handle.write(bytes(moved))
        with self.assertRaisesRegex(authenticode.DerError, "does not start on 8 bytes"):
            authenticode.check_pe_layout(path, der)

    def test_too_few_data_directories_are_refused(self):
        good = FIXTURE.sign()
        der = self.extracted(good)
        data = bytearray(open(good, "rb").read())
        struct.pack_into("<I", data, struct.unpack_from("<I", data, 0x3C)[0] + 24 + 92, 4)
        path = os.path.join(FIXTURE.folder, "four-directories.exe")
        with open(path, "wb") as handle:
            handle.write(bytes(data))
        with self.assertRaisesRegex(authenticode.DerError, "too few data directories"):
            authenticode.check_pe_layout(path, der)

    def extracted(self, path):
        target = os.path.join(FIXTURE.folder, "extracted-%d.p7" % len(os.listdir(FIXTURE.folder)))
        subprocess.run([OSSLSIGNCODE, "extract-signature", "-in", path, "-out", target], check=True, capture_output=True)
        with open(target, "rb") as handle:
            return handle.read()


@needs_tools
class DigestAndKindTests(SigningTestCase):
    def test_sha1_is_refused_unless_the_recipe_allows_it(self):
        path = FIXTURE.sign(digest="sha1")
        self.refused(path, "the file digest uses sha1, which the recipe does not allow")
        self.verify(path, digest_algorithms=["sha1"])

    def test_md5_is_refused_always(self):
        path = FIXTURE.sign(digest="md5")
        for allowed in (["sha256"], ["sha1", "sha256", "sha384", "sha512"]):
            with self.subTest(allowed=allowed):
                self.refused(path, "uses md5, which the recipe does not allow", digest_algorithms=allowed)

    def test_sha384_is_refused_by_default_and_allowed_by_name(self):
        path = FIXTURE.sign(digest="sha384")
        self.refused(path, "uses sha384")
        self.verify(path, digest_algorithms="sha384")

    def test_a_nested_sha1_signature_is_refused_by_default(self):
        path = FIXTURE.sign(source=FIXTURE.sign(), nest=True, digest="sha1")
        self.refused(path, "signature 1: the file digest uses sha1")

    def test_a_pe_file_named_msi_is_refused(self):
        path = os.path.join(FIXTURE.folder, "not-an-msi.msi")
        shutil.copyfile(FIXTURE.sign(), path)
        self.refused(path, "the file does not begin as an .msi file does")


@needs_tools
class GuardTests(SigningTestCase):
    """The checks that the tool alone would also make, each with a test of its own."""

    def test_the_timestamp_is_required_from_the_signature_itself(self):
        message = self.refused(FIXTURE.sign(timestamp=False), "has no timestamp")
        self.assertIn("Without one the chain would be judged today", message)

    def test_a_field_twice_is_refused(self):
        FIXTURE.pki.issue("twofields", "root", EXPECTED_SUBJECT.replace("/O=Example, Inc.", "/O=Example, Inc./O=Example Other"),
                          1010)
        self.refused(FIXTURE.sign("twofields"), "has 2 fields O, not exactly one")

    def test_a_timestamp_chain_that_ends_in_another_root_is_refused(self):
        path = FIXTURE.sign()
        with open(FIXTURE.pki.path("tsaroot.pem")) as handle:
            serial = authenticode.certificate_serial(ssl.PEM_cert_to_DER_cert(handle.read()))
        shown = "%X" % serial
        shown = ("0" if len(shown) % 2 else "") + shown

        def other_root(out):
            head, _, tail = out.partition(authenticode.TIMESTAMP_CHAIN_HEADER)
            return head + authenticode.TIMESTAMP_CHAIN_HEADER + tail.replace("Serial : " + shown, "Serial : 01", 1)
        ToolOutputTests.stand_in(self, path, other_root)
        self.refused(path, "the timestamp's chain does not end in one of example-tsaroot")

    def test_a_signature_larger_than_the_cap_is_refused(self):
        with mock.patch.object(authenticode, "MAX_SIGNATURE_BYTES", 100):
            self.refused(FIXTURE.sign(), "the signature is larger than 100 bytes")


# ---- a small DER writer, for signatures that no signing tool makes -------------------

def der(tag, content):
    length = len(content)
    if length < 0x80:
        head = bytes([length])
    else:
        raw = length.to_bytes((length.bit_length() + 7) // 8, "big")
        head = bytes([0x80 | len(raw)]) + raw
    return bytes([tag]) + head + content


def seq(*parts):
    return der(0x30, b"".join(parts))


def oid(numbers):
    body = bytes([40 * numbers[0] + numbers[1]])
    for number in numbers[2:]:
        chunk = [number & 0x7F]
        number >>= 7
        while number:
            chunk.insert(0, 0x80 | (number & 0x7F))
            number >>= 7
        body += bytes(chunk)
    return der(0x06, body)


def integer(value):
    return der(0x02, value.to_bytes((value.bit_length() + 8) // 8, "big", signed=True))


def name(*fields):
    return seq(*(der(0x31, seq(oid(kind), der(0x0C, text.encode("utf-8")))) for kind, text in fields))


ISSUER = name(((2, 5, 4, 3), "Example Issuer"))
OTHER_ISSUER = name(((2, 5, 4, 3), "Example Other Issuer"))
SUBJECT = name(((2, 5, 4, 6), "AT"), ((2, 5, 4, 10), "Example, Inc."), ((2, 5, 4, 3), "Example, Inc."))
SHA256 = authenticode.DIGEST_ALGORITHMS["sha256"]


def certificate(serial, issuer=ISSUER, subject=SUBJECT):
    tbs = seq(der(0xA0, integer(2)), integer(serial), seq(oid((1, 2, 840, 113549, 1, 1, 11))), issuer,
              seq(der(0x17, b"240101000000Z"), der(0x17, b"400101000000Z")), subject, seq())
    return seq(tbs, seq(oid((1, 2, 840, 113549, 1, 1, 11))), der(0x03, b"\0"))


TST_INFO = (1, 2, 840, 113549, 1, 9, 16, 1, 4)


RSA = (1, 2, 840, 113549, 1, 1, 1)
NULL = der(0x05, b"")


def algorithm(kind, parameters=b""):
    return seq(oid(kind), parameters)


def plain_signer_info(digest=SHA256, unsigned=b"", version=None):
    return seq(version or integer(1), seq(ISSUER, integer(5)), algorithm(digest), algorithm(RSA, NULL),
               der(0x04, b"timestamp signature"), unsigned)


def timestamp_token(digest=SHA256, unsigned=b"", crls=b"", version=None, digest_set=None):
    """An RFC 3161 token: a SignedData of a TSTInfo with one SignerInfo."""
    body = seq(version or integer(3), der(0x31, digest_set if digest_set is not None else algorithm(digest)),
               seq(oid(TST_INFO), der(0xA0, der(0x04, b"tst"))),
               der(0xA0, b""), crls, der(0x31, plain_signer_info(digest, unsigned)))
    return seq(oid(authenticode.OID_SIGNED_DATA), der(0xA0, body))


def attribute(kind, *values):
    return seq(oid(kind), der(0x31, b"".join(values)))


def signer_info(serial=1001, issuer=ISSUER, sid=None, digest=SHA256, timestamp=True, attributes=None, version=None,
                digest_algorithm=None, signature_algorithm=None):
    if attributes is None:
        attributes = [attribute(authenticode.OID_RFC3161_TIMESTAMP, timestamp_token())] if timestamp else []
    unsigned = der(0xA1, b"".join(attributes)) if attributes else b""
    return seq(version or integer(1), sid if sid is not None else seq(issuer, integer(serial)),
               digest_algorithm or algorithm(digest, NULL), signature_algorithm or algorithm(RSA, NULL),
               der(0x04, b"signature"), unsigned)


def signed_data(infos, certificates, file_digest=SHA256, crls=b"", version=None, digest_set=None, signer_digest=SHA256):
    content = seq(oid(authenticode.OID_SPC_INDIRECT_DATA),
                  der(0xA0, seq(seq(oid((1, 3, 6, 1, 4, 1, 311, 2, 1, 15))), seq(seq(oid(file_digest)), der(0x04, b"d")))))
    body = seq(version or integer(1), der(0x31, digest_set if digest_set is not None else algorithm(signer_digest, NULL)),
               content, der(0xA0, b"".join(certificates)), crls, der(0x31, b"".join(infos)))
    return memoryview(seq(oid(authenticode.OID_SIGNED_DATA), der(0xA0, body)))


class SignatureStructureTests(unittest.TestCase):
    """Signatures built here, byte by byte, for the cases that no signing tool makes."""

    def test_a_well_formed_signature_is_read(self):
        found = authenticode.read_signatures(signed_data([signer_info()], [certificate(1001)]))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].signer.serial, 1001)
        self.assertTrue(found[0].timestamped)
        self.assertEqual(found[0].file_digest, SHA256)
        self.assertEqual(found[0].signer_digest, SHA256)

    def test_two_signer_infos_are_refused(self):
        with self.assertRaisesRegex(authenticode.DerError, "2 SignerInfos, not exactly one"):
            authenticode.read_signatures(signed_data([signer_info(), signer_info()], [certificate(1001)]))

    def test_a_key_identifier_sid_is_refused(self):
        with self.assertRaisesRegex(authenticode.DerError, "by a key identifier"):
            authenticode.read_signatures(signed_data([signer_info(sid=der(0x80, b"key-id"))], [certificate(1001)]))

    def test_a_certificate_with_the_serial_but_another_issuer_is_refused(self):
        with self.assertRaisesRegex(authenticode.DerError, "has another issuer than the SignerInfo names"):
            authenticode.read_signatures(signed_data([signer_info()], [certificate(1001, issuer=OTHER_ISSUER)]))

    def test_two_different_certificates_with_the_serial_are_refused(self):
        with self.assertRaisesRegex(authenticode.DerError, "2 different certificates"):
            authenticode.read_signatures(signed_data(
                [signer_info()], [certificate(1001), certificate(1001, issuer=OTHER_ISSUER)]))

    def test_no_timestamp_is_seen(self):
        found = authenticode.read_signatures(signed_data([signer_info(timestamp=False)], [certificate(1001)]))
        self.assertFalse(found[0].timestamped)

    def test_the_digest_algorithms_are_read_and_md5_is_refused(self):
        md5 = (1, 2, 840, 113549, 2, 5)
        for file_digest, signer_digest in ((md5, SHA256), (SHA256, md5)):
            with self.subTest(file=file_digest, signer=signer_digest):
                found = authenticode.read_signatures(
                    signed_data([signer_info(digest=signer_digest)], [certificate(1001)], file_digest=file_digest,
                                signer_digest=signer_digest))
                with self.assertRaisesRegex(authenticode.DerError, "uses md5"):
                    authenticode.check_digests(found[0], ["sha256", "sha1"])

    def test_content_that_is_not_authenticode_is_refused(self):
        data = bytes(signed_data([signer_info()], [certificate(1001)]))
        spc = bytes(oid(authenticode.OID_SPC_INDIRECT_DATA))
        other = bytes(oid((1, 3, 6, 1, 4, 1, 311, 2, 1, 99)))
        self.assertEqual(len(spc), len(other))
        with self.assertRaisesRegex(authenticode.DerError, "not Authenticode's SpcIndirectDataContent"):
            authenticode.read_signatures(memoryview(data.replace(spc, other)))

    def read(self, **info):
        return authenticode.read_signatures(signed_data([signer_info(**info)], [certificate(1001)]))

    def test_an_unsigned_attribute_of_another_kind_is_refused_and_named(self):
        # The reader's E10: bytes of anyone's choosing in an unsigned attribute.
        extra = attribute((1, 3, 6, 1, 4, 1, 55555, 1), der(0x04, b"not signed by the publisher" * 20))
        with self.assertRaisesRegex(authenticode.DerError, r"unsigned attribute 1\.3\.6\.1\.4\.1\.55555\.1, which is "
                                                           "not one of the allowed kinds"):
            self.read(attributes=[attribute(authenticode.OID_RFC3161_TIMESTAMP, timestamp_token()), extra])

    def test_a_repeated_or_a_second_timestamp_is_refused(self):
        token = attribute(authenticode.OID_RFC3161_TIMESTAMP, timestamp_token())
        with self.assertRaisesRegex(authenticode.DerError, "twice"):
            self.read(attributes=[token, token])
        with self.assertRaisesRegex(authenticode.DerError, "has 2 values"):
            self.read(attributes=[attribute(authenticode.OID_RFC3161_TIMESTAMP, timestamp_token(), timestamp_token())])
        with self.assertRaisesRegex(authenticode.DerError, "more than one timestamp"):
            self.read(attributes=[token, attribute(authenticode.OID_COUNTERSIGNATURE, plain_signer_info())])

    def test_the_older_countersignature_is_a_timestamp(self):
        found = self.read(attributes=[attribute(authenticode.OID_COUNTERSIGNATURE, plain_signer_info())])
        self.assertTrue(found[0].timestamped)
        self.assertEqual(found[0].timestamp_digest, SHA256)

    def test_a_timestamp_with_unsigned_attributes_of_its_own_is_refused(self):
        inner = der(0xA1, attribute((1, 3, 6, 1, 4, 1, 55555, 1), der(0x04, b"x")))
        with self.assertRaisesRegex(authenticode.DerError, "55555"):
            self.read(attributes=[attribute(authenticode.OID_RFC3161_TIMESTAMP, timestamp_token(unsigned=inner))])
        inner = der(0xA1, attribute(authenticode.OID_RFC3161_TIMESTAMP, timestamp_token()))
        with self.assertRaisesRegex(authenticode.DerError, "the timestamp's SignerInfo carries unsigned attributes"):
            self.read(attributes=[attribute(authenticode.OID_COUNTERSIGNATURE, plain_signer_info(unsigned=inner))])

    def test_a_crl_field_is_refused_in_the_signature_and_in_the_timestamp(self):
        crls = der(0xA1, seq(integer(1)))
        with self.assertRaisesRegex(authenticode.DerError, "the signature carries a CRL field"):
            authenticode.read_signatures(signed_data([signer_info()], [certificate(1001)], crls=crls))
        with self.assertRaisesRegex(authenticode.DerError, "the timestamp token carries a CRL field"):
            self.read(attributes=[attribute(authenticode.OID_RFC3161_TIMESTAMP, timestamp_token(crls=crls))])

    def test_the_timestamps_digest_is_checked_like_the_others(self):
        sha384 = authenticode.DIGEST_ALGORITHMS["sha384"]
        found = self.read(attributes=[attribute(authenticode.OID_RFC3161_TIMESTAMP, timestamp_token(digest=sha384))])
        self.assertEqual(found[0].timestamp_digest, sha384)
        with self.assertRaisesRegex(authenticode.DerError, "the timestamp's digest uses sha384"):
            authenticode.check_digests(found[0], ["sha256"])
        authenticode.check_digests(found[0], ["sha256", "sha384"])
        md5 = (1, 2, 840, 113549, 2, 5)
        found = self.read(attributes=[attribute(authenticode.OID_RFC3161_TIMESTAMP, timestamp_token(digest=md5))])
        with self.assertRaisesRegex(authenticode.DerError, "the timestamp's digest uses md5"):
            authenticode.check_digests(found[0], ["sha256", "sha1", "sha384", "sha512"])

    def test_algorithm_parameters_must_be_absent_or_null(self):
        junk = der(0x04, b"not signed by the publisher" * 10)
        cases = {
            "a digestAlgorithms entry of the signature": dict(digest_set=algorithm(SHA256, junk)),
            "the digest algorithm of the SignerInfo": dict(info=dict(digest_algorithm=algorithm(SHA256, junk))),
            "the signature algorithm of the SignerInfo": dict(info=dict(signature_algorithm=algorithm(RSA, junk))),
            "the signature algorithm of the SignerInfo ": dict(info=dict(signature_algorithm=algorithm(RSA, NULL + NULL))),
            "the signature algorithm of the SignerInfo  ": dict(info=dict(signature_algorithm=algorithm(
                RSA, der(0x05, b"a NULL that carries bytes")))),
            "a digestAlgorithms entry of the timestamp token": dict(info=dict(attributes=[attribute(
                authenticode.OID_RFC3161_TIMESTAMP, timestamp_token(digest_set=algorithm(SHA256, junk)))])),
        }
        for where, case in cases.items():
            with self.subTest(where=where):
                with self.assertRaisesRegex(authenticode.DerError, "%s has parameters other than NULL" % where.strip()):
                    authenticode.read_signatures(signed_data([signer_info(**case.get("info", {}))], [certificate(1001)],
                                                             digest_set=case.get("digest_set")))
        # NULL and no parameters both pass (the real signatures carry both)
        authenticode.read_signatures(signed_data([signer_info(digest_algorithm=algorithm(SHA256))], [certificate(1001)],
                                                 digest_set=algorithm(SHA256)))
        self.assertEqual(authenticode.algorithm_of(memoryview(algorithm(SHA256, NULL)),
                                                   (0x30, 0, 2, len(algorithm(SHA256, NULL))), "x"), SHA256)

    def test_digest_algorithms_hold_exactly_the_signers(self):
        sha1 = authenticode.DIGEST_ALGORITHMS["sha1"]
        for name, digest_set in (("an extra entry", algorithm(SHA256, NULL) + algorithm(SHA256, NULL)),
                                 ("another algorithm", algorithm(sha1, NULL)), ("none", b"")):
            with self.subTest(case=name):
                with self.assertRaisesRegex(authenticode.DerError, "digestAlgorithms of the signature hold"):
                    authenticode.read_signatures(signed_data([signer_info()], [certificate(1001)], digest_set=digest_set))
        with self.assertRaisesRegex(authenticode.DerError, "digestAlgorithms of the timestamp token hold"):
            self.read(attributes=[attribute(authenticode.OID_RFC3161_TIMESTAMP, timestamp_token(
                digest_set=algorithm(SHA256) + algorithm(sha1)))])

    def test_versions_are_the_small_integers_that_the_standards_allow(self):
        big = der(0x02, b"\x01" + b"R" * 200)
        padded = der(0x02, b"\x00\x01")
        for name, value in (("a long integer", big), ("a padded 1", padded), ("2", integer(2))):
            with self.subTest(field="SignedData", case=name):
                with self.assertRaisesRegex(authenticode.DerError, "the version of the signature is not 1"):
                    authenticode.read_signatures(signed_data([signer_info()], [certificate(1001)], version=value))
            with self.subTest(field="SignerInfo", case=name):
                with self.assertRaisesRegex(authenticode.DerError, "the version of the SignerInfo is not 1"):
                    self.read(version=value)
            with self.subTest(field="timestamp token", case=name):
                with self.assertRaisesRegex(authenticode.DerError, "the version of the timestamp token is not 3"):
                    self.read(attributes=[attribute(authenticode.OID_RFC3161_TIMESTAMP, timestamp_token(version=value))])
            with self.subTest(field="timestamp SignerInfo", case=name):
                with self.assertRaisesRegex(authenticode.DerError, "the version of the timestamp's SignerInfo is not 1"):
                    self.read(attributes=[attribute(authenticode.OID_COUNTERSIGNATURE, plain_signer_info(version=value))])
        with self.assertRaisesRegex(authenticode.DerError, "the version of the timestamp token is not 3"):
            self.read(attributes=[attribute(authenticode.OID_RFC3161_TIMESTAMP, timestamp_token(version=integer(1)))])
        self.assertEqual(authenticode.SIGNATURE_SIGNED_DATA_VERSIONS, (1,))
        self.assertEqual(authenticode.TOKEN_SIGNED_DATA_VERSIONS, (3,))
        self.assertEqual(authenticode.SIGNER_INFO_VERSIONS, (1,))

    def test_a_field_that_is_not_named_must_be_absent(self):
        signer = authenticode.read_signatures(signed_data([signer_info()], [certificate(1001)]))[0].signer
        authenticode.check_signer(signer, {"CN": "Example, Inc.", "O": "Example, Inc.", "C": "AT"})
        with_l = certificate(1001, subject=name(((2, 5, 4, 6), "AT"), ((2, 5, 4, 7), "Linz"),
                                                ((2, 5, 4, 10), "Example, Inc."), ((2, 5, 4, 3), "Example, Inc.")))
        signer = authenticode.read_signatures(signed_data([signer_info()], [with_l]))[0].signer
        with self.assertRaisesRegex(authenticode.DerError, "has a field L, which the recipe does not name"):
            authenticode.check_signer(signer, {"CN": "Example, Inc.", "O": "Example, Inc.", "C": "AT"})
        authenticode.check_signer(signer, {"CN": "Example, Inc.", "O": "Example, Inc.", "L": "Linz", "C": "AT"})


SAMPLES = os.environ.get("AUTHENTICODE_SAMPLES", "")
REPOSITORY_DIR = os.path.dirname(PROCESSOR_DIR)


def recipe_steps():
    """(folder, arguments) of every AuthenticodeVerifier step of a download recipe of this repository."""
    import plistlib
    found = []
    for folder in sorted(os.listdir(REPOSITORY_DIR)):
        path = os.path.join(REPOSITORY_DIR, folder)
        if not os.path.isdir(path):
            continue
        for name in sorted(os.listdir(path)):
            if not name.endswith(".download.recipe"):
                continue
            with open(os.path.join(path, name), "rb") as handle:
                recipe = plistlib.load(handle)
            for step in recipe["Process"]:
                if step["Processor"].endswith("/AuthenticodeVerifier"):
                    found.append((folder, step["Arguments"]))
    return found


@unittest.skipUnless(SAMPLES and OSSLSIGNCODE, "set AUTHENTICODE_SAMPLES to a folder of real installers "
                     "(<folder>.exe or <folder>.msi, e.g. Win-Scratch.exe); needs osslsigncode and the network")
class RealSampleTests(unittest.TestCase):
    """Each recipe's step on a real installer that a person downloaded: it must pass, and a copy with one
    byte changed must not. The CRLs are fetched over the network. Never run by default."""

    def test_each_recipes_step_on_its_real_installer(self):
        checked = 0
        for folder, arguments in recipe_steps():
            for extension in authenticode.SIGNED_EXTENSIONS:
                sample = os.path.join(SAMPLES, folder + extension)
                if not os.path.isfile(sample):
                    continue
                checked += 1
                env = dict(arguments)
                env["pathname"] = sample
                with self.subTest(folder=folder):
                    processor, _ = new_processor(PROCESSOR, env)
                    processor.main()
                    self.assertEqual(processor.env["signature_sha256"], sha256_hex(sample))
                    work = tempfile.mkdtemp()
                    self.addCleanup(shutil.rmtree, work)
                    changed = os.path.join(work, os.path.basename(sample))
                    shutil.copyfile(sample, changed)
                    with open(changed, "r+b") as handle:
                        middle = os.path.getsize(changed) // 2
                        handle.seek(middle)
                        byte = handle.read(1)
                        handle.seek(middle)
                        handle.write(bytes([byte[0] ^ 1]))
                    env["pathname"] = changed
                    processor, _ = new_processor(PROCESSOR, env)
                    with self.assertRaises(ProcessorError):
                        processor.main()
        self.assertGreater(checked, 0, "no sample named after a recipe folder was found")


class RecipeStepTests(unittest.TestCase):
    """Every download recipe of this repository that has the step names pinned roots and the required fields."""

    def test_every_step_is_complete(self):
        steps = recipe_steps()
        self.assertTrue(steps)
        for folder, arguments in steps:
            with self.subTest(folder=folder):
                self.assertEqual(set(arguments) - set(PROCESSOR.input_variables), set())
                for name in arguments["code_signing_roots"] + arguments["timestamp_roots"]:
                    self.assertIn(name, authenticode.PINNED_ROOTS)
                for field in authenticode.REQUIRED_SIGNER_FIELDS:
                    self.assertIn(field, arguments["expected_signer"])
                self.assertEqual(authenticode.digest_input(arguments.get("digest_algorithms")),
                                 [name.lower() for name in arguments.get("digest_algorithms", ["sha256"])])


class InputTests(unittest.TestCase):
    """What is refused before the tool runs."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)
        self.path = os.path.join(self.folder, "setup.exe")
        with open(self.path, "wb") as handle:
            handle.write(build_pe())
        self.tool_folders = (os.path.join(self.folder, "no-tool-here"),)

    def refused(self, fragment, **overrides):
        env = {"pathname": self.path, "expected_signer": {"CN": "Example", "O": "Example", "C": "US"},
               "code_signing_roots": ["digicert-trusted-root-g4"], "timestamp_roots": ["digicert-trusted-root-g4"]}
        env.update(overrides)
        processor, _ = new_processor(PROCESSOR, env)
        with self.assertRaises(ProcessorError) as caught, \
                mock.patch.object(authenticode, "TOOL_FOLDERS", self.tool_folders):
            processor.main()
        self.assertIn(fragment, str(caught.exception))
        self.assertNotIn("signature_verified", processor.env)
        return str(caught.exception)

    def test_a_missing_file(self):
        self.refused("pathname is not a file", pathname=os.path.join(self.folder, "missing.exe"))

    def test_another_kind_of_file(self):
        other = os.path.join(self.folder, "setup.zip")
        shutil.copyfile(self.path, other)
        self.refused("only .exe and .msi files are checked", pathname=other)

    def test_the_expected_signer_must_give_cn_o_and_c_and_nothing_unknown(self):
        self.refused("it lacks O", expected_signer={"CN": "Example", "C": "US"})
        self.refused("fields that are not compared: E", expected_signer={"CN": "Example", "O": "Example", "C": "US",
                                                                        "E": "x"})
        self.refused("must be a dictionary", expected_signer="CN=Example")
        self.refused("without white space", expected_signer={"CN": " Example", "O": "Example", "C": "US"})
        self.refused("without white space", expected_signer={"CN": "", "O": "Example", "C": "US"})

    def test_roots_must_be_pinned_names(self):
        self.refused("is not a pinned root", code_signing_roots=["example-root"])
        self.refused("names no root", timestamp_roots=[])
        self.refused("must be a list", code_signing_roots=5)

    def test_a_missing_tool_is_a_clear_error(self):
        message = self.refused("osslsigncode was not found in")
        self.assertIn("brew install osslsigncode", message)

    def test_no_input_or_path_names_the_tool(self):
        self.assertNotIn("osslsigncode_path", PROCESSOR.input_variables)
        self.assertEqual(authenticode.TOOL_FOLDERS, ("/opt/homebrew/bin", "/usr/local/bin"))
        script = os.path.join(self.folder, "osslsigncode")
        with open(script, "w") as handle:
            handle.write("#!/bin/sh\necho 'osslsigncode 9.9, using:'\n")
        os.chmod(script, 0o755)
        # a program on the PATH, or named by an input, is not taken
        with mock.patch.dict(os.environ, {"PATH": self.folder}):
            self.refused("osslsigncode was not found in", **{"osslsigncode_path": script})

    def test_a_tool_that_is_too_old_is_refused(self):
        script = os.path.join(self.folder, "osslsigncode")
        with open(script, "w") as handle:
            handle.write("#!/bin/sh\necho 'osslsigncode 2.5, using:'\necho '\tOpenSSL 3.0.0'\n")
        os.chmod(script, 0o755)
        self.tool_folders = (self.folder,)
        self.refused("is version 2.5; this processor needs 2.16 or later")

    def test_the_digest_algorithms_are_names_and_md5_is_never_accepted(self):
        for value, fragment in ((["md5"], "MD5 is never accepted"), ("sha256, MD5", "MD5 is never accepted"),
                                (["sha3"], "it names sha3"), ([], "it names none"), (5, "must be a list")):
            with self.subTest(value=value):
                self.refused(fragment, digest_algorithms=value)
        self.assertEqual(authenticode.digest_input(None), ["sha256"])
        self.assertEqual(authenticode.digest_input("SHA256, sha1"), ["sha256", "sha1"])
        self.assertNotIn("md5", authenticode.DIGEST_ALGORITHMS)

class PinnedRootTests(unittest.TestCase):
    """The roots that ship beside the processor."""

    def test_every_pinned_root_file_has_its_pinned_hash_and_is_self_signed(self):
        for name, (filename, pinned) in authenticode.PINNED_ROOTS.items():
            with self.subTest(root=name):
                der, serial = authenticode.load_root(name)
                self.assertEqual(hashlib.sha256(der).hexdigest(), pinned)
                data = memoryview(der)
                certificate = authenticode.Certificate(data, authenticode.elements(data, 0, len(data))[0])
                self.assertEqual(serial, certificate.serial)
                self.assertEqual(certificate.issuer_fields, certificate.subject)

    def test_every_pinned_root_file_is_beside_the_processor_and_nothing_else_is(self):
        files = sorted(name for name in os.listdir(PROCESSOR_DIR) if name.endswith(".pem"))
        expected = sorted([filename for filename, _ in authenticode.PINNED_ROOTS.values()] +
                          ["microsoft-root-2011.pem"])
        self.assertEqual(files, expected)

    def test_a_file_with_two_certificates_is_refused(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        source = os.path.join(PROCESSOR_DIR, "digicert-trusted-root-g4.pem")
        with open(source) as handle:
            text = handle.read()
        with open(os.path.join(folder, "digicert-trusted-root-g4.pem"), "w") as handle:
            handle.write(text + text)
        with self.assertRaises(ProcessorError) as caught:
            authenticode.load_root("digicert-trusted-root-g4", folder=folder)
        self.assertIn("holds 2 certificates", str(caught.exception))

    def test_a_file_with_another_certificate_is_refused(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        shutil.copyfile(os.path.join(PROCESSOR_DIR, "globalsign-code-signing-root-r45.pem"),
                        os.path.join(folder, "digicert-trusted-root-g4.pem"))
        with self.assertRaises(ProcessorError) as caught:
            authenticode.load_root("digicert-trusted-root-g4", folder=folder)
        self.assertIn("does not have the SHA-256 written for digicert-trusted-root-g4", str(caught.exception))


class DerTests(unittest.TestCase):
    """The reader takes DER only, and never reads past what holds an element."""

    def test_an_indefinite_length_is_refused(self):
        with self.assertRaises(authenticode.DerError):
            authenticode.read_element(b"\x30\x80\x00\x00", 0, 4)

    def test_a_length_past_the_end_is_refused(self):
        with self.assertRaises(authenticode.DerError):
            authenticode.read_element(b"\x30\x05\x00", 0, 3)

    def test_a_long_form_for_a_short_length_is_refused(self):
        with self.assertRaises(authenticode.DerError):
            authenticode.read_element(b"\x04\x81\x01\x00", 0, 4)

    def test_an_object_identifier(self):
        self.assertEqual(authenticode.decode_oid(bytes.fromhex("2a864886f70d010702")),
                         authenticode.OID_SIGNED_DATA)

    def test_something_that_is_not_a_signature_is_refused(self):
        for data in (b"", b"\x30\x00", b"\x30\x03\x06\x01\x2a", b"\x04\x00"):
            with self.subTest(data=data):
                with self.assertRaises(authenticode.DerError):
                    authenticode.read_signatures(memoryview(data))

    def test_name_values_of_each_string_type(self):
        cases = ((0x0C, "Oberösterreich".encode("utf-8")), (0x13, b"Example"), (0x16, b"Example"),
                 (0x1E, "Oberösterreich".encode("utf-16-be")), (0x1C, "Göppingen".encode("utf-32-be")))
        for tag, raw in cases:
            with self.subTest(tag=tag):
                self.assertIn(authenticode.decode_name_value(tag, raw, "L"),
                              ("Oberösterreich", "Example", "Göppingen"))
        with self.assertRaises(authenticode.DerError):
            authenticode.decode_name_value(0x14, b"Example", "O")  # TeletexString is not read
        with self.assertRaises(authenticode.DerError):
            authenticode.decode_name_value(0x13, "ö".encode("utf-8"), "O")


class OutputTests(unittest.TestCase):
    """The reading of the tool's output, on made-up text in its layout."""

    BLOCK = (
        "Signature Index: {index}{primary}\n\n"
        "Timestamp verified using:\n\t------------------\n\tSigner #1:\n\t\tSubject: CN=Root\n\t\tSerial : 0A\n"
        "\t------------------\n\tSigner #0:\n\t\tSubject: CN=TSA\n\t\tSerial : 0B\n\n"
        "TSA's CRL distribution point: http://example.invalid/a.crl\n"
        "Timestamp Server Signature CRL verification: ok\n"
        "Timestamp Server Signature verification: ok\n"
        "Signature verification time: Jan  2 12:00:00 2025 GMT\n"
        "Signing certificate chain verified using:\n\t------------------\n\tSigner #1:\n\t\tSubject: CN=Root\n"
        "\t\tSerial : 0C\n\t------------------\n\tSigner #0:\n\t\tSubject: CN=Leaf\n\t\tSerial : 03E9\n\n"
        "CRL distribution point: http://example.invalid/b.crl\n"
        "Signature CRL verification: ok\nSignature verification: ok\n\n"
    )

    def output(self, count=1, tail="Number of verified signatures: {count}\nSucceeded\n"):
        blocks = "".join(self.BLOCK.format(index=i, primary="  (Primary Signature)" if i == 0 else " ")
                         for i in range(count))
        return blocks + tail.format(count=count)

    def test_a_complete_output(self):
        blocks = authenticode.read_verify_output(self.output(), 1)
        self.assertEqual(blocks, [("Jan  2 12:00:00 2025 GMT", [0x3E9, 0x0C], [0x0B, 0x0A])])

    def test_two_signatures(self):
        self.assertEqual(len(authenticode.read_verify_output(self.output(2), 2)), 2)

    def test_each_required_line_is_needed(self):
        for line in authenticode.REQUIRED_BLOCK_LINES + (authenticode.CODE_CHAIN_HEADER,
                                                         authenticode.TIMESTAMP_CHAIN_HEADER):
            with self.subTest(line=line):
                with self.assertRaises(authenticode.DerError):
                    authenticode.read_verify_output(self.output().replace(line + "\n", "", 1), 1)

    def test_no_timestamp_is_refused(self):
        with self.assertRaises(authenticode.DerError):
            authenticode.read_verify_output(self.output().replace("Signature verification time",
                                                                  "Timestamp is not available\nSignature verification time"), 1)

    def test_a_count_that_differs_from_the_file_is_refused(self):
        with self.assertRaises(authenticode.DerError):
            authenticode.read_verify_output(self.output(1), 2)
        with self.assertRaises(authenticode.DerError):
            authenticode.read_verify_output(self.output(2), 1)

    def test_signatures_out_of_order_are_refused(self):
        text = self.output(2).replace("Signature Index: 1", "Signature Index: 3")
        with self.assertRaises(authenticode.DerError):
            authenticode.read_verify_output(text, 2)

    def test_an_msi_must_show_its_extended_signature_and_the_two_values_must_agree(self):
        good = ("Current MsiDigitalSignatureEx    : AB12 \nCalculated MsiDigitalSignatureEx : AB12 \n"
                "Current DigitalSignature         : CD34 \n")
        authenticode.read_verify_output(good + self.output(), 1, msi=True)
        with self.assertRaisesRegex(authenticode.DerError, "has no MsiDigitalSignatureEx"):
            authenticode.read_verify_output("Warning: MsiDigitalSignatureEx stream doesn't exist\n" + self.output(), 1,
                                            msi=True)
        with self.assertRaisesRegex(authenticode.DerError, "printed 2 line"):
            authenticode.read_verify_output(good + good + self.output(), 1, msi=True)
        with self.assertRaisesRegex(authenticode.DerError, "does not match"):
            authenticode.read_verify_output(good.replace("Calculated MsiDigitalSignatureEx : AB12",
                                                         "Calculated MsiDigitalSignatureEx : AB13") + self.output(),
                                            1, msi=True)
        # a PE file's output has no such lines, and needs none
        authenticode.read_verify_output(self.output(), 1)

    def test_a_chain_with_a_gap_in_its_numbers_is_not_read(self):
        text = self.output().replace("Signer #1:\n\t\tSubject: CN=Root\n\t\tSerial : 0C", "Signer #2:\n\t\tSubject: "
                                     "CN=Root\n\t\tSerial : 0C")
        with self.assertRaises(authenticode.DerError):
            authenticode.read_verify_output(text, 1)


if __name__ == "__main__":
    unittest.main()
