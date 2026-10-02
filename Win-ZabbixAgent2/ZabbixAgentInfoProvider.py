#!/usr/local/autopkg/python
"""Find the newest release of a Zabbix agent on the vendor's download page.

The page https://www.zabbix.com/download_agents holds one record for every
file the vendor offers. The records are JSON in the attribute `:agents` of the
element <download-agents-filter>, written with HTML entities. Each record has
the release, the platform, the architecture, the encryption, the packaging,
the type of agent, the path of the file and its SHA-256.

This processor reads the records, keeps those that match the inputs, and takes
the newest release. "Newest" is decided by comparing the three numbers of the
release (7.0.31 is newer than 7.0.5), not by the order on the page. It outputs:

    url              the address of the file on the vendor's download server
    version          the release, three numbers (7.0.31)
    expected_sha256  the SHA-256 that the page gives for the file

The hash and the file come from two host names of one vendor. The check shows
that the file is what the vendor published, not more.

A record is taken only when all of these are true: it is of the chosen line
(7.0 takes 7.0.N), its platform, architecture, encryption, packaging and type
match (letter case does not matter), it is not a static build and not a legacy
download. The flags "static" and "legacy" are read by flag_value(): a boolean,
0 or 1, or the text true/false/yes/no/1/0. Any other value is an error, never a
guess. A release that is not three numbers (a pre-release) is ignored.

The file that is returned is checked against the record. Its path must be
exactly <line>/<release>/<file name>, where the file name is built from the
inputs: zabbix_agent2-7.0.31-windows-amd64-openssl.msi for the defaults. No
other file name and no other folder is accepted.

The processor stops the recipe when the page cannot be fetched or is not the
page that is expected, when no record matches, when the newest release has
two different files or hashes, when its record has no valid SHA-256, when a
flag is not one of the accepted spellings, when the inputs are not ones for
which a file name can be built, or when the path of the file is not the
expected one.
"""
import html
import http.client
import json
import re
import urllib.error
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "ZabbixAgentInfoProvider",
    "extract_records",
    "find_newest",
    "release_key",
    "flag_value",
    "expected_file_name",
    "fetch_page",
    "open_request",
]

DOWNLOAD_PAGE_URL = "https://www.zabbix.com/download_agents"
# The page's own script puts this in front of the path of a record.
DOWNLOAD_BASE_URL = "https://cdn.zabbix.com/zabbix/binaries/stable/"
FETCH_TIMEOUT_SECONDS = 120
# The page is about 5.5 MB. More than this is not the page.
MAX_PAGE_BYTES = 32 * 1024 * 1024
USER_AGENT = "autopkg-ZabbixAgentInfoProvider"

DEFAULT_LINE = "7.0"
DEFAULT_PLATFORM = "Windows"
DEFAULT_ARCHITECTURE = "amd64"
DEFAULT_ENCRYPTION = "OpenSSL"
DEFAULT_PACKAGING = "MSI"
DEFAULT_AGENT_TYPE = "agent2"

LINE_PATTERN = re.compile(r"[0-9]+\.[0-9]+")
RELEASE_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
# The file name of a record, built from the inputs. The vendor's names are
# zabbix_agent2-7.0.31-windows-amd64-openssl.msi (an MSI, with OpenSSL) and
# zabbix_agent2-7.0.31-windows-amd64.zip (an archive, no encryption).
FILE_NAME_PATTERN = "zabbix_{agent_type}-{release}-{platform}-{architecture}{encryption_part}.{extension}"
# Only the Windows file names are known here.
SUPPORTED_PLATFORM = "windows"
ENCRYPTION_NAME_PARTS = {"openssl": "-openssl", "no encryption": ""}
PACKAGING_EXTENSIONS = {"msi": "msi", "archive": "zip"}
# The spellings of a flag in a record (see flag_value).
FLAG_TRUE_WORDS = ("true", "yes", "1")
FLAG_FALSE_WORDS = ("false", "no", "0")
# What follows the attribute name `:agents=` is one value in double quotes.
# The JSON inside has no raw double quote: they are written as &quot;.
AGENTS_ATTRIBUTE_PATTERN = re.compile(
    r"<download-agents-filter\b[^>]*?\s:agents=\"([^\"]*)\""
)
# Keys that a record needs to be compared with the inputs.
FILTER_KEYS = ("release", "os", "hardware", "encryption", "package", "type")


def release_key(release):
    """The three numbers of a release as a tuple of integers, or None when
    the text is not three numbers separated by dots."""
    if not isinstance(release, str) or not RELEASE_PATTERN.fullmatch(release):
        return None
    return tuple(int(part) for part in release.split("."))


