"""Tests of WindowsExeVersion.

No real EXE is committed. The tests build a small PE file in a temporary
folder, with the layout of a real one: a DOS header, a PE header, an optional
header with its data directories, a section table, and a resource section that
holds the resource directory tree (root, RT_VERSION, name, language, data
entry) and a VS_VERSIONINFO block. Everything is written with `struct`.

The real values that the layout was checked against (read from two real files
with an independent tool): a PE32+ file with fixed versions of 4, 33, 0 and 0,
the strings `4.33`, and the product name `BGInfo`; a PE32 file with fixed
versions of 14, 44, 35211 and 0, the strings `14.44.35211.0`, and a long
product name with parentheses. Numbers are written as tuples and joined here,
because a four-part number with small parts looks like an address to the scan
of `test_public_repository.py`.

An optional test reads real files: see RealSamplesTests.
"""
import os
import struct
import tempfile
import unittest
from unittest import mock

from _win_support import ProcessorError, exe_version, new_processor, run_processor

PROCESSOR = exe_version.WindowsExeVersion
HIGH = 0x80000000
SIGNATURE = 0xFEEF04BD
MAX_BYTES = exe_version.MAX_VERSION_BYTES

SMALL_NUMBERS = (4, 33, 0, 0)
LONG_NUMBERS = (14, 44, 35211, 0)
OTHER_NUMBERS = (1, 2, 3000, 4)
ZERO_NUMBERS = (0, 0, 0, 0)


def dotted(numbers):
    return ".".join(str(n) for n in numbers)


def pad4(data):
    return bytes(data) + b"\0" * (-len(data) % 4)


def utf16(text):
    return text.encode("utf-16-le")


# ---- the version block ------------------------------------------------------

def block(key, value=b"", value_length=None, wtype=1, children=(), length=None):
    """One block of a VS_VERSIONINFO structure. The length is the real one,
    without the padding after the block, unless `length` says otherwise."""
    out = bytearray(6) + utf16(key) + b"\0\0"
    out = bytearray(pad4(out))
    out += value
    for child in children:
        out = bytearray(pad4(out))
        out += child
    if value_length is None:
        value_length = len(value)
    struct.pack_into("<HHH", out, 0, len(out) if length is None else length, value_length, wtype)
    return bytes(out)


def string_block(key, text, **kwargs):
    value = utf16(text + "\0")
    kwargs.setdefault("value_length", len(text) + 1)
    return block(key, value=value, **kwargs)


def fixed_file_info(file_numbers, product_numbers, signature=SIGNATURE):
    def pack(numbers):
        a, b, c, d = numbers
        return (a << 16) | b, (c << 16) | d

    file_ms, file_ls = pack(file_numbers)
    product_ms, product_ls = pack(product_numbers)
    return struct.pack(
        "<13I", signature, 0x10000, file_ms, file_ls, product_ms, product_ls,
        0x3F, 0, 0x4, 1, 0, 0, 0,
    )


def default_strings(product, file, name):
    strings = {
        "CompanyName": "Example Corp",
        "FileDescription": "Example application",
        "FileVersion": file,
        "InternalName": "example",
        "ProductName": name,
        "ProductVersion": product,
    }
    return {key: value for key, value in strings.items() if value is not None}


def version_info(product="4.33", file="4.33", name="BGInfo", file_numbers=SMALL_NUMBERS,
                 product_numbers=SMALL_NUMBERS, strings=None, tables=None, signature=SIGNATURE,
                 root_key="VS_VERSION_INFO", string_info=True, root_length=None):
    """A complete VS_VERSIONINFO block. `tables` is a list of (key, strings)
    and replaces the one default table."""
    if tables is None:
        tables = [("040904B0", strings if strings is not None else default_strings(product, file, name))]
    children = []
    if string_info:
        table_blocks = [
            block(key, children=[string_block(k, v) for k, v in table.items()], value_length=0)
            for key, table in tables
        ]
        children.append(block("StringFileInfo", children=table_blocks, value_length=0))
    children.append(
        block("VarFileInfo", value_length=0, children=[
            block("Translation", value=struct.pack("<HH", 0x409, 0x4B0), wtype=0)
        ])
    )
    return block(
        root_key, value=fixed_file_info(file_numbers, product_numbers, signature),
        value_length=52, wtype=0, children=children, length=root_length,
    )


# ---- the PE file ------------------------------------------------------------

PE_OFFSET = 0x80
OPTIONAL_OFFSET = PE_OFFSET + 4 + 20
TEXT_VIRTUAL_ADDRESS = 0x1000
TEXT_RAW_BYTES = 0x200


def directory_header(named, ids):
    return struct.pack("<IIHHHH", 0, 0, 0, 0, named, ids)


def resource_tree(section_rva, blobs, data_padding=0, named_decoy=False, shape=None):
    """The resource section's content. `blobs` is a list of (type id, bytes) in
    the order of the root's entries. Each type has one name (id 1) with one
    language (0x409). `shape` changes one level, for the tests of a bad tree:
      "type-is-data"    the entry for the version type is a data entry
      "name-is-data"    the first name entry is a data entry
      "language-is-dir" the first language entry is a directory
      "empty-root"      the root has no entries
      "many-entries"    the root says that it has too many entries"""
    count = len(blobs)
    root_length = 16 + 8 * (count + (1 if named_decoy else 0))
    blob_offset = root_length + 64 * count
    root_entries = []
    body = bytearray()
    blob_area = bytearray()
    first_type_dir = root_length
    for index, (type_id, blob) in enumerate(blobs):
        base = root_length + 64 * index
        size = len(blob) + (data_padding if type_id == 16 else 0)
        data_offset = blob_offset + len(blob_area)
        blob_area += pad4(blob + b"\0" * (data_padding if type_id == 16 else 0))
        language_entry = HIGH | (base + 48) if shape == "language-is-dir" and type_id == 16 else base + 48
        type_dir = directory_header(0, 1) + struct.pack(
            "<II", 1, (base + 24) if shape == "name-is-data" and type_id == 16 else HIGH | (base + 24)
        )
        name_dir = directory_header(0, 1) + struct.pack("<II", 0x409, language_entry)
        data_entry = struct.pack("<IIII", section_rva + data_offset, size, 0, 0)
        body += type_dir + name_dir + data_entry
        entry_target = base if shape == "type-is-data" and type_id == 16 else HIGH | base
        root_entries.append((type_id, entry_target))
    named = 0
    if named_decoy:
        # A named entry whose low bits are 16, pointing at the first type
        # (not the version type). It comes first, as named entries do.
        root_entries.insert(0, (HIGH | RT_VERSION_ID, HIGH | first_type_dir))
        named = 1
    root = directory_header(named, count)
    for name, target in root_entries:
        root += struct.pack("<II", name, target)
    if shape == "empty-root":
        root = directory_header(0, 0)
    if shape == "many-entries":
        root = directory_header(0, 0xFFFF) + root[16:]
    return bytes(root) + bytes(body) + bytes(blob_area)


