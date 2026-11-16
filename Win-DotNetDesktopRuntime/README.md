# Win-DotNetDesktopRuntime

A Windows recipe pair: Microsoft's .NET Desktop Runtime, the installer EXE (x64 by default), the newest release of one channel (10.0 by default). It exists because other programs need it: HandBrake's Windows GUI names ".NET Desktop Runtime version 10.0" in its release notes (see `../Win-HandBrake/README.md`), and its item gets a `requires` on the item that this recipe makes.

**Status. New. On 2026-11-16 the Cimian way ran under AutoPkg 2.9.0 once, and the installer was tried once on one PC; the package tool's way (pcman) was NOT run. READ on 2026-11-16 by the writers: (1) `https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json` answered 200 with JSON of about 1.2 MB, no redirect was seen; (2) its top level has `channel-version` (`10.0`), `latest-release` (`10.0.15`), `latest-release-date`, `latest-runtime`, `support-phase` (`active`), `release-type` (`lts`), `eol-date` (`2028-11-14`), a `signature` entry that names a detached file `releases.json.<stamp>.p7s`, and `releases`, a list of 25 releases, the newest first; (3) each release has `release-version`, `release-date`, `security` and `windowsdesktop`: `{version, version-display, files: [{name, rid, url, hash}]}`; the file names are `windowsdesktop-runtime-win-x64.exe`, `-win-x86.exe`, `-win-arm64.exe` and the `.zip` forms; `rid` is `win-x64` and so on; the `url` of the x64 installer of `10.0.15` is `https://builds.dotnet.microsoft.com/dotnet/WindowsDesktop/10.0.15/windowsdesktop-runtime-10.0.15-win-x64.exe`; the `hash` is 128 hex digits (a SHA-512), and the metadata has no SHA-256; (4) HandBrake `1.11.2`'s own release notes (GitHub release of the tag `1.11.2`) name .NET Desktop Runtime 10.0 and link `https://aka.ms/dotnet/10.0/windowsdesktop-runtime-win-x64.exe` (and an arm64 one). **What ran, on 2026-11-16:** under AutoPkg 2.9.0, into a scratch Cimian repository that had no item of this name: `make-override` with `--override-dir`, `verify-trust-info` OK, a dry run, a real run that published `dotnet-desktop-runtime` `10.0.15` (the file `windowsdesktop-runtime-10.0.15-win-x64.exe`, 60066584 bytes, its SHA-512 from the metadata verified), and a second real run that said nothing is new; the importer warned that the pkginfo has no install check (expected: a person completes it). On one Windows 11 test PC, as SYSTEM from a scheduled task, `<file> /install /quiet /norestart` ended with exit code 0 after 33 seconds, with no window and no child process left. The PC's uninstall list gained the bundle's own entry `Microsoft Windows Desktop Runtime 10.0.15 (x64)` in the 32-bit view of the registry (WOW6432Node), with DisplayVersion `10.0.15(.50000)` and a QuietUninstallString of the form `"C:\ProgramData\Package Cache\{<guid>}\windowsdesktop-runtime-10.0.15-win-x64.exe" /uninstall /quiet`, and four MSI entries in the 64-bit view (`Microsoft Windows Desktop Runtime - 10.0.15 (x64)`, `Microsoft .NET Runtime - 10.0.15 (x64)`, `Microsoft .NET Host - 10.0.15 (x64)`, `Microsoft .NET Host FX Resolver - 10.0.15 (x64)`), each with DisplayVersion `80.60.61788`. Afterwards the folders `C:\Program Files\dotnet\shared\Microsoft.WindowsDesktop.App\10.0.15` and `C:\Program Files\dotnet\shared\Microsoft.NETCore.App\10.0.15` existed. HandBrake `1.11.2` (installed earlier on that PC; it had never been started before the runtime), started as SYSTEM after the runtime was there, was still running after 40 seconds and no dialog window was seen; that is weak evidence only (no window of it would be seen in session 0 either): it does not show that HandBrake works. NOT established: an upgrade from an older `10.0.x` (whether the old one leaves); the uninstall (its string was read, not run); an install through the Cimian client; the right install check; Windows 10, x86 and ARM; the installer's signature (not looked at in the test); the metadata's detached signature (not checked); any run of the package tool's way. The hash lines in the tests are made up. When a run fails, STOP: nothing was written. Read the real metadata, correct the processor or the recipe, and never accept new trust information first.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `DotNetDesktopRuntime-Win.download.recipe` | `com.github.serrc-techops.download.DotNetDesktopRuntime-Win` | Reads the release metadata of the channel, downloads the latest release's Windows Desktop Runtime installer, and stops when the file does not match the SHA-512 that the metadata gives for it |
| `DotNetDesktopRuntime.cimian.recipe` | `com.github.serrc-techops.cimian.DotNetDesktopRuntime` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository, or says that nothing is new |
| `DotNetDesktopRuntime.pcman.recipe` | `com.github.serrc-techops.pcman.DotNetDesktopRuntime` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `DotNetDesktopRuntime.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `DotNetDesktopRuntime.pcman.recipe` is the package tool's way, with `PcmanImporter`. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

## The processors of this folder

`DotNetDesktopRuntimeInfoProvider.py` has three inputs, all in the download recipe's `Input` (an override changes them): `dotnet_channel` (default `10.0`; two numbers joined by a dot, checked strictly), `dotnet_rid` (default `win-x64`; `win-x64`, `win-x86` or `win-arm64`) and `dotnet_allow_eol` (default false). It reads `https://builds.dotnet.microsoft.com/dotnet/release-metadata/<channel>/releases.json` and takes the release whose `release-version` equals the metadata's `latest-release` (the first release of the list is not assumed to be it). It refuses, and sets no output:

