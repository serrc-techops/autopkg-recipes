# Win-Grammarly

A Windows recipe pair: Grammarly for Windows, the vendor's `.exe` installer packed into one self-extracting EXE that installs Grammarly for each person at sign-in, with the version label read from the installer itself.

**Status. Main caveat: Grammarly for Windows installs PER USER, into the profile of the account that runs its installer, and a Cimian client runs installers as SYSTEM, so the plain installer as an item gives the program to nobody. This folder therefore publishes a PACKED EXE (made by `GrammarlyPerUserPackager.py`, in this folder): run by the client as SYSTEM with no arguments, it stages the installer under `Program Files`, registers a scheduled task that runs at the sign-in of any user, as that user, and installs Grammarly into that person's profile when the person has none, writes an entry of the Windows uninstall list that the item's install check reads, and starts the task once for whoever is signed in. What ran: on 2026-11-16 a build of this folder ran under AutoPkg into a scratch repository, the packed EXE ran as SYSTEM on one Windows 11 test PC, the task started on demand gave Grammarly to that PC's one signed-in user (an administrator), and the removal worked (see "Results of 2026-11-16" below). That was the first build. The current form (it carries `install-user.ps1` and `remove.ps1` inside `install-machine.ps1`, checks the extraction folder and starts the task itself) also ran the same day: under AutoPkg into the scratch repository, and as SYSTEM on the same PC, where its own start of the task found Grammarly present for the same administrator (see "Results of 2026-11-16, for the current form"). **With the current form the per-user INSTALL path (a person without Grammarly) and the removal have not run**; they ran with the first build only. NOT established: a real sign-in starting the task; a standard user; a second user; a first sign-in with a new profile; an upgrade to a newer staged version; the failure counter; a non-zero exit code coming back through the stub; the item through the Cimian client (install, check, removal); Windows 10; a PC whose policy sets an execution policy, or with AppLocker or WDAC. What it means for the PCs: every person who signs in on a PC with this item gets Grammarly in their profile (about 85 MB each), so it suits PCs of one person and not shared ones, and not roaming profiles (the check key roams, the program does not); Grammarly updates itself in each profile, so the item's version is only the version of the staged installer, and the install check is the entry (and the task), not any person's Grammarly; the vendor's file changes about every two weeks, so each real run then publishes about 87 MB more, and a person decides how often to run it. The item must NOT go into a manifest until the steps of "What must be proven on a PC" below have been done. Read on 2026-11-13: `https://download-windows.grammarly.com/GrammarlyInstaller.exe` answered a HEAD request with 200, no redirect, `Content-Type` `application/octet-stream`, `Content-Length` 87044640 and a `Last-Modified` of the same day (the file changes often); the address holds no version. The vendor's support article "How to deploy Grammarly for Windows" (`support.grammarly.com/hc/en-us/articles/4422076438029`) was read in full on that day and links that same address as its installer; it gives the install command `GrammarlyInstaller.exe /S`, the uninstall command `GrammarlyInstaller.exe /S /uninstall`, the parameters `/ignore-os-version` (needed on Windows Server 2016 and 2019), `/do-not-create-desktop-shortcut` and `/disable-launch-at-startup` (the names are case-sensitive), the minimum of Windows 10 version 1903 with .NET Framework 4.7.2 and WebView2, per-user MSI packages beside the EXE, an Intune setting `Install behavior: User`, and a detection rule on the registry value `DisplayVersion` of the key `Grammarly Desktop Integrations` under `HKEY_CURRENT_USER` (an uninstall key of the user's own hive); a per-machine install is unavailable by default (the vendor's Customer Success Manager enables it for a subscription bought through the vendor's Sales team). No hash for the file was found. READ on 2026-11-16: Microsoft's Store catalog (`storeedgefd.dsx.mp.microsoft.com/v9.0/packageManifests/XPDDXX9QW8N9D7`) lists Grammarly as installer type `exe`, scope `user`, at `https://download-windows.grammarly.com/versions/<version>/net10/x64/w/GrammarlyInstaller.exe` (version `1.2.305(.1980)` that day) with the silent switch `/windows-store`: the Store product is the same per-user EXE, not an app package, so nothing can be provisioned for all users. When a run fails, STOP: nothing was written (a run that fails before the import writes nothing). Read the error, correct the recipe or the processor, and only then look at the trust information. Never accept new trust information first to make a failure go away.**

