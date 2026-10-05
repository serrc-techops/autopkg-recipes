"""Tests of the two XCP-ng Center recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names one of our shared
processors is compared with what that processor declares (see
../../Win-SharedProcessors). The shared folder's tests are run separately.
"""
import json
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
if SHARED_TESTS_DIR not in sys.path:
    sys.path.insert(0, SHARED_TESTS_DIR)

if PCMAN_TESTS_DIR not in sys.path:
    sys.path.insert(0, PCMAN_TESTS_DIR)

import _win_support  # noqa: E402,F401  (installs the autopkglib stand-in, imports the processors)
import _pcman_support  # noqa: E402,F401  (the stand-in for the package tool, and its processor)
import test_public_repository as shared_hygiene  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
# The pattern of the first run with AutoPkg 2.9.0 (2026-10-04): the name that the project used up to 2020.
OLD_PATTERN = r"XCP-ng-Center-(?!99\.)[0-9.]+\.msi$"
PATTERN = r"XCP-ng\.Center\.msi$"
# Names, sizes and digest flags of the newest 12 releases, read from GitHub on 2026-10-04. A version of four
# numbers is written with `_dot_` for each dot in the file (see its note), and put back here.
RELEASES = os.path.join(TESTS_DIR, "releases_excerpt.json")
DOWNLOAD = os.path.join(RECIPE_DIR, "XCPngCenter-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "XCPngCenter.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "XCPngCenter.pcman.recipe")
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
    for name in ("PcmanImporter", "CimianImporter", "ChecksumVerifier", "GitHubAssetDigest"):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def releases():
    with open(RELEASES, "r", encoding="utf-8") as handle:
        text = handle.read().replace("_dot_", ".")
    return json.loads(text)["releases"]


def selected(pattern, include_prereleases=False):
    """How the download recipe chooses its file in AutoPkg 2.9.0 (`GitHubReleasesInfoProvider.py`,
    `select_asset`): the releases in the order that GitHub lists them (newest first), a pre-release
    skipped unless `include_prereleases` is true, and in a release the first asset whose name the
    pattern matches from its start (`re.match`). Returns (tag, asset name, digest recorded) or None."""
    for release in releases():
        if release["prerelease"] and not include_prereleases:
            continue
        for asset in release["assets"]:
            if re.match(pattern, asset["name"]):
                return release["tag_name"], asset["name"], asset["digest_recorded"]
    return None


def shared_steps(recipe):
    """The steps that name a processor of this repository, of either folder: (name, arguments)."""
    for step in recipe["Process"]:
        for prefix in (SHARED_PREFIX, PCMAN_PREFIX):
            if step["Processor"].startswith(prefix):
                yield step["Processor"][len(prefix):], step.get("Arguments", {})


