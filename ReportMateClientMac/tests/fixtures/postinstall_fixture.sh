#!/bin/zsh
# Trimmed fixture of ReportMate's macOS client installer postinstall script,
# for tests only. MIT licensed by ReportMate; see LICENSE-reportmate next to
# this file. Origin: reportmate/reportmate-client-mac, Scripts/postinstall,
# release ReportMate-2026.09.24.0622.pkg (com.github.reportmate).
#
# Only the two sections ReportMatePostinstallPatcher.py patches are kept
# verbatim, byte for byte, with the small amount of surrounding context they
# depend on (the shebang and log_message()). Everything else the real
# installer does -- legacy log cleanup, app relocation, LaunchDaemon
# install, preference defaults, the initial collection run -- is upstream's
# and is omitted here; a comment marks each omission and its approximate
# real line numbers so this fixture can be re-diffed against a new release.

log_message() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

# --- upstream: legacy log cleanup (real lines 15-27), omitted ---

# ═══════════════════════════════════════════════════════════════════════════
# INSTALL OSQUERY IF MISSING
# ═══════════════════════════════════════════════════════════════════════════

OSQUERY_PATH="/usr/local/bin/osqueryi"
OSQUERY_VERSION="5.21.0"  # Pin to known compatible version with macadmins extension
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
    log_message "osquery not found, installing..."

    # Determine architecture
    ARCH=$(uname -m)
    if [ "$ARCH" = "arm64" ]; then
        PKG_URL="https://github.com/osquery/osquery/releases/download/${OSQUERY_VERSION}/osquery-${OSQUERY_VERSION}.pkg"
    else
        PKG_URL="https://github.com/osquery/osquery/releases/download/${OSQUERY_VERSION}/osquery-${OSQUERY_VERSION}.pkg"
    fi

    TEMP_PKG="/tmp/osquery-${OSQUERY_VERSION}.pkg"

    log_message "Downloading osquery ${OSQUERY_VERSION}..."
    if /usr/bin/curl -L -s -o "$TEMP_PKG" "$PKG_URL"; then
        log_message "Installing osquery..."
        if /usr/sbin/installer -pkg "$TEMP_PKG" -target / >/dev/null 2>&1; then
            log_message "osquery installed successfully"
        else
            log_message "WARNING: osquery installation failed"
        fi
        rm -f "$TEMP_PKG"
    else
        log_message "WARNING: Failed to download osquery"
    fi
else
    log_message "osquery already present at $EXISTING_OSQUERY; leaving it as is"
fi

# Make extension and watcher executable
chmod 755 /usr/local/reportmate/macadmins_extension.ext 2>/dev/null
chmod 755 /usr/local/reportmate/reportmate-appusage 2>/dev/null

# --- upstream: old app-bundle cleanup, duplicate cleanup, LaunchServices
#     registration, LaunchDaemon install, /usr/local/bin symlink, /etc/paths.d
#     entry (real lines 82-185), omitted ---

# ═══════════════════════════════════════════════════════════════════════════
# MUNKI POSTFLIGHT INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════
# Install wrapper postflight that implements postflight.d/ directory support
# This allows both MunkiReport and ReportMate to run after Munki updates

MUNKI_DIR="/usr/local/munki"
POSTFLIGHT_D="${MUNKI_DIR}/postflight.d"
POSTFLIGHT="${MUNKI_DIR}/postflight"

