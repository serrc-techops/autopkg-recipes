"""Tests of PcmanImporter against a stand-in for the package tool.

The stand-in (see _win_support.py) is a small script that writes a result
file and exits with a chosen code. It records what it was given: its argument
list, its whole environment, what its standard input looked like. The real
package tool is tested in test_importer_real_tool.py.
"""
import builtins
import hashlib
import inspect
import os
import time
import unittest
from unittest import mock

from _win_support import (
    ADDED_BY_THE_SYSTEM,
    ProcessorError,
    ToolTestCase,
    checksum,
    importer,
    new_processor,
    result_file_content,
    run_processor,
    sha256_hex,
)

PCMAN = importer.PcmanImporter
PLANTED = "planted-value-that-must-not-travel"


def own_variables(environment):
    return {k: v for k, v in environment.items() if k not in ADDED_BY_THE_SYSTEM}


class CommandLineTests(ToolTestCase):
    def test_the_exact_argument_list_of_a_real_run(self):
        run_processor(PCMAN, self.env())
        argv = self.record()["argv"]
        result_file = argv[argv.index("--result-file") + 1]
        self.assertEqual(
            argv,
            [
                "import", self.exe, "--template", "Example-App", "--version", "2.5.0",
                "--no-prompt", "--if-new", "--result-file", result_file,
            ],
        )
        self.assertEqual(os.path.basename(result_file), "result.json")

    def test_build_command_is_a_list_that_starts_with_python_and_the_script(self):
        command = importer.build_command("/p/python3", "/r", "/d/x.exe", "T", "1.0", "/t/result.json", True)
        self.assertEqual(
            command,
            ["/p/python3", "/r/bin/pcman", "import", "/d/x.exe", "--template", "T",
             "--version", "1.0", "--no-prompt", "--if-new", "--result-file", "/t/result.json",
             "--dry-run"],
        )

    def test_the_version_is_left_out_when_empty(self):
        command = importer.build_command("/p", "/r", "/d/x.msi", "T", "", "/t/r.json", False)
        self.assertNotIn("--version", command)
        self.assertNotIn("--dry-run", command)

    def test_an_installer_and_a_tool_folder_with_a_space_arrive_whole(self):
        run_processor(PCMAN, self.env())
        argv = self.record()["argv"]
        self.assertIn(self.exe, argv)
        self.assertIn(" ", self.exe)
        self.assertIn(" ", self.root)

    def test_no_forbidden_flag_is_ever_passed(self):
        cases = [
            ("exe, real run", self.env(), "published"),
            ("exe, dry run", self.env(pcman_dry_run=True), "dry-run"),
            ("msi without version", self.env(installer=self.msi, pcman_version=None), "published"),
            ("msi with version", self.env(installer=self.msi, pcman_version="2.5.0"), "published"),
        ]
        for label, env, kind in cases:
            with self.subTest(case=label):
                self.behave(result=result_file_content(kind))
                run_processor(PCMAN, env)
                for flag in importer.FORBIDDEN_FLAGS:
                    self.assertNotIn(flag, self.record()["argv"])

    def test_the_forbidden_flags_are_the_four_of_the_design(self):
        self.assertEqual(
            sorted(importer.FORBIDDEN_FLAGS),
            ["--allow-duplicate", "--allow-product-change", "--allow-version-label", "--force"],
        )

    def test_there_is_no_input_that_could_carry_a_forbidden_flag(self):
        for name in PCMAN.input_variables:
            self.assertNotIn("force", name)
            self.assertNotIn("allow_duplicate", name)
            self.assertNotIn("allow_product", name)
            self.assertNotIn("allow_version", name)
            self.assertNotIn("duplicate", name)

    def test_the_only_input_that_allows_anything_is_the_unverified_one(self):
        """An input whose name suggests a way around a check (pcman_allow_anything,
        pcman_allow_changes) must not appear without this test being changed."""
        allowing = [name for name in PCMAN.input_variables if "allow" in name]
        self.assertEqual(allowing, ["pcman_allow_unverified"])
        begins = [name for name in PCMAN.input_variables if name.startswith("pcman_allow_")]
        self.assertEqual(begins, ["pcman_allow_unverified"])

    def test_a_template_or_version_that_looks_like_a_flag_is_refused_and_nothing_runs(self):
        for key, value in (
            ("pcman_template", "--force"),
            ("pcman_template", "-x"),
            ("pcman_version", "--allow-version-label"),
            ("pcman_version", "-1"),
            ("pcman_template", "Two\nlines"),
        ):
            with self.subTest(key=key, value=value):
                with self.assertRaises(ProcessorError):
                    run_processor(PCMAN, self.env(**{key: value}))
                self.assertFalse(self.was_run())

    def test_a_relative_installer_path_is_made_absolute(self):
        old = os.getcwd()
        os.chdir(self.downloads)
        try:
            run_processor(PCMAN, self.env(installer="Example App-2.5.0.exe"))
        finally:
            os.chdir(old)
        self.assertIn(self.exe, self.record()["argv"])

    def test_the_default_python_is_the_tools_own_virtual_environment(self):
        captured = {}

        def fake_run(self_, command, child_env, timeout):
            captured["command"] = command
            raise ProcessorError("stop")

        with mock.patch.object(PCMAN, "run_tool", fake_run):
            with self.assertRaises(ProcessorError):
                run_processor(PCMAN, self.env())
        self.assertEqual(captured["command"][0], os.path.join(self.root, ".venv", "bin", "python3"))
        self.assertEqual(captured["command"][1], os.path.join(self.root, "bin", "pcman"))

    def test_another_python_can_be_named(self):
        other = os.path.join(self.tmp, "other python")
        os.symlink(self.python, other)
        captured = {}

        def fake_run(self_, command, child_env, timeout):
            captured["command"] = command
            raise ProcessorError("stop")

        with mock.patch.object(PCMAN, "run_tool", fake_run):
            with self.assertRaises(ProcessorError):
                run_processor(PCMAN, self.env(pcman_python=other))
        self.assertEqual(captured["command"][0], other)


class DryRunTests(ToolTestCase):
    def test_a_dry_run_is_the_default(self):
        self.behave(result=result_file_content("dry-run"))
        run_processor(PCMAN, self.env(pcman_dry_run=None))
        self.assertEqual(self.record()["argv"][-1], "--dry-run")

    def test_the_input_default_is_true(self):
        self.assertIs(PCMAN.input_variables["pcman_dry_run"]["default"], True)

    def test_a_dry_run_changes_nothing_and_warns_once(self):
        self.behave(result=result_file_content("dry-run"))
        processor, messages = run_processor(PCMAN, self.env(pcman_dry_run=True))
        self.assertIs(processor.env["pcman_repo_changed"], False)
        self.assertEqual(processor.env["pcman_result"], "dry-run")
        warnings = [m for m in messages if m.startswith("WARNING:")]
        self.assertEqual(len(warnings), 1)
        self.assertIn("pcman_dry_run", warnings[0])
        self.assertIn("DRY RUN", warnings[0])
        summary = processor.env["pcman_importer_summary_result"]
        self.assertEqual(summary["data"]["result"], importer.DRY_RUN_SUMMARY_RESULT)

    def test_the_explicit_false_makes_a_real_run(self):
        for value in (False, "false", "False", "no", "0", " false ", "FALSE\n"):
            with self.subTest(value=value):
                self.behave()
                processor, _ = run_processor(PCMAN, self.env(pcman_dry_run=value))
                self.assertNotIn("--dry-run", self.record()["argv"])
                self.assertIs(processor.env["pcman_repo_changed"], True)

    def test_text_true_is_a_dry_run(self):
        self.behave(result=result_file_content("dry-run"))
        run_processor(PCMAN, self.env(pcman_dry_run="true"))
        self.assertIn("--dry-run", self.record()["argv"])

    def test_a_value_that_is_neither_true_nor_false_is_refused(self):
        for value in ("maybe", "", None, 2, "off", "n", "f", "on", "disabled", "0.0", "false;"):
            with self.subTest(value=value):
                with self.assertRaises(ProcessorError):
                    run_processor(PCMAN, self.env(pcman_dry_run=value if value is not None else "none"))
                self.assertFalse(self.was_run())

    def test_a_real_run_that_answers_dry_run_is_an_error(self):
        self.behave(result=result_file_content("dry-run"))
        with self.assertRaises(ProcessorError):
            run_processor(PCMAN, self.env())

    def test_a_dry_run_that_answers_published_is_an_error(self):
        with self.assertRaises(ProcessorError):
            run_processor(PCMAN, self.env(pcman_dry_run=True))


