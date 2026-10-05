#!/usr/local/autopkg/python
"""Find the newest release of LibreOffice for Windows (64-bit MSI) on the
download server of The Document Foundation.

The index was read on 2026-10-02 (a mirrorbrain HTML index, status 200, no
redirect). The name, path and format of the hash file below were NOT read: the
one answer the server gave for it was a 404, so they are the writer's
knowledge. The first run with AutoPkg 2.9.0 (2026-10-04) got as far as the hash file
and stopped there; nothing after it has run.

THE HASH FILE DOES NOT EXIST (checked 2026-10-02). The listing of
.../stable/26.8.1/win/x86_64/ holds, for the MSI and for every helppack and
langpack, only <name>.msi, <name>.msi.mirrorlist, <name>.msi.asc and
<name>.msi.asc.mirrorlist: no .sha256, .md5 or .sha1 file. The address that
hash_url() builds answered 404 once and 500 once, and 404 again in the first run of 2026-10-04. So this
processor stops at the hash file today. Its code and its tests are kept as the shape of the next
step (the owner reads the .mirrorlist page of the MSI, where mirrorbrain
usually shows the hashes, and the processor is then changed to read the hash
from wherever it is shown). Until then the recipe is a dry run that fails here
and LibreOffice is a hand import.

The directory https://download.documentfoundation.org/libreoffice/stable/ is
an HTML index whose links are the version folders (on 2026-10-02: 25.8.7/,
26.2.5/, 26.2.6/, 26.8.0/ and 26.8.1/, three lines at once). The processor
reads the links, keeps those that are exactly three numbers and a slash, and
chooses one version:

    fresh   the highest version, compared by its numbers (25.8.1)
    still   the highest version of the next lower line

A line is the first two numbers of a version (25.8). Versions are compared by
their numbers, never by their text (25.10.0 is newer than 25.8.1), and the
order of the links is not used. The input is `libreoffice_line`, default
`fresh`; any other value is an error.

For the chosen version the processor then reads the hash file that stands
beside the MSI:

    <index>/<version>/win/x86_64/LibreOffice_<version>_Win_x86-64.msi.sha256

It holds one line: 64 hex digits, two spaces, the file name. The file name
must be the name of the MSI of that version, and the file must hold that one
line and nothing else. The processor outputs:

    url              the address of the MSI (in the same versioned folder)
    version          the release, three numbers (25.8.1)
    expected_sha256  the SHA-256 that the hash file gives for the MSI

Both fetches (the index and the hash file) go to one fixed host over https,
follow NO redirect, have a size limit and a time limit. A redirect is an
error: a hash read from a mirror is not the publisher's. The download of the
MSI itself is done by the core processor URLDownloader, which does follow a
redirect to a mirror; the hash check afterwards is what protects the run.

The processor stops the recipe when a page cannot be fetched or is not what
is expected, when the index has no version folder, when the line asked for
does not exist, when the hash file is not one line of the expected form, when
the file name on that line is not the MSI's, or when the input is not one of
the two lines.
"""
import http.client
import re
import urllib.error
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "LibreOfficeInfoProvider",
    "release_key",
    "extract_versions",
    "choose_version",
    "expected_file_name",
    "file_url",
    "hash_url",
    "parse_hash_file",
    "fetch_text",
    "open_request",
]

INDEX_URL = "https://download.documentfoundation.org/libreoffice/stable/"
# Every address that is fetched must begin with this: one host, one folder.
ALLOWED_PREFIX = INDEX_URL
FETCH_TIMEOUT_SECONDS = 120
# The index is a few kilobytes. More than this is not the index.
MAX_INDEX_BYTES = 4 * 1024 * 1024
# The hash file is one line of about 100 bytes.
MAX_HASH_FILE_BYTES = 4096
USER_AGENT = "autopkg-LibreOfficeInfoProvider"

LINE_FRESH = "fresh"
LINE_STILL = "still"
LINES = (LINE_FRESH, LINE_STILL)
DEFAULT_LINE = LINE_FRESH

# A version folder: three numbers, no leading zeros, and the slash.
NUMBER = r"(?:0|[1-9][0-9]*)"
VERSION_PATTERN = re.compile(r"%s\.%s\.%s" % (NUMBER, NUMBER, NUMBER), re.ASCII)
FOLDER_PATTERN = re.compile(r"(%s\.%s\.%s)/" % (NUMBER, NUMBER, NUMBER), re.ASCII)
HREF_PATTERN = re.compile(r"<a\s[^>]*?\bhref=\"([^\"]*)\"", re.IGNORECASE)
# One line of the hash file: 64 hex digits, two spaces, a file name.
HASH_LINE_PATTERN = re.compile(r"([0-9a-fA-F]{64}) {2}([^ ]+)", re.ASCII)

# The path of the MSI under the versioned folder, and its name.
WINDOWS_FOLDER = "win/x86_64"
FILE_NAME_PATTERN = "LibreOffice_{version}_Win_x86-64.msi"


def release_key(version):
    """The three numbers of a version as a tuple of integers, or None when the
    text is not three numbers separated by dots (no sign, no space, no leading
    zero, no other digits)."""
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        return None
    return tuple(int(part) for part in version.split("."))


def extract_versions(index_text):
    """The version folders that the index links to, as a sorted list of
    distinct version texts (oldest first), or raise ValueError with a reason.

    A link counts only when it is exactly <three numbers>/ . Other links (the
    sort links of the listing, the parent folder, a folder with another name)
    are ignored."""
    found = set()
    for href in HREF_PATTERN.findall(index_text):
        match = FOLDER_PATTERN.fullmatch(href)
        if match:
            found.add(match.group(1))
    if not found:
        raise ValueError("the index has no link to a version folder (three numbers and a slash)")
    return sorted(found, key=release_key)