- a metadata whose `channel-version` is not the channel asked for;
- a `latest-release` or a `windowsdesktop` version that is not three plain numbers of the channel: a preview or release candidate (`-rc.`, `-preview.`) is refused;
- a channel whose `support-phase` is not `active` or `maintenance`; `eol` is refused unless the override sets `dotnet_allow_eol` to true, and `preview`, `go-live` and anything else are refused;
- a latest release that is missing or listed twice, that has no `windowsdesktop` files, or that has no `.exe` file for the RID (or lists it twice);
- a file whose `rid` is not the one asked for, whose address is not `https://builds.dotnet.microsoft.com/dotnet/WindowsDesktop/<version>/windowsdesktop-runtime-<version>-<rid>.exe`, or whose `hash` is not 128 hex digits.

It outputs `url`, `version` (three numbers, such as `10.0.15`), `expected_sha512`, `filename` and `dotnet_release_date`. The fetch goes to `builds.dotnet.microsoft.com` over https, follows no redirect (a redirect is an error), has a limit of 16 MiB and a time limit of 120 seconds.

`Sha512ChecksumVerifier.py` hashes the downloaded file with SHA-512 and compares it with `expected_sha512` (128 hex digits, with or without the prefix `sha512:`). **Why a second verifier exists:** the shared `ChecksumVerifier` takes a SHA-256 only, and Microsoft's metadata gives a SHA-512 only. The shared processor is not changed: every existing override has trust information for its text, and a change would break them all. On a match the new processor sets exactly the two outputs that `CimianImporter` and `PcmanImporter` read from the shared one: `checksum_verified` (the boolean true) and `checksum_sha256` (the SHA-256 of the file, computed in the same pass). Each importer hashes the file it imports again and refuses it when that is not `checksum_sha256`, so a file other than the verified one is refused. On a mismatch, a malformed value or an unreadable file it stops the run and sets neither output, and the importers refuse an unverified download.

The other processors are in `../Win-SharedProcessors/` (see its README). Neither recipe stops on an unchanged download, so an import that failed is tried again at the next run. `URLDownloader` keeps the file under the provider's `filename` output (`windowsdesktop-runtime-<version>-<rid>.exe`).

