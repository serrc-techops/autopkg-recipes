"""Tests of the three Acellus recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. Each step that names one of our shared
processors is compared with what that processor declares (see
../../Win-SharedProcessors). The shared folder's tests are run separately.
The download step is run once with the Store's catalog answered by this folder's
saved excerpt and the delivery service replaced by a function that fails the test
if it is asked; the importers are run with a tiny made-up bundle.
"""
import base64
import copy
import json
import os
import plistlib
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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
import MicrosoftStorePackageDownloader as store  # noqa: E402  (beside the other shared processors)

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "Acellus-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "Acellus.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "Acellus.pcman.recipe")
# The fields of the Store's catalog record of the product that the download step reads, read on 2026-11-13.
CATALOG = os.path.join(TESTS_DIR, "catalog_excerpt.json")
PRODUCT_ID = "9NXWFBJHRXKC"
IDENTITY_NAME = "GoldKeyCorporation.Acellus"
FULL_NAME = "GoldKeyCorporation.Acellus_2026.1028.1836.0_neutral_~_v2rn50m687qry"
BUNDLE_VERSION = "2026.1028.1836.0"
FRAMEWORK = ("Microsoft.WindowsAppRuntime.1.4", "4000.1309.2056.0")
DOWNLOADER = "MicrosoftStorePackageDownloader"
# Required inputs that a recipe must NOT pass: they come from AutoPkg's
# preferences or the override on the machine that runs it.
SUPPLIED_BY_THE_MACHINE = {"PcmanImporter": {"pcman_root"}}
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir", "pcman_allow_unverified",
                     "checksum_verified", "store_file_host_suffixes", "store_market", "store_language")


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def _text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def processor_classes():
    import importlib
    classes = {}
    for name in ("PcmanImporter", "CimianImporter", "ChecksumVerifier", DOWNLOADER):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def catalog():
    with open(CATALOG, "r", encoding="utf-8") as handle:
        return json.load(handle)


def shared_steps(recipe):
    """The steps that name a processor of this repository, of either folder: (name, arguments)."""
    for step in recipe["Process"]:
        for prefix in (SHARED_PREFIX, PCMAN_PREFIX):
            if step["Processor"].startswith(prefix):
                yield step["Processor"][len(prefix):], step.get("Arguments", {})


def write_bundle(path, identity_name=IDENTITY_NAME, version=BUNDLE_VERSION, payload=b"made-up"):
    """A tiny made-up bundle: a zip with a bundle manifest, built by the shared tests' helper."""
    manifest = _win_support.package_manifest(name=identity_name, version=version, bundle=True)
    return _win_support.write_app_package(path, {"AppxMetadata/AppxBundleManifest.xml": manifest,
                                                 "payload.bin": payload})


