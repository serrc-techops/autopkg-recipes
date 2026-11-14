#!/usr/local/autopkg/python
"""Find the newest GIMP installer for Windows on the project's download server.

The facts of the server were read on 2026-11-13 (see the README).

https://download.gimp.org/gimp/ is an HTML directory index (200, no redirect).
Its links name the series folders, v2.10/ ... v3.0/, v3.1/, v3.2/. The
processor keeps the links that are exactly v<number>.<number>/ and chooses one
series:

    by default   the highest series whose second number is EVEN (3.2, not 3.1)
    gimp_series  a series named by the override, such as 3.0; it must be in the index

By the project's convention a series with an odd second number (3.1, 2.99) is
a development series. That convention is the writer's knowledge; it was NOT
read from the project's pages. An odd series is taken only when
gimp_allow_development is true, also when gimp_series names it.

https://download.gimp.org/gimp/v<series>/windows/ is the index of the series
(200, no redirect). Its installers are named gimp-<version>-setup.exe, and a
re-issued installer of the same GIMP version is gimp-<version>-setup-<n>.exe
(seen in v3.0/windows/: setup.exe, setup-1.exe, setup-2.exe). The processor
keeps the links that are exactly of that form, with a version of three numbers
(a release candidate, gimp-3.2.0-RC1-setup.exe, is not one), takes the highest
version and, for it, the highest revision (no suffix is revision 0). Every
version must belong to the series of its folder. The file
0.0_LATEST-IS-<version> of the folder is NOT used.

The version label is the GIMP version (3.0.8), never the revision. A later
revision of a version that a repository has already is therefore "Nothing new"
for the importers: a person imports it by hand if it matters.

The hash comes from SHA256SUMS in the same folder: one line per file, 64 hex
digits, two spaces, the file name. Every line must have that form, and the line
of the chosen installer must be there exactly once.

THE HASH IS NOT THE PUBLISHER'S OWN. On 2026-11-13 download.gimp.org answered
both the installer and SHA256SUMS with 302 Found and a Location on a mirror
host, which differs by time and place. So this processor follows AT MOST ONE
redirect for SHA256SUMS, and only to an https address without a user name, a
port, a query or a fragment, whose path ends with /gimp/v<series>/windows/SHA256SUMS.
It outputs the host that served the file (gimp_sha256sums_host), and the run
prints it. The installer is downloaded by URLDownloader from the
download.gimp.org address, which follows the redirect to a mirror (maybe the
same, maybe another). The check against this hash shows that the file is the
file that a mirror's SHA256SUMS names, undamaged: a transfer check, not proof
that either file is what the project published.

The two index pages are read from download.gimp.org and follow no redirect (a
redirect is an error). Every fetch is https, has a size limit and a time limit.

It outputs:

    url                   the download.gimp.org address of the installer
    version               the GIMP version, three numbers (3.2.8)
    expected_sha256       the SHA-256 that the (mirror's) SHA256SUMS gives for the file
    gimp_chosen_series    the series that was read (3.2)
    gimp_installer_name   the file name of the installer (gimp-3.2.8-setup.exe)
    gimp_sha256sums_host  the host that served SHA256SUMS

No output is set unless every check passed.
"""
import html
import http.client
import re
import urllib.error
import urllib.parse
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "GimpInfoProvider",
    "parse_bool",
    "series_key",
    "is_development",
    "extract_series",
    "choose_series",
    "series_folder_url",
    "find_installer",
    "parse_sums",
    "check_redirect_target",
    "fetch_text",
    "fetch_sums",
    "open_request",
]

BASE_URL = "https://download.gimp.org/gimp/"
BASE_HOST = "download.gimp.org"
FETCH_TIMEOUT_SECONDS = 120
# The top index is a few kilobytes, the index of a series folder too.
MAX_INDEX_BYTES = 1024 * 1024
# SHA256SUMS of a series is under 1 KB (708 bytes for v3.2 on 2026-11-13).
MAX_SUMS_BYTES = 64 * 1024
USER_AGENT = "autopkg-GimpInfoProvider"
SUMS_NAME = "SHA256SUMS"

