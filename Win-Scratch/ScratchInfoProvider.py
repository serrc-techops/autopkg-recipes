#!/usr/local/autopkg/python
"""Find the address and the version of the current Scratch 3 installer for Windows.

The Scratch Foundation serves its newest Windows installer through one redirect.
On 2026-11-13:

    https://downloads.scratch.mit.edu/desktop/Scratch%20Setup.exe
        answered 301 to https://downloads.scratch.mit.edu/desktop/Scratch%203.32.1%20Setup.exe
    that address
        answered 200 (the installer itself)

The fixed address is the one that the script of the Scratch download page names
for the direct Windows download (read on the same day).

This processor reads the Location header of the first answer and nothing else.
It follows NO redirect: a redirect is read, not obeyed. It outputs:

    url        the address that the Location names (it is not fetched here: the
               downloader fetches it)
    version    the version that the file name of that address names (3.32.1)

It outputs no hash: none was found published for the file. The version is the
publisher's word for the release, read from the name of the file; whether the
file itself carries the same version, and what the installed program reports,
were not read.

How strict it is:

  - Exactly one request is made, to the fixed address above. The answer must be
    a redirect (301, 302, 303, 307 or 308) with exactly one Location header of
    at most 2048 characters, without white space or control characters. A
    status that is not a redirect is an error.
  - The Location must be https on downloads.scratch.mit.edu and nothing else:
    no user name, no port, no query, no fragment.
  - The path must be exactly /desktop/Scratch%20<version>%20Setup.exe, with the
    spaces written as %20 and <version> made of two to four numbers joined by
    dots, each of at most nine digits, with at least one digit that is not
    zero. Any other path is an error, never a guess.
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
    "ScratchInfoProvider",
    "read_location",
    "location_values",
    "parse_address",
    "open_request",
]

HOST = "downloads.scratch.mit.edu"
START_URL = "https://downloads.scratch.mit.edu/desktop/Scratch%20Setup.exe"
FETCH_TIMEOUT_SECONDS = 120
REDIRECT_CODES = (301, 302, 303, 307, 308)
MAX_LOCATION_CHARS = 2048
USER_AGENT = "autopkg-ScratchInfoProvider"

# What a Location header may be made of: no space, no control character.
LOCATION_PATTERN = re.compile(r"[^\x00-\x20\x7f]+")
PATH_PATTERN = re.compile(
    r"/desktop/Scratch%20(?P<version>[0-9]{1,9}(?:\.[0-9]{1,9}){1,3})%20Setup\.exe"
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


def parse_address(address):
    """(version, url) of the address that the redirect names, or ValueError.
    The whole address must be the expected one: https on the fixed host, no
    user name, no port, no query, no fragment, and the expected path. The url
    is built from the fixed host and the checked path."""
    parts = urllib.parse.urlsplit(address)
    if parts.scheme != "https" or parts.hostname != HOST:
        raise ValueError("the redirect leads to %s, not to https on %s" % (address[:80], HOST))
    try:
        port = parts.port
    except ValueError:
        port = -1
    if parts.username is not None or parts.password is not None or port is not None or parts.fragment:
        raise ValueError("the redirect leads to an address with a user name, a port or a fragment")
    if parts.query or "?" in address:
        raise ValueError("the address of the installer has a query, which is not expected")
    match = PATH_PATTERN.fullmatch(parts.path)
    if not match:
        raise ValueError("the path of the installer is %r, not the expected form" % parts.path[:80])
    version = match.group("version")
    if not re.search(r"[1-9]", version):
        raise ValueError("the version in the file name is %r, which has no digit other than zero" % version)
    return version, "https://%s%s" % (HOST, parts.path)


class ScratchInfoProvider(Processor):
    description = __doc__
    input_variables = {}
    output_variables = {
        "url": {"description": "The address of the installer that the redirect of the fixed address names."},
        "version": {
            "description": "The version that the installer's file name names, such as 3.32.1. It is the label of the recipe."
        },
    }

    def main(self):
        location = read_location(START_URL, "Scratch's download address")
        try:
            version, url = parse_address(location)
        except ValueError as err:
            raise ProcessorError("Scratch's download address: %s." % err)

        self.env["url"] = url
        self.env["version"] = version
        self.output("Scratch's address names version %s: %s" % (version, url))
        self.output(
            "This is the version in the file's name: the file itself and the installed program "
            "were not compared with it."
        )


if __name__ == "__main__":
    processor = ScratchInfoProvider()
    processor.execute_shell()