class RecipeFileTests(unittest.TestCase):
    def test_both_files_are_valid_property_lists(self):
        for path in (DOWNLOAD, PCMAN):
            with self.subTest(path=os.path.basename(path)):
                result = subprocess.run(["plutil", "-lint", path], capture_output=True, text=True) \
                    if os.path.exists("/usr/bin/plutil") else None
                if result is not None:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                recipe = load(path)
                for key in ("Description", "Identifier", "Input", "MinimumVersion", "Process"):
                    self.assertIn(key, recipe)

    def test_identifiers_and_parent(self):
        download, cimian = load(DOWNLOAD), load(PCMAN)
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.XCPngCenter-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".pcman.XCPngCenter")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, ["GitHubReleasesInfoProvider", "URLDownloader", "EndOfCheckPhase"])

    def test_the_pcman_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(PCMAN)["Process"]]
        self.assertEqual(steps, [PCMAN_PREFIX + "PcmanImporter"])

    def test_the_provider_arguments(self):
        args = load(DOWNLOAD)["Process"][0]["Arguments"]
        self.assertEqual(args["github_repo"], "xcp-ng/xenadmin")
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

    def test_the_default_pattern_matches_the_msi_and_not_the_others(self):
        """The names are those of GitHub's release list of 2026-10-04 (releases_excerpt.json). A dotted name of
        four numbers is built, not written, so that no file of the folder holds text that looks like an IPv4
        address."""
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        old_version = ".".join(["20", "04", "01", "33"])
        self.assertTrue(pattern.match("XCP-ng.Center.msi"))
        for name in ("XCP-ng.Center.zip", "XCP-ng.Center_pdb.zip", "XCP-ng.Center.msi.sig", "XCP-ng.Center.exe",
                     "XCP-ng-Center-%s.msi" % old_version, "installer-xcp-ng-nightly-%s.msi" % ".".join(["99"] * 3 + ["28"]),
                     "old-XCP-ng.Center.msi", "XCP-ng_Center.msi", "XCP-ng.Center.msix", "xcp-ng.center.msi"):
            self.assertIsNone(pattern.match(name), name)

    def test_only_the_newest_release_has_a_file_that_the_pattern_takes(self):
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        self.assertEqual(len(releases()), 12)
        taken = {release["tag_name"]: [a["name"] for a in release["assets"] if pattern.match(a["name"])] for release in releases()}
        self.assertEqual({tag: hits for tag, hits in taken.items() if hits}, {"v25.04": ["XCP-ng.Center.msi"]})

    def test_the_recipe_takes_the_newest_release_where_the_old_pattern_went_back_to_2020(self):
        """The first run (2026-10-04) took the installer of v20.04.01.33, a file of December 2020, and stopped
        because GitHub records no digest for it: the old pattern matches no file of any release after that one,
        and AutoPkg goes on to the next release when none matches."""
        old_tag = "v" + ".".join(["20", "04", "01", "33"])
        tag, name, digest = selected(OLD_PATTERN)
        self.assertEqual(tag, old_tag)
        self.assertEqual(name, "XCP-ng-Center-" + ".".join(["20", "04", "01", "33"]) + ".msi")
        self.assertFalse(digest)
        tag, name, digest = selected(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        self.assertEqual((tag, name), ("v25.04", "XCP-ng.Center.msi"))
        self.assertEqual(tag, [r["tag_name"] for r in releases() if not r["prerelease"]][0])

    def test_the_old_pattern_took_nothing_of_the_nightly_builds_and_the_new_one_cannot(self):
        """The `99.` guard of the old pattern is not needed: the nightly builds are pre-releases, and no file of
        theirs has the name that the new pattern takes."""
        nightly = [r for r in releases() if r["tag_name"].lstrip("v.").startswith("99.")]
        self.assertEqual(len(nightly), 4)
        for release in nightly:
            self.assertTrue(release["prerelease"])
            for asset in release["assets"]:
                self.assertIsNone(re.match(PATTERN, asset["name"]), asset["name"])
        self.assertEqual(selected(PATTERN, include_prereleases=True)[0], "v25.04")

    def test_no_asset_of_the_excerpt_has_a_digest_so_no_digest_step_could_run(self):
        """GitHub records no digest for any asset of the 12 releases: the recipe has no digest step, and the
        shared importer refuses a real run of the chain."""
        for release in releases():
            for asset in release["assets"]:
                self.assertFalse(asset["digest_recorded"], (release["tag_name"], asset["name"]))

    def test_searching_a_name_or_matching_it_from_its_start_gives_the_same_answer(self):
        pattern = re.compile(load(DOWNLOAD)["Input"]["SEARCH_PATTERN"])
        for release in releases():
            for asset in release["assets"]:
                self.assertEqual(bool(pattern.search(asset["name"])), bool(pattern.match(asset["name"])), asset["name"])

    def test_the_inputs_of_the_pcman_recipe(self):
        recipe = load(PCMAN)
        self.assertEqual(recipe["Input"]["NAME"], "XCPngCenter")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "xcp-ng-center")
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%"})

    def test_the_template_keeps_the_name_of_the_item_it_replaces(self):
        self.assertEqual(load(PCMAN)["Input"]["PCMAN_TEMPLATE"], "xcp-ng-center")

    def test_no_pcman_version_in_an_msi_recipe(self):
        """For an MSI the package tool takes the MSI's own ProductVersion."""
        for path in (DOWNLOAD, PCMAN):
            with open(path, "r", encoding="utf-8") as handle:
                self.assertNotIn("pcman_version", handle.read())
        for step in load(PCMAN)["Process"]:
            self.assertNotIn("pcman_version", step.get("Arguments", {}))
            self.assertNotIn("%version%", str(step.get("Arguments", {})))

    def test_there_is_no_digest_and_no_checksum_step(self):
        """GitHub records no digest for the file: a step that asked for one would stop every run. The two steps
        can come back when a release has a digest (the README says so)."""
        names = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(names, ["GitHubReleasesInfoProvider", "URLDownloader", "EndOfCheckPhase"])
        self.assertEqual(list(shared_steps(load(DOWNLOAD))), [])

    def test_no_stop_on_an_unchanged_download_and_no_latest_only(self):
        for path in (DOWNLOAD, PCMAN):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.assertNotIn("StopProcessingIf", text)
            self.assertNotIn("latest_only", text)

    def test_no_blocking_applications_and_no_hash_in_a_recipe(self):
        for path in (DOWNLOAD, PCMAN):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.assertNotIn("blocking_applications", text)
            self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", text))

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in (DOWNLOAD, PCMAN):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text)

    def test_the_description_says_what_a_reader_must_know(self):
        download = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        for needle in ("newest non-pre-release", "matching file", "GitHub records no digest",
                       "The release list was read on 2026-10-04", "v25.04 (published 2025-04-29)",
                       "A digest step (GitHubAssetDigest, then ChecksumVerifier) can come back",
                       "took the installer of release", "a file of December 2020",
                       "AutoPkg takes the first release that has a matching file however old it is"):
            self.assertIn(needle, download)
        for claim in ("Rehearsed", "rehearsed on", "was rehearsed", "from the writer's knowledge", "nobody has read"):
            self.assertNotIn(claim, download)
        cimian = re.sub(r"\s+", " ", load(PCMAN)["Description"])
        self.assertIn("MSI's own ProductVersion", cimian)
        self.assertIn("dry run", cimian)
        self.assertIn("pcman_dry_run", cimian)
        self.assertNotIn("ehearsed", cimian)

    def test_no_value_of_a_recipe_is_a_path_or_a_catalog(self):
        for path in (DOWNLOAD, PCMAN):
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


