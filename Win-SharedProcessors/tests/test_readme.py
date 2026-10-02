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

    def test_every_operator_command_names_the_override_dir(self):
        """An override outside AutoPkg's configured override folders loses its trust
        check unless --override-dir is on the command line (AutoPkg 2.9.0)."""
        with open(README, "r", encoding="utf-8") as handle:
            raw = handle.read()
        commands = list(re.finditer(r"autopkg (run|verify-trust-info|update-trust-info)\b([^`]*)`", raw, re.S))
        self.assertGreaterEqual(len(commands), 3)
        for match in commands:
            with self.subTest(command=match.group(0)[:50]):
                if "--override-dir=" not in match.group(0):
                    # the sentence that only names the commands, and the "-k" warning
                    self.assertNotIn("<", match.group(2))

    def test_a_command_line_of_autopkg_at_the_start_of_a_line_has_the_option_at_any_indent(self):
        """An operator's command in a code block, indented or not."""
        with open(README, "r", encoding="utf-8") as handle:
            raw = handle.read()
        pattern = r"^[ \t]*autopkg (?:run|verify-trust-info|update-trust-info|make-override)\b[^\n]*"
        for match in re.finditer(pattern, raw, re.M):
            with self.subTest(line=match.group(0)[:50]):
                self.assertIn("--override-dir=", match.group(0) + raw[match.end():match.end() + 80].split("\n\n")[0])

    def test_the_unverified_download_rule_is_documented(self):
        text = normalized_text()
        for needle in ("pcman_allow_unverified", "checksum_verified", "checksum_sha256",
                       "published WITHOUT a verified download", "published, NOT verified",
                       "dry run, nothing written, NOT verified", "`checksum_verified` is a boolean `true`"):
            self.assertIn(needle, text)

    def test_the_guard_ties_the_download_to_the_file_that_is_imported(self):
        text = normalized_text()
        for needle in ("is a SHA-256 that equals the hash of the file about to be imported",
                       "hashes that file itself, once",
                       "A checksum for another file stops the run",
                       "also in a dry run, and `pcman_allow_unverified` does not override it",
                       "That is a pinned hash, chosen by whoever wrote the override, and the override's "
                       "trust information does not cover its `Input`",
                       "`signature_verified` does not count: no step sets it",
                       "A later signature step must output the hash of the file it checked under a named key",
                       "The download was not verified: no step of the recipe set checksum_verified together "
                       "with the checksum_sha256 of this file"):
            self.assertIn(needle, text)

    def test_the_readme_does_not_say_that_a_signature_flag_counts(self):
        text = normalized_text()
        self.assertNotIn("or `signature_verified`", text)
        self.assertNotIn("checksum_verified or signature_verified", text)
        self.assertEqual(text.count("signature_verified"), 1)

    def test_the_importer_message_is_the_one_in_the_readme(self):
        """The text of the refusal in the README is the real text."""
        import PcmanImporter
        text = normalized_text()
        refusal = "The download was not verified: %s. Nothing was published." % PcmanImporter.UNVERIFIED_REASON
        self.assertIn(refusal, text)

    def test_the_readme_states_no_hash(self):
        with open(README, "r", encoding="utf-8") as handle:
            self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", handle.read()))

    def test_the_facts_of_the_rehearsal_are_there(self):
        text = normalized_text()
        for needle in ("--override-dir", "by path", "pcman catalogs", "Failed local trust verification",
                       "pcman_dry_run", "<false/>"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
