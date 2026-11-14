"""Tests of CimianImporter against a temporary Cimian repository.

The repository, the installers (files with bytes in them) and a stand-in for
msiinfo are made in a temporary folder (see _win_support.py). The pkginfo files
of the tests are made-up ones. The tests that read or write pkginfo files need
PyYAML, which AutoPkg's own Python has; they are skipped in a Python without it.
"""
import hashlib
import io
import os
import stat
import sys
import unittest
from unittest import mock

from _win_support import (
    PRODUCT_CODE,
    UPGRADE_CODE,
    ProcessorError,
    RepoTestCase,
    checksum,
    cimian,
    needs_yaml,
    new_processor,
    property_export,
    run_processor,
    sha256_hex,
    yaml,
)

IMPORTER = cimian.CimianImporter
BACKSLASH = chr(92)
# A path of the installed program, as it is written in a pkginfo (single backslashes).
EXE_PATH = r"C:\Program Files\Example App\example.exe"
TEMPLATE_HASH = "a" * 64
OLD_FILE_HASH = "b" * 64
OLD_PRODUCT_CODE = "{AAAAAAAA-0000-0000-0000-000000000001}"
OLD_UPGRADE_CODE = "{AAAAAAAA-0000-0000-0000-000000000002}"

# A made-up EXE item, in the shape of the pkginfo files that the client reads:
# the version is also in a file check, which has a hash of the installed file.
EXE_TEMPLATE = r"""display_name: Example App
version: 2.4.0
category: Utilities
description: A made-up program for the tests.
developer: Example Vendor
catalogs:
- Production
icon_name: Example-App.png
supported_architectures:
- x64
unattended_install: true
unattended_uninstall: true
installer:
  location: apps/Example-App-2.4.0.exe
  hash: %(hash)s
  size: 1661239
  type: exe
  args:
  - /S
check:
  file:
    path: C:\Program Files\Example App\example.exe
    version: 2.4.0
    hash: %(file_hash)s
name: Example-App
""" % {"hash": TEMPLATE_HASH, "file_hash": OLD_FILE_HASH}

# A made-up MSI item: no size, a Windows Installer entry in `installs`.
MSI_TEMPLATE = """display_name: Example Library
version: 2.4.0
category: Libraries
description: A made-up library for the tests.
developer: Example Vendor
catalogs:
- Production
unattended_install: true
installer:
  location: libs/Example-Lib-2.4.0.msi
  hash: %(hash)s
  type: msi
installs:
- type: msi
  product_code: '%(product)s'
  upgrade_code: '%(upgrade)s'
  version: 2.4.0
  display_name: Example Library
name: Example-Lib
""" % {"hash": TEMPLATE_HASH, "product": OLD_PRODUCT_CODE, "upgrade": UPGRADE_CODE}


def run(env):
    return run_processor(IMPORTER, env)


def lines(messages, prefix):
    return [m for m in messages if m.startswith(prefix)]


def text_of(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def files_of(tree):
    """The files of a tree (see tree_of), without the folders."""
    return {path: digest for path, digest in tree.items() if digest is not None}


class PyYamlCase(RepoTestCase):
    def put_exe_template(self, version="2.4.0", relpath=None, text=None):
        body = (text or EXE_TEMPLATE).replace("2.4.0", version)
        return self.put_pkginfo(relpath or "apps/Example-App-%s.yaml" % version, body)

    def another_exe(self, number):
        """An installer that is not the same file as self.exe."""
        return self.make_installer("another-%d.exe" % number, b"MZ" + bytes([number]) * 64)


@needs_yaml
class TemplateCopyTests(PyYamlCase):
    def test_a_new_version_copies_the_template_and_replaces_what_belongs_to_the_file(self):
        self.put_exe_template()
        old = self.read_pkginfo("apps/Example-App-2.4.0.yaml")
        processor, messages = run(self.env())
        new = self.read_pkginfo("apps/Example-App-2.5.0.yaml")
        self.assertEqual(processor.env["cimian_result"], "published")
        self.assertEqual(new["version"], "2.5.0")
        self.assertEqual(new["installer"]["location"], "apps/Example-App-2.5.0.exe")
        self.assertEqual(new["installer"]["hash"], sha256_hex(self.exe))
        self.assertEqual(new["installer"]["size"], os.path.getsize(self.exe))
        self.assertEqual(new["installer"]["type"], "exe")
        self.assertEqual(new["check"]["file"]["version"], "2.5.0")
        self.assertNotIn("hash", new["check"]["file"])
        # everything else is the template's
        for key in ("display_name", "category", "description", "developer", "catalogs", "icon_name",
                    "supported_architectures", "unattended_install", "unattended_uninstall", "name"):
            self.assertEqual(new[key], old[key], key)
        self.assertEqual(new["installer"]["args"], ["/S"])
        self.assertEqual(new["check"]["file"]["path"], old["check"]["file"]["path"])

    def test_the_key_order_of_the_template_is_kept(self):
        self.put_exe_template()
        old = self.read_pkginfo("apps/Example-App-2.4.0.yaml")
        run(self.env())
        new = self.read_pkginfo("apps/Example-App-2.5.0.yaml")
        self.assertEqual(list(new), list(old))
        self.assertEqual(list(new["installer"]), list(old["installer"]))
        self.assertEqual(list(new["check"]["file"]), ["path", "version"])

    def test_the_installer_is_copied_unchanged_into_pkgs(self):
        self.put_exe_template()
        run(self.env())
        copied = os.path.join(self.repo, "pkgs", "apps", "Example-App-2.5.0.exe")
        self.assertEqual(sha256_hex(copied), sha256_hex(self.exe))
        self.assertEqual(stat.S_IMODE(os.stat(copied).st_mode), 0o644)
        self.assertTrue(os.path.isfile(self.exe))  # the download stays where it was

    def test_the_template_is_the_highest_version_by_the_clients_order(self):
        self.put_exe_template("1.9.0", text=EXE_TEMPLATE.replace("Example App", "From 1.9.0"))
        self.put_exe_template("1.10.0", text=EXE_TEMPLATE.replace("Example App", "From 1.10.0"))
        self.put_exe_template("1.2.0", text=EXE_TEMPLATE.replace("Example App", "From 1.2.0"))
        run(self.env())
        new = self.read_pkginfo("apps/Example-App-2.5.0.yaml")
        self.assertEqual(new["display_name"], "From 1.10.0")

    def test_a_file_of_another_item_is_never_the_template(self):
        self.put_exe_template("2.4.0", relpath="apps/Other.yaml",
                              text=EXE_TEMPLATE.replace("name: Example-App", "name: Other-App"))
        processor, messages = run(self.env(cimian_catalogs=["Testing"]))
        new = self.read_pkginfo("Example-App-2.5.0.yaml")
        self.assertEqual(new["catalogs"], ["Testing"])

    def test_the_new_version_goes_into_the_folder_of_the_templates_installer(self):
        self.put_exe_template(text=EXE_TEMPLATE.replace("apps/Example-App", "tools/deep/Example-App"))
        run(self.env())
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "pkgs", "tools", "deep", "Example-App-2.5.0.exe")))
        self.assertEqual(self.read_pkginfo("tools/deep/Example-App-2.5.0.yaml")["installer"]["location"],
                         "tools/deep/Example-App-2.5.0.exe")

    def test_a_subdirectory_given_wins_over_the_templates_folder(self):
        self.put_exe_template()
        run(self.env(cimian_subdirectory="newer"))
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "pkgs", "newer", "Example-App-2.5.0.exe")))
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "pkgsinfo", "newer", "Example-App-2.5.0.yaml")))
        self.assertEqual(self.read_pkginfo("newer/Example-App-2.5.0.yaml")["installer"]["location"],
                         "newer/Example-App-2.5.0.exe")

    def test_a_template_with_a_windows_location_gives_its_folder(self):
        self.put_exe_template(text=EXE_TEMPLATE.replace("apps/Example-App-2.4.0.exe", "apps" + BACKSLASH + "win" + BACKSLASH + "Example-App-2.4.0.exe"))
        run(self.env())
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "pkgs", "apps", "win", "Example-App-2.5.0.exe")))

    def test_the_name_is_kept_as_the_repository_writes_it(self):
        self.put_exe_template(text=EXE_TEMPLATE.replace("name: Example-App", "name: example-app"))
        processor, messages = run(self.env())
        new = self.read_pkginfo("apps/example-app-2.5.0.yaml")
        self.assertEqual(new["name"], "example-app")
        self.assertTrue(any("writes the name as example-app" in m for m in messages))

    def test_a_force_date_is_not_carried(self):
        self.put_exe_template(text=EXE_TEMPLATE.replace("name: Example-App",
                                                        "force_install_after_date: 2026-01-01\nname: Example-App"))
        processor, messages = run(self.env())
        self.assertNotIn("force_install_after_date", self.read_pkginfo("apps/Example-App-2.5.0.yaml"))
        self.assertTrue(any("force_install_after_date of the template is not carried" in m for m in messages))

    def test_a_version_that_is_not_the_templates_is_kept_and_said(self):
        self.put_exe_template(text=EXE_TEMPLATE.replace("    version: 2.4.0\n", "    version: 9.9.9\n"))
        processor, messages = run(self.env())
        new = self.read_pkginfo("apps/Example-App-2.5.0.yaml")
        self.assertEqual(new["check"]["file"]["version"], "9.9.9")
        warning = lines(messages, "WARNING: check.file.version is 9.9.9, not the template's version 2.4.0")
        self.assertEqual(len(warning), 1)

    def test_the_hash_of_an_installed_file_is_dropped_and_said(self):
        self.put_exe_template()
        processor, messages = run(self.env())
        self.assertTrue(any("check.file.hash belongs to a file of the old version" in m for m in messages))

    def test_the_md5checksum_of_an_installs_entry_is_dropped(self):
        text = EXE_TEMPLATE.replace("check:\n  file:\n    path: %s\n"
                                    "    version: 2.4.0\n    hash: %s\n" % (EXE_PATH, OLD_FILE_HASH),
                                    "installs:\n- type: file\n  path: %s\n"
                                    "  md5checksum: %s\n  version: 2.4.0\n" % (EXE_PATH, OLD_FILE_HASH))
        self.assertIn("installs:", text)
        self.put_exe_template(text=text)
        processor, messages = run(self.env())
        entry = self.read_pkginfo("apps/Example-App-2.5.0.yaml")["installs"][0]
        self.assertEqual(entry, {"type": "file", "path": EXE_PATH,
                                 "version": "2.5.0"})
        self.assertTrue(any("installs[1].md5checksum belongs to a file of the old version" in m for m in messages))

    def test_a_script_that_holds_the_old_version_is_named(self):
        text = EXE_TEMPLATE.replace("name: Example-App", "installcheck_script: test 2.4.0 = x\nname: Example-App")
        self.put_exe_template(text=text)
        processor, messages = run(self.env())
        self.assertEqual(len(lines(messages, "WARNING: installcheck_script contains the template's version 2.4.0")), 1)

    def test_a_version_inside_another_number_is_not_the_old_version(self):
        text = EXE_TEMPLATE.replace("name: Example-App", "installcheck_script: a 12.4.0 b 2.4.01 c 2.4.0" + ".1\nname: Example-App")
        self.put_exe_template(text=text)
        processor, messages = run(self.env())
        self.assertEqual(lines(messages, "WARNING: installcheck_script"), [])

    def test_a_template_of_another_kind_of_installer_is_refused(self):
        self.put_exe_template()
        with self.assertRaises(ProcessorError) as caught:
            run(self.env(self.msi, version=None, cimian_path=self.msi_bin))
        self.assertIn("is of the kind exe, and the file is an .msi", str(caught.exception))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "pkgs", "apps", "Example-App-2.5.0.msi")))

    def test_the_catalogs_of_the_template_are_kept_and_the_input_is_not_used(self):
        self.put_exe_template()
        run(self.env(cimian_catalogs=["Testing"]))
        self.assertEqual(self.read_pkginfo("apps/Example-App-2.5.0.yaml")["catalogs"], ["Production"])

    def test_a_pkginfo_input_never_changes_what_the_template_has_and_the_notes_say_so(self):
        """The generic recipes carry a pkginfo (a display name, say) in their Input on every run: it
        must not rename the item or double the installer's arguments."""
        text = EXE_TEMPLATE.replace("  args:\n  - /S\n", "  switches:\n  - /S\n  - /D=C:" + BACKSLASH + "Tools\n")
        self.assertIn("switches:", text)
        self.put_exe_template(text=text)
        pkginfo = {"display_name": "Example Application", "developer": "Another Vendor",
                   "catalogs": ["Testing"], "installer": {"args": ["/S"]}}
        processor, messages = run(self.env(pkginfo=pkginfo))
        new = self.read_pkginfo("apps/Example-App-2.5.0.yaml")
        old = self.read_pkginfo("apps/Example-App-2.4.0.yaml")
        self.assertEqual(new["display_name"], old["display_name"])
        self.assertEqual(new["developer"], old["developer"])
        self.assertEqual(new["catalogs"], ["Production"])
        self.assertEqual(new["installer"]["switches"], ["/S", r"/D=C:\Tools"])
        self.assertNotIn("args", new["installer"])
        for key in ("display_name", "developer", "catalogs"):
            self.assertEqual(len(lines(messages, "NOTE: pkginfo's %s differs from the template's and is not used" % key)), 1, key)
        self.assertEqual(len(lines(messages, "NOTE: pkginfo's installer.args is not used: the template gives the installer's "
                                             "arguments as installer.switches")), 1)
        joined = "\n".join(messages)
        self.assertNotIn("everything else", joined)  # the old claim that the display name and the arguments were carried
        self.assertEqual(len(lines(messages, "NOTE: this pkginfo is a copy of the template Example-App 2.4.0")), 1)

    def test_a_pkginfo_key_that_the_template_lacks_is_added_and_said(self):
        self.put_exe_template()
        processor, messages = run(self.env(pkginfo={"blocking_applications": ["example.exe"],
                                                    "installer": {"success_codes": [3010]}}))
        new = self.read_pkginfo("apps/Example-App-2.5.0.yaml")
        self.assertEqual(new["blocking_applications"], ["example.exe"])
        self.assertEqual(new["installer"]["success_codes"], [3010])
        self.assertEqual(len(lines(messages, "NOTE: pkginfo gives blocking_applications and the template has none")), 1)
        self.assertEqual(len(lines(messages, "NOTE: pkginfo gives installer.success_codes and the template has none")), 1)
        self.assertEqual(new["installer"]["hash"], sha256_hex(self.exe))  # the merge never touches the file's values
        self.assertEqual(new["installer"]["location"], "apps/Example-App-2.5.0.exe")

    def test_a_pkginfo_value_that_equals_the_templates_says_nothing(self):
        self.put_exe_template()
        processor, messages = run(self.env(pkginfo={"display_name": "Example App", "installer": {"args": ["/S"]}}))
        self.assertEqual(lines(messages, "NOTE: pkginfo"), [])

    def test_pkginfo_wins_over_the_template_only_when_asked_and_each_key_is_named(self):
        text = EXE_TEMPLATE.replace("  args:\n  - /S\n", "  switches:\n  - /S\n  - /D=C:" + BACKSLASH + "Tools\n")
        self.put_exe_template(text=text)
        processor, messages = run(self.env(cimian_pkginfo_wins=True, pkginfo={
            "display_name": "Example Application", "catalogs": ["Testing"], "installer": {"args": ["/S"]}}))
        new = self.read_pkginfo("apps/Example-App-2.5.0.yaml")
        self.assertEqual(new["display_name"], "Example Application")
        self.assertEqual(new["catalogs"], ["Testing"])
        self.assertEqual(new["installer"]["args"], ["/S"])
        self.assertNotIn("switches", new["installer"])
        for where in ("display_name", "catalogs"):
            self.assertEqual(len(lines(messages, "NOTE: pkginfo replaces %s of the template." % where)), 1, where)
        self.assertEqual(len(lines(messages, "NOTE: pkginfo gives the installer's arguments as args, so the template's "
                                             "installer.switches is not carried")), 1)
        self.assertEqual(new["installer"]["hash"], sha256_hex(self.exe))
        self.assertEqual(new["installer"]["location"], "apps/Example-App-2.5.0.exe")

    def test_a_dry_run_names_the_same_changes_as_a_real_run(self):
        self.put_exe_template()
        pkginfo = {"display_name": "Example Application", "blocking_applications": ["example.exe"]}
        before = self.repo_tree()
        dry, dry_messages = run(self.env(cimian_dry_run=True, pkginfo=pkginfo))
        self.assertEqual(self.repo_tree(), before)
        real, real_messages = run(self.env(pkginfo=pkginfo))
        pick = lambda messages: sorted(m for m in messages if m.startswith(("NOTE", "WARNING")) and "DRY RUN" not in m)
        self.assertEqual(pick(dry_messages), pick(real_messages))
        self.assertTrue(pick(real_messages))

    def test_the_switch_that_lets_pkginfo_win_is_parsed_like_the_others(self):
        for value in ("maybe", "", 2):
            with self.subTest(value=value):
                with self.assertRaises(ProcessorError):
                    run(self.env(cimian_pkginfo_wins=value))

    def test_the_templates_own_scripts_survive_in_a_literal_block(self):
        text = EXE_TEMPLATE.replace(
            "name: Example-App",
            "postinstall_script: |\n  Write-Host 'one'\n  Write-Host \"two\"\nname: Example-App")
        self.put_exe_template(text=text)
        run(self.env())
        written = self.read_text("pkgsinfo", "apps", "Example-App-2.5.0.yaml")
        self.assertIn("postinstall_script: |\n  Write-Host 'one'\n  Write-Host \"two\"\n", written)