class NotVerifiedTests(unittest.TestCase):
    """The download has no hard check. The recipes and the README must say so first, and nothing may invent a
    check."""

    def first_sentence(self, text):
        return re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]

    def test_the_descriptions_begin_by_saying_that_nothing_is_verified(self):
        self.assertTrue(load(DOWNLOAD)["Description"].startswith("This download is NOT verified yet:"))
        for path in (CIMIAN, PCMAN):
            self.assertTrue(load(path)["Description"].startswith("This import is NOT verified yet:"), path)

    def test_the_download_description_names_the_missing_checks(self):
        sentence = self.first_sentence(load(DOWNLOAD)["Description"])
        for needle in ("GitHub records no digest", "no hash", "signature"):
            self.assertIn(needle, sentence)

    def test_the_descriptions_say_that_a_real_run_is_refused_unless_the_override_allows_it(self):
        for path, allowance in ((DOWNLOAD, "cimian_allow_unverified"), (CIMIAN, "cimian_allow_unverified"),
                                (PCMAN, "pcman_allow_unverified")):
            text = re.sub(r"\s+", " ", load(path)["Description"])
            with self.subTest(path=os.path.basename(path)):
                self.assertIn(allowance, text)
                self.assertIn("refuses a real run" if path == DOWNLOAD else "A real run is refused", text)
                self.assertIn("published, NOT verified" if path != DOWNLOAD else "unless the override sets", text)

    def test_no_recipe_sets_the_allowance_or_a_verified_flag_and_no_step_checks_the_file(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = _text(path)
            self.assertNotIn("<key>pcman_allow_unverified</key>", text)
            self.assertNotIn("<key>cimian_allow_unverified</key>", text)
            self.assertNotIn("<key>checksum_verified</key>", text)
            self.assertNotIn("<key>expected_sha256</key>", text)
            self.assertNotIn("signature_verified", text)
            self.assertNotIn("CodeSignatureVerifier", text)
            for step in load(path)["Process"]:
                self.assertNotIn(step["Processor"].rsplit("/", 1)[-1], ("ChecksumVerifier", "GitHubAssetDigest"))
            self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", text))

    def test_the_readme_opens_with_a_bold_status_line_that_says_so(self):
        raw = _text(os.path.join(RECIPE_DIR, "README.md"))
        lines = [line for line in raw.splitlines() if line.strip()]
        self.assertTrue(lines[0].startswith("# "))
        status = lines[2] if lines[1].startswith("A Windows recipe pair") else lines[1]
        self.assertTrue(status.startswith("**Status."), status[:60])
        self.assertTrue(status.endswith("**"))
        for needle in ("NOT verified", "a check of the signature is not built", "REFUSES a real run", "pcman_allow_unverified",
                       "Do not set it before the signature check exists",
                       "pcman import <file> --template xcp-ng-center", "no `--version` for an MSI",
                       "the real run of the override of `XCPngCenter.pcman`", "was REFUSED"):
            self.assertIn(needle, status)
        self.assertNotIn("has NOT been run by anyone", status)

    def test_the_readme_says_what_still_protects_and_that_it_is_not_enough(self):
        text = re.sub(r"\s+", " ", _text(os.path.join(RECIPE_DIR, "README.md")))
        for needle in ("## What protects, and what does not", "The same product",
                       "refuses an MSI whose upgrade code differs from the template's",
                       "refuses a label that is not the MSI's own version", "They do not replace a verification",
                       "a real run is refused before the package tool starts"):
            self.assertIn(needle, text)

    def test_the_real_run_steps_say_not_yet_and_the_refusal_text_is_the_importers(self):
        raw = _text(os.path.join(RECIPE_DIR, "README.md"))
        text = re.sub(r"\s+", " ", raw)
        self.assertIn("## d. Switch a real run on (NOT YET: see the status line)", raw)
        self.assertIn("### 4. Switch a real run on (NOT YET: see the status line)", raw)
        self.assertIn("Add :Input:pcman_allow_unverified bool true", raw)
        self.assertIn("Add :Input:cimian_allow_unverified bool true", raw)
        self.assertIn("Both lines are needed", raw)
        refusal = "The download was not verified: %s. Nothing was published." % _pcman_support.importer.UNVERIFIED_REASON
        self.assertIn(refusal, text)
        self.assertIn("published, NOT verified", raw)
        self.assertIn("published WITHOUT a verified download", raw)

    def test_the_hand_command_uses_the_template_and_no_version(self):
        raw = _text(os.path.join(RECIPE_DIR, "README.md"))
        match = re.search(r"\n    (pcman import <the file> --template xcp-ng-center[^\n]*)\n", raw)
        self.assertTrue(match)
        for flag in ("--version", "--name", "--build"):
            self.assertNotIn(flag, match.group(1))
        self.assertIn("it makes no second item", re.sub(r"\s+", " ", raw))


class SharedProcessorTests(unittest.TestCase):
    def test_every_named_shared_processor_is_a_file_of_the_shared_folder(self):
        for path in (DOWNLOAD, PCMAN):
            for name, _ in shared_steps(load(path)):
                self.assertTrue(os.path.isfile(os.path.join(PCMAN_DIR if name == "PcmanImporter" else SHARED_DIR, name + ".py")), name)

    def test_the_stub_identifier_is_the_prefix_of_the_processor_names(self):
        stub = load(os.path.join(SHARED_DIR, "SharedProcessors.recipe"))
        self.assertEqual(stub["Identifier"] + "/", SHARED_PREFIX)

    def test_every_argument_is_a_declared_input(self):
        classes = processor_classes()
        for path in (DOWNLOAD, PCMAN):
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
        for path in (DOWNLOAD, PCMAN):
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
            "XCPngCenter-Win.download.recipe", "XCPngCenter.cimian.recipe", "XCPngCenter.pcman.recipe", "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "releases_excerpt.json"),
            os.path.join("tests", "test_recipes.py"),
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
        self.assertEqual(len([c for c in commands if c.startswith("autopkg run")]), 6)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg verify-trust-info")]), 4)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg update-trust-info")]), 2)
        for command in commands:
            with self.subTest(command=command):
                self.assertRegex(
                    command,
                    r"^autopkg (run|verify-trust-info|update-trust-info)( -vv?)? "
                    r"--override-dir=<the Windows overrides folder> "
                    r"<the Windows overrides folder>/XCPngCenter\.(?:cimian|pcman)\.recipe$",
                )

    def test_no_autopkg_command_line_is_missed_by_the_indent_rule(self):
        """An operator's command that is not indented four spaces (or is indented
        less) must still be counted: every line that begins with an autopkg
        command is one of the lines checked above, and `autopkg run ` occurs
        three times in the whole file."""
        pattern = r"^[ \t]*autopkg (?:run|verify-trust-info|update-trust-info)\b"
        at_line_start = re.findall(pattern, self.raw, re.M)
        self.assertEqual(len(at_line_start), len(self.operator_commands()))
        self.assertEqual(len(re.findall(r"autopkg run ", self.raw)), 6)

    def test_no_prose_line_shows_a_full_command_without_the_option(self):
        for match in re.finditer(r"`(autopkg (?:run|verify-trust-info|update-trust-info)[^`]*<[^`]*)`", self.raw):
            self.assertIn("--override-dir=", match.group(1))

    def test_the_name_check_and_the_parent_check_are_in_step_b(self):
        step = self.raw[self.raw.index("## b."):self.raw.index("## c.")]
        self.assertIn("First check that no other recipe has the same name.", step)
        self.assertIn("autopkg list-recipes | grep -i XCPngCenter-Win", step)
        self.assertIn("autopkg list-recipes | grep -i XCPngCenter.pcman", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.XCPngCenter`",
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

    def test_the_status_line_says_what_is_not_verified_and_what_was_read(self):
        opening = "**Status. The download is NOT verified:"
        self.assertTrue(self.raw.index(opening) >= 0)
        self.assertLess(self.raw.index("**Status."), self.raw.index("## a."))
        self.assertLess(self.raw.index("# Win-XCPngCenter"), self.raw.index("**Status."))
        i = self.raw.index("**Status.")
        paragraph = re.sub(r"\s+", " ", self.raw[i:self.raw.index("\n\n", i)])
        self.assertTrue(paragraph.startswith(opening))
        self.assertTrue(paragraph.endswith("**"))
        for needle in ("GitHub records no digest for the asset that the recipe takes",
                       "the release's text names no hash and no signature", "a check of the signature is not built",
                       "REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true",
                       "Do not set it before the signature check exists",
                       "`pcman import <file> --template xcp-ng-center` (no `--version` for an MSI)",
                       "A digest step (`GitHubAssetDigest`, then `ChecksumVerifier`) can come back into the download recipe when a release has a digest",
                       "and run again after the change (2026-10-04)",
                       "\"GitHub asset 29445639: the record has no digest (older assets have none)\"",
                       "the installer of release `v20.04.01.33`", "a file of December 2020",
                       "`XCP-ng-Center-(?!99\\.)[0-9.]+\\.msi$`", "the newest release names its installer `XCP-ng.Center.msi`",
                       "the first release (in GitHub's order, newest first, a pre-release skipped) that has a file whose name the pattern matches from its start",
                       "`select_asset`", "`re.match`", "however old",
                       "the old pattern takes the file of 2020 and the new one takes the newest",
                       "`https://api.github.com/repos/xcp-ng/xenadmin/releases`", "the newest 12 releases", "no file was downloaded",
                       "`v25.04` (published 2025-04-29)", "`XCP-ng.Center.msi` (9298220 bytes)",
                       "GitHub records no digest for any asset of the 12 releases",
                       "(3787 characters) names no hash, no signature and no certificate",
                       "`XCP-ng\\.Center\\.msi$`", "takes the file of `v25.04` and nothing in the other 11 releases",
                       "NOT established", "UpgradeCode",
                       "that the next release keeps the name `XCP-ng.Center.msi`", "any install on a PC",
                       "An install on a test PC is the check of each of them",
                       "stop: nothing was written", "correct the recipe",
                       "Never correct the trust information first.", "carries `--override-dir`"):
            self.assertIn(needle, paragraph)
        for claim in ("the network was closed", "from the writer's knowledge or from another recipe", "nobody has read the release list"):
            self.assertNotIn(claim, self.text)

    def test_the_readme_claims_no_rehearsal_of_this_program(self):
        self.assertNotIn("Rehearsed on", self.raw)
        self.assertNotIn("NOT yet run", self.raw)
        # What it says of a rehearsal is about the 7-Zip folder only.
        for sentence in re.split(r"(?<=[.:;])\s", self.text):
            if re.search(r"(?i)rehears", sentence):
                self.assertTrue("7-Zip" in sentence or re.search(r"(?i)not rehearsed", sentence), sentence)

    def test_the_readme_says_that_the_provider_goes_back_when_a_name_changes(self):
        self.assertIn("takes the first release, newest first, that has a file whose name matches `SEARCH_PATTERN`, however old",
                      self.text)
        self.assertIn("Read the `Selected asset` line of every dry run", self.text)
        self.assertIn("**Read the line `Selected asset ... from release ...`**", self.text)
        self.assertIn("The run goes on, but with an old release", self.text)

    def test_the_readme_says_that_the_version_is_the_msis_own(self):
        self.assertIn("There is no `--version`: the package tool takes the MSI's own version", self.text)
        self.assertIn("MSI's own ProductVersion", self.text)

    def test_the_readme_says_what_to_do_without_a_digest(self):
        for needle in ("no digest", "import by hand", "A person checks the file first",
                       "A digest step can come back into the download recipe when a release has a digest on GitHub"):
            self.assertIn(needle, self.text)
        self.assertNotIn("Publish it by hand after checking it, and wait for a release with a digest", self.text)

    def test_the_first_import_is_the_form_that_ran_and_says_what_is_still_to_decide(self):
        step = re.sub(r"\s+", " ", self.raw[self.raw.index("3. **The template item"):self.raw.index("## b.")])
        for needle in ("If an item of the kind `msi` exists already (an import by hand), it is the template and this step is not needed",
                       "An item `xcp-ng-center` of the kind `choco` (version 1.0, no installer) is not the template, and `pcman versions xcp-ng-center` lists it too, so look at the kind",
                       "in the form that ran on 2026-10-04 (it worked as written)", "--architectures x86,x64", "--icon",
                       "`25.04` on 2026-10-04", "the client runs `msiexec /i <file> /qn /norestart` itself (not tested on a PC)",
                       "the MSI's summary says platform `Intel`, a 32-bit package",
                       "**Still to decide after a test on a PC:** whether the template needs the install argument `ALLUSERS=1`"):
            self.assertIn(needle, step)
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        command = re.sub(r"\s+", " ", match.group(1))
        self.assertIn("--architectures x86,x64 --icon", command)
        self.assertNotIn("--install-path", command)
        self.assertNotIn("--architectures <the MSI's architecture, read in the MSI first>", step)
        self.assertNotIn("from the writer's knowledge, not read in the package tool's README", step)

    def test_the_status_line_says_what_the_four_runs_of_2026_10_04_showed(self):
        status = re.sub(r"\s+", " ", [line for line in self.raw.splitlines() if line.startswith("**Status.")][0])
        for needle in ("The recipe was changed after the first dry run with AutoPkg 2.9.0, and run again after the change (2026-10-04).",
                       "After the change a dry run under AutoPkg 2.9.0 selected `XCP-ng.Center.msi` of `v25.04` (GitHub records no digest for it, so no digest step ran: the unverified route)",
                       "the first import with the package tool (the command of step a.3 below, run with `--no-prompt` and `--build`) made the item `xcp-ng-center` "
                       "(an MSI item, version `25.04` read from the MSI: two parts, the second keeping its leading zero; architectures `x86,x64`",
                       "was REFUSED with `The download was not verified:", "(exit 70)", "`pcman_allow_unverified` was not set",
                       "The override downloaded the file again, and its hash was the imported file's",
                       "`Nothing new: xcp-ng-center 25.04 exists already ...` with exit 3",
                       "went beside the Chocolatey item `xcp-ng-center` (version 1.0) without any option of the tool",
                       "the Chocolatey item file and its `xcp-ng-center-1.0` pkginfo remain until a person removes them by hand",
                       "`pcman versions xcp-ng-center` lists the Chocolatey item too (`1.0`, no installer), so its listing does not show that a template exists",
                       "`pcman catalogs` ran a second time later on 2026-10-04", "110 items each (106 before)",
                       "**The MSI has no `ALLUSERS` property** in its Property table (the MSI of PDFsam has `ALLUSERS=1`)",
                       "so an install that the client runs as SYSTEM may install the program for the SYSTEM account only",
                       "that is Windows Installer's rule, and it was NOT tested here",
                       "The template may need the install argument `ALLUSERS=1`; whether to add it is the owner's decision after a test on a PC",
                       "Nothing has been installed on a PC",
                       "NOT established: that a new release has the same UpgradeCode as the template",
                       "that the MSI installs silently on a PC and for all users", "An install on a test PC is the check of each of them"):
            self.assertIn(needle, status)
        for gone in ("NOT rehearsed since", "any run with AutoPkg after this change", "has NOT been run by anyone",
                     "the MSI's own ProductVersion, its architecture and its UpgradeCode", "that the template item `xcp-ng-center` exists"):
            self.assertNotIn(gone, status)