class UnverifiedDownloadTests(ToolTestCase):
    """A download that no step verified is not published silently."""

    def verified(self, **overrides):
        return self.env(**overrides)

    def unverified(self, **overrides):
        return self.env(checksum_verified=None, **overrides)

    def refused_message(self, env):
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, env)
        self.assertFalse(self.was_run(), "the tool must not start")
        return str(caught.exception)

    def always_shown(self, processor, start):
        return [m for level, m in processor.message_levels if level == importer.ALWAYS_SHOWN and m.startswith(start)]

    # ---- the declaration

    def test_the_variables_that_count_are_the_flag_and_the_hash_of_the_checksum_step(self):
        self.assertEqual(importer.VERIFIED_FLAG_VARIABLE, "checksum_verified")
        self.assertEqual(importer.VERIFIED_HASH_VARIABLE, "checksum_sha256")
        # The names are those that ChecksumVerifier outputs.
        self.assertIn(importer.VERIFIED_FLAG_VARIABLE, checksum.ChecksumVerifier.output_variables)
        self.assertIn(importer.VERIFIED_HASH_VARIABLE, checksum.ChecksumVerifier.output_variables)
        self.assertFalse(hasattr(importer, "VERIFIED_VARIABLES"))

    def test_the_new_input_is_optional_and_false_by_default(self):
        flags = PCMAN.input_variables["pcman_allow_unverified"]
        self.assertIs(flags["required"], False)
        self.assertIs(flags["default"], False)

    # ---- a real run

    def test_a_real_run_of_an_unverified_download_is_refused_before_the_tool_starts(self):
        message = self.refused_message(self.unverified())
        self.assertIn("not verified", message)
        self.assertIn("pcman_allow_unverified", message)
        self.assertIn("Publish by hand after checking the file", message)

    def test_a_refused_run_sets_no_output(self):
        processor, _ = new_processor(PCMAN, self.unverified())
        with self.assertRaises(ProcessorError):
            processor.main()
        for name in PCMAN.output_variables:
            self.assertNotIn(name, processor.env)

    def test_only_a_boolean_true_counts_as_verified(self):
        for value in (False, None, "true", "True", 1, "", 0, "yes", ["x"]):
            with self.subTest(value=value):
                env = self.env()  # the hash is the real one
                env["checksum_verified"] = value
                self.refused_message(env)

    def test_the_flag_with_the_hash_of_the_file_is_enough_and_nothing_is_warned(self):
        processor, _ = run_processor(PCMAN, self.verified())
        self.assertIs(processor.env["pcman_repo_changed"], True)
        self.assertEqual(self.always_shown(processor, "WARNING:"), [])
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published")

    def test_a_signature_flag_does_not_count_alone_or_with_the_hash(self):
        """No signature step exists that outputs what it verified."""
        for hashed in (False, True):
            with self.subTest(with_the_hash=hashed):
                env = self.unverified()
                env["signature_verified"] = True
                if not hashed:
                    env.pop("checksum_sha256")
                self.refused_message(env)
        self.assertNotIn("signature_verified", PCMAN.input_variables)
        self.assertNotIn("signature_verified", inspect.getsource(importer.check_verification))

    def test_the_hash_without_the_flag_does_not_count(self):
        for flag in (None, False, "true"):
            with self.subTest(flag=flag):
                self.refused_message(self.env(checksum_verified=flag))

    def test_the_default_is_a_refusal_whatever_the_false_spelling(self):
        for value in (False, "false", "no", "0", " False "):
            with self.subTest(value=value):
                self.refused_message(self.unverified(pcman_allow_unverified=value))

    # ---- allowed by the override

    def test_with_the_allowance_the_run_goes_on_and_says_so_at_every_verbosity(self):
        for value in (True, "true", "True", "yes", "1", " true "):
            with self.subTest(value=value):
                self.behave()
                processor, _ = run_processor(PCMAN, self.unverified(pcman_allow_unverified=value))
                self.assertIs(processor.env["pcman_repo_changed"], True)
                warnings = self.always_shown(processor, "WARNING:")
                self.assertEqual(len(warnings), 1)
                self.assertIn("published WITHOUT a verified download", warnings[0])

    def test_with_the_allowance_the_summary_row_says_not_verified(self):
        processor, _ = run_processor(PCMAN, self.unverified(pcman_allow_unverified=True))
        data = processor.env["pcman_importer_summary_result"]["data"]
        self.assertEqual(data["result"], "published, NOT verified")
        self.assertEqual(data["result"], importer.PUBLISHED_UNVERIFIED_SUMMARY_RESULT)
        self.assertEqual(set(data), {"name", "version", "catalogs", "result"})

    def test_an_earlier_publish_that_is_finished_also_says_not_verified(self):
        self.behave(result=result_file_content("finished-earlier-publish"))
        processor, _ = run_processor(PCMAN, self.unverified(pcman_allow_unverified=True))
        self.assertEqual(len(self.always_shown(processor, "WARNING: published WITHOUT")), 1)
        self.assertEqual(
            processor.env["pcman_importer_summary_result"]["data"]["result"], "published, NOT verified"
        )

    def test_the_allowance_does_nothing_for_a_verified_download(self):
        processor, _ = run_processor(PCMAN, self.verified(pcman_allow_unverified=True))
        self.assertEqual(self.always_shown(processor, "WARNING:"), [])
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published")

    def test_nothing_new_is_not_called_a_publish_even_when_unverified(self):
        self.behave(exit=3, result=result_file_content("nothing-new"))
        processor, _ = run_processor(PCMAN, self.unverified(pcman_allow_unverified=True))
        self.assertEqual(self.always_shown(processor, "WARNING:"), [])
        self.assertEqual(len(self.always_shown(processor, "Nothing new")), 1)
        self.assertIs(processor.env["pcman_repo_changed"], False)

    def test_the_allowance_is_read_strictly_even_for_a_verified_download(self):
        for value in ("maybe", "off", "n", "f", "", "2", 2, "on", "false;", "0.0", None):
            env = self.verified()
            env["pcman_allow_unverified"] = value
            with self.subTest(value=value):
                self.refused_message(env)

    def test_the_allowance_has_no_effect_on_the_command_line_of_the_tool(self):
        run_processor(PCMAN, self.unverified(pcman_allow_unverified=True))
        argv = self.record()["argv"]
        self.assertNotIn("pcman_allow_unverified", " ".join(argv))
        for flag in importer.FORBIDDEN_FLAGS:
            self.assertNotIn(flag, argv)
        self.assertNotIn("--dry-run", argv)

    # ---- a dry run

    def test_a_dry_run_of_an_unverified_download_warns_and_the_summary_says_so(self):
        for allow in (None, False, True):
            with self.subTest(allow=allow):
                self.behave(result=result_file_content("dry-run"))
                processor, _ = run_processor(PCMAN, self.unverified(pcman_dry_run=True, pcman_allow_unverified=allow))
                warnings = self.always_shown(processor, "WARNING: the download was NOT verified")
                self.assertEqual(len(warnings), 1)
                self.assertIn("pcman_allow_unverified", warnings[0])
                data = processor.env["pcman_importer_summary_result"]["data"]
                self.assertEqual(data["result"], "dry run, nothing written, NOT verified")
                self.assertIs(processor.env["pcman_repo_changed"], False)
                self.assertIn("--dry-run", self.record()["argv"])

    def test_the_dry_run_of_the_default_is_a_dry_run_and_not_a_refusal(self):
        self.behave(result=result_file_content("dry-run"))
        processor, _ = run_processor(PCMAN, self.unverified(pcman_dry_run=None))
        self.assertEqual(processor.env["pcman_result"], "dry-run")

    def test_a_dry_run_of_a_verified_download_has_the_old_summary_and_one_warning(self):
        self.behave(result=result_file_content("dry-run"))
        processor, _ = run_processor(PCMAN, self.verified(pcman_dry_run=True))
        self.assertEqual(len(self.always_shown(processor, "WARNING:")), 1)
        self.assertEqual(
            processor.env["pcman_importer_summary_result"]["data"]["result"], importer.DRY_RUN_SUMMARY_RESULT
        )

    # ---- the chain with the real ChecksumVerifier

    def test_the_checksum_verifier_makes_a_real_run_possible_and_a_failed_one_does_not(self):
        import hashlib
        with open(self.exe, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        run = {"pathname": self.exe, "expected_sha256": digest}
        verifier, _ = run_processor(checksum.ChecksumVerifier, run)
        env = self.unverified()
        env.pop("checksum_sha256")
        env.update({k: v for k, v in verifier.env.items() if k.startswith("checksum_")})
        self.assertEqual(env["checksum_sha256"], digest)
        processor, _ = run_processor(PCMAN, env)
        self.assertIs(processor.env["pcman_repo_changed"], True)
        self.assertEqual(self.always_shown(processor, "WARNING:"), [])
        # A wrong hash stops the verifier and sets nothing.
        bad, _ = new_processor(checksum.ChecksumVerifier, {"pathname": self.exe, "expected_sha256": "0" * 64})
        with self.assertRaises(ProcessorError):
            bad.main()
        self.assertNotIn("checksum_verified", bad.env)


class VerifiedFileTests(ToolTestCase):
    """The verified download is tied to the file that is imported: the importer
    hashes that file and compares it with checksum_sha256."""

    def swapped(self, **overrides):
        """checksum_verified and the hash of one file, another file to import."""
        other = self.make_installer("Other App-9.9.9.exe")
        with open(other, "wb") as handle:
            handle.write(b"a different file")
        env = self.env(**overrides)
        env["pathname"] = other
        return env

    def refused_message(self, env):
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, env)
        self.assertFalse(self.was_run(), "the tool must not start")
        return str(caught.exception)

    def always_shown(self, processor, start):
        return [m for level, m in processor.message_levels if level == importer.ALWAYS_SHOWN and m.startswith(start)]

    # ---- another file than the verified one

    def test_a_swapped_file_is_refused_before_the_tool_starts(self):
        env = self.swapped()
        verified, imported = env["checksum_sha256"], sha256_hex(env["pathname"])
        message = self.refused_message(env)
        self.assertIn("not the file whose checksum was verified", message)
        self.assertIn("Other App-9.9.9.exe", message)
        # both hashes, shortened: head and tail, never the whole value
        for value in (verified, imported):
            self.assertIn("%s...%s" % (value[:8], value[-8:]), message)
            self.assertNotIn(value, message)

    def test_a_swapped_file_is_an_error_in_a_dry_run_too(self):
        message = self.refused_message(self.swapped(pcman_dry_run=True))
        self.assertIn("not the file whose checksum was verified", message)

    def test_the_default_dry_run_checks_the_file_too(self):
        self.refused_message(self.swapped(pcman_dry_run=None))

    def test_the_allowance_does_not_override_a_swapped_file(self):
        for dry in (False, True):
            with self.subTest(dry_run=dry):
                message = self.refused_message(self.swapped(pcman_allow_unverified=True, pcman_dry_run=dry))
                self.assertIn("not the file whose checksum was verified", message)

    def test_a_file_that_was_rewritten_after_the_check_is_refused(self):
        env = self.env()
        with open(self.exe, "wb") as handle:
            handle.write(b"the same path, other content")
        self.refused_message(env)

    def test_a_swapped_file_sets_no_output(self):
        processor, _ = new_processor(PCMAN, self.swapped())
        with self.assertRaises(ProcessorError):
            processor.main()
        for name in PCMAN.output_variables:
            self.assertNotIn(name, processor.env)

    def test_the_hash_of_another_file_in_upper_case_or_with_a_prefix_is_still_a_mismatch(self):
        other = hashlib.sha256(b"another file").hexdigest()
        for value in (other.upper(), "sha256:" + other, " SHA256:" + other.upper() + " "):
            with self.subTest(value=value[:20]):
                self.refused_message(self.env(checksum_sha256=value))

    # ---- a boolean without the hash of the file

    def test_a_flag_without_a_matching_hash_is_not_verified_on_a_real_run(self):
        not_a_hash = (
            "", "   ", "sha256:", "0" * 63, "0" * 65, "g" * 64, "md5:" + "0" * 64, "0" * 64 + " file.exe",
            1, True, ["0" * 64], b"0" * 64,
        )
        for value in not_a_hash:
            with self.subTest(value=repr(value)[:30]):
                message = self.refused_message(self.env(checksum_sha256=value))
                self.assertIn("The download was not verified", message)
                self.assertIn("pcman_allow_unverified", message)

    def test_a_flag_without_any_hash_is_not_verified_on_a_real_run(self):
        env = self.env()
        env.pop("checksum_sha256")
        message = self.refused_message(env)
        self.assertIn("The download was not verified", message)
        self.assertIn("checksum_sha256", message)

    def test_a_flag_without_a_matching_hash_warns_on_a_dry_run(self):
        for hash_value in (None, "", "0" * 63, 7):
            with self.subTest(value=repr(hash_value)):
                self.behave(result=result_file_content("dry-run"))
                env = self.env(pcman_dry_run=True, checksum_sha256=hash_value)
                if hash_value is None:
                    env.pop("checksum_sha256", None)
                processor, _ = run_processor(PCMAN, env)
                warnings = self.always_shown(processor, "WARNING: the download was NOT verified")
                self.assertEqual(len(warnings), 1)
                data = processor.env["pcman_importer_summary_result"]["data"]
                self.assertEqual(data["result"], "dry run, nothing written, NOT verified")

    def test_a_flag_without_a_matching_hash_is_published_with_the_allowance_and_marked(self):
        env = self.env(pcman_allow_unverified=True)
        env.pop("checksum_sha256")
        processor, _ = run_processor(PCMAN, env)
        self.assertEqual(len(self.always_shown(processor, "WARNING: published WITHOUT")), 1)
        self.assertEqual(
            processor.env["pcman_importer_summary_result"]["data"]["result"], "published, NOT verified"
        )

    # ---- the hash of the file counts

    def test_a_faked_flag_with_the_right_hash_counts_as_verified(self):
        """A pinned hash that whoever wrote the override chose: the README says so."""
        env = {
            "checksum_verified": True,
            "checksum_sha256": sha256_hex(self.exe),
            "pathname": self.exe,
            "pcman_template": "Example-App",
            "pcman_version": "2.5.0",
            "pcman_root": self.root,
            "pcman_dry_run": False,
            "pcman_path": self.msi_bin,
        }
        processor, _ = run_processor(PCMAN, env)
        self.assertIs(processor.env["pcman_repo_changed"], True)
        self.assertEqual(self.always_shown(processor, "WARNING:"), [])

    def test_the_hash_in_upper_case_with_a_prefix_or_blanks_is_normalised_like_the_verifier(self):
        real = sha256_hex(self.exe)
        for value in (real.upper(), "sha256:" + real, "SHA256:" + real.upper(), "  " + real + "\n", "sha256: " + real):
            with self.subTest(value=value[:20]):
                self.behave()
                processor, _ = run_processor(PCMAN, self.env(checksum_sha256=value))
                self.assertEqual(self.always_shown(processor, "WARNING:"), [])
                data = processor.env["pcman_importer_summary_result"]["data"]
                self.assertEqual(data["result"], "published")

    def test_the_verified_dry_run_has_one_warning_only(self):
        self.behave(result=result_file_content("dry-run"))
        processor, _ = run_processor(PCMAN, self.env(pcman_dry_run=True))
        self.assertEqual(len(self.always_shown(processor, "WARNING:")), 1)

    def test_the_real_chain_with_the_checksum_verifier_counts_as_verified(self):
        verifier, _ = run_processor(
            checksum.ChecksumVerifier, {"pathname": self.exe, "expected_sha256": sha256_hex(self.exe).upper()}
        )
        env = self.env(checksum_verified=None, checksum_sha256=None)
        env.update({k: v for k, v in verifier.env.items() if k.startswith("checksum_")})
        processor, _ = run_processor(PCMAN, env)
        self.assertEqual(self.always_shown(processor, "WARNING:"), [])
        self.assertEqual(processor.env["pcman_importer_summary_result"]["data"]["result"], "published")

    def test_the_real_chain_then_a_second_file_is_refused(self):
        """Verify file A, hand over file B (the hole that this guard closes)."""
        verifier, _ = run_processor(checksum.ChecksumVerifier, {"pathname": self.exe, "expected_sha256": sha256_hex(self.exe)})
        env = self.swapped(checksum_verified=None, checksum_sha256=None)
        env.update({k: v for k, v in verifier.env.items() if k.startswith("checksum_")})
        message = self.refused_message(env)
        self.assertIn("not the file whose checksum was verified", message)

    # ---- the file is hashed once, and only when the flag is true

    def test_the_file_is_hashed_once_per_run(self):
        for dry in (False, True):
            with self.subTest(dry_run=dry):
                self.behave(result=result_file_content("dry-run") if dry else result_file_content())
                with mock.patch.object(importer, "sha256_of_file", wraps=importer.sha256_of_file) as spy:
                    run_processor(PCMAN, self.env(pcman_dry_run=dry))
                self.assertEqual(spy.call_count, 1)
                self.assertEqual(spy.call_args[0][0], self.exe)

    def test_a_file_is_not_read_for_a_hash_when_the_flag_is_not_true(self):
        with mock.patch.object(importer, "sha256_of_file", wraps=importer.sha256_of_file) as spy:
            self.refused_message(self.env(checksum_verified=None))
        self.assertEqual(spy.call_count, 0)

    def test_a_file_that_cannot_be_read_is_an_error_and_the_tool_does_not_start(self):
        with mock.patch.object(importer, "sha256_of_file", side_effect=OSError("denied")):
            message = self.refused_message(self.env())
        self.assertIn("Could not read", message)

    # ---- the copy of the verifier's rules

    def test_the_hash_rules_equal_those_of_the_checksum_verifier(self):
        real = sha256_hex(self.exe)
        values = (
            real, real.upper(), "sha256:" + real, "SHA256:" + real, " sha256: " + real.upper() + " ", "", " ",
            "sha256:", "0" * 63, "0" * 65, "g" * 64, "md5:" + real, real + " file", None, 5, True, b"x", [real],
        )
        for value in values:
            with self.subTest(value=repr(value)[:30]):
                try:
                    expected = checksum.normalize_expected_sha256(value)
                except ValueError:
                    expected = None
                self.assertEqual(importer.normalize_sha256(value), expected)

    def test_the_two_hash_functions_give_the_same_result_over_several_blocks(self):
        path = os.path.join(self.downloads, "big.exe")
        size = importer.READ_BLOCK_BYTES * 2 + 12345
        with open(path, "wb") as handle:
            handle.write(os.urandom(size))
        self.assertEqual(importer.sha256_of_file(path), checksum.sha256_of_file(path))
        self.assertEqual(importer.sha256_of_file(path), sha256_hex(path))
        self.assertEqual(importer.sha256_of_file(self.exe), sha256_hex(self.exe))

    def test_the_constants_and_the_shortening_equal_those_of_the_checksum_verifier(self):
        for name in ("HASH_PREFIX", "HEX_DIGITS", "READ_BLOCK_BYTES", "SHOWN_HEAD_CHARS", "SHOWN_TAIL_CHARS"):
            with self.subTest(name=name):
                self.assertEqual(getattr(importer, name), getattr(checksum, name))
        self.assertEqual(importer.HASH_PATTERN.pattern, checksum.HASH_PATTERN.pattern)
        for text in ("short", "a" * 19, "a" * 20, "0123456789abcdef" * 4):
            self.assertEqual(importer.shorten(text), checksum.shorten(text))