RT_VERSION_ID = 16


class BuiltPe:
    def __init__(self, data, rsrc_offset):
        self.data = bytearray(data)
        self.rsrc_offset = rsrc_offset


def build_pe(version, plus=False, types=(16,), padded=True, text_size=TEXT_RAW_BYTES,
             directory_count=16, resource_entry=True, magic=None, section_count=None,
             data_padding=0, named_decoy=False, shape=None, rsrc_virtual_size=None,
             rsrc_raw_extra=0, blob_for_other=b"junk-data"):
    """A PE file with a .text section and a .rsrc section. `version` is the
    VS_VERSIONINFO block (a type-16 resource); other types get junk."""
    blobs = []
    for type_id in types:
        blobs.append((type_id, version if type_id == 16 else blob_for_other))
    # The resources follow the .text section in the address space too.
    rsrc_address = TEXT_VIRTUAL_ADDRESS + ((text_size + 0xFFF) & ~0xFFF)
    rsrc = resource_tree(rsrc_address, blobs, data_padding, named_decoy, shape)
    rsrc += b"\0" * rsrc_raw_extra
    raw_size = (len(rsrc) + 0x1FF) & ~0x1FF if padded else len(rsrc)
    rsrc_padded = rsrc + b"\0" * (raw_size - len(rsrc))

    optional_fixed = 112 if plus else 96
    chosen_magic = magic if magic is not None else (0x20B if plus else 0x10B)
    optional = bytearray(optional_fixed)
    struct.pack_into("<H", optional, 0, chosen_magic)
    struct.pack_into("<I", optional, optional_fixed - 4, directory_count)
    directories = bytearray(16 * 8)
    if resource_entry:
        struct.pack_into("<II", directories, 8 * 2, rsrc_address, len(rsrc))
    optional = bytes(optional) + bytes(directories)

    text_offset = 0x200
    rsrc_offset = text_offset + text_size
    sections = [
        (b".text\0\0\0", min(text_size, 0x100), TEXT_VIRTUAL_ADDRESS, text_size, text_offset),
        (b".rsrc\0\0\0", rsrc_virtual_size if rsrc_virtual_size is not None else len(rsrc),
         rsrc_address, raw_size, rsrc_offset),
    ]
    table = b"".join(
        struct.pack("<8sIIIIIIHHI", name, vsize, va, rsize, roff, 0, 0, 0, 0, 0x40000040)
        for name, vsize, va, rsize, roff in sections
    )
    coff = struct.pack(
        "<HHIIIHH", 0x8664 if plus else 0x14C,
        len(sections) if section_count is None else section_count, 0, 0, 0, len(optional), 0x22,
    )
    dos = bytearray(PE_OFFSET)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, PE_OFFSET)
    headers = bytes(dos) + b"PE\0\0" + coff + optional + table
    headers += b"\0" * (text_offset - len(headers))
    # The .text section is a hole in a real sparse file; here it is zeros.
    data = headers + b"\0" * text_size + rsrc_padded
    return BuiltPe(data, rsrc_offset)


class ExeTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="win-exe-version-")
        self.addCleanup(self._tmp.cleanup)
        self.folder = os.path.realpath(self._tmp.name)
        self.counter = 0

    def write(self, data, name=None):
        self.counter += 1
        path = os.path.join(self.folder, name or "setup%d.exe" % self.counter)
        with open(path, "wb") as handle:
            handle.write(bytes(data))
        return path

    def read(self, built, **env):
        """Run the processor on a built file (or on raw bytes). Returns the
        processor."""
        data = built.data if isinstance(built, BuiltPe) else built
        values = {"pathname": self.write(data)}
        values.update(env)
        processor, _ = run_processor(PROCESSOR, values)
        return processor

    def assertRejected(self, built, fragment, **env):
        data = built.data if isinstance(built, BuiltPe) else built
        values = {"pathname": self.write(data)}
        values.update(env)
        processor, _ = new_processor(PROCESSOR, values)
        with self.assertRaises(ProcessorError) as caught:
            processor.main()
        self.assertIn(fragment, str(caught.exception))
        for key in ("exe_product_version", "exe_file_version", "version", "exe_product_name"):
            self.assertNotIn(key, processor.env)
        return str(caught.exception)


