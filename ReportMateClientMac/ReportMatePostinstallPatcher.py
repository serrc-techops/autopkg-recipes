#!/usr/local/autopkg/python
"""Patch ReportMate's postinstall: two fixed rules, always both applied.

Rule 1 -- the installs collection. Upstream starts it from a script under
/usr/local/munki/postflight.d/, which macOS Installer overwrites completely
on every install: it unconditionally replaces
/usr/local/munki/postflight with its own wrapper, backing up whatever was
there into postflight.d/. On a Mac whose postflight already runs every
script in postflight.d/ -- Zentral's Munki package does this -- the
backed-up copy is itself a runner of that same directory, so it recurses
into itself on every Munki run, without end. Zentral's Monolith
distribution also deletes and recreates postflight.d/ on every install, so
a script placed there would not survive anyway. This build instead makes
upstream's own installs-collection launchd job (already shipped,
already installed by an earlier part of postinstall) watch Munki's own
report file, and creates, changes and moves nothing under
/usr/local/munki -- except to undo whatever an earlier, unpatched install
left there.

Rule 2 -- osquery. This build never downloads or installs osquery; osquery
is provided by Munki instead. Upstream's "INSTALL OSQUERY IF MISSING"
section downloads a pinned osquery release over the network and runs
`/usr/sbin/installer` when no osquery is found; that download and install
is always replaced with one log line. Detection of an existing osquery,
and its log line, are unchanged -- only the "not found" branch's network
install is removed. There is no input to switch this off.

This module's logic is plain functions (patch_postinstall() and its
helpers) so it can be imported and unit tested without AutoPkg; see
ReportMateChecksumVerifier.py in this directory for the surrounding
Processor style, and tests/ for the tests that exercise these functions and
the behaviour of the block they produce.

The processor:
  - locates each section of Scripts/postinstall by the banner line that
    precedes it and the "fi" that follows its final log line, extracts the
    Munki section's two here-documents (validated, then discarded -- this
    build's replacement never writes them), and replaces each whole
    section with a fixed block (see build_munki_replacement() and
    build_osquery_replacement());
  - refuses, without writing anything, if a section's markers are missing,
    duplicated, or (Munki section) a here-document cannot be extracted --
    an upstream change must stop the recipe, never produce a wrongly
    patched package;
  - refuses to patch a script that already carries its own marker, which
    names both rules, so one marker proves both were applied.
"""
import hashlib
import os
import re

from autopkglib import Processor, ProcessorError

__all__ = ["ReportMatePostinstallPatcher", "PostinstallPatchError", "patch_postinstall"]


class PostinstallPatchError(Exception):
    """Raised when Scripts/postinstall cannot be safely patched."""


# A single line embedded in the replaced Munki section. Its presence is how
# this whole processor refuses to run a second time on its own output, and
# how ReportMatePostinstallChecker.py recognises the custom build. It names
# both rules this build always applies, so one marker proves both were
# patched. Bump the rule numbers if a replacement block's behaviour changes.
MARKER = (
    "# serrc-techops custom build: ReportMateClientMac postflight "
    "integration rule 3, osquery-not-installed rule 1"
)

MUNKI_HEADING = "# MUNKI POSTFLIGHT INTEGRATION"
MUNKI_END_LOG = "Munki not detected, skipping postflight integration"
MUNKI_SECTION_NAME = "Munki postflight integration"

OSQUERY_HEADING = "# INSTALL OSQUERY IF MISSING"
OSQUERY_END_LOG = "osquery already present at $EXISTING_OSQUERY; leaving it as is"
OSQUERY_SECTION_NAME = "osquery install"

# Upstream's own banner style: a comment line that is only a long run of the
# box-drawing "═" character. Both sections this module patches are wrapped
# in one, immediately before and after their heading comment.
_BANNER_RE = re.compile("^#[ \t]*═{10,}[ \t]*$")


# --------------------------------------------------------------------------
# Section location, strictly, by marker text -- never by line number, since
# upstream's own line numbers move from release to release.
# --------------------------------------------------------------------------

def _line_indices_containing(lines, needle):
    return [i for i, line in enumerate(lines) if needle in line]


