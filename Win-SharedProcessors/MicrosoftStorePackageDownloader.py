#!/usr/local/autopkg/python
"""Download the package of a free Microsoft Store product without the Store and
without an account, and accept it only when its SHA-256 is the one that the
Store's catalog gives.

What is read, in order:

 1. The product in Microsoft's Store catalog,
    https://displaycatalog.mp.microsoft.com/v7.0/products/<id>?market=..&languages=..
    (system trust, no redirect followed). Every SKU of the product must name the
    same one package (one PackageFullName with one hash): none, or two, is an
    error. Read from the package: PackageFullName, PackageFormat, Hash and
    HashAlgorithm (SHA256 only), MaxDownloadSizeInBytes, the framework
    dependencies, and FulfillmentData.WuCategoryId.
 2. Microsoft's delivery service, https://fe3.delivery.mp.microsoft.com (the
    service that a Windows PC asks for Store files): GetCookie, then SyncUpdates
    with the category, repeated with the non-leaf update ids that the service
    returns (at most SYNC_ROUNDS rounds) until it names leaf updates, then
    GetExtendedUpdateInfo2 on /secured for each leaf update, which gives file
    addresses. The service's certificate is issued under "Microsoft Root
    Certificate Authority 2011", which macOS does not trust. The file
    microsoft-root-2011.pem beside this processor is that public root; it is
    used only if its DER has the SHA-256 fingerprint PINNED_ROOT_SHA256, and
    only for connections to this one host. No redirect is followed.
 3. The file addresses. They point at Microsoft's content hosts and may be
    plain http. An address is used only when its scheme is http or https and
    its host ends in one of the suffixes of store_file_host_suffixes; a
    refused address stops the run and names its host. A redirect is followed
    only to an address that passes the same rule. Plain http is acceptable
    ONLY because a file is accepted solely on the catalog's SHA-256, which came
    over verified https: whatever the way of the file, a file with another hash
    is deleted.

Each offered file is downloaded to a .partial file in the downloads folder with
a size limit (the catalog's MaxDownloadSizeInBytes plus SIZE_MARGIN_BYTES) and
hashed while it is written. The one whose SHA-256 equals the catalog's becomes
<downloads>/<PackageFullName>.<extension>; every other one is deleted. No
.partial file is left behind, also on an error or an interrupt. When that file
is in the downloads folder already with the catalog's SHA-256, the delivery
service is not asked at all and download_changed is False.

What this proves: the file is the one whose SHA-256 Microsoft's catalog gives,
read over verified TLS. What it does not prove: the package's signature is not
checked here (the Store signs the package; Windows checks it when the package
is added). It sets no checksum_verified: the recipe's next step is
ChecksumVerifier with pathname and expected_sha256.

The processor prints the package's name, its size and each framework
dependency with its minimum version. A person compares that with the framework
item of their repository: the package does not install without it.

Every value taken from an answer is checked for its shape before it is used,
because it is put into XML or into a file name: the product id, the package
full name, the hash, the format, the category (a GUID), the cookie, the update
ids (GUIDs or numbers) and the revision numbers. What is put into XML is
escaped.
"""
import base64
import datetime
import hashlib
import html
import http.client
import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape as xml_escape

from autopkglib import Processor, ProcessorError

__all__ = [
    "MicrosoftStorePackageDownloader",
    "catalog_url",
    "version_text",
    "parse_catalog",
    "framework_text",
    "pinned_context",
    "context_for",
    "parse_cookie",
    "parse_sync",
    "parse_file_urls",
    "parse_suffixes",
    "check_file_url",
    "envelope",
    "open_request",
    "fetch_bytes",
    "soap_post",
    "file_urls",
    "download_candidate",
    "fetch_package",
    "sha256_of_file",
]

CATALOG_HOST = "displaycatalog.mp.microsoft.com"
CATALOG_URL = "https://" + CATALOG_HOST + "/v7.0/products/%s?%s"
DELIVERY_HOST = "fe3.delivery.mp.microsoft.com"
DELIVERY_URL = "https://" + DELIVERY_HOST + "/ClientWebService/client.asmx"
DELIVERY_SECURED_URL = DELIVERY_URL + "/secured"
NS = "http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService"

# Microsoft Root Certificate Authority 2011, the public root that issues the delivery
# service's certificate (http://www.microsoft.com/pki/certs/MicRooCerAut2011_2011_03_22.crt).
# The SHA-256 of its DER form; a .pem beside the processor with another one is refused.
PINNED_ROOT_FILE = "microsoft-root-2011.pem"
PINNED_ROOT_SHA256 = "847df6a78497943f27fc72eb93f9a637320a02b561d0a91b09e87a7807ed7c61"

