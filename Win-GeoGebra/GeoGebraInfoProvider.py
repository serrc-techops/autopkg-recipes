#!/usr/local/autopkg/python
"""Find the address of the current GeoGebra Classic 6 MSI for Windows.

GeoGebra serves its newest MSI through one redirect. On 2026-11-13:

    https://download.geogebra.org/package/win-msi6
        answered 302 with the RELATIVE Location
        /installers/6.0/GeoGebra-Windows-Installer-6-0-936-0.msi

This processor reads the Location header of that one answer and nothing else.
It follows NO redirect: a redirect is read, not obeyed. It outputs:

    url                        the address of the MSI on download.geogebra.org
                               (the downloader fetches it)
    geogebra_address_version   the four numbers of the file name with dots
                               instead of hyphens (6.0.936.0 on 2026-11-13)

It outputs no hash and no `version`: GeoGebra publishes no hash (none was seen
in the index of the folder on 2026-11-13), and the version label of an MSI is
read from the MSI itself by the importer (its ProductVersion). The address's
version is shown so that a person can compare it with that label.

How strict it is:

  - Exactly one request is made, to the fixed address above. The answer must be
    a redirect (301, 302, 303, 307 or 308) with exactly one Location header of
    at most 2048 characters, without white space or control characters. A
    status that is not a redirect is an error.
  - The Location may be relative: it is resolved against the fixed address. The
    result must be https on download.geogebra.org and nothing else: no user
    name, no port, no query, no fragment.
  - The path must be exactly
    /installers/6.0/GeoGebra-Windows-Installer-<n>-<n>-<n>-<n>.msi
    with each <n> made of the digits 0 to 9. Any other path is an error, never
    a guess: another folder than 6.0 stops the run too.
  - The answer is never read: no body is fetched, and the request has a time
    limit of 120 seconds.
  - No output is set unless every check passed.
"""
import http.client
import re
import urllib.error
import urllib.parse
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "GeoGebraInfoProvider",
    "read_location",
    "location_values",
    "checked_location",
    "parse_address",
    "open_request",
]

HOST = "download.geogebra.org"
START_URL = "https://download.geogebra.org/package/win-msi6"
FETCH_TIMEOUT_SECONDS = 120
REDIRECT_CODES = (301, 302, 303, 307, 308)
MAX_LOCATION_CHARS = 2048
USER_AGENT = "autopkg-GeoGebraInfoProvider"

# What a Location header may be made of: no space, no control character.
LOCATION_PATTERN = re.compile(r"[^\x00-\x20\x7f]+")
PATH_PATTERN = re.compile(
    r"/installers/6\.0/GeoGebra-Windows-Installer-"
    r"(?P<numbers>[0-9]+-[0-9]+-[0-9]+-[0-9]+)\.msi"
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The answer is read, not obeyed: a redirect would send the request
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
    absolute against the address. The one place where the network is used:
    tests replace this function or open_request. No body is read."""
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


def checked_location(address):
    """ValueError unless the address is https on exactly HOST, with no user
    name, no port and no fragment."""
    parts = urllib.parse.urlsplit(address)
    if parts.scheme != "https" or parts.hostname != HOST:
        raise ValueError("the answer leads to %s, not to https on %s" % (address[:80], HOST))
    try:
        port = parts.port
    except ValueError:
        port = -1
    if parts.username is not None or parts.password is not None or port is not None or parts.fragment:
        raise ValueError("the answer leads to an address with a user name, a port or a fragment")
    return parts


def parse_address(address):
    """(address version, url) of the MSI's address, or ValueError. The whole
    address must be the expected one: no query, no other path. The url is built
    from the fixed host and the checked path."""
    parts = checked_location(address)
    if parts.query or "?" in address:
        raise ValueError("the address of the MSI has a query, which is not expected")
    match = PATH_PATTERN.fullmatch(parts.path)
    if not match:
        raise ValueError("the path of the MSI is %r, not the expected form" % parts.path[:100])
    version = match.group("numbers").replace("-", ".")
    return version, "https://%s%s" % (HOST, parts.path)


class GeoGebraInfoProvider(Processor):
    description = __doc__
    input_variables = {}
    output_variables = {
        "url": {"description": "The address of the MSI on GeoGebra's download server."},
        "geogebra_address_version": {
            "description": "The four numbers of the MSI's file name, with dots instead of hyphens. "
                           "It is not the label of the recipe."
        },
    }

    def main(self):
        address = read_location(START_URL, "GeoGebra's download address")
        try:
            version, url = parse_address(address)
        except ValueError as err:
            raise ProcessorError("GeoGebra's download address: %s." % err)

        self.env["url"] = url
        self.env["geogebra_address_version"] = version
        self.output("GeoGebra's address names version %s: %s" % (version, url))
        self.output(
            "This is the name of the file, not the label of the recipe: "
            "the label is the MSI's own ProductVersion."
        )


if __name__ == "__main__":
    processor = GeoGebraInfoProvider()
    processor.execute_shell()
