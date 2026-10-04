"""Tests of the two Temurin JRE 8 recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names one of our
processors is compared with what that processor declares: the shared ones
(see ../../Win-SharedProcessors) and this folder's own AdoptiumInfoProvider
(tested in test_info_provider.py). The shared folder's tests are run separately.
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
for folder in (SHARED_TESTS_DIR, RECIPE_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import _win_support  # noqa: E402,F401  (installs the autopkglib stand-in, imports the processors)
import test_public_repository as shared_hygiene  # noqa: E402
import AdoptiumInfoProvider as own  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
OWN_PROCESSOR = "AdoptiumInfoProvider"
DOWNLOAD = os.path.join(RECIPE_DIR, "TemurinJRE8-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "TemurinJRE8.cimian.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
# Processors that are part of AutoPkg itself.
CORE_PROCESSORS = ("URLDownloader", "EndOfCheckPhase")
# Required inputs that a recipe must NOT pass: they come from AutoPkg's
# preferences or the override on the machine that runs it.
SUPPLIED_BY_THE_MACHINE = {"PcmanImporter": {"pcman_root"}}
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir", "pcman_timeout")
# What the earlier steps leave in the run (a step reads these without an argument).
SET_BY_CORE_STEPS = {"pathname", "url", "version", "expected_sha256"}


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def processor_classes():
    import importlib
    classes = {OWN_PROCESSOR: own.AdoptiumInfoProvider}
    for name in ("PcmanImporter", "ChecksumVerifier", "GitHubAssetDigest"):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def named_steps(recipe):
    """(processor name without the shared prefix, arguments) of every step
    that is ours: a shared processor or this folder's own."""
    for step in recipe["Process"]:
        name = step["Processor"]
        if name.startswith(SHARED_PREFIX):
            yield name[len(SHARED_PREFIX):], step.get("Arguments", {})
        elif name == OWN_PROCESSOR:
            yield name, step.get("Arguments", {})


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
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.TemurinJRE8-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.TemurinJRE8")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [
            OWN_PROCESSOR, "URLDownloader", "EndOfCheckPhase", SHARED_PREFIX + "ChecksumVerifier",
        ])

    def test_the_cimian_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "PcmanImporter"])

    def test_the_hard_check_comes_after_the_download_and_before_anything_is_imported(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertLess(steps.index("URLDownloader"), steps.index(SHARED_PREFIX + "ChecksumVerifier"))
        self.assertEqual(steps[-1], SHARED_PREFIX + "ChecksumVerifier")

    def test_the_provider_arguments_are_the_recipes_inputs(self):
        recipe = load(DOWNLOAD)
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {
            "temurin_feature_version": "%TEMURIN_FEATURE_VERSION%",
            "temurin_image_type": "%TEMURIN_IMAGE_TYPE%",
            "temurin_architecture": "%TEMURIN_ARCHITECTURE%",
            "temurin_os": "%TEMURIN_OS%",
        })
        for value in args.values():
            match = re.fullmatch(r"%([A-Z_]+)%", value)
            self.assertTrue(match)
            self.assertIn(match.group(1), recipe["Input"])

    def test_the_defaults_of_the_recipe_are_the_defaults_of_the_processor(self):
        inputs = load(DOWNLOAD)["Input"]
        flags = own.AdoptiumInfoProvider.input_variables
        self.assertEqual(inputs["NAME"], "TemurinJRE8")
        self.assertEqual(inputs["TEMURIN_FEATURE_VERSION"], "8")
        self.assertEqual(inputs["TEMURIN_FEATURE_VERSION"], flags["temurin_feature_version"]["default"])
        self.assertEqual(inputs["TEMURIN_IMAGE_TYPE"], "jre")
        self.assertEqual(inputs["TEMURIN_IMAGE_TYPE"], flags["temurin_image_type"]["default"])
        self.assertEqual(inputs["TEMURIN_ARCHITECTURE"], "x64")
        self.assertEqual(inputs["TEMURIN_ARCHITECTURE"], flags["temurin_architecture"]["default"])
        self.assertEqual(inputs["TEMURIN_OS"], "windows")
        self.assertEqual(inputs["TEMURIN_OS"], flags["temurin_os"]["default"])
        self.assertIn(inputs["TEMURIN_IMAGE_TYPE"], own.IMAGE_TYPES)
        self.assertIn(inputs["TEMURIN_ARCHITECTURE"], own.ARCHITECTURES)
        self.assertIn(inputs["TEMURIN_OS"], own.OPERATING_SYSTEMS)

    def test_the_downloader_gets_its_address_from_the_provider(self):
        """URLDownloader needs `url`. It is set by the provider and passed as no argument."""
        step = load(DOWNLOAD)["Process"][1]
        self.assertEqual(step["Processor"], "URLDownloader")
        self.assertNotIn("Arguments", step)  # the cached file keeps the name of the link, which ends in .msi
        self.assertIn("url", own.AdoptiumInfoProvider.output_variables)

    def test_the_checksum_arguments_are_the_pages_hash(self):
        steps = dict(named_steps(load(DOWNLOAD)))
        self.assertEqual(steps["ChecksumVerifier"],
                         {"pathname": "%pathname%", "expected_sha256": "%expected_sha256%"})
        self.assertIn("expected_sha256", own.AdoptiumInfoProvider.output_variables)

    def test_every_variable_a_recipe_uses_is_an_input_or_set_by_an_earlier_step(self):
        for path in (DOWNLOAD, CIMIAN):
            recipe = load(path)
            known = set(recipe["Input"]) | SET_BY_CORE_STEPS
            if path == CIMIAN:
                known |= set(load(DOWNLOAD)["Input"])
            for step in recipe["Process"]:
                for value in step.get("Arguments", {}).values():
                    for name in re.findall(r"%([A-Za-z_]+)%", str(value)):
                        with self.subTest(recipe=os.path.basename(path), variable=name):
                            self.assertIn(name, known)

    def test_the_inputs_of_the_cimian_recipe(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], "TemurinJRE8")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "temurin")
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%"})

    def test_the_template_does_not_keep_the_name_of_the_item_it_replaces(self):
        """The other recipes keep the name of the Chocolatey item they replace. This one does
        not: Temurin is a different product than Oracle's JRE, so the owner decided on
        2026-10-02 that it gets its own name, `temurin`, and Oracle's item `jre8` goes."""
        template = load(CIMIAN)["Input"]["PCMAN_TEMPLATE"]
        self.assertEqual(template, "temurin")
        self.assertNotEqual(template, "jre8")
        self.assertNotIn("jre8", read(DOWNLOAD))
        description = re.sub(r"\s+", " ", load(CIMIAN)["Description"])
        self.assertIn("another product than Oracle's JRE", description)
        self.assertNotIn("jre8", description.replace("Oracle's item jre8", ""))

    def test_no_pcman_version_in_an_msi_recipe(self):
        """For an MSI the package tool takes the MSI's own ProductVersion. The project's
        release name (jdk8u504-b01) is not a label at all."""
        for path in (DOWNLOAD, CIMIAN):
            self.assertNotIn("pcman_version", read(path))
        for step in load(CIMIAN)["Process"]:
            self.assertNotIn("pcman_version", step.get("Arguments", {}))
            self.assertNotIn("%version%", str(step.get("Arguments", {})))

    def test_no_stop_on_an_unchanged_download_and_no_latest_only(self):
        for path in (DOWNLOAD, CIMIAN):
            text = read(path)
            self.assertNotIn("StopProcessingIf", text)
            self.assertNotIn("latest_only", text)

    def test_no_blocking_applications(self):
        for path in (DOWNLOAD, CIMIAN):
            self.assertNotIn("blocking_applications", read(path))

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in (DOWNLOAD, CIMIAN):
            text = read(path)
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text)
            for name in ("catalogs", "catalog", "pcman_catalogs", "path", "repo", "directory"):
                self.assertNotIn("<key>%s</key>" % name, text)

    def test_no_value_of_a_recipe_is_a_path_or_a_catalog(self):
        for path in (DOWNLOAD, CIMIAN):
            recipe = load(path)
            values = list(recipe["Input"].values())
            for step in recipe["Process"]:
                values.extend(step.get("Arguments", {}).values())
            for value in values:
                if not isinstance(value, str) or value.startswith("https://"):
                    continue
                with self.subTest(path=os.path.basename(path), value=value):
                    self.assertFalse(value.startswith(("/", "~", ".")), value)
                    self.assertNotIn("\\", value)
                    self.assertNotIn("Production", value)
                    self.assertNotIn("Testing", value)

    def test_the_download_has_no_hash_written_into_it(self):
        for path in (DOWNLOAD, CIMIAN):
            self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", read(path)))

    def test_the_description_says_what_a_reader_must_know(self):
        text = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        self.assertIn("SHA-256", text)
        self.assertIn("AdoptiumInfoProvider", text)
        self.assertIn("The layout of the API's answer was read on 2026-10-02", text)
        self.assertIn("the recipe was NOT run with AutoPkg", text)
        self.assertIn("NOT downloaded or compared with the hash", text)
        cimian = re.sub(r"\s+", " ", load(CIMIAN)["Description"])
        self.assertIn("MSI's own ProductVersion", cimian)
        self.assertIn("The owner decided on 2026-10-02 that Temurin replaces Oracle's JRE 8", cimian)
        self.assertIn("under the new item name temurin", cimian)
        self.assertIn("must be made from a Temurin MSI first", cimian)
        self.assertIn("must remove Oracle's JRE 8 before the install", cimian)
        self.assertIn("The template temurin must be made from a Temurin MSI first", cimian)
        self.assertIn("another product than Oracle's JRE", cimian)
        self.assertIn("dry run", cimian)
        self.assertIn("pcman_dry_run", cimian)

    def test_no_description_claims_a_rehearsal(self):
        for path in (DOWNLOAD, CIMIAN):
            text = re.sub(r"\s+", " ", load(path)["Description"])
            self.assertNotRegex(text, r"(?i)\brehearsed\b")
            self.assertNotRegex(text, r"(?i)\bwas tried\b")


