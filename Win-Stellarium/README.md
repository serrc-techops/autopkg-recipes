# Win-Stellarium

A Windows recipe pair: Stellarium, the public Qt6 x64 Windows `.exe` installer, with the version label taken from the file's name.

**Status. New. Nothing in this folder has run under AutoPkg: no dry run, no real run, no import with the package tool, no catalog build, and nothing was installed on a PC. No file was downloaded; the installer was never opened. Facts of the source were read by the writer on 2026-11-13 from GitHub's public release list of `Stellarium/stellarium` (`https://api.github.com/repos/Stellarium/stellarium/releases`, the newest 30 releases; read only). READ: (1) the project publishes its releases there, with tags such as `v26.3` (published 2026-09-28, the newest), `v26.2`, `v26.1` and `v25.4`; none of the 30 releases is flagged as a pre-release and none is a draft; (2) each release from `v26.3` back to `v23.1` has several Windows installers: the Qt6 build for 64-bit Windows (`stellarium-26.3-qt6-win64.exe`, 489006448 bytes, about 466 MiB), a Qt5 build for 64-bit Windows (`stellarium-26.3-qt5-win64.exe`), and a Qt6 build for ARM64 (`stellarium-26.3-qt6-arm64.exe`, in the releases from `v23.4` on); `v25.2` also has `stellarium-25.2-qt5.15-win64.exe`, and the releases up to `v24.4` also have 32-bit installers; each installer has a signature file of the same name with `.asc` added, which the recipe does not use; (3) the pattern is `stellarium-([0-9]+(?:\.[0-9]+)+)-qt6-win64\.exe$`, and its one group is the label: it takes exactly one file in each of 17 of the 30 releases (`v26.3` back to `v1.1`) and none in the 13 older ones (`v1.0` and before, which have no Qt6 build); (4) the tag is not always the version in the file's name: the release `v1.1` holds an installer whose name says `1.1.1`, and in every release from `v1.2` to `v26.3` the tag without its `v` is the version in the name; (5) GitHub records a SHA-256 digest for the Qt6 x64 installer of each release from `v25.2` (2025-06-22) to the newest, and for none of `v25.1` (2025-03-23) and older, so `GitHubAssetDigest` finds one for the release that the recipe takes. NOT established: that this is the build that the fleet should have (the Qt5 build is, by the writer's knowledge, the one for older Windows, which was NOT read, and which Windows versions the Qt6 build supports was NOT read); whether the installer has a version resource (nothing was downloaded; the label comes from the file's name, as a precaution, see "The version label"); the installer's kind: **the installer is an Inno Setup installer by the writer's knowledge, which was NOT read from the vendor and NOT checked in the file**, with the usual switches `/VERYSILENT /NORESTART /SUPPRESSMSGBOXES`, **NOT tested on a PC**; the install path and the architecture of the installed program; the version that the installed program reports about itself; whether it matches the label; that the next release keeps the file's name (if the project renames the file, the provider goes back to the newest older release that matches: read the line of the first dry run that names the selected asset and release); the package tool's answer to the label and to the switches; the file's size (about 466 MiB) against the share and the PCs' disks and download times; any install on a PC. The template item has NO install check until a person adds one. When a run fails, stop. Nothing was written. Read the real release page or the real release, and correct the recipe. Never change the trust information first.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Stellarium-Win.download.recipe` | `com.github.serrc-techops.download.Stellarium-Win` | Takes the newest non-pre-release of `Stellarium/stellarium` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match. Last, takes the version label from the file's name (`VersionFromName`: the one group of `SEARCH_PATTERN`, checked for its shape) and sets `version` to it |
| `Stellarium.cimian.recipe` | `com.github.serrc-techops.cimian.Stellarium` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new. It passes the version label that the download recipe took from the file's name (`%version%`) |
| `Stellarium.pcman.recipe` | `com.github.serrc-techops.pcman.Stellarium` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new. It passes the version label that the download recipe took from the file's name (`%version%`) |

**Three recipes.** The download recipe is the parent of both of the others. `Stellarium.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `Stellarium.pcman.recipe` is the package tool's way, with `PcmanImporter`. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. None of the 30 releases read on 2026-11-13 is one. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/Stellarium.cimian.recipe

(For an override that was made before this key existed, use
`Add :Input:include_prereleases bool true` instead.) Keep it a boolean: AutoPkg only
tests whether the value is empty, so the text `false` would count as true. The recipe's
step does not set it, because AutoPkg applies the arguments of a step after the
override's `Input`, and they would beat it.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## The version label