@needs_yaml
class MsiTemplateTests(PyYamlCase):
    def setUp(self):
        super().setUp()
        self.put_pkginfo("libs/Example-Lib-2.4.0.yaml", MSI_TEMPLATE)
        self.msiinfo_says(stdout=property_export(version="2.5.0"))

    def env(self, installer=None, **overrides):
        values = {"cimian_name": "Example-Lib", "version": None, "cimian_path": self.msi_bin}
        values.update(overrides)
        return super().env(installer or self.msi, **values)

    def test_the_codes_and_the_versions_of_the_install_check_are_those_of_the_new_msi(self):
        processor, messages = run(self.env())
        new = self.read_pkginfo("libs/Example-Lib-2.5.0.yaml")
        self.assertEqual(new["version"], "2.5.0")
        self.assertEqual(new["installs"], [{
            "type": "msi", "product_code": PRODUCT_CODE, "upgrade_code": UPGRADE_CODE,
            "version": "2.5.0", "display_name": "Example Library"}])
        self.assertEqual(new["installer"]["type"], "msi")
        self.assertEqual(new["installer"]["location"], "libs/Example-Lib-2.5.0.msi")
        self.assertEqual(new["installer"]["hash"], sha256_hex(self.msi))
        self.assertEqual(new["installer"]["size"], os.path.getsize(self.msi))
        self.assertEqual(list(new["installer"]), ["location", "hash", "type", "size"])
        self.assertEqual(self.msiinfo_calls(), [["export", self.msi, "Property"]])

    def test_the_label_defaults_to_the_products_own_version(self):
        processor, messages = run(self.env())
        self.assertEqual(processor.env["cimian_version_imported"], "2.5.0")

    def test_the_same_label_is_accepted_and_another_is_refused(self):
        before = self.repo_tree()
        with self.assertRaises(ProcessorError) as caught:
            run(self.env(version="2.6.0"))
        self.assertIn("the MSI's own ProductVersion is 2.5.0", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)
        processor, _ = run(self.env(version="2.5.0"))
        self.assertEqual(processor.env["cimian_result"], "published")

    def test_the_installs_of_the_older_form_in_the_installer_block_follow(self):
        text = MSI_TEMPLATE.replace("  type: msi\ninstalls:", "  type: msi\n  product_code: '%s'\n  upgrade_code: '%s'\ninstalls:"
                                    % (OLD_PRODUCT_CODE, UPGRADE_CODE), 1)
        self.put_pkginfo("libs/Example-Lib-2.4.0.yaml", text)
        run(self.env())
        installer = self.read_pkginfo("libs/Example-Lib-2.5.0.yaml")["installer"]
        self.assertEqual((installer["product_code"], installer["upgrade_code"]), (PRODUCT_CODE, UPGRADE_CODE))

    def test_an_msi_without_an_upgrade_code_loses_the_stale_one_and_is_warned_when_it_is_allowed(self):
        self.msiinfo_says(stdout=property_export(version="2.5.0", upgrade_code=None))
        processor, messages = run(self.env(cimian_allow_product_change=True))
        entry = self.read_pkginfo("libs/Example-Lib-2.5.0.yaml")["installs"][0]
        self.assertNotIn("upgrade_code", entry)
        self.assertEqual(entry["product_code"], PRODUCT_CODE)
        self.assertEqual(len(lines(messages, "WARNING: the MSI has no UpgradeCode")), 1)
        self.assertEqual(len(lines(messages, "WARNING: the upgrade code of the MSI is not the template's, and "
                                             "cimian_allow_product_change is true")), 1)

    def test_an_msi_without_an_upgrade_code_is_refused_where_the_template_had_one(self):
        """The same side-by-side risk as another code: the old product would no longer be this item's."""
        self.msiinfo_says(stdout=property_export(version="2.5.0", upgrade_code=None))
        before = self.repo_tree()
        for dry in (True, False):
            with self.subTest(dry_run=dry):
                with self.assertRaises(ProcessorError) as caught:
                    run(self.env(cimian_dry_run=dry))
                self.assertIn("The upgrade code of this MSI (none) is not the template's", str(caught.exception))
                self.assertIn("cimian_allow_product_change", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    def test_a_template_without_an_msi_entry_gets_none(self):
        text = MSI_TEMPLATE.replace("installs:\n- type: msi\n  product_code: '%s'\n  upgrade_code: '%s'\n"
                                    "  version: 2.4.0\n  display_name: Example Library\n"
                                    % (OLD_PRODUCT_CODE, UPGRADE_CODE), "")
        self.assertNotIn("installs", text)
        self.put_pkginfo("libs/Example-Lib-2.4.0.yaml", text)
        run(self.env())
        self.assertNotIn("installs", self.read_pkginfo("libs/Example-Lib-2.5.0.yaml"))

    OTHER_UPGRADE_CODE = "{11111111-2222-3333-4444-555555555555}"

    def test_an_msi_with_another_upgrade_code_than_the_templates_is_refused(self):
        self.msiinfo_says(stdout=property_export(version="2.5.0", upgrade_code=self.OTHER_UPGRADE_CODE))
        before = self.repo_tree()
        for dry in (True, False):
            with self.subTest(dry_run=dry):
                with self.assertRaises(ProcessorError) as caught:
                    run(self.env(cimian_dry_run=dry))
                self.assertIn("is not the template's", str(caught.exception))
                self.assertIn("cimian_allow_product_change", str(caught.exception))
                self.assertIn(self.OTHER_UPGRADE_CODE, str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    def test_the_override_can_allow_another_upgrade_code_with_a_warning(self):
        self.msiinfo_says(stdout=property_export(version="2.5.0", upgrade_code=self.OTHER_UPGRADE_CODE))
        processor, messages = run(self.env(cimian_allow_product_change=True))
        entry = self.read_pkginfo("libs/Example-Lib-2.5.0.yaml")["installs"][0]
        self.assertEqual(entry["upgrade_code"], self.OTHER_UPGRADE_CODE)
        self.assertEqual(len(lines(messages, "WARNING: the upgrade code of the MSI is not the template's, and "
                                             "cimian_allow_product_change is true")), 1)

    def test_the_allowance_for_another_product_is_parsed_strictly(self):
        for value in ("maybe", "", 2):
            with self.subTest(value=value):
                with self.assertRaises(ProcessorError):
                    run(self.env(cimian_allow_product_change=value))

    def test_another_upgrade_code_in_the_older_form_is_refused_too(self):
        text = MSI_TEMPLATE.replace("  type: msi\ninstalls:", "  type: msi\n  upgrade_code: '%s'\ninstalls:" % OLD_UPGRADE_CODE, 1)
        text = text.replace("  upgrade_code: '%s'\n  version: 2.4.0" % UPGRADE_CODE, "  version: 2.4.0")
        self.put_pkginfo("libs/Example-Lib-2.4.0.yaml", text)
        with self.assertRaises(ProcessorError) as caught:
            run(self.env())
        self.assertIn("cimian_allow_product_change", str(caught.exception))

    def test_the_uninstaller_of_an_msi_follows_the_new_product_code(self):
        text = MSI_TEMPLATE.replace("name: Example-Lib", "uninstaller:\n- type: msi\n  product_code: '%s'\nname: Example-Lib" % OLD_PRODUCT_CODE)
        self.put_pkginfo("libs/Example-Lib-2.4.0.yaml", text)
        processor, messages = run(self.env())
        new = self.read_pkginfo("libs/Example-Lib-2.5.0.yaml")
        self.assertEqual(new["uninstaller"], [{"type": "msi", "product_code": PRODUCT_CODE}])
        self.assertEqual(len(lines(messages, "NOTE: uninstaller[1].product_code was the old product code")), 1)

    def test_an_uninstaller_that_is_not_the_old_product_is_kept_and_said(self):
        text = MSI_TEMPLATE.replace("name: Example-Lib", "uninstaller:\n- type: msi\n  product_code: '%s'\n- type: msi\n"
                                    "  product_code: '{BBBBBBBB-0000-0000-0000-000000000009}'\nname: Example-Lib" % OLD_PRODUCT_CODE)
        self.put_pkginfo("libs/Example-Lib-2.4.0.yaml", text)
        processor, messages = run(self.env())
        new = self.read_pkginfo("libs/Example-Lib-2.5.0.yaml")
        self.assertEqual([entry["product_code"] for entry in new["uninstaller"]],
                         [PRODUCT_CODE, "{BBBBBBBB-0000-0000-0000-000000000009}"])
        self.assertEqual(len(lines(messages, "WARNING: uninstaller[2].product_code is not the template's product code")), 1)

    def test_a_script_uninstaller_is_left_alone(self):
        text = MSI_TEMPLATE.replace("name: Example-Lib", "uninstaller:\n- type: ps1\n  command: remove.ps1\nname: Example-Lib")
        self.put_pkginfo("libs/Example-Lib-2.4.0.yaml", text)
        processor, messages = run(self.env())
        self.assertEqual(self.read_pkginfo("libs/Example-Lib-2.5.0.yaml")["uninstaller"], [{"type": "ps1", "command": "remove.ps1"}])
        self.assertEqual(lines(messages, "WARNING: uninstaller"), [])

    PREREQUISITE = ("- type: msi\n  product_code: '{CCCCCCCC-0000-0000-0000-000000000001}'\n"
                    "  upgrade_code: '{CCCCCCCC-0000-0000-0000-000000000002}'\n  version: 9.0\n")

    def test_an_msi_entry_that_is_another_product_keeps_its_codes(self):
        text = MSI_TEMPLATE.replace("installs:\n", "installs:\n" + self.PREREQUISITE)
        self.put_pkginfo("libs/Example-Lib-2.4.0.yaml", text)
        processor, messages = run(self.env())
        installs = self.read_pkginfo("libs/Example-Lib-2.5.0.yaml")["installs"]
        self.assertEqual(installs[0]["product_code"], "{CCCCCCCC-0000-0000-0000-000000000001}")
        self.assertEqual(installs[0]["version"], "9.0")
        self.assertEqual(installs[1]["product_code"], PRODUCT_CODE)
        self.assertEqual(installs[1]["version"], "2.5.0")
        self.assertEqual(len(lines(messages, "WARNING: installs[1] is another msi entry, not this product's")), 1)

    def test_two_msi_entries_and_none_with_the_new_upgrade_code_cannot_be_told_apart(self):
        text = MSI_TEMPLATE.replace("installs:\n", "installs:\n" + self.PREREQUISITE)
        text = text.replace("  upgrade_code: '%s'\n  version: 2.4.0" % UPGRADE_CODE, "  upgrade_code: '%s'\n  version: 2.4.0" % OLD_UPGRADE_CODE)
        self.put_pkginfo("libs/Example-Lib-2.4.0.yaml", text)
        before = self.repo_tree()
        with self.assertRaises(ProcessorError) as caught:
            run(self.env())
        self.assertIn("The template has 2 msi entries in installs, and none of them has the new MSI's upgrade code",
                      str(caught.exception))
        self.assertEqual(self.repo_tree(), before)


@needs_yaml
class NothingNewTests(PyYamlCase):
    def setUp(self):
        super().setUp()
        self.put_exe_template("2.5.0")  # the repository has this version already
        self.before = self.repo_tree()

    def test_the_same_version_writes_nothing_and_is_not_an_error(self):
        processor, messages = run(self.env())
        self.assertEqual(self.repo_tree(), self.before)
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertIs(processor.env["cimian_repo_changed"], False)
        self.assertNotIn("cimian_importer_summary_result", processor.env)
        self.assertEqual(messages[0],
                         "Nothing new: Example-App 2.5.0 is in the repository already (it has this version). "
                         "Nothing was written.")
        self.assertEqual(processor.env["cimian_version_imported"], "2.5.0")

    def test_the_line_is_shown_at_every_verbosity(self):
        processor, messages = new_processor(IMPORTER, self.env())
        processor.main()
        self.assertEqual({level for level, _ in processor.message_levels}, {0})

    def test_a_version_the_client_reads_as_the_same_is_the_same(self):
        processor, messages = run(self.env(version="2.5"))
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertEqual(self.repo_tree(), self.before)

    def test_the_same_installer_file_under_another_version_is_nothing_new(self):
        digest = sha256_hex(self.exe)
        self.put_pkginfo("apps/Example-App-2.5.0.yaml",
                         EXE_TEMPLATE.replace("2.4.0", "2.5.0").replace(TEMPLATE_HASH, digest))
        before = self.repo_tree()
        processor, messages = run(self.env(version="3.0.0"))
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertIn("it has this very installer file", messages[0])
        self.assertEqual(self.repo_tree(), before)

    def test_the_same_version_with_another_installer_file_says_so_and_writes_nothing(self):
        other = os.path.join(self.downloads, "other.exe")
        with open(other, "wb") as handle:
            handle.write(b"another installer")
        processor, messages = run(self.env(other))
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertTrue(any("has another installer file; nothing was written" in m for m in messages))
        self.assertEqual(self.repo_tree(), self.before)

    def test_a_dry_run_says_nothing_new_too(self):
        processor, messages = run(self.env(cimian_dry_run=True))
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertEqual(lines(messages, "WARNING: DRY RUN"), [])

    def test_the_msi_facts_are_not_needed_when_the_installer_file_is_known(self):
        digest = sha256_hex(self.msi)
        self.put_pkginfo("libs/Example-Lib-2.4.0.yaml", MSI_TEMPLATE.replace(TEMPLATE_HASH, digest))
        before = self.repo_tree()
        processor, messages = run(self.env(self.msi, cimian_name="Example-Lib", version=None, cimian_path=self.empty_bin))
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertEqual(self.repo_tree(), before)


@needs_yaml
class NoTemplateTests(PyYamlCase):
    def test_the_pkginfo_is_built_from_the_inputs(self):
        processor, messages = run(self.env(pkginfo={
            "display_name": "Example App", "developer": "Example Vendor", "category": "Utilities",
            "description": "A made-up program.", "installer": {"args": ["/S"]},
            "check": {"file": {"path": EXE_PATH}},
            "unattended_install": True}))
        new = self.read_pkginfo("Example-App-2.5.0.yaml")
        self.assertEqual(new, {
            "name": "Example-App", "display_name": "Example App", "version": "2.5.0",
            "catalogs": ["Development"], "category": "Utilities", "description": "A made-up program.",
            "developer": "Example Vendor", "unattended_install": True,
            "check": {"file": {"path": EXE_PATH}},
            "installer": {"type": "exe", "size": os.path.getsize(self.exe),
                          "location": "Example-App-2.5.0.exe", "hash": sha256_hex(self.exe), "args": ["/S"]},
        })
        # the order of Cimian's own makepkginfo
        self.assertEqual(list(new), ["name", "display_name", "version", "catalogs", "category", "description",
                                     "developer", "unattended_install", "check", "installer"])
        self.assertEqual(list(new["installer"]), ["type", "size", "location", "hash", "args"])
        self.assertEqual(os.path.getsize(os.path.join(self.repo, "pkgs", "Example-App-2.5.0.exe")), os.path.getsize(self.exe))

    def test_the_catalogs_are_the_input_and_default_to_the_one_cimians_own_tools_use(self):
        run(self.env(cimian_catalogs=["Testing", "Pilot"]))
        self.assertEqual(self.read_pkginfo("Example-App-2.5.0.yaml")["catalogs"], ["Testing", "Pilot"])
        run(self.env(self.another_exe(1), version="2.6.0"))
        # the second run has a template now: its catalogs are kept
        self.assertEqual(self.read_pkginfo("Example-App-2.6.0.yaml")["catalogs"], ["Testing", "Pilot"])

    def test_the_catalogs_may_be_a_comma_separated_text(self):
        run(self.env(cimian_catalogs="Testing, Pilot"))
        self.assertEqual(self.read_pkginfo("Example-App-2.5.0.yaml")["catalogs"], ["Testing", "Pilot"])

    def test_a_bad_catalogs_input_is_an_error(self):
        for value in ([], "", [""], [1], 5):
            with self.subTest(value=value):
                with self.assertRaises(ProcessorError):
                    run(self.env(cimian_catalogs=value))

    def test_the_subdirectory_is_used_for_both_folders(self):
        run(self.env(cimian_subdirectory="util"))
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "pkgs", "util", "Example-App-2.5.0.exe")))
        self.assertEqual(self.read_pkginfo("util/Example-App-2.5.0.yaml")["installer"]["location"],
                         "util/Example-App-2.5.0.exe")

    def test_an_exe_without_an_install_check_is_warned(self):
        processor, messages = run(self.env())
        self.assertEqual(len(lines(messages, "WARNING: this pkginfo has no install check")), 1)
        processor, messages = run(self.env(self.another_exe(2), version="2.6.0",
                                           pkginfo={"check": {"file": {"path": r"C:\x.exe"}}}))
        self.assertEqual(lines(messages, "WARNING: this pkginfo has no install check"), [])

    def test_an_msi_gets_a_windows_installer_entry_and_the_products_own_version(self):
        processor, messages = run(self.env(self.msi, version=None))
        new = self.read_pkginfo("Example-App-2.5.0.yaml")
        self.assertEqual(new["installs"], [{"type": "msi", "product_code": PRODUCT_CODE,
                                            "upgrade_code": UPGRADE_CODE, "version": "2.5.0"}])
        self.assertEqual(new["installer"]["type"], "msi")
        self.assertEqual(lines(messages, "WARNING: this pkginfo has no install check"), [])

    def test_an_msi_entry_is_added_when_the_pkginfo_input_gives_other_installs(self):
        run(self.env(self.msi, version=None, pkginfo={"installs": [{"type": "file", "path": r"C:\x.exe"}]}))
        installs = self.read_pkginfo("Example-App-2.5.0.yaml")["installs"]
        self.assertEqual([entry["type"] for entry in installs], ["file", "msi"])
        self.assertEqual(installs[1]["product_code"], PRODUCT_CODE)

    def test_an_msi_entry_of_the_pkginfo_input_gets_the_codes_it_lacks(self):
        run(self.env(self.msi, version=None, pkginfo={"installs": [{"type": "msi", "display_name": "Example"}]}))
        entry = self.read_pkginfo("Example-App-2.5.0.yaml")["installs"][0]
        self.assertEqual((entry["product_code"], entry["upgrade_code"]), (PRODUCT_CODE, UPGRADE_CODE))
        self.assertEqual(entry["display_name"], "Example")

    def test_codes_in_the_pkginfo_input_that_are_not_the_msis_are_refused(self):
        for entry in ({"type": "msi", "product_code": OLD_PRODUCT_CODE},
                      {"type": "msi", "upgrade_code": OLD_UPGRADE_CODE}):
            with self.subTest(entry=entry):
                before = self.repo_tree()
                with self.assertRaises(ProcessorError) as caught:
                    run(self.env(self.msi, version=None, pkginfo={"installs": [entry]}))
                self.assertIn("leave them out of pkginfo", str(caught.exception))
                self.assertEqual(self.repo_tree(), before)

    def test_what_belongs_to_the_file_cannot_be_set_by_the_pkginfo_input(self):
        for extra in ({"name": "X"}, {"version": "9"}, {"installer": {"location": "a"}},
                      {"installer": {"hash": "a"}}, {"installer": {"size": 1}}, {"installer": {"type": "msi"}},
                      {"installer": "text"}):
            with self.subTest(extra=extra):
                before = self.repo_tree()
                with self.assertRaises(ProcessorError):
                    run(self.env(pkginfo=extra))
                self.assertEqual(self.repo_tree(), before)

    def test_a_pkginfo_input_that_is_not_a_dictionary_is_an_error(self):
        for value in ("text", ["a"], 5):
            with self.subTest(value=value):
                with self.assertRaises(ProcessorError):
                    run(self.env(pkginfo=value))

    def test_an_empty_pkginfo_input_counts_as_none(self):
        run(self.env(pkginfo=""))
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "pkgsinfo", "Example-App-2.5.0.yaml")))

    def test_the_pkginfo_input_keeps_the_texts_of_nested_values(self):
        run(self.env(pkginfo={"installer": {"args": ["/S", r"/D=C:\Example App"]}, "blocking_applications": ["example.exe"]}))
        new = self.read_pkginfo("Example-App-2.5.0.yaml")
        self.assertEqual(new["installer"]["args"], ["/S", r"/D=C:\Example App"])
        self.assertEqual(new["blocking_applications"], ["example.exe"])


