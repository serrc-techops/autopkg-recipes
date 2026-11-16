"""Tests of WindowsAppRuntimeFrameworkExtractor. Nothing here uses the network or the real redistributable.

The tests build tiny zips in a temporary folder: a zip with the layout that was read on
2026-11-16 (MSIX/win10-<arch>/ with the framework, Main, Singleton and DDLM packages), where
each "package" is itself a tiny zip with an AppxManifest.xml.
"""
import hashlib
import io
import os
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

from _win_support import ProcessorError, new_processor, run_processor  # noqa: E402  (installs the autopkglib stand-in)

import WindowsAppRuntimeFrameworkExtractor as extractor  # noqa: E402

PROCESSOR = extractor.WindowsAppRuntimeFrameworkExtractor
PUBLISHER = "CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US"
NAMESPACE = "http://schemas.microsoft.com/appx/manifest/foundation/windows10"


def manifest(publisher=PUBLISHER, name="Microsoft.WindowsAppRuntime.1.4", version="4000.1309.2056.0", architecture="x64",
             framework="true", extra=""):
    attributes = 'Name="%s" Publisher="%s" Version="%s" ProcessorArchitecture="%s"' % (name, publisher, version, architecture)
    framework_element = "<Framework>%s</Framework>" % framework if framework is not None else ""
    return ('<?xml version="1.0" encoding="utf-8"?>%s<Package xmlns="%s"><Identity %s />'
            "<Properties>%s<DisplayName>Example</DisplayName></Properties></Package>"
            % (extra, NAMESPACE, attributes, framework_element))


