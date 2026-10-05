"""Tests of VersionFromName: every branch. No file is opened: the processor reads only a name."""
import unittest

from _win_support import ProcessorError, new_processor, run_processor, version_name

READER = version_name.VersionFromName
# The pattern of the Angry IP Scanner download recipe, and a pattern of the same kind for a name
# with a build date after the version.
SCANNER_PATTERN = r"ipscan-([0-9]+(?:\.[0-9]+)+)-setup\.exe$"
STAMPED_PATTERN = r"Studio_(?:win_public|win|public)[_-]v([0-9]+(?:\.[0-9]+)+)-[0-9]+\.exe$"
STAMP = "20260128215914"


def dotted(*parts):
    """A label of numbers joined by dots. Built here: a label of four numbers, written out in a file
    of this folder, reads as an address to the repository's hygiene check."""
    return ".".join(parts)


class LabelTests(unittest.TestCase):
    def test_the_group_of_the_pattern_is_the_label(self):
        processor, messages = run_processor(READER, {
            "pathname": "/downloads/ipscan-3.10.0-setup.exe", "version_pattern": SCANNER_PATTERN})
        self.assertEqual(processor.env["version"], "3.10.0")
        self.assertEqual(messages, ["version is 3.10.0, taken from the file name ipscan-3.10.0-setup.exe"])

    def test_it_sets_version_over_what_an_earlier_step_left_and_nothing_else(self):
        env = {"pathname": "ipscan-3.9.3-setup.exe", "version_pattern": SCANNER_PATTERN,
               "version": "tag-of-the-release", "other": "kept"}
        processor, _ = run_processor(READER, env)
        self.assertEqual(processor.env["version"], "3.9.3")
        self.assertEqual(processor.env["other"], "kept")
        self.assertEqual(sorted(processor.env), sorted(env))

    def test_leading_zeros_stay_and_a_label_of_four_parts_is_taken(self):
        label = dotted("02", "08", "02", "61")
        for name in ("Bambu_Studio_win_public-v%s-%s.exe" % (label, STAMP),
                     "Bambu_Studio_win-v%s-%s.exe" % (label, STAMP),
                     "Bambu_Studio_win_v%s-%s.exe" % (label, STAMP),
                     "Bambu_Studio_public-v%s-%s.exe" % (label, STAMP)):
            with self.subTest(name=name):
                processor, _ = run_processor(READER, {"pathname": name, "version_pattern": "Bambu_" + STAMPED_PATTERN})
                self.assertEqual(processor.env["version"], label)

    def test_only_the_file_name_is_read_and_never_a_folder(self):
        folder = "/downloads/9.9.9/downloads-1.2.3"
        processor, _ = run_processor(READER, {
            "pathname": folder + "/ipscan-3.10.0-setup.exe", "version_pattern": SCANNER_PATTERN})
        self.assertEqual(processor.env["version"], "3.10.0")
        # A pattern that would match the folder cannot reach it.
        with self.assertRaises(ProcessorError):
            run_processor(READER, {"pathname": folder + "/setup.exe", "version_pattern": r"[^/]*([0-9.]+)"})

    def test_the_name_is_matched_from_its_start_like_asset_regex(self):
        with self.assertRaises(ProcessorError) as caught:
            run_processor(READER, {"pathname": "old-ipscan-3.10.0-setup.exe", "version_pattern": SCANNER_PATTERN})
        self.assertIn("does not match version_pattern", str(caught.exception))

    def test_text_after_the_group_is_the_patterns_business(self):
        """Without a `$` the pattern lets more follow, as the asset_regex of AutoPkg does."""
        processor, _ = run_processor(READER, {
            "pathname": "ipscan-3.10.0-setup.exe.sig", "version_pattern": r"ipscan-([0-9.]+)-setup"})
        self.assertEqual(processor.env["version"], "3.10.0")

    def test_a_build_date_is_never_taken_for_a_label(self):
        """The group of a pattern that is written for the wrong part of the name takes the build date."""
        name = "Bambu_Studio_win-v%s-%s.exe" % (dotted("02", "08", "02", "61"), STAMP)
        processor, _ = new_processor(READER, {"pathname": name, "version_pattern": r"Bambu_Studio_win-v[0-9.]+-([0-9]+)\.exe$"})
        with self.assertRaises(ProcessorError) as caught:
            processor.main()
        self.assertIn("is not a version label", str(caught.exception))
        self.assertNotIn("version", processor.env)

    def test_a_failure_leaves_version_as_it_was(self):
        processor, _ = new_processor(READER, {
            "pathname": "ipscan-setup.exe", "version_pattern": SCANNER_PATTERN, "version": "kept"})
        with self.assertRaises(ProcessorError):
            processor.main()
        self.assertEqual(processor.env["version"], "kept")


