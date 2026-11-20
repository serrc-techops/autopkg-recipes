#!/usr/local/autopkg/python
"""Pack the downloaded Grammarly for Windows installer into ONE self-extracting
EXE that installs Grammarly for each person who signs in, not for the account
that runs it.

Why: Grammarly for Windows installs PER USER, into the profile of the account
that runs its installer, and a Cimian client runs installers as SYSTEM. Run
plainly, the installer gives the program to SYSTEM and to nobody else (seen on
a test PC on 2026-11-13). So the item does not install Grammarly; it stages the
installer on the PC and lets each person's own sign-in install it.

What the EXE does on the PC (run by the client as SYSTEM, with no arguments):
the stub unpacks into a new folder under the temp folder and runs setup.bat,
which makes System32 the current folder and runs install-machine.ps1, by its
full path, in the 64-bit Windows PowerShell. That script

 1. makes the folder FOLDER_NAME under Program Files and gives it an explicit
    access list (SYSTEM and Administrators full control, Users read and run,
    nothing inherited) and checks it;
 2. writes GrammarlyInstaller.exe, install-user.ps1, remove.ps1,
    uninstall-user.ps1 and cleanup.ps1 into it, each beside its place,
    compared with a SHA-256 written into install-machine.ps1 at build time,
    then swapped in. The four scripts are carried INSIDE install-machine.ps1
    (base64) and written from there: from
    the extraction folder, which a standard user may add files to (it lies
    under SYSTEM's temp folder), only the installer is taken, and only by its
    SHA-256; and install-machine.ps1 stops when that folder holds anything
    the EXE did not put there (a narrowing, not a proof). Before that it
    takes a pending removal away (its two tasks and the key of its date), so
    that an install after a removal works;
 3. registers the scheduled task TASK_NAME: at the sign-in of any user, as the
    group Users (S-1-5-32-545) with least privilege, so it runs as the person
    who signed in, in that person's session, with that person's rights; its
    action runs install-user.ps1 in a hidden window;
 4. writes an entry of the Windows uninstall list under HKLM with the
    staged installer's version: the item's install check reads it;
 5. starts the task once, so that a person who is signed in now gets
    Grammarly without signing out (a failure there is only reported).

install-user.ps1 does nothing for SYSTEM and service accounts. For a person it
looks for the uninstall key "Grammarly Desktop Integrations" in that person's
own hive (the vendor's detection rule); when it is missing it runs the staged
installer with /S (and the documented parameters of the input
grammarly_installer_arguments), waits for it, and logs one line per run in
the person's local application data. It never upgrades: Grammarly updates
itself. After MAX_ATTEMPTS failed runs with one staged version it stops trying
until another version is staged.

remove.ps1 (SYSTEM; decided 2026-11-18) also removes each person's copy, and
nothing that runs as SYSTEM runs a file from, or writes into, a profile. In
this order: it compares uninstall-user.ps1 and cleanup.ps1 with the SHA-256
written into it; unregisters the install task and deletes the staged
installer and install-user.ps1; registers the task REMOVAL_TASK_NAME (any
sign-in, the group Users, least privilege, hidden: uninstall-user.ps1) and
starts it once; registers the task CLEANUP_TASK_NAME (SYSTEM, at each start
and once a day: cleanup.ps1); records the removal's UTC date in the HKLM
key SOFTWARE, MARKER_KEY_NAME; last deletes the uninstall entry.

uninstall-user.ps1 (as the person, the guards of install-user.ps1) runs the
person's own QuietUninstallString only when it is exactly the quoted path of
VENDOR_UNINSTALLER under the person's LOCALAPPDATA followed by /S, and waits up to
UNINSTALL_WAIT_SECONDS until the person's uninstall entry is gone: the entry
decides, not the exit code.

cleanup.ps1 (SYSTEM) only tests with Test-Path whether a person's profile
still holds Grammarly's uninstaller. When none does, or the removal is older
than REMOVAL_KEEP_DAYS days, it unregisters both removal tasks and deletes the
folder and the key of the date (both tasks first, then the files, cleanup.ps1
last); otherwise it does nothing. install-machine.ps1 and cleanup.ps1 share
the named mutex MUTEX_NAME, so a cleanup run never deletes what an install is
staging.

The scripts are made by the pure functions below, so tests can pin their text.
The stub is 7zS2con.sfx of the public-domain LZMA SDK, as in the
Microsoft 365 Apps folder of this repository; it ends with setup.bat's exit
code.

Verification. The vendor publishes no hash for its installer. The download
recipe runs the shared AuthenticodeVerifier on the installer BEFORE this step: it
sets signature_verified and signature_sha256 (the hash of the installer). The
importers count a download as verified only when signature_sha256 is the hash of
the file they import, and that file is the EXE built here. So this processor hands
the verification over to the EXE only when all of this holds: signature_verified
is true and signature_sha256 is the hash of the installer; the copy of the
installer that is packed has that hash too (it is hashed again after it was
copied into the stage); and the EXE is built in this run (a cached EXE is not
reused then, because nothing but its record in the cache says what it holds).
Then it replaces signature_sha256 with the hash of the EXE and leaves
signature_verified true. The EXE is then verified in this sense only: it is the
stub of the LZMA SDK archive with the pinned SHA-256, the two scripts that this
processor writes, and the installer whose signature was verified. The EXE
itself is not signed. When signature_verified is not true, nothing is handed
over (the importers then refuse a real run unless the override allows an
unverified download); a signature_sha256 of another file stops the run. A
checksum_sha256 that an earlier step left in the run is the hash of the
downloaded file, not of the EXE built here, and the importers stop on it (on
purpose).

Seen on 2026-11-16 (see the README): the first build (scripts as files in the
archive) under AutoPkg, as SYSTEM on one PC, one on-demand start of the task
that installed Grammarly for an administrator, and the removal; this form
under AutoPkg and as SYSTEM on the same PC, where its own start of the task
found Grammarly present. With this form the per-user install path and the
removal have not run. The removal of 2026-11-18 (uninstall-user.ps1,
cleanup.ps1 and the new remove.ps1) has not run on any PC.
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "GrammarlyPerUserPackager",
    "ALLOWED_ARGUMENTS",
    "parse_installer_arguments",
    "check_version",
    "setup_bat",
    "machine_script",
    "user_script",
    "remove_script",
    "uninstall_script",
    "cleanup_script",
    "settings_digest",
    "SETUP_CODES",
    "REMOVE_CODES",
    "UNINSTALL_USER_CODES",
    "CLEANUP_CODES",
]

# What the PC gets. None of these names an organisation.
FOLDER_NAME = "Grammarly Deployment"
TASK_NAME = "Grammarly per-user install"
MARKER_KEY_NAME = "GrammarlyPerUserDeployment"
DISPLAY_NAME = "Grammarly per-user deployment"
INSTALLER_NAME = "GrammarlyInstaller.exe"
USER_SCRIPT_NAME = "install-user.ps1"
REMOVE_SCRIPT_NAME = "remove.ps1"
MACHINE_SCRIPT_NAME = "install-machine.ps1"
UNINSTALL_SCRIPT_NAME = "uninstall-user.ps1"
CLEANUP_SCRIPT_NAME = "cleanup.ps1"
# The two tasks of a removal: one runs as each person at sign-in, one as SYSTEM.
REMOVAL_TASK_NAME = "Grammarly per-user removal"
CLEANUP_TASK_NAME = "Grammarly removal cleanup"
# The value under HKLM:\SOFTWARE\<MARKER_KEY_NAME> that holds the removal's UTC date, and its form.
REMOVAL_DATE_VALUE = "RemovedUtc"
REMOVAL_DATE_FORMAT = "yyyy-MM-dd"
# The vendor's detection rule: this key in the user's own hive, value DisplayVersion.
VENDOR_UNINSTALL_KEY = "Grammarly Desktop Integrations"
# The person's own uninstaller of Grammarly, under the person's local application data; that
# key's QuietUninstallString is this path in quotes followed by /S (read on a PC on 2026-11-18).
VENDOR_UNINSTALLER = r"Grammarly\DesktopIntegrations\Uninstall.exe"
VENDOR_UNINSTALL_ARGUMENT = "/S"
# Where local application data lies in a profile (for the look of cleanup.ps1 only).
PROFILE_LOCAL_APPDATA = r"AppData\Local"
# The SIDs of people: local and domain accounts, and Microsoft Entra accounts.
PERSON_SID_PATTERN = "^S-1-(5-21|12-1)-"
USERS_SID = "S-1-5-32-545"
SYSTEM_SID = "S-1-5-18"
ADMINISTRATORS_SID = "S-1-5-32-544"
# A person's run gives up after this many failed runs with one staged version.
MAX_ATTEMPTS = 3
# How long a person's run waits for the installer before it lets it be (seconds).
INSTALLER_WAIT_SECONDS = 900
# The sign-in trigger waits this long, so that the session is up first.
LOGON_DELAY = "PT30S"
TASK_TIME_LIMIT_MINUTES = 30
# How long a person's removal run waits for that person's uninstall entry to go (seconds), and
# how often it looks: the vendor's uninstaller may hand over to a copy of itself and return early.
UNINSTALL_WAIT_SECONDS = 600
UNINSTALL_POLL_SECONDS = 5
# A removal ends this many days after its date even when a profile still has Grammarly.
REMOVAL_KEEP_DAYS = 90
# The cleanup task runs at each start and once a day at this local time.
CLEANUP_DAILY_AT = "12:00"
# One lock that install-machine.ps1 and cleanup.ps1 share (a named mutex in the Global namespace):
# a cleanup run that is already going when an install starts would otherwise delete the folder
# that the install stages (Unregister-ScheduledTask does not stop a running instance). The
# install waits for it up to MUTEX_WAIT_SECONDS; cleanup does not wait and does nothing when it
# is held.
MUTEX_NAME = r"Global\GrammarlyPerUserDeployment"
MUTEX_WAIT_SECONDS = 120

# The parameters of the vendor's article "How to deploy Grammarly for Windows"
# (read on 2026-11-13). The names are case-sensitive. /S is always given.
ALLOWED_ARGUMENTS = ("/do-not-create-desktop-shortcut", "/disable-launch-at-startup", "/ignore-os-version")

VERSION_PATTERN = re.compile(r"[0-9]{1,9}(\.[0-9]{1,9}){1,3}", re.ASCII)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}", re.ASCII)

FETCH_TIMEOUT_SECONDS = 120
MAX_SDK_BYTES = 16 * 1024 * 1024
# The stub (32-bit) holds a whole file in memory while it unpacks it. The
# installer was about 87 MB on 2026-11-13; a much larger file is not this program.
MAX_INSTALLER_BYTES = 256 * 1024 * 1024
STUB_MEMBER = "bin/7zS2con.sfx"
# What the shared AuthenticodeVerifier sets for the installer (see "Verification" above).
SIGNATURE_FLAG_VARIABLE = "signature_verified"
SIGNATURE_HASH_VARIABLE = "signature_sha256"
# Every packed file gets this time and mode, so that the same installer and scripts
# pack to the same bytes on any day and in any cache folder (2020-01-01 00:00 UTC).
PACKED_FILE_TIME = 1577836800
PACKED_FILE_MODE = 0o644
USER_AGENT = "autopkg-GrammarlyPerUserPackager"
SEVENZIP_NAMES = ("7zz", "7z", "7za")
SEVENZIP_FOLDERS = ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin")

SETUP_CODES = {
    40: "System32 could not be made the current folder",
    41: "install-machine.ps1 was not run as an administrator or SYSTEM",
    42: "the folder could not be made, or its access list is not the one that was set",
    43: "a file could not be staged (or the unpacked installer is not the one that was packed)",
    44: "the scheduled task could not be registered, or it is not the one that was asked for",
    45: "the entry of the uninstall list could not be written",
    46: "a 32-bit PowerShell on a 64-bit Windows (the 64-bit one could not be started)",
    48: "the extraction folder holds a file or folder that the EXE did not put there",
    49: "a pending removal (its two tasks or the key of its date) could not be taken away, or the lock shared "
        "with the cleanup could not be taken: at once when another account holds its name with an access list "
        "that refuses SYSTEM, else after MUTEX_WAIT_SECONDS",
}
# What the stub unpacks; anything else in the extraction folder stops the run.
EXTRACTED_NAMES = ("setup.bat", "install-machine.ps1", "GrammarlyInstaller.exe")
REMOVE_CODES = {
    41: "remove.ps1 was not run as an administrator or SYSTEM",
    46: "a 32-bit PowerShell on a 64-bit Windows",
    47: "the install task, the staged installer, install-user.ps1 or (last) the uninstall entry could not be removed",
    50: "uninstall-user.ps1 or cleanup.ps1 is missing or not the one that was packed, or the folder or one of "
        "them may be changed by an account other than SYSTEM and Administrators (nothing was changed)",
    51: "the per-user removal task could not be registered, or it is not the one that was asked for",
    52: "the cleanup task could not be registered, or it is not the one that was asked for",
    53: "the date of the removal could not be recorded",
}
UNINSTALL_USER_CODES = {
    0: "nothing to do for this account, another run of the same person is going on, no Grammarly in "
       "this profile, or Grammarly was removed (the person's uninstall entry is gone)",
    1: "not removed: the person's uninstall command is not the expected one, the uninstaller is missing, "
       "the entry is still there after the wait, or an error",
}
CLEANUP_CODES = {
    0: "nothing to do yet (an install is there, or a profile still has Grammarly within the days), or the "
       "removal was ended",
    41: "cleanup.ps1 was not run as an administrator or SYSTEM",
    46: "a 32-bit PowerShell on a 64-bit Windows",
    54: "a removal task could not be unregistered (nothing was deleted; the next run tries again), or, with both "
        "tasks already unregistered, a file, the folder or the key of the date could not be deleted (they stay, "
        "inert: no task runs them; an administrator deletes them, or the next install takes them over)",
}


def check_version(version):
    """The version label, or raise ValueError: numbers and dots only, two to four numbers."""
    text = str(version).strip()
    if not VERSION_PATTERN.fullmatch(text):
        raise ValueError("the version %r is not two to four numbers with dots" % text[:40])
    return text


def check_sha256(value):
    text = str(value).strip().lower()
    if not SHA256_PATTERN.fullmatch(text):
        raise ValueError("%r is not a SHA-256 (64 hex digits)" % text[:70])
    return text


def parse_installer_arguments(text):
    """The parameters for the installer beside /S, from a text of names separated
    by spaces or commas. Each must be one of ALLOWED_ARGUMENTS, exactly (the vendor's
    names are case-sensitive); a repeated one is refused."""
    names = [name for name in re.split(r"[\s,]+", str(text or "")) if name]
    seen = []
    for name in names:
        if name not in ALLOWED_ARGUMENTS:
            raise ValueError("the installer parameter %r is not one of %s (the names are case-sensitive)" % (
                name[:60], ", ".join(ALLOWED_ARGUMENTS)))
        if name in seen:
            raise ValueError("the installer parameter %s is given twice" % name)
        seen.append(name)
    return seen


def _fill(template, values):
    """Put the values into a script template; every @NAME@ must be filled."""
    text = template
    for name, value in values.items():
        text = text.replace("@%s@" % name, value)
    left = re.findall(r"@[A-Z_]+@", text)
    if left:
        raise ValueError("unfilled placeholders: %s" % ", ".join(sorted(set(left))))
    text.encode("ascii")
    return text


def _crlf(text):
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def setup_bat():
    """The text of setup.bat (CRLF lines). The stub is a 32-bit program, so cmd.exe
    may be the 32-bit one: Sysnative then names the 64-bit PowerShell, whose
    Program Files, registry and task cmdlets are the machine's own. System32,
    not the extraction folder, is the current folder, and every program is
    named by its full path."""
    native = r"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
    from_32_bit = r"%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
    lines = [
        "@echo off",
        "setlocal",
        r'cd /d "%SystemRoot%\System32" || exit 40',
        'set "PS=' + native + '"',
        'if exist "' + from_32_bit + '" set "PS=' + from_32_bit + '"',
        '"%PS%" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0' + MACHINE_SCRIPT_NAME + '"',
        "exit %ERRORLEVEL%",
    ]
    return "\r\n".join(lines) + "\r\n"


_COMMON_HEAD = r"""
function Fail([int]$Code, [string]$Text) {
    Write-Output ('ERROR ' + $Code + ': ' + $Text)
    exit $Code
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Fail 41 'not run as an administrator or SYSTEM' }
if ([Environment]::Is64BitOperatingSystem -and -not [Environment]::Is64BitProcess) { Fail 46 'a 32-bit PowerShell on a 64-bit Windows' }
$ProgramFolder = $env:ProgramFiles
$Folder = Join-Path $ProgramFolder $FolderName
$MarkerKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\' + $MarkerKeyName
$RemovalKey = 'HKLM:\SOFTWARE\' + $MarkerKeyName
"""

# The check of an access list: SYSTEM and Administrators may do anything, Users may read and run,
# nobody else may change anything. Shared by install-machine.ps1 and remove.ps1.
_FOLDER_ACCESS = r"""
$writeRights = [Security.AccessControl.FileSystemRights]'WriteData, AppendData, WriteExtendedAttributes, WriteAttributes, Delete, DeleteSubdirectoriesAndFiles, ChangePermissions, TakeOwnership'
function Test-FolderAccess([string]$Path, [bool]$Owner) {
    $acl = Get-Acl -LiteralPath $Path
    $ownerSid = $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
    if ($Owner -and @('@SYSTEM_SID@', '@ADMINISTRATORS_SID@') -notcontains $ownerSid) { return "the owner of $Path is $ownerSid" }
    $usersRead = $false
    foreach ($rule in $acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
        if ($rule.AccessControlType -ne 'Allow') { continue }
        $sid = $rule.IdentityReference.Value
        if (@('@SYSTEM_SID@', '@ADMINISTRATORS_SID@') -contains $sid) { continue }
        if (($rule.FileSystemRights -band $writeRights) -ne 0) { return "$sid may change $Path" }
        if ($sid -eq $UsersSid -and ($rule.FileSystemRights -band [Security.AccessControl.FileSystemRights]::ReadAndExecute) -eq [Security.AccessControl.FileSystemRights]::ReadAndExecute) { $usersRead = $true }
    }
    if (-not $usersRead) { return "Users may not read $Path" }
    return ''
}
"""

# The accounts that a per-user run leaves alone. Shared by install-user.ps1 and uninstall-user.ps1.
_PERSON_GUARDS = r"""
# Nothing for SYSTEM, the service accounts and other built-in accounts: only a local or
# domain account (S-1-5-21-...) or a Microsoft Entra account (S-1-12-1-...).
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
if ($sid -notmatch '@PERSON_SID_PATTERN@') { exit 0 }
# Nor for the accounts of the first setup and of Windows Sandbox: throwaway profiles.
$account = [Environment]::UserName
if ($account -like 'defaultuser*' -or $account -eq 'WDAGUtilityAccount') { exit 0 }
"""


def _snippets(template):
    """Put the shared pieces into a template (before _fill fills the values)."""
    for name, text in (("COMMON_HEAD", _COMMON_HEAD), ("FOLDER_ACCESS", _FOLDER_ACCESS), ("PERSON_GUARDS", _PERSON_GUARDS)):
        template = template.replace("@%s@" % name, text.strip("\n"))
    return template


MACHINE_TEMPLATE = r"""# Stages the Grammarly for Windows installer so that each person who signs in gets Grammarly
# in their own profile. Run by setup.bat as SYSTEM (or an administrator), from the folder that
# the self-extracting EXE unpacked into. Exit 0 only when everything is in place. The four
# scripts that it stages are carried in this file; from the extraction folder only the
# installer is taken, and only when it has the SHA-256 below.
$ErrorActionPreference = 'Stop'
$Version = '@VERSION@'
$Sha256 = '@SHA256@'
$FolderName = '@FOLDER_NAME@'
$TaskName = '@TASK_NAME@'
$RemovalTaskName = '@REMOVAL_TASK_NAME@'
$CleanupTaskName = '@CLEANUP_TASK_NAME@'
$MarkerKeyName = '@MARKER_KEY_NAME@'
$DisplayName = '@DISPLAY_NAME@'
$UsersSid = '@USERS_SID@'
@COMMON_HEAD@
$here = $PSScriptRoot
$source = Join-Path $here '@INSTALLER_NAME@'