class ProcessorTests(unittest.TestCase):
    def test_every_named_processor_exists(self):
        for path in (DOWNLOAD, CIMIAN):
            for step in load(path)["Process"]:
                name = step["Processor"]
                if name.startswith(SHARED_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, name[len(SHARED_PREFIX):] + ".py")), name)
                elif name not in CORE_PROCESSORS:
                    self.assertTrue(os.path.isfile(os.path.join(RECIPE_DIR, name + ".py")), name)

    def test_the_own_processor_has_no_prefix_and_a_class_of_the_same_name(self):
        text = read(os.path.join(RECIPE_DIR, OWN_PROCESSOR + ".py"))
        self.assertIn("class %s(Processor):" % OWN_PROCESSOR, text)

    def test_the_stub_identifier_is_the_prefix_of_the_processor_names(self):
        stub = load(os.path.join(SHARED_DIR, "SharedProcessors.recipe"))
        self.assertEqual(stub["Identifier"] + "/", SHARED_PREFIX)

    def test_every_argument_is_a_declared_input(self):
        classes = processor_classes()
        for path in (DOWNLOAD, CIMIAN):
            for name, args in named_steps(load(path)):
                for key in args:
                    with self.subTest(recipe=os.path.basename(path), processor=name, argument=key):
                        self.assertIn(key, classes[name].input_variables)

    def test_every_required_input_is_passed_or_comes_from_the_machine(self):
        classes = processor_classes()
        for path in (DOWNLOAD, CIMIAN):
            for name, args in named_steps(load(path)):
                for key, flags in classes[name].input_variables.items():
                    if not flags.get("required") or "default" in flags:
                        continue
                    with self.subTest(recipe=os.path.basename(path), processor=name, input=key):
                        if key in SUPPLIED_BY_THE_MACHINE.get(name, ()):
                            self.assertNotIn(key, args)
                        else:
                            self.assertIn(key, args)

    def test_every_input_of_the_own_processor_has_the_flags_that_autopkg_reads(self):
        for name, flags in own.AdoptiumInfoProvider.input_variables.items():
            self.assertIn("required", flags, name)
            self.assertIn("description", flags, name)


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
            "TemurinJRE8-Win.download.recipe", "TemurinJRE8.cimian.recipe", "AdoptiumInfoProvider.py",
            "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
            os.path.join("tests", "test_info_provider.py"),
            os.path.join("tests", "adoptium_latest_excerpt.json"),
        ]))

    def test_the_hand_written_excerpt_is_small(self):
        self.assertLess(os.path.getsize(os.path.join(TESTS_DIR, "adoptium_latest_excerpt.json")), 4000)

    def test_no_recipe_no_readme_and_no_provider_holds_a_hash(self):
        for path in (DOWNLOAD, CIMIAN, README, os.path.join(RECIPE_DIR, OWN_PROCESSOR + ".py")):
            with self.subTest(path=os.path.basename(path)):
                self.assertIsNone(re.search(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", read(path)))


class ReadmeTests(unittest.TestCase):
    """The README must not teach what the rehearsal of 7-Zip showed to be wrong."""

    def setUp(self):
        self.raw = read(README)
        self.text = re.sub(r"\s+", " ", self.raw)

    def test_every_make_override_command_names_an_override_folder(self):
        commands = list(re.finditer(r"autopkg make-override([^`\n]*(?:\n[ \t]+--[^\n`]*)?)", self.raw))
        self.assertTrue(commands)
        for match in commands:
            self.assertIn("--override-dir=", match.group(1))

    def test_no_run_of_a_recipe_identifier(self):
        runs = list(re.finditer(r"autopkg run([^`\n]*)", self.raw))
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
                    r"<the Windows overrides folder>/TemurinJRE8\.cimian\.recipe$",
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

    def test_the_steps_of_the_model_folders_are_there(self):
        for needle in ("pcman catalogs", "pcman versions <the template's name>", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string", "make-override"):
            self.assertIn(needle, self.text)

    def test_the_first_import_has_no_version_and_names_the_flags_of_the_package_tool(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        self.assertTrue(match)
        command = re.sub(r"\s+", " ", match.group(1))
        self.assertIn("<path of OpenJDK8U-jre_x64_windows_hotspot_8u504b01.msi>", command)
        self.assertIn("--name temurin ", command)
        self.assertNotIn("--version", command)  # an MSI has its own version
        self.assertNotIn("--install-arguments", command)  # the package tool knows the arguments of an MSI
        for flag in ("--display-name", "--category", "--developer", "--description", "--architectures x64",
                     "--no-prompt"):
            self.assertIn(flag, command)
        self.assertIn("There is no `--version`: the package tool takes the MSI's own version", self.text)

    def test_the_status_line_says_what_was_fetched_and_what_was_not(self):
        """The models say "Rehearsed on ...". This folder was NOT run with AutoPkg. The writer fetched
        some facts of the source on 2026-10-02: the README opens with a bold paragraph that lists what
        was verified and what is still not."""
        opening = "**Status. NOT rehearsed with AutoPkg. Some facts of the source were fetched by the writer on 2026-10-02:"
        start = self.raw.index(opening)
        self.assertLess(start, self.raw.index("| Recipe |"))
        self.assertLess(self.raw.index("# Win-TemurinJRE8"), start)
        end = self.raw.index("**\n", start)
        paragraph = re.sub(r"\s+", " ", self.raw[start:end + 2])
        self.assertTrue(paragraph.startswith(opening))
        self.assertTrue(paragraph.endswith("**"))
        verified, _, not_established = paragraph.partition("NOT established:")
        self.assertTrue(not_established)
        for needle in ("no run of AutoPkg was made",
                       "https://api.adoptium.net/v3/assets/latest/8/hotspot?os=windows&architecture=x64&image_type=jre&vendor=eclipse",
                       "answered 200 with no redirect", "a JSON array of one element",
                       "`release_name` `jdk8u504-b01`", "`version.semver` `8.0.504+1`",
                       "`image_type` is `jre`", "`os` is `windows`", "`architecture` is `x64`",
                       "`OpenJDK8U-jre_x64_windows_hotspot_8u504b01.msi`", "a size of 32010240",
                       "https://github.com/adoptium/temurin8-binaries/releases/download/",
                       "a `checksum` that is a SHA-256 (64 hex digits)",
                       "a `package`, which is a zip file that the processor never takes",
                       "ran end to end on the saved real answer",
                       "the `version` `jdk8u504-b01` and an installer SHA-256 beginning 087a6724"):
            self.assertIn(needle, verified)
        for needle in ("that the file at that link can be downloaded and that its hash equals the checksum",
                       "the writer did not request GitHub",
                       "`URLDownloader` follows without trouble",
                       "what the API answers for another feature version, image type or architecture (never read)",
                       "the MSI's own ProductVersion, its UpgradeCode, its features and its properties",
                       "that the upgrade code differs from Oracle's JRE",
                       "what kind of item `jre8` is today", "`pcman catalogs`", "any run with AutoPkg",
                       "the Chocolatey item file of Oracle's JRE",
                       "how Oracle's JRE 8 is removed on a PC, and whether a preinstall step of the template can do it, "
                       "is NOT established and is read on the test PC first"):
            self.assertIn(needle, not_established)
        self.assertIn("The owner decided on 2026-10-02 that Temurin replaces Oracle's JRE 8 "
                      "(the new item is named `temurin`)", paragraph)
        self.assertNotIn("has NOT been taken", paragraph)
        for needle in ("wrote by hand after the real answer of 2026-10-02, with made-up digits for the checksums",
                       "The first run on the build Mac is the check of everything that is NOT established",
                       "STOP: nothing was written", "correct the processor or the recipe",
                       "and only then look at the trust information",
                       "Never accept new trust information first"):
            self.assertIn(needle, paragraph)
        self.assertNotRegex(self.text, r"Rehearsed on 20")
        self.assertNotRegex(self.text, r"(?i)\bwas rehearsed\b")
        self.assertNotIn("the network was closed", self.text)
        # No real digest in the status: only made-up ones in the tests.
        self.assertIsNone(re.search(r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", paragraph))

    def test_the_status_is_before_the_product_decision_and_the_steps(self):
        self.assertLess(self.raw.index("**Status."), self.raw.index("## The product decision"))
        self.assertLess(self.raw.index("## The product decision"), self.raw.index("## Run every override"))

    def test_the_product_decision_is_the_owners_with_its_date_and_the_readme_says_what_follows(self):
        i = self.raw.index("## The product decision")
        section = re.sub(r"\s+", " ", self.raw[i:self.raw.index("## What the checks prove")])
        for needle in ("**The owner decided on 2026-10-02 that Eclipse Temurin replaces Oracle's JRE 8, "
                       "and that the new item is named `temurin`.**",
                       "The item `jre8` installs Oracle's JRE 8 today",
                       "needs a subscription",
                       "The template `temurin` is made from the Temurin MSI",
                       "The recipe's default `PCMAN_TEMPLATE` is `temurin`",
                       "Temurin is a different product than Oracle's JRE, so it gets its own name and does not keep the name `jre8`",
                       "the manifests that list `jre8` change to `temurin` (two lines in the content repository, done there)",
                       "every item of the package tool whose `requires:` names `jre8` is changed to `temurin` by the owner "
                       "before the catalogs are built",
                       "Oracle's item `jre8` (its item file and its pkginfo) is removed in the same commit as the new template",
                       "Temurin has another UpgradeCode than Oracle's JRE (from the writer's knowledge, NOT read in an MSI)",
                       "**beside it, not instead of it**",
                       "So the template `temurin` must remove Oracle's JRE 8 first: a preinstall step of the template, "
                       "as the VLC template removes the EXE edition",
                       "That is the template's task, not this recipe's",
                       "How Oracle's JRE 8 is removed on a PC (its uninstaller, its product code, whether it leaves "
                       "files or registry values) is NOT established: read it on the test PC first",
                       "The first import makes the new template under the name `temurin`",
                       "The Chocolatey item file of Oracle's JRE (`jre8`) is removed in the same commit as the new template, "
                       "as for 7-Zip"):
            self.assertIn(needle, section)
        for old in ("has not decided", "until the owner decides", "the name that the owner chooses",
                    "Do not run the first import into the name `jre8` while", "keeps the name `jre8`",
                    "stay unchanged", "no manifest changes"):
            self.assertNotIn(old, self.text)
        self.assertIn("The owner decided on 2026-10-02 that Temurin replaces Oracle's JRE 8, and that the new item "
                      "is named `temurin`", self.text.split("## The product decision")[0])
        a = re.sub(r"\s+", " ", self.raw[self.raw.index("3. **The template item"):self.raw.index("## b.")])
        self.assertIn("The template item `temurin`, made once by a first import, in the same commit that removes "
                      "Oracle's item `jre8`", a)
        self.assertIn("--name temurin", a)
        self.assertNotIn("--name jre8", self.text)
        self.assertIn("`PCMAN_TEMPLATE` is `temurin`", self.text)

    def test_nothing_in_the_readme_claims_a_run_that_did_not_happen(self):
        for needle in ("Expected, from the code and the rehearsals of the other folders, NOT printed by this recipe yet",
                       "(Not run: the lines of the output are not known.)",
                       "Expected (not run)"):
            self.assertIn(needle, self.text)
        self.assertNotIn("The rehearsal printed", self.text)
        self.assertNotRegex(self.text, r"(?<!NOT )(?i:rehearsed with)")

    def test_the_readme_says_how_the_file_is_checked_against_the_answer(self):
        for needle in ("`binary.os`, `binary.architecture` and `binary.image_type` must equal the inputs",
                       "an array of exactly one element",
                       "A redirect is not followed", "`checksum_verified`",
                       "a `name` that ends in `.msi`",
                       "`https://github.com/adoptium/temurin<feature>-binaries/releases/download/`",
                       "(no query, no fragment)",
                       "is never taken"):
            self.assertIn(needle, self.text)

    def test_the_name_check_and_the_parent_check_are_in_step_b(self):
        b = self.raw.index("## b.")
        c = self.raw.index("## c.")
        step = self.raw[b:c]
        self.assertIn("autopkg list-recipes | grep -i TemurinJRE8-Win", step)
        self.assertIn("autopkg list-recipes | grep -i TemurinJRE8.cimian", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.download.TemurinJRE8-Win`",
                      re.sub(r"\s+", " ", step))

    def test_the_readme_says_that_the_version_is_the_msis_own_and_not_established(self):
        self.assertIn("For an MSI the package tool takes the MSI's own ProductVersion", self.text)
        self.assertIn("is NOT established", self.text)
        self.assertIn("nothing is passed by the recipe", self.text)

    def test_the_readme_says_that_a_redirect_is_a_stop(self):
        self.assertIn("If the line says that the API answered with a redirect, stop and tell the owner", self.text)

    def test_the_readme_has_no_label_that_looks_like_a_version_the_tool_never_gave(self):
        """The writer does not know the MSI's own version. No example label is written."""
        self.assertNotIn("Published temurin", self.text)
        self.assertIn("<the MSI's own version>", self.text)


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