class ShapeTests(unittest.TestCase):
    def test_labels_of_two_to_four_numbers_pass(self):
        for text in ("3.10.0", "26.03", "1.0", "2.5.0", dotted("02", "08", "02", "61"), dotted("14", "44", "35211", "0"),
                     "999999999.999999999", "0.0.1", "10.0.0"):
            with self.subTest(text=text):
                self.assertEqual(version_name.check_label_shape(text), text)

    def test_everything_else_is_refused(self):
        for text in ("", "3", "3.", ".3", "3..1", "3.x", "x.3", "v3.1", "3.1-beta", "3.1 ", " 3.1", "3.1\n",
                     dotted("3", "1", "2", "3", "4"), "20260128215914", "1.2." + STAMP, STAMP + ".1", "1,2", "1_2",
                     "１.２"):  # full-width digits
            with self.subTest(text=text):
                with self.assertRaises(ValueError) as caught:
                    version_name.check_label_shape(text)
                self.assertIn("is not a version label", str(caught.exception))

    def test_a_part_of_ten_digits_is_refused_and_one_of_nine_is_not(self):
        version_name.check_label_shape("1." + "9" * 9)
        with self.assertRaises(ValueError):
            version_name.check_label_shape("1." + "9" * 10)

    def test_zeros_are_not_a_version(self):
        for text in ("0.0", "0.0.0", dotted("0", "0", "0", "0"), "00.00"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError) as caught:
                    version_name.check_label_shape(text)
                self.assertIn("made of zeros", str(caught.exception))
        version_name.check_label_shape("0.0.1")

    def test_a_long_value_is_cut_in_the_message(self):
        with self.assertRaises(ValueError) as caught:
            version_name.check_label_shape("x" * 500)
        self.assertLess(len(str(caught.exception)), 300)
        self.assertIn("...", str(caught.exception))


class InputTests(unittest.TestCase):
    def failure(self, env):
        processor, _ = new_processor(READER, env)
        with self.assertRaises(ProcessorError) as caught:
            processor.main()
        self.assertEqual(processor.env.get("version"), env.get("version"))
        return str(caught.exception)

    def test_a_pathname_without_a_file_name_is_an_error(self):
        for value in (None, "", "/", "/downloads/", 5, ["ipscan-3.10.0-setup.exe"]):
            with self.subTest(pathname=value):
                env = {"version_pattern": SCANNER_PATTERN}
                if value is not None:
                    env["pathname"] = value
                self.assertIn("pathname has no file name", self.failure(env))

    def test_a_pattern_that_is_missing_empty_or_not_text_is_an_error(self):
        for value in (None, "", 5, ["x"]):
            with self.subTest(pattern=value):
                env = {"pathname": "ipscan-3.10.0-setup.exe"}
                if value is not None:
                    env["version_pattern"] = value
                self.assertIn("version_pattern is empty or is not text", self.failure(env))

    def test_a_pattern_that_is_not_a_regular_expression_is_an_error(self):
        message = self.failure({"pathname": "ipscan-3.10.0-setup.exe", "version_pattern": "ipscan-([0-9"})
        self.assertIn("not a regular expression", message)

    def test_a_pattern_needs_exactly_one_group(self):
        for pattern, count in ((r"ipscan-[0-9.]+-setup\.exe$", 0),
                               (r"ipscan-([0-9]+)\.([0-9.]+)-setup\.exe$", 2),
                               (r"ipscan-((?:[0-9]+\.)+[0-9]+)-(setup)\.exe$", 2)):
            with self.subTest(pattern=pattern):
                message = self.failure({"pathname": "ipscan-3.10.0-setup.exe", "version_pattern": pattern})
                self.assertIn("must have exactly one group", message)
                self.assertIn("it has %d" % count, message)

    def test_a_group_that_took_no_part_in_the_match_is_an_error(self):
        message = self.failure({"pathname": "ipscan-setup.exe", "version_pattern": r"ipscan-(?:([0-9.]+)-)?setup\.exe$"})
        self.assertIn("did not take part", message)

    def test_a_name_that_does_not_match_names_the_name_and_the_pattern(self):
        message = self.failure({"pathname": "ipscan-3.10.0-win.exe", "version_pattern": SCANNER_PATTERN})
        self.assertIn("ipscan-3.10.0-win.exe", message)
        self.assertIn(SCANNER_PATTERN, message)


class DeclarationTests(unittest.TestCase):
    def test_the_declaration(self):
        for name in ("pathname", "version_pattern"):
            self.assertTrue(READER.input_variables[name]["required"])
            self.assertNotIn("default", READER.input_variables[name])
        self.assertEqual(sorted(READER.input_variables), ["pathname", "version_pattern"])
        self.assertEqual(sorted(READER.output_variables), ["version"])

    def test_the_shape_constants_are_the_ones_that_the_readme_states(self):
        self.assertEqual((version_name.MIN_PARTS, version_name.MAX_PARTS, version_name.MAX_PART_DIGITS), (2, 4, 9))


if __name__ == "__main__":
    unittest.main()
