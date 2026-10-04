#!/usr/local/autopkg/python
"""Find the address of the current Foxit PDF Reader installer for Windows.

Foxit serves its newest installer through a chain of redirects. On 2026-10-02:

    https://www.foxit.com/downloads/latest.html?product=Foxit-Reader&platform=Windows&version=&package_type=exe&language=L10N
        answers 301 to https://www.foxit.com/downloads/latest/?product=... (the same query)
    https://www.foxit.com/downloads/latest/?product=...
        answers 307 to https://cdn01.foxitsoftware.com/product/reader/desktop/win/<version>/FoxitPDFReader<digits>_L10N_Setup_Prom_x64.exe
    that address
        answers 302 to a signed, short-lived address on a cloud storage host.

This processor reads the Location header of the first two answers and nothing
else. It follows NO redirect: a redirect is read, not obeyed. It outputs:

    url                      the address on cdn01.foxitsoftware.com (the third
                             answer is not fetched: the downloader follows it)
    foxit_address_version    the version that the address names (2026.2.1)

It outputs no hash and no `version`: Foxit publishes no hash, and the version
label of a recipe comes from the installer file itself (WindowsExeVersion). The
address's version is only the name of the release folder, and is shown so that
a person can compare it with the version that the file shows.

How strict it is:

  - Exactly two requests are made. The first goes to www.foxit.com, built from
    the inputs. Each answer must be a redirect (301, 302, 303, 307 or 308) with
    exactly one Location header of at most 2048 characters, without white space
    or control characters. A status that is not a redirect is an error.
  - The first Location must be https on www.foxit.com. The second must be https
    on cdn01.foxitsoftware.com and nothing else: no user name, no port, no query,
    no fragment.
  - The second Location must be exactly
    /product/reader/desktop/win/<version>/FoxitPDFReader<digits>_<language>_Setup_Prom_x64.exe
    with <version> made of numbers and dots, <digits> numbers, and <language>
    equal to the input. Any other path is an error, never a guess.
  - The answer is never read: no body is fetched, and each request has a time
    limit of 120 seconds.
  - The inputs are names (letters, digits and "-"), never paths. Only the
    defaults were read from Foxit's servers: another product, language or
    package type is sent as asked, and an answer of another shape is an error.
  - No output is set unless every check passed.
"""
import http.client
import re
import urllib.error
import urllib.parse
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "FoxitInfoProvider",
    "checked_name",
    "start_url",
    "read_location",
    "location_values",
    "checked_location",
    "parse_final_address",
    "open_request",
]

START_HOST = "www.foxit.com"
FINAL_HOST = "cdn01.foxitsoftware.com"
START_URL_BASE = "https://www.foxit.com/downloads/latest.html"
PLATFORM = "Windows"
FETCH_TIMEOUT_SECONDS = 120
REDIRECT_CODES = (301, 302, 303, 307, 308)
MAX_LOCATION_CHARS = 2048
USER_AGENT = "autopkg-FoxitInfoProvider"

DEFAULT_PRODUCT = "Foxit-Reader"
DEFAULT_LANGUAGE = "L10N"
DEFAULT_PACKAGE_TYPE = "exe"
NAME_PATTERN = re.compile(r"[A-Za-z0-9-]+")
# What a Location header may be made of: no space, no control character.
LOCATION_PATTERN = re.compile(r"[^\x00-\x20\x7f]+")
FINAL_PATH_PATTERN = re.compile(
    r"/product/reader/desktop/win/(?P<version>[0-9]+(?:\.[0-9]+)+)"
    r"/FoxitPDFReader(?P<digits>[0-9]+)_(?P<language>[A-Za-z0-9-]+)_Setup_Prom_x64\.exe"
)


def checked_name(value, name, default):
    """An input that is a name: letters, digits and '-', no more."""
    if value is None:
        value = default
    if not isinstance(value, str) or not NAME_PATTERN.fullmatch(value):
        raise ProcessorError(
            "%s must be letters, digits and '-' (a name, not a path): %r" % (name, str(value)[:40])
        )
    return value


def start_url(product, language, package_type):
    """The first address. The query keeps the empty `version=` that Foxit's own
    page sends."""
    query = urllib.parse.urlencode([
        ("product", product),
        ("platform", PLATFORM),
        ("version", ""),
        ("package_type", package_type),
        ("language", language),
    ])
    return "%s?%s" % (START_URL_BASE, query)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The answers are read, not obeyed: a redirect would send the request
    elsewhere. It becomes an HTTPError that holds the headers."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request):
    """Send the request without following redirects."""
    opener = urllib.request.build_opener(NoRedirect)
    return opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)


def location_values(headers):
    """The values of every Location header, as a list (empty when there is none)."""
    if headers is None:
        return []
    get_all = getattr(headers, "get_all", None)
    if get_all is not None:
        return list(get_all("Location") or [])
    value = headers.get("Location")
    return [] if value is None else [value]


