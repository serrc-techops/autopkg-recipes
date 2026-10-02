"""The README must not teach what the rehearsal showed to be wrong."""
import os
import re
import unittest

from _win_support import PROCESSOR_DIR

README = os.path.join(PROCESSOR_DIR, "README.md")


def normalized_text():
    with open(README, "r", encoding="utf-8") as handle:
        return re.sub(r"\s+", " ", handle.read())


class ReadmeTests(unittest.TestCase):
    def test_every_make_override_command_names_an_override_folder(self):
        with open(README, "r", encoding="utf-8") as handle:
            raw = handle.read()
        commands = list(re.finditer(r"autopkg make-override([^`\n]*(?:\n[ \t]+--[^\n`]*)?)", raw))
        self.assertTrue(commands)
        for match in commands:
            self.assertIn("--override-dir=", match.group(1))

    def test_no_run_of_a_recipe_identifier(self):
        with open(README, "r", encoding="utf-8") as handle:
            raw = handle.read()
        for match in re.finditer(r"autopkg run([^`\n]*)", raw):
            self.assertNotIn("com.github.", match.group(1))

    def test_the_facts_of_the_rehearsal_are_there(self):
        text = normalized_text()
        for needle in ("--override-dir", "by path", "pcman catalogs", "Failed local trust verification",
                       "pcman_dry_run", "<false/>"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