def find_section(text, heading, end_log_snippet, section_name):
    """Return the 0-based (start, end) line indices, inclusive, of the
    section that starts at the banner line immediately before the line
    containing `heading` and ends at the "fi" line immediately after the
    line containing `end_log_snippet`.

    Raises PostinstallPatchError -- without having modified anything -- if
    `heading` or `end_log_snippet` is missing or appears more than once, if
    no banner line precedes the heading, or if a "fi" does not immediately
    follow the end-log line.
    """
    lines = text.splitlines()

    heading_hits = _line_indices_containing(lines, heading)
    if len(heading_hits) != 1:
        raise PostinstallPatchError(
            "expected exactly one line containing %r for the %s section, "
            "found %d" % (heading, section_name, len(heading_hits))
        )
    heading_index = heading_hits[0]

    banner_index = heading_index - 1
    if banner_index < 0 or not _BANNER_RE.match(lines[banner_index]):
        raise PostinstallPatchError(
            "no banner line immediately precedes %r (the %s section's "
            "heading, line %d)" % (heading, section_name, heading_index + 1)
        )

    end_hits = _line_indices_containing(lines, end_log_snippet)
    if len(end_hits) != 1:
        raise PostinstallPatchError(
            "expected exactly one line containing %r for the %s section, "
            "found %d" % (end_log_snippet, section_name, len(end_hits))
        )
    end_log_index = end_hits[0]

    fi_index = end_log_index + 1
    if fi_index >= len(lines) or lines[fi_index].strip() != "fi":
        raise PostinstallPatchError(
            "no 'fi' line immediately follows %r (the %s section's last "
            "log line, line %d)" % (end_log_snippet, section_name, end_log_index + 1)
        )

    if fi_index <= banner_index:
        raise PostinstallPatchError(
            "the %s section's end came before its start; its markers are "
            "out of order" % section_name
        )

    return banner_index, fi_index


def extract_heredoc(section_text, terminator):
    """Return the exact, unindented body of the single here-document opened
    with `<< 'terminator'` (quoted, so no expansion or indent-stripping)
    inside `section_text`, without its opening or closing lines.

    Raises PostinstallPatchError if the opening delimiter is missing or
    appears more than once, or its closing line is missing.
    """
    lines = section_text.splitlines()
    open_re = re.compile(r"<<\s*'%s'\s*$" % re.escape(terminator))
    open_hits = [i for i, line in enumerate(lines) if open_re.search(line)]
    if len(open_hits) != 1:
        raise PostinstallPatchError(
            "expected exactly one here-document opened with << '%s', found %d"
            % (terminator, len(open_hits))
        )
    open_index = open_hits[0]

    close_hits = [
        i for i in range(open_index + 1, len(lines)) if lines[i] == terminator
    ]
    if not close_hits:
        raise PostinstallPatchError(
            "no closing '%s' line found for the here-document opened at "
            "line %d of the section" % (terminator, open_index + 1)
        )
    close_index = close_hits[0]

    return "\n".join(lines[open_index + 1 : close_index])


# --------------------------------------------------------------------------
# Replacement text.
# --------------------------------------------------------------------------

