#!/usr/local/autopkg/python
"""Find the newest .NET Desktop Runtime installer for Windows of one channel.

The facts of the source were read on 2026-11-16 (see the README).

Microsoft publishes the release metadata of each channel as JSON:
https://builds.dotnet.microsoft.com/dotnet/release-metadata/<channel>/releases.json
(200, no redirect, about 1.2 MB for channel 10.0). Its top level has
"channel-version", "latest-release", "support-phase" and "releases", a list of
releases, the newest first. A release has "release-version" and
"windowsdesktop": {"version", "files": [{"name", "rid", "url", "hash"}]}. The
hash is a SHA-512 (128 hex digits); there is no SHA-256 in the metadata.

The processor takes the release whose "release-version" is the metadata's
"latest-release" (the first release of the list is not assumed to be it). It
refuses, and sets no output:

  - a channel or a RID that is not valid (the channel is two numbers such as
    10.0; the RID is win-x64, win-x86 or win-arm64);
  - a metadata whose "channel-version" is not the channel asked for;
  - a "latest-release" or a runtime version that is not three plain numbers
    of the channel (a preview or release candidate, such as 10.0.0-rc.2.25502.107,
    is not three plain numbers);
  - a channel whose "support-phase" is not "active" or "maintenance" ("eol"
    only when the input dotnet_allow_eol is true; "preview", "go-live" and
    anything else are refused);
  - a latest release that is not in the list, or has no Windows Desktop
    Runtime files, or has no .exe file for the RID (or more than one);
  - a file whose address is not https on builds.dotnet.microsoft.com with the
    path /dotnet/WindowsDesktop/<version>/windowsdesktop-runtime-<version>-<rid>.exe,
    or whose name is not windowsdesktop-runtime-<rid>.exe, or whose "rid" is
    not the RID asked for, or whose hash is not 128 hex digits.

The fetch goes to builds.dotnet.microsoft.com over https, follows no redirect
(a redirect is an error), has a size limit and a time limit. The installer's
own download (URLDownloader) may be redirected by the server; the check against
the SHA-512 in this metadata is what shows that the file is the right one. The
metadata's detached signature (releases.json.<stamp>.p7s) is NOT checked.

It outputs:

    url              the address of the installer
    version          the runtime's version, three numbers (10.0.15)
    expected_sha512  the SHA-512 that the metadata gives for the installer
    filename         the installer's file name
    dotnet_release_date  the release's date as the metadata gives it, or empty
"""
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "DotNetDesktopRuntimeInfoProvider",
    "metadata_url",
    "validate_channel",
    "validate_rid",
    "select_installer",
    "fetch_json",
    "open_request",
]

HOST = "builds.dotnet.microsoft.com"
METADATA_URL_TEMPLATE = "https://" + HOST + "/dotnet/release-metadata/%s/releases.json"
FETCH_TIMEOUT_SECONDS = 120
# The metadata of channel 10.0 was about 1.2 MB on 2026-11-16 and grows with each
# release; more than this is not the metadata.
MAX_METADATA_BYTES = 16 * 1024 * 1024
USER_AGENT = "autopkg-DotNetDesktopRuntimeInfoProvider"
ALLOWED_RIDS = ("win-x64", "win-x86", "win-arm64")
# What a channel in the "support-phase" field may say for the run to go on.
SUPPORTED_PHASES = ("active", "maintenance")

NUMBER = r"(?:0|[1-9][0-9]*)"
CHANNEL_PATTERN = re.compile(r"%s\.%s" % (NUMBER, NUMBER), re.ASCII)
VERSION_PATTERN = re.compile(r"%s\.%s\.%s" % (NUMBER, NUMBER, NUMBER), re.ASCII)
HASH_PATTERN = re.compile(r"[0-9a-fA-F]{128}")


def validate_channel(channel):
    """The channel (such as 10.0) or raise ValueError."""
    if not isinstance(channel, str) or not CHANNEL_PATTERN.fullmatch(channel):
        raise ValueError("dotnet_channel is not two numbers joined by a dot (such as 10.0): %r" % str(channel)[:24])
    return channel


