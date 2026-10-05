"""The repository is public. These tests look at every file of this folder
for what must never be in it, and check the stub recipe. The patterns are those of
../../Win-SharedProcessors/tests/test_public_repository.py."""
import os
import plistlib
import re
import unittest

from _pcman_support import PROCESSOR_DIR

import test_public_repository as shared_hygiene

IDENTIFIER_PREFIX = "com.github.serrc-techops"
FORBIDDEN_PATTERNS = shared_hygiene.FORBIDDEN_PATTERNS
# This file names the patterns, so it is not scanned.
NOT_SCANNED = {"test_pcman_public_repository.py"}


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
        with open(os.path.join(PROCESSOR_DIR, "PcmanProcessors.recipe"), "rb") as handle:
            recipe = plistlib.load(handle)
        self.assertEqual(recipe["Identifier"], IDENTIFIER_PREFIX + ".PcmanProcessors")
        self.assertEqual(recipe["Process"], [])
        self.assertEqual(recipe["Input"], {})
        self.assertTrue(recipe["MinimumVersion"])

    def test_the_stub_says_that_the_package_tool_is_not_in_this_repository(self):
        with open(os.path.join(PROCESSOR_DIR, "PcmanProcessors.recipe"), "rb") as handle:
            description = plistlib.load(handle)["Description"]
        self.assertIn("it needs that tool, which is not part of this repository", description)
        self.assertIn("com.github.serrc-techops.SharedProcessors/CimianImporter", description)

    def test_the_folder_holds_only_what_is_expected(self):
        names = sorted(os.path.relpath(path, PROCESSOR_DIR) for path in folder_files())
        self.assertEqual(names, sorted([
            "PcmanImporter.py", "PcmanProcessors.recipe", "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "_pcman_support.py"),
            os.path.join("tests", "test_importer.py"), os.path.join("tests", "test_importer_real_tool.py"),
            os.path.join("tests", "test_pcman_readme.py"),
        ]))  # this file is not listed: it is not scanned

    def test_each_processor_file_has_a_class_of_the_same_name(self):
        for name in ("PcmanImporter",):
            with open(os.path.join(PROCESSOR_DIR, name + ".py"), "r", encoding="utf-8") as handle:
                self.assertIn("class %s(Processor):" % name, handle.read())


if __name__ == "__main__":
    unittest.main()