class ReadingTests(ExeTestCase):
    def test_pe32_with_four_part_strings(self):
        pe = build_pe(version_info(
            product="14.44.35211.0", file="14.44.35211.0",
            name="Example Redistributable (x64) - 14.44.35211",
            file_numbers=LONG_NUMBERS, product_numbers=LONG_NUMBERS,
        ))
        env = self.read(pe).env
        self.assertEqual(env["exe_product_version"], "14.44.35211.0")
        self.assertEqual(env["exe_file_version"], "14.44.35211.0")
        self.assertEqual(env["exe_product_version_numbers"], dotted(LONG_NUMBERS))
        self.assertEqual(env["exe_file_version_numbers"], dotted(LONG_NUMBERS))
        self.assertEqual(env["exe_product_name"], "Example Redistributable (x64) - 14.44.35211")
        self.assertEqual(env["version"], "14.44.35211.0")

    def test_pe32_plus_with_two_part_strings(self):
        pe = build_pe(version_info(), plus=True)
        env = self.read(pe).env
        self.assertEqual(env["exe_product_version"], "4.33")
        self.assertEqual(env["exe_file_version"], "4.33")
        self.assertEqual(env["exe_product_version_numbers"], dotted(SMALL_NUMBERS))
        self.assertEqual(env["exe_file_version_numbers"], dotted(SMALL_NUMBERS))
        self.assertEqual(env["exe_product_name"], "BGInfo")
        self.assertEqual(env["version"], "4.33")

    def test_both_layouts_read_the_same_facts(self):
        info = version_info()
        a = self.read(build_pe(info, plus=False)).env
        b = self.read(build_pe(info, plus=True)).env
        for key in ("exe_product_version", "exe_file_version", "exe_product_version_numbers",
                    "exe_file_version_numbers", "exe_product_name", "version"):
            self.assertEqual(a[key], b[key], key)

    def test_file_and_product_versions_are_kept_apart(self):
        pe = build_pe(version_info(
            product="1.2", file="3.4.5000.6", file_numbers=(3, 4, 5000, 6), product_numbers=(1, 2, 0, 0),
        ))
        env = self.read(pe).env
        self.assertEqual(env["exe_product_version"], "1.2")
        self.assertEqual(env["exe_file_version"], "3.4.5000.6")
        self.assertEqual(env["exe_product_version_numbers"], dotted((1, 2, 0, 0)))
        self.assertEqual(env["exe_file_version_numbers"], dotted((3, 4, 5000, 6)))
        self.assertEqual(env["version"], "1.2")

    def test_the_four_numbers_are_split_as_major_minor_build_revision(self):
        pe = build_pe(version_info(product_numbers=(65535, 1, 65534, 2), file_numbers=(2, 65535, 3, 65535)))
        env = self.read(pe).env
        self.assertEqual(env["exe_product_version_numbers"], dotted((65535, 1, 65534, 2)))
        self.assertEqual(env["exe_file_version_numbers"], dotted((2, 65535, 3, 65535)))

    def test_a_product_version_with_text_makes_version_fall_back_to_the_numbers(self):
        for text in ("4.33 (x64)", "v4.33", "4.33-beta", "4.33.", "4..33", "", " "):
            with self.subTest(product=text):
                pe = build_pe(version_info(product=text, file="4.33", product_numbers=OTHER_NUMBERS))
                env = self.read(pe).env
                self.assertEqual(env["exe_product_version"], text.strip())
                self.assertEqual(env["version"], dotted(OTHER_NUMBERS))

    def test_a_leading_zero_is_kept(self):
        pe = build_pe(version_info(product="26.03", file="26.03", product_numbers=(26, 3, 0, 0)))
        env = self.read(pe).env
        self.assertEqual(env["exe_product_version"], "26.03")
        self.assertEqual(env["version"], "26.03")

    def test_digits_that_are_not_ascii_do_not_count_as_numbers(self):
        pe = build_pe(version_info(product="٤.٣", file="1.0", product_numbers=OTHER_NUMBERS))
        self.assertEqual(self.read(pe).env["version"], dotted(OTHER_NUMBERS))

    def test_a_single_number_is_a_label(self):
        pe = build_pe(version_info(product="7", file="7"))
        self.assertEqual(self.read(pe).env["version"], "7")

    def test_set_version_false_leaves_version_alone(self):
        pe = build_pe(version_info())
        processor = self.read(pe, set_version=False)
        self.assertNotIn("version", processor.env)
        self.assertEqual(processor.env["exe_product_version"], "4.33")

    def test_set_version_false_does_not_change_a_version_that_is_set(self):
        pe = build_pe(version_info())
        processor = self.read(pe, set_version="no", version="earlier")
        self.assertEqual(processor.env["version"], "earlier")

    def test_set_version_true_replaces_a_version_that_is_set(self):
        pe = build_pe(version_info())
        processor = self.read(pe, set_version="True", version="earlier")
        self.assertEqual(processor.env["version"], "4.33")

    def test_set_version_is_true_by_default(self):
        self.assertTrue(PROCESSOR.input_variables["set_version"]["default"])
        self.assertIn("version", self.read(build_pe(version_info())).env)

    def test_set_version_must_be_a_boolean_or_its_text(self):
        pe = build_pe(version_info())
        for value in ("maybe", "", 2, None, [], "off"):
            with self.subTest(value=value):
                self.assertRejected(pe, "set_version must be true or false", set_version=value)

    def test_values_are_stripped_and_end_at_the_null(self):
        strings = {
            "FileVersion": "  1.0 ",
            "ProductVersion": " \t4.33\r\n",
            "ProductName": "  Example  ",
        }
        env = self.read(build_pe(version_info(strings=strings))).env
        self.assertEqual(env["exe_product_version"], "4.33")
        self.assertEqual(env["exe_file_version"], "1.0")
        self.assertEqual(env["exe_product_name"], "Example")
        # Text after the null is not part of the value.
        table = block("040904B0", value_length=0, children=[
            string_block("ProductVersion", "5.0\0junk after the null", value_length=30),
        ])
        info = block("VS_VERSION_INFO", value=fixed_file_info(SMALL_NUMBERS, SMALL_NUMBERS), value_length=52,
                     wtype=0, children=[block("StringFileInfo", value_length=0, children=[table])])
        self.assertEqual(self.read(build_pe(info)).env["exe_product_version"], "5.0")

    def test_a_value_length_in_bytes_instead_of_characters_is_cut_at_the_block(self):
        text = "4.33"
        table = block("040904B0", value_length=0, children=[
            string_block("ProductVersion", text, value_length=2 * (len(text) + 1)),
            string_block("FileVersion", text, value_length=0),
        ])
        info = block("VS_VERSION_INFO", value=fixed_file_info(SMALL_NUMBERS, SMALL_NUMBERS), value_length=52,
                     wtype=0, children=[block("StringFileInfo", value_length=0, children=[table])])
        env = self.read(build_pe(info)).env
        self.assertEqual(env["exe_product_version"], "4.33")
        self.assertEqual(env["exe_file_version"], "")

    def test_text_that_is_not_ascii_is_read(self):
        pe = build_pe(version_info(name="Café 日本 \U0001F600"))
        self.assertEqual(self.read(pe).env["exe_product_name"], "Café 日本 \U0001F600")

    def test_text_that_is_not_valid_utf16_is_an_error(self):
        table = block("040904B0", value_length=0, children=[
            block("ProductVersion", value=b"\x00\xd8\0\0", value_length=2),
        ])
        info = block("VS_VERSION_INFO", value=fixed_file_info(SMALL_NUMBERS, SMALL_NUMBERS), value_length=52,
                     wtype=0, children=[block("StringFileInfo", value_length=0, children=[table])])
        self.assertRejected(build_pe(info), "not valid UTF-16")

    def test_the_first_string_table_is_the_one_that_is_read(self):
        tables = [
            ("040904B0", {"ProductVersion": "1.0", "FileVersion": "1.1", "ProductName": "First"}),
            ("000004B0", {"ProductVersion": "2.0", "FileVersion": "2.1", "ProductName": "Second"}),
        ]
        env = self.read(build_pe(version_info(tables=tables))).env
        self.assertEqual((env["exe_product_version"], env["exe_file_version"], env["exe_product_name"]),
                         ("1.0", "1.1", "First"))

    def test_the_first_of_two_strings_with_one_key_is_the_one_that_is_read(self):
        table = block("040904B0", value_length=0, children=[
            string_block("ProductVersion", "1.0"), string_block("ProductVersion", "2.0"),
        ])
        info = block("VS_VERSION_INFO", value=fixed_file_info(SMALL_NUMBERS, SMALL_NUMBERS), value_length=52,
                     wtype=0, children=[block("StringFileInfo", value_length=0, children=[table])])
        self.assertEqual(self.read(build_pe(info)).env["exe_product_version"], "1.0")

    def test_a_key_is_matched_exactly(self):
        strings = {"productversion": "9.9", "ProductVersion ": "8.8", "FileVersion": "1.0"}
        env = self.read(build_pe(version_info(strings=strings))).env
        self.assertEqual(env["exe_product_version"], "")
        self.assertEqual(env["exe_file_version"], "1.0")

    def test_only_a_file_version_gives_an_empty_product_version_and_the_numbers_as_label(self):
        strings = {"FileVersion": "3.0.1", "ProductName": "Example"}
        env = self.read(build_pe(version_info(strings=strings, product_numbers=OTHER_NUMBERS))).env
        self.assertEqual(env["exe_product_version"], "")
        self.assertEqual(env["exe_file_version"], "3.0.1")
        self.assertEqual(env["version"], dotted(OTHER_NUMBERS))

    def test_only_a_product_version_gives_an_empty_file_version(self):
        strings = {"ProductVersion": "3.0.1"}
        env = self.read(build_pe(version_info(strings=strings))).env
        self.assertEqual(env["exe_file_version"], "")
        self.assertEqual(env["exe_product_name"], "")
        self.assertEqual(env["version"], "3.0.1")

    def test_a_missing_product_name_is_an_empty_string(self):
        env = self.read(build_pe(version_info(name=None))).env
        self.assertEqual(env["exe_product_name"], "")

    def test_the_resource_is_found_when_it_is_not_the_first_type(self):
        pe = build_pe(version_info(), types=(3, 6, 16, 24))
        self.assertEqual(self.read(pe).env["exe_product_version"], "4.33")

    def test_a_named_entry_is_never_the_version_type(self):
        pe = build_pe(version_info(), types=(3, 16), named_decoy=True)
        self.assertEqual(self.read(pe).env["exe_product_version"], "4.33")

    def test_a_resource_section_that_is_not_the_first_is_mapped(self):
        # build_pe puts the resources after a .text section: the address is
        # not the file offset. A bigger .text moves the file offset only.
        for text_size in (0x200, 0x600, 0x1000):
            with self.subTest(text_size=text_size):
                pe = build_pe(version_info(), text_size=text_size)
                self.assertEqual(self.read(pe).env["exe_product_version"], "4.33")

    def test_an_unpadded_section_and_a_padded_one_read_the_same(self):
        info = version_info()
        a = self.read(build_pe(info, padded=True)).env["exe_product_version"]
        b = self.read(build_pe(info, padded=False)).env["exe_product_version"]
        self.assertEqual(a, b)

    def test_a_virtual_size_that_is_smaller_than_the_raw_size_still_maps(self):
        pe = build_pe(version_info(), rsrc_virtual_size=0x10)
        self.assertEqual(self.read(pe).env["exe_product_version"], "4.33")

    def test_bytes_after_the_root_block_are_ignored(self):
        pe = build_pe(version_info(), data_padding=100)
        self.assertEqual(self.read(pe).env["exe_product_version"], "4.33")

    def test_the_file_is_not_changed_and_nothing_is_written_beside_it(self):
        pe = build_pe(version_info())
        path = self.write(pe.data, "keep.exe")
        with open(path, "rb") as handle:
            before = handle.read()
        listing = sorted(os.listdir(self.folder))
        mtime = os.stat(path).st_mtime_ns
        run_processor(PROCESSOR, {"pathname": path})
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), before)
        self.assertEqual(sorted(os.listdir(self.folder)), listing)
        self.assertEqual(os.stat(path).st_mtime_ns, mtime)

    def test_the_processor_uses_no_program_and_no_network(self):
        for name in ("subprocess", "socket", "urllib", "http", "ctypes"):
            self.assertFalse(hasattr(exe_version, name), name)

    def test_the_message_names_the_versions_and_where_the_label_came_from(self):
        pe = build_pe(version_info(product="4.33 (x64)", product_numbers=OTHER_NUMBERS))
        path = self.write(pe.data, "Example.exe")
        _processor, messages = run_processor(PROCESSOR, {"pathname": path})
        text = "\n".join(messages)
        self.assertIn("Example.exe", text)
        self.assertIn("4.33 (x64)", text)
        self.assertIn("the numbers of the fixed file information", text)
        self.assertNotIn(self.folder, text)