The installer is an `.exe`, so the recipes pass the label on: the pcman recipe to the package tool
(`pcman_version` is `%version%`), the cimian recipe to `CimianImporter` (`version` is `%version%`); neither tool reads a version from an EXE. Whether this installer has a version resource was NOT read:
nothing was downloaded, and `WindowsExeVersion` was not tried on it. So the label is the version in the file's name, which
needs no file. AutoPkg makes `version` from the release tag first, and the last step of the download recipe, `VersionFromName` (shared, see its
section in the shared README), matches the downloaded file's name with `SEARCH_PATTERN`, whose
one group is the label, checks that the group is two to four numbers joined by dots, and
overwrites `version` with it. The tag is not the source: it belongs to the release
and not to the file, and it is not always the file's version (see the status line: the release `v1.1` holds an installer whose name says `1.1.1`).

**What the label is not.** It is not the file's own version (not known) and it is not
what the installed program says about itself: that is NOT established, because nobody has
installed the program. The project sets the number in the name, and the label is only as good as
that word.

**Two parts.** The labels of the releases that the pattern takes are two numbers joined by a dot, like `26.3` (the year and the number of the release in that year), except `1.1.1` in the oldest one. Two questions about them are open. The package tool's answer to such a label has NOT been seen (the first dry run shows it). And whether the Cimian client orders it as the program's own version is NOT established. The README of `Win-BambuStudio` states, from a reading of `windowsadmins/cimian` at commit `3cf02c4` on 2026-10-04 (a second reader found the same code at `e10498b`; not read again for this folder), that the client compares the parts of a version as numbers and has two rules that read a label as a build time: `VersionService.TryParseCalendarBuildStamp` needs a first part that is a year of four digits, and `CatalogService.ExpandBuildTimestamp` (the code of the catalog order and of the check of installed versions) reads a label of exactly three parts, `yy.M.ddHH`, with `yy` from 20 to 99, a month from 1 to 12 and a third part of three or four digits, as a build time. A label like `26.3` has two parts and meets neither rule.

**A third part.** The project has not used a three-part label in the 17 releases read, apart from `1.1.1` in the oldest. A label such as `26.3.1` would have the shape `yy.M.x`, and `yy` and the month would fit the second rule. By the rule as that README states it, it is read as a build time only when its third part has three or four digits, so `26.3.1` (one digit) is not; a label such as `26.3.100` or `26.3.1000` would be. What follows for the first one: it is ordered as numbers, `26.3.1` against `26.3` and against `26.4` by their parts; how the client treats the missing third part of `26.3` was NOT read here. What follows for the second: the client would order it by a build time and not by its numbers, which could place it wrongly beside `26.4`. Neither has been seen in a release. If a release of Stellarium has such a label, stop and tell the owner before the import is real.

The first dry run (with `-v`) prints the lines of the provider that name the selected asset and
release (`Selected asset ... from release ...`) and one line from the label step: `version is ...,
taken from the file name ...`. **Read them first**: the selected release must be the newest that
is not a pre-release (see the status line for why), and the label must be the release's number.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01 in another folder of this repository: `verify-trust-info` without the option said "No trust information present" for an override that has it. Not seen with this folder.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `Stellarium.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