@needs_yaml
class UnreadableFileTests(PyYamlCase):
    def test_an_unreadable_file_that_names_the_item_stops_a_run_without_a_template(self):
        self.put_pkginfo("apps/Broken.yaml", "name: Example-App\nversion: [unclosed\n")
        before = self.repo_tree()
        with self.assertRaises(ProcessorError) as caught:
            run(self.env())
        self.assertIn("the template may be among them", str(caught.exception))
        self.assertIn("apps/Broken.yaml", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    def test_an_unreadable_file_beside_a_template_is_said_and_the_run_goes_on(self):
        self.put_exe_template()
        self.put_pkginfo("apps/Broken.yaml", "name: Example-App\nversion: [unclosed\n")
        processor, messages = run(self.env())
        self.assertEqual(processor.env["cimian_result"], "published")
        self.assertEqual(len(lines(messages, "NOTE: 1 pkginfo file(s) could not be read and were left out: pkgsinfo/apps/Broken.yaml")), 1)

    def test_a_broken_file_that_does_not_hold_the_name_is_not_read(self):
        self.put_pkginfo("apps/Other.yaml", "name: Other\n  : [unclosed\n")
        processor, messages = run(self.env())
        self.assertEqual(processor.env["cimian_result"], "published")
        self.assertEqual(lines(messages, "NOTE"), [])

    def test_a_file_that_is_not_text_stops_a_run_without_a_template(self):
        path = os.path.join(self.repo, "pkgsinfo", "binary.yaml")
        with open(path, "wb") as handle:
            handle.write(b"\xff\xfe\x00name")
        with self.assertRaises(ProcessorError):
            run(self.env())

    def test_files_of_the_item_with_no_readable_version_leave_no_template(self):
        self.put_pkginfo("apps/Odd.yaml", "name: Example-App\nversion: latest\n")
        with self.assertRaises(ProcessorError) as caught:
            run(self.env())
        self.assertIn("none with a version that Cimian can read", str(caught.exception))

    def test_only_files_that_end_in_yaml_are_read(self):
        self.put_pkginfo("apps/Example-App-2.4.0.yml", EXE_TEMPLATE)
        self.put_pkginfo("apps/Example-App-2.4.0.txt", EXE_TEMPLATE)
        processor, messages = run(self.env())
        self.assertEqual(self.read_pkginfo("Example-App-2.5.0.yaml")["catalogs"], ["Development"])


@needs_yaml
class DryRunTests(PyYamlCase):
    def test_a_dry_run_is_the_default_and_writes_nothing(self):
        self.put_exe_template()
        before = self.repo_tree()
        processor, messages = run(self.env(cimian_dry_run=None))
        self.assertEqual(self.repo_tree(), before)
        self.assertEqual(processor.env["cimian_result"], "dry-run")
        self.assertIs(processor.env["cimian_repo_changed"], False)

    def test_the_warning_is_shown_at_every_verbosity_and_the_plan_names_the_files(self):
        self.put_exe_template()
        processor, messages = new_processor(IMPORTER, self.env(cimian_dry_run=True))
        processor.main()
        self.assertTrue(all(level == 0 for level, _ in processor.message_levels))
        self.assertTrue(messages[0].startswith("WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on."))
        self.assertIn("Would write Example-App 2.5.0: pkgsinfo/apps/Example-App-2.5.0.yaml and "
                      "pkgs/apps/Example-App-2.5.0.exe (%d bytes)." % os.path.getsize(self.exe), messages[1])
        self.assertEqual(messages[2], "Template: Example-App 2.4.0 (pkgsinfo/apps/Example-App-2.4.0.yaml).")

    def test_the_plan_without_a_template_says_so(self):
        processor, messages = run(self.env(cimian_dry_run=True))
        self.assertIn("No template: the pkginfo is built from the inputs.", messages)

    def test_the_outputs_name_the_planned_files_and_the_summary_has_no_path(self):
        self.put_exe_template()
        processor, messages = run(self.env(cimian_dry_run=True))
        self.assertEqual(processor.env["cimian_version_imported"], "2.5.0")
        self.assertEqual(processor.env["cimian_pkginfo_path"],
                         os.path.join(self.repo, "pkgsinfo", "apps", "Example-App-2.5.0.yaml"))
        self.assertEqual(processor.env["cimian_installer_path"],
                         os.path.join(self.repo, "pkgs", "apps", "Example-App-2.5.0.exe"))
        summary = processor.env["cimian_importer_summary_result"]
        self.assertEqual(summary["report_fields"], ["name", "version", "catalogs", "result"])
        self.assertEqual(summary["data"], {"name": "Example-App", "version": "2.5.0",
                                           "catalogs": "Production", "result": "dry run, nothing written"})
        self.assertNotIn(self.repo, repr(summary))
        self.assertNotIn(self.tmp, repr(summary))

    def test_the_plan_does_not_print_the_text_of_the_pkginfo(self):
        self.put_exe_template(text=EXE_TEMPLATE.replace("name: Example-App", "postinstall_script: do-the-secret-thing\nname: Example-App"))
        processor, messages = run(self.env(cimian_dry_run=True))
        joined = "\n".join(messages)
        for text in ("do-the-secret-thing", "/S", "A made-up program", "Example Vendor"):
            self.assertNotIn(text, joined)

    def test_a_dry_run_refuses_what_a_real_run_refuses(self):
        self.put_exe_template()
        self.put_pkginfo("apps/Example-App-2.5.0.yaml", "not a pkginfo of the item\n")
        for dry in (True, False):
            with self.subTest(dry_run=dry):
                with self.assertRaises(ProcessorError):
                    run(self.env(cimian_dry_run=dry))

    def test_an_msi_dry_run_needs_the_facts_too(self):
        with self.assertRaises(ProcessorError) as caught:
            run(self.env(self.msi, version=None, cimian_dry_run=True, cimian_path=self.empty_bin))
        self.assertIn("msi_product_code", str(caught.exception))

    def test_a_flag_that_is_not_a_boolean_is_an_error(self):
        for value in ("off", "n", "f", "", 2):
            with self.subTest(value=value):
                with self.assertRaises(ProcessorError):
                    run(self.env(cimian_dry_run=value))

    def test_the_text_false_in_any_letter_case_is_a_real_run(self):
        for number, value in enumerate(("false", "FALSE", "no", "0")):
            with self.subTest(value=value):
                processor, _ = run(self.env(self.another_exe(10 + number), cimian_dry_run=value,
                                            version="2.%d.0" % (6 + number)))
                self.assertEqual(processor.env["cimian_result"], "published")


@needs_yaml
class VerifiedDownloadTests(PyYamlCase):
    """The guard has the meaning that PcmanImporter gives it (see the README)."""

    def env(self, installer=None, **overrides):
        # An install check of its own, so that the only warnings are those of the guard.
        values = {"pkginfo": {"check": {"file": {"path": EXE_PATH}}}}
        values.update(overrides)
        return super().env(installer, **values)

    def test_a_verified_download_is_published_without_a_warning(self):
        processor, messages = run(self.env())
        self.assertEqual(lines(messages, "WARNING"), [])
        self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published")
        self.assertIs(processor.env["cimian_repo_changed"], True)

    def test_a_download_that_no_step_verified_is_refused_in_a_real_run(self):
        for flag in (None, False, "true", "True", 1, "yes"):
            with self.subTest(flag=flag):
                before = self.repo_tree()
                with self.assertRaises(ProcessorError) as caught:
                    run(self.env(checksum_verified=flag))
                self.assertIn("The download was not verified: no step of the recipe set checksum_verified "
                              "together with the checksum_sha256 of this file. Nothing was published.",
                              str(caught.exception))
                self.assertEqual(self.repo_tree(), before)

    def test_a_flag_without_a_usable_hash_is_refused(self):
        for value in (None, "", "not a hash", "a" * 63, 5):
            with self.subTest(value=value):
                with self.assertRaises(ProcessorError) as caught:
                    run(self.env(checksum_sha256=value))
                self.assertIn("The download was not verified", str(caught.exception))

    def test_the_hash_is_read_as_the_checksum_step_reads_it(self):
        digest = sha256_hex(self.exe)
        for value in (digest.upper(), "sha256:" + digest, "SHA256:" + digest, "  %s  " % digest):
            with self.subTest(value=value):
                processor, messages = run(self.env(checksum_sha256=value))
                self.assertEqual(lines(messages, "WARNING"), [])
                os.unlink(os.path.join(self.repo, "pkgsinfo", "Example-App-2.5.0.yaml"))
                os.unlink(os.path.join(self.repo, "pkgs", "Example-App-2.5.0.exe"))

    def test_the_override_can_allow_an_unverified_download_with_a_warning(self):
        processor, messages = run(self.env(checksum_verified=None, cimian_allow_unverified=True))
        warnings = lines(messages, "WARNING: published WITHOUT a verified download")
        self.assertEqual(len(warnings), 1)
        self.assertIn("cimian_allow_unverified is true", warnings[0])
        self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published, NOT verified")

    def test_a_dry_run_of_an_unverified_download_warns_and_says_so_in_the_summary(self):
        processor, messages = run(self.env(checksum_verified=None, cimian_dry_run=True))
        self.assertEqual(len(lines(messages, "WARNING: the download was NOT verified")), 1)
        self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"],
                         "dry run, nothing written, NOT verified")

    def test_a_checksum_of_another_file_stops_every_run_and_the_override_does_not_change_that(self):
        other = "c" * 64
        for dry in (True, False):
            for allow in (False, True):
                with self.subTest(dry_run=dry, allow=allow):
                    before = self.repo_tree()
                    with self.assertRaises(ProcessorError) as caught:
                        run(self.env(checksum_sha256=other, cimian_dry_run=dry, cimian_allow_unverified=allow))
                    message = str(caught.exception)
                    self.assertIn("The file to import is not the file whose checksum was verified", message)
                    self.assertIn(cimian.shorten(other), message)
                    self.assertIn(cimian.shorten(sha256_hex(self.exe)), message)
                    self.assertNotIn(sha256_hex(self.exe), message)
                    self.assertEqual(self.repo_tree(), before)

    def test_the_flag_counts_only_with_the_hash_of_this_file(self):
        digest = sha256_hex(self.exe)
        before = self.repo_tree()
        with self.assertRaises(ProcessorError):
            run(self.env(checksum_sha256=digest[::-1]))
        self.assertEqual(self.repo_tree(), before)

    def test_the_allowance_is_parsed_like_the_dry_run_switch(self):
        for value in ("maybe", "", 2):
            with self.subTest(value=value):
                with self.assertRaises(ProcessorError):
                    run(self.env(cimian_allow_unverified=value))
        for number, value in enumerate(("true", "yes", "1", True)):
            with self.subTest(value=value):
                processor, _ = run(self.env(self.another_exe(20 + number), checksum_verified=None,
                                            cimian_allow_unverified=value, version="2.%d.0" % (6 + number)))
                self.assertEqual(processor.env["cimian_result"], "published")

    def test_the_names_are_those_that_the_checksum_step_sets(self):
        self.assertEqual(cimian.VERIFIED_FLAG_VARIABLE, "checksum_verified")
        self.assertEqual(cimian.VERIFIED_HASH_VARIABLE, "checksum_sha256")
        self.assertIn(cimian.VERIFIED_FLAG_VARIABLE, checksum.ChecksumVerifier.output_variables)
        self.assertIn(cimian.VERIFIED_HASH_VARIABLE, checksum.ChecksumVerifier.output_variables)

    def test_the_chain_with_the_real_checksum_step(self):
        verifier, _ = run_processor(checksum.ChecksumVerifier, {"pathname": self.exe, "expected_sha256": sha256_hex(self.exe)})
        env = self.env(checksum_verified=None, checksum_sha256=None)
        env.update({key: value for key, value in verifier.env.items() if key.startswith("checksum_")})
        processor, messages = run(env)
        self.assertEqual(lines(messages, "WARNING"), [])
        # and the same chain for another file is refused
        other = os.path.join(self.downloads, "other.exe")
        with open(other, "wb") as handle:
            handle.write(b"the file that was not verified")
        env["pathname"] = other
        with self.assertRaises(ProcessorError):
            run(env)

    def test_the_hash_rules_are_those_of_the_checksum_step(self):
        digest = sha256_hex(self.exe)
        for value in (digest, digest.upper(), "sha256:" + digest, "SHA256: " + digest, " " + digest, "", "x" * 64,
                      digest + " file.exe", digest[:-1], None, 5):
            with self.subTest(value=value):
                try:
                    expected = checksum.normalize_expected_sha256(value)
                except ValueError:
                    expected = None
                self.assertEqual(cimian.normalize_sha256(value), expected)
        self.assertEqual(cimian.sha256_of_file(self.exe), checksum.sha256_of_file(self.exe))
        self.assertEqual(cimian.HEX_DIGITS, checksum.HEX_DIGITS)
        self.assertEqual(cimian.HASH_PREFIX, checksum.HASH_PREFIX)

    def test_the_file_is_hashed_once_for_the_guard_the_pkginfo_and_the_copy(self):
        calls = []
        real = cimian.sha256_of_file

        def counting(path):
            calls.append(path)
            return real(path)

        with mock.patch.object(cimian, "sha256_of_file", counting):
            run(self.env())
        self.assertEqual(calls, [self.exe])