class ZeroLabelTests(ExeTestCase):
    """A label of zeros is not a version. An installer built with no version set
    can say zeros in both places, and one built with a text version (a .NET
    informational version, say) can say text in the string and zeros in the
    numbers. Such a label is refused, not published."""

    ZEROS = dotted(ZERO_NUMBERS)

    def test_text_in_the_product_version_and_zeros_in_the_numbers_is_refused(self):
        text = "10.0.7-servicing.26217.108+0123456789abcdef"
        pe = build_pe(version_info(product=text, file="10.0.7", product_numbers=ZERO_NUMBERS,
                                   file_numbers=ZERO_NUMBERS))
        message = self.assertRejected(pe, "a label of zeros is not a version")
        self.assertIn("the version label would be %s" % self.ZEROS, message)
        self.assertIn("taken from the numbers of the fixed file information", message)
        self.assertIn(repr(text), message)
        self.assertIn("FileVersion '10.0.7'", message)
        self.assertIn("file version numbers %s" % self.ZEROS, message)

    def test_a_product_version_of_zeros_is_refused_whatever_the_numbers_say(self):
        for text in ("0", "0.0", "00.00", "0.0.0", self.ZEROS, "0" * 5000):
            with self.subTest(product=text[:20]):
                pe = build_pe(version_info(product=text, file=text, product_numbers=OTHER_NUMBERS))
                message = self.assertRejected(pe, "a label of zeros is not a version")
                self.assertIn("taken from the ProductVersion string", message)

    def test_zero_numbers_with_no_product_version_are_refused(self):
        strings = {"FileVersion": dotted(OTHER_NUMBERS), "ProductName": "Example"}
        pe = build_pe(version_info(strings=strings, product_numbers=ZERO_NUMBERS))
        message = self.assertRejected(pe, "a label of zeros is not a version")
        self.assertIn("ProductVersion ''", message)
        self.assertIn("FileVersion %r" % dotted(OTHER_NUMBERS), message)

    def test_a_refused_label_sets_nothing_and_leaves_an_earlier_version_alone(self):
        pe = build_pe(version_info(product="4.33 (x64)", product_numbers=ZERO_NUMBERS))
        processor, _ = new_processor(PROCESSOR, {"pathname": self.write(pe.data), "version": "earlier"})
        with self.assertRaises(ProcessorError):
            processor.main()
        self.assertEqual(processor.env["version"], "earlier")
        for key in ("exe_product_version", "exe_file_version", "exe_product_version_numbers",
                    "exe_file_version_numbers", "exe_product_name"):
            self.assertNotIn(key, processor.env)

    def test_set_version_false_does_not_choose_a_label_and_so_does_not_refuse_one(self):
        pe = build_pe(version_info(product="4.33 (x64)", product_numbers=ZERO_NUMBERS))
        processor = self.read(pe, set_version=False)
        self.assertNotIn("version", processor.env)
        self.assertEqual(processor.env["exe_product_version"], "4.33 (x64)")
        self.assertEqual(processor.env["exe_product_version_numbers"], self.ZEROS)

    def test_one_digit_other_than_zero_is_enough(self):
        cases = [
            ("4.33 (x64)", (0, 0, 0, 1), dotted((0, 0, 0, 1))),
            ("4.33 (x64)", (0, 0, 1, 0), dotted((0, 0, 1, 0))),
            ("0.9", OTHER_NUMBERS, "0.9"),
            ("0.0.1", ZERO_NUMBERS, "0.0.1"),
            ("10.0", ZERO_NUMBERS, "10.0"),
            ("0" * 5000 + "1", ZERO_NUMBERS, "0" * 5000 + "1"),
        ]
        for text, numbers, label in cases:
            with self.subTest(product=text[:20], numbers=numbers):
                pe = build_pe(version_info(product=text, file=text, product_numbers=numbers))
                self.assertEqual(self.read(pe).env["version"], label)

    def test_the_message_is_short_whatever_the_file_says(self):
        for text in ("x" * 5000, "0" * 5000):
            with self.subTest(product=text[:3]):
                pe = build_pe(version_info(product=text, file=text, product_numbers=ZERO_NUMBERS))
                message = self.assertRejected(pe, "a label of zeros is not a version")
                self.assertLess(len(message), 600)

    def test_the_run_stops_with_a_processor_error_and_names_the_file(self):
        path = self.write(build_pe(version_info(product="x", product_numbers=ZERO_NUMBERS)).data, "Example.exe")
        processor, _ = new_processor(PROCESSOR, {"pathname": path})
        with self.assertRaises(ProcessorError) as caught:
            processor.main()
        self.assertTrue(str(caught.exception).startswith("Example.exe: the version label would be "))
        self.assertTrue(str(caught.exception).endswith("."))
        self.assertNotIn(self.folder, str(caught.exception))