class ChainTests(_pcman_support.ToolTestCase):
    """The chain of this program has no verification step: the shared importer refuses a real run unless the
    override allows it. The stand-in package tool is used; nothing else is run."""

    def chain_env(self, installer):
        """What the steps of the two recipes leave in the run, with the arguments of the recipe's own
        PcmanImporter step. No step sets checksum_verified, so the run has no checksum_* variable."""
        values = {"%pathname%": installer, "%PCMAN_TEMPLATE%": load(PCMAN)["Input"]["PCMAN_TEMPLATE"],
                  "%version%": ""}
        env = {"pathname": installer, "pcman_root": self.root, "pcman_dry_run": False,
               "pcman_path": self.msi_bin}
        steps = [step for step in load(PCMAN)["Process"] if step["Processor"].endswith("/PcmanImporter")]
        self.assertEqual(len(steps), 1)
        for name, value in steps[0]["Arguments"].items():
            env[name] = values.get(value, value)
        return env

    def test_a_real_run_of_the_chain_is_refused_and_the_tool_does_not_start(self):
        env = self.chain_env(self.msi)
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        self.assertIn("The download was not verified", str(caught.exception))
        self.assertIn("pcman_allow_unverified", str(caught.exception))
        self.assertFalse(self.was_run())

    def test_with_the_override_s_allowance_the_run_goes_on_and_says_so(self):
        env = self.chain_env(self.msi)
        env["pcman_allow_unverified"] = True
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        warnings = [m for level, m in processor.message_levels if m.startswith("WARNING:")]
        self.assertTrue([m for m in warnings if "published WITHOUT a verified download" in m], warnings)
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published, NOT verified")

    def test_a_dry_run_of_the_chain_is_allowed_and_says_it_is_not_verified(self):
        env = self.chain_env(self.msi)
        env["pcman_dry_run"] = True
        self.behave(result=_pcman_support.result_file_content("dry-run"))
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        warnings = [m for level, m in processor.message_levels if m.startswith("WARNING:")]
        self.assertTrue([m for m in warnings if "the download was NOT verified" in m], warnings)
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "dry run, nothing written, NOT verified")


