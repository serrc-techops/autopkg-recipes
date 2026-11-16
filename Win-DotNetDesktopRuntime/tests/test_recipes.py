"""Tests of the three .NET Desktop Runtime recipes and the README. Nothing here runs AutoPkg or uses the
network. The folder's own processors are tested in test_info_provider.py; the shared folders' tests are
run separately."""
import hashlib
import os
import plistlib
import re
import subprocess
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.dirname(TESTS_DIR)
SHARED_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-SharedProcessors")
PCMAN_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-PcmanProcessors")
HANDBRAKE_README = os.path.join(os.path.dirname(RECIPE_DIR), "Win-HandBrake", "README.md")
for folder in (os.path.join(SHARED_DIR, "tests"), os.path.join(PCMAN_DIR, "tests"), RECIPE_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import _win_support  # noqa: E402  (installs the autopkglib stand-in, imports the processors)
import _pcman_support  # noqa: E402
import test_public_repository as shared_hygiene  # noqa: E402
import DotNetDesktopRuntimeInfoProvider as provider  # noqa: E402
import Sha512ChecksumVerifier as verifier  # noqa: E402

PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = PREFIX + ".PcmanProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "DotNetDesktopRuntime-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "DotNetDesktopRuntime.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "DotNetDesktopRuntime.pcman.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
CORE_PROCESSORS = ("URLDownloader", "EndOfCheckPhase")
OWN_PROCESSORS = {"DotNetDesktopRuntimeInfoProvider": provider.DotNetDesktopRuntimeInfoProvider,
                  "Sha512ChecksumVerifier": verifier.Sha512ChecksumVerifier}
LABEL = "10.0.15"


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def flat(path):
    return re.sub(r"\s+", " ", read(path))


class RecipeTests(unittest.TestCase):
    def test_property_lists_with_the_keys_autopkg_reads(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            with self.subTest(path=os.path.basename(path)):
                if os.path.exists("/usr/bin/plutil"):
                    result = subprocess.run(["plutil", "-lint", path], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                recipe = load(path)
                for key in ("Description", "Identifier", "Input", "MinimumVersion", "Process"):
                    self.assertIn(key, recipe)

    def test_identifiers_and_parents(self):
        download, cimian, pcman = load(DOWNLOAD), load(CIMIAN), load(PCMAN)
        self.assertEqual(download["Identifier"], PREFIX + ".download.DotNetDesktopRuntime-Win")
        self.assertEqual(cimian["Identifier"], PREFIX + ".cimian.DotNetDesktopRuntime")
        self.assertEqual(pcman["Identifier"], PREFIX + ".pcman.DotNetDesktopRuntime")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)

    def test_the_download_steps_in_order_and_the_check_is_last(self):
        steps = [step["Processor"] for step in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, ["DotNetDesktopRuntimeInfoProvider", "URLDownloader", "EndOfCheckPhase",
                                 "Sha512ChecksumVerifier"])
        self.assertNotIn("ChecksumVerifier", [s.split("/")[-1] for s in steps if s.startswith(SHARED_PREFIX)])

    def test_the_importer_steps(self):
        self.assertEqual([s["Processor"] for s in load(CIMIAN)["Process"]], [SHARED_PREFIX + "CimianImporter"])
        self.assertEqual([s["Processor"] for s in load(PCMAN)["Process"]], [PCMAN_PREFIX + "PcmanImporter"])
        self.assertEqual(load(CIMIAN)["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": "%version%"})
        self.assertEqual(load(PCMAN)["Process"][0]["Arguments"], {
            "pathname": "%pathname%", "pcman_template": "%PCMAN_TEMPLATE%", "pcman_version": "%version%"})

    def test_inputs_and_names(self):
        download, cimian, pcman = load(DOWNLOAD), load(CIMIAN), load(PCMAN)
        self.assertEqual(download["Input"], {"NAME": "DotNetDesktopRuntime", "dotnet_allow_eol": False,
                                             "dotnet_channel": "10.0", "dotnet_rid": "win-x64"})
        self.assertIsInstance(download["Input"]["dotnet_allow_eol"], bool)
        self.assertEqual(cimian["Input"]["CIMIAN_NAME"], "dotnet-desktop-runtime")
        self.assertEqual(pcman["Input"]["PCMAN_TEMPLATE"], "dotnet-desktop-runtime")
        self.assertEqual(cimian["Input"]["CIMIAN_SUBDIRECTORY"], "")
        self.assertEqual(sorted(cimian["Input"]), ["CIMIAN_NAME", "CIMIAN_SUBDIRECTORY", "NAME", "pkginfo"])
        self.assertEqual(cimian["Input"]["pkginfo"], {"developer": "Microsoft", "display_name": ".NET Desktop Runtime"})

    def test_the_download_inputs_are_inputs_that_the_provider_declares_with_the_same_defaults(self):
        declared = provider.DotNetDesktopRuntimeInfoProvider.input_variables
        for key, value in load(DOWNLOAD)["Input"].items():
            if key == "NAME":
                continue
            self.assertIn(key, declared)
            self.assertEqual(declared[key]["default"], value)

    def test_every_variable_a_recipe_uses_is_an_input_or_set_by_an_earlier_step(self):
        earlier = {"pathname", "url", "version", "expected_sha512", "filename"}
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            recipe = load(path)
            known = set(recipe["Input"]) | earlier | set(load(DOWNLOAD)["Input"])
            for step in recipe["Process"]:
                for value in step.get("Arguments", {}).values():
                    for name in re.findall(r"%([A-Za-z_]+)%", str(value)):
                        with self.subTest(recipe=os.path.basename(path), variable=name):
                            self.assertIn(name, known)

    def test_the_verifier_gets_the_providers_hash_and_every_argument_is_declared(self):
        step = load(DOWNLOAD)["Process"][3]
        self.assertEqual(step["Arguments"], {"pathname": "%pathname%", "expected_sha512": "%expected_sha512%"})
        for name, args in ((("Sha512ChecksumVerifier"), step["Arguments"]),):
            for key in args:
                self.assertIn(key, OWN_PROCESSORS[name].input_variables)
        for key in ("url", "version", "expected_sha512"):
            self.assertIn(key, provider.DotNetDesktopRuntimeInfoProvider.output_variables)

    def test_every_argument_of_an_importer_is_declared_and_every_required_one_is_given(self):
        classes = {CIMIAN: _win_support.cimian.CimianImporter, PCMAN: _pcman_support.importer.PcmanImporter}
        for path, cls in classes.items():
            arguments = load(path)["Process"][0]["Arguments"]
            for key in arguments:
                self.assertIn(key, cls.input_variables)
            for key, flags in cls.input_variables.items():
                if flags.get("required") and "default" not in flags and key != "pcman_root":
                    self.assertIn(key, arguments, key)

    def test_every_named_processor_exists(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            for step in load(path)["Process"]:
                name = step["Processor"]
                if name.startswith(SHARED_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, name[len(SHARED_PREFIX):] + ".py")))
                elif name.startswith(PCMAN_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(PCMAN_DIR, name[len(PCMAN_PREFIX):] + ".py")))
                elif name not in CORE_PROCESSORS:
                    self.assertTrue(os.path.isfile(os.path.join(RECIPE_DIR, name + ".py")), name)
                    self.assertIn("class %s(Processor):" % name, read(os.path.join(RECIPE_DIR, name + ".py")))

    def test_the_shared_verifier_is_untouched_by_the_recipe(self):
        """The shared ChecksumVerifier takes a SHA-256 only and is not changed: it is not a step here."""
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            self.assertNotIn("SharedProcessors/ChecksumVerifier", read(path))
        self.assertNotIn("sha512", read(os.path.join(SHARED_DIR, "ChecksumVerifier.py")).lower())

    def test_no_stop_no_latest_only_no_blocking_applications_no_hash_no_machine_value(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = read(path)
            for word in ("StopProcessingIf", "latest_only", "blocking_applications", "pcman_root", "pcman_dry_run",
                         "cimian_repo", "cimian_dry_run", "cimian_allow_unverified", "pcman_allow_unverified",
                         "checksum_verified", "checksum_sha256"):
                self.assertNotIn("<key>%s</key>" % word, text)
                self.assertNotIn(word + "<", text)
            self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", text))

    def test_no_value_is_a_path_or_a_catalog(self):
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            recipe = load(path)
            values = list(recipe["Input"].values())
            for step in recipe["Process"]:
                values.extend(step.get("Arguments", {}).values())
            for value in values:
                if isinstance(value, str):
                    self.assertFalse(value.startswith(("/", "~")), value)
                    self.assertNotIn("\\", value)
                    self.assertNotIn("Production", value)

    def test_descriptions_say_what_ran_and_what_did_not(self):
        text = flat(DOWNLOAD)
        for needle in ("SHA-512 that Microsoft's own release metadata gives", "without following a redirect",
                       "refuses a preview or release candidate", "dotnet_allow_eol", "the metadata's detached signature is NOT checked",
                       "shared ChecksumVerifier takes a SHA-256 only and is not changed", "Sha512ChecksumVerifier",
                       "were read on 2026-11-16", "ran once under AutoPkg 2.9.0 as the parent of the Cimian recipe",
                       "the installer's own signature was not checked"):
            self.assertIn(needle, text)
        description = flat(CIMIAN)
        for needle in ("EXE", "version label", "On 2026-11-16 the silent arguments /install /quiet /norestart ended with exit code 0 on one Windows 11 test PC",
                       "the right install check, the uninstall command, an install through the Cimian client",
                       "are NOT established", "a dry run, a real run that published 10.0.15, and a second run that said nothing is new",
                       "dry run", "the importer warns that it has no install check"):
            self.assertIn(needle, description)
        self.assertNotIn("NOT run with AutoPkg", description)
        description = flat(PCMAN)
        for needle in ("EXE", "version label", "exit code 0 on one Windows 11 test PC", "are NOT established",
                       "This recipe (the package tool's way) was NOT run with AutoPkg; its sibling, the Cimian recipe, was.",
                       "dry run"):
            self.assertIn(needle, description)
        self.assertIn("cimian_dry_run", flat(CIMIAN))
        self.assertIn("pcman_dry_run", flat(PCMAN))
        self.assertNotIn("pcman", read(CIMIAN).lower())
        for path in (DOWNLOAD, CIMIAN, PCMAN):
            text = flat(path)
            self.assertNotRegex(text, r"(?i)\brehearsed\b")
            self.assertNotRegex(text, r"(?i)\bran on 20")
            self.assertNotRegex(text, r"(?i)works on a PC")
            self.assertNotRegex(text, r"(?i)HandBrake works")

    def test_the_label_is_the_release_version_and_the_client_does_not_read_it_as_a_build_date(self):
        # The shared README: a first part from 20 to 99 (three parts) or four digits is a build time.
        self.assertLess(int(LABEL.split(".")[0]), 20)
        self.assertRegex(LABEL, r"^[0-9]+\.[0-9]+\.[0-9]+$")


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

    def test_the_folder_holds_only_what_is_expected(self):
        names = sorted(os.path.relpath(path, RECIPE_DIR) for path in self.files())
        self.assertEqual(names, sorted([
            "DotNetDesktopRuntime-Win.download.recipe", "DotNetDesktopRuntime.cimian.recipe",
            "DotNetDesktopRuntime.pcman.recipe", "DotNetDesktopRuntimeInfoProvider.py",
            "Sha512ChecksumVerifier.py", "README.md",
            os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
            os.path.join("tests", "test_info_provider.py"), os.path.join("tests", "releases_excerpt.json"),
        ]))

    def test_the_excerpt_is_small_and_its_hashes_are_invented(self):
        path = os.path.join(TESTS_DIR, "releases_excerpt.json")
        self.assertLess(os.path.getsize(path), 8000)
        # an invented digit string repeats one 8-character block sixteen times
        for digest in re.findall(r'"hash": "([0-9a-f]{128})"', read(path)):
            self.assertEqual(digest, digest[:8] * 16)

    def test_processors_use_the_standard_library_only(self):
        allowed = {"hashlib", "http", "json", "os", "re", "urllib", "autopkglib"}
        for name in ("DotNetDesktopRuntimeInfoProvider.py", "Sha512ChecksumVerifier.py"):
            for match in re.finditer(r"^(?:import|from) ([A-Za-z_]+)", read(os.path.join(RECIPE_DIR, name)), re.M):
                self.assertIn(match.group(1), allowed, name)


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.raw = read(README)
        self.text = re.sub(r"\s+", " ", self.raw)

    def commands(self, name):
        pattern = re.compile(r"^ {4,}(autopkg %s\b.*)$" % name, re.M)
        return [m.group(1) for m in pattern.finditer(self.raw)]

    def test_every_make_override_names_an_override_folder_and_a_recipe_name(self):
        commands = re.findall(r"autopkg make-override([^`\n]*)", self.raw)
        self.assertEqual(len(commands), 2)
        for command in commands:
            self.assertIn("--override-dir=", command)
            self.assertRegex(command, r"DotNetDesktopRuntime\.(cimian|pcman)$")

    def test_every_run_and_trust_command_carries_the_override_dir_and_the_path(self):
        for name in ("run", "verify-trust-info", "update-trust-info"):
            for command in self.commands(name):
                with self.subTest(command=command):
                    self.assertRegex(command, r"--override-dir=<the Windows overrides folder> "
                                              r"<the Windows overrides folder>/DotNetDesktopRuntime\.(cimian|pcman)\.recipe$")
                    self.assertNotIn("com.github.", command)
        pattern = r"^[ \t]*autopkg (?:run|verify-trust-info|update-trust-info)\b"
        self.assertEqual(len(re.findall(pattern, self.raw, re.M)),
                         sum(len(self.commands(n)) for n in ("run", "verify-trust-info", "update-trust-info")))
        self.assertEqual(len(self.commands("run")), 6)

    def test_prose_never_shows_a_run_without_the_option(self):
        for match in re.finditer(r"`(autopkg (?:run|verify-trust-info|update-trust-info)[^`]*<[^`]*)`", self.raw):
            self.assertIn("--override-dir=", match.group(1))

    def test_the_status_line_comes_first_and_says_what_ran_what_was_read_and_what_was_not(self):
        opening = "**Status. New. On 2026-11-16 the Cimian way ran under AutoPkg 2.9.0 once, and the installer was tried once on one PC; the package tool's way (pcman) was NOT run."
        self.assertIn(opening, self.raw)
        start = self.raw.index(opening)
        self.assertLess(self.raw.index("# Win-DotNetDesktopRuntime"), start)
        self.assertLess(start, self.raw.index("| Recipe |"))
        paragraph = re.sub(r"\s+", " ", self.raw[start:self.raw.index("**\n", start) + 2])
        self.assertTrue(paragraph.endswith("**"))
        read_part, _, rest = paragraph.partition("**What ran, on 2026-11-16:**")
        ran_part, _, not_part = rest.partition("NOT established:")
        self.assertTrue(ran_part and not_part)
        self.assertIn("READ on 2026-11-16", read_part)
        for needle in ("answered 200 with JSON of about 1.2 MB", "`latest-release` (`10.0.15`)", "`support-phase` (`active`)",
                       "`eol-date` (`2028-11-14`)", "`releases.json.<stamp>.p7s`", "a list of 25 releases, the newest first",
                       "128 hex digits (a SHA-512), and the metadata has no SHA-256",
                       "`1.11.2`'s own release notes", "name .NET Desktop Runtime 10.0",
                       "https://aka.ms/dotnet/10.0/windowsdesktop-runtime-win-x64.exe"):
            self.assertIn(needle, read_part)
        for needle in ("under AutoPkg 2.9.0, into a scratch Cimian repository that had no item of this name",
                       "`make-override` with `--override-dir`, `verify-trust-info` OK, a dry run",
                       "published `dotnet-desktop-runtime` `10.0.15`", "60066584 bytes", "its SHA-512 from the metadata verified",
                       "a second real run that said nothing is new", "the importer warned that the pkginfo has no install check",
                       "ended with exit code 0 after 33 seconds, with no window and no child process left",
                       "`Microsoft Windows Desktop Runtime 10.0.15 (x64)` in the 32-bit view of the registry (WOW6432Node)",
                       "DisplayVersion `10.0.15(.50000)`", "windowsdesktop-runtime-10.0.15-win-x64.exe\" /uninstall /quiet", "`Microsoft .NET Host FX Resolver - 10.0.15 (x64)`",
                       "each with DisplayVersion `80.60.61788`", "Microsoft.WindowsDesktop.App", "Microsoft.NETCore.App",
                       "was still running after 40 seconds and no dialog window was seen",
                       "that is weak evidence only", "it does not show that HandBrake works"):
            self.assertIn(needle, ran_part)
        for needle in ("an upgrade from an older `10.0.x` (whether the old one leaves)", "the uninstall (its string was read, not run)",
                       "an install through the Cimian client", "the right install check", "Windows 10, x86 and ARM",
                       "the installer's signature (not looked at in the test)", "the metadata's detached signature (not checked)",
                       "any run of the package tool's way", "STOP: nothing was written", "never accept new trust information first"):
            self.assertIn(needle, not_part)
        self.assertIn("The hash lines in the tests are made up", paragraph)
        self.assertNotRegex(self.text, r"(?i)\bwas rehearsed\b")
        self.assertNotRegex(self.text, r"\bRan on 20")
        self.assertNotIn("Run on 20", self.text)
        self.assertNotRegex(self.text, r"(?i)(?<!show that )HandBrake works")

    def test_it_says_why_a_second_verifier_exists_and_what_it_sets(self):
        for needle in ("**Why a second verifier exists:**", "takes a SHA-256 only",
                       "Microsoft's metadata gives a SHA-512 only", "The shared processor is not changed",
                       "`checksum_verified` (the boolean true)", "`checksum_sha256`",
                       "refuses it when that is not `checksum_sha256`"):
            self.assertIn(needle, self.text)

    def test_it_says_what_protects_and_what_does_not(self):
        i = self.raw.index("## What protects, and what does not")
        self.assertLess(i, self.raw.index("## Run every override with `--override-dir`"))
        section = re.sub(r"\s+", " ", self.raw[i:self.raw.index("## Run every override")])
        for needle in ("It is the vendor's word, but it is in another file than the installer",
                       "`releases.json.<stamp>.p7s`", "**It is NOT checked.**", "Authenticode", "was not read; it is not checked",
                       "nobody should check the MSI entries against `10.0.15`"):
            self.assertIn(needle, section)

    def test_the_override_dir_rule_is_a_bold_paragraph_before_the_ways(self):
        i = self.raw.index("## Run every override with `--override-dir`")
        paragraph = re.sub(r"\s+", " ", self.raw[i:i + 2500])
        for needle in ("**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`",
                       "skips the trust check with one warning line", "a changed processor is not caught",
                       "If that line ever appears in a run of an override, stop: the run was not checked.**",
                       "`FAIL_RECIPES_WITHOUT_TRUST_INFO`", "owner's decision"):
            self.assertIn(needle, paragraph)
        self.assertLess(i, self.raw.index("## With any Cimian repository"))

    def test_it_says_what_a_person_completes_by_hand_and_the_handbrake_requirement(self):
        i = self.raw.index("## What a person completes by hand in the pkginfo")
        section = re.sub(r"\s+", " ", self.raw[i:self.raw.index("## With any Cimian repository")])
        for needle in ("`/install /quiet /norestart` is what Microsoft documents", "exit code 0 after 33 seconds",
                       "not on Windows 10, x86 or ARM", "an install check", "**NOT established which check is right.**",
                       "Microsoft.WindowsDesktop.App", "`80.60.61788`: do not compare them with the item's version",
                       "It was read, **not run**", "what a newer `10.0.x` does to the older one: NOT established",
                       "**HandBrake's item gets a `requires` on this item**", "`requires: [dotnet-desktop-runtime]`"):
            self.assertIn(needle, section)

    def test_the_sections_come_in_this_order(self):
        marks = ("## The processors of this folder", "## What protects, and what does not",
                 "## Run every override with `--override-dir`", "## What a person completes by hand in the pkginfo",
                 "## With any Cimian repository", "## With the package tool (pcman)", "## a. ", "## g. ",
                 "## Other facts", "## Tests")
        positions = [self.raw.index(mark) for mark in marks]
        self.assertEqual(positions, sorted(positions))

    def test_the_provider_and_the_label_are_described(self):
        for needle in ("`dotnet_channel` (default `10.0`", "`dotnet_rid` (default `win-x64`", "`dotnet_allow_eol` (default false)",
                       "the first release of the list is not assumed to be it", "a preview or release candidate",
                       "`eol` is refused unless the override sets `dotnet_allow_eol` to true",
                       "follows no redirect (a redirect is an error)", "the label is", "three numbers",
                       "does not read the label as a build date", "`WindowsExeVersion` was not chosen"):
            self.assertIn(needle.replace("the label is", "An EXE has no version"), self.text)

    def test_the_names_check_the_parent_and_the_catalog_steps_are_there(self):
        for needle in ("autopkg list-recipes | grep -i DotNetDesktopRuntime-Win", "autopkg list-recipes | grep -i DotNetDesktopRuntime.cimian",
                       "`com.github.serrc-techops.cimian.DotNetDesktopRuntime`",
                       "`com.github.serrc-techops.pcman.DotNetDesktopRuntime`", "`makecatalogs`", "pcman catalogs",
                       "pcman versions dotnet-desktop-runtime", "Add :Input:cimian_dry_run bool false",
                       "Add :Input:pcman_dry_run bool false", "Failed local trust verification", "repo-add", "-string",
                       "DRY RUN", "Nothing new"):
            self.assertIn(needle, self.text)

    def test_it_names_no_site_no_hash_no_four_number_version(self):
        self.assertIsNone(re.search(r"(?i)\b[0-9a-f]{64}\b", self.raw))
        self.assertIsNone(re.search(r"\b[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\b", self.raw))

    def test_the_handbrake_readme_points_here_and_no_longer_says_eight_point_zero_from_guides(self):
        hb = re.sub(r"\s+", " ", read(HANDBRAKE_README))
        self.assertIn("Win-DotNetDesktopRuntime", hb)
        self.assertNotIn("install \".NET Desktop Runtime 8.0 (x64)\" together with HandBrake", hb)
        self.assertIn("HandBrake 1.11.2's own release notes name", hb)


class ChainTests(_pcman_support.ToolTestCase):
    """The chain with the real Sha512ChecksumVerifier and the real importer (the package tool is a stand-in)."""

    def verified(self, installer):
        digest = hashlib.sha512()
        with open(installer, "rb") as handle:
            digest.update(handle.read())
        verifier_run, _ = _win_support.run_processor(
            verifier.Sha512ChecksumVerifier, {"pathname": installer, "expected_sha512": digest.hexdigest()})
        return {k: v for k, v in verifier_run.env.items() if k.startswith("checksum_")}

    def test_the_chain_counts_as_verified_and_nothing_is_warned(self):
        env = {"pathname": self.exe, "pcman_template": "dotnet-desktop-runtime", "pcman_version": LABEL,
               "pcman_root": self.root, "pcman_dry_run": False, "pcman_path": self.msi_bin}
        env.update(self.verified(self.exe))
        self.assertEqual(env["checksum_sha256"], _win_support.sha256_hex(self.exe))
        processor, _ = _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        warnings = [m for level, m in processor.message_levels if m.startswith("WARNING:")]
        self.assertEqual(warnings, [])
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published")
        self.assertIn(LABEL, self.record()["argv"])

    def test_the_chain_is_refused_for_another_file(self):
        env = {"pathname": self.exe, "pcman_template": "dotnet-desktop-runtime", "pcman_version": LABEL,
               "pcman_root": self.root, "pcman_dry_run": False, "pcman_path": self.msi_bin}
        env.update(self.verified(self.exe))
        other = os.path.join(self.downloads, "other.exe")
        with open(other, "wb") as handle:
            handle.write(b"not the file that was verified")
        env["pathname"] = other
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)
        self.assertIn("not the file whose checksum was verified", str(caught.exception))
        self.assertFalse(self.was_run())