def validate_rid(rid):
    """The runtime identifier or raise ValueError."""
    if rid not in ALLOWED_RIDS:
        raise ValueError("dotnet_rid is not one of %s: %r" % (", ".join(ALLOWED_RIDS), str(rid)[:24]))
    return rid


def metadata_url(channel):
    return METADATA_URL_TEMPLATE % validate_channel(channel)


def _plain_version(value, channel, what):
    if not isinstance(value, str) or not VERSION_PATTERN.fullmatch(value):
        raise ValueError("%s is not three plain numbers (a preview or release candidate is refused): %r"
                         % (what, str(value)[:40]))
    if not value.startswith(channel + "."):
        raise ValueError("%s %s is not of the channel %s" % (what, value, channel))
    return value


def select_installer(data, channel, rid, allow_eol=False):
    """From the parsed metadata, the dict of url, version, expected_sha512, filename
    and release_date of the latest release's .exe for `rid`; raise ValueError."""
    validate_channel(channel)
    validate_rid(rid)
    if not isinstance(data, dict):
        raise ValueError("the metadata is not a JSON object")
    if data.get("channel-version") != channel:
        raise ValueError("the metadata is of channel %r, not %s" % (str(data.get("channel-version"))[:24], channel))
    phase = data.get("support-phase")
    if phase == "eol":
        if not allow_eol:
            raise ValueError("the channel %s is end of life (support-phase eol); set dotnet_allow_eol to true to take it" % channel)
    elif phase not in SUPPORTED_PHASES:
        raise ValueError("the support-phase of the channel is %r, not one of %s" % (str(phase)[:24], ", ".join(SUPPORTED_PHASES)))
    latest = _plain_version(data.get("latest-release"), channel, "latest-release")
    releases = data.get("releases")
    if not isinstance(releases, list):
        raise ValueError("the metadata has no list of releases")
    matching = [r for r in releases if isinstance(r, dict) and r.get("release-version") == latest]
    if len(matching) != 1:
        raise ValueError("the latest release %s is in the list %d times, not once" % (latest, len(matching)))
    release = matching[0]
    desktop = release.get("windowsdesktop")
    if not isinstance(desktop, dict):
        raise ValueError("the latest release %s has no windowsdesktop section" % latest)
    version = _plain_version(desktop.get("version"), channel, "the windowsdesktop version")
    files = desktop.get("files")
    if not isinstance(files, list):
        raise ValueError("the windowsdesktop section of %s has no list of files" % latest)
    wanted_name = "windowsdesktop-runtime-%s.exe" % rid
    found = [f for f in files if isinstance(f, dict) and f.get("name") == wanted_name]
    if not found:
        raise ValueError("the release %s has no file %s" % (version, wanted_name))
    if len(found) != 1:
        raise ValueError("the release %s lists %s %d times, not once" % (version, wanted_name, len(found)))
    entry = found[0]
    if entry.get("rid") != rid:
        raise ValueError("the file %s names the rid %r, not %s" % (wanted_name, str(entry.get("rid"))[:24], rid))
    url = entry.get("url")
    file_name = "windowsdesktop-runtime-%s-%s.exe" % (version, rid)
    expected_url = "https://%s/dotnet/WindowsDesktop/%s/%s" % (HOST, version, file_name)
    if not isinstance(url, str):
        raise ValueError("the file has no address")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.netloc != HOST or parts.query or parts.fragment or parts.username \
            or parts.password:
        raise ValueError("the address is not a plain https address on %s: %r" % (HOST, url[:80]))
    if url != expected_url:
        raise ValueError("the address is not the expected %s: %r" % (expected_url, url[:120]))
    digest = entry.get("hash")
    if not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest):
        raise ValueError("the hash of %s is not 128 hex digits (a SHA-512)" % file_name)
    date = release.get("release-date")
    return {
        "url": url,
        "version": version,
        "expected_sha512": digest.lower(),
        "filename": file_name,
        "release_date": date if isinstance(date, str) and re.fullmatch(r"[0-9T:+\-Z.]{0,40}", date) else "",
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The metadata is a plain answer of one fixed host. A redirect would send the
    request elsewhere: it is an error (HTTPError)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request):
    """Send the request without following redirects."""
    opener = urllib.request.build_opener(NoRedirect)
    return opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)


