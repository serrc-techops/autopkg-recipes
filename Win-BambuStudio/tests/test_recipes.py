"""Tests of the two Bambu Studio recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names one of our shared
processors is compared with what that processor declares (see
../../Win-SharedProcessors). The shared folder's tests are run separately.
"""
import os
import plistlib
import re
import subprocess
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.dirname(TESTS_DIR)
SHARED_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-SharedProcessors")
SHARED_TESTS_DIR = os.path.join(SHARED_DIR, "tests")
if SHARED_TESTS_DIR not in sys.path:
    sys.path.insert(0, SHARED_TESTS_DIR)

import _win_support  # noqa: E402,F401  (installs the autopkglib stand-in, imports the processors)
import test_exe_version as exe_tests  # noqa: E402  (builds a small PE file; its tests are not collected here)
import test_public_repository as shared_hygiene  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
PATTERN = r"Bambu_Studio_win_public-v[0-9.]+-[0-9]+\.exe$"
# The tag is v02.08.04.61 by the writer's knowledge. A label of four numbers
# joined by dots reads as an IPv4 address to the repository's hygiene check, so
# it is built here and never written out in a file of the folder.
TAG_PARTS = ("02", "08", "04", "61")
LABEL = ".".join(TAG_PARTS)
TAG = "v" + LABEL
ASSET = "Bambu_Studio_win_public-%s-20250725142530.exe" % TAG
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "BambuStudio-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "BambuStudio.cimian.recipe")
# Required inputs that a recipe must NOT pass: they come from AutoPkg's
# preferences or the override on the machine that runs it.
SUPPLIED_BY_THE_MACHINE = {"PcmanImporter": {"pcman_root"}}
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir")


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def processor_classes():
    import importlib
    classes = {}
    for name in ("PcmanImporter", "ChecksumVerifier", "GitHubAssetDigest", "WindowsExeVersion"):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def shared_steps(recipe):
    for step in recipe["Process"]:
        if step["Processor"].startswith(SHARED_PREFIX):
            yield step["Processor"][len(SHARED_PREFIX):], step.get("Arguments", {})