def choose_version(versions, line_choice):
    """The version for `fresh` or `still`, or raise ValueError.

    The versions are grouped by line (their first two numbers). `fresh` is the
    highest version of the highest line. `still` is the highest version of the
    line just below it. When the index holds only one line there is no `still`:
    that is an error, not a fall back to `fresh`."""
    if line_choice not in LINES:
        raise ValueError("the line must be one of %s, not %r" % (", ".join(LINES), str(line_choice)[:24]))
    best = {}
    for version in versions:
        key = release_key(version)
        if key is None:
            raise ValueError("%r is not three numbers" % str(version)[:24])
        line = key[:2]
        if line not in best or key > best[line]:
            best[line] = key
    lines = sorted(best, reverse=True)
    wanted = 0 if line_choice == LINE_FRESH else 1
    if len(lines) <= wanted:
        raise ValueError(
            "the index has %d line(s) of releases, so there is no %s line" % (len(lines), line_choice)
        )
    return ".".join(str(number) for number in best[lines[wanted]])


def expected_file_name(version):
    """The name of the MSI of this version. ValueError for a text that is not a version."""
    if release_key(version) is None:
        raise ValueError("%r is not three numbers" % str(version)[:24])
    return FILE_NAME_PATTERN.format(version=version)


def file_url(version):
    return "%s%s/%s/%s" % (INDEX_URL, version, WINDOWS_FOLDER, expected_file_name(version))


def hash_url(version):
    return file_url(version) + ".sha256"


def parse_hash_file(text, version):
    """The SHA-256 (lower case) from the hash file of this version, or raise
    ValueError. The file must hold exactly one line, 64 hex digits, two
    spaces and the name of the MSI of this version."""
    name = expected_file_name(version)
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError("the hash file has %d lines, not exactly one" % len(lines))
    match = HASH_LINE_PATTERN.fullmatch(lines[0])
    if not match:
        raise ValueError("the line of the hash file is not 64 hex digits, two spaces and a file name")
    if match.group(2) != name:
        raise ValueError("the hash file names %r, not the expected %s" % (match.group(2)[:80], name))
    return match.group(1).lower()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The index and the hash file are plain answers of one fixed host. A
    redirect would send the request elsewhere: it is an error (HTTPError)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request):
    """Send the request without following redirects."""
    opener = urllib.request.build_opener(NoRedirect)
    return opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)


def fetch_text(url, max_bytes, what):
    """GET the address and return its text. The one place where the network is
    used: tests replace this function or open_request. `what` names the thing
    in the messages ("the index", "the hash file")."""
    if not isinstance(url, str) or not url.startswith(ALLOWED_PREFIX):
        raise ProcessorError("The address of %s is not under %s." % (what, ALLOWED_PREFIX))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with open_request(request) as response:
            body = response.read(max_bytes + 1)
    except urllib.error.HTTPError as err:
        redirect = (
            " (a redirect is not followed: a hash read from a mirror is not the publisher's; "
            "stop and tell the owner)" if 300 <= err.code < 400 else ""
        )
        message = "The server answered %s %s for %s%s." % (err.code, err.reason, what, redirect)
        err.close()
        raise ProcessorError(message)
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("%s could not be fetched: %s" % (what[:1].upper() + what[1:], err))
    if len(body) > max_bytes:
        raise ProcessorError("%s is larger than %d bytes." % (what[:1].upper() + what[1:], max_bytes))
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as err:
        raise ProcessorError("%s is not UTF-8 text: %s" % (what[:1].upper() + what[1:], err))


class LibreOfficeInfoProvider(Processor):
    description = __doc__
    input_variables = {
        "libreoffice_line": {
            "required": False,
            "default": DEFAULT_LINE,
            "description": "fresh (the newer line, the default) or still (the next lower line).",
        },
    }
    output_variables = {
        "url": {"description": "The address of the MSI on the vendor's download server."},
        "version": {"description": "The release: three numbers, such as 25.8.1."},
        "expected_sha256": {
            "description": "The SHA-256 that the vendor's hash file gives for the MSI (lower-case hex)."
        },
    }

    def main(self):
        line_choice = self.env.get("libreoffice_line", DEFAULT_LINE)
        if not isinstance(line_choice, str) or line_choice.strip() not in LINES:
            raise ProcessorError(
                "libreoffice_line must be one of %s: %r" % (", ".join(LINES), str(line_choice)[:24])
            )
        line_choice = line_choice.strip()

        index = fetch_text(INDEX_URL, MAX_INDEX_BYTES, "the index")
        try:
            version = choose_version(extract_versions(index), line_choice)
        except ValueError as err:
            raise ProcessorError("LibreOffice download index: %s." % err)

        hash_text = fetch_text(hash_url(version), MAX_HASH_FILE_BYTES, "the hash file")
        try:
            sha256 = parse_hash_file(hash_text, version)
        except ValueError as err:
            raise ProcessorError("LibreOffice hash file: %s." % err)

        self.env["url"] = file_url(version)
        self.env["version"] = version
        self.env["expected_sha256"] = sha256
        self.output("Release of the %s line: %s" % (line_choice, version))
        self.output("Vendor's SHA-256: %s" % sha256)


if __name__ == "__main__":
    processor = LibreOfficeInfoProvider()
    processor.execute_shell()