CATALOG_TIMEOUT_SECONDS = 60
SOAP_TIMEOUT_SECONDS = 90
FILE_TIMEOUT_SECONDS = 120
# The catalog record of a product is some tens of kilobytes (40 KB for the first one read).
MAX_CATALOG_BYTES = 4 * 1024 * 1024
# A SyncUpdates answer lists updates with their XML; some megabytes at most.
MAX_SOAP_BYTES = 16 * 1024 * 1024
# The file may differ from MaxDownloadSizeInBytes by a little; a larger file is not the one.
SIZE_MARGIN_BYTES = 1024 * 1024
READ_BLOCK_BYTES = 1024 * 1024
USER_AGENT = "autopkg-MicrosoftStorePackageDownloader"
# The delivery service is asked as Windows Update asks it (from the tool that ran on 2026-11-10).
SOAP_USER_AGENT = "Windows-Update-Agent/10.0.10011.16384 Client-Protocol/1.81"

# SyncUpdates is repeated at most this often, each time with the non-leaf ids it returned.
SYNC_ROUNDS = 8
# More leaf updates or offered files than this is not the answer for one product.
MAX_LEAF_UPDATES = 200
MAX_FILE_URLS = 200
MAX_NONLEAF_IDS = 2000
# Addresses of exactly this length in GetExtendedUpdateInfo2's answer are block maps, not
# packages (the rule of the tool that ran on 2026-11-10).
BLOCKMAP_URL_LENGTH = 99

DEFAULT_MARKET = "US"
DEFAULT_LANGUAGE = "en-us"
# ASSUMED, not read: the hosts of the file addresses were not recorded by the tool that ran
# on 2026-11-10. A refused address stops the run and names its host.
DEFAULT_FILE_HOST_SUFFIXES = [".dl.delivery.mp.microsoft.com", ".microsoft.com"]
FILE_SCHEMES = ("http", "https")

# The device that the delivery service is told about: Windows 10 desktop, retail ring, x64.
# Constant, from the tool that ran on 2026-11-10 (already XML-escaped: & is &amp;).
DEVICE_ATTRIBUTES = (
    "E:BranchReadinessLevel=CBB&amp;CurrentBranch=rs4_release&amp;FlightRing=Retail&amp;AttrDataVer=57"
    "&amp;InstallLanguage=en-US&amp;OSUILocale=en-US&amp;InstallationType=Client&amp;FlightingBranchName="
    "&amp;OSSkuId=48&amp;App=WU&amp;ProcessorManufacturer=GenuineIntel&amp;AppVer=10.0.19045.3000"
    "&amp;OSArchitecture=AMD64&amp;UpdateManagementGroup=2&amp;IsDeviceRetailDemo=0&amp;IsFlightingEnabled=0"
    "&amp;TelemetryLevel=1&amp;WuClientVer=10.0.19045.3000&amp;OSVersion=10.0.19045.3000"
    "&amp;DeviceFamily=Windows.Desktop"
)
CALLER_ATTRIBUTES = "E:Interactive=1&amp;IsSeeker=0&amp;Id=UpdateOrchestrator&amp;"
# The category updates that every client is taken to have; the service then answers with the
# next level. Constant, from the tool that ran on 2026-11-10.
INSTALLED_NONLEAF_UPDATE_IDS = (
    1, 2, 3, 11, 19, 2359974, 5169044, 8788830, 23110993, 23110994, 59830006, 59830007, 59830008,
    60484010, 62450018, 62450019, 62450020, 98959022, 98959023, 98959024, 98959025, 98959026,
    129905029, 130040030, 130040031, 130040032, 130040033, 138372035, 138372036, 139536037,
    139536038, 139536039, 139536040, 142045136, 158941041, 158941042, 158941043, 158941044,
    159776047, 160733048, 160733049, 160733050, 160733051, 160733055, 160733056, 161870057,
    161870058, 161870059,
)
# Fixed texts of the SOAP header, as the tool that ran on 2026-11-10 sends them.
SOAP_MESSAGE_ID = "urn:uuid:5754a03d-d8d5-489f-b24d-efc31b3fd32d"
SOAP_TIMESTAMP_CREATED = "2017-12-02T00:16:15.210Z"
SOAP_TIMESTAMP_EXPIRES = "2017-12-29T06:25:43.943Z"
COOKIE_LAST_CHANGE = "2015-10-21T17:01:07.1472913Z"

PRODUCT_ID_PATTERN = re.compile(r"[A-Za-z0-9]{12}")
MARKET_PATTERN = re.compile(r"[A-Za-z]{2}")
LANGUAGE_PATTERN = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,2}")
# <name>_<version>_<architecture>_<resource id>_<publisher id>, as Windows writes a package
# full name; a bundle's resource id is "~".
FULL_NAME_PATTERN = re.compile(
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9.-]{2,49})_(?P<version>[0-9]{1,5}(?:\.[0-9]{1,5}){3})"
    r"_(?P<architecture>neutral|x86|x64|arm|arm64)_(?P<resource>~|[A-Za-z0-9.-]{0,30})"
    r"_(?P<publisher>[a-z0-9]{13})"
)
FRAMEWORK_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,99}")
GUID_PATTERN = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")
REVISION_PATTERN = re.compile(r"[0-9]{1,10}")
NONLEAF_ID_PATTERN = re.compile(r"[0-9]{1,12}")
COOKIE_EXPIRATION_PATTERN = re.compile(r"[0-9T:.Z+-]{10,40}")
COOKIE_DATA_PATTERN = re.compile(r"[A-Za-z0-9+/=]{1,65536}")
SUFFIX_PATTERN = re.compile(r"\.?[a-z0-9-]+(?:\.[a-z0-9-]+)+")
# The catalog's PackageFormat and the extension of the file.
FORMATS = {"MsixBundle": "msixbundle", "AppxBundle": "appxbundle", "Msix": "msix", "Appx": "appx"}
UINT64_MAX = 2 ** 64 - 1
MAX_SHOWN_CHARACTERS = 80

