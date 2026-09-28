"""Tests for ReportMatePostinstallChecker.py.

check_postinstall_text() is exercised directly (no subprocess, no files).
ReportMatePostinstallChecker's Processor is exercised end to end against
real, minimal flat packages built and read with pkgutil --flatten/--expand
entirely inside a temporary directory. Nothing is installed and no package
script is ever run; pkgutil only reads and writes the files it is told to.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

from _support import checker, patcher, read_fixture, ProcessorError

FIXTURE = read_fixture("postinstall_fixture.sh")


def munki_only_patched_text():
    """Simulate a hypothetical package whose Munki section was patched but
    whose osquery section was not -- e.g. a future regression in
    patch_postinstall() that dropped the osquery step, or an older build.
    The checker must refuse this on the osquery download/install text alone,
    independent of the marker (which patch_munki_section() already writes).
    """
    new_text, _wrapper, _reportmate = patcher.patch_munki_section(FIXTURE)
    return new_text

MINIMAL_PACKAGE_INFO = """<?xml version="1.0" encoding="utf-8"?>
<pkg-info overwrite-permissions="true" relocatable="false" identifier="com.example.reportmateclientmac.test" postinstall-action="none" version="1.0" format-version="2" install-location="/" auth="root">
    <payload numberOfFiles="0" installKBytes="0"/>
    <scripts>
        <postinstall file="./postinstall"/>
    </scripts>
</pkg-info>
"""


def build_flat_pkg(tmp_dir, postinstall_text, pkg_name="test.pkg"):
    """Build a minimal flat package containing only Scripts/postinstall,
    with pkgutil --flatten, and return its path. No Payload/Bom is needed
    for pkgutil to flatten and later expand a component package -- verified
    directly against /usr/sbin/pkgutil before this test suite was written."""
    src_dir = os.path.join(tmp_dir, "src-%s" % pkg_name)
    scripts_dir = os.path.join(src_dir, "Scripts")
    os.makedirs(scripts_dir)
    with open(os.path.join(src_dir, "PackageInfo"), "w") as handle:
        handle.write(MINIMAL_PACKAGE_INFO)
    postinstall_path = os.path.join(scripts_dir, "postinstall")
    with open(postinstall_path, "w") as handle:
        handle.write(postinstall_text)
    os.chmod(postinstall_path, 0o755)

    pkg_path = os.path.join(tmp_dir, pkg_name)
    subprocess.run(
        ["/usr/sbin/pkgutil", "--flatten", src_dir, pkg_path],
        check=True,
        capture_output=True,
        text=True,
    )
    return pkg_path


class CheckPostinstallTextTests(unittest.TestCase):
    def test_accepts_patched_text(self):
        patched = patcher.patch_postinstall(FIXTURE)
        checker.check_postinstall_text(patched)  # must not raise

    def test_refuses_upstream_text(self):
        with self.assertRaisesRegex(ValueError, "does not carry the custom-build marker"):
            checker.check_postinstall_text(FIXTURE)

    def test_refuses_text_with_marker_but_forbidden_string_reintroduced(self):
        patched = patcher.patch_postinstall(FIXTURE)
        tampered = patched + "\n# Backing up existing postflight (reintroduced)\n"
        with self.assertRaisesRegex(ValueError, "Backing up existing postflight"):
            checker.check_postinstall_text(tampered)

    def test_marker_constant_matches_patcher(self):
        self.assertEqual(checker.MARKER, patcher.MARKER)

    def test_refuses_munki_patched_text_that_still_has_osquery_download(self):
        partial = munki_only_patched_text()
        self.assertIn(checker.MARKER, partial)  # marker alone is not enough
        with self.assertRaisesRegex(ValueError, "osquery download/install"):
            checker.check_postinstall_text(partial)

    def test_refuses_text_with_marker_but_wrapper_heredoc_reintroduced(self):
        patched = patcher.patch_postinstall(FIXTURE)
        tampered = patched + "\ncat > \"$POSTFLIGHT\" << 'WRAPPER_EOF'\nfoo\nWRAPPER_EOF\n"
        with self.assertRaisesRegex(ValueError, "still opens"):
            checker.check_postinstall_text(tampered)

    def test_refuses_text_with_marker_but_reportmate_heredoc_reintroduced(self):
        patched = patcher.patch_postinstall(FIXTURE)
        tampered = patched + "\ncat > \"$X\" << 'REPORTMATE_EOF'\nfoo\nREPORTMATE_EOF\n"
        with self.assertRaisesRegex(ValueError, "still opens"):
            checker.check_postinstall_text(tampered)


class ReportMatePostinstallCheckerProcessorTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="reportmate-checker-test-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_accepts_the_custom_package(self):
        patched_text = patcher.patch_postinstall(FIXTURE)
        pkg_path = build_flat_pkg(self.tmp_dir, patched_text, "custom.pkg")

        proc = checker.ReportMatePostinstallChecker({"pkg_path": pkg_path})
        proc.main()  # must not raise
        self.assertTrue(proc.env["reportmate_postinstall_checked"])

    def test_refuses_upstream_package(self):
        pkg_path = build_flat_pkg(self.tmp_dir, FIXTURE, "upstream.pkg")

        proc = checker.ReportMatePostinstallChecker({"pkg_path": pkg_path})
        with self.assertRaisesRegex(ProcessorError, "Refusing to import"):
            proc.main()

    def test_refuses_a_package_that_still_downloads_osquery(self):
        pkg_path = build_flat_pkg(
            self.tmp_dir, munki_only_patched_text(), "munki-only.pkg"
        )

        proc = checker.ReportMatePostinstallChecker({"pkg_path": pkg_path})
        with self.assertRaisesRegex(ProcessorError, "osquery download/install"):
            proc.main()

    def test_refuses_a_package_that_still_writes_the_wrapper(self):
        patched_text = patcher.patch_postinstall(FIXTURE)
        tampered = patched_text + "\ncat > \"$POSTFLIGHT\" << 'WRAPPER_EOF'\nfoo\nWRAPPER_EOF\n"
        pkg_path = build_flat_pkg(self.tmp_dir, tampered, "still-writes-wrapper.pkg")

        proc = checker.ReportMatePostinstallChecker({"pkg_path": pkg_path})
        with self.assertRaisesRegex(ProcessorError, "still opens"):
            proc.main()

    def test_a_signed_looking_package_expands_and_is_checked_the_same_way(self):
        # pkgutil --expand does not verify or require a signature; a real
        # signature lives in a distribution archive's outer xar wrapper,
        # which --expand reads regardless. This asserts the checker's own
        # logic does not special-case an unsigned package -- it only ever
        # looks at the expanded Scripts/postinstall content.
        patched_text = patcher.patch_postinstall(FIXTURE)
        pkg_path = build_flat_pkg(self.tmp_dir, patched_text, "signed-like.pkg")

        proc = checker.ReportMatePostinstallChecker({"pkg_path": pkg_path})
        proc.main()
        self.assertTrue(proc.env["reportmate_postinstall_checked"])

    def test_cleans_up_its_temporary_directory(self):
        patched_text = patcher.patch_postinstall(FIXTURE)
        pkg_path = build_flat_pkg(self.tmp_dir, patched_text, "custom2.pkg")

        before = set(os.listdir(tempfile.gettempdir()))
        proc = checker.ReportMatePostinstallChecker({"pkg_path": pkg_path})
        proc.main()
        after = set(os.listdir(tempfile.gettempdir()))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
