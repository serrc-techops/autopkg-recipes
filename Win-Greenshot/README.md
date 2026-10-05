# Win-Greenshot

A Windows recipe pair: Greenshot, the installer `.exe`, with the version label read from the file itself.

**Status. Run on 2026-10-04 under AutoPkg 2.9.0, as follows. The first import (the command of step a.3 below, run with `--no-prompt` and `--build`) made the template `greenshot` (an EXE item, label `1.3.315` with a fourth part `0`, `--install-arguments '/VERYSILENT /NORESTART'`, architectures `x64`) in the package tool's repository, in the catalog `Production`. The first import went beside the Chocolatey item `greenshot` (version 1.0) without any option of the tool; the Chocolatey item file and its `greenshot-1.0` pkginfo remain until a person removes them by hand, and `pcman validate` warns that the item has two versions until then. The override of `Greenshot.pcman` (`make-override` with `--override-dir`, `ParentRecipe` right, `verify-trust-info` OK, `pcman_dry_run` false) then ran for real: the provider took `Greenshot-INSTALLER-1.3.315-RELEASE.exe` of `v1.3.315`, `GitHubAssetDigest` found its digest, the checksum and the label step passed, and the run ended with `PcmanImporter: Nothing new: greenshot <the label> is in the repository already. Nothing was written.` `pcman catalogs` ran once for all the new items together (2026-10-04): the tool's configured command ran `makecatalogs` on the repository's server, with exit 0, and wrote the catalogs `All` and `Production`, 106 items each. The installer has a version resource whose `ProductVersion` text is `1.3.315+420b08b2a9`, which is not numbers and dots only, so `WindowsExeVersion` took the four numbers of the fixed file information (`1.3.315` and a fourth part `0`) as the label (see "The label"); the file has "Inno Setup" strings, so it is an Inno Setup installer. No `--install-path` was given (it must be read on a PC after a test install), so the template has NO install check until a person adds one. The switches `/VERYSILENT /NORESTART` are the ones this README proposed from the writer's knowledge of Inno Setup: they were **used on 2026-10-04, not tested on a PC**. Still NOT established after those runs: that the switches install silently on a PC; the architecture of the installed program (the loader is a 32-bit program, and the item says `x64`, as this README proposed) and its install path; that the next release keeps these names; any install on a PC. Facts of the source read the same day: GitHub's public release list of `greenshot/greenshot` (`https://api.github.com/repos/greenshot/greenshot/releases`, the newest twelve releases; read only, no file was downloaded). READ: (1) the project publishes its releases there, and its tags begin with `v`; the newest release that is not flagged as a pre-release is `v1.3.315` (published 2026-03-20, titled "Greenshot 1.3.315"), then `v1.3.312` and `v1.3.311` (both published 2026-01-07); (2) the other nine of the twelve are flagged as pre-releases and titled "(continuous build)": every `v1.4.` build (the newest, `v1.4.289-g7bee683e93`, was published on 2026-10-04) and the 1.3 builds whose files are named `-UNSTABLE-UNSIGNED`; (3) the files of `v1.3.315` are `Greenshot-INSTALLER-1.3.315-RELEASE.exe` (3967064 bytes) and `Greenshot-PORTABLE-1.3.315-RELEASE.zip` (3722113 bytes), and `v1.3.312` and `v1.3.311` have the same two kinds of name; the installers of the pre-releases are named like `Greenshot-INSTALLER-1.4.289-g7bee683e93-UNSTABLE-UNSIGNED.exe`, and the 1.4 builds have a second installer, `Greenshot-Light-INSTALLER-...`; (4) the pattern `Greenshot-INSTALLER-[0-9.]+-RELEASE\.exe$` matches the installer of each of the three releases that are not flagged and no other file of the twelve releases; (5) GitHub records a SHA-256 digest for every file of the twelve releases, the `.exe` files included. So, by these names, AutoPkg 2.9.0 (which takes the first release, in GitHub's order, that is not flagged and has a file whose name the pattern matches from its start: `GitHubReleasesInfoProvider.py`, `select_asset`, `re.match`) took `Greenshot-INSTALLER-1.3.315-RELEASE.exe` of `v1.3.315` in the runs of 2026-10-04, and `GitHubAssetDigest` found its digest. An install on a test PC is the check of what is NOT established. When a run fails (no asset matches, the asset has no digest, the digest does not match, the executable has no version resource or says zeros, the package tool refuses the label): stop; nothing was written. Read the real release page and the real asset list of the project, and correct the recipe or the template, never the trust information first. Where a line below says "expected", it is what the recipes and the other folders lead to, not something that was printed. Every override command here carries `--override-dir`: see the paragraph below.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Greenshot-Win.download.recipe` | `com.github.serrc-techops.download.Greenshot-Win` | Takes the newest non-pre-release of `greenshot/greenshot` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match. Last, reads the `ProductVersion` from the `.exe` itself and sets `version` to it |
| `Greenshot.cimian.recipe` | `com.github.serrc-techops.cimian.Greenshot` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new. It passes the version label that the download recipe read from the `.exe` (`%version%`), because the installer is an `.exe` |
| `Greenshot.pcman.recipe` | `com.github.serrc-techops.pcman.Greenshot` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new. It passes the version label that the download recipe read from the `.exe` (`%version%`), because the installer is an `.exe` |

**Three recipes.** The download recipe is the parent of both of the others. `Greenshot.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `Greenshot.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

## The label

The release's tag is not a label. AutoPkg's `GitHubReleasesInfoProvider` makes `version`
from the tag by removing a leading `v` or `.`; the tag of the release that the recipe is
expected to take is `v1.3.315`, which gives `1.3.315`, and the tag of a pre-release such as
`v1.4.289-g7bee683e93` gives `1.4.289-g7bee683e93`, with the commit's short name in it,
which is not a label. The last step of the download recipe, `WindowsExeVersion`, reads the
`ProductVersion` of the downloaded file and overwrites `version` with it (when that
string is numbers and dots only; otherwise it takes the four numbers of the fixed file
information; see its section in the shared README). The cimian recipe passes it as
`version`, the pcman recipe as `pcman_version`.

The first dry run prints two lines from that step: `ProductVersion '...', product
version numbers ..., file version '...', file version numbers ...` and `version is ...,
taken from ...`. A person reads them and compares: the label must be the version that
the file's properties show, and the first import (step a) must be made with the same
label. If the `ProductVersion` is not numbers and dots only, the label has four numbers
and may not look like what the project prints; the package tool's plan shows what it
makes of it. On 2026-10-04 the `ProductVersion` string was `1.3.315+420b08b2a9` (not numbers and dots only), so the label is the fixed file information's `1.3.315` with a fourth part `0`. Whether the label orders correctly against the installed program's version is NOT established.

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/Greenshot.cimian.recipe

(For an override that was made before this key existed, use
`Add :Input:include_prereleases bool true` instead.) Keep it a boolean: AutoPkg only
tests whether the value is empty, so the text `false` would count as true. The recipe's
step does not set it, because AutoPkg applies the arguments of a step after the
override's `Input`, and they would beat it.

**The 1.4 line.** In the twelve releases read, the 1.4 builds are published only as pre-releases, and the names of their
installers (`Greenshot-INSTALLER-1.4.289-g7bee683e93-UNSTABLE-UNSIGNED.exe`) do not match the
pattern. With `include_prereleases` set to true and nothing else changed, the recipe still
takes `Greenshot-INSTALLER-1.3.315-RELEASE.exe` of `v1.3.315`, because that is the first
release with a matching file. Taking a 1.4 build would need two changes in the override's
`Input`, and the recipe makes neither: `include_prereleases` true, and `SEARCH_PATTERN`
changed to a pattern that matches the 1.4 installer and not the `Greenshot-Light-INSTALLER-...`
file beside it, for example `Greenshot-INSTALLER-[0-9.]+-g[0-9a-f]+-UNSTABLE-UNSIGNED\.exe$`.
Whether a continuous build with `UNSTABLE-UNSIGNED` in its name goes to the PCs is the
owner's decision. With the guard in the recipe, that run (`include_prereleases` true and the pattern unchanged) **stops**:
the newest release is then a 1.4 build whose files the pattern does not take, and the message of `GitHubNewestReleaseGuard` says so; before the guard it took
`v1.3.315` without a word. With the two changes above (the 1.4 pattern and `include_prereleases` true) the guard **still stops whenever a 1.3 release is on top of
GitHub's list**, because the vendor publishes 1.3 releases between its 1.4 builds: on the list read on 2026-10-04 the top was a 1.3 release from `v1.3.310` (2026-01-05) until `v1.4.284`
(2026-10-02), so such a run would have stopped for those nine months although the provider took the right 1.4 build. The third change that follows the 1.4 line is
the override's key `release_tag_pattern` set to `v1\.4\.` (a regular expression matched from the start of the tag): then only a 1.4 release counts as the newest.
Every run then names the newer releases that the pattern left out (here the 1.3 releases listed above the newest 1.4 build), so that the pattern cannot hide a rename in silence.
`accepted_newest_release` is not the way out here: every 1.3 release has a Windows installer file, so an acceptance is refused for it.

**A newer release without the file.** AutoPkg's provider takes the first release, newest first, that has a file whose
name matches `SEARCH_PATTERN`, however old, and says nothing when the newest release has none (a vendor's new spelling of the
name). The download recipe's step `GitHubNewestReleaseGuard`, right after the provider, stops the run in that case: its message
names the selected release, the newest release and the files of the newest release. Then correct `SEARCH_PATTERN` in the
override's `Input`. If the newest release has no Windows installer file (none ending in `.msi`, `.exe` or `.msix`) on purpose, for example
a development build with only a `.zip`, and you have looked at it, accept exactly that release: `/usr/libexec/PlistBuddy -c 'Set :Input:accepted_newest_release <its tag>' <the override>`
(`Add :Input:accepted_newest_release string <its tag>` for an override that was made before this key existed). The guard offers and honours
this only for a release without such a file (a release that has one is a renamed installer: correct `SEARCH_PATTERN`), and not when a release
between it and the selected one has one. The run then goes on with the older release **only while that release is the newest**, says so in every
run and in AutoPkg's end-of-run table, and stops again when a newer release appears. Never set it in the recipe. The guard compares positions in
GitHub's list, not versions: for a vendor that publishes two lines of releases side by side, and only then, name the line with the override's
`release_tag_pattern` (a regular expression matched from the start of the tag; every run names the newer releases that it left out). The guard
asks GitHub once, without a credential, and has not run under AutoPkg yet. Read the `Selected asset` line of every dry run all the same (run it
with `-v`): the guard compares releases, the line names the file.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `Greenshot.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

