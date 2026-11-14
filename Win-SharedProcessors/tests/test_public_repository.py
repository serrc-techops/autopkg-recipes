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

    def test_the_stub_says_that_no_other_tool_is_needed(self):
        with open(os.path.join(PROCESSOR_DIR, "SharedProcessors.recipe"), "rb") as handle:
            description = plistlib.load(handle)["Description"]
        self.assertIn("None of them needs the package tool or any other tool", description)
        self.assertIn("they work with any Cimian repository", description)
        for name in ("CimianImporter", "ChecksumVerifier", "GitHubAssetDigest", "GitHubNewestReleaseGuard",
                     "WindowsExeVersion", "VersionFromName"):
            self.assertIn("/" + name if name != "CimianImporter" else "SharedProcessors/" + name, description)
        self.assertNotIn("PcmanImporter", description)

    def test_no_processor_of_this_folder_needs_the_package_tool(self):
        """The processors are the files that end in .py beside the README: none names the
        package tool or imports a module that is not part of AutoPkg or of this folder."""
        for name in sorted(os.listdir(PROCESSOR_DIR)):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(PROCESSOR_DIR, name), "r", encoding="utf-8") as handle:
                text = handle.read().lower()
            with self.subTest(processor=name):
                self.assertNotIn("pcman", text)
                self.assertNotIn("package tool", text)

    def test_the_readme_names_the_package_tool_only_to_point_at_its_folder(self):
        with open(os.path.join(PROCESSOR_DIR, "README.md"), "r", encoding="utf-8") as handle:
            lines = [line for line in handle.read().splitlines() if "pcman" in line.lower()]
        self.assertEqual(len(lines), 2)
        self.assertTrue(any("Win-PcmanProcessors" in line or "owner's own package tool" in line for line in lines))

    def test_the_folder_holds_only_what_is_expected(self):
        names = sorted(os.path.relpath(path, PROCESSOR_DIR) for path in folder_files())
        expected = [
            "ChecksumVerifier.py", "CimianImporter.py", "GitHubAssetDigest.py", "GitHubNewestReleaseGuard.py",
            "README.md", "SharedProcessors.recipe", "VersionFromName.py", "WindowsExeVersion.py",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "_win_support.py"),
            os.path.join("tests", "test_checksum.py"), os.path.join("tests", "test_cimian_importer.py"),
            os.path.join("tests", "test_digest.py"), os.path.join("tests", "test_exe_version.py"),
            os.path.join("tests", "test_newest_release.py"),
            os.path.join("tests", "test_readme.py"), os.path.join("tests", "test_version_name.py"),
            "MicrosoftStorePackageDownloader.py", "microsoft-root-2011.pem",
            os.path.join("tests", "test_store_downloader.py"),
        ]  # this file is not listed: it is not scanned
        self.assertEqual(names, sorted(expected))

    def test_each_processor_file_has_a_class_of_the_same_name(self):
        for name in ("CimianImporter", "ChecksumVerifier", "GitHubAssetDigest", "GitHubNewestReleaseGuard",
                     "WindowsExeVersion", "VersionFromName"):
            with open(os.path.join(PROCESSOR_DIR, name + ".py"), "r", encoding="utf-8") as handle:
                self.assertIn("class %s(Processor):" % name, handle.read())


if __name__ == "__main__":
    unittest.main()
