# Win-Audacity

A Windows recipe pair: Audacity, the x86_64 `.msi` of the project `audacity/audacity` on GitHub (4.0 and later).

**Status. New, and not rehearsed (written 2026-11-13). Nothing has run under AutoPkg for this folder, no file was downloaded and nothing was installed on a PC. READ on 2026-11-13, from GitHub's public release list of `audacity/audacity` (`https://api.github.com/repos/audacity/audacity/releases`, the newest 30 releases, saved; a small excerpt of it is `tests/releases_excerpt.json`): the tags are written like `Audacity-4.0.2`, not as a bare version. The newest release that is not a pre-release is `Audacity-4.0.2` (published 2026-11-02), then `Audacity-4.0.1` (2026-09-30), `Audacity-4.0.0` (2026-09-03) and `Audacity-3.7.9` (2026-09-01). From 4.0.0 on, a release has two Windows MSIs, `audacity-win-<version>-x86_64.msi` (`audacity-win-4.0.2-x86_64.msi` is 49823744 bytes) and `audacity-win-<version>-arm64.msi`, and GitHub records a digest for both. The 3.x line has `.exe` installers (`audacity-win-3.7.9-64bit.exe`, `-32bit.exe`, `-arm64.exe`) and no MSI. The pre-releases of 4.0 used other spellings (`Audacity-4.0.0-beta4-x86_64.msi`, `Audacity-4.0.0-beta4-aarch64.msi`, `Audacity-4.0.0-beta2-x86_64.msi`, and a build-number name for the alpha) and are skipped anyway. The recipe takes the x86_64 MSI with `audacity-win-[0-9.]+-x86_64\.msi$`: on the 30 saved releases it matches exactly one file in each of `Audacity-4.0.2`, `Audacity-4.0.1` and `Audacity-4.0.0` and no file in any other release, pre-releases included. GitHub records a digest for the MSI of each of those three, so the download stays verified by `GitHubAssetDigest` and `ChecksumVerifier`. The project may still publish a 3.x maintenance release after a 4.x one. That release would be first in GitHub's list and has `.exe` files and no MSI: the provider would go on to the 4.x release below it, and `GitHubNewestReleaseGuard` stops the run because the newest release is not the one that was selected. The way to follow the 4.x line is the override's `release_tag_pattern` (see the section "Following the 4.x line"). NOT established: the MSI's ProductVersion and whether it equals the version in the name; whether the install is per machine or per user; that `msiexec /qn` installs silently; the install path; the publisher that the installer names (the developer `Audacity Team` in the recipe is the project's name, not read from the installer); what happens to a 3.x installation made with the `.exe` (an Inno Setup install may stay beside the 4.x MSI: a person checks on a test PC); whether a later release keeps the same UpgradeCode. NOT run: `GitHubReleasesInfoProvider`, `URLDownloader`, `PcmanImporter` and `CimianImporter` with this recipe; the guard and the checksum steps were only tested as functions on the saved list (the tests of this folder). The first dry run is the test: run it with `-v`, read the `Selected asset ... from release ...` line against the vendor's releases page, and if a step fails, nothing was written: correct the recipe, never accept trust information to make a failure go away. Every command of this README carries `--override-dir`.**

**Results of 2026-11-13, newer than the status above; where the two differ, this paragraph holds.** Under AutoPkg 2.9.0, into a scratch Cimian repository with a hand-made first pkginfo of the item (`make-override` with `--override-dir`, `verify-trust-info` OK, a dry run, a real run, a second real run): the real run published `audacity-4.0.2.263060742.msi`, and the second run said that nothing is new. The label is the MSI's ProductVersion, not the release tag. On one Windows 11 test PC, as SYSTEM from a scheduled task, `msiexec /i <file> /qn /norestart` ended with exit code 0 after 7 seconds; the file's signature was valid (MUSECY SM LTD); the PC then listed `Audacity 4.0` with DisplayVersion `4.0.2.263060742`, installed in `C:\Program Files\Audacity 4\`, product code `{6CECECEA-CC25-46AF-AACE-DD7EA6FB83D3}`. The program was not started, an upgrade over an older version and the uninstall were not tested, and no Cimian client installed it.

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Audacity-Win.download.recipe` | `com.github.serrc-techops.download.Audacity-Win` | Takes the newest non-pre-release of `audacity/audacity` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match |
| `Audacity.cimian.recipe` | `com.github.serrc-techops.cimian.Audacity` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `Audacity.pcman.recipe` | `com.github.serrc-techops.pcman.Audacity` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `Audacity.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `Audacity.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

No shared download recipe is the parent. Neither recipe stops on an unchanged
download, so an import that failed is tried again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/Audacity.cimian.recipe

(For an override that was made before this key existed, use
`Add :Input:include_prereleases bool true` instead.) Keep it a boolean: AutoPkg only
tests whether the value is empty, so the text `false` would count as true. The recipe's
step does not set it, because AutoPkg applies the arguments of a step after the
override's `Input`, and they would beat it.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## Following the 4.x line

The project may publish a 3.x maintenance release after a 4.x one. Such a release has `.exe` installers and no MSI. GitHub lists it first, so `GitHubNewestReleaseGuard` sees it as the newest release, while the provider (which takes the first release that has a file matching `SEARCH_PATTERN`) goes on to the 4.x release below it. The guard then stops the run. Its message names the newest release and its files, says that it has Windows installer files, and offers no acceptance for it: `accepted_newest_release` is only for a newest release without a `.msi`, `.exe` or `.msix` file. (Tested as a function on the saved list with a made-up `Audacity-3.7.10` on top; NOT seen in a real run.)

The cure is the override's `release_tag_pattern`: a regular expression that is matched from the start of the tag (`re.match`). Only a release whose tag matches it counts as the newest. For this project:

    /usr/libexec/PlistBuddy -c 'Set :Input:release_tag_pattern Audacity-4\.' \
        <the Windows overrides folder>/Audacity.cimian.recipe

(Use the override of the recipe that you run; the key is in the recipe's `Input`, empty, so `make-override` copies it.) The pattern does not choose the file: `SEARCH_PATTERN` does. With the pattern the run goes on, and every run, not only with `-v`, prints a line that names the newer releases that the pattern left out (for the made-up case: `release_tag_pattern 'Audacity-4\.' left out 1 newer release of audacity/audacity: 'Audacity-3.7.10'. ...`). **Read that line.** When a 5.x release appears, the provider selects its MSI, which the pattern does not cover, and the guard stops the run (tested on a made-up list, NOT seen in a real run; its message names the 5.x release as selected and the newest 4.x release as newest): change the pattern then. The pattern is no cure for a renamed 4.x installer either: the guard says so too.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg, `msiinfo` (msitools: `brew install msitools`) for the MSI, and nothing of the owner's: no package tool. It uses `Audacity.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

3. **`msiinfo` on the PATH of the run** (`brew install msitools`): `CimianImporter` reads the MSI's ProductVersion and its two codes with it, and does not parse an MSI itself. A job that `launchd` starts may have no Homebrew on its `PATH`, so the importer looks in `/opt/homebrew/bin` and `/usr/local/bin` too; the input `cimian_path` changes that list. This recipe cannot run without it: its step passes an empty `version` (so that a release tag is not taken for the MSI's own version), and an argument of a step wins over an override's `Input`, so the label can only come from the MSI. The run stops and names the facts that are missing.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `audacity`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **For an `.msi` nothing needs completing for a silent install:** the client runs `msiexec /i <file> /qn /norestart` itself and then the arguments of the item (`InstallerService.cs:936-948`), so the recipe gives no silent arguments, and `CimianImporter` writes the install check of an MSI (an `installs` entry of type `msi` with the MSI's codes and version). What the MSI's own properties allow (features, per-user or per-machine) is the template's business: give them as `installer: {args: [...]}` in the override's `pkginfo`. An MSI whose upgrade code is not the template's, or that has none where the template's item had one, is refused (Windows Installer does not upgrade across upgrade codes): `cimian_allow_product_change` set to true in the override allows it, with a WARNING.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i Audacity-Win
    autopkg list-recipes | grep -i Audacity.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Audacity.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `Audacity.cimian`, not a path. It writes `<the Windows overrides folder>/Audacity.cimian.recipe` with the identifier `local.cimian.Audacity` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.Audacity`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the line of the provider that names the selected asset and release (`Selected asset ... from release ...`) is printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Audacity.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.Audacity`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.msi (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/Audacity.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Audacity.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Audacity.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Audacity.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Audacity.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Audacity.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `Audacity.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `Audacity.pcman` where this README used to say `Audacity.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `Audacity.cimian.recipe` (when that recipe ran the package tool) must be made again from `Audacity.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `Audacity.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

## a. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in
   AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step b) takes a recipe NAME and refuses
   a path. The rehearsal of `Win-7Zip` printed: `make-override doesn't work with absolute recipe
   paths`.

2. **The settings of the processor, as AutoPkg preferences.** One line each:

       defaults write com.github.autopkg pcman_root -string "<the package tool's folder>"
       defaults write com.github.autopkg pcman_python -string "<the package tool's Python>"

   `pcman_python` is only needed when it is not `<the package tool's folder>/.venv/bin/python3`.
   Write the values as strings. The repository is not a setting here: the package
   tool's own configuration says where it is. The repository must be reachable
   (the share mounted). For an MSI the package tool needs `msiinfo` (the processor
   looks for it in its default `PATH`, which has the Homebrew folders).

3. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. The template keeps the name of the item that
   it replaces. An old item `audacity` of another kind (a Chocolatey item, say) is not the template: a person decides what happens to it. The command (the form of the package tool's README; NOT run for this program), with a real MSI of the project:

       pcman import <path of the downloaded audacity-win-<version>-x86_64.msi> --name audacity \
           --display-name "Audacity" --category <the category> \
           --developer <the developer's name> --description <the description> \
           --directory <the folder of the item> --architectures x64 \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version (how many parts it has, and whether it equals the version in the file's name, is NOT established). The install arguments are the package tool's own for an MSI (`/qn /norestart` from the client; not tested
   on a PC): do not add an install path for an MSI unless the package tool's README asks for one. `--architectures x64` is
   from the name of the file (`x86_64`); the MSI's summary was NOT read.
   Give the category, the developer and the description the package tool's README
   describes. A person changes the template later; nothing else does. **If the
   template is made from the installer that is current on GitHub, the first run says
   "Nothing new" (see step c). To see a dry run that would publish, make the
   template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Audacity-Win
    autopkg list-recipes | grep -i Audacity.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Audacity.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Audacity.pcman`, not a path. It writes
`<the Windows overrides folder>/Audacity.pcman.recipe` with the identifier
`local.pcman.Audacity` and the trust information of the two recipes and the four
processors. **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Audacity`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the line of the provider that names the selected asset and release (`Selected asset ... from release ...`) is printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Audacity.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.Audacity`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected (the lines are those that `Win-7Zip` printed in its rehearsal, with this
product's name; NOT seen for this program), also without `-v`, when the current version is
not yet in the repository. `<version>` is the MSI's own version (whether it equals the release's tag is NOT established):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name   Version  Catalogs    Result
    audacity <version>  Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: audacity <version> is in the repository already. Nothing was written.`
instead. That is correct.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Audacity.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Audacity.pcman.recipe

The trust check still reports OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Audacity.pcman.recipe

   Expected: `Published audacity <version>.` and the table

       The following versions were published by the package tool:
       Name   Version  Catalogs    Result
       audacity <version>  Production  published

   The repository now has the MSI under `pkgs/` and its pkginfo under `pkgsinfo/`,
   in the folder of the template. The item file of the template is not changed.

2. `pcman versions audacity` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Not run.) The package tool prints "nothing to run" when its catalogs command is not set.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Audacity.pcman.recipe

   It prints `Nothing new: audacity <version> is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Audacity.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Audacity.pcman.recipe

## g. A share that is not mounted

The rehearsal of `Win-7Zip` used an empty folder as the repository. Its recipe failed
(exit code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written there. Expected here too, not run. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `Audacity` and `PCMAN_TEMPLATE` is `audacity`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- The recipe gives no version label: for an MSI the package tool takes the MSI's own
  version. Whether it equals the release's tag is NOT established. Read what the
  first dry run prints.
- Whether a new release keeps the same UpgradeCode as the template, so that the
  package tool accepts it as the same product, is NOT established. The package
  tool refuses an MSI whose upgrade code differs from the template's: that is
  the correct stop, not a fault of the recipe. Test the first published version on one PC before
  the PCs get it.
- The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which the
  shared importer compares with the file it imports, so it allows a real run of this
  recipe without `pcman_allow_unverified`. The input of the download recipe is
  `SEARCH_PATTERN` (default `audacity-win-[0-9.]+-x86_64\.msi$`): change it in the override's
  `Input`, not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.
- A 3.x installation that was made with the vendor's `.exe` may stay beside the 4.x MSI (the two are different installers; NOT checked). A person looks on a test PC before the PCs get the item, and removes the 3.x program by hand if it stays.
- The `developer` of the Cimian recipe, `Audacity Team`, is the name of the project's team; the publisher that the installer names was NOT read.
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
  Read the `Selected asset` line of every dry run (run it with `-v`).

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares, that no recipe sets `pcman_version` for an MSI,
that the pattern takes the MSI and none of the other assets, that this README
opens with the status line that says what was NOT done, that this README has no `make-override`
without `--override-dir` and runs no recipe by its identifier, and that nothing
site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).

The fixture `tests/releases_excerpt.json` is a cut of the saved list of 2026-11-13 (11 of the 30 releases). The check that the pattern matches exactly one file in each of the three 4.x releases and none in the other 19 was made on all 30 and is written in the status line; the tests repeat it on the cut. The 3.x release on top of the list is made up.