class ExitCodeTests(ToolTestCase):
    def test_exit_0_published_sets_every_output(self):
        processor, messages = run_processor(PCMAN, self.env())
        env = processor.env
        self.assertEqual(env["pcman_result"], "published")
        self.assertEqual(env["pcman_name"], "Example App")
        self.assertEqual(env["pcman_version_published"], "2.5.0")
        self.assertEqual(env["pcman_pkginfo_path"], "/example/pkgsinfo/apps/Example-2.5.0.yaml")
        self.assertEqual(env["pcman_installer_path"], "/example/pkgs/apps/Example-2.5.0.exe")
        self.assertIs(env["pcman_repo_changed"], True)
        self.assertTrue(any("Published Example App 2.5.0" in m for m in messages))

    def test_the_summary_result_has_the_form_of_autopkg(self):
        processor, _ = run_processor(PCMAN, self.env())
        summary = processor.env["pcman_importer_summary_result"]
        self.assertEqual(set(summary), {"summary_text", "report_fields", "data"})
        self.assertTrue(summary["summary_text"])
        self.assertEqual(summary["report_fields"], ["name", "version", "catalogs", "result"])
        self.assertEqual(set(summary["data"]), set(summary["report_fields"]))
        self.assertEqual(summary["data"]["catalogs"], "Production")

    def test_exit_0_finishing_an_earlier_publish_changes_the_repository(self):
        self.behave(result=result_file_content("finished-earlier-publish"))
        processor, _ = run_processor(PCMAN, self.env())
        self.assertIs(processor.env["pcman_repo_changed"], True)
        self.assertIn("pcman_importer_summary_result", processor.env)

    def test_exit_0_with_another_result_is_an_error(self):
        for kind in ("imported", "imported-and-built", "nothing-new", "error", "something"):
            with self.subTest(kind=kind):
                self.behave(result=result_file_content(kind))
                with self.assertRaises(ProcessorError):
                    run_processor(PCMAN, self.env())

    def test_exit_3_is_not_an_error_and_changes_nothing(self):
        self.behave(exit=3, result=result_file_content("nothing-new"), stdout="Nothing new: Example App\n")
        processor, messages = run_processor(PCMAN, self.env())
        self.assertIs(processor.env["pcman_repo_changed"], False)
        self.assertEqual(processor.env["pcman_result"], "nothing-new")
        self.assertEqual(processor.env["pcman_name"], "Example App")
        self.assertNotIn("pcman_importer_summary_result", processor.env)
        self.assertEqual(len([m for m in messages if m.startswith("Nothing new")]), 1)

    def test_exit_3_with_another_result_is_an_error(self):
        self.behave(exit=3, result=result_file_content("published"))
        with self.assertRaises(ProcessorError):
            run_processor(PCMAN, self.env())

    def test_exit_3_also_in_a_dry_run(self):
        self.behave(exit=3, result=result_file_content("nothing-new"))
        processor, _ = run_processor(PCMAN, self.env(pcman_dry_run=True))
        self.assertIs(processor.env["pcman_repo_changed"], False)

    def test_exit_1_is_an_error_with_the_error_lines(self):
        self.behave(
            exit=1,
            result=result_file_content("error", message="the message of the file"),
            stderr="ERROR: the version 'v9.0' cannot be ordered by the client.\n",
        )
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env())
        self.assertIn("the version 'v9.0' cannot be ordered", str(caught.exception))

    def test_only_the_error_lines_are_passed_on(self):
        self.behave(
            exit=1,
            result=None,
            stdout="The pkginfo is made from this text:\ninstall_arguments: ['/key=PLANTED']\n",
            stderr="some other line\nERROR: first\nERROR: second\ntrailing text\n",
        )
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env())
        text = str(caught.exception)
        self.assertIn("ERROR: first", text)
        self.assertIn("ERROR: second", text)
        self.assertNotIn("PLANTED", text)
        self.assertNotIn("some other line", text)
        self.assertNotIn("trailing text", text)

    def test_error_lines_are_limited_in_number_and_length(self):
        lines = "".join("ERROR: line %d %s\n" % (i, "x" * 1000) for i in range(30))
        self.behave(exit=1, result=None, stderr=lines)
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env())
        text = str(caught.exception)
        self.assertIn("line %d" % (importer.MAX_LINES_PASSED_ON - 1), text)
        self.assertNotIn("line %d " % importer.MAX_LINES_PASSED_ON, text)
        self.assertLess(len(text), importer.MAX_LINES_PASSED_ON * (importer.MAX_LINE_CHARS + 20) + 400)

    def test_exit_1_without_an_error_line_uses_the_message_of_the_result_file(self):
        self.behave(exit=1, result=result_file_content("error", message="the file says this"))
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env())
        self.assertIn("the file says this", str(caught.exception))

    def test_exit_1_with_nothing_at_all_is_still_an_error(self):
        self.behave(exit=1, result=None)
        with self.assertRaises(ProcessorError):
            run_processor(PCMAN, self.env())

    def test_exit_2_is_a_mistake_in_the_recipe_or_the_setup(self):
        self.behave(exit=2, result=None, stderr="pcman import: error: unrecognized arguments: --x\n")
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env())
        self.assertIn("command line", str(caught.exception))
        self.assertIn("unrecognized arguments", str(caught.exception))

    def test_an_unexpected_exit_code_is_an_error(self):
        for code in (4, 127):
            with self.subTest(code=code):
                self.behave(exit=code, result=result_file_content("published"))
                with self.assertRaises(ProcessorError) as caught:
                    run_processor(PCMAN, self.env())
                self.assertIn(str(code), str(caught.exception))

    def test_no_output_is_set_after_an_error(self):
        self.behave(exit=1, result=None, stderr="ERROR: x\n")
        processor, _ = new_processor(PCMAN, self.env())
        with self.assertRaises(ProcessorError):
            processor.main()
        for key in PCMAN.output_variables:
            self.assertNotIn(key, processor.env)

    def test_warning_and_note_lines_are_passed_on_after_a_good_run(self):
        self.behave(stdout="NOTE: a note\nWARNING: a warning\nCopied installer -> /somewhere\n")
        _, messages = run_processor(PCMAN, self.env())
        self.assertIn("NOTE: a note", messages)
        self.assertIn("WARNING: a warning", messages)
        self.assertFalse(any("Copied installer" in m for m in messages))


