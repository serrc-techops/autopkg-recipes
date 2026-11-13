"""Tests of Microsoft365AppsPackager and the three recipes. Nothing here uses
the network, 7z or AutoPkg: the parts that decide what is downloaded and what
the PC runs are plain functions, and a build is run with those two replaced.
"""
import os
import plistlib
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ElementTree

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.dirname(TESTS_DIR)
SHARED_TESTS_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-SharedProcessors", "tests")
PCMAN_TESTS_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-PcmanProcessors", "tests")
for folder in (SHARED_TESTS_DIR, PCMAN_TESTS_DIR, RECIPE_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import _win_support  # noqa: E402,F401  (installs the autopkglib stand-in)
import _pcman_support  # noqa: E402,F401
import Microsoft365AppsPackager as packager  # noqa: E402

ProcessorError = sys.modules["autopkglib"].ProcessorError
VERSION = "16.0.20527.20194"
PREFIX = "com.github.serrc-techops"
DESCRIPTOR = (
    '﻿<?xml version="1.0" encoding="utf-8"?><Version>'
    '<Available Build="16.0.12527.22286" I320Version="16.0.20527.20190" I640Version="%s" />'
    "</Version>" % VERSION
)


def load(name):
    with open(os.path.join(RECIPE_DIR, name), "rb") as handle:
        return plistlib.load(handle)


class DescriptorTests(unittest.TestCase):
    def test_the_64_bit_version_is_taken(self):
        self.assertEqual(packager.parse_version_descriptor(DESCRIPTOR.lstrip("﻿")), VERSION)

    def test_what_is_not_a_descriptor_is_refused(self):
        for text in ("<html/>", "not xml", '<Version><Available I640Version="17.0.12345.67890"/></Version>',
                     '<Version><Available I640Version="16.0.1.2; rm"/></Version>'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    packager.parse_version_descriptor(text)


class SourceFileTests(unittest.TestCase):
    def test_the_list_of_one_version(self):
        files = packager.source_files(VERSION, "en-us")
        self.assertEqual(files[0], "Office/Data/v64_%s.cab" % VERSION)
        self.assertEqual(len(files), 12)
        self.assertEqual(len(packager.source_files(VERSION, "en-us", include_arm64x=True)), 14)
        self.assertFalse([path for path in files if "arm64x" in path])
        self.assertEqual(len(files), len(set(files)))
        for name in ("stream.x64.x-none.dat", "stream.x64.en-us.dat", "i641033.cab", "s641033.cab", "a640_exp.cab", "sa640.cab"):
            self.assertIn("Office/Data/%s/%s" % (VERSION, name), files)
        for path in files:
            self.assertNotIn("..", path)
            self.assertFalse(path.startswith("/"))

    def test_another_language_changes_the_names(self):
        files = packager.source_files(VERSION, "es-es")
        self.assertIn("Office/Data/%s/stream.x64.es-es.dat" % VERSION, files)
        self.assertIn("Office/Data/%s/i643082.cab" % VERSION, files)

    def test_a_bad_version_or_language_is_refused(self):
        for version, language in (("16.0.1.2/../x", "en-us"), ("", "en-us"), (VERSION, "xx-xx"), (VERSION, "../en-us")):
            with self.subTest(version=version, language=language):
                with self.assertRaises(ValueError):
                    packager.source_files(version, language)


class ConfigurationTests(unittest.TestCase):
    def build(self, **changes):
        arguments = dict(version=VERSION, channel="MonthlyEnterprise", language="en-us", product_id="O365BusinessRetail",
                         exclude_apps=["Access", "Outlook"], updates_enabled=False, migrate_architecture=True,
                         remove_msi=True, force_app_shutdown=False)
        arguments.update(changes)
        return ElementTree.fromstring(packager.configuration_xml(**arguments))

    def test_the_install_is_from_the_local_folder_only(self):
        add = self.build().find("Add")
        self.assertEqual(add.get("SourcePath"), packager.SOURCE_PLACEHOLDER)
        self.assertEqual(add.get("AllowCdnFallback"), "FALSE")
        self.assertEqual(add.get("Version"), VERSION)
        self.assertEqual(add.get("OfficeClientEdition"), "64")
        self.assertEqual(add.get("Channel"), "MonthlyEnterprise")

    def test_product_language_and_left_out_apps(self):
        product = self.build().find("Add/Product")
        self.assertEqual(product.get("ID"), "O365BusinessRetail")
        self.assertEqual(product.find("Language").get("ID"), "en-us")
        self.assertEqual([app.get("ID") for app in product.findall("ExcludeApp")], ["Access", "Outlook"])

    def test_silent_and_the_switches(self):
        root = self.build()
        self.assertEqual(root.find("Display").attrib, {"Level": "None", "AcceptEULA": "TRUE"})
        self.assertEqual(root.find("Updates").get("Enabled"), "FALSE")
        self.assertIsNotNone(root.find("RemoveMSI"))
        self.assertEqual(root.find("Add").get("MigrateArch"), "TRUE")
        self.assertEqual(root.find("Property").attrib, {"Name": "FORCEAPPSHUTDOWN", "Value": "FALSE"})
        other = self.build(remove_msi=False, migrate_architecture=False, updates_enabled=True, force_app_shutdown=True)
        self.assertIsNone(other.find("RemoveMSI"))
        self.assertEqual(other.find("Add").get("MigrateArch"), "FALSE")
        self.assertEqual(other.find("Updates").get("Enabled"), "TRUE")
        self.assertEqual(other.find("Property").get("Value"), "TRUE")

    def test_values_that_could_change_the_xml_are_refused(self):
        for changes in ({"product_id": 'X"><Evil/>'}, {"exclude_apps": ["Access", "a b"]}, {"channel": "Nightly"},
                        {"version": "1.2.3.4"}, {"language": "en"}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self.build(**changes)


class SetupBatTests(unittest.TestCase):
    def test_parts_are_named_in_order_and_cover_the_file(self):
        size = packager.PART_BYTES * 2 + 1
        self.assertEqual(packager.part_names("a/b.dat", size), ["a/b.dat.part001", "a/b.dat.part002", "a/b.dat.part003"])
        self.assertEqual(packager.part_names("a/b.dat", packager.PART_BYTES), [])

    def test_the_script_joins_checks_and_passes_the_exit_code_on(self):
        parts = ["Office/Data/x.dat.part001", "Office/Data/x.dat.part002", "Office/Data/x.dat.part003"]
        text = packager.setup_bat([("Office/Data/x.dat", 12345, parts)])
        lines = text.split("\r\n")
        self.assertEqual(lines[-1], "")
        self.assertNotIn("\n", text.replace("\r\n", ""))
        self.assertEqual(lines[2], 'cd /d "%~dp0" || exit 30')
        self.assertEqual(
            lines[3], 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File join.ps1 '
                      '"Office\\Data\\x.dat" || exit 31')
        self.assertNotIn("copy /b", text)
        self.assertIn('for %%F in ("Office\\Data\\x.dat") do if not "%%~zF"=="12345" exit 32', lines)
        self.assertEqual(lines[-3], 'start "" /wait setup.exe /configure configuration.xml')
        self.assertEqual(lines[-2], "exit %ERRORLEVEL%")
        self.assertIn(packager.SOURCE_PLACEHOLDER, lines[-4])
        self.assertTrue(lines[-4].endswith("|| exit 33"))
        text.encode("ascii")

    def test_every_own_exit_code_is_described(self):
        import re
        used = {int(code) for code in re.findall(r"exit (3[0-9])", packager.setup_bat([("a", 1, ["a.part001"])]))}
        self.assertEqual(used, set(packager.SETUP_BAT_CODES))


class BuildTests(unittest.TestCase):
    """A whole run with the network and 7z replaced: what is staged, and when nothing is built."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.saved = {name: getattr(packager, name) for name in ("remote_size", "download_file", "fetch_bytes", "PART_BYTES")}
        self.addCleanup(lambda: [setattr(packager, name, value) for name, value in self.saved.items()])
        packager.PART_BYTES = 10
        self.downloads = []
        self.staged = {}
        packager.remote_size = lambda url, what, curl=None: 25 if url.endswith("x-none.dat") else 4

        def download(url, path, what, curl=None):
            self.downloads.append(url)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(b"MZ" + b"z" * 23 if url.endswith(("x-none.dat", "setup.exe")) else b"abcd")
        packager.download_file = download
        test = self

        class Fake(packager.Microsoft365AppsPackager):
            def offered_version(self, base):
                test.base = base
                return VERSION

            def stub(self, work):
                path = os.path.join(work, "stub.sfx")
                with open(path, "wb") as handle:
                    handle.write(b"MZstub")
                return path

            def sevenzip(self):
                return "/usr/bin/true"
        self.Fake = Fake
        real_run = packager.subprocess.run

        def run(command, **kwargs):
            if command[0] == "/usr/bin/true" and command[1] == "a":
                stage = kwargs["cwd"]
                for root, _dirs, names in os.walk(stage):
                    for name in names:
                        full = os.path.join(root, name)
                        with open(full, "rb") as handle:
                            test.staged[os.path.relpath(full, stage)] = handle.read()
                with open(command[command.index("-y") + 1], "wb") as handle:
                    handle.write(b"ARCHIVE")
            return real_run(["/usr/bin/true"], capture_output=True, text=True)
        packager.subprocess.run = run
        self.addCleanup(lambda: setattr(packager.subprocess, "run", real_run))

    def env(self, **more):
        env = {"RECIPE_CACHE_DIR": self.folder.name, "sfx_sdk_url": "https://example.invalid/sdk.7z",
               "sfx_sdk_sha256": "0" * 64, "office_exclude_apps": "Access, Outlook"}
        env.update(more)
        return env

    def test_a_build_and_then_nothing_to_build(self):
        processor = self.Fake(env=self.env())
        processor.main()
        exe = processor.env["pathname"]
        self.assertEqual(os.path.basename(exe), "Microsoft365Apps-%s-x64.exe" % VERSION)
        with open(exe, "rb") as handle:
            self.assertEqual(handle.read(), b"MZstubARCHIVE")
        self.assertEqual(processor.env["version"], VERSION)
        self.assertNotIn("checksum_verified", processor.env)
        self.assertTrue(self.base.endswith("/" + packager.CHANNELS["MonthlyEnterprise"]))
        self.assertTrue(all(url.startswith(packager.CDN_PREFIX) for url in self.downloads))
        big = "Office/Data/%s/stream.x64.x-none.dat" % VERSION
        self.assertNotIn(big, self.staged)
        joined = b"".join(self.staged["%s.part%03d" % (big, number)] for number in (1, 2, 3))
        self.assertEqual(joined, b"MZ" + b"z" * 23)
        self.assertIn(b'"25" exit 32', self.staged["setup.bat"])
        self.assertIn(b"<ExcludeApp ID=\"Outlook\"", self.staged["configuration.xml"])
        self.assertEqual(self.staged["setup.exe"][:2], b"MZ")
        self.assertIn(b".part*", self.staged["join.ps1"])
        self.assertNotIn(b"\n", self.staged["join.ps1"].replace(b"\r\n", b""))
        self.assertEqual([name for name in os.listdir(self.folder.name) if name.startswith("m365-build-")], [])

        self.downloads.clear()
        again = self.Fake(env=self.env())
        again.main()
        self.assertEqual(again.env["pathname"], exe)
        self.assertEqual(self.downloads, [])

    def test_other_settings_build_again(self):
        self.Fake(env=self.env()).main()
        self.downloads.clear()
        self.Fake(env=self.env(office_exclude_apps="Access")).main()
        self.assertTrue(self.downloads)

    def test_an_exe_of_4_gib_is_refused(self):
        saved = packager.MAX_EXE_BYTES
        packager.MAX_EXE_BYTES = 5
        self.addCleanup(lambda: setattr(packager, "MAX_EXE_BYTES", saved))
        with self.assertRaises(ProcessorError):
            self.Fake(env=self.env()).main()
        self.assertEqual([name for name in os.listdir(self.folder.name) if name.endswith(".exe")], [])

    def test_a_file_of_the_wrong_size_stops_the_run(self):
        packager.remote_size = lambda url, what, curl=None: 5
        with self.assertRaises(ProcessorError):
            self.Fake(env=self.env()).main()

    def test_an_unknown_channel_stops_the_run(self):
        with self.assertRaises(ProcessorError):
            self.Fake(env=self.env(office_channel="Nightly")).main()


class RecipeTests(unittest.TestCase):
    def test_identifiers_and_parents(self):
        download, cimian, pcman = (load(name) for name in (
            "Microsoft365Apps-Win.download.recipe", "Microsoft365Apps.cimian.recipe", "Microsoft365Apps.pcman.recipe"))
        self.assertEqual(download["Identifier"], PREFIX + ".download.Microsoft365Apps-Win")
        self.assertNotIn("ParentRecipe", download)
        for recipe, kind in ((cimian, "cimian"), (pcman, "pcman")):
            self.assertEqual(recipe["Identifier"], "%s.%s.Microsoft365Apps" % (PREFIX, kind))
            self.assertEqual(recipe["ParentRecipe"], download["Identifier"])

    def test_the_download_recipe_passes_only_declared_inputs_and_every_input_is_set(self):
        recipe = load("Microsoft365Apps-Win.download.recipe")
        (step,) = recipe["Process"]
        self.assertEqual(step["Processor"], "Microsoft365AppsPackager")
        declared = packager.Microsoft365AppsPackager.input_variables
        self.assertEqual(set(step["Arguments"]) | {"sevenzip_path"}, set(declared))
        self.assertIs(recipe["Input"]["OFFICE_INCLUDE_ARM64X"], False)
        for value in step["Arguments"].values():
            self.assertIn(value.strip("%"), recipe["Input"])
        self.assertEqual(len(recipe["Input"]["SFX_SDK_SHA256"]), 64)
        self.assertTrue(recipe["Input"]["SFX_SDK_URL"].startswith("https://"))
        self.assertIs(recipe["Input"]["OFFICE_UPDATES_ENABLED"], False)
        self.assertIs(recipe["Input"]["OFFICE_FORCE_APP_SHUTDOWN"], False)

    def test_every_description_says_not_verified_first_and_no_recipe_claims_a_check(self):
        for name in os.listdir(RECIPE_DIR):
            if name.endswith(".recipe"):
                with self.subTest(name=name):
                    recipe = load(name)
                    self.assertIn("NOT verified", recipe["Description"].split(".")[0] + recipe["Description"][:120])
                    with open(os.path.join(RECIPE_DIR, name), encoding="utf-8") as handle:
                        text = handle.read()
                    self.assertNotIn("ChecksumVerifier", text)
                    self.assertNotIn("allow_unverified</key>", text)
                    self.assertNotIn("dry_run</key>", text)

    def test_the_importers_get_the_exe_and_the_office_version(self):
        cimian = load("Microsoft365Apps.cimian.recipe")["Process"][0]
        self.assertEqual(cimian["Processor"], PREFIX + ".SharedProcessors/CimianImporter")
        self.assertEqual(cimian["Arguments"]["version"], "%version%")
        self.assertEqual(cimian["Arguments"]["pathname"], "%pathname%")
        pcman = load("Microsoft365Apps.pcman.recipe")["Process"][0]
        self.assertEqual(pcman["Processor"], PREFIX + ".PcmanProcessors/PcmanImporter")
        self.assertEqual(pcman["Arguments"]["pcman_version"], "%version%")

    def test_the_readme_says_not_verified_at_the_top(self):
        with open(os.path.join(RECIPE_DIR, "README.md"), encoding="utf-8") as handle:
            self.assertIn("NOT verified", handle.read()[:1500])


if __name__ == "__main__":
    unittest.main()
