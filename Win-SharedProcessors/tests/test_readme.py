"""The README must not teach what the rehearsal showed to be wrong, and must say what the
code does."""
import os
import re
import unittest

from _win_support import PROCESSOR_DIR, cimian, newest_release

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
        self.assertIn("Until 2026-10-04 nothing here had run with AutoPkg, with a real Cimian repository or with a real `msiinfo`", text)
        self.assertNotIn("Nothing here has run with AutoPkg", text)
        self.assertIn("NOT established", text)

    def test_the_readme_says_what_happens_when_a_vendor_renames_a_file_and_what_the_operator_compares(self):
        text = normalized_text()
        start = text.index("## When a vendor renames a file")
        section = text[start:text.index("## An example: the last steps of a recipe")]
        for needle in ("the **first release, newest first and a pre-release skipped, that has a file whose name matches the pattern**",
                       "`GitHubReleasesInfoProvider.py`, `select_asset` and `main`",
                       "the provider does not stop and says nothing: it goes on to the next older release whose file matches",
                       "If that older release has a digest, the digest and checksum steps pass; the label is the old file's",
                       "the importer finds that version in the repository and says `Nothing new`",
                       "it stops only when no release of the whole list matches",
                       "(they took files of January 2026, October 2024 and December 2020",
                       "The eight download recipes that use the provider now have a **guard**: the step `GitHubNewestReleaseGuard`",
                       "stops the run when the release that the provider selected is not the newest release that is not a pre-release",
                       "names the files of the newest release, so that the new spelling is in the message",
                       "is accepted by its tag in the override's `Input` key `accepted_newest_release`, and the run goes on only while that release is the newest",
                       "The guard is new and has not run under AutoPkg",
                       "the release that Angry IP Scanner, Bambu Studio, PDFsam, XCP-ng Center, osquery, Greenshot, 7-Zip and OpenSSH take is the newest release that is not a pre-release",
                       "for 7-Zip and OpenSSH this is a new reading",
                       "**What the operator still compares in a dry run** (run it with `-v`)",
                       "`Selected asset ... from release ...` against the vendor's releases page",
                       "The guard compares the release, not the file",
                       "A run that ends in `Nothing new` is not proof that the newest release was taken"):
            self.assertIn(needle, section)
        for old in ("no guard", "none is built", "only their dry runs are known"):
            self.assertNotIn(old, section)
        self.assertLess(text.index("## VersionFromName"), start)
        self.assertLess(text.index("## GitHubNewestReleaseGuard"), text.index("## VersionFromName"))

    def test_the_readme_describes_the_newest_release_guard(self):
        raw = raw_text()
        text = normalized_text()
        self.assertIn("Seven AutoPkg processors", text)
        self.assertIn("| `GitHubNewestReleaseGuard.py` | Stops the recipe when the release that `GitHubReleasesInfoProvider` selected is not the newest one", text)
        section = text[text.index("## GitHubNewestReleaseGuard"):text.index("## WindowsExeVersion")]
        for needle in ("`GitHubReleasesInfoProvider.py:173-201`", "(`:204-205`)", "(`:235-255`)", "(`:244-248`)",
                       "ends with the asset's number (`:238`)",
                       "The record of an asset has no key that names its release",
                       "reads the owner, the repository and the asset's number from `asset_url`",
                       "**The rule for the newest release.**", "A release **without files counts**",
                       "**The guard compares positions in the list, not versions.**",
                       "has a tag that matches it",
                       "the next page is read, up to three pages",
                       "**Two lines of releases side by side.**",
                       "a recipe that follows one line says so explicitly**: the override's `release_tag_pattern`",
                       "matched from the start of the tag (`re.match`, like the provider matches `asset_regex`)",
                       "a guard without a pattern passes it unseen",
                       "the guard stopped it whenever a 1.3 release was on top, from 2026-01-05 until 2026-10-02",
                       "**A newest release that has no installer on purpose.**",
                       "names its **tag**, as text",
                       "**only while that release is the newest**",
                       "in every run, not only with `-v`, in one line",
                       "An older release is taken on purpose: the newest release of <owner>/<repo>, '<tag>', has <n> file(s)",
                       "the tag no longer matches and the run stops again, naming the new release and its files",
                       "A tag that is set but not needed",
                       "a tag with another character gets no command",
                       "replaces a switch of the first version, `allow_older_release`, which turned the whole check off",
                       "**The provider's `sort_by_highest_tag_names` and `latest_only` are refused.**",
                       "a recipe that sets either input stops with a message that says so, whatever else is set, before anything is asked",
                       "`:222-225`", "`:148-149`", "`:214-232`",
                       "`'<tag>' (titled '<title>')`", "`whose tag matches '<pattern>'`",
                       "is **not in the list that was read**", "`cache-control: public, max-age=60`", "which was not established",
                       "it does not exist or is not public",
                       "numbers double (30, and 46 without a token)",
                       "**The output.** The processor has one output variable, `github_newest_release_guard_summary_result`",
                       "AutoPkg collects every variable whose name ends in `_summary_result`",
                       "`summary_text`, `report_fields` (`repository`, `newest_release`, `release_taken`, `reason`)",
                       "no secret, no path", "The variable is cleared at the start of each run of the processor",
                       "**An acceptance is offered, and honoured, only for a release without a Windows installer file**",
                       "`INSTALLER_EXTENSIONS`", "stops passing when an installer file is added to that release later",
                       "does not cover **a rename below it**",
                       "Two releases without an installer in a row are accepted with the tag of the newest one",
                       "and the selected release is not listed above the newest",
                       "**A pattern hides the releases it leaves out, so it says which ones, in every run, not only with `-v`**",
                       "passed the run in silence; now the line names the newer releases it left out",
                       "**the releases between the newest and the selected one, with their files**",
                       "only when none of those releases has a Windows installer file, accept the newest release by its tag",
                       "a backtick is shown as a single quote",
                       "**The message of a stop**", "correct `SEARCH_PATTERN`",
                       "**The request.**", "reads no token file, no preference and no environment variable",
                       "A redirect is not followed", "A 404 names the repository",
                       "`X-RateLimit-Remaining: 0`", "said as GitHub's limit for anonymous requests",
                       "**Requests of a run, and GitHub's limit.**", "60 an hour for one address",
                       "**8 anonymous requests with the guard and 7 with `GitHubAssetDigest`**",
                       "15 anonymous requests", "23 in all", "that is not built"):
            self.assertIn(needle, section)
        guard = newest_release
        self.assertIn("a time limit of %d seconds" % guard.FETCH_TIMEOUT_SECONDS, section)
        self.assertIn("read up to %d MiB" % (guard.MAX_RESPONSE_BYTES // (1024 * 1024)), section)
        self.assertIn("?per_page=%d&page=1" % guard.RELEASES_PER_PAGE, section)
        self.assertIn("a whole page of thirty releases", section)
        self.assertEqual(guard.RELEASES_PER_PAGE, 30)
        self.assertEqual(guard.MAX_PAGES, 3)
        self.assertIn("all its files up to thirty", section)
        self.assertEqual(guard.MAX_ASSET_NAMES_SHOWN, 30)
        self.assertIn("cut at %d characters" % guard.MAX_SHOWN_CHARACTERS, section)
        # every input has a row, with `yes` for a required one and the default where there is one
        rows = [line for line in raw[raw.index("## GitHubNewestReleaseGuard"):raw.index("## WindowsExeVersion")].splitlines()
                if line.startswith("| `")]
        for name, flags in guard.GitHubNewestReleaseGuard.input_variables.items():
            with self.subTest(input=name):
                row = [line for line in rows if line.startswith("| `%s` |" % name)]
                self.assertEqual(len(row), 1)
                cells = [cell.strip() for cell in row[0].strip("|").split("|")]
                if flags.get("required"):
                    self.assertEqual(cells[1], "yes")
                elif flags.get("default") == "":
                    self.assertEqual(cells[1], "no (default empty)")
                elif "default" in flags:
                    self.assertEqual(cells[1], "no (default `%s`)" % str(flags["default"]).lower())
                else:
                    self.assertEqual(cells[1], "no")
        # the README names the keys of an asset record as they were read on 2026-10-04
        keys = ("browser_download_url", "content_type", "created_at", "digest", "download_count", "id", "label",
                "name", "node_id", "size", "state", "updated_at", "uploader", "url")
        for key in keys:
            self.assertIn("`%s`" % key, section)

    def test_the_pass_line_and_the_release_label_of_the_readme_are_what_the_code_prints(self):
        text = normalized_text()
        guard = newest_release
        line = "The selected release '<tag>' of <owner>/<repo> is the newest release that is not a pre-release."
        self.assertEqual(guard.pass_message("<owner>", "<repo>", {"tag_name": "<tag>"}, False), line)
        self.assertIn("`" + line + "`", text)
        self.assertEqual(guard.release_label({"tag_name": "<tag>", "name": "<title>"}), "'<tag>' (titled '<title>')")
        self.assertEqual(guard.release_label({"tag_name": "<tag>", "name": "<tag>"}), "'<tag>'")
        self.assertIn("`'<tag>' (titled '<title>')`", text)
        pattern = guard.parse_tag_pattern("<pattern>")
        self.assertTrue(guard.pass_message("o", "r", {"tag_name": "t"}, False, pattern).endswith(" whose tag matches '<pattern>'."))

    def test_the_readme_names_the_installer_extensions_and_the_skipped_line_of_the_code(self):
        text = normalized_text()
        guard = newest_release
        for extension in guard.INSTALLER_EXTENSIONS:
            self.assertIn("`%s`" % extension, text)
        self.assertIn("a file whose name ends in `.msi`, `.exe` or `.msix`", text)
        pattern = guard.parse_tag_pattern("<pattern>")
        line = guard.skipped_message("<owner>", "<repo>", pattern, [{"tag_name": "<tag>"}])
        self.assertTrue(line.startswith("release_tag_pattern '<pattern>' left out 1 newer release of <owner>/<repo>: '<tag>'. "))
        ending = "If one of them carries the installer that this recipe should take, the pattern hides a rename."
        self.assertTrue(line.endswith(ending))
        self.assertIn("release_tag_pattern '<pattern>' left out <n> newer release(s) of <owner>/<repo>: '<tag>', ...", text)
        self.assertIn(ending, text)
        self.assertEqual(guard.MAX_SKIPPED_TAGS_SHOWN, 5)
        self.assertIn("at most five tags are named, then how many more", text)
        self.assertEqual(guard.MAX_BETWEEN_SHOWN, 5)
        self.assertIn("(up to five;", text)

    def test_the_accepted_line_of_the_readme_is_the_start_of_what_the_code_prints(self):
        text = normalized_text()
        guard = newest_release
        newest = {"tag_name": "<tag>", "assets": [{"name": "<names>"}]}
        shown = guard.accepted_message("<owner>", "<repo>", newest, [newest], 1, None)
        start = "An older release is taken on purpose: the newest release of <owner>/<repo>, '<tag>', has 1 file (<names>) and"
        self.assertTrue(shown.startswith(start))
        self.assertIn("An older release is taken on purpose: the newest release of <owner>/<repo>, '<tag>', has <n> file(s) (<names>) and", text)

    def test_the_readme_example_has_the_guard_right_after_the_provider(self):
        raw = raw_text()
        example = raw[raw.index("## An example: the last steps of a recipe"):raw.index("## Switching on a real run")]
        order = [name for name in re.findall(r"<key>Processor</key>\n\s*<string>([^<]*)</string>", example)]
        self.assertEqual(order[:3], ["GitHubReleasesInfoProvider",
                                     "com.github.serrc-techops.SharedProcessors/GitHubNewestReleaseGuard",
                                     "URLDownloader"])

    def test_the_readme_names_the_three_part_label_rules_of_the_client(self):
        text = normalized_text()
        start = text.index("**Three-part labels.**")
        paragraph = text[start:text.index("## When a vendor renames a file")]
        for needle in ("`CatalogService.ExpandBuildTimestamp`", "exactly three parts, `yy.M.ddHH`",
                       "the first part from 20 to 99, a month from 1 to 12 and a third part of three or four digits",
                       "`VersionService.TryParseCalendarBuildStamp`", "accepts such a label", "does not warn about it",
                       "A label of four parts", "meets neither rule"):
            self.assertIn(needle, paragraph)
        self.assertIn("for the three programs whose template was an MSI or an EXE item. The ten programs whose item was a Chocolatey `nopkg` item were refused, as designed",
                      text)
        self.assertNotIn("ended in `Nothing new` for the programs that had a template", text)

    def test_the_readme_gives_the_measured_result_against_the_package_tool(self):
        text = normalized_text()
        start = text.index("### Measured against the package tool (2026-10-04)")
        section = text[start:text.index("### Not established")]
        for needle in ("on scratch copies of a repository (never on the share)", "run for real under AutoPkg 2.9.0",
                       "an MSI program, an EXE program and one more MSI program",
                       "**With a template, the importer's pkginfo was byte for byte the package tool's** for each of the three",
                       "`diff` found nothing", "the keys, their values and their order were equal",
                       "**Without a template**", "it lands in the catalog `Development`",
                       "the catalog `Production` (a PC that reads `Production` does not see the version at all)",
                       "`supported_architectures`", "`unattended_install` and `unattended_uninstall`",
                       "the installer's arguments and the install check of an EXE",
                       "`category`, `description` and `icon_name`",
                       "`developer` where the recipe's `pkginfo` does not give it",
                       "That is what a person completes by hand",
                       "One of the three runs needed `cimian_allow_unverified`", "set in the scratch override only"):
            self.assertIn(needle, section)
        self.assertEqual(section.count("byte for byte"), 1)
        self.assertNotIn("Chrome", section)
        self.assertNotIn("VLC", section)
        self.assertNotIn("Firefox", section)

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
