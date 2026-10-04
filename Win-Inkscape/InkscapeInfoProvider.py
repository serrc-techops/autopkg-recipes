#!/usr/local/autopkg/python
"""Find the current release of Inkscape for Windows (the 64-bit MSI) on the publisher's site.

The facts of the site were read on 2026-10-02 (see the README). Four requests
lead from the project's own "current release" address to the file and its hash:

 1. https://inkscape.org/release/ answers with a redirect (302) to
    https://inkscape.org/release/inkscape-<version>/. This processor does NOT
    follow it: it reads the Location header of that one answer, requires the
    host inkscape.org and a path of exactly /release/inkscape-<version>/ with a
    version of numbers and dots, and takes the version.
 2. https://inkscape.org/release/inkscape-<version>/windows/64-bit/msi/dl/ is
    an HTML page that holds one link /gallery/item/<id>/<file name>, where the
    file name begins with inkscape-<version>_ and ends with
    -x64.signed_<token>.msi (the publisher adds the token, letters and digits).
    The same path under a language prefix (/de/gallery/...) is not a gallery
    link. Exactly one such link is accepted.
 3. https://inkscape.org/gallery/item/<id>/ is an HTML page that holds exactly
    one link https://media.inkscape.org/media/resources/sigs/<name>.sha256.
 4. That hash file holds exactly one line: 64 hex digits, two spaces, and the
    file name WITHOUT the download's _<token>, then a new line. The name must
    equal the gallery file name with _<token> removed before .msi.

It outputs:

    url              the address of the file on the publisher's media server,
                     built from the file name (the processor does not follow
                     the redirect from the gallery to that server)
    version          the release, numbers separated by dots (1.4.4)
    expected_sha256  the SHA-256 that the publisher's hash file gives for the file

Every fetch goes to a fixed host over https (inkscape.org for the first three,
media.inkscape.org for the hash file), follows no redirect (a redirect is an
error, except that fetch 1 must be one and only its Location is read), has a
size limit (256 KiB for a page, 4 KiB for the hash file) and a time limit of
120 seconds. The input inkscape_architecture is 64-bit and nothing else: the
file names of the 32-bit installer were not read, so 32-bit is refused.

The processor stops the recipe when a request fails or answers otherwise than
expected, when the redirect is not the expected address, when a page does not
hold exactly one link of the expected form, when a link is not of the expected
form, when the hash file does not have exactly one line of the expected form,
or when its file name is not the MSI's name without the token.
"""
import html
import http.client
import re
import urllib.error
import urllib.parse
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "InkscapeInfoProvider",
    "version_key",
    "parse_release_location",
    "dl_page_url",
    "item_page_url",
    "find_download_link",
    "find_hash_link",
    "hash_file_name",
    "parse_hash_line",
    "media_url",
    "fetch_location",
    "fetch_text",
    "open_request",
]

SITE_HOST = "inkscape.org"
MEDIA_HOST = "media.inkscape.org"
SITE_URL = "https://inkscape.org/"
RELEASE_URL = SITE_URL + "release/"
# The only addresses that a request may go to: the project's own site, and the
# folder of the hash files on its media server.
SIGS_PATH = "/media/resources/sigs/"
ALLOWED_PREFIXES = (SITE_URL, "https://" + MEDIA_HOST + SIGS_PATH)
# The file itself is on the media server, under this folder (built, not fetched).
MEDIA_DOWNLOAD_URL = "https://" + MEDIA_HOST + "/dl/resources/file/"
FETCH_TIMEOUT_SECONDS = 120
# The pages are about 28 KB. More than this is not the page.
MAX_PAGE_BYTES = 256 * 1024
# The hash file is one line. More than this is not the hash file.
MAX_HASH_FILE_BYTES = 4 * 1024
USER_AGENT = "autopkg-InkscapeInfoProvider"

DEFAULT_ARCHITECTURE = "64-bit"
ARCHITECTURES = ("64-bit",)
REDIRECT_CODES = (301, 302, 303, 307, 308)

# Two to four numbers (1.4, 1.4.4).
VERSION_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+){1,3}")
RELEASE_PATH_PATTERN = re.compile(r"/release/inkscape-([0-9.]+)/")
HASH_LINE_PATTERN = re.compile(r"([0-9a-fA-F]{64})  (.+)")
# A link of a page: double or single quotes around the address.
LINK_PATTERN = re.compile(r"<a\s(?:[^>]*?\s)?href\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", re.I)
GALLERY_PATH_PATTERN = re.compile(r"/gallery/item/([0-9]+)/([^/]+\.msi)")
# The middle of the file name is the date and the commit: 2026-05-05_dcaf3e7.
FILE_NAME_TEMPLATE = r"inkscape-{version}_[A-Za-z0-9._-]+-x64\.signed_([A-Za-z0-9]+)\.msi"
SIG_NAME_PATTERN = re.compile(r"[A-Za-z0-9._-]+\.sha256")


def version_key(version):
    """The numbers of a version as a tuple of integers, or None when the text
    is not two to four numbers separated by dots."""
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        return None
    return tuple(int(part) for part in version.split("."))


