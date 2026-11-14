#!/usr/local/autopkg/python
"""Find the newest release of Blender for Windows (the x64 MSI) on the Blender
Foundation's download server, and the SHA-256 that the server publishes for it.

What the server showed on 2026-11-13 (read by the writer; nothing of this
processor has run under AutoPkg):

    https://download.blender.org/release/
        An HTML index (status 200, no redirect). Its links are the series
        folders Blender<major>.<minor>/ (Blender5.3/ was the newest), beside
        old folders of other shapes (Blender2.28a/, Blender2.50alpha/,
        Blender2.27-newpy/, BlenderBenchmark2.0/ ...) and some files.
    https://download.blender.org/release/Blender5.3/
        An HTML index of one series. It listed blender-5.3.0-windows-x64.msi,
        the arm64 MSI, .msix and .zip builds, Linux and macOS files, and
        blender-5.3.0.sha256 and blender-5.3.0.md5. The folder Blender5.2/
        held 5.2.0 to 5.2.4, each with its own blender-<version>.sha256.
    https://download.blender.org/release/Blender5.3/blender-5.3.0.sha256
        One line for every file of that version: 64 hex digits, two spaces,
        the file name (eight lines for 5.3.0).

The processor reads the index and keeps the links that are exactly
Blender<two numbers>/ . It takes the highest series by its numbers (5.10 is
newer than 5.9), reads that series' folder, and keeps the links that are exactly
blender-<three numbers>-windows-x64.msi. A name with anything else in place of
the three numbers (a letter, a fourth number, "rc") is ignored, not an error.
It takes the highest of those versions, reads blender-<version>.sha256 in the
same folder, and takes the one line whose file name is exactly the MSI's name.

Whether a series folder can appear before its first release, or hold release
candidates, was NOT read. So a folder without a matching MSI is not an error
by itself: the processor goes on to the next lower series and says which folder
it used. It tries at most MAX_SERIES_TRIED folders; then it stops. In the normal
case it sends three requests: the index, the series folder, the hash file.

The input blender_series pins one series (such as 4.5): then only that folder
is read, and a folder without a matching MSI is an error, never a fall back to
another series. The default, an empty text, means the newest series.

The processor outputs:

    url              the address of the MSI (in the series folder)
    version          the release, three numbers from the file name (5.3.0)
    expected_sha256  the SHA-256 that the hash file gives for the MSI

The hash file and the MSI come from the same server. The check shows that the
downloaded file is the file that the server's hash file names. It does not help
if the server itself is changed.

How strict it is:

  - Every fetch goes to https://download.blender.org/release/ and nothing
    else. A redirect is NOT followed: it is an error. A status other than 200
    is an error. Each answer has a size limit and a time limit and must be
    UTF-8 text.
  - A version in a series folder whose first two numbers are not the series'
    is an error: the folder is not what the code expects.
  - Every line of the hash file must be 64 hex digits, two spaces and a file
    name without a space, a slash or a control character. A line of another
    form is an error, never skipped. No line for the MSI, or more than one, is
    an error.
  - No output is set unless every check passed.

The download of the MSI itself is done by the core processor URLDownloader,
which follows a redirect (on 2026-11-13 a HEAD of the MSI answered 200 with
no redirect); the hash check after it is what protects the run.
"""
import http.client
import re
import urllib.error
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "BlenderInfoProvider",
    "release_key",
    "series_key",
    "extract_series",
    "msi_versions",
    "expected_file_name",
    "series_url",
    "file_url",
    "hash_url",
    "sha256_of",
    "fetch_text",
    "open_request",
]

INDEX_URL = "https://download.blender.org/release/"
# Every address that is fetched must begin with this: one host, one folder.
ALLOWED_PREFIX = INDEX_URL
FETCH_TIMEOUT_SECONDS = 120
# The index was about 12 KB and a series folder a few KB. More than this is not the page.
MAX_INDEX_BYTES = 1024 * 1024
MAX_FOLDER_BYTES = 1024 * 1024
# The hash file was 777 bytes (eight lines).
MAX_HASH_FILE_BYTES = 16 * 1024
# How many series folders are read, newest first, before the run stops.
MAX_SERIES_TRIED = 3
USER_AGENT = "autopkg-BlenderInfoProvider"

DEFAULT_SERIES = ""

