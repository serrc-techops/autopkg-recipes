"""Tests of the three Grammarly recipes and this README. Nothing here runs AutoPkg or uses the network.
The packer's scripts are tested in test_packager.py.

The recipes are read as property lists. The step that names our shared
processor is compared with what that processor declares (see
../../Win-SharedProcessors). The shared folder's tests are run separately.

No vendor hash of this program was found: the vendor's installer is verified by its
Authenticode signature (the shared AuthenticodeVerifier, tested in its own folder) before
the packer, which hands that over to the packed EXE (tested in test_packager.py). The tests
make sure that the step is where it belongs, that the descriptions and the README say what it
proves and what not, and that no recipe invents a checksum.

The plain installer was rehearsed on 2026-11-13 (under AutoPkg, and as SYSTEM on a test PC,
where it installed into SYSTEM's own profile). So the download recipe now packs it with
GrammarlyPerUserPackager into an EXE that installs Grammarly for each person at sign-in; that
packed form that ran on 2026-11-16 is pinned below. The main caveat (the program installs per user, a Cimian
client installs as SYSTEM, so the item installs at each sign-in) is in the Description of every
recipe and at the top of the README, and tests check that nobody can overlook it. The version label is
read from the EXE by the shared processor WindowsExeVersion: the tests check that
the recipes use it as the brief says (a step after EndOfCheckPhase, the label passed
on as pcman_version) and compare its arguments with what it declares.
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
PCMAN_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-PcmanProcessors")
PCMAN_TESTS_DIR = os.path.join(PCMAN_DIR, "tests")
if SHARED_TESTS_DIR not in sys.path:
    sys.path.insert(0, SHARED_TESTS_DIR)

if PCMAN_TESTS_DIR not in sys.path:
    sys.path.insert(0, PCMAN_TESTS_DIR)
if RECIPE_DIR not in sys.path:
    sys.path.insert(0, RECIPE_DIR)  # GrammarlyPerUserPackager

import _win_support  # noqa: E402,F401  (installs the autopkglib stand-in, imports the processors)
import _pcman_support  # noqa: E402,F401  (the stand-in for the package tool, and its processor)
import test_public_repository as shared_hygiene  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "Grammarly-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "Grammarly.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "Grammarly.pcman.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
# Processors that are part of AutoPkg itself.
CORE_PROCESSORS = ("URLDownloader", "EndOfCheckPhase")
# Required inputs that a recipe must NOT pass: they come from AutoPkg's
# preferences or the override on the machine that runs it.
SUPPLIED_BY_THE_MACHINE = {"PcmanImporter": {"pcman_root"}}
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir", "pcman_timeout")
HEX_64 = re.compile(r"(?i)\b[0-9a-f]{64}\b")
# File names of recipes in repositories that the build machine has (read in the
# survey of the earlier readings). AutoPkg takes the first match by name and says
# nothing, so none of our file names may be one of these.
NAMES_OF_OTHER_REPOSITORIES = (
    "Zoom-Win.download", "Zoom64-Win.download", "GoogleChrome-Win.download", "GoogleChrome-Win64.download",
    "7zip-Win64.download", "Zoom.munki", "GoogleChrome.munki", "Zoom.download", "GoogleChrome.download",
    "Grammarly.download", "Grammarly.munki", "GrammarlyFS.download", "GrammarlyFS.munki",
)


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def processor_classes():
    import importlib
    classes = {}
    for name in ("PcmanImporter", "CimianImporter", "ChecksumVerifier", "GitHubAssetDigest", "WindowsExeVersion",
                 "AuthenticodeVerifier"):
        classes[name] = getattr(importlib.import_module(name), name)
    return classes


def shared_steps(recipe):
    """The steps that name a processor of this repository, of either folder: (name, arguments)."""
    for step in recipe["Process"]:
        for prefix in (SHARED_PREFIX, PCMAN_PREFIX):
            if step["Processor"].startswith(prefix):
                yield step["Processor"][len(prefix):], step.get("Arguments", {})


def first_sentence(text):
    return re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]


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
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.Grammarly-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".pcman.Grammarly")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, ["URLDownloader", "EndOfCheckPhase", SHARED_PREFIX + "AuthenticodeVerifier",
                                 SHARED_PREFIX + "WindowsExeVersion", "GrammarlyPerUserPackager"])

    def test_the_version_step_comes_after_the_end_of_the_check_phase_with_only_the_pathname(self):
        steps = load(DOWNLOAD)["Process"]
        names = [step["Processor"] for step in steps]
        self.assertGreater(names.index(SHARED_PREFIX + "WindowsExeVersion"), names.index("EndOfCheckPhase"))
        version_step = steps[names.index(SHARED_PREFIX + "WindowsExeVersion")]
        self.assertEqual(version_step.get("Arguments"), {"pathname": "%pathname%",
                                                         "expected_product_name": "Grammarly for Windows",
                                                         "expected_company_name": "Grammarly Inc."})
        # nothing of the processor's inputs is changed: set_version stays at its default
        self.assertNotIn("set_version", read(DOWNLOAD))

    def test_there_is_exactly_one_version_step_and_it_is_in_the_download_recipe_only(self):
        self.assertEqual(read(DOWNLOAD).count("WindowsExeVersion</string>"), 1)
        self.assertNotIn("WindowsExeVersion</string>", read(PCMAN))

    def test_the_pcman_recipe_has_one_step(self):
        steps = [step["Processor"] for step in load(PCMAN)["Process"]]
        self.assertEqual(steps, [PCMAN_PREFIX + "PcmanImporter"])

    def test_the_downloader_arguments(self):
        recipe = load(DOWNLOAD)
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args["url"], "%DOWNLOAD_URL%")
        self.assertEqual(recipe["Input"]["DOWNLOAD_URL"], "https://download-windows.grammarly.com/GrammarlyInstaller.exe")
        self.assertTrue(recipe["Input"]["DOWNLOAD_URL"].startswith("https://"))

    def test_the_file_name_of_the_address_ends_in_exe_so_no_file_name_is_set(self):
        recipe = load(DOWNLOAD)
        url = recipe["Input"]["DOWNLOAD_URL"]
        self.assertNotIn("?", url)
        self.assertTrue(url.rsplit("/", 1)[-1].endswith(".exe"))
        self.assertNotIn("filename", recipe["Process"][0]["Arguments"])

    def test_the_address_is_the_one_that_was_read_and_has_no_version_in_it(self):
        url = load(DOWNLOAD)["Input"]["DOWNLOAD_URL"]
        self.assertEqual(url, "https://download-windows.grammarly.com/GrammarlyInstaller.exe")
        self.assertIsNone(re.search(r"[0-9]", url.rsplit("/", 1)[-1]))

    def test_the_download_recipe_has_no_parent(self):
        self.assertNotIn("ParentRecipe", read(DOWNLOAD))

    def test_the_download_description_says_what_was_fetched_and_what_was_not_rehearsed(self):
        text = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        self.assertIn("seen on a test PC on 2026-11-13, where the installer run as SYSTEM installed into SYSTEM's own profile", text)
        self.assertIn("On 2026-11-16 a build of this recipe ran under AutoPkg into a scratch repository", text)
        self.assertIn("but with it the per-user install path and the removal have not run", text)
        self.assertIn("This recipe's output pathname is the PACKED EXE built below, not the vendor's file", text[:1000])
        self.assertIn("then packs it with GrammarlyPerUserPackager", text)

    def test_the_download_description_says_that_the_version_is_read_from_the_exe(self):
        text = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        self.assertIn("reads the version from the EXE itself with the shared processor WindowsExeVersion", text)
        self.assertIn("the address has no version in it", text)

    def test_the_pcman_description_says_where_the_label_comes_from(self):
        text = re.sub(r"\s+", " ", load(PCMAN)["Description"])
        self.assertIn("The version label is the one that the download recipe's WindowsExeVersion step read from the "
                      "downloaded installer itself", text)
        self.assertIn("the packed EXE carries that installer and keeps its version", text)
        self.assertIn("The label must equal what a person reads in the installer's properties", text)
        self.assertIn("that was the first build", text)

    def test_no_description_claims_a_rehearsal(self):
        for path in (DOWNLOAD, PCMAN):
            text = load(path)["Description"]
            self.assertNotIn("Rehearsed", text)
            self.assertNotIn("rehearsed on", text)

    def test_the_inputs_of_the_pcman_recipe(self):
        recipe = load(PCMAN)
        self.assertEqual(recipe["Input"]["NAME"], "Grammarly")
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "grammarly")
        args = recipe["Process"][0]["Arguments"]
        self.assertEqual(args, {"pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%",
                                "pcman_version": "%version%"})

    def test_no_file_name_of_ours_is_the_name_of_a_recipe_in_another_repository(self):
        ours = [name[: -len(".recipe")].casefold() for name in (os.path.basename(DOWNLOAD), os.path.basename(PCMAN))]
        for other in NAMES_OF_OTHER_REPOSITORIES:
            self.assertNotIn(other.casefold(), ours)
        for name in ours:
            self.assertNotIn(name, [other.casefold() for other in NAMES_OF_OTHER_REPOSITORIES])

    def test_the_template_keeps_the_name_that_the_readme_names(self):
        self.assertEqual(load(PCMAN)["Input"]["PCMAN_TEMPLATE"], "grammarly")

    def test_the_label_of_an_exe_is_passed_from_the_processor_and_from_nothing_else(self):
        """An EXE needs pcman_version. It is the `version` that WindowsExeVersion
        outputs, never a value written in the recipe, an input or a hash."""
        self.assertNotIn("pcman_version", read(DOWNLOAD))
        text = read(PCMAN)
        self.assertEqual(text.count("<key>pcman_version</key>"), 1)
        self.assertEqual(load(PCMAN)["Process"][0]["Arguments"]["pcman_version"], "%version%")
        # the packer passes the label on unchanged: it gets %version% and has no input that sets another
        packer = [step for step in load(DOWNLOAD)["Process"] if step["Processor"] == "GrammarlyPerUserPackager"][0]
        self.assertEqual(packer["Arguments"]["version"], "%version%")
        for key in ("VERSION", "PCMAN_VERSION", "LABEL"):
            self.assertNotIn("<key>%s</key>" % key, text)
            self.assertNotIn("<key>%s</key>" % key, read(DOWNLOAD))
        for path in (DOWNLOAD, PCMAN):
            self.assertNotIn("exe_product_version", read(path))
            self.assertNotIn("exe_file_version", read(path))

    def test_the_processor_that_gives_the_label_declares_the_output_the_recipe_uses(self):
        self.assertIn("version", processor_classes()["WindowsExeVersion"].output_variables)
        self.assertIn("pathname", processor_classes()["WindowsExeVersion"].input_variables)

    def test_no_stop_on_an_unchanged_download_and_no_latest_only(self):
        for path in (DOWNLOAD, PCMAN):
            text = read(path)
            self.assertNotIn("StopProcessingIf", text)
            self.assertNotIn("latest_only", text)

    def test_no_blocking_applications(self):
        for path in (DOWNLOAD, PCMAN):
            self.assertNotIn("blocking_applications", read(path))

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in (DOWNLOAD, PCMAN):
            text = read(path)
            for name in NEVER_IN_A_RECIPE:
                self.assertNotIn("<key>%s</key>" % name, text)
            for name in ("catalogs", "catalog", "pcman_catalogs", "path", "repo", "directory"):
                self.assertNotIn("<key>%s</key>" % name, text)

    def test_no_value_of_a_recipe_is_a_path_or_a_catalog(self):
        for path in (DOWNLOAD, PCMAN):
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


SIGNER = {"CN": "Grammarly, Inc.", "O": "Grammarly, Inc.", "L": "San Francisco", "ST": "California", "C": "US"}
ROOT = "digicert-trusted-root-g4"


class SignatureTests(unittest.TestCase):
    """The vendor's installer is verified by its signature before the packer, and the packer hands that
    over to the packed EXE. The recipes and the README say so, and what it does not prove."""

    def test_the_step_checks_the_downloaded_installer_with_the_vendors_name_and_the_pinned_root(self):
        import AuthenticodeVerifier
        steps = [step for step in load(DOWNLOAD)["Process"] if step["Processor"] == SHARED_PREFIX + "AuthenticodeVerifier"]
        self.assertEqual(len(steps), 1)
        arguments = steps[0]["Arguments"]
        self.assertEqual(arguments["pathname"], "%pathname%")
        self.assertEqual(arguments["expected_signer"], SIGNER)
        self.assertEqual(arguments["code_signing_roots"], [ROOT])
        self.assertEqual(arguments["timestamp_roots"], [ROOT])
        self.assertIn(ROOT, AuthenticodeVerifier.PINNED_ROOTS)
        self.assertNotIn("osslsigncode_path", arguments)

    def test_the_step_comes_right_after_the_check_phase_and_before_the_version_step_and_the_packer(self):
        names = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        position = names.index(SHARED_PREFIX + "AuthenticodeVerifier")
        self.assertEqual(position, names.index("EndOfCheckPhase") + 1)
        self.assertLess(position, names.index(SHARED_PREFIX + "WindowsExeVersion"))
        self.assertLess(position, names.index("GrammarlyPerUserPackager"))

    def test_the_packer_hands_over_exactly_the_pair_that_the_importers_accept(self):
        import AuthenticodeVerifier
        import CimianImporter
        import GrammarlyPerUserPackager as packer
        import PcmanImporter
        self.assertEqual(packer.SIGNATURE_FLAG_VARIABLE, CimianImporter.SIGNATURE_FLAG_VARIABLE)
        self.assertEqual(packer.SIGNATURE_HASH_VARIABLE, CimianImporter.SIGNATURE_HASH_VARIABLE)
        self.assertEqual(packer.SIGNATURE_HASH_VARIABLE, PcmanImporter.SIGNATURE_HASH_VARIABLE)
        self.assertIn(packer.SIGNATURE_HASH_VARIABLE, AuthenticodeVerifier.AuthenticodeVerifier.output_variables)
        self.assertIn(packer.SIGNATURE_HASH_VARIABLE, packer.GrammarlyPerUserPackager.output_variables)

    def test_every_description_says_how_the_download_is_verified_first(self):
        self.assertIn("verified by the Authenticode signature of the vendor's installer, not by a hash",
                      first_sentence(load(DOWNLOAD)["Description"]))
        for path in (CIMIAN, PCMAN):
            with self.subTest(path=os.path.basename(path)):
                self.assertTrue(load(path)["Description"].startswith(
                    "This import is verified by the signature step of the download recipe"))

    def test_the_download_description_says_what_is_checked_and_what_is_not(self):
        text = re.sub(r"\s+", " ", load(DOWNLOAD)["Description"])
        for needle in ("no hash was found for the file", "AuthenticodeVerifier", "before anything reads or packs the file",
                       "CN and O Grammarly, Inc., L San Francisco, ST California, C US, and no OU",
                       "ProductName must be Grammarly for Windows", ROOT, "verified timestamp", "CRLs",
                       "signature_verified and signature_sha256", "the EXE is built in that run",
                       "The packed EXE itself is not signed",
                       "does not prove that a release that the vendor itself signed is harmless",
                       "not the intermediate's", "needs osslsigncode", "NOT run with AutoPkg"):
            self.assertIn(needle, text)

    def test_the_child_descriptions_name_the_flag_for_a_run_without_the_step(self):
        for path, flag in ((CIMIAN, "cimian_allow_unverified"), (PCMAN, "pcman_allow_unverified")):
            text = re.sub(r"\s+", " ", load(path)["Description"])
            with self.subTest(path=os.path.basename(path)):
                self.assertIn("Without that step", text)
                self.assertIn("%s to true" % flag, text)
                self.assertIn("published, NOT verified", text)

    def test_the_pcman_description_says_what_is_not_established_about_what_still_protects(self):
        text = re.sub(r"\s+", " ", load(PCMAN)["Description"])
        self.assertIn("Whether the package tool has a check of the product for an EXE, like its upgrade code check "
                      "for an MSI, was NOT established", text)
        self.assertNotIn("refuses an MSI whose upgrade code differs", text)
        self.assertIn("pcman_dry_run", text)
        self.assertIn("dry run", text)

    def test_no_recipe_sets_the_allowance_or_a_verified_flag_itself(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = read(path)
            for word in ("<key>pcman_allow_unverified</key>", "<key>cimian_allow_unverified</key>",
                         "<key>checksum_verified</key>", "<key>signature_verified</key>",
                         "<key>signature_sha256</key>", "<key>checksum_sha256</key>"):
                self.assertNotIn(word, text)

    def test_no_recipe_invents_a_checksum_step(self):
        """The only hash in a recipe is the LZMA SDK's (the stub of the packer), the same value as the
        Microsoft 365 Apps folder's; nothing claims a hash of the download."""
        office = os.path.join(os.path.dirname(RECIPE_DIR), "Win-Microsoft365Apps", "Microsoft365Apps-Win.download.recipe")
        sdk = load(office)["Input"]["SFX_SDK_SHA256"]
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = read(path)
            self.assertNotIn("ChecksumVerifier", text)
            self.assertNotIn("expected_sha256", text)
            self.assertNotIn("CodeSignatureVerifier", text)
            self.assertEqual(HEX_64.findall(text), [sdk] if path == DOWNLOAD else [])
            hashes = re.findall(r"(?i)<key>([^<]*sha256[^<]*)</key>", text)
            self.assertEqual(hashes, ["SFX_SDK_SHA256", "sfx_sdk_sha256"] if path == DOWNLOAD else [])

    def test_the_readme_opens_with_a_status_line_and_a_verification_line_both_bold(self):
        lines = [line for line in read(README).splitlines() if line.strip()]
        self.assertTrue(lines[0].startswith("# "))
        self.assertTrue(lines[1].startswith("A Windows recipe pair: Grammarly for Windows, the vendor's `.exe` installer packed"))
        status, verified = lines[2], lines[3]
        self.assertTrue(status.startswith("**Status. Main caveat:"), status[:100])
        self.assertTrue(status.endswith("**"))
        self.assertTrue(verified.startswith("**Verified by the installer's signature."), verified[:60])
        self.assertTrue(verified.endswith("**"))
        for needle in ("`AuthenticodeVerifier`", "BEFORE the packer", "the packer then hands that verification over to "
                       "the packed EXE that it builds from that installer in the same run",
                       "The packed EXE itself is not signed", "That step and the hand-over were NOT run with AutoPkg",
                       "The packed EXE in its current form has run once on one test PC, as SYSTEM; no person has received "
                       "Grammarly through it",
                       "Do not put the item into a manifest before the steps of \"What must be proven on a PC\" have been done"):
            self.assertIn(needle, verified)

    def test_the_status_line_says_what_was_read_and_what_was_not_established(self):
        status = [line for line in read(README).splitlines() if line.startswith("**Status.")][0]
        text = re.sub(r"\s+", " ", status)
        for needle in (
                "That was the first build", "also ran the same day:",
                "**With the current form the per-user INSTALL path (a person without Grammarly) has not run**; it ran "
                "with the first build only",
                "NOT established: a real sign-in starting the task; a standard user; a second user; a first sign-in with "
                "a new profile; an upgrade to a newer staged version; the failure counter; a non-zero exit code coming "
                "back through the stub; the item through the Cimian client (install, check, removal); Windows 10; a PC "
                "whose policy sets an execution policy, or with AppLocker or WDAC",
                "and not roaming profiles",
                "Read on 2026-11-13: `https://download-windows.grammarly.com/GrammarlyInstaller.exe` answered a HEAD "
                "request with 200, no redirect",
                "`Content-Length` 87044640", "the address holds no version",
                "was read in full on that day and links that same address as its installer",
                "`GrammarlyInstaller.exe /S`", "`GrammarlyInstaller.exe /S /uninstall`", "`/ignore-os-version`",
                "No hash for the file was found",
                "READ on 2026-11-16: Microsoft's Store catalog", "installer type `exe`, scope `user`",
                "the silent switch `/windows-store`", "the Store product is the same per-user EXE, not an app package, "
                "so nothing can be provisioned for all users",
                "When a run fails, STOP: nothing was written",
                "and only then look at the trust information",
                "Never accept new trust information first"):
            self.assertIn(needle, text)
        for gone in ("Run on 2026-10", "was REFUSED on", "ran for real", "pcman catalogs` ran"):
            self.assertNotIn(gone, text)

    def test_the_status_line_opens_with_the_main_caveat_and_its_consequences(self):
        status = re.sub(r"\s+", " ", [line for line in read(README).splitlines() if line.startswith("**Status.")][0])
        head = status[:900]
        for needle in ("installs PER USER, into the profile of the account that runs its installer",
                       "a Cimian client runs installers as SYSTEM",
                       "the plain installer as an item gives the program to nobody",
                       "a PACKED EXE", "registers a scheduled task that runs at the sign-in of any user, as that user"):
            self.assertIn(needle, head)
        for needle in ("every person who signs in on a PC with this item gets Grammarly in their profile (about 85 MB each), "
                       "so it suits PCs of one person and not shared ones",
                       "the item's version is only the version of the staged installer, and the install check is the "
                       "entry (and the task), not any person's Grammarly",
                       "each real run then publishes about 87 MB more, and a person decides how often to run it",
                       "The item must NOT go into a manifest until the steps of \"What must be proven on a PC\" below have been done"):
            self.assertIn(needle, status)

    def test_the_readme_has_a_section_on_the_label_with_the_two_lines_of_the_processor(self):
        text = re.sub(r"\s+", " ", read(README))
        self.assertIn("## The label", text)
        self.assertIn("`version is ..., taken from ...`", text)
        self.assertIn("the ProductVersion string when that is numbers and dots only, else the four numbers of the "
                      "fixed file information", text)
        self.assertIn("compare them with the file's properties on a Windows PC", text)
        self.assertLess(text.index("## The label"), text.index("## a."))

    def test_the_readme_says_that_the_program_updates_itself_so_a_hosted_version_is_a_floor(self):
        text = re.sub(r"\s+", " ", read(README))
        self.assertIn("Grammarly updates itself in each profile, so a hosted version sets a floor at best", text)
        self.assertIn("a check by Grammarly's own version would fight the updater", text)
        self.assertIn("it changes nobody's Grammarly", text)
        self.assertIn("**Grammarly installs per user.**", text)

    def test_the_readme_says_what_the_signature_proves_and_what_still_protects(self):
        text = re.sub(r"\s+", " ", read(README))
        for needle in ("**The download is verified by the installer's signature, and the packed EXE by being built from "
                       "that installer in the same run.**", "`CN=Grammarly, Inc.`", "`O=Grammarly, Inc.`", "`C=US`",
                       "`digicert-trusted-root-g4`", "**The packed EXE.**",
                       "it hashes the copy again after it was put into the stage", "the EXE is built in this run",
                       "A `signature_sha256` of another file stops the build", "The EXE itself carries no signature",
                       "**Checked on 2026-11-19**", "the same file with one byte changed was refused",
                       "a bad release that Grammarly itself signed passes", "only the signing certificate's CRL is read",
                       "**The step needs `osslsigncode`**", "**The label and the product.**", "**The same product.**", "`L=San Francisco`",
                       "`ST=California`", "**An older release, signed for real.**", "It does not refuse an older version",
                       "1 KB of other bytes put into its certificate table", "`Grammarly Inc.`",
                       "For an MSI the package tool refuses a different upgrade code",
                       "Whether it has an equivalent check for an EXE was NOT established by the writer",
                       "Without the signature step, a file of another product"):
            self.assertIn(needle, text)

    def test_the_real_run_steps_need_only_the_dry_run_switch(self):
        text = read(README)
        self.assertIn("## d. Switch a real run on\n", text)
        self.assertIn("### 4. Switch a real run on\n", text)
        self.assertNotIn("NOT YET", text)
        self.assertLess(text.index("**Status."), text.index("**Verified by the installer's signature."))
        self.assertLess(text.index("**Verified by the installer's signature."), text.index("## a."))

    def test_the_hand_command_uses_the_template_and_the_label(self):
        """S2: after the template exists, `pcman import` without --template would make a second item.
        An EXE needs its label."""
        text = read(README)
        self.assertNotIn("with the same command", text)
        match = re.search(r"\n    (pcman import <the file> --template grammarly[^\n]*)\n", text)
        self.assertTrue(match)
        self.assertIn("--version <the label>", match.group(1))
        self.assertNotIn("--name", match.group(1))
        self.assertNotIn("--build", match.group(1))
        self.assertIn("It uses the template, so it makes no second item", re.sub(r"\s+", " ", text))
        # the only `pcman import` with --name is the first import of step a.3
        first_imports = [m for m in re.finditer(r"pcman import [^`]*?--name", text)]
        self.assertEqual(len(first_imports), 1)
        self.assertLess(first_imports[0].start(), text.index("## b."))

    def test_the_override_lines_that_allow_an_unverified_run_are_two_and_marked(self):
        text = read(README)
        self.assertIn("Add :Input:pcman_dry_run bool false", text)
        self.assertIn("Add :Input:pcman_allow_unverified bool true", text)
        self.assertIn("Both lines are needed", text)
        self.assertIn("The download was not verified: no step of the recipe set checksum_verified", text)
        # the real text of the refusal, as the shared importer gives it
        import PcmanImporter
        refusal = "The download was not verified: %s. Nothing was published." % PcmanImporter.UNVERIFIED_REASON
        self.assertIn(refusal, re.sub(r"\s+", " ", text))
        self.assertIn("published, NOT verified", text)
        self.assertIn("published WITHOUT a verified download", text)
        self.assertIn("**Without the signature step**", text)
        self.assertIn("**Only when the signature step cannot be used**", text)


