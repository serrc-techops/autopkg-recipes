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
    """find_section() locates *upstream's* section, in the unpatched
    fixture, by its own markers -- unaffected by what this build's
    replacement contains, so these are unchanged by the launchd redesign."""

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
    """extract_heredoc() reads upstream's original heredocs -- still called
    by patch_munki_section() to validate the input looks like a genuine
    installer, even though the new replacement discards the bodies."""

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

    def test_upstream_heredocs_still_validated_even_though_discarded(self):
        # patch_munki_section() still calls extract_heredoc() on the
        # original section (to refuse a future release that no longer
        # looks like a genuine installer) even though the new replacement
        # never reuses the bodies -- a missing here-document must still
        # refuse, exactly as before the launchd redesign.
        broken = FIXTURE.replace("<< 'WRAPPER_EOF'", "")
        with self.assertRaises(patcher.PostinstallPatchError):
            patcher.patch_postinstall(broken)

    def test_backup_text_removed(self):
        patched = patcher.patch_postinstall(FIXTURE)
        self.assertNotIn("Backing up existing postflight", patched)

    def test_neither_heredoc_opening_present(self):
        # This build starts the installs collection through launchd and
        # writes neither the postflight wrapper nor postflight.d/
        # reportmate.sh -- the two here-document openings upstream's own
        # (unpatched) section has must both be absent from the output.
        patched = patcher.patch_postinstall(FIXTURE)
        self.assertNotIn("<< 'WRAPPER_EOF'", patched)
        self.assertNotIn("<< 'REPORTMATE_EOF'", patched)

    def test_neither_heredoc_body_text_present(self):
        section = munki_section_text(FIXTURE)
        wrapper_body = patcher.extract_heredoc(section, "WRAPPER_EOF")
        reportmate_body = patcher.extract_heredoc(section, "REPORTMATE_EOF")

        patched = patcher.patch_postinstall(FIXTURE)

        self.assertNotIn(wrapper_body, patched)
        self.assertNotIn(reportmate_body, patched)

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

    def test_patching_twice_is_refused(self):
        patched = patcher.patch_postinstall(FIXTURE)
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "already carries"):
            patcher.patch_postinstall(patched)

    def test_refuses_without_writing_when_munki_section_broken(self):
        broken = FIXTURE.replace(patcher.MUNKI_HEADING, "# renamed by a future release")
        with self.assertRaises(patcher.PostinstallPatchError):
            patcher.patch_postinstall(broken)


class SafetyNetTests(unittest.TestCase):
    """patch_postinstall() checks, after building each replacement, that
    none of three specific upstream behaviours survived -- structurally
    unreachable through the normal flow, since build_munki_replacement()
    and build_osquery_replacement() are fixed text that never contains
    them, but kept as an explicit last line of defence. Exercised here by
    temporarily substituting a non-compliant replacement function, so the
    check that would catch a real regression is proven to actually fire,
    not just asserted to exist."""

    def _substitute(self, attr, replacement_func):
        original = getattr(patcher, attr)
        setattr(patcher, attr, replacement_func)
        self.addCleanup(setattr, patcher, attr, original)

    def test_munki_backup_text_safety_net_fires(self):
        original = patcher.build_munki_replacement
        self._substitute(
            "build_munki_replacement",
            lambda: original() + "\n# Backing up existing postflight (regression)",
        )
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "unconditional postflight"):
            patcher.patch_postinstall(FIXTURE)

    def test_munki_heredoc_safety_net_fires_for_wrapper(self):
        original = patcher.build_munki_replacement
        self._substitute(
            "build_munki_replacement",
            lambda: original() + "\ncat > \"$POSTFLIGHT\" << 'WRAPPER_EOF'\nfoo\nWRAPPER_EOF",
        )
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "here-document"):
            patcher.patch_postinstall(FIXTURE)

    def test_munki_heredoc_safety_net_fires_for_reportmate(self):
        original = patcher.build_munki_replacement
        self._substitute(
            "build_munki_replacement",
            lambda: original() + "\ncat > \"$X\" << 'REPORTMATE_EOF'\nfoo\nREPORTMATE_EOF",
        )
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "here-document"):
            patcher.patch_postinstall(FIXTURE)

    def test_osquery_safety_net_fires(self):
        original = patcher.build_osquery_replacement
        self._substitute(
            "build_osquery_replacement",
            lambda: original() + "\n# github.com/osquery/osquery/releases (regression)",
        )
        with self.assertRaisesRegex(patcher.PostinstallPatchError, "osquery download"):
            patcher.patch_postinstall(FIXTURE)