class RecipeFileTests(unittest.TestCase):
    def test_the_three_files_are_property_lists_with_the_keys_that_autopkg_reads(self):
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
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.Acellus-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.Acellus")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.Acellus")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)
        self.assertEqual(cimian["MinimumVersion"], pcman["MinimumVersion"])
        self.assertEqual(download["MinimumVersion"], pcman["MinimumVersion"])

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + DOWNLOADER, "EndOfCheckPhase", SHARED_PREFIX + "ChecksumVerifier"])

    def test_the_download_inputs_and_the_store_step(self):
        recipe = load(DOWNLOAD)
        self.assertEqual(recipe["Input"], {"NAME": "Acellus", "STORE_PRODUCT_ID": PRODUCT_ID})
        self.assertTrue(store.PRODUCT_ID_PATTERN.fullmatch(recipe["Input"]["STORE_PRODUCT_ID"]))
        self.assertEqual(recipe["Process"][0]["Arguments"], {"store_product_id": "%STORE_PRODUCT_ID%"})

    def test_the_checksum_step_takes_what_the_store_step_gives(self):
        steps = dict(shared_steps(load(DOWNLOAD)))
        self.assertEqual(steps["ChecksumVerifier"], {"pathname": "%pathname%", "expected_sha256": "%expected_sha256%"})
        outputs = store.MicrosoftStorePackageDownloader.output_variables
        for name in ("pathname", "expected_sha256"):
            self.assertIn(name, outputs)
        self.assertNotIn("checksum_verified", outputs)

    def test_the_inputs_of_the_pcman_recipe(self):
        recipe = load(PCMAN)
        self.assertEqual(recipe["Input"], {"NAME": "Acellus", "PCMAN_TEMPLATE": "Acellus"})
        self.assertEqual(recipe["Process"][0]["Arguments"], {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%"})

    def test_the_pcman_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(PCMAN)["Process"]]
        self.assertEqual(steps, [PCMAN_PREFIX + "PcmanImporter"])

    def test_no_recipe_gives_a_version_label(self):
        """The importers read the version from the package itself, as an MSI's: no pcman_version, and the
        CimianImporter step passes an empty version so that nothing an earlier step left is taken for it."""
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = _text(path)
            self.assertNotIn("pcman_version", text)
            self.assertNotIn("%version%", text)
            self.assertNotIn("store_package_version", text)
        self.assertEqual(load(CIMIAN)["Process"][0]["Arguments"]["version"], "")

    def test_no_stop_on_an_unchanged_download_and_no_latest_only_and_no_blocking_applications(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = _text(path)
            for word in ("StopProcessingIf", "latest_only", "blocking_applications", "download_changed"):
                self.assertNotIn(word, text)

    def test_no_hash_in_a_recipe(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", _text(path)))

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        """Also not the Store step's optional inputs: the hosts, the market and the language belong to an override."""
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = _text(path)
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text)

    def test_no_boolean_of_an_input_is_named_by_a_step(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            recipe = load(path)
            for step in recipe["Process"]:
                for key, value in step.get("Arguments", {}).items():
                    match = re.fullmatch(r"%([A-Za-z_]+)%", value) if isinstance(value, str) else None
                    if match:
                        self.assertNotIsInstance(recipe["Input"].get(match.group(1)), bool, key)

    def test_the_descriptions_say_what_a_reader_must_know(self):
        download = load(DOWNLOAD)["Description"]
        for needle in ("Microsoft Store application", PRODUCT_ID, IDENTITY_NAME, ".msixbundle", "without the Store",
                       "MicrosoftStorePackageDownloader", "ChecksumVerifier", "The vendor offers no other download",
                       "Windows App Runtime framework, which this recipe does not fetch",
                       "prints each framework dependency with its minimum version at every run",
                       "more than one package", "offers no file", "store_file_host_suffixes", "names the host",
                       "no offered file has the catalog's SHA-256", "writes nothing", "the delivery service is not asked",
                       "never stops on an unchanged download", "the package's own version",
                       "Nothing of this recipe has run under AutoPkg"):
            self.assertIn(needle, download)
        pcman = load(PCMAN)["Description"]
        for needle in ("package's own Identity Version", "the bundle's version", "dry run", "pcman_dry_run",
                       "identity name is not the template's"):
            self.assertIn(needle, pcman)
        for description in (download, pcman, load(CIMIAN)["Description"]):
            self.assertNotIn("ehearsed", description)
            self.assertNotIn("MSI's own", description)


class CatalogTests(unittest.TestCase):
    """The facts of the status line, against the saved cut of the catalog record (2026-11-13), read with the
    download step's own parser."""

    def test_the_catalog_names_one_package_the_bundle_of_the_status_line(self):
        package = store.parse_catalog(catalog(), PRODUCT_ID)
        self.assertEqual(package["full_name"], FULL_NAME)
        self.assertEqual(package["version"], BUNDLE_VERSION)
        self.assertEqual(package["format"], "msixbundle")
        self.assertEqual(package["max_size"], 88033841)
        self.assertEqual(package["frameworks"], [FRAMEWORK])
        self.assertEqual(package["title"], "Acellus")
        self.assertEqual(len(catalog()["Product"]["DisplaySkuAvailabilities"]), 2)

    def test_the_framework_line_is_the_one_the_readme_tells_a_person_to_compare(self):
        line = store.framework_text(store.parse_catalog(catalog(), PRODUCT_ID)["frameworks"])
        self.assertIn(FRAMEWORK[0], line)
        self.assertIn(FRAMEWORK[1], line)
        readme = re.sub(r"\s+", " ", _text(os.path.join(RECIPE_DIR, "README.md")))
        self.assertIn("`Microsoft.WindowsAppRuntime.1.4`, minimum version %s" % FRAMEWORK[1], readme)
        self.assertIn("`needs Microsoft.WindowsAppRuntime.1.4 <minimum> or later`", readme)

    def test_the_publisher_is_the_developer_of_the_cimian_recipe(self):
        names = catalog()["Product"]["LocalizedProperties"][0]
        self.assertEqual(names["PublisherName"], load(CIMIAN)["Input"]["pkginfo"]["developer"])
        self.assertEqual(names["DeveloperName"], "")

    def test_a_second_package_in_the_catalog_stops_the_run(self):
        document = catalog()
        other = copy.deepcopy(document["Product"]["DisplaySkuAvailabilities"][1])
        other["Sku"]["Properties"]["Packages"][0]["PackageFullName"] = FULL_NAME.replace("2026.1028.1836.0", "2026.1101.1200.0")
        other["Sku"]["Properties"]["Packages"][0]["Version"] = None
        document["Product"]["DisplaySkuAvailabilities"][1] = other
        with self.assertRaises(ValueError) as caught:
            store.parse_catalog(document, PRODUCT_ID)
        self.assertIn("not exactly one", str(caught.exception))


class StoreStepTests(unittest.TestCase):
    """The download step of this recipe with the saved catalog record. Its hash is replaced by the hash of a
    tiny made-up bundle that lies in the cache under the package's full name; the delivery service must
    then not be asked. Nothing here uses the network."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="win-acellus-tests-")
        self.addCleanup(self._tmp.cleanup)
        self.cache = os.path.realpath(self._tmp.name)
        os.makedirs(os.path.join(self.cache, "downloads"))
        self.bundle = write_bundle(os.path.join(self.cache, "downloads", FULL_NAME + ".msixbundle"))
        document = catalog()
        digest = base64.b64encode(bytes.fromhex(_win_support.sha256_hex(self.bundle))).decode("ascii")
        for entry in document["Product"]["DisplaySkuAvailabilities"]:
            entry["Sku"]["Properties"]["Packages"][0]["Hash"] = digest
        self.answer = json.dumps(document).encode("utf-8")
        self.asked = []

    def run_step(self):
        recipe = load(DOWNLOAD)
        env = {"RECIPE_CACHE_DIR": self.cache}
        env.update(recipe["Input"])
        for name, value in recipe["Process"][0]["Arguments"].items():
            env[name] = re.sub(r"%([A-Za-z_]+)%", lambda m: str(env[m.group(1)]), value)

        def fetch(url, *args, **kwargs):
            self.asked.append(url)
            return self.answer

        def delivery(*args, **kwargs):
            raise AssertionError("the delivery service was asked")

        with mock.patch.object(store, "fetch_bytes", fetch), mock.patch.object(store, "file_urls", delivery):
            return _win_support.run_processor(store.MicrosoftStorePackageDownloader, env)

    def test_the_cached_package_is_used_and_the_delivery_service_is_not_asked(self):
        processor, messages = self.run_step()
        self.assertEqual(processor.env["pathname"], self.bundle)
        self.assertEqual(processor.env["expected_sha256"], _win_support.sha256_hex(self.bundle))
        self.assertIs(processor.env["download_changed"], False)
        self.assertEqual(processor.env["store_package_version"], BUNDLE_VERSION)
        self.assertEqual(processor.env["store_package_format"], "msixbundle")
        self.assertEqual(len(self.asked), 1)
        self.assertTrue(self.asked[0].startswith("https://displaycatalog.mp.microsoft.com/v7.0/products/%s?" % PRODUCT_ID))
        self.assertIn("  needs %s %s or later" % FRAMEWORK, messages)
        self.assertTrue(any(m.startswith("Acellus: %s (88033841 bytes at most)" % FULL_NAME) for m in messages))

    def test_the_checksum_step_then_verifies_the_package(self):
        processor, _ = self.run_step()
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, {
            "pathname": processor.env["pathname"], "expected_sha256": processor.env["expected_sha256"]})
        self.assertIs(verifier.env["checksum_verified"], True)
        self.assertEqual(verifier.env["checksum_sha256"], _win_support.sha256_hex(self.bundle))

    def test_another_file_in_the_cache_sends_the_step_to_the_delivery_service(self):
        with open(self.bundle, "ab") as handle:
            handle.write(b"changed")
        with self.assertRaises(AssertionError) as caught:
            self.run_step()
        self.assertIn("the delivery service was asked", str(caught.exception))


class SharedProcessorTests(unittest.TestCase):
    def test_every_named_shared_processor_is_a_file_of_the_shared_folder(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            for name, _ in shared_steps(load(path)):
                self.assertTrue(os.path.isfile(os.path.join(PCMAN_DIR if name == "PcmanImporter" else SHARED_DIR, name + ".py")), name)
        self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, store.PINNED_ROOT_FILE)))

    def test_the_stub_identifier_is_the_prefix_of_the_processor_names(self):
        stub = load(os.path.join(SHARED_DIR, "SharedProcessors.recipe"))
        self.assertEqual(stub["Identifier"] + "/", SHARED_PREFIX)

    def test_every_argument_is_a_declared_input(self):
        classes = processor_classes()
        names = set()
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            for name, args in shared_steps(load(path)):
                names.add(name)
                for key in args:
                    with self.subTest(recipe=os.path.basename(path), processor=name, argument=key):
                        self.assertIn(key, classes[name].input_variables)
        self.assertEqual(names, {DOWNLOADER, "ChecksumVerifier", "CimianImporter", "PcmanImporter"})

    def test_every_required_input_is_passed_or_has_a_default(self):
        """Inputs of a processor come from its arguments or from variables that
        earlier steps and the parent recipe set. pcman_root comes from the machine."""
        classes = processor_classes()
        for path in (DOWNLOAD, CIMIAN, PCMAN):
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

    def test_this_file_holds_no_address_either(self):
        text = _text(os.path.abspath(__file__))
        self.assertIsNone(shared_hygiene.FORBIDDEN_PATTERNS["an IPv4 address"].search(text))

    def test_nothing_deeper_than_the_tests_folder(self):
        for path in self.files():
            self.assertLessEqual(len(os.path.relpath(path, RECIPE_DIR).split(os.sep)), 2, path)


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.raw = _text(os.path.join(RECIPE_DIR, "README.md"))
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
                    r"<the Windows overrides folder>/Acellus\.(?:cimian|pcman)\.recipe$",
                )

    def test_no_autopkg_command_line_is_missed_by_the_indent_rule(self):
        pattern = r"^[ \t]*autopkg (?:run|verify-trust-info|update-trust-info)\b"
        self.assertEqual(len(re.findall(pattern, self.raw, re.M)), len(self.operator_commands()))
        self.assertEqual(len(re.findall(r"autopkg run ", self.raw)), 6)

    def test_no_prose_line_shows_a_full_command_without_the_option(self):
        for match in re.finditer(r"`(autopkg (?:run|verify-trust-info|update-trust-info)[^`]*<[^`]*)`", self.raw):
            self.assertIn("--override-dir=", match.group(1))

    def test_the_dry_run_commands_carry_dash_v(self):
        commands = self.operator_commands()
        self.assertEqual(len([c for c in commands if c.startswith("autopkg run -v ")]), 2)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg run --override-dir")]), 4)

    def test_the_name_check_and_the_parent_check_are_in_step_b(self):
        step = self.raw[self.raw.index("## b."):self.raw.index("## c.")]
        self.assertIn("First check that no other recipe has the same name.", step)
        self.assertIn("autopkg list-recipes | grep -i Acellus-Win", step)
        self.assertIn("autopkg list-recipes | grep -i Acellus.pcman", step)
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Acellus`", re.sub(r"\s+", " ", step))
        self.assertLess(step.index("list-recipes"), step.index("autopkg make-override"))

    def test_the_readme_states_no_hash(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.raw))

    def test_a_bold_paragraph_says_why_and_what_to_do_when_the_warning_appears(self):
        i = self.raw.index("## Run every override with `--override-dir`")
        paragraph = re.sub(r"\s+", " ", self.raw[i:i + 2500])
        for needle in ("**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`",
                       "skips the trust check with one warning line", "is missing trust info",
                       "a changed processor is not caught", "If that line ever appears in a run of an override, stop: the run was not checked.**",
                       "`FAIL_RECIPES_WITHOUT_TRUST_INFO`", "owner's decision"):
            self.assertIn(needle, paragraph)
        self.assertLess(i, self.raw.index("## a."))

    def test_the_steps_are_there(self):
        for needle in ("pcman catalogs", "pcman versions Acellus", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string", "--display-name", "--category",
                       "--developer", "--description"):
            self.assertIn(needle, self.text)

    def test_the_first_import_has_no_version_and_no_architecture_and_names_the_framework(self):
        start = self.raw.index("pcman import ")
        command = self.raw[start:self.raw.index("\n\n", start)]
        for flag in ("--version", "--architectures", "--install-path", "--identity-name"):
            self.assertNotIn(flag, command)
        for flag in ("--name Acellus", "--display-name", "--category", "--developer", "--description",
                     "--dependencies <the framework item>", "--icon", ".msixbundle"):
            self.assertIn(flag, command)
        for needle in ("There is no `--version`", "There is no `--architectures`: a bundle names none",
                       "NOT run for this program", "the bundle's (2026.1028.1836.0 in the catalog of 2026-11-13)"):
            self.assertIn(needle, self.text)

    def test_the_status_line_says_what_was_read_and_what_was_not(self):
        lines = [line for line in self.raw.splitlines() if line.strip()]
        self.assertTrue(lines[0].startswith("# "))
        status = lines[2]
        self.assertTrue(status.startswith("**Status. New, and not rehearsed (written 2026-11-13)."))
        self.assertTrue(status.endswith("**"))
        self.assertEqual(status.count("**"), 2)
        for needle in ("Nothing of this folder has run under AutoPkg", "no file was downloaded for it",
                       "nothing was installed on a PC with it",
                       "`MicrosoftStorePackageDownloader` has never run under AutoPkg and has never contacted Microsoft's delivery service",
                       "READ on 2026-11-13 from the Store's catalog record",
                       "the publisher `GoldKey Corporation` (the record's developer name is empty)",
                       "two SKUs that name the same one package", "`%s`" % FULL_NAME, "88033841 bytes",
                       "`Microsoft.WindowsAppRuntime.1.4`, minimum version 4000.1309.2056.0",
                       "a stand-alone tool with the same protocol", "2026-11-10", "Windows 11 test PC",
                       "`GoldKeyCorporation.Acellus_v2rn50m687qry`",
                       "That is the BUNDLE's version, which looks like a date",
                       "the application inside it was version 40.0.22 (with a fourth part 0)",
                       "`Get-AppxProvisionedPackage`", "`Get-AppxPackage`", "compare each with its own",
                       "signed by the Store, so no certificate and no sideloading setting are needed",
                       "4000.1136.2333.0 or later", "about 35 s", "without signing in again",
                       "That test ran a script, NOT the Cimian client",
                       "The vendor offers no other download", "the Store package is the source",
                       "The framework is NOT fetched by this recipe", "a `requires` on a framework item",
                       "prints the framework dependencies with their minimum versions at every run",
                       "compare that line with the framework item at every new version",
                       "NOT established: an install through the Cimian client", "a user with Acellus open during the install",
                       "Windows 10", "ARM", "The first dry run is the test",
                       "a refused file host (the message names the host: a person checks that the host is Microsoft's, "
                       "and only then corrects `store_file_host_suffixes` in the override)",
                       "the delivery service offers no file", "no offered file has the catalog's SHA-256",
                       "the catalog names more than one package",
                       "never accept trust information to make a failure go away", "carries `--override-dir`"):
            self.assertIn(needle, status)
        self.assertLess(self.raw.index("**Status."), self.raw.index("## a."))
        self.assertNotIn("Rehearsed on", self.raw)

    def test_no_run_or_import_of_an_earlier_program_is_told_as_this_ones(self):
        for gone in ("PDF" + "sam", "pdf" + "sam", "GitHub" + "AssetDigest", "Selected " + "asset", "SEARCH" + "_PATTERN",
                     "(Run on 2026-10-04", "110 items", "msiexec /i"):
            self.assertNotIn(gone, self.raw)

    def test_nothing_says_where_the_stand_alone_tool_lives_or_who_ran_it(self):
        lowered = self.raw.lower()
        for word in ("get-store-package", "generator", "gorilla", "owner's stand-alone", "the owner ran"):
            self.assertNotIn(word, lowered)

    def test_the_file_hosts_paragraph_says_how_to_correct_them_in_the_override(self):
        start = self.text.index("**The file hosts.**")
        paragraph = self.text[start:self.text.index("Below, `pcman` stands for")]
        for needle in ("`store_file_host_suffixes`", "`.dl.delivery.mp.microsoft.com` and `.microsoft.com`",
                       "assumed by the processor, not read", "its message names the host",
                       "a person checks that the host is Microsoft's", "never in the recipe",
                       "Add :Input:store_file_host_suffixes string .dl.delivery.mp.microsoft.com,.microsoft.com,",
                       "The file is accepted only on the catalog's SHA-256"):
            self.assertIn(needle, paragraph)

    def test_the_readme_counts_the_processors_of_the_trust_information(self):
        names = {name for path in (DOWNLOAD, PCMAN) for name, _ in shared_steps(load(path))}
        self.assertEqual(len(names), 3)
        self.assertIn("the trust information of the two recipes and the three processors", self.text)

    def test_the_lines_that_the_readme_quotes_from_the_store_step_are_in_it(self):
        source = _text(os.path.join(SHARED_DIR, DOWNLOADER + ".py"))
        for fragment in ("bytes at most", "  needs %s %s or later", "Downloaded and matched the catalog's SHA-256",
                         "The package with the catalog's SHA-256 is in the cache; the delivery service was not asked.",
                         "The delivery service offered no file.", "The delivery service named no update with a file for this product.",
                         "No offered file has the catalog's SHA-256: "):
            self.assertIn(fragment, source)
        for fragment in ("bytes at most)", "needs Microsoft.WindowsAppRuntime.1.4 <minimum> or later",
                         "Downloaded and matched the catalog's SHA-256 <hash>",
                         "The package with the catalog's SHA-256 is in the cache; the delivery service was not asked.",
                         "The delivery service offered no file.", "No offered file has the catalog's SHA-256: ..."):
            self.assertIn(fragment, self.text)


class FrameworkReadmeTests(unittest.TestCase):
    """What a person completes by hand: the framework item, the requires, the comparison at every version."""

    def setUp(self):
        raw = _text(os.path.join(RECIPE_DIR, "README.md"))
        start = raw.index("**What a person completes by hand for an app package.**")
        self.section = re.sub(r"\s+", " ", raw[start:raw.index("### 2. Make the override")])

    def test_the_framework_item_is_made_from_microsofts_redistributable(self):
        for needle in ("**Make the framework item once**", "an `msix` item of its own",
                       "`https://aka.ms/windowsappsdk/1.4/latest/Microsoft.WindowsAppRuntime.Redist.1.4.zip`",
                       "`MSIX/win10-x64/`", "at least the minimum that the download step prints"):
            self.assertIn(needle, self.section)

    def test_the_item_gets_a_requires_on_it(self):
        for needle in ("**Give the item a `requires` on it**", "`requires: [<the framework item>]`",
                       "Add :Input:pkginfo:requires array", "Add :Input:pkginfo:requires:0 string <the framework item>",
                       "A template's `requires` is carried into each new version"):
            self.assertIn(needle, self.section)

    def test_the_line_is_compared_at_every_version_and_a_newer_runtime_has_its_steps(self):
        for needle in ("**At every new version, compare the line that the download step prints**",
                       "a higher minimum of the same runtime", "publish a newer version of the framework item",
                       "build the catalogs, and only then", "another runtime", "make a new framework item",
                       "change the `requires`", "keep the override in the dry run",
                       "the package does not install without its framework"):
            self.assertIn(needle, self.section)

    def test_an_app_package_takes_no_arguments(self):
        self.assertIn("the client takes no arguments for it", self.section)
        for key in ("`installer.args`", "`switches`", "`product_code`", "`upgrade_code`"):
            self.assertIn(key, self.section)

    def test_the_cimian_recipe_does_not_add_the_requires_itself(self):
        """The framework item's name is the repository's own: it is set in the override or the template."""
        self.assertNotIn("requires", load(CIMIAN)["Input"]["pkginfo"])
        self.assertIn("this recipe does not add it", load(CIMIAN)["Description"])


class CimianRecipeTests(unittest.TestCase):
    """The recipe for any Cimian repository: its only step is CimianImporter, and nothing of the
    package tool is in it."""

    def test_the_only_step_is_the_cimian_importer(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "CimianImporter"])

    def test_the_inputs_and_the_arguments(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], load(PCMAN)["Input"]["NAME"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], load(PCMAN)["Input"]["PCMAN_TEMPLATE"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], "Acellus")
        self.assertEqual(recipe["Input"]["CIMIAN_SUBDIRECTORY"], "")
        self.assertEqual(sorted(recipe["Input"]), ["CIMIAN_NAME", "CIMIAN_SUBDIRECTORY", "NAME", "pkginfo"])
        self.assertEqual(recipe["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": ""})

    def test_the_pkginfo_gives_only_what_the_readme_states(self):
        self.assertEqual(load(CIMIAN)["Input"]["pkginfo"], {"developer": "GoldKey Corporation", "display_name": "Acellus"})

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
                     "cimian_architecture", "msi_product_code", "msi_upgrade_code", "checksum_verified",
                     "checksum_sha256", "CIMIAN_REPO"):
            self.assertNotIn("<key>%s</key>" % name, text)

    def test_no_value_of_the_cimian_recipe_is_a_path_a_catalog_or_a_hash(self):
        recipe = load(CIMIAN)
        values = [value for value in recipe["Input"].values() if isinstance(value, str)]
        values.extend(value for value in recipe["Process"][0]["Arguments"].values() if isinstance(value, str))
        for value in values:
            self.assertFalse(value.startswith(("/", "~", ".")), value)
            self.assertNotIn("Production", value)
            self.assertNotIn("Testing", value)

    def test_the_description_says_what_a_reader_must_know(self):
        description = load(CIMIAN)["Description"]
        for needle in ("CimianImporter", "dry run", "cimian_dry_run", "CIMIAN_REPO", "says that nothing is new",
                       "package's own Identity Version", "the bundle's version", "not the version of the application",
                       "identity name", "Windows App Runtime framework item in its requires"):
            self.assertIn(needle, description)
        self.assertNotIn("NOT verified yet", description)


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
            "**Status.", "**The file hosts.**", "## Run every override with `--override-dir`", "## With any Cimian repository",
            "## With the package tool (pcman)", "## a. ", "## g. ", "## Other facts", "## Tests")]
        self.assertEqual(positions, sorted(positions))

    def test_the_table_has_the_three_recipes(self):
        for name, identifier in (("Acellus-Win.download.recipe", "com.github.serrc-techops.download.Acellus-Win"),
                                 ("Acellus.cimian.recipe", "com.github.serrc-techops.cimian.Acellus"),
                                 ("Acellus.pcman.recipe", "com.github.serrc-techops.pcman.Acellus")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)

    def test_the_generic_way_has_the_same_steps_as_the_package_tools(self):
        self.assertEqual(len(self.commands(self.generic, "run")), 3)
        self.assertEqual(len(self.commands(self.generic, "verify-trust-info")), 2)
        self.assertEqual(len(self.commands(self.generic, "update-trust-info")), 1)
        self.assertEqual(len(self.commands(self.generic, "make-override")), 1)
        self.assertEqual(len(self.commands(self.generic, "repo-add")), 1)
        for heading in ("### 1. What must exist first", "### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER",
                        "### 3. First try: a dry run", "### 4. Switch a real run on",
                        "### 5. The real run, the catalogs, the second run",
                        "### 6. When a recipe or a processor changes upstream", "### A share that is not mounted"):
            self.assertIn(heading, self.generic)

    def test_every_command_of_each_way_names_its_own_recipe_and_the_override_dir(self):
        for text, recipe, other in ((self.generic, "Acellus.cimian", "Acellus.pcman"), (self.tool, "Acellus.pcman", "Acellus.cimian")):
            for name in ("run", "verify-trust-info", "update-trust-info", "make-override"):
                for command in self.commands(text, name):
                    with self.subTest(command=command):
                        self.assertIn("--override-dir=", command)
                        self.assertIn(recipe, command)
                        self.assertNotIn(other, command)
        self.assertEqual(len(self.commands(self.tool, "run")), 3)
        self.assertEqual(len(self.commands(self.tool, "make-override")), 1)

    def test_the_generic_way_names_nothing_of_the_package_tool_to_run(self):
        for word in ("pcman import", "pcman catalogs", "pcman versions", "pcman_root", "pcman_python", "PCMAN_TEMPLATE", "PcmanImporter"):
            self.assertNotIn(word, self.generic)
        self.assertIn("no package tool", self.generic)
        self.assertIn("no `msiinfo`", self.generic)

    def test_the_generic_way_gives_the_preference_the_switch_and_the_catalogs(self):
        for needle in ("defaults write com.github.autopkg CIMIAN_REPO -string", "Add :Input:cimian_dry_run bool false",
                       "Cimian's `makecatalogs`", "`CIMIAN_NAME`", "`CIMIAN_SUBDIRECTORY`",
                       "WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on.", "ParentRecipe",
                       "`Add-AppxProvisionedPackage -Online -PackagePath <file> -SkipLicense`",
                       "{type: msix, identity_name: GoldKeyCorporation.Acellus, version: <version>}",
                       "Install on one test PC through the Cimian client"):
            self.assertIn(needle, self.generic)

    def test_the_lines_that_the_generic_way_quotes_are_in_the_processor(self):
        source = _text(os.path.join(SHARED_DIR, "CimianImporter.py"))
        generic = self.generic.replace("`", "")
        for fragment in ("WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on.", "Would write ",
                         "No template: the pkginfo is built from the inputs.", "Nothing new: ", "Published ",
                         "Build the catalogs with makecatalogs.", "(the bundle's own version, not the application's)"):
            self.assertIn(fragment, source)
            self.assertIn(fragment.strip(), generic)

    def test_the_item_name_is_said_with_its_reason(self):
        self.assertIn("with a capital A: the name that packagers of this program are likely to have given it; "
                      "the override sets the repository's own name if it differs", re.sub(r"\s+", " ", self.generic))
        self.assertIn("the override sets the repository's own name if it differs", re.sub(r"\s+", " ", self.tool))

    def test_the_parent_recipe_is_the_recipe_the_override_was_made_from(self):
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.cimian.Acellus`**", self.generic.replace("\n", " "))
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Acellus`**", self.tool.replace("\n", " "))

    def test_the_package_tools_way_says_the_tool_is_not_in_this_repository(self):
        self.assertIn("**not part of this repository**", self.tool)
        self.assertIn("`PcmanImporter` of `../Win-PcmanProcessors/`", self.tool)

    def test_the_catalogs_step_says_not_run(self):
        text = re.sub(r"\s+", " ", self.tool)
        i = text.index("3. **Build the catalogs: `pcman catalogs`.**")
        self.assertIn("(Not run.)", text[i:text.index("4. The second run, by path again:", i)])


class ChainTests(_pcman_support.ToolTestCase):
    """The chain of this program counts as verified for the package tool's importer: the real
    ChecksumVerifier hashes the bundle, and the importer hashes it again and compares. The
    stand-in package tool is used; nothing else is run."""

    def chain_env(self, installer):
        run = {"pathname": installer, "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        values = {"%pathname%": installer, "%PCMAN_TEMPLATE%": load(PCMAN)["Input"]["PCMAN_TEMPLATE"]}
        env = {"pathname": installer, "pcman_root": self.root, "pcman_dry_run": False, "pcman_path": self.msi_bin,
               "store_package_version": BUNDLE_VERSION}
        env.update({k: v for k, v in verifier.env.items() if k.startswith("checksum_")})
        for name, value in load(PCMAN)["Process"][0]["Arguments"].items():
            env[name] = values.get(value, value)
        return env

    def bundle_file(self):
        return _pcman_support.write_app_package(os.path.join(self.downloads, FULL_NAME + ".msixbundle"),
                                                identity_name=IDENTITY_NAME, version=BUNDLE_VERSION)

    def test_the_chain_counts_as_verified_and_no_version_is_passed(self):
        self.behave(result=_pcman_support.result_file_content(name="Acellus", version=BUNDLE_VERSION, extension=".msixbundle"))
        bundle = self.bundle_file()
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, self.chain_env(bundle))
        self.assertIs(processor.env["pcman_repo_changed"], True)
        self.assertEqual([m for level, m in processor.message_levels if m.startswith("WARNING:")], [])
        argv = self.record()["argv"]
        self.assertEqual(argv[:4], ["import", bundle, "--template", "Acellus"])
        self.assertNotIn("--version", argv)

    def test_the_chain_is_refused_for_another_file(self):
        env = self.chain_env(self.bundle_file())
        env["pathname"] = _pcman_support.write_app_package(os.path.join(self.downloads, "other.msixbundle"),
                                                           identity_name=IDENTITY_NAME, payload=b"another file")
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        self.assertIn("not the file whose checksum was verified", str(caught.exception))
        self.assertFalse(self.was_run())


class CimianChainTests(_win_support.RepoTestCase):
    """The chain of this program with the real CimianImporter and a temporary repository: the steps of the
    download recipe leave their variables in the run, the recipe's own step reads them."""

    def bundle(self, name=FULL_NAME + ".msixbundle", identity_name=IDENTITY_NAME, version=BUNDLE_VERSION, payload=b"made-up"):
        return write_bundle(os.path.join(self.downloads, name), identity_name, version, payload)

    def run_chain(self, installer, **extra):
        """What the recipe's step is given, with the substitutions that AutoPkg makes. The run holds what
        the download step leaves (among them store_package_version) and a `version` that some earlier
        step may have left: the recipe's empty argument keeps it out."""
        recipe = load(CIMIAN)
        run = {"pathname": installer, "version": "9.9.9", "store_package_version": BUNDLE_VERSION,
               "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        run.update({key: value for key, value in verifier.env.items() if key.startswith("checksum_")})
        run.update(recipe["Input"])
        arguments = {}
        for name, value in recipe["Process"][0]["Arguments"].items():
            for variable in re.findall(r"%([A-Za-z_]+)%", value):
                value = value.replace("%" + variable + "%", str(run[variable]))
            arguments[name] = value
        env = dict(run)
        env.update({"cimian_repo": self.repo, "cimian_dry_run": False, "cimian_path": self.empty_bin})
        env.update(arguments)
        env.update(extra)
        return _win_support.run_processor(_win_support.cimian.CimianImporter, env)

    @_win_support.needs_yaml
    def test_the_chain_publishes_into_an_empty_repository_as_the_recipes_inputs_say(self):
        processor, messages = self.run_chain(self.bundle())
        self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published")
        self.assertEqual([m for m in messages if m.startswith("WARNING: published WITHOUT")], [])
        self.assertEqual(processor.env["cimian_version_imported"], BUNDLE_VERSION)  # the bundle's, not the run's 9.9.9
        new = self.read_pkginfo("Acellus-%s.yaml" % BUNDLE_VERSION)
        self.assertEqual(new["name"], "Acellus")
        self.assertEqual(new["display_name"], "Acellus")
        self.assertEqual(new["developer"], "GoldKey Corporation")
        self.assertEqual(new["installer"]["type"], "msix")
        self.assertTrue(new["installer"]["location"].endswith(".msixbundle"))
        self.assertEqual(new["installer"]["hash"], _win_support.sha256_hex(self.bundle()))
        self.assertEqual(new["installs"], [{"type": "msix", "identity_name": IDENTITY_NAME, "version": BUNDLE_VERSION}])
        self.assertNotIn("supported_architectures", new)  # a bundle names none
        self.assertNotIn("requires", new)  # a person adds it (README: what a person completes by hand)
        self.assertTrue(any("(the bundle's own version, not the application's)" in m for m in messages))

    @_win_support.needs_yaml
    def test_a_template_keeps_its_requires_and_its_install_check_gets_the_new_version(self):
        self.put_pkginfo("app/Acellus-2026.1001.1000.0.yaml", (
            "name: Acellus\ndisplay_name: Acellus\nversion: 2026.1001.1000.0\ncatalogs:\n- Production\n"
            "requires:\n- Example-Framework\n"
            "installs:\n- type: msix\n  identity_name: GoldKeyCorporation.Acellus\n  version: 2026.1001.1000.0\n"
            "installer:\n  type: msix\n  location: app/Acellus-2026.1001.1000.0.msixbundle\n  hash: " + "a" * 64 + "\n"))
        processor, messages = self.run_chain(self.bundle())
        new = self.read_pkginfo("app/Acellus-%s.yaml" % BUNDLE_VERSION)
        self.assertEqual(new["requires"], ["Example-Framework"])
        self.assertEqual(new["catalogs"], ["Production"])
        self.assertEqual(new["installs"], [{"type": "msix", "identity_name": IDENTITY_NAME, "version": BUNDLE_VERSION}])
        self.assertEqual(new["installer"]["location"], "app/Acellus-%s.msixbundle" % BUNDLE_VERSION)
        self.assertEqual(new["developer"], "GoldKey Corporation")  # a key that the template lacks is added
        processor, messages = self.run_chain(self.bundle(name="dry.msixbundle", version="2026.1101.1200.0"),
                                             cimian_dry_run=True)
        self.assertTrue(any(m.startswith("Template: Acellus %s (" % BUNDLE_VERSION) for m in messages))

    @_win_support.needs_yaml
    def test_a_package_with_another_identity_name_is_refused(self):
        self.put_pkginfo("app/Acellus-2026.1001.1000.0.yaml", (
            "name: Acellus\nversion: 2026.1001.1000.0\ncatalogs:\n- Production\n"
            "installs:\n- type: msix\n  identity_name: GoldKeyCorporation.Acellus\n  version: 2026.1001.1000.0\n"
            "installer:\n  type: msix\n  location: app/Acellus-2026.1001.1000.0.msixbundle\n  hash: " + "a" * 64 + "\n"))
        before = self.repo_tree()
        with self.assertRaises(_win_support.ProcessorError) as caught:
            self.run_chain(self.bundle(name="other.msixbundle", identity_name="Example.Other.App"))
        self.assertIn("another product", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    @_win_support.needs_yaml
    def test_a_second_run_with_the_same_file_has_nothing_new(self):
        self.run_chain(self.bundle())
        before = self.repo_tree()
        processor, messages = self.run_chain(self.bundle())
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertEqual(self.repo_tree(), before)

    @_win_support.needs_yaml
    def test_the_chain_is_refused_for_another_file(self):
        installer = self.bundle()
        run = {"pathname": installer, "expected_sha256": _win_support.sha256_hex(installer)}
        verifier, _ = _win_support.run_processor(_win_support.checksum.ChecksumVerifier, run)
        other = self.bundle(name="other.msixbundle", payload=b"not the file that was verified")
        env = {"pathname": other, "cimian_name": "Acellus", "version": "", "cimian_repo": self.repo,
               "cimian_dry_run": False, "cimian_path": self.empty_bin}
        env.update({key: value for key, value in verifier.env.items() if key.startswith("checksum_")})
        before = self.repo_tree()
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_win_support.cimian.CimianImporter, env)
        self.assertIn("not the file whose checksum was verified", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)


if __name__ == "__main__":
    unittest.main()