class ResultFileTests(ToolTestCase):
    def test_a_missing_result_file_is_an_error_whatever_the_exit_code(self):
        for code in (0, 1, 2, 3):
            with self.subTest(code=code):
                self.behave(exit=code, result=None, stderr="ERROR: stopped\n")
                with self.assertRaises(ProcessorError):
                    run_processor(PCMAN, self.env())

    def test_a_result_file_that_cannot_be_read_is_an_error(self):
        for raw in ("{not json", "[1, 2]", '{"name": "no result key"}', '{"result": 5}', ""):
            with self.subTest(raw=raw):
                self.behave(exit=0, raw_result=raw)
                with self.assertRaises(ProcessorError):
                    run_processor(PCMAN, self.env())

    def test_null_values_become_empty_texts_after_a_dry_run(self):
        self.behave(result=result_file_content("dry-run", pkginfo_path=None, installer_path=None, version=None))
        processor, _ = run_processor(PCMAN, self.env(pcman_dry_run=True))
        self.assertEqual(processor.env["pcman_pkginfo_path"], "")
        self.assertEqual(processor.env["pcman_installer_path"], "")
        self.assertEqual(processor.env["pcman_version_published"], "")

    def test_the_temporary_folder_is_removed_after_success_and_after_failure(self):
        for behaviour in ({}, {"exit": 1, "result": None, "stderr": "ERROR: x\n"}):
            with self.subTest(behaviour=behaviour):
                self.behave(**behaviour)
                try:
                    run_processor(PCMAN, self.env())
                except ProcessorError:
                    pass
                argv = self.record()["argv"]
                result_file = argv[argv.index("--result-file") + 1]
                self.assertFalse(os.path.exists(os.path.dirname(result_file)))

    def test_the_temporary_folder_is_removed_after_a_time_out(self):
        self.behave(sleep=30)
        with mock.patch.object(importer, "MIN_TIMEOUT_SECONDS", 1):
            with self.assertRaises(ProcessorError):
                run_processor(PCMAN, self.env(pcman_timeout=1))
        argv = self.record()["argv"]
        self.assertFalse(os.path.exists(os.path.dirname(argv[argv.index("--result-file") + 1])))