An override that was made from this recipe before the recipes were separated from the package tool belongs to the package tool's way: see the paragraph at the start of that section.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `StatusService.cs:194-219`) are copied from the README of `Win-BambuStudio`: `windowsadmins/cimian` at commit `e10498b`, read on 2026-10-04 by another writer and not read again for this folder, nor checked against a later version.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **The version label** needs no program: the download recipe's step `VersionFromName` takes it from the installer's file name, and this recipe passes it on as `%version%`. The answer of `CimianImporter` to the label has NOT been seen.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `stellarium`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the status line marks that the installer's kind is only the writer's knowledge, and the first step of the package tool's way below gives the switches that the writer expects), so they are left for a person who has read them in the vendor's documentation and tried them on a test PC. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i Stellarium-Win
    autopkg list-recipes | grep -i Stellarium.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Stellarium.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `Stellarium.cimian`, not a path. It writes `<the Windows overrides folder>/Stellarium.cimian.recipe` with the identifier `local.cimian.Stellarium` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.Stellarium`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the lines of the provider and of the label step are printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Stellarium.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.Stellarium`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/Stellarium.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Stellarium.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Stellarium.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Stellarium.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Stellarium.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Stellarium.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `Stellarium.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `Stellarium.pcman` where this README used to say `Stellarium.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `Stellarium.cimian.recipe` (when that recipe ran the package tool) must be made again from `Stellarium.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `Stellarium.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   installer are in the repository. The command is a **proposal, NOT run**, with a real
   installer (about 466 MiB) that a person has downloaded and checked:

       pcman import <path of the installer> --name stellarium --version <label> \
           --display-name "Stellarium" --category <the category> \
           --developer "Stellarium team" --description "<the description>" \
           --directory <the folder of the item> \
           --install-arguments "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES" --architectures x64 \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   `--version <label>` is for an EXE only, and the label is the one that step c will
   show (see "The version label"). By the writer's knowledge the installer is an Inno Setup
   installer, which was NOT read from the vendor and NOT checked in the file, and the three
   switches are the usual ones of that kind; **they are NOT tested on a PC**: test that the
   installer installs without a window on a test PC, and read the vendor's own notes first.
   How `pcman import` wants several switches written (one quoted argument as above, or the option
   repeated) was NOT read: read its help. **Still to fill in:** the architecture and the install
   path. `--architectures x64` is an expectation from the file's name (`win64`), not a reading of the
   installed program, and `--install-path` is left out because the path must be read on a PC after a
   hand install; the template then has no install check, and a wrong path would install again at
   every run, so add it only after reading it. A person changes the
   template later; nothing else does. **If the template is made from the installer that
   is current on GitHub, the first run says "Nothing new" (see step c). To see a dry run
   that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Stellarium-Win
    autopkg list-recipes | grep -i Stellarium.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Stellarium.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Stellarium.pcman`, not a path. It writes
`<the Windows overrides folder>/Stellarium.pcman.recipe` with the identifier
`local.pcman.Stellarium` and the trust information of the two recipes and the five
processors that are not part of AutoPkg itself (`GitHubNewestReleaseGuard`, `GitHubAssetDigest`, `ChecksumVerifier`,
`VersionFromName`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Stellarium`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the
lines of the label step are printed (`-v` prints what each processor says about its own
work; `-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the
repository among them, and such a log would have to be kept private):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Stellarium.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.Stellarium`) runs the recipe itself, not the
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
  pattern does not take, and the provider went back to an older one. Stop. Correct `SEARCH_PATTERN` before anything is published. The guard now stops this case.
- **`GitHubAssetDigest` stops with its error** (the record has no digest): GitHub
  recorded none for this asset. Nothing was written. The program is a hand import
  until a release with a digest exists.
- **`VersionFromName` stops** (the file's name does not match the pattern, or the number in
  it is not two to four numbers joined by dots): the name is not what the recipe expects.
  Nothing was written. Read the release's real asset list, and import by hand with a label
  that a person has read.
- **The package tool refuses the label**: see "The version label"; its answer to a two-part label has NOT been seen.

Expected when everything holds and the current version is not yet in the repository
(the lines are what the shared processor prints; the real run has not been seen):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name          Version  Catalogs    Result
    stellarium   <label>  Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: stellarium <label> is in the repository already. Nothing was written.`
instead. That is correct. **Read the label in that line and compare it with the version that the
installed program shows** (see "The version label").

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Stellarium.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Stellarium.pcman.recipe

The trust check should still report OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Stellarium.pcman.recipe

   Expected: `Published stellarium <label>.` and a table of the published version
   with the result `published`. The repository then has the installer and the pkginfo of
   the new version. The item file of the template is not changed.

2. `pcman versions stellarium` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Not run. The package tool prints "nothing to run" when its catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Stellarium.pcman.recipe

   It should print `Nothing new: stellarium <label> is in the repository already.
   Nothing was written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Stellarium.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Stellarium.pcman.recipe

## g. A share that is not mounted

The recipe fails (exit code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing is written. Mount the share, then run again. (The shared processors'
tests show this failure; it was NOT seen on this program.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `Stellarium` and `PCMAN_TEMPLATE` is `stellarium`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.
- The recipe takes the newest non-pre-release only. A beta that the project marks as a
  pre-release is not downloaded, unless the override sets `include_prereleases` (see
  "Pre-releases" at the top).
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

They check that all three files are property lists, that every argument is an input
that the shared processor declares, that the pattern takes exactly one file in each release of the
saved list that has one and none of the other files, that this README opens with the status line
that says what was not done, has no `make-override` without `--override-dir` and
runs no recipe by its identifier, and that nothing site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