def flag_value(value, key):
    """A flag of a record as a bool. Accepted: a boolean, the integers 0 and 1,
    and the text true, false, yes, no, 1 or 0 in any letter case. Anything else
    (null, 2, "maybe", a list) raises ValueError: a flag that is not understood
    could hide a static build or a legacy download."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        word = value.strip().casefold()
        if word in FLAG_TRUE_WORDS:
            return True
        if word in FLAG_FALSE_WORDS:
            return False
    shown = repr(value)
    raise ValueError("the record has %s = %s, which is not a flag" % (key, shown[:24]))


def expected_file_name(release, platform, architecture, encryption, packaging, agent_type):
    """The file name that a record of these inputs must have, or ValueError
    when the inputs are not ones for which the name is known."""
    if platform.casefold() != SUPPORTED_PLATFORM:
        raise ValueError("platform %s is not supported: only %s file names are known" % (platform, SUPPORTED_PLATFORM))
    if encryption.casefold() not in ENCRYPTION_NAME_PARTS:
        raise ValueError("encryption %s is not supported: use one of %s" % (encryption, ", ".join(sorted(ENCRYPTION_NAME_PARTS))))
    if packaging.casefold() not in PACKAGING_EXTENSIONS:
        raise ValueError("packaging %s is not supported: use one of %s" % (packaging, ", ".join(sorted(PACKAGING_EXTENSIONS))))
    return FILE_NAME_PATTERN.format(
        agent_type=agent_type.casefold(),
        release=release,
        platform=platform.casefold(),
        architecture=architecture.casefold(),
        encryption_part=ENCRYPTION_NAME_PARTS[encryption.casefold()],
        extension=PACKAGING_EXTENSIONS[packaging.casefold()],
    )


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The page is a plain answer of one fixed host. A redirect would send the
    request elsewhere: it is an error (HTTPError)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request):
    """Send the request without following redirects."""
    opener = urllib.request.build_opener(NoRedirect)
    return opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)


def fetch_page(url):
    """GET the page and return its text. The one place where the network is
    used: tests replace this function or open_request."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with open_request(request) as response:
            body = response.read(MAX_PAGE_BYTES + 1)
    except urllib.error.HTTPError as err:
        redirect = " (a redirect is not followed)" if 300 <= err.code < 400 else ""
        message = "The vendor's page answered %s %s%s." % (err.code, err.reason, redirect)
        err.close()
        raise ProcessorError(message)
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("The vendor's page could not be fetched: %s" % err)
    if len(body) > MAX_PAGE_BYTES:
        raise ProcessorError("The vendor's page is larger than %d bytes." % MAX_PAGE_BYTES)
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as err:
        raise ProcessorError("The vendor's page is not UTF-8 text: %s" % err)


def extract_records(page_text):
    """The list of records of the page, or raise ValueError with a reason."""
    matches = AGENTS_ATTRIBUTE_PATTERN.findall(page_text)
    if len(matches) != 1:
        raise ValueError(
            "the page has %d elements <download-agents-filter> with a :agents "
            "attribute, not exactly one" % len(matches)
        )
    try:
        records = json.loads(html.unescape(matches[0]))
    except ValueError as err:
        raise ValueError("the :agents attribute is not JSON: %s" % err)
    if not isinstance(records, list) or not records:
        raise ValueError("the :agents attribute is not a list with records")
    return records


def same(left, right):
    """Equal as text, letter case ignored."""
    return isinstance(left, str) and left.casefold() == right.casefold()


def matches(record, line, platform, architecture, encryption, packaging, agent_type):
    """True when the record is a candidate for the inputs."""
    if not isinstance(record, dict):
        return False
    if any(key not in record for key in FILTER_KEYS):
        return False
    release = record["release"]
    if not isinstance(release, str) or not release.startswith(line + "."):
        return False
    if release_key(release) is None:
        return False  # a pre-release or another form: cannot be compared
    if not (
        same(record["os"], platform)
        and same(record["hardware"], architecture)
        and same(record["encryption"], encryption)
        and same(record["package"], packaging)
        and same(record["type"], agent_type)
    ):
        return False
    # A record that says it is a static build or a legacy download is not wanted.
    # A record without these keys is not static and not legacy. The flags are
    # read last, so that a strange value in a record that is none of ours does
    # not stop the run.
    for key in ("static", "legacy"):
        if key in record and flag_value(record[key], key):
            return False
    return True


def checked_path(path, line, release, platform, architecture, encryption, packaging, agent_type):
    """The path of the file, if it is exactly <line>/<release>/<expected file
    name>. No other file name and no sub-folder is accepted."""
    expected = "%s/%s/%s" % (
        line, release,
        expected_file_name(release, platform, architecture, encryption, packaging, agent_type),
    )
    if path != expected:
        shown = path[:80] if isinstance(path, str) else repr(path)[:80]
        raise ValueError("the path of the file is %r, not the expected %s" % (shown, expected))
    return path


