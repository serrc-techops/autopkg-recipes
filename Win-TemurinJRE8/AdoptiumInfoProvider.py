#!/usr/local/autopkg/python
"""Find the latest Eclipse Temurin installer for Windows and the SHA-256 that the project publishes for it.

One file of the project's API is read:

    https://api.adoptium.net/v3/assets/latest/<feature>/hotspot?os=<os>&architecture=<architecture>&image_type=<type>&vendor=eclipse

The answer is a JSON array of one element. The element has a `release_name`
(jdk8u504-b01 for Java 8) and a `binary`. The binary has an `os`, an
`architecture`, an `image_type`, and an `installer` with a `name` (an .msi), a
`link` (an address on GitHub) and a `checksum` (a SHA-256). The binary also has a
`package`, which is a zip file: this processor never takes it.

The processor outputs:

    url              the address of the installer (the `link` of the installer)
    version          the `release_name` of the project (jdk8u504-b01)
    expected_sha256  the `checksum` of the installer (lower-case hex)

The hash comes from the project's API and the file from GitHub: two hosts. The
check shows that the file is what the project published. It does not help if
the project's release is changed on both.

How strict it is:

  - The request goes to one fixed host over https. A redirect is NOT followed:
    it is an error. A status other than 200 is an error. The answer is limited
    in size (1 MiB) and in time (120 seconds), and must be UTF-8 text.
  - The feature version is digits only, the image type is jre or jdk, the
    architecture is x64, x86 or aarch64, the operating system is windows.
    Anything else is an error and nothing is fetched.
  - The answer must be an array of exactly one element. Its `binary.os`,
    `binary.architecture` and `binary.image_type` must be equal to the inputs.
  - The installer must have a name that ends in .msi, a link that begins with
    https://github.com/adoptium/temurin<feature>-binaries/releases/download/
    followed by one folder and that file name and nothing else (no query, no
    fragment), and a checksum of 64 hex digits.
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
    "AdoptiumInfoProvider",
    "api_address",
    "check_address",
    "choose_installer",
    "fetch_text",
    "link_prefix",
    "open_request",
]

API_HOST = "api.adoptium.net"
API_BASE_URL = "https://api.adoptium.net/v3/assets/latest/"
# The only host name that this processor talks to.
ALLOWED_HOSTS = (API_HOST,)
RELEASE_LINK_HOST = "github.com"
FETCH_TIMEOUT_SECONDS = 120
# The answer for one product is a few KB. More than this is not that answer.
MAX_ANSWER_BYTES = 1024 * 1024
USER_AGENT = "autopkg-AdoptiumInfoProvider"

DEFAULT_FEATURE_VERSION = "8"
DEFAULT_IMAGE_TYPE = "jre"
DEFAULT_ARCHITECTURE = "x64"
DEFAULT_OS = "windows"
IMAGE_TYPES = ("jre", "jdk")
ARCHITECTURES = ("x64", "x86", "aarch64")
# Only Windows has an MSI installer.
OPERATING_SYSTEMS = ("windows",)

FEATURE_VERSION_PATTERN = re.compile(r"[1-9][0-9]{0,2}")
HASH_PATTERN = re.compile(r"[0-9A-Fa-f]{64}")
# The tag of a release as the project writes it: letters, digits and the
# characters of jdk8u504-b01 and jdk-17.0.9+9. It begins with a letter or a
# digit, so that it is never "." or "..". In a link a plus may be written %2B.
RELEASE_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}")
LINK_FOLDER_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._+-]|%2B){0,63}")
INSTALLER_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.msi")


def api_address(feature, image_type, architecture, operating_system):
    """The address of the API for the inputs. The inputs must be checked first."""
    return "%s%s/hotspot?os=%s&architecture=%s&image_type=%s&vendor=eclipse" % (
        API_BASE_URL, feature, operating_system, architecture, image_type,
    )


def link_prefix(feature):
    """The beginning that every installer link of this feature version must have."""
    return "https://%s/adoptium/temurin%s-binaries/releases/download/" % (RELEASE_LINK_HOST, feature)


def check_address(url):
    """ValueError unless the address is https, on the fixed host, with no
    user name, no port and no fragment. This is checked for every fetch."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise ValueError("the address %s is not on the fixed host of the project" % url[:80])
    if parts.username is not None or parts.password is not None or parts.port is not None or parts.fragment:
        raise ValueError("the address %s has a user name, a port or a fragment" % url[:80])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The answer is a plain answer of one fixed host. A redirect would send the
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