class TimeoutTests(ToolTestCase):
    def wait_until_gone(self, pid, seconds=5):
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            except PermissionError:
                return False
            time.sleep(0.1)
        return False

    def test_a_tool_that_does_not_finish_is_stopped_with_its_children(self):
        self.behave(sleep=30, grandchild=True)
        started = time.time()
        with mock.patch.object(importer, "MIN_TIMEOUT_SECONDS", 1):
            with self.assertRaises(ProcessorError) as caught:
                run_processor(PCMAN, self.env(pcman_timeout=1))
        self.assertLess(time.time() - started, 20)
        self.assertIn("did not finish", str(caught.exception))
        record = self.record()
        self.assertTrue(self.wait_until_gone(record["pid"]), "the tool is still running")
        self.assertTrue(self.wait_until_gone(record["grandchild_pid"]), "its child is still running")

    def test_the_group_is_killed_with_sigkill_not_sigterm(self):
        import signal
        calls = []
        real = os.killpg

        def spy(pid, signum):
            calls.append(signum)
            return real(pid, signum)

        self.behave(sleep=30, grandchild=True)
        with mock.patch.object(importer.os, "killpg", spy):
            with mock.patch.object(importer, "MIN_TIMEOUT_SECONDS", 1):
                with self.assertRaises(ProcessorError):
                    run_processor(PCMAN, self.env(pcman_timeout=1))
        self.assertEqual(calls, [signal.SIGKILL])
        record = self.record()
        self.assertTrue(self.wait_until_gone(record["pid"]))
        self.assertTrue(self.wait_until_gone(record["grandchild_pid"]))

    def test_the_time_limit_is_given_to_the_call(self):
        seen = {}

        def fake_run(self_, command, child_env, timeout):
            seen["timeout"] = timeout
            raise ProcessorError("stop")

        with mock.patch.object(PCMAN, "run_tool", fake_run):
            for given, expected in ((None, importer.DEFAULT_TIMEOUT_SECONDS), (120, 120), ("300", 300)):
                with self.subTest(given=given):
                    with self.assertRaises(ProcessorError):
                        run_processor(PCMAN, self.env(pcman_timeout=given))
                    self.assertEqual(seen["timeout"], expected)

    def test_the_time_limit_has_bounds(self):
        for value in (0, importer.MIN_TIMEOUT_SECONDS - 1, importer.MAX_TIMEOUT_SECONDS + 1, "soon", True, -5):
            with self.subTest(value=value):
                with self.assertRaises(ProcessorError):
                    run_processor(PCMAN, self.env(pcman_timeout=value))
                self.assertFalse(self.was_run())

    def test_the_default_limit_is_inside_the_bounds(self):
        self.assertTrue(importer.MIN_TIMEOUT_SECONDS <= importer.DEFAULT_TIMEOUT_SECONDS <= importer.MAX_TIMEOUT_SECONDS)
        self.assertEqual(PCMAN.input_variables["pcman_timeout"]["default"], importer.DEFAULT_TIMEOUT_SECONDS)


class StandardInputTests(ToolTestCase):
    def test_standard_input_of_the_tool_is_closed_not_inherited(self):
        read_end, write_end = os.pipe()
        saved = os.dup(0)
        try:
            os.dup2(read_end, 0)  # the processor's own stdin: an open pipe that never gets data
            run_processor(PCMAN, self.env())
        finally:
            os.dup2(saved, 0)
            for fd in (saved, read_end, write_end):
                os.close(fd)
        self.assertEqual(self.record()["stdin"], "eof")


