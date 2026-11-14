# Win-OBSStudio

A Windows recipe pair: OBS Studio, the public Windows x64 `.exe` installer from the project's GitHub releases, with the version label taken from the file's name.

**Status. New, and not rehearsed: nothing has run under AutoPkg for this program, no file was downloaded, and nothing was installed on a PC (read on 2026-11-13).** What was read: GitHub's public release list of `obsproject/obs-studio` (`https://api.github.com/repos/obsproject/obs-studio/releases`), the newest 30 releases (published 2025-09-19 to 2026-10-29), saved as names, sizes and digest flags in `tests/releases_excerpt.json` (the Windows files only). The newest release that is not a pre-release is `33.0.1` (published 2026-10-29); its installer is `OBS-Studio-33.0.1-Windows-x64-Installer.exe`, 186662440 bytes. The tags are bare versions (no leading `v`). GitHub flags the betas and release candidates as pre-releases: 17 of the 30 releases, and 13 are not. All 30 releases name the installer in one spelling, `OBS-Studio-<version>-Windows-x64-Installer.exe`, and the pattern `OBS-Studio-([0-9]+(?:\.[0-9]+)+)-Windows-x64-Installer\.exe$` (its one group is the label) takes exactly one file in each of the 13 releases that are not pre-releases and none in the 17 pre-releases, because a name such as `OBS-Studio-33.0.0-rc3-Windows-x64-Installer.exe` has `-rc3` where the pattern wants `-Windows`. In each of the 13 releases that are not pre-releases the version in the installer's name is the release's tag. The label is still taken from the name and not from the tag, as a precaution (the tag belongs to the release, not to the file). GitHub records a digest for the installer of every one of the 30 releases. Each release also has a Windows x64 `.zip`, a Windows arm64 `.zip` and two `.zip` files of debug symbols (PDBs); the pattern takes none of them, and the list has no arm64 installer (only a `.zip`; what is inside it was not opened). NOT read: releases older than the 30 of the list (they may use another spelling of the name, and AutoPkg would then go back to them: see "Other facts"); whether an arm64 installer exists anywhere; whether the installer has a version resource (no file was downloaded, so `WindowsExeVersion` is not used and was not tried); the silent switch (see step a.3); the install path and the architecture of the installed program; the version that the installed program reports about itself; how the program's own updater behaves for a standard user (see "Other facts"). The selection of the file is tested on the saved list with the rule of AutoPkg 2.9.0 as the shared test helper writes it down (`_win_support.provider_select`); that rule was not read again from AutoPkg's source for this folder, and the recipe itself was not run. Nothing is established about the first dry run: read it as the steps below say.**

**Results of 2026-11-13, newer than the status above; where the two differ, this paragraph holds.** Under AutoPkg 2.9.0, into a scratch Cimian repository with a hand-made first pkginfo of the item (`make-override` with `--override-dir`, `verify-trust-info` OK, a dry run, a real run, a second real run): the real run published `obs-studio-33.0.1.exe`, and the second run said that nothing is new. On one Windows 11 test PC, as SYSTEM from a scheduled task, `<file> /S` ended with exit code 0 after 75 seconds; the file's signature was valid (OBS Project, LLC); the PC then listed `OBS Studio` with DisplayVersion `33.0.1` (in the 32-bit view of the registry), installed in `C:\Program Files\obs-studio`, uninstall string `"C:\Program Files\obs-studio\uninstall.exe" /S`. It also made `C:\ProgramData\obs-studio-hook`, and two processes that the installer started were still running when it ended (not identified). The program was not started, an upgrade over an older version and the uninstall were not tested, and no Cimian client installed it.

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `OBSStudio-Win.download.recipe` | `com.github.serrc-techops.download.OBSStudio-Win` | Takes the newest non-pre-release of `obsproject/obs-studio` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match. Last, takes the version label from the file's name (`VersionFromName`: the one group of `SEARCH_PATTERN`, checked for its shape) and sets `version` to it |
| `OBSStudio.cimian.recipe` | `com.github.serrc-techops.cimian.OBSStudio` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new. It passes the version label that the download recipe took from the file's name (`%version%`) |
| `OBSStudio.pcman.recipe` | `com.github.serrc-techops.pcman.OBSStudio` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new. It passes the version label that the download recipe took from the file's name (`%version%`) |