class MunkiReplacementFidelityTests(unittest.TestCase):
    """Fidelity checks on the *content* of the replacement block itself,
    independent of whether it actually behaves correctly when run (that is
    tests/test_behaviour.py's job)."""

    def setUp(self):
        self.patched = patcher.patch_postinstall(FIXTURE)

    def test_no_longer_gated_on_munki_directory_existing(self):
        # The launchd trigger applies regardless of whether Munki is
        # installed; there is no outer "if -d MUNKI_DIR ... else ... fi"
        # wrapping the whole section any more.
        self.assertNotIn("Munki not detected, skipping postflight integration", self.patched)
        self.assertNotIn("Munki detected, installing postflight integration", self.patched)

    def test_creates_nothing_under_usr_local_munki(self):
        # No mkdir anywhere in either replaced section (rule 2: no new
        # directory, wrapper, or reportmate.sh).
        self.assertNotIn("mkdir", self.patched)

    def test_trigger_edits_watchpaths_and_throttle_interval(self):
        self.assertIn(
            'JOB_PLIST="/Library/LaunchDaemons/com.github.reportmate.installs.plist"',
            self.patched,
        )
        self.assertIn(
            'MUNKI_REPORT="/Library/Managed Installs/ManagedInstallReport.plist"',
            self.patched,
        )
        self.assertIn("-replace WatchPaths -json", self.patched)
        self.assertIn("-replace ThrottleInterval -integer 60", self.patched)

    def test_trigger_calls_launchctl_by_its_absolute_path(self):
        # An installer script must not depend on PATH for a system tool.
        self.assertIn('/bin/launchctl bootout system "$JOB_PLIST"', self.patched)
        self.assertIn('/bin/launchctl bootstrap system "$JOB_PLIST"', self.patched)
        self.assertNotIn(' launchctl bootout system "$JOB_PLIST"', self.patched)
        self.assertNotIn(' launchctl bootstrap system "$JOB_PLIST"', self.patched)

    def test_trigger_unload_before_edit_before_load_in_source_order(self):
        section = self.patched
        unload_index = section.index('/bin/launchctl bootout system "$JOB_PLIST"')
        watchpaths_index = section.index("-replace WatchPaths")
        throttle_index = section.index("-replace ThrottleInterval")
        load_index = section.index('/bin/launchctl bootstrap system "$JOB_PLIST"')
        self.assertLess(unload_index, watchpaths_index)
        self.assertLess(watchpaths_index, throttle_index)
        self.assertLess(throttle_index, load_index)

    def test_trigger_load_failure_logged_in_upstreams_own_words(self):
        # Upstream's own daemon-install loop logs failures as
        # "WARNING: failed to load {label} - collection scheduled by this
        # daemon will not run"; this build reuses that phrasing.
        self.assertIn(
            "WARNING: failed to load com.github.reportmate.installs - "
            "collection scheduled by this daemon will not run",
            self.patched,
        )

    def test_undo_only_when_postflight_is_reportmates_wrapper(self):
        self.assertIn('is_reportmate_text() {', self.patched)
        self.assertIn('grep -q "Deployed by: ReportMate macOS Client" "$1"', self.patched)
        self.assertIn('if is_reportmate_text "$POSTFLIGHT"; then', self.patched)

    def test_undo_checks_all_three_upstream_backup_names(self):
        self.assertIn("for backup in sal.sh original.sh munkireport.sh", self.patched)
        self.assertIn('mv -f "$entry" "$POSTFLIGHT"', self.patched)

    def test_undo_removes_wrapper_when_nothing_to_restore(self):
        self.assertIn('rm -f "$POSTFLIGHT"', self.patched)

    def test_undo_removes_stale_wrapper_copies_at_upstreams_two_names(self):
        self.assertIn(
            'for stale in "${POSTFLIGHT_D}/00-original.sh" "${POSTFLIGHT_D}/original.sh"',
            self.patched,
        )

    def test_reportmate_sh_removed_regardless_of_postflight_state(self):
        self.assertIn('reportmate_sh="${POSTFLIGHT_D}/reportmate.sh"', self.patched)
        self.assertIn('if is_reportmate_text "$reportmate_sh"; then', self.patched)
        self.assertIn('rm -f "$reportmate_sh"', self.patched)

    def test_never_touches_preflight(self):
        # Never touch Munki's separate preflight/preflight.d. The
        # replacement block should not mention it at all.
        self.assertNotIn("preflight", self.patched.lower())


if __name__ == "__main__":
    unittest.main()