class EnvironmentTests(ToolTestCase):
    def run_with_environment(self, planted, env=None):
        with mock.patch.dict(os.environ, planted):
            run_processor(PCMAN, env or self.env())
        return self.record()["env"]

    def test_only_path_home_and_the_named_variables_reach_the_tool(self):
        planted = {
            "PLANTED_SECRET": PLANTED,
            "AWS_SECRET_ACCESS_KEY": PLANTED,
            "PCMAN_SOMETHING_ELSE": PLANTED,
            "PCMAN_CIMIAN_REPO": "/example/repo",
            "PCMAN_CONFIG": "/example/config.yaml",
            "PCMAN_CIMIAN_CATALOGS": "Testing",
            "PCMAN_STATE_DIR": "/example/state",
            "HOME": "/example/home",
        }
        seen = own_variables(self.run_with_environment(planted))
        self.assertEqual(
            seen,
            {
                "PATH": self.msi_bin,
                "HOME": "/example/home",
                "PCMAN_CIMIAN_REPO": "/example/repo",
                "PCMAN_CONFIG": "/example/config.yaml",
                "PCMAN_CIMIAN_CATALOGS": "Testing",
                "PCMAN_STATE_DIR": "/example/state",
            },
        )
        self.assertNotIn(PLANTED, "".join(seen.values()))

    def test_variables_that_are_not_set_are_not_passed_as_empty(self):
        for name in importer.PASSED_VARIABLES:
            os.environ.pop(name, None)
        with mock.patch.dict(os.environ, {"PLANTED_SECRET": PLANTED}):
            run_processor(PCMAN, self.env())
        seen = own_variables(self.record()["env"])
        self.assertEqual(set(seen), {"PATH", "HOME"})

    def test_an_input_of_the_lower_case_name_is_passed_and_wins(self):
        env = self.env(pcman_cimian_repo="/example/from-input", pcman_state_dir="/example/state-input")
        seen = self.run_with_environment({"PCMAN_CIMIAN_REPO": "/example/from-environment"}, env)
        self.assertEqual(seen["PCMAN_CIMIAN_REPO"], "/example/from-input")
        self.assertEqual(seen["PCMAN_STATE_DIR"], "/example/state-input")

    def test_an_empty_input_falls_back_to_the_environment(self):
        env = self.env(pcman_cimian_repo="  ")
        seen = self.run_with_environment({"PCMAN_CIMIAN_REPO": "/example/from-environment"}, env)
        self.assertEqual(seen["PCMAN_CIMIAN_REPO"], "/example/from-environment")

    def test_the_path_is_the_input_or_the_named_default(self):
        self.run_with_environment({}, self.env(pcman_path=self.msi_bin))
        self.assertEqual(self.record()["env"]["PATH"], self.msi_bin)
        self.assertTrue(importer.DEFAULT_CHILD_PATH.startswith("/opt/homebrew/bin"))
        self.assertEqual(
            importer.child_environment({}, {"HOME": "/h"}, importer.DEFAULT_CHILD_PATH)["PATH"],
            importer.DEFAULT_CHILD_PATH,
        )
        self.assertEqual(PCMAN.input_variables["pcman_path"]["default"], importer.DEFAULT_CHILD_PATH)

    def test_the_default_path_reaches_the_tool_when_no_path_is_given(self):
        with mock.patch.object(importer.shutil, "which", return_value="/found/msiinfo"):
            self.behave()
            run_processor(PCMAN, self.env(installer=self.msi, pcman_version=None, pcman_path=None))
        self.assertEqual(self.record()["env"]["PATH"], importer.DEFAULT_CHILD_PATH)

    def test_the_environment_is_never_printed(self):
        with mock.patch.dict(os.environ, {"PCMAN_CIMIAN_REPO": PLANTED, "PLANTED_SECRET": PLANTED}):
            _, messages = run_processor(PCMAN, self.env())
        self.assertNotIn(PLANTED, "\n".join(messages))

    def test_pcman_yaml_is_never_opened(self):
        with open(os.path.join(self.root, "pcman.yaml"), "w") as handle:
            handle.write("cimian_repo: /example\n")
        opened = []
        real_open = builtins.open

        def recording_open(file, *args, **kwargs):
            opened.append(str(file))
            return real_open(file, *args, **kwargs)

        with mock.patch.object(builtins, "open", recording_open):
            run_processor(PCMAN, self.env())
        self.assertFalse([name for name in opened if "pcman.yaml" in name])

    def test_the_working_folder_is_not_changed_for_the_tool(self):
        run_processor(PCMAN, self.env())
        self.assertEqual(os.path.realpath(self.record()["cwd"]), os.path.realpath(os.getcwd()))


