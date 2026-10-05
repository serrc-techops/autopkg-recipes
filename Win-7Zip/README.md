# Win-7Zip

The first Windows recipe pair: 7-Zip, the 64-bit `.exe`.

**Status.** Rehearsed on 2026-10-01 with AutoPkg 2.9.0 and the real installer in
a scratch repository (a folder with `pkgs/` and `pkgsinfo/`): a dry run, a publish,
"Nothing new", a trust failure (a changed processor) and a missing repository. The first rehearsal was NOT against the real share. On 2026-10-04, under AutoPkg 2.9.0, both recipes of this folder (`7Zip.cimian.recipe` and `7Zip.pcman.recipe`) ran as a dry run, the default, against the real repository, whose template had been imported before, and **each ended clean**: the package tool's recipe with `PcmanImporter: Nothing new: 7zip 26.03 is in the repository already.` and the generic recipe with `CimianImporter: Nothing new: 7zip 26.03 is in the repository already (it has this very installer file).` Nothing was written. No real run of this program was made that day, and nothing has been installed on a PC. The lines quoted
below are those that the rehearsal printed; spacing of the tables may differ. After the
rehearsal the pre-release switch moved from the step into the `Input` (2026-10-04): that
form was checked against AutoPkg 2.9.0's source and not run on the build machine. (In the
rehearsal the scratch overrides folder was one of AutoPkg's override folders. On the
build machine the Windows overrides folder is not, so every override command here
carries `--override-dir`: see the next paragraph.)

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `7Zip-Win.download.recipe` | `com.github.serrc-techops.download.7Zip-Win` | Takes the newest non-pre-release of `ip7z/7zip` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match |
| `7Zip.cimian.recipe` | `com.github.serrc-techops.cimian.7Zip` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `7Zip.pcman.recipe` | `com.github.serrc-techops.pcman.7Zip` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `7Zip.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `7Zip.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The shared 7zip-Win64 download recipe is not the parent: its pattern and file
name are for the `.msi`. Neither recipe stops on an unchanged download, so an
import that failed is tried again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/7Zip.cimian.recipe

(For an override that was made before this key existed, use
`Add :Input:include_prereleases bool true` instead.) Keep it a boolean: AutoPkg only
tests whether the value is empty, so the text `false` would count as true. The recipe's
step does not set it, because AutoPkg applies the arguments of a step after the
override's `Input`, and they would beat it.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `7Zip.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

3. **The version label** is the download recipe's `version` (the release tag of the GitHub project), and this recipe passes it on as `%version%`. `CimianImporter` takes it as the label and does not check it against the file: the first dry run shows it, and a person compares it with the version that the installer's own properties show.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `7zip`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the first step of the package tool's way below marks what is only the writer's knowledge or was not read), so they are left for a person who has read them in the vendor's documentation and tried them on a test PC. The first step of the package tool's way below shows `/S` as the command of the rehearsal, and nothing in this folder says that it was run on a PC, so it is not in the recipe either. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i 7Zip-Win
    autopkg list-recipes | grep -i 7Zip.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> 7Zip.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `7Zip.cimian`, not a path. It writes `<the Windows overrides folder>/7Zip.cimian.recipe` with the identifier `local.cimian.7Zip` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.7Zip`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.7Zip`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/7Zip.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `7Zip.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `7Zip.pcman` where this README used to say `7Zip.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `7Zip.cimian.recipe` (when that recipe ran the package tool) must be made again from `7Zip.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `7Zip.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

## a. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in
   AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step b) takes a recipe NAME and refuses
   a path. The rehearsal printed: `make-override doesn't work with absolute recipe
   paths`.

2. **The settings of the processor, as AutoPkg preferences.** One line each:

       defaults write com.github.autopkg pcman_root -string "<the package tool's folder>"
       defaults write com.github.autopkg pcman_python -string "<the package tool's Python>"

   `pcman_python` is only needed when it is not `<the package tool's folder>/.venv/bin/python3`.
   Write the values as strings. The repository is not a setting here: the package
   tool's own configuration says where it is. The repository must be reachable
   (the share mounted).

3. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. The command of the rehearsal, with a real
   installer:

       pcman import <path of 7z2603-x64.exe> --name 7zip --version 26.03 \
           --directory util --install-arguments /S \
           --install-path 'C:\Program Files\7-Zip\7z.exe' --architectures x64 \
           --no-prompt --build

   Add `--display-name`, `--category`, `--developer` and `--description` as the
   package tool's README describes. A person changes the template later; nothing
   else does. **If the template is made from the installer that is current on
   GitHub, the first run says "Nothing new" (see step c). To see a dry run that
   would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i 7Zip-Win
    autopkg list-recipes | grep -i 7Zip.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> 7Zip.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `7Zip.pcman`, not a path. It writes
`<the Windows overrides folder>/7Zip.pcman.recipe` with the identifier
`local.pcman.7Zip` and the trust information of the two recipes and the three
processors. **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.7Zip`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name. (No collision is known: the shared recipe `7zip-Win64.download` has another name.)

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.7Zip`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current version is not yet in the
repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name   Version  Catalogs    Result
    7zip   26.03    Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: 7zip 26.03 is in the repository already. Nothing was written.`
instead. That is correct.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/7Zip.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.pcman.recipe

The trust check still reports OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.pcman.recipe

   Expected: `Published 7zip 26.03.` and the table

       The following versions were published by the package tool:
       Name   Version  Catalogs    Result
       7zip   26.03    Production  published

   The repository now has `pkgs/util/7zip-26.03.exe` and
   `pkgsinfo/util/7zip-26.03.yaml`. The item file of the template is not changed.

2. `pcman versions 7zip` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (On 2026-10-04 `pcman catalogs` ran once for other programs' new items: the tool's configured command ran `makecatalogs` on the repository's server and wrote the catalogs `All` and `Production`, with exit 0. It has not been run for this program. The package tool prints "nothing to run" when its catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.pcman.recipe

   It prints `Nothing new: 7zip 26.03 is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.pcman.recipe

## g. A share that is not mounted

The rehearsal used an empty folder as the repository. The recipe failed (exit
code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written; the folder stayed empty. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `7Zip` and `PCMAN_TEMPLATE` is `7zip`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares, that this README has no `make-override`
without `--override-dir` and runs no recipe by its identifier, and that nothing
site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