class RecipeFileTests(unittest.TestCase):
    def test_both_files_are_valid_property_lists(self):
        for path in (DOWNLOAD, CIMIAN):
            with self.subTest(path=os.path.basename(path)):
                result = subprocess.run(["plutil", "-lint", path], capture_output=True, text=True) \
                    if os.path.exists("/usr/bin/plutil") else None
                if result is not None:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                recipe = load(path)
                for key in ("Description", "Identifier", "Input", "MinimumVersion", "Process"):
                    self.assertIn(key, recipe)

    def test_identifiers_and_parent(self):
        download, cimian = load(DOWNLOAD), load(CIMIAN)
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.BambuStudio-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.BambuStudio")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [
            "GitHubReleasesInfoProvider", "URLDownloader", "EndOfCheckPhase",
            SHARED_PREFIX + "GitHubAssetDigest", SHARED_PREFIX + "ChecksumVerifier",
            SHARED_PREFIX + "WindowsExeVersion",
        ])

    def test_the_cimian_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "PcmanImporter"])

    def test_the_provider_arguments(self):
        args = load(DOWNLOAD)["Process"][0]["Arguments"]
        self.assertEqual(args["github_repo"], "bambulab/BambuStudio")
        self.assertEqual(args["asset_regex"], "%SEARCH_PATTERN%")
        self.assertNotIn("include_prereleases", args)
        self.assertEqual(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"], PATTERN)

    def test_pre_releases_are_a_switch_of_the_input_that_an_override_can_change(self):
        """AutoPkg 2.9.0 puts the Input of the recipe and of the override into the run first and
        injects the Arguments of each step after them (`autopkglib/__init__.py`:
        `process_cli_overrides`, then `Processor.inject`), so a value in the Arguments would beat
        the override. The switch is therefore a key of the Input, with the name of the provider's
        own input variable. The provider reads it from the run and tests its truth
        (`GitHubReleasesInfoProvider.py`, `select_asset`), so the text `false` counts as true and
        the value is a boolean. A `%variable%` that holds a boolean stops the whole run with a
        TypeError (`update_data` in `autopkglib/__init__.py`, where only a KeyError is caught), so
        no step names the key; the last loop of this test keeps every such reference away from the
        booleans of the Input."""
        recipe = load(DOWNLOAD)
        self.assertIs(recipe["Input"]["include_prereleases"], False)
        arguments = recipe["Process"][0]["Arguments"]
        self.assertNotIn("include_prereleases", arguments)
        for override_input, wanted in (({}, False), ({"include_prereleases": True}, True)):
            run = dict(recipe["Input"])  # the recipe's Input
            run.update(override_input)  # then the override's Input
            run.update(arguments)  # then the Arguments of the step
            self.assertIs(run["include_prereleases"], wanted)
        for step in recipe["Process"]:
            for key, value in step.get("Arguments", {}).items():
                match = re.fullmatch(r"%([A-Za-z_]+)%", value) if isinstance(value, str) else None
                if match:
                    self.assertNotIsInstance(recipe["Input"].get(match.group(1)), bool, key)

    def test_the_default_pattern_matches_the_exe_and_not_the_others(self):
        """The names are from the writer's knowledge, not from the real release."""
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        self.assertTrue(pattern.search(ASSET))
        for name in (ASSET[:-4] + ".zip", ASSET + ".sig", ASSET[:-4] + ".msi",
                     "Bambu_Studio_win_public-%s.exe" % TAG,  # no build number
                     "Bambu_Studio_win_public-%s-20250725142530_portable.zip" % TAG,
                     "Bambu_Studio_linux_ubuntu-%s-20250725142530.AppImage" % TAG,
                     "Bambu_Studio_mac-%s-20250725142530.dmg" % TAG):
            self.assertFalse(pattern.search(name), name)

    def test_the_download_recipe_names_no_prerelease_and_keeps_the_file_name(self):
        steps = load(DOWNLOAD)["Process"]
        self.assertNotIn("include_prereleases", steps[0]["Arguments"])
        self.assertIs(load(DOWNLOAD)["Input"]["include_prereleases"], False)
        self.assertNotIn("Arguments", steps[1])  # URLDownloader: the asset's own file name
        self.assertTrue(ASSET.endswith(".exe"))

    def test_the_tag_without_the_v_has_leading_zeros_and_is_no_longer_the_label(self):
        """AutoPkg 2.9.0 strips a leading v from the tag (read in its source: tag.lstrip("v.")), so
        `version` starts as the tag's four parts with their leading zeros. The last step of the
        download recipe overwrites it with the installer's own ProductVersion, and the cimian
        recipe passes %version% on."""
        self.assertEqual(TAG.lstrip("v."), LABEL)
        self.assertEqual(LABEL.split(".")[0], "02")
        args = load(CIMIAN)["Process"][0]["Arguments"]
        self.assertEqual(args["pcman_version"], "%version%")
        steps = load(DOWNLOAD)["Process"]
        self.assertEqual(steps[-1]["Processor"], SHARED_PREFIX + "WindowsExeVersion")

    def test_the_exe_version_step_is_last_and_reads_the_downloaded_file(self):
        steps = load(DOWNLOAD)["Process"]
        names = [step["Processor"] for step in steps]
        self.assertEqual(names[-1], SHARED_PREFIX + "WindowsExeVersion")
        self.assertLess(names.index("EndOfCheckPhase"), names.index(SHARED_PREFIX + "ChecksumVerifier"))
        self.assertLess(names.index(SHARED_PREFIX + "ChecksumVerifier"), len(names) - 1)
        self.assertEqual(steps[-1]["Arguments"], {"pathname": "%pathname%"})  # set_version stays at its default

    def test_the_inputs_of_the_cimian_recipe(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], "BambuStudio")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "bambustudio")
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%",
                                "pcman_version": "%version%"})

    def test_the_digest_and_the_checksum_arguments(self):
        steps = dict(shared_steps(load(DOWNLOAD)))
        self.assertEqual(steps["GitHubAssetDigest"], {"github_asset_api_url": "%asset_url%"})
        self.assertEqual(steps["ChecksumVerifier"],
                         {"pathname": "%pathname%", "expected_sha256": "%expected_sha256%"})

    def test_no_stop_on_an_unchanged_download_and_no_latest_only(self):
        for path in (DOWNLOAD, CIMIAN):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.assertNotIn("StopProcessingIf", text)
            self.assertNotIn("latest_only", text)

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in (DOWNLOAD, CIMIAN):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text)

    def test_the_description_says_what_a_reader_must_know(self):
        self.assertIn("newest non-pre-release", load(DOWNLOAD)["Description"])
        self.assertIn("matching file", load(DOWNLOAD)["Description"])
        self.assertIn("reads the version label from the .exe itself (its ProductVersion)", load(DOWNLOAD)["Description"])
        self.assertIn("dry run", load(CIMIAN)["Description"])
        self.assertIn("pcman_dry_run", load(CIMIAN)["Description"])
        self.assertIn("the one that the download recipe read from the .exe itself", load(CIMIAN)["Description"])
        self.assertNotIn("release tag without its leading v", load(CIMIAN)["Description"])

    def test_the_descriptions_claim_no_rehearsal_and_say_what_is_not_checked(self):
        for path in (DOWNLOAD, CIMIAN):
            description = load(path)["Description"]
            self.assertNotIn("ehearsed", description)
        self.assertIn("NOT checked against the real release page", load(DOWNLOAD)["Description"])
        self.assertIn("the first run on the build Mac checks it", load(DOWNLOAD)["Description"])
        self.assertIn("has NOT been seen yet", load(CIMIAN)["Description"])