SUMMARY_KEY = "microsoft_store_package_downloader_summary_result"
SUMMARY_FIELDS = ["product_id", "package_full_name", "package_version", "framework_dependencies"]


def shown(value):
    """A value from an answer for a message: printable characters only, and short."""
    text = value if isinstance(value, str) else repr(value)
    text = "".join(char if char.isprintable() else "?" for char in text)
    if len(text) > MAX_SHOWN_CHARACTERS:
        text = text[:MAX_SHOWN_CHARACTERS] + "..."
    return text


def version_text(number):
    """The four numbers of a version that the catalog writes as one 64-bit number."""
    value = int(number)
    if not 0 <= value <= UINT64_MAX:
        raise ValueError("a version number is out of range")
    return ".".join(str((value >> shift) & 0xFFFF) for shift in (48, 32, 16, 0))


def catalog_url(product_id, market, language):
    if not PRODUCT_ID_PATTERN.fullmatch(product_id):
        raise ValueError("the product id is not 12 letters and digits")
    query = urllib.parse.urlencode({"market": market, "languages": language})
    return CATALOG_URL % (product_id, query)


# ---- the catalog --------------------------------------------------------------


def _number(value, what):
    """A whole number from JSON: an integer, or text of digits."""
    if isinstance(value, bool):
        raise ValueError("%s is not a number" % what)
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.isdigit() and value.isascii():
        number = int(value)
    else:
        raise ValueError("%s is not a number" % what)
    if not 0 <= number <= UINT64_MAX:
        raise ValueError("%s is out of range" % what)
    return number


def _package_facts(package, product_id):
    """The checked facts of one package record of the catalog."""
    if not isinstance(package, dict):
        raise ValueError("a package is not a record")
    full_name = package.get("PackageFullName")
    if not isinstance(full_name, str) or not FULL_NAME_PATTERN.fullmatch(full_name):
        raise ValueError("PackageFullName %s does not have the shape of a package full name" % shown(full_name))
    parts = FULL_NAME_PATTERN.fullmatch(full_name)
    version = parts.group("version")
    if any(int(part) > 0xFFFF for part in version.split(".")):
        raise ValueError("the version in PackageFullName %s has a part above 65535" % shown(full_name))
    if package.get("HashAlgorithm") != "SHA256":
        raise ValueError("the catalog's hash is not SHA-256 (HashAlgorithm %s)" % shown(package.get("HashAlgorithm")))
    encoded = package.get("Hash")
    try:
        if not isinstance(encoded, str):
            raise ValueError
        raw = base64.b64decode(encoded, validate=True)
    except ValueError:
        raise ValueError("the catalog's Hash is not base64")
    if len(raw) != 32:
        raise ValueError("the catalog's Hash is %d bytes, not the 32 of a SHA-256" % len(raw))
    package_format = package.get("PackageFormat")
    if package_format not in FORMATS:
        raise ValueError("PackageFormat %s is not one of %s" % (shown(package_format), ", ".join(FORMATS)))
    size = _number(package.get("MaxDownloadSizeInBytes"), "MaxDownloadSizeInBytes")
    if size <= 0:
        raise ValueError("MaxDownloadSizeInBytes is not above zero")
    catalog_version = package.get("Version")
    if catalog_version is not None and version_text(_number(catalog_version, "Version")) != version:
        raise ValueError("the package's Version is not the version in PackageFullName %s" % shown(full_name))
    fulfillment = package.get("FulfillmentData")
    if not isinstance(fulfillment, dict):
        raise ValueError("the package has no FulfillmentData record")
    category = fulfillment.get("WuCategoryId")
    if not isinstance(category, str) or not GUID_PATTERN.fullmatch(category):
        raise ValueError("WuCategoryId %s is not a GUID" % shown(category))
    fulfilled = fulfillment.get("ProductId")
    if fulfilled is not None and (not isinstance(fulfilled, str) or fulfilled.upper() != product_id.upper()):
        raise ValueError("FulfillmentData names product %s, not %s" % (shown(fulfilled), product_id))
    frameworks = []
    for entry in package.get("FrameworkDependencies") or []:
        if not isinstance(entry, dict):
            raise ValueError("a framework dependency is not a record")
        identity = entry.get("PackageIdentity")
        if not isinstance(identity, str) or not FRAMEWORK_PATTERN.fullmatch(identity):
            raise ValueError("a framework dependency's PackageIdentity %s is not a package name" % shown(identity))
        frameworks.append((identity, version_text(_number(entry.get("MinVersion"), "a framework's MinVersion"))))
    return {
        "full_name": full_name,
        "version": version,
        "sha256": raw.hex(),
        "format": FORMATS[package_format],
        "max_size": size,
        "category": category.lower(),
        "frameworks": frameworks,
    }


