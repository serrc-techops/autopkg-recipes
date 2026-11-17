"""Tests of KyoceraKXDriverRepacker. Nothing here uses the network or the real vendor zip.

The tests build small zips in a temporary folder with the layout that was read on 2026-11-17
(32bit/, 64bit/, arm64/ and Utility/ folders, an OEMSETUP.INF in each architecture folder) and a
short INF of the same shape: a [Version] section with DriverVer, a [Manufacturer] section that names
the model sections, model lines of the form "<name>" = <install section>,<hardware id>, and [Strings].
"""
import hashlib
import os
import stat
import sys
import tempfile
import unittest
import zipfile

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.dirname(TESTS_DIR)
SHARED_TESTS_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-SharedProcessors", "tests")
for folder in (SHARED_TESTS_DIR, RECIPE_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

from _win_support import ProcessorError, run_processor  # noqa: E402  (installs the autopkglib stand-in)

import KyoceraKXDriverRepacker as repacker  # noqa: E402

PROCESSOR = repacker.KyoceraKXDriverRepacker
VERSION = "8.7.0917.0"
UNIVERSAL = "KX DRIVER for Universal Printing"

INF_TEXT = """;================================================================
;  OEMSETUP.INF  (a made-up stand-in for the vendor's file)
;================================================================

[Version]
Signature  = "$Windows NT$"
Class      = Printer
Provider   = %KMC%
CatalogFile= KYOMITA.CAT
DriverVer  = 09/17/2026,{version}

[Manufacturer]
Kyocera=Kyocera,NTx86.6.0,NTamd64.6.0

[Kyocera.NTx86.6.0]
"Kyocera Model A KX"   = ModelA,USBPRINT@KyoceraModelA0001,Kyocera_ModelA

[Kyocera.NTamd64.6.0]
"Kyocera Model A KX"   = ModelA,USBPRINT@KyoceraModelA0001,Kyocera_ModelA
"Kyocera Model A KX"   = ModelA,LPTENUM@KyoceraModelA0001,Kyocera_ModelA
; "Kyocera Commented Out KX" = Gone,USBPRINT@KyoceraGone
"Kyocera Model B; KX"  = ModelB,USBPRINT@KyoceraModelB0002,Kyocera_ModelB
%UPDM% = KM-UPDM,LPTENUM@KyoceraKM-42873DDE,Kyocera-UPDM

[ModelA]
CopyFiles = Files

[Other.NTamd64.6.0]
"Not A Model Of This INF" = Nope,USBPRINT@Nope

[Strings]
KMC = "KYOCERA"
UPDM = "{universal}"
"""


def inf_text(version=VERSION):
    return INF_TEXT.format(version=version, universal=UNIVERSAL).replace("@", chr(92))


def inf_bytes(version=VERSION, encoding="utf-16"):
    return inf_text(version).encode(encoding)


def vendor_members(version=VERSION, inf=None):
    inf = inf_bytes(version) if inf is None else inf
    members = [
        ("upd.pnf", b"top level file"),
        ("32bit/OEMSETUP.INF", inf_bytes("1000.0.0.0")),
        ("32bit/kyomita.cat", b"32 catalog"),
        ("64bit/OEMSETUP.INF", inf),
        ("64bit/kyomita.cat", b"catalog bytes"),
        ("64bit/Copyright.txt", b"copyright"),
        ("64bit/KACT/KACT.exe", b"KACT program"),
        ("64bit/KACT/ja/KACT.resources", b"resources"),
        ("64bit/a.ic_", b"icc a"),
        ("arm64/OEMSETUP.INF", inf_bytes("2000.0.0.0")),
        ("Utility/tool.exe", b"utility"),
    ]
    return members


def write_zip(path, members, compression=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(path, "w", compression) as archive:
        for name, content in members:
            archive.writestr(name, content)
    return path


def sha256_of(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="kx-tests-")
        self.addCleanup(self._tmp.cleanup)
        self.folder = os.path.realpath(self._tmp.name)
        self.zip_path = os.path.join(self.folder, "KX_Print_Driver.zip")

    def make(self, members=None, compression=zipfile.ZIP_DEFLATED):
        return write_zip(self.zip_path, vendor_members() if members is None else members, compression)

    def files(self):
        return sorted(os.listdir(self.folder))

    def run_it(self, **extra):
        env = {"pathname": self.zip_path}
        env.update(extra)
        return run_processor(PROCESSOR, env)

    def assert_refused(self, fragment, **extra):
        before = self.files()
        with self.assertRaises(ProcessorError) as caught:
            self.run_it(**extra)
        self.assertIn(fragment, str(caught.exception))
        self.assertIn("No zip was written", str(caught.exception))
        self.assertEqual(self.files(), before)


class LayoutTests(Base):
    def test_the_new_zip_holds_one_folder_with_the_files_of_the_chosen_folder(self):
        self.make()
        processor, messages = self.run_it()
        target = os.path.join(self.folder, "KyoceraKXDriver-%s.zip" % VERSION)
        self.assertEqual(processor.env["pathname"], target)
        self.assertEqual(self.files(), sorted([os.path.basename(self.zip_path), os.path.basename(target)]))
        top = "KyoceraKXDriver-%s/" % VERSION
        with zipfile.ZipFile(target) as archive:
            names = [info.filename for info in archive.infolist()]
            self.assertEqual(names, sorted(names, key=lambda n: n.encode("utf-8")))
            self.assertEqual(names, [top + n for n in (
                "Copyright.txt", "KACT/KACT.exe", "KACT/ja/KACT.resources", "OEMSETUP.INF", "a.ic_", "kyomita.cat")])
            self.assertEqual(archive.read(top + "KACT/KACT.exe"), b"KACT program")
            self.assertEqual(archive.read(top + "OEMSETUP.INF"), inf_bytes())
            self.assertIsNone(archive.testzip())
        self.assertEqual(len(messages), 1)
        self.assertIn("NOT verified", messages[0])

    def test_the_other_architectures_and_top_level_files_are_not_taken(self):
        self.make()
        self.run_it()
        with zipfile.ZipFile(os.path.join(self.folder, "KyoceraKXDriver-%s.zip" % VERSION)) as archive:
            for name in archive.namelist():
                self.assertNotIn("32bit", name)
                self.assertNotIn("arm64", name)
                self.assertNotIn("Utility", name)
                self.assertNotIn("upd.pnf", name)

    def test_the_architecture_folder_input_chooses_the_folder(self):
        self.make()
        processor, _ = self.run_it(kx_architecture_folder="arm64")
        self.assertTrue(processor.env["pathname"].endswith("KyoceraKXDriver-arm64-2000.0.0.0.zip"))
        with zipfile.ZipFile(processor.env["pathname"]) as archive:
            self.assertEqual(archive.namelist(), ["KyoceraKXDriver-arm64-2000.0.0.0/OEMSETUP.INF"])

    def test_the_outputs(self):
        self.make()
        processor, _ = self.run_it()
        env = processor.env
        self.assertEqual(env["version"], VERSION)
        self.assertEqual(env["checksum_sha256"], sha256_of(env["pathname"]))
        self.assertIs(env["checksum_verified"], False)
        self.assertEqual(env["kx_vendor_zip_pathname"], self.zip_path)
        self.assertEqual(env["kx_vendor_zip_sha256"], sha256_of(self.zip_path))
        self.assertEqual(env["kx_inf_driver_date"], "09/17/2026")
        self.assertEqual(env["kx_driver_folder"], "KyoceraKXDriver-" + VERSION)
        self.assertEqual(env["kx_file_count"], 6)
        self.assertEqual(env["kx_driver_name_count"], 3)

    def test_the_declared_inputs_and_outputs(self):
        self.assertEqual(sorted(PROCESSOR.input_variables), ["kx_architecture_folder", "kx_required_driver_names", "pathname"])
        self.assertTrue(PROCESSOR.input_variables["pathname"]["required"])
        for key in ("version", "checksum_sha256", "checksum_verified", "pathname"):
            self.assertIn(key, PROCESSOR.output_variables)

    def test_a_verified_flag_that_was_set_before_is_cleared(self):
        self.make()
        processor, _ = self.run_it(checksum_verified=True, checksum_sha256="0" * 64)
        self.assertIs(processor.env["checksum_verified"], False)
        self.assertEqual(processor.env["checksum_sha256"], sha256_of(processor.env["pathname"]))

    def test_no_temporary_file_is_left(self):
        self.make()
        self.run_it()
        self.assertFalse([n for n in self.files() if n.endswith(".tmp") or n.startswith(".")])


class DeterminismTests(Base):
    def test_two_runs_give_equal_bytes(self):
        self.make()
        first, _ = self.run_it()
        digest = sha256_of(first.env["pathname"])
        os.unlink(first.env["pathname"])
        second, _ = self.run_it()
        self.assertEqual(sha256_of(second.env["pathname"]), digest)

    def test_the_vendor_zip_in_another_order_and_compression_gives_the_same_bytes(self):
        self.make()
        first, _ = self.run_it()
        digest = sha256_of(first.env["pathname"])
        os.unlink(first.env["pathname"])
        self.make(list(reversed(vendor_members())), compression=zipfile.ZIP_STORED)
        second, _ = self.run_it()
        self.assertEqual(sha256_of(second.env["pathname"]), digest)

    def test_the_members_have_the_fixed_time_and_no_extra_attributes(self):
        self.make()
        processor, _ = self.run_it()
        with zipfile.ZipFile(processor.env["pathname"]) as archive:
            for info in archive.infolist():
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(info.external_attr, (stat.S_IFREG | 0o644) << 16)
                self.assertEqual(info.extra, b"")
                self.assertEqual(info.comment, b"")
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(info.create_system, 3)
            self.assertEqual(archive.comment, b"")

    def test_a_changed_file_gives_other_bytes(self):
        self.make()
        first, _ = self.run_it()
        digest = sha256_of(first.env["pathname"])
        members = [(n, (c + b"x") if n == "64bit/kyomita.cat" else c) for n, c in vendor_members()]
        self.make(members)
        second, _ = self.run_it()
        self.assertNotEqual(sha256_of(second.env["pathname"]), digest)

    def test_the_vendor_zip_is_not_changed(self):
        self.make()
        before = sha256_of(self.zip_path)
        self.run_it()
        self.assertEqual(sha256_of(self.zip_path), before)


class RefusalTests(Base):
    def test_not_a_zip(self):
        with open(self.zip_path, "wb") as handle:
            handle.write(b"this is not a zip")
        self.assert_refused("not a zip file")

    def test_no_file(self):
        with self.assertRaises(ProcessorError):
            self.run_it()

    def test_names_that_could_leave_the_folder(self):
        for name in ("/etc/passwd", "../evil.txt", "64bit/../../evil.txt", "64bit" + chr(92) + "evil.txt", "C:/evil.txt"):
            with self.subTest(name=name):
                members = vendor_members() + [(name, b"x")]
                with zipfile.ZipFile(self.zip_path, "w") as archive:
                    for n, c in members:
                        archive.writestr(n, c)
                self.assert_refused("not a relative path" if name != "../evil.txt" and name != "64bit/../../evil.txt"
                                    else "'..' part")

    def test_a_name_with_a_nul_is_refused(self):
        class FakeInfo:
            filename = "64bit/x\x00y"

        class FakeArchive:
            def infolist(self):
                return [FakeInfo()]

        with self.assertRaises(ValueError) as caught:
            repacker.check_member_names(FakeArchive())
        self.assertIn("not a relative path", str(caught.exception))

    def test_a_symbolic_link_is_refused(self):
        with zipfile.ZipFile(self.zip_path, "w") as archive:
            for name, content in vendor_members():
                archive.writestr(name, content)
            link = zipfile.ZipInfo("64bit/link.dll")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "/etc/passwd")
        self.assert_refused("symbolic link")

    def test_a_symbolic_link_outside_the_chosen_folder_is_not_looked_at(self):
        with zipfile.ZipFile(self.zip_path, "w") as archive:
            for name, content in vendor_members():
                archive.writestr(name, content)
            link = zipfile.ZipInfo("Utility/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "/etc/passwd")
        self.run_it()

    def test_a_duplicate_name(self):
        members = vendor_members() + [("64bit/kyomita.cat", b"second")]
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            write_zip(self.zip_path, members)
        self.assert_refused("two members named")

    def test_names_that_differ_only_in_case(self):
        self.make(vendor_members() + [("64bit/KYOMITA.CAT", b"second")])
        self.assert_refused("differ only in letter case")

    def test_a_zip_with_too_many_members(self):
        self.make()
        original = repacker.MAX_MEMBERS
        repacker.MAX_MEMBERS = 5
        self.addCleanup(setattr, repacker, "MAX_MEMBERS", original)
        self.assert_refused("members (at most 5")

    def test_an_archive_that_expands_over_the_limit(self):
        self.make()
        original = repacker.MAX_EXPANDED_BYTES
        repacker.MAX_EXPANDED_BYTES = 20
        self.addCleanup(setattr, repacker, "MAX_EXPANDED_BYTES", original)
        self.assert_refused("expand to more than 20 bytes")

    def test_the_limit_counts_only_the_chosen_folder(self):
        members = vendor_members() + [("Utility/huge.bin", b"x" * 5000)]
        self.make(members)
        original = repacker.MAX_EXPANDED_BYTES
        repacker.MAX_EXPANDED_BYTES = 4000
        self.addCleanup(setattr, repacker, "MAX_EXPANDED_BYTES", original)
        self.run_it()

    def test_a_damaged_member_is_a_refusal_with_a_message(self):
        with zipfile.ZipFile(self.zip_path, "w", zipfile.ZIP_STORED) as archive:
            for name, content in vendor_members():
                archive.writestr(name, content)
        with open(self.zip_path, "rb") as handle:
            data = bytearray(handle.read())
        marker = b"KACT program"
        at = data.rfind(marker)
        self.assertGreater(at, 0)
        data[at] ^= 0xFF  # a damaged byte: the CRC no longer fits
        with open(self.zip_path, "wb") as handle:
            handle.write(data)
        self.assert_refused("could not be read")

    def test_a_missing_folder(self):
        self.make()
        self.assert_refused("no files in the folder 32bits/", kx_architecture_folder="32bits")

    def test_bad_folder_inputs(self):
        self.make()
        for value in ("../64bit", "64bit/KACT", "a b", "x" * 40):
            with self.subTest(value=value):
                self.assert_refused("kx_architecture_folder must be one folder name", kx_architecture_folder=value)

    def test_no_inf(self):
        self.make([(n, c) for n, c in vendor_members() if n != "64bit/OEMSETUP.INF"])
        self.assert_refused("no member named OEMSETUP.INF")

    def test_two_infs_that_differ_in_case(self):
        self.make(vendor_members() + [("64bit/oemsetup.inf", inf_bytes())])
        self.assert_refused("differ only in letter case")

    def test_the_inf_too_long(self):
        self.make()
        original = repacker.MAX_INF_BYTES
        repacker.MAX_INF_BYTES = 100
        self.addCleanup(setattr, repacker, "MAX_INF_BYTES", original)
        self.assert_refused("OEMSETUP.INF is")

    def test_a_target_that_is_a_link_is_refused(self):
        self.make()
        os.symlink(os.path.join(self.folder, "elsewhere"), os.path.join(self.folder, "KyoceraKXDriver-%s.zip" % VERSION))
        before = self.files()
        with self.assertRaises(ProcessorError) as caught:
            self.run_it()
        self.assertIn("is a link", str(caught.exception))
        self.assertEqual(self.files(), before)

    def test_an_existing_target_is_replaced_by_the_same_bytes(self):
        self.make()
        first, _ = self.run_it()
        digest = sha256_of(first.env["pathname"])
        second, _ = self.run_it()
        self.assertEqual(sha256_of(second.env["pathname"]), digest)


class MoreGuardTests(Base):
    def test_the_new_zip_may_not_replace_the_vendor_zip(self):
        self.zip_path = os.path.join(self.folder, "KyoceraKXDriver-%s.zip" % VERSION)
        self.make()
        before = sha256_of(self.zip_path)
        self.assert_refused("would replace the vendor zip itself")
        self.assertEqual(sha256_of(self.zip_path), before)

    def test_an_empty_member_name_is_refused(self):
        class FakeInfo:
            filename = ""

        class FakeArchive:
            def infolist(self):
                return [FakeInfo()]

        with self.assertRaises(ValueError) as caught:
            repacker.check_member_names(FakeArchive())
        self.assertIn("empty name", str(caught.exception))

    def test_the_default_architecture_keeps_the_plain_name_and_another_one_carries_its_folder(self):
        self.make()
        default, _ = self.run_it()
        self.assertEqual(os.path.basename(default.env["pathname"]), "KyoceraKXDriver-%s.zip" % VERSION)
        arm, _ = self.run_it(kx_architecture_folder="arm64")
        self.assertEqual(os.path.basename(arm.env["pathname"]), "KyoceraKXDriver-arm64-2000.0.0.0.zip")
        self.assertEqual(arm.env["kx_driver_folder"], "KyoceraKXDriver-arm64-2000.0.0.0")
        with zipfile.ZipFile(arm.env["pathname"]) as archive:
            self.assertEqual(archive.namelist(), ["KyoceraKXDriver-arm64-2000.0.0.0/OEMSETUP.INF"])
        self.assertEqual(repacker.output_name("1000.0.0.0"), "KyoceraKXDriver-1000.0.0.0.zip")
        self.assertEqual(repacker.output_name("1000.0.0.0", "64bit"), "KyoceraKXDriver-1000.0.0.0.zip")


class VersionTests(Base):
    def test_the_version_comes_from_the_driverver_line(self):
        self.make(vendor_members("9.1.0201.3"))
        processor, _ = self.run_it()
        self.assertEqual(processor.env["version"], "9.1.0201.3")
        self.assertTrue(processor.env["pathname"].endswith("KyoceraKXDriver-9.1.0201.3.zip"))

    def test_a_missing_driverver_line(self):
        text = inf_text().replace("DriverVer  = 09/17/2026,%s" % VERSION, "")
        self.make(vendor_members(inf=text.encode("utf-16")))
        self.assert_refused("no DriverVer")

    def test_a_driverver_outside_the_version_section_does_not_count(self):
        text = inf_text().replace("DriverVer  = 09/17/2026,%s" % VERSION, "")
        text += "\n[Other]\nDriverVer = 09/17/2026,%s\n" % VERSION
        self.make(vendor_members(inf=text.encode("utf-16")))
        self.assert_refused("no DriverVer")

    def test_malformed_versions(self):
        for version in ("8.7.0917", "8.7.0917.0.1", "8.7.x.0", "", "8.7.0917.", "1234567.1.2.3", "-1001.2.3.4", "8,7,0917,0"):
            with self.subTest(version=version):
                self.make(vendor_members(inf=inf_bytes(version)))
                self.assert_refused("DriverVer")

    def test_a_driverver_without_a_comma(self):
        text = inf_text().replace("09/17/2026,%s" % VERSION, "09/17/2026")
        self.make(vendor_members(inf=text.encode("utf-16")))
        self.assert_refused("DriverVer")

    def test_two_driverver_lines(self):
        text = inf_text().replace("[Manufacturer]", "DriverVer = 09/18/2026,8.7.0918.0\n\n[Manufacturer]")
        self.make(vendor_members(inf=text.encode("utf-16")))
        self.assert_refused("2 DriverVer lines")

    def test_a_comment_after_the_version_is_ignored(self):
        text = inf_text().replace("09/17/2026,%s" % VERSION, "09/17/2026,%s ; made up" % VERSION)
        self.make(vendor_members(inf=text.encode("utf-16")))
        processor, _ = self.run_it()
        self.assertEqual(processor.env["version"], VERSION)

    def test_a_commented_out_line_is_not_a_line(self):
        text = inf_text().replace("DriverVer  =", "; DriverVer  =")
        self.make(vendor_members(inf=text.encode("utf-16")))
        self.assert_refused("no DriverVer")


class EncodingTests(Base):
    def test_every_encoding_gives_the_same_names_and_version(self):
        for label, data in (
            ("utf-16 with a byte order mark", inf_text().encode("utf-16")),
            ("utf-16 big endian with a byte order mark", b"\xfe\xff" + inf_text().encode("utf-16-be")),
            ("utf-16 little endian without a mark", inf_text().encode("utf-16-le")),
            ("utf-16 big endian without a mark", inf_text().encode("utf-16-be")),
            ("utf-8 with a byte order mark", b"\xef\xbb\xbf" + inf_text().encode("utf-8")),
            ("utf-8", inf_text().encode("utf-8")),
            ("windows-1252", inf_text().replace("Model A", "Mod\u00e9l A").encode("cp1252")),
            ("crlf line ends", inf_text().replace("\n", "\r\n").encode("utf-16")),
        ):
            with self.subTest(label=label):
                self.make(vendor_members(inf=data))
                processor, _ = self.run_it(kx_required_driver_names=[UNIVERSAL, "Kyocera Model B; KX"])
                self.assertEqual(processor.env["version"], VERSION)
                self.assertEqual(processor.env["kx_driver_name_count"], 3)

    def test_decode_inf_directly(self):
        self.assertEqual(repacker.decode_inf("[Version]\n".encode("utf-16")), "[Version]\n")
        self.assertEqual(repacker.decode_inf(b"abc"), "abc")
        self.assertEqual(repacker.decode_inf("\u00e9".encode("cp1252")), "\u00e9")


class NamesTests(Base):
    def test_the_model_names_of_the_inf(self):
        names = repacker.model_names(inf_text())
        self.assertEqual(names, {"Kyocera Model A KX", "Kyocera Model B; KX", UNIVERSAL})

    def test_a_commented_line_and_another_section_are_not_models(self):
        names = repacker.model_names(inf_text())
        self.assertNotIn("Kyocera Commented Out KX", names)
        self.assertNotIn("Not A Model Of This INF", names)

    def test_a_named_driver_is_found_and_a_missing_one_is_listed(self):
        self.make()
        self.run_it(kx_required_driver_names=["Kyocera Model A KX", UNIVERSAL])
        os.unlink(os.path.join(self.folder, "KyoceraKXDriver-%s.zip" % VERSION))
        with self.assertRaises(ProcessorError) as caught:
            self.run_it(kx_required_driver_names=["Kyocera Model A KX", "Kyocera Missing One KX", "Kyocera Missing Two KX",
                                                  "Not A Model Of This INF"])
        message = str(caught.exception)
        self.assertIn("does not list 3 of the required driver names", message)
        for name in ("Kyocera Missing One KX", "Kyocera Missing Two KX", "Not A Model Of This INF"):
            self.assertIn(name, message)
        self.assertNotIn("'Kyocera Model A KX'", message)
        self.assertNotIn("KyoceraKXDriver-", "".join(self.files()))

    def test_the_names_check_ignores_letter_case_and_lists_the_missing_as_written(self):
        self.make()
        self.run_it(kx_required_driver_names=["kyocera model a kx", "KX DRIVER FOR UNIVERSAL PRINTING"])
        os.unlink(os.path.join(self.folder, "KyoceraKXDriver-%s.zip" % VERSION))
        with self.assertRaises(ProcessorError) as caught:
            self.run_it(kx_required_driver_names=["Kyocera MISSING kx"])
        self.assertIn("'Kyocera MISSING kx'", str(caught.exception))

    def test_no_required_names_is_fine(self):
        self.make()
        for value in (None, []):
            self.run_it(kx_required_driver_names=value)

    def test_bad_name_inputs(self):
        self.make()
        for value in ("Kyocera Model A KX", [""], [5], ["a\nb"], {"a": 1}):
            with self.subTest(value=value):
                self.assert_refused("kx_required_driver_names", kx_required_driver_names=value)

    def test_an_inf_without_model_lines_is_refused(self):
        text = inf_text().replace("[Manufacturer]\nKyocera=Kyocera,NTx86.6.0,NTamd64.6.0", "[Manufacturer]")
        self.make(vendor_members(inf=text.encode("utf-16")))
        self.assert_refused("no model lines")

    def test_a_model_section_named_without_a_decoration(self):
        text = "[Version]\nDriverVer=01/02/2026,1001.2.3.4\n[Manufacturer]\nVendor=Plain\n[Plain]\n\"Plain Driver\" = X,Y\n"
        self.assertEqual(repacker.model_names(text), {"Plain Driver"})

    def test_a_string_key_that_is_not_defined_stays_as_written(self):
        text = "[Manufacturer]\nV=Plain\n[Plain]\n%UNDEFINED% = X,Y\n"
        self.assertEqual(repacker.model_names(text), {"%UNDEFINED%"})


class ErrorMessageTests(Base):
    def test_the_message_names_the_file_and_says_nothing_was_written(self):
        self.make([("64bit/kyomita.cat", b"no inf")])
        with self.assertRaises(ProcessorError) as caught:
            self.run_it()
        self.assertIn("KX_Print_Driver.zip", str(caught.exception))
        self.assertIn("No zip was written", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