**Not verified. The download is NOT verified: the vendor publishes no hash that was found, and a check of the signature is not built; the packed EXE carries that unverified file, so it is NOT verified either. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `cimian_allow_unverified` (or `pcman_allow_unverified` for the package tool's recipe) to true. Do not set it before the signature check exists, or before a person has decided to accept an unverified download. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template grammarly --version <label>` (the file is the packed EXE; the label of an EXE: see "The label" below). The packed EXE in its current form has run once on one test PC, as SYSTEM; no person has received Grammarly through it. Do not put the item into a manifest before the steps of "What must be proven on a PC" have been done. The Windows overrides folder is not one of AutoPkg's override folders, so every override command here carries `--override-dir`: see the paragraph below.**

**Results of 2026-11-13, for the plain installer (before this folder packed it).** Under AutoPkg 2.9.0, into a scratch Cimian repository with a hand-made first pkginfo of the item (`make-override` with `--override-dir`, `verify-trust-info` OK, a dry run, a real run, a second real run): the real run published `grammarly-1.2.312(.2004).exe`, and the second run said that nothing is new. On one Windows 11 test PC, as SYSTEM from a scheduled task, `<file> /S` ended with exit code 0 after 48 seconds; the file's signature was valid (Grammarly, Inc.), and it has a version resource (`1.2.312(.2004)`). **It installed into the profile of the account that ran it** (the PC listed `Grammarly for Windows` `1.2.312(.2004)` under SYSTEM's own `AppData\Local\Grammarly\DesktopIntegrations`, nothing under `Program Files`), and a process that it started was still running fifteen minutes later, when the test ended it. That is why this folder packs the installer. None of those runs used the packer.