def choose_installer(text, feature, image_type, architecture, operating_system):
    """(url, release_name, sha256) from the text of the answer, or ValueError
    with a reason that is safe to show. sha256 is lower-case hex."""
    try:
        answer = json.loads(text)
    except ValueError as err:
        raise ValueError("it is not JSON: %s" % err)
    if not isinstance(answer, list):
        raise ValueError("it is not a JSON array")
    if len(answer) != 1:
        raise ValueError("it has %d elements, not exactly one" % len(answer))
    element = answer[0]
    if not isinstance(element, dict):
        raise ValueError("its element is not a JSON object")
    release_name = element.get("release_name")
    if not isinstance(release_name, str) or not RELEASE_NAME_PATTERN.fullmatch(release_name):
        raise ValueError("it has no release_name of the form of a release name")
    binary = element.get("binary")
    if not isinstance(binary, dict):
        raise ValueError("its element has no binary")
    for key, wanted in (("os", operating_system), ("architecture", architecture), ("image_type", image_type)):
        value = binary.get(key)
        if value != wanted:
            raise ValueError("its binary has %s %r, not the %r of the inputs" % (key, str(value)[:24], wanted))
    installer = binary.get("installer")
    if not isinstance(installer, dict):
        raise ValueError("its binary has no installer")
    name = installer.get("name")
    if not isinstance(name, str) or not INSTALLER_NAME_PATTERN.fullmatch(name):
        raise ValueError("its installer has no name that ends in .msi")
    link = installer.get("link")
    if not isinstance(link, str):
        raise ValueError("its installer has no link")
    prefix = link_prefix(feature)
    if not link.startswith(prefix):
        raise ValueError("the link of the installer does not begin with %s" % prefix)
    rest = link[len(prefix):].split("/")
    if len(rest) != 2 or not LINK_FOLDER_PATTERN.fullmatch(rest[0]) or rest[1] != name:
        raise ValueError("the link of the installer is not <release folder>/<installer name> under %s" % prefix)
    checksum = installer.get("checksum")
    if not isinstance(checksum, str) or not HASH_PATTERN.fullmatch(checksum):
        raise ValueError("its installer has no checksum of 64 hex digits")
    return link, release_name, checksum.lower()


class AdoptiumInfoProvider(Processor):
    description = __doc__
    input_variables = {
        "temurin_feature_version": {
            "required": False,
            "default": DEFAULT_FEATURE_VERSION,
            "description": "The feature version of Java: digits only, such as 8 or 17.",
        },
        "temurin_image_type": {
            "required": False,
            "default": DEFAULT_IMAGE_TYPE,
            "description": "jre or jdk.",
        },
        "temurin_architecture": {
            "required": False,
            "default": DEFAULT_ARCHITECTURE,
            "description": "x64, x86 or aarch64.",
        },
        "temurin_os": {
            "required": False,
            "default": DEFAULT_OS,
            "description": "windows. Only Windows has an MSI installer.",
        },
    }
    output_variables = {
        "url": {"description": "The address of the installer (an MSI) on GitHub, as the project's API gives it."},
        "version": {"description": "The release name of the project, such as jdk8u504-b01."},
        "expected_sha256": {
            "description": "The SHA-256 that the project's API gives for the installer (lower-case hex)."
        },
    }

    def choice_input(self, name, default, allowed):
        value = self.env.get(name, default)
        if not isinstance(value, str) or value not in allowed:
            raise ProcessorError("%s must be one of %s: %r" % (name, ", ".join(allowed), str(value)[:40]))
        return value

    def main(self):
        feature = self.env.get("temurin_feature_version", DEFAULT_FEATURE_VERSION)
        if not isinstance(feature, str) or not FEATURE_VERSION_PATTERN.fullmatch(feature):
            raise ProcessorError(
                "temurin_feature_version must be digits only, such as 8 or 17: %r" % str(feature)[:24]
            )
        image_type = self.choice_input("temurin_image_type", DEFAULT_IMAGE_TYPE, IMAGE_TYPES)
        architecture = self.choice_input("temurin_architecture", DEFAULT_ARCHITECTURE, ARCHITECTURES)
        operating_system = self.choice_input("temurin_os", DEFAULT_OS, OPERATING_SYSTEMS)

        text = fetch_text(
            api_address(feature, image_type, architecture, operating_system),
            MAX_ANSWER_BYTES, "The Adoptium API",
        )
        try:
            url, release_name, sha256 = choose_installer(text, feature, image_type, architecture, operating_system)
        except ValueError as err:
            raise ProcessorError("The Adoptium API answer: %s." % err)

        self.env["url"] = url
        self.env["version"] = release_name
        self.env["expected_sha256"] = sha256
        self.output("Latest Temurin %s %s of Java %s: %s" % (image_type, operating_system, feature, release_name))
        self.output("The project's SHA-256: %s" % sha256)


if __name__ == "__main__":
    processor = AdoptiumInfoProvider()
    processor.execute_shell()
