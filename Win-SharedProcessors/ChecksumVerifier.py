#!/usr/local/autopkg/python
"""Check that a downloaded file has the SHA-256 that its publisher gives.

The expected value comes from the publisher (a vendor page, or the digest of
a GitHub release asset). It is written as 64 hex digits, in any letter case,
with or without the prefix "sha256:". Nothing else is accepted: no file name
after the digest, no other length, no other algorithm.

The file is hashed here, in blocks. The processor stops the recipe when the
value is empty, is not a SHA-256, or differs from the hash of the file.
"""
import hashlib
import os
import re

from autopkglib import Processor, ProcessorError

__all__ = ["ChecksumVerifier", "normalize_expected_sha256", "sha256_of_file"]

HASH_PREFIX = "sha256:"
HEX_DIGITS = 64
HASH_PATTERN = re.compile(r"[0-9a-f]{%d}" % HEX_DIGITS)
READ_BLOCK_BYTES = 1024 * 1024
# How much of a hash an error message shows: enough to compare by eye.
SHOWN_HEAD_CHARS = 8
SHOWN_TAIL_CHARS = 8
# How much of a malformed value an error message shows.
SHOWN_BAD_VALUE_CHARS = 24


def shorten(text):
    """Head and tail of a long value, so that a message stays short."""
    if len(text) <= SHOWN_HEAD_CHARS + SHOWN_TAIL_CHARS + 3:
        return text
    return "%s...%s" % (text[:SHOWN_HEAD_CHARS], text[-SHOWN_TAIL_CHARS:])


def normalize_expected_sha256(value):
    """Return the 64 lower-case hex digits of `value`, or raise ValueError
    with a reason that is safe to show."""
    if not isinstance(value, str):
        raise ValueError("expected_sha256 is not text")
    text = value.strip()
    if text[: len(HASH_PREFIX)].lower() == HASH_PREFIX:
        text = text[len(HASH_PREFIX):].strip()
    if not text:
        raise ValueError("expected_sha256 is empty")
    text = text.lower()
    if not HASH_PATTERN.fullmatch(text):
        shown = value.strip()
        if len(shown) > SHOWN_BAD_VALUE_CHARS:
            shown = shown[:SHOWN_BAD_VALUE_CHARS] + "..."
        raise ValueError(
            "expected_sha256 is not a SHA-256 (%d hex digits, with or "
            "without the prefix %r): %r" % (HEX_DIGITS, HASH_PREFIX, shown)
        )
    return text


def sha256_of_file(path):
    """SHA-256 of a file, as lower-case hex, read in blocks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(READ_BLOCK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


class ChecksumVerifier(Processor):
    description = __doc__
    input_variables = {
        "pathname": {
            "required": True,
            "description": "Path to the downloaded file.",
        },
        "expected_sha256": {
            "required": True,
            "description": (
                "The SHA-256 that the publisher gives: 64 hex digits, any "
                "letter case, with or without the prefix 'sha256:'."
            ),
        },
    }
    output_variables = {
        "checksum_verified": {
            "description": "True when the file has the expected SHA-256.",
        },
        "checksum_sha256": {
            "description": "The SHA-256 of the file (lower-case hex).",
        },
    }

    def main(self):
        try:
            expected = normalize_expected_sha256(self.env.get("expected_sha256"))
        except ValueError as err:
            raise ProcessorError(str(err))

        path = self.env.get("pathname")
        if not path or not os.path.isfile(path):
            raise ProcessorError("pathname is not a file: %r" % (path,))
        try:
            actual = sha256_of_file(path)
        except OSError as err:
            raise ProcessorError("Could not read %s: %s" % (path, err))

        if actual != expected:
            raise ProcessorError(
                "SHA-256 mismatch for %s: expected %s, got %s"
                % (os.path.basename(path), shorten(expected), shorten(actual))
            )

        self.env["checksum_verified"] = True
        self.env["checksum_sha256"] = actual
        self.output("SHA-256 verified: %s" % actual)


if __name__ == "__main__":
    processor = ChecksumVerifier()
    processor.execute_shell()