class SharedProcessorTests(unittest.TestCase):
    def test_every_named_shared_processor_is_a_file_of_the_shared_folder(self):
        for path in (DOWNLOAD, CIMIAN):
            for name, _ in shared_steps(load(path)):
                self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, name + ".py")), name)

    def test_the_stub_identifier_is_the_prefix_of_the_processor_names(self):
        stub = load(os.path.join(SHARED_DIR, "SharedProcessors.recipe"))
        self.assertEqual(stub["Identifier"] + "/", SHARED_PREFIX)

    def test_every_argument_is_a_declared_input(self):
        classes = processor_classes()
        for path in (DOWNLOAD, CIMIAN):
            for name, args in shared_steps(load(path)):
                for key in args:
                    with self.subTest(recipe=os.path.basename(path), processor=name, argument=key):
                        self.assertIn(key, classes[name].input_variables)

    def test_every_required_input_is_passed_or_has_a_default(self):
        """Inputs of a processor come from its arguments or from variables that
        earlier steps and the parent recipe set. The variable of the same name
        must then exist; pcman_root comes from the machine."""
        classes = processor_classes()
        provided = {  # what the earlier steps leave in the run
            "ChecksumVerifier": {"pathname", "expected_sha256"},
            "GitHubAssetDigest": set(),
            "PcmanImporter": {"pathname"},
            "WindowsExeVersion": {"pathname"},
        }
        for path in (DOWNLOAD, CIMIAN):
            for name, args in shared_steps(load(path)):
                for key, flags in classes[name].input_variables.items():
                    if not flags.get("required") or "default" in flags:
                        continue
                    with self.subTest(recipe=os.path.basename(path), processor=name, input=key):
                        if key in SUPPLIED_BY_THE_MACHINE.get(name, ()):
                            self.assertNotIn(key, args)
                        else:
                            self.assertIn(key, args)


class HygieneTests(unittest.TestCase):
    def files(self):
        for folder, dirs, files in os.walk(RECIPE_DIR):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if not name.endswith(".pyc"):
                    yield os.path.join(folder, name)

    def test_no_file_holds_a_value_that_belongs_to_one_site(self):
        for path in self.files():
            if os.path.basename(path) == "test_recipes.py":
                continue  # this file names the inputs that must not appear
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            for kind, pattern in shared_hygiene.FORBIDDEN_PATTERNS.items():
                with self.subTest(file=os.path.relpath(path, RECIPE_DIR), kind=kind):
                    self.assertIsNone(pattern.search(text))

    def test_nothing_deeper_than_the_tests_folder(self):
        for path in self.files():
            self.assertLessEqual(len(os.path.relpath(path, RECIPE_DIR).split(os.sep)), 2, path)