def package(**kwargs):
    """The bytes of a tiny package: a zip with a manifest."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("AppxManifest.xml", manifest(**kwargs))
        archive.writestr("payload.bin", b"payload " * 50)
    return buffer.getvalue()


def redist_members(architectures=("x64", "x86", "arm64"), release="1.4"):
    members = []
    for architecture in architectures:
        base = "MSIX/win10-%s/" % architecture
        members.append((base + "Microsoft.WindowsAppRuntime.%s.msix" % release,
                        package(name="Microsoft.WindowsAppRuntime." + release, architecture=architecture)))
        members.append((base + "Microsoft.WindowsAppRuntime.Main.%s.msix" % release,
                        package(name="MicrosoftCorporationII.WinAppRuntime.Main." + release, architecture=architecture,
                                framework=None)))
        members.append((base + "Microsoft.WindowsAppRuntime.Singleton.%s.msix" % release,
                        package(name="MicrosoftCorporationII.WinAppRuntime.Singleton", architecture=architecture, framework=None)))
        members.append((base + "Microsoft.WindowsAppRuntime.DDLM.%s.msix" % release,
                        package(name="Microsoft.WinAppRuntime.DDLM.1.4", architecture=architecture, framework=None)))
    members.append(("WindowsAppSDK-Installer-x64/WindowsAppRuntimeInstall-x64.exe", b"MZ not run"))
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
        self._tmp = tempfile.TemporaryDirectory(prefix="win-war-tests-")
        self.addCleanup(self._tmp.cleanup)
        self.folder = os.path.realpath(self._tmp.name)
        self.zip_path = os.path.join(self.folder, "Microsoft.WindowsAppRuntime.Redist.1.4.zip")

    def make(self, members=None):
        return write_zip(self.zip_path, redist_members() if members is None else members)

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
        self.assertIn("No package was written", str(caught.exception))
        self.assertEqual(self.files(), before)


class ExtractionTests(Base):
    def test_the_framework_package_of_x64_is_written_beside_the_zip_with_its_facts(self):
        self.make()
        processor, messages = self.run_it()
        target = os.path.join(self.folder, "Microsoft.WindowsAppRuntime.1.4_4000.1309.2056.0_x64.msix")
        self.assertEqual(processor.env["pathname"], target)
        self.assertEqual(self.files(), sorted([os.path.basename(self.zip_path), os.path.basename(target)]))
        with open(target, "rb") as handle:
            self.assertEqual(handle.read(), dict(redist_members())["MSIX/win10-x64/Microsoft.WindowsAppRuntime.1.4.msix"])
        self.assertEqual(processor.env["windowsappruntime_zip_pathname"], self.zip_path)
        self.assertEqual(processor.env["windowsappruntime_zip_sha256"], sha256_of(self.zip_path))
        self.assertEqual(processor.env["windowsappruntime_identity_name"], "Microsoft.WindowsAppRuntime.1.4")
        self.assertEqual(processor.env["windowsappruntime_version"], "4000.1309.2056.0")
        self.assertEqual(processor.env["windowsappruntime_package_architecture"], "x64")
        self.assertEqual(processor.env["windowsappruntime_publisher"], PUBLISHER)
        self.assertEqual(len(messages), 1)
        self.assertIn("NOT verified", messages[0])

    def test_the_architecture_input_chooses_the_member(self):
        self.make()
        processor, _ = self.run_it(windowsappruntime_architecture="arm64")
        self.assertTrue(processor.env["pathname"].endswith("_arm64.msix"))
        self.assertEqual(processor.env["windowsappruntime_package_architecture"], "arm64")

    def test_the_decoys_are_never_taken(self):
        self.make()
        self.run_it()
        for name in self.files():
            self.assertNotIn("Main", name)
            self.assertNotIn("Singleton", name)
            self.assertNotIn("DDLM", name)

    def test_the_same_zip_gives_the_same_bytes_twice(self):
        self.make()
        first, _ = self.run_it()
        digest = sha256_of(first.env["pathname"])
        second, _ = self.run_it()
        self.assertEqual(sha256_of(second.env["pathname"]), digest)
        self.assertEqual(len(self.files()), 2)

    def test_the_release_input_is_used(self):
        self.make(redist_members(release="1.5"))
        processor, _ = self.run_it(windowsappruntime_release="1.5")
        self.assertEqual(processor.env["windowsappruntime_identity_name"], "Microsoft.WindowsAppRuntime.1.5")

    def test_the_letter_case_of_the_member_name_does_not_matter(self):
        self.make([(name.replace("MSIX/", "msix/"), data) for name, data in redist_members()])
        processor, _ = self.run_it()
        self.assertTrue(processor.env["pathname"].endswith("_x64.msix"))

    def test_the_package_gets_no_execute_bit(self):
        self.make()
        os.chmod(self.zip_path, 0o755)
        processor, _ = self.run_it()
        self.assertEqual(os.stat(processor.env["pathname"]).st_mode & 0o111, 0)


class RefusalTests(Base):
    def test_a_missing_member(self):
        self.make([m for m in redist_members() if "win10-x64/Microsoft.WindowsAppRuntime.1.4.msix" not in m[0]])
        self.assert_refused("has no member MSIX/win10-x64/Microsoft.WindowsAppRuntime.1.4.msix")

    def test_only_the_decoys_of_the_architecture_are_there(self):
        self.make([m for m in redist_members() if m[0].endswith(("Main.1.4.msix", "Singleton.1.4.msix", "DDLM.1.4.msix"))])
        self.assert_refused("has no member")

    def test_wrong_architecture_only(self):
        self.make(redist_members(architectures=("x86",)))
        self.assert_refused("has no member")

    def test_a_doubled_member(self):
        members = redist_members()
        members.append(members[0])
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # the zip module warns about a duplicate name when it is written
            self.make(members)
        self.assert_refused("2 members named")

    def test_two_members_that_differ_only_in_case(self):
        members = redist_members()
        members.append((members[0][0].upper().replace("MSIX/", "MSIX/"), members[0][1]))
        self.make(members)
        self.assert_refused("2 members named")

    def test_a_package_with_another_identity_name(self):
        members = redist_members()
        members[0] = (members[0][0], package(name="Example.Other.1.4"))
        self.make(members)
        self.assert_refused("not Microsoft.WindowsAppRuntime.1.4")

    def test_the_main_package_under_the_framework_name(self):
        members = redist_members()
        members[0] = (members[0][0], package(name="MicrosoftCorporationII.WinAppRuntime.Main.1.4", framework=None))
        self.make(members)
        self.assert_refused("not Microsoft.WindowsAppRuntime.1.4")

    def test_a_package_for_another_architecture_in_the_right_place(self):
        members = redist_members()
        members[0] = (members[0][0], package(architecture="x86"))
        self.make(members)
        self.assert_refused("is for 'x86', not x64")

    def test_a_package_without_the_framework_mark(self):
        members = redist_members()
        members[0] = (members[0][0], package(framework=None))
        self.make(members)
        self.assert_refused("Properties/Framework")

    def test_a_package_with_the_framework_mark_false(self):
        members = redist_members()
        members[0] = (members[0][0], package(framework="false"))
        self.make(members)
        self.assert_refused("Properties/Framework")

    def test_a_manifest_with_a_document_type(self):
        members = redist_members()
        members[0] = (members[0][0], package(extra='<!DOCTYPE Package [<!ENTITY x "y">]>'))
        self.make(members)
        self.assert_refused("document type or entity declaration")

    def test_a_package_that_is_not_a_zip(self):
        members = redist_members()
        members[0] = (members[0][0], b"not a zip at all")
        self.make(members)
        self.assert_refused("not a zip file")

    def test_a_package_without_a_manifest(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("other.xml", "<a/>")
        members = redist_members()
        members[0] = (members[0][0], buffer.getvalue())
        self.make(members)
        self.assert_refused("0 members named AppxManifest.xml")

    def test_a_version_that_is_not_numbers(self):
        members = redist_members()
        members[0] = (members[0][0], package(version="latest"))
        self.make(members)
        self.assert_refused("version of the package is not usable")

    def test_the_zip_is_not_a_zip(self):
        with open(self.zip_path, "wb") as handle:
            handle.write(b"hello")
        self.assert_refused("not a zip file")

    def test_pathname_is_not_a_file(self):
        with self.assertRaises(ProcessorError):
            run_processor(PROCESSOR, {"pathname": self.folder})
        with self.assertRaises(ProcessorError):
            run_processor(PROCESSOR, {"pathname": os.path.join(self.folder, "absent.zip")})

    def test_a_bad_architecture_or_release_input(self):
        self.make()
        self.assert_refused("must be one of", windowsappruntime_architecture="amd64")
        self.assert_refused("must look like 1.4", windowsappruntime_release="1.4/../x")

    def test_a_size_above_the_bound(self):
        self.make()
        with unittest.mock.patch.object(extractor, "MAX_MSIX_BYTES", 10):
            self.assert_refused("at most 10 are accepted")

    def test_a_manifest_above_the_bound(self):
        self.make()
        with unittest.mock.patch.object(extractor, "MAX_MANIFEST_BYTES", 10):
            self.assert_refused("at most 10 are accepted")

    def test_a_link_at_the_target(self):
        self.make()
        outside = os.path.join(self.folder, "elsewhere")
        open(outside, "w").close()
        os.symlink(outside, os.path.join(self.folder, "Microsoft.WindowsAppRuntime.1.4_4000.1309.2056.0_x64.msix"))
        before = self.files()
        with self.assertRaises(ProcessorError) as caught:
            self.run_it()
        self.assertIn("is a link", str(caught.exception))
        self.assertEqual(self.files(), before)
        self.assertEqual(os.path.getsize(outside), 0)


class HardeningTests(Base):
    def test_a_utf16_manifest_with_an_entity_is_refused(self):
        text = manifest(publisher="CN=&a;", extra='<!DOCTYPE Package [<!ENTITY a "x">]>')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("AppxManifest.xml", text.encode("utf-16"))
        members = redist_members()
        members[0] = (members[0][0], buffer.getvalue())
        self.make(members)
        self.assert_refused("not UTF-8 text")

    def test_a_utf8_manifest_with_a_bom_is_accepted(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("AppxManifest.xml", b"\xef\xbb\xbf" + manifest().encode("utf-8"))
        members = redist_members()
        members[0] = (members[0][0], buffer.getvalue())
        self.make(members)
        self.run_it()

    def test_a_manifest_that_is_not_valid_utf8(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("AppxManifest.xml", manifest().encode("utf-8") + b"\xff")
        members = redist_members()
        members[0] = (members[0][0], buffer.getvalue())
        self.make(members)
        self.assert_refused("not valid UTF-8")

    def test_a_corrupt_member_is_a_refusal_with_no_temporary_file(self):
        members = redist_members()
        write_zip(self.zip_path, members, zipfile.ZIP_STORED)
        with open(self.zip_path, "rb") as handle:
            data = bytearray(handle.read())
        spot = data.find(members[0][1]) + len(members[0][1]) // 2
        data[spot] ^= 0xFF
        with open(self.zip_path, "wb") as handle:
            handle.write(bytes(data))
        self.assert_refused("could not be read")

    def test_a_corrupt_package_is_a_refusal(self):
        members = redist_members()
        inner = bytearray(members[0][1])
        spot = inner.find(b"payload ") if b"payload " in inner else len(inner) // 2
        # The inner zip's own members are deflated: damage the compressed manifest instead.
        inner[len(inner) // 3] ^= 0xFF
        members[0] = (members[0][0], bytes(inner))
        self.make(members)
        with self.assertRaises(ProcessorError) as caught:
            self.run_it()
        self.assertIn("No package was written", str(caught.exception))

    def test_a_publisher_that_is_not_microsofts(self):
        members = redist_members()
        members[0] = (members[0][0], package(publisher="CN=Somebody Else"))
        self.make(members)
        self.assert_refused("not Microsoft's")


class PathTrickTests(Base):
    def check(self, bad_name):
        members = redist_members() + [(bad_name, b"x")]
        self.make(members)
        self.assert_refused("member name")

    def test_an_absolute_name(self):
        self.check("/etc/evil")

    def test_a_dot_dot_part(self):
        self.check("MSIX/../../evil")

    def test_a_backslash(self):
        self.check("MSIX\\win10-x64\\evil.msix")

    def test_a_drive_letter(self):
        self.check("C:/evil")

    def test_nothing_is_written_outside_the_folder(self):
        self.make(redist_members() + [("../escape.txt", b"x")])
        with self.assertRaises(ProcessorError):
            self.run_it()
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.folder), "escape.txt")))


class VerificationHandoffTests(Base):
    """The zip is verified by ChecksumVerifier; the importers want the hash of the file they import."""

    def setUp(self):
        super().setUp()
        self.make()
        self.zip_hash = sha256_of(self.zip_path)

    def test_a_verified_zip_gives_the_package_hash_and_keeps_the_flag(self):
        processor, messages = self.run_it(checksum_verified=True, checksum_sha256=self.zip_hash)
        self.assertIs(processor.env["checksum_verified"], True)
        self.assertEqual(processor.env["checksum_sha256"], sha256_of(processor.env["pathname"]))
        self.assertNotEqual(processor.env["checksum_sha256"], self.zip_hash)
        self.assertNotIn("NOT verified", messages[0])

    def test_the_importers_check_accepts_the_result(self):
        import _win_support
        processor, _ = self.run_it(checksum_verified=True, checksum_sha256=self.zip_hash)
        path = processor.env["pathname"]
        actual = sha256_of(path)
        importer, _ = new_processor(_win_support.cimian.CimianImporter, dict(processor.env))
        self.assertTrue(importer.check_verification(path, actual))

    def test_the_importers_check_refuses_the_zips_hash_for_the_package(self):
        """Without the replacement the importers would stop: the verified file is not the imported one."""
        import _win_support
        processor, _ = self.run_it(checksum_verified=True, checksum_sha256=self.zip_hash)
        env = dict(processor.env)
        env["checksum_sha256"] = self.zip_hash
        importer, _ = new_processor(_win_support.cimian.CimianImporter, env)
        with self.assertRaises(ProcessorError):
            importer.check_verification(processor.env["pathname"], sha256_of(processor.env["pathname"]))

    def test_an_unverified_zip_leaves_the_checksum_variables_alone(self):
        processor, _ = self.run_it()
        self.assertNotIn("checksum_verified", processor.env)
        self.assertNotIn("checksum_sha256", processor.env)
        import _win_support
        importer, _ = new_processor(_win_support.cimian.CimianImporter, dict(processor.env))
        self.assertFalse(importer.check_verification(processor.env["pathname"], sha256_of(processor.env["pathname"])))

    def test_a_flag_that_is_text_does_not_count(self):
        processor, _ = self.run_it(checksum_verified="True", checksum_sha256=self.zip_hash)
        self.assertEqual(processor.env["checksum_sha256"], self.zip_hash)  # left as it was: not replaced

    def test_a_hash_of_another_file_stops_the_run(self):
        self.assert_refused("hash of another file", checksum_verified=True, checksum_sha256="0" * 64)

    def test_a_flag_without_a_hash_marks_nothing(self):
        processor, _ = self.run_it(checksum_verified=True)
        self.assertNotIn("checksum_sha256", processor.env)
        self.assertIn("NOT verified", _last(processor))

    def test_the_real_checksum_step_then_the_extractor(self):
        import _win_support
        verifier, _ = run_processor(_win_support.checksum.ChecksumVerifier,
                                    {"pathname": self.zip_path, "expected_sha256": self.zip_hash})
        processor, _ = self.run_it(checksum_verified=verifier.env["checksum_verified"],
                                   checksum_sha256=verifier.env["checksum_sha256"])
        self.assertEqual(processor.env["checksum_sha256"], sha256_of(processor.env["pathname"]))


def _last(processor):
    return processor.message_levels[-1][1]


class DeclarationTests(unittest.TestCase):
    def test_inputs_and_outputs(self):
        self.assertEqual(set(PROCESSOR.input_variables), {
            "pathname", "windowsappruntime_release", "windowsappruntime_architecture",
            "checksum_verified", "checksum_sha256"})
        self.assertEqual(set(PROCESSOR.output_variables), {
            "pathname", "windowsappruntime_zip_pathname", "windowsappruntime_zip_sha256",
            "windowsappruntime_identity_name", "windowsappruntime_version",
            "windowsappruntime_package_architecture", "windowsappruntime_publisher", "checksum_sha256"})
        self.assertTrue(PROCESSOR.input_variables["pathname"]["required"])

    def test_only_the_standard_library_and_autopkg_are_imported(self):
        with open(os.path.join(RECIPE_DIR, "WindowsAppRuntimeFrameworkExtractor.py"), encoding="utf-8") as handle:
            text = handle.read()
        imported = set()
        for line in text.splitlines():
            if line.startswith("import "):
                imported.add(line.split()[1].split(".")[0])
            elif line.startswith("from "):
                imported.add(line.split()[1].split(".")[0])
        self.assertEqual(imported, {"hashlib", "os", "re", "tempfile", "xml", "zipfile", "zlib", "autopkglib"})
        for word in ("subprocess", "extractall", "os.system"):
            self.assertNotIn(word, text)


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