class SharedProcessorTests(unittest.TestCase):
    def test_every_named_processor_exists(self):
        for path in (DOWNLOAD, PCMAN):
            for step in load(path)["Process"]:
                name = step["Processor"]
                if name.startswith(SHARED_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, name[len(SHARED_PREFIX):] + ".py")), name)
                elif name.startswith(PCMAN_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(PCMAN_DIR, name[len(PCMAN_PREFIX):] + ".py")), name)
                elif name not in CORE_PROCESSORS:
                    self.assertTrue(os.path.isfile(os.path.join(RECIPE_DIR, name + ".py")), name)

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

    def test_every_required_input_is_passed_or_comes_from_the_machine(self):
        classes = processor_classes()
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

    def test_the_input_that_a_core_processor_needs_is_there(self):
        """URLDownloader needs `url`; the recipe passes it."""
        self.assertIn("url", load(DOWNLOAD)["Process"][0]["Arguments"])


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
            "Grammarly-Win.download.recipe", "Grammarly.cimian.recipe", "Grammarly.pcman.recipe", "README.md",
            "GrammarlyPerUserPackager.py",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
            os.path.join("tests", "test_packager.py"),
        ]))


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
        self.assertEqual(len([c for c in commands if c.startswith("autopkg run")]), 6)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg verify-trust-info")]), 4)
        self.assertEqual(len([c for c in commands if c.startswith("autopkg update-trust-info")]), 2)
        for command in commands:
            with self.subTest(command=command):
                self.assertRegex(
                    command,
                    r"^autopkg (run|verify-trust-info|update-trust-info)( -vv?)? "
                    r"--override-dir=<the Windows overrides folder> "
                    r"<the Windows overrides folder>/Grammarly\.(?:cimian|pcman)\.recipe$",
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

    def test_the_steps_of_the_rehearsal_are_there(self):
        for needle in ("pcman catalogs", "pcman versions grammarly", "PlistBuddy", "verify-trust-info",
                       "update-trust-info", "Failed local trust verification", "Nothing new",
                       "DRY RUN", "--build", "repo-add", "-string", "make-override"):
            self.assertIn(needle, self.text)

    def test_the_name_check_comes_before_the_override_and_the_parent_is_read_after_it(self):
        text = read(README)
        check = text.index("autopkg list-recipes | grep -i Grammarly-Win")
        override = text.index("    autopkg make-override --override-dir=")
        self.assertLess(check, override)
        self.assertIn("First check that no other recipe has the same name.", text)
        self.assertIn("Each name must be listed once, from this repository.", text)
        self.assertIn("autopkg list-recipes | grep -i Grammarly.pcman", text)
        self.assertIn("read\n`ParentRecipe`", text)
        step = re.sub(r"\s+", " ", text[override:])
        self.assertIn(
            "**Open the written file and read `ParentRecipe`: it must be "
            "`com.github.serrc-techops.pcman.Grammarly`**",
            step,
        )
        self.assertIn("com.github.serrc-techops.pcman.Grammarly", text[override:])

    def test_the_readme_says_that_the_label_is_the_installers_version_and_nothing_compares_it(self):
        heading = "## The label is the installer's version, and nothing compares it with the product's"
        self.assertIn(heading, self.raw)
        start = self.text.index(heading)
        section = self.text[start:self.text.index("## Run every override")]
        for needle in ("the `ProductVersion` of the downloaded setup file", "`GrammarlyInstaller.exe`",
                       "No step of this recipe compares the two",
                       "the recipe has no other version to compare it with",
                       "the address has none, and the recipe reads no other page",
                       "would still publish under the setup file's number",
                       "that number orders the versions in the repository",
                       "does not check this at any run", "A person checks it, at the first dry run",
                       "with `-v`", "the Details tab", "that was one file",
                       "the vendor's release notes", "stop and tell the owner before anything is published"):
            self.assertIn(needle, section)
        self.assertLess(self.raw.index(heading), self.raw.index("## a."))
        step = self.raw[self.raw.index("## c."):self.raw.index("## d.")]
        self.assertIn("autopkg run -v --override-dir=", step)

    def test_the_readme_states_no_hash(self):
        """S7: a README that states a SHA-256 (64 hex digits) could be taken for a check."""
        self.assertIsNone(HEX_64.search(self.raw))

    def test_the_first_import_has_the_label_and_keeps_the_template_name(self):
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        self.assertTrue(match)
        command = re.sub(r"\s+", " ", match.group(1))
        self.assertIn("--name grammarly", command)
        self.assertIn("--version <the label that the first dry run prints>", command)
        self.assertIn("--no-prompt", command)

    def test_the_first_import_is_a_proposal_of_the_packed_exe_with_no_arguments(self):
        """The packed EXE runs its own setup.bat: no install arguments. The architecture was not read."""
        match = re.search(r"pcman import ([^`]*?--build)", self.raw, re.S)
        command = re.sub(r"\s+", " ", match.group(1))
        self.assertTrue(command.startswith("<the override's cache folder>/GrammarlyPerUser-<version>.exe "))
        for flag in ("--display-name", "--category", "--developer", "--description", "--directory", "--icon"):
            self.assertIn(flag, command)
        for flag in ("--install-arguments", "--install-path", "--architectures", "Program Files", "/S"):
            self.assertNotIn(flag, command)
        step = re.sub(r"\s+", " ", self.raw[self.raw.index("3. **The template item"):self.raw.index("## b.")])
        for needle in ("as a proposal that was NOT run", "No install arguments: the packed EXE takes none",
                       "neither is an item made from the plain installer",
                       "name: 'Grammarly per-user deployment'", "uninstall_command:", "uninstall_arguments:",
                       "Grammarly Deployment\\remove.ps1",
                       "A check on a per-user path is never true for another user",
                       "a check by Grammarly's own version would fight the updater"):
            self.assertIn(needle, step)

    def test_the_readme_says_what_was_rehearsed_and_what_was_not(self):
        self.assertNotIn("Rehearsed on", self.raw)
        self.assertIn("carries `--override-dir`", self.text)
        self.assertIn("**Results of 2026-11-13, for the plain installer (before this folder packed it).**", self.raw)
        self.assertIn("None of those runs used the packer", self.text)
        self.assertIn("NOT seen for this recipe", self.text)
        self.assertIn("## What must be proven on a PC", self.raw)
        self.assertIn("The per-user install path ran with the first build only, for an administrator, started on demand", self.text)
        self.assertIn("### Races, as designed (NOT proven)", self.raw)
        self.assertIn("**Results of 2026-11-16, for the packed EXE, first build (", self.raw)
        self.assertIn("**Results of 2026-11-16, for the packed EXE, current form.**", self.raw)
        for needle in ("87224890 bytes", "exit code 0 after 69 seconds", "held only the three expected files, so check 48 passed",
                       "`install-user.ps1` (5114 bytes) and `remove.ps1` (2135 bytes), written from the embedded text",
                       "which already had Grammarly from the first build's test",
                       "So with this form the per-user INSTALL path (a person without Grammarly) has not run, and neither has the removal",
                       "only by lacking the two lines that skip the first-setup and Windows Sandbox accounts"):
            self.assertIn(needle, self.text)
        for needle in ("87169096 bytes", "87220102 bytes", "exit code 0 after 20 seconds",
                       "(so `Register-ScheduledTask` accepted the group's SID)", "started ON DEMAND (`schtasks /run`), not by a sign-in",
                       "a member of Administrators (NOT a standard user)", "What window flashed was not seen",
                       "ended with exit code 0 after 5 seconds", "the user's Grammarly and log stayed"):
            self.assertIn(needle, self.text)
        self.assertIn("**The extraction folder, and what remains.**", self.raw)
        for needle in ("`(CI)(S,WD,AD,X)`", "it is NOT a proof", "they may not list `C:\\Windows\\TEMP`"):
            self.assertIn(needle, self.text)
        self.assertIn("the install path of `install-user.ps1` has not run in the current form", self.text)
        self.assertIn("The first form of the removal of 2026-11-18 (`remove.ps1`, `uninstall-user.ps1`, `cleanup.ps1`) was run "
                      "once on one Windows 11 test PC on 2026-11-18; the current form of it ran on the same PC the same day", self.text)
        self.assertNotIn("and the removal have not run", self.text)
        self.assertIn("On a Mac, the five generated scripts were parsed", self.text)
        for history in ("ran on 2026", "Chocolatey item", "106 items"):
            self.assertNotIn(history, self.text)
        self.assertNotIn("was REFUSED on", self.text)

    def test_the_readme_lists_the_exit_codes_of_the_packer(self):
        import GrammarlyPerUserPackager as packager
        for code in packager.SETUP_CODES:
            self.assertRegex(self.raw, r"\n\| %d \| " % code)
        self.assertIn("| 49 | A pending removal", self.raw)
        self.assertIn("`remove.ps1` returns 0, 41, 46, 47, 50, 51, 52 or 53, `uninstall-user.ps1` 0 or 1, and `cleanup.ps1`\n0, 41, 46 or 54",
                      self.raw)
        self.assertEqual(set(packager.REMOVE_CODES), {41, 46, 47, 50, 51, 52, 53})
        self.assertEqual(set(packager.CLEANUP_CODES), {0, 41, 46, 54})
        self.assertIn("### The removal (2026-11-18)", self.raw)
        self.assertIn("**Seen on one Windows 11 test PC on 2026-11-18, with the build of the first form of this removal**", self.raw)
        self.assertIn("NOT run on a PC: this form (the lock, the re-read entry, the new order of the end)", self.text)
        self.assertNotIn("`remove.ps1` is unchanged since", self.raw)

    def test_the_readme_says_what_to_do_when_the_server_does_not_answer_the_changed_file_question(self):
        self.assertIn("whether this server answers that question is NOT established", self.text)
        self.assertIn("If the address answers \"not found\" or \"access denied\", the vendor moved the file", self.text)


def _text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class SourceFactsTests(unittest.TestCase):
    """What the README says of the facts read on 2026-11-13, and that the file was never downloaded."""

    def setUp(self):
        self.raw = read(README)
        self.text = re.sub(r"\s+", " ", self.raw)

    def test_nothing_that_was_not_tested_is_called_tested(self):
        for claim in ('was tested on a PC', 'the switch is established', 'proven on a test PC that works'):
            self.assertNotIn(claim, self.text)

    def test_the_readme_names_no_dated_run_of_this_folder(self):
        self.assertIsNone(re.search(r"Run on 20\d\d-", self.raw))
        self.assertNotIn("answered 200 with no redirect, 87044640 bytes", self.text)  # a HEAD answer is not a download

    def test_the_second_run_line_is_not_promised_for_a_fresh_override(self):
        self.assertIn("A new override gets a new cache folder, so its first run downloads the file again", self.text)

    def test_the_readme_keeps_the_dated_facts(self):
        self.assertIn("`/ignore-os-version` (needed on Windows Server 2016 and 2019)", self.text)
        self.assertIn("READ on 2026-11-16", self.text)
        self.assertIn("`1.2.305(.1980)`", self.text)
        self.assertIn("**It installed into the profile of the account that ran it**", self.text)
        self.assertIn("a process that it started was still running fifteen minutes later", self.text)


class CaveatTests(unittest.TestCase):
    """The per-user caveat must be in every recipe's Description, not only in the README."""

    NEEDLES = ("MAIN CAVEAT", "installs PER USER", "A Cimian client runs installers as SYSTEM",
               "where the installer run as SYSTEM installed into SYSTEM's own profile",
               "the downloaded installer is NOT published as it is",
               "registers a scheduled task that runs at the sign-in of any user, as that user",
               "every person who signs in on a PC with this item gets Grammarly (about 85 MB each): it suits PCs of one "
               "person, not shared ones",
               "updates itself", "the item's version is only the version of the staged installer",
               "the item's install check reads the entry that the EXE writes, not any person's Grammarly",
               "that was the first build", "but with it the per-user install path and the removal have not run",
               "NOT established: a real sign-in, a standard user, an upgrade, the item through the Cimian client",
               "the EXE starts the task once for whoever is signed in")

    def test_every_recipe_description_carries_the_caveat(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = re.sub(r"\s+", " ", load(path)["Description"])
            for needle in self.NEEDLES:
                with self.subTest(path=os.path.basename(path), needle=needle):
                    self.assertIn(needle, text)

    def test_the_caveat_comes_right_after_the_verification_sentences(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = re.sub(r"\s+", " ", load(path)["Description"])
            self.assertLess(text.index("verified by the"), text.index("MAIN CAVEAT"))
            self.assertLess(text.index("MAIN CAVEAT"), 1300, os.path.basename(path))

    def test_no_recipe_gives_silent_arguments_or_an_install_check(self):
        """The item must not be usable before a person has chosen them: the recipes carry none."""
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = read(path)
            for key in ("args", "installs", "check", "switches", "installer"):
                self.assertNotIn("<key>%s</key>" % key, text)

    def test_the_recipes_name_no_per_user_path_as_a_check(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = read(path)
            self.assertNotIn("AppData", text)
            self.assertNotIn("HKEY_CURRENT_USER", text)


class FlagNameTests(unittest.TestCase):
    """The cimian recipe's flag for an unverified download is `cimian_allow_unverified`; `pcman_allow_unverified` is the package tool's."""

    def test_each_child_description_names_its_own_flag(self):
        self.assertIn("cimian_allow_unverified", load(CIMIAN)["Description"])
        self.assertNotIn("pcman_allow_unverified", load(CIMIAN)["Description"])
        self.assertIn("pcman_allow_unverified", load(PCMAN)["Description"])
        self.assertNotIn("cimian_allow_unverified", load(PCMAN)["Description"])


class CimianVersionArgumentTextTests(unittest.TestCase):
    """The cimian recipe passes the label to `CimianImporter` as `version`; only the pcman recipe passes `pcman_version`."""

    def test_no_sentence_says_that_the_cimian_recipe_passes_pcman_version(self):
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md"), "r", encoding="utf-8") as handle:
            text = re.sub(r"\s+", " ", handle.read())
        for sentence in re.split(r"(?<=[.;])\s", text):
            if re.search(r"cimian recipe passes", sentence) and "pcman_version" in sentence:
                self.assertIn("pcman recipe", sentence)  # `pcman_version` is named only as the pcman recipe's argument
        self.assertEqual(text.count("the cimian recipe passes that `version` as `pcman_version`"), 0)


class CimianRecipeTests(unittest.TestCase):
    """The recipe for any Cimian repository: its only step is CimianImporter, and nothing of the
    package tool is in it. The package tool's recipe runs PcmanImporter."""

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
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.Grammarly")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.Grammarly")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotEqual(cimian["Identifier"], pcman["Identifier"])
        self.assertEqual(cimian["MinimumVersion"], pcman["MinimumVersion"])
        self.assertTrue(CIMIAN.endswith("Grammarly.cimian.recipe"))
        self.assertTrue(PCMAN.endswith("Grammarly.pcman.recipe"))

    def test_the_only_step_is_the_cimian_importer(self):
        steps = [step["Processor"] for step in load(CIMIAN)["Process"]]
        self.assertEqual(steps, [SHARED_PREFIX + "CimianImporter"])

    def test_the_inputs_and_the_arguments(self):
        recipe = load(CIMIAN)
        self.assertEqual(recipe["Input"]["NAME"], load(PCMAN)["Input"]["NAME"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], load(PCMAN)["Input"]["PCMAN_TEMPLATE"])
        self.assertEqual(recipe["Input"]["CIMIAN_NAME"], "grammarly")
        self.assertEqual(recipe["Input"]["CIMIAN_SUBDIRECTORY"], "")
        self.assertEqual(sorted(recipe["Input"]), ["CIMIAN_NAME", "CIMIAN_SUBDIRECTORY", "NAME", "pkginfo"])
        self.assertEqual(recipe["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": "%version%"})

    def test_the_pkginfo_gives_only_what_the_readme_states(self):
        self.assertEqual(load(CIMIAN)["Input"]["pkginfo"], {'display_name': 'Grammarly', 'developer': 'Grammarly'})

    def test_the_version_argument_is_the_exes_label_or_empty_for_an_msi(self):
        argument = load(CIMIAN)["Process"][0]["Arguments"]["version"]
        if "exe" == "exe":
            self.assertEqual(argument, "%version%")
        else:
            self.assertEqual(argument, "")  # the MSI's own ProductVersion, not a tag that an earlier step set

    def test_the_package_tool_recipe_runs_the_pcman_importer(self):
        recipe = load(PCMAN)
        steps = [step["Processor"] for step in recipe["Process"]]
        self.assertEqual(steps, [PCMAN_PREFIX + "PcmanImporter"])
        self.assertEqual(recipe["Input"]["PCMAN_TEMPLATE"], "grammarly")
        arguments = recipe["Process"][0]["Arguments"]
        self.assertEqual(arguments["pathname"], "%pathname%")
        self.assertEqual(arguments["pcman_template"], "%PCMAN_TEMPLATE%")
        self.assertEqual("pcman_version" in arguments, "exe" == "exe")

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

    def test_the_description_says_how_the_download_is_verified_first(self):
        description = load(CIMIAN)["Description"]
        self.assertTrue(description.startswith("This import is verified by the signature step of the download recipe"))
        self.assertIn("cimian_allow_unverified", description)
        self.assertIn("published, NOT verified", description)
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
        for name, identifier in (("Grammarly.cimian.recipe", "com.github.serrc-techops.cimian.Grammarly"),
                                 ("Grammarly.pcman.recipe", "com.github.serrc-techops.pcman.Grammarly")):
            rows = [line for line in self.raw.splitlines() if line.startswith("| `%s` | `%s` |" % (name, identifier))]
            self.assertEqual(len(rows), 1, name)
        self.assertIn("`CimianImporter`", [line for line in self.raw.splitlines() if line.startswith("| `Grammarly.cimian.recipe`")][0])
        self.assertIn("`pcman`", [line for line in self.raw.splitlines() if line.startswith("| `Grammarly.pcman.recipe`")][0])

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
        for text, recipe, other in ((self.generic, "Grammarly.cimian", "Grammarly.pcman"), (self.tool, "Grammarly.pcman", "Grammarly.cimian")):
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
            self.assertRegex(command, r"--override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly\.cimian\.recipe$")

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
        if "exe" == "exe":
            self.assertIn("What a person completes by hand for an `.exe`", self.generic)
            self.assertIn("an install check", self.generic)
            self.assertIn("StatusService.cs:194-219", self.generic)
            self.assertIn("the recipe's `pkginfo` gives no arguments, no install check and no uninstaller", self.generic)
            self.assertIn("The packed EXE takes **no arguments**", self.generic)
            self.assertIn("name: 'Grammarly per-user deployment'", self.generic)
            self.assertIn("is NOT a template for the packed EXE", self.generic)
            self.assertNotIn("args: [/S]", self.generic)
        else:
            self.assertIn("For an `.msi` nothing needs completing for a silent install", self.generic)
            self.assertIn("InstallerService.cs:936-948", self.generic)
            self.assertIn("`msiinfo`", self.generic)
            self.assertIn("This recipe cannot run without it", self.generic)
            self.assertIn("an argument of a step wins over an override's `Input`", self.generic)
            self.assertIn("`cimian_allow_product_change`", self.generic)
            self.assertIn("or that has none where the template's item had one", self.generic)

    def test_the_uninstaller_and_the_check_are_given_with_their_source_lines(self):
        text = re.sub(r"\s+", " ", self.generic)
        for needle in ("`windowsadmins/cimian` `main` at commit `6384299f` (2026-10-28)",
                       "That is the development branch, not a release",
                       "uninstaller: - type: exe", "args: ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',",
                       "`cli/managedsoftwareupdate/Services/StatusService.cs:1628-1700`",
                       "`cli/managedsoftwareupdate/Models/UpdateModels.cs:479`", "`Services/InstallerService.cs:723-735`",
                       "`InstallerService.cs:1574-1593`", "`InstallerService.cs:1701-1745`",
                       "So `version` is only a switch", "so give the `uninstaller` explicitly"):
            self.assertIn(needle, text)
        self.assertNotIn("/Users/", self.generic)

    def test_the_recipes_pkginfo_does_not_change_a_template_says_the_generic_way(self):
        for needle in ("The recipe's `pkginfo` does not change a template", "a NOTE names each",
                       "`cimian_pkginfo_wins` set to true in the override", "`cimian_architecture`"):
            self.assertIn(needle, self.generic)

    def test_the_parent_recipe_is_the_recipe_the_override_was_made_from(self):
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.cimian.Grammarly`**", self.generic.replace("\n", " "))
        self.assertIn("`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Grammarly`**", self.tool.replace("\n", " "))
        for text in (self.generic, self.tool):
            self.assertNotIn("it must be `com.github.serrc-techops.download.", text.replace("\n", " "))

    def test_the_condition_of_never_overwrites_is_said(self):
        self.assertIn("do not run two runs of one item at the same time", self.generic)

    def test_the_generic_way_states_no_hash_and_no_made_up_label(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.generic))
        self.assertNotIn("Published grammarly", self.generic)

    def test_the_generic_way_says_that_the_signature_verifies(self):
        self.assertIn("**The download of this program is verified by the installer's signature**", self.generic)
        self.assertIn("### 4. Switch a real run on\n", self.generic)
        self.assertIn("Add :Input:cimian_allow_unverified bool true", self.generic)
        self.assertIn("**Only when the signature step cannot be used**", self.generic)
        self.assertLess(self.generic.index("Add :Input:cimian_dry_run bool false"), self.generic.index("Add :Input:cimian_allow_unverified bool true"))

    def test_the_package_tools_way_says_the_tool_is_not_in_this_repository(self):
        self.assertIn("**not part of this repository**", self.tool)
        self.assertIn("`PcmanImporter` of `../Win-PcmanProcessors/`", self.tool)
        self.assertIn("Grammarly.pcman", self.tool)

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
        WindowsExeVersion leaves in `version` for an .exe."""
        recipe = load(CIMIAN)
        run = {"pathname": installer, "version": label if "exe" == "exe" else tag}
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
        return self.exe if "exe" == "exe" else self.msi

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
        self.assertEqual(new["installer"]["type"], "exe")
        self.assertEqual(new["installer"]["hash"], _win_support.sha256_hex(self.installer()))

    @_win_support.needs_yaml
    def test_the_version_is_the_label_of_an_exe_and_the_products_own_for_an_msi(self):
        if "exe" == "exe":
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
        head = "display_name: Template Name\nversion: 1.0.0\ncatalogs:\n- Production\ninstaller:\n  location: apps/Example-Chain-1.0.0.exe\n"
        if "exe" == "exe":
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
        if "exe" == "exe":
            self.assertEqual(new["installer"]["switches"], ["/TEMPLATE-SWITCH"])
            self.assertNotIn("args", new["installer"])

    @_win_support.needs_yaml
    def test_a_second_run_with_the_same_file_has_nothing_new(self):
        self.run_chain(self.installer(), cimian_allow_unverified=True)
        before = self.repo_tree()
        processor, messages = self.run_chain(self.installer(), cimian_allow_unverified=True)
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertEqual(self.repo_tree(), before)


class SignatureHandOverChainTests(_win_support.RepoTestCase):
    """The packer (its stub and 7z replaced) with what the signature step leaves in the run, then the real
    CimianImporter with what the packer leaves: the packed EXE counts as verified only through the hand-over."""

    def build(self, **signature):
        import GrammarlyPerUserPackager as packer
        installer = os.path.join(self.downloads, "GrammarlyInstaller.exe")
        with open(installer, "wb") as handle:
            handle.write(b"MZ" + b"g" * 100)

        class Fake(packer.GrammarlyPerUserPackager):
            def stub(self, work):
                path = os.path.join(work, "stub.sfx")
                with open(path, "wb") as handle:
                    handle.write(b"MZstub")
                return path

            def sevenzip(self):
                return "/usr/bin/true"
        real_run = packer.subprocess.run

        def run(command, **kwargs):
            if command[0] == "/usr/bin/true" and command[1] == "a":
                with open(command[command.index("-y") + 1], "wb") as handle:
                    handle.write(b"ARCHIVE")
            return real_run(["/usr/bin/true"], capture_output=True, text=True)
        packer.subprocess.run = run
        self.addCleanup(lambda: setattr(packer.subprocess, "run", real_run))
        env = {"RECIPE_CACHE_DIR": os.path.join(self.downloads, "cache"), "pathname": installer, "version": "1.2.3",
               "sfx_sdk_url": "https://example.invalid/sdk.7z", "sfx_sdk_sha256": "0" * 64,
               "grammarly_installer_arguments": ""}
        env.update({key: (_win_support.sha256_hex(installer) if value == "installer" else value)
                    for key, value in signature.items()})
        processor = Fake(env)
        processor.output = lambda *args, **kwargs: None
        processor.main()
        return processor.env

    def import_packed(self, env, **extra):
        run = {key: env[key] for key in ("pathname", "version", "signature_verified", "signature_sha256") if key in env}
        run.update({"cimian_repo": self.repo, "cimian_name": "Example-Chain", "cimian_dry_run": False,
                    "cimian_path": self.msi_bin})
        run.update(extra)
        return _win_support.run_processor(_win_support.cimian.CimianImporter, run)

    @_win_support.needs_yaml
    def test_the_packed_exe_of_a_verified_installer_is_published_as_verified(self):
        env = self.build(signature_verified=True, signature_sha256="installer")
        processor, messages = self.import_packed(env)
        self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published")
        self.assertFalse([m for m in messages if "NOT verified" in m or "WITHOUT a verified" in m])

    @_win_support.needs_yaml
    def test_without_the_signature_step_the_packed_exe_is_refused(self):
        env = self.build()
        with self.assertRaises(_win_support.ProcessorError) as caught:
            self.import_packed(env)
        self.assertIn("The download was not verified", str(caught.exception))

    @_win_support.needs_yaml
    def test_the_installers_hash_is_not_taken_for_the_packed_exe(self):
        env = self.build()
        env.update(signature_verified=True, signature_sha256=_win_support.sha256_hex(
            os.path.join(self.downloads, "GrammarlyInstaller.exe")))
        with self.assertRaises(_win_support.ProcessorError) as caught:
            self.import_packed(env, cimian_allow_unverified=True)
        self.assertIn("is not the file whose signature was verified", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
