"""Tests of GrammarlyPerUserPackager. Nothing here uses the network, 7z,
PowerShell or AutoPkg: the scripts that the PC runs are made by plain
functions, and their text is pinned here; a build is run with the stub and 7z
replaced. A test parses the scripts only where `pwsh` is installed (it is
skipped otherwise); what ran on a PC is in the README.
"""
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import base64
import hashlib

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.dirname(TESTS_DIR)
SHARED_TESTS_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-SharedProcessors", "tests")
PCMAN_TESTS_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-PcmanProcessors", "tests")
for folder in (SHARED_TESTS_DIR, PCMAN_TESTS_DIR, RECIPE_DIR):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import _win_support  # noqa: E402,F401  (installs the autopkglib stand-in)
import GrammarlyPerUserPackager as packager  # noqa: E402

ProcessorError = sys.modules["autopkglib"].ProcessorError
VERSION = "1.2.312.2004"
SHA = "ab" * 32
OTHER_SHA = "cd" * 32


def load(name):
    with open(os.path.join(RECIPE_DIR, name), "rb") as handle:
        return plistlib.load(handle)


def all_scripts(arguments=()):
    return {
        "setup.bat": packager.setup_bat(),
        "install-machine.ps1": packager.machine_script(VERSION, SHA),
        "install-user.ps1": packager.user_script(VERSION, SHA, arguments),
        "remove.ps1": packager.remove_script(),
        "uninstall-user.ps1": packager.uninstall_script(),
        "cleanup.ps1": packager.cleanup_script(),
    }


def code_lines(text):
    """The lines of a PowerShell script without its comment lines."""
    return [line for line in text.split("\r\n") if not line.lstrip().startswith("#")]


