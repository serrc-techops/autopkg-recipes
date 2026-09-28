#!/usr/local/autopkg/python
"""Verify a downloaded ReportMate .pkg against the release's own .sha256.

Upstream publishes the package unsigned, so there is no signature for
CodeSignatureVerifier to check. This compares the SHA-256 of the download
with the "<pkg>.sha256" asset of the same release, which URLTextSearcher
fetched into expected_sha256.

Skipped when the recipe was given a package with the PKG input: that file
was signed by the operator, and a signed file never has the hash of the
unsigned release.
"""
import hashlib

from autopkglib import Processor, ProcessorError

__all__ = ["ReportMateChecksumVerifier"]


class ReportMateChecksumVerifier(Processor):
    description = __doc__
    input_variables = {
        "pkg_path": {
            "required": True,
            "description": "Path to the downloaded (or overridden) package.",
        },
        "expected_sha256": {
            "required": True,
            "description": (
                "Text fetched from the release's own <pkg>.sha256 asset "
                "(URLTextSearcher output) -- 'hexdigest  filename', the "
                "standard `shasum -a 256` / `sha256sum` format."
            ),
        },
    }
    output_variables = {
        "reportmate_checksum_verified": {
            "description": "True when the SHA-256 was checked and matched.",
        },
    }

    def main(self):
        if self.env.get("PKG"):
            self.output(
                "PKG input given (%s): checksum comparison skipped."
                % self.env["PKG"]
            )
            self.env["reportmate_checksum_verified"] = False
            return

        expected = self.env["expected_sha256"].strip().split()
        if not expected:
            raise ProcessorError(
                "expected_sha256 was empty; the release's .sha256 asset "
                "did not fetch correctly."
            )
        expected_hex = expected[0].lower()
        if len(expected_hex) != 64 or any(c not in "0123456789abcdef" for c in expected_hex):
            raise ProcessorError(
                "expected_sha256 does not look like a SHA-256 hex digest: %r"
                % expected[0]
            )

        digest = hashlib.sha256()
        with open(self.env["pkg_path"], "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        actual_hex = digest.hexdigest()

        if actual_hex != expected_hex:
            raise ProcessorError(
                "SHA-256 mismatch for %s: expected %s, got %s"
                % (self.env["pkg_path"], expected_hex, actual_hex)
            )

        self.output("SHA-256 verified: %s" % actual_hex)
        self.env["reportmate_checksum_verified"] = True


if __name__ == "__main__":
    processor = ReportMateChecksumVerifier()
    processor.execute_shell()