def parse_catalog(document, product_id):
    """The facts of the product's one package, or raise ValueError with a reason that
    is safe to show. Every SKU must name the same package (full name and hash)."""
    if not isinstance(document, dict) or not isinstance(document.get("Product"), dict):
        raise ValueError("the answer has no Product record")
    product = document["Product"]
    found_id = product.get("ProductId")
    if not isinstance(found_id, str) or found_id.upper() != product_id.upper():
        raise ValueError("the answer is for product %s, not %s" % (shown(found_id), product_id))
    title = "?"
    names = product.get("LocalizedProperties")
    if isinstance(names, list) and names and isinstance(names[0], dict):
        title = shown(names[0].get("ProductTitle"))
    skus = product.get("DisplaySkuAvailabilities")
    if not isinstance(skus, list) or not skus:
        raise ValueError("the product has no SKU")
    facts = []
    for entry in skus:
        try:
            packages = entry["Sku"]["Properties"]["Packages"]
        except (KeyError, TypeError):
            raise ValueError("a SKU has no list of packages")
        if not isinstance(packages, list):
            raise ValueError("a SKU has no list of packages")
        for package in packages:
            facts.append(_package_facts(package, product_id))
    distinct = {(fact["full_name"], fact["sha256"]): fact for fact in facts}
    if len(distinct) != 1:
        raise ValueError(
            "%s: the catalog names %d different packages (%s), not exactly one; this processor handles "
            "a product with one package" % (title, len(distinct), ", ".join(sorted(shown(k[0]) for k in distinct)))
        )
    fact = next(iter(distinct.values()))
    if len({(f["category"], f["format"], f["max_size"], tuple(f["frameworks"])) for f in facts}) != 1:
        raise ValueError("%s: the SKUs describe the same package differently" % title)
    fact["title"] = title
    return fact


def framework_text(frameworks):
    """One line: each framework's identity and minimum version."""
    if not frameworks:
        return "none"
    return "; ".join("%s %s or later" % (identity, version) for identity, version in frameworks)


# ---- TLS and requests -----------------------------------------------------------


def pinned_context(pem_path=None):
    """An SSL context that trusts the bundled Microsoft root only, after checking that the
    file holds exactly one certificate whose DER has the SHA-256 PINNED_ROOT_SHA256."""
    path = pem_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), PINNED_ROOT_FILE)
    try:
        with open(path, "r", encoding="ascii") as handle:
            text = handle.read(64 * 1024)
    except (OSError, UnicodeDecodeError) as err:
        raise ProcessorError("The bundled root %s cannot be read: %s" % (PINNED_ROOT_FILE, err))
    blocks = re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", text, re.S)
    if len(blocks) != 1:
        raise ProcessorError("The bundled root %s holds %d certificates, not exactly one." % (PINNED_ROOT_FILE, len(blocks)))
    try:
        der = ssl.PEM_cert_to_DER_cert(blocks[0])
    except ValueError as err:
        raise ProcessorError("The bundled root %s is not a certificate: %s" % (PINNED_ROOT_FILE, err))
    if hashlib.sha256(der).hexdigest() != PINNED_ROOT_SHA256:
        raise ProcessorError(
            "The bundled root %s is not Microsoft Root Certificate Authority 2011 (its SHA-256 "
            "fingerprint differs); it is not used." % PINNED_ROOT_FILE
        )
    # cadata: exactly the checked bytes are trusted, and no system root besides them.
    return ssl.create_default_context(cadata=der)


def context_for(url, pem_path=None):
    """The trust for one address: the bundled root for the delivery host only, the
    system's trust for every other host."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme == "https" and parts.hostname == DELIVERY_HOST:
        return pinned_context(pem_path)
    return ssl.create_default_context()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The catalog and the delivery service answer at one fixed address. A redirect
    would send the request elsewhere: it is an error (HTTPError)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CheckedRedirect(urllib.request.HTTPRedirectHandler):
    """For a file address: a redirect is followed only to an address that passes the
    host rule."""

    def __init__(self, suffixes):
        super().__init__()
        self.suffixes = suffixes

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_file_url(urllib.parse.urljoin(req.full_url, newurl), self.suffixes)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_request(request, context, redirect_handler, timeout):
    """Send one request with the given trust and redirect rule. The one place where the
    network is used: tests replace it."""
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), redirect_handler)
    return opener.open(request, timeout=timeout)


def fetch_bytes(url, max_bytes, what, data=None, headers=None, timeout=CATALOG_TIMEOUT_SECONDS):
    """GET (or POST `data` to) one of the two fixed hosts and return the body. No
    redirect is followed."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in (CATALOG_HOST, DELIVERY_HOST):
        raise ProcessorError("Refusing to ask for %s at an address outside the catalog and the delivery service." % what)
    all_headers = {"User-Agent": USER_AGENT}
    all_headers.update(headers or {})
    request = urllib.request.Request(url, data=data, headers=all_headers)
    try:
        with open_request(request, context_for(url), NoRedirect(), timeout) as response:
            body = response.read(max_bytes + 1)
    except urllib.error.HTTPError as err:
        code, reason = err.code, err.reason
        err.close()
        redirect = " (a redirect is not followed)" if 300 <= code < 400 else ""
        raise ProcessorError("Microsoft answered %s %s for %s%s." % (code, shown(reason), what, redirect))
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("%s could not be fetched: %s" % (what[:1].upper() + what[1:], shown(str(err))))
    if len(body) > max_bytes:
        raise ProcessorError("The answer for %s is larger than %d bytes." % (what, max_bytes))
    return body


