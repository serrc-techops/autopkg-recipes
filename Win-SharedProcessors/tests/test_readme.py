"""The README must not teach what the rehearsal showed to be wrong, and must say what the
code does."""
import os
import re
import unittest

from _win_support import PROCESSOR_DIR, cimian

README = os.path.join(PROCESSOR_DIR, "README.md")


def raw_text():
    with open(README, "r", encoding="utf-8") as handle:
        return handle.read()


def normalized_text():
    return re.sub(r"\s+", " ", raw_text())


class ReadmeTests(unittest.TestCase):
    def test_every_make_override_command_names_an_override_folder(self):
        raw = raw_text()
        commands = list(re.finditer(r"autopkg make-override([^`\n]*(?:\n[ \t]+--[^\n`]*)?)", raw))
        self.assertTrue(commands)
        for match in commands:
            self.assertIn("--override-dir=", match.group(1))

    def test_no_run_of_a_recipe_identifier(self):
        raw = raw_text()
        for match in re.finditer(r"autopkg run([^`\n]*)", raw):
            self.assertNotIn("com.github.", match.group(1))

    def test_every_operator_command_names_the_override_dir(self):
        """An override outside AutoPkg's configured override folders loses its trust
        check unless --override-dir is on the command line (AutoPkg 2.9.0)."""
        raw = raw_text()
        commands = list(re.finditer(r"autopkg (run|verify-trust-info|update-trust-info)\b([^`]*)`", raw, re.S))
        self.assertGreaterEqual(len(commands), 3)
        for match in commands:
            with self.subTest(command=match.group(0)[:50]):
                if "--override-dir=" not in match.group(0):
                    # the sentence that only names the commands, and the "-k" warning
                    self.assertNotIn("<", match.group(2))

    def test_a_command_line_of_autopkg_at_the_start_of_a_line_has_the_option_at_any_indent(self):
        """An operator's command in a code block, indented or not."""
        raw = raw_text()
        pattern = r"^[ \t]*autopkg (?:run|verify-trust-info|update-trust-info|make-override)\b[^\n]*"
        for match in re.finditer(pattern, raw, re.M):
            with self.subTest(line=match.group(0)[:50]):
                self.assertIn("--override-dir=", match.group(0) + raw[match.end():match.end() + 80].split("\n\n")[0])

    def test_the_unverified_download_rule_is_documented(self):
        text = normalized_text()
        for needle in ("cimian_allow_unverified", "checksum_verified", "checksum_sha256",
                       "published WITHOUT a verified download", "published, NOT verified",
                       "dry run, nothing written, NOT verified", "`checksum_verified` is a boolean `true`"):
            self.assertIn(needle, text)

    def test_the_guard_ties_the_download_to_the_file_that_is_imported(self):
        text = normalized_text()
        for needle in ("is a SHA-256 that equals the hash of the file about to be imported",
                       "hashes that file itself, once",
                       "A checksum for another file stops the run",
                       "also in a dry run, and `cimian_allow_unverified` does not override it",
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
        refusal = (
            "The download was not verified: %s. Nothing was published. Publish by hand after "
            "checking the file, or set cimian_allow_unverified to true in the override."
            % cimian.UNVERIFIED_REASON
        )
        self.assertIn(refusal, normalized_text())

    def test_the_readme_states_no_hash(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", raw_text()))

    def test_the_facts_of_the_rehearsal_are_there(self):
        text = normalized_text()
        for needle in ("--override-dir", "by path", "makecatalogs", "Failed local trust verification",
                       "cimian_dry_run", "<false/>"):
            self.assertIn(needle, text)

    def test_every_input_and_every_output_of_the_importer_is_documented_with_its_default(self):
        raw = raw_text()
        inputs = raw[raw.index("### Inputs"):raw.index("### Outputs")]
        outputs = raw[raw.index("### Outputs"):raw.index("### What is written with PyYAML")]
        for name, flags in cimian.CimianImporter.input_variables.items():
            with self.subTest(input=name):
                row = [line for line in inputs.splitlines() if line.startswith("| `%s` |" % name)]
                self.assertEqual(len(row), 1)
                cells = [cell.strip() for cell in row[0].strip("|").split("|")]
                expected = "yes" if flags["required"] else ("`.exe` only" if name == "version" else "no")
                self.assertEqual(cells[1], expected)
        for name in cimian.CimianImporter.output_variables:
            with self.subTest(output=name):
                self.assertEqual(len([line for line in outputs.splitlines() if line.startswith("| `%s` |" % name)]), 1)

    def test_the_defaults_in_the_readme_are_the_defaults_of_the_code(self):
        raw = raw_text()
        inputs = raw[raw.index("### Inputs"):raw.index("### Outputs")]
        variables = cimian.CimianImporter.input_variables

        def row(name):
            return [line for line in inputs.splitlines() if line.startswith("| `%s` |" % name)][0]

        self.assertIn("| `true` |", row("cimian_dry_run"))
        self.assertIn("| `false` |", row("cimian_allow_unverified"))
        self.assertIn("| `Development` |", row("cimian_catalogs"))
        self.assertEqual(variables["cimian_catalogs"]["default"], ["Development"])
        self.assertIn("| `%s` |" % variables["cimian_path"]["default"], row("cimian_path"))
        self.assertIn("a time limit of %d seconds" % cimian.MSIINFO_TIMEOUT_SECONDS, normalized_text())
        self.assertIn("cut at %d lines of at most %d characters" % (cimian.MAX_LINES_SHOWN, cimian.MAX_LINE_CHARS),
                      normalized_text())
        self.assertIn("`" + cimian.REPO_PREFERENCE + "`", normalized_text())

    def test_the_readme_names_every_key_that_the_template_changes_and_the_two_it_drops(self):
        text = normalized_text()
        for needle in ("`version`", "`installer.location`", "`installer.hash`", "`installer.size`",
                       "`installer.type`", "`product_code`", "`upgrade_code`", "`check.file.version`",
                       "`check.registry.version`", "`check.file.hash`", "`md5checksum`",
                       "`force_install_after_date`", "**dropped**", "every other key"):
            self.assertIn(needle, text)
        for key in cimian.NOT_CARRIED_KEYS:
            self.assertIn("`%s`" % key, text)

    def test_the_readme_says_what_the_importer_does_not_do(self):
        text = normalized_text()
        self.assertIn("It does **not build catalogs**", text)
        self.assertIn("Run `makecatalogs` (Cimian's tool) after a publish", text)
        self.assertIn("**This processor does not parse an MSI itself.**", text)
        self.assertIn("**A person should then complete by hand**", text)
        self.assertIn("Nothing here has run with AutoPkg, with a real Cimian repository or with a real `msiinfo`", text)
        self.assertIn("NOT established", text)

    def test_the_nothing_new_and_dry_run_rules_are_documented(self):
        text = normalized_text()
        for needle in ("**The same version, or the same installer file, is in the repository: nothing is written, "
                       "and it is not an error.**",
                       "A dry run **writes nothing**", "`WARNING: DRY RUN.`", "dry run, nothing written",
                       "A dry run refuses what a real run refuses"):
            self.assertIn(needle, text)

    def test_the_readme_gives_the_version_of_the_source_that_its_lines_come_from(self):
        text = normalized_text()
        self.assertIn("`windowsadmins/cimian` at commit `e10498b`", text)
        self.assertIn("AutoPkg 2.9.0", text)
        self.assertIn("A behaviour that no line is given for is a decision of this repository", text)

    def test_the_readme_says_what_the_input_pkginfo_does_with_a_template(self):
        text = normalized_text()
        for needle in ("**With a template it does not change what the template has.**",
                       "A key that the template **lacks** is added, with a NOTE",
                       "keeps the template's value, with a NOTE that names the key",
                       "With **`cimian_pkginfo_wins` set to true** in the override",
                       "A dry run prints the same notes as a real run",
                       "does not add another"):
            self.assertIn(needle, text)
        self.assertIn("The input `pkginfo` does not change them", text)
        self.assertIn("every key it would have changed is named in a NOTE", text)
        self.assertNotIn("A dictionary merged over the pkginfo that was made", text)

    def test_the_readme_says_which_checks_stop_the_run_after_a_hash_is_dropped(self):
        text = normalized_text()
        for needle in ("**A dropped hash must not leave a check that cannot work.**",
                       "the item would never be updated: the run stops and names the entry",
                       "the item would install again at every run: the run stops",
                       "For a file that ends in `.exe` or `.dll` it only warns"):
            self.assertIn(needle, text)

    def test_the_readme_says_how_the_msi_entries_the_uninstaller_and_the_upgrade_code_are_treated(self):
        text = normalized_text()
        for needle in ("**Which MSI entry is this product's.**", "`uninstaller[].product_code` of type `msi`",
                       "is **refused**", "`cimian_allow_product_change`", "a prerequisite"):
            self.assertIn(needle, text)

    def test_the_readme_says_how_several_architectures_are_handled(self):
        text = normalized_text()
        for needle in ("`cimian_architecture`", "`CatalogService.cs:43-56`", "`amd64` and `x86_64` are `x64`",
                       "never overwritten: the run says whose it is"):
            self.assertIn(needle, text)

    def test_the_readme_says_the_msi_recipes_need_msiinfo_and_why(self):
        text = normalized_text()
        self.assertIn("**An argument of a recipe's step wins over an override's `Input`**", text)
        self.assertIn("for those recipes `msiinfo` is required", text)

    def test_the_readme_names_the_one_condition_of_never_overwrites(self):
        text = normalized_text()
        self.assertIn("two runs of one item at the same moment could both pass the check", text)

    def test_the_readme_says_the_result_line_is_never_cut(self):
        self.assertIn("are printed first and are never cut", normalized_text())

    def test_the_readme_says_that_a_leading_slash_of_a_templates_location_is_dropped(self):
        self.assertIn("its leading slashes or backslashes are dropped first", normalized_text())

    def test_the_readme_teaches_a_remedy_that_gives_the_real_version(self):
        text = normalized_text()
        self.assertNotIn('check: {file: {version: "%version%"}}', text)
        for needle in ("**How to end the stop:** add `version:`, with the template's own version, to that check in the "
                       "template's pkginfo in the repository",
                       "or give a literal version in the input `pkginfo`",
                       "**A version the client cannot read is refused.**",
                       "**Variables in the input `pkginfo`.**",
                       "AutoPkg replaces the `%name%` variables of a recipe's `Input` once, before the first step runs",
                       "so `%version%`, which a download step sets, reaches the importer as the text `%version%`",
                       "A `%name%` that remains is a name that nothing sets: the run stops before anything is written",
                       "Windows environment variables such as `%ProgramFiles%` and `%TEMP%`"):
            self.assertIn(needle, text)

    def test_the_readme_says_which_check_the_client_uses_and_that_the_stop_follows_it(self):
        text = normalized_text()
        self.assertIn("**but only when the client will use that check**", text)
        self.assertIn("`StatusService.cs:117-186`", text)

    def test_the_readme_says_how_an_all_template_and_a_history_of_all_then_one_are_treated(self):
        text = normalized_text()
        for needle in ("When the template is for all architectures (no list) and another file of the item names one, the new version is written for the given architecture only",
                       "Files for all architectures and files for **one** named architecture need no input",
                       "\"Nothing new\" by the installer's hash is decided among the files for the given architecture too"):
            self.assertIn(needle, text)

    def test_the_readme_says_that_no_upgrade_code_counts_as_a_change(self):
        self.assertIn("or that has none where the template's item had one, is **refused**", normalized_text())

    def test_the_readme_names_the_boolean_and_null_spellings_of_the_core_schema(self):
        self.assertIn("`true`, `True`, `TRUE`, `false`, `False`, `FALSE`; `null`, `Null`, `NULL`, `~`", normalized_text())

    def test_the_readme_names_no_input_of_the_package_tool(self):
        for word in ("pcman_", "PcmanImporter", "--template"):
            self.assertNotIn(word, raw_text())


if __name__ == "__main__":
    unittest.main()