_MUNKI_REPLACEMENT_TEMPLATE = """# ══════════════════════════════════════════════════════════════════════════════
# MUNKI POSTFLIGHT INTEGRATION
__MARKER__
# ══════════════════════════════════════════════════════════════════════════════
# The installs collection is started by launchd, watching Munki's own report
# file, not by a script under /usr/local/munki. This installer creates,
# changes and moves nothing there, except to undo what an earlier, unpatched
# install may have left behind.

JOB_PLIST="/Library/LaunchDaemons/com.github.reportmate.installs.plist"
MUNKI_REPORT="/Library/Managed Installs/ManagedInstallReport.plist"
MUNKI_DIR="/usr/local/munki"
POSTFLIGHT_D="${MUNKI_DIR}/postflight.d"
POSTFLIGHT="${MUNKI_DIR}/postflight"

is_reportmate_text() {
    grep -q "Deployed by: ReportMate macOS Client" "$1" 2>/dev/null
}

# Make the already-installed installs-collection job watch Munki's report
# file instead of waiting for anything under /usr/local/munki. Unload, edit,
# reload; every other key of the file is left as it is.
if [ -f "$JOB_PLIST" ]; then
    /bin/launchctl bootout system "$JOB_PLIST" 2>/dev/null
    /usr/bin/plutil -replace WatchPaths -json '["'"${MUNKI_REPORT}"'"]' "$JOB_PLIST"
    /usr/bin/plutil -replace ThrottleInterval -integer 60 "$JOB_PLIST"
    if /bin/launchctl bootstrap system "$JOB_PLIST" 2>/dev/null; then
        log_message "installs collection now triggers when Munki writes its report"
    else
        log_message "WARNING: failed to load com.github.reportmate.installs - collection scheduled by this daemon will not run"
    fi
else
    log_message "com.github.reportmate.installs.plist not found; skipping installs-collection trigger setup"
fi

# Undo what an earlier, unpatched install left under /usr/local/munki.
# Never touch a postflight that is not ReportMate's own wrapper -- a
# dangling link included: is_reportmate_text can't read through one, so it
# is simply never true for one, and nothing below is reached for it.
if is_reportmate_text "$POSTFLIGHT"; then
    # A stale copy of the wrapper itself, at either name upstream's own
    # installer used for that cleanup, is debris, not something to restore.
    for stale in "${POSTFLIGHT_D}/00-original.sh" "${POSTFLIGHT_D}/original.sh"; do
        if is_reportmate_text "$stale"; then
            log_message "Removing stale wrapper copy from postflight.d/: $(basename "$stale")"
            rm -f "$stale"
        fi
    done

    # Whatever upstream's installer backed up under one of its own three
    # names is what was there before it ran; put it back, as the link or
    # file it is.
    restored=""
    for backup in sal.sh original.sh munkireport.sh; do
        entry="${POSTFLIGHT_D}/${backup}"
        if [ -e "$entry" ] || [ -L "$entry" ]; then
            log_message "Restoring postflight from postflight.d/${backup}"
            mv -f "$entry" "$POSTFLIGHT"
            restored="yes"
            break
        fi
    done

    if [ -z "$restored" ]; then
        log_message "Removing ReportMate's postflight wrapper (nothing was there before)"
        rm -f "$POSTFLIGHT"
    fi
fi

# ReportMate's own postflight.d/ script, if an earlier install left one,
# regardless of what postflight now is.
reportmate_sh="${POSTFLIGHT_D}/reportmate.sh"
if is_reportmate_text "$reportmate_sh"; then
    log_message "Removing postflight.d/reportmate.sh"
    rm -f "$reportmate_sh"
fi

log_message "Done: the installs collection is started by launchd; nothing was added under /usr/local/munki"
"""


_OSQUERY_REPLACEMENT_TEXT = """# ══════════════════════════════════════════════════════════════════════════════
# INSTALL OSQUERY IF MISSING
# ══════════════════════════════════════════════════════════════════════════════
# This installer does not download or install osquery over the network;
# osquery is provided by Munki instead. Detection of an existing osquery,
# and its log line, are unchanged: an osquery already present is still
# left alone.

OSQUERY_PATH="/usr/local/bin/osqueryi"
OSQUERY_APP_BIN="/opt/osquery/lib/osquery.app/Contents/MacOS/osqueryd"

# ReportMate uses whatever osquery the device already has and never changes it. Another
# tool may own an osquery.app elsewhere under /opt, and installing the osquery pkg over it
# would make Installer relocate the new bundle on top of that copy. The client finds a
# runnable copy on its own (link, intended location, or any osquery.app under /opt), so
# the pkg is installed only when no osquery.app exists at all.
find_osquery() {
    if [ -x "$OSQUERY_PATH" ]; then echo "$OSQUERY_PATH"; return 0; fi
    if [ -x "$OSQUERY_APP_BIN" ]; then echo "$OSQUERY_APP_BIN"; return 0; fi
    /usr/bin/find /opt -maxdepth 7 -type d -name osquery.app -prune 2>/dev/null | head -n 1
}

EXISTING_OSQUERY=$(find_osquery)
if [ -z "$EXISTING_OSQUERY" ]; then
    log_message "osquery was not found; it is provided by Munki and this installer does not install it"
else
    log_message "osquery already present at $EXISTING_OSQUERY; leaving it as is"
fi"""


def build_munki_replacement():
    """Return the full, fixed replacement text for the Munki section. It
    never writes upstream's wrapper or postflight.d/reportmate.sh, so
    neither here-document body is used here -- extract_heredoc() is still
    called on the original section by patch_munki_section() below, purely
    to validate that it looks like a genuine, well-formed upstream
    installer before anything is replaced."""
    return _MUNKI_REPLACEMENT_TEMPLATE.replace("__MARKER__", MARKER)


def build_osquery_replacement():
    return _OSQUERY_REPLACEMENT_TEXT


# --------------------------------------------------------------------------
# Whole-script patch.
# --------------------------------------------------------------------------

def _splice(text, start_line, end_line, replacement_text):
    lines = text.splitlines()
    new_lines = lines[:start_line] + replacement_text.splitlines() + lines[end_line + 1 :]
    result = "\n".join(new_lines)
    if text.endswith("\n"):
        result += "\n"
    return result