# A number without a leading zero.
NUMBER = r"(?:0|[1-9][0-9]*)"
VERSION_PATTERN = re.compile(r"%s\.%s\.%s" % (NUMBER, NUMBER, NUMBER), re.ASCII)
SERIES_PATTERN = re.compile(r"%s\.%s" % (NUMBER, NUMBER), re.ASCII)
SERIES_FOLDER_PATTERN = re.compile(r"Blender(%s\.%s)/" % (NUMBER, NUMBER), re.ASCII)
MSI_PATTERN = re.compile(r"blender-(%s\.%s\.%s)-windows-x64\.msi" % (NUMBER, NUMBER, NUMBER), re.ASCII)
HREF_PATTERN = re.compile(r"<a\s[^>]*?\bhref=\"([^\"]*)\"", re.IGNORECASE)
# One line of the hash file: the hash, two spaces, a file name without a space,
# a slash, a backslash or a control character.
HASH_LINE_PATTERN = re.compile(r"([0-9A-Fa-f]{64})  ([^\x00-\x20\x7f/\\]+)", re.ASCII)

FILE_NAME_PATTERN = "blender-{version}-windows-x64.msi"
HASH_FILE_NAME_PATTERN = "blender-{version}.sha256"


def release_key(version):
    """The three numbers of a version as a tuple of integers, or None when the
    text is not three numbers separated by dots (no sign, no space, no leading
    zero, no other characters)."""
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        return None
    return tuple(int(part) for part in version.split("."))


def series_key(series):
    """The two numbers of a series (5.3) as a tuple of integers, or None."""
    if not isinstance(series, str) or not SERIES_PATTERN.fullmatch(series):
        return None
    return tuple(int(part) for part in series.split("."))


def extract_series(index_text):
    """The series that the index links to, as a sorted list of distinct series
    texts (oldest first), or raise ValueError.

    A link counts only when it is exactly Blender<two numbers>/ . Other links
    (the parent folder, Blender2.28a/, BlenderBenchmark2.0/, files) are ignored."""
    found = set()
    for href in HREF_PATTERN.findall(index_text):
        match = SERIES_FOLDER_PATTERN.fullmatch(href)
        if match:
            found.add(match.group(1))
    if not found:
        raise ValueError("the index has no link to a series folder (Blender, two numbers and a slash)")
    return sorted(found, key=series_key)


def msi_versions(folder_text, series):
    """The versions of the x64 MSIs that a series folder links to, sorted by
    their numbers (oldest first). An empty list is not an error. A name that is
    not exactly blender-<three numbers>-windows-x64.msi is ignored. A version
    of another series is a ValueError."""
    key = series_key(series)
    if key is None:
        raise ValueError("%r is not a series of two numbers" % str(series)[:24])
    found = set()
    for href in HREF_PATTERN.findall(folder_text):
        match = MSI_PATTERN.fullmatch(href)
        if match:
            version = match.group(1)
            if release_key(version)[:2] != key:
                raise ValueError("the folder of series %s links to %s, a release of another series"
                                 % (series, href[:80]))
            found.add(version)
    return sorted(found, key=release_key)


def expected_file_name(version):
    """The name of the x64 MSI of this version. ValueError for a text that is not a version."""
    if release_key(version) is None:
        raise ValueError("%r is not three numbers" % str(version)[:24])
    return FILE_NAME_PATTERN.format(version=version)


def series_of(version):
    """The series of a version (5.3 for 5.3.0)."""
    key = release_key(version)
    if key is None:
        raise ValueError("%r is not three numbers" % str(version)[:24])
    return "%d.%d" % key[:2]


def series_url(series):
    if series_key(series) is None:
        raise ValueError("%r is not a series of two numbers" % str(series)[:24])
    return "%sBlender%s/" % (INDEX_URL, series)


def file_url(version):
    return series_url(series_of(version)) + expected_file_name(version)


def hash_url(version):
    return series_url(series_of(version)) + HASH_FILE_NAME_PATTERN.format(version=version)


def sha256_of(text, version):
    """The SHA-256 (lower case) of the one line of the hash file whose file name
    is exactly the MSI's name, or ValueError. Every line is checked, not only
    that one."""
    name = expected_file_name(version)
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if line == "":
            continue  # the file ends with a line break
        match = HASH_LINE_PATTERN.fullmatch(line)
        if not match:
            raise ValueError("line %d is not 64 hex digits, two spaces and a file name" % number)
        if match.group(2) == name:
            found.append(match.group(1).lower())
    if not found:
        raise ValueError("it has no line for %s" % name)
    if len(found) > 1:
        raise ValueError("it has %d lines for %s, not exactly one" % (len(found), name))
    return found[0]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The index, the series folder and the hash file are plain answers of one
    fixed host. A redirect would send the request elsewhere: it is an error
    (HTTPError)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request):
    """Send the request without following redirects."""
    opener = urllib.request.build_opener(NoRedirect)
    return opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)


