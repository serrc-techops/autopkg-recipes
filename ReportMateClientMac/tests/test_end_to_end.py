"""End-to-end test against a real, released ReportMate package.

Skipped unless the environment variable REPORTMATE_UPSTREAM_PKG names a
package file. When run: pkgutil --expand it, patch a copy of its
Scripts/postinstall with patch_postinstall(), pkgutil --flatten the
result, pkgutil --expand that again, and check:

  - the custom-build marker is present in the re-expanded Scripts/postinstall,
    and neither upstream behaviour it replaces remains (the unconditional
    postflight backup; the osquery download URL and installer call);
  - Payload, Bom and PackageInfo are byte-identical to upstream's own
    expansion of the same package -- only Scripts/postinstall was ever
    touched;
  - ReportMatePostinstallChecker accepts the round-tripped package and
    refuses the original.

Uses only pkgutil --expand/--flatten (explicitly allowed) inside a
temporary directory; nothing is installed and no package script is run.
"""
import filecmp
import os
import shutil
import subprocess
import tempfile
import unittest

from _support import checker, patcher, ProcessorError

UPSTREAM_PKG = os.environ.get("REPORTMATE_UPSTREAM_PKG")


def _expand(pkg_path, dest):
    subprocess.run(
        ["/usr/sbin/pkgutil", "--expand", pkg_path, dest],
        check=True,
        capture_output=True,
        text=True,
    )
    return dest


@unittest.skipUnless(
    UPSTREAM_PKG, "set REPORTMATE_UPSTREAM_PKG to a package file to run this test"
)
class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="reportmate-e2e-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        self.original_expand = _expand(
            UPSTREAM_PKG, os.path.join(self.tmp_dir, "original-expanded")
        )

        # Patch a *copy*, so self.original_expand stays a pristine baseline.
        self.patched_expand = os.path.join(self.tmp_dir, "patched-expanded")
        shutil.copytree(self.original_expand, self.patched_expand)
        postinstall_path = os.path.join(self.patched_expand, "Scripts", "postinstall")
        with open(postinstall_path, "r") as handle:
            original_text = handle.read()
        self.patched_text = patcher.patch_postinstall(original_text)
        with open(postinstall_path, "w") as handle:
            handle.write(self.patched_text)

        self.flattened_path = os.path.join(self.tmp_dir, "patched.pkg")
        subprocess.run(
            ["/usr/sbin/pkgutil", "--flatten", self.patched_expand, self.flattened_path],
            check=True,
            capture_output=True,
            text=True,
        )

        self.reexpanded = _expand(
            self.flattened_path, os.path.join(self.tmp_dir, "reexpanded")
        )
        with open(os.path.join(self.reexpanded, "Scripts", "postinstall"), "r") as handle:
            self.reexpanded_postinstall = handle.read()

    def test_marker_present_after_round_trip(self):
        self.assertIn(patcher.MARKER, self.reexpanded_postinstall)

    def test_replaced_behaviours_absent_after_round_trip(self):
        self.assertNotIn("Backing up existing postflight", self.reexpanded_postinstall)
        self.assertNotIn(
            "github.com/osquery/osquery/releases", self.reexpanded_postinstall
        )
        self.assertNotIn("/usr/sbin/installer", self.reexpanded_postinstall)

    def test_osquery_detection_branch_survives_round_trip(self):
        self.assertIn(
            'log_message "osquery already present at $EXISTING_OSQUERY; '
            'leaving it as is"',
            self.reexpanded_postinstall,
        )

    def test_payload_bom_packageinfo_byte_identical(self):
        for name in ("Payload", "Bom", "PackageInfo"):
            original_file = os.path.join(self.original_expand, name)
            reexpanded_file = os.path.join(self.reexpanded, name)
            self.assertTrue(
                os.path.exists(original_file), "upstream package has no %s" % name
            )
            self.assertTrue(
                os.path.exists(reexpanded_file),
                "%s missing after the round trip" % name,
            )
            self.assertTrue(
                filecmp.cmp(original_file, reexpanded_file, shallow=False),
                "%s changed by the patch/pack round trip" % name,
            )

    def test_preinstall_untouched_if_present(self):
        original_preinstall = os.path.join(self.original_expand, "Scripts", "preinstall")
        if not os.path.exists(original_preinstall):
            self.skipTest("this release has no Scripts/preinstall")
        reexpanded_preinstall = os.path.join(self.reexpanded, "Scripts", "preinstall")
        self.assertTrue(filecmp.cmp(original_preinstall, reexpanded_preinstall, shallow=False))

    def test_checker_accepts_the_round_tripped_package(self):
        checker.check_postinstall_text(self.reexpanded_postinstall)  # must not raise

        proc = checker.ReportMatePostinstallChecker({"pkg_path": self.flattened_path})
        proc.main()  # must not raise
        self.assertTrue(proc.env["reportmate_postinstall_checked"])

    def test_checker_refuses_the_original_upstream_package(self):
        proc = checker.ReportMatePostinstallChecker({"pkg_path": UPSTREAM_PKG})
        with self.assertRaisesRegex(ProcessorError, "Refusing to import"):
            proc.main()


if __name__ == "__main__":
    unittest.main()