# 0. The extraction folder lies under SYSTEM's temp folder, where a standard user may create
# files. It must hold what the EXE put there and nothing else. This narrows the risk; it is
# not a proof (a file made and removed again in between is not seen).
$expected = @(@EXTRACTED_NAMES@)
try {
    $found = @(Get-ChildItem -LiteralPath $here -Force -Recurse | ForEach-Object { $_.FullName.Substring($here.Length).TrimStart('\') })
} catch { Fail 48 ('the extraction folder could not be listed: ' + $_.Exception.Message) }
$extra = @($found | Where-Object { $expected -notcontains $_ })
if ($extra.Count -gt 0) { Fail 48 ('the extraction folder holds what the EXE did not put there: ' + ($extra -join ', ')) }
try {
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $Sha256) { Fail 43 'the unpacked installer is not the one that was packed' }
} catch { Fail 43 ('the unpacked installer could not be read: ' + $_.Exception.Message) }

# 0a. The lock shared with cleanup.ps1, held from here until the entry is written: a cleanup run
# that started before this install would otherwise delete the folder staged below (unregistering
# its task does not stop a run that is going). A lock left by a run that died counts as taken.
$owned = $false
try {
    $mutex = New-Object Threading.Mutex($false, '@MUTEX_NAME@')
    $owned = $mutex.WaitOne(@MUTEX_WAIT_SECONDS@ * 1000)
} catch {
    if ($_.Exception.GetBaseException() -is [Threading.AbandonedMutexException]) { $owned = $true } else { Fail 49 ('the lock shared with the cleanup could not be taken: ' + $_.Exception.Message) }
}
if (-not $owned) { Fail 49 'a cleanup run holds the lock shared with it' }

# 0b. A removal that is still pending (its two tasks and the key of its date) is taken away
# first, so that an install after a removal works and a later removal starts afresh. The
# folder itself is staged again below.
try {
    foreach ($name in @($RemovalTaskName, $CleanupTaskName)) {
        if (Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $name -TaskPath '\' -Confirm:$false
        }
    }
    if (Test-Path -LiteralPath $RemovalKey) { Remove-Item -LiteralPath $RemovalKey -Recurse -Force }
} catch { Fail 49 ('a pending removal could not be taken away: ' + $_.Exception.Message) }

# 1. The folder: SYSTEM and Administrators full control, Users read and run, nothing inherited.
@FOLDER_ACCESS@
try {
    if (-not (Test-Path -LiteralPath $Folder -PathType Container)) { New-Item -ItemType Directory -Path $Folder | Out-Null }
    $security = New-Object Security.AccessControl.DirectorySecurity
    $security.SetOwner((New-Object Security.Principal.SecurityIdentifier('@ADMINISTRATORS_SID@')))
    $security.SetAccessRuleProtection($true, $false)
    $inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    $propagate = [Security.AccessControl.PropagationFlags]::None
    foreach ($pair in @(('@SYSTEM_SID@', 'FullControl'), ('@ADMINISTRATORS_SID@', 'FullControl'), ($UsersSid, 'ReadAndExecute'))) {
        $sid = New-Object Security.Principal.SecurityIdentifier($pair[0])
        $rights = [Security.AccessControl.FileSystemRights]$pair[1]
        $security.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid, $rights, $inherit, $propagate, 'Allow')))
    }
    (Get-Item -LiteralPath $Folder).SetAccessControl($security)
} catch { Fail 42 ('the folder could not be made or its access set: ' + $_.Exception.Message) }
$problem = Test-FolderAccess $Folder $true
if ($problem) { Fail 42 $problem }

