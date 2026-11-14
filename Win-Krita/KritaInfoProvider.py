#!/usr/local/autopkg/python
"""Find the newest Krita installer for Windows on KDE's download server.

The facts of the server were read on 2026-11-13 (see the README).

https://download.kde.org/stable/krita/ is an HTML directory index (200, no
redirect). Its links name the version folders of Krita (three or four numbers
and a slash, such as 6.0.4/; a re-issue adds a fourth number), other folders
(updates/, plug-in folders) and the site's own pages; each folder is linked
twice. The processor keeps the links that are exactly <version>/ with a version
of three or four numbers. A link of digits and dots that is not such a version
(7.0/, say) is an error, never skipped: the server has changed and a person
looks. Other links are ignored.

It reads the version folders from the highest version down (the numbers are
compared one by one, so a fourth number makes a version higher than its first
three alone). A folder is used when its own index (200, no redirect) links to
exactly krita-x64-<the folder's version>-setup.exe. A folder without that
link is passed over, and the processor goes down to the next lower version, at
most MAX_FOLDERS_TRIED folders in all; it says which folders it passed over. A
folder that links to a Windows installer of another version is an error.

The hash comes from krita-x64-<version>-setup.exe.sha256 in the same folder.
The folder's index does not link to it; it is fetched by its name. On
2026-11-13 download.kde.org answered it itself with 200 (no redirect): one
line, 64 hex digits, two spaces and the file name, with or without a new line
at the end. The installer itself is answered with a redirect to a mirror; the
downloader follows that, and the check against this hash shows that the
mirror's file is the file that KDE's own server gives the hash for. It is not
a signature check.

All three fetches go to download.kde.org over https, follow no redirect (a
redirect is an error), have a size limit and a time limit.

It outputs:

    url                    the download.kde.org address of the installer
    version                the folder's version, three or four numbers
    expected_sha256        the SHA-256 that the .sha256 file gives for the installer
    krita_chosen_folder    the version folder that was used
    krita_installer_name   the file name of the installer
    krita_passed_over      the newer folders without the installer, or empty

No output is set unless every check passed.
"""
import html
import http.client
import re
import urllib.error
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "KritaInfoProvider",
    "version_key",
    "installer_name",
    "folder_url",
    "extract_versions",
    "folder_has_installer",
    "parse_hash_line",
    "fetch_text",
    "open_request",
]

BASE_URL = "https://download.kde.org/stable/krita/"
FETCH_TIMEOUT_SECONDS = 120
# The index pages are about 11 KB (2026-11-13). More than this is not the index.
MAX_INDEX_BYTES = 1024 * 1024
# The hash file is one line of 93 bytes. More than this is not the hash file.
MAX_HASH_FILE_BYTES = 16 * 1024
USER_AGENT = "autopkg-KritaInfoProvider"
# How many version folders are read, the newest first, before the run stops
# because none of them has the Windows installer.
MAX_FOLDERS_TRIED = 3

NUMBER = r"(?:0|[1-9][0-9]*)"
# Three or four numbers (6.0.4, and a fourth for a re-issue).
VERSION_PATTERN = re.compile(r"%s(?:\.%s){2,3}" % (NUMBER, NUMBER), re.ASCII)
# A link that looks like a version folder: digits and dots, and a slash.
NUMERIC_FOLDER_PATTERN = re.compile(r"[0-9][0-9.]*/", re.ASCII)
# Any Windows installer of the folder, of whatever version.
ANY_INSTALLER_PATTERN = re.compile(r"krita-x64-(.+)-setup\.exe", re.ASCII)
HASH_LINE_PATTERN = re.compile(r"([0-9a-fA-F]{64})  (.+)")
# A link of the index: double or single quotes around the address.
LINK_PATTERN = re.compile(r"<a\s(?:[^>]*?\s)?href\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", re.I)


def version_key(version):
    """The numbers of a version as a tuple of integers, or None when the text
    is not three or four numbers separated by dots (no sign, no space, no
    leading zero)."""
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        return None
    return tuple(int(part) for part in version.split("."))


def installer_name(version):
    """The name of the Windows installer of a version: krita-x64-6.0.4-setup.exe."""
    if version_key(version) is None:
        raise ValueError("%r is not a version of three or four numbers" % str(version)[:24])
    return "krita-x64-%s-setup.exe" % version


def folder_url(version):
    """The address of the folder of one version."""
    if version_key(version) is None:
        raise ValueError("%r is not a version of three or four numbers" % str(version)[:24])
    return "%s%s/" % (BASE_URL, version)


