#!/usr/local/autopkg/python
"""Find the current release of VLC for Windows on the vendor's own download server.

The facts of the server were read on 2026-10-02 (see the README). The directory
https://download.videolan.org/vlc/last/win64/ is an HTML directory index. Its
links are bare file names. They name the files of the current release: the .exe,
the .msi, the .7z and the .zip, each with .asc, .md5, .sha1 and .sha256 files
beside it, and a -debugsym.7z set. This processor reads the links of the index
and keeps those that are exactly vlc-<version>-win64.msi (a link such as
vlc-<version>-win64.msi.sha256 is not one). It requires exactly one version
among them: none, or two, is an error.

It then fetches the hash file of that release from the versioned folder,
https://download.videolan.org/vlc/<version>/win64/vlc-<version>-win64.msi.sha256.
The file holds one line: 64 hex digits, two spaces, and a file name. The file
name must be the name of the MSI. The file to download is in the same versioned
folder, not in `last`, so that the file and its hash name one release.

It outputs:

    url              the address of the MSI in the versioned folder
    version          the release, three or four numbers (3.0.24)
    expected_sha256  the SHA-256 that the vendor's hash file gives for the file

The index and the hash file are read from the publisher's own server,
download.videolan.org, never from get.videolan.org: the second answers the hash
file with a redirect to a mirror, and a hash read from a mirror is not the
publisher's. The MSI itself is redirected to a mirror by the server; the
downloader follows that, and the check against the publisher's hash shows that
the file is what the publisher published, not more.

Both fetches of this processor go to one fixed host over https, follow no
redirect (a redirect is an error), have a size limit and a time limit. The input
vlc_architecture is win64 or win32 and nothing else; it is part of two addresses
and of a file name, never a path.

The processor stops the recipe when the index or the hash file cannot be
fetched or is not what is expected, when no link or more than one version is
found, when a link names a version that is not numbers, when the hash file does
not have exactly one line of the expected form, or when its file name is not the
MSI's.
"""
import html
import http.client
import re
import urllib.error
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "VideoLANVlcInfoProvider",
    "version_key",
    "msi_file_name",
    "index_url",
    "folder_url",
    "find_version",
    "parse_hash_line",
    "fetch_text",
    "open_request",
]

# The publisher's own server. get.videolan.org redirects the hash file to a mirror.
BASE_URL = "https://download.videolan.org/vlc/"
LAST_FOLDER = "last"
FETCH_TIMEOUT_SECONDS = 120
# The index lists about forty files. More than this is not the index.
MAX_INDEX_BYTES = 1024 * 1024
# The hash file is one line. More than this is not the hash file.
MAX_HASH_FILE_BYTES = 16 * 1024
USER_AGENT = "autopkg-VideoLANVlcInfoProvider"

DEFAULT_ARCHITECTURE = "win64"
ARCHITECTURES = ("win64", "win32")

# Three or four numbers (3.0.21, and a fourth for a fix release).
VERSION_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+){2,3}")
HASH_LINE_PATTERN = re.compile(r"([0-9a-fA-F]{64})  (.+)")
# A link of the index: double or single quotes around the address.
LINK_PATTERN = re.compile(r"<a\s(?:[^>]*?\s)?href\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", re.I)


def version_key(version):
    """The numbers of a version as a tuple of integers, or None when the text
    is not three or four numbers separated by dots."""
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        return None
    return tuple(int(part) for part in version.split("."))


def msi_file_name(version, architecture):
    """The name of the MSI of a release: vlc-3.0.21-win64.msi."""
    if version_key(version) is None:
        raise ValueError("%s is not a version of three or four numbers" % repr(version)[:24])
    if architecture not in ARCHITECTURES:
        raise ValueError("architecture %s is not supported: use one of %s" % (architecture, ", ".join(ARCHITECTURES)))
    return "vlc-%s-%s.msi" % (version, architecture)


def index_url(architecture):
    """The address of the index of the current release."""
    if architecture not in ARCHITECTURES:
        raise ValueError("architecture %s is not supported: use one of %s" % (architecture, ", ".join(ARCHITECTURES)))
    return "%s%s/%s/" % (BASE_URL, LAST_FOLDER, architecture)


def folder_url(version, architecture):
    """The address of the folder of one release."""
    msi_file_name(version, architecture)  # checks both inputs
    return "%s%s/%s/" % (BASE_URL, version, architecture)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Both fetches are plain answers of one fixed host. A redirect would send
    the request elsewhere: it is an error (HTTPError)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request):
    """Send the request without following redirects."""
    opener = urllib.request.build_opener(NoRedirect)
    return opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)