@needs_yaml
class ArchitectureTests(PyYamlCase):
    """An item can have pkginfo files for several architectures; the client keeps the highest version
    among the files for the PC's architecture (CatalogService.cs:43-56)."""

    def put_two(self, x64_version="1.0", arm_version="1.1", arm_folder="apps"):
        self.assertIn("supported_architectures:\n- x64\n", EXE_TEMPLATE)
        x64 = EXE_TEMPLATE.replace("2.4.0", x64_version).replace("Example App", "The x64 one")
        arm = EXE_TEMPLATE.replace("2.4.0", arm_version).replace("Example App", "The arm64 one") \
            .replace("supported_architectures:\n- x64\n", "supported_architectures:\n- arm64\n") \
            .replace("apps/Example-App-%s.exe" % arm_version, "%s/Example-App-%s.exe" % (arm_folder, arm_version))
        self.put_pkginfo("apps/Example-App-%s.yaml" % x64_version, x64)
        self.put_pkginfo("%s/Example-App-%s.yaml" % (arm_folder, arm_version), arm)

    def test_pkginfo_files_for_several_architectures_need_the_architecture_of_the_installer(self):
        self.put_two()
        before = self.repo_tree()
        for dry in (True, False):
            with self.subTest(dry_run=dry):
                with self.assertRaises(ProcessorError) as caught:
                    run(self.env(version="1.2", cimian_dry_run=dry))
                self.assertIn("for several architectures (arm64; x64)", str(caught.exception))
                self.assertIn("cimian_architecture", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    def test_the_template_is_the_newest_file_for_the_architecture_and_keeps_it(self):
        self.put_two()
        processor, messages = run(self.env(version="1.2", cimian_architecture="x64"))
        new = self.read_pkginfo("apps/Example-App-1.2.yaml")
        self.assertEqual(new["display_name"], "The x64 one")  # not the arm64 file's, although its version is higher
        self.assertEqual(new["supported_architectures"], ["x64"])
        self.assertEqual(self.read_pkginfo("apps/Example-App-1.1.yaml")["supported_architectures"], ["arm64"])

    def test_the_other_architecture_is_a_template_of_its_own(self):
        self.put_two()
        run(self.env(version="1.3", cimian_architecture="arm64"))
        new = self.read_pkginfo("apps/Example-App-1.3.yaml")
        self.assertEqual(new["display_name"], "The arm64 one")
        self.assertEqual(new["supported_architectures"], ["arm64"])

    def test_the_version_of_another_architecture_is_not_nothing_new(self):
        self.put_two(arm_folder="arm")
        processor, messages = run(self.env(version="1.1", cimian_architecture="x64"))
        self.assertEqual(processor.env["cimian_result"], "published")
        self.assertEqual(self.read_pkginfo("apps/Example-App-1.1.yaml")["display_name"], "The x64 one")
        self.assertEqual(self.read_pkginfo("arm/Example-App-1.1.yaml")["display_name"], "The arm64 one")

    def test_the_same_version_for_the_same_architecture_is_nothing_new(self):
        self.put_two(x64_version="1.1", arm_version="1.1", arm_folder="arm")
        processor, messages = run(self.env(version="1.1", cimian_architecture="x64"))
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertIn("apps/Example-App-1.1.yaml", processor.env["cimian_pkginfo_path"])

    def test_a_target_that_holds_another_architectures_pkginfo_is_named_and_never_overwritten(self):
        self.put_two(arm_folder="apps")
        before = self.repo_tree()
        with self.assertRaises(ProcessorError) as caught:
            run(self.env(version="1.1", cimian_architecture="x64"))
        self.assertIn("is the pkginfo of Example-App 1.1 for other architectures (arm64)", str(caught.exception))
        self.assertIn("cimian_subdirectory", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)
        processor, _ = run(self.env(version="1.1", cimian_architecture="x64", cimian_subdirectory="x64"))
        self.assertEqual(processor.env["cimian_result"], "published")

    def test_a_file_for_all_architectures_is_a_template_for_every_one(self):
        self.put_exe_template("1.0", text=EXE_TEMPLATE.replace("supported_architectures:\n- x64\n", ""))
        run(self.env(version="1.1", cimian_architecture="arm64"))
        self.assertEqual(self.read_pkginfo("apps/Example-App-1.1.yaml")["display_name"], "Example App")

    def test_the_names_amd64_and_x86_64_are_x64(self):
        self.put_two()
        for number, spelling in enumerate(("amd64", "X86_64")):
            with self.subTest(spelling=spelling):
                processor, _ = run(self.env(self.another_exe(60 + number), version="1.%d" % (2 + number), cimian_architecture=spelling))
                self.assertEqual(self.read_pkginfo("apps/Example-App-1.%d.yaml" % (2 + number))["display_name"], "The x64 one")

    def test_without_a_file_for_the_architecture_the_pkginfo_is_built_for_it(self):
        self.put_two()
        processor, messages = run(self.env(version="1.2", cimian_architecture="x86", cimian_catalogs=["Testing"]))
        new = self.read_pkginfo("Example-App-1.2.yaml")
        self.assertEqual(new["supported_architectures"], ["x86"])
        self.assertEqual(new["catalogs"], ["Testing"])
        self.assertEqual(len(lines(messages, "NOTE: the repository has pkginfo files of Example-App for other architectures only")), 1)

    def test_a_pkginfo_input_may_give_its_own_architectures_when_there_is_no_template(self):
        run(self.env(version="1.2", cimian_architecture="x64", pkginfo={"supported_architectures": ["x64", "x86"]}))
        self.assertEqual(self.read_pkginfo("Example-App-1.2.yaml")["supported_architectures"], ["x64", "x86"])

    def test_the_architecture_is_a_word(self):
        for value in ("x 64", "x64;", "../x"):
            with self.subTest(value=value):
                with self.assertRaises(ProcessorError):
                    run(self.env(cimian_architecture=value))

    def test_files_that_all_have_the_same_architecture_need_no_input(self):
        self.put_two(x64_version="1.0", arm_version="1.1")
        os.unlink(os.path.join(self.repo, "pkgsinfo", "apps", "Example-App-1.1.yaml"))
        processor, _ = run(self.env(version="1.2"))
        self.assertEqual(processor.env["cimian_result"], "published")
        self.assertEqual(self.read_pkginfo("apps/Example-App-1.2.yaml")["supported_architectures"], ["x64"])


@needs_yaml
class HashWithoutVersionTests(PyYamlCase):
    """Dropping the hash of the old file must not leave a check that cannot work."""

    HASH_ONLY = EXE_TEMPLATE.replace("    version: 2.4.0\n    hash: %s\n" % OLD_FILE_HASH, "    hash: %s\n" % OLD_FILE_HASH)

    def test_a_file_check_with_a_hash_and_no_version_stops_the_run(self):
        self.assertNotIn("    version: 2.4.0", self.HASH_ONLY)
        self.put_exe_template(text=self.HASH_ONLY)
        before = self.repo_tree()
        for dry in (True, False):
            with self.subTest(dry_run=dry):
                with self.assertRaises(ProcessorError) as caught:
                    run(self.env(cimian_dry_run=dry))
                self.assertIn("check.file had a hash and no version", str(caught.exception))
                self.assertIn("would never be updated", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    def test_the_override_can_give_the_version_and_then_the_run_goes_on(self):
        self.put_exe_template(text=self.HASH_ONLY)
        processor, messages = run(self.env(pkginfo={"check": {"file": {"version": "2.5.0"}}}))
        self.assertEqual(self.read_pkginfo("apps/Example-App-2.5.0.yaml")["check"]["file"]["version"], "2.5.0")
        self.assertEqual(lines(messages, "WARNING: the template's check.file"), [])

    def test_an_installs_entry_for_a_file_without_version_data_stops_the_run(self):
        text = EXE_TEMPLATE.replace("check:\n  file:\n    path: %s\n    version: 2.4.0\n    hash: %s\n" % (EXE_PATH, OLD_FILE_HASH),
                                    "installs:\n- type: file\n  path: C:" + BACKSLASH + "Example" + BACKSLASH + "settings.ini\n"
                                    "  md5checksum: %s\n" % OLD_FILE_HASH)
        self.assertIn("settings.ini", text)
        self.put_exe_template(text=text)
        before = self.repo_tree()
        with self.assertRaises(ProcessorError) as caught:
            run(self.env())
        self.assertIn("installs[1] is a file with a hash and no version", str(caught.exception))
        self.assertIn("install again at every run", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    def warning_for(self, name):
        text = EXE_TEMPLATE.replace("check:\n  file:\n    path: %s\n    version: 2.4.0\n    hash: %s\n" % (EXE_PATH, OLD_FILE_HASH),
                                    "installs:\n- type: file\n  path: C:" + BACKSLASH + "Example" + BACKSLASH + name + "\n"
                                    "  md5checksum: %s\n" % OLD_FILE_HASH)
        self.put_exe_template(text=text)
        processor, messages = run(self.env())
        self.assertEqual(len(lines(messages, "WARNING: the template's installs[1] had a hash and no version")), 1)

    def test_an_installs_entry_for_an_exe_is_a_warning(self):
        self.warning_for("example.exe")

    def test_an_installs_entry_for_a_dll_in_capitals_is_a_warning(self):
        self.warning_for("Helper.DLL")

    def test_a_hash_beside_a_version_is_dropped_with_a_note_only(self):
        self.put_exe_template()
        processor, messages = run(self.env())
        self.assertEqual(lines(messages, "WARNING: the template's"), [])


@needs_yaml
class ValuesPassThroughTests(PyYamlCase):
    """Reading and writing a pkginfo must not change the type or the text of a value that the
    importer does not replace. PyYAML reads YAML 1.1: 22:00 is the integer 1320 there, 2025.10 the
    float 2025.1, yes a boolean; Cimian's own reader takes them as text."""

    ODD = [
        ("start", "22:00"), ("end", "06:00"), ("text_yes", "yes"), ("text_No", "No"), ("text_on", "on"), ("text_off", "off"),
        ("minimum_cimian_version", "2025.10"), ("zero_lead", "007"), ("hex", "0x1F"), ("underscore", "1_000"),
        ("plus", "+5"), ("exp", "1e5"), ("dot", ".5"), ("date", "2026-01-01"), ("mixed", "tRUE"), ("word_nul", "nUll"),
        ("percent", "50%"), ("colon", "a: b"), ("hash_sign", "a #b"), ("star", "*star"), ("amp", "&amp"),
    ]

    def odd_template(self):
        keys = "".join("%s: %s\n" % (key, value if key not in ("colon", "hash_sign", "star", "amp") else repr(value)) for key, value in self.ODD)
        text = EXE_TEMPLATE.replace("\nname: Example-App\n", "\ninstall_window:\n  start: 22:00\n  end: 06:00\n  weekdays:\n  - Mon\n  - Tue\n"
                                    "restart_action: yes\ninstaller_timeout: 900\nprecache: true\nrecurring: false\n"
                                    "uninstallable: ~\nmetadata:\n  note: no\n" + keys + "name: Example-App\n")
        return text

    def test_the_type_and_the_text_of_every_other_value_survive_a_publish(self):
        template_path = self.put_exe_template(text=self.odd_template())
        before = self.read_pkginfo("apps/Example-App-2.4.0.yaml")
        self.assertEqual(before["install_window"]["start"], "22:00")  # the loader: text, not 1320
        processor, messages = run(self.env())
        after = self.read_pkginfo("apps/Example-App-2.5.0.yaml")
        for key, value in self.ODD:
            self.assertEqual(after[key], value, key)
            self.assertIs(type(after[key]), str, key)
        self.assertEqual(after["install_window"], {"start": "22:00", "end": "06:00", "weekdays": ["Mon", "Tue"]})
        self.assertEqual(after["restart_action"], "yes")
        self.assertEqual(after["installer_timeout"], 900)
        self.assertIs(type(after["installer_timeout"]), int)
        self.assertIs(after["precache"], True)
        self.assertIs(after["recurring"], False)
        self.assertIsNone(after["uninstallable"])
        self.assertEqual(after["metadata"], {"note": "no"})
        written = self.read_text("pkgsinfo", "apps", "Example-App-2.5.0.yaml")
        # a text that PyYAML would read as another type is written quoted, so it comes back as the same text
        for line in ("  start: '22:00'\n", "  end: 06:00\n", "restart_action: 'yes'\n", "minimum_cimian_version: '2025.10'\n",
                     "zero_lead: '007'\n", "installer_timeout: 900\n", "precache: true\n", "recurring: false\n"):
            self.assertIn(line, written)

    def test_a_value_that_is_a_real_integer_or_boolean_keeps_its_type(self):
        loader, dumper = cimian.make_yaml_classes(yaml)
        data = yaml.load("a: 1320\nb: -3\nc: 0\nd: true\ne: false\nf: null\ng: ~\nh:\n", Loader=loader)
        self.assertEqual(data, {"a": 1320, "b": -3, "c": 0, "d": True, "e": False, "f": None, "g": None, "h": None})
        for key in "abcde":
            self.assertIn(type(data[key]), (int, bool))
        self.assertIsNot(data["a"], True)
        self.assertEqual([type(data[key]) for key in "ab"], [int, int])

    def test_every_odd_value_is_a_text_for_the_loader_and_a_text_again_after_a_round_trip(self):
        loader, dumper = cimian.make_yaml_classes(yaml)
        text = "".join("%s: %s\n" % (key, value) for key, value in self.ODD[:17])
        data = yaml.load(text, Loader=loader)
        for key, value in self.ODD[:17]:
            self.assertEqual(data[key], value, key)
        written = IMPORTER.render_pkginfo(yaml, loader, dumper, data)
        self.assertEqual(yaml.load(written, Loader=loader), data)
        # PyYAML's own reading of the written text agrees about the type of each: all text
        for key, value in yaml.load(written, Loader=yaml.SafeLoader).items():
            self.assertIs(type(value), str, key)

    def test_a_version_stays_text_whatever_it_looks_like(self):
        loader, dumper = cimian.make_yaml_classes(yaml)
        for text in ("5", "5.0", "1.10", "007", "22:00", "2025.10"):
            with self.subTest(version=text):
                data = yaml.load("version: %s\n" % text, Loader=loader)
                self.assertEqual(data["version"], text)
                self.assertIs(type(data["version"]), str)

    def test_a_pkginfo_file_is_written_as_it_was_read_when_nothing_changes(self):
        """The real files that the client reads keep their shape: reading and writing them again,
        with no change of value, gives the same text."""
        loader, dumper = cimian.make_yaml_classes(yaml)
        for name, text in (("EXE", EXE_TEMPLATE), ("MSI", MSI_TEMPLATE), ("odd values", self.odd_template())):
            with self.subTest(sample=name):
                data = yaml.load(text, Loader=loader)
                again = IMPORTER.render_pkginfo(yaml, loader, dumper, data)
                self.assertEqual(yaml.load(again, Loader=loader), data)
        data = yaml.load(EXE_TEMPLATE, Loader=loader)
        self.assertEqual(IMPORTER.render_pkginfo(yaml, loader, dumper, data), EXE_TEMPLATE.replace("version: 2.4.0", "version: 2.4.0"))

    @unittest.skipUnless(os.environ.get("CIMIAN_SAMPLES"), "set CIMIAN_SAMPLES to a folder of real pkginfo files")
    def test_real_pkginfo_files_come_back_the_same(self):
        """The real files of a repository, read and written again with no change, must be the same text.
        Run by hand with CIMIAN_SAMPLES=<folder of *.yaml pkginfo files>."""
        loader, dumper = cimian.make_yaml_classes(yaml)
        folder = os.environ["CIMIAN_SAMPLES"]
        names = sorted(name for name in os.listdir(folder) if name.endswith(".yaml"))
        self.assertTrue(names, "no *.yaml file in " + folder)
        for name in names:
            with self.subTest(file=name):
                text = text_of(os.path.join(folder, name))
                data = yaml.load(text, Loader=loader)
                self.assertEqual(IMPORTER.render_pkginfo(yaml, loader, dumper, data), text)


@needs_yaml
class RoundThreeTests(PyYamlCase):
    """The cases of the reader's second check."""

    HASH_ONLY = EXE_TEMPLATE.replace("    version: 2.4.0\n    hash: %s\n" % OLD_FILE_HASH, "    hash: %s\n" % OLD_FILE_HASH)

    # --- R2-M1: AutoPkg leaves `%version%` in an Input as it is, because `version` does not exist yet

    def test_a_variable_that_a_download_step_has_set_since_autopkg_replaced_the_input_is_replaced_by_the_importer(self):
        """The remedy that the hash stop taught: `check: {file: {version: %version%}}` in the override. AutoPkg
        hands the importer the literal text; the importer must write the real version."""
        self.put_exe_template(text=self.HASH_ONLY)
        processor, messages = run(self.env(pkginfo={"check": {"file": {"version": "%version%"}}}))
        new = self.read_pkginfo("apps/Example-App-2.5.0.yaml")
        self.assertEqual(new["check"]["file"]["version"], "2.5.0")
        self.assertNotIn("%", self.read_text("pkgsinfo", "apps", "Example-App-2.5.0.yaml").replace("%s", ""))

    def test_for_an_msi_the_version_variable_is_the_products_own_version(self):
        """The MSI recipes pass an empty `version`; `%version%` is still the MSI's own ProductVersion."""
        env = RepoTestCase.env(self, self.msi, cimian_name="Example-Lib", version="", cimian_path=self.msi_bin,
                               pkginfo={"check": {"registry": {"name": "Example Library", "version": "%version%"}}})
        processor, messages = run(env)
        new = self.read_pkginfo("Example-Lib-2.5.0.yaml")
        self.assertEqual(new["check"]["registry"]["version"], "2.5.0")

    def test_other_variables_of_the_run_are_replaced_too(self):
        processor, messages = run(dict(self.env(pkginfo={"description": "From %download_site% for %cimian_name%."}),
                                       download_site="example.test"))
        self.assertEqual(self.read_pkginfo("Example-App-2.5.0.yaml")["description"], "From example.test for Example-App.")

    def test_a_variable_that_nothing_has_set_is_refused_before_anything_is_written(self):
        before = self.repo_tree()
        for dry in (True, False):
            with self.subTest(dry_run=dry):
                with self.assertRaises(ProcessorError) as caught:
                    run(self.env(cimian_dry_run=dry, pkginfo={"check": {"file": {"version": "%versoin%"}},
                                                              "description": "ok"}))
                self.assertIn("%versoin% in check.file.version", str(caught.exception))
                self.assertIn("Nothing was written", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    def test_a_variable_in_a_list_or_a_nested_value_is_found_too(self):
        for pkginfo in ({"installer": {"args": ["/S", "/D=%unknown_dir%"]}}, {"blocking_applications": ["%unknown_app%"]}):
            with self.subTest(pkginfo=pkginfo):
                with self.assertRaises(ProcessorError):
                    run(self.env(pkginfo=pkginfo))

    def test_a_windows_environment_variable_in_pkginfo_is_meant_as_it_stands(self):
        processor, messages = run(self.env(pkginfo={"installer": {"args": ["/D=%ProgramFiles%" + chr(92) + "Example"]},
                                                    "installs": [{"type": "directory", "path": "%PROGRAMDATA%" + chr(92) + "Example"}]}))
        new = self.read_pkginfo("Example-App-2.5.0.yaml")
        self.assertEqual(new["installer"]["args"], ["/D=%ProgramFiles%" + chr(92) + "Example"])
        self.assertEqual(new["installs"][0]["path"], "%PROGRAMDATA%" + chr(92) + "Example")

    def test_a_version_in_a_check_that_the_client_cannot_read_is_refused(self):
        """An earlier publish may have written the literal text; it is not carried on and on."""
        text = EXE_TEMPLATE.replace("    version: 2.4.0\n", "    version: '%version%'\n")
        self.assertIn("'%version%'", text)
        self.put_exe_template(text=text)
        before = self.repo_tree()
        with self.assertRaises(ProcessorError) as caught:
            run(self.env())
        self.assertIn("check.file.version is '%version%', which the client cannot read as a version", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)
        for value in ("latest", "InternalName", "x1"):
            with self.subTest(value=value):
                with self.assertRaises(ProcessorError):
                    run(self.env(self.another_exe(90), version="3.0.0", pkginfo={"installs": [{"type": "file", "path": "C:" + chr(92) + "x.dll", "version": value}]}))

    def test_an_empty_version_in_a_check_is_no_version(self):
        text = EXE_TEMPLATE.replace("    version: 2.4.0\n", "    version: ''\n")
        self.put_exe_template(text=text)
        processor, messages = run(self.env())
        self.assertEqual(processor.env["cimian_result"], "published")

    def test_the_hash_stops_advice_names_no_variable_and_says_how_to_make_the_real_version(self):
        self.put_exe_template(text=self.HASH_ONLY)
        with self.assertRaises(ProcessorError) as caught:
            run(self.env())
        message = str(caught.exception)
        self.assertNotIn("%version%", message)
        self.assertNotIn("{file: {version", message)
        self.assertIn("add `version:` with the template's own version to that check in the template's pkginfo", message)
        self.assertIn("or a literal version in the override's pkginfo", message)

    def test_the_remedy_of_editing_the_template_gives_the_new_release_its_own_version(self):
        self.put_exe_template(text=self.HASH_ONLY)
        with self.assertRaises(ProcessorError):
            run(self.env())
        # the person adds the template's own version to its check, as the message says
        self.put_exe_template(text=EXE_TEMPLATE)
        processor, messages = run(self.env())
        self.assertEqual(self.read_pkginfo("apps/Example-App-2.5.0.yaml")["check"]["file"]["version"], "2.5.0")
        processor, messages = run(self.env(self.another_exe(91), version="2.6.0"))
        self.assertEqual(self.read_pkginfo("apps/Example-App-2.6.0.yaml")["check"]["file"]["version"], "2.6.0")

    # --- R2-L5: the hash stop only for the check that the client will use

    def test_a_hash_only_file_check_does_not_stop_a_run_when_the_client_never_reads_it(self):
        for number, extra in enumerate(("installcheck_script: test-it\n", "version_script: print-it\n",
                                        "installs:\n- type: directory\n  path: C:" + chr(92) + "Example\n",
                                        "OnDemand: true\n")):
            text = self.HASH_ONLY.replace("\nname: Example-App\n", "\n" + extra + "name: Example-App\n")
            self.assertIn(extra, text)
            with self.subTest(extra=extra.split(":")[0]):
                self.put_exe_template(text=text)
                processor, messages = run(self.env(self.another_exe(100 + number), version="2.%d.0" % (5 + number)))
                self.assertEqual(processor.env["cimian_result"], "published")
                os.unlink(os.path.join(self.repo, "pkgsinfo", "apps", "Example-App-2.4.0.yaml"))

    def test_a_hash_only_file_check_does_not_stop_a_run_when_a_registry_check_comes_first(self):
        text = self.HASH_ONLY.replace("check:\n", "check:\n  registry:\n    name: Example App\n", 1)
        self.put_exe_template(text=text)
        processor, messages = run(self.env())
        self.assertEqual(processor.env["cimian_result"], "published")

    def test_an_installs_entry_without_a_version_does_not_stop_a_run_when_installcheck_script_comes_first(self):
        text = EXE_TEMPLATE.replace("check:\n  file:\n    path: %s\n    version: 2.4.0\n    hash: %s\n" % (EXE_PATH, OLD_FILE_HASH),
                                    "installcheck_script: test-it\ninstalls:\n- type: file\n  path: C:" + chr(92) + "Example" + chr(92)
                                    + "settings.ini\n  md5checksum: %s\n" % OLD_FILE_HASH)
        self.put_exe_template(text=text)
        processor, messages = run(self.env())
        self.assertEqual(processor.env["cimian_result"], "published")

    def test_a_hash_only_file_check_still_stops_a_run_when_it_is_the_check_in_use(self):
        self.put_exe_template(text=self.HASH_ONLY)
        with self.assertRaises(ProcessorError):
            run(self.env())

    # --- R2-L3

    def test_no_upgrade_code_in_the_msi_while_pkginfo_names_one_is_refused(self):
        self.msiinfo_says(stdout=property_export(version="2.5.0", upgrade_code=None))
        with self.assertRaises(ProcessorError) as caught:
            run(RepoTestCase.env(self, self.msi, version=None, pkginfo={"installs": [{"type": "msi", "upgrade_code": OLD_UPGRADE_CODE}]}))
        self.assertIn("but the MSI's is none", str(caught.exception))

    # --- R2-L4

    def test_the_boolean_and_null_spellings_of_the_core_schema_are_typed(self):
        loader, dumper = cimian.make_yaml_classes(yaml)
        data = yaml.load("a: True\nb: TRUE\nc: False\nd: FALSE\ne: Null\nf: NULL\ng: tRUE\nh: yes\ni: nUll\n", Loader=loader)
        self.assertEqual(data, {"a": True, "b": True, "c": False, "d": False, "e": None, "f": None,
                                "g": "tRUE", "h": "yes", "i": "nUll"})
        self.assertIs(data["a"], True)
        self.assertIs(data["c"], False)

    def test_a_capitalised_boolean_of_a_template_stays_a_boolean(self):
        self.put_exe_template(text=EXE_TEMPLATE.replace("unattended_install: true", "unattended_install: True"))
        run(self.env())
        new = self.read_pkginfo("apps/Example-App-2.5.0.yaml")
        self.assertIs(new["unattended_install"], True)

    # --- R2-M2: the template is for all architectures, another file of the item names one

    def put_all_and_arm64(self):
        all_files = EXE_TEMPLATE.replace("supported_architectures:\n- x64\n", "").replace("2.4.0", "1.0").replace("Example App", "For all")
        arm = EXE_TEMPLATE.replace("supported_architectures:\n- x64\n", "supported_architectures:\n- arm64\n") \
            .replace("2.4.0", "1.1").replace("Example App", "For arm64")
        self.put_pkginfo("apps/Example-App-1.0.yaml", all_files)
        self.put_pkginfo("apps/Example-App-1.1.yaml", arm)

    @staticmethod
    def newest_for(files, architecture):
        """What the client keeps for a PC: the highest version among the files for its architecture or for all
        (CatalogService.cs:43-56)."""
        usable = [f for f in files if not f["architectures"] or architecture in f["architectures"]]
        best = None
        for f in usable:
            if best is None or cimian.compare_versions(f["version"], best["version"]) > 0:
                best = f
        return best

    def files(self):
        found = []
        for name in sorted(os.listdir(os.path.join(self.repo, "pkgsinfo", "apps"))):
            data = self.read_pkginfo("apps/" + name)
            found.append({"version": data["version"], "architectures": [a for a in data.get("supported_architectures", [])], "name": name})
        return found

    def test_an_all_template_gets_the_architecture_when_another_file_names_one(self):
        self.put_all_and_arm64()
        processor, messages = run(self.env(version="1.2", cimian_architecture="x64"))
        new = self.read_pkginfo("apps/Example-App-1.2.yaml")
        self.assertEqual(new["display_name"], "For all")  # the template is the file for all architectures
        self.assertEqual(new["supported_architectures"], ["x64"])
        self.assertEqual(len(lines(messages, "NOTE: the template is for all architectures and another pkginfo of the item names one")), 1)
        files = self.files()
        # arm64 PCs keep their arm64 1.1; x64 PCs get 1.2
        self.assertEqual(self.newest_for(files, "arm64")["version"], "1.1")
        self.assertEqual(self.newest_for(files, "x64")["version"], "1.2")

    def test_the_dry_run_says_the_same(self):
        self.put_all_and_arm64()
        processor, messages = run(self.env(version="1.2", cimian_architecture="x64", cimian_dry_run=True))
        self.assertEqual(len(lines(messages, "NOTE: the template is for all architectures and another pkginfo of the item names one")), 1)

    def test_an_all_template_stays_for_all_when_no_other_file_names_an_architecture(self):
        self.put_exe_template("1.0", text=EXE_TEMPLATE.replace("supported_architectures:\n- x64\n", ""))
        processor, messages = run(self.env(version="1.1", cimian_architecture="x64"))
        self.assertNotIn("supported_architectures", self.read_pkginfo("apps/Example-App-1.1.yaml"))
        self.assertEqual(lines(messages, "NOTE: the template is for all architectures"), [])

    def test_a_list_that_pkginfo_gives_is_the_persons_own(self):
        self.put_all_and_arm64()
        run(self.env(version="1.2", cimian_architecture="x64", pkginfo={"supported_architectures": ["x64", "x86"]}))
        self.assertEqual(self.read_pkginfo("apps/Example-App-1.2.yaml")["supported_architectures"], ["x64", "x86"])

    # --- R2-L1: "nothing new" by hash among the files for the architecture

    def test_a_file_that_only_an_other_architectures_pkginfo_holds_is_not_nothing_new_for_this_one(self):
        arm = EXE_TEMPLATE.replace("supported_architectures:\n- x64\n", "supported_architectures:\n- arm64\n").replace(TEMPLATE_HASH, sha256_hex(self.exe))
        self.put_pkginfo("apps/Example-App-2.4.0.yaml", arm)
        processor, messages = run(self.env(version="2.5.0", cimian_architecture="x64"))
        self.assertEqual(processor.env["cimian_result"], "published")
        self.assertEqual(self.read_pkginfo("Example-App-2.5.0.yaml")["supported_architectures"], ["x64"])

    def test_without_the_architecture_a_known_file_is_still_nothing_new(self):
        arm = EXE_TEMPLATE.replace("supported_architectures:\n- x64\n", "supported_architectures:\n- arm64\n").replace(TEMPLATE_HASH, sha256_hex(self.exe))
        self.put_pkginfo("apps/Example-App-2.4.0.yaml", arm)
        processor, messages = run(self.env(version="2.5.0"))
        self.assertEqual(processor.env["cimian_result"], "nothing-new")

    # --- R2-L2: a history that is all and then one architecture is no ambiguity

    def test_files_for_all_and_files_for_one_architecture_need_no_input(self):
        all_files = EXE_TEMPLATE.replace("supported_architectures:\n- x64\n", "").replace("2.4.0", "1.0").replace("Example App", "For all")
        one = EXE_TEMPLATE.replace("2.4.0", "1.1").replace("Example App", "For x64")
        self.put_pkginfo("apps/Example-App-1.0.yaml", all_files)
        self.put_pkginfo("apps/Example-App-1.1.yaml", one)
        processor, messages = run(self.env(version="1.2"))
        new = self.read_pkginfo("apps/Example-App-1.2.yaml")
        self.assertEqual(new["display_name"], "For x64")
        self.assertEqual(new["supported_architectures"], ["x64"])
        self.assertEqual(len(lines(messages, "NOTE: the repository has pkginfo files of Example-App for all architectures and files for x64")), 1)

    def test_two_named_architectures_still_stop_the_run_and_the_message_names_all_when_there_is_one(self):
        self.put_all_and_arm64()
        x64 = EXE_TEMPLATE.replace("2.4.0", "1.05").replace("Example App", "For x64")
        self.put_pkginfo("apps/Example-App-1.05.yaml", x64)
        with self.assertRaises(ProcessorError) as caught:
            run(self.env(version="1.2"))
        self.assertIn("for several architectures (arm64; x64; all)", str(caught.exception))


@needs_yaml
class RepositoryPathTests(PyYamlCase):
    def test_a_subdirectory_that_leaves_the_repository_is_refused(self):
        for value in ("..", "../x", "a/../../x", "a/..", "/etc", "~/x", "C:/x", "a//b", "./a", "a/./b", "a/b/",
                      "a" + BACKSLASH + ".." + BACKSLASH + "x", ".hidden", "-x", "a b.", "a/ ", "tab\tx", "x;y", "x*y"):
            with self.subTest(value=value):
                before = self.repo_tree()
                with self.assertRaises(ProcessorError):
                    run(self.env(cimian_subdirectory=value))
                self.assertEqual(self.repo_tree(), before)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "x")))

    def test_windows_separators_are_read_as_folders(self):
        run(self.env(cimian_subdirectory="apps" + BACKSLASH + "win"))
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "pkgs", "apps", "win", "Example-App-2.5.0.exe")))

    def test_a_link_below_pkgs_that_leads_out_is_refused(self):
        outside = os.path.join(self.tmp, "elsewhere")
        os.makedirs(outside)
        os.symlink(outside, os.path.join(self.repo, "pkgs", "linked"))
        with self.assertRaises(ProcessorError) as caught:
            run(self.env(cimian_subdirectory="linked/deeper"))
        self.assertIn("leaves the repository", str(caught.exception))
        self.assertEqual(os.listdir(outside), [])
        self.assertEqual(os.listdir(os.path.join(self.repo, "pkgsinfo")), [])

    def test_a_link_below_pkgsinfo_that_leads_out_is_refused(self):
        outside = os.path.join(self.tmp, "elsewhere")
        os.makedirs(outside)
        os.symlink(outside, os.path.join(self.repo, "pkgsinfo", "linked"))
        with self.assertRaises(ProcessorError):
            run(self.env(cimian_subdirectory="linked"))
        self.assertEqual(os.listdir(outside), [])
        self.assertEqual(os.listdir(os.path.join(self.repo, "pkgs")), [])

    def test_pkgs_itself_may_be_a_link_to_another_disk(self):
        elsewhere = os.path.join(self.tmp, "big disk")
        os.makedirs(elsewhere)
        os.rmdir(os.path.join(self.repo, "pkgs"))
        os.symlink(elsewhere, os.path.join(self.repo, "pkgs"))
        run(self.env(cimian_subdirectory="apps"))
        self.assertTrue(os.path.isfile(os.path.join(elsewhere, "apps", "Example-App-2.5.0.exe")))

    def test_a_template_whose_installer_leaves_pkgs_is_refused(self):
        for location in ("../../x/Example-App-2.4.0.exe", "/../x/Example-App-2.4.0.exe", "C:/x/Example-App-2.4.0.exe"):
            with self.subTest(location=location):
                self.put_exe_template(text=EXE_TEMPLATE.replace("apps/Example-App-2.4.0.exe", location))
                before = self.repo_tree()
                with self.assertRaises(ProcessorError):
                    run(self.env())
                self.assertEqual(self.repo_tree(), before)

    def test_a_template_made_by_cimians_own_importer_has_a_location_that_begins_with_a_slash(self):
        """cimiimport writes the location with a leading slash; the client and makecatalogs read it
        as relative to pkgs/. The default folder of a new version is still the template's."""
        for number, location in enumerate(("/apps/Example-App-2.4.0.exe", BACKSLASH + "apps" + BACKSLASH + "Example-App-2.4.0.exe", "//apps/Example-App-2.4.0.exe")):
            with self.subTest(location=location):
                self.put_exe_template(text=EXE_TEMPLATE.replace("apps/Example-App-2.4.0.exe", location))
                processor, messages = run(self.env(self.another_exe(50 + number), version="2.%d.0" % (5 + number)))
                self.assertEqual(processor.env["cimian_result"], "published")
                new = self.read_pkginfo("apps/Example-App-2.%d.0.yaml" % (5 + number))
                self.assertEqual(new["installer"]["location"], "apps/Example-App-2.%d.0.exe" % (5 + number))
                self.assertTrue(os.path.isfile(os.path.join(self.repo, "pkgs", "apps", "Example-App-2.%d.0.exe" % (5 + number))))

    def test_a_template_whose_installer_is_an_address_asks_for_a_subdirectory(self):
        self.put_exe_template(text=EXE_TEMPLATE.replace("apps/Example-App-2.4.0.exe", "https://example.test/x.exe"))
        with self.assertRaises(ProcessorError) as caught:
            run(self.env())
        self.assertIn("Give cimian_subdirectory", str(caught.exception))
        processor, messages = run(self.env(cimian_subdirectory="apps"))
        self.assertEqual(processor.env["cimian_result"], "published")

    def test_a_name_or_a_label_that_is_not_plain_is_refused(self):
        for name in ("a/b", "../a", "a b", "-a", ".a", "a" + BACKSLASH + "b", "", "x" * 101, "a;b"):
            with self.subTest(name=name):
                with self.assertRaises(ProcessorError):
                    run(self.env(cimian_name=name))
        for version in ("a/b", "../1", "1 2", "-1", "v1", "1;2", "x" * 101):
            with self.subTest(version=version):
                with self.assertRaises(ProcessorError):
                    run(self.env(version=version))

    def test_an_exe_needs_a_version(self):
        with self.assertRaises(ProcessorError) as caught:
            run(self.env(version=None))
        self.assertIn("An .exe needs a version", str(caught.exception))
        with self.assertRaises(ProcessorError):
            run(self.env(version="   "))

    def test_the_installer_must_be_an_msi_or_an_exe_that_exists(self):
        other = self.make_installer("setup.zip", b"zip")
        for pathname in (other, os.path.join(self.downloads, "missing.exe"), "", self.downloads):
            with self.subTest(pathname=pathname):
                with self.assertRaises(ProcessorError):
                    run(self.env(pathname=pathname))

    def test_the_extension_is_read_in_any_letter_case_and_written_in_lower_case(self):
        upper = self.make_installer("SETUP.EXE", b"MZ" + b"1" * 50)
        run(self.env(upper))
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "pkgs", "Example-App-2.5.0.exe")))

    def test_the_repository_comes_from_the_input_or_from_the_preference(self):
        env = self.env(cimian_repo=None)
        with self.assertRaises(ProcessorError) as caught:
            run(env)
        self.assertIn("CIMIAN_REPO", str(caught.exception))
        env["CIMIAN_REPO"] = self.repo
        processor, _ = run(env)
        self.assertEqual(processor.env["cimian_result"], "published")

    def test_the_input_wins_over_the_preference(self):
        other = os.path.join(self.tmp, "other repo")
        os.makedirs(os.path.join(other, "pkgs"))
        os.makedirs(os.path.join(other, "pkgsinfo"))
        env = self.env()
        env["CIMIAN_REPO"] = other
        run(env)
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "pkgsinfo", "Example-App-2.5.0.yaml")))
        self.assertEqual(os.listdir(os.path.join(other, "pkgsinfo")), [])

    def test_a_repository_that_is_missing_or_not_complete_is_an_error(self):
        with self.assertRaises(ProcessorError) as caught:
            run(self.env(cimian_repo=os.path.join(self.tmp, "not mounted")))
        self.assertIn("Is the share mounted?", str(caught.exception))
        for missing in ("pkgs", "pkgsinfo"):
            with self.subTest(missing=missing):
                os.rename(os.path.join(self.repo, missing), os.path.join(self.repo, "x-" + missing))
                try:
                    with self.assertRaises(ProcessorError) as caught:
                        run(self.env())
                    self.assertIn("no %s/ folder" % missing, str(caught.exception))
                finally:
                    os.rename(os.path.join(self.repo, "x-" + missing), os.path.join(self.repo, missing))

    def test_a_leading_tilde_of_the_repository_is_expanded(self):
        with mock.patch.dict(os.environ, {"HOME": self.tmp}):
            processor, _ = run(self.env(cimian_repo="~/cimian repo"))
        self.assertEqual(processor.env["cimian_result"], "published")