NUMBER = r"(?:0|[1-9][0-9]*)"
SERIES_PATTERN = re.compile(r"%s\.%s" % (NUMBER, NUMBER), re.ASCII)
SERIES_LINK_PATTERN = re.compile(r"v(%s\.%s)/" % (NUMBER, NUMBER), re.ASCII)
VERSION_PATTERN = re.compile(r"%s\.%s\.%s" % (NUMBER, NUMBER, NUMBER), re.ASCII)
INSTALLER_PATTERN = re.compile(
    r"gimp-(%s\.%s\.%s)-setup(?:-([1-9][0-9]*))?\.exe" % (NUMBER, NUMBER, NUMBER), re.ASCII
)
# A link of the index: double or single quotes around the address.
LINK_PATTERN = re.compile(r"<a\s(?:[^>]*?\s)?href\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", re.I)
# One line of SHA256SUMS: the hash, two spaces, a file name without a space or a slash.
SUMS_LINE_PATTERN = re.compile(r"([0-9A-Fa-f]{64})  ([^\x00-\x20\x7f/\\]+)")
HOST_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", re.ASCII)

TRUE_TEXTS = ("true", "yes", "1")
FALSE_TEXTS = ("false", "no", "0", "")


def parse_bool(value, name):
    """A boolean input: a boolean, or the text true/yes/1 or false/no/0 (or empty)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in TRUE_TEXTS:
        return True
    if isinstance(value, str) and value.strip().lower() in FALSE_TEXTS:
        return False
    raise ProcessorError("%s must be true or false: %r" % (name, str(value)[:24]))


def series_key(series):
    """The two numbers of a series as a tuple, or None when the text is not
    two numbers separated by a dot (no sign, no space, no leading zero)."""
    if not isinstance(series, str) or not SERIES_PATTERN.fullmatch(series):
        return None
    return tuple(int(part) for part in series.split("."))


def version_key(version):
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        return None
    return tuple(int(part) for part in version.split("."))


def is_development(series):
    """True for a series whose second number is odd (3.1, 2.99)."""
    key = series_key(series)
    if key is None:
        raise ValueError("%r is not a series of two numbers" % str(series)[:24])
    return key[1] % 2 == 1


def links(index_text):
    for double, single in LINK_PATTERN.findall(index_text):
        yield html.unescape(double or single)


def extract_series(index_text):
    """The series that the index links to, sorted by their numbers (oldest
    first), or raise ValueError."""
    found = set()
    for address in links(index_text):
        match = SERIES_LINK_PATTERN.fullmatch(address)
        if match:
            found.add(match.group(1))
    if not found:
        raise ValueError("the index has no link to a series folder (v<number>.<number>/)")
    return sorted(found, key=series_key)


def choose_series(available, pinned, allow_development):
    """The series to read, or raise ValueError. `pinned` is "" for the default."""
    if pinned:
        if series_key(pinned) is None:
            raise ValueError("gimp_series %r is not two numbers such as 3.0" % pinned[:24])
        if pinned not in available:
            raise ValueError("the index has no folder v%s/" % pinned)
        if is_development(pinned) and not allow_development:
            raise ValueError(
                "series %s has an odd second number (a development series); "
                "set gimp_allow_development to true to take it" % pinned
            )
        return pinned
    candidates = [series for series in available if allow_development or not is_development(series)]
    if not candidates:
        raise ValueError("the index has no stable series (an even second number)")
    return max(candidates, key=series_key)


def series_folder_url(series):
    if series_key(series) is None:
        raise ValueError("%r is not a series of two numbers" % str(series)[:24])
    return "%sv%s/windows/" % (BASE_URL, series)


def find_installer(index_text, series):
    """(version, revision, file name) of the newest installer that the index of
    the series links to, or raise ValueError."""
    wanted = series_key(series)
    if wanted is None:
        raise ValueError("%r is not a series of two numbers" % str(series)[:24])
    found = {}
    for address in links(index_text):
        match = INSTALLER_PATTERN.fullmatch(address)
        if not match:
            continue
        version = match.group(1)
        revision = int(match.group(2) or 0)
        if version_key(version)[:2] != wanted:
            raise ValueError("the folder of series %s links to an installer of another series: %r"
                             % (series, address[:60]))
        found[(version_key(version), revision)] = (version, revision, address)
    if not found:
        raise ValueError("the index has no link to gimp-<version>-setup.exe")
    return found[max(found)]


def parse_sums(text, file_name):
    """The SHA-256 (lower case) of the one line of SHA256SUMS for `file_name`,
    or raise ValueError. Every line is checked, not only that one."""
    hashes = []
    for number, line in enumerate(text.split("\n"), 1):
        line = line.rstrip("\r")
        if line == "":
            continue
        match = SUMS_LINE_PATTERN.fullmatch(line)
        if not match:
            raise ValueError("line %d is not a SHA-256, two spaces and a file name" % number)
        if match.group(2) == file_name:
            hashes.append(match.group(1).lower())
    if not hashes:
        raise ValueError("it has no line for %s" % file_name)
    if len(hashes) > 1:
        raise ValueError("it has %d lines for %s, not exactly one" % (len(hashes), file_name))
    return hashes[0]


def check_redirect_target(location, series):
    """The address a redirect of SHA256SUMS may lead to, or raise ValueError:
    https, a plain host name, no user name, port, query or fragment, and a
    path that ends with /gimp/v<series>/windows/SHA256SUMS."""
    if not isinstance(location, str) or not location:
        raise ValueError("the redirect has no Location")
    parts = urllib.parse.urlsplit(location)
    if parts.scheme != "https":
        raise ValueError("the redirect leads to an address that is not https: %s" % location[:100])
    host = parts.hostname or ""
    if not HOST_PATTERN.fullmatch(host) or "." not in host:
        raise ValueError("the redirect leads to an address without a plain host name: %s" % location[:100])
    if parts.username is not None or parts.password is not None or parts.port is not None:
        raise ValueError("the redirect leads to an address with a user name or a port: %s" % location[:100])
    if parts.query or parts.fragment:
        raise ValueError("the redirect leads to an address with a query or a fragment: %s" % location[:100])
    tail = "/gimp/v%s/windows/%s" % (series, SUMS_NAME)
    if not parts.path.endswith(tail) or "/../" in parts.path or "/./" in parts.path or "//" in parts.path:
        raise ValueError("the redirect leads to a path that does not end with %s: %s" % (tail, location[:100]))
    return urllib.parse.urlunsplit(("https", parts.netloc, parts.path, "", ""))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """No redirect is followed by urllib: a redirect is an HTTPError, and
    fetch_sums decides about the one it accepts."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request):
    """Send the request without following redirects."""
    opener = urllib.request.build_opener(NoRedirect)
    return opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)