def check_architecture(architecture):
    """ValueError unless the architecture is one whose file names were read."""
    if architecture == "32-bit":
        raise ValueError(
            "architecture 32-bit is not supported: the file names of the 32-bit installer were not read"
        )
    if architecture not in ARCHITECTURES:
        raise ValueError("architecture %r is not supported: use %s" % (str(architecture)[:24], ", ".join(ARCHITECTURES)))


def parse_release_location(location):
    """The version in the Location header of the answer of /release/, or raise
    ValueError. The address must be https://inkscape.org/release/inkscape-<version>/
    with nothing else in it."""
    if not isinstance(location, str):
        raise ValueError("the redirect has no Location")
    parts = urllib.parse.urlsplit(location)
    if parts.scheme != "https" or parts.netloc != SITE_HOST:
        raise ValueError("the redirect goes to %r, not to https://%s/" % (location[:80], SITE_HOST))
    if parts.query or parts.fragment:
        raise ValueError("the redirect %r has a query or a fragment" % location[:80])
    found = RELEASE_PATH_PATTERN.fullmatch(parts.path)
    if not found:
        raise ValueError("the path of the redirect, %r, is not /release/inkscape-<version>/" % parts.path[:60])
    version = found.group(1)
    if version_key(version) is None:
        raise ValueError("the redirect names a version that is not numbers and dots: %r" % version[:24])
    return version


def dl_page_url(version, architecture):
    """The address of the page that links the MSI of a release."""
    if version_key(version) is None:
        raise ValueError("%s is not a version of numbers and dots" % repr(version)[:24])
    check_architecture(architecture)
    return "%srelease/inkscape-%s/windows/%s/msi/dl/" % (SITE_URL, version, architecture)


def item_page_url(item_id):
    """The address of the gallery page of one file."""
    if not isinstance(item_id, str) or not re.fullmatch(r"[0-9]+", item_id):
        raise ValueError("%s is not the number of a gallery item" % repr(item_id)[:24])
    return "%sgallery/item/%s/" % (SITE_URL, item_id)


def media_url(file_name):
    """The address of the file on the media server."""
    if not isinstance(file_name, str) or not re.fullmatch(r"[A-Za-z0-9._-]+\.msi", file_name):
        raise ValueError("%s is not the name of an MSI" % repr(file_name)[:60])
    return MEDIA_DOWNLOAD_URL + file_name


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Every request is a plain answer of one fixed host. A redirect would send
    the request elsewhere: it is an error (HTTPError). The one request that is
    meant to be a redirect reads the Location of that error."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request):
    """Send the request without following redirects."""
    opener = urllib.request.build_opener(NoRedirect)
    return opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)


def check_address(url, what):
    """ProcessorError unless the address is under one of the fixed prefixes."""
    if not isinstance(url, str) or not url.startswith(ALLOWED_PREFIXES):
        raise ProcessorError("Refusing to fetch %s from an address outside %s." % (what, " or ".join(ALLOWED_PREFIXES)))


def fetch_location(url, what):
    """GET the address, which must answer with a redirect, and return the
    Location header (an absolute address) WITHOUT following it. The one place
    where the redirect is read: tests replace this function or open_request."""
    check_address(url, what)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with open_request(request) as response:
            status = getattr(response, "status", None)
        raise ProcessorError("The server answered %s for %s, not with a redirect." % (status or "a page", what))
    except urllib.error.HTTPError as err:
        try:
            if err.code not in REDIRECT_CODES:
                raise ProcessorError("The server answered %s %s for %s, not with a redirect." % (err.code, err.reason, what))
            location = err.headers.get("Location") if err.headers is not None else None
            location = location.strip() if isinstance(location, str) else None
        finally:
            err.close()
        if not location:
            raise ProcessorError("The redirect for %s has no Location header." % what)
        return urllib.parse.urljoin(url, location)
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("The server could not be asked for %s: %s" % (what, err))


def fetch_text(url, max_bytes, what):
    """GET the address and return its text. No redirect is followed. The one
    place where a page is fetched: tests replace this function or open_request.
    `what` names the thing for the messages ("the download page")."""
    check_address(url, what)
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


def links_of(page_text):
    """The addresses of the links of a page, with HTML entities decoded."""
    return [html.unescape(double or single) for double, single in LINK_PATTERN.findall(page_text)]


def find_download_link(page_text, version):
    """(item id, file name) of the one gallery link of the MSI, or raise
    ValueError with a reason that is safe to show. A link of /gallery/item/ that
    ends in .msi must be of the expected form: it is an error, not a skip."""
    file_name_pattern = re.compile(FILE_NAME_TEMPLATE.format(version=re.escape(version)))
    found = set()
    for address in links_of(page_text):
        gallery = GALLERY_PATH_PATTERN.fullmatch(address)
        if not gallery:
            continue  # not a gallery link of an MSI (a language prefix makes /de/gallery/..., also skipped)
        item_id, file_name = gallery.groups()
        if not file_name_pattern.fullmatch(file_name):
            raise ValueError(
                "a gallery link names %r, which is not inkscape-%s_<date and commit>-x64.signed_<token>.msi"
                % (file_name[:80], version)
            )
        found.add((item_id, file_name))
    if not found:
        raise ValueError("the page has no gallery link to an MSI of release %s" % version)
    if len(found) != 1:
        raise ValueError("the page has %d different gallery links to an MSI, not exactly one" % len(found))
    return next(iter(found))


