# Win-Grammarly

A Windows recipe pair: Grammarly for Windows, the `.exe` installer, with the version label read from the EXE itself.

**Status. Main caveat: by the vendor's own article Grammarly for Windows installs PER USER, into the profile of the account that runs the installer, and a per-machine install is unavailable by default (the article says the vendor's Customer Success Manager enables it for a subscription bought through the vendor's Sales team). A Cimian client runs installers as SYSTEM, so a plain `/S` item would install into the SYSTEM profile and no person would get the program, and an install check on a per-user path would never be true for the other users. Whether the per-machine mode makes this item usable through Cimian is NOT established. So the recipe can fetch and publish the file, but the item must NOT go into a manifest until a person has read the vendor's article, chosen the parameters and proven on a test PC that a signed-in standard user gets Grammarly after an install by SYSTEM. The program also updates itself (about every two weeks, by the article), so a published version is soon behind what the PCs run, and an install check by version would fight the updater: a check on presence, not on version, is the likely shape, and that is a person's decision. This recipe set is new and NOT rehearsed: nothing was run under AutoPkg, nothing was downloaded, nothing was imported into any repository and nothing was installed on a PC. Read on 2026-11-13: `https://download-windows.grammarly.com/GrammarlyInstaller.exe` answered a HEAD request with 200, no redirect, `Content-Type` `application/octet-stream`, `Content-Length` 87044640 and a `Last-Modified` of the same day (the file changes often); the address holds no version. The vendor's support article "How to deploy Grammarly for Windows" (`support.grammarly.com/hc/en-us/articles/4422076438029`) was read in full on that day and links that same address as its installer; it gives the install command `GrammarlyInstaller.exe /S`, the uninstall command `GrammarlyInstaller.exe /S /uninstall`, the parameters `/ignore-os-version` (needed on Windows Server 2016 and 2019), `/do-not-create-desktop-shortcut` and `/disable-launch-at-startup` (the names are case-sensitive), the minimum of Windows 10 version 1903 with .NET Framework 4.7.2 and WebView2, per-user MSI packages (`GrammarlyInstaller-perUser-x64.msi` and `-x86.msi`) beside the EXE, an Intune setting `Install behavior: User`, and a detection rule on the registry value `DisplayVersion` of the key `Grammarly Desktop Integrations` under `HKEY_CURRENT_USER` (an uninstall key of the user's own hive). No hash for the file was found. NOT established: that the file has a version resource (the file was not downloaded; `WindowsExeVersion` stops the run if it has none, and the first dry run shows it); the version that the installed program reports and whether it equals the file's; the architecture of the EXE; the publisher named in its signature (the developer in the recipe is the vendor's name, not read from the file); that `/S` installs silently on a test PC and where; that a per-machine install is possible for this organization; any install check; any install. When a run fails, STOP: nothing was written (a run that fails before the import writes nothing). Read the address in a browser and the file's properties on a Windows PC, correct the recipe, and only then look at the trust information. Never accept new trust information first to make a failure go away.**

**Not verified. The download is NOT verified: the vendor publishes no hash that was found, and a check of the signature is not built. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `cimian_allow_unverified` (or `pcman_allow_unverified` for the package tool's recipe) to true. Do not set it before the signature check exists. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template grammarly --version <label>` (the label of an EXE: see "The label" below). Nothing was run for this folder, and nothing has been installed on a PC. Do not put the item into a manifest before the test on the status line has been done. The Windows overrides folder is not one of AutoPkg's override folders, so every override command here carries `--override-dir`: see the paragraph below.**

**Results of 2026-11-13, newer than the status above; where the two differ, this paragraph holds.** Under AutoPkg 2.9.0, into a scratch Cimian repository with a hand-made first pkginfo of the item (`make-override` with `--override-dir`, `verify-trust-info` OK, a dry run, a real run, a second real run): the real run published `grammarly-1.2.312.2004.exe`, and the second run said that nothing is new. On one Windows 11 test PC, as SYSTEM from a scheduled task, `<file> /S` ended with exit code 0 after 48 seconds; the file's signature was valid (Grammarly, Inc.), and it has a version resource (`1.2.312.2004`). **It installed into the profile of the account that ran it** (the PC listed `Grammarly for Windows` `1.2.312.2004` under SYSTEM's own `AppData\Local\Grammarly\DesktopIntegrations`, nothing under `Program Files`), and a process that it started was still running fifteen minutes later, when the test ended it. Run by a management client as SYSTEM, this installer therefore does not give the program to the people who sign in. No per-machine way was looked for.

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Grammarly-Win.download.recipe` | `com.github.serrc-techops.download.Grammarly-Win` | Downloads the Grammarly for Windows installer that the vendor serves at a fixed address (an EXE), kept under the file name of the address, and reads its version from the file itself (`WindowsExeVersion`). It has no hard check |
| `Grammarly.cimian.recipe` | `com.github.serrc-techops.cimian.Grammarly` | Parent: the download recipe. Hands the file and its label to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `Grammarly.pcman.recipe` | `com.github.serrc-techops.pcman.Grammarly` | Parent: the download recipe. Hands the file and its label to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `Grammarly.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `Grammarly.pcman.recipe` is the package tool's way, with `PcmanImporter`. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The steps of the download recipe are `URLDownloader`, `EndOfCheckPhase` and then
`WindowsExeVersion`, which is a shared processor: it reads the ProductVersion of the
downloaded EXE and outputs it as `version`; the cimian recipe passes that as `version`, and the
pcman recipe as the package tool's `pcman_version`. How the processor reads the file and which string it
takes is in the README of `../Win-SharedProcessors/`.

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What protects, and what does not

Nothing proves that the downloaded file is what the vendor published: there is no vendor
hash, and a signature check is not built. The shared importer knows this: no step of
the recipe sets `checksum_verified` with the hash of the file, so a real run is refused
before the package tool starts. What remains does not replace a verification.

- **The label.** An EXE has no version that the package tool can read for itself, so
  the recipe passes the label that `WindowsExeVersion` read from the file. That is data
  in the file: it shows what the file claims, and proves nothing about where the file
  came from. The label must equal what a person reads in the file's properties (the
  Details tab of a Windows PC); the first dry run shows it.
- **The same product.** For an MSI the package tool refuses a different upgrade code.
  Whether it has an equivalent check for an EXE was NOT established by the writer. For
  this recipe the checks are the dry run and a person's look at what it plans.

A file of another product, or with other content (a changed file of the vendor, or a
changed download on the way), could pass these checks.

## The label

The processor prints, when the run is verbose (`-v`), a line with the file's name, its
`ProductVersion`, its fixed version numbers and its `FileVersion`, and a second line,
`version is ..., taken from ...`. It takes the ProductVersion string when that is
numbers and dots only, else the four numbers of the fixed file information. Read both
lines at the first dry run and compare them with the file's properties on a Windows PC.
If the processor stops (no version resource, a file that is not a PE file), the run fails,
nothing is written, and the file is not what the recipe expects: read it before anything
else.

## The label is the installer's version, and nothing compares it with the product's

**The label that the package tool gets is the `ProductVersion` of the downloaded setup file
(`GrammarlyInstaller.exe`), and not the version of the program that it installs. No step
of this recipe compares the two, and the recipe has no other version to compare it with: the
address has none, and the recipe reads no other page.** If the setup program stopped
tracking the product, the recipe would still publish under the setup file's number, and that
number orders the versions in the repository. The recipe does not check this at any run. A
person checks it, at the first dry run:

1. Run the dry run with `-v` (step c) and read the line `version is ..., taken from ...`
   of `WindowsExeVersion`. Nobody has seen it for this file: it was not downloaded.
2. Compare the label with the file's properties on a Windows PC (the Details tab): they
   must agree. Nobody has looked at the properties on a PC.
3. Compare the label with the version that the vendor gives for the current program (the vendor's release notes; the writer did not read them), and, after
   the first install on a test PC, with the version that the installed program shows. The program updates itself, so the installed version may be
   newer than the file's. If they do not agree by their numbers, stop and tell the owner before anything is published.
   Nobody has done that comparison.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `Grammarly.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `InstallerService.cs:936`) are from `windowsadmins/cimian` at commit `e10498b`, read on 2026-10-04 for another folder of this repository and not read again for this one nor checked against a later version.

**The download of this program is NOT verified** (see the status line above, which speaks of `pcman_allow_unverified` for the package tool's way). For this way the same rule holds with the input `cimian_allow_unverified`: `CimianImporter` REFUSES a real run of a download that no step verified (nothing is published) unless the override sets `cimian_allow_unverified` to true. Do not set it before a verification step exists. A dry run is allowed, and prints a `WARNING: the download was NOT verified` line.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **The version label** needs no program: the download recipe's step `WindowsExeVersion` reads it from the `.exe` itself, and this recipe passes it on as `%version%`.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `grammarly`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the first step of the package tool's way below marks what is only the writer's knowledge or was not read), so they are left for a person who has read them in the vendor's documentation and tried them on a test PC. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i Grammarly-Win
    autopkg list-recipes | grep -i Grammarly.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Grammarly.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `Grammarly.cimian`, not a path. It writes `<the Windows overrides folder>/Grammarly.cimian.recipe` with the identifier `local.cimian.Grammarly` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.Grammarly`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.Grammarly`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on (NOT YET: see the status line)

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/Grammarly.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

**Not yet.** This download has no verification step, so `CimianImporter` refuses the real run below until the override also sets `cimian_allow_unverified` to true, which a person decides only after the file was checked by hand, and which is then written in the override's `Input`, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_allow_unverified bool true' \
        <the Windows overrides folder>/Grammarly.cimian.recipe

With it the run prints `WARNING: published WITHOUT a verified download` and the report row says `published, NOT verified`.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

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

3. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. The template keeps the name of the item that
   it replaces. If the package tool's repository has an item for Grammarly
   already, look at it first: an item of the kind `choco` is not the template; an item that an earlier run of this step made is, and this step is then not needed; set its name in the override (step b).
   The command, as a proposal that was NOT run:

       pcman import <path of GrammarlyInstaller.exe> --name grammarly \
           --version <the label that the first dry run prints> \
           --directory <the folder of the item> \
           --install-arguments=/S \
           --display-name "Grammarly" --category <the category of the item> --developer Grammarly \
           --description "<one line about the item>" \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   The switch `/S` is from the vendor's article (read on 2026-11-13) and was NOT tested on a PC. By that article a plain `/S` install is a per-user install:
   run by SYSTEM it would not give the program to any person (see the status line), so a person decides the parameters after the test on the status line. `--architectures` is left out because the architecture of the EXE was not read (the file was not downloaded; the vendor's article offers x64 and x86 MSI packages beside it). `--install-path` is left out too: the program installs into the profile of the user, and a check on a per-user path is never true for another user. A check on presence, not on version, is the likely shape, because the program updates itself; that is a person's decision.
   The label after `--version` is the version of the installer as its properties show
   it. For an EXE the package tool is given it; here it is the same text that the recipe
   passes (see "The label").
   A person changes the template later; nothing else does. **If the template is made
   from the installer that is current at the vendor, the first run says "Nothing new"
   (see step c). To see a dry run that would publish, make the template from an older
   installer.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Grammarly-Win
    autopkg list-recipes | grep -i Grammarly.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Grammarly.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Grammarly.pcman`, not a path. Expected (not
run for this recipe): it writes `<the Windows overrides folder>/Grammarly.pcman.recipe`
with the identifier `local.pcman.Grammarly` and the trust information of the two
recipes and of the two processors that are not part of AutoPkg itself
(`WindowsExeVersion`, `PcmanImporter`). **Open the written file and read
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

Before that, the run prints the two lines of the processor (see "The label"). The plan
itself is not printed. The repository is unchanged. If the current version is in the
repository already (the template was made from it), the line is `Nothing new: ... is in
the repository already. Nothing was written.` instead. That is correct.

## d. Switch a real run on (NOT YET: see the second paragraph at the top)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file. Nothing was published. Publish by hand after
    checking the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template grammarly --version <the label>

The label of an EXE is needed: the package tool never takes it from the file (see "The
label"). Then `pcman catalogs` (step e.3).

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

   The repository then has the installer under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions grammarly` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Grammarly.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.` (Not seen for this recipe. A new override gets a new cache folder, so its first run downloads the file again.)

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
- **Grammarly installs per user.** See the status line. The vendor's article names an Intune setting that runs the installer as the user and a detection rule in the user's own registry hive; a Cimian client runs installers as SYSTEM and has no such setting that this README establishes. Whether the per-machine mode (which the article says is unavailable by default) changes this is NOT established.
- **Grammarly updates itself on the PCs, so a hosted version sets a floor at best.** The article says the update happens about every two weeks. A PC that has updated itself is
  newer than the version in the repository. What the Cimian client does with a PC that
  is newer than the hosted version is NOT established here, and an install check by version would fight the updater.
- The vendor replaces the file at the same address without a new address (the `Last-Modified` of the answer to the HEAD request was the day it was read, 2026-11-13). AutoPkg asks the server whether the
  file changed; whether this server answers that question is NOT established. If
  every run downloads the whole file, that is the reason. The package tool decides by
  the file's hash and the label.
- If the address answers "not found" or "access denied", the vendor moved the file. Read
  the vendor's article on deploying Grammarly for Windows in a browser, then correct the recipe.
- The file is about 87 MB (87044640 bytes in the HEAD answer of 2026-11-13). The copy to the share is
  the slowest step. The processor waits 30 minutes by default (`pcman_timeout`).
- The downloader keeps the file under the name of the address, `GrammarlyInstaller.exe`.
  The cache therefore holds one file, replaced by each new download.
- Whether the EXE's own ProductVersion is the number that the vendor calls the
  version of the program is NOT established. The first dry run shows what the file says.
- The recipe's `NAME` is `Grammarly` and `PCMAN_TEMPLATE` is `grammarly`. Change
  the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) skips the download. The file is not
  checked at all; the version is still read from it.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that the Description of both recipes
and the top of this README say that the download is not verified, that a real run is
refused, and that nothing was rehearsed and what was fetched, that this README states no
hash, that every argument is an input that the shared processors declare, that the
version step comes after the end of the check phase and the cimian recipe passes its
output as the label, that this README has no `make-override` without `--override-dir`
and runs no recipe by its identifier, and that nothing site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