class CheckBeforeTheCallTests(ToolTestCase):
    def refused(self, **overrides):
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env(**overrides))
        self.assertFalse(self.was_run(), "the tool must not run after a refused input")
        return str(caught.exception)

    def test_pcman_root_must_be_given_and_must_hold_the_tool(self):
        self.assertIn("pcman_root", self.refused(pcman_root=None))
        self.assertIn("pcman_root", self.refused(pcman_root=""))
        self.assertIn("not a folder", self.refused(pcman_root=os.path.join(self.tmp, "nowhere")))
        self.assertIn("is missing", self.refused(pcman_root=self.empty_bin))

    def test_pcman_root_has_no_default(self):
        self.assertNotIn("default", PCMAN.input_variables["pcman_root"])

    def test_the_python_must_exist(self):
        self.refused(pcman_python=os.path.join(self.tmp, "no python"))
        os.remove(self.python)
        self.refused()

    def test_the_installer_must_exist_and_end_in_msi_or_exe(self):
        self.assertIn("does not exist", self.refused(installer=os.path.join(self.downloads, "gone.exe")))
        other = self.make_installer("Example.zip")
        self.assertIn(".msi or .exe", self.refused(installer=other))
        self.refused(pathname="")
        self.refused(installer=self.downloads + os.sep + "Example App-2.5.0")

    def test_the_extension_is_read_in_any_letter_case(self):
        shouting = self.make_installer("EXAMPLE-2.5.0.EXE")
        run_processor(PCMAN, self.env(installer=shouting))
        self.assertIn(shouting, self.record()["argv"])

    def test_an_exe_needs_a_version(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                message = self.refused(pcman_version=value)
                self.assertIn("pcman_version", message)

    def test_an_msi_needs_no_version_and_the_flag_is_left_out(self):
        for value in (None, "", " "):
            with self.subTest(value=value):
                run_processor(PCMAN, self.env(installer=self.msi, pcman_version=value))
                self.assertNotIn("--version", self.record()["argv"])

    def test_an_msi_with_a_version_passes_it_on_for_the_tool_to_compare(self):
        run_processor(PCMAN, self.env(installer=self.msi, pcman_version="2.5.0"))
        argv = self.record()["argv"]
        self.assertEqual(argv[argv.index("--version") + 1], "2.5.0")

    def test_the_template_must_be_given(self):
        self.refused(pcman_template=None)
        self.refused(pcman_template="  ")

    def test_an_msi_needs_msiinfo_on_the_path_that_the_tool_gets(self):
        message = self.refused(installer=self.msi, pcman_version=None, pcman_path=self.empty_bin)
        self.assertIn("msiinfo", message)

    def test_msiinfo_on_the_processors_own_path_does_not_count(self):
        with mock.patch.dict(os.environ, {"PATH": self.msi_bin + os.pathsep + os.environ.get("PATH", "")}):
            message = self.refused(installer=self.msi, pcman_version=None, pcman_path=self.empty_bin)
        self.assertIn("msiinfo", message)

    def test_an_msi_with_msiinfo_on_the_given_path_runs(self):
        run_processor(PCMAN, self.env(installer=self.msi, pcman_version=None, pcman_path=self.msi_bin))
        self.assertTrue(self.was_run())

    def test_an_exe_needs_no_msiinfo(self):
        run_processor(PCMAN, self.env(pcman_path=self.empty_bin))
        self.assertTrue(self.was_run())

    def test_a_tool_that_cannot_be_started_is_an_error(self):
        with mock.patch.object(importer.subprocess, "Popen", side_effect=OSError("no such thing")):
            with self.assertRaises(ProcessorError) as caught:
                run_processor(PCMAN, self.env())
        self.assertIn("could not be started", str(caught.exception))


class DeclarationTests(unittest.TestCase):
    def test_the_inputs_of_the_design_exist(self):
        for name in (
            "pathname", "pcman_template", "pcman_version", "pcman_root", "pcman_python",
            "pcman_dry_run", "pcman_timeout", "pcman_path",
        ):
            self.assertIn(name, PCMAN.input_variables)

    def test_the_outputs_of_the_design_exist(self):
        for name in (
            "pcman_result", "pcman_name", "pcman_version_published", "pcman_pkginfo_path",
            "pcman_installer_path", "pcman_repo_changed", "pcman_importer_summary_result",
        ):
            self.assertIn(name, PCMAN.output_variables)

    def test_the_inputs_that_a_recipe_must_give_are_required(self):
        self.assertTrue(PCMAN.input_variables["pathname"]["required"])
        self.assertTrue(PCMAN.input_variables["pcman_template"]["required"])
        self.assertTrue(PCMAN.input_variables["pcman_root"]["required"])
        self.assertFalse(PCMAN.input_variables["pcman_version"]["required"])



# The longest message that the tool prints today (a minor upgrade of an MSI),
# as it is printed for made-up names. Its advice is at the end.
REAL_MINOR_UPGRADE_NOTE = (
    "NOTE: the earlier version Example-App 1.0.0 has the same MSI product code: this is a minor "
    "upgrade of the same product. The client runs `msiexec /i` with the install arguments of the "
    "item; for an upgrade of an installed product of the same code that may change nothing unless "
    "the install arguments ask for a reinstall (Windows Installer's REINSTALL and REINSTALLMODE "
    "properties). Test the first such version on a PC before the PCs get it. No install argument "
    "is added by this tool."
)


def wait_until_gone(pid, seconds=5):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        time.sleep(0.1)
    return False


class VisibilityTests(ToolTestCase):
    """AutoPkg prints a message of level 1 or more only with -v. What an
    operator must see at the default verbosity has the level 0."""

    def levels(self, processor):
        return {text: level for level, text in processor.message_levels}

    def test_the_dry_run_line_is_always_shown(self):
        self.behave(result=result_file_content("dry-run"))
        processor, messages = run_processor(PCMAN, self.env(pcman_dry_run=True))
        warning = [m for m in messages if m.startswith("WARNING:")][0]
        self.assertEqual(self.levels(processor)[warning], importer.ALWAYS_SHOWN)
        self.assertEqual(importer.ALWAYS_SHOWN, 0)

    def test_the_nothing_new_line_is_always_shown(self):
        self.behave(exit=3, result=result_file_content("nothing-new"))
        processor, messages = run_processor(PCMAN, self.env())
        line = [m for m in messages if m.startswith("Nothing new")][0]
        self.assertEqual(self.levels(processor)[line], 0)

    def test_the_published_line_and_the_tools_notes_are_always_shown(self):
        self.behave(stdout=REAL_MINOR_UPGRADE_NOTE + "\n", stderr="WARNING: from the error stream\n")
        processor, messages = run_processor(PCMAN, self.env())
        levels = self.levels(processor)
        for text in (REAL_MINOR_UPGRADE_NOTE, "WARNING: from the error stream", "Published Example App 2.5.0."):
            self.assertEqual(levels[text], 0, text)

    def test_the_summary_of_a_dry_run_says_that_nothing_was_written(self):
        self.behave(result=result_file_content("dry-run"))
        processor, _ = run_processor(PCMAN, self.env(pcman_dry_run=True))
        summary = processor.env["pcman_importer_summary_result"]
        self.assertEqual(set(summary), {"summary_text", "report_fields", "data"})
        self.assertIn("result", summary["report_fields"])
        self.assertEqual(summary["data"]["result"], "dry run, nothing written")
        self.assertEqual(set(summary["data"]), set(summary["report_fields"]))
        self.assertTrue(all(isinstance(v, str) for v in summary["data"].values()))
        self.assertIn("Dry run", summary["summary_text"])

    def test_the_summary_holds_no_path_and_the_result_of_a_publish(self):
        for kind, expected in (("published", "published"), ("finished-earlier-publish", "finished-earlier-publish")):
            with self.subTest(kind=kind):
                self.behave(result=result_file_content(kind))
                processor, _ = run_processor(PCMAN, self.env())
                data = processor.env["pcman_importer_summary_result"]["data"]
                self.assertEqual(data["result"], expected)
                self.assertEqual(data["name"], "Example App")
                self.assertEqual(data["version"], "2.5.0")
                self.assertEqual(data["catalogs"], "Production")
                self.assertFalse([v for v in data.values() if "/" in v])
                self.assertNotIn("pkginfo_path", data)
                self.assertNotIn("installer_path", data)

    def test_the_paths_stay_as_output_variables(self):
        processor, _ = run_processor(PCMAN, self.env())
        self.assertTrue(processor.env["pcman_pkginfo_path"].startswith("/"))
        self.assertTrue(processor.env["pcman_installer_path"].startswith("/"))

    def test_a_dry_run_that_planned_paths_keeps_them_out_of_the_summary(self):
        self.behave(result=result_file_content("dry-run"))
        processor, _ = run_processor(PCMAN, self.env(pcman_dry_run=True))
        self.assertFalse([v for v in processor.env["pcman_importer_summary_result"]["data"].values() if "/" in v])


class ShownLinesTests(ToolTestCase):
    def test_the_minor_upgrade_note_is_shown_whole(self):
        self.assertLess(len(REAL_MINOR_UPGRADE_NOTE), importer.MAX_LINE_CHARS)
        self.behave(stdout="Copied installer\n" + REAL_MINOR_UPGRADE_NOTE + "\n")
        _, messages = run_processor(PCMAN, self.env(installer=self.msi, pcman_version=None))
        self.assertIn(REAL_MINOR_UPGRADE_NOTE, messages)
        self.assertTrue(REAL_MINOR_UPGRADE_NOTE.endswith("is added by this tool."))

    def test_the_limit_leaves_room_for_the_longest_known_note_with_long_names(self):
        longer = REAL_MINOR_UPGRADE_NOTE.replace("Example-App 1.0.0", "A" * 100 + " 1.0.0") + " /" + "p" * 300
        self.assertLess(len(longer), importer.MAX_LINE_CHARS)

    def test_a_line_above_the_limit_is_cut(self):
        self.behave(stdout="NOTE: " + "x" * (importer.MAX_LINE_CHARS + 500) + "\n")
        _, messages = run_processor(PCMAN, self.env())
        long_line = [m for m in messages if m.startswith("NOTE: xxx")][0]
        self.assertTrue(long_line.endswith("..."))
        self.assertLessEqual(len(long_line), importer.MAX_LINE_CHARS + 3)

    def test_an_error_line_of_a_normal_length_is_shown_whole(self):
        line = "ERROR: " + "word " * 150
        self.behave(exit=1, result=None, stderr=line + "\n")
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env())
        self.assertIn(line.strip(), str(caught.exception))

    def test_note_and_warning_lines_of_the_error_stream_are_shown(self):
        self.behave(stderr="NOTE: one\nWARNING: two\n")
        _, messages = run_processor(PCMAN, self.env())
        self.assertIn("NOTE: one", messages)
        self.assertIn("WARNING: two", messages)

    def test_error_lines_of_the_output_stream_are_used(self):
        self.behave(exit=1, result=None, stdout="ERROR: said on standard output\n")
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env())
        self.assertIn("said on standard output", str(caught.exception))

    def test_output_that_is_not_utf8_does_not_crash_the_processor(self):
        self.behave(stdout_hex="fffe", stderr_hex="e9")
        processor, _ = run_processor(PCMAN, self.env())
        self.assertEqual(processor.env["pcman_result"], "published")
        self.behave(exit=1, result=None, stderr="ERROR: bad byte follows ", stderr_hex="fffe0a")
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env())
        self.assertIn("bad byte follows", str(caught.exception))


class ResultCheckTests(ToolTestCase):
    def test_a_published_result_needs_four_texts(self):
        for kind in ("published", "finished-earlier-publish"):
            for key in importer.PUBLISHED_RESULT_KEYS:
                for bad in (None, "", "   ", 5, []):
                    with self.subTest(kind=kind, key=key, value=bad):
                        self.behave(result=result_file_content(kind, **{key: bad}))
                        with self.assertRaises(ProcessorError) as caught:
                            run_processor(PCMAN, self.env())
                        self.assertIn(key, str(caught.exception))

    def test_a_published_result_without_the_key_at_all_is_an_error(self):
        for kind in ("published", "finished-earlier-publish"):
            for key in importer.PUBLISHED_RESULT_KEYS:
                with self.subTest(kind=kind, key=key):
                    content = result_file_content(kind)
                    del content[key]
                    self.behave(result=content)
                    with self.assertRaises(ProcessorError) as caught:
                        run_processor(PCMAN, self.env())
                    self.assertIn(key, str(caught.exception))

    def test_a_published_result_without_installer_path_is_an_error(self):
        content = result_file_content()
        content["installer_path"] = None
        self.behave(result=content)
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env())
        self.assertIn("installer_path", str(caught.exception))
        self.assertIn("installer_path", importer.PUBLISHED_RESULT_KEYS)

    def test_a_result_file_with_only_the_result_is_refused_for_a_publish(self):
        self.behave(result={"result": "published"})
        with self.assertRaises(ProcessorError):
            run_processor(PCMAN, self.env())

    def test_a_result_that_the_tool_does_not_document_is_refused(self):
        for exit_code in (0, 3):
            with self.subTest(exit=exit_code):
                self.behave(exit=exit_code, result=result_file_content("published-ish"))
                with self.assertRaises(ProcessorError) as caught:
                    run_processor(PCMAN, self.env(pcman_dry_run=exit_code == 0))
                self.assertIn("documents", str(caught.exception))

    def test_the_documented_values_are_those_of_the_tools_readme(self):
        self.assertEqual(
            sorted(importer.RESULTS_DOCUMENTED),
            sorted(["published", "finished-earlier-publish", "imported", "imported-and-built",
                    "finished-earlier-import", "nothing-new", "dry-run", "error"]),
        )

    def test_nothing_new_needs_no_name_or_paths(self):
        self.behave(exit=3, result={"result": "nothing-new"})
        processor, _ = run_processor(PCMAN, self.env())
        self.assertEqual(processor.env["pcman_name"], "")