**Results of 2026-11-16, for the packed EXE, first build (then `install-user.ps1` and `remove.ps1` were files in the archive, there was no check of the extraction folder, and the task was not started by the install; its `install-user.ps1` differed from the current one only by lacking the two lines that skip the first-setup and Windows Sandbox accounts; `remove.ps1` is unchanged since).** Under AutoPkg 2.9.0, into a scratch Cimian repository: `make-override` with `--override-dir`, `verify-trust-info` OK, a dry run, a real run (with `cimian_allow_unverified` true in the scratch override) and a second real run. The download was `GrammarlyInstaller.exe` `1.2.313(.2008)`, 87169096 bytes; the packer built `GrammarlyPerUser-<version>.exe` of 87220102 bytes (the 87 MB installer is not cut into parts, and the stub unpacked it); `CimianImporter` published `grammarly` `1.2.313(.2008)`, warned that the download was not verified and that the pkginfo has no install check, and said at the second run that nothing is new. On one Windows 11 test PC the packed EXE, run as SYSTEM by a scheduled task with no arguments, ended with exit code 0 after 20 seconds, with no window and no child process left. The stub unpacked into a folder `7z<8 hex digits>` under `C:\Windows\TEMP` and ran `setup.bat`, which ran the 64-bit PowerShell through `Sysnative`. Afterwards: `C:\Program Files\Grammarly Deployment` held the installer (87169096 bytes), `install-user.ps1` and `remove.ps1`; `icacls` on the folder showed exactly SYSTEM full, Administrators full, Users read and execute, all `(OI)(CI)`, none inherited; the task `Grammarly per-user install` was Ready, with the group Users as principal, run level Limited and a logon trigger for any user (so `Register-ScheduledTask` accepted the group's SID); the uninstall entry `GrammarlyPerUserDeployment` was in the 64-bit view with DisplayName `Grammarly per-user deployment`, DisplayVersion `1.2.313(.2008)` and the PowerShell `remove.ps1` command as UninstallString. The task was then started ON DEMAND (`schtasks /run`), not by a sign-in: it ran in the session of the PC's one signed-in local user, a member of Administrators (NOT a standard user), in a disconnected session; about one minute later that user's hive had `Grammarly Desktop Integrations` with DisplayVersion `1.2.313(.2008)`, the user's `install.log` said `installed ... from the staged ... (installer: exit code 0)`, a process `Grammarly.Desktop` ran in that user's session, the task's last result was 0, and nothing was written into SYSTEM's profile. A second on-demand start logged `present (...): nothing to do`. What window flashed was not seen (nobody watched the screen). `remove.ps1`, run as SYSTEM through the same command as the UninstallString, ended with exit code 0 after 5 seconds; the folder, the task and the entry were gone; the user's Grammarly and log stayed.

**Results of 2026-11-16, for the packed EXE, current form.** Under AutoPkg 2.9.0 into the scratch repository again: the override, `verify-trust-info` OK, a dry run, a real run, a second run; the packer built `GrammarlyPerUser-<version>.exe` of 87224890 bytes (version `1.2.313(.2008)`); it was published, and the second run said that nothing is new. On the same Windows 11 test PC, as SYSTEM, no arguments: exit code 0 after 69 seconds. The extraction folder was `C:\Windows\TEMP\7z<8 hex digits>` and held only the three expected files, so check 48 passed. The folder held the installer (87169096 bytes), `install-user.ps1` (5114 bytes) and `remove.ps1` (2135 bytes), written from the embedded text; the same access list as before (SYSTEM full, Administrators full, Users read and execute, nothing inherited); the task Ready, group Users, Limited, logon trigger; the uninstall entry with `1.2.313(.2008)`. The EXE's own start of the task ran in the signed-in user's session (the same administrator account, which already had Grammarly from the first build's test): the log gained `present (...): nothing to do`, and the task's last result was 0. So with this form the per-user INSTALL path (a person without Grammarly) has not run, and neither has the removal. Everything in the NOT-established list of the status line stays.

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Grammarly-Win.download.recipe` | `com.github.serrc-techops.download.Grammarly-Win` | Downloads the Grammarly for Windows installer that the vendor serves at a fixed address (an EXE), reads its version from the file itself (`WindowsExeVersion`), and packs it with `GrammarlyPerUserPackager` (in this folder) into the self-extracting EXE in the recipe's cache. Its output `pathname` is the PACKED EXE, not the vendor's file. It has no hard check |
| `Grammarly.cimian.recipe` | `com.github.serrc-techops.cimian.Grammarly` | Parent: the download recipe. Hands the packed EXE and its label to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `Grammarly.pcman.recipe` | `com.github.serrc-techops.pcman.Grammarly` | Parent: the download recipe. Hands the packed EXE and its label to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `Grammarly.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `Grammarly.pcman.recipe` is the package tool's way, with `PcmanImporter`. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The steps of the download recipe are `URLDownloader`, `EndOfCheckPhase`, `WindowsExeVersion`
and `GrammarlyPerUserPackager`. `WindowsExeVersion` is a shared processor: it reads the
ProductVersion of the downloaded EXE and outputs it as `version`; the packer keeps that
`version` and replaces `pathname` with the packed EXE (another child recipe of this download
recipe, in a fork say, therefore gets the packed EXE too); the cimian recipe passes `version` as
`version`, and the pcman recipe as the package tool's `pcman_version`. How the processor
reads the file and which string it takes is in the README of `../Win-SharedProcessors/`.

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What the packed EXE does on a PC

The EXE is `7zS2con.sfx` of the LZMA SDK (public domain) followed by a 7z archive, built the
way `../Win-Microsoft365Apps/` builds Office's. That stub ends with the exit code of what it runs
by the Office folder's reading of the SDK's `C/Util/SfxSetup/SfxSetup.c`; only exit code 0 has
been seen through it (the Office folder's runs and the run of 2026-11-16), never a failure.
The archive holds three files: the vendor's `GrammarlyInstaller.exe`, `setup.bat` and
`install-machine.ps1`. `install-machine.ps1` carries `install-user.ps1` and `remove.ps1` inside
it (base64, each with its SHA-256). All four scripts are made by pure functions of
`GrammarlyPerUserPackager.py`, so the tests pin their text. ASCII only, for Windows PowerShell
5.1, with nothing beyond what Windows 10 version 1903 ships (the `ScheduledTasks` cmdlets).

1. The client runs the EXE as SYSTEM, with no arguments. The stub unpacks into a new folder
   under SYSTEM's temp folder and runs `setup.bat`, which makes `%SystemRoot%\System32` the
   current folder (not the extraction folder) and starts the 64-bit Windows PowerShell by its
   full path (the stub is a 32-bit program, so `setup.bat` takes `Sysnative` when it is there)
   with `install-machine.ps1`, also by its full path, and ends with its exit code.
2. `install-machine.ps1` first lists the extraction folder: anything but the three files stops
   the run (48). Then it checks that the unpacked installer has the SHA-256 that the packer
   wrote into it, makes `C:\Program Files\Grammarly Deployment` (from `$env:ProgramFiles` of
   the 64-bit PowerShell), sets its access list (owner Administrators; SYSTEM and Administrators
   full control, Users read and run, nothing inherited) and reads it back: any other account
   that may change the folder or a staged file stops the run.
3. It writes the installer (copied from the extraction folder) and `install-user.ps1` and
   `remove.ps1` (from its own text) into that folder, each beside its place, compares each with
   its SHA-256 and swaps it in (ten tries three seconds apart while a file is held), and
   compares the staged files once more.
4. It registers the task `Grammarly per-user install` (in the root of the Task Scheduler
   library): trigger at the sign-in of any user, 30 seconds late so that the session is up;
   principal the group Users by its SID `S-1-5-32-545`, least privilege, so that the task runs
   as the person who signed in, in that person's session, with that person's own rights; several
   people may run it at the same time; a run is stopped after 30 minutes. Its action is
   `powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File
   "<the folder>\install-user.ps1"` (PowerShell by its full path): the window is hidden, and a
   console may flash briefly. The script reads the task back and stops the run when it does not
   run as the group Users or not with least privilege.
5. It writes an entry of the Windows uninstall list,
   `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\GrammarlyPerUserDeployment`, with
   `DisplayName` `Grammarly per-user deployment`, `DisplayVersion` the staged installer's
   version (written last), and `UninstallString` and `QuietUninstallString` the command that
   runs the staged `remove.ps1`.
6. It starts the task once (`Start-ScheduledTask`), so that a person who is signed in gets
   Grammarly without signing out (on 2026-11-16 an on-demand start ran in the one signed-in
   user's session; with two people signed in it was not tried). A failure there, with nobody
   signed in say, is only written to the output: the task runs at the next sign-in anyway.

**The extraction folder, and what remains.** The stub chooses the folder: a new folder under
SYSTEM's temp folder, which on the Windows 11 test PC of 2026-11-16 is `C:\Windows\TEMP`. Read
there as SYSTEM: its access list gives Users `(CI)(S,WD,AD,X)`, and a folder that SYSTEM makes in
it inherits that entry, so a standard user may CREATE files and folders in the extraction folder
if they know or guess its name (they may not list `C:\Windows\TEMP`), but may not read, change or
replace a file that SYSTEM wrote there (such a file showed only Administrators and SYSTEM, full).
So nothing is taken from that folder by name unless it is checked: the installer by the SHA-256
written into `install-machine.ps1`; `setup.bat` and `install-machine.ps1`, written by the stub,
are run by their full paths, and no program is found through the current folder or by a bare
name. The two scripts that stay on the PC come from `install-machine.ps1` itself. The listing in
step 2 narrows what is left; it is NOT a proof (a file made and removed again in between is not
seen, and a user who creates `setup.bat` or `install-machine.ps1` before the stub writes it is
the stub's question, which was not read in `SfxSetup.c` for this folder).

`install-user.ps1`, at each sign-in, as the person: it does nothing for SYSTEM, the service
accounts and other built-in accounts (only an account whose SID begins `S-1-5-21-` or, for
Microsoft Entra, `S-1-12-1-`), nor for the accounts of the first setup (`defaultuser...`) and of
Windows Sandbox (`WDAGUtilityAccount`); it does nothing when the person's own hive has the uninstall key
`Grammarly Desktop Integrations` with a `DisplayVersion` (the vendor's detection rule), so it
never upgrades an install, because Grammarly updates itself; otherwise it copies the staged
installer into the person's temp folder, checks its SHA-256, runs it with `/S` and the
parameters of `GRAMMARLY_INSTALLER_ARGUMENTS`, waits up to 15 minutes for the installer itself
(not for the program it starts), and reads the key again: the key decides whether the run
succeeded, not the installer's exit code (which it logs). It writes one line per run to
`%LOCALAPPDATA%\GrammarlyPerUserDeployment\install.log`. After three failed runs with one
staged version it stops trying until another version is staged (the count is under
`HKCU\Software\GrammarlyPerUserDeployment`). It never elevates and never loops. A person who
removes Grammarly gets it again at the next sign-in. With a roaming profile the key roams and
the program (under `%LOCALAPPDATA%`) does not, so on a second PC the person would never get it:
not for roaming profiles.

`remove.ps1`, as SYSTEM or an administrator: it removes the task, the folder and the entry
(the entry last, only when the other two are gone) and ends with 0 only then. **Grammarly
stays in every profile that has it**; the vendor's `GrammarlyInstaller.exe /S /uninstall`, run
by each person, removes it there.

### What the EXE returns

| Code | Meaning |
| --- | --- |
| 0 | Staged, the task registered, the entry written (the start of the task may have failed: see the output) |
| 1 | The stub could not unpack, or PowerShell stopped on an error that the script did not catch |
| 40 | `%SystemRoot%\System32` could not be made the current folder |
| 41 | Not run as an administrator or SYSTEM |
| 42 | The folder could not be made, or its access list is not the one that was set |
| 43 | A file could not be staged, or the unpacked installer is not the one that was packed |
| 44 | The task could not be registered, or it is not the one that was asked for |
| 45 | The entry of the uninstall list could not be written |
| 46 | A 32-bit PowerShell on a 64-bit Windows |
| 48 | The extraction folder holds a file or folder that the EXE did not put there |

`remove.ps1` returns 0, 41, 46 or 47 (the task, the folder or the entry could not be removed).

### Races, as designed (NOT proven)

- A person who signs in while the EXE is still staging the first version: the task does not
  exist yet; the start of step 6 covers a person who is signed in by then, else that person gets
  Grammarly at the next sign-in.
- A person whose run copies the installer while a new version is being swapped in: the copy's
  SHA-256 is not the one that person's (old) script expects, so nothing runs and no failed
  attempt is counted; the next sign-in uses the new version. The swap waits for a copy that holds the file.
- Two sessions of one person: a lock file in the person's log folder lets one run go on.

## What must be proven on a PC

Done on 2026-11-16 (see the two "Results of 2026-11-16" paragraphs): step 1 with both builds,
on one PC as SYSTEM; parts of step 7 and the removal of step 8 with the first build only. The
per-user install path ran with the first build only, for an administrator, started on demand.

1. On a test PC with no Grammarly, run the packed EXE as SYSTEM from a scheduled task: exit
   code 0; the folder with three files and the access list above (`icacls`); the task with the
   group Users and least privilege (`schtasks /query /tn "Grammarly per-user install" /xml`);
   the entry with the version; the output line says whether the task was started.
2. A standard user signs in: within about a minute the key `Grammarly Desktop Integrations`
   appears under that user's `HKEY_CURRENT_USER` uninstall keys, Grammarly is in that profile,
   the log has one line `installed ...`, and no window stayed open (say what flashed).
3. The same user signs out and in again: one line `present (...)`, nothing installed.
4. A second standard user signs in, and a first sign-in with a new profile: Grammarly in those profiles too.
5. An administrator signs in: Grammarly installs without an elevation prompt.
6. The EXE again (the same version): exit 0, the task and the entry unchanged; then an EXE of
   a newer version: the staged installer replaced, the task kept, the entry's version new.
7. The task's run history shows no run as SYSTEM, and nothing was installed into SYSTEM's profile.
8. `remove.ps1` from the `UninstallString`: exit 0; task, folder and entry gone; the users'
   Grammarly still there.
9. The same through the Cimian client with the item's pkginfo: install, the next check says
   installed, uninstall through the pkginfo's `uninstaller`.
10. A failure comes back: an EXE whose installer does not match its hash (built by hand) must
    end with 43 through the stub, and an extra file in the extraction folder with 48.
11. The failure counter: three failed runs, then `not tried: 3 failed runs ...`.
12. Whether the vendor's installer runs at all from a standard user's sign-in with
    `/S` (it needs .NET Framework 4.7.2 and WebView2) and how long it takes; Windows 10.
13. Policy: a machine or user policy that sets the execution policy (`AllSigned`, say) wins
    over `-ExecutionPolicy Bypass`, so the setup and every per-user run fail; AppLocker's or
    WDAC's default rules block programs in a user's temp folder, where the per-user run starts
    the installer, so every per-user run fails while the item reports installed (only the
    per-user logs say why). Check the fleet's policies before the item goes into a manifest.

## What protects, and what does not

Nothing proves that the downloaded file is what the vendor published: there is no vendor
hash, and a signature check is not built. The shared importer knows this: no step of
the recipe sets `checksum_verified` with the hash of the file, so a real run is refused
before the package tool starts. What remains does not replace a verification.

- **The label.** An EXE has no version that the package tool can read for itself, so
  the recipe passes the label that `WindowsExeVersion` read from the downloaded installer. That is data
  in the file: it shows what the file claims, and proves nothing about where the file
  came from. The label must equal what a person reads in the file's properties (the
  Details tab of a Windows PC); the first dry run shows it.
- **The same product.** For an MSI the package tool refuses a different upgrade code.
  Whether it has an equivalent check for an EXE was NOT established by the writer. For
  this recipe the checks are the dry run and a person's look at what it plans.
- **Inside the EXE.** The packer writes the installer's SHA-256 into the scripts, and the
  scripts compare the unpacked, the staged and each person's copy with it. That proves that
  the PC runs the file the packer packed, nothing about where that file came from.

A file of another product, or with other content (a changed file of the vendor, or a
changed download on the way), could pass these checks. A `checksum_sha256` that a future
verification step leaves in the run is the hash of the downloaded installer, not of the packed
EXE: the importers then stop the run, and the packer would first have to carry the verification over.

## The label

The processor prints, when the run is verbose (`-v`), a line with the file's name, its
`ProductVersion`, its fixed version numbers and its `FileVersion`, and a second line,
`version is ..., taken from ...`. It takes the ProductVersion string when that is
numbers and dots only, else the four numbers of the fixed file information. Read both
lines at the first dry run and compare them with the file's properties on a Windows PC.
If the processor stops (no version resource, a file that is not a PE file), the run fails,
nothing is written, and the file is not what the recipe expects: read it before anything
else. The packer refuses a label that is not two to four numbers with dots.

## The label is the installer's version, and nothing compares it with the product's

**The label that the importers get is the `ProductVersion` of the downloaded setup file
(`GrammarlyInstaller.exe`), and not the version of the program that it installs. No step
of this recipe compares the two, and the recipe has no other version to compare it with: the
address has none, and the recipe reads no other page.** If the setup program stopped
tracking the product, the recipe would still publish under the setup file's number, and that
number orders the versions in the repository. The recipe does not check this at any run. A
person checks it, at the first dry run:

1. Run the dry run with `-v` (step c) and read the line `version is ..., taken from ...`
   of `WindowsExeVersion`.
2. Compare the label with the file's properties on a Windows PC (the Details tab): they
   must agree. On 2026-11-13 the file's version resource and the program's version agreed
   (`1.2.312(.2004)`); that was one file.
3. Compare the label with the version that the vendor gives for the current program (the vendor's release notes; the writer did not read them).
   The program updates itself, so the installed version may be newer than the file's soon
   after the first sign-in. If they do not agree by their numbers, stop and tell the owner before anything is published.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## What the build machine needs

- A 7z program (`7zz`, `7z` or `7za` in `/opt/homebrew/bin`, `/usr/local/bin` or `/usr/bin`; or
  the input `sevenzip_path` in the override). It unpacks the SDK and writes the archive.
- The SDK archive at `SFX_SDK_URL`, compared with `SFX_SDK_SHA256` (the same LZMA SDK 26.06 as
  the Microsoft 365 Apps folder's); a different file stops the run.
- About 200 MB in the recipe's cache: the download and the packed EXE of the current version
  (an EXE of another version is removed). A second run with the same installer and the same
  settings builds nothing.

## The inputs (set them in the override, never in the recipe)

| Input | Default | Meaning |
| --- | --- | --- |
| `GRAMMARLY_INSTALLER_ARGUMENTS` | empty | The vendor's parameters beside `/S`, separated by spaces or commas: `/do-not-create-desktop-shortcut`, `/disable-launch-at-startup`, `/ignore-os-version` (Windows Server 2016 and 2019). The names are case-sensitive; any other name stops the run. They are written into `install-user.ps1` |
| `SFX_SDK_URL`, `SFX_SDK_SHA256` | LZMA SDK 26.06 from the 7-Zip project's GitHub release | The archive that holds the stub, and its SHA-256 |

A changed input builds a new EXE of the same version; the importers then say "nothing new"
for a version the repository has. To publish a changed setting for the same version, remove
that version from the repository first, or wait for the vendor's next file.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `Grammarly.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

**Line numbers.** Two kinds. `StatusService.cs:194-219` and `:268-298` are from `windowsadmins/cimian` at commit `e10498b`, read on 2026-10-04 for another folder of this repository and not read again for this one. The lines about the `uninstaller` and `check.registry` below were read on 2026-11-16 in `windowsadmins/cimian` `main` at commit `6384299f` (2026-10-28), through a local clone of a branch that merges that `main`; the line numbers here are those of `6384299f`. That is the development branch, not a release: the client on a PC may be older or newer, and nothing here was checked against one.

**The download of this program is NOT verified** (see the status line above, which speaks of `pcman_allow_unverified` for the package tool's way). For this way the same rule holds with the input `cimian_allow_unverified`: `CimianImporter` REFUSES a real run of a download that no step verified (nothing is published) unless the override sets `cimian_allow_unverified` to true. Do not set it before a verification step exists, or before a person has decided to accept an unverified download. A dry run is allowed, and prints a `WARNING: the download was NOT verified` line.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **The version label** needs no program: the download recipe's step `WindowsExeVersion` reads it from the downloaded installer, and this recipe passes it on as `%version%`.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `grammarly`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. **An item `grammarly` made from the plain installer (the run of 2026-11-13 made one in a scratch repository) is NOT a template for the packed EXE: its arguments and check belong to the plain installer. Remove it, or give this item another name.** The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the first pkginfo (the template):** the recipe's `pkginfo` gives no arguments, no install check and no uninstaller. The packed EXE takes **no arguments** (it runs its own `setup.bat`): give none. Add an install check, because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`), and the uninstaller:

       check:
         registry:
           name: 'Grammarly per-user deployment'
           version: 'yes'
       uninstaller:
         - type: exe
           command: 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
           args: ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', '"C:\Program Files\Grammarly Deployment\remove.ps1"']

   What the client does with them, as read at `6384299f` (paths in the upstream repository):
   - `check.registry` (`cli/managedsoftwareupdate/Services/StatusService.cs:1628-1700`, `CheckRegistryStatus`): it looks through `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`, the 64-bit view first, then the 32-bit one, for the first entry whose `DisplayName` CONTAINS `name` (case-insensitive), and calls the item installed. When `check.registry.version` is not empty, it compares the ITEM's version with the entry's `DisplayVersion`, and an item version above it means "update available". So `version` is only a switch: any non-empty text turns the comparison on (`'yes'` above); a label written there is never compared and does not need updating. The entry's `DisplayVersion` is the staged installer's version, which is the item's, so a newer item version installs the new EXE, which writes the new version.
   - `uninstaller` (`cli/managedsoftwareupdate/Models/UpdateModels.cs:479`, a list of `UninstallerInfo`, `:960-1010`: `type`, `command`, `switches`, `flags`, `args`): the client takes the first entry (`Services/InstallerService.cs:723-735`); for `type: exe` it runs `command` with `subcommand`, `switches`, `flags` and `args` joined by spaces, without a shell (`InstallerService.cs:1574-1593`), so the quotes around the path with a space must be inside the `args` item, as above.
   - Without an `uninstaller` (and without `uninstall_script` or an MSI product code), an `exe` item is removed through the Windows uninstall list (`InstallerService.cs:1701-1745`, `ResolveRegistryUninstall`): the entry whose `DisplayName` equals the item's display name, else the first one that CONTAINS it, 64-bit view first, `QuietUninstallString` before `UninstallString`. With the display name `Grammarly` that could be ours or another machine-wide Grammarly product's entry, so give the `uninstaller` explicitly.

   The check reads the entry, not the task: a task that someone deleted by hand is not seen. The entry's `UninstallString` is the same command as the `uninstaller`. The run says in a WARNING that the pkginfo has no install check until the template has one.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i Grammarly-Win
    autopkg list-recipes | grep -i Grammarly.cimian

Each name must be listed once, from this repository. Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Grammarly.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `Grammarly.cimian`, not a path. It writes `<the Windows overrides folder>/Grammarly.cimian.recipe` with the identifier `local.cimian.Grammarly` and the trust information of the recipes and the processors (the packer among them). **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.Grammarly`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY`, `GRAMMARLY_INSTALLER_ARGUMENTS`, the two SDK inputs and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.Grammarly`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

The dry run downloads the installer and BUILDS the packed EXE (the packer runs before the importer; only the importer has a dry run). Expected (the lines that `CimianImporter` prints, read in its code and tests; NOT seen for this recipe; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. Before them the packer prints `Built GrammarlyPerUser-<version>.exe (<size> bytes), Grammarly <version>` (or `Nothing to build: ...` when the cache has it). The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

**The same installer packs to the same bytes (2026-11-18).** The packer names the packed files one by one in a fixed order and gives each a fixed time and mode, with no creation or access time, so two builds from one installer, one stub and the same scripts are one file with one SHA-256, on any day and in any cache folder. Before this, each build stored the moment the files were staged: a second cache folder (another override, a cleared cache) packed the same installer into a file with another SHA-256, and an importer that had the version already refused it as another installer. Seen on that day with the real installer and stub: two builds in two folders, two seconds apart, the same SHA-256. A version that was published from a build of the old form has the old bytes: publish it again once from the new form, or wait for the vendor's next version.

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on (NOT YET: see the status line)

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/Grammarly.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

**Not yet.** This download has no verification step, so `CimianImporter` refuses the real run below until the override also sets `cimian_allow_unverified` to true, which a person decides only after the file was checked by hand and the packed EXE was proven on a test PC, and which is then written in the override's `Input`, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_allow_unverified bool true' \
        <the Windows overrides folder>/Grammarly.cimian.recipe

With it the run prints `WARNING: published WITHOUT a verified download` and the report row says `published, NOT verified`.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published, NOT verified`. The repository now has the packed EXE under `pkgs/` (copied beside its place, checked against its SHA-256, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version.

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically. A change of `GrammarlyPerUserPackager.py` changes what every PC runs: read its scripts' diff before accepting it.

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `Grammarly.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `Grammarly.pcman`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool.

## a. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in
   AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   `make-override` (step b) takes a recipe NAME and refuses a path.

2. **The settings of the processor, as AutoPkg preferences.** One line each:

       defaults write com.github.autopkg pcman_root -string "<the package tool's folder>"
       defaults write com.github.autopkg pcman_python -string "<the package tool's Python>"

   `pcman_python` is only needed when it is not `<the package tool's folder>/.venv/bin/python3`.
   Write the values as strings. The repository is not a setting here: the package
   tool's own configuration says where it is. The repository must be reachable
   (the share mounted).

3. **The template item, made once by a first import of the PACKED EXE**, so that its
   pkginfo and installer are in the repository. The packed EXE is in the override's cache
   after a dry run (step c): `<the override's cache folder>/GrammarlyPerUser-<version>.exe`.
   If the package tool's repository has an item for Grammarly already, look at it first: an
   item of the kind `choco` is not the template, and neither is an item made from the plain
   installer (its arguments and check belong to that file); an item that an earlier run of
   this step made is, and this step is then not needed; set its name in the override (step b).
   The command, as a proposal that was NOT run:

       pcman import <the override's cache folder>/GrammarlyPerUser-<version>.exe --name grammarly \
           --version <the label that the first dry run prints> \
           --directory <the folder of the item> \
           --display-name "Grammarly" --category <the category of the item> --developer Grammarly \
           --description "<one line about the item>" \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   No install arguments: the packed EXE takes none (it runs its own `setup.bat`).
   `--architectures` is left out because the architecture of the vendor's installer was not
   read. Then, in the item file, the install check and the uninstaller, in the form the
   Microsoft 365 Apps item uses (`version` is only a switch for the client: see "What a person
   completes by hand" in the Cimian section, which also gives the `uninstaller` list that the
   pkginfo must end up with; whether the package tool writes these two keys into exactly that
   form was not read for this folder: look at the pkginfo it writes):

       check:
         registry:
           name: 'Grammarly per-user deployment'
           version: 'yes'
       uninstall_command: 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
       uninstall_arguments: '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "C:\Program Files\Grammarly Deployment\remove.ps1"'

   The check reads the entry that the packed EXE writes (its version is the staged
   installer's), not any person's Grammarly, which updates itself. A check on a per-user path
   is never true for another user, and a check by Grammarly's own version would fight the
   updater.
   The label after `--version` is the version of the installer as its properties show
   it. For an EXE the package tool is given it; here it is the same text that the recipe
   passes (see "The label").
   A person changes the template later; nothing else does. **If the template is made
   from the installer that is current at the vendor, the first run says "Nothing new"
   (see step c).**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Grammarly-Win
    autopkg list-recipes | grep -i Grammarly.pcman

Each name must be listed once, from this repository. Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Grammarly.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Grammarly.pcman`, not a path. Expected (not
run for this recipe): it writes `<the Windows overrides folder>/Grammarly.pcman.recipe`
with the identifier `local.pcman.Grammarly` and the trust information of the two
recipes and of the processors that are not part of AutoPkg itself
(`WindowsExeVersion`, `GrammarlyPerUserPackager`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Grammarly`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.Grammarly`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**`-v` prints what each processor says about its own work; `-vv` would add every processor's
inputs and outputs, `pcman_root` and the repository among them, to the log: keep such a log private.** Expected, from
the code and the rehearsals of the other folders, NOT seen for this recipe, when the
current version is not yet in the repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name          Version                   Catalogs    Result
    grammarly   <the label of the EXE>    Production  dry run, nothing written, NOT verified

Before that, the run prints the two lines of the version step (see "The label") and the
packer's `Built ...` line. The plan itself is not printed. The repository is unchanged.
If the current version is in the repository already (the template was made from it), the
line is `Nothing new: ... is in the repository already. Nothing was written.` instead.
That is correct.

## d. Switch a real run on (NOT YET: see the second paragraph at the top)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file. Nothing was published. Publish by hand after
    checking the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template grammarly --version <the label>

The file is the packed EXE from the override's cache. The label of an EXE is needed: the
package tool never takes it from the file (see "The label"). Then `pcman catalogs` (step e.3).

**Only after the signature check exists, or when a person has decided to accept an
unverified download:** the override allows it. Both lines are needed.

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Grammarly.pcman.recipe
    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_allow_unverified bool true' \
        <the Windows overrides folder>/Grammarly.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.pcman.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip). Do not use `-k`
instead: on the command line it applies to every recipe of that run. A run then prints
`WARNING: published WITHOUT a verified download ...` at any verbosity, and the report's
row says `published, NOT verified`.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.pcman.recipe

   Only after both lines of step d. Expected: `Published grammarly ...`, the warning
   `published WITHOUT a verified download`, and the table

       The following versions were published by the package tool:
       Name          Version                   Catalogs    Result
       grammarly   <the label of the EXE>    Production  published, NOT verified

   The repository then has the packed EXE under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions grammarly` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` (Not seen for this recipe. A new override gets a new cache folder, so its first run downloads the file again and builds the EXE again.)

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line (not seen for this recipe):

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- **Grammarly installs per user.** See the status line. The packed EXE is this folder's answer;
  the vendor's per-machine mode (by subscription) was not looked at.
- **Grammarly updates itself in each profile, so a hosted version sets a floor at best.** The
  vendor's article says the update happens about every two weeks. The staged installer is
  used only for a person who has no Grammarly yet, and then updates itself too. A newer
  version of the item replaces the staged installer; it changes nobody's Grammarly.
- **How often to run.** The vendor replaces the file at the same address about every two
  weeks; each new file is a new version of about 87 MB in the repository and on every server
  that mirrors it. Nothing is gained for the people who have Grammarly already; a person
  decides how often the recipe runs and removes old versions as the repository's rules allow.
- AutoPkg asks the server whether the file changed; whether this server answers that
  question is NOT established. If every run downloads the whole file, that is the reason. The
  packer builds again only when the installer's SHA-256 or a setting changed; the importers decide by
  the label.
- If the address answers "not found" or "access denied", the vendor moved the file. Read
  the vendor's article on deploying Grammarly for Windows in a browser, then correct the recipe.
- The downloader keeps the file under the name of the address, `GrammarlyInstaller.exe`.
  The cache therefore holds one download, replaced by each new one, and one packed EXE.
- The recipe's `NAME` is `Grammarly` and `PCMAN_TEMPLATE` is `grammarly`. Change
  the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) skips the download. The file is not
  checked at all; the version is still read from it, and it is packed.

## Tests

From the repository's root, no AutoPkg, no 7z and no network needed:

    python3 -m unittest discover -s Win-Grammarly/tests -t Win-Grammarly/tests

`tests/test_recipes.py` checks that the three files are property lists, that the Description of
every recipe and the top of this README say that the download is not verified, that a real run is
refused, what was rehearsed and what was not, the per-user caveat, that this README states no hash
of a download, that every argument is an input that the processors declare, the order of the steps,
that this README has no `make-override` without `--override-dir` and runs no recipe by its
identifier, and that nothing site-specific is in the folder; it also runs the cimian recipe's step
against a temporary Cimian repository (needs PyYAML; skipped without it).
`tests/test_packager.py` pins the scripts that the packer writes (the task's principal, the
per-user checks, the allowed parameters, the exit codes, ASCII only) and runs a build with the
network and 7z replaced, and tests the stub's checks (the SDK's SHA-256, the `MZ` member, the size
cap). The tests parse no PowerShell (a parse test runs only where `pwsh` is installed). On
2026-11-16 Windows PowerShell 5.1 ran `install-machine.ps1`, `install-user.ps1` and `remove.ps1`
of the first build, and `install-machine.ps1` and `install-user.ps1` (its "present" path only)
of the current form (see the top); `remove.ps1` and the install path of `install-user.ps1` have
not run in the current form.