def read_answer(url, max_bytes, what):
    """(status, body, location) of one request that follows no redirect.
    A redirect gives its Location; any other status than 200 is an error."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with open_request(request) as response:
            status = getattr(response, "status", 200)
            body = response.read(max_bytes + 1)
    except urllib.error.HTTPError as err:
        code, reason = err.code, err.reason
        location = err.headers.get("Location") if (300 <= code < 400 and err.headers is not None) else None
        err.close()
        if 300 <= code < 400:
            return code, None, location
        raise ProcessorError("The server answered %s %s for %s." % (code, reason, what))
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("%s could not be fetched: %s" % (what[:1].upper() + what[1:], err))
    if status != 200:
        raise ProcessorError("The server answered %s for %s, not 200." % (status, what))
    if len(body) > max_bytes:
        raise ProcessorError("%s is larger than %d bytes." % (what[:1].upper() + what[1:], max_bytes))
    try:
        return status, body.decode("utf-8"), None
    except UnicodeDecodeError as err:
        raise ProcessorError("%s is not UTF-8 text: %s" % (what[:1].upper() + what[1:], err))


def fetch_text(url, max_bytes, what):
    """GET an index page of download.gimp.org. A redirect is an error."""
    if not isinstance(url, str) or not url.startswith(BASE_URL):
        raise ProcessorError("Refusing to fetch %s from an address outside %s." % (what, BASE_URL))
    status, text, _ = read_answer(url, max_bytes, what)
    if text is None:
        raise ProcessorError("The server answered %s for %s (a redirect is not followed)." % (status, what))
    return text


def fetch_sums(series):
    """(text, host) of SHA256SUMS of the series. At most one redirect is
    followed, to an address that check_redirect_target accepts; the address
    it leads to must answer 200 itself."""
    url = series_folder_url(series) + SUMS_NAME
    status, text, location = read_answer(url, MAX_SUMS_BYTES, "SHA256SUMS")
    if text is None:
        try:
            if not isinstance(location, str) or not location.strip():
                raise ValueError("the redirect has no Location")
            url = check_redirect_target(urllib.parse.urljoin(url, location.strip()), series)
        except ValueError as err:
            raise ProcessorError("SHA256SUMS: %s." % err)
        status, text, _ = read_answer(url, MAX_SUMS_BYTES, "SHA256SUMS (after the redirect)")
        if text is None:
            raise ProcessorError(
                "The mirror answered %s for SHA256SUMS: only one redirect is followed." % status)
    return text, urllib.parse.urlsplit(url).hostname


class GimpInfoProvider(Processor):
    description = __doc__
    input_variables = {
        "gimp_series": {
            "required": False,
            "default": "",
            "description": "A series such as 3.0. Empty (the default): the highest series with an even second number.",
        },
        "gimp_allow_development": {
            "required": False,
            "default": False,
            "description": "True: a series with an odd second number (a development series) may be taken.",
        },
    }
    output_variables = {
        "url": {"description": "The download.gimp.org address of the installer."},
        "version": {"description": "The GIMP version: three numbers, such as 3.2.8. Never the installer's revision."},
        "expected_sha256": {
            "description": "The SHA-256 that SHA256SUMS gives for the installer (lower-case hex). "
                           "SHA256SUMS is served by a mirror: a transfer check, not proof of origin."
        },
        "gimp_chosen_series": {"description": "The series that was read, such as 3.2."},
        "gimp_installer_name": {"description": "The file name of the installer, such as gimp-3.2.8-setup.exe."},
        "gimp_sha256sums_host": {"description": "The host that served SHA256SUMS (a mirror, as seen on 2026-11-13)."},
    }

    def main(self):
        pinned = self.env.get("gimp_series", "")
        if pinned is None:
            pinned = ""
        if not isinstance(pinned, str):
            raise ProcessorError("gimp_series must be text: %r" % str(pinned)[:24])
        pinned = pinned.strip()
        if pinned and series_key(pinned) is None:
            raise ProcessorError("gimp_series must be two numbers such as 3.0, or empty: %r" % pinned[:24])
        allow = parse_bool(self.env.get("gimp_allow_development", False), "gimp_allow_development")

        index = fetch_text(BASE_URL, MAX_INDEX_BYTES, "the index of the series")
        try:
            series = choose_series(extract_series(index), pinned, allow)
        except ValueError as err:
            raise ProcessorError("GIMP index: %s." % err)

        folder = series_folder_url(series)
        folder_index = fetch_text(folder, MAX_INDEX_BYTES, "the index of v%s/windows/" % series)
        try:
            version, revision, name = find_installer(folder_index, series)
        except ValueError as err:
            raise ProcessorError("GIMP index of v%s/windows/: %s." % (series, err))

        sums, host = fetch_sums(series)
        try:
            sha256 = parse_sums(sums, name)
        except ValueError as err:
            raise ProcessorError("GIMP SHA256SUMS of v%s (served by %s): %s." % (series, host, err))

        self.env["url"] = folder + name
        self.env["version"] = version
        self.env["expected_sha256"] = sha256
        self.env["gimp_chosen_series"] = series
        self.env["gimp_installer_name"] = name
        self.env["gimp_sha256sums_host"] = host
        self.output("Series %s: GIMP %s, installer %s (revision %d)" % (series, version, name, revision))
        self.output("SHA-256 from SHA256SUMS served by %s (a transfer check, not proof of origin): %s"
                    % (host, sha256))


if __name__ == "__main__":
    processor = GimpInfoProvider()
    processor.execute_shell()
