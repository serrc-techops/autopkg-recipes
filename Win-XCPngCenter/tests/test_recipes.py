"""Tests of the two XCP-ng Center recipes. Nothing here runs AutoPkg or uses the network.

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
import test_public_repository as shared_hygiene  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "XCPngCenter-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "XCPngCenter.cimian.recipe")
# Required inputs that a recipe must NOT pass: they come from AutoPkg's
# preferences or the override on the machine that runs it.
SUPPLIED_BY_THE_MACHINE = {"PcmanImporter": {"pcman_root"}}
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir", "pcman_allow_unverified",
                     "checksum_verified")


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def processor_classes():
    import importlib
    classes = {}
    for name in ("PcmanImporter", "ChecksumVerifier", "GitHubAssetDigest"):
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
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.XCPngCenter-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.XCPngCenter")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [
            "GitHubReleasesInfoProvider", "URLDownloader", "EndOfCheckPhase",
            SHARED_PREFIX + "GitHubAssetDigest", SHARED_PREFIX + "ChecksumVerifier",
        ])

    def test_the_cimian_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "PcmanImporter"])

    def test_the_provider_arguments(self):
        args = load(DOWNLOAD)["Process"][0]["Arguments"]
        self.assertEqual(args["github_repo"], "xcp-ng/xenadmin")
        self.assertEqual(args["asset_regex"], "%SEARCH_PATTERN%")
        self.assertNotIn("include_prereleases", args)
        self.assertEqual(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"], r"XCP-ng-Center-(?!99\.)[0-9.]+\.msi$")

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

    def test_the_default_pattern_matches_the_msi_and_not_the_others(self):
        """The names are written by hand from what the writer knows (not read in a release).
        A dotted name of four numbers is built, not written, so that no file of the folder
        holds text that looks like an IPv4 address."""
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        version = ".".join(["20", "04", "01", "33"])
        self.assertTrue(pattern.search("XCP-ng-Center-%s.msi" % version))
        self.assertTrue(pattern.search("XCP-ng-Center-8.2.msi"))
        for name in ("XCP-ng-Center-%s.msi.sig" % version, "XCP-ng-Center-%s.zip" % version,
                     "XCP-ng-Center-%s.exe" % version, "XCP-ng-Center-.msi", "XCP-ng-Center-beta.msi",
                     "xcp-ng-center-%s.msi" % version, "Source code (zip)"):
            self.assertFalse(pattern.search(name), name)

    def test_the_default_pattern_does_not_take_the_99_builds(self):
        """The tags v99.99.99.x look like test builds. A release with an MSI of that kind would be
        published as version 99 and no later release would ever be newer. AutoPkg 2.9.0 matches the
        pattern from the start of the name (`re.match`, `GitHubReleasesInfoProvider.py`,
        `select_asset`); searching the name is tried too. Names are built, not written (see the
        pattern test)."""
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        test_build = ".".join(["99", "99", "99", "29"])
        for check in (pattern.match, pattern.search):
            for name in ("XCP-ng-Center-%s.msi" % test_build, "XCP-ng-Center-99.msi", "XCP-ng-Center-99.1.msi",
                         "XCP-ng-Center-99.99.msi"):
                self.assertIsNone(check(name), name)
            # a version that merely contains or begins with the digits is not a 99 build
            for name in ("XCP-ng-Center-%s.msi" % ".".join(["20", "04", "01", "33"]), "XCP-ng-Center-25.04.msi",
                         "XCP-ng-Center-8.2.msi", "XCP-ng-Center-199.1.msi", "XCP-ng-Center-990.1.msi",
                         "XCP-ng-Center-8.99.msi"):
                self.assertIsNotNone(check(name), name)

    def test_the_inputs_of_the_cimian_recipe(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], "XCPngCenter")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "xcp-ng-center")
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%"})

    def test_the_template_keeps_the_name_of_the_item_it_replaces(self):
        self.assertEqual(load(CIMIAN)["Input"]["PCMAN_TEMPLATE"], "xcp-ng-center")

    def test_no_pcman_version_in_an_msi_recipe(self):
        """For an MSI the package tool takes the MSI's own ProductVersion."""
        for path in (DOWNLOAD, CIMIAN):
            with open(path, "r", encoding="utf-8") as handle:
                self.assertNotIn("pcman_version", handle.read())
        for step in load(CIMIAN)["Process"]:
            self.assertNotIn("pcman_version", step.get("Arguments", {}))
            self.assertNotIn("%version%", str(step.get("Arguments", {})))

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

    def test_no_blocking_applications_and_no_hash_in_a_recipe(self):
        for path in (DOWNLOAD, CIMIAN):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.assertNotIn("blocking_applications", text)
            self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", text))

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in (DOWNLOAD, CIMIAN):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text)

    def test_the_description_says_what_a_reader_must_know(self):
        download = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        for needle in ("newest non-pre-release", "matching file", "SHA-256 that GitHub records",
                       "has no recorded digest", "the run stops with an error and writes nothing",
                       "hand import", "from the writer's knowledge"):
            self.assertIn(needle, download)
        for claim in ("Rehearsed", "rehearsed on", "was rehearsed"):
            self.assertNotIn(claim, download)
        cimian = re.sub(r"\s+", " ", load(CIMIAN)["Description"])
        self.assertIn("MSI's own ProductVersion", cimian)
        self.assertIn("dry run", cimian)
        self.assertIn("pcman_dry_run", cimian)
        self.assertNotIn("ehearsed", cimian)

    def test_no_value_of_a_recipe_is_a_path_or_a_catalog(self):
        for path in (DOWNLOAD, CIMIAN):
            recipe = load(path)
            values = list(recipe["Input"].values())
            for step in recipe["Process"]:
                values.extend(step.get("Arguments", {}).values())
            for value in values:
                if not isinstance(value, str):
                    continue
                with self.subTest(path=os.path.basename(path), value=value):
                    self.assertFalse(value.startswith(("/", "~", ".")), value)
                    self.assertNotIn("\\\\", value)
                    self.assertNotIn("Production", value)
                    self.assertNotIn("Testing", value)


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

    def test_the_folder_holds_only_what_is_expected(self):
        names = sorted(os.path.relpath(path, RECIPE_DIR) for path in self.files())
        self.assertEqual(names, sorted([
            "XCPngCenter-Win.download.recipe", "XCPngCenter.cimian.recipe", "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
        ]))

    def test_no_file_holds_text_that_looks_like_an_address(self):
        """The hygiene pattern for an IPv4 address also matches a version of four numbers;
        nothing of the folder may hold one (see the pattern test)."""
        for path in self.files():
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                self.assertIsNone(re.search(r"\b\d+\.\d+\.\d+\.\d+\b", handle.read()), path)

    def test_nothing_deeper_than_the_tests_folder(self):
        for path in self.files():
            self.assertLessEqual(len(os.path.relpath(path, RECIPE_DIR).split(os.sep)), 2, path)


