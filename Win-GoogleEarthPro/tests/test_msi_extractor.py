"""Tests of GoogleEarthProMsiExtractor. Nothing here uses the network or a real installer.

No real EXE or MSI is in this repository. The tests build a small PE file in a
temporary folder with `struct`: a DOS header, a PE header, an optional header
with its data directories, a section table and one resource section that holds
a resource tree whose type and resource are NAMED entries (BINARY, ID_MSI), as
7-Zip showed them in the real file on 2026-11-13, with one language (1033). The
"MSI" in it is a few bytes that begin with the compound file signature; it is
not a real MSI.
"""
import os
import struct
import sys
import tempfile
import unittest
from unittest import mock

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.dirname(TESTS_DIR)
SHARED_TESTS_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-SharedProcessors", "tests")
for folder in (SHARED_TESTS_DIR, RECIPE_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

from _win_support import ProcessorError, new_processor, run_processor  # noqa: E402  (installs the autopkglib stand-in)

import GoogleEarthProMsiExtractor as extractor  # noqa: E402

PROCESSOR = extractor.GoogleEarthProMsiExtractor
HIGH = 0x80000000
SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
FAKE_MSI = SIGNATURE + b"a stand-in for a Windows Installer database" + bytes(range(256))
ENGLISH = 1033
SECTION_RVA = 0x1000
SECTION_OFFSET = 0x200
PE_OFFSET = 0x80


def directory_header(named, ids):
    return struct.pack("<IIHHHH", 0, 0, 0, 0, named, ids)


def resource_tree(entries):
    """The bytes of a resource section at SECTION_RVA. `entries` is a list of
    (name, child): a name is a text (a named entry) or a number (an id); a child
    is a list (a directory) or bytes (a data entry for that blob). Blobs come
    last; their data entries carry their address."""
    buffer = bytearray()
    patches = []  # (offset of a data entry, blob)

    def put(data):
        offset = len(buffer)
        buffer.extend(data)
        return offset

    def align(n):
        while len(buffer) % n:
            buffer.append(0)

    def directory(items):
        named = [item for item in items if isinstance(item[0], str)]
        ids = [item for item in items if not isinstance(item[0], str)]
        ordered = named + ids
        start = put(directory_header(len(named), len(ids)) + b"\0" * (8 * len(ordered)))
        for index, (name, child) in enumerate(ordered):
            if isinstance(name, str):
                align(2)
                name_field = HIGH | put(struct.pack("<H", len(name)) + name.encode("utf-16-le"))
            else:
                name_field = name
            align(4)
            if isinstance(child, list):
                target = HIGH | directory(child)
            else:
                target = put(b"\0" * 16)
                patches.append((target, bytes(child)))
            struct.pack_into("<II", buffer, start + 16 + 8 * index, name_field, target)
        return start

    directory(entries)
    for entry_offset, blob in patches:
        align(8)
        blob_offset = put(blob)
        struct.pack_into("<II", buffer, entry_offset, SECTION_RVA + blob_offset, len(blob))
    return bytes(buffer)


def standard_tree(blob=FAKE_MSI):
    """The shape of the real file: an icon (by number), and BINARY/ID_MSI/1033."""
    return [
        (3, [(1, [(ENGLISH, b"an icon")])]),
        ("BINARY", [("ID_MSI", [(ENGLISH, blob)])]),
    ]


def build_pe(entries, raw_size=None, virtual_size=None, plus=False, truncate=0):
    """A PE file with one resource section that holds `entries`."""
    rsrc = resource_tree(entries)
    padded = rsrc + b"\0" * ((-len(rsrc)) % 0x200)
    fixed = 112 if plus else 96
    optional = bytearray(fixed)
    struct.pack_into("<H", optional, 0, 0x20B if plus else 0x10B)
    struct.pack_into("<I", optional, fixed - 4, 16)
    directories = bytearray(16 * 8)
    struct.pack_into("<II", directories, 8 * 2, SECTION_RVA, len(rsrc))
    optional = bytes(optional) + bytes(directories)
    section = struct.pack(
        "<8sIIIIIIHHI", b".rsrc\0\0\0", len(rsrc) if virtual_size is None else virtual_size, SECTION_RVA,
        len(padded) if raw_size is None else raw_size, SECTION_OFFSET, 0, 0, 0, 0, 0x40000040,
    )
    coff = struct.pack("<HHIIIHH", 0x8664 if plus else 0x14C, 1, 0, 0, 0, len(optional), 0x102)
    dos = bytearray(PE_OFFSET)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, PE_OFFSET)
    headers = bytes(dos) + b"PE\0\0" + coff + optional + section
    data = headers + b"\0" * (SECTION_OFFSET - len(headers)) + padded
    return data[:len(data) - truncate] if truncate else data


class ExtractorTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="gep-msi-")
        self.addCleanup(self._tmp.cleanup)
        self.folder = os.path.realpath(self._tmp.name)

    def write(self, data, name="googleearthprowin-x64.exe"):
        path = os.path.join(self.folder, name)
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def run_on(self, data):
        return run_processor(PROCESSOR, {"pathname": self.write(data)})

    def assertRejected(self, data, fragment):
        exe = self.write(data)
        before = sorted(os.listdir(self.folder))
        processor, _ = new_processor(PROCESSOR, {"pathname": exe})
        with self.assertRaises(ProcessorError) as caught:
            processor.main()
        self.assertIn(fragment, str(caught.exception))
        self.assertIn("No MSI was written", str(caught.exception))
        self.assertEqual(processor.env, {"pathname": exe})
        # nothing written, no temporary file left
        self.assertEqual(sorted(os.listdir(self.folder)), before)
        return str(caught.exception)


class FoundTests(ExtractorTestCase):
    def test_the_msi_is_written_beside_the_exe_byte_for_byte(self):
        processor, messages = self.run_on(build_pe(standard_tree()))
        exe = os.path.join(self.folder, "googleearthprowin-x64.exe")
        msi = os.path.join(self.folder, "googleearthprowin-x64.msi")
        self.assertEqual(processor.env["pathname"], msi)
        self.assertEqual(processor.env["googleearthpro_wrapper_pathname"], exe)
        with open(msi, "rb") as handle:
            self.assertEqual(handle.read(), FAKE_MSI)
        self.assertEqual(sorted(os.listdir(self.folder)), ["googleearthprowin-x64.exe", "googleearthprowin-x64.msi"])

    def test_one_line_names_both_sizes(self):
        data = build_pe(standard_tree())
        _, messages = self.run_on(data)
        self.assertEqual(len(messages), 1)
        self.assertIn("(%d bytes)" % len(data), messages[0])
        self.assertIn("(%d bytes)" % len(FAKE_MSI), messages[0])
        self.assertIn("BINARY/ID_MSI", messages[0])

    def test_pe32_plus_is_read_the_same(self):
        processor, _ = self.run_on(build_pe(standard_tree(), plus=True))
        with open(processor.env["pathname"], "rb") as handle:
            self.assertEqual(handle.read(), FAKE_MSI)

    def test_the_same_exe_gives_the_same_msi_and_a_second_run_replaces_the_first(self):
        processor, _ = self.run_on(build_pe(standard_tree()))
        with open(processor.env["pathname"], "rb") as handle:
            first = handle.read()
        processor, _ = run_processor(PROCESSOR, {"pathname": processor.env["googleearthpro_wrapper_pathname"]})
        with open(processor.env["pathname"], "rb") as handle:
            self.assertEqual(handle.read(), first)
        self.assertEqual(len(os.listdir(self.folder)), 2)

    def test_an_old_msi_of_another_download_is_replaced(self):
        self.write(b"an old file", name="googleearthprowin-x64.msi")
        processor, _ = self.run_on(build_pe(standard_tree()))
        with open(processor.env["pathname"], "rb") as handle:
            self.assertEqual(handle.read(), FAKE_MSI)

    def test_the_msi_gets_the_read_and_write_bits_of_the_download_and_no_execute_bit(self):
        exe = self.write(build_pe(standard_tree()))
        os.chmod(exe, 0o755)
        processor, _ = run_processor(PROCESSOR, {"pathname": exe})
        self.assertEqual(os.stat(processor.env["pathname"]).st_mode & 0o777, 0o644)

    def test_other_resources_and_an_id_named_like_the_type_are_passed_over(self):
        tree = [(10, [(1, [(ENGLISH, b"RCDATA, not it")])])] + standard_tree()
        processor, _ = self.run_on(build_pe(tree))
        with open(processor.env["pathname"], "rb") as handle:
            self.assertEqual(handle.read(), FAKE_MSI)

    def test_any_single_language_is_accepted(self):
        processor, _ = self.run_on(build_pe([("BINARY", [("ID_MSI", [(0, FAKE_MSI)])])]))
        with open(processor.env["pathname"], "rb") as handle:
            self.assertEqual(handle.read(), FAKE_MSI)

    def test_msi_path_for(self):
        self.assertEqual(extractor.msi_path_for("/a/b/setup.exe"), "/a/b/setup.msi")
        self.assertEqual(extractor.msi_path_for("/a/b/setup.EXE"), "/a/b/setup.msi")


