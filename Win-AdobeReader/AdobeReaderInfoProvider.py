#!/usr/local/autopkg/python
"""Find the current Adobe Acrobat Reader for Windows and the address of its installer.

One file of Adobe's servers is read: the public endpoint that Adobe's own
download page calls,

    https://rdc.adobe.io/reader/products?lang=en&platformArch=64&site=landing&os=Windows%2010&preInstalled=&country=US&nativeOs=Windows%2010&api_key=dc-get-adobereader-cdn

It answers a JSON object. Under "products", the key "reader" is a list of one
element with a "displayName" (Reader 2026.002.21931 English for Windows
(Recommended)), a "fileSize" and a "version" (26.002.21931). The other keys
("dcPro", "addons") are not used. The api_key in the address is not a secret:
it is the fixed public key that the download page itself sends.

The installer is NOT named in the answer. Its address is built from the
version by the scheme that Adobe's download server was seen to use:

    https://ardownload2.adobe.com/pub/adobe/reader/win/AcrobatDC/<packed>/AcroRdrDC<packed>_<language>.exe

where <packed> is the version with its dots removed (2600221931) and the
language is en_US or MUI. These are the 32-bit installers. Whether Adobe offers
an installer for x64 under another scheme is NOT established. Adobe publishes
no hash for the installer, so this processor outputs none: the download is not
verified by any step.

The processor outputs:

    url                    the address of the installer
    version                the version as the endpoint writes it (26.002.21931)
    adobe_packed_version   the version without dots (2600221931)

The `version` of this processor is the endpoint's text. A later step of the
recipe (WindowsExeVersion) replaces it by the version that the installer file
itself carries, and that one is the label for the package tool.

How strict it is:

  - The one fetch goes to a fixed host (rdc.adobe.io) over https. A redirect
    is NOT followed: it is an error. A status other than 200 is an error. The
    answer is limited in size (64 KiB) and in time (120 seconds), and must be
    UTF-8 text.
  - The answer must be a JSON object with products.reader a list of exactly one
    element, whose "version" has the form NN.NNN.NNNNN (two, three and five
    digits). Anything else is an error, and no address is built from it.
  - The language is en_US or MUI and nothing else.
  - No output is set unless every check passed.
"""
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "AdobeReaderInfoProvider",
    "LANGUAGES",
    "check_address",
    "fetch_text",
    "installer_url",
    "open_request",
    "packed_version",
    "parse_products",
]

PRODUCTS_URL = (
    "https://rdc.adobe.io/reader/products?lang=en&platformArch=64&site=landing"
    "&os=Windows%2010&preInstalled=&country=US&nativeOs=Windows%2010"
    "&api_key=dc-get-adobereader-cdn"
)
# The only host name that this processor talks to.
ALLOWED_HOST = "rdc.adobe.io"
# Where the installers are, by the scheme that was seen on 2026-10-02.
DOWNLOAD_BASE_URL = "https://ardownload2.adobe.com/pub/adobe/reader/win/AcrobatDC/"
INSTALLER_NAME = "AcroRdrDC%s_%s.exe"
FETCH_TIMEOUT_SECONDS = 120
# The answer is about 0.5 KB; more than this is not the endpoint.
MAX_PRODUCTS_BYTES = 64 * 1024
USER_AGENT = "autopkg-AdobeReaderInfoProvider"

DEFAULT_LANGUAGE = "en_US"
LANGUAGES = ("en_US", "MUI")
# Two, three and five digits: 26.002.21931.
VERSION_PATTERN = re.compile(r"[0-9]{2}\.[0-9]{3}\.[0-9]{5}")


def parse_products(text):
    """The version of the one Reader of the endpoint's answer, or ValueError."""
    try:
        data = json.loads(text)
    except ValueError as err:
        raise ValueError("it is not JSON: %s" % err)
    if not isinstance(data, dict):
        raise ValueError("it is not a JSON object")
    products = data.get("products")
    if not isinstance(products, dict):
        raise ValueError("it has no object products")
    readers = products.get("reader")
    if not isinstance(readers, list):
        raise ValueError("products.reader is not a list")
    if len(readers) != 1:
        raise ValueError("products.reader has %d elements, not exactly one" % len(readers))
    reader = readers[0]
    if not isinstance(reader, dict):
        raise ValueError("the element of products.reader is not an object")
    version = reader.get("version")
    if not isinstance(version, str):
        raise ValueError("the element of products.reader has no text version")
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(
            "the version %r is not of the form NN.NNN.NNNNN (two, three and five digits)" % version[:40]
        )
    return version