def read_location(url, what):
    """GET the address and return the one Location header of its redirect, made
    absolute. The one place where the network is used: tests replace this
    function or open_request. No body is read."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with open_request(request) as response:
            status = getattr(response, "status", 200)
        raise ProcessorError("%s answered %s, not a redirect." % (what, status))
    except urllib.error.HTTPError as err:
        code, reason, headers = err.code, err.reason, err.headers
        values = location_values(headers)
        err.close()
        if code not in REDIRECT_CODES:
            raise ProcessorError("%s answered %s %s, not a redirect." % (what, code, reason))
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("%s could not be fetched: %s" % (what, err))
    if len(values) != 1:
        raise ProcessorError(
            "%s answered %s with %d Location headers, not exactly one." % (what, code, len(values))
        )
    location = values[0]
    if not isinstance(location, str) or not location or len(location) > MAX_LOCATION_CHARS:
        raise ProcessorError(
            "%s answered %s with a Location that is empty or longer than %d characters."
            % (what, code, MAX_LOCATION_CHARS)
        )
    if not LOCATION_PATTERN.fullmatch(location):
        raise ProcessorError("%s answered %s with a Location that has a space or a control character." % (what, code))
    return urllib.parse.urljoin(url, location)


def checked_location(address, host, what):
    """ValueError unless the address is https on exactly `host`, with no user
    name, no port and no fragment."""
    parts = urllib.parse.urlsplit(address)
    if parts.scheme != "https" or parts.hostname != host:
        raise ValueError("%s leads to %s, not to https on %s" % (what, address[:80], host))
    try:
        port = parts.port
    except ValueError:
        port = -1
    if parts.username is not None or parts.password is not None or port is not None or parts.fragment:
        raise ValueError("%s leads to an address with a user name, a port or a fragment" % what)
    return parts


def parse_final_address(address, language):
    """(version, digits, url) of the address on the final host, or ValueError.
    The whole address must be the expected one: no query, no other path. The
    url is built from the fixed host and the checked path."""
    parts = checked_location(address, FINAL_HOST, "the second answer")
    if parts.query or "?" in address:
        raise ValueError("the address of the installer has a query, which is not expected")
    match = FINAL_PATH_PATTERN.fullmatch(parts.path)
    if not match:
        raise ValueError("the path of the installer is %r, not the expected form" % parts.path[:80])
    if match.group("language") != language:
        raise ValueError(
            "the installer's file name names the language %r, not the asked %r"
            % (match.group("language"), language)
        )
    return match.group("version"), match.group("digits"), "https://%s%s" % (FINAL_HOST, parts.path)


class FoxitInfoProvider(Processor):
    description = __doc__
    input_variables = {
        "foxit_product": {
            "required": False,
            "default": DEFAULT_PRODUCT,
            "description": "The product as Foxit's download address writes it. Letters, digits and '-'.",
        },
        "foxit_language": {
            "required": False,
            "default": DEFAULT_LANGUAGE,
            "description": "The language as Foxit writes it: L10N is the multi-language installer. Letters, digits and '-'.",
        },
        "foxit_package_type": {
            "required": False,
            "default": DEFAULT_PACKAGE_TYPE,
            "description": "The package type as Foxit writes it: exe. Letters, digits and '-'.",
        },
    }
    output_variables = {
        "url": {"description": "The address of the installer on Foxit's download server (cdn01)."},
        "foxit_address_version": {
            "description": "The version that the address names, such as 2026.2.1. It is not the label of the recipe."
        },
    }

    def main(self):
        product = checked_name(self.env.get("foxit_product"), "foxit_product", DEFAULT_PRODUCT)
        language = checked_name(self.env.get("foxit_language"), "foxit_language", DEFAULT_LANGUAGE)
        package_type = checked_name(self.env.get("foxit_package_type"), "foxit_package_type", DEFAULT_PACKAGE_TYPE)

        first = start_url(product, language, package_type)
        second = read_location(first, "Foxit's download address")
        try:
            checked_location(second, START_HOST, "the first answer")
        except ValueError as err:
            raise ProcessorError("Foxit's download address: %s." % err)
        final = read_location(second, "Foxit's second download address")
        try:
            version, _digits, url = parse_final_address(final, language)
        except ValueError as err:
            raise ProcessorError("Foxit's second download address: %s." % err)

        self.env["url"] = url
        self.env["foxit_address_version"] = version
        self.output("Foxit's address names version %s: %s" % (version, url))
        self.output(
            "This is the name of the release folder, not the label of the recipe: "
            "the label is read from the file."
        )


if __name__ == "__main__":
    processor = FoxitInfoProvider()
    processor.execute_shell()