def _text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class CimianRecipeTests(unittest.TestCase):
    """The recipe for any Cimian repository: its only step is CimianImporter, and nothing of the
    package tool is in it. The package tool's recipe is the old recipe under its new name."""

    def test_the_three_recipes_are_property_lists_with_the_keys_that_autopkg_reads(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            with self.subTest(path=os.path.basename(path)):
                result = subprocess.run(["plutil", "-lint", path], capture_output=True, text=True) \
                    if os.path.exists("/usr/bin/plutil") else None
                if result is not None:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                recipe = load(path)
                for key in ("Description", "Identifier", "Input", "MinimumVersion", "Process"):
                    self.assertIn(key, recipe)

    def test_identifiers_and_parents(self):
        download, cimian, pcman = load(DOWNLOAD), load(CIMIAN), load(PCMAN)
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.XCPngCenter")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.XCPngCenter")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotEqual(cimian["Identifier"], pcman["Identifier"])
        self.assertEqual(cimian["MinimumVersion"], pcman["MinimumVersion"])
        self.assertTrue(CIMIAN.endswith("XCPngCenter.cimian.recipe"))
        self.assertTrue(PCMAN.endswith("XCPngCenter.pcman.recipe"))

    def test_the_only_step_is_the_cimian_importer(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "CimianImporter"])

    def test_the_inputs_and_the_arguments(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], load(PCMAN)["Input"]["NAME"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], load(PCMAN)["Input"]["PCMAN_TEMPLATE"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], "xcp-ng-center")
        self.assertEqual(recipe["Input"]["CIMIAN_SUBDIRECTORY"], "")
        self.assertEqual(sorted(recipe["Input"]), ["CIMIAN_NAME", "CIMIAN_SUBDIRECTORY", "NAME", "pkginfo"])
        self.assertEqual(recipe["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": ""})

    def test_the_pkginfo_gives_only_what_the_readme_states(self):
        self.assertEqual(load(CIMIAN)["Input"]["pkginfo"], {'display_name': 'XCP-ng Center'})

    def test_the_version_argument_is_the_exes_label_or_empty_for_an_msi(self):
        argument = load(CIMIAN)["Process"][0]["Arguments"]["version"]
        if "msi" == "exe":
            self.assertEqual(argument, "%version%")
        else:
            self.assertEqual(argument, "")  # the MSI's own ProductVersion, not a tag that an earlier step set

    def test_the_package_tool_recipe_is_the_old_recipe_with_the_new_processor_name(self):
        recipe = load(PCMAN)
        steps = [step["Processor"] for step in recipe["Process"]]
        self.assertEqual(steps, [PCMAN_PREFIX + "PcmanImporter"])
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "xcp-ng-center")
        arguments = recipe["Process"][0]["Arguments"]
        self.assertEqual(arguments["pathname"], "%pathname%")
        self.assertEqual(arguments["pcman_template"], "%PCMAN_TEMPLATE%")
        self.assertEqual("pcman_version" in arguments, "msi" == "exe")

    def test_nothing_of_the_package_tool_is_in_the_cimian_recipe(self):
        text = _text(CIMIAN).lower()
        for word in ("pcman", "package tool", "template item"):
            self.assertNotIn(word, text)

    def test_every_argument_is_a_declared_input_and_every_required_input_is_given(self):
        declared = _win_support.cimian.CimianImporter.input_variables
        arguments = load(CIMIAN)["Process"][0]["Arguments"]
        for key in arguments:
            self.assertIn(key, declared)
        for key, flags in declared.items():
            if flags.get("required") and "default" not in flags:
                self.assertIn(key, arguments)

    def test_what_the_machine_decides_is_not_in_the_cimian_recipe(self):
        text = _text(CIMIAN)
        for name in ("cimian_repo", "cimian_dry_run", "cimian_allow_unverified", "cimian_path", "cimian_catalogs",
                     "msi_product_code", "msi_upgrade_code", "checksum_verified", "checksum_sha256", "CIMIAN_REPO"):
            self.assertNotIn("<key>%s</key>" % name, text)

    def test_no_stop_on_an_unchanged_download_and_no_latest_only_and_no_blocking_applications(self):
        text = _text(CIMIAN)
        for word in ("StopProcessingIf", "latest_only", "blocking_applications"):
            self.assertNotIn(word, text)

    def test_no_value_of_the_cimian_recipe_is_a_path_a_catalog_or_a_hash(self):
        recipe = load(CIMIAN)
        values = [value for value in recipe["Input"].values() if isinstance(value, str)]
        values.extend(value for value in recipe["Process"][0]["Arguments"].values() if isinstance(value, str))
        for value in values:
            self.assertFalse(value.startswith(("/", "~", ".")), value)
            self.assertNotIn("Production", value)
            self.assertNotIn("Testing", value)
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", _text(CIMIAN)))

    def test_the_description_says_what_a_reader_must_know(self):
        description = load(CIMIAN)["Description"]
        for needle in ("CimianImporter", "dry run", "cimian_dry_run", "CIMIAN_REPO", "says that nothing is new"):
            self.assertIn(needle, description)
        self.assertNotIn("pcman", description)
        self.assertNotIn("package tool", description)

    def test_the_description_says_that_another_upgrade_code_is_refused_where_the_old_one_said_so(self):
        description = load(CIMIAN)["Description"]
        if "refuses an MSI whose upgrade code differs from the template's" in load(PCMAN)["Description"]:
            self.assertIn("It refuses an MSI whose upgrade code differs from the template's unless the override sets "
                          "cimian_allow_product_change to true", description)
        self.assertNotIn("warns when an MSI", description)

    def test_the_description_of_an_unverified_download_says_so_first(self):
        description = load(CIMIAN)["Description"]
        if True:
            self.assertTrue(description.startswith("This import is NOT verified yet:"))
            self.assertIn("cimian_allow_unverified", description)
            self.assertIn("published, NOT verified", description)
        else:
            self.assertNotIn("NOT verified yet", description)

    def test_the_cimian_recipe_names_only_the_shared_importer_and_it_is_in_the_shared_folder(self):
        for step in load(CIMIAN)["Process"]:
            self.assertEqual(step["Processor"], SHARED_PREFIX + "CimianImporter")
            self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, "CimianImporter.py")))