3. **The version label** needs no program: the download recipe's step `WindowsExeVersion` reads it from the `.exe` itself, and this recipe passes it on as `%version%`.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `greenshot`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the first step of the package tool's way below marks what is only the writer's knowledge or was not read), so they are left for a person who has read them in the vendor's documentation and tried them on a test PC. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i Greenshot-Win
    autopkg list-recipes | grep -i Greenshot.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Greenshot.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `Greenshot.cimian`, not a path. It writes `<the Windows overrides folder>/Greenshot.cimian.recipe` with the identifier `local.cimian.Greenshot` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.Greenshot`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.Greenshot`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/Greenshot.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `Greenshot.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `Greenshot.pcman` where this README used to say `Greenshot.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `Greenshot.cimian.recipe` (when that recipe ran the package tool) must be made again from `Greenshot.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `Greenshot.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   installer are in the repository. The command, in the form that ran on 2026-10-04, with the
   real installer:

       pcman import <path of the installer, a file that matches the pattern> --name greenshot \
           --version <the label that the first dry run prints> \
           --directory <the repository folder for this item> \
           --display-name "Greenshot" --category <the category> \
           --developer "Greenshot" --description "<one sentence>" \
           --install-arguments '/VERYSILENT /NORESTART' \
           --architectures x64 --icon <the file name of an icon that the repository has> --no-prompt --build

   The silent switches `/VERYSILENT /NORESTART` are an Inno Setup installer's, and the file has "Inno Setup"
   strings; they were **used on 2026-10-04, not tested on a PC**: test that they install without a window on a
   test PC. `--architectures x64` is an expectation, not a fact: the installer is a 32-bit loader, and the
   architecture of the installed program is NOT established (see the status line). `--install-path` was left out because
   the path must be read on that PC after a test install; the template then has no install check, and a wrong path would
   install again at every run, so add it only after reading it. The label
   after `--version` is for an `.exe`: it must be the same that the first dry run prints
   (see "The label"; on 2026-10-04 it was `1.3.315` with a fourth part `0`, the fixed file information, because the
   `ProductVersion` string has text in it). Give the flags `--category`,
   `--developer` and `--description` as the package tool's README describes. A person
   changes the template later; nothing else does. **If the template is made from the
   installer that is current on GitHub, the first run says "Nothing new" (see step c).
   To see a dry run that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Greenshot-Win
    autopkg list-recipes | grep -i Greenshot.pcman