# 2. The files: each is written beside its place, compared with the SHA-256 that the packer
# wrote into this script, and swapped in. The four scripts come from this file, not from the
# extraction folder; uninstall-user.ps1 and cleanup.ps1 lie unused until a removal, which
# compares them again before it registers its tasks. A person's run copies the installer away
# before it runs it, so the staged file is held only briefly.
function Install-Staged([string]$To, [string]$Hash, [byte[]]$Bytes, [string]$From) {
    $new = $To + '.new'
    if ($From) { [IO.File]::Copy($From, $new, $true) } else { [IO.File]::WriteAllBytes($new, $Bytes) }
    if ((Get-FileHash -LiteralPath $new -Algorithm SHA256).Hash -ne $Hash) {
        Remove-Item -LiteralPath $new -Force
        throw "the new $To is not the one that was packed"
    }
    for ($try = 1; $try -le 10; $try++) {
        try {
            if (Test-Path -LiteralPath $To) { [IO.File]::Replace($new, $To, [NullString]::Value) } else { [IO.File]::Move($new, $To) }
            return
        } catch {
            if ($try -eq 10) { throw }
            Start-Sleep -Seconds 3
        }
    }
}
$staged = @{
    '@INSTALLER_NAME@' = $Sha256
    '@USER_SCRIPT_NAME@' = '@USER_SCRIPT_SHA256@'
    '@REMOVE_SCRIPT_NAME@' = '@REMOVE_SCRIPT_SHA256@'
    '@UNINSTALL_SCRIPT_NAME@' = '@UNINSTALL_SCRIPT_SHA256@'
    '@CLEANUP_SCRIPT_NAME@' = '@CLEANUP_SCRIPT_SHA256@'
}
try {
    Install-Staged (Join-Path $Folder '@INSTALLER_NAME@') $Sha256 $null $source
    Install-Staged (Join-Path $Folder '@USER_SCRIPT_NAME@') '@USER_SCRIPT_SHA256@' ([Convert]::FromBase64String('@USER_SCRIPT_BASE64@')) ''
    Install-Staged (Join-Path $Folder '@REMOVE_SCRIPT_NAME@') '@REMOVE_SCRIPT_SHA256@' ([Convert]::FromBase64String('@REMOVE_SCRIPT_BASE64@')) ''
    Install-Staged (Join-Path $Folder '@UNINSTALL_SCRIPT_NAME@') '@UNINSTALL_SCRIPT_SHA256@' ([Convert]::FromBase64String('@UNINSTALL_SCRIPT_BASE64@')) ''
    Install-Staged (Join-Path $Folder '@CLEANUP_SCRIPT_NAME@') '@CLEANUP_SCRIPT_SHA256@' ([Convert]::FromBase64String('@CLEANUP_SCRIPT_BASE64@')) ''
    foreach ($name in $staged.Keys) {
        if ((Get-FileHash -LiteralPath (Join-Path $Folder $name) -Algorithm SHA256).Hash -ne $staged[$name]) { throw "the staged $name is not the one that was packed" }
    }
} catch { Fail 43 ('a file could not be staged: ' + $_.Exception.Message) }
foreach ($name in $staged.Keys) {
    # A file's owner is whoever ran this (an administrator may own it); only the rights count.
    $problem = Test-FolderAccess (Join-Path $Folder $name) $false
    if ($problem) { Fail 42 $problem }
}