class CimianReadmeTests(unittest.TestCase):
    """The README has two ways, in this order: any Cimian repository, then the package tool."""

    def setUp(self):
        self.raw = _text(os.path.join(RECIPE_DIR, "README.md"))
        self.generic = self.raw[self.raw.index("## With any Cimian repository"):self.raw.index("## With the package tool (pcman)")]
        self.tool = self.raw[self.raw.index("## With the package tool (pcman)"):self.raw.index("\n## Tests")]

    @staticmethod
    def commands(text, name):
        return [line.strip() for line in text.splitlines() if re.match(r"^\s*autopkg %s\b" % name, line)]

    def test_the_sections_come_in_this_order(self):
        positions = [self.raw.index(mark) for mark in (
            "## Run every override with `--override-dir`", "## With any Cimian repository",
            "## With the package tool (pcman)", "## a. ", "## g. ", "## Other facts", "## Tests")]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(len(set(positions)), len(positions))

    def test_the_table_has_the_three_recipes(self):
        for name, identifier in (("XCPngCenter.cimian.recipe", "com.github.serrc-techops.cimian.XCPngCenter"),
                                 ("XCPngCenter.pcman.recipe", "com.github.serrc-techops.pcman.XCPngCenter")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)
        self.assertIn("`CimianImporter`", [line for line in self.raw.splitlines() if line.startswith("| `XCPngCenter.cimian.recipe`")][0])
        self.assertIn("`pcman`", [line for line in self.raw.splitlines() if line.startswith("| `XCPngCenter.pcman.recipe`")][0])

    def test_the_generic_way_has_the_same_steps_as_the_package_tools(self):
        self.assertEqual(len(self.commands(self.generic, "run")), 3)
        self.assertEqual(len(self.commands(self.generic, "verify-trust-info")), 2)
        self.assertEqual(len(self.commands(self.generic, "update-trust-info")), 1)
        self.assertEqual(len(self.commands(self.generic, "make-override")), 1)
        self.assertEqual(len(self.commands(self.generic, "repo-add")), 1)
        for heading in ("### 1. What must exist first", "### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER",
                        "### 3. First try: a dry run", "### 5. The real run, the catalogs, the second run",
                        "### 6. When a recipe or a processor changes upstream", "### A share that is not mounted"):
            self.assertIn(heading, self.generic)
        self.assertIn("### 4. Switch a real run on", self.generic)

    def test_every_command_of_each_way_names_its_own_recipe_and_the_override_dir(self):
        for text, recipe, other in ((self.generic, "XCPngCenter.cimian", "XCPngCenter.pcman"), (self.tool, "XCPngCenter.pcman", "XCPngCenter.cimian")):
            for name in ("run", "verify-trust-info", "update-trust-info", "make-override"):
                for command in self.commands(text, name):
                    with self.subTest(command=command):
                        self.assertIn("--override-dir=", command)
                        self.assertIn(recipe, command)
                        self.assertNotIn(other, command)
        self.assertEqual(len(self.commands(self.tool, "run")), 3)
        self.assertEqual(len(self.commands(self.tool, "make-override")), 1)

    def test_the_generic_way_runs_an_override_by_path_and_never_a_recipe_identifier(self):
        for command in self.commands(self.generic, "run"):
            self.assertNotIn("com.github.", command)
            self.assertRegex(command, r"--override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter\.cimian\.recipe$")

    def test_the_generic_way_names_nothing_of_the_package_tool_to_run(self):
        for word in ("pcman import", "pcman catalogs", "pcman versions", "pcman_root", "pcman_python", "PCMAN_TEMPLATE", "PcmanImporter"):
            self.assertNotIn(word, self.generic)
        self.assertIn("no package tool", self.generic)

    def test_the_generic_way_gives_the_preference_the_switch_and_the_catalogs(self):
        for needle in ("defaults write com.github.autopkg CIMIAN_REPO -string", "Add :Input:cimian_dry_run bool false",
                       "Cimian's `makecatalogs`", "`CIMIAN_NAME`", "`CIMIAN_SUBDIRECTORY`", "WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on.",
                       "windowsadmins/cimian", "e10498b", "ParentRecipe"):
            self.assertIn(needle, self.generic)
        self.assertNotIn("-k cimian_dry_run=false instead", self.generic.replace("Do not use `-k cimian_dry_run=false` instead", ""))

    def test_the_lines_that_the_generic_way_quotes_are_in_the_processor(self):
        source = _text(os.path.join(SHARED_DIR, "CimianImporter.py"))
        for fragment in ("WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on.", "Would write ", "No template: the pkginfo is built from the inputs.",
                         "Nothing new: ", "Published ", "Build the catalogs with makecatalogs."):
            self.assertIn(fragment, source)
            self.assertIn(fragment.split(". ")[0] if fragment.startswith("WARNING") else fragment.strip(), self.generic.replace("`", ""))

    def test_the_generic_way_says_what_a_person_completes_by_hand(self):
        if "msi" == "exe":
            self.assertIn("What a person completes by hand for an `.exe`", self.generic)
            self.assertIn("an install check", self.generic)
            self.assertIn("StatusService.cs:194-219", self.generic)
            self.assertIn("does NOT give the silent arguments", self.generic)
            self.assertNotIn("installer: {args: [/S]}", self.generic.replace("`installer: {args: [...]}`", ""))
        else:
            self.assertIn("For an `.msi` nothing needs completing for a silent install", self.generic)
            self.assertIn("InstallerService.cs:936-948", self.generic)
            self.assertIn("`msiinfo`", self.generic)
            self.assertIn("This recipe cannot run without it", self.generic)
            self.assertIn("an argument of a step wins over an override's `Input`", self.generic)
            self.assertIn("`cimian_allow_product_change`", self.generic)
            self.assertIn("or that has none where the template's item had one", self.generic)

    def test_the_recipes_pkginfo_does_not_change_a_template_says_the_generic_way(self):
        for needle in ("The recipe's `pkginfo` does not change a template", "a NOTE names each",
                       "`cimian_pkginfo_wins` set to true in the override", "`cimian_architecture`"):
            self.assertIn(needle, self.generic)

    def test_the_parent_recipe_is_the_recipe_the_override_was_made_from(self):
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.cimian.XCPngCenter`**", self.generic.replace("\n", " "))
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.XCPngCenter`**", self.tool.replace("\n", " "))
        for text in (self.generic, self.tool):
            self.assertNotIn("it must be `com.github.serrc-techops.download.", text.replace("\n", " "))

    def test_an_override_of_the_old_cimian_recipe_is_to_be_made_again_for_the_package_tool(self):
        self.assertIn("An override that was made from the old `XCPngCenter.cimian.recipe`", self.tool)
        self.assertIn("must be made again from `XCPngCenter.pcman.recipe`", self.tool)
        self.assertIn("An override that was made from this recipe before the recipes were separated", self.generic)

    def test_the_condition_of_never_overwrites_is_said(self):
        self.assertIn("do not run two runs of one item at the same time", self.generic)

    def test_the_generic_way_states_no_hash_and_no_made_up_label(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.generic))
        self.assertNotIn("Published xcp-ng-center", self.generic)

    def test_an_unverified_download_is_said_not_yet_in_the_generic_way(self):
        if True:
            self.assertIn("**The download of this program is NOT verified**", self.generic)
            self.assertIn("### 4. Switch a real run on (NOT YET: see the status line)", self.generic)
            self.assertIn("Add :Input:cimian_allow_unverified bool true", self.generic)
            self.assertIn("**Not yet.**", self.generic)
            self.assertLess(self.generic.index("Add :Input:cimian_dry_run bool false"), self.generic.index("Add :Input:cimian_allow_unverified bool true"))
        else:
            self.assertNotIn("cimian_allow_unverified bool true", self.generic)
            self.assertNotIn("NOT verified", self.generic)

    def test_the_package_tools_way_says_the_tool_is_not_in_this_repository(self):
        self.assertIn("**not part of this repository**", self.tool)
        self.assertIn("`PcmanImporter` of `../Win-PcmanProcessors/`", self.tool)
        self.assertIn("XCPngCenter.pcman", self.tool)

    def test_the_processors_are_named_in_their_new_folders(self):
        self.assertNotIn("SharedProcessors/PcmanImporter", self.raw)
        self.assertNotIn("PcmanImporter` is in `../Win-SharedProcessors", self.raw)