class ErrorTests(ExeTestCase):
    def test_a_file_that_does_not_exist(self):
        processor, _ = new_processor(PROCESSOR, {"pathname": os.path.join(self.folder, "missing.exe")})
        with self.assertRaises(ProcessorError) as caught:
            processor.main()
        self.assertIn("not a file", str(caught.exception))

    def test_a_folder_and_a_missing_or_empty_pathname(self):
        for env in ({"pathname": self.folder}, {}, {"pathname": ""}, {"pathname": None}, {"pathname": 5}):
            with self.subTest(env=env):
                processor, _ = new_processor(PROCESSOR, env)
                with self.assertRaises(ProcessorError):
                    processor.main()

    def test_a_file_that_cannot_be_read_is_an_error(self):
        path = self.write(build_pe(version_info()).data)
        with mock.patch("builtins.open", side_effect=PermissionError("denied")):
            processor, _ = new_processor(PROCESSOR, {"pathname": path})
            with self.assertRaises(ProcessorError) as caught:
                processor.main()
        self.assertIn("Could not read", str(caught.exception))

    def test_a_file_that_is_not_a_pe_file(self):
        for label, data in {
            "empty": b"",
            "text": b"This is not an executable file.\n" * 10,
            "one byte": b"M",
            "msi header": bytes.fromhex("d0cf11e0a1b11ae1") + b"\0" * 600,
            "zip": b"PK\x03\x04" + b"\0" * 600,
        }.items():
            with self.subTest(file=label):
                self.assertRejected(data, "")

    def test_mz_without_a_pe_header(self):
        data = bytearray(build_pe(version_info()).data)
        data[PE_OFFSET:PE_OFFSET + 4] = b"PX\0\0"
        self.assertRejected(data, "no PE signature")
        data = bytearray(build_pe(version_info()).data)
        data[0:2] = b"ZM"
        self.assertRejected(data, "no MZ header")

    def test_a_pe_offset_that_is_wrong(self):
        for offset in (0, 0x20, 0x3C, 0xFFFFFFF0, 0x7FFFFFFF, 0x100000):
            with self.subTest(offset=hex(offset)):
                data = bytearray(build_pe(version_info()).data)
                struct.pack_into("<I", data, 0x3C, offset)
                self.assertRejected(data, "")

    def test_an_optional_header_that_is_not_pe32_or_pe32_plus(self):
        self.assertRejected(build_pe(version_info(), magic=0x107), "not a PE32 or PE32+ file")
        self.assertRejected(build_pe(version_info(), magic=0), "not a PE32 or PE32+ file")

    def test_the_file_has_no_resource_directory(self):
        self.assertRejected(build_pe(version_info(), resource_entry=False), "no resource directory")
        self.assertRejected(build_pe(version_info(), plus=True, resource_entry=False), "no resource directory")

    def test_too_few_data_directories_mean_no_resource_directory(self):
        for count in (0, 1, 2):
            with self.subTest(count=count):
                self.assertRejected(build_pe(version_info(), directory_count=count), "no resource directory")

    def test_an_optional_header_that_is_too_short(self):
        data = bytearray(build_pe(version_info()).data)
        struct.pack_into("<H", data, PE_OFFSET + 4 + 16, 40)
        self.assertRejected(data, "too short")
        data = bytearray(build_pe(version_info()).data)
        struct.pack_into("<H", data, PE_OFFSET + 4 + 16, 0)
        self.assertRejected(data, "no optional header")
        data = bytearray(build_pe(version_info()).data)
        struct.pack_into("<H", data, PE_OFFSET + 4 + 16, 96 + 16)
        self.assertRejected(data, "no resource directory")

    def test_sections_that_are_missing_or_too_many(self):
        self.assertRejected(build_pe(version_info(), section_count=0), "no sections")
        self.assertRejected(build_pe(version_info(), section_count=97), "97 sections")
        self.assertRejected(build_pe(version_info(), section_count=96), "")
        self.assertRejected(build_pe(version_info(), section_count=0xFFFF), "sections")

    def test_a_resource_address_that_no_section_holds(self):
        data = bytearray(build_pe(version_info()).data)
        struct.pack_into("<I", data, OPTIONAL_OFFSET + 96 + 16, 0x9000)
        self.assertRejected(data, "no section holds")
        data = bytearray(build_pe(version_info()).data)
        struct.pack_into("<I", data, OPTIONAL_OFFSET + 96 + 16, 0xFFFFFFFF)
        self.assertRejected(data, "no section holds")

    def test_the_file_has_no_version_resource(self):
        self.assertRejected(build_pe(version_info(), types=(3,)), "no version resource")
        self.assertRejected(build_pe(version_info(), types=(3, 6, 24)), "no version resource")
        self.assertRejected(build_pe(version_info(), types=(17,)), "no version resource")

    def test_a_tree_that_is_not_built_as_expected(self):
        cases = {
            "type-is-data": "not a directory",
            "name-is-data": "not a directory",
            "language-is-dir": "not a data entry",
            "empty-root": "no entries",
            "many-entries": "entries (at most",
        }
        for shape, fragment in cases.items():
            with self.subTest(shape=shape):
                self.assertRejected(build_pe(version_info(), shape=shape), fragment)

    def test_a_wrong_signature_of_the_fixed_file_information(self):
        for signature in (0, 0xFEEF04BC, 0xBD04EFFE):
            with self.subTest(signature=hex(signature)):
                self.assertRejected(build_pe(version_info(signature=signature)), "signature")

    def test_a_root_block_with_another_key(self):
        self.assertRejected(build_pe(version_info(root_key="VS_VERSION_INFX")), "does not start with")
        self.assertRejected(build_pe(version_info(root_key="")), "does not start with")

    def test_a_root_block_without_fixed_file_information(self):
        info = block("VS_VERSION_INFO", value_length=0, wtype=0)
        self.assertRejected(build_pe(info), "fixed file information")
        info = block("VS_VERSION_INFO", value=b"\0" * 20, value_length=20, wtype=0)
        self.assertRejected(build_pe(info), "fixed file information")

    def test_a_string_file_info_that_is_missing_or_empty(self):
        self.assertRejected(build_pe(version_info(string_info=False)), "no StringFileInfo")
        info = block("VS_VERSION_INFO", value=fixed_file_info(SMALL_NUMBERS, SMALL_NUMBERS), value_length=52,
                     wtype=0, children=[block("StringFileInfo", value_length=0)])
        self.assertRejected(build_pe(info), "no StringFileInfo")

    def test_a_string_table_without_a_product_version_and_a_file_version(self):
        for strings in ({}, {"ProductName": "Example"}, {"ProductVersion": "", "FileVersion": "  "}):
            with self.subTest(strings=strings):
                self.assertRejected(
                    build_pe(version_info(strings=strings)), "no ProductVersion and no FileVersion"
                )

    def test_a_string_table_key_that_is_not_eight_hex_digits(self):
        for key in ("0409", "040904B0X", "040904G0", "English", ""):
            with self.subTest(key=key):
                tables = [(key, {"ProductVersion": "1.0"})]
                self.assertRejected(build_pe(version_info(tables=tables)), "8 hex digits")

    def test_only_the_first_string_table_counts_for_the_error(self):
        tables = [("040904B0", {"ProductName": "x"}), ("000004B0", {"ProductVersion": "2.0"})]
        self.assertRejected(build_pe(version_info(tables=tables)), "no ProductVersion and no FileVersion")

    def test_a_block_whose_length_is_too_long(self):
        good = version_info()
        for extra in (1, 4, 100):
            with self.subTest(extra=extra):
                self.assertRejected(build_pe(version_info(root_length=len(good) + extra)), "out of bounds")

    def test_a_block_whose_length_is_too_short(self):
        good = version_info()
        for length in (0, 5, 6, 12, 40, 60, len(good) // 2):
            with self.subTest(length=length):
                info = version_info(root_length=length)
                data = build_pe(info).data
                processor, _ = new_processor(PROCESSOR, {"pathname": self.write(data)})
                with self.assertRaises(ProcessorError):
                    processor.main()

    def test_a_child_that_runs_past_its_parent(self):
        table = block("040904B0", value_length=0, children=[
            string_block("ProductVersion", "4.33", length=200),
        ])
        info = block("VS_VERSION_INFO", value=fixed_file_info(SMALL_NUMBERS, SMALL_NUMBERS), value_length=52,
                     wtype=0, children=[block("StringFileInfo", value_length=0, children=[table])])
        self.assertRejected(build_pe(info), "out of bounds")

    def test_a_child_with_a_length_below_the_header(self):
        for length in (0, 2, 5):
            with self.subTest(length=length):
                table = block("040904B0", value_length=0, children=[
                    string_block("ProductVersion", "4.33", length=length),
                ])
                info = block("VS_VERSION_INFO", value=fixed_file_info(SMALL_NUMBERS, SMALL_NUMBERS),
                             value_length=52, wtype=0,
                             children=[block("StringFileInfo", value_length=0, children=[table])])
                self.assertRejected(build_pe(info), "out of bounds")

    def test_bytes_after_the_last_child_that_are_not_padding_are_an_error(self):
        child = string_block("ProductVersion", "4.33")
        parent = pad4(child)
        # Zero bytes after the last child are padding.
        self.assertEqual(len(list(exe_version.children_of(parent + b"\0\0\0", 0, len(parent) + 3))), 1)
        # Other bytes, fewer than a block header, are not.
        with self.assertRaises(ValueError) as caught:
            list(exe_version.children_of(parent + b"\x01\x02\x03", 0, len(parent) + 3))
        self.assertIn("out of bounds", str(caught.exception))
        # Nor is a block header that does not fit.
        with self.assertRaises(ValueError):
            list(exe_version.children_of(parent + b"\x01" * 6, 0, len(parent) + 6 - 1))

    def test_a_key_without_an_end(self):
        info = bytearray(version_info())
        # Fill the root's key with non-null characters up to the end of the block.
        for index in range(6, len(info) - 1, 2):
            info[index:index + 2] = b"A\0"
        self.assertRejected(build_pe(bytes(info)), "no end")

    def test_a_value_that_runs_past_the_block(self):
        info = block("VS_VERSION_INFO", value=fixed_file_info(SMALL_NUMBERS, SMALL_NUMBERS), value_length=60,
                     wtype=0)
        self.assertRejected(build_pe(info), "out of bounds")

    def test_a_resource_that_is_too_small_for_a_block(self):
        for size in (1, 5, 10):
            with self.subTest(size=size):
                self.assertRejected(build_pe(b"\0" * size), "")

    def test_the_data_of_the_resource_must_lie_in_the_file(self):
        pe = build_pe(version_info(), padded=False)
        # The version data is the last thing in the file.
        for lost in (1, 10, 100):
            self.assertRejected(bytes(pe.data[:-lost]), "truncated")

    def test_every_truncation_of_a_good_file_is_an_error(self):
        pe = build_pe(version_info(), padded=False, text_size=0x200)
        full = bytes(pe.data)
        for length in range(len(full)):
            processor, _ = new_processor(PROCESSOR, {"pathname": self.write(full[:length], "cut.exe")})
            with self.assertRaises(ProcessorError, msg="length %d" % length):
                processor.main()
        # And the whole file is read.
        self.assertEqual(self.read(full).env["exe_product_version"], "4.33")

    def test_every_truncation_of_a_pe32_plus_file_is_an_error(self):
        pe = build_pe(version_info(), plus=True, padded=False, text_size=0x200)
        full = bytes(pe.data)
        for length in range(0, len(full), 3):
            processor, _ = new_processor(PROCESSOR, {"pathname": self.write(full[:length], "cut.exe")})
            with self.assertRaises(ProcessorError, msg="length %d" % length):
                processor.main()

    def test_any_damage_to_a_good_file_is_a_processor_error_or_a_read(self):
        """Flip each byte of the headers and the resource section in turn. The
        result is either facts or a ProcessorError, never another exception."""
        pe = build_pe(version_info(), padded=False, text_size=0x200)
        full = bytes(pe.data)
        positions = list(range(0, 0x200)) + list(range(pe.rsrc_offset, len(full)))
        for position in positions:
            for value in (0x00, 0xFF):
                damaged = bytearray(full)
                damaged[position] = value
                processor, _ = new_processor(PROCESSOR, {"pathname": self.write(damaged, "damaged.exe")})
                try:
                    processor.main()
                except ProcessorError:
                    pass

    def test_a_file_with_the_data_after_the_raw_size_of_its_section_is_an_error(self):
        # The section says that it has fewer raw bytes than the resource needs.
        pe = build_pe(version_info(), padded=False)
        table_offset = OPTIONAL_OFFSET + 96 + 16 * 8
        raw_size_of_rsrc = table_offset + 40 + 16
        struct.pack_into("<I", pe.data, raw_size_of_rsrc, 0x40)
        self.assertRejected(pe, "outside the raw data")


class SizeLimitTests(ExeTestCase):
    def test_a_resource_of_exactly_the_limit_is_read(self):
        info = version_info()
        pe = build_pe(info, data_padding=MAX_BYTES - len(info))
        self.assertEqual(self.read(pe).env["exe_product_version"], "4.33")

    def test_a_resource_of_one_byte_more_is_an_error(self):
        info = version_info()
        pe = build_pe(info, data_padding=MAX_BYTES - len(info) + 1)
        self.assertRejected(pe, "at most %d" % MAX_BYTES)

    def test_a_resource_that_claims_four_gigabytes_is_an_error_and_nothing_big_is_read(self):
        info = version_info()
        pe = build_pe(info)
        # The data entry sits after the three directories of the one type.
        entry_offset = pe.rsrc_offset + 16 + 8 + 24 + 24 + 4
        struct.pack_into("<I", pe.data, entry_offset, 0xFFFFFFFF)
        with mock.patch.object(exe_version, "read_exact", wraps=exe_version.read_exact) as spy:
            self.assertRejected(pe, "at most %d" % MAX_BYTES)
        self.assertLessEqual(max(call.args[3] for call in spy.call_args_list), 4096)

    def test_the_whole_file_is_never_read(self):
        info = version_info()
        pe = build_pe(info, text_size=8 * 1024 * 1024)
        path = self.write(pe.data)
        with mock.patch.object(exe_version, "read_exact", wraps=exe_version.read_exact) as spy:
            run_processor(PROCESSOR, {"pathname": path})
        sizes = [call.args[3] for call in spy.call_args_list]
        self.assertLess(sum(sizes), 8192)
        self.assertGreater(os.path.getsize(path), 8 * 1024 * 1024)

    def test_the_most_entries_of_a_directory_is_a_small_read(self):
        self.assertEqual(exe_version.MAX_DIRECTORY_ENTRIES * exe_version.RESOURCE_ENTRY_BYTES, 32768)

    def test_the_limits_are_the_documented_ones(self):
        self.assertEqual(exe_version.MAX_VERSION_BYTES, 1024 * 1024)
        self.assertEqual(exe_version.MAX_SECTIONS, 96)
        self.assertEqual(exe_version.RT_VERSION, 16)


class DeclarationTests(unittest.TestCase):
    def test_inputs(self):
        inputs = PROCESSOR.input_variables
        self.assertTrue(inputs["pathname"]["required"])
        self.assertFalse(inputs["set_version"]["required"])
        self.assertEqual(set(inputs), {"pathname", "set_version"})

    def test_outputs(self):
        self.assertEqual(
            set(PROCESSOR.output_variables),
            {"exe_product_version", "exe_file_version", "exe_product_version_numbers",
             "exe_file_version_numbers", "exe_product_name", "version"},
        )

    def test_choose_version(self):
        facts = {"exe_product_version": "1.2.3", "exe_product_version_numbers": dotted(OTHER_NUMBERS)}
        self.assertEqual(exe_version.choose_version(facts)[0], "1.2.3")
        facts["exe_product_version"] = "1.2.3 beta"
        self.assertEqual(exe_version.choose_version(facts)[0], dotted(OTHER_NUMBERS))
        facts["exe_product_version"] = "1.2.3\n"
        self.assertEqual(exe_version.choose_version(facts)[0], dotted(OTHER_NUMBERS))

    def test_choose_version_refuses_a_label_of_zeros(self):
        zeros = dotted(ZERO_NUMBERS)
        # the numbers are the label, and they are zeros
        facts = {"exe_product_version": "1.2.3 beta", "exe_product_version_numbers": zeros}
        with self.assertRaises(ValueError) as caught:
            exe_version.choose_version(facts)
        self.assertIn("a label of zeros is not a version", str(caught.exception))
        self.assertIn("taken from %s" % exe_version.SOURCE_NUMBERS, str(caught.exception))
        # the string is the label, and it is zeros, whatever the numbers say
        facts = {"exe_product_version": "0.0", "exe_product_version_numbers": dotted(OTHER_NUMBERS)}
        with self.assertRaises(ValueError) as caught:
            exe_version.choose_version(facts)
        self.assertIn("taken from %s" % exe_version.SOURCE_STRING, str(caught.exception))
        # a digit other than zero anywhere is a version
        facts = {"exe_product_version": "0.0.1", "exe_product_version_numbers": zeros}
        self.assertEqual(exe_version.choose_version(facts), ("0.0.1", exe_version.SOURCE_STRING))

    def test_the_file_ends_with_the_class_entry_point(self):
        with open(exe_version.__file__, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("class WindowsExeVersion(Processor):", text)
        self.assertIn("processor.execute_shell()", text)


SAMPLES = os.environ.get("WIN_EXE_SAMPLES", "")


@unittest.skipUnless(
    SAMPLES and os.path.isdir(SAMPLES),
    "set WIN_EXE_SAMPLES to a folder of <name>.exe files, each with a <name>.expected beside it",
)
class RealSamplesTests(unittest.TestCase):
    """Real files. For each `<name>.exe` in the folder with a `<name>.expected`
    beside it (lines such as `exe_product_version=4.33`), the outputs equal the
    expected values. Nothing is copied from the folder."""

    def pairs(self):
        found = []
        for entry in sorted(os.listdir(SAMPLES)):
            stem, extension = os.path.splitext(entry)
            expected = os.path.join(SAMPLES, stem + ".expected")
            if extension.lower() == ".exe" and os.path.isfile(expected):
                found.append((os.path.join(SAMPLES, entry), expected))
        return found

    @staticmethod
    def expected_values(path):
        values = {}
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.rstrip("\r\n")
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                key, separator, value = line.partition("=")
                if not separator:
                    raise AssertionError("not a key=value line in %s: %r" % (path, line))
                values[key.strip()] = value
        return values

    def test_the_outputs_equal_the_expected_values(self):
        pairs = self.pairs()
        self.assertTrue(pairs, "no <name>.exe with a <name>.expected in %s" % SAMPLES)
        for exe, expected in pairs:
            wanted = self.expected_values(expected)
            self.assertTrue(wanted, expected)
            with self.subTest(file=os.path.basename(exe)):
                processor, _ = run_processor(PROCESSOR, {"pathname": exe})
                for key, value in wanted.items():
                    self.assertIn(key, PROCESSOR.output_variables)
                    self.assertEqual(processor.env[key], value, key)


class RealSamplesFormatTests(unittest.TestCase):
    """The reader of the expected files, without any real file."""

    def test_the_expected_file_format(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "x.expected")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("# a comment\n\nexe_product_version=4.33\nexe_product_version_numbers=1.2.3000.4\n")
            self.assertEqual(
                RealSamplesTests.expected_values(path),
                {"exe_product_version": "4.33", "exe_product_version_numbers": "1.2.3000.4"},
            )


if __name__ == "__main__":
    unittest.main()