# 3. The task: at the sign-in of any user, as the group Users, least privilege, so that it
# runs as the person who signed in. Its window is hidden (a console may flash briefly).
try {
    $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $userScript = Join-Path $Folder '@USER_SCRIPT_NAME@'
    $action = New-ScheduledTaskAction -Execute $powershell -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $userScript + '"')
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $trigger.Delay = '@LOGON_DELAY@'
    $taskPrincipal = New-ScheduledTaskPrincipal -GroupId $UsersSid -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances Parallel -ExecutionTimeLimit (New-TimeSpan -Minutes @TASK_TIME_LIMIT_MINUTES@)
    Register-ScheduledTask -TaskName $TaskName -TaskPath '\' -Action $action -Trigger $trigger -Principal $taskPrincipal -Settings $settings -Description 'Installs Grammarly for Windows into the profile of the person who signs in, when it is not there.' -Force | Out-Null
    $task = Get-ScheduledTask -TaskName $TaskName -TaskPath '\'
    $group = [string]$task.Principal.GroupId
    if ($group -notmatch '^S-1-') { $group = (New-Object Security.Principal.NTAccount($group)).Translate([Security.Principal.SecurityIdentifier]).Value }
} catch { Fail 44 ('the task could not be registered: ' + $_.Exception.Message) }
if ($group -ne $UsersSid) { Fail 44 ('the task runs as ' + $group + ', not as the group Users') }
if ([string]$task.Principal.RunLevel -ne 'Limited') { Fail 44 ('the task runs with ' + $task.Principal.RunLevel + ', not with least privilege') }