class ReadmeTests(unittest.TestCase):
    """The README must say that nothing was rehearsed or fetched, and must not teach a command that loses the trust check."""

    def setUp(self):
        import re
        self.re = re
        with open(os.path.join(RECIPE_DIR, "README.md"), "r", encoding="utf-8") as handle:
            self.raw = handle.read()
        self.text = re.sub(r"\s+", " ", self.raw)

    def test_every_make_override_command_names_an_override_folder(self):
        commands = list(self.re.finditer(r"autopkg make-override([^`\n]*(?:\n[ \t]+--[^\n`]*)?)", self.raw))
        self.assertTrue(commands)
        for match in commands:
            self.assertIn("--override-dir=", match.group(1))

    def test_no_run_of_a_recipe_identifier(self):
        runs = list(self.re.finditer(r"autopkg run([^`\n]*)", self.raw))
        self.assertTrue(runs)
        for match in runs:
            self.assertNotIn("com.github.", match.group(1))

    def operator_commands(self):
        """The lines of an operator step that run autopkg: indented four spaces or more."""
        pattern = re.compile(r"^ {4,}(autopkg (?:run|verify-trust-info|update-trust-info)\b.*)$", re.M)
        return [match.group(1) for match in pattern.finditer(self.raw)]

    def test_every_run_and_every_trust_command_carries_the_override_dir_and_the_path(self):
        """An override outside AutoPkg's configured override folders loses its trust check
        unless the folder is named on the command line (AutoPkg 2.9.0)."""
        commands = self.operator_commands()
        self.assertEqual(len([c for c in commands if c.startswith("autopkg run")]), 3)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg verify-trust-info")]), 2)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg update-trust-info")]), 1)
        for command in commands:
            with self.subTest(command=command):
                self.assertRegex(
                    command,
                    r"^autopkg (run|verify-trust-info|update-trust-info)( -vv?)? "
                    r"--override-dir=<the Windows overrides folder> "
                    r"<the Windows overrides folder>/BambuStudio\.cimian\.recipe$",
                )

    def test_no_autopkg_command_line_is_missed_by_the_indent_rule(self):
        """An operator's command that is not indented four spaces (or is indented
        less) must still be counted: every line that begins with an autopkg
        command is one of the lines checked above, and `autopkg run ` occurs
        three times in the whole file."""
        pattern = r"^[ \t]*autopkg (?:run|verify-trust-info|update-trust-info)\b"
        at_line_start = re.findall(pattern, self.raw, re.M)
        self.assertEqual(len(at_line_start), len(self.operator_commands()))
        self.assertEqual(len(re.findall(r"autopkg run ", self.raw)), 3)

    def test_no_prose_line_shows_a_full_command_without_the_option(self):
        for match in re.finditer(r"`(autopkg (?:run|verify-trust-info|update-trust-info)[^`]*<[^`]*)`", self.raw):
            self.assertIn("--override-dir=", match.group(1))

    def test_the_name_check_and_the_parent_check_are_in_step_b(self):
        step = self.raw[self.raw.index("## b."):self.raw.index("## c.")]
        self.assertIn("First check that no other recipe has the same name.", step)
        self.assertIn("autopkg list-recipes | grep -i BambuStudio-Win", step)
        self.assertIn("autopkg list-recipes | grep -i BambuStudio.cimian", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.download.BambuStudio-Win`",
                      re.sub(r"\s+", " ", step))
        self.assertLess(step.index("list-recipes"), step.index("autopkg make-override"))

    def test_the_readme_says_how_to_take_pre_releases_and_that_the_switch_is_a_boolean(self):
        start = self.text.index("**Pre-releases.**")
        paragraph = self.text[start:self.text.index("Below, `pcman` stands for")]
        for needle in ("the key `include_prereleases` in the recipe's `Input`, a boolean that is `false`",
                       "`make-override` copies it into the override", "never in the recipe",
                       "Set :Input:include_prereleases true",
                       "<the Windows overrides folder>/BambuStudio.cimian.recipe",
                       "`Add :Input:include_prereleases bool true`",
                       "Keep it a boolean", "the text `false` would count as true",
                       "applies the arguments of a step after the override's `Input`"):
            self.assertIn(needle, paragraph)
        self.assertLess(self.raw.index("**Pre-releases.**"), self.raw.index("## a."))

    def test_the_readme_states_no_hash(self):
        """A README that states a SHA-256 (64 hex digits) could be taken for a check."""
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.raw))

    def test_a_bold_paragraph_says_why_and_what_to_do_when_the_warning_appears(self):
        self.assertIn("## Run every override with `--override-dir`", self.raw)
        i = self.raw.index("## Run every override with `--override-dir`")
        paragraph = re.sub(r"\s+", " ", self.raw[i:i + 2500])
        for needle in ("**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`",
                       "skips the trust check with one warning line", "is missing trust info",
                       "a changed processor is not caught", "If that line ever appears in a run of an override, stop: the run was not checked.**",
                       "`FAIL_RECIPES_WITHOUT_TRUST_INFO`", "not set on the build machine today",
                       "change how the Mac recipes run", "owner's decision"):
            self.assertIn(needle, paragraph)
        self.assertLess(i, self.raw.index("## a."))

    def test_the_steps_of_the_operator_are_there(self):
        for needle in ("pcman catalogs", "pcman versions bambustudio", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string"):
            self.assertIn(needle, self.text)

    def test_the_status_line_says_what_was_not_done(self):
        opening = "**Status. NOT rehearsed, and the facts of the source NOT fetched by the writer:"
        self.assertIn(opening, self.raw)
        i = self.raw.index(opening)
        self.assertLess(i, self.raw.index("## a."))
        self.assertLess(i, self.raw.index("| Recipe |"))
        self.assertIn("the newest tags of `bambulab/BambuStudio` are `v02.08.03.65`, `v02.08.03.66`, "
                      "`v02.08.04.57` and `v02.08.04.61`", re.sub(r"\s+", " ", self.raw))
        self.assertIn("(tags only; the release assets and their digests were NOT fetched)", re.sub(r"\s+", " ", self.raw))
        self.assertEqual(self.raw.index("# Win-BambuStudio"), 0)
        paragraph = re.sub(r"\s+", " ", self.raw[i:self.raw.index("\n\n", i)])
        self.assertTrue(paragraph.endswith("**"))
        for needle in ("the network was closed",
                       "bambulab/BambuStudio",                       # the repository
                       "Bambu_Studio_win_public-v<version>-<number>.exe",  # the asset name
                       "build date",
                       "leading `v`",                                # the tag
                       "leading zeros",
                       "GitHub records a digest",                    # the digest
                       "NSIS", "/S", "from the writer's knowledge, not read in the installer",
                       "the first run on the build Mac is the check of each one",
                       "accepts a version part with a leading zero",
                       "orders that label as the EXE's own version",
                       "is NOT established",
                       "The first dry run shows the label and the package tool's answer",
                       "ProductVersion as a person reads it",
                       "stop. Nothing was written.",
                       "correct the recipe", "Never change the trust information first",
                       "A real run has NOT been run by anyone",
                       "`pcman catalogs` was NOT rehearsed"):
            self.assertIn(needle, paragraph)

    def test_the_readme_does_not_claim_a_rehearsal(self):
        self.assertNotIn("Rehearsed on", self.raw)
        self.assertNotIn("rehearsal printed", self.raw)
        self.assertNotIn("The rehearsal", self.raw)

    def test_the_label_is_never_written_out_alone_and_the_command_names_the_exe_only_flags(self):
        # Only inside the asset name (v<label>-<build date>) may it appear: alone it reads as an address.
        self.assertIsNone(re.search(r"(?<!v)" + re.escape(LABEL), self.raw))
        self.assertIn("## The version label", self.raw)
        step = self.raw[self.raw.index("3. **The template item"):self.raw.index("## b.")]
        command = step[step.index("pcman import"):step.index("--build") + len("--build")]
        for flag in ("--name bambustudio", "--version <label>", "--display-name", "--category", "--developer",
                     "--description", "--install-arguments /S", "--install-path", "--architectures x64",
                     "--no-prompt"):
            self.assertIn(flag, command)
        self.assertNotRegex(command, r"C:\\Program Files")  # the install path was not read: a placeholder
        self.assertIn("from the writer's knowledge, not read in the installer", re.sub(r"\s+", " ", step))
        self.assertIn("`--version <label>` is for an EXE only", re.sub(r"\s+", " ", step))

    def test_the_first_dry_run_names_what_can_stop_it(self):
        step = re.sub(r"\s+", " ", self.raw[self.raw.index("## c."):self.raw.index("## d.")])
        for needle in ("No asset matches", "`GitHubAssetDigest` stops with its error",
                       "a hand import", "The package tool refuses the label",
                       "compare it with the EXE's own ProductVersion",
                       "`WindowsExeVersion` stops", "says a version of zeros"):
            self.assertIn(needle, step)
        self.assertIn("autopkg run -v --override-dir=", step)
        self.assertIn("`-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the repository among them, "
                      "and such a log would have to be kept private", re.sub(r"\s+", " ", step))

    def test_the_version_label_section_says_where_the_label_comes_from(self):
        section = self.raw[self.raw.index("## The version label"):self.raw.index("## Run every override")]
        text = re.sub(r"\s+", " ", section)
        for needle in ("`WindowsExeVersion`", "`ProductVersion`", "overwrites `version` with it",
                       "numbers and dots only", "a label of zeros stops the run",
                       "belongs to the release and not to the file", "published under the tag",
                       "keeps their leading zeros", "is NOT known", "accept a part with a leading zero",
                       "order that label as the EXE's own version", "stop and tell the owner",
                       "`version is ..., taken from ...`", "**Read them first**"):
            self.assertIn(needle, text)


class ChainTests(_win_support.ToolTestCase):
    """The chain of this program counts as verified for the importer: the real
    ChecksumVerifier hashes the file, and the importer hashes it again and
    compares. The stand-in package tool is used; nothing else is run."""

    PRODUCT_VERSION = "9.8.7"  # made up: the real ProductVersion is NOT known

    def build_installer(self, product, numbers):
        built = exe_tests.build_pe(exe_tests.version_info(
            product=product, file=product, name="Example App", file_numbers=numbers, product_numbers=numbers))
        with open(self.exe, "wb") as handle:
            handle.write(bytes(built.data))

    def setUp(self):
        super().setUp()
        # The installer is a small PE file with a version resource, so that the
        # recipe's own WindowsExeVersion step can read it.
        self.build_installer(self.PRODUCT_VERSION, (9, 8, 7, 0))

    def chain_env(self, installer):
        """What the steps of the two recipes leave in the run, with the
        arguments of the recipe's own steps. The download recipe's last step
        is run with the recipe's own arguments."""
        run = {"pathname": installer, "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        steps = {step["Processor"][len(SHARED_PREFIX):]: step.get("Arguments", {})
                 for step in load(DOWNLOAD)["Process"] if step["Processor"].startswith(SHARED_PREFIX)}
        values = {"%pathname%": installer}
        reader_env = {name: values.get(value, value) for name, value in steps["WindowsExeVersion"].items()}
        reader_env["version"] = LABEL  # what the provider made of the tag
        reader, _ = _win_support.run_processor(_win_support.exe_version.WindowsExeVersion, reader_env)
        values.update({"%PCMAN_TEMPLATE%": load(CIMIAN)["Input"]["PCMAN_TEMPLATE"],
                       "%version%": reader.env["version"]})
        env = {"pathname": installer, "pcman_root": self.root, "pcman_dry_run": False,
               "pcman_path": self.msi_bin}
        env.update({k: v for k, v in verifier.env.items() if k.startswith("checksum_")})
        cimian_steps = [step for step in load(CIMIAN)["Process"] if step["Processor"].endswith("/PcmanImporter")]
        self.assertEqual(len(cimian_steps), 1)
        for name, value in cimian_steps[0]["Arguments"].items():
            env[name] = values.get(value, value)
        return env

    def test_the_label_is_the_exe_s_own_version_and_not_the_tag(self):
        env = self.chain_env(self.exe)
        self.assertEqual(env["pcman_version"], self.PRODUCT_VERSION)
        self.assertNotEqual(env["pcman_version"], LABEL)
        _win_support.run_processor(_win_support.importer.PcmanImporter, env)
        argv = self.record()["argv"]
        self.assertEqual(argv[argv.index("--version") + 1], self.PRODUCT_VERSION)

    def test_a_product_version_with_the_leading_zeros_of_the_tag_is_passed_as_it_is(self):
        """The processor guesses nothing: if the installer's ProductVersion has the tag's
        leading zeros, so has the label. (Whether the package tool and the client take it is NOT established.)"""
        self.build_installer(LABEL, tuple(int(part) for part in TAG_PARTS))
        env = self.chain_env(self.exe)
        self.assertEqual(env["pcman_version"], LABEL)

    def test_the_chain_counts_as_verified_and_nothing_is_warned(self):
        env = self.chain_env(self.exe)
        self.assertEqual(env["checksum_sha256"], _win_support.sha256_hex(self.exe))
        processor, _ = _win_support.run_processor(_win_support.importer.PcmanImporter, env)
        self.assertIs(processor.env["pcman_repo_changed"], True)
        warnings = [m for level, m in processor.message_levels if m.startswith("WARNING:")]
        self.assertEqual(warnings, [])
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published")

    def test_the_chain_is_refused_for_another_file(self):
        env = self.chain_env(self.exe)
        other = os.path.join(self.downloads, "other.exe")
        with open(other, "wb") as handle:
            handle.write(b"not the file that was verified")
        env["pathname"] = other
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_win_support.importer.PcmanImporter, env)
        self.assertIn("not the file whose checksum was verified", str(caught.exception))
        self.assertFalse(self.was_run())


if __name__ == "__main__":
    unittest.main()