def fetch_text(url, max_bytes, what):
    """GET the address and return its text. The one place where the network is
    used: tests replace this function or open_request. `what` names the thing
    for the messages ("the index", "the hash file")."""
    if not url.startswith(BASE_URL):
        raise ProcessorError("Refusing to fetch %s from an address outside %s." % (what, BASE_URL))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with open_request(request) as response:
            body = response.read(max_bytes + 1)
    except urllib.error.HTTPError as err:
        redirect = " (a redirect is not followed)" if 300 <= err.code < 400 else ""
        message = "The server answered %s %s for %s%s." % (err.code, err.reason, what, redirect)
        err.close()
        raise ProcessorError(message)
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("The server could not be asked for %s: %s" % (what, err))
    if len(body) > max_bytes:
        raise ProcessorError("The answer for %s is larger than %d bytes." % (what, max_bytes))
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as err:
        raise ProcessorError("The answer for %s is not UTF-8 text: %s" % (what, err))


def find_version(index_text, architecture):
    """The one version that the links of the index name for the MSI, or raise
    ValueError with a reason that is safe to show."""
    if architecture not in ARCHITECTURES:
        raise ValueError("architecture %s is not supported: use one of %s" % (architecture, ", ".join(ARCHITECTURES)))
    link_name = re.compile(r"vlc-([0-9.]+)-%s\.msi" % re.escape(architecture))
    versions = set()
    for double, single in LINK_PATTERN.findall(index_text):
        address = html.unescape(double or single)
        found = link_name.fullmatch(address)
        if not found:
            continue
        version = found.group(1)
        if version_key(version) is None:
            raise ValueError("a link names the MSI of a version that is not three or four numbers: %r" % address[:60])
        versions.add(version)
    if not versions:
        raise ValueError("the index has no link to vlc-<version>-%s.msi" % architecture)
    if len(versions) != 1:
        raise ValueError(
            "the index names %d different versions of the MSI (%s), not exactly one"
            % (len(versions), ", ".join(sorted(versions, key=version_key)))
        )
    return next(iter(versions))


def parse_hash_line(text, file_name):
    """The SHA-256 (lower case) of the one line of the hash file, or raise
    ValueError. The line is 64 hex digits, two spaces, and the file name, which
    must be `file_name`."""
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError("the hash file has %d lines, not exactly one" % len(lines))
    found = HASH_LINE_PATTERN.fullmatch(lines[0])
    if not found:
        raise ValueError("the line of the hash file is not 64 hex digits, two spaces and a file name")
    if found.group(2) != file_name:
        raise ValueError("the hash file names %r, not %s" % (found.group(2)[:80], file_name))
    return found.group(1).lower()


class VideoLANVlcInfoProvider(Processor):
    description = __doc__
    input_variables = {
        "vlc_architecture": {
            "required": False,
            "default": DEFAULT_ARCHITECTURE,
            "description": "The architecture as the server writes it: win64 or win32.",
        },
    }
    output_variables = {
        "url": {"description": "The address of the MSI in the folder of its release."},
        "version": {"description": "The release: three or four numbers, such as 3.0.21."},
        "expected_sha256": {
            "description": "The SHA-256 that the vendor's hash file gives for the file (lower-case hex)."
        },
    }

    def text_input(self, name, default):
        value = self.env.get(name, default)
        if not isinstance(value, str) or not value.strip():
            raise ProcessorError("%s must be text that is not empty." % name)
        return value.strip()

    def main(self):
        architecture = self.text_input("vlc_architecture", DEFAULT_ARCHITECTURE)
        if architecture not in ARCHITECTURES:
            raise ProcessorError(
                "vlc_architecture must be one of %s: %r" % (", ".join(ARCHITECTURES), architecture[:24])
            )

        index = fetch_text(index_url(architecture), MAX_INDEX_BYTES, "the index of the current release")
        try:
            version = find_version(index, architecture)
        except ValueError as err:
            raise ProcessorError("VideoLAN index: %s." % err)

        file_name = msi_file_name(version, architecture)
        folder = folder_url(version, architecture)
        hash_text = fetch_text(folder + file_name + ".sha256", MAX_HASH_FILE_BYTES, "the hash file")
        try:
            sha256 = parse_hash_line(hash_text, file_name)
        except ValueError as err:
            raise ProcessorError("VideoLAN hash file: %s." % err)

        self.env["url"] = folder + file_name
        self.env["version"] = version
        self.env["expected_sha256"] = sha256
        self.output("Current release: %s" % version)
        self.output("Vendor's SHA-256: %s" % sha256)


if __name__ == "__main__":
    processor = VideoLANVlcInfoProvider()
    processor.execute_shell()