@needs_yaml
class ExistingFileTests(PyYamlCase):
    def test_a_pkginfo_at_the_target_that_is_not_one_of_the_item_is_never_overwritten(self):
        self.put_exe_template()
        target = self.put_pkginfo("apps/Example-App-2.5.0.yaml", "not a pkginfo of the item\n")
        before = self.repo_tree()
        with self.assertRaises(ProcessorError) as caught:
            run(self.env())
        self.assertIn("is never overwritten", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)
        self.assertEqual(text_of(target), "not a pkginfo of the item\n")

    def test_an_installer_at_the_target_with_other_content_is_never_overwritten(self):
        self.put_exe_template()
        os.makedirs(os.path.join(self.repo, "pkgs", "apps"))
        target = os.path.join(self.repo, "pkgs", "apps", "Example-App-2.5.0.exe")
        with open(target, "wb") as handle:
            handle.write(b"another version of the file")
        before = self.repo_tree()
        with self.assertRaises(ProcessorError) as caught:
            run(self.env())
        self.assertIn("pkgs/apps/Example-App-2.5.0.exe exists with other content and is never overwritten",
                      str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    def test_an_installer_that_an_earlier_run_left_is_kept_and_the_pkginfo_is_written(self):
        self.put_exe_template()
        os.makedirs(os.path.join(self.repo, "pkgs", "apps"))
        target = os.path.join(self.repo, "pkgs", "apps", "Example-App-2.5.0.exe")
        with open(self.exe, "rb") as source, open(target, "wb") as handle:
            handle.write(source.read())
        processor, messages = run(self.env())
        self.assertEqual(processor.env["cimian_result"], "published")
        self.assertTrue(any("was in the repository already with the same SHA-256" in m for m in messages))
        self.assertEqual(self.read_pkginfo("apps/Example-App-2.5.0.yaml")["version"], "2.5.0")

    def test_a_link_at_the_installer_target_is_never_followed(self):
        self.put_exe_template()
        os.makedirs(os.path.join(self.repo, "pkgs", "apps"))
        target = os.path.join(self.repo, "pkgs", "apps", "Example-App-2.5.0.exe")
        os.symlink(self.exe, target)
        with self.assertRaises(ProcessorError):
            run(self.env())
        self.assertTrue(os.path.islink(target))

    def test_move_into_place_never_replaces_a_file(self):
        folder = os.path.join(self.tmp, "move")
        os.makedirs(folder)
        temp = os.path.join(folder, "new.tmp")
        target = os.path.join(folder, "target.yaml")
        for path, text in ((temp, "new"), (target, "old")):
            with open(path, "w") as handle:
                handle.write(text)
        with self.assertRaises(ProcessorError):
            IMPORTER.move_into_place(temp, target)
        self.assertEqual(text_of(target), "old")

    def test_move_into_place_without_links_checks_and_renames(self):
        folder = os.path.join(self.tmp, "move")
        os.makedirs(folder)
        temp = os.path.join(folder, "new.tmp")
        target = os.path.join(folder, "target.yaml")
        with open(temp, "w") as handle:
            handle.write("new")
        with mock.patch.object(os, "link", side_effect=OSError("no links here")):
            IMPORTER.move_into_place(temp, target)
        self.assertEqual(text_of(target), "new")
        self.assertFalse(os.path.exists(temp))
        with open(temp, "w") as handle:
            handle.write("newer")
        with mock.patch.object(os, "link", side_effect=OSError("no links here")):
            with self.assertRaises(ProcessorError):
                IMPORTER.move_into_place(temp, target)
        self.assertEqual(text_of(target), "new")

    def test_a_failed_move_leaves_no_temporary_file(self):
        self.put_exe_template()
        before = self.repo_tree()
        with mock.patch.object(IMPORTER, "move_into_place", side_effect=ProcessorError("stopped")):
            with self.assertRaises(ProcessorError):
                run(self.env())
        self.assertEqual(files_of(self.repo_tree()), files_of(before))

    def test_a_failed_pkginfo_write_leaves_the_installer_and_no_temporary_file(self):
        self.put_exe_template()
        calls = []
        real = IMPORTER.move_into_place

        def second_fails(temp, target):
            calls.append(target)
            if len(calls) == 2:
                raise ProcessorError("stopped")
            return real(temp, target)

        with mock.patch.object(IMPORTER, "move_into_place", side_effect=second_fails):
            with self.assertRaises(ProcessorError):
                run(self.env())
        names = sorted(os.listdir(os.path.join(self.repo, "pkgs", "apps")))
        self.assertEqual(names, ["Example-App-2.5.0.exe"])
        self.assertEqual(sorted(os.listdir(os.path.join(self.repo, "pkgsinfo", "apps"))), ["Example-App-2.4.0.yaml"])
        # the next run finishes the publish
        processor, messages = run(self.env())
        self.assertEqual(processor.env["cimian_result"], "published")

    def test_the_installer_is_written_before_the_pkginfo(self):
        self.put_exe_template()
        order = []
        real = IMPORTER.move_into_place

        def record(temp, target):
            order.append(os.path.basename(target))
            return real(temp, target)

        with mock.patch.object(IMPORTER, "move_into_place", side_effect=record):
            run(self.env())
        self.assertEqual(order, ["Example-App-2.5.0.exe", "Example-App-2.5.0.yaml"])

    def test_a_copy_that_does_not_have_the_verified_hash_is_not_published(self):
        self.put_exe_template()
        before = self.repo_tree()
        target = os.path.join(self.repo, "pkgs", "apps", "x.exe")
        with self.assertRaises(ProcessorError) as caught:
            IMPORTER().copy_installer(self.exe, target, "0" * 64)
        self.assertIn("The installer changed while it was copied", str(caught.exception))
        self.assertFalse(os.path.exists(target))
        self.assertEqual(os.listdir(os.path.join(self.repo, "pkgs", "apps")), [])
        self.assertEqual(files_of(self.repo_tree()), files_of(before))

    def test_the_pkginfo_file_has_a_readable_mode_and_ends_in_a_newline(self):
        self.put_exe_template()
        run(self.env())
        path = os.path.join(self.repo, "pkgsinfo", "apps", "Example-App-2.5.0.yaml")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o644)
        self.assertTrue(text_of(path).endswith("\n"))
        self.assertEqual(sorted(os.listdir(os.path.join(self.repo, "pkgsinfo", "apps"))),
                         ["Example-App-2.4.0.yaml", "Example-App-2.5.0.yaml"])