class ReadmeTests(unittest.TestCase):
    """The README must not claim a rehearsal, and must not teach what the 7-Zip rehearsal showed to be wrong."""

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
                    r"^autopkg (run|verify-trust-info|update-trust-info)( -vv)? "
                    r"--override-dir=<the Windows overrides folder> "
                    r"<the Windows overrides folder>/XCPngCenter\.cimian\.recipe$",
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
        self.assertIn("autopkg list-recipes | grep -i XCPngCenter-Win", step)
        self.assertIn("autopkg list-recipes | grep -i XCPngCenter.cimian", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.download.XCPngCenter-Win`",
                      re.sub(r"\s+", " ", step))
        self.assertLess(step.index("list-recipes"), step.index("autopkg make-override"))

    def test_the_readme_says_how_to_take_pre_releases_and_that_the_switch_is_a_boolean(self):
        start = self.text.index("**Pre-releases.**")
        paragraph = self.text[start:self.text.index("Below, `pcman` stands for")]
        for needle in ("the key `include_prereleases` in the recipe's `Input`, a boolean that is `false`",
                       "`make-override` copies it into the override", "never in the recipe",
                       "Set :Input:include_prereleases true",
                       "<the Windows overrides folder>/XCPngCenter.cimian.recipe",
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

    def test_the_steps_of_the_model_are_there(self):
        for needle in ("pcman catalogs", "pcman versions xcp-ng-center", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string"):
            self.assertIn(needle, self.text)

    def test_the_first_import_has_the_descriptive_flags_no_version_and_keeps_the_template_name(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        self.assertTrue(match)
        command = re.sub(r"\s+", " ", match.group(1))
        self.assertIn("--name xcp-ng-center", command)
        for flag in ("--display-name", "--category", "--developer", "--description"):
            self.assertIn(flag, command)
        self.assertNotIn("--version", command)
        self.assertIn("--no-prompt", command)
        self.assertIn("--architectures", command)

    def test_the_status_line_says_what_was_not_done(self):
        self.assertTrue(self.raw.index("**Status. NOT rehearsed, and the facts of the source NOT fetched by the writer:") >= 0)
        self.assertLess(self.raw.index("**Status."), self.raw.index("## a."))
        self.assertLess(self.raw.index("# Win-XCPngCenter"), self.raw.index("**Status."))
        i = self.raw.index("**Status.")
        paragraph = re.sub(r"\s+", " ", self.raw[i:self.raw.index("\n\n", i)])
        self.assertTrue(paragraph.startswith(
            "**Status. NOT rehearsed, and the facts of the source NOT fetched by the writer:"))
        for needle in ("the network was closed", "from the writer's knowledge or from another recipe",
                       "`xcp-ng/xenadmin`", "`XCP-ng-Center-(?!99\\.)[0-9.]+\\.msi$`", "UpgradeCode", "architecture",
                       "The project releases rarely",
                       "read through git on 2026-10-02", "`v20.04.01.33`", "`v99.99.99.23`", "`vNext-24307`",
                       "look like test builds", "does not take a file whose version begins with `99.`",
                       "nobody has read the release list", "A person must still read the first dry run before anything else",
                       "the newest release may be another kind of test build",
                       "takes whatever GitHub returns first with a matching asset",
                       "has no digest", "`GitHubAssetDigest` stops the run with its error",
                       "nothing is written", "the program is a hand import until a release with a digest exists",
                       "The first run on the build Mac is the check of every one of these facts",
                       "stop: nothing was written", "correct the recipe",
                       "Never correct the trust information first.**", "carries `--override-dir`"):
            self.assertIn(needle, paragraph)

    def test_the_readme_claims_no_rehearsal_of_this_program(self):
        self.assertNotIn("Rehearsed on", self.raw)
        self.assertNotIn("NOT yet run", self.raw)
        # What it says of a rehearsal is about the 7-Zip folder only.
        for sentence in re.split(r"(?<=[.:;])\s", self.text):
            if re.search(r"(?i)rehears", sentence):
                self.assertTrue("7-Zip" in sentence or re.search(r"(?i)not rehearsed", sentence), sentence)

    def test_the_readme_says_that_the_version_is_the_msis_own(self):
        self.assertIn("There is no `--version`: the package tool takes the MSI's own version", self.text)
        self.assertIn("MSI's own ProductVersion", self.text)

    def test_the_readme_says_what_to_do_without_a_digest(self):
        for needle in ("no digest", "hand import", "Publish it by hand after checking it"):
            self.assertIn(needle, self.text)

    def test_the_install_facts_are_marked_as_from_knowledge(self):
        self.assertIn("(from the writer's knowledge, not read in the package tool's README)", self.text)


class ChainTests(_win_support.ToolTestCase):
    """The chain of this program counts as verified for the importer: the real
    ChecksumVerifier hashes the file, and the importer hashes it again and
    compares. The stand-in package tool is used; nothing else is run."""

    def chain_env(self, installer):
        """What the steps of the two recipes leave in the run, with the
        arguments of the recipe's own PcmanImporter step."""
        run = {"pathname": installer, "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        values = {"%pathname%": installer, "%PCMAN_TEMPLATE%": load(CIMIAN)["Input"]["PCMAN_TEMPLATE"],
                  "%version%": ""}
        env = {"pathname": installer, "pcman_root": self.root, "pcman_dry_run": False,
               "pcman_path": self.msi_bin}
        env.update({k: v for k, v in verifier.env.items() if k.startswith("checksum_")})
        steps = [step for step in load(CIMIAN)["Process"] if step["Processor"].endswith("/PcmanImporter")]
        self.assertEqual(len(steps), 1)
        for name, value in steps[0]["Arguments"].items():
            env[name] = values.get(value, value)
        return env

    def test_the_chain_counts_as_verified_and_nothing_is_warned(self):
        env = self.chain_env(self.msi)
        self.assertEqual(env["checksum_sha256"], _win_support.sha256_hex(self.msi))
        processor, _ = _win_support.run_processor(_win_support.importer.PcmanImporter, env)
        self.assertIs(processor.env["pcman_repo_changed"], True)
        warnings = [m for level, m in processor.message_levels if m.startswith("WARNING:")]
        self.assertEqual(warnings, [])
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published")

    def test_the_chain_is_refused_for_another_file(self):
        env = self.chain_env(self.msi)
        other = os.path.join(self.downloads, "other.msi")
        with open(other, "wb") as handle:
            handle.write(b"not the file that was verified")
        env["pathname"] = other
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_win_support.importer.PcmanImporter, env)
        self.assertIn("not the file whose checksum was verified", str(caught.exception))
        self.assertFalse(self.was_run())


if __name__ == "__main__":
    unittest.main()
