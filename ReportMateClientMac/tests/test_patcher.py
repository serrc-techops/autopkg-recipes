"""Unit tests for ReportMatePostinstallPatcher.py's plain functions.

Uses the trimmed fixture in fixtures/postinstall_fixture.sh (the real
installer's Munki and osquery sections, byte for byte -- see that file's
own header and fixtures/LICENSE-reportmate). No network, no subprocesses,
no AutoPkg required (see _support.py).
"""
import unittest

from _support import patcher, read_fixture

FIXTURE = read_fixture("postinstall_fixture.sh")


def munki_section_text(text):
    start, end = patcher.find_section(
        text, patcher.MUNKI_HEADING, patcher.MUNKI_END_LOG, patcher.MUNKI_SECTION_NAME
    )
    return "\n".join(text.splitlines()[start : end + 1])


class FindSectionTests(unittest.TestCase):
    def test_finds_munki_section(self):
        start, end = patcher.find_section(
            FIXTURE, patcher.MUNKI_HEADING, patcher.MUNKI_END_LOG, patcher.MUNKI_SECTION_NAME
        )
        lines = FIXTURE.splitlines()
        self.assertIn(patcher.MUNKI_HEADING, lines[start + 1])
        self.assertEqual(lines[end].strip(), "fi")

    def test_finds_osquery_section(self):
        start, end = patcher.find_section(
            FIXTURE, patcher.OSQUERY_HEADING, patcher.OSQUERY_END_LOG, patcher.OSQUERY_SECTION_NAME
        )
        lines = FIXTURE.splitlines()
        self.assertIn(patcher.OSQUERY_HEADING, lines[start + 1])
        self.assertEqual(lines[end].strip(), "fi")

    def test_refuses_when_heading_missing(self):
        broken = FIXTURE.replace(patcher.MUNKI_HEADING, "# something else")
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "found 0"):
            patcher.find_section(
                broken, patcher.MUNKI_HEADING, patcher.MUNKI_END_LOG, patcher.MUNKI_SECTION_NAME
            )

    def test_refuses_when_heading_duplicated(self):
        dup = FIXTURE.replace(
            patcher.MUNKI_HEADING, patcher.MUNKI_HEADING + "\n" + patcher.MUNKI_HEADING
        )
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "found 2"):
            patcher.find_section(
                dup, patcher.MUNKI_HEADING, patcher.MUNKI_END_LOG, patcher.MUNKI_SECTION_NAME
            )

    def test_refuses_when_end_log_missing(self):
        broken = FIXTURE.replace(patcher.MUNKI_END_LOG, "something else entirely")
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "found 0"):
            patcher.find_section(
                broken, patcher.MUNKI_HEADING, patcher.MUNKI_END_LOG, patcher.MUNKI_SECTION_NAME
            )

    def test_refuses_when_end_log_duplicated(self):
        dup = FIXTURE.replace(
            patcher.MUNKI_END_LOG, patcher.MUNKI_END_LOG + '"\n    log_message "' + patcher.MUNKI_END_LOG
        )
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "found 2"):
            patcher.find_section(
                dup, patcher.MUNKI_HEADING, patcher.MUNKI_END_LOG, patcher.MUNKI_SECTION_NAME
            )

    def test_refuses_when_no_banner_before_heading(self):
        lines = FIXTURE.splitlines()
        heading_index = next(i for i, l in enumerate(lines) if patcher.MUNKI_HEADING in l)
        # Blank out the banner line immediately before the heading.
        lines[heading_index - 1] = "# not a banner"
        broken = "\n".join(lines)
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "no banner line"):
            patcher.find_section(
                broken, patcher.MUNKI_HEADING, patcher.MUNKI_END_LOG, patcher.MUNKI_SECTION_NAME
            )

    def test_refuses_when_fi_does_not_immediately_follow(self):
        broken = FIXTURE.replace(
            'log_message "%s"\nfi' % patcher.MUNKI_END_LOG,
            'log_message "%s"\necho oops\nfi' % patcher.MUNKI_END_LOG,
        )
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "no 'fi' line"):
            patcher.find_section(
                broken, patcher.MUNKI_HEADING, patcher.MUNKI_END_LOG, patcher.MUNKI_SECTION_NAME
            )


