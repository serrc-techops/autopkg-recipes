#!/usr/local/autopkg/python
"""Find the current Visual Studio Code for Windows (the System Installer) and the
SHA-256 that Microsoft publishes for it.

One file of Microsoft's site is read:

    https://code.visualstudio.com/sha?build=stable

It answers a JSON object. Its key "products" is a list with one element for
every download of the current stable release (25 on 2026-11-13: Windows, macOS,
Linux and the command-line tool). Each element has:

    url             the address of the file
    productVersion  the version as numbers (1.146.0)
    name            the same text as productVersion
    version         the commit of the release (40 hex digits)
    sha256hash      the SHA-256 of the file (64 hex digits)
    hash            another hash (40 hex digits), not used
    build           "stable"
    platform        an object: "os" names the kind of download (win32-x64 is
                    the System Installer for x64, win32-x64-user the User
                    Installer, win32-x64-archive the zip) and "prettyname"
                    says it in words

The processor outputs:

    url              the address of the installer, as the JSON gives it
    version          productVersion (1.146.0)
    expected_sha256  the sha256hash of the same element (lower-case hex)

The hash and the address come from code.visualstudio.com, the file from
Microsoft's download host. The check shows that the downloaded file is the file
that Microsoft's site names for this release. It does not help if Microsoft's
site is changed, and it checks no signature.

How strict it is:

  - The one fetch goes to a fixed address on code.visualstudio.com over https.
    A redirect is NOT followed: it is an error. A status other than 200 is an
    error. The answer is limited in size (1 MB) and in time (120 seconds), and
    must be UTF-8 text.
  - The platform is win32-x64 or win32-arm64: a System Installer, which
    installs for every user of the PC. The User Installer (which installs into
    one person's profile) and the zip are refused, and so is anything else.
  - The answer must be a JSON object whose "products" is a list of objects,
    each with a platform object whose "os" is text. Exactly one element has the
    wanted os; none, or more than one, is an error. That element's "build" must
    be "stable", its "productVersion" numbers and dots (two to four numbers),
    its "version" 40 hex digits and its "sha256hash" exactly 64 hex digits.
  - Its "url" must be exactly https://vscode.download.prss.microsoft.com/dbazure/download/stable/
    followed by the element's commit and the file name
    VSCodeSetup-<arch>-<productVersion>.exe, with no user name, port, query or
    fragment. Anything else is an error.
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
    "VisualStudioCodeInfoProvider",
    "PLATFORMS",
    "check_address",
    "check_download_url",
    "fetch_text",
    "installer_name",
    "open_request",
    "select_product",
]

SHA_URL = "https://code.visualstudio.com/sha?build=stable"
# The only host name that this processor talks to.
ALLOWED_HOST = "code.visualstudio.com"
# The only host and folder that the installer's address may name (seen on 2026-11-13).
DOWNLOAD_HOST = "vscode.download.prss.microsoft.com"
DOWNLOAD_PATH_PREFIX = "/dbazure/download/stable/"
FETCH_TIMEOUT_SECONDS = 120
# The answer was about 14 KB on 2026-11-13.
MAX_SHA_BYTES = 1024 * 1024
USER_AGENT = "autopkg-VisualStudioCodeInfoProvider"

DEFAULT_PLATFORM = "win32-x64"
# The System Installers, by the os of the JSON, and the architecture in their file name.
PLATFORMS = {"win32-x64": "x64", "win32-arm64": "arm64"}
BUILD = "stable"

VERSION_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+){1,3}")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
SHA256_PATTERN = re.compile(r"[0-9A-Fa-f]{64}")


def installer_name(architecture, version):
    """The file name of the System Installer, as Microsoft names it."""
    return "VSCodeSetup-%s-%s.exe" % (architecture, version)


def check_address(url):
    """ValueError unless the address is https, on the fixed host, with no user
    name, no port and no fragment. This is checked for every fetch."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname != ALLOWED_HOST:
        raise ValueError("the address %s is not on the fixed host of Microsoft" % url[:80])
    if parts.username is not None or parts.password is not None or parts.port is not None or parts.fragment:
        raise ValueError("the address %s has a user name, a port or a fragment" % url[:80])