# ---- the delivery service ----------------------------------------------------------


def envelope(action, to, body):
    """The SOAP envelope of the tool that ran on 2026-11-10. `action` and `to` are this
    module's constants; `body` is built from escaped values."""
    return (
        '<s:Envelope xmlns:a="http://www.w3.org/2005/08/addressing" xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
        '<s:Header>'
        '<a:Action s:mustUnderstand="1">%s/%s</a:Action>'
        '<a:MessageID>%s</a:MessageID>'
        '<a:To s:mustUnderstand="1">%s</a:To>'
        '<o:Security s:mustUnderstand="1" xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">'
        '<Timestamp xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">'
        '<Created>%s</Created><Expires>%s</Expires></Timestamp>'
        '<wuws:WindowsUpdateTicketsToken wsu:id="ClientMSA" '
        'xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd" '
        'xmlns:wuws="http://schemas.microsoft.com/msus/2014/10/WindowsUpdateAuthorization">'
        '<TicketType Name="MSA" Version="1.0" Policy="MBI_SSL"><User /></TicketType>'
        '</wuws:WindowsUpdateTicketsToken></o:Security></s:Header>'
        '<s:Body>%s</s:Body></s:Envelope>'
        % (NS, xml_escape(action), SOAP_MESSAGE_ID, xml_escape(to), SOAP_TIMESTAMP_CREATED,
           SOAP_TIMESTAMP_EXPIRES, body)
    )


def soap_post(url, action, body):
    """POST one SOAP request to the delivery service and return the answer as text."""
    data = envelope(action, url, body).encode("utf-8")
    headers = {"Content-Type": "application/soap+xml; charset=utf-8", "User-Agent": SOAP_USER_AGENT}
    raw = fetch_bytes(url, MAX_SOAP_BYTES, "the delivery service's %s" % action, data=data, headers=headers,
                      timeout=SOAP_TIMEOUT_SECONDS)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ProcessorError("The delivery service's answer to %s is not UTF-8 text." % action)


def cookie_body(now):
    return (
        '<GetCookie xmlns="%s"><oldCookie /><lastChange>%s</lastChange>'
        '<currentTime>%s</currentTime><protocolVersion>1.40</protocolVersion></GetCookie>'
        % (NS, COOKIE_LAST_CHANGE, xml_escape(now))
    )


def parse_cookie(text):
    """The cookie (expiration, encrypted data) of GetCookie's answer, checked."""
    match = re.search(r"<Expiration>([^<]+)</Expiration>\s*<EncryptedData>([^<]+)</EncryptedData>", text)
    if not match:
        raise ValueError("the delivery service gave no cookie")
    expiration, data = match.group(1), match.group(2)
    if not COOKIE_EXPIRATION_PATTERN.fullmatch(expiration):
        raise ValueError("the cookie's Expiration %s is not a time" % shown(expiration))
    if not COOKIE_DATA_PATTERN.fullmatch(data):
        raise ValueError("the cookie's EncryptedData is not base64")
    return expiration, data