def patch_munki_section(text):
    """Return (new_text, wrapper_body, reportmate_body). The two bodies are
    the original, unpatched section's -- returned for tests that need real
    upstream content to build fixture state with -- not because the
    replacement (which writes neither) uses them."""
    start, end = find_section(text, MUNKI_HEADING, MUNKI_END_LOG, MUNKI_SECTION_NAME)
    section_text = "\n".join(text.splitlines()[start : end + 1])

    wrapper_body = extract_heredoc(section_text, "WRAPPER_EOF")
    reportmate_body = extract_heredoc(section_text, "REPORTMATE_EOF")

    replacement = build_munki_replacement()
    return _splice(text, start, end, replacement), wrapper_body, reportmate_body


def patch_osquery_section(text):
    start, end = find_section(text, OSQUERY_HEADING, OSQUERY_END_LOG, OSQUERY_SECTION_NAME)
    replacement = build_osquery_replacement()
    return _splice(text, start, end, replacement)


def patch_postinstall(text):
    """Return the patched postinstall text: both rules always applied --
    the Munki postflight integration section, and the osquery section (its
    download/install replaced with one log line; osquery is provided by
    Munki, never by this installer). Raises PostinstallPatchError, without
    returning a partially patched result, on any of the refusal conditions
    described in the module docstring.
    """
    if MARKER in text:
        raise PostinstallPatchError(
            "the script already carries the custom-build marker; refusing "
            "to patch it again"
        )

    new_text, _wrapper_body, _reportmate_body = patch_munki_section(text)

    if "Backing up existing postflight" in new_text:
        # Structurally this should be unreachable, since patch_munki_section
        # replaces the whole section -- but this exact behaviour is the one
        # reason this module exists, so it gets its own explicit check.
        raise PostinstallPatchError(
            "patched text still contains upstream's unconditional postflight "
            "backup; refusing to produce it"
        )

    if "<< 'WRAPPER_EOF'" in new_text or "<< 'REPORTMATE_EOF'" in new_text:
        # This build never writes upstream's wrapper or postflight.d/
        # reportmate.sh -- the installs collection is triggered by launchd
        # instead. Structurally unreachable, since patch_munki_section
        # replaces the whole section with text that opens neither
        # here-document, but kept as an explicit check for the same reason
        # as the one above.
        raise PostinstallPatchError(
            "patched text still opens upstream's postflight wrapper or "
            "reportmate.sh here-document; refusing to produce it"
        )

    new_text = patch_osquery_section(new_text)

    if "github.com/osquery/osquery/releases" in new_text or "/usr/sbin/installer" in new_text:
        # Same reasoning as the Munki safety net above: structurally
        # unreachable, since patch_osquery_section replaces the whole
        # section, but this is the other reason this module exists.
        raise PostinstallPatchError(
            "patched text still contains upstream's osquery download or "
            "install; refusing to produce it"
        )

    return new_text


class ReportMatePostinstallPatcher(Processor):
    description = __doc__
    input_variables = {
        "expanded_pkg_path": {
            "required": True,
            "description": (
                "Path to an expanded package directory (holds Scripts/postinstall)."
            ),
        },
    }
    output_variables = {
        "postinstall_sha256_before": {
            "description": "SHA-256 of Scripts/postinstall before patching.",
        },
        "postinstall_sha256_after": {
            "description": "SHA-256 of Scripts/postinstall after patching.",
        },
    }

    def main(self):
        postinstall_path = os.path.join(
            self.env["expanded_pkg_path"], "Scripts", "postinstall"
        )
        try:
            with open(postinstall_path, "r") as handle:
                original = handle.read()
        except OSError as err:
            raise ProcessorError(
                "Could not read %s: %s" % (postinstall_path, err)
            )

        before_hash = hashlib.sha256(original.encode("utf-8")).hexdigest()
        self.env["postinstall_sha256_before"] = before_hash

        try:
            patched = patch_postinstall(original)
        except PostinstallPatchError as err:
            raise ProcessorError(
                "Refusing to patch %s: %s" % (postinstall_path, err)
            )

        with open(postinstall_path, "w") as handle:
            handle.write(patched)

        after_hash = hashlib.sha256(patched.encode("utf-8")).hexdigest()
        self.env["postinstall_sha256_after"] = after_hash

        self.output(
            "Patched %s (SHA-256 %s -> %s)"
            % (postinstall_path, before_hash[:12], after_hash[:12])
        )


if __name__ == "__main__":
    processor = ReportMatePostinstallPatcher()
    processor.execute_shell()