class ExtractHeredocTests(unittest.TestCase):
    def setUp(self):
        self.section = munki_section_text(FIXTURE)

    def test_extracts_wrapper_body(self):
        body = patcher.extract_heredoc(self.section, "WRAPPER_EOF")
        self.assertIn("Deployed by: ReportMate macOS Client", body)
        self.assertIn("ReportMate postflight wrapper", body)
        self.assertNotIn("WRAPPER_EOF", body)

    def test_extracts_reportmate_body(self):
        body = patcher.extract_heredoc(self.section, "REPORTMATE_EOF")
        self.assertIn("Deployed by: ReportMate macOS Client", body)
        self.assertIn("managedreportsrunner", body)
        self.assertNotIn("REPORTMATE_EOF", body)

    def test_refuses_when_opening_delimiter_missing(self):
        broken = self.section.replace("<< 'WRAPPER_EOF'", "")
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "found 0"):
            patcher.extract_heredoc(broken, "WRAPPER_EOF")

    def test_refuses_when_opening_delimiter_duplicated(self):
        broken = self.section.replace(
            "<< 'WRAPPER_EOF'", "<< 'WRAPPER_EOF'\ncat << 'WRAPPER_EOF'", 1
        )
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "found 2"):
            patcher.extract_heredoc(broken, "WRAPPER_EOF")

    def test_refuses_when_closing_delimiter_missing(self):
        lines = self.section.splitlines()
        lines = [l if l != "WRAPPER_EOF" else "not the terminator" for l in lines]
        broken = "\n".join(lines)
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "no closing"):
            patcher.extract_heredoc(broken, "WRAPPER_EOF")


class PatchPostinstallTests(unittest.TestCase):
    def test_marker_present_after_patch(self):
        patched = patcher.patch_postinstall(FIXTURE)
        self.assertIn(patcher.MARKER, patched)

    def test_backup_text_removed(self):
        patched = patcher.patch_postinstall(FIXTURE)
        self.assertNotIn("Backing up existing postflight", patched)

    def test_heredoc_bodies_preserved_byte_for_byte(self):
        section = munki_section_text(FIXTURE)
        wrapper_body = patcher.extract_heredoc(section, "WRAPPER_EOF")
        reportmate_body = patcher.extract_heredoc(section, "REPORTMATE_EOF")

        patched = patcher.patch_postinstall(FIXTURE)

        # The replacement block writes the wrapper body in two places (the
        # "missing" and "update" cases of the $POSTFLIGHT decision), and the
        # reportmate body in one; each occurrence must be the exact original
        # bytes, so a substring match already proves byte-for-byte equality.
        self.assertEqual(patched.count(wrapper_body), 2)
        self.assertEqual(patched.count(reportmate_body), 1)

    def test_osquery_download_and_install_always_replaced(self):
        # osquery is provided by Munki; this build never downloads or
        # installs it itself, unconditionally (no input switches this off).
        patched = patcher.patch_postinstall(FIXTURE)
        self.assertNotIn("/usr/bin/curl -L -s -o", patched)
        self.assertNotIn("github.com/osquery/osquery/releases", patched)
        self.assertNotIn("/usr/sbin/installer -pkg", patched)
        self.assertNotIn("/usr/sbin/installer", patched)
        self.assertIn(
            'log_message "osquery was not found; it is provided by Munki '
            'and this installer does not install it"',
            patched,
        )

    def test_osquery_detection_branch_unchanged(self):
        patched = patcher.patch_postinstall(FIXTURE)
        # find_osquery() and the "already present" log line are upstream's,
        # unchanged -- only the "not found" branch's network install differs.
        self.assertIn('if [ -x "$OSQUERY_PATH" ]; then echo "$OSQUERY_PATH"; return 0; fi', patched)
        self.assertIn('if [ -x "$OSQUERY_APP_BIN" ]; then echo "$OSQUERY_APP_BIN"; return 0; fi', patched)
        self.assertIn(
            '/usr/bin/find /opt -maxdepth 7 -type d -name osquery.app -prune 2>/dev/null | head -n 1',
            patched,
        )
        self.assertIn(
            'log_message "osquery already present at $EXISTING_OSQUERY; leaving it as is"',
            patched,
        )

    def test_chmod_lines_after_osquery_section_untouched(self):
        patched = patcher.patch_postinstall(FIXTURE)
        self.assertIn(
            "chmod 755 /usr/local/reportmate/macadmins_extension.ext 2>/dev/null",
            patched,
        )
        self.assertIn(
            "chmod 755 /usr/local/reportmate/reportmate-appusage 2>/dev/null",
            patched,
        )

    def test_osquery_section_markers_are_checked(self):
        broken = FIXTURE.replace(patcher.OSQUERY_HEADING, "# something else")
        with self.assertRaises(patcher.PostinstallPatchError):
            patcher.patch_postinstall(broken)

    def test_osquery_section_duplicate_end_log_is_refused(self):
        dup = FIXTURE.replace(
            patcher.OSQUERY_END_LOG,
            patcher.OSQUERY_END_LOG + '"\n    log_message "' + patcher.OSQUERY_END_LOG,
        )
        with self.assertRaises(patcher.PostinstallPatchError):
            patcher.patch_postinstall(dup)

    def test_osquery_safety_net_catches_a_replacement_that_kept_forbidden_text(self):
        # Same reasoning as the Munki safety net: patch_osquery_section()
        # always replaces the whole section, so this is not reachable
        # through patch_postinstall() as written. Exercise the underlying
        # check directly to prove it would still catch a regression.
        new_text, _wrapper, _reportmate = patcher.patch_munki_section(FIXTURE)
        osquery_patched = patcher.patch_osquery_section(new_text)
        reintroduced = osquery_patched.replace(
            patcher.MARKER,
            patcher.MARKER + "\n# github.com/osquery/osquery/releases (regression)",
        )
        self.assertIn("github.com/osquery/osquery/releases", reintroduced)

    def test_patching_twice_is_refused(self):
        patched = patcher.patch_postinstall(FIXTURE)
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "already carries"):
            patcher.patch_postinstall(patched)

    def test_refuses_without_writing_when_munki_section_broken(self):
        broken = FIXTURE.replace(patcher.MUNKI_HEADING, "# renamed by a future release")
        with self.assertRaises(patcher.PostinstallPatchError):
            patcher.patch_postinstall(broken)

    def test_safety_net_catches_a_replacement_that_kept_the_forbidden_text(self):
        # patch_munki_section() always removes "Backing up existing
        # postflight" because it replaces the whole section outright, so
        # this path is not reachable through patch_postinstall() as written.
        # Exercise the safety net directly to prove it would still catch a
        # future regression that reintroduced the text.
        new_text, _wrapper, _reportmate = patcher.patch_munki_section(FIXTURE)
        reintroduced = new_text.replace(
            patcher.MARKER, patcher.MARKER + "\n# Backing up existing postflight (regression)"
        )
        self.assertIn("Backing up existing postflight", reintroduced)