# Only install if Munki is present
if [ -d "$MUNKI_DIR" ]; then
    log_message "Munki detected, installing postflight integration..."
    
    # Create postflight.d directory
    mkdir -p "$POSTFLIGHT_D"
    chmod 755 "$POSTFLIGHT_D"

    # Remove any stale wrapper copies that previous installs may have left in postflight.d/.
    # Old versions used "00-original.sh" or "original.sh" as the fallback backup name, which
    # means the wrapper itself could end up inside the directory it orchestrates — causing
    # an infinite loop (wrapper → runs postflight.d/ → runs itself → ...).
    for stale in "${POSTFLIGHT_D}/00-original.sh" "${POSTFLIGHT_D}/original.sh"; do
        if [ -f "$stale" ] && grep -q "Deployed by: ReportMate macOS Client" "$stale" 2>/dev/null; then
            log_message "Removing stale wrapper copy from postflight.d/: $(basename $stale)"
            rm -f "$stale"
        fi
    done

    # Backup existing postflight if it exists and isn't our wrapper
    if [ -f "$POSTFLIGHT" ]; then
        if ! grep -q "Deployed by: ReportMate macOS Client" "$POSTFLIGHT" 2>/dev/null; then
            # Identify what owns the existing postflight for an informative backup name
            if grep -qi "munkireport" "$POSTFLIGHT" 2>/dev/null; then
                BACKUP_NAME="munkireport.sh"
            elif grep -qi "sal-submit\|/sal/" "$POSTFLIGHT" 2>/dev/null; then
                BACKUP_NAME="sal.sh"
            else
                BACKUP_NAME="original.sh"
            fi
            # Only backup if we're not about to overwrite an existing same-named file
            # (i.e., a previous backup from an earlier install is already in place)
            if [ ! -f "${POSTFLIGHT_D}/${BACKUP_NAME}" ]; then
                log_message "Backing up existing postflight to postflight.d/${BACKUP_NAME}"
                mv "$POSTFLIGHT" "${POSTFLIGHT_D}/${BACKUP_NAME}"
                chmod 755 "${POSTFLIGHT_D}/${BACKUP_NAME}"
            else
                log_message "postflight.d/${BACKUP_NAME} already exists, removing superseded postflight"
                rm -f "$POSTFLIGHT"
            fi
        fi
    fi
    
    # Write the wrapper postflight (implements .d/ directory iteration). The
    # scripts are emitted here rather than copied from the app bundle so the
    # package can always recreate the hook -- a receipt says nothing about a
    # script-authored file, and the hook has been lost to other packages' cleanups.
    log_message "Installing postflight wrapper..."
    cat > "$POSTFLIGHT" << 'WRAPPER_EOF'
#!/bin/bash
# ReportMate postflight wrapper
# Deployed by: ReportMate macOS Client
#
# Munki honours a single /usr/local/munki/postflight. This wrapper runs every
# executable in /usr/local/munki/postflight.d/ in name order, passing Munki's
# runtype through, so several tools can share the slot (10-munkireport.sh,
# reportmate.sh, ...). One script failing never stops the others.

RUNTYPE="${1:-}"
POSTFLIGHT_D="/usr/local/munki/postflight.d"
LOG_DIR="/Library/Managed Reports/logs"
LOG="${LOG_DIR}/reportmate-postflight.log"
mkdir -p "$LOG_DIR" 2>/dev/null

# Same rules as the client's own log: roll on the first write of a new local
# day to reportmate-postflight-YYYY-MM-DD.log and keep the newest 30 days.
roll_log() {
    [ -s "$LOG" ] || return 0
    local last today rolled
    last=$(/usr/bin/stat -f '%Sm' -t '%Y-%m-%d' "$LOG" 2>/dev/null) || return 0
    today=$(date '+%Y-%m-%d')
    [[ "$last" < "$today" ]] || return 0
    rolled="${LOG_DIR}/reportmate-postflight-${last}.log"
    if [ -e "$rolled" ]; then
        cat "$LOG" >> "$rolled" 2>/dev/null && rm -f "$LOG"
    else
        mv "$LOG" "$rolled" 2>/dev/null
    fi
    ls -1 "${LOG_DIR}"/reportmate-postflight-????-??-??.log 2>/dev/null | sort -r | tail -n +31 | \
        while IFS= read -r old; do rm -f "$old"; done
}
roll_log
log() {
    local level="$1"; shift
    printf '[%s] %-5s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$level" "$*" >> "$LOG" 2>/dev/null
}

