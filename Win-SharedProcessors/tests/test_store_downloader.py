"""Tests of MicrosoftStorePackageDownloader. No test uses the network: the lowest function
(open_request) or the functions above it (fetch_bytes, soap_post, file_urls) are replaced.

The catalog record is made up (ExamplePublisher.ExampleApp) in the shape of the catalog's
answer as it was read on 2026-11-13: two SKUs naming the same one package, FulfillmentData as
a record, the version as one 64-bit number in text. The delivery service's answers are written
by hand in the shape that the ported tool reads; the service itself was never asked by these
tests or by the person who wrote them."""
import base64
import hashlib
import json
import os
import shutil
import ssl
import tempfile
import unittest
import urllib.error
from unittest import mock

from _win_support import PROCESSOR_DIR, ProcessorError, new_processor, run_processor

import MicrosoftStorePackageDownloader as store  # noqa: E402  (after _win_support: the autopkglib stand-in)

DOWNLOADER = store.MicrosoftStorePackageDownloader
PRODUCT = "9EXAMPLE0APP"
PACKAGE_BODY = b"made-up package bytes, not a real bundle\n" * 100
WANTED = hashlib.sha256(PACKAGE_BODY).hexdigest()
FULL_NAME = "ExamplePublisher.ExampleApp_2026.1028.1836.0_neutral_~_abcdefghjk123"
CATEGORY = "11111111-2222-3333-4444-555555555555"
UPDATE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
FILE_URL = "http://tlu.dl.delivery.mp.microsoft.com/filestreamingservice/files/example-file-of-the-test?P1=1"
OTHER_URL = "http://tlu.dl.delivery.mp.microsoft.com/filestreamingservice/files/another-file-of-the-test?P1=2"


def packed(*parts):
    """Four numbers as the catalog's one 64-bit number."""
    value = 0
    for part in parts:
        value = (value << 16) | part
    return value


def package_record(**changes):
    record = {
        "PackageFullName": FULL_NAME,
        "PackageFormat": "MsixBundle",
        "Hash": base64.b64encode(bytes.fromhex(WANTED)).decode("ascii"),
        "HashAlgorithm": "SHA256",
        "MaxDownloadSizeInBytes": len(PACKAGE_BODY),
        "Version": str(packed(2026, 1028, 1836, 0)),
        "FrameworkDependencies": [
            {"MaxTested": 0, "MinVersion": packed(4000, 1309, 2056, 0), "PackageIdentity": "Example.Runtime.1.4"}
        ],
        "FulfillmentData": {"ProductId": PRODUCT, "WuCategoryId": CATEGORY, "SkuId": "0010"},
    }
    for key, value in changes.items():
        if value is KeyError:
            record.pop(key, None)
        else:
            record[key] = value
    return record


def catalog(*sku_packages):
    if not sku_packages:
        sku_packages = ([package_record()], [package_record()])
    return {
        "Product": {
            "ProductId": PRODUCT,
            "LocalizedProperties": [{"ProductTitle": "Example App"}],
            "DisplaySkuAvailabilities": [
                {"Sku": {"Properties": {"Packages": packages}}} for packages in sku_packages
            ],
        }
    }


def update_info(leaf, update_id=UPDATE_ID, revision="1", number="77"):
    """One UpdateInfo of a SyncUpdates answer; the inner XML escaped, as the service sends it."""
    inner = (
        '<UpdateIdentity UpdateID="%s" RevisionNumber="%s" /><Properties />'
        % (update_id, revision)
    )
    if leaf:
        inner += "<SecuredFragment>x</SecuredFragment>"
    escaped = inner.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return "<UpdateInfo><ID>%s</ID><IsLeaf>%s</IsLeaf><Xml>%s</Xml></UpdateInfo>" % (
        number, "true" if leaf else "false", escaped)


def sync_answer(*infos):
    return "<s:Envelope><s:Body><SyncUpdatesResponse><NewUpdates>%s</NewUpdates></SyncUpdatesResponse></s:Body></s:Envelope>" % "".join(infos)


COOKIE_ANSWER = (
    "<s:Envelope><s:Body><GetCookieResponse><GetCookieResult>"
    "<Expiration>2036-01-01T00:00:00Z</Expiration>\n<EncryptedData>QUJDRA==</EncryptedData>"
    "</GetCookieResult></GetCookieResponse></s:Body></s:Envelope>"
)