class NotFoundTests(ExtractorTestCase):
    def test_no_binary_type(self):
        self.assertRejected(build_pe([(3, [(1, [(ENGLISH, b"an icon")])])]), "has no entry named BINARY")

    def test_the_type_as_a_number_is_not_the_named_type(self):
        self.assertRejected(build_pe([(10, [("ID_MSI", [(ENGLISH, FAKE_MSI)])])]), "has no entry named BINARY")

    def test_no_id_msi_resource(self):
        self.assertRejected(build_pe([("BINARY", [("OTHER", [(ENGLISH, FAKE_MSI)])])]), "has no entry named ID_MSI")

    def test_a_name_that_differs_in_case_is_not_the_name(self):
        self.assertRejected(build_pe([("BINARY", [("id_msi", [(ENGLISH, FAKE_MSI)])])]), "has no entry named ID_MSI")

    def test_not_a_pe_file(self):
        self.assertRejected(b"PK\3\4" + b"\0" * 200, "not a PE file")

    def test_a_missing_file(self):
        processor, _ = new_processor(PROCESSOR, {"pathname": os.path.join(self.folder, "missing.exe")})
        with self.assertRaises(ProcessorError):
            processor.main()


class AmbiguityTests(ExtractorTestCase):
    def test_two_languages_are_refused(self):
        tree = [("BINARY", [("ID_MSI", [(ENGLISH, FAKE_MSI), (1031, FAKE_MSI)])])]
        self.assertRejected(build_pe(tree), "has 2 entries (exactly one is accepted)")

    def test_two_types_named_binary_are_refused(self):
        tree = [("BINARY", [("ID_MSI", [(ENGLISH, FAKE_MSI)])]), ("BINARY", [("ID_MSI", [(ENGLISH, FAKE_MSI)])])]
        self.assertRejected(build_pe(tree), "has 2 entries named BINARY")

    def test_two_resources_named_id_msi_are_refused(self):
        tree = [("BINARY", [("ID_MSI", [(ENGLISH, FAKE_MSI)]), ("ID_MSI", [(ENGLISH, FAKE_MSI)])])]
        self.assertRejected(build_pe(tree), "has 2 entries named ID_MSI")

    def test_a_type_entry_that_is_data_is_refused(self):
        self.assertRejected(build_pe([("BINARY", FAKE_MSI)]), "the entry named BINARY")

    def test_a_language_entry_that_is_a_directory_is_refused(self):
        tree = [("BINARY", [("ID_MSI", [(ENGLISH, [(1, FAKE_MSI)])])])]
        self.assertRejected(build_pe(tree), "is not a data entry")


class ContentTests(ExtractorTestCase):
    def test_a_resource_without_the_signature_is_refused(self):
        self.assertRejected(build_pe(standard_tree(b"MZ" + b"\0" * 64)), "does not begin with the signature")

    def test_a_signature_that_is_one_byte_off_is_refused(self):
        blob = bytearray(FAKE_MSI)
        blob[7] ^= 1
        self.assertRejected(build_pe(standard_tree(bytes(blob))), "does not begin with the signature")

    def test_a_resource_shorter_than_the_signature_is_refused(self):
        self.assertRejected(build_pe(standard_tree(SIGNATURE[:4])), "does not begin with the signature")

    def test_an_empty_resource_is_refused(self):
        self.assertRejected(build_pe(standard_tree(b"")), "is empty")

    def test_a_resource_over_the_limit_is_refused(self):
        with mock.patch.object(extractor, "MAX_MSI_BYTES", len(FAKE_MSI) - 1):
            self.assertRejected(build_pe(standard_tree()), "at most %d are accepted" % (len(FAKE_MSI) - 1))

    def test_a_resource_at_the_limit_is_accepted(self):
        with mock.patch.object(extractor, "MAX_MSI_BYTES", len(FAKE_MSI)):
            processor, _ = self.run_on(build_pe(standard_tree()))
        self.assertTrue(os.path.isfile(processor.env["pathname"]))

    def test_the_limit_is_far_above_the_real_msi(self):
        self.assertGreater(extractor.MAX_MSI_BYTES, 63475712)