def sync_body(cookie, category, nonleaf):
    expiration, data = cookie
    ids = "".join("<int>%d</int>" % int(number) for number in nonleaf)
    return (
        '<SyncUpdates xmlns="%s"><cookie><Expiration>%s</Expiration><EncryptedData>%s</EncryptedData></cookie>'
        '<parameters><ExpressQuery>false</ExpressQuery>'
        '<InstalledNonLeafUpdateIDs>%s</InstalledNonLeafUpdateIDs>'
        '<OtherCachedUpdateIDs /><SkipSoftwareSync>false</SkipSoftwareSync>'
        '<NeedTwoGroupOutOfScopeUpdates>true</NeedTwoGroupOutOfScopeUpdates>'
        '<FilterAppCategoryIds><CategoryIdentifier><Id>%s</Id></CategoryIdentifier></FilterAppCategoryIds>'
        '<AlsoPerformRegularSync>false</AlsoPerformRegularSync><ComputerSpec /><ExtendedUpdateInfoParameters>'
        '<XmlUpdateFragmentTypes><XmlUpdateFragmentType>Extended</XmlUpdateFragmentType>'
        '<XmlUpdateFragmentType>LocalizedProperties</XmlUpdateFragmentType><XmlUpdateFragmentType>Eula</XmlUpdateFragmentType>'
        '</XmlUpdateFragmentTypes><Locales><string>en-US</string><string>en</string></Locales></ExtendedUpdateInfoParameters>'
        '<ClientPreferredLanguages><string>en-US</string></ClientPreferredLanguages>'
        '<ProductsParameters><SyncCurrentVersionOnly>false</SyncCurrentVersionOnly>'
        '<DeviceAttributes>%s</DeviceAttributes>'
        '<CallerAttributes>%s</CallerAttributes><Products />'
        '</ProductsParameters></parameters></SyncUpdates>'
        % (NS, xml_escape(expiration), xml_escape(data), ids, xml_escape(category), DEVICE_ATTRIBUTES,
           CALLER_ATTRIBUTES)
    )


def parse_sync(text):
    """(leaf updates as (update id, revision), new non-leaf ids) of a SyncUpdates answer.
    The answer carries XML in escaped form: it is unescaped first, as the tool did."""
    document = html.unescape(text)
    infos = re.findall(r"<UpdateInfo>(.*?)</UpdateInfo>", document, re.S)
    leaves = []
    nonleaf = []
    for block in infos:
        if "<IsLeaf>true</IsLeaf>" in block and "<SecuredFragment>" in block:
            match = re.search(r'UpdateIdentity UpdateID="([^"]+)" RevisionNumber="([^"]+)"', block)
            if not match:
                raise ValueError("a leaf update has no UpdateIdentity")
            update_id, revision = match.groups()
            if not GUID_PATTERN.fullmatch(update_id):
                raise ValueError("an update id %s is not a GUID" % shown(update_id))
            if not REVISION_PATTERN.fullmatch(revision):
                raise ValueError("a revision number %s is not digits" % shown(revision))
            if (update_id.lower(), revision) not in leaves:
                leaves.append((update_id.lower(), revision))
        elif "<IsLeaf>false</IsLeaf>" in block:
            match = re.search(r"<ID>([^<]*)</ID>", block)
            if not match or not NONLEAF_ID_PATTERN.fullmatch(match.group(1)):
                raise ValueError("a non-leaf update's ID is not digits")
            nonleaf.append(int(match.group(1)))
    if len(leaves) > MAX_LEAF_UPDATES:
        raise ValueError("the answer names %d leaf updates, more than %d" % (len(leaves), MAX_LEAF_UPDATES))
    return leaves, nonleaf


def extended_body(update_id, revision):
    return (
        '<GetExtendedUpdateInfo2 xmlns="%s"><updateIDs><UpdateIdentity><UpdateID>%s</UpdateID>'
        '<RevisionNumber>%s</RevisionNumber></UpdateIdentity></updateIDs><infoTypes>'
        '<XmlUpdateFragmentType>FileUrl</XmlUpdateFragmentType><XmlUpdateFragmentType>FileDecryption</XmlUpdateFragmentType>'
        '</infoTypes><deviceAttributes>%s</deviceAttributes></GetExtendedUpdateInfo2>'
        % (NS, xml_escape(update_id), xml_escape(revision), DEVICE_ATTRIBUTES)
    )


def parse_file_urls(text):
    """The file addresses of a GetExtendedUpdateInfo2 answer, block maps left out."""
    urls = [html.unescape(found) for found in re.findall(r"<Url>([^<]+)</Url>", text)]
    return [url for url in urls if len(url) != BLOCKMAP_URL_LENGTH]


def file_urls(category, now=None):
    """Ask the delivery service for the addresses of the files of a category."""
    stamp = now or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    try:
        cookie = parse_cookie(soap_post(DELIVERY_URL, "GetCookie", cookie_body(stamp)))
    except ValueError as err:
        raise ProcessorError("Delivery service, GetCookie: %s." % err)
    nonleaf = list(INSTALLED_NONLEAF_UPDATE_IDS)
    leaves = []
    for _ in range(SYNC_ROUNDS):
        try:
            leaves, offered = parse_sync(soap_post(DELIVERY_URL, "SyncUpdates", sync_body(cookie, category, nonleaf)))
        except ValueError as err:
            raise ProcessorError("Delivery service, SyncUpdates: %s." % err)
        new = []
        for number in offered:
            if number not in nonleaf and number not in new:
                new.append(number)
        if leaves or not new:
            break
        nonleaf += new
        if len(nonleaf) > MAX_NONLEAF_IDS:
            raise ProcessorError("Delivery service, SyncUpdates: more than %d non-leaf ids." % MAX_NONLEAF_IDS)
    if not leaves:
        raise ProcessorError("The delivery service named no update with a file for this product.")
    urls = []
    for update_id, revision in leaves:
        answer = soap_post(DELIVERY_SECURED_URL, "GetExtendedUpdateInfo2", extended_body(update_id, revision))
        for url in parse_file_urls(answer):
            if url not in urls:
                urls.append(url)
    if len(urls) > MAX_FILE_URLS:
        raise ProcessorError("The delivery service offered %d files, more than %d." % (len(urls), MAX_FILE_URLS))
    return urls