**Three recipes.** The download recipe is the parent of both of the others. `OBSStudio.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `OBSStudio.pcman.recipe` is the package tool's way, with `PcmanImporter`. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/OBSStudio.cimian.recipe

(An override made without this key needs `Add :Input:include_prereleases bool true` instead of `Set`.) Keep it a boolean: AutoPkg only
tests whether the value is empty, so the text `false` would count as true. The recipe's
step does not set it, because AutoPkg applies the arguments of a step after the
override's `Input`, and they would beat it.

**This recipe's pattern takes no pre-release name.** The pattern wants `-Windows` right after the version, and the names of the release candidates and betas have `-rc` or `-beta` there. So the switch alone does not bring one of them: with it on, the run still takes the newest release that has a name that the pattern takes (today `33.0.1`), and `GitHubNewestReleaseGuard` stops the run when a newer pre-release is on top of the list. To follow pre-releases a person must also change `SEARCH_PATTERN` in the override. Neither was tried under AutoPkg.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## The version label

The installer is an `.exe`, so the recipes pass the label on: the pcman recipe to the package tool
(`pcman_version` is `%version%`), the cimian recipe to `CimianImporter` (`version` is `%version%`); neither tool reads a version from an EXE. Whether this installer has a version
resource of its own is NOT established (no file was downloaded), so the recipe does not read one: no step is `WindowsExeVersion`. The label is the version in the file's name. AutoPkg makes `version` from the
release tag first, and the last step of the download recipe, `VersionFromName` (shared, see its
section in the shared README), matches the downloaded file's name with `SEARCH_PATTERN`, whose
one group is the label, checks that the group is two to four numbers joined by dots, and
overwrites `version` with it. The tag is not the source: it belongs to the release and not to the
file. In the 13 releases of the saved list that are not pre-releases the version in the installer's name is the release's tag (a test
checks it on the saved list), so today the two agree.

**What the label is not.** It is not the file's own version (unread) and it is not what the installed
program says about itself: that is NOT established, because nobody has installed the program. The
project sets the number in the name, and the label is only as good as that word.

Two questions are open:

- **Does the package tool accept the label?** A label of three numbers with no leading zero, such as the one of the newest release, is
  the common shape; the package tool's answer to it for this program has NOT been seen. (The importer of the way for any Cimian repository takes a label that has a digit first and
  letters, numbers, dots, underscores and hyphens only; that rule is the model folder's README's statement and was not re-read here.)
- **Does the Cimian client order that label as the program's own version?** The model folder's README describes two rules of the client that read a
  label as a build time (`VersionService.TryParseCalendarBuildStamp`, which needs a first part that is a year of four digits, and `CatalogService.ExpandBuildTimestamp`, which reads a label of
  exactly three parts, `yy.M.ddHH`, with `yy` from 20 to 99, a month from 1 to 12 and a third part of three or four digits). A label of this program has three parts and a first part from 32 to 33, so the
  first rule does not apply. By the second rule as described there, the label of `33.0.1` is not a build time (its third part has one digit, and its month is 0), and neither is any label of
  the saved list. That was worked out from the model README's description, NOT from the client's code, which was not read for this folder. What the program itself shows has still to be compared with the label, on a PC after
  a hand install (its About box, or Apps & features). If the numbers differ, stop and tell the owner: a label that the
  client orders wrongly would hide a newer version or offer an older one.

The first dry run (with `-v`) prints the lines of the provider that name the selected asset and
release (`Selected asset ... from release ...`) and one line from the label step: `version is ...,
taken from the file name ...`. **Read them first**: the selected release must be the newest that
is not a pre-release.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `OBSStudio.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `InstallerService.cs:936`) are copied from the README of the model folder (`../Win-BambuStudio/`), where they are given as from `windowsadmins/cimian` at commit `e10498b`; they were not read again for this folder and not checked against a later version.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **The version label** needs no program: the download recipe's step `VersionFromName` takes it from the installer's file name, and this recipe passes it on as `%version%`.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `obs-studio`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the first step of the package tool's way below marks what is only the writer's knowledge or was not read), so they are left for a person who has read them in the vendor's documentation and tried them on a test PC. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i OBSStudio-Win
    autopkg list-recipes | grep -i OBSStudio.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> OBSStudio.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `OBSStudio.cimian`, not a path. It writes `<the Windows overrides folder>/OBSStudio.cimian.recipe` with the identifier `local.cimian.OBSStudio` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.OBSStudio`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the lines of the provider and of the label step are printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OBSStudio.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.OBSStudio`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/OBSStudio.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OBSStudio.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OBSStudio.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OBSStudio.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OBSStudio.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OBSStudio.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `OBSStudio.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `OBSStudio.pcman`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool.

## a. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in
   AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step b) takes a recipe NAME and refuses
   a path.

2. **The settings of the processor, as AutoPkg preferences.** One line each:

       defaults write com.github.autopkg pcman_root -string "<the package tool's folder>"
       defaults write com.github.autopkg pcman_python -string "<the package tool's Python>"

   `pcman_python` is only needed when it is not `<the package tool's folder>/.venv/bin/python3`.
   Write the values as strings. The repository is not a setting here: the package
   tool's own configuration says where it is. The repository must be reachable
   (the share mounted).

3. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. The command, with a real installer that a person has
   downloaded and checked (**not run: the command has not been tried on this program**):

       pcman import <path of the installer> --name obs-studio --version <label> \
           --display-name "OBS Studio" --category <the category> \
           --developer "OBS Project" --description "<the description>" \
           --directory <the folder of the item> \
           --install-arguments /S --architectures x64 \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   `--version <label>` is for an EXE only, and the label is the one that step c will
   show (see "The version label"). **The silent switch is NOT established.** The writer
   believes the installer is an NSIS installer and that `/S` is its silent switch; that
   was NOT read from the vendor, the installer was not downloaded or opened, and nothing was
   tried on a PC. Test that `/S` installs without a window on a test PC before the item goes
   to any PC. **Still to fill in:** the install path, which was left out because it is not
   known and must be read on a PC after a hand install; the template then has no install
   check, and a wrong path would install again at every run, so add it only after reading it.
   `--architectures x64` follows the installer's name (`Windows-x64`); whether the installed
   program is a 64-bit one is NOT established. A person changes the template later; nothing
   else does. **If the template is made from the installer that is current on GitHub, the
   first run says "Nothing new" (see step c). To see a dry run that would publish, make the
   template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i OBSStudio-Win
    autopkg list-recipes | grep -i OBSStudio.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> OBSStudio.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `OBSStudio.pcman`, not a path. It writes