@needs_yaml
class MsiFactsTests(RepoTestCase):
    def env(self, **overrides):
        values = {"version": None, "cimian_path": self.msi_bin}
        values.update(overrides)
        return super().env(self.msi, **values)

    def test_msiinfo_is_asked_for_the_property_table_as_a_list_without_a_shell(self):
        run(self.env())
        self.assertEqual(self.msiinfo_calls(), [["export", self.msi, "Property"]])

    def test_without_msiinfo_the_missing_facts_are_named_in_a_dry_run_and_a_real_run(self):
        for dry in (True, False):
            with self.subTest(dry_run=dry):
                with self.assertRaises(ProcessorError) as caught:
                    run(self.env(cimian_path=self.empty_bin, cimian_dry_run=dry))
                message = str(caught.exception)
                self.assertIn("msiinfo is not on the PATH", message)
                self.assertIn("version (the MSI's ProductVersion), msi_product_code, msi_upgrade_code", message)
        self.assertEqual(os.listdir(os.path.join(self.repo, "pkgs")), [])

    def test_the_missing_facts_error_says_that_a_steps_own_version_wins_over_an_override(self):
        with self.assertRaises(ProcessorError) as caught:
            run(self.env(cimian_path=self.empty_bin))
        self.assertIn("an argument of the recipe's step wins over an override's Input", str(caught.exception))
        self.assertIn("Install msitools", str(caught.exception))

    def test_the_facts_that_were_given_are_not_named_as_missing(self):
        with self.assertRaises(ProcessorError) as caught:
            run(self.env(cimian_path=self.empty_bin, version="2.5.0", msi_product_code=PRODUCT_CODE))
        self.assertIn("must be given: msi_upgrade_code.", str(caught.exception))

    def test_without_msiinfo_the_facts_of_the_inputs_are_used_and_the_run_says_so(self):
        processor, messages = run(self.env(cimian_path=self.empty_bin, version="2.5.0",
                                           msi_product_code=PRODUCT_CODE, msi_upgrade_code=UPGRADE_CODE))
        self.assertEqual(len(lines(messages, "NOTE: msiinfo was not found")), 1)
        entry = self.read_pkginfo("Example-App-2.5.0.yaml")["installs"][0]
        self.assertEqual((entry["product_code"], entry["upgrade_code"], entry["version"]),
                         (PRODUCT_CODE, UPGRADE_CODE, "2.5.0"))

    def test_a_code_that_is_not_a_guid_is_refused(self):
        for key in ("msi_product_code", "msi_upgrade_code"):
            for value in ("5A1B2C3D-0000-4000-8000-00000000A001", "{not a guid}", "{1234}", "x"):
                with self.subTest(key=key, value=value):
                    with self.assertRaises(ProcessorError):
                        run(self.env(**{key: value}))

    def test_an_input_that_msiinfo_contradicts_is_refused(self):
        before = self.repo_tree()
        for key in ("msi_product_code", "msi_upgrade_code"):
            with self.subTest(key=key):
                with self.assertRaises(ProcessorError) as caught:
                    run(self.env(**{key: "{99999999-9999-9999-9999-999999999999}"}))
                self.assertIn("the MSI says", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    def test_an_input_that_msiinfo_confirms_is_accepted_in_any_letter_case(self):
        processor, _ = run(self.env(msi_product_code=PRODUCT_CODE.lower(), msi_upgrade_code=UPGRADE_CODE))
        self.assertEqual(processor.env["cimian_result"], "published")

    def test_msiinfo_that_fails_is_an_error_with_its_last_line(self):
        self.msiinfo_says(exit=1, stdout="", stderr="first\nCould not open the database\n")
        with self.assertRaises(ProcessorError) as caught:
            run(self.env())
        self.assertIn("msiinfo could not read Example App-2.5.0.msi (exit code 1): Could not open the database",
                      str(caught.exception))

    def test_msiinfo_output_without_a_version_or_a_code_is_an_error(self):
        for text, needle in ((property_export(version=None), "ProductVersion"),
                             (property_export(product_code=None), "ProductCode"),
                             ("", "ProductVersion")):
            with self.subTest(needle=needle):
                self.msiinfo_says(stdout=text)
                with self.assertRaises(ProcessorError) as caught:
                    run(self.env())
                self.assertIn(needle, str(caught.exception))

    def test_msiinfo_output_with_a_bad_value_is_an_error(self):
        for text in (property_export(product_code="not a guid"), property_export(upgrade_code="{x}"),
                     property_export(version="v2")):
            with self.subTest(text=text):
                self.msiinfo_says(stdout=text)
                with self.assertRaises(ProcessorError) as caught:
                    run(self.env())
                self.assertIn("is not valid", str(caught.exception))

    def test_msiinfo_that_does_not_finish_is_stopped(self):
        import subprocess
        with mock.patch.object(cimian.subprocess, "run", side_effect=subprocess.TimeoutExpired("msiinfo", 60)):
            with self.assertRaises(ProcessorError) as caught:
                run(self.env())
        self.assertIn("did not finish in 60 seconds", str(caught.exception))

    def test_msiinfo_gets_a_small_environment_and_no_input(self):
        seen = {}
        real = cimian.subprocess.run

        def spy(command, **kwargs):
            seen.update(kwargs)
            seen["command"] = command
            return real(command, **kwargs)

        with mock.patch.dict(os.environ, {"PLANTED_VARIABLE": "that-must-not-travel"}):
            with mock.patch.object(cimian.subprocess, "run", spy):
                try:
                    run(self.env(cimian_dry_run=True))
                except ProcessorError:
                    pass
        self.assertEqual(sorted(seen["env"]), ["HOME", "PATH"])
        self.assertEqual(seen["env"]["PATH"], self.msi_bin)
        self.assertEqual(seen["stdin"], cimian.subprocess.DEVNULL)
        self.assertEqual(seen["timeout"], 60)
        self.assertIsInstance(seen["command"], list)
        self.assertNotIn("shell", seen)


class PropertyExportTests(unittest.TestCase):
    def test_the_property_export_is_read_tolerantly(self):
        text = ("Property\tValue\ns72\tl0\nProperty\tProperty\nProductCode\t{ABC}\nnoise\nProductVersion\t1.0\textra\n"
                "UpgradeCode\t {DEF} \nManufacturer\tExample\n\n")
        self.assertEqual(cimian.parse_property_export(text), {"ProductCode": "{ABC}", "UpgradeCode": "{DEF}"})
        self.assertEqual(cimian.parse_property_export("ProductVersion\t1.0\r\nProductVersion\t1.0\r\n"),
                         {"ProductVersion": "1.0"})
        with self.assertRaises(ProcessorError):
            cimian.parse_property_export("ProductVersion\t1.0\nProductVersion\t1.1\n")


class VersionTests(unittest.TestCase):
    """The order of versions is the client's (CatalogService.cs, CompareVersions)."""

    def test_the_order_is_by_number_and_not_by_text(self):
        self.assertEqual(cimian.compare_versions("1.9", "1.10"), -1)
        self.assertEqual(cimian.compare_versions("1.10", "1.9"), 1)
        self.assertEqual(cimian.compare_versions("2.0.1", "2.0"), 1)

    def test_trailing_zeros_make_no_difference(self):
        self.assertEqual(cimian.compare_versions("2.0", "2.0.0"), 0)
        self.assertTrue(cimian.same_version("2.0", "2.0.0"))
        self.assertTrue(cimian.same_version("26.03", "26.3"))
        self.assertFalse(cimian.same_version("2.0", "2.0.1"))

    def test_tags_sort_before_the_release(self):
        order = ["1.0.alpha1", "1.0.beta2", "1.0.rc1", "1.0"]
        for lower, higher in zip(order, order[1:]):
            self.assertEqual(cimian.compare_versions(lower, higher), -1, (lower, higher))

    def test_metadata_after_a_parenthesis_and_commas_are_read_as_the_client_reads_them(self):
        self.assertEqual(cimian.version_parts("5.2.3 (git 68d178c)"), ["5", "2", "3"])
        self.assertEqual(cimian.version_parts("2025, 0, 408, 54890"), ["2025", "0", "408", "54890"])
        self.assertEqual(cimian.version_parts("1.2.3-beta4"), ["1", "2", "3", "beta4"])
        self.assertEqual(cimian.version_parts("1.2.build7"), ["1", "2"])

    def test_a_build_timestamp_in_the_short_form_is_expanded(self):
        self.assertEqual(cimian.version_parts("26.8.1712"), ["2026", "08", "17", "1200"])
        self.assertEqual(cimian.compare_versions("26.8.1712", "2026.08.17.1200"), 0)
        self.assertEqual(cimian.compare_versions("2026.04.28.1212", "26.8.1712"), -1)
        self.assertEqual(cimian.version_parts("10.8.1712"), ["10", "8", "1712"])  # the year is too small
        self.assertEqual(cimian.version_parts("26.13.1712"), ["26", "13", "1712"])  # not a month
        self.assertEqual(cimian.version_parts("26.8.1799"), ["26", "8", "1799"])  # not an hour

    def test_a_text_that_is_not_a_version_has_no_parts(self):
        for text in ("", "   ", "latest", "x1.2", None, 5, "(1.2)"):
            with self.subTest(text=text):
                self.assertIsNone(cimian.version_parts(text))

    def test_a_number_that_does_not_fit_the_clients_integer_ends_the_version(self):
        self.assertEqual(cimian.version_parts("1.99999999999.3"), ["1"])

    def test_two_versions_that_cannot_be_read_are_equal_to_each_other_only_as_text(self):
        self.assertEqual(cimian.compare_versions("latest", "other"), 0)  # as the client
        self.assertTrue(cimian.same_version("latest", "latest"))
        self.assertFalse(cimian.same_version("latest", "other"))
        self.assertFalse(cimian.same_version("latest", "1.0"))


class DeclarationTests(unittest.TestCase):
    def test_every_input_has_a_description_and_the_flags_that_autopkg_reads(self):
        for name, flags in IMPORTER.input_variables.items():
            with self.subTest(input=name):
                self.assertTrue(flags["description"])
                self.assertIn("required", flags)
                self.assertTrue(set(flags) <= {"required", "description", "default"})

    def test_the_required_inputs_are_the_installer_and_the_name(self):
        required = sorted(name for name, flags in IMPORTER.input_variables.items() if flags["required"])
        self.assertEqual(required, ["cimian_name", "pathname"])

    def test_the_defaults_are_the_safe_ones(self):
        variables = IMPORTER.input_variables
        self.assertIs(variables["cimian_dry_run"]["default"], True)
        self.assertIs(variables["cimian_allow_unverified"]["default"], False)
        self.assertEqual(variables["cimian_catalogs"]["default"], ["Development"])
        self.assertIn("/opt/homebrew/bin", variables["cimian_path"]["default"])

    def test_the_repository_is_never_a_required_input(self):
        self.assertFalse(IMPORTER.input_variables["cimian_repo"]["required"])
        self.assertEqual(cimian.REPO_PREFERENCE, "CIMIAN_REPO")

    def test_every_output_is_described_and_named_for_the_processor(self):
        self.assertEqual(sorted(IMPORTER.output_variables), [
            "cimian_importer_summary_result", "cimian_installer_path", "cimian_pkginfo_path",
            "cimian_repo_changed", "cimian_result", "cimian_version_imported"])
        for name, flags in IMPORTER.output_variables.items():
            self.assertTrue(flags["description"], name)

    def test_the_processor_has_no_input_for_a_forced_overwrite(self):
        for name in IMPORTER.input_variables:
            for word in ("force", "overwrite", "replace"):
                self.assertNotIn(word, name)

    def test_the_description_is_the_docstring(self):
        self.assertIs(IMPORTER.description, cimian.__doc__)

    def test_the_module_needs_no_other_module_of_the_repository_and_imports_yaml_late(self):
        with open(cimian.__file__, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertEqual(source.count("import yaml"), 1)
        main = source.index("def load_yaml")
        self.assertGreater(source.index("import yaml"), main)
        for other in ("ChecksumVerifier", "GitHubAssetDigest", "WindowsExeVersion", "PcmanImporter"):
            self.assertNotIn("import " + other, source)
            self.assertNotIn("from " + other, source)

    def test_it_knows_nothing_of_the_package_tool(self):
        with open(cimian.__file__, "r", encoding="utf-8") as handle:
            source = handle.read().lower()
        self.assertNotIn("pcman", source)


class YamlLibraryTests(RepoTestCase):
    def test_a_missing_pyyaml_stops_the_run_with_a_clear_error_and_writes_nothing(self):
        before = self.repo_tree()
        with mock.patch.dict(sys.modules, {"yaml": None}):
            with self.assertRaises(ProcessorError) as caught:
                run(self.env())
        self.assertIn("PyYAML is not available", str(caught.exception))
        self.assertIn("AutoPkg's own Python has it", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    def test_the_checks_that_need_no_pyyaml_come_first(self):
        with mock.patch.dict(sys.modules, {"yaml": None}):
            with self.assertRaises(ProcessorError) as caught:
                run(self.env(cimian_name="not a name"))
        self.assertIn("cimian_name must be an item name", str(caught.exception))
        with mock.patch.dict(sys.modules, {"yaml": None}):
            with self.assertRaises(ProcessorError) as caught:
                run(self.env(checksum_verified=None))
        self.assertIn("The download was not verified", str(caught.exception))


@needs_yaml
class YamlWrittenTests(PyYamlCase):
    def test_the_pkginfo_reads_back_as_what_was_meant_in_block_style(self):
        self.put_exe_template()
        run(self.env())
        text = self.read_text("pkgsinfo", "apps", "Example-App-2.5.0.yaml")
        self.assertIn("catalogs:\n- Production\n", text)
        self.assertIn("installer:\n  location: apps/Example-App-2.5.0.exe\n  hash: %s\n" % sha256_hex(self.exe), text)
        self.assertIn("  args:\n  - /S\n", text)
        self.assertNotIn("{", text)  # no flow style
        self.assertNotIn("&id", text)  # no anchors
        self.assertNotIn("\t", text)
        self.assertTrue(text.startswith("display_name: Example App\nversion: 2.5.0\n"))
        self.assertTrue(text.endswith("name: Example-App\n"))
        self.assertEqual(self.read_pkginfo("apps/Example-App-2.5.0.yaml")["version"], "2.5.0")

    def test_a_version_that_looks_like_a_number_stays_text_on_the_way_through(self):
        self.put_exe_template("1.10", text=EXE_TEMPLATE.replace("2.4.0", "1.10"))
        run(self.env(version="1.20"))
        text = self.read_text("pkgsinfo", "apps", "Example-App-1.20.yaml")
        self.assertIn("version: '1.20'\n", text)
        self.assertIn("    version: '1.20'\n", text)
        self.assertEqual(self.read_pkginfo("apps/Example-App-1.20.yaml")["version"], "1.20")

    def test_a_template_version_that_pyyaml_would_read_as_a_number_is_read_as_text(self):
        self.put_exe_template("1.10", text=EXE_TEMPLATE.replace("version: 2.4.0\n", "version: 1.10\n", 1))
        processor, messages = run(self.env(cimian_dry_run=True, version="1.11"))
        self.assertIn("Template: Example-App 1.10 (", " ".join(messages))

    def test_a_date_and_a_number_pass_through_as_they_are(self):
        self.put_exe_template(text=EXE_TEMPLATE.replace("name: Example-App",
                                                        "installer_timeout: 900\nrestart_action: RequireRestart\nname: Example-App"))
        run(self.env())
        new = self.read_pkginfo("apps/Example-App-2.5.0.yaml")
        self.assertEqual(new["installer_timeout"], 900)
        self.assertEqual(new["restart_action"], "RequireRestart")

    def test_a_pkginfo_that_would_not_read_back_is_not_written(self):
        self.put_exe_template()
        real = cimian.make_yaml_classes

        def broken(yaml_module):
            loader, dumper = real(yaml_module)

            class Wrong(dumper):
                def represent_data(self, data):
                    if data == "2.5.0":
                        return super().represent_data("2.5.1")
                    return super().represent_data(data)

            return loader, Wrong

        before = self.repo_tree()
        with mock.patch.object(cimian, "make_yaml_classes", broken):
            with self.assertRaises(ProcessorError) as caught:
                run(self.env())
        self.assertIn("does not read back as what was meant", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)  # not even the installer was copied

    def test_non_ascii_text_survives(self):
        self.put_exe_template(text=EXE_TEMPLATE.replace("A made-up program for the tests.", "Ein Programm f\u00fcr Tests \u2013 caf\u00e9."))
        run(self.env())
        self.assertEqual(self.read_pkginfo("apps/Example-App-2.5.0.yaml")["description"],
                         "Ein Programm f\u00fcr Tests \u2013 caf\u00e9.")


@needs_yaml
class OutputTests(PyYamlCase):
    def test_a_real_run_sets_the_outputs_and_the_summary(self):
        self.put_exe_template()
        processor, messages = run(self.env())
        env = processor.env
        self.assertEqual(env["cimian_result"], "published")
        self.assertIs(env["cimian_repo_changed"], True)
        self.assertEqual(env["cimian_version_imported"], "2.5.0")
        self.assertTrue(os.path.isfile(env["cimian_pkginfo_path"]))
        self.assertTrue(os.path.isfile(env["cimian_installer_path"]))
        summary = env["cimian_importer_summary_result"]
        self.assertEqual(summary["summary_text"], "The following versions were published into the Cimian repository:")
        self.assertEqual(summary["data"]["result"], "published")
        self.assertEqual(summary["data"]["catalogs"], "Production")
        self.assertNotIn(self.repo, repr(summary))
        self.assertTrue(any(m.startswith("Published Example-App 2.5.0 (pkgsinfo/apps/Example-App-2.5.0.yaml).") for m in messages))
        self.assertTrue(any("makecatalogs" in m for m in messages))

    def test_what_is_printed_has_no_path_of_the_repository_or_of_the_download(self):
        self.put_exe_template()
        for dry in (True, False):
            processor, messages = run(self.env(cimian_dry_run=dry, version="2.%d.0" % (6 if dry else 7)))
            joined = "\n".join(messages)
            self.assertNotIn(self.tmp, joined)

    def test_no_more_than_the_limit_of_lines_is_shown(self):
        processor, messages = new_processor(IMPORTER, self.env())
        processor.say(["the result"], ["line %d" % number for number in range(40)])
        self.assertEqual(len(messages), cimian.MAX_LINES_SHOWN + 2)
        self.assertEqual(messages[0], "the result")
        self.assertEqual(messages[-1], "... and %d more lines." % (40 - cimian.MAX_LINES_SHOWN))
        self.assertTrue(all(len(m) <= cimian.MAX_LINE_CHARS + 3 for m in messages))

    def test_the_result_and_the_unverified_warning_are_never_cut_off(self):
        """Many notes (here: a version that is not the template's in each of six `installs`
        entries) must not push the 'Published' line or the warning for an unverified download
        out of what is shown, in a real run and in a dry run."""
        entries = "".join("- type: file\n  path: C:" + BACKSLASH + "Example" + BACKSLASH + "file%d.dll\n  version: 9.%d\n" % (n, n) for n in range(15))
        self.put_exe_template(text=EXE_TEMPLATE.replace("check:", "installs:\n" + entries + "check:", 1))
        for dry in (True, False):
            with self.subTest(dry_run=dry):
                processor, messages = run(self.env(self.another_exe(40 if dry else 41), version="2.%d.0" % (5 if dry else 6),
                                                   checksum_verified=None, cimian_allow_unverified=True, cimian_dry_run=dry))
                self.assertTrue(any(m.startswith("... and ") and m.endswith("more lines.") for m in messages))
                if dry:
                    self.assertEqual(len(lines(messages, "WARNING: the download was NOT verified")), 1)
                    self.assertTrue(messages[0].startswith("WARNING: DRY RUN"))
                else:
                    self.assertEqual(len(lines(messages, "WARNING: published WITHOUT a verified download")), 1)
                    self.assertTrue(messages[0].startswith("Published Example-App 2.6.0"))


# ---- app packages (.msix, .appx, .msixbundle, .appxbundle) -------------------

from _win_support import package_manifest, tree_of, write_app_package  # noqa: E402

PACKAGE_NAME = "Example.Vendor.App"
NEW_PACKAGE_VERSION = "2026.1028.1836.0"
OLD_PACKAGE_VERSION = "2026.1001.1200.0"

# A made-up app package item, in the shape that the client reads for an app package.
MSIX_TEMPLATE = """name: Example-Store-App
display_name: Example Store App
version: %(old)s
catalogs:
- Production
category: Education
developer: Example Vendor
dependencies:
- Example-Framework
supported_architectures:
- x64
unattended_install: true
installs:
- type: msix
  identity_name: %(identity)s
  version: %(old)s
installer:
  type: msix
  size: 1234
  location: app/Example-Store-App-%(old)s.msixbundle
  hash: %(hash)s
""" % {"old": OLD_PACKAGE_VERSION, "identity": PACKAGE_NAME, "hash": TEMPLATE_HASH}


class PackageIdentityReaderTests(unittest.TestCase):
    """read_package_identity: a zip file, one manifest read into memory, no declarations."""

    def setUp(self):
        self._tmp = cimian.tempfile.TemporaryDirectory(prefix="win-cimian-msix-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def package(self, members, name="package.msix"):
        return write_app_package(os.path.join(self.tmp, name), members)

    def refused(self, path, needle):
        with self.assertRaises(ProcessorError) as caught:
            cimian.read_package_identity(path)
        self.assertIn(needle, str(caught.exception))
        self.assertNotIn("\n", str(caught.exception))
        return str(caught.exception)

    def test_a_single_package_gives_its_name_version_and_architecture(self):
        identity = cimian.read_package_identity(self.package({"AppxManifest.xml": package_manifest()}))
        self.assertEqual((identity.name, identity.version, identity.architecture, identity.bundle),
                         (PACKAGE_NAME, NEW_PACKAGE_VERSION, "x64", False))

    def test_a_bundle_gives_its_own_version_and_no_architecture(self):
        members = {"AppxMetadata/AppxBundleManifest.xml": package_manifest(version="2026.1103.900.0", bundle=True),
                   # a single package's manifest beside it does not count: the bundle's wins
                   "AppxManifest.xml": package_manifest(version="7.1.300.0", architecture="arm64")}
        identity = cimian.read_package_identity(self.package(members, "bundle.msixbundle"))
        self.assertEqual((identity.version, identity.architecture, identity.bundle), ("2026.1103.900.0", "", True))

    def test_member_names_are_found_with_backslashes_and_in_any_letter_case(self):
        identity = cimian.read_package_identity(
            self.package({"appxmetadata" + BACKSLASH + "APPXBUNDLEMANIFEST.XML": package_manifest(bundle=True)}))
        self.assertTrue(identity.bundle)

    def test_neutral_is_read_as_written(self):
        identity = cimian.read_package_identity(self.package({"AppxManifest.xml": package_manifest(architecture="Neutral")}))
        self.assertEqual(identity.architecture, "neutral")

    def test_a_file_that_is_not_a_zip_is_refused(self):
        path = os.path.join(self.tmp, "not.msix")
        with open(path, "wb") as handle:
            handle.write(b"MZ" + bytes(300))
        self.refused(path, "is not an app package that can be read")

    def test_a_zip_without_a_manifest_is_refused(self):
        self.refused(self.package({"readme.txt": "x"}), "holds neither AppxManifest.xml nor AppxMetadata/AppxBundleManifest.xml")

    def test_a_manifest_larger_than_the_limit_is_refused(self):
        path = self.package({"AppxManifest.xml": package_manifest()})
        with mock.patch.object(cimian, "MAX_MANIFEST_BYTES", 100), \
                mock.patch.object(cimian.zipfile.ZipFile, "open", side_effect=AssertionError("opened")) as opened:
            self.refused(path, "is larger than 100 bytes")
        opened.assert_not_called()  # refused by the size the zip records, before anything is read

    def test_a_manifest_that_reads_longer_than_its_recorded_size_is_cut_at_the_limit(self):
        """The size in the zip's directory is not the only guard: what is read stops after the limit."""
        path = self.package({"AppxManifest.xml": package_manifest()})
        with mock.patch.object(cimian, "MAX_MANIFEST_BYTES", 1000), \
                mock.patch.object(cimian.zipfile.ZipFile, "open", lambda archive, info: io.BytesIO(b" " * 5000)):
            self.refused(path, "is larger than 1000 bytes")

    def test_a_document_type_declaration_is_refused(self):
        text = ('<?xml version="1.0"?>\n<!DOCTYPE Package>\n'
                '<Package><Identity Name="%s" Version="%s"/></Package>' % (PACKAGE_NAME, NEW_PACKAGE_VERSION))
        self.refused(self.package({"AppxManifest.xml": text}), "document type or an entity declaration")

    def test_an_entity_declaration_is_refused_by_its_own_handler(self):
        """The document type handler stops such a manifest first; with it taken away, the entity
        handler still does, so that an entity cannot expand into a large text."""
        text = ('<?xml version="1.0"?>\n<!DOCTYPE Package [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;">]>\n'
                '<Package><Identity Name="&b;" Version="%s"/></Package>' % NEW_PACKAGE_VERSION)
        path = self.package({"AppxManifest.xml": text})
        self.refused(path, "document type or an entity declaration")
        real_create = cimian.expat.ParserCreate

        class WithoutDoctypeGuard(object):
            def __init__(self, parser):
                object.__setattr__(self, "parser", parser)

            def __getattr__(self, name):
                return getattr(self.parser, name)

            def __setattr__(self, name, value):
                if name != "StartDoctypeDeclHandler":
                    setattr(self.parser, name, value)

        with mock.patch.object(cimian.expat, "ParserCreate", lambda *a, **k: WithoutDoctypeGuard(real_create(*a, **k))):
            self.refused(path, "document type or an entity declaration")

    def test_a_manifest_that_is_not_xml_is_refused(self):
        self.refused(self.package({"AppxManifest.xml": "<Package><Identity"}), "is not well-formed XML")

    def test_a_manifest_without_an_identity_under_its_root_is_refused(self):
        deeper = ('<Package xmlns="urn:example"><Properties><Identity Name="%s" Version="%s"/></Properties></Package>'
                  % (PACKAGE_NAME, NEW_PACKAGE_VERSION))
        self.refused(self.package({"AppxManifest.xml": deeper}), "has no Identity element")

    def test_an_identity_without_a_name_or_a_version_is_refused(self):
        for kwargs in ({"name": None}, {"version": None}, {"name": "  "}):
            with self.subTest(**kwargs):
                self.refused(self.package({"AppxManifest.xml": package_manifest(**kwargs)}), "has no Name or no Version")

    def test_a_version_that_the_client_cannot_compare_is_refused(self):
        for version in ("1", ".".join("12345"), "v2.0", "2.0-beta"):
            with self.subTest(version=version):
                self.refused(self.package({"AppxManifest.xml": package_manifest(version=version)}),
                             "is not two to four numbers")

    def test_an_identity_name_that_is_not_one_is_refused(self):
        self.refused(self.package({"AppxManifest.xml": package_manifest(name="Bad Name!")}), "is not one")

    def test_the_message_names_the_file_and_not_its_folder(self):
        message = self.refused(self.package({"readme.txt": "x"}, "Example.msix"), "Example.msix")
        self.assertNotIn(self.tmp, message)


class PackageCase(PyYamlCase):
    def make_package(self, file_name="Example.Vendor.App_%s_neutral_~_abc.msixbundle" % NEW_PACKAGE_VERSION,
                     bundle=None, **manifest):
        if bundle is None:
            bundle = file_name.lower().endswith("bundle")
        member = "AppxMetadata/AppxBundleManifest.xml" if bundle else "AppxManifest.xml"
        return write_app_package(os.path.join(self.downloads, file_name),
                                 {member: package_manifest(bundle=bundle, **manifest), "payload.bin": bytes(range(256))})

    def package_env(self, package=None, **overrides):
        values = {"cimian_name": "Example-Store-App", "version": None}
        values.update(overrides)
        return self.env(package or self.make_package(), **values)

    def put_msix_template(self, text=MSIX_TEMPLATE):
        return self.put_pkginfo("app/Example-Store-App-%s.yaml" % OLD_PACKAGE_VERSION, text)

    def new_pkginfo(self, folder="app/"):
        return self.read_pkginfo("%sExample-Store-App-%s.yaml" % (folder, NEW_PACKAGE_VERSION))


@needs_yaml
class PackageWithoutTemplateTests(PackageCase):
    def test_a_bundle_is_published_into_an_empty_repository(self):
        package = self.make_package()
        processor, messages = run(self.package_env(package))
        self.assertEqual(processor.env["cimian_result"], "published")
        self.assertEqual(processor.env["cimian_version_imported"], NEW_PACKAGE_VERSION)
        file_name = "Example-Store-App-%s.msixbundle" % NEW_PACKAGE_VERSION
        new = self.new_pkginfo("")
        self.assertEqual(new, {
            "name": "Example-Store-App",
            "version": NEW_PACKAGE_VERSION,
            "catalogs": ["Development"],
            "installs": [{"type": "msix", "identity_name": PACKAGE_NAME, "version": NEW_PACKAGE_VERSION}],
            "installer": {"type": "msix", "size": os.path.getsize(package), "location": file_name,
                          "hash": sha256_hex(package)},
        })
        self.assertEqual(list(new), ["name", "version", "catalogs", "installs", "installer"])
        self.assertEqual(sha256_hex(os.path.join(self.repo, "pkgs", file_name)), sha256_hex(package))
        # the installs entry is the check: no warning about a missing one, and no architecture is guessed
        self.assertEqual(lines(messages, "WARNING"), [])
        self.assertNotIn("supported_architectures", new)
        self.assertTrue(any(m.startswith("NOTE: read from the bundle: identity name %s, version %s (the bundle's own"
                                         % (PACKAGE_NAME, NEW_PACKAGE_VERSION)) for m in messages))

    def test_a_single_package_names_its_architecture(self):
        package = self.make_package("Example.Vendor.App_%s_x64.msix" % NEW_PACKAGE_VERSION)
        run(self.package_env(package))
        new = self.new_pkginfo("")
        self.assertEqual(new["supported_architectures"], ["x64"])
        self.assertEqual(new["installer"]["location"], "Example-Store-App-%s.msix" % NEW_PACKAGE_VERSION)

    def test_a_neutral_package_names_none(self):
        package = self.make_package("Example.appx", architecture="neutral")
        run(self.package_env(package))
        new = self.new_pkginfo("")
        self.assertNotIn("supported_architectures", new)
        self.assertEqual(new["installer"]["type"], "msix")
        self.assertEqual(new["installer"]["location"], "Example-Store-App-%s.appx" % NEW_PACKAGE_VERSION)

    def test_an_architecture_that_is_not_known_is_said_and_not_used(self):
        package = self.make_package("Example.msix", architecture="x86a64")
        processor, messages = run(self.package_env(package))
        self.assertNotIn("supported_architectures", self.new_pkginfo(""))
        self.assertEqual(len(lines(messages, "NOTE: the package's ProcessorArchitecture x86a64 is not one of")), 1)

    def test_a_bundle_takes_the_architecture_input_as_an_msi_does(self):
        run(self.package_env(self.make_package("Example.appxbundle"), cimian_architecture="x64"))
        self.assertEqual(self.new_pkginfo("")["supported_architectures"], ["x64"])

    def test_the_architecture_input_must_be_the_single_packages(self):
        package = self.make_package("Example.msix", architecture="x64")
        run(self.package_env(package, cimian_architecture="amd64"))  # amd64 is x64
        with self.assertRaises(ProcessorError) as caught:
            run(self.package_env(package, cimian_architecture="x86", cimian_dry_run=True))
        self.assertIn("cimian_architecture is x86, but the package is for x64", str(caught.exception))

    def test_a_version_input_must_be_the_packages_own(self):
        package = self.make_package()
        before = self.repo_tree()
        with self.assertRaises(ProcessorError) as caught:
            run(self.package_env(package, version="26.10.28"))
        self.assertIn("version is 26.10.28, but the package's own version (Identity Version of its manifest) is %s"
                      % NEW_PACKAGE_VERSION, str(caught.exception))
        self.assertEqual(self.repo_tree(), before)
        processor, _ = run(self.package_env(package, version=NEW_PACKAGE_VERSION))
        self.assertEqual(processor.env["cimian_result"], "published")

    def test_every_extension_of_an_app_package_is_taken_in_any_letter_case(self):
        for number, extension in enumerate((".msix", ".APPX", ".MsixBundle", ".appxbundle")):
            with self.subTest(extension=extension):
                package = self.make_package("Example%d%s" % (number, extension), version="2026.%d.1000.0" % (1100 + number))
                processor, _ = run(self.package_env(package))
                self.assertTrue(processor.env["cimian_installer_path"].endswith(extension.lower()))
                self.assertEqual(processor.env["cimian_result"], "published")

    def test_another_extension_is_refused_and_the_message_names_all_six(self):
        other = self.make_installer("Example.zip", b"PK")
        with self.assertRaises(ProcessorError) as caught:
            run(self.env(other))
        self.assertIn("must end in .msi, .exe, .msix, .appx, .msixbundle or .appxbundle: Example.zip", str(caught.exception))

    def test_a_package_that_cannot_be_read_stops_the_run_in_a_dry_run_too(self):
        broken = self.make_installer("Broken.msixbundle", b"not a zip")
        before = self.repo_tree()
        with self.assertRaises(ProcessorError) as caught:
            run(self.package_env(broken, cimian_dry_run=True))
        self.assertIn("is not an app package that can be read", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    def test_installer_keys_that_an_app_package_does_not_take_are_refused(self):
        for key, value in (("args", ["/S"]), ("switches", ["x"]), ("success_codes", [5]),
                           ("product_code", PRODUCT_CODE), ("upgrade_code", UPGRADE_CODE)):
            with self.subTest(key=key):
                before = self.repo_tree()
                with self.assertRaises(ProcessorError) as caught:
                    run(self.package_env(pkginfo={"installer": {key: value}}))
                self.assertIn("The pkginfo has installer.%s" % key, str(caught.exception))
                self.assertEqual(self.repo_tree(), before)

    def test_an_msix_entry_of_another_package_in_pkginfo_is_refused(self):
        entry = {"type": "msix", "identity_name": "Other.Vendor.App", "version": "1.0"}
        with self.assertRaises(ProcessorError) as caught:
            run(self.package_env(pkginfo={"installs": [entry]}))
        self.assertIn("identity name Other.Vendor.App, but the package's is %s" % PACKAGE_NAME, str(caught.exception))

    def test_an_msix_entry_in_pkginfo_gets_the_packages_identity_and_version(self):
        entry = {"type": "msix", "identity_name": PACKAGE_NAME.lower()}
        other = {"type": "file", "path": EXE_PATH, "version": "1.0"}
        run(self.package_env(pkginfo={"installs": [other, entry], "display_name": "Example Store App"}))
        new = self.new_pkginfo("")
        self.assertEqual(new["installs"], [other, {"type": "msix", "identity_name": PACKAGE_NAME,
                                                   "version": NEW_PACKAGE_VERSION}])
        self.assertEqual(new["display_name"], "Example Store App")

    def test_a_dry_run_writes_nothing_and_says_what_it_would_write(self):
        package = self.make_package()
        before = self.repo_tree()
        processor, messages = run(self.package_env(package, cimian_dry_run=True))
        self.assertEqual(self.repo_tree(), before)
        self.assertEqual(processor.env["cimian_result"], "dry-run")
        self.assertIn("Would write Example-Store-App %s: pkgsinfo/Example-Store-App-%s.yaml and "
                      "pkgs/Example-Store-App-%s.msixbundle (%d bytes)."
                      % (NEW_PACKAGE_VERSION, NEW_PACKAGE_VERSION, NEW_PACKAGE_VERSION, os.path.getsize(package)), messages)
        self.assertIn("No template: the pkginfo is built from the inputs.", messages)


@needs_yaml
class PackageTemplateTests(PackageCase):
    def test_a_new_version_copies_the_template_and_replaces_what_belongs_to_the_file(self):
        self.put_msix_template()
        old = self.read_pkginfo("app/Example-Store-App-%s.yaml" % OLD_PACKAGE_VERSION)
        package = self.make_package()
        processor, messages = run(self.package_env(package))
        new = self.new_pkginfo()
        self.assertEqual(list(new), list(old))
        self.assertEqual(new["version"], NEW_PACKAGE_VERSION)
        self.assertEqual(new["installer"], {"type": "msix", "size": os.path.getsize(package),
                                            "location": "app/Example-Store-App-%s.msixbundle" % NEW_PACKAGE_VERSION,
                                            "hash": sha256_hex(package)})
        self.assertEqual(new["installs"], [{"type": "msix", "identity_name": PACKAGE_NAME, "version": NEW_PACKAGE_VERSION}])
        for key in ("display_name", "catalogs", "category", "developer", "dependencies", "supported_architectures",
                    "unattended_install", "name"):
            self.assertEqual(new[key], old[key], key)
        self.assertTrue(os.path.isfile(os.path.join(self.repo, "pkgs", "app",
                                                    "Example-Store-App-%s.msixbundle" % NEW_PACKAGE_VERSION)))
        self.assertEqual(lines(messages, "WARNING"), [])

    def test_a_package_of_another_identity_is_another_product(self):
        self.put_msix_template()
        before = self.repo_tree()
        with self.assertRaises(ProcessorError) as caught:
            run(self.package_env(self.make_package(name="Other.Vendor.App")))
        self.assertIn("has the identity name %s, and the package's is Other.Vendor.App: it is another product"
                      % PACKAGE_NAME, str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    def test_the_identity_name_is_compared_without_regard_to_case_and_takes_the_packages_spelling(self):
        self.put_msix_template(MSIX_TEMPLATE.replace("identity_name: " + PACKAGE_NAME, "identity_name: " + PACKAGE_NAME.upper()))
        processor, messages = run(self.package_env())
        self.assertEqual(self.new_pkginfo()["installs"][0]["identity_name"], PACKAGE_NAME)
        self.assertEqual(len(lines(messages, "NOTE: the msix entry of installs writes the identity name as")), 1)

    def test_a_template_without_an_msix_entry_gets_one_and_says_so(self):
        text = MSIX_TEMPLATE.replace("installs:\n- type: msix\n  identity_name: %s\n  version: %s\n"
                                     % (PACKAGE_NAME, OLD_PACKAGE_VERSION), "")
        self.assertNotIn("installs:", text)
        self.put_msix_template(text)
        processor, messages = run(self.package_env())
        self.assertEqual(self.new_pkginfo()["installs"],
                         [{"type": "msix", "identity_name": PACKAGE_NAME, "version": NEW_PACKAGE_VERSION}])
        self.assertEqual(len(lines(messages, "NOTE: the template has no msix entry in installs: one is added")), 1)

    def test_other_entries_follow_the_carry_rules_and_the_packages_entry_is_found_among_several(self):
        extra = ("- type: msix\n  identity_name: Example.Vendor.Framework\n  version: 9.0.100\n"
                 "- type: file\n  path: %s\n  version: %s\n" % (EXE_PATH, OLD_PACKAGE_VERSION))
        self.put_msix_template(MSIX_TEMPLATE.replace("installer:\n", extra + "installer:\n"))
        processor, messages = run(self.package_env())
        installs = self.new_pkginfo()["installs"]
        self.assertEqual(installs[0], {"type": "msix", "identity_name": PACKAGE_NAME, "version": NEW_PACKAGE_VERSION})
        self.assertEqual(installs[1], {"type": "msix", "identity_name": "Example.Vendor.Framework", "version": "9.0.100"})
        self.assertEqual(installs[2], {"type": "file", "path": EXE_PATH, "version": NEW_PACKAGE_VERSION})
        # the msix entries are not given the carry rules' warning about a version that is not the template's
        self.assertEqual(lines(messages, "WARNING"),
                         ["WARNING: installs[2] is another msix entry, not this package's: it is kept as it is."])

    def test_several_msix_entries_and_none_of_this_package_stop_the_run(self):
        text = MSIX_TEMPLATE.replace("identity_name: " + PACKAGE_NAME, "identity_name: Other.One")
        text = text.replace("installer:\n", "- type: msix\n  identity_name: Other.Two\n  version: 1.0\ninstaller:\n")
        self.put_msix_template(text)
        with self.assertRaises(ProcessorError) as caught:
            run(self.package_env())
        self.assertIn("The template has 2 msix entries in installs, and none of them has the package's identity name",
                      str(caught.exception))

    def test_a_template_of_another_kind_of_installer_is_refused_both_ways(self):
        self.put_exe_template()
        with self.assertRaises(ProcessorError) as caught:
            run(self.env(self.make_package("Example.msixbundle"), version=None))
        self.assertIn("is of the kind exe, and the file is an .msixbundle", str(caught.exception))
        self.put_msix_template(MSIX_TEMPLATE.replace("Example-Store-App", "Example-App"))
        with self.assertRaises(ProcessorError) as caught:
            run(self.env(self.exe, version="2026.1100.1000.0"))
        self.assertIn("is of the kind msix, and the file is an .exe", str(caught.exception))

    def test_a_template_of_the_type_appx_is_the_same_kind_and_is_written_as_msix(self):
        self.put_msix_template(MSIX_TEMPLATE.replace("  type: msix\n  size", "  type: appx\n  size"))
        processor, messages = run(self.package_env())
        self.assertEqual(self.new_pkginfo()["installer"]["type"], "msix")
        self.assertEqual(len(lines(messages, "NOTE: the template's installer.type is appx")), 1)

    def test_a_template_with_installer_arguments_is_refused(self):
        self.put_msix_template(MSIX_TEMPLATE + "  args:\n  - /quiet\n")
        before = self.repo_tree()
        with self.assertRaises(ProcessorError) as caught:
            run(self.package_env())
        self.assertIn("The pkginfo has installer.args (from the template or the input pkginfo)", str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    def test_a_template_keeps_its_architectures_whatever_the_package_names(self):
        """The rule for a template and an architecture is the one an MSI has: a single x64 package and a template
        for x64 (or for all) give a copy of the template's list."""
        self.put_msix_template()
        run(self.package_env(self.make_package("Example.msix", architecture="x64")))
        self.assertEqual(self.new_pkginfo()["supported_architectures"], ["x64"])

    def test_a_template_for_another_architecture_is_not_the_template(self):
        self.put_msix_template(MSIX_TEMPLATE.replace("- x64", "- arm64"))
        processor, messages = run(self.package_env(self.make_package("Example.msix", architecture="x64")))
        self.assertTrue(any("for other architectures only: there is no template for x64" in m for m in messages))
        self.assertEqual(self.new_pkginfo("")["supported_architectures"], ["x64"])

    def test_a_dry_run_over_a_template_writes_nothing_and_prints_the_same_notes(self):
        self.put_msix_template(MSIX_TEMPLATE.replace("installs:\n- type: msix\n  identity_name: %s\n  version: %s\n"
                                                     % (PACKAGE_NAME, OLD_PACKAGE_VERSION), ""))
        before = self.repo_tree()
        processor, messages = run(self.package_env(cimian_dry_run=True))
        self.assertEqual(self.repo_tree(), before)
        self.assertIn("Template: Example-Store-App %s (pkgsinfo/app/Example-Store-App-%s.yaml)."
                      % (OLD_PACKAGE_VERSION, OLD_PACKAGE_VERSION), messages)
        self.assertEqual(len(lines(messages, "NOTE: the template has no msix entry in installs")), 1)


@needs_yaml
class PackageNothingNewTests(PackageCase):
    def test_the_same_identity_version_is_nothing_new(self):
        self.put_msix_template(MSIX_TEMPLATE.replace(OLD_PACKAGE_VERSION, NEW_PACKAGE_VERSION))
        before = self.repo_tree()
        processor, messages = run(self.package_env())
        self.assertEqual(self.repo_tree(), before)
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertIn("Nothing new: Example-Store-App %s is in the repository already (it has this version). "
                      "Nothing was written." % NEW_PACKAGE_VERSION, messages)
        self.assertTrue(any("has another installer file" in m for m in messages))

    def test_the_same_package_file_is_nothing_new_whatever_the_version(self):
        package = self.make_package()
        self.put_msix_template(MSIX_TEMPLATE.replace(TEMPLATE_HASH, sha256_hex(package)))
        before = self.repo_tree()
        processor, messages = run(self.package_env(package))
        self.assertEqual(self.repo_tree(), before)
        self.assertEqual(processor.env["cimian_result"], "nothing-new")
        self.assertTrue(any("it has this very installer file" in m for m in messages))



if __name__ == "__main__":
    unittest.main()