def extended_answer(*urls):
    return "<s:Envelope><FileLocations>%s</FileLocations></s:Envelope>" % "".join(
        "<FileLocation><Url>%s</Url></FileLocation>" % url.replace("&", "&amp;") for url in urls)


class FakeResponse:
    """Stands in for an HTTP response: a body, headers, and an optional failure after
    the first block."""

    def __init__(self, body, headers=None, fail_after_first=None):
        self.body = body
        self.position = 0
        self.headers = headers if headers is not None else {}
        self.fail_after_first = fail_after_first
        self.reads = 0

    def read(self, size=-1):
        self.reads += 1
        if self.fail_after_first is not None and self.reads > 1:
            raise self.fail_after_first
        if size is None or size < 0:
            size = len(self.body)
        chunk = self.body[self.position:self.position + size]
        self.position += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Network:
    """Stands in for open_request: answers by address, records every call."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, request, context, redirect_handler, timeout):
        self.calls.append((request.full_url, context, redirect_handler, timeout))
        answer = self.answers[request.full_url]
        if isinstance(answer, BaseException):
            raise answer
        if callable(answer):
            return answer()
        return answer


class TempFolderTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="store-test-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.cache = os.path.join(self.folder, "cache")
        self.downloads = os.path.join(self.cache, "downloads")
        os.makedirs(self.downloads)

    def leftovers(self):
        return sorted(name for name in os.listdir(self.downloads))


class CatalogTests(unittest.TestCase):
    def test_a_good_record(self):
        fact = store.parse_catalog(catalog(), PRODUCT)
        self.assertEqual(fact["full_name"], FULL_NAME)
        self.assertEqual(fact["version"], "2026.1028.1836.0")
        self.assertEqual(fact["sha256"], WANTED)
        self.assertEqual(fact["format"], "msixbundle")
        self.assertEqual(fact["category"], CATEGORY)
        self.assertEqual(fact["frameworks"], [("Example.Runtime.1.4", "4000.1309.2056.0")])
        self.assertEqual(fact["title"], "Example App")

    def test_each_format_has_its_extension(self):
        for name, extension in (("MsixBundle", "msixbundle"), ("AppxBundle", "appxbundle"),
                                ("Msix", "msix"), ("Appx", "appx")):
            with self.subTest(format=name):
                record = package_record(PackageFormat=name)
                self.assertEqual(store.parse_catalog(catalog([record]), PRODUCT)["format"], extension)

    def test_version_text_is_the_tools(self):
        self.assertEqual(store.version_text(packed(4000, 1309, 2056, 0)), "4000.1309.2056.0")
        self.assertEqual(store.version_text(0), ".".join(["0"] * 4))  # built: the hygiene test reads it as an address
        with self.assertRaises(ValueError):
            store.version_text(-1)

    def test_the_framework_line(self):
        self.assertEqual(store.framework_text([]), "none")
        self.assertEqual(store.framework_text([("A.B", "1.2.3.400"), ("C", "5.6.7.800")]),
                         "A.B 1.2.3.400 or later; C 5.6.7.800 or later")

    def test_no_framework_list_is_no_framework(self):
        record = package_record(FrameworkDependencies=KeyError)
        self.assertEqual(store.parse_catalog(catalog([record]), PRODUCT)["frameworks"], [])

    def assert_refused(self, document, needle):
        with self.assertRaises(ValueError) as caught:
            store.parse_catalog(document, PRODUCT)
        self.assertIn(needle, str(caught.exception))

    def test_bad_shapes_are_refused(self):
        other_hash = base64.b64encode(hashlib.sha256(b"other").digest()).decode("ascii")
        cases = {
            "no Product": ({}, "no Product record"),
            "another product": ({"Product": dict(catalog()["Product"], ProductId="9OTHER0APP00")}, "not " + PRODUCT),
            "no SKU": ({"Product": dict(catalog()["Product"], DisplaySkuAvailabilities=[])}, "no SKU"),
            "SKU without packages": ({"Product": dict(catalog()["Product"], DisplaySkuAvailabilities=[{"Sku": {}}])},
                                     "no list of packages"),
            "packages not a list": (catalog("x"), "no list of packages"),
            "no package": (catalog([]), "0 different packages"),
            "two packages": (catalog([package_record(), package_record(Hash=other_hash)]), "2 different packages"),
            "SKUs disagree": (catalog([package_record()], [package_record(Hash=other_hash)]), "not exactly one"),
            "SKUs differ in category": (
                catalog([package_record()], [package_record(FulfillmentData={"WuCategoryId": CATEGORY.replace("1", "9")})]),
                "differently"),
            "package not a record": (catalog(["x"]), "not a record"),
            "full name shape": (catalog([package_record(PackageFullName="../evil_1.2.3.400_x64__abcdefghjk123")]),
                                "shape of a package full name"),
            "full name with a slash": (catalog([package_record(PackageFullName="Example/App_1.2.3.400_x64_~_abcdefghjk123")]),
                                       "shape"),
            "version part too large": (catalog([package_record(PackageFullName=FULL_NAME.replace("1028", "70000"),
                                                               Version=KeyError)]), "above 65535"),
            "SHA1": (catalog([package_record(HashAlgorithm="SHA1")]), "not SHA-256"),
            "hash not base64": (catalog([package_record(Hash="not base64!")]), "not base64"),
            "hash not text": (catalog([package_record(Hash=5)]), "not base64"),
            "hash of 20 bytes": (catalog([package_record(Hash=base64.b64encode(b"x" * 20).decode())]), "20 bytes"),
            "unknown format": (catalog([package_record(PackageFormat="Exe")]), "is not one of"),
            "size not a number": (catalog([package_record(MaxDownloadSizeInBytes="big")]), "not a number"),
            "size zero": (catalog([package_record(MaxDownloadSizeInBytes=0)]), "not above zero"),
            "size a boolean": (catalog([package_record(MaxDownloadSizeInBytes=True)]), "not a number"),
            "version differs": (catalog([package_record(Version=str(packed(2026, 1, 1, 0)))]), "not the version"),
            "no FulfillmentData": (catalog([package_record(FulfillmentData=None)]), "no FulfillmentData"),
            "category not a GUID": (catalog([package_record(FulfillmentData={"WuCategoryId": "1 or 1=1"})]), "not a GUID"),
            "fulfillment of another product": (
                catalog([package_record(FulfillmentData={"WuCategoryId": CATEGORY, "ProductId": "9OTHER0APP00"})]),
                "FulfillmentData names product"),
            "framework name": (catalog([package_record(FrameworkDependencies=[{"PackageIdentity": "<x>", "MinVersion": 1}])]),
                               "not a package name"),
            "framework version": (catalog([package_record(FrameworkDependencies=[{"PackageIdentity": "A", "MinVersion": "x"}])]),
                                  "not a number"),
            "framework version too large": (
                catalog([package_record(FrameworkDependencies=[{"PackageIdentity": "A", "MinVersion": 2 ** 64}])]),
                "out of range"),
        }
        for name, (document, needle) in cases.items():
            with self.subTest(case=name):
                self.assert_refused(document, needle)

    def test_the_catalog_address(self):
        self.assertEqual(store.catalog_url(PRODUCT, "US", "en-us"),
                         "https://displaycatalog.mp.microsoft.com/v7.0/products/%s?market=US&languages=en-us" % PRODUCT)
        with self.assertRaises(ValueError):
            store.catalog_url("../x", "US", "en-us")


class DeliveryAnswerTests(unittest.TestCase):
    def test_the_cookie(self):
        self.assertEqual(store.parse_cookie(COOKIE_ANSWER), ("2036-01-01T00:00:00Z", "QUJDRA=="))

    def test_bad_cookies(self):
        for text, needle in (
            ("<x/>", "no cookie"),
            ("<Expiration>soon</Expiration><EncryptedData>QUJD</EncryptedData>", "not a time"),
            ("<Expiration>2036-01-01T00:00:00Z</Expiration><EncryptedData>a&amp;b</EncryptedData>", "not base64"),
        ):
            with self.subTest(text=text):
                with self.assertRaises(ValueError) as caught:
                    store.parse_cookie(text)
                self.assertIn(needle, str(caught.exception))

    def test_leaf_and_nonleaf_updates(self):
        leaves, nonleaf = store.parse_sync(sync_answer(
            update_info(False, number="123456"), update_info(True), update_info(True)))
        self.assertEqual(leaves, [(UPDATE_ID, "1")])
        self.assertEqual(nonleaf, [123456])

    def test_a_leaf_without_a_secured_fragment_is_not_taken(self):
        answer = sync_answer(update_info(True)).replace("SecuredFragment", "OtherFragment")
        self.assertEqual(store.parse_sync(answer), ([], []))

    def test_bad_update_answers(self):
        for answer, needle in (
            (sync_answer(update_info(True, update_id="not-a-guid")), "not a GUID"),
            (sync_answer(update_info(True, update_id=UPDATE_ID + '" x="')), "no UpdateIdentity"),
            (sync_answer(update_info(True, update_id=UPDATE_ID + "0")), "not a GUID"),
            (sync_answer(update_info(True, revision="1x")), "not digits"),
            (sync_answer(update_info(False, number="12a")), "not digits"),
            (sync_answer(*[update_info(True, update_id=UPDATE_ID[:-4] + "%04x" % n) for n in range(store.MAX_LEAF_UPDATES + 1)]),
             "more than"),
        ):
            with self.subTest(needle=needle):
                with self.assertRaises(ValueError) as caught:
                    store.parse_sync(answer)
                self.assertIn(needle, str(caught.exception))

    def test_block_maps_are_left_out(self):
        blockmap = "http://example.dl.delivery.mp.microsoft.com/" + "b" * (store.BLOCKMAP_URL_LENGTH - 44)
        self.assertEqual(len(blockmap), store.BLOCKMAP_URL_LENGTH)
        self.assertEqual(store.parse_file_urls(extended_answer(FILE_URL, blockmap, OTHER_URL + "&x=1")),
                         [FILE_URL, OTHER_URL + "&x=1"])

    def test_what_is_put_into_xml_is_escaped(self):
        body = store.sync_body(("2036-01-01T00:00:00Z", "QUJD"), "a<b&c", [1, 2])
        self.assertIn("<Id>a&lt;b&amp;c</Id>", body)
        self.assertIn("<int>1</int><int>2</int>", body)
        self.assertIn("<UpdateID>x&lt;y</UpdateID>", store.extended_body("x<y", "1"))
        self.assertIn("<a:To s:mustUnderstand=\"1\">a&amp;b</a:To>", store.envelope("GetCookie", "a&b", ""))

    def test_the_constants_of_the_tool_are_kept(self):
        self.assertEqual(len(store.INSTALLED_NONLEAF_UPDATE_IDS), 48)
        self.assertEqual(store.INSTALLED_NONLEAF_UPDATE_IDS[:5], (1, 2, 3, 11, 19))
        self.assertTrue(store.DEVICE_ATTRIBUTES.startswith("E:BranchReadinessLevel=CBB&amp;"))
        self.assertTrue(store.DEVICE_ATTRIBUTES.endswith("&amp;DeviceFamily=Windows.Desktop"))


class FileUrlsTests(unittest.TestCase):
    def run_service(self, sync_answers, extended, calls=None):
        calls = calls if calls is not None else []
        sync_iter = iter(sync_answers)

        def post(url, action, body):
            calls.append((url, action, body))
            if action == "GetCookie":
                return COOKIE_ANSWER
            if action == "SyncUpdates":
                return next(sync_iter)
            return extended

        with mock.patch.object(store, "soap_post", side_effect=post):
            urls = store.file_urls(CATEGORY, now="2026-11-13T00:00:00.000Z")
        return urls, calls

    def test_rounds_until_a_leaf(self):
        urls, calls = self.run_service(
            [sync_answer(update_info(False, number="987654321")), sync_answer(update_info(True))],
            extended_answer(FILE_URL))
        self.assertEqual(urls, [FILE_URL])
        self.assertEqual([action for _, action, _ in calls], ["GetCookie", "SyncUpdates", "SyncUpdates", "GetExtendedUpdateInfo2"])
        self.assertNotIn("<int>987654321</int>", calls[1][2])
        self.assertIn("<int>987654321</int>", calls[2][2])
        self.assertIn("<EncryptedData>QUJDRA==</EncryptedData>", calls[1][2])
        self.assertEqual(calls[3][0], store.DELIVERY_SECURED_URL)
        self.assertEqual(calls[1][0], store.DELIVERY_URL)

    def test_at_most_eight_rounds(self):
        answers = [sync_answer(update_info(False, number=str(1000000 + n))) for n in range(20)]
        calls = []
        with self.assertRaises(ProcessorError) as caught:
            self.run_service(answers, "", calls)
        self.assertIn("named no update", str(caught.exception))
        self.assertEqual(store.SYNC_ROUNDS, 8)
        self.assertEqual([action for _, action, _ in calls], ["GetCookie"] + ["SyncUpdates"] * store.SYNC_ROUNDS)

    def test_no_new_nonleaf_ends_the_rounds(self):
        with self.assertRaises(ProcessorError):
            self.run_service([sync_answer(update_info(False, number="1"))], "")

    def test_a_bad_answer_is_named(self):
        with self.assertRaises(ProcessorError) as caught:
            self.run_service([sync_answer(update_info(True, revision="x"))], "")
        self.assertIn("SyncUpdates", str(caught.exception))


class HostRuleTests(unittest.TestCase):
    SUFFIXES = store.DEFAULT_FILE_HOST_SUFFIXES

    def test_allowed_addresses(self):
        for url in (FILE_URL, "https://example.dl.delivery.mp.microsoft.com/x", "http://download.microsoft.com/x",
                    "http://tlu.dl.delivery.mp.microsoft.com:80/x"):
            with self.subTest(url=url):
                store.check_file_url(url, self.SUFFIXES)

    def test_refused_addresses_name_the_host(self):
        for url, needle in (
            ("http://files.example.test/x", "files.example.test"),
            ("http://evilmicrosoft.com/x", "evilmicrosoft.com"),
            ("http://microsoft.com.example.test/x", "microsoft.com.example.test"),
            ("ftp://download.microsoft.com/x", "scheme ftp"),
            ("file:///etc/passwd", "scheme file"),
            ("http://user@download.microsoft.com/x", "user name"),
            ("http://download.microsoft.com:8080/x", "port 8080"),
        ):
            with self.subTest(url=url):
                with self.assertRaises(ProcessorError) as caught:
                    store.check_file_url(url, self.SUFFIXES)
                self.assertIn(needle, str(caught.exception))

    def test_the_suffixes_input(self):
        self.assertEqual(store.parse_suffixes(None), list(self.SUFFIXES))
        self.assertEqual(store.parse_suffixes(""), list(self.SUFFIXES))
        self.assertEqual(store.parse_suffixes(".Example.Test, cdn.example.test"), [".example.test", "cdn.example.test"])
        self.assertEqual(store.parse_suffixes([".example.test"]), [".example.test"])
        for bad in ("com", ".example.test/x", "*.example.test", 5, [1]):
            with self.subTest(value=bad):
                with self.assertRaises(ProcessorError):
                    store.parse_suffixes(bad)

    def test_a_redirect_of_a_file_goes_only_to_an_allowed_host(self):
        handler = store.CheckedRedirect(self.SUFFIXES)
        request = mock.Mock(full_url=FILE_URL)
        with self.assertRaises(ProcessorError) as caught:
            handler.redirect_request(request, None, 302, "Found", {}, "http://files.example.test/y")
        self.assertIn("files.example.test", str(caught.exception))

    def test_the_catalog_and_the_service_follow_no_redirect(self):
        self.assertIsNone(store.NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://example.test/"))


class TrustTests(unittest.TestCase):
    PEM = os.path.join(PROCESSOR_DIR, store.PINNED_ROOT_FILE)

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="store-pem-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        with open(self.PEM, "r", encoding="ascii") as handle:
            self.text = handle.read()

    def write(self, text):
        path = os.path.join(self.folder, "root.pem")
        with open(path, "w", encoding="ascii") as handle:
            handle.write(text)
        return path

    def test_the_bundled_root_has_the_pinned_fingerprint(self):
        der = ssl.PEM_cert_to_DER_cert(self.text)
        self.assertEqual(hashlib.sha256(der).hexdigest(), store.PINNED_ROOT_SHA256)
        context = store.pinned_context()
        certificates = context.get_ca_certs()
        self.assertEqual(len(certificates), 1)
        subject = dict(item[0] for item in certificates[0]["subject"])
        self.assertEqual(subject["commonName"], "Microsoft Root Certificate Authority 2011")
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_another_certificate_is_refused(self):
        lines = self.text.splitlines()
        body = lines[5]
        lines[5] = ("B" if body[0] != "B" else "C") + body[1:]  # another DER, same length
        with self.assertRaises(ProcessorError) as caught:
            store.pinned_context(self.write("\n".join(lines) + "\n"))
        self.assertIn("fingerprint differs", str(caught.exception))

    def test_two_or_no_certificates_are_refused(self):
        for text in (self.text + self.text, "", "not a certificate"):
            with self.subTest(length=len(text)):
                with self.assertRaises(ProcessorError):
                    store.pinned_context(self.write(text))

    def test_a_missing_root_is_an_error(self):
        with self.assertRaises(ProcessorError):
            store.pinned_context(os.path.join(self.folder, "missing.pem"))

    def test_only_the_delivery_host_gets_the_bundled_root(self):
        with mock.patch.object(store, "pinned_context", return_value="PINNED") as pinned:
            self.assertEqual(store.context_for(store.DELIVERY_URL), "PINNED")
            self.assertEqual(store.context_for(store.DELIVERY_SECURED_URL), "PINNED")
            for url in (store.catalog_url(PRODUCT, "US", "en-us"), FILE_URL,
                        "https://tlu.dl.delivery.mp.microsoft.com/x", "http://" + store.DELIVERY_HOST + "/x",
                        "https://fe3.delivery.mp.microsoft.com.example.test/x"):
                with self.subTest(url=url):
                    self.assertNotEqual(store.context_for(url), "PINNED")
        self.assertEqual(pinned.call_count, 2)

    def test_the_requests_carry_that_trust(self):
        network = Network({
            store.DELIVERY_URL: FakeResponse(b"<ok/>"),
            store.catalog_url(PRODUCT, "US", "en-us"): FakeResponse(b"{}"),
        })
        with mock.patch.object(store, "open_request", side_effect=network):
            store.soap_post(store.DELIVERY_URL, "GetCookie", "")
            store.fetch_bytes(store.catalog_url(PRODUCT, "US", "en-us"), 100, "the catalog")
        delivery_context, catalog_context = network.calls[0][1], network.calls[1][1]
        self.assertEqual(len(delivery_context.get_ca_certs()), 1)
        self.assertNotEqual(catalog_context.get_ca_certs(), delivery_context.get_ca_certs())
        for call in network.calls:
            self.assertIsInstance(call[2], store.NoRedirect)


class FetchTests(unittest.TestCase):
    URL = "https://displaycatalog.mp.microsoft.com/v7.0/products/x"

    def test_only_the_two_hosts(self):
        network = Network({})
        with mock.patch.object(store, "open_request", side_effect=network):
            for url in ("https://example.test/x", "http://displaycatalog.mp.microsoft.com/x",
                        "https://displaycatalog.mp.microsoft.com.example.test/x"):
                with self.subTest(url=url):
                    with self.assertRaises(ProcessorError) as caught:
                        store.fetch_bytes(url, 10, "x")
                    self.assertIn("Refusing", str(caught.exception))
        self.assertEqual(network.calls, [])

    def test_the_size_limit(self):
        network = Network({self.URL: FakeResponse(b"x" * 11)})
        with mock.patch.object(store, "open_request", side_effect=network):
            with self.assertRaises(ProcessorError) as caught:
                store.fetch_bytes(self.URL, 10, "the catalog")
        self.assertIn("larger than 10 bytes", str(caught.exception))

    def test_a_redirect_is_an_error(self):
        error = urllib.error.HTTPError(self.URL, 302, "Found", {}, None)
        with mock.patch.object(store, "open_request", side_effect=Network({self.URL: error})):
            with self.assertRaises(ProcessorError) as caught:
                store.fetch_bytes(self.URL, 10, "the catalog")
        self.assertIn("a redirect is not followed", str(caught.exception))

    def test_a_failed_request(self):
        error = urllib.error.URLError("no route")
        with mock.patch.object(store, "open_request", side_effect=Network({self.URL: error})):
            with self.assertRaises(ProcessorError) as caught:
                store.fetch_bytes(self.URL, 10, "the catalog")
        self.assertIn("could not be fetched", str(caught.exception))


class DownloadTests(TempFolderTest):
    SUFFIXES = store.DEFAULT_FILE_HOST_SUFFIXES

    def destination(self):
        return os.path.join(self.downloads, FULL_NAME + ".msixbundle")

    def fetch(self, answers, urls, cap=len(PACKAGE_BODY) + 10):
        network = Network(answers)
        with mock.patch.object(store, "open_request", side_effect=network):
            path = store.fetch_package(urls, self.destination(), WANTED, cap, self.SUFFIXES)
        return path, network

    def test_the_catalogs_hash_picks_the_file(self):
        path, network = self.fetch({OTHER_URL: FakeResponse(b"another file"), FILE_URL: FakeResponse(PACKAGE_BODY)},
                                   [OTHER_URL, FILE_URL])
        self.assertEqual(path, self.destination())
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), PACKAGE_BODY)
        self.assertEqual(self.leftovers(), [FULL_NAME + ".msixbundle"])
        self.assertEqual([call[0] for call in network.calls], [OTHER_URL, FILE_URL])
        for call in network.calls:
            self.assertIsInstance(call[2], store.CheckedRedirect)
            self.assertNotEqual(call[1].get_ca_certs(), store.pinned_context().get_ca_certs())

    def test_no_file_with_the_hash_keeps_nothing(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch({OTHER_URL: FakeResponse(b"another file"), FILE_URL: FakeResponse(b"x" * 10000)},
                       [OTHER_URL, FILE_URL])
        self.assertIn("1 had another hash, 1 were larger", str(caught.exception))
        self.assertEqual(self.leftovers(), [])

    def test_the_size_cap(self):
        with self.assertRaises(ProcessorError):
            self.fetch({FILE_URL: FakeResponse(PACKAGE_BODY)}, [FILE_URL], cap=len(PACKAGE_BODY) - 1)
        self.assertEqual(self.leftovers(), [])

    def test_an_announced_size_above_the_cap_is_not_read(self):
        response = FakeResponse(PACKAGE_BODY, headers={"Content-Length": str(len(PACKAGE_BODY) + 100)})
        with self.assertRaises(ProcessorError):
            self.fetch({FILE_URL: response}, [FILE_URL])
        self.assertEqual(response.reads, 0)
        self.assertEqual(self.leftovers(), [])

    def test_an_error_while_writing_leaves_no_partial(self):
        response = FakeResponse(PACKAGE_BODY * 40, fail_after_first=OSError("connection reset"))
        with self.assertRaises(ProcessorError) as caught:
            self.fetch({FILE_URL: response}, [FILE_URL], cap=len(PACKAGE_BODY) * 50)
        self.assertIn("tlu.dl.delivery.mp.microsoft.com", str(caught.exception))
        self.assertEqual(self.leftovers(), [])

    def test_an_interrupt_leaves_no_partial(self):
        big = b"y" * (store.READ_BLOCK_BYTES * 2)
        response = FakeResponse(big, fail_after_first=KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.fetch({FILE_URL: response}, [FILE_URL], cap=len(big))
        self.assertEqual(self.leftovers(), [])

    def test_one_candidate_leaves_no_partial_after_an_error_or_an_interrupt(self):
        partial = self.destination() + ".partial"
        for failure, expected in ((OSError("connection reset"), ProcessorError), (KeyboardInterrupt(), KeyboardInterrupt)):
            with self.subTest(failure=type(failure).__name__):
                response = FakeResponse(b"z" * (store.READ_BLOCK_BYTES * 2), fail_after_first=failure)
                with mock.patch.object(store, "open_request", side_effect=Network({FILE_URL: response})):
                    with self.assertRaises(expected):
                        store.download_candidate(FILE_URL, partial, store.READ_BLOCK_BYTES * 4, self.SUFFIXES)
                self.assertFalse(os.path.exists(partial))

    def test_one_candidate_above_the_cap_leaves_no_partial(self):
        partial = self.destination() + ".partial"
        with mock.patch.object(store, "open_request", side_effect=Network({FILE_URL: FakeResponse(PACKAGE_BODY)})):
            self.assertIsNone(store.download_candidate(FILE_URL, partial, len(PACKAGE_BODY) - 1, self.SUFFIXES))
        self.assertFalse(os.path.exists(partial))

    def test_every_address_is_checked_before_a_download(self):
        with self.assertRaises(ProcessorError) as caught:
            _, network = self.fetch({FILE_URL: FakeResponse(PACKAGE_BODY)}, [FILE_URL, "http://files.example.test/x"])
        self.assertIn("files.example.test", str(caught.exception))
        self.assertEqual(self.leftovers(), [])

    def test_no_address_is_an_error(self):
        with self.assertRaises(ProcessorError) as caught:
            self.fetch({}, [])
        self.assertIn("offered no file", str(caught.exception))


class RunTests(TempFolderTest):
    def env(self, **more):
        env = {"store_product_id": PRODUCT, "RECIPE_CACHE_DIR": self.cache}
        env.update(more)
        return env

    def run_downloader(self, env, document=None, urls=(FILE_URL,), answers=None):
        answers = answers if answers is not None else {FILE_URL: FakeResponse(PACKAGE_BODY)}
        body = json.dumps(document if document is not None else catalog()).encode("utf-8")
        with mock.patch.object(store, "fetch_bytes", return_value=body) as fetch, \
                mock.patch.object(store, "file_urls", return_value=list(urls)) as service, \
                mock.patch.object(store, "open_request", side_effect=Network(answers)):
            processor, messages = run_processor(DOWNLOADER, env)
        return processor, messages, fetch, service

    def test_a_new_download(self):
        processor, messages, fetch, service = self.run_downloader(self.env())
        destination = os.path.join(self.downloads, FULL_NAME + ".msixbundle")
        self.assertEqual(processor.env["pathname"], destination)
        self.assertEqual(processor.env["expected_sha256"], WANTED)
        self.assertEqual(processor.env["store_package_full_name"], FULL_NAME)
        self.assertEqual(processor.env["store_package_version"], "2026.1028.1836.0")
        self.assertEqual(processor.env["store_package_format"], "msixbundle")
        self.assertEqual(processor.env["store_framework_dependencies"], "Example.Runtime.1.4 4000.1309.2056.0 or later")
        self.assertIs(processor.env["download_changed"], True)
        self.assertNotIn("checksum_verified", processor.env)
        service.assert_called_once_with(CATEGORY)
        self.assertEqual(fetch.call_args[0][0], store.catalog_url(PRODUCT, "US", "en-us"))
        text = "\n".join(messages)
        self.assertIn(FULL_NAME, text)
        self.assertIn("needs Example.Runtime.1.4 4000.1309.2056.0 or later", text)
        self.assertIn("%d bytes" % len(PACKAGE_BODY), text)
        summary = processor.env[store.SUMMARY_KEY]
        self.assertEqual(summary["data"]["package_full_name"], FULL_NAME)
        self.assertNotIn(self.folder, json.dumps(summary))
        self.assertEqual(self.leftovers(), [FULL_NAME + ".msixbundle"])

    def test_the_cached_file_does_not_ask_the_service(self):
        destination = os.path.join(self.downloads, FULL_NAME + ".msixbundle")
        with open(destination, "wb") as handle:
            handle.write(PACKAGE_BODY)
        env = self.env(**{store.SUMMARY_KEY: {"old": "result"}})
        processor, messages, _, service = self.run_downloader(env, answers={})
        service.assert_not_called()
        self.assertIs(processor.env["download_changed"], False)
        self.assertEqual(processor.env["pathname"], destination)
        self.assertNotIn(store.SUMMARY_KEY, processor.env)

    def test_a_cached_file_with_another_hash_is_replaced(self):
        destination = os.path.join(self.downloads, FULL_NAME + ".msixbundle")
        with open(destination, "wb") as handle:
            handle.write(b"stale")
        processor, _, _, service = self.run_downloader(self.env())
        service.assert_called_once()
        self.assertIs(processor.env["download_changed"], True)
        with open(destination, "rb") as handle:
            self.assertEqual(handle.read(), PACKAGE_BODY)

    def test_a_link_in_the_cache_is_refused(self):
        destination = os.path.join(self.downloads, FULL_NAME + ".msixbundle")
        target = os.path.join(self.folder, "elsewhere")
        with open(target, "wb") as handle:
            handle.write(PACKAGE_BODY)
        os.symlink(target, destination)
        with self.assertRaises(ProcessorError) as caught:
            self.run_downloader(self.env())
        self.assertIn("is a link", str(caught.exception))

    def test_inputs_are_checked(self):
        for env, needle in (
            ({"store_product_id": "9EXAMPLE"}, "store_product_id"),
            ({"store_product_id": "9EXAMPLE0AP/"}, "store_product_id"),
            ({"store_market": "USA"}, "store_market"),
            ({"store_language": "en us"}, "store_language"),
            ({"store_file_host_suffixes": ["com"]}, "store_file_host_suffixes"),
            ({"RECIPE_CACHE_DIR": ""}, "RECIPE_CACHE_DIR"),
        ):
            with self.subTest(env=env):
                with self.assertRaises(ProcessorError) as caught:
                    self.run_downloader(self.env(**env))
                self.assertIn(needle, str(caught.exception))

    def test_an_answer_that_is_not_json(self):
        with mock.patch.object(store, "fetch_bytes", return_value=b"<html>"):
            processor, _ = new_processor(DOWNLOADER, self.env())
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        self.assertIn("not JSON", str(caught.exception))

    def test_a_catalog_error_names_the_product(self):
        with self.assertRaises(ProcessorError) as caught:
            self.run_downloader(self.env(), document=catalog([package_record(HashAlgorithm="MD5")]))
        self.assertIn(PRODUCT, str(caught.exception))
        self.assertIn("not SHA-256", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