def find_hash_link(page_text):
    """The address of the one hash file linked on the gallery page, or raise
    ValueError. A link that ends in .sha256 must be exactly
    https://media.inkscape.org/media/resources/sigs/<name>.sha256."""
    found = set()
    for address in links_of(page_text):
        if not address.endswith(".sha256"):
            continue
        parts = urllib.parse.urlsplit(address)
        ok = (
            parts.scheme == "https"
            and parts.netloc == MEDIA_HOST
            and not parts.query
            and not parts.fragment
            and parts.path.startswith(SIGS_PATH)
            and SIG_NAME_PATTERN.fullmatch(parts.path[len(SIGS_PATH):]) is not None
        )
        if not ok:
            raise ValueError(
                "a link to a .sha256 file is not https://%s%s<name>.sha256: %r" % (MEDIA_HOST, SIGS_PATH, address[:100])
            )
        found.add(address)
    if not found:
        raise ValueError("the page has no link to a .sha256 file")
    if len(found) != 1:
        raise ValueError("the page has %d different links to a .sha256 file, not exactly one" % len(found))
    return next(iter(found))


def hash_file_name(file_name):
    """The name that the hash file gives for the file: the download's name with
    _<token> removed before .msi."""
    found = re.fullmatch(r"(inkscape-[0-9.]+_[A-Za-z0-9._-]+-x64\.signed)_[A-Za-z0-9]+\.msi", file_name or "")
    if not found:
        raise ValueError("%s is not the name of a download of the MSI" % repr(file_name)[:60])
    return found.group(1) + ".msi"


def parse_hash_line(text, file_name):
    """The SHA-256 (lower case) of the one line of the hash file, or raise
    ValueError. The line is 64 hex digits, two spaces, and a file name, which
    must be the download's name without its token."""
    expected = hash_file_name(file_name)
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError("the hash file has %d lines, not exactly one" % len(lines))
    found = HASH_LINE_PATTERN.fullmatch(lines[0])
    if not found:
        raise ValueError("the line of the hash file is not 64 hex digits, two spaces and a file name")
    if found.group(2) != expected:
        raise ValueError("the hash file names %r, not %s" % (found.group(2)[:80], expected))
    return found.group(1).lower()


class InkscapeInfoProvider(Processor):
    description = __doc__
    input_variables = {
        "inkscape_architecture": {
            "required": False,
            "default": DEFAULT_ARCHITECTURE,
            "description": "The architecture as the site writes it in its addresses: 64-bit (the only one accepted).",
        },
    }
    output_variables = {
        "url": {"description": "The address of the MSI on the publisher's media server."},
        "version": {"description": "The release: numbers separated by dots, such as 1.4.4."},
        "expected_sha256": {
            "description": "The SHA-256 that the publisher's hash file gives for the file (lower-case hex)."
        },
    }

    def text_input(self, name, default):
        value = self.env.get(name, default)
        if not isinstance(value, str) or not value.strip():
            raise ProcessorError("%s must be text that is not empty." % name)
        return value.strip()

    def main(self):
        architecture = self.text_input("inkscape_architecture", DEFAULT_ARCHITECTURE)
        try:
            check_architecture(architecture)
        except ValueError as err:
            raise ProcessorError("inkscape_architecture: %s." % err)

        location = fetch_location(RELEASE_URL, "the current release")
        try:
            version = parse_release_location(location)
        except ValueError as err:
            raise ProcessorError("Inkscape release address: %s." % err)

        page = fetch_text(dl_page_url(version, architecture), MAX_PAGE_BYTES, "the download page")
        try:
            item_id, file_name = find_download_link(page, version)
        except ValueError as err:
            raise ProcessorError("Inkscape download page: %s." % err)

        item = fetch_text(item_page_url(item_id), MAX_PAGE_BYTES, "the gallery page of the file")
        try:
            hash_url = find_hash_link(item)
        except ValueError as err:
            raise ProcessorError("Inkscape gallery page: %s." % err)

        hash_text = fetch_text(hash_url, MAX_HASH_FILE_BYTES, "the hash file")
        try:
            sha256 = parse_hash_line(hash_text, file_name)
        except ValueError as err:
            raise ProcessorError("Inkscape hash file: %s." % err)

        self.env["url"] = media_url(file_name)
        self.env["version"] = version
        self.env["expected_sha256"] = sha256
        self.output("Current release: %s" % version)
        self.output("Vendor's SHA-256: %s" % sha256)


if __name__ == "__main__":
    processor = InkscapeInfoProvider()
    processor.execute_shell()