class ArgumentTests(unittest.TestCase):
    def test_the_vendors_names_are_taken_in_order(self):
        self.assertEqual(packager.parse_installer_arguments(""), [])
        self.assertEqual(packager.parse_installer_arguments(None), [])
        self.assertEqual(
            packager.parse_installer_arguments("/disable-launch-at-startup, /do-not-create-desktop-shortcut"),
            ["/disable-launch-at-startup", "/do-not-create-desktop-shortcut"])
        self.assertEqual(packager.parse_installer_arguments(" ".join(packager.ALLOWED_ARGUMENTS)),
                         list(packager.ALLOWED_ARGUMENTS))

    def test_the_allowlist_is_the_vendors_documented_parameters(self):
        self.assertEqual(set(packager.ALLOWED_ARGUMENTS), {
            "/do-not-create-desktop-shortcut", "/disable-launch-at-startup", "/ignore-os-version"})

    def test_anything_else_is_refused(self):
        for text in ("/S", "/uninstall", "/Disable-Launch-At-Startup", "/do-not-create-desktop-shortcut'",
                     "/ignore-os-version;calc", "/windows-store", "--disable-launch-at-startup",
                     "/disable-launch-at-startup /disable-launch-at-startup"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    packager.parse_installer_arguments(text)

    def test_the_user_script_refuses_what_the_parser_refuses(self):
        with self.assertRaises(ValueError):
            packager.user_script(VERSION, SHA, ["/uninstall"])


class VersionAndHashTests(unittest.TestCase):
    def test_versions(self):
        for good in (VERSION, "1.2", "1.2.312"):
            self.assertEqual(packager.check_version(good), good)
        for bad in ("", "1", "1.2.312.2004.7", "v1.2", "1.2'; x", "1.2.312.2004 ", "1..2"):
            if bad.strip() == VERSION:
                continue
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    packager.check_version(bad)

    def test_a_bad_hash_is_refused(self):
        for bad in ("", "ab" * 31, "zz" * 32, SHA + "00"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    packager.machine_script(VERSION, bad)


class AllScriptsTests(unittest.TestCase):
    def test_ascii_crlf_and_every_placeholder_filled(self):
        for name, text in all_scripts(["/disable-launch-at-startup"]).items():
            with self.subTest(name=name):
                text.encode("ascii")
                self.assertNotIn("\n", text.replace("\r\n", ""))
                self.assertTrue(text.endswith("\r\n"))
                self.assertIsNone(re.search(r"@[A-Z_]+@", text))

    def test_the_same_input_gives_the_same_text(self):
        self.assertEqual(all_scripts(), all_scripts())

    def test_no_script_names_an_organisation_a_share_or_a_host(self):
        for name, text in all_scripts().items():
            with self.subTest(name=name):
                self.assertIsNone(re.search(r"\\\\[A-Za-z0-9]", text))  # a UNC path
                self.assertNotIn("http", text)
                self.assertNotIn(".local", text)
        self.assertEqual(packager.MARKER_KEY_NAME, "GrammarlyPerUserDeployment")
        self.assertEqual(packager.FOLDER_NAME, "Grammarly Deployment")

    def test_every_exit_code_is_described(self):
        used = set()
        for name in ("setup.bat", "install-machine.ps1"):
            text = all_scripts()[name]
            used |= {int(code) for code in re.findall(r"exit (4[0-9])", text)}
            used |= {int(code) for code in re.findall(r"Fail (4[0-9])", text)}
        self.assertEqual(used, set(packager.SETUP_CODES))
        for text, codes in ((packager.remove_script(), packager.REMOVE_CODES),
                            (packager.cleanup_script(), packager.CLEANUP_CODES),
                            (packager.uninstall_script(), packager.UNINSTALL_USER_CODES)):
            with self.subTest(codes=sorted(codes)):
                code = "\r\n".join(code_lines(text))
                used = {int(found) for found in re.findall(r"(?:\bexit|Fail) ([0-9]+)", code)}
                used |= {int(found) for found in re.findall(r"Finish (?:'[^']*'|\([^\r]*\)) ([0-9]+)", code)}
                self.assertIn(0, used)  # success
                self.assertEqual(used - {0}, set(codes) - {0})
        # the codes of the machine install and of the removal do not mean two things
        self.assertEqual(set(packager.SETUP_CODES) & (set(packager.REMOVE_CODES) - {41, 46}), set())

    def test_no_script_calls_a_program_by_a_bare_name(self):
        for name, text in all_scripts().items():
            if not name.endswith(".ps1"):
                continue
            code = "\r\n".join(code_lines(text))
            with self.subTest(name=name):
                for word in ("schtasks", "icacls", "reg.exe", "reg ", "cmd.exe", "cmd /", "& '", "& $", "& \"",
                             "Invoke-Expression", "iex ", "Start-Process", "msiexec", "rundll32", "takeown"):
                    self.assertNotIn(word, code)
                for line in code.split("\r\n"):
                    if "-Execute " in line:
                        self.assertIn("-Execute $powershell", line)
                    if "FileName = " in line:
                        self.assertRegex(line.strip(), r"^\$info\.FileName = \$(copy|uninstaller)$")

    @unittest.skipUnless(shutil.which("pwsh"), "pwsh is not installed: the scripts were not parsed")
    def test_powershell_parses_the_scripts(self):  # pragma: no cover - only where pwsh exists
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        for name, text in all_scripts(["/ignore-os-version"]).items():
            if not name.endswith(".ps1"):
                continue
            path = os.path.join(folder, name)
            with open(path, "w", encoding="ascii", newline="") as handle:
                handle.write(text)
            command = ("$e = $null; [void][Management.Automation.Language.Parser]::ParseFile('%s', [ref]$null, [ref]$e); "
                       "if ($e) { $e | ForEach-Object { $_.Message }; exit 1 }" % path)
            result = subprocess.run(["pwsh", "-NoProfile", "-Command", command], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, name + ": " + result.stdout + result.stderr)


class SetupBatTests(unittest.TestCase):
    def test_the_64_bit_powershell_runs_the_machine_script_and_its_code_comes_back(self):
        lines = packager.setup_bat().split("\r\n")
        self.assertEqual(lines[:3], ["@echo off", "setlocal", r'cd /d "%SystemRoot%\System32" || exit 40'])
        self.assertEqual(lines[3], r'set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"')
        self.assertEqual(lines[4], r'if exist "%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe" '
                                   r'set "PS=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"')
        self.assertEqual(lines[5], '"%PS%" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0install-machine.ps1"')
        self.assertNotIn("%~dp0" + '"', packager.setup_bat())  # the extraction folder is never the current folder
        self.assertEqual(lines[6], "exit %ERRORLEVEL%")
        self.assertEqual(lines[7:], [""])


class MachineScriptTests(unittest.TestCase):
    def setUp(self):
        self.text = packager.machine_script(VERSION, SHA)
        self.code = "\r\n".join(code_lines(self.text))

    def test_the_values(self):
        self.assertIn("$Version = '%s'" % VERSION, self.text)
        self.assertIn("$Sha256 = '%s'" % SHA.upper(), self.text)
        self.assertIn("$UsersSid = 'S-1-5-32-545'", self.text)
        self.assertIn("$TaskName = 'Grammarly per-user install'", self.text)

    def test_it_needs_an_administrator_and_the_64_bit_powershell(self):
        self.assertIn("IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Fail 41", self.text)
        self.assertIn("[Environment]::Is64BitOperatingSystem -and -not [Environment]::Is64BitProcess) { Fail 46", self.text)
        self.assertIn("$ProgramFolder = $env:ProgramFiles", self.text)

    def test_the_unpacked_and_the_staged_installer_are_compared_with_the_packed_hash(self):
        self.assertIn("(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $Sha256) { Fail 43", self.text)
        self.assertIn("Install-Staged (Join-Path $Folder 'GrammarlyInstaller.exe') $Sha256 $null $source", self.text)
        self.assertIn("'GrammarlyInstaller.exe' = $Sha256", self.text)
        self.assertIn("if ((Get-FileHash -LiteralPath (Join-Path $Folder $name) -Algorithm SHA256).Hash -ne $staged[$name])",
                      self.text)

    def test_the_access_list_is_set_explicitly_and_checked(self):
        self.assertIn("$security.SetAccessRuleProtection($true, $false)", self.text)
        self.assertIn("$security.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))", self.text)
        self.assertIn("@(('S-1-5-18', 'FullControl'), ('S-1-5-32-544', 'FullControl'), ($UsersSid, 'ReadAndExecute'))",
                      self.text)
        self.assertEqual(self.code.count("AddAccessRule("), 1)
        self.assertIn("$problem = Test-FolderAccess $Folder $true", self.text)
        self.assertIn("if (($rule.FileSystemRights -band $writeRights) -ne 0) { return \"$sid may change $Path\" }", self.text)
        for right in ("WriteData", "AppendData", "Delete", "ChangePermissions", "TakeOwnership"):
            self.assertIn(right, self.text.split("$writeRights = ")[1].split("\r\n")[0])

    def test_the_task_runs_at_any_sign_in_as_the_users_group_with_least_privilege_hidden(self):
        self.assertIn("$trigger = New-ScheduledTaskTrigger -AtLogOn\r\n", self.text)  # no -User: any user
        self.assertIn("$taskPrincipal = New-ScheduledTaskPrincipal -GroupId $UsersSid -RunLevel Limited", self.text)
        self.assertIn("-WindowStyle Hidden -ExecutionPolicy Bypass -File", self.text)
        self.assertIn("-MultipleInstances Parallel", self.text)
        self.assertIn("$trigger.Delay = 'PT30S'", self.text)
        self.assertIn("-ExecutionTimeLimit (New-TimeSpan -Minutes 30)", self.text)
        self.assertIn("Register-ScheduledTask -TaskName $TaskName -TaskPath '\\' ", self.text)
        self.assertIn("-Force | Out-Null", self.text)
        # read back: anything but the Users group with least privilege stops the run
        self.assertIn("if ($group -ne $UsersSid) { Fail 44", self.text)
        self.assertIn("if ([string]$task.Principal.RunLevel -ne 'Limited') { Fail 44", self.text)
        for word in ("-RunLevel Highest", "-UserId", "-LogonType ServiceAccount", "RunAs"):
            self.assertNotIn(word, self.code)
        self.assertEqual(self.code.count("New-ScheduledTaskPrincipal"), 1)

    def test_the_order_files_then_task_then_the_entry_with_its_version_last(self):
        stage = self.code.index("Install-Staged (Join-Path $Folder 'GrammarlyInstaller.exe')")
        task = self.code.index("Register-ScheduledTask")
        entry = self.code.index("Set-ItemProperty -LiteralPath $MarkerKey -Name 'DisplayName'")
        version = self.code.index("Set-ItemProperty -LiteralPath $MarkerKey -Name 'DisplayVersion' -Value $Version")
        self.assertLess(stage, task)
        self.assertLess(task, entry)
        self.assertLess(entry, version)
        self.assertEqual(self.code[version:].count("Set-ItemProperty"), 1)
        self.assertIn(r"$MarkerKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\' + $MarkerKeyName", self.text)

    def test_files_are_swapped_in_after_a_compared_copy(self):
        self.assertIn("$new = $To + '.new'", self.text)
        self.assertIn("[IO.File]::Replace($new, $To, [NullString]::Value)", self.text)
        self.assertIn("if ((Get-FileHash -LiteralPath $new -Algorithm SHA256).Hash -ne $Hash) {", self.text)
        # the owner is checked for the folder, the rights for each staged file
        self.assertIn("if ($Owner -and @('S-1-5-18', 'S-1-5-32-544') -notcontains $ownerSid)", self.text)
        self.assertIn("foreach ($name in $staged.Keys) {\r\n    # A file's owner", self.text)
        self.assertIn("$problem = Test-FolderAccess (Join-Path $Folder $name) $false", self.text)
        self.assertIn("if (@('S-1-5-18', 'S-1-5-32-544') -contains $sid) { continue }", self.text)

    def embedded(self, name):
        match = re.search(r"Install-Staged \(Join-Path \$Folder '%s'\) '([0-9A-F]{64})' "
                          r"\(\[Convert\]::FromBase64String\('([A-Za-z0-9+/=]+)'\)\) ''" % re.escape(name), self.text)
        self.assertTrue(match, name)
        return match.group(1), base64.b64decode(match.group(2))

    def test_the_four_scripts_are_carried_inside_with_their_hashes(self):
        for name, expected in (("install-user.ps1", packager.user_script(VERSION, SHA)),
                               ("remove.ps1", packager.remove_script()),
                               ("uninstall-user.ps1", packager.uninstall_script()),
                               ("cleanup.ps1", packager.cleanup_script())):
            with self.subTest(name=name):
                digest, body = self.embedded(name)
                self.assertEqual(body, expected.encode("ascii"))
                self.assertEqual(digest, hashlib.sha256(body).hexdigest().upper())
                self.assertIn("'%s' = '%s'" % (name, digest), self.text)
        arguments = packager.machine_script(VERSION, SHA, ["/ignore-os-version"])
        self.assertIn(base64.b64encode(packager.user_script(VERSION, SHA, ["/ignore-os-version"]).encode("ascii")).decode(),
                      arguments)

    def test_nothing_but_the_installer_is_taken_from_the_extraction_folder(self):
        self.assertEqual(self.code.count("Join-Path $here"), 1)
        self.assertIn("$source = Join-Path $here 'GrammarlyInstaller.exe'", self.text)
        self.assertNotIn("Join-Path $here $name", self.text)

    def test_the_extraction_folder_must_hold_only_what_the_exe_put_there(self):
        self.assertIn("$expected = @('setup.bat', 'install-machine.ps1', 'GrammarlyInstaller.exe')", self.text)
        self.assertIn("Get-ChildItem -LiteralPath $here -Force -Recurse", self.text)
        self.assertIn("if ($extra.Count -gt 0) { Fail 48", self.text)
        check = self.code.index("if ($extra.Count -gt 0) { Fail 48")
        self.assertLess(check, self.code.index("Get-FileHash -LiteralPath $source"))
        self.assertLess(check, self.code.index("New-Item -ItemType Directory -Path $Folder"))
        self.assertEqual(tuple(packager.EXTRACTED_NAMES), ("setup.bat", "install-machine.ps1", "GrammarlyInstaller.exe"))

    def test_the_task_is_started_once_after_the_entry_and_a_failure_is_only_reported(self):
        start = self.code.index("Start-ScheduledTask -TaskName $TaskName -TaskPath '\\'")
        self.assertGreater(start, self.code.index("-Name 'DisplayVersion' -Value $Version"))
        self.assertIn("} catch { $started = 'could not start it now (", self.code)
        self.assertLess(start, self.code.index("exit 0"))

    def test_no_program_is_called_by_a_bare_name(self):
        for word in ("schtasks", "icacls", "reg.exe", "cmd.exe", "& '", "Invoke-Expression", "iex "):
            self.assertNotIn(word, self.code)

    def test_success_is_the_only_exit_0_and_it_is_last(self):
        self.assertEqual(self.code.count("exit 0"), 1)
        self.assertTrue(self.text.rstrip("\r\n").endswith("exit 0"))


class UserScriptTests(unittest.TestCase):
    def setUp(self):
        self.text = packager.user_script(VERSION, SHA, ["/do-not-create-desktop-shortcut", "/disable-launch-at-startup"])
        self.code = "\r\n".join(code_lines(self.text))

    def test_nothing_for_system_and_service_accounts_and_before_anything_else(self):
        guard = "if ($sid -notmatch '^S-1-(5-21|12-1)-') { exit 0 }"
        self.assertIn(guard, self.text)
        self.assertLess(self.code.index(guard), self.code.index("HKCU:"))
        self.assertLess(self.code.index(guard), self.code.index("$env:LOCALAPPDATA"))
        for sid in ("S-1-5-18", "S-1-5-19", "S-1-5-20", "S-1-5-80-1", "S-1-5-90-0-1"):
            self.assertIsNone(re.match(r"^S-1-(5-21|12-1)-", sid), sid)
        self.assertIsNotNone(re.match(r"^S-1-(5-21|12-1)-", "S-1-5-21-1-2-3-1001"))

    def test_nothing_for_the_first_setup_and_sandbox_accounts(self):
        self.assertIn("if ($account -like 'defaultuser*' -or $account -eq 'WDAGUtilityAccount') { exit 0 }", self.text)
        self.assertLess(self.code.index("$account -like 'defaultuser*'"), self.code.index("HKCU:"))

    def test_it_reads_the_vendors_key_in_the_users_own_hive(self):
        self.assertIn(r"$vendorKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Grammarly Desktop Integrations'",
                      self.text)
        self.assertIn("(Get-ItemProperty -LiteralPath $vendorKey -Name 'DisplayVersion' -ErrorAction Stop).DisplayVersion",
                      self.text)
        self.assertIn("if ($present) { Finish ('present (' + $present + '): nothing to do') 0 }", self.text)
        self.assertNotIn("HKLM:", self.code)
        self.assertNotIn("Registry::HKEY_USERS", self.code)

    def test_it_runs_the_installer_silently_with_the_allowed_parameters_and_never_elevates(self):
        self.assertIn("$InstallerArguments = @('/do-not-create-desktop-shortcut', '/disable-launch-at-startup')", self.text)
        self.assertIn("$info.Arguments = (@('/S') + $InstallerArguments) -join ' '", self.text)
        self.assertIn("$info.UseShellExecute = $false", self.text)
        for word in ("RunAs", "Start-Process", "-Verb", "runas"):
            self.assertNotIn(word, self.code)
        self.assertIn("$InstallerArguments = @()", packager.user_script(VERSION, SHA))

    def test_it_waits_for_the_installer_only_and_never_loops(self):
        self.assertIn("$process.WaitForExit($WaitSeconds * 1000)", self.text)
        self.assertIn("$WaitSeconds = %d" % packager.INSTALLER_WAIT_SECONDS, self.text)
        self.assertEqual(len(re.findall(r"\b(while|for|foreach|do)\s*[({]", self.code)), 0)
        self.assertIn("$MaxAttempts = 3", self.text)
        self.assertIn("if ($attempts -ge $MaxAttempts) { Finish", self.text)

    def test_the_vendors_key_decides_success_not_the_exit_code(self):
        decision = self.code.index("if ($after) {")
        self.assertLess(self.code.index("$code = 'exit code ' + $process.ExitCode"), decision)
        self.assertNotIn("ExitCode -eq", self.code)
        self.assertIn("Finish ('installed ' + $after", self.code[decision:])

    def test_it_runs_a_checked_copy_and_does_not_count_a_copy_of_a_changing_file(self):
        copy = self.code.index("Copy-Item -LiteralPath $staged -Destination $copy")
        check = self.code.index("(Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash -ne $Sha256")
        count = self.code.index("-Name 'Attempts' -Value ($attempts + 1)")
        start = self.code.index("[Diagnostics.Process]::Start($info)")
        self.assertLess(copy, check)
        self.assertLess(check, count)
        self.assertLess(count, start)
        self.assertIn("$Sha256 = '%s'" % SHA.upper(), self.text)

    def test_one_log_line_per_run_in_the_users_own_folder(self):
        self.assertIn("$logFolder = Join-Path $env:LOCALAPPDATA 'GrammarlyPerUserDeployment'", self.text)
        self.assertEqual(self.code.count("Add-Content"), 1)
        self.assertEqual(len(re.findall(r"\bexit (?:\$Code|[0-9])", self.code)), 4)  # two account guards, the lock, Finish
        self.assertIn("-Encoding Ascii", self.text)

    def test_one_run_per_person_at_a_time(self):
        self.assertIn("[IO.File]::Open((Join-Path $logFolder 'install.lock'), 'OpenOrCreate', 'ReadWrite', 'None')", self.text)


class RemoveScriptTests(unittest.TestCase):
    def setUp(self):
        self.text = packager.remove_script()
        self.code = "\r\n".join(code_lines(self.text))

    def test_the_order_of_the_removal(self):
        steps = [
            "Get-FileHash -LiteralPath (Join-Path $Folder $name) -Algorithm SHA256).Hash -ne $removal[$name]) { Fail 50",
            "Unregister-ScheduledTask -TaskName $TaskName -TaskPath '\\' -Confirm:$false",
            "foreach ($name in @('GrammarlyInstaller.exe', 'install-user.ps1')) {",
            "Register-ScheduledTask -TaskName $RemovalTaskName",
            "Start-ScheduledTask -TaskName $RemovalTaskName -TaskPath '\\'",
            "Register-ScheduledTask -TaskName $CleanupTaskName",
            "Set-ItemProperty -LiteralPath $RemovalKey -Name 'RemovedUtc'",
            "Remove-Item -LiteralPath $MarkerKey -Recurse -Force",
            "exit 0",
        ]
        places = [self.code.index(step) for step in steps]
        self.assertEqual(places, sorted(places))
        for step in steps:
            self.assertEqual(self.code.count(step), 1, step)

    def test_the_removal_scripts_are_compared_with_their_packed_hashes_and_their_access_before_anything_changes(self):
        for name, text in (("uninstall-user.ps1", packager.uninstall_script()), ("cleanup.ps1", packager.cleanup_script())):
            self.assertIn("'%s' = '%s'" % (name, hashlib.sha256(text.encode("ascii")).hexdigest().upper()), self.text)
        self.assertIn("$problem = Test-FolderAccess $Folder $true", self.text)
        self.assertIn("if (-not $problem) { $problem = Test-FolderAccess (Join-Path $Folder $name) $false }", self.text)
        first_change = self.code.index("Unregister-ScheduledTask")
        self.assertLess(self.code.index("if ($problem) { Fail 50 $problem }"), first_change)
        # nothing is written by remove.ps1 into the folder: the install wrote the texts
        self.assertNotIn("FromBase64String", self.text)
        for word in ("WriteAllBytes", "Set-Content", "Out-File", "Copy-Item", "SetAccessControl"):
            self.assertNotIn(word, self.code)

    def test_a_staged_file_that_cannot_be_deleted_stops_the_removal(self):
        # reader's guard 632: with the installer or install-user.ps1 still staged nothing goes on
        loop = self.code.index("foreach ($name in @('GrammarlyInstaller.exe', 'install-user.ps1')) {")
        check = self.code.index("    if (Test-Path -LiteralPath $path) { Fail 47 ('could not delete ' + $path) }\r\n}")
        self.assertLess(loop, check)
        self.assertLess(self.code.index("try { Remove-Item -LiteralPath $path -Force }"), check)
        self.assertLess(check, self.code.index("Register-ScheduledTask"))

    def test_the_hashes_are_the_ones_the_install_stages(self):
        machine = packager.machine_script(VERSION, SHA)
        for name in ("uninstall-user.ps1", "cleanup.ps1"):
            digest = re.search(r"'%s' = '([0-9A-F]{64})'" % re.escape(name), self.text).group(1)
            self.assertIn("'%s' = '%s'" % (name, digest), machine)

    def test_the_removal_task_runs_at_any_sign_in_as_the_users_group_with_least_privilege_hidden(self):
        part =self.text[self.text.index("# 3. The removal task"):self.text.index("# 4. The cleanup task")]
        self.assertIn("$trigger = New-ScheduledTaskTrigger -AtLogOn\r\n", part)
        self.assertIn("$taskPrincipal = New-ScheduledTaskPrincipal -GroupId $UsersSid -RunLevel Limited", part)
        self.assertIn(r"$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'", self.text)
        self.assertIn("New-ScheduledTaskAction -Execute $powershell -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden "
                      "-ExecutionPolicy Bypass -File \"' + (Join-Path $Folder 'uninstall-user.ps1') + '\"')", part)
        self.assertIn("if ($group -ne $UsersSid) { Fail 51", part)
        self.assertIn("if ([string]$task.Principal.RunLevel -ne 'Limited') { Fail 51", part)
        self.assertIn("} catch { $started = 'could not start it now (", part)
        self.assertIn("$UsersSid = 'S-1-5-32-545'", self.text)

    def test_the_cleanup_task_runs_as_system_at_start_and_daily(self):
        part = self.text[self.text.index("# 4. The cleanup task"):self.text.index("# 5. The removal's date")]
        self.assertIn("@((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -Daily -At '%s'))"
                      % packager.CLEANUP_DAILY_AT, part)
        self.assertIn("New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -LogonType ServiceAccount -RunLevel Highest", part)
        self.assertIn("(Join-Path $Folder 'cleanup.ps1')", part)
        self.assertIn("if ($runAs -ne 'S-1-5-18') { Fail 52", part)
        self.assertIn("-StartWhenAvailable", part)

    def test_the_date_is_utc_in_one_hklm_key_and_a_recorded_date_is_kept(self):
        self.assertIn("[DateTime]::UtcNow.ToString('yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)", self.text)
        self.assertIn("if (-not (Get-ItemProperty -LiteralPath $RemovalKey).'RemovedUtc') {", self.text)
        self.assertIn(r"$RemovalKey = 'HKLM:\SOFTWARE\' + $MarkerKeyName", self.text)
        self.assertEqual(len(re.findall(r"Set-ItemProperty", self.code)), 1)

    def test_nothing_runs_from_or_writes_into_a_profile(self):
        for word in ("HKCU", "LOCALAPPDATA", "APPDATA", "USERPROFILE", "ProfileList", "Registry::HKEY_USERS", r"C:\Users",
                     "/uninstall", "Uninstall.exe"):
            self.assertNotIn(word, self.code)

    def test_success_is_the_only_exit_0_and_it_is_last(self):
        self.assertEqual(self.code.count("exit 0"), 1)
        self.assertTrue(self.text.rstrip("\r\n").endswith("exit 0"))
        self.assertIn("each person's own sign-in", self.text)

    def test_the_same_names_as_the_install(self):
        machine = packager.machine_script(VERSION, SHA)
        for line in ("$FolderName = 'Grammarly Deployment'", "$TaskName = 'Grammarly per-user install'",
                     "$MarkerKeyName = 'GrammarlyPerUserDeployment'", "$RemovalTaskName = 'Grammarly per-user removal'",
                     "$CleanupTaskName = 'Grammarly removal cleanup'"):
            self.assertIn(line, self.text)
            self.assertIn(line, machine)
            if not line.startswith("$TaskName"):
                self.assertIn(line, packager.cleanup_script())


class UninstallScriptTests(unittest.TestCase):
    def setUp(self):
        self.text = packager.uninstall_script()
        self.code = "\r\n".join(code_lines(self.text))
        self.user = "\r\n".join(code_lines(packager.user_script(VERSION, SHA)))

    def test_the_same_account_guards_as_the_install_and_before_anything_else(self):
        for guard in ("if ($sid -notmatch '^S-1-(5-21|12-1)-') { exit 0 }",
                      "if ($account -like 'defaultuser*' -or $account -eq 'WDAGUtilityAccount') { exit 0 }"):
            self.assertIn(guard, self.code)
            self.assertIn(guard, self.user)
            self.assertLess(self.code.index(guard), self.code.index("HKCU:"))
            self.assertLess(self.code.index(guard), self.code.index("$env:LOCALAPPDATA"))

    def test_one_run_per_person_at_a_time_shared_with_the_install(self):
        lock = "[IO.File]::Open((Join-Path $logFolder 'install.lock'), 'OpenOrCreate', 'ReadWrite', 'None')"
        self.assertIn(lock, self.code)
        self.assertIn(lock, self.user)
        self.assertLess(self.code.index(lock), self.code.index("Get-ItemProperty"))

    def test_one_log_line_per_run_in_the_persons_own_folder(self):
        self.assertIn("$logFolder = Join-Path $env:LOCALAPPDATA 'GrammarlyPerUserDeployment'", self.text)
        self.assertIn("$log = Join-Path $logFolder 'uninstall.log'", self.text)
        self.assertEqual(self.code.count("Add-Content"), 1)
        self.assertEqual(len(re.findall(r"\bexit (?:\$Code|[0-9])", self.code)), 4)  # two account guards, the lock, Finish

    def test_only_the_exact_command_of_this_profile_is_accepted(self):
        self.assertIn(r"$uninstaller = Join-Path $env:LOCALAPPDATA 'Grammarly\DesktopIntegrations\Uninstall.exe'", self.text)
        self.assertIn("$expected = '\"' + $uninstaller + '\" /S'", self.text)
        self.assertIn("(Get-ItemProperty -LiteralPath $vendorKey -Name 'QuietUninstallString' -ErrorAction Stop)", self.text)
        self.assertIn("if ($command -cne $expected) { Finish ('not removed:", self.code)
        check = self.code.index("if ($command -cne $expected)")
        self.assertLess(check, self.code.index("[Diagnostics.Process]::Start($info)"))
        # it runs the path that it built and compared, never the text that it read
        self.assertIn("$info.FileName = $uninstaller", self.code)
        self.assertIn("$info.Arguments = '/S'", self.code)
        self.assertNotIn("$info.FileName = $command", self.code)
        for word in ("Invoke-Expression", "iex ", "cmd.exe", "& $command", "Start-Process", "RunAs", "-Verb", "runas"):
            self.assertNotIn(word, self.code)
        self.assertIn("$info.UseShellExecute = $false", self.code)

    def test_a_missing_uninstaller_is_not_run(self):
        # reader's guard 729
        check = self.code.index("if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) { Finish ('not removed: ' + $uninstaller + ' is missing') 1 }")
        self.assertLess(self.code.index("if ($command -cne $expected)"), check)
        self.assertLess(check, self.code.index("[Diagnostics.Process]::Start($info)"))

    def test_no_grammarly_is_one_line_and_exit_0(self):
        self.assertIn("Finish 'no Grammarly in this profile: nothing to do' 0", self.code)
        self.assertLess(self.code.index("if (-not (Test-Path -LiteralPath $vendorKey)) {"),
                        self.code.index("QuietUninstallString"))

    def test_the_entry_decides_success_within_a_bounded_wait(self):
        self.assertIn("$WaitSeconds = %d" % packager.UNINSTALL_WAIT_SECONDS, self.text)
        self.assertIn("$PollSeconds = %d" % packager.UNINSTALL_POLL_SECONDS, self.text)
        self.assertIn("$deadline = (Get-Date).AddSeconds($WaitSeconds)", self.code)
        self.assertIn("$process.WaitForExit($WaitSeconds * 1000)", self.code)
        self.assertIn("while ((Test-Path -LiteralPath $vendorKey) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds $PollSeconds }",
                      self.code)
        self.assertEqual(len(re.findall(r"\b(while|for|foreach|do)\s*[({]", self.code)), 1)
        decision = self.code.index("if (Test-Path -LiteralPath $vendorKey) { Finish ('not removed: the entry is still there")
        self.assertLess(self.code.index("$code = 'exit code ' + $process.ExitCode"), decision)
        self.assertNotIn("ExitCode -eq", self.code)
        self.assertIn("Finish ('removed Grammarly from this profile", self.code[decision:])

    def test_it_reads_only_the_persons_own_hive(self):
        self.assertNotIn("HKLM:", self.code)
        self.assertNotIn("Registry::HKEY_USERS", self.code)
        self.assertIn(r"$vendorKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Grammarly Desktop Integrations'",
                      self.text)


class CleanupScriptTests(unittest.TestCase):
    def setUp(self):
        self.text = packager.cleanup_script()
        self.code = "\r\n".join(code_lines(self.text))

    def test_the_profiles_are_only_tested_with_test_path(self):
        uses = [line.strip() for line in self.code.split("\r\n") if "$profilePath" in line or "$entry" in line]
        self.assertEqual(uses, [
            "foreach ($entry in @(Get-ChildItem -LiteralPath $profileList)) {",
            "if ($entry.PSChildName -notmatch '^S-1-(5-21|12-1)-') { continue }",
            "$profilePath = [string]$entry.GetValue('ProfileImagePath')",
            "if (-not $profilePath) { continue }",
            r"if (Test-Path -LiteralPath ($profilePath.TrimEnd('\') + '\AppData\Local\Grammarly\DesktopIntegrations\Uninstall.exe') "
            "-PathType Leaf) { $left++ }",
        ])
        self.assertIn(r"$profileList = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList'", self.text)
        for word in ("HKCU", "LOCALAPPDATA", "USERPROFILE", "Registry::HKEY_USERS", "Get-Content", "Get-ChildItem -LiteralPath $profilePath",
                     "Start-Process", "Diagnostics.Process", "Invoke-Expression", "Set-Content", "Copy-Item", "New-Item",
                     "Set-ItemProperty", "Get-Acl", "Get-FileHash"):
            self.assertNotIn(word, self.code)
        # what it removes is only its own: the folder under Program Files and the HKLM key
        self.assertEqual(sorted(set(re.findall(r"Remove-Item -LiteralPath (\$\w+)", self.code))), ["$Folder", "$RemovalKey", "$_", "$self"])

    def test_the_end_comes_when_no_profile_has_it_or_after_90_days(self):
        self.assertEqual(packager.REMOVAL_KEEP_DAYS, 90)
        self.assertIn("$KeepDays = 90", self.text)
        self.assertIn("$expired = (-not $removedOn) -or ($removedOn.AddDays($KeepDays) -lt [DateTime]::UtcNow.Date)", self.code)
        self.assertIn("[DateTime]::ParseExact($text, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)", self.code)
        self.assertIn("if ($left -gt 0 -and -not $expired) {", self.code)
        stop = self.code.index("if ($left -gt 0 -and -not $expired) {")
        self.assertLess(stop, self.code.index("Unregister-ScheduledTask"))
        self.assertLess(stop, self.code.index("Remove-Item"))

    def test_it_does_nothing_while_the_item_is_installed_again(self):
        guard = self.code.index("if (Test-Path -LiteralPath $MarkerKey) {")
        self.assertLess(guard, self.code.index("Get-ChildItem"))
        self.assertLess(guard, self.code.index("Remove-Item"))

    def test_the_end_unregisters_both_tasks_before_it_deletes_and_this_script_last(self):
        loop = self.code.index("foreach ($name in @($RemovalTaskName, $CleanupTaskName)) {")
        unregister = self.code.index("Unregister-ScheduledTask -TaskName $name -TaskPath '\\' -Confirm:$false")
        stop = self.code.index("Write-Output ('ERROR 54: the task ' + $name + ' could not be unregistered; nothing was deleted: '")
        others = self.code.index("Where-Object { $_.FullName -ne $self } | ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }")
        self_delete = self.code.index("if (Test-Path -LiteralPath $self) { Remove-Item -LiteralPath $self -Force }")
        folder = self.code.index("Remove-Item -LiteralPath $Folder -Recurse -Force")
        key = self.code.index("Remove-Item -LiteralPath $RemovalKey -Recurse -Force")
        self.assertEqual([loop, unregister, stop, others, self_delete, folder, key],
                         sorted([loop, unregister, stop, others, self_delete, folder, key]))
        self.assertEqual(self.code.count("Unregister-ScheduledTask"), 1)
        self.assertIn(r"$self = Join-Path $Folder 'cleanup.ps1'", self.text)
        self.assertTrue(self.text.rstrip("\r\n").endswith("exit 0"))

    def test_a_task_that_cannot_be_unregistered_stops_the_run_before_anything_is_deleted(self):
        # reader's guard 808: nothing is deleted while a task is left that would run a missing script
        catch = self.code.index("could not be unregistered; nothing was deleted: ' + $_.Exception.Message)\r\n        exit 54")
        self.assertLess(catch, self.code.index("Remove-Item"))
        self.assertIn("nothing was deleted; the next run tries again", packager.CLEANUP_CODES[54])
        self.assertIn("inert: no task runs them", packager.CLEANUP_CODES[54])

    def test_an_unreadable_profile_list_counts_as_a_profile_with_grammarly(self):
        # reader's guard 794: an unreadable ProfileList must not end the removal at once
        self.assertIn("} catch {\r\n    # The list could not be read: as if a profile still had it, so only the days end the "
                      "removal.\r\n    $left = 1\r\n}", self.text)

    def test_the_lock_is_taken_without_waiting_before_anything_else(self):
        self.assertIn("$mutex = New-Object Threading.Mutex($false, '%s')" % packager.MUTEX_NAME, self.code)
        self.assertIn("$owned = $mutex.WaitOne(0)", self.code)
        self.assertIn("if ($_.Exception.GetBaseException() -is [Threading.AbandonedMutexException]) { $owned = $true }", self.code)
        gate = self.code.index("if (-not $owned) {")
        self.assertIn("exit 0", self.code[gate:gate + 120])
        for later in ("if (Test-Path -LiteralPath $MarkerKey)", "Get-ChildItem", "Unregister-ScheduledTask", "Remove-Item"):
            self.assertLess(gate, self.code.index(later), later)
        self.assertNotIn("ReleaseMutex", self.code)  # held until the run ends

    def test_the_entry_is_read_again_just_before_the_end(self):
        guard = "if (Test-Path -LiteralPath $MarkerKey) {"
        self.assertEqual(self.code.count(guard), 2)
        second = self.code.rindex(guard)
        self.assertGreater(second, self.code.index("if ($left -gt 0 -and -not $expired) {"))
        self.assertLess(second, self.code.index("Unregister-ScheduledTask"))
        self.assertIn("exit 0", self.code[second:second + 120])


class LockTests(unittest.TestCase):
    """install-machine.ps1 and cleanup.ps1 share one named mutex."""

    def test_one_global_name_in_both(self):
        self.assertTrue(packager.MUTEX_NAME.startswith("Global\\"))
        line = "New-Object Threading.Mutex($false, '%s')" % packager.MUTEX_NAME
        self.assertIn(line, packager.machine_script(VERSION, SHA))
        self.assertIn(line, packager.cleanup_script())

    def test_the_install_holds_it_from_before_0b_until_after_the_entry(self):
        code = "\r\n".join(code_lines(packager.machine_script(VERSION, SHA)))
        take = code.index("$owned = $mutex.WaitOne(%d * 1000)" % packager.MUTEX_WAIT_SECONDS)
        gate = code.index("if (-not $owned) { Fail 49")
        pending = code.index("foreach ($name in @($RemovalTaskName, $CleanupTaskName)) {")
        entry = code.index("Set-ItemProperty -LiteralPath $MarkerKey -Name 'DisplayVersion' -Value $Version")
        release = code.index("try { $mutex.ReleaseMutex() } catch { }")
        start = code.index("Start-ScheduledTask -TaskName $TaskName")
        self.assertEqual([take, gate, pending, entry, release, start], sorted([take, gate, pending, entry, release, start]))
        self.assertGreater(take, code.index("if ($extra.Count -gt 0) { Fail 48"))
        self.assertEqual(code.count("ReleaseMutex"), 1)

    def test_the_install_takes_an_abandoned_lock(self):
        # cleanup.ps1 never releases the lock, so an install that waited on a cleanup always gets it abandoned:
        # that must count as taken, not as a failure
        code = "\r\n".join(code_lines(packager.machine_script(VERSION, SHA)))
        self.assertIn("if ($_.Exception.GetBaseException() -is [Threading.AbandonedMutexException]) { $owned = $true } else { Fail 49",
                      code)
        self.assertEqual(code.count("[Threading.AbandonedMutexException]) { $owned = $true }"), 1)


class InstallAfterRemoveTests(unittest.TestCase):
    def setUp(self):
        self.machine = "\r\n".join(code_lines(packager.machine_script(VERSION, SHA)))

    def test_an_install_takes_a_pending_removal_away_before_it_stages(self):
        step = self.machine.index("foreach ($name in @($RemovalTaskName, $CleanupTaskName)) {")
        self.assertIn("Unregister-ScheduledTask -TaskName $name -TaskPath '\\' -Confirm:$false", self.machine[step:step + 300])
        key = self.machine.index("if (Test-Path -LiteralPath $RemovalKey) { Remove-Item -LiteralPath $RemovalKey -Recurse -Force }")
        self.assertIn("} catch { Fail 49", self.machine[key:key + 200])
        # after the checks of what was unpacked, before the folder and the files
        self.assertLess(self.machine.index("if ($extra.Count -gt 0) { Fail 48"), step)
        self.assertLess(self.machine.index("Get-FileHash -LiteralPath $source"), step)
        self.assertLess(key, self.machine.index("New-Item -ItemType Directory -Path $Folder"))
        self.assertLess(key, self.machine.index("Install-Staged (Join-Path $Folder 'GrammarlyInstaller.exe')"))

    def test_the_install_stages_what_a_later_removal_needs(self):
        # a removal deletes the installer and install-user.ps1 and keeps the rest; an install stages all again
        for name in ("GrammarlyInstaller.exe", "install-user.ps1", "remove.ps1", "uninstall-user.ps1", "cleanup.ps1"):
            self.assertIn("Install-Staged (Join-Path $Folder '%s')" % name, self.machine)
        # the key that a removal writes and that cleanup reads is the one that the install takes away
        for text in (packager.remove_script(), packager.cleanup_script(), packager.machine_script(VERSION, SHA)):
            self.assertIn(r"$RemovalKey = 'HKLM:\SOFTWARE\' + $MarkerKeyName", text)


class BuildTests(unittest.TestCase):
    """A whole run with the stub and 7z replaced: what is packed, and when nothing is built."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.installer = os.path.join(self.folder.name, "downloads", "GrammarlyInstaller.exe")
        os.makedirs(os.path.dirname(self.installer))
        with open(self.installer, "wb") as handle:
            handle.write(b"MZ" + b"g" * 100)
        self.staged = {}
        self.packs = 0
        test = self

        class Fake(packager.GrammarlyPerUserPackager):
            def stub(self, work):
                path = os.path.join(work, "stub.sfx")
                with open(path, "wb") as handle:
                    handle.write(b"MZstub")
                return path

            def sevenzip(self):
                return "/usr/bin/true"
        self.Fake = Fake
        real_run = packager.subprocess.run

        def run(command, **kwargs):
            if command[0] == "/usr/bin/true" and command[1] == "a":
                test.packs += 1
                test.staged.clear()
                stage = kwargs["cwd"]
                for name in os.listdir(stage):
                    with open(os.path.join(stage, name), "rb") as handle:
                        test.staged[name] = handle.read()
                with open(command[command.index("-y") + 1], "wb") as handle:
                    handle.write(b"ARCHIVE")
            return real_run(["/usr/bin/true"], capture_output=True, text=True)
        packager.subprocess.run = run
        self.real_run = real_run
        self.addCleanup(lambda: setattr(packager.subprocess, "run", real_run))

    def env(self, **more):
        env = {"RECIPE_CACHE_DIR": self.folder.name, "pathname": self.installer, "version": VERSION,
               "sfx_sdk_url": "https://example.invalid/sdk.7z", "sfx_sdk_sha256": "0" * 64,
               "grammarly_installer_arguments": ""}
        env.update(more)
        return env

    def test_a_build_and_then_nothing_to_build(self):
        processor = self.Fake(env=self.env())
        processor.main()
        exe = processor.env["pathname"]
        self.assertEqual(os.path.basename(exe), "GrammarlyPerUser-%s.exe" % VERSION)
        with open(exe, "rb") as handle:
            self.assertEqual(handle.read(), b"MZstubARCHIVE")
        self.assertEqual(processor.env["version"], VERSION)
        self.assertNotIn("checksum_verified", processor.env)
        self.assertNotIn("checksum_sha256", processor.env)
        self.assertEqual(sorted(self.staged), sorted(packager.EXTRACTED_NAMES))
        self.assertEqual(self.staged["GrammarlyInstaller.exe"], b"MZ" + b"g" * 100)
        sha = packager.sha256_of_file(self.installer)
        self.assertEqual(processor.env["grammarly_installer_sha256"], sha)
        self.assertEqual(self.staged["install-machine.ps1"].decode("ascii"), packager.machine_script(VERSION, sha))
        self.assertIn(base64.b64encode(packager.user_script(VERSION, sha).encode("ascii")).decode(),
                      self.staged["install-machine.ps1"].decode("ascii"))
        self.assertEqual(self.staged["setup.bat"].decode("ascii"), packager.setup_bat())
        for script in (packager.remove_script(), packager.uninstall_script(), packager.cleanup_script()):
            self.assertIn(base64.b64encode(script.encode("ascii")).decode(), self.staged["install-machine.ps1"].decode("ascii"))
        self.assertEqual([name for name in os.listdir(self.folder.name) if name.startswith("grammarly-build-")], [])

        again = self.Fake(env=self.env())
        again.main()
        self.assertEqual(again.env["pathname"], exe)
        self.assertEqual(self.packs, 1)

    def verified(self, **more):
        return self.env(signature_verified=True, signature_sha256=packager.sha256_of_file(self.installer), **more)

    def test_a_verified_installer_hands_its_signature_over_to_the_exe_built_in_this_run(self):
        processor = self.Fake(env=self.verified())
        processor.main()
        exe = processor.env["pathname"]
        self.assertIs(processor.env["signature_verified"], True)
        self.assertEqual(processor.env["signature_sha256"], packager.sha256_of_file(exe))
        self.assertNotEqual(processor.env["signature_sha256"], packager.sha256_of_file(self.installer))
        self.assertEqual(self.staged["GrammarlyInstaller.exe"], b"MZ" + b"g" * 100)
        self.assertIn("whose signature was verified", processor.env["grammarly_packager_summary_result"]["summary_text"])

    def test_a_verified_installer_never_takes_a_cached_exe(self):
        self.Fake(env=self.env()).main()
        processor = self.Fake(env=self.verified())
        processor.main()
        self.assertEqual(self.packs, 2)
        self.assertEqual(processor.env["signature_sha256"], packager.sha256_of_file(processor.env["pathname"]))

    def test_a_signature_of_another_file_stops_the_build(self):
        with self.assertRaises(ProcessorError) as caught:
            self.Fake(env=self.env(signature_verified=True, signature_sha256=OTHER_SHA)).main()
        self.assertIn("signature_sha256 is the hash of another file than the installer", str(caught.exception))
        self.assertEqual(self.packs, 0)

    def test_an_unverified_installer_hands_nothing_over(self):
        for more in ({}, {"signature_verified": "true"}, {"signature_verified": False},
                     {"signature_verified": True, "signature_sha256": "not a hash"}):
            with self.subTest(more=more):
                env = self.env(**more)
                if "signature_verified" in more and "signature_sha256" not in more:
                    env["signature_sha256"] = packager.sha256_of_file(self.installer)
                processor = self.Fake(env=env)
                processor.main()
                self.assertEqual(processor.env.get("signature_sha256"), env.get("signature_sha256"))
                self.assertIn("NOT verified", processor.env.get("grammarly_packager_summary_result", {}).get(
                    "summary_text", "NOT verified"))

    def test_an_installer_that_changes_while_it_is_staged_stops_the_build(self):
        real = packager.shutil.copyfile

        def changed(source, target):
            real(source, target)
            with open(target, "ab") as handle:
                handle.write(b"!")
        packager.shutil.copyfile = changed
        self.addCleanup(lambda: setattr(packager.shutil, "copyfile", real))
        with self.assertRaises(ProcessorError) as caught:
            self.Fake(env=self.verified()).main()
        self.assertIn("The installer changed while it was copied into the stage", str(caught.exception))
        self.assertEqual(self.packs, 0)

    def test_the_packed_files_are_named_in_order_with_a_fixed_time_and_mode(self):
        seen = {}
        real_run = packager.subprocess.run

        def run(command, **kwargs):
            if command[1] == "a":
                stage = kwargs["cwd"]
                seen["names"] = command[command.index("-y") + 2:]
                seen["switches"] = command[2:command.index("-y")]
                seen["stat"] = {name: (int(os.stat(os.path.join(stage, name)).st_mtime),
                                       os.stat(os.path.join(stage, name)).st_mode & 0o777) for name in os.listdir(stage)}
            return real_run(command, **kwargs)
        packager.subprocess.run = run
        self.addCleanup(lambda: setattr(packager.subprocess, "run", real_run))
        self.Fake(env=self.env()).main()
        self.assertEqual(seen["names"], sorted(seen["stat"]))
        self.assertNotIn(".", seen["names"])
        self.assertIn("-mtc=off", seen["switches"])
        self.assertIn("-mta=off", seen["switches"])
        self.assertEqual(set(seen["stat"].values()), {(packager.PACKED_FILE_TIME, packager.PACKED_FILE_MODE)})

    @unittest.skipUnless(any(shutil.which(name) for name in packager.SEVENZIP_NAMES), "no 7z program is installed")
    def test_two_builds_in_two_cache_folders_are_the_same_bytes(self):  # pragma: no cover - only where 7z exists
        packager.subprocess.run = self.real_run
        sevenzip = next(shutil.which(name) for name in packager.SEVENZIP_NAMES if shutil.which(name))

        class Real(self.Fake):
            def sevenzip(self):
                return sevenzip
        digests = []
        for number in (1, 2):
            cache = os.path.join(self.folder.name, "cache%d" % number)
            processor = Real(env=self.env(RECIPE_CACHE_DIR=cache))
            processor.main()
            digests.append(packager.sha256_of_file(processor.env["pathname"]))
            time.sleep(1.1)  # the staged copies of the second build are written in another second
        self.assertEqual(digests[0], digests[1])

    def test_other_parameters_build_again_into_the_user_script(self):
        self.Fake(env=self.env()).main()
        self.Fake(env=self.env(grammarly_installer_arguments="/disable-launch-at-startup")).main()
        self.assertEqual(self.packs, 2)
        user = packager.user_script(VERSION, packager.sha256_of_file(self.installer), ["/disable-launch-at-startup"])
        self.assertIn(b"$InstallerArguments = @('/disable-launch-at-startup')", user.encode("ascii"))
        self.assertIn(base64.b64encode(user.encode("ascii")), self.staged["install-machine.ps1"])

    def test_a_changed_removal_text_builds_a_new_exe(self):
        self.Fake(env=self.env()).main()
        for name, value in (("UNINSTALL_WAIT_SECONDS", 601), ("REMOVAL_KEEP_DAYS", 91)):
            saved = getattr(packager, name)
            setattr(packager, name, value)
            self.addCleanup(setattr, packager, name, saved)
            before = self.packs
            self.Fake(env=self.env()).main()
            self.assertEqual(self.packs, before + 1, name)
        self.assertIn(base64.b64encode(packager.cleanup_script().encode("ascii")), self.staged["install-machine.ps1"])
        self.assertIn(b"$KeepDays = 91", base64.b64decode(re.search(
            rb"'cleanup\.ps1'\) '[0-9A-F]{64}' \(\[Convert\]::FromBase64String\('([A-Za-z0-9+/=]+)'",
            self.staged["install-machine.ps1"]).group(1)))

    def test_a_cached_exe_that_changed_is_built_again_and_no_partial_is_left(self):
        processor = self.Fake(env=self.env())
        processor.main()
        exe = processor.env["pathname"]
        with open(exe, "r+b") as handle:  # the same size, other content
            handle.write(b"XX")
        self.Fake(env=self.env()).main()
        self.assertEqual(self.packs, 2)
        with open(exe, "rb") as handle:
            self.assertEqual(handle.read(), b"MZstubARCHIVE")
        with open(exe, "ab") as handle:  # another size
            handle.write(b"!")
        self.Fake(env=self.env()).main()
        self.assertEqual(self.packs, 3)
        self.assertFalse([name for name in os.listdir(self.folder.name) if name.endswith(".partial")])

    def test_an_older_exe_is_removed(self):
        self.Fake(env=self.env(version="1.2.311.1999")).main()
        self.Fake(env=self.env()).main()
        names = sorted(name for name in os.listdir(self.folder.name) if name.startswith("GrammarlyPerUser-"))
        self.assertEqual(names, ["GrammarlyPerUser-%s.exe" % VERSION, "GrammarlyPerUser-%s.exe.json" % VERSION])

    def test_what_is_refused_before_anything_is_built(self):
        cases = [{"version": "1.2'x"}, {"grammarly_installer_arguments": "/uninstall"},
                 {"sfx_sdk_sha256": "short"}, {"pathname": os.path.join(self.folder.name, "missing.exe")}]
        for more in cases:
            with self.subTest(more=more):
                with self.assertRaises(ProcessorError):
                    self.Fake(env=self.env(**more)).main()
        with open(self.installer, "wb") as handle:
            handle.write(b"<html>not a program</html>")
        with self.assertRaises(ProcessorError):
            self.Fake(env=self.env()).main()
        self.assertEqual(self.packs, 0)

    def test_a_file_too_large_for_the_stub_is_refused(self):
        saved = packager.MAX_INSTALLER_BYTES
        packager.MAX_INSTALLER_BYTES = 10
        self.addCleanup(lambda: setattr(packager, "MAX_INSTALLER_BYTES", saved))
        with self.assertRaises(ProcessorError):
            self.Fake(env=self.env()).main()
        self.assertEqual(self.packs, 0)


class StubTests(unittest.TestCase):
    """The stub: the SDK must have its SHA-256, be small, and hold a Windows program."""

    def setUp(self):
        self.work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.work)
        self.body = b"sdk archive"
        self.saved = packager.fetch_bytes
        self.addCleanup(lambda: setattr(packager, "fetch_bytes", self.saved))
        self.member = b"MZ stub"
        test = self

        class Stub(packager.GrammarlyPerUserPackager):
            def run_sevenzip(self, arguments, what, cwd=None):
                with open(os.path.join(test.work, "7zS2con.sfx"), "wb") as handle:
                    handle.write(test.member)
        self.Stub = Stub

    def processor(self, sha=None):
        packager.fetch_bytes = lambda url, max_bytes, what: self.body
        return self.Stub(env={"sfx_sdk_url": "https://example.invalid/sdk.7z",
                              "sfx_sdk_sha256": sha or hashlib.sha256(self.body).hexdigest()})

    def test_the_right_archive_gives_the_stub(self):
        self.assertEqual(self.processor().stub(self.work), os.path.join(self.work, "7zS2con.sfx"))

    def test_another_archive_stops_the_run(self):
        with self.assertRaises(ProcessorError):
            self.processor(sha="0" * 64).stub(self.work)

    def test_a_member_that_is_not_a_windows_program_stops_the_run(self):
        self.member = b"<html>"
        with self.assertRaises(ProcessorError):
            self.processor().stub(self.work)

    def test_a_hash_that_is_not_a_sha256_stops_the_run(self):
        with self.assertRaises(ProcessorError):
            self.processor(sha="short").stub(self.work)

    def test_an_oversized_download_is_refused(self):
        class Response:
            def __init__(self, body):
                self.body = body

            def read(self, count):
                return self.body[:count]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class Opener:
            def open(self, request, timeout):
                return Response(b"x" * 20)
        saved = packager.urllib.request.build_opener
        packager.urllib.request.build_opener = lambda *handlers: Opener()
        self.addCleanup(lambda: setattr(packager.urllib.request, "build_opener", saved))
        with self.assertRaises(ProcessorError):
            self.saved("https://example.invalid/sdk.7z", 10, "the SDK")
        self.assertEqual(self.saved("https://example.invalid/sdk.7z", 20, "the SDK"), b"x" * 20)


class RecipeTests(unittest.TestCase):
    def packer_step(self):
        steps = [step for step in load("Grammarly-Win.download.recipe")["Process"]
                 if step["Processor"] == "GrammarlyPerUserPackager"]
        self.assertEqual(len(steps), 1)
        return steps[0]

    def test_the_packer_is_the_last_step_and_gets_only_declared_inputs(self):
        recipe = load("Grammarly-Win.download.recipe")
        self.assertEqual(recipe["Process"][-1]["Processor"], "GrammarlyPerUserPackager")
        declared = packager.GrammarlyPerUserPackager.input_variables
        arguments = self.packer_step()["Arguments"]
        self.assertEqual(set(arguments) | {"sevenzip_path"}, set(declared))
        for key, flags in declared.items():
            if flags.get("required"):
                self.assertIn(key, arguments)
        self.assertEqual(arguments["pathname"], "%pathname%")
        self.assertEqual(arguments["version"], "%version%")

    def test_the_inputs_of_the_packer(self):
        recipe = load("Grammarly-Win.download.recipe")
        self.assertEqual(recipe["Input"]["GRAMMARLY_INSTALLER_ARGUMENTS"], "")
        self.assertEqual(packager.parse_installer_arguments(recipe["Input"]["GRAMMARLY_INSTALLER_ARGUMENTS"]), [])
        for value in self.packer_step()["Arguments"].values():
            name = value.strip("%")
            self.assertTrue(name in recipe["Input"] or name in ("pathname", "version"), name)

    def test_the_stub_is_the_same_sdk_as_the_office_folders(self):
        office = os.path.join(os.path.dirname(RECIPE_DIR), "Win-Microsoft365Apps", "Microsoft365Apps-Win.download.recipe")
        with open(office, "rb") as handle:
            office_input = plistlib.load(handle)["Input"]
        recipe = load("Grammarly-Win.download.recipe")
        for key in ("SFX_SDK_URL", "SFX_SDK_SHA256"):
            self.assertEqual(recipe["Input"][key], office_input[key])
        self.assertTrue(recipe["Input"]["SFX_SDK_URL"].startswith("https://"))

    def test_the_processor_is_folder_local_and_imports_nothing_from_another_folder(self):
        with open(os.path.join(RECIPE_DIR, "GrammarlyPerUserPackager.py"), encoding="utf-8") as handle:
            text = handle.read()
        imports = re.findall(r"^(?:from|import) (\w+)", text, re.M)
        self.assertEqual(sorted(set(imports)), sorted({"base64", "hashlib", "json", "os", "re", "shutil", "subprocess",
                                                        "tempfile", "urllib", "autopkglib"}))
        text.encode("ascii")


if __name__ == "__main__":
    unittest.main()