`<the Windows overrides folder>/OBSStudio.pcman.recipe` with the identifier
`local.pcman.OBSStudio` and the trust information of the two recipes and the five
processors that are not part of AutoPkg itself (`GitHubNewestReleaseGuard`, `GitHubAssetDigest`, `ChecksumVerifier`,
`VersionFromName`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.OBSStudio`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the
lines of the label step are printed (`-v` prints what each processor says about its own
work; `-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the
repository among them, and such a log would have to be kept private):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OBSStudio.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.OBSStudio`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

This is the first check of every fact in the status line. The run may stop before the
dry run, and that is the check working:

- **No asset matches** (the lines of the provider name the pattern and the release):
  the real asset name is not one that the pattern knows. Read the release's real asset
  list and correct `SEARCH_PATTERN`.
- **`GitHubNewestReleaseGuard` stops** (its message names the selected release, the newest release and the files
  of the newest release): the newest release has a file name that the pattern does not take, and the provider
  went back to an older release. Nothing was written. Correct `SEARCH_PATTERN` in the override's `Input`, or, for a newest release that has no Windows installer on
  purpose (no file ending in `.msi`, `.exe` or `.msix`), accept exactly that release with `accepted_newest_release` in the override.
  The guard is new and has not run under AutoPkg.
- **The run goes on, but with an old release** (the line `Selected asset ... from release ...`
  names a release that is not the newest non-pre-release): the newest one has a name that the
  pattern does not take, and the provider went back to an older one. Stop. Correct `SEARCH_PATTERN`
  before anything is published. The guard stops this case.
- **`GitHubAssetDigest` stops with its error** (the record has no digest): GitHub
  recorded none for this asset. Nothing was written. The program is a hand import
  until a release with a digest exists.
- **`VersionFromName` stops** (the file's name does not match the pattern, or the number in
  it is not two to four numbers joined by dots): the name is not what the recipe expects.
  Nothing was written. Read the release's real asset list, and import by hand with a label
  that a person has read.
- **The package tool refuses the label**: see "The version label".

Expected when everything holds and the current version is not yet in the repository
(the lines are what the shared processor prints; the real run has not been seen):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name        Version  Catalogs    Result
    obs-studio  <label>  Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: obs-studio <label> is in the repository already. Nothing was written.`
instead. That is correct. **Read the label in that line and compare it with the version that the
installed program shows** (see "The version label").

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/OBSStudio.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OBSStudio.pcman.recipe

The trust check should still report OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OBSStudio.pcman.recipe

   Expected: `Published obs-studio <label>.` and a table of the published version
   with the result `published`. The repository then has the installer and the pkginfo of
   the new version. The item file of the template is not changed.

2. `pcman versions obs-studio` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Not run: nothing has run under AutoPkg for this program, and the tool's catalogs command was not tried here.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OBSStudio.pcman.recipe

   It should print `Nothing new: obs-studio <label> is in the repository already.
   Nothing was written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OBSStudio.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OBSStudio.pcman.recipe

## g. A share that is not mounted

The recipe fails (exit code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing is written. Mount the share, then run again. (The shared processors'
tests show this failure; it was NOT seen on this program.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `OBSStudio` and `PCMAN_TEMPLATE` is `obs-studio`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.
- The recipe takes the newest non-pre-release only. A beta that the project marks as a
  pre-release is not downloaded, unless the override sets `include_prereleases`, and with this
  recipe's pattern not even then (see "Pre-releases" at the top).
- AutoPkg's provider takes the first release, newest first, that has a file whose name
  matches `SEARCH_PATTERN`, however old. When a name changes, the provider does not stop: it
  goes back. The step `GitHubNewestReleaseGuard`, right after it, now stops the run when the
  release that the provider selected is not the newest release that is not a pre-release; its
  message names the newest release and its files. Then correct `SEARCH_PATTERN` in the
  override's `Input`, or, for a newest release that has no Windows installer file (none ending in
  `.msi`, `.exe` or `.msix`) on purpose, accept exactly that release with the key
  `accepted_newest_release` of the override (its tag: offered only for a release without such a file,
  and not when a release between it and the selected one has one; the run goes on only while that
  release is the newest, says so in every run, and stops again when a newer one appears; never in the
  recipe). The guard compares positions in GitHub's list, not versions. It is new and has not run under
  AutoPkg. It compares releases, not files.
  Read the `Selected asset` line of every dry run (the run is made with `-v`).
- The project's own updater: OBS Studio has one that offers updates to the user (the writer's knowledge, NOT read from the
  vendor). How it behaves for a standard user, and whether it should be switched off where the client manages the version, is NOT
  established. Test it on a test PC before the item goes to any PC.
- The list was read once, on 2026-11-13. Its 30 releases have one spelling of the installer's name; older releases were not read. The installer
  of an arm64 PC, if the project makes one, is not in the list: this recipe is for x64.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares, that this README opens with the status line
that says what was not done, has no `make-override` without `--override-dir` and
runs no recipe by its identifier, and that nothing site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
