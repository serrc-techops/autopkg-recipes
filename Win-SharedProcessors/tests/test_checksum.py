"""Tests of ChecksumVerifier: every branch."""
import hashlib
import os
import tempfile
import unittest

from _win_support import ProcessorError, checksum, new_processor, run_processor

VERIFIER = checksum.ChecksumVerifier


class ChecksumTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="win-shared-checksum-")
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "Example App-1.0.exe")
        with open(self.path, "wb") as handle:
            handle.write(b"example installer bytes")
        self.hex = hashlib.sha256(b"example installer bytes").hexdigest()

    def run_with(self, expected, path=None):
        return run_processor(VERIFIER, {"pathname": self.path if path is None else path, "expected_sha256": expected})

    def refused(self, expected, path=None):
        processor, _ = new_processor(
            VERIFIER, {"pathname": self.path if path is None else path, "expected_sha256": expected}
        )
        with self.assertRaises(ProcessorError) as caught:
            processor.main()
        self.assertNotIn("checksum_verified", processor.env)
        return str(caught.exception)

    def test_the_right_hash_passes_and_is_an_output(self):
        processor, messages = self.run_with(self.hex)
        self.assertIs(processor.env["checksum_verified"], True)
        self.assertEqual(processor.env["checksum_sha256"], self.hex)
        self.assertTrue(any(self.hex in m for m in messages))

    def test_letter_case_of_the_expected_value_does_not_matter(self):
        for value in (self.hex.upper(), self.hex[:10].upper() + self.hex[10:]):
            with self.subTest(value=value):
                self.run_with(value)

    def test_the_prefix_is_accepted_in_any_letter_case(self):
        for prefix in ("sha256:", "SHA256:", "Sha256:"):
            with self.subTest(prefix=prefix):
                self.run_with(prefix + self.hex)
                self.run_with(prefix + self.hex.upper())

    def test_white_space_after_the_prefix_is_ignored(self):
        self.run_with("sha256: " + self.hex)

    def test_white_space_around_the_value_is_ignored(self):
        self.run_with("  " + self.hex + "\n")

    def test_a_different_hash_is_an_error_that_shows_both_shortened(self):
        wrong = "0" * 64
        message = self.refused(wrong)
        self.assertIn("mismatch", message)
        self.assertIn(wrong[:8] + "...", message)
        self.assertIn(self.hex[:8], message)
        self.assertIn(self.hex[-8:], message)
        self.assertNotIn(self.hex, message)
        self.assertNotIn(wrong, message)

    def test_one_changed_digit_is_an_error(self):
        last = "0" if self.hex[-1] != "0" else "1"
        self.refused(self.hex[:-1] + last)

    def test_an_empty_expected_value_is_an_error(self):
        for value in ("", "   ", "\n", "sha256:", "SHA256:  "):
            with self.subTest(value=value):
                self.assertIn("empty", self.refused(value))
        self.assertIn("not text", self.refused(None))

    def test_a_value_that_is_not_a_sha256_is_an_error(self):
        bad = {
            "63 digits": self.hex[:-1],
            "65 digits": self.hex + "0",
            "not hex": "g" + self.hex[1:],
            "digest and file name": self.hex + "  Example App-1.0.exe",
            "md5": hashlib.md5(b"x").hexdigest(),
            "another algorithm": "sha1:" + hashlib.sha1(b"x").hexdigest(),
            "a number": 12345,
            "a word": "none",
        }
        for label, value in bad.items():
            with self.subTest(case=label):
                self.assertIn("is not a SHA-256" if label != "a number" else "not text", self.refused(value))

    def test_a_long_bad_value_is_shortened_in_the_message(self):
        message = self.refused("z" * 500)
        self.assertLess(len(message), 300)

    def test_a_missing_file_or_a_folder_is_an_error(self):
        self.refused(self.hex, path=os.path.join(self._tmp.name, "gone.exe"))
        self.refused(self.hex, path=self._tmp.name)
        self.refused(self.hex, path="")

    def test_an_unreadable_file_is_an_error(self):
        os.chmod(self.path, 0)
        try:
            if os.access(self.path, os.R_OK):
                self.skipTest("this account can read a file with mode 0")
            self.refused(self.hex)
        finally:
            os.chmod(self.path, 0o644)

    def test_a_file_of_several_blocks_is_hashed_whole(self):
        data = os.urandom(2 * checksum.READ_BLOCK_BYTES + 5)
        with open(self.path, "wb") as handle:
            handle.write(data)
        self.run_with(hashlib.sha256(data).hexdigest())
        self.refused(hashlib.sha256(data[: checksum.READ_BLOCK_BYTES]).hexdigest())

    def test_the_file_is_read_in_blocks_not_all_at_once(self):
        sizes = []
        real_open = open

        class Spy:
            def __init__(self, handle):
                self.handle = handle

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.handle.close()

            def read(self, size=-1):
                sizes.append(size)
                return self.handle.read(size)

        original = checksum.open if hasattr(checksum, "open") else None
        checksum.open = lambda path, mode="r": Spy(real_open(path, mode))
        try:
            self.run_with(self.hex)
        finally:
            if original is None:
                del checksum.open
            else:
                checksum.open = original
        self.assertTrue(sizes)
        self.assertTrue(all(size == checksum.READ_BLOCK_BYTES for size in sizes))

    def test_an_empty_file_has_the_hash_of_nothing(self):
        with open(self.path, "wb"):
            pass
        self.run_with(hashlib.sha256(b"").hexdigest())

    def test_the_declaration(self):
        self.assertTrue(VERIFIER.input_variables["pathname"]["required"])
        self.assertTrue(VERIFIER.input_variables["expected_sha256"]["required"])
        self.assertIn("checksum_verified", VERIFIER.output_variables)

    def test_the_normalizer_gives_lower_case_hex_only(self):
        self.assertEqual(checksum.normalize_expected_sha256("SHA256:" + "AB" * 32), "ab" * 32)
        with self.assertRaises(ValueError):
            checksum.normalize_expected_sha256("ab" * 31)

    def test_shorten_keeps_head_and_tail(self):
        self.assertEqual(checksum.shorten("abc"), "abc")
        shown = checksum.shorten("a" * 8 + "m" * 40 + "z" * 8)
        self.assertEqual(shown, "a" * 8 + "..." + "z" * 8)


if __name__ == "__main__":
    unittest.main()