def links(index_text):
    for double, single in LINK_PATTERN.findall(index_text):
        yield html.unescape(double or single)


def extract_versions(index_text):
    """The versions of the folders that the index links to, the highest first,
    or raise ValueError."""
    found = set()
    for address in links(index_text):
        if not NUMERIC_FOLDER_PATTERN.fullmatch(address):
            continue
        version = address[:-1]
        if version_key(version) is None:
            raise ValueError("a folder link is not a version of three or four numbers: %r" % address[:40])
        found.add(version)
    if not found:
        raise ValueError("the index has no link to a version folder (<version>/)")
    return sorted(found, key=version_key, reverse=True)


def folder_has_installer(index_text, version):
    """True when the index of the folder of `version` links to its Windows
    installer, False when it links to none; raise ValueError when it links
    to the installer of another version."""
    wanted = installer_name(version)
    has = False
    for address in links(index_text):
        if not ANY_INSTALLER_PATTERN.fullmatch(address):
            continue
        if address != wanted:
            raise ValueError("the folder %s/ links to an installer of another version: %r" % (version, address[:60]))
        has = True
    return has


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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Every fetch is a plain answer of one fixed host. A redirect would send
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
    if not isinstance(url, str) or not url.startswith(BASE_URL):
        raise ProcessorError("Refusing to fetch %s from an address outside %s." % (what, BASE_URL))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with open_request(request) as response:
            status = getattr(response, "status", 200)
            body = response.read(max_bytes + 1)
    except urllib.error.HTTPError as err:
        redirect = " (a redirect is not followed)" if 300 <= err.code < 400 else ""
        message = "The server answered %s %s for %s%s." % (err.code, err.reason, what, redirect)
        err.close()
        raise ProcessorError(message)
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("The server could not be asked for %s: %s" % (what, err))
    if status != 200:
        raise ProcessorError("The server answered %s for %s, not 200." % (status, what))
    if len(body) > max_bytes:
        raise ProcessorError("The answer for %s is larger than %d bytes." % (what, max_bytes))
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as err:
        raise ProcessorError("The answer for %s is not UTF-8 text: %s" % (what, err))


class KritaInfoProvider(Processor):
    description = __doc__
    input_variables = {}
    output_variables = {
        "url": {"description": "The download.kde.org address of the Windows installer."},
        "version": {"description": "The version of the folder: three or four numbers, such as 6.0.4."},
        "expected_sha256": {
            "description": "The SHA-256 that download.kde.org's .sha256 file gives for the installer (lower-case hex)."
        },
        "krita_chosen_folder": {"description": "The version folder that was used."},
        "krita_installer_name": {"description": "The file name of the installer, such as krita-x64-6.0.4-setup.exe."},
        "krita_passed_over": {
            "description": "The newer version folders without a Windows installer, joined by ', ', or empty."
        },
    }

    def main(self):
        index = fetch_text(BASE_URL, MAX_INDEX_BYTES, "the index of the versions")
        try:
            versions = extract_versions(index)
        except ValueError as err:
            raise ProcessorError("Krita index: %s." % err)

        chosen = None
        passed_over = []
        for version in versions[:MAX_FOLDERS_TRIED]:
            folder_index = fetch_text(folder_url(version), MAX_INDEX_BYTES, "the index of %s/" % version)
            try:
                if folder_has_installer(folder_index, version):
                    chosen = version
                    break
            except ValueError as err:
                raise ProcessorError("Krita index of %s/: %s." % (version, err))
            passed_over.append(version)
        if chosen is None:
            raise ProcessorError(
                "Krita index: none of the %d newest version folders (%s) links to its Windows installer."
                % (len(passed_over), ", ".join(passed_over))
            )

        name = installer_name(chosen)
        folder = folder_url(chosen)
        hash_text = fetch_text(folder + name + ".sha256", MAX_HASH_FILE_BYTES, "the hash file")
        try:
            sha256 = parse_hash_line(hash_text, name)
        except ValueError as err:
            raise ProcessorError("Krita hash file of %s/: %s." % (chosen, err))

        self.env["url"] = folder + name
        self.env["version"] = chosen
        self.env["expected_sha256"] = sha256
        self.env["krita_chosen_folder"] = chosen
        self.env["krita_installer_name"] = name
        self.env["krita_passed_over"] = ", ".join(passed_over)
        if passed_over:
            self.output("Passed over (no Windows installer): %s" % ", ".join(passed_over))
        self.output("Folder %s: installer %s" % (chosen, name))
        self.output("SHA-256 from download.kde.org: %s" % sha256)


if __name__ == "__main__":
    processor = KritaInfoProvider()
    processor.execute_shell()
