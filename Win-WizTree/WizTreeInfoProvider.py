#!/usr/local/autopkg/python
"""Find the current WizTree installer for Windows (the .exe) and its SHA-256 on the publisher's download page.

The facts of the page were read on 2026-11-13 (see the README). The page
https://diskanalyzer.com/download answers 200 without a redirect. Near its top
it has one link to the installer, a relative address of the form
files/wiztree_<numbers joined by underscores>_setup.exe (files/wiztree_4_33_setup.exe
on that day), and one link to the portable .zip of the same release. Each link
is an <a> element whose content holds the release ("V&nbsp;4.33&nbsp;" and the
date and size) and a <div class="shacopy"> with the SHA-256 of that file in full
twice: in its attribute data-sha="<64 hex digits>" and in its title
"SHA-256: <64 hex digits> (click to copy)". The text of the div shows only a
shortened form. Further down the page lists the history of releases as text
(headings "WizTree 4.33", "WizTree 4.32", ... "WizTree 3.33"), with no link to an
installer.

This processor reads the links of the page and requires:

 1. exactly ONE link whose address names a WizTree .exe (any address with
    "wiztree" and ".exe" in it, in any case), and that link must be exactly
    files/wiztree_<two to four numbers joined by underscores>_setup.exe.
    A second such link (an old release, say) stops the run, and so does one in
    another form (an absolute address, another folder, a query);
 2. the content of that <a> element, up to its own </a>, holds no other <a>
    element, exactly one data-sha="<64 hex digits>", and no other 64-digit hex
    number than that one (the title repeats it). The hash of the portable .zip
    sits in the content of the other link and is never read;
 3. that content holds exactly one release text "V <numbers and dots> " (after
    HTML entities are decoded, so &nbsp; is a space), and it is the label that
    the file name gives.

The label is the file name's numbers with dots for the underscores
(wiztree_4_33_setup.exe gives 4.33), as written: leading zeros are kept.

It outputs:

    url              https://diskanalyzer.com/files/<the file name>
    version          the label from the file name (4.33)
    expected_sha256  the SHA-256 that the page gives inside the installer's link

The page is read from one fixed address over https, follows no redirect (a
redirect is an error), has a size limit (512 KiB) and a time limit (120 seconds).
The installer itself is not fetched here. On 2026-11-13 its address answered a
HEAD request with a redirect (301) to the publisher's content delivery host; the
downloader follows that, and the check against the page's hash shows that the
file is the one whose hash the page gave.

The processor stops the recipe when the page cannot be fetched or is not what is
expected, when the rules above do not hold exactly, or when the release text of
the link is not the label of the file name.
"""
import html
import http.client
import re
import urllib.error
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "WizTreeInfoProvider",
    "version_key",
    "label_from_name",
    "find_installer",
    "fetch_text",
    "open_request",
]

SITE_URL = "https://diskanalyzer.com/"
PAGE_URL = SITE_URL + "download"
# The folder of the files on the site. The page links into it by a relative address.
FILES_FOLDER = "files/"
FETCH_TIMEOUT_SECONDS = 120
# The page was 98004 bytes on 2026-11-13. More than this is not the page.
MAX_PAGE_BYTES = 512 * 1024
USER_AGENT = "autopkg-WizTreeInfoProvider"

# Two to four numbers joined by dots (4.33).
VERSION_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+){1,3}")
# The one form of the installer's link: files/wiztree_4_33_setup.exe.
INSTALLER_HREF_PATTERN = re.compile(r"files/(wiztree_([0-9]+(?:_[0-9]+){1,3})_setup\.exe)")
# An opening <a> tag with its address: double or single quotes around it.
ANCHOR_PATTERN = re.compile(r"<a\s(?:[^>]*?\s)?href\s*=\s*(?:\"([^\"]*)\"|'([^']*)')[^>]*>", re.I)
ANY_ANCHOR_PATTERN = re.compile(r"<a[\s>]", re.I)
CLOSE_ANCHOR_PATTERN = re.compile(r"</a\s*>", re.I)
DATA_SHA_PATTERN = re.compile(r"\bdata-sha\s*=\s*\"([0-9A-Fa-f]{64})\"")
HEX64_PATTERN = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{64}(?![0-9A-Fa-f])")
# "V&nbsp;4.33&nbsp;16 September 2026" once the entities are decoded.
RELEASE_TEXT_PATTERN = re.compile(r"(?<![A-Za-z0-9])V\s+([0-9]+(?:\.[0-9]+)+)\s")


