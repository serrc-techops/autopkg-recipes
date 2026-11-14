"""Tests of the three WizTree recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names one of our
processors is compared with what that processor declares: the shared ones
(see ../../Win-SharedProcessors and ../../Win-PcmanProcessors) and this folder's
own WizTreeInfoProvider (tested in test_info_provider.py). The shared folders'
tests are run separately.
"""
import importlib
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
PCMAN_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-PcmanProcessors")
PCMAN_TESTS_DIR = os.path.join(PCMAN_DIR, "tests")
for folder in (SHARED_TESTS_DIR, RECIPE_DIR, PCMAN_TESTS_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import _win_support  # noqa: E402  (installs the autopkglib stand-in, imports the processors)
import _pcman_support  # noqa: E402  (the stand-in for the package tool, and its processor)
import test_public_repository as shared_hygiene  # noqa: E402
import WizTreeInfoProvider as own  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
OWN_PROCESSOR = "WizTreeInfoProvider"
DOWNLOAD = os.path.join(RECIPE_DIR, "WizTree-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "WizTree.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "WizTree.pcman.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
EXCERPT = os.path.join(TESTS_DIR, "download_page_excerpt.html")
ALL = (DOWNLOAD, CIMIAN, PCMAN)
# Processors that are part of AutoPkg itself.
CORE_PROCESSORS = ("URLDownloader", "EndOfCheckPhase")
# Required inputs that a recipe must NOT pass: they come from AutoPkg's
# preferences or the override on the machine that runs it.
SUPPLIED_BY_THE_MACHINE = {"PcmanImporter": {"pcman_root"}, "CimianImporter": {"cimian_repo"}}
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir", "pcman_timeout",
                     "cimian_repo", "cimian_dry_run", "cimian_allow_unverified", "cimian_path", "cimian_catalogs",
                     "pcman_allow_unverified")
# What the earlier steps leave in the run (a step reads these without an argument).
SET_BY_EARLIER_STEPS = {"pathname", "url", "version", "expected_sha256"}


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def processor_classes():
    classes = {OWN_PROCESSOR: own.WizTreeInfoProvider}
    for name in ("PcmanImporter", "CimianImporter", "ChecksumVerifier"):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def named_steps(recipe):
    """(processor name without the prefix, arguments) of every step that is ours."""
    for step in recipe["Process"]:
        name = step["Processor"]
        if name.startswith(SHARED_PREFIX):
            yield name[len(SHARED_PREFIX):], step.get("Arguments", {})
        elif name.startswith(PCMAN_PREFIX):
            yield name[len(PCMAN_PREFIX):], step.get("Arguments", {})
        elif name == OWN_PROCESSOR:
            yield name, step.get("Arguments", {})


class RecipeFileTests(unittest.TestCase):
    def test_the_three_files_are_valid_property_lists(self):
        for path in ALL:
            with self.subTest(path=os.path.basename(path)):
                if os.path.exists("/usr/bin/plutil"):
                    result = subprocess.run(["plutil", "-lint", path], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                recipe = load(path)
                for key in ("Description", "Identifier", "Input", "MinimumVersion", "Process"):
                    self.assertIn(key, recipe)

    def test_identifiers_and_parents(self):
        download, cimian, pcman = load(DOWNLOAD), load(CIMIAN), load(PCMAN)
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.WizTree-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.WizTree")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.WizTree")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)
        self.assertEqual(cimian["MinimumVersion"], pcman["MinimumVersion"])

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [OWN_PROCESSOR, "URLDownloader", "EndOfCheckPhase", SHARED_PREFIX + "ChecksumVerifier"])

    def test_the_provider_has_no_arguments_and_the_downloader_takes_its_address(self):
        process = load(DOWNLOAD)["Process"]
        self.assertNotIn("Arguments", process[0])
        self.assertNotIn("Arguments", process[1])
        self.assertIn("url", own.WizTreeInfoProvider.output_variables)
        self.assertEqual(load(DOWNLOAD)["Input"], {"NAME": "WizTree"})

    def test_the_checksum_arguments_are_the_pages_hash(self):
        steps = dict(named_steps(load(DOWNLOAD)))
        self.assertEqual(steps["ChecksumVerifier"], {"pathname": "%pathname%", "expected_sha256": "%expected_sha256%"})
        self.assertIn("expected_sha256", own.WizTreeInfoProvider.output_variables)

    def test_no_step_reads_a_version_from_the_file(self):
        """The label comes from the provider; a second source of the version would be ambiguous."""
        for path in ALL:
            text = read(path)
            for name in ("WindowsExeVersion", "VersionFromName"):
                self.assertNotIn(name, text)
        self.assertIn("version", own.WizTreeInfoProvider.output_variables)

    def test_both_importer_recipes_pass_the_label(self):
        self.assertEqual(load(CIMIAN)["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": "%version%"})
        self.assertEqual(load(PCMAN)["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%", "pcman_version": "%version%"})

    def test_the_inputs_of_the_importer_recipes(self):
        cimian, pcman = load(CIMIAN)["Input"], load(PCMAN)["Input"]
        self.assertEqual(sorted(cimian), ["CIMIAN_NAME", "CIMIAN_SUBDIRECTORY", "NAME", "pkginfo"])
        self.assertEqual(cimian["CIMIAN_NAME"], "wiztree")
        self.assertEqual(cimian["CIMIAN_SUBDIRECTORY"], "")
        self.assertEqual(cimian["NAME"], "WizTree")
        self.assertEqual(cimian["pkginfo"], {"display_name": "WizTree", "developer": "Antibody Software"})
        self.assertEqual(pcman, {"NAME": "WizTree", "PCMAN_TEMPLATE": "wiztree"})

    def test_the_only_step_of_each_importer_recipe(self):
        self.assertEqual([s["Processor"] for s in load(CIMIAN)["Process"]], [SHARED_PREFIX + "CimianImporter"])
        self.assertEqual([s["Processor"] for s in load(PCMAN)["Process"]], [PCMAN_PREFIX + "PcmanImporter"])

    def test_every_variable_a_recipe_uses_is_an_input_or_set_by_an_earlier_step(self):
        parent = set(load(DOWNLOAD)["Input"])
        for path in ALL:
            recipe = load(path)
            known = set(recipe["Input"]) | SET_BY_EARLIER_STEPS | parent
            for step in recipe["Process"]:
                for value in step.get("Arguments", {}).values():
                    for name in re.findall(r"%([A-Za-z_]+)%", str(value)):
                        with self.subTest(recipe=os.path.basename(path), variable=name):
                            self.assertIn(name, known)

    def test_no_stop_on_an_unchanged_download_no_latest_only_no_blocking_applications(self):
        for path in ALL:
            text = read(path)
            for word in ("StopProcessingIf", "latest_only", "blocking_applications"):
                self.assertNotIn(word, text)

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in ALL:
            text = read(path)
            for name in NEVER_IN_A_RECIPE + ("catalogs", "catalog", "path", "repo", "directory", "CIMIAN_REPO"):
                with self.subTest(recipe=os.path.basename(path), name=name):
                    self.assertNotIn("<key>%s</key>" % name, text)

    def test_no_value_of_a_recipe_is_a_path_a_catalog_or_a_hash(self):
        for path in ALL:
            recipe = load(path)
            values = [v for v in recipe["Input"].values() if isinstance(v, str)]
            for step in recipe["Process"]:
                values.extend(v for v in step.get("Arguments", {}).values() if isinstance(v, str))
            for value in values:
                with self.subTest(path=os.path.basename(path), value=value):
                    self.assertFalse(value.startswith(("/", "~", ".")), value)
                    self.assertNotIn("\\", value)
                    self.assertNotIn("Production", value)
                    self.assertNotIn("Testing", value)
            self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", read(path)))

    def test_no_silent_arguments_or_licence_key_in_a_recipe(self):
        """The switches were not tested on a PC; a licence key never goes into a public recipe."""
        for path in ALL:
            text = read(path)
            for word in ("VERYSILENT", "supportercode", "/S<", "args", "install-arguments"):
                self.assertNotIn(word, text)

    def test_nothing_of_the_package_tool_is_in_the_cimian_recipe(self):
        text = read(CIMIAN).lower()
        for word in ("pcman", "package tool", "template item"):
            self.assertNotIn(word, text)

    def test_the_descriptions_say_what_a_reader_must_know(self):
        download = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        for needle in ("SHA-256", "WizTreeInfoProvider", "exactly one link", "never the portable .zip's",
                       "4_33 gives 4.33", "diskanalyzer.com", "without following a redirect",
                       "has not been run with AutoPkg yet", "free for personal use only"):
            self.assertIn(needle, download)
        for path, switch in ((CIMIAN, "cimian_dry_run"), (PCMAN, "pcman_dry_run")):
            description = re.sub(r"\s+", " ", load(path)["Description"])
            for needle in ("dry run", switch, "has not been run by anyone yet", "free for personal use only",
                           "says that nothing is new", "4_33 gives 4.33"):
                with self.subTest(recipe=os.path.basename(path), needle=needle):
                    self.assertIn(needle, description)
        self.assertIn("CIMIAN_REPO", load(CIMIAN)["Description"])
        for path in ALL:
            self.assertNotIn("ehearsed on", load(path)["Description"])


