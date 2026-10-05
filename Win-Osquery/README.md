# Win-Osquery

A Windows recipe pair: osquery, the `.msi` (the only MSI in each of the six releases that were read, so presumably the x64 package: the ARM64 build is published as a zip).

**Status. On 2026-10-04, under AutoPkg 2.9.0, both recipes of this folder (`Osquery.cimian.recipe` and `Osquery.pcman.recipe`) ran as a dry run, the default, against the real repository, whose template had been imported before, and **each ended clean**: the package tool's recipe with `PcmanImporter: Nothing new: osquery 5.23.1 is in the repository already.` and the generic recipe with `CimianImporter: Nothing new: osquery 5.23.1 is in the repository already (it has this very installer file).` Nothing was written. No real run of this program was made that day, and nothing has been installed on a PC. The facts of the source were read by the writer on 2026-10-04 from GitHub's public API (read only, no file was downloaded): the release list (`https://api.github.com/repos/osquery/osquery/releases`, the newest six releases) and the record of one asset (`https://api.github.com/repos/osquery/osquery/releases/assets/<id>` of the MSI of `5.23.1`, the kind of address that `GitHubAssetDigest` reads). READ: (1) `osquery/osquery` publishes its releases there; the newest six (`5.23.1`, `5.23.0`, `5.22.1`, `5.21.0`, `5.20.0` and `5.19.0`) have plain numbers as tags, without a `v`, and none is flagged as a pre-release; (2) each has 17 assets and exactly one of them is an MSI, named `osquery-<version>.msi` (`osquery-5.23.1.msi`, 19984384 bytes); the pattern `osquery-[0-9.]+\.msi$` matches that file and none of the others; the other Windows files are `osquery-<version>.windows_x86_64.zip` and `osquery-<version>.windows_arm64.zip`, and there is a NuGet package `osquery.<version>.nupkg`; there is no arm64 MSI in these six releases, so the one MSI cannot be confused with one; AutoPkg 2.9.0 takes the first release (in GitHub's order, newest first, a pre-release skipped) that has a file whose name the pattern matches from its start (`GitHubReleasesInfoProvider.py`, `select_asset`, `re.match`); the test file writes that down as a function, and run on the saved list it takes `osquery-5.23.1.msi` of `5.23.1`; (3) GitHub records a SHA-256 digest for every asset of all six releases, and the record of the MSI of `5.23.1`, fetched anonymously as `GitHubAssetDigest` does it, holds one (`sha256:` and 64 hex digits); (4) the tag is a plain number, so `version` would be `5.23.1`; the recipe does not pass it on, because for an MSI the package tool takes the MSI's own version. NOT established: that the MSI is x64 (its name carries no architecture; it is the one MSI beside an x86_64 zip and an arm64 zip, and nobody opened it); that a newer release has the same UpgradeCode as the template; the silent switch of the MSI on a PC. The steps and the lines quoted below are those of the rehearsal of `../Win-7Zip/`, which is another program: they show the shape of a run, and what this recipe printed on 2026-10-04 is given above. When a run fails: stop. Nothing was written. Read the real release page and the real asset list, correct the recipe, and never the trust information first. Every override command here carries `--override-dir`: see the next paragraph.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Osquery-Win.download.recipe` | `com.github.serrc-techops.download.Osquery-Win` | Takes the newest non-pre-release of `osquery/osquery` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match |
| `Osquery.cimian.recipe` | `com.github.serrc-techops.cimian.Osquery` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `Osquery.pcman.recipe` | `com.github.serrc-techops.pcman.Osquery` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `Osquery.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `Osquery.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The recipe gives no version label to the package tool: for an MSI the tool takes
the MSI's own version. Neither recipe stops on an unchanged download, so an
import that failed is tried again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/Osquery.cimian.recipe

(For an override that was made before this key existed, use
`Add :Input:include_prereleases bool true` instead.) Keep it a boolean: AutoPkg only
tests whether the value is empty, so the text `false` would count as true. The recipe's
step does not set it, because AutoPkg applies the arguments of a step after the
override's `Input`, and they would beat it.

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

This way needs AutoPkg, `msiinfo` (msitools: `brew install msitools`) for the MSI, and nothing of the owner's: no package tool. It uses `Osquery.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `osquery`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **For an `.msi` nothing needs completing for a silent install:** the client runs `msiexec /i <file> /qn /norestart` itself and then the arguments of the item (`InstallerService.cs:936-948`), so the recipe gives no silent arguments, and `CimianImporter` writes the install check of an MSI (an `installs` entry of type `msi` with the MSI's codes and version). What the MSI's own properties allow (features, per-user or per-machine) is the template's business: give them as `installer: {args: [...]}` in the override's `pkginfo`. An MSI whose upgrade code is not the template's, or that has none where the template's item had one, is refused (Windows Installer does not upgrade across upgrade codes): `cimian_allow_product_change` set to true in the override allows it, with a WARNING.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i Osquery-Win
    autopkg list-recipes | grep -i Osquery.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Osquery.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `Osquery.cimian`, not a path. It writes `<the Windows overrides folder>/Osquery.cimian.recipe` with the identifier `local.cimian.Osquery` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.Osquery`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.Osquery`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.msi (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/Osquery.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `Osquery.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `Osquery.pcman` where this README used to say `Osquery.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `Osquery.cimian.recipe` (when that recipe ran the package tool) must be made again from `Osquery.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `Osquery.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   (the share mounted). For an MSI the tool needs `msiinfo` on its `PATH`.

3. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. If the repository has no item named `osquery`,
   make it once with this import, from a real MSI of osquery; if it has one, do not
   run the command. The command:

       pcman import <path of osquery-5.23.1.msi> --name osquery \
           --directory <the folder of the item> --architectures x64 \
           --display-name osquery --category <the category> \
           --developer <the developer> --description <one line> \
           --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. There
   is no `--install-arguments`: the package tool knows the arguments of an MSI
   (`/qn`; from the writer's knowledge, not read in the tool's code), so check on
   this first import that the pkginfo it wrote installs the MSI silently.
   `--architectures x64` is an expectation, not a fact: nobody opened the MSI, so its
   architecture is NOT established (see the status line); read it in the MSI before the
   import. The values of `--category`, `--developer` and `--description` are the owner's: see
   the package tool's README for the flags. What the template does about the
   osquery service and about its enrollment is the template's business, not the
   recipe's. A person changes the template later; nothing else does. **If the
   template is made from the release that is current on GitHub, the first run
   says "Nothing new" (see step c). To see a dry run that would publish, make the
   template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Osquery-Win
    autopkg list-recipes | grep -i Osquery.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Osquery.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Osquery.pcman`, not a path. It writes
`<the Windows overrides folder>/Osquery.pcman.recipe` with the identifier
`local.pcman.Osquery` and the trust information of the two recipes and the four
processors. **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Osquery`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.Osquery`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected (the shape from the rehearsal of Win-7Zip, NOT seen for this recipe),
also without `-v`, when the current version is not yet in the repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name      Version    Catalogs    Result
    osquery   5.23.1  Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: osquery 5.23.1 is in the repository already. Nothing was written.`
instead. That is correct.

If the run stops before this, with an error from `GitHubReleasesInfoProvider`
(no matching asset), from `GitHubNewestReleaseGuard` (the provider went back to an older release) or from `GitHubAssetDigest` (no digest), the status line at the
top applies: nothing was written; read the real release; correct the recipe.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Osquery.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.pcman.recipe

The trust check still reports OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.pcman.recipe

   Expected: `Published osquery 5.23.1.` and a table with the result
   `published`. The repository now has the installer under `pkgs/` and the
   pkginfo under `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions osquery` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (On 2026-10-04 `pcman catalogs` ran once for other programs' new items: the tool's configured command ran `makecatalogs` on the repository's server and wrote the catalogs `All` and `Production`, with exit 0. It has not been run for this program. The package tool prints "nothing to run" when its catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.pcman.recipe

   It prints `Nothing new: osquery 5.23.1 is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.pcman.recipe

## g. A share that is not mounted

The rehearsal of Win-7Zip used an empty folder as the repository. The recipe failed
(exit code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written; the folder stayed empty. Mount the share, then run again.
Here the same line also appears when the template `osquery` was never made (step a, 3).

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `Osquery` and `PCMAN_TEMPLATE` is `osquery`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares, that the asset pattern takes the one MSI of each
release that was read and no other file, that this README has no `make-override` without `--override-dir`
and runs no recipe by its identifier, that its status line says what was NOT done,
and that nothing site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