class InputCheckTests(ToolTestCase):
    def refused(self, **overrides):
        with self.assertRaises(ProcessorError) as caught:
            run_processor(PCMAN, self.env(**overrides))
        self.assertFalse(self.was_run())
        return str(caught.exception)

    def test_a_template_is_an_item_name(self):
        bad = ["", "  ", "a/b", "a" + chr(92) + "b", "../x", "/abs", "-x", "--force", "a b", "a\tb", "a\rb", "a\0b",
               "a\nb", "T\r", "T\n", ".hidden", "..", "~", "T;x", "a*b", "naïve"]
        for value in bad:
            with self.subTest(value=value):
                self.refused(pcman_template=value)

    def test_names_that_the_tool_accepts_are_accepted(self):
        for value in ("Example-App", "7zip", "Tool_2.x", "A"):
            with self.subTest(value=value):
                self.behave()
                run_processor(PCMAN, self.env(pcman_template=value))
                argv = self.record()["argv"]
                self.assertEqual(argv[argv.index("--template") + 1], value)

    def test_a_version_has_no_white_space_control_character_or_separator(self):
        bad = ["2.5.0 --force", " 2.5.0", "2.5.0 ", "2.5.0\n", "2.5\r", "2\0", "2.5\t0", "-1", "--x", "2/5", "2" + chr(92) + "5",
               "2.5.0" + chr(160), "2" + chr(127) + "0", chr(127), "2.5.0" + chr(127)]
        for value in bad:
            with self.subTest(value=value):
                self.refused(pcman_version=value)

    def test_a_version_label_is_accepted(self):
        for value in ("2.5.1.300", "26.03", "7"):
            with self.subTest(value=value):
                self.behave()
                run_processor(PCMAN, self.env(pcman_version=value))
                argv = self.record()["argv"]
                self.assertEqual(argv[argv.index("--version") + 1], value)

    def test_a_blank_version_for_an_msi_is_not_given(self):
        for value in ("", "   ", "\n", None):
            with self.subTest(value=value):
                run_processor(PCMAN, self.env(installer=self.msi, pcman_version=value))
                self.assertNotIn("--version", self.record()["argv"])

    def test_a_tilde_in_pcman_root_is_expanded(self):
        with mock.patch.dict(os.environ, {"HOME": self.tmp}):
            run_processor(PCMAN, self.env(pcman_root="~/tool root"))
        self.assertTrue(self.was_run())

    def test_a_tilde_root_that_does_not_exist_is_refused(self):
        with mock.patch.dict(os.environ, {"HOME": self.tmp}):
            message = self.refused(pcman_root="~/no such tool")
        self.assertIn("not a folder", message)

    def test_a_python_that_cannot_be_executed_has_its_own_message(self):
        plain = os.path.join(self.tmp, "plain python")
        with open(plain, "w") as handle:
            handle.write("not executable")
        os.chmod(plain, 0o644)
        self.assertIn("cannot be executed", self.refused(pcman_python=plain))
        self.assertIn("does not exist", self.refused(pcman_python=os.path.join(self.tmp, "gone")))

    def test_the_time_limit_bounds_are_exact(self):
        seen = []

        def fake_run(self_, command, child_env, timeout):
            seen.append(timeout)
            raise ProcessorError("stop")

        with mock.patch.object(PCMAN, "run_tool", fake_run):
            for value in (importer.MIN_TIMEOUT_SECONDS, importer.MAX_TIMEOUT_SECONDS):
                with self.assertRaises(ProcessorError) as caught:
                    run_processor(PCMAN, self.env(pcman_timeout=value))
                self.assertEqual(str(caught.exception), "stop")
        self.assertEqual(seen, [60, 14400])
        self.assertEqual((importer.MIN_TIMEOUT_SECONDS, importer.MAX_TIMEOUT_SECONDS), (60, 14400))
        for value in (59, 14401):
            with self.assertRaises(ProcessorError) as caught:
                run_processor(PCMAN, self.env(pcman_timeout=value))
            self.assertIn("between", str(caught.exception))


class InterruptTests(ToolTestCase):
    """Ctrl-C and a termination of AutoPkg end the tool and its children, and
    the temporary folder is removed. The processor runs in a child process of
    the test, as AutoPkg runs it in its main thread."""

    SCRIPT = (
        "import json, signal, sys\n"
        "sys.path.insert(0, %(tests)r)\n"
        "signal.signal(signal.SIGINT, signal.default_int_handler)\n"
        "from _win_support import importer\n"
        "env = json.load(open(sys.argv[1]))\n"
        "importer.PcmanImporter(env).main()\n"
    )

    def start_processor(self):
        import json
        import subprocess
        import sys
        self.behave(sleep=60, grandchild=True)
        env_file = os.path.join(self.tmp, "env.json")
        with open(env_file, "w") as handle:
            json.dump(self.env(), handle)
        script = os.path.join(self.tmp, "run_processor.py")
        with open(script, "w") as handle:
            handle.write(self.SCRIPT % {"tests": os.path.dirname(os.path.abspath(__file__))})
        proc = subprocess.Popen([sys.executable, script, env_file], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        deadline = time.time() + 20
        record = None
        while time.time() < deadline and record is None:
            try:
                record = self.record()
            except (OSError, ValueError):
                time.sleep(0.1)
        self.assertIsNotNone(record, "the stand-in tool did not start")
        self.assertTrue(record["grandchild_pid"])
        return proc, record

    def check_after(self, proc, record, signum):
        proc.send_signal(signum)
        proc.wait(timeout=30)
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue(wait_until_gone(record["pid"]), "the tool is still running")
        self.assertTrue(wait_until_gone(record["grandchild_pid"]), "its child is still running")
        argv = record["argv"]
        self.assertFalse(os.path.exists(os.path.dirname(argv[argv.index("--result-file") + 1])))

    def test_ctrl_c_ends_the_tool_its_child_and_removes_the_folder(self):
        import signal
        proc, record = self.start_processor()
        self.check_after(proc, record, signal.SIGINT)

    def test_a_termination_ends_the_tool_its_child_and_removes_the_folder(self):
        import signal
        proc, record = self.start_processor()
        self.check_after(proc, record, signal.SIGTERM)
        self.assertEqual(proc.returncode, 128 + signal.SIGTERM)

    def test_a_handler_that_was_reported_as_none_is_not_set_again(self):
        import signal
        original = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, original)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        importer.restore_termination_handler(None)  # must not raise
        self.assertEqual(signal.getsignal(signal.SIGTERM), signal.SIG_IGN)
        importer.restore_termination_handler(importer.NOT_INSTALLED)
        self.assertEqual(signal.getsignal(signal.SIGTERM), signal.SIG_IGN)

    def test_the_handler_for_a_termination_is_restored_after_a_run(self):
        import signal
        original = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, original)
        before = signal.signal(signal.SIGTERM, signal.SIG_IGN)  # a known handler that is not ours
        self.assertNotEqual(before, importer.end_on_termination)
        before = signal.SIG_IGN
        run_processor(PCMAN, self.env())
        self.assertEqual(signal.getsignal(signal.SIGTERM), before)
        self.behave(exit=1, result=None, stderr="ERROR: x\n")
        with self.assertRaises(ProcessorError):
            run_processor(PCMAN, self.env())
        self.assertEqual(signal.getsignal(signal.SIGTERM), before)

    def test_outside_the_main_thread_the_processor_still_runs(self):
        import threading
        outcome = {}

        def work():
            try:
                outcome["processor"], _ = run_processor(PCMAN, self.env())
            except BaseException as err:  # noqa: BLE001
                outcome["error"] = err

        thread = threading.Thread(target=work)
        thread.start()
        thread.join(30)
        self.assertNotIn("error", outcome)
        self.assertEqual(outcome["processor"].env["pcman_result"], "published")


if __name__ == "__main__":
    unittest.main()