def packed_version(version):
    """The version without its dots (26.002.21931 gives 2600221931)."""
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise ValueError("the version %r is not of the form NN.NNN.NNNNN" % str(version)[:40])
    return version.replace(".", "")


def installer_url(packed, language):
    """The address of the installer for a packed version and a language."""
    if language not in LANGUAGES:
        raise ValueError("the language %r is not one of %s" % (str(language)[:40], ", ".join(LANGUAGES)))
    if not isinstance(packed, str) or not re.fullmatch(r"[0-9]{10}", packed):
        raise ValueError("the packed version %r is not ten digits" % str(packed)[:40])
    return "%s%s/%s" % (DOWNLOAD_BASE_URL, packed, INSTALLER_NAME % (packed, language))


def check_address(url):
    """ValueError unless the address is https, on the fixed host, with no user
    name, no port and no fragment. This is checked for every fetch."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname != ALLOWED_HOST:
        raise ValueError("the address %s is not on the fixed host of Adobe" % url[:80])
    if parts.username is not None or parts.password is not None or parts.port is not None or parts.fragment:
        raise ValueError("the address %s has a user name, a port or a fragment" % url[:80])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The endpoint is a plain answer of one fixed host. A redirect would send
    the request elsewhere: it is an error (HTTPError)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request):
    """Send the request without following redirects."""
    opener = urllib.request.build_opener(NoRedirect)
    return opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)


def fetch_text(url, max_bytes, what):
    """GET the address and return its text. The one place where the network is
    used: tests replace this function or open_request."""
    try:
        check_address(url)
    except ValueError as err:
        raise ProcessorError("%s: %s." % (what, err))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with open_request(request) as response:
            status = getattr(response, "status", 200)
            body = response.read(max_bytes + 1)
    except urllib.error.HTTPError as err:
        redirect = " (a redirect is not followed)" if 300 <= err.code < 400 else ""
        message = "%s answered %s %s%s." % (what, err.code, err.reason, redirect)
        err.close()
        raise ProcessorError(message)
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("%s could not be fetched: %s" % (what, err))
    if status != 200:
        raise ProcessorError("%s answered %s, not 200." % (what, status))
    if len(body) > max_bytes:
        raise ProcessorError("%s is larger than %d bytes." % (what, max_bytes))
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as err:
        raise ProcessorError("%s is not UTF-8 text: %s" % (what, err))


class AdobeReaderInfoProvider(Processor):
    description = __doc__
    input_variables = {
        "adobe_language": {
            "required": False,
            "default": DEFAULT_LANGUAGE,
            "description": "The installer: en_US (English) or MUI (all languages). Nothing else is accepted.",
        },
    }
    output_variables = {
        "url": {"description": "The address of the installer on Adobe's download server."},
        "version": {"description": "The version as the endpoint writes it, such as 26.002.21931."},
        "adobe_packed_version": {"description": "The version without dots, such as 2600221931."},
    }

    def main(self):
        language = self.env.get("adobe_language", DEFAULT_LANGUAGE)
        if not isinstance(language, str) or language not in LANGUAGES:
            raise ProcessorError(
                "adobe_language must be one of %s: %r" % (", ".join(LANGUAGES), str(language)[:40])
            )
        text = fetch_text(PRODUCTS_URL, MAX_PRODUCTS_BYTES, "Adobe's products file")
        try:
            version = parse_products(text)
        except ValueError as err:
            raise ProcessorError("Adobe's products file: %s." % err)
        packed = packed_version(version)

        self.env["url"] = installer_url(packed, language)
        self.env["version"] = version
        self.env["adobe_packed_version"] = packed
        self.output("Current Adobe Acrobat Reader according to Adobe's products file: %s" % version)


if __name__ == "__main__":
    processor = AdobeReaderInfoProvider()
    processor.execute_shell()