class CimianChainTests(_win_support.RepoTestCase):
    def run_chain(self, installer, **extra):
        recipe = load(CIMIAN)
        env = {"pathname": installer, "cimian_repo": self.repo, "cimian_dry_run": False, "cimian_path": self.msi_bin}
        env.update(ChainTests.verified(self, installer))
        env.update(recipe["Input"])
        values = dict(recipe["Input"])
        values.update({"CIMIAN_NAME": "Example-Chain", "version": LABEL, "pathname": installer})
        for name, value in recipe["Process"][0]["Arguments"].items():
            for variable in re.findall(r"%([A-Za-z_]+)%", value):
                value = value.replace("%" + variable + "%", str(values[variable]))
            env[name] = value
        env.update(extra)
        return _win_support.run_processor(_win_support.cimian.CimianImporter, env)

    @_win_support.needs_yaml
    def test_the_chain_publishes_as_verified_with_the_release_version_as_the_label(self):
        processor, messages = self.run_chain(self.exe)
        self.assertEqual([m for m in messages if m.startswith("WARNING: published WITHOUT")], [])
        self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published")
        self.assertEqual(processor.env["cimian_version_imported"], LABEL)
        new = self.read_pkginfo("Example-Chain-%s.yaml" % LABEL)
        self.assertEqual(new["installer"]["type"], "exe")
        self.assertEqual(new["installer"]["hash"], _win_support.sha256_hex(self.exe))
        for key, value in load(CIMIAN)["Input"]["pkginfo"].items():
            self.assertEqual(new[key], value)

    @_win_support.needs_yaml
    def test_a_second_run_has_nothing_new(self):
        self.run_chain(self.exe)
        before = self.repo_tree()
        processor, _ = self.run_chain(self.exe)
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertEqual(self.repo_tree(), before)

    @_win_support.needs_yaml
    def test_the_chain_is_refused_for_another_file(self):
        env = {"pathname": self.exe, "cimian_name": "Example-Chain", "version": LABEL, "cimian_repo": self.repo,
               "cimian_dry_run": False, "cimian_path": self.msi_bin}
        env.update(ChainTests.verified(self, self.exe))
        other = self.make_installer("other-" + os.path.basename(self.exe), b"not the file that was verified")
        env["pathname"] = other
        before = self.repo_tree()
        with self.assertRaises(_win_support.ProcessorError) as caught:
            _win_support.run_processor(_win_support.cimian.CimianImporter, env)
        self.assertIn("not the file whose checksum was verified", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)


if __name__ == "__main__":
    unittest.main()