Below, `pcman` stands for `<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What protects, and what does not

- **The hash.** The SHA-512 comes from the vendor's own metadata, fetched from `builds.dotnet.microsoft.com` without a redirect. It is the vendor's word, but it is in another file than the installer (the installer is downloaded by `URLDownloader`, which follows what the server answers). The check shows that the installer is the file that the metadata names, undamaged. It does not show who wrote the metadata.
- **The signature of the metadata.** The metadata names a detached signature (`releases.json.<stamp>.p7s`). **It is NOT checked.** A check of it would need the signature file and a trust decision about its chain; it is not built.
- **The signature of the installer.** Whether the EXE carries an Authenticode signature was not looked at in the test on a PC and was not read; it is not checked.
- **The same product.** `CimianImporter` compares only the upgrade code of an MSI, and whether the package tool has an equivalent check for an EXE was NOT established. For this recipe the checks are the hash, the dry run and a person's look at what the dry run plans.
- **The label.** An EXE has no version that the importers read for themselves, so the recipe passes `version`, the runtime's version of three numbers (`10.0.15`). The first number is below 20, so the Cimian client does not read the label as a build date (the shared README's section "Three-part labels" has the two rules; read there on 2026-11-16: the first rule needs a first part from 20 to 99, the second a first part of four digits). The release number is the label because the metadata gives it, and the file has no version resource that was read; `WindowsExeVersion` was not chosen. What the PC reports differs from the label, and from entry to entry: the bundle's own uninstall entry has DisplayVersion `10.0.15(.50000)`, and the four MSI entries have `80.60.61788` (see the Status). A check that names a version must say which entry it reads; **nobody should check the MSI entries against `10.0.15`.**

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## What a person completes by hand in the pkginfo

This recipe's `pkginfo` gives only the display name and the developer. For an `.exe` a person completes, in the override's `pkginfo` or in the template item, after reading Microsoft's documentation and trying it on a test PC:

- the silent arguments: `installer: {args: [...]}`. `/install /quiet /norestart` is what Microsoft documents for the runtime bundle, and on 2026-11-16 it ended with exit code 0 after 33 seconds on one Windows 11 test PC (as SYSTEM, from a scheduled task, no window, no child process left). It was not run through the Cimian client, and not on Windows 10, x86 or ARM;
- an install check (`installs`, or `check`): without one the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (the importer warns about this). **NOT established which check is right.** Two candidates, for a person to try: the folder or file under `C:\Program Files\dotnet\shared\Microsoft.WindowsDesktop.App\<version>` (it existed afterwards), or the bundle's own uninstall entry by name (`Microsoft Windows Desktop Runtime <version> (x64)`, 32-bit view) and its version `10.0.15(.50000)`. The four MSI entries report `80.60.61788`: do not compare them with the item's version;
- the uninstall: the bundle's entry has a QuietUninstallString of the form `"C:\ProgramData\Package Cache\{<guid>}\windowsdesktop-runtime-<version>-win-x64.exe" /uninstall /quiet`. It was read, **not run**; the path has a GUID that changes with the release, so a fixed uninstall command is NOT established;
- what a newer `10.0.x` does to the older one: NOT established (no upgrade was tried). If both stay on a PC, the item's check must be written for that.

**HandBrake's item gets a `requires` on this item** (`requires: [dotnet-desktop-runtime]` in the template item of HandBrake, by hand: see `../Win-HandBrake/README.md`, "The .NET Desktop Runtime"). A program that needs another major version of .NET gets its own item: run this recipe with an override whose `dotnet_channel` is that channel, under another `CIMIAN_NAME` (`dotnet-desktop-runtime-<major>`) so that the two do not share one item.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `DotNetDesktopRuntime.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted; `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`.

3. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `dotnet-desktop-runtime`. If the repository has an item of that name, its newest pkginfo is the template and its arguments and checks are carried into the new version. If it has none, the first run builds the pkginfo from the inputs and says so; a person then completes it as above before any PC gets the item.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i DotNetDesktopRuntime-Win
    autopkg list-recipes | grep -i DotNetDesktopRuntime.cimian

