"""The repository is public. These tests look at every file of this folder
for what must never be in it, and check the stub recipe."""
import os
import plistlib
import re
import unittest

from _win_support import PROCESSOR_DIR

IDENTIFIER_PREFIX = "com.github.serrc-techops"
# Kinds of text that belong to one site, not to a public tool.
FORBIDDEN_PATTERNS = {
    "a user's home folder": re.compile(r"/Users/[A-Za-z]"),
    "a mounted share": re.compile(r"/Volumes/"),
    "a temporary session folder": re.compile(r"/private/tmp|scratchpad"),
    "a UNC path": re.compile(r"\\\\[A-Za-z0-9]"),
    "an IPv4 address": re.compile(r"\b(?!127\.0\.0\.1\b)(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"),
    "a key or a token": re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9+/]{16,}"),
}
# This file names the patterns, so it is not scanned.
NOT_SCANNED = {"test_public_repository.py"}


def folder_files():
    for folder, dirs, files in os.walk(PROCESSOR_DIR):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if name.endswith(".pyc") or name in NOT_SCANNED:
                continue
            yield os.path.join(folder, name)


class PublicRepositoryTests(unittest.TestCase):
    def test_no_file_holds_a_value_that_belongs_to_one_site(self):
        for path in folder_files():
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            for kind, pattern in FORBIDDEN_PATTERNS.items():
                with self.subTest(file=os.path.relpath(path, PROCESSOR_DIR), kind=kind):
                    self.assertIsNone(pattern.search(text))

    def test_nothing_sits_deeper_than_the_tests_folder(self):
        for path in folder_files():
            depth = len(os.path.relpath(path, PROCESSOR_DIR).split(os.sep))
            self.assertLessEqual(depth, 2, path)

    def test_the_stub_recipe_carries_only_an_identifier(self):
        with open(os.path.join(PROCESSOR_DIR, "SharedProcessors.recipe"), "rb") as handle:
            recipe = plistlib.load(handle)
        self.assertEqual(recipe["Identifier"], IDENTIFIER_PREFIX + ".SharedProcessors")
        self.assertEqual(recipe["Process"], [])
        self.assertEqual(recipe["Input"], {})
        self.assertTrue(recipe["MinimumVersion"])

    def test_each_processor_file_has_a_class_of_the_same_name(self):
        for name in ("PcmanImporter", "ChecksumVerifier", "GitHubAssetDigest"):
            with open(os.path.join(PROCESSOR_DIR, name + ".py"), "r", encoding="utf-8") as handle:
                self.assertIn("class %s(Processor):" % name, handle.read())


if __name__ == "__main__":
    unittest.main()
