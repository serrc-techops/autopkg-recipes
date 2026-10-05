# Win-AngryIPScanner

A Windows recipe pair: Angry IP Scanner, the `.exe` installer (`ipscan-<version>-setup.exe`), with the version label taken from the file's name.

**Status. Changed after the first dry run with AutoPkg 2.9.0, and run again after the change (2026-10-04). The first run (before the change) stopped at the last step of the download recipe: `WindowsExeVersion` said that `ipscan-3.10.0-setup.exe` has no version resource (RT_VERSION), so the installer carries no version of its own and the label is now taken from the file's name by `VersionFromName` (see "The label"). The steps before it, the download and the checks of the digest, had passed (by the order of the steps; that run's log was not kept). After the change a dry run under AutoPkg 2.9.0 selected `ipscan-3.10.0-setup.exe` of `3.10.0`, passed the digest and checksum steps and took the label `3.10.0` from the file name (`VersionFromName`). Later that day the first import with the package tool (the command of step a.3 below, run with `--no-prompt` and `--build`) made the template `angryip` (an EXE item, label `3.10.0`, `--install-arguments /S`, architectures `x64`, the catalog `Production`, no install path), and the real run of the override of `AngryIPScanner.pcman` (`make-override` with `--override-dir`, `ParentRecipe` right, `verify-trust-info` OK, `pcman_dry_run` false) ended with `PcmanImporter: Nothing new: angryip 3.10.0 is in the repository already. Nothing was written.` The first import went beside the Chocolatey item `angryip` (version 1.0) without any option of the tool; the Chocolatey item file and its `angryip-1.0` pkginfo remain until a person removes them by hand, and `pcman validate` warns that the item has two versions until then. `pcman catalogs` ran a second time later on 2026-10-04, after the first imports of this and three other programs: the same command wrote the catalogs `All` and `Production`, 110 items each (106 before), with exit 0, and `Production` lists both versions of this name (the Chocolatey item's `1.0` and the new one). **The installer is an NSIS installer, not an Inno Setup installer** (the file has "Nullsoft" and "NSIS" strings and NSIS's `.ndata` section), so the switch used was `/S` and not `/VERYSILENT /NORESTART`; it was **used on 2026-10-04, not tested on a PC**. The file's stub is a 32-bit program that says nothing about the architecture of what it installs: `x64` was chosen from the project's older file names (`win64`) and the bundled Java, and no install path was given, so the template has NO install check until a person adds one. Nothing has been installed on a PC. Some facts of the source were read by the writer on 2026-10-04 from GitHub's public release list of `angryip/ipscan` (`https://api.github.com/repos/angryip/ipscan/releases`, the newest four releases; read only, no file was downloaded). READ: (1) the project publishes its releases there; the tags are plain numbers without a `v` (`3.10.0`, published 2026-08-31, then `3.9.3`, `3.9.2` and `3.9.1`) and none is flagged as a pre-release; (2) the Windows files of `3.10.0` are `ipscan-3.10.0-setup.exe` (24912120 bytes) and `ipscan-3.10.0-win.exe` (3009741 bytes); those of `3.9.3` are `ipscan-3.9.3-setup.exe` (22162953 bytes) and `ipscan-win64-3.9.3.exe` (3064425 bytes), and `3.9.2` and `3.9.1` have the same two kinds of name; (3) GitHub records a SHA-256 digest for every file of `3.10.0`, `3.9.3` and `3.9.2`, and for none of `3.9.1` (uploaded in 2023); (4) in each of the four the number in the installer's name is the release's tag (`3.10.0`, `3.9.3`, `3.9.2`, `3.9.1`). **Installer or portable program?** The release's text does not say in words which file is the installer (the `body` field of GitHub's answer holds the change list only, and neither of the words "installer" and "portable" is in it for `3.10.0` and `3.9.3`; the release's `README` file was not opened), so this is by name and size: the `-setup.exe` is the installer (18 to 25 MB; the change list of `3.10.0` says that Java 25 is bundled with the Windows builds), and the other Windows file (3 MB) is the stand-alone program, with no installer, that a silent switch would only start. Nobody opened either file, so even that is NOT established beyond the names and the sizes. The pattern of an earlier draft of this recipe, `ipscan-win64-[0-9.]+\.exe$`, names the stand-alone program of `3.9.3` and older and matches nothing in `3.10.0`: AutoPkg 2.9.0 takes the first release (in GitHub's order, newest first, a pre-release skipped) that has a file whose name the pattern matches from its start (`GitHubReleasesInfoProvider.py`, `select_asset`, `re.match`); the test file writes that down as a function, and run on the saved list it takes `ipscan-win64-3.9.3.exe` and skips `3.10.0`. The pattern is now `ipscan-([0-9]+(?:\.[0-9]+)+)-setup\.exe$`, which takes the installer of each of the four releases and no other file; its one group is the label. The label is neither the tag nor read from the file: `VersionFromName` takes it from the name (see "The label"). NOT established: that the switch `/S` installs silently on a PC; the architecture of the installed program and its install path (the template has none); the version that the installed program reports about itself (the installer has no version resource, and nobody installed it); that the next release keeps these names; any install on a PC. An install on a test PC is the check of each of them. When a run fails (no asset matches, the asset has no digest, the digest does not match, the file's name does not give a label of the right shape, the package tool refuses the label): stop; nothing was written. Read the real release page and the real asset list of the project, and correct the recipe or the template, never the trust information first. Where a line below says "expected", it is what the recipes and the other folders lead to, not something that was printed. Every override command here carries `--override-dir`: see the paragraph below.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `AngryIPScanner-Win.download.recipe` | `com.github.serrc-techops.download.AngryIPScanner-Win` | Takes the newest non-pre-release of `angryip/ipscan` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match. Last, takes the version label from the file's name (`VersionFromName`: the one group of `SEARCH_PATTERN`, checked for its shape) and sets `version` to it |
| `AngryIPScanner.cimian.recipe` | `com.github.serrc-techops.cimian.AngryIPScanner` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new. It passes the version label that the download recipe took from the file's name (`%version%`), because the installer is an `.exe` |
| `AngryIPScanner.pcman.recipe` | `com.github.serrc-techops.pcman.AngryIPScanner` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new. It passes the version label that the download recipe took from the file's name (`%version%`), because the installer is an `.exe` |