class BoundsTests(ExtractorTestCase):
    @staticmethod
    def msi_end():
        """Where the MSI blob ends, counted from the start of the section."""
        tree = resource_tree(standard_tree())
        return tree.index(FAKE_MSI) + len(FAKE_MSI)

    def test_a_resource_that_leaves_the_raw_data_of_its_section_is_refused(self):
        # The section's raw data ends four bytes before the end of the MSI blob.
        self.assertRejected(build_pe(standard_tree(), raw_size=self.msi_end() - 4), "outside the raw data of its section")

    def test_a_resource_that_ends_with_the_raw_data_of_its_section_is_accepted(self):
        processor, _ = self.run_on(build_pe(standard_tree(), raw_size=self.msi_end()))
        self.assertTrue(os.path.isfile(processor.env["pathname"]))

    def test_a_resource_that_leaves_the_file_is_refused(self):
        # The section claims all its raw data, but the file ends four bytes before the end of the MSI blob.
        full = len(build_pe(standard_tree()))
        cut = full - (SECTION_OFFSET + self.msi_end() - 4)
        self.assertRejected(build_pe(standard_tree(), truncate=cut), "lies outside the file")

    def test_a_data_entry_that_points_at_no_section_is_refused(self):
        data = bytearray(build_pe(standard_tree()))
        tree = resource_tree(standard_tree())
        # The last data entry is that of ID_MSI; move its address far beyond the section.
        position = SECTION_OFFSET + tree.rindex(struct.pack("<I", len(FAKE_MSI))) - 4
        struct.pack_into("<I", data, position, 0x7000000)
        self.assertRejected(bytes(data), "is at an address that no section holds")

    def test_a_size_that_runs_past_the_section_is_refused(self):
        data = bytearray(build_pe(standard_tree()))
        tree = resource_tree(standard_tree())
        position = SECTION_OFFSET + tree.rindex(struct.pack("<I", len(FAKE_MSI)))
        struct.pack_into("<I", data, position, 0x100000)
        self.assertRejected(bytes(data), "outside the raw data of its section")

    def test_a_directory_offset_outside_the_section_is_refused(self):
        data = bytearray(build_pe(standard_tree()))
        # The root's first entry (the named type BINARY comes first) points far away.
        struct.pack_into("<I", data, SECTION_OFFSET + 16 + 4, HIGH | 0x400000)
        self.assertRejected(bytes(data), "no section holds")

    def test_a_name_offset_outside_the_section_is_refused(self):
        data = bytearray(build_pe(standard_tree()))
        struct.pack_into("<I", data, SECTION_OFFSET + 16, HIGH | 0x400000)
        self.assertRejected(bytes(data), "no section holds")

    def test_a_long_name_is_refused(self):
        tree = [("B" * (extractor.MAX_NAME_CHARACTERS + 1), [("ID_MSI", [(ENGLISH, FAKE_MSI)])])]
        self.assertRejected(build_pe(tree), "characters (at most")

    def test_too_many_entries_are_refused(self):
        data = bytearray(build_pe(standard_tree()))
        struct.pack_into("<HH", data, SECTION_OFFSET + 12, 0xFFFF, 0xFFFF)
        self.assertRejected(bytes(data), "entries (at most")


class TargetTests(ExtractorTestCase):
    def test_a_link_at_the_target_is_refused_and_left_alone(self):
        elsewhere = os.path.join(self.folder, "elsewhere")
        os.mkdir(elsewhere)
        victim = os.path.join(elsewhere, "victim")
        with open(victim, "wb") as handle:
            handle.write(b"keep")
        os.symlink(victim, os.path.join(self.folder, "googleearthprowin-x64.msi"))
        self.assertRejected(build_pe(standard_tree()), "is a link, which is refused")
        with open(victim, "rb") as handle:
            self.assertEqual(handle.read(), b"keep")
        self.assertTrue(os.path.islink(os.path.join(self.folder, "googleearthprowin-x64.msi")))

    def test_a_dangling_link_at_the_target_is_refused(self):
        os.symlink(os.path.join(self.folder, "nowhere"), os.path.join(self.folder, "googleearthprowin-x64.msi"))
        self.assertRejected(build_pe(standard_tree()), "is a link, which is refused")

    def test_a_folder_at_the_target_is_refused(self):
        os.mkdir(os.path.join(self.folder, "googleearthprowin-x64.msi"))
        self.assertRejected(build_pe(standard_tree()), "exists and is not a file")

    def test_a_pathname_that_is_already_an_msi_is_refused(self):
        exe = self.write(build_pe(standard_tree()), name="googleearthprowin-x64.msi")
        processor, _ = new_processor(PROCESSOR, {"pathname": exe})
        with self.assertRaises(ProcessorError) as caught:
            processor.main()
        self.assertIn("would replace the EXE itself", str(caught.exception))

    def test_a_failure_while_writing_leaves_no_file(self):
        exe = self.write(build_pe(standard_tree()))
        processor, _ = new_processor(PROCESSOR, {"pathname": exe})
        with mock.patch.object(extractor.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        self.assertIn("disk full", str(caught.exception))
        self.assertEqual(os.listdir(self.folder), ["googleearthprowin-x64.exe"])
        self.assertEqual(processor.env, {"pathname": exe})


if __name__ == "__main__":
    unittest.main()