def version_key(version):
    """The numbers of a label as a tuple of integers, or None when the text is not
    two to four numbers separated by dots."""
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        return None
    return tuple(int(part) for part in version.split("."))


def label_from_name(file_name):
    """The label of an installer's file name: wiztree_4_33_setup.exe gives 4.33.
    ValueError for any other name."""
    found = re.fullmatch(r"wiztree_([0-9]+(?:_[0-9]+){1,3})_setup\.exe", file_name or "")
    if not found:
        raise ValueError("%s is not wiztree_<numbers>_setup.exe" % repr(file_name)[:60])
    return found.group(1).replace("_", ".")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The page is a plain answer of one fixed address. A redirect would send the
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
    if url != PAGE_URL:
        raise ProcessorError("Refusing to fetch %s from an address other than %s." % (what, PAGE_URL))
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


def is_setup_link(address):
    """True for an address that names a WizTree .exe in any form (with a query, in
    another folder, in capitals): every such link must be the one strict form."""
    lowered = address.lower()
    return "wiztree" in lowered and ".exe" in lowered


def find_installer(page_text):
    """(file name, label, sha256) of the one installer link of the page, or raise
    ValueError with a reason that is safe to show."""
    found = []
    for match in ANCHOR_PATTERN.finditer(page_text):
        address = html.unescape(match.group(1) if match.group(1) is not None else match.group(2))
        if not is_setup_link(address):
            continue
        strict = INSTALLER_HREF_PATTERN.fullmatch(address)
        if not strict:
            raise ValueError(
                "a link names a WizTree .exe in another form than files/wiztree_<numbers>_setup.exe: %r" % address[:80]
            )
        found.append((match, strict.group(1)))
    if not found:
        raise ValueError("the page has no link to files/wiztree_<numbers>_setup.exe")
    if len(found) != 1:
        raise ValueError("the page has %d links to a WizTree .exe, not exactly one" % len(found))
    match, file_name = found[0]
    label = label_from_name(file_name)
    if version_key(label) is None:
        raise ValueError("the file name %s does not give two to four numbers" % file_name)

    close = CLOSE_ANCHOR_PATTERN.search(page_text, match.end())
    if not close:
        raise ValueError("the link to %s has no </a>" % file_name)
    block = page_text[match.end():close.start()]
    if ANY_ANCHOR_PATTERN.search(block):
        raise ValueError("the link to %s holds another <a> element before its </a>" % file_name)

    data = DATA_SHA_PATTERN.findall(block)
    if len(data) != 1:
        raise ValueError("the link to %s holds %d data-sha hashes, not exactly one" % (file_name, len(data)))
    numbers = {value.lower() for value in HEX64_PATTERN.findall(block)}
    if numbers != {data[0].lower()}:
        raise ValueError("the link to %s holds %d different SHA-256 values, not exactly one" % (file_name, len(numbers)))

    releases = RELEASE_TEXT_PATTERN.findall(html.unescape(block))
    if len(releases) != 1:
        raise ValueError("the link to %s holds %d release texts \"V <version>\", not exactly one" % (file_name, len(releases)))
    if releases[0] != label:
        raise ValueError("the link to %s says release %s, not %s" % (file_name, releases[0][:24], label))
    return file_name, label, data[0].lower()


class WizTreeInfoProvider(Processor):
    description = __doc__
    input_variables = {}
    output_variables = {
        "url": {"description": "The address of the installer on the publisher's site."},
        "version": {"description": "The label from the file name: two to four numbers, such as 4.33, as written."},
        "expected_sha256": {
            "description": "The SHA-256 that the page gives inside the installer's link (lower-case hex)."
        },
    }

    def main(self):
        page = fetch_text(PAGE_URL, MAX_PAGE_BYTES, "the download page")
        try:
            file_name, label, sha256 = find_installer(page)
        except ValueError as err:
            raise ProcessorError("WizTree download page: %s." % err)

        self.env["url"] = SITE_URL + FILES_FOLDER + file_name
        self.env["version"] = label
        self.env["expected_sha256"] = sha256
        self.output("Current installer: %s (label %s)" % (file_name, label))
        self.output("Page's SHA-256: %s" % sha256)


if __name__ == "__main__":
    processor = WizTreeInfoProvider()
    processor.execute_shell()