**Three recipes.** The download recipe is the parent of both of the others. `AngryIPScanner.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `AngryIPScanner.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/AngryIPScanner.cimian.recipe

(For an override that was made before this key existed, use
`Add :Input:include_prereleases bool true` instead.) Keep it a boolean: AutoPkg only
tests whether the value is empty, so the text `false` would count as true. The recipe's
step does not set it, because AutoPkg applies the arguments of a step after the
override's `Input`, and they would beat it.

## The label

An `.exe` has no version that the package tool reads for itself, so the recipe gives one. This
installer has no version resource of its own: in the first dry run with AutoPkg 2.9.0
(2026-10-04) `WindowsExeVersion` stopped on `ipscan-3.10.0-setup.exe` with "the file has no
version resource (RT_VERSION)". So the label is the number in the file's name. AutoPkg's
`GitHubReleasesInfoProvider` makes `version` from the release's tag (`3.10.0`, with no `v` to
strip), and the last step of the download recipe, `VersionFromName` (see its section in the
shared README), matches the downloaded file's name with `SEARCH_PATTERN`, whose one group is the
label (`3.10.0` for `ipscan-3.10.0-setup.exe`), checks that the group is two to four numbers
joined by dots, and overwrites `version` with it. The cimian recipe passes it as `version`, the
pcman recipe as `pcman_version`. The tag is not the source: it belongs to the release and not to the file. In the
four releases read the tag and the number in the installer's name are the same, so today the
label is also the tag; if a later release has a name and a tag that differ, the label is the
name's.

**What the label is not.** It is not the file's own version (the file has none) and it is not
what the installed program says about itself: that is NOT established, because nobody has
installed the program. The project sets the number in the name, and the label is only as good as
that word.