log INFO "Munki postflight started (runtype: ${RUNTYPE:-none})"
if [ ! -d "$POSTFLIGHT_D" ]; then
    log INFO "No postflight.d directory; nothing to run"
    exit 0
fi

count=0
for script in "$POSTFLIGHT_D"/*; do
    [ -f "$script" ] || continue
    name=$(basename "$script")
    case "$name" in .*) continue ;; esac
    if [ ! -x "$script" ]; then
        log WARN "Skipping non-executable: $name"
        continue
    fi
    # A copy of this wrapper inside the directory it orchestrates would recurse forever
    if grep -q "ReportMate postflight wrapper" "$script" 2>/dev/null; then
        log WARN "Skipping wrapper copy: $name"
        continue
    fi
    count=$((count + 1))
    log INFO "Running: $name"
    # Child output is folded into this log line by line so one grammar survives.
    "$script" "$RUNTYPE" 2>&1 | while IFS= read -r line; do log INFO "  $name: $line"; done
    rc=${PIPESTATUS[0]}
    if [ "$rc" -eq 0 ]; then
        log INFO "  $name completed successfully"
    else
        log ERROR "  $name exited $rc (continuing)"
    fi
done
log INFO "Munki postflight completed ($count script(s))"
exit 0
WRAPPER_EOF
    chmod 755 "$POSTFLIGHT"
    chown root:wheel "$POSTFLIGHT"

    # Write the ReportMate postflight.d script: collect and transmit the installs
    # module after every Munki run. This is the only scheduled path for installs.
    log_message "Installing ReportMate postflight script..."
    cat > "${POSTFLIGHT_D}/reportmate.sh" << 'REPORTMATE_EOF'
#!/bin/bash
# ReportMate installs-module postflight
# Deployed by: ReportMate macOS Client
#
# Runs after every managedsoftwareupdate so the installs module reflects the run
# that just finished. Invoked by the postflight wrapper with Munki's runtype.

RUNNER="/Applications/Utilities/Managed Reports Runner.app/Contents/MacOS/managedreportsrunner"
[ -x "$RUNNER" ] || RUNNER="/usr/local/reportmate/managedreportsrunner"
LOG_DIR="/Library/Managed Reports/logs"
LOG="${LOG_DIR}/reportmate-postflight.log"
mkdir -p "$LOG_DIR" 2>/dev/null
log() {
    local level="$1"; shift
    printf '[%s] %-5s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$level" "$*" >> "$LOG" 2>/dev/null
}

log INFO "Munki run finished (runtype: ${1:-none}); collecting installs"
if [ -x "$RUNNER" ]; then
    # Munki gives a postflight 60 seconds, and launchd kills managedsoftwareupdate's
    # whole process group when the run ends (Munki's daemons do not set
    # AbandonProcessGroup), so a child started here cannot outlive the run.
    # Hand the collection to launchd instead: the installs daemon has no schedule
    # of its own and runs --run-modules installs --force when kickstarted.
    if /bin/launchctl kickstart -k system/com.github.reportmate.installs 2>/dev/null; then
        log INFO "installs module kickstarted via launchd (com.github.reportmate.installs)"
    else
        log ERROR "launchctl kickstart of com.github.reportmate.installs failed; running inline"
        "$RUNNER" --run-modules installs --force >/dev/null 2>&1
        log INFO "installs module exited $?"
    fi
else
    log ERROR "managedreportsrunner not found; skipping"
fi
exit 0
REPORTMATE_EOF
    chmod 755 "${POSTFLIGHT_D}/reportmate.sh"
    chown root:wheel "${POSTFLIGHT_D}/reportmate.sh"

    log_message "Munki postflight integration installed"
else
    log_message "Munki not detected, skipping postflight integration"
fi

# --- upstream: preference defaults, initial collection run (real lines
#     369-396), omitted ---
exit 0