Each name must be listed once, from this repository. (The lines of the output are not quoted here.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> DotNetDesktopRuntime.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, not a path. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.DotNetDesktopRuntime`.** Another value means that AutoPkg found another recipe of the same name.

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/DotNetDesktopRuntime.cimian.recipe

**Why by path:** the recipe's name or identifier runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected (from the importer's code; this README does not quote the output of the run of 2026-11-16): `WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on.`, then `Would write dotnet-desktop-runtime <version>: ...`, or `Nothing new: ...` when the repository has the version. With `-v` the run also prints the channel, the release, the file name and the SHA-512 of the metadata.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/DotNetDesktopRuntime.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/DotNetDesktopRuntime.cimian.recipe

Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/DotNetDesktopRuntime.cimian.recipe

   Expected: `Published dotnet-desktop-runtime <version> (...)`. Neither file replaces another: a file that is there already stops the run.

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/DotNetDesktopRuntime.cimian.recipe

   Expected: `Nothing new: ...`.

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/DotNetDesktopRuntime.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/DotNetDesktopRuntime.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `DotNetDesktopRuntime.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool, `dotnet-desktop-runtime`.

## a. What must exist first

1. **The recipe repository is added to AutoPkg:** `autopkg repo-add <the URL of the recipe repository>`.
2. **The settings of the processor, as AutoPkg preferences:**

       defaults write com.github.autopkg pcman_root -string "<the package tool's folder>"
       defaults write com.github.autopkg pcman_python -string "<the package tool's Python>"

3. **The template item, made once by a first import** of a real installer of an older release than the metadata's newest (this way was NOT run). The silent switches below were tried once on one test PC on 2026-11-16 (exit code 0, see the Status); the rest of the command is NOT tested:

       pcman import <path of windowsdesktop-runtime-<older version>-win-x64.exe> --name dotnet-desktop-runtime --version <older version> \
           --directory <the folder of the item> \
           --install-arguments '/install /quiet /norestart' \
           --architectures x64 \
           --display-name '.NET Desktop Runtime' --category <the category of the item> --developer Microsoft \
           --description <one sentence about the item> --icon <the file name of an icon that the repository has> --no-prompt --build

   The label after `--version` is the runtime's version of three numbers, the same text that the recipe passes. The install check and the uninstall are NOT established and are completed by a person.

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

    autopkg list-recipes | grep -i DotNetDesktopRuntime.pcman
    autopkg make-override --override-dir=<the Windows overrides folder> DotNetDesktopRuntime.pcman

Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.pcman.DotNetDesktopRuntime`.

## c. First try: a dry run

    autopkg run -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/DotNetDesktopRuntime.pcman.recipe

**`-vv` prints `pcman_root` and the repository: keep this log private.** Expected (this way was NOT run): a dry-run table with the result `dry run, nothing written`, or `Nothing new: ...` when the repository has the version.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/DotNetDesktopRuntime.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/DotNetDesktopRuntime.pcman.recipe

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/DotNetDesktopRuntime.pcman.recipe

2. `pcman versions dotnet-desktop-runtime` lists the template and the new version.
3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new version.
4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/DotNetDesktopRuntime.pcman.recipe

   Expected: `Nothing new: ...`.

## f. When a recipe or a processor changes upstream

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/DotNetDesktopRuntime.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/DotNetDesktopRuntime.pcman.recipe

Look at what changed first; never accept it automatically.

## g. A share that is not mounted

The package tool stops with `the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?` and writes nothing. Mount the share, then run again. (Not run with this recipe.)

## Other facts

- The download recipe takes the latest release of one channel. A new major channel (`11.0`) is a person's decision: the install check, the switches and the programs that need it may change.
- The checksum step sets `checksum_verified` and `checksum_sha256`, so a real run needs neither `pcman_allow_unverified` nor `cimian_allow_unverified`.
- The recipe's `NAME` is `DotNetDesktopRuntime`; `CIMIAN_NAME` and `PCMAN_TEMPLATE` are `dotnet-desktop-runtime`. Change the item's name in the override's `Input`, not in the recipe.
- `-p` (a local file instead of the download) fails the checksum unless the file is the one that the metadata names.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the provider handles the metadata (an excerpt made from the structure above with invented hash digits: a good release, every refusal), that the SHA-512 verifier accepts a match and refuses a mismatch and a malformed value, that the three recipes are property lists whose arguments are inputs that the processors declare, that the chain with each real importer counts as verified and refuses another file, and that this README has no `make-override` without `--override-dir`, runs no recipe by its identifier and says what was NOT done, and that nothing site-specific is in the folder.