class CimianChainTests(_win_support.RepoTestCase):
    """The chain of this program with the real CimianImporter and a temporary repository: the steps of the
    download recipe leave their variables in the run, the recipe's own step reads them."""

    VERIFIED = False

    def run_chain(self, installer, tag="9.9.9", label="1.2.3", **extra):
        """What the recipe's step is given, with the substitutions that AutoPkg makes. `tag` is a version that an
        earlier step of the download recipe may have left in the run (a release tag, say); `label` is what
        an earlier step leaves in `version` for an .exe."""
        recipe = load(CIMIAN)
        run = {"pathname": installer, "version": label if "msi" == "exe" else tag}
        if self.VERIFIED:
            run["expected_sha256"] = _win_support.sha256_hex(installer)
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

    def installer(self):
        return self.exe if "msi" == "exe" else self.msi

    @_win_support.needs_yaml
    def test_the_chain_publishes_into_an_empty_repository_as_the_recipes_inputs_say(self):
        if not self.VERIFIED:
            with self.assertRaises(_win_support.ProcessorError):
                self.run_chain(self.installer())
            processor, messages = self.run_chain(self.installer(), cimian_allow_unverified=True)
            self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published, NOT verified")
        else:
            processor, messages = self.run_chain(self.installer())
            self.assertEqual([m for m in messages if m.startswith("WARNING: published WITHOUT")], [])
            self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published")
        new = self.read_pkginfo("Example-Chain-%s.yaml" % processor.env["cimian_version_imported"])
        self.assertEqual(new["name"], "Example-Chain")
        for key, value in load(CIMIAN)["Input"]["pkginfo"].items():
            if isinstance(value, dict):
                for inner, expected in value.items():
                    self.assertEqual(new[key][inner], expected)
            else:
                self.assertEqual(new[key], value)
        self.assertEqual(new["installer"]["type"], "msi")
        self.assertEqual(new["installer"]["hash"], _win_support.sha256_hex(self.installer()))

    @_win_support.needs_yaml
    def test_the_version_is_the_label_of_an_exe_and_the_products_own_for_an_msi(self):
        if "msi" == "exe":
            processor, _ = self.run_chain(self.exe, label="1.2.3", cimian_allow_unverified=True)
            self.assertEqual(processor.env["cimian_version_imported"], "1.2.3")
        else:
            self.msiinfo_says(stdout=_win_support.property_export(version="2.5.0"))
            processor, _ = self.run_chain(self.msi, tag="9.9.9", cimian_allow_unverified=True)
            self.assertEqual(processor.env["cimian_version_imported"], "2.5.0")  # not the tag of the run

    @_win_support.needs_yaml
    def test_the_recipes_pkginfo_does_not_change_an_item_that_the_repository_has(self):
        """A template wins over the recipe's own pkginfo: the display name of the recipe does not rename an
        existing item, and the recipe's arguments are not added beside the template's."""
        head = "display_name: Template Name\nversion: 1.0.0\ncatalogs:\n- Production\ninstaller:\n  location: apps/Example-Chain-1.0.0.msi\n"
        if "msi" == "exe":
            body = ("  hash: " + "a" * 64 + "\n  type: exe\n  switches:\n  - /TEMPLATE-SWITCH\n"
                    "check:\n  file:\n    path: C:" + chr(92) + "Example" + chr(92) + "example.exe\n    version: 1.0.0\nname: Example-Chain\n")
        else:
            body = ("  hash: " + "a" * 64 + "\n  type: msi\ninstalls:\n- type: msi\n  product_code: '{AAAAAAAA-0000-0000-0000-000000000001}'\n"
                    "  upgrade_code: '" + _win_support.UPGRADE_CODE + "'\n  version: 1.0.0\nname: Example-Chain\n")
        self.put_pkginfo("apps/Example-Chain-1.0.0.yaml", head + body)
        template = self.read_pkginfo("apps/Example-Chain-1.0.0.yaml")
        processor, messages = self.run_chain(self.installer(), cimian_allow_unverified=True)
        new = self.read_pkginfo("apps/Example-Chain-%s.yaml" % processor.env["cimian_version_imported"])
        for key, value in load(CIMIAN)["Input"]["pkginfo"].items():
            if key in template:
                self.assertEqual(new[key], template[key], key)
                self.assertTrue(any(m.startswith("NOTE: pkginfo's %s differs from the template's and is not used" % key) for m in messages), key)
            else:
                self.assertEqual(new[key], value, key)
        self.assertEqual(new["display_name"], "Template Name")
        if "msi" == "exe":
            self.assertEqual(new["installer"]["switches"], ["/TEMPLATE-SWITCH"])
            self.assertNotIn("args", new["installer"])

    @_win_support.needs_yaml
    def test_a_second_run_with_the_same_file_has_nothing_new(self):
        self.run_chain(self.installer(), cimian_allow_unverified=True)
        before = self.repo_tree()
        processor, messages = self.run_chain(self.installer(), cimian_allow_unverified=True)
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertEqual(self.repo_tree(), before)

    @_win_support.needs_yaml
    def test_the_chain_is_refused_for_another_file(self):
        if not self.VERIFIED:
            self.skipTest("this download has no verification step: the guard refuses every real run (see the first test)")
        installer = self.installer()
        run = {"pathname": installer, "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        other = self.make_installer("other-" + os.path.basename(installer), b"not the file that was verified")
        env = {"pathname": other, "cimian_name": "Example-Chain", "version": "1.2.3", "cimian_repo": self.repo,
               "cimian_dry_run": False, "cimian_path": self.msi_bin}
        env.update({key: value for key, value in verifier.env.items() if key.startswith("checksum_")})
        before = self.repo_tree()
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_win_support.cimian.CimianImporter, env)
        self.assertIn("not the file whose checksum was verified", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)


if __name__ == "__main__":
    unittest.main()