def fetch_json(url, max_bytes=MAX_METADATA_BYTES):
    """GET the address and return the parsed JSON. The one place where the network is
    used: tests replace this function or open_request."""
    if not isinstance(url, str) or not url.startswith("https://" + HOST + "/"):
        raise ProcessorError("Refusing to fetch the metadata from an address outside https://%s/." % HOST)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with open_request(request) as response:
            status = getattr(response, "status", 200)
            body = response.read(max_bytes + 1)
    except urllib.error.HTTPError as err:
        redirect = " (a redirect is not followed)" if 300 <= err.code < 400 else ""
        message = "The server answered %s %s for the release metadata%s." % (err.code, err.reason, redirect)
        err.close()
        raise ProcessorError(message)
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("The server could not be asked for the release metadata: %s" % err)
    if status != 200:
        raise ProcessorError("The server answered %s for the release metadata, not 200." % status)
    if len(body) > max_bytes:
        raise ProcessorError("The release metadata is larger than %d bytes." % max_bytes)
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as err:
        raise ProcessorError("The release metadata is not JSON: %s" % err)


class DotNetDesktopRuntimeInfoProvider(Processor):
    description = __doc__
    input_variables = {
        "dotnet_channel": {
            "required": False,
            "default": "10.0",
            "description": "The channel of .NET: two numbers joined by a dot, such as 10.0.",
        },
        "dotnet_rid": {
            "required": False,
            "default": "win-x64",
            "description": "The runtime identifier of the installer: win-x64, win-x86 or win-arm64.",
        },
        "dotnet_allow_eol": {
            "required": False,
            "default": False,
            "description": "True takes the installer of a channel whose support-phase is eol. Default false.",
        },
    }
    output_variables = {
        "url": {"description": "The address of the installer on builds.dotnet.microsoft.com."},
        "version": {"description": "The runtime's version: three plain numbers, such as 10.0.15."},
        "expected_sha512": {
            "description": "The SHA-512 that the metadata gives for the installer (lower-case hex, 128 digits)."
        },
        "filename": {"description": "The installer's file name, such as windowsdesktop-runtime-10.0.15-win-x64.exe."},
        "dotnet_release_date": {"description": "The release date as the metadata gives it, or empty."},
    }

    def main(self):
        channel = self.env.get("dotnet_channel", "10.0")
        rid = self.env.get("dotnet_rid", "win-x64")
        allow_eol = self.env.get("dotnet_allow_eol", False)
        if allow_eol not in (True, False):
            raise ProcessorError("dotnet_allow_eol must be true or false (a boolean).")
        try:
            url = metadata_url(channel)
            validate_rid(rid)
        except ValueError as err:
            raise ProcessorError(".NET Desktop Runtime: %s." % err)
        data = fetch_json(url)
        try:
            chosen = select_installer(data, channel, rid, allow_eol)
        except ValueError as err:
            raise ProcessorError(".NET Desktop Runtime metadata of channel %s: %s." % (channel, err))
        self.env["url"] = chosen["url"]
        self.env["version"] = chosen["version"]
        self.env["expected_sha512"] = chosen["expected_sha512"]
        self.env["filename"] = chosen["filename"]
        self.env["dotnet_release_date"] = chosen["release_date"]
        self.output("Channel %s, latest release %s: %s" % (channel, chosen["version"], chosen["filename"]))
        self.output("SHA-512 from the release metadata: %s" % chosen["expected_sha512"])


if __name__ == "__main__":
    processor = DotNetDesktopRuntimeInfoProvider()
    processor.execute_shell()