def fetch_text(url, max_bytes, what):
    """GET the address and return its text. The one place where the network is
    used: tests replace this function or open_request. `what` names the thing
    in the messages ("the index", "the folder Blender5.3/", "the hash file")."""
    if not isinstance(url, str) or not url.startswith(ALLOWED_PREFIX):
        raise ProcessorError("The address of %s is not under %s." % (what, ALLOWED_PREFIX))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with open_request(request) as response:
            status = getattr(response, "status", 200)
            body = response.read(max_bytes + 1)
    except urllib.error.HTTPError as err:
        redirect = (
            " (a redirect is not followed: a hash read from another server is not the publisher's; "
            "stop and tell the owner)" if 300 <= err.code < 400 else ""
        )
        message = "The server answered %s %s for %s%s." % (err.code, err.reason, what, redirect)
        err.close()
        raise ProcessorError(message)
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("%s could not be fetched: %s" % (what[:1].upper() + what[1:], err))
    if status != 200:
        raise ProcessorError("The server answered %s, not 200, for %s." % (status, what))
    if len(body) > max_bytes:
        raise ProcessorError("%s is larger than %d bytes." % (what[:1].upper() + what[1:], max_bytes))
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as err:
        raise ProcessorError("%s is not UTF-8 text: %s" % (what[:1].upper() + what[1:], err))


class BlenderInfoProvider(Processor):
    description = __doc__
    input_variables = {
        "blender_series": {
            "required": False,
            "default": DEFAULT_SERIES,
            "description": "Empty (the default): the newest series that has an x64 MSI. "
                           "Two numbers, such as 4.5: only that series, for example to stay on a long-term line.",
        },
    }
    output_variables = {
        "url": {"description": "The address of the x64 MSI on the Blender Foundation's download server."},
        "version": {"description": "The release: three numbers from the file name, such as 5.3.0."},
        "expected_sha256": {
            "description": "The SHA-256 that the server's hash file gives for the MSI (lower-case hex)."
        },
    }

    def main(self):
        pinned = self.env.get("blender_series", DEFAULT_SERIES)
        if not isinstance(pinned, str) or (pinned.strip() and series_key(pinned.strip()) is None):
            raise ProcessorError(
                "blender_series must be empty or two numbers such as 4.5: %r" % str(pinned)[:24]
            )
        pinned = pinned.strip()

        index = fetch_text(INDEX_URL, MAX_INDEX_BYTES, "the index")
        try:
            series_list = extract_series(index)
        except ValueError as err:
            raise ProcessorError("Blender download index: %s." % err)
        if pinned:
            if pinned not in series_list:
                raise ProcessorError("Blender download index: it has no folder Blender%s/." % pinned)
            candidates = [pinned]
        else:
            candidates = list(reversed(series_list))[:MAX_SERIES_TRIED]

        version = None
        skipped = []
        for series in candidates:
            folder = "Blender%s/" % series
            listing = fetch_text(series_url(series), MAX_FOLDER_BYTES, "the folder " + folder)
            try:
                versions = msi_versions(listing, series)
            except ValueError as err:
                raise ProcessorError("Blender folder %s: %s." % (folder, err))
            if versions:
                version = versions[-1]
                break
            skipped.append(folder)
        if version is None:
            raise ProcessorError(
                "Blender folder: no blender-<three numbers>-windows-x64.msi in %s%s." % (
                    ", ".join(skipped),
                    "" if pinned else " (the %d newest series folders)" % len(skipped),
                )
            )

        hash_text = fetch_text(hash_url(version), MAX_HASH_FILE_BYTES, "the hash file")
        try:
            sha256 = sha256_of(hash_text, version)
        except ValueError as err:
            raise ProcessorError("Blender hash file of %s: %s." % (version, err))

        self.env["url"] = file_url(version)
        self.env["version"] = version
        self.env["expected_sha256"] = sha256
        for folder in skipped:
            self.output("Folder %s has no x64 MSI: the next lower series was read." % folder)
        self.output("Folder used: Blender%s/ (%s)" % (series_of(version), "pinned" if pinned else "newest"))
        self.output("Release: %s" % version)
        self.output("Server's SHA-256: %s" % sha256)


if __name__ == "__main__":
    processor = BlenderInfoProvider()
    processor.execute_shell()