Each name must be listed once, from this repository. (Not run, so the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Greenshot.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Greenshot.pcman`, not a path. It writes
`<the Windows overrides folder>/Greenshot.pcman.recipe` with the identifier
`local.pcman.Greenshot` and the trust information of the two recipes and the five
processors that are not part of AutoPkg itself (`GitHubNewestReleaseGuard`, `GitHubAssetDigest`, `ChecksumVerifier`,
`WindowsExeVersion`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Greenshot`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name. (Whether another recipe of this name exists was NOT checked: the writer had no AutoPkg.)

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the
lines of the label step are printed (`-v` prints what each processor says about its own
work; `-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the
repository among them, and such a log would have to be kept private):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.Greenshot`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected (from the rehearsal of the 7-Zip folder, not printed for this program), also without `-v`, when the current version is not yet in the
repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name       Version      Catalogs    Result
    greenshot  <the label>  Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: greenshot <the label> is in the repository already. Nothing was written.`
instead. That is correct.

Before the table the run prints the lines of the step that reads the label: `... ProductVersion
'...' ...` and `version is ..., taken from ...` (see "The label"). **Read them first.** Read
the provider's line `Selected asset '...' from release '...'` too (`GitHubReleasesInfoProvider.py`,
`select_asset`): by the release list of 2026-10-04 it names `Greenshot-INSTALLER-1.3.315-RELEASE.exe`
and `Greenshot 1.3.315`, and a newer release that is not flagged would show its own names. If it
names a file with `UNSTABLE`, `Light` or `PORTABLE` in its name, stop and tell the owner: the pattern
or the override is not what this README says. A `ProductVersion` with text in it
means that the label is the four numbers: compare it with the file's properties.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Greenshot.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.pcman.recipe

The trust check still reports OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.pcman.recipe

   Expected (from the 7-Zip rehearsal): `Published greenshot <the label>.` and the table

       The following versions were published by the package tool:
       Name       Version      Catalogs    Result
       greenshot  <the label>  Production  published

   The repository now has `pkgs/<the item folder>/greenshot-<the label>.exe` and
   `pkgsinfo/<the item folder>/greenshot-<the label>.yaml`. The item file of the template is not changed.

2. `pcman versions greenshot` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Run on 2026-10-04 for all the new items of that day together, this one among them: the tool's configured command ran `makecatalogs` on the repository's server and wrote the catalogs `All` and `Production`, with exit 0. The package tool prints "nothing to run" when its catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.pcman.recipe

   It prints `Nothing new: greenshot <the label> is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.` (On 2026-10-04 the first run of a fresh override printed the line `Nothing new: ...` after it had downloaded the file again, because a new override gets a new cache folder; `Nothing downloaded, packaged or imported.` was not seen in that run, and is the line of a later run of the same override.)

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.pcman.recipe

## g. A share that is not mounted

When the repository cannot be read, the 7-Zip rehearsal (an empty folder as the
repository) failed with exit code 70 and the tool's line (NOT seen for this program):

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written; the folder stayed empty. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `Greenshot` and `PCMAN_TEMPLATE` is `greenshot`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares (`WindowsExeVersion` included, and that it is the
last step of the download recipe, after the checksum), that the pattern matches the
installer and not the other files of a release, that this README has no `make-override`
without `--override-dir` and runs no recipe by its identifier, and that nothing
site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