# ---- the files ---------------------------------------------------------------------


def parse_suffixes(value):
    """The host suffixes of store_file_host_suffixes: a list of text, or one text with
    commas. Each is a DNS name, lower case, with at least two labels."""
    if value is None or value == "" or value == []:
        return list(DEFAULT_FILE_HOST_SUFFIXES)
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",")]
    elif isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        items = [item.strip() for item in value]
    else:
        raise ProcessorError("store_file_host_suffixes must be a list of host suffixes, or one text with commas.")
    suffixes = []
    for item in items:
        lowered = item.lower()
        if not SUFFIX_PATTERN.fullmatch(lowered):
            raise ProcessorError("store_file_host_suffixes: %s is not a host suffix such as .example.test." % shown(item))
        suffixes.append(lowered)
    return suffixes


def host_allowed(host, suffixes):
    """True when the host is one of the suffixes without its leading dot, or ends in it
    as a whole label."""
    for suffix in suffixes:
        bare = suffix.lstrip(".")
        if host == bare or host.endswith("." + bare):
            return True
    return False


def check_file_url(url, suffixes):
    """Raise ProcessorError naming the host unless the address is http or https on an
    allowed host, without a user name or an unusual port."""
    try:
        parts = urllib.parse.urlsplit(url)
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        raise ProcessorError("The delivery service offered an address that cannot be read: %s" % shown(url))
    if parts.scheme not in FILE_SCHEMES:
        raise ProcessorError("The delivery service offered an address with scheme %s; only http and https are used." % shown(parts.scheme))
    if parts.username is not None or parts.password is not None:
        raise ProcessorError("The delivery service offered an address with a user name, on host %s; refused." % shown(host))
    if port not in (None, 80, 443):
        raise ProcessorError("The delivery service offered an address on port %d of host %s; refused." % (port, shown(host)))
    if not host or not host_allowed(host, suffixes):
        raise ProcessorError(
            "The delivery service offered a file on host %s, which is not under %s. If that host is "
            "Microsoft's, add its suffix to store_file_host_suffixes in the override." % (shown(host), ", ".join(suffixes))
        )