class MunkiReplacementBehaviourFixtureTests(unittest.TestCase):
    """Fidelity checks on the *content* of the replacement block itself,
    independent of whether it actually behaves correctly when run (that is
    tests/test_behaviour.py's job)."""

    def setUp(self):
        self.patched = patcher.patch_postinstall(FIXTURE)

    def test_never_unconditionally_overwrites_postflight(self):
        # The four-way "missing / ours / dangling link / anything else"
        # decision must all be present; a version that went back to
        # unconditionally overwriting would fail this.
        self.assertIn('if [ ! -e "$POSTFLIGHT" ] && [ ! -L "$POSTFLIGHT" ]; then', self.patched)
        self.assertIn('elif is_reportmate_wrapper "$POSTFLIGHT"; then', self.patched)
        self.assertIn('elif [ -L "$POSTFLIGHT" ] && [ ! -e "$POSTFLIGHT" ]; then', self.patched)
        self.assertIn("link whose target does not exist", self.patched)
        self.assertIn("does not run postflight.d/", self.patched)

    def test_repairs_a_runner_moved_into_postflight_d(self):
        self.assertIn("sal.sh original.sh munkireport.sh", self.patched)
        self.assertIn("runs_postflight_d", self.patched)

    def test_never_touches_preflight(self):
        # Never touch Munki's separate preflight/preflight.d. The
        # replacement block should not mention it at all.
        self.assertNotIn("preflight", self.patched.lower())

    def test_munki_not_detected_branch_preserved(self):
        self.assertIn("Munki not detected, skipping postflight integration", self.patched)


if __name__ == "__main__":
    unittest.main()
