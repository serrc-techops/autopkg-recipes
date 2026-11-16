#!/usr/local/autopkg/python
"""Check that a downloaded file has the SHA-512 that its publisher gives.

Why this processor exists: the shared ChecksumVerifier takes a SHA-256 only, and
Microsoft's release metadata for .NET gives a SHA-512 only. The shared processor
is not changed (every override trusts its text). This one hashes the file with
SHA-512 and compares; when they are equal it sets the two outputs that the
importers read from the shared verifier:

    checksum_verified   true (a boolean)
    checksum_sha256     the SHA-256 of the file (the importers compare it with
                        the hash of the file they import, so another file is refused)

The expected value is 128 hex digits in any letter case, with or without the
prefix "sha512:". Nothing else is accepted. On a mismatch, an unreadable file or
a malformed value the processor stops the recipe and sets neither output.
"""
import hashlib
import os
import re

from autopkglib import Processor, ProcessorError

__all__ = ["Sha512ChecksumVerifier", "normalize_expected_sha512", "hashes_of_file"]

HASH_PREFIX = "sha512:"
HEX_DIGITS = 128
HASH_PATTERN = re.compile(r"[0-9a-f]{%d}" % HEX_DIGITS)
READ_BLOCK_BYTES = 1024 * 1024
SHOWN_HEAD_CHARS = 8
SHOWN_TAIL_CHARS = 8
SHOWN_BAD_VALUE_CHARS = 24


def shorten(text):
    if len(text) <= SHOWN_HEAD_CHARS + SHOWN_TAIL_CHARS + 3:
        return text
    return "%s...%s" % (text[:SHOWN_HEAD_CHARS], text[-SHOWN_TAIL_CHARS:])


def normalize_expected_sha512(value):
    """The 128 lower-case hex digits of `value`, or raise ValueError with a reason that is safe to show."""
    if not isinstance(value, str):
        raise ValueError("expected_sha512 is not text")
    text = value.strip()
    if text[: len(HASH_PREFIX)].lower() == HASH_PREFIX:
        text = text[len(HASH_PREFIX):].strip()
    if not text:
        raise ValueError("expected_sha512 is empty")
    text = text.lower()
    if not HASH_PATTERN.fullmatch(text):
        shown = value.strip()
        if len(shown) > SHOWN_BAD_VALUE_CHARS:
            shown = shown[:SHOWN_BAD_VALUE_CHARS] + "..."
        raise ValueError("expected_sha512 is not a SHA-512 (%d hex digits, with or without the prefix %r): %r"
                         % (HEX_DIGITS, HASH_PREFIX, shown))
    return text


def hashes_of_file(path):
    """(SHA-512, SHA-256) of a file as lower-case hex, read once in blocks."""
    sha512 = hashlib.sha512()
    sha256 = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(READ_BLOCK_BYTES), b""):
            sha512.update(block)
            sha256.update(block)
    return sha512.hexdigest(), sha256.hexdigest()


class Sha512ChecksumVerifier(Processor):
    description = __doc__
    input_variables = {
        "pathname": {"required": True, "description": "Path to the downloaded file."},
        "expected_sha512": {
            "required": True,
            "description": "The SHA-512 that the publisher gives: 128 hex digits, any letter case, "
                           "with or without the prefix 'sha512:'.",
        },
    }
    output_variables = {
        "checksum_verified": {"description": "True when the file has the expected SHA-512."},
        "checksum_sha256": {"description": "The SHA-256 of the file (lower-case hex)."},
    }

    def main(self):
        try:
            expected = normalize_expected_sha512(self.env.get("expected_sha512"))
        except ValueError as err:
            raise ProcessorError(str(err))
        path = self.env.get("pathname")
        if not path or not os.path.isfile(path):
            raise ProcessorError("pathname is not a file: %r" % (path,))
        try:
            actual512, actual256 = hashes_of_file(path)
        except OSError as err:
            raise ProcessorError("Could not read %s: %s" % (path, err))
        if actual512 != expected:
            raise ProcessorError("SHA-512 mismatch for %s: expected %s, got %s"
                                 % (os.path.basename(path), shorten(expected), shorten(actual512)))
        self.env["checksum_verified"] = True
        self.env["checksum_sha256"] = actual256
        self.output("SHA-512 verified: %s" % shorten(actual512))


if __name__ == "__main__":
    processor = Sha512ChecksumVerifier()
    processor.execute_shell()