class ProcessorTests(unittest.TestCase):
    def test_every_named_processor_exists(self):
        for path in ALL:
            for step in load(path)["Process"]:
                name = step["Processor"]
                if name.startswith(SHARED_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, name[len(SHARED_PREFIX):] + ".py")), name)
                elif name.startswith(PCMAN_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(PCMAN_DIR, name[len(PCMAN_PREFIX):] + ".py")), name)
                elif name not in CORE_PROCESSORS:
                    self.assertTrue(os.path.isfile(os.path.join(RECIPE_DIR, name + ".py")), name)

    def test_the_own_processor_has_a_class_of_the_same_name(self):
        self.assertIn("class %s(Processor):" % OWN_PROCESSOR, read(os.path.join(RECIPE_DIR, OWN_PROCESSOR + ".py")))

    def test_the_stub_identifier_is_the_prefix_of_the_processor_names(self):
        stub = load(os.path.join(SHARED_DIR, "SharedProcessors.recipe"))
        self.assertEqual(stub["Identifier"] + "/", SHARED_PREFIX)

    def test_every_argument_is_a_declared_input(self):
        classes = processor_classes()
        for path in ALL:
            for name, args in named_steps(load(path)):
                for key in args:
                    with self.subTest(recipe=os.path.basename(path), processor=name, argument=key):
                        self.assertIn(key, classes[name].input_variables)

    def test_every_required_input_is_passed_or_comes_from_the_machine(self):
        classes = processor_classes()
        for path in ALL:
            for name, args in named_steps(load(path)):
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
            text = read(path)
            for kind, pattern in shared_hygiene.FORBIDDEN_PATTERNS.items():
                with self.subTest(file=os.path.relpath(path, RECIPE_DIR), kind=kind):
                    self.assertIsNone(pattern.search(text))

    def test_nothing_deeper_than_the_tests_folder(self):
        for path in self.files():
            self.assertLessEqual(len(os.path.relpath(path, RECIPE_DIR).split(os.sep)), 2, path)

    def test_the_folder_holds_only_what_is_expected(self):
        names = sorted(os.path.relpath(path, RECIPE_DIR) for path in self.files())
        self.assertEqual(names, sorted([
            "WizTree-Win.download.recipe", "WizTree.cimian.recipe", "WizTree.pcman.recipe",
            "WizTreeInfoProvider.py", "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
            os.path.join("tests", "test_info_provider.py"), os.path.join("tests", "download_page_excerpt.html"),
        ]))

    def test_the_saved_page_is_an_excerpt_not_the_page(self):
        self.assertLess(os.path.getsize(EXCERPT), 20000)


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.raw = read(README)
        self.text = re.sub(r"\s+", " ", self.raw)
        self.status = self.text[self.text.index("**Status."):self.text.index("| Recipe |")]

    def operator_commands(self):
        pattern = re.compile(r"^ {4,}(autopkg (?:run|verify-trust-info|update-trust-info)\b.*)$", re.M)
        return [match.group(1) for match in pattern.finditer(self.raw)]

    def test_every_make_override_command_names_an_override_folder(self):
        commands = list(re.finditer(r"autopkg make-override([^`\n]*)", self.raw))
        self.assertEqual(len(commands), 2)
        for match in commands:
            self.assertIn("--override-dir=", match.group(1))

    def test_no_run_of_a_recipe_identifier(self):
        runs = list(re.finditer(r"autopkg run([^`\n]*)", self.raw))
        self.assertTrue(runs)
        for match in runs:
            self.assertNotIn("com.github.", match.group(1))

    def test_every_run_and_every_trust_command_carries_the_override_dir_and_the_path(self):
        commands = self.operator_commands()
        self.assertEqual(len([c for c in commands if c.startswith("autopkg run")]), 6)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg verify-trust-info")]), 4)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg update-trust-info")]), 2)
        for command in commands:
            with self.subTest(command=command):
                self.assertRegex(
                    command,
                    r"^autopkg (run|verify-trust-info|update-trust-info)( -vv?)? "
                    r"--override-dir=<the Windows overrides folder> "
                    r"<the Windows overrides folder>/WizTree\.(?:cimian|pcman)\.recipe$",
                )

    def test_no_autopkg_command_line_is_missed_by_the_indent_rule(self):
        pattern = r"^[ \t]*autopkg (?:run|verify-trust-info|update-trust-info)\b"
        self.assertEqual(len(re.findall(pattern, self.raw, re.M)), len(self.operator_commands()))

    def test_no_prose_line_shows_a_full_command_without_the_option(self):
        for match in re.finditer(r"`(autopkg (?:run|verify-trust-info|update-trust-info)[^`]*<[^`]*)`", self.raw):
            self.assertIn("--override-dir=", match.group(1))

    def test_the_readme_states_no_hash(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.raw))

    def test_the_sections_come_in_this_order(self):
        positions = [self.raw.index(mark) for mark in (
            "**Status.", "| Recipe |", "## What the checks prove", "## The version label",
            "## Run every override with `--override-dir`", "## With any Cimian repository",
            "## With the package tool (pcman)", "## a. ", "## b. ", "## c. ", "## g. ", "## Other facts", "## Tests")]
        self.assertEqual(positions, sorted(positions))

    def test_the_status_line_is_first_and_says_nothing_was_run(self):
        self.assertTrue(self.raw.split("\n\n")[2].startswith("**Status. New and not rehearsed: nothing of this folder has run under AutoPkg"))
        for needle in ("no installer was downloaded", "nothing was installed on a PC"):
            self.assertIn(needle, self.status)

    def test_the_status_line_carries_the_licence_question(self):
        for needle in ("LICENCE: WizTree is free for personal use only", "\"Personal use only\"",
                       "\"Commercial use not allowed\"", "Whether a school or its IT staff need a licence is the owner's question",
                       "before the item goes into any manifest"):
            self.assertIn(needle, self.status)

    def test_the_status_line_separates_what_was_read_from_what_was_not(self):
        read_facts = ("read by the writer on 2026-11-13", "answers 200 without a redirect",
                      "with curl's own and with the processor's", "exactly one link to the installer",
                      "`<base href=\"/\">`", "in its attribute `data-sha` and in its title",
                      "the hash belongs to a file by sitting inside that file's link", "text only",
                      "redirect (301) to the publisher's content delivery host", "that host was not asked",
                      "`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-`",
                      "that the installer is one was NOT read from the file")
        not_known = ("NOT established: that the switches install silently on a PC (NOT tested)", "the install path",
                     "whether the installer has a version resource",
                     "the version that the installed program reports about itself",
                     "whether the publisher ever replaces a file under the same name", "any run under AutoPkg",
                     "When a run fails, stop", "never accept a trust change", "stop and tell the owner")
        for needle in read_facts + not_known:
            with self.subTest(needle=needle):
                self.assertIn(needle, self.status)

    def test_nothing_is_claimed_as_run_or_tested_for_this_program(self):
        for claim in ("was tested on a PC", "Rehearsed on", "ran on 2026", "worked as written"):
            self.assertNotIn(claim, self.text)

    def test_the_readme_says_how_the_installer_and_its_hash_are_found(self):
        for needle in ("**exactly one link**", "`files/wiztree_<two to four numbers joined by underscores>_setup.exe`",
                       "no other `<a>`", "exactly one `data-sha=\"<64 hex digits>\"`", "is never read",
                       "cannot be taken", "follows no redirect", "512 KiB", "time limit of 120 seconds",
                       "It never guesses"):
            self.assertIn(needle, self.text)

    def test_the_checks_prove_section_says_what_the_hash_does_not_prove(self):
        section = self.text[self.text.index("## What the checks prove"):self.text.index("## The version label")]
        for needle in ("The hash and the file come from the same publisher", "It does NOT help if the publisher's site itself is changed",
                       "No signature of the file (Authenticode) is checked"):
            self.assertIn(needle, section)

    def test_the_version_label_section(self):
        section = self.text[self.text.index("## The version label"):self.text.index("## Run every override")]
        for needle in ("`wiztree_4_33_setup.exe` gives `4.33`", "a leading zero stays", "4.00, 4.01, ... 4.09",
                       "then 4.10", "4.09 comes before 4.10", "A label of two parts meets neither",
                       "release written `4.4` after `4.33` would be ordered before it",
                       "**Open: does the publisher replace a file under the same name?**",
                       "compare the label with what the installed program shows"):
            self.assertIn(needle, section)

    def test_the_first_import_names_the_exe_flags_and_leaves_the_untested_open(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        command = re.sub(r"\s+", " ", match.group(1))
        for flag in ("--name wiztree", "--version <label>", "--display-name \"WizTree\"", "--developer \"Antibody Software\"",
                     "--install-arguments <the silent arguments>", "--no-prompt"):
            self.assertIn(flag, command)
        self.assertNotIn("VERYSILENT", command)
        self.assertIn("(NOT run for WizTree)", self.text)

    def test_no_licence_key_goes_into_the_repository(self):
        self.assertIn("A licence key (`/supportercode=`) never goes into this public repository", self.text)
        self.assertIn("A licence key never goes into this public repository", self.text)

    def test_the_real_run_waits_for_the_licence_question(self):
        self.assertEqual(self.text.count("Only after the owner has settled the licence question"), 2)

    def test_the_name_check_and_the_parent_check(self):
        generic = self.raw[self.raw.index("## With any Cimian repository"):self.raw.index("## With the package tool (pcman)")]
        tool = self.raw[self.raw.index("## b."):self.raw.index("## c.")]
        self.assertIn("autopkg list-recipes | grep -i WizTree.cimian", generic)
        self.assertIn("autopkg list-recipes | grep -i WizTree.pcman", tool)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.cimian.WizTree`**", re.sub(r"\s+", " ", generic))
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.WizTree`**", re.sub(r"\s+", " ", tool))

    def test_each_way_names_only_its_own_recipe(self):
        generic = self.raw[self.raw.index("## With any Cimian repository"):self.raw.index("## With the package tool (pcman)")]
        tool = self.raw[self.raw.index("## With the package tool (pcman)"):self.raw.index("\n## Other facts")]
        for text, mine, other in ((generic, "WizTree.cimian", "WizTree.pcman"), (tool, "WizTree.pcman", "WizTree.cimian")):
            for line in text.splitlines():
                if re.match(r"^\s*autopkg (run|verify-trust-info|update-trust-info|make-override)\b", line):
                    with self.subTest(line=line):
                        self.assertIn(mine, line)
                        self.assertNotIn(other, line)
        for word in ("pcman import", "pcman catalogs", "pcman_root", "PCMAN_TEMPLATE", "PcmanImporter"):
            self.assertNotIn(word, generic)

    def test_the_lines_that_the_generic_way_quotes_are_in_the_importer(self):
        source = read(os.path.join(SHARED_DIR, "CimianImporter.py"))
        for fragment in ("WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on.", "Would write ",
                         "No template: the pkginfo is built from the inputs.", "Nothing new: ", "Published ",
                         "Build the catalogs with makecatalogs.", "The Cimian repository is not a folder"):
            self.assertIn(fragment, source)


class ChainTests(_pcman_support.ToolTestCase):
    """The chain with the package tool's stand-in: the real ChecksumVerifier hashes the file, the provider's
    label reaches the importer through the recipe's own arguments."""

    def chain_env(self, installer, label="4.33"):
        run = {"pathname": installer, "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        values = {"%pathname%": installer, "%PCMAN_TEMPLATE%": load(PCMAN)["Input"]["PCMAN_TEMPLATE"], "%version%": label}
        env = {"pathname": installer, "pcman_root": self.root, "pcman_dry_run": False, "pcman_path": self.msi_bin}
        env.update({k: v for k, v in verifier.env.items() if k.startswith("checksum_")})
        for name, value in load(PCMAN)["Process"][0]["Arguments"].items():
            env[name] = values.get(value, value)
        return env

    def test_the_label_reaches_the_tool_as_written(self):
        env = self.chain_env(self.exe, label="4.09")
        self.assertEqual(env["pcman_version"], "4.09")
        _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        argv = self.record()["argv"]
        self.assertEqual(argv[argv.index("--version") + 1], "4.09")

    def test_the_chain_counts_as_verified_and_nothing_is_warned(self):
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, self.chain_env(self.exe))
        self.assertIs(processor.env["pcman_repo_changed"], True)
        self.assertEqual([m for level, m in processor.message_levels if m.startswith("WARNING:")], [])
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published")

    def test_the_chain_is_refused_for_another_file(self):
        env = self.chain_env(self.exe)
        other = os.path.join(self.downloads, "other.exe")
        with open(other, "wb") as handle:
            handle.write(b"not the file that was verified")
        env["pathname"] = other
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        self.assertIn("not the file whose checksum was verified", str(caught.exception))
        self.assertFalse(self.was_run())


class CimianChainTests(_win_support.RepoTestCase):
    """The chain with the real CimianImporter and a temporary repository."""

    def run_chain(self, installer, label="4.33", **extra):
        recipe = load(CIMIAN)
        run = {"pathname": installer, "version": label, "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        run.update({key: value for key, value in verifier.env.items() if key.startswith("checksum_")})
        run.update(recipe["Input"])
        run["CIMIAN_NAME"] = "Example-Chain"
        arguments = {}
        for name, value in recipe["Process"][0]["Arguments"].items():
            for variable in re.findall(r"%([A-Za-z_]+)%", value):
                value = value.replace("%" + variable + "%", str(run[variable]))
            arguments[name] = value
        env = dict(run)
        env.update({"cimian_repo": self.repo, "cimian_dry_run": False, "cimian_path": self.msi_bin})
        env.update(arguments)
        env.update(extra)
        return _win_support.run_processor(_win_support.cimian.CimianImporter, env)

    @_win_support.needs_yaml
    def test_the_chain_publishes_the_label_into_an_empty_repository(self):
        processor, messages = self.run_chain(self.exe)
        self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published")
        self.assertEqual(processor.env["cimian_version_imported"], "4.33")
        new = self.read_pkginfo("Example-Chain-4.33.yaml")
        self.assertEqual(new["display_name"], "WizTree")
        self.assertEqual(new["developer"], "Antibody Software")
        self.assertEqual(new["installer"]["type"], "exe")
        self.assertEqual(new["installer"]["hash"], _win_support.sha256_hex(self.exe))

    @_win_support.needs_yaml
    def test_a_label_with_a_leading_zero_is_kept(self):
        processor, _ = self.run_chain(self.exe, label="4.09")
        self.assertEqual(processor.env["cimian_version_imported"], "4.09")

    @_win_support.needs_yaml
    def test_a_second_run_with_the_same_file_has_nothing_new(self):
        self.run_chain(self.exe)
        before = self.repo_tree()
        processor, _ = self.run_chain(self.exe)
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertEqual(self.repo_tree(), before)


if __name__ == "__main__":
    unittest.main()
