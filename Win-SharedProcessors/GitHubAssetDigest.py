#!/usr/local/autopkg/python
"""Read the SHA-256 that GitHub records for one release asset.

GitHub's API gives each release asset a "digest" field ("sha256:<hex>").
The core processor GitHubReleasesInfoProvider has no output for it, so this
processor fetches the record of the asset itself and outputs the hash as
expected_sha256, for ChecksumVerifier.

The record and the file come from one place: this check proves that the file
is what GitHub holds, not that GitHub's content is the vendor's. The request
is anonymous and goes to the API of one fixed host. A redirect is not followed:
it is an error that names the status.

The recipe stops (ProcessorError) when the URL is not the API URL of an
asset, when the request fails, when the record has no digest, or when the
digest is not a SHA-256.
"""
import http.client
import json
import re
import urllib.error
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = ["GitHubAssetDigest", "fetch_asset_record", "digest_to_sha256"]

# The only kind of URL that is fetched: the API record of one release asset.
ASSET_API_URL_PATTERN = re.compile(
    r"https://api\.github\.com/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
    r"/releases/assets/[0-9]+"
)
FETCH_TIMEOUT_SECONDS = 30
# A record of an asset is a few kilobytes; more than this is not a record.
MAX_RESPONSE_BYTES = 1024 * 1024
USER_AGENT = "autopkg-GitHubAssetDigest"
DIGEST_ALGORITHM = "sha256"
HASH_PATTERN = re.compile(r"[0-9a-f]{64}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The record of an asset is a plain answer of the one fixed host. A
    redirect would send the request elsewhere: it is an error (HTTPError)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request):
    """Send the request without following redirects."""
    opener = urllib.request.build_opener(NoRedirect)
    return opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)


def fetch_asset_record(url):
    """GET the record of an asset and return it as a dict. The one place
    where the network is used: tests replace this function."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with open_request(request) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as err:
        redirect = " (a redirect is not followed)" if 300 <= err.code < 400 else ""
        message = "GitHub answered %s %s for the asset record%s." % (err.code, err.reason, redirect)
        err.close()
        raise ProcessorError(message)
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("The asset record could not be fetched: %s" % err)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ProcessorError("The asset record is larger than %d bytes." % MAX_RESPONSE_BYTES)
    try:
        record = json.loads(body.decode("utf-8"))
    except ValueError as err:
        raise ProcessorError("The asset record is not JSON: %s" % err)
    return record


def digest_to_sha256(digest):
    """Return the lower-case hex of a GitHub digest ("sha256:<hex>"), or
    raise ValueError with a reason that is safe to show."""
    if not isinstance(digest, str) or not digest:
        raise ValueError("the record has no digest (older assets have none)")
    algorithm, separator, value = digest.partition(":")
    if not separator or algorithm.lower() != DIGEST_ALGORITHM:
        raise ValueError(
            "the digest is not a SHA-256 (it starts with %r)" % algorithm[:16]
        )
    value = value.lower()
    if not HASH_PATTERN.fullmatch(value):
        raise ValueError("the digest is not 64 hex digits")
    return value


class GitHubAssetDigest(Processor):
    description = __doc__
    input_variables = {
        "github_asset_api_url": {
            "required": True,
            "description": (
                "The API URL of the release asset, "
                "https://api.github.com/repos/<owner>/<repo>/releases/assets/<id>. "
                "In a recipe it is fed from the output of the core processor "
                "GitHubReleasesInfoProvider (expected: asset_url)."
            ),
        },
    }
    output_variables = {
        "expected_sha256": {
            "description": "The SHA-256 of the asset (lower-case hex, no prefix).",
        },
    }

    def main(self):
        url = self.env.get("github_asset_api_url")
        if not isinstance(url, str) or not ASSET_API_URL_PATTERN.fullmatch(url):
            raise ProcessorError(
                "github_asset_api_url is not the API URL of a release asset "
                "(https://api.github.com/repos/<owner>/<repo>/releases/assets/<id>): %r"
                % (url if not isinstance(url, str) else url[:80],)
            )
        record = fetch_asset_record(url)
        if not isinstance(record, dict):
            raise ProcessorError("The asset record is not a JSON object.")
        try:
            sha256 = digest_to_sha256(record.get("digest"))
        except ValueError as err:
            raise ProcessorError("GitHub asset %s: %s" % (url.rsplit("/", 1)[-1], err))
        self.env["expected_sha256"] = sha256
        self.output("GitHub's digest of the asset: %s" % sha256)


if __name__ == "__main__":
    processor = GitHubAssetDigest()
    processor.execute_shell()
