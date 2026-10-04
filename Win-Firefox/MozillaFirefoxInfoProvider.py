#!/usr/local/autopkg/python
"""Find the current Firefox for Windows and the SHA-256 that Mozilla publishes for it.

Two files of Mozilla's servers are read:

    https://product-details.mozilla.org/1.0/firefox_versions.json
        A JSON object. The key LATEST_FIREFOX_VERSION holds the version of the
        release channel (141.0 or 141.0.1), the key FIREFOX_ESR the version of
        the ESR channel (Mozilla may write it with the suffix "esr").
    https://download-installer.cdn.mozilla.net/pub/firefox/releases/<version>/SHA256SUMS
        A text file with one line for every file of the release: 64 hex digits,
        two spaces, and the path of the file relative to the release folder, such
        as "win64/en-US/Firefox Setup 141.0.exe".

The installer is read from the same release folder:

    https://download-installer.cdn.mozilla.net/pub/firefox/releases/<version>/<platform>/<locale>/Firefox%20Setup%20<version>.exe

The processor outputs:

    url              the address of the installer (the spaces of its name are %20)
    version          the version as numbers (141.0, 141.0.1), without any suffix
    expected_sha256  the SHA-256 that SHA256SUMS gives for exactly that file

The file and the hash come from one server, and the file's own address is built
from the same parts as the line that is looked up. The check shows that the file
is what Mozilla published. It does not help if Mozilla's server is changed.

How strict it is:

  - Both fetches go to a fixed address over https. A redirect is NOT followed:
    it is an error. A status other than 200 is an error. The answer is limited
    in size (1 MB for the version file, 8 MB for SHA256SUMS) and in time (120
    seconds), and must be UTF-8 text.
  - The channel is "release" or "esr" and nothing else. The platform and the
    locale are letters, digits, "-" and "_", never a path.
  - The version of the JSON must have the form of a version (numbers, and for
    the ESR channel an optional "esr"). Anything else is an error, and no
    address is built from it.
  - Every line of SHA256SUMS must be 64 hex digits, two spaces and a path
    without control characters that does not begin or end with a space. A line
    of another form is an error, never skipped. The one line whose path is exactly
    <platform>/<locale>/Firefox Setup <version>.exe is taken. No such line, or
    more than one, is an error.
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
    "MozillaFirefoxInfoProvider",
    "CHANNELS",
    "check_address",
    "checked_text",
    "installer_name",
    "installer_url",
    "sha256_of",
    "fetch_text",
    "open_request",
    "parse_version",
]

VERSIONS_URL = "https://product-details.mozilla.org/1.0/firefox_versions.json"
RELEASES_BASE_URL = "https://download-installer.cdn.mozilla.net/pub/firefox/releases/"
# The only host names that this processor talks to.
ALLOWED_HOSTS = ("product-details.mozilla.org", "download-installer.cdn.mozilla.net")
FETCH_TIMEOUT_SECONDS = 120
# The version file is about 1 KB; SHA256SUMS is a few hundred KB.
MAX_VERSIONS_BYTES = 1024 * 1024
MAX_SUMS_BYTES = 8 * 1024 * 1024
USER_AGENT = "autopkg-MozillaFirefoxInfoProvider"

DEFAULT_CHANNEL = "release"
DEFAULT_PLATFORM = "win64"
DEFAULT_LOCALE = "en-US"
# The channel is the key of the version file that holds its version.
CHANNELS = {"release": "LATEST_FIREFOX_VERSION", "esr": "FIREFOX_ESR"}

NUMBERS_PATTERN = r"[0-9]+\.[0-9]+(?:\.[0-9]+)?"
RELEASE_VERSION_PATTERN = re.compile(NUMBERS_PATTERN)
ESR_VERSION_PATTERN = re.compile(r"(" + NUMBERS_PATTERN + r")(?:esr)?")
NAME_PART_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
# One line of SHA256SUMS: the hash, two spaces, a path of printable characters
# that neither begins nor ends with a space.
SUMS_LINE_PATTERN = re.compile(r"([0-9A-Fa-f]{64})  ([^\x00-\x1f\x7f ](?:[^\x00-\x1f\x7f]*[^\x00-\x1f\x7f ])?)")


def parse_version(text, channel):
    """(folder, version) of a version text from the version file, or ValueError.

    `folder` is the text as Mozilla writes it, which names the release folder
    (the ESR channel may carry the suffix "esr"). `version` is its numbers only,
    which is the label that goes on to the package tool."""
    if not isinstance(text, str):
        raise ValueError("the version is not text: %s" % repr(text)[:40])
    if channel == "esr":
        match = ESR_VERSION_PATTERN.fullmatch(text)
        if match:
            return text, match.group(1)
    elif RELEASE_VERSION_PATTERN.fullmatch(text):
        return text, text
    raise ValueError("the version %r does not have the form of a %s version" % (text[:40], channel))


def installer_name(folder_version):
    """The file name of the installer. It has spaces."""
    return "Firefox Setup %s.exe" % folder_version


def installer_url(folder_version, platform, locale):
    """The address of the installer: the spaces of its name are written %20."""
    return "%s%s/%s/%s/%s" % (
        RELEASES_BASE_URL, folder_version, platform, locale,
        urllib.parse.quote(installer_name(folder_version), safe=""),
    )


def check_address(url):
    """ValueError unless the address is https, on one of the fixed hosts, with no
    user name, no port and no fragment. This is checked for every fetch."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise ValueError("the address %s is not on a fixed host of Mozilla" % url[:80])
    if parts.username is not None or parts.password is not None or parts.port is not None or parts.fragment:
        raise ValueError("the address %s has a user name, a port or a fragment" % url[:80])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Both files are plain answers of fixed hosts. A redirect would send the
    request elsewhere: it is an error (HTTPError)."""

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


def checked_text(value, name, default):
    """An input that is a name part: letters, digits, '-' and '_', no more."""
    if value is None:
        value = default
    if not isinstance(value, str) or not NAME_PART_PATTERN.fullmatch(value):
        raise ProcessorError(
            "%s must be letters, digits, '-' and '_' (a name, not a path): %r" % (name, str(value)[:40])
        )
    return value


def sha256_of(sums_text, path):
    """The SHA-256 of the one line of SHA256SUMS whose path is exactly `path`
    (lower-case hex), or ValueError. Every line is checked, not only that one."""
    found = []
    for number, line in enumerate(sums_text.split("\n"), 1):
        if line == "":
            continue  # the file ends with a line break, and may have empty lines
        match = SUMS_LINE_PATTERN.fullmatch(line)
        if not match:
            raise ValueError("line %d is not a SHA-256, two spaces and a path" % number)
        if match.group(2) == path:
            found.append(match.group(1).lower())
    if not found:
        raise ValueError("it has no line for %s" % path)
    if len(found) > 1:
        raise ValueError("it has %d lines for %s, not exactly one" % (len(found), path))
    return found[0]


class MozillaFirefoxInfoProvider(Processor):
    description = __doc__
    input_variables = {
        "firefox_channel": {
            "required": False,
            "default": DEFAULT_CHANNEL,
            "description": "The channel: release or esr. Nothing else is accepted.",
        },
        "firefox_platform": {
            "required": False,
            "default": DEFAULT_PLATFORM,
            "description": "The platform folder of the release, such as win64. Letters, digits, '-' and '_'.",
        },
        "firefox_locale": {
            "required": False,
            "default": DEFAULT_LOCALE,
            "description": "The locale folder of the release, such as en-US. Letters, digits, '-' and '_'.",
        },
    }
    output_variables = {
        "url": {"description": "The address of the installer on Mozilla's download server."},
        "version": {"description": "The version as numbers, such as 141.0 or 141.0.1."},
        "expected_sha256": {
            "description": "The SHA-256 that Mozilla's SHA256SUMS gives for the installer (lower-case hex)."
        },
    }

    def main(self):
        channel = self.env.get("firefox_channel", DEFAULT_CHANNEL)
        if not isinstance(channel, str) or channel not in CHANNELS:
            raise ProcessorError(
                "firefox_channel must be one of %s: %r" % (", ".join(sorted(CHANNELS)), str(channel)[:40])
            )
        platform = checked_text(self.env.get("firefox_platform"), "firefox_platform", DEFAULT_PLATFORM)
        locale = checked_text(self.env.get("firefox_locale"), "firefox_locale", DEFAULT_LOCALE)

        text = fetch_text(VERSIONS_URL, MAX_VERSIONS_BYTES, "Mozilla's version file")
        key = CHANNELS[channel]
        try:
            try:
                versions = json.loads(text)
            except ValueError as err:
                raise ValueError("it is not JSON: %s" % err)
            if not isinstance(versions, dict):
                raise ValueError("it is not a JSON object")
            if key not in versions:
                raise ValueError("it has no key %s" % key)
            folder, version = parse_version(versions[key], channel)
        except ValueError as err:
            raise ProcessorError("Mozilla's version file: %s." % err)

        sums_url = "%s%s/SHA256SUMS" % (RELEASES_BASE_URL, folder)
        sums = fetch_text(sums_url, MAX_SUMS_BYTES, "Mozilla's SHA256SUMS")
        path = "%s/%s/%s" % (platform, locale, installer_name(folder))
        try:
            sha256 = sha256_of(sums, path)
        except ValueError as err:
            raise ProcessorError("Mozilla's SHA256SUMS of %s: %s." % (folder, err))

        self.env["url"] = installer_url(folder, platform, locale)
        self.env["version"] = version
        self.env["expected_sha256"] = sha256
        self.output("Current Firefox of channel %s: %s" % (channel, version))
        self.output("Mozilla's SHA-256: %s" % sha256)


if __name__ == "__main__":
    processor = MozillaFirefoxInfoProvider()
    processor.execute_shell()