# 4. The entry of the uninstall list, last: the item's install check reads its DisplayVersion.
try {
    if (-not (Test-Path -LiteralPath $MarkerKey)) { New-Item -Path $MarkerKey | Out-Null }
    $remove = '"' + (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') + '" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + (Join-Path $Folder '@REMOVE_SCRIPT_NAME@') + '"'
    Set-ItemProperty -LiteralPath $MarkerKey -Name 'DisplayName' -Value $DisplayName
    Set-ItemProperty -LiteralPath $MarkerKey -Name 'InstallLocation' -Value $Folder
    Set-ItemProperty -LiteralPath $MarkerKey -Name 'UninstallString' -Value $remove
    Set-ItemProperty -LiteralPath $MarkerKey -Name 'QuietUninstallString' -Value $remove
    Set-ItemProperty -LiteralPath $MarkerKey -Name 'NoModify' -Value 1 -Type DWord
    Set-ItemProperty -LiteralPath $MarkerKey -Name 'NoRepair' -Value 1 -Type DWord
    Set-ItemProperty -LiteralPath $MarkerKey -Name 'DisplayVersion' -Value $Version
} catch { Fail 45 ('the entry could not be written: ' + $_.Exception.Message) }
# The entry is there: a cleanup run now sees the install and does nothing, so the lock may go.
try { $mutex.ReleaseMutex() } catch { }

# 5. Start the task once now, so that a person who is signed in gets Grammarly without signing
# out. Seen on 2026-11-16: an on-demand start ran in the signed-in person's session. A failure
# (nobody signed in, say) is only reported: the task runs at the next sign-in anyway.
try {
    Start-ScheduledTask -TaskName $TaskName -TaskPath '\'
    $started = 'started it once for the people signed in'
} catch { $started = 'could not start it now (' + $_.Exception.Message + '); it runs at the next sign-in' }
Write-Output ('Staged Grammarly ' + $Version + ' in ' + $Folder + ', registered the task ' + $TaskName + ' and ' + $started + '.')
exit 0
"""

USER_TEMPLATE = r"""# Installs Grammarly for Windows into the profile of the person who signed in, once, from the
# installer that the machine install staged beside this script. Run by the scheduled task
# '@TASK_NAME@' as that person, with that person's own rights. It never elevates and never
# upgrades: Grammarly updates itself. One line per run goes to the person's log.
$ErrorActionPreference = 'Stop'
$Version = '@VERSION@'
$Sha256 = '@SHA256@'
$InstallerArguments = @(@ARGUMENTS@)
$MaxAttempts = @MAX_ATTEMPTS@
$WaitSeconds = @INSTALLER_WAIT_SECONDS@

@PERSON_GUARDS@

$staged = Join-Path $PSScriptRoot '@INSTALLER_NAME@'
$vendorKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\@VENDOR_UNINSTALL_KEY@'
$stateKey = 'HKCU:\Software\@MARKER_KEY_NAME@'
$logFolder = Join-Path $env:LOCALAPPDATA '@MARKER_KEY_NAME@'
$log = Join-Path $logFolder 'install.log'
$lock = $null
$work = $null

function Finish([string]$Text, [int]$Code) {
    try {
        if ((Test-Path -LiteralPath $log) -and (Get-Item -LiteralPath $log).Length -gt 262144) { Move-Item -LiteralPath $log -Destination ($log + '.old') -Force }
        Add-Content -LiteralPath $log -Value ((Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz') + ' ' + $Text) -Encoding Ascii
    } catch { }
    if ($work) { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
    if ($lock) { $lock.Close() }
    exit $Code
}

try {
    if (-not (Test-Path -LiteralPath $logFolder)) { New-Item -ItemType Directory -Path $logFolder | Out-Null }
    # One run per person at a time (a second session of the same person signs in, say).
    try { $lock = [IO.File]::Open((Join-Path $logFolder 'install.lock'), 'OpenOrCreate', 'ReadWrite', 'None') } catch { exit 0 }

    $present = $null
    try { $present = (Get-ItemProperty -LiteralPath $vendorKey -Name 'DisplayVersion' -ErrorAction Stop).DisplayVersion } catch { }
    if ($present) { Finish ('present (' + $present + '): nothing to do') 0 }
    if (-not (Test-Path -LiteralPath $staged)) { Finish 'the staged installer is missing: nothing done' 0 }

    $attempts = 0
    if (Test-Path -LiteralPath $stateKey) {
        $state = Get-ItemProperty -LiteralPath $stateKey
        if ([string]$state.Version -eq $Version) { $attempts = [int]$state.Attempts }
    }
    if ($attempts -ge $MaxAttempts) { Finish ('not tried: ' + $attempts + ' failed runs with ' + $Version + ' already') 0 }

    # The installer runs from a copy in the person's temp folder, so that the staged file is
    # free for the next machine install.
    $work = Join-Path ([IO.Path]::GetTempPath()) ('GrammarlyPerUser-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $work | Out-Null
    $copy = Join-Path $work '@INSTALLER_NAME@'
    Copy-Item -LiteralPath $staged -Destination $copy
    if ((Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash -ne $Sha256) { Finish 'the staged installer changed while it was copied (a new version is being staged): nothing run' 0 }

    if (-not (Test-Path -LiteralPath $stateKey)) { New-Item -Path $stateKey | Out-Null }
    Set-ItemProperty -LiteralPath $stateKey -Name 'Version' -Value $Version
    Set-ItemProperty -LiteralPath $stateKey -Name 'Attempts' -Value ($attempts + 1) -Type DWord

    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $copy
    $info.Arguments = (@('/S') + $InstallerArguments) -join ' '
    $info.UseShellExecute = $false
    $info.WorkingDirectory = $work
    $process = [Diagnostics.Process]::Start($info)
    # Wait for the installer itself, not for the program that it may start.
    if ($process.WaitForExit($WaitSeconds * 1000)) {
        $code = 'exit code ' + $process.ExitCode
    } else {
        $code = 'still running after ' + $WaitSeconds + ' seconds'
        $work = $null  # still in use: left for the temp folder's own cleanup
    }
    # The vendor's detection rule decides, not the exit code.
    $after = $null
    try { $after = (Get-ItemProperty -LiteralPath $vendorKey -Name 'DisplayVersion' -ErrorAction Stop).DisplayVersion } catch { }
    if ($after) {
        Remove-Item -LiteralPath $stateKey -Recurse -Force -ErrorAction SilentlyContinue
        Finish ('installed ' + $after + ' from the staged ' + $Version + ' (installer: ' + $code + ')') 0
    }
    Finish ('not installed: the installer ' + $Version + ', ' + $code + ', and no key: attempt ' + ($attempts + 1) + ' of ' + $MaxAttempts) 1
} catch {
    Finish ('error: ' + $_.Exception.Message) 1
}
"""

REMOVE_TEMPLATE = r"""# Removes the Grammarly per-user item from the PC and, through each person's own sign-in,
# Grammarly from each profile. Run as SYSTEM or an administrator. Nothing here runs a file from,
# or writes into, a person's profile. In this order: the two removal scripts that the install
# staged are compared with their SHA-256 (nothing is changed when they differ); the install task
# goes, then the staged installer and install-user.ps1 (no new installs); the removal task (at the
# sign-in of any user, as that person) and the cleanup task (as SYSTEM) are registered; the
# removal's date is recorded; last, the entry of the uninstall list goes. Exit 0 only when all of
# that holds.
$ErrorActionPreference = 'Stop'
$FolderName = '@FOLDER_NAME@'
$TaskName = '@TASK_NAME@'
$RemovalTaskName = '@REMOVAL_TASK_NAME@'
$CleanupTaskName = '@CLEANUP_TASK_NAME@'
$MarkerKeyName = '@MARKER_KEY_NAME@'
$UsersSid = '@USERS_SID@'
@COMMON_HEAD@
@FOLDER_ACCESS@
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

# 1. The two scripts that the removal runs were staged by the install from its own text; they must
# still have the SHA-256 that the packer wrote here, and only SYSTEM and Administrators may
# change them or the folder (which keeps its access list).
$removal = @{
    '@UNINSTALL_SCRIPT_NAME@' = '@UNINSTALL_SCRIPT_SHA256@'
    '@CLEANUP_SCRIPT_NAME@' = '@CLEANUP_SCRIPT_SHA256@'
}
try {
    foreach ($name in $removal.Keys) {
        if ((Get-FileHash -LiteralPath (Join-Path $Folder $name) -Algorithm SHA256).Hash -ne $removal[$name]) { Fail 50 ('the staged ' + $name + ' is not the one that was packed') }
    }
    $problem = Test-FolderAccess $Folder $true
    foreach ($name in $removal.Keys) {
        if (-not $problem) { $problem = Test-FolderAccess (Join-Path $Folder $name) $false }
    }
} catch { Fail 50 ('the removal scripts could not be checked: ' + $_.Exception.Message) }
if ($problem) { Fail 50 $problem }

# 2. No new installs: the install task goes, then the staged installer and install-user.ps1.
try {
    if (Get-ScheduledTask -TaskName $TaskName -TaskPath '\' -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath '\' -Confirm:$false
    }
} catch { Fail 47 ('the install task could not be removed: ' + $_.Exception.Message) }
foreach ($name in @('@INSTALLER_NAME@', '@USER_SCRIPT_NAME@')) {
    $path = Join-Path $Folder $name
    # A person's run may be copying the installer just now: a few tries.
    for ($try = 1; $try -le 5 -and (Test-Path -LiteralPath $path); $try++) {
        try { Remove-Item -LiteralPath $path -Force } catch { Start-Sleep -Seconds 3 }
    }
    if (Test-Path -LiteralPath $path) { Fail 47 ('could not delete ' + $path) }
}

# 3. The removal task: at the sign-in of any user, as the group Users, least privilege, hidden,
# so that uninstall-user.ps1 runs as the person who signed in, with that person's own rights.
try {
    $action = New-ScheduledTaskAction -Execute $powershell -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + (Join-Path $Folder '@UNINSTALL_SCRIPT_NAME@') + '"')
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $trigger.Delay = '@LOGON_DELAY@'
    $taskPrincipal = New-ScheduledTaskPrincipal -GroupId $UsersSid -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances Parallel -ExecutionTimeLimit (New-TimeSpan -Minutes @TASK_TIME_LIMIT_MINUTES@)
    Register-ScheduledTask -TaskName $RemovalTaskName -TaskPath '\' -Action $action -Trigger $trigger -Principal $taskPrincipal -Settings $settings -Description 'Removes Grammarly for Windows from the profile of the person who signs in, with that profile''s own uninstaller.' -Force | Out-Null
    $task = Get-ScheduledTask -TaskName $RemovalTaskName -TaskPath '\'
    $group = [string]$task.Principal.GroupId
    if ($group -notmatch '^S-1-') { $group = (New-Object Security.Principal.NTAccount($group)).Translate([Security.Principal.SecurityIdentifier]).Value }
} catch { Fail 51 ('the removal task could not be registered: ' + $_.Exception.Message) }
if ($group -ne $UsersSid) { Fail 51 ('the removal task runs as ' + $group + ', not as the group Users') }
if ([string]$task.Principal.RunLevel -ne 'Limited') { Fail 51 ('the removal task runs with ' + $task.Principal.RunLevel + ', not with least privilege') }
# Started once now for the people signed in, as the install starts its task; a failure is only
# reported: the task runs at the next sign-in anyway.
try {
    Start-ScheduledTask -TaskName $RemovalTaskName -TaskPath '\'
    $started = 'started it once for the people signed in'
} catch { $started = 'could not start it now (' + $_.Exception.Message + '); it runs at the next sign-in' }

# 4. The cleanup task: as SYSTEM, at each start and once a day. cleanup.ps1 only looks whether a
# profile still has Grammarly, and ends the removal when none has or the removal is old.
try {
    $cleanupAction = New-ScheduledTaskAction -Execute $powershell -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + (Join-Path $Folder '@CLEANUP_SCRIPT_NAME@') + '"')
    $cleanupTriggers = @((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -Daily -At '@CLEANUP_DAILY_AT@'))
    $cleanupPrincipal = New-ScheduledTaskPrincipal -UserId '@SYSTEM_SID@' -LogonType ServiceAccount -RunLevel Highest
    $cleanupSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes @TASK_TIME_LIMIT_MINUTES@)
    Register-ScheduledTask -TaskName $CleanupTaskName -TaskPath '\' -Action $cleanupAction -Trigger $cleanupTriggers -Principal $cleanupPrincipal -Settings $cleanupSettings -Description 'Ends the removal of the Grammarly per-user deployment when no profile has Grammarly any more, or after @REMOVAL_KEEP_DAYS@ days.' -Force | Out-Null
    $cleanupTask = Get-ScheduledTask -TaskName $CleanupTaskName -TaskPath '\'
    $runAs = [string]$cleanupTask.Principal.UserId
    if ($runAs -notmatch '^S-1-') { $runAs = (New-Object Security.Principal.NTAccount($runAs)).Translate([Security.Principal.SecurityIdentifier]).Value }
} catch { Fail 52 ('the cleanup task could not be registered: ' + $_.Exception.Message) }
if ($runAs -ne '@SYSTEM_SID@') { Fail 52 ('the cleanup task runs as ' + $runAs + ', not as SYSTEM') }

# 5. The removal's date (UTC) in this deployment's key. A date that is there already is kept, so
# that a second removal does not put off the end.
try {
    if (-not (Test-Path -LiteralPath $RemovalKey)) { New-Item -Path $RemovalKey | Out-Null }
    if (-not (Get-ItemProperty -LiteralPath $RemovalKey).'@REMOVAL_DATE_VALUE@') {
        Set-ItemProperty -LiteralPath $RemovalKey -Name '@REMOVAL_DATE_VALUE@' -Value ([DateTime]::UtcNow.ToString('@REMOVAL_DATE_FORMAT@', [Globalization.CultureInfo]::InvariantCulture))
    }
} catch { Fail 53 ('the date of the removal could not be recorded: ' + $_.Exception.Message) }

# 6. Last, the entry of the uninstall list: the item counts as removed only now.
try {
    if (Test-Path -LiteralPath $MarkerKey) { Remove-Item -LiteralPath $MarkerKey -Recurse -Force }
} catch { Fail 47 ('the entry could not be removed: ' + $_.Exception.Message) }
Write-Output ('Removed the install task, the staged installer and the entry; registered the task ' + $RemovalTaskName + ' (' + $started + ') and the task ' + $CleanupTaskName + '.')
exit 0
"""

UNINSTALL_TEMPLATE = r"""# Removes Grammarly for Windows from the profile of the person who signed in, with that profile's
# own uninstaller, after the Grammarly per-user item was removed from the PC. Run by the scheduled
# task '@REMOVAL_TASK_NAME@' as that person, with that person's own rights. It never elevates. Only
# the command that the vendor writes for this very profile is run. One line per run goes to the
# person's log.
$ErrorActionPreference = 'Stop'
$WaitSeconds = @UNINSTALL_WAIT_SECONDS@
$PollSeconds = @UNINSTALL_POLL_SECONDS@

@PERSON_GUARDS@

$vendorKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\@VENDOR_UNINSTALL_KEY@'
$stateKey = 'HKCU:\Software\@MARKER_KEY_NAME@'
$logFolder = Join-Path $env:LOCALAPPDATA '@MARKER_KEY_NAME@'
$log = Join-Path $logFolder 'uninstall.log'
$uninstaller = Join-Path $env:LOCALAPPDATA '@VENDOR_UNINSTALLER@'
$expected = '"' + $uninstaller + '" @VENDOR_UNINSTALL_ARGUMENT@'
$lock = $null

function Finish([string]$Text, [int]$Code) {
    try {
        if ((Test-Path -LiteralPath $log) -and (Get-Item -LiteralPath $log).Length -gt 262144) { Move-Item -LiteralPath $log -Destination ($log + '.old') -Force }
        Add-Content -LiteralPath $log -Value ((Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz') + ' ' + $Text) -Encoding Ascii
    } catch { }
    if ($lock) { $lock.Close() }
    exit $Code
}

try {
    if (-not (Test-Path -LiteralPath $logFolder)) { New-Item -ItemType Directory -Path $logFolder | Out-Null }
    # One run per person at a time, the install's run included (the same lock file).
    try { $lock = [IO.File]::Open((Join-Path $logFolder 'install.lock'), 'OpenOrCreate', 'ReadWrite', 'None') } catch { exit 0 }

    if (-not (Test-Path -LiteralPath $vendorKey)) {
        Remove-Item -LiteralPath $stateKey -Recurse -Force -ErrorAction SilentlyContinue
        Finish 'no Grammarly in this profile: nothing to do' 0
    }
    $command = $null
    try { $command = [string](Get-ItemProperty -LiteralPath $vendorKey -Name 'QuietUninstallString' -ErrorAction Stop).QuietUninstallString } catch { }
    # Only this profile's own uninstaller, with /S, exactly as the vendor writes it.
    if ($command -cne $expected) { Finish ('not removed: the uninstall command of this profile is not ' + $expected + ' but ' + $command) 1 }
    if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) { Finish ('not removed: ' + $uninstaller + ' is missing') 1 }

    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $uninstaller
    $info.Arguments = '@VENDOR_UNINSTALL_ARGUMENT@'
    $info.UseShellExecute = $false
    $info.WorkingDirectory = [IO.Path]::GetTempPath()
    $process = [Diagnostics.Process]::Start($info)
    if ($process.WaitForExit($WaitSeconds * 1000)) {
        $code = 'exit code ' + $process.ExitCode
    } else {
        $code = 'still running after ' + $WaitSeconds + ' seconds'
    }
    # The uninstaller may hand over to a copy of itself and return at once: wait for the entry.
    while ((Test-Path -LiteralPath $vendorKey) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds $PollSeconds }
    # The person's uninstall entry decides, not the exit code.
    if (Test-Path -LiteralPath $vendorKey) { Finish ('not removed: the entry is still there after ' + $WaitSeconds + ' seconds (uninstaller: ' + $code + ')') 1 }
    Remove-Item -LiteralPath $stateKey -Recurse -Force -ErrorAction SilentlyContinue
    Finish ('removed Grammarly from this profile (uninstaller: ' + $code + ')') 0
} catch {
    Finish ('error: ' + $_.Exception.Message) 1
}
"""

CLEANUP_TEMPLATE = r"""# Ends a removal of the Grammarly per-user item. Run as SYSTEM by the task '@CLEANUP_TASK_NAME@' at
# each start and once a day. Toward the profiles it only LOOKS (Test-Path, nothing else): nothing
# is run from, read from or written into a profile. When no person's profile has Grammarly's own
# uninstaller any more, or the removal was recorded more than @REMOVAL_KEEP_DAYS@ days ago, it
# unregisters both removal tasks and then deletes the folder (this script last) and the key of the
# removal's date. Otherwise it does nothing. Run as SYSTEM or an administrator.
$ErrorActionPreference = 'Stop'
$FolderName = '@FOLDER_NAME@'
$RemovalTaskName = '@REMOVAL_TASK_NAME@'
$CleanupTaskName = '@CLEANUP_TASK_NAME@'
$MarkerKeyName = '@MARKER_KEY_NAME@'
$KeepDays = @REMOVAL_KEEP_DAYS@
@COMMON_HEAD@
$profileList = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList'

# The lock shared with install-machine.ps1: an install that starts while this run goes on would
# otherwise have its freshly staged folder deleted below (unregistering this task does not stop
# this run). Not waited for: when an install holds it, this run does nothing and the next start
# or day runs again. A lock left by a run that died counts as taken. Held until this run ends.
$owned = $false
try {
    $mutex = New-Object Threading.Mutex($false, '@MUTEX_NAME@')
    $owned = $mutex.WaitOne(0)
} catch {
    if ($_.Exception.GetBaseException() -is [Threading.AbandonedMutexException]) { $owned = $true }
}
if (-not $owned) {
    Write-Output 'An install holds the lock shared with it: nothing to do now.'
    exit 0
}

# An install is there again: it takes the pending removal away itself.
if (Test-Path -LiteralPath $MarkerKey) {
    Write-Output 'The item is installed again: nothing to do.'
    exit 0
}

# A date that is missing or cannot be read counts as an old one: the removal must end some day.
$removedOn = $null
try {
    $text = [string](Get-ItemProperty -LiteralPath $RemovalKey -Name '@REMOVAL_DATE_VALUE@' -ErrorAction Stop).'@REMOVAL_DATE_VALUE@'
    $removedOn = [DateTime]::ParseExact($text, '@REMOVAL_DATE_FORMAT@', [Globalization.CultureInfo]::InvariantCulture)
} catch { }
$expired = (-not $removedOn) -or ($removedOn.AddDays($KeepDays) -lt [DateTime]::UtcNow.Date)

# The profiles of people: does Grammarly's own uninstaller still lie in one of them? Test-Path only.
$left = 0
try {
    foreach ($entry in @(Get-ChildItem -LiteralPath $profileList)) {
        if ($entry.PSChildName -notmatch '@PERSON_SID_PATTERN@') { continue }
        $profilePath = [string]$entry.GetValue('ProfileImagePath')
        if (-not $profilePath) { continue }
        if (Test-Path -LiteralPath ($profilePath.TrimEnd('\') + '\@PROFILE_UNINSTALLER@') -PathType Leaf) { $left++ }
    }
} catch {
    # The list could not be read: as if a profile still had it, so only the days end the removal.
    $left = 1
}
if ($left -gt 0 -and -not $expired) {
    Write-Output ('Grammarly is still in ' + $left + ' profiles: the removal goes on.')
    exit 0
}

# The end. The entry once more, just before anything is changed.
if (Test-Path -LiteralPath $MarkerKey) {
    Write-Output 'The item is installed again: nothing to do.'
    exit 0
}
# Both tasks go first, so that no path leaves a task that runs a script that is gone: when one
# cannot be unregistered, nothing is deleted and the next run tries again.
foreach ($name in @($RemovalTaskName, $CleanupTaskName)) {
    try {
        if (Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $name -TaskPath '\' -Confirm:$false
        }
    } catch {
        Write-Output ('ERROR 54: the task ' + $name + ' could not be unregistered; nothing was deleted: ' + $_.Exception.Message)
        exit 54
    }
}
# Then the files, this script last among them, then the folder and the key. With both tasks gone,
# whatever cannot be deleted stays inert.
$self = Join-Path $Folder '@CLEANUP_SCRIPT_NAME@'
for ($try = 1; $try -le 5 -and (Test-Path -LiteralPath $Folder); $try++) {
    try {
        Get-ChildItem -LiteralPath $Folder -Force | Where-Object { $_.FullName -ne $self } | ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
        if (Test-Path -LiteralPath $self) { Remove-Item -LiteralPath $self -Force }
        Remove-Item -LiteralPath $Folder -Recurse -Force
    } catch { Start-Sleep -Seconds 3 }
}
$failed = @()
if (Test-Path -LiteralPath $Folder) { $failed += ('the folder ' + $Folder) }
try { if (Test-Path -LiteralPath $RemovalKey) { Remove-Item -LiteralPath $RemovalKey -Recurse -Force } } catch { $failed += ('the key: ' + $_.Exception.Message) }
if ($failed.Count -gt 0) {
    Write-Output ('ERROR 54: both tasks are unregistered, but not deleted: ' + ($failed -join '; '))
    exit 54
}
Write-Output ('The removal is finished (' + $left + ' profiles with Grammarly left).')
exit 0
"""


def _common_values():
    return {
        "FOLDER_NAME": FOLDER_NAME, "TASK_NAME": TASK_NAME, "MARKER_KEY_NAME": MARKER_KEY_NAME,
        "DISPLAY_NAME": DISPLAY_NAME, "INSTALLER_NAME": INSTALLER_NAME, "USER_SCRIPT_NAME": USER_SCRIPT_NAME,
        "REMOVE_SCRIPT_NAME": REMOVE_SCRIPT_NAME, "USERS_SID": USERS_SID, "SYSTEM_SID": SYSTEM_SID,
        "ADMINISTRATORS_SID": ADMINISTRATORS_SID, "UNINSTALL_SCRIPT_NAME": UNINSTALL_SCRIPT_NAME,
        "CLEANUP_SCRIPT_NAME": CLEANUP_SCRIPT_NAME, "REMOVAL_TASK_NAME": REMOVAL_TASK_NAME,
        "CLEANUP_TASK_NAME": CLEANUP_TASK_NAME, "PERSON_SID_PATTERN": PERSON_SID_PATTERN,
        "LOGON_DELAY": LOGON_DELAY, "TASK_TIME_LIMIT_MINUTES": str(TASK_TIME_LIMIT_MINUTES),
        "REMOVAL_DATE_VALUE": REMOVAL_DATE_VALUE, "REMOVAL_DATE_FORMAT": REMOVAL_DATE_FORMAT,
        "REMOVAL_KEEP_DAYS": str(REMOVAL_KEEP_DAYS), "VENDOR_UNINSTALL_KEY": VENDOR_UNINSTALL_KEY,
        "MUTEX_NAME": MUTEX_NAME, "MUTEX_WAIT_SECONDS": str(MUTEX_WAIT_SECONDS),
    }


def _embedded(prefix, text):
    """The SHA-256 (upper case) and base64 of a script, as values for a template."""
    body = text.encode("ascii")
    return {prefix + "_SHA256": hashlib.sha256(body).hexdigest().upper(),
            prefix + "_BASE64": base64.b64encode(body).decode("ascii")}


def machine_script(version, sha256, arguments=()):
    """install-machine.ps1 (CRLF lines, ASCII). It carries install-user.ps1 (made with the
    same version, hash and arguments), remove.ps1, uninstall-user.ps1 and cleanup.ps1, each as
    base64 with its SHA-256."""
    values = _common_values()
    values.update({
        "VERSION": check_version(version), "SHA256": check_sha256(sha256).upper(),
        "EXTRACTED_NAMES": ", ".join("'%s'" % name for name in EXTRACTED_NAMES),
    })
    values.update(_embedded("USER_SCRIPT", user_script(version, sha256, arguments)))
    values.update(_embedded("REMOVE_SCRIPT", remove_script()))
    values.update(_embedded("UNINSTALL_SCRIPT", uninstall_script()))
    values.update(_embedded("CLEANUP_SCRIPT", cleanup_script()))
    return _crlf(_fill(_snippets(MACHINE_TEMPLATE), values))


def user_script(version, sha256, arguments=()):
    """install-user.ps1 (CRLF lines, ASCII). `arguments` are checked against ALLOWED_ARGUMENTS."""
    checked = parse_installer_arguments(" ".join(arguments))
    values = _common_values()
    values.update({
        "VERSION": check_version(version), "SHA256": check_sha256(sha256).upper(),
        "ARGUMENTS": ", ".join("'%s'" % name for name in checked),
        "MAX_ATTEMPTS": str(MAX_ATTEMPTS), "INSTALLER_WAIT_SECONDS": str(INSTALLER_WAIT_SECONDS),
    })
    return _crlf(_fill(_snippets(USER_TEMPLATE), values))


def remove_script():
    """remove.ps1 (CRLF lines, ASCII): the same text for every version. It carries the SHA-256 of
    uninstall-user.ps1 and cleanup.ps1, which the install stages, and compares them before use."""
    values = _common_values()
    values["CLEANUP_DAILY_AT"] = CLEANUP_DAILY_AT
    for prefix, text in (("UNINSTALL_SCRIPT", uninstall_script()), ("CLEANUP_SCRIPT", cleanup_script())):
        values[prefix + "_SHA256"] = _embedded(prefix, text)[prefix + "_SHA256"]
    return _crlf(_fill(_snippets(REMOVE_TEMPLATE), values))


def uninstall_script():
    """uninstall-user.ps1 (CRLF lines, ASCII): the same text for every version. Run as the person."""
    values = _common_values()
    values.update({
        "UNINSTALL_WAIT_SECONDS": str(UNINSTALL_WAIT_SECONDS), "UNINSTALL_POLL_SECONDS": str(UNINSTALL_POLL_SECONDS),
        "VENDOR_UNINSTALLER": VENDOR_UNINSTALLER, "VENDOR_UNINSTALL_ARGUMENT": VENDOR_UNINSTALL_ARGUMENT,
    })
    return _crlf(_fill(_snippets(UNINSTALL_TEMPLATE), values))


def cleanup_script():
    """cleanup.ps1 (CRLF lines, ASCII): the same text for every version. Run as SYSTEM; only
    Test-Path toward the profiles."""
    values = _common_values()
    values["PROFILE_UNINSTALLER"] = PROFILE_LOCAL_APPDATA + "\\" + VENDOR_UNINSTALLER
    return _crlf(_fill(_snippets(CLEANUP_TEMPLATE), values))


def settings_digest(settings):
    """A short name for a set of settings: the EXE in the cache is reused only
    when it was built with the same ones."""
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode("utf-8")).hexdigest()


def is_windows_program(path):
    """Whether the file begins like a Windows program (the letters MZ)."""
    with open(path, "rb") as handle:
        return handle.read(2) == b"MZ"


def sha256_of_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_bytes(url, max_bytes, what):
    """GET a small file (the SDK: a release address that redirects, checked
    against a SHA-256 afterwards)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.build_opener().open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            body = response.read(max_bytes + 1)
    except urllib.error.HTTPError as err:
        message = "The server answered %s %s for %s." % (err.code, err.reason, what)
        err.close()
        raise ProcessorError(message)
    except (urllib.error.URLError, OSError, ValueError) as err:
        raise ProcessorError("%s could not be fetched: %s" % (what, err))
    if len(body) > max_bytes:
        raise ProcessorError("%s is larger than %d bytes." % (what, max_bytes))
    return body


class GrammarlyPerUserPackager(Processor):
    description = __doc__
    input_variables = {
        "pathname": {
            "required": True,
            "description": "The downloaded GrammarlyInstaller.exe.",
        },
        "version": {
            "required": True,
            "description": "Its version (WindowsExeVersion reads it from the file). It stays the version of the item.",
        },
        "grammarly_installer_arguments": {
            "required": False,
            "default": "",
            "description": "Parameters for the installer beside /S, separated by spaces or commas: %s. "
                           "The names are case-sensitive. Empty: none." % ", ".join(ALLOWED_ARGUMENTS),
        },
        "sfx_sdk_url": {
            "required": True,
            "description": "The address of the LZMA SDK archive (.7z) that holds %s." % STUB_MEMBER,
        },
        "sfx_sdk_sha256": {
            "required": True,
            "description": "The SHA-256 of that archive (64 hex digits). A different file stops the run.",
        },
        "sevenzip_path": {
            "required": False,
            "default": "",
            "description": "The 7z program. Empty: 7zz, 7z or 7za in /opt/homebrew/bin, /usr/local/bin or /usr/bin.",
        },
    }
    output_variables = {
        "pathname": {"description": "The self-extracting EXE."},
        "version": {"description": "Unchanged: the version of the staged installer."},
        "grammarly_installer_sha256": {"description": "The SHA-256 of the installer inside the EXE."},
        "grammarly_packager_summary_result": {"description": "What was built."},
        "signature_sha256": {"description": "The SHA-256 of the EXE, only when the installer's signature was verified "
                                            "and the EXE was built in this run."},
    }

    # -- helpers ---------------------------------------------------------
    def sevenzip(self):
        given = str(self.env.get("sevenzip_path") or "").strip()
        candidates = [given] if given else [os.path.join(folder, name) for folder in SEVENZIP_FOLDERS for name in SEVENZIP_NAMES]
        for candidate in candidates:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        raise ProcessorError(
            "No 7z program was found (%s). Install one (brew install sevenzip) or set sevenzip_path."
            % ", ".join(candidates))

    def run_sevenzip(self, arguments, what, cwd=None):
        result = subprocess.run([self.sevenzip()] + arguments, capture_output=True, text=True, cwd=cwd)
        if result.returncode != 0:
            raise ProcessorError("7z failed (%s): %s" % (what, (result.stderr or result.stdout).strip()[-400:]))

    def stub(self, work):
        try:
            sha256 = check_sha256(self.env["sfx_sdk_sha256"])
        except ValueError:
            raise ProcessorError("sfx_sdk_sha256 is not 64 hex digits.")
        body = fetch_bytes(str(self.env["sfx_sdk_url"]), MAX_SDK_BYTES, "the LZMA SDK")
        actual = hashlib.sha256(body).hexdigest()
        if actual != sha256:
            raise ProcessorError(
                "The LZMA SDK does not have the SHA-256 of sfx_sdk_sha256 (got %s...). Nothing was built." % actual[:12])
        archive = os.path.join(work, "lzma-sdk.7z")
        with open(archive, "wb") as handle:
            handle.write(body)
        self.run_sevenzip(["e", "-y", "-o" + work, archive, STUB_MEMBER], "unpacking the stub")
        path = os.path.join(work, os.path.basename(STUB_MEMBER))
        if not os.path.isfile(path) or not is_windows_program(path):
            raise ProcessorError("The LZMA SDK holds no %s that is a Windows program." % STUB_MEMBER)
        return path

    def verified_input(self, installer_sha256):
        """True when the installer's signature was verified: signature_verified is exactly
        true and signature_sha256 is the installer's SHA-256. A signature_sha256 of another
        file stops the run; a flag that is not true, or a hash that is not a SHA-256, is
        not verified."""
        if self.env.get(SIGNATURE_FLAG_VARIABLE) is not True:
            return False
        try:
            claimed = check_sha256(self.env.get(SIGNATURE_HASH_VARIABLE, ""))
        except ValueError:
            return False
        if claimed != installer_sha256:
            raise ProcessorError(
                "%s is the hash of another file than the installer (the installer has %s...). Nothing was built."
                % (SIGNATURE_HASH_VARIABLE, installer_sha256[:12]))
        return True

    # -- main ------------------------------------------------------------
    def main(self):
        env = self.env
        installer = str(env.get("pathname") or "")
        try:
            version = check_version(env.get("version", ""))
            arguments = parse_installer_arguments(env.get("grammarly_installer_arguments", ""))
            sdk_sha256 = check_sha256(env.get("sfx_sdk_sha256", ""))
        except ValueError as err:
            raise ProcessorError(str(err))
        if not os.path.isfile(installer):
            raise ProcessorError("The installer is not a file: %s" % installer)
        size = os.path.getsize(installer)
        if size > MAX_INSTALLER_BYTES:
            raise ProcessorError("The installer has %d bytes, more than %d: not the file this recipe expects." % (
                size, MAX_INSTALLER_BYTES))
        if not is_windows_program(installer):
            raise ProcessorError("The installer is not a Windows program.")
        installer_sha256 = sha256_of_file(installer)
        handed_over = self.verified_input(installer_sha256)
        scripts = {
            "setup.bat": setup_bat(),
            MACHINE_SCRIPT_NAME: machine_script(version, installer_sha256, arguments),
            USER_SCRIPT_NAME: user_script(version, installer_sha256, arguments),
            REMOVE_SCRIPT_NAME: remove_script(),
            UNINSTALL_SCRIPT_NAME: uninstall_script(),
            CLEANUP_SCRIPT_NAME: cleanup_script(),
        }

        cache = env.get("RECIPE_CACHE_DIR")
        if not cache:
            raise ProcessorError("RECIPE_CACHE_DIR is not set.")
        os.makedirs(cache, exist_ok=True)
        exe_path = os.path.join(cache, "GrammarlyPerUser-%s.exe" % version)
        record_path = exe_path + ".json"
        settings = settings_digest({"installer": installer_sha256, "sdk": sdk_sha256, "scripts": scripts})
        try:
            with open(record_path, "r", encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, ValueError):
            record = {}
        env["version"] = version
        env["grammarly_installer_sha256"] = installer_sha256
        if (not handed_over and os.path.isfile(exe_path) and record.get("settings") == settings
                and record.get("size") == os.path.getsize(exe_path)
                and record.get("sha256") == sha256_of_file(exe_path)):
            env["pathname"] = exe_path
            self.output("Nothing to build: %s is in the cache with the same settings." % os.path.basename(exe_path))
            return

        work = tempfile.mkdtemp(prefix="grammarly-build-", dir=cache)
        try:
            stub_path = self.stub(work)
            stage = os.path.join(work, "stage")
            os.makedirs(stage)
            shutil.copyfile(installer, os.path.join(stage, INSTALLER_NAME))
            if sha256_of_file(os.path.join(stage, INSTALLER_NAME)) != installer_sha256:
                raise ProcessorError("The installer changed while it was copied into the stage. Nothing was built.")
            for name in ("setup.bat", MACHINE_SCRIPT_NAME):  # the other four are inside install-machine.ps1
                text = scripts[name]
                with open(os.path.join(stage, name), "w", encoding="ascii", newline="") as handle:
                    handle.write(text)
            names = sorted(os.listdir(stage))
            for name in names:
                os.chmod(os.path.join(stage, name), PACKED_FILE_MODE)
                os.utime(os.path.join(stage, name), (PACKED_FILE_TIME, PACKED_FILE_TIME))
            archive = os.path.join(work, "stage.7z")
            # stored, one file per block: the stub unpacks a block in memory. The files are named one by one in a
            # fixed order, with a fixed time and no creation or access time: the archive is the same bytes each time
            self.run_sevenzip(["a", "-t7z", "-mx=0", "-ms=off", "-mtc=off", "-mta=off", "-bd", "-y", archive] + names,
                              "packing", cwd=stage)
            shutil.rmtree(stage)
            partial = exe_path + ".partial"
            with open(partial, "wb") as out:
                for piece in (stub_path, archive):
                    with open(piece, "rb") as handle:
                        shutil.copyfileobj(handle, out, 4 * 1024 * 1024)
            os.replace(partial, exe_path)
        finally:
            shutil.rmtree(work, ignore_errors=True)
            if os.path.exists(exe_path + ".partial"):
                os.remove(exe_path + ".partial")

        exe_sha256 = sha256_of_file(exe_path)
        with open(record_path, "w", encoding="utf-8") as handle:
            json.dump({"settings": settings, "size": os.path.getsize(exe_path), "sha256": exe_sha256,
                       "version": version,
                       "installer_sha256": installer_sha256, "arguments": arguments}, handle, indent=2)
        for name in os.listdir(cache):  # an EXE of another version is 87 MB of no use
            if re.fullmatch(r"GrammarlyPerUser-.*\.exe(\.json)?", name) and not name.startswith(os.path.basename(exe_path)):
                os.remove(os.path.join(cache, name))
        env["pathname"] = exe_path
        if handed_over:
            env[SIGNATURE_HASH_VARIABLE] = exe_sha256
            self.output("The installer's verified signature is handed over to the EXE built from it in this run "
                        "(%s is now the EXE's SHA-256)." % SIGNATURE_HASH_VARIABLE)
        env["grammarly_packager_summary_result"] = {
            "summary_text": ("The following Grammarly per-user installer was built from an installer whose signature "
                             "was verified:" if handed_over else
                             "The following Grammarly per-user installer was built (NOT verified: see the processor):"),
            "report_fields": ["version", "size", "path"],
            "data": {"version": version, "size": str(os.path.getsize(exe_path)), "path": exe_path},
        }
        self.output("Built %s (%d bytes), Grammarly %s" % (os.path.basename(exe_path), os.path.getsize(exe_path), version))


if __name__ == "__main__":
    PROCESSOR = GrammarlyPerUserPackager()
    PROCESSOR.execute_shell()