def remove_quietly(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def download_candidate(url, partial, max_bytes, suffixes):
    """Download one offered file to `partial`, hashing while writing, at most `max_bytes`.
    Returns its SHA-256, or None when it is larger than the limit (then nothing is kept).
    The partial file is removed on any error or interrupt; the caller removes it after a
    hash that is not the wanted one."""
    check_file_url(url, suffixes)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    written = 0
    finished = False
    try:
        with open_request(request, ssl.create_default_context(), CheckedRedirect(suffixes), FILE_TIMEOUT_SECONDS) as response:
            announced = response.headers.get("Content-Length") if response.headers is not None else None
            if announced is not None and announced.isdigit() and int(announced) > max_bytes:
                return None
            with open(partial, "wb") as out:
                while True:
                    block = response.read(READ_BLOCK_BYTES)
                    if not block:
                        break
                    written += len(block)
                    if written > max_bytes:
                        return None
                    digest.update(block)
                    out.write(block)
        finished = True
        return digest.hexdigest()
    except urllib.error.HTTPError as err:
        code, reason = err.code, err.reason
        err.close()
        raise ProcessorError("The content host %s answered %s %s for an offered file." % (
            shown(urllib.parse.urlsplit(url).hostname), code, shown(reason)))
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("An offered file could not be downloaded from %s: %s" % (
            shown(urllib.parse.urlsplit(url).hostname), shown(str(err))))
    finally:
        if not finished:
            remove_quietly(partial)


def sha256_of_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(READ_BLOCK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_package(urls, destination, wanted, max_bytes, suffixes):
    """Download the offered files in turn until one has the wanted SHA-256; that one
    becomes `destination`. Every other file is deleted. Returns the destination."""
    if not urls:
        raise ProcessorError("The delivery service offered no file.")
    for url in urls:  # every address is checked before anything is downloaded
        check_file_url(url, suffixes)
    partial = destination + ".partial"
    too_large = 0
    other = 0
    try:
        for url in urls:
            found = download_candidate(url, partial, max_bytes, suffixes)
            if found == wanted:
                os.replace(partial, destination)
                return destination
            remove_quietly(partial)
            if found is None:
                too_large += 1
            else:
                other += 1
    finally:
        remove_quietly(partial)
    raise ProcessorError(
        "No offered file has the catalog's SHA-256: %d had another hash, %d were larger than %d bytes; "
        "nothing kept." % (other, too_large, max_bytes)
    )


class MicrosoftStorePackageDownloader(Processor):
    description = __doc__
    input_variables = {
        "store_product_id": {
            "required": True,
            "description": "The Store's product id: 12 letters and digits, as in the address of the product's page.",
        },
        "store_market": {
            "required": False,
            "default": DEFAULT_MARKET,
            "description": "The catalog's market, two letters.",
        },
        "store_language": {
            "required": False,
            "default": DEFAULT_LANGUAGE,
            "description": "The catalog's language, such as en-us.",
        },
        "store_file_host_suffixes": {
            "required": False,
            "default": list(DEFAULT_FILE_HOST_SUFFIXES),
            "description": (
                "The host suffixes that a file address of the delivery service may have (a list, or "
                "one text with commas). The default was assumed, not read; a refused address stops "
                "the run and names its host."
            ),
        },
    }
    output_variables = {
        "pathname": {"description": "The package, <downloads>/<PackageFullName>.<extension>."},
        "expected_sha256": {"description": "The catalog's SHA-256 of the package (lower-case hex)."},
        "store_package_full_name": {"description": "The package's full name from the catalog."},
        "store_package_version": {"description": "The four numbers of the version in the full name."},
        "store_package_format": {"description": "msixbundle, appxbundle, msix or appx."},
        "store_framework_dependencies": {
            "description": "One line: each framework's identity and minimum version (none when there is none)."
        },
        "download_changed": {
            "description": "False when the file with the catalog's SHA-256 was in the cache and the delivery service was not asked."
        },
        SUMMARY_KEY: {
            "description": "Set when a new file was downloaded: the product id, the package, its version and the frameworks. No path."
        },
    }

    def text_input(self, name, default, pattern, shape):
        value = self.env.get(name, default)
        if not isinstance(value, str) or not pattern.fullmatch(value.strip()):
            raise ProcessorError("%s must be %s, not %s." % (name, shape, shown(value)))
        return value.strip()

    def main(self):
        self.env.pop(SUMMARY_KEY, None)
        product_id = self.text_input("store_product_id", None, PRODUCT_ID_PATTERN, "12 letters and digits")
        market = self.text_input("store_market", DEFAULT_MARKET, MARKET_PATTERN, "two letters")
        language = self.text_input("store_language", DEFAULT_LANGUAGE, LANGUAGE_PATTERN, "a language such as en-us")
        suffixes = parse_suffixes(self.env.get("store_file_host_suffixes"))
        cache = self.env.get("RECIPE_CACHE_DIR")
        if not isinstance(cache, str) or not cache:
            raise ProcessorError("RECIPE_CACHE_DIR is not set.")

        raw = fetch_bytes(catalog_url(product_id, market, language), MAX_CATALOG_BYTES, "the catalog record of %s" % product_id)
        try:
            document = json.loads(raw.decode("utf-8"))
        except ValueError as err:  # UnicodeDecodeError and JSONDecodeError are ValueErrors
            raise ProcessorError("Store catalog, product %s: the answer is not JSON: %s" % (product_id, shown(str(err))))
        try:
            package = parse_catalog(document, product_id)
        except ValueError as err:
            raise ProcessorError("Store catalog, product %s: %s." % (product_id, err))

        frameworks = framework_text(package["frameworks"])
        self.output("%s: %s (%d bytes at most)" % (package["title"], package["full_name"], package["max_size"]), verbose_level=0)
        for identity, version in package["frameworks"]:
            self.output("  needs %s %s or later" % (identity, version), verbose_level=0)

        downloads = os.path.join(cache, "downloads")
        os.makedirs(downloads, exist_ok=True)
        destination = os.path.join(downloads, "%s.%s" % (package["full_name"], package["format"]))
        if os.path.islink(destination):
            raise ProcessorError("%s in the downloads folder is a link; remove it." % os.path.basename(destination))
        changed = True
        if os.path.isfile(destination) and sha256_of_file(destination) == package["sha256"]:
            changed = False
            self.output("The package with the catalog's SHA-256 is in the cache; the delivery service was not asked.")
        else:
            urls = file_urls(package["category"])
            fetch_package(urls, destination, package["sha256"], package["max_size"] + SIZE_MARGIN_BYTES, suffixes)
            self.output("Downloaded and matched the catalog's SHA-256 %s" % package["sha256"])

        self.env["pathname"] = destination
        self.env["expected_sha256"] = package["sha256"]
        self.env["store_package_full_name"] = package["full_name"]
        self.env["store_package_version"] = package["version"]
        self.env["store_package_format"] = package["format"]
        self.env["store_framework_dependencies"] = frameworks
        self.env["download_changed"] = changed
        if changed:
            self.env[SUMMARY_KEY] = {
                "summary_text": "The following Microsoft Store packages were downloaded:",
                "report_fields": list(SUMMARY_FIELDS),
                "data": {
                    "product_id": product_id,
                    "package_full_name": package["full_name"],
                    "package_version": package["version"],
                    "framework_dependencies": frameworks,
                },
            }


if __name__ == "__main__":
    processor = MicrosoftStorePackageDownloader()
    processor.execute_shell()
