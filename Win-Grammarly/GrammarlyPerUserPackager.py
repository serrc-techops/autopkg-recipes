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
 2. writes GrammarlyInstaller.exe, install-user.ps1 and remove.ps1 into it,
    each beside its place, compared with a SHA-256 written into
    install-machine.ps1 at build time, then swapped in. The two scripts are
    carried INSIDE install-machine.ps1 (base64) and written from there: from
    the extraction folder, which a standard user may add files to (it lies
    under SYSTEM's temp folder), only the installer is taken, and only by its
    SHA-256; and install-machine.ps1 stops when that folder holds anything
    the EXE did not put there (a narrowing, not a proof);
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

remove.ps1 removes the task, the folder and the uninstall entry. Grammarly
stays in every profile that has it.

The scripts are made by the pure functions below, so tests can pin their text.
The stub is 7zS2con.sfx of the public-domain LZMA SDK, as in the
Microsoft 365 Apps folder of this repository; it ends with setup.bat's exit
code.

NOT verified: the vendor publishes no hash for its installer, and no signature
is checked here. This processor sets no checksum_verified; the importers refuse
a real run until the override allows an unverified download. A checksum_sha256
that an earlier step left in the run is the hash of the downloaded file, not of
the EXE built here, and the importers stop on it (on purpose).

Seen on 2026-11-16 (see the README): the first build (scripts as files in the
archive) under AutoPkg, as SYSTEM on one PC, one on-demand start of the task
that installed Grammarly for an administrator, and the removal; this form
under AutoPkg and as SYSTEM on the same PC, where its own start of the task
found Grammarly present. With this form the per-user install path and the
removal have not run.
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
    "settings_digest",
    "SETUP_CODES",
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
# The vendor's detection rule: this key in the user's own hive, value DisplayVersion.
VENDOR_UNINSTALL_KEY = "Grammarly Desktop Integrations"
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
}
# What the stub unpacks; anything else in the extraction folder stops the run.
EXTRACTED_NAMES = ("setup.bat", "install-machine.ps1", "GrammarlyInstaller.exe")
REMOVE_CODES = {
    41: "remove.ps1 was not run as an administrator or SYSTEM",
    46: "a 32-bit PowerShell on a 64-bit Windows",
    47: "the task, the folder or the entry could not be removed",
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
"""

MACHINE_TEMPLATE = r"""# Stages the Grammarly for Windows installer so that each person who signs in gets Grammarly
# in their own profile. Run by setup.bat as SYSTEM (or an administrator), from the folder that
# the self-extracting EXE unpacked into. Exit 0 only when everything is in place. The two
# scripts that it stages are carried in this file; from the extraction folder only the
# installer is taken, and only when it has the SHA-256 below.
$ErrorActionPreference = 'Stop'
$Version = '@VERSION@'
$Sha256 = '@SHA256@'
$FolderName = '@FOLDER_NAME@'
$TaskName = '@TASK_NAME@'
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

# 1. The folder: SYSTEM and Administrators full control, Users read and run, nothing inherited.
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
# wrote into this script, and swapped in. The two scripts come from this file, not from the
# extraction folder. A person's run copies the installer away before it runs it, so the
# staged file is held only briefly.
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
}
try {
    Install-Staged (Join-Path $Folder '@INSTALLER_NAME@') $Sha256 $null $source
    Install-Staged (Join-Path $Folder '@USER_SCRIPT_NAME@') '@USER_SCRIPT_SHA256@' ([Convert]::FromBase64String('@USER_SCRIPT_BASE64@')) ''
    Install-Staged (Join-Path $Folder '@REMOVE_SCRIPT_NAME@') '@REMOVE_SCRIPT_SHA256@' ([Convert]::FromBase64String('@REMOVE_SCRIPT_BASE64@')) ''
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

# Nothing for SYSTEM, the service accounts and other built-in accounts: only a local or
# domain account (S-1-5-21-...) or a Microsoft Entra account (S-1-12-1-...).
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
if ($sid -notmatch '^S-1-(5-21|12-1)-') { exit 0 }
# Nor for the accounts of the first setup and of Windows Sandbox: throwaway profiles.
$account = [Environment]::UserName
if ($account -like 'defaultuser*' -or $account -eq 'WDAGUtilityAccount') { exit 0 }

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

REMOVE_TEMPLATE = r"""# Removes what the Grammarly per-user item put on the PC: the scheduled task, the staged
# folder and the entry of the uninstall list. Grammarly stays in every profile that has it
# (each person removes it, or an administrator does per profile). Run as SYSTEM or an
# administrator. Exit 0 only when all three are gone.
$ErrorActionPreference = 'Stop'
$FolderName = '@FOLDER_NAME@'
$TaskName = '@TASK_NAME@'
$MarkerKeyName = '@MARKER_KEY_NAME@'
@COMMON_HEAD@
$failed = @()
try {
    if (Get-ScheduledTask -TaskName $TaskName -TaskPath '\' -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath '\' -Confirm:$false
    }
} catch { $failed += ('the task: ' + $_.Exception.Message) }
for ($try = 1; $try -le 5 -and (Test-Path -LiteralPath $Folder); $try++) {
    try { Remove-Item -LiteralPath $Folder -Recurse -Force } catch { Start-Sleep -Seconds 3 }
}
if (Test-Path -LiteralPath $Folder) { $failed += ('the folder ' + $Folder) }
if ($failed.Count -eq 0) {
    try { if (Test-Path -LiteralPath $MarkerKey) { Remove-Item -LiteralPath $MarkerKey -Recurse -Force } } catch { $failed += ('the entry: ' + $_.Exception.Message) }
}
if ($failed.Count -gt 0) {
    Write-Output ('ERROR 47: not removed: ' + ($failed -join '; '))
    exit 47
}
Write-Output 'Removed the task, the folder and the entry. Grammarly stays in every profile that has it.'
exit 0
"""


def _common_values():
    return {
        "FOLDER_NAME": FOLDER_NAME, "TASK_NAME": TASK_NAME, "MARKER_KEY_NAME": MARKER_KEY_NAME,
        "DISPLAY_NAME": DISPLAY_NAME, "INSTALLER_NAME": INSTALLER_NAME, "USER_SCRIPT_NAME": USER_SCRIPT_NAME,
        "REMOVE_SCRIPT_NAME": REMOVE_SCRIPT_NAME, "USERS_SID": USERS_SID, "SYSTEM_SID": SYSTEM_SID,
        "ADMINISTRATORS_SID": ADMINISTRATORS_SID,
    }


def machine_script(version, sha256, arguments=()):
    """install-machine.ps1 (CRLF lines, ASCII). It carries install-user.ps1 (made with the
    same version, hash and arguments) and remove.ps1, each as base64 with its SHA-256."""
    user = user_script(version, sha256, arguments).encode("ascii")
    remove = remove_script().encode("ascii")
    values = _common_values()
    values.update({
        "VERSION": check_version(version), "SHA256": check_sha256(sha256).upper(),
        "LOGON_DELAY": LOGON_DELAY, "TASK_TIME_LIMIT_MINUTES": str(TASK_TIME_LIMIT_MINUTES),
        "EXTRACTED_NAMES": ", ".join("'%s'" % name for name in EXTRACTED_NAMES),
        "USER_SCRIPT_SHA256": hashlib.sha256(user).hexdigest().upper(),
        "USER_SCRIPT_BASE64": base64.b64encode(user).decode("ascii"),
        "REMOVE_SCRIPT_SHA256": hashlib.sha256(remove).hexdigest().upper(),
        "REMOVE_SCRIPT_BASE64": base64.b64encode(remove).decode("ascii"),
    })
    return _crlf(_fill(MACHINE_TEMPLATE.replace("@COMMON_HEAD@", _COMMON_HEAD.strip("\n")), values))


def user_script(version, sha256, arguments=()):
    """install-user.ps1 (CRLF lines, ASCII). `arguments` are checked against ALLOWED_ARGUMENTS."""
    checked = parse_installer_arguments(" ".join(arguments))
    values = _common_values()
    values.update({
        "VERSION": check_version(version), "SHA256": check_sha256(sha256).upper(),
        "ARGUMENTS": ", ".join("'%s'" % name for name in checked),
        "MAX_ATTEMPTS": str(MAX_ATTEMPTS), "INSTALLER_WAIT_SECONDS": str(INSTALLER_WAIT_SECONDS),
        "VENDOR_UNINSTALL_KEY": VENDOR_UNINSTALL_KEY,
    })
    return _crlf(_fill(USER_TEMPLATE, values))


def remove_script():
    """remove.ps1 (CRLF lines, ASCII): the same text for every version."""
    return _crlf(_fill(REMOVE_TEMPLATE.replace("@COMMON_HEAD@", _COMMON_HEAD.strip("\n")), _common_values()))


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
        scripts = {
            "setup.bat": setup_bat(),
            MACHINE_SCRIPT_NAME: machine_script(version, installer_sha256, arguments),
            USER_SCRIPT_NAME: user_script(version, installer_sha256, arguments),
            REMOVE_SCRIPT_NAME: remove_script(),
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
        if (os.path.isfile(exe_path) and record.get("settings") == settings
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
            for name in ("setup.bat", MACHINE_SCRIPT_NAME):  # the other two are inside install-machine.ps1
                text = scripts[name]
                with open(os.path.join(stage, name), "w", encoding="ascii", newline="") as handle:
                    handle.write(text)
            archive = os.path.join(work, "stage.7z")
            # stored, one file per block: the stub unpacks a block in memory
            self.run_sevenzip(["a", "-t7z", "-mx=0", "-ms=off", "-bd", "-y", archive, "."], "packing", cwd=stage)
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

        with open(record_path, "w", encoding="utf-8") as handle:
            json.dump({"settings": settings, "size": os.path.getsize(exe_path), "sha256": sha256_of_file(exe_path),
                       "version": version,
                       "installer_sha256": installer_sha256, "arguments": arguments}, handle, indent=2)
        for name in os.listdir(cache):  # an EXE of another version is 87 MB of no use
            if re.fullmatch(r"GrammarlyPerUser-.*\.exe(\.json)?", name) and not name.startswith(os.path.basename(exe_path)):
                os.remove(os.path.join(cache, name))
        env["pathname"] = exe_path
        env["grammarly_packager_summary_result"] = {
            "summary_text": "The following Grammarly per-user installer was built (NOT verified: see the processor):",
            "report_fields": ["version", "size", "path"],
            "data": {"version": version, "size": str(os.path.getsize(exe_path)), "path": exe_path},
        }
        self.output("Built %s (%d bytes), Grammarly %s" % (os.path.basename(exe_path), os.path.getsize(exe_path), version))


if __name__ == "__main__":
    PROCESSOR = GrammarlyPerUserPackager()
    PROCESSOR.execute_shell()