def check_download_url(url, commit, architecture, version):
    """ValueError unless the installer's address is exactly the fixed download
    host and folder, the commit and the file name of this version."""
    if not isinstance(url, str):
        raise ValueError("its url is not text")
    expected = "https://%s%s%s/%s" % (DOWNLOAD_HOST, DOWNLOAD_PATH_PREFIX, commit, installer_name(architecture, version))
    if url != expected:
        raise ValueError("its url %r is not %s" % (url[:160], expected))
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != "https" or parts.hostname != DOWNLOAD_HOST or parts.username is not None
            or parts.password is not None or parts.port is not None or parts.query or parts.fragment):
        raise ValueError("its url %r is not a plain https address on %s" % (url[:160], DOWNLOAD_HOST))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The file is a plain answer of one fixed host. A redirect would send the
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


def select_product(text, platform):
    """(url, version, sha256) of the one element of the answer whose os is
    `platform`, or ValueError. Every element is checked for its os, not only
    the one that is taken."""
    architecture = PLATFORMS[platform]
    try:
        data = json.loads(text)
    except ValueError as err:
        raise ValueError("it is not JSON: %s" % err)
    if not isinstance(data, dict):
        raise ValueError("it is not a JSON object")
    products = data.get("products")
    if not isinstance(products, list):
        raise ValueError("its products is not a list")
    found = []
    for number, product in enumerate(products, 1):
        if not isinstance(product, dict):
            raise ValueError("element %d of products is not an object" % number)
        kind = product.get("platform")
        if not isinstance(kind, dict) or not isinstance(kind.get("os"), str):
            raise ValueError("element %d of products has no platform with a text os" % number)
        if kind["os"] == platform:
            found.append(product)
    if not found:
        raise ValueError("it has no element with the os %s" % platform)
    if len(found) > 1:
        raise ValueError("it has %d elements with the os %s, not exactly one" % (len(found), platform))
    product = found[0]
    if product.get("build") != BUILD:
        raise ValueError("the element of %s has the build %r, not %s" % (platform, str(product.get("build"))[:40], BUILD))
    version = product.get("productVersion")
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise ValueError("the productVersion %r of %s is not numbers and dots" % (str(version)[:40], platform))
    commit = product.get("version")
    if not isinstance(commit, str) or not COMMIT_PATTERN.fullmatch(commit):
        raise ValueError("the version (commit) %r of %s is not 40 hex digits" % (str(commit)[:60], platform))
    sha256 = product.get("sha256hash")
    if not isinstance(sha256, str) or not SHA256_PATTERN.fullmatch(sha256):
        raise ValueError("the sha256hash of %s is not exactly 64 hex digits" % platform)
    try:
        check_download_url(product.get("url"), commit, architecture, version)
    except ValueError as err:
        raise ValueError("the element of %s: %s" % (platform, err))
    return product["url"], version, sha256.lower()


class VisualStudioCodeInfoProvider(Processor):
    description = __doc__
    input_variables = {
        "vscode_platform": {
            "required": False,
            "default": DEFAULT_PLATFORM,
            "description": "The System Installer to take: win32-x64 or win32-arm64. The User Installer "
                           "and the zip are refused, and so is anything else.",
        },
    }
    output_variables = {
        "url": {"description": "The address of the installer on Microsoft's download host."},
        "version": {"description": "The productVersion of the release, such as 1.146.0."},
        "expected_sha256": {
            "description": "The SHA-256 that code.visualstudio.com gives for the installer (lower-case hex)."
        },
    }

    def main(self):
        platform = self.env.get("vscode_platform", DEFAULT_PLATFORM)
        if platform is None:
            platform = DEFAULT_PLATFORM
        if not isinstance(platform, str) or platform not in PLATFORMS:
            raise ProcessorError(
                "vscode_platform must be one of %s (a System Installer; the User Installer and the zip "
                "are not taken): %r" % (", ".join(sorted(PLATFORMS)), str(platform)[:40])
            )
        text = fetch_text(SHA_URL, MAX_SHA_BYTES, "Microsoft's release file")
        try:
            url, version, sha256 = select_product(text, platform)
        except ValueError as err:
            raise ProcessorError("Microsoft's release file: %s." % err)

        self.env["url"] = url
        self.env["version"] = version
        self.env["expected_sha256"] = sha256
        self.output("Current Visual Studio Code (%s): %s" % (platform, version))
        self.output("Microsoft's SHA-256: %s" % sha256)


if __name__ == "__main__":
    processor = VisualStudioCodeInfoProvider()
    processor.execute_shell()