def find_newest(records, line, platform, architecture, encryption, packaging, agent_type):
    """Return (url, release, sha256) of the newest matching release, or raise
    ValueError with a reason that is safe to show."""
    candidates = [
        record
        for record in records
        if matches(record, line, platform, architecture, encryption, packaging, agent_type)
    ]
    if not candidates:
        raise ValueError(
            "no record matches line %s, platform %s, architecture %s, encryption %s, "
            "packaging %s, type %s" % (line, platform, architecture, encryption, packaging, agent_type)
        )
    newest = max(release_key(record["release"]) for record in candidates)
    release = ".".join(str(number) for number in newest)
    of_release = [r for r in candidates if release_key(r["release"]) == newest]
    # The page repeats a file for each version of the operating system. Records of
    # one release must agree on the path and the hash.
    seen = set()
    for record in of_release:
        sha256 = record.get("sha256")
        if not isinstance(sha256, str) or not HASH_PATTERN.fullmatch(sha256.lower()):
            raise ValueError("the record of release %s has no valid SHA-256" % release)
        path = record.get("url")
        if not isinstance(path, str):
            raise ValueError("the record of release %s has no path of a file" % release)
        seen.add((path, sha256.lower()))
    if len(seen) != 1:
        raise ValueError(
            "the records of release %s disagree: %d different files or hashes" % (release, len(seen))
        )
    path, sha256 = next(iter(seen))
    checked = checked_path(path, line, release, platform, architecture, encryption, packaging, agent_type)
    return DOWNLOAD_BASE_URL + checked, release, sha256


class ZabbixAgentInfoProvider(Processor):
    description = __doc__
    input_variables = {
        "zabbix_line": {
            "required": False,
            "default": DEFAULT_LINE,
            "description": "The line of releases: two numbers, such as 7.0.",
        },
        "zabbix_platform": {
            "required": False,
            "default": DEFAULT_PLATFORM,
            "description": "The platform as the page writes it, such as Windows.",
        },
        "zabbix_architecture": {
            "required": False,
            "default": DEFAULT_ARCHITECTURE,
            "description": "The architecture as the page writes it: amd64 or i386.",
        },
        "zabbix_encryption": {
            "required": False,
            "default": DEFAULT_ENCRYPTION,
            "description": "The encryption as the page writes it: OpenSSL or No encryption.",
        },
        "zabbix_packaging": {
            "required": False,
            "default": DEFAULT_PACKAGING,
            "description": "The packaging as the page writes it: MSI or Archive.",
        },
        "zabbix_agent_type": {
            "required": False,
            "default": DEFAULT_AGENT_TYPE,
            "description": "The type of agent as the page writes it: agent or agent2.",
        },
    }
    output_variables = {
        "url": {"description": "The address of the file on the vendor's download server."},
        "version": {"description": "The release: three numbers, such as 7.0.31."},
        "expected_sha256": {
            "description": "The SHA-256 that the page gives for the file (lower-case hex)."
        },
    }

    def text_input(self, name, default):
        value = self.env.get(name, default)
        if not isinstance(value, str) or not value.strip():
            raise ProcessorError("%s must be text that is not empty." % name)
        return value.strip()

    def main(self):
        line = self.text_input("zabbix_line", DEFAULT_LINE)
        if not LINE_PATTERN.fullmatch(line):
            raise ProcessorError(
                "zabbix_line must be two numbers separated by a dot, such as 7.0: %r" % line[:24]
            )
        platform = self.text_input("zabbix_platform", DEFAULT_PLATFORM)
        architecture = self.text_input("zabbix_architecture", DEFAULT_ARCHITECTURE)
        encryption = self.text_input("zabbix_encryption", DEFAULT_ENCRYPTION)
        packaging = self.text_input("zabbix_packaging", DEFAULT_PACKAGING)
        agent_type = self.text_input("zabbix_agent_type", DEFAULT_AGENT_TYPE)

        try:
            expected_file_name(
                "0.0.0", platform, architecture, encryption, packaging, agent_type
            )
        except ValueError as err:
            raise ProcessorError("Zabbix agent inputs: %s." % err)

        page = fetch_page(DOWNLOAD_PAGE_URL)
        try:
            records = extract_records(page)
            url, release, sha256 = find_newest(
                records, line, platform, architecture, encryption, packaging, agent_type
            )
        except ValueError as err:
            raise ProcessorError("Zabbix download page: %s." % err)

        self.env["url"] = url
        self.env["version"] = release
        self.env["expected_sha256"] = sha256
        self.output("Newest release of line %s: %s" % (line, release))
        self.output("Vendor's SHA-256: %s" % sha256)


if __name__ == "__main__":
    processor = ZabbixAgentInfoProvider()
    processor.execute_shell()