The first dry run (with `-v`) prints one line from that step: `version is ..., taken from the file
name ...`. **Read it first.** (The way for any Cimian repository shows the same label in its line `Would write <CIMIAN_NAME> <version>: ...`.) Before the first import (step a): install the file by hand on a
test PC, read the version that the program shows (its About box, or Apps & features), and compare
it with that label. If they differ in their numbers, stop and
tell the owner before anything is published: a label that the client orders differently from the
program's own version would hide a newer version or offer an older one. The first import (step a)
must be made with the same label that the dry run prints.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `AngryIPScanner.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

An override that was made from this recipe before the recipes were separated from the package tool belongs to the package tool's way: see the paragraph at the start of that section.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `InstallerService.cs:936`) are from `windowsadmins/cimian` at commit `e10498b`, read on 2026-10-04 and not checked against a later version.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **The version label** needs no program: the download recipe's step `VersionFromName` takes it from the installer's file name, and this recipe passes it on as `%version%`.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `angryip`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the first step of the package tool's way below marks what is only the writer's knowledge or was not read), so they are left for a person who has read them in the vendor's documentation and tried them on a test PC. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i AngryIPScanner-Win
    autopkg list-recipes | grep -i AngryIPScanner.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> AngryIPScanner.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `AngryIPScanner.cimian`, not a path. It writes `<the Windows overrides folder>/AngryIPScanner.cimian.recipe` with the identifier `local.cimian.AngryIPScanner` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.AngryIPScanner`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the lines of the provider and of the label step are printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AngryIPScanner.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.AngryIPScanner`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/AngryIPScanner.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AngryIPScanner.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AngryIPScanner.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AngryIPScanner.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AngryIPScanner.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AngryIPScanner.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `AngryIPScanner.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `AngryIPScanner.pcman` where this README used to say `AngryIPScanner.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `AngryIPScanner.cimian.recipe` (when that recipe ran the package tool) must be made again from `AngryIPScanner.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `AngryIPScanner.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   installer are in the repository. The command, in the form that ran on 2026-10-04 (it worked as
   written), with the real installer:

       pcman import <path of ipscan-3.10.0-setup.exe> --name angryip \
           --version <the label that the first dry run prints> \
           --directory <the repository folder for this item> \
           --display-name "Angry IP Scanner" --category <the category> \
           --developer "Angry IP Scanner" --description "<one sentence>" \
           --install-arguments /S --architectures x64 \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   The installer is an NSIS installer, not an Inno Setup installer: the file has "Nullsoft" and "NSIS" strings and
   NSIS's `.ndata` section. So the switch is NSIS's `/S`, and `/VERYSILENT /NORESTART` (an Inno Setup installer's) would
   not make it silent. `/S` was **used on 2026-10-04, not tested on a PC**: test that it installs without a window on a
   test PC. **Still to fill in:** the architecture and the install path. The file's stub is a 32-bit program that says nothing about
   the architecture of what it installs, so `--architectures x64` is an expectation (from the project's older `win64`
   file names and the bundled Java), and `--install-path` was left out because the path must be read on that PC after a
   test install; the template then has no install check, and a wrong path would install again at every run, so add it
   only after reading it. The label after `--version` is for an `.exe`: it must be the same that the
   first dry run prints, the number in the file's name, once a person has compared it with
   the installed program (see "The label"). Make the template from the `-setup.exe`, never from the
   other Windows file of the release (`-win.exe`, or `win64` in older names): by its name
   and size that is the stand-alone program, which a silent switch would only start. Give the flags `--category`,
   `--developer` and `--description` as the package tool's README describes. A person
   changes the template later; nothing else does. **If the template is made from the
   installer that is current on GitHub, the first run says "Nothing new" (see step c).
   To see a dry run that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i AngryIPScanner-Win
    autopkg list-recipes | grep -i AngryIPScanner.pcman

Each name must be listed once, from this repository. (Not run, so the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> AngryIPScanner.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `AngryIPScanner.pcman`, not a path. It writes
`<the Windows overrides folder>/AngryIPScanner.pcman.recipe` with the identifier
`local.pcman.AngryIPScanner` and the trust information of the two recipes and the five
processors that are not part of AutoPkg itself (`GitHubNewestReleaseGuard`, `GitHubAssetDigest`, `ChecksumVerifier`,
`VersionFromName`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.AngryIPScanner`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name. (Whether another recipe of this name exists was NOT checked: the writer had no AutoPkg.)

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the
lines of the label step are printed (`-v` prints what each processor says about its own
work; `-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the
repository among them, and such a log would have to be kept private):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AngryIPScanner.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.AngryIPScanner`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected (from the rehearsal of the 7-Zip folder, not printed for this program), also without `-v`, when the current version is not yet in the
repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name      Version      Catalogs    Result
    angryip   <the label>  Production  dry run, nothing written

Before the table the run prints the lines of the label step (see "The label"). The plan
itself is not printed. The repository is unchanged. If the current version is in the
repository already (the template was made from it), the line is `Nothing new: angryip
<the label> is in the repository already. Nothing was written.` instead. That is correct.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/AngryIPScanner.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AngryIPScanner.pcman.recipe

The trust check still reports OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AngryIPScanner.pcman.recipe

   Expected (from the 7-Zip rehearsal): `Published angryip <the label>.` and the table

       The following versions were published by the package tool:
       Name      Version      Catalogs    Result
       angryip   <the label>  Production  published

   The repository now has `pkgs/<the item folder>/angryip-<the label>.exe` and
   `pkgsinfo/<the item folder>/angryip-<the label>.yaml`. The item file of the template is not changed.

2. `pcman versions angryip` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Run on 2026-10-04: `pcman catalogs` ran twice that day, the second time after the first imports of this and three other programs. The tool's configured command ran `makecatalogs` on the repository's server and wrote the catalogs `All` and `Production`, 110 items each in the second run, with exit 0. The package tool prints "nothing to run" when its catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AngryIPScanner.pcman.recipe

   It prints `Nothing new: angryip <the label> is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AngryIPScanner.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AngryIPScanner.pcman.recipe

## g. A share that is not mounted

When the repository cannot be read, the 7-Zip rehearsal (an empty folder as the
repository) failed with exit code 70 and the tool's line (NOT seen for this program):

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written; the folder stayed empty. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `AngryIPScanner` and `PCMAN_TEMPLATE` is `angryip`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.
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

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares, that this README has no `make-override`
without `--override-dir` and runs no recipe by its identifier, and that nothing
site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
