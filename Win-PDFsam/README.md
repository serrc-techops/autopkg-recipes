# Win-PDFsam

A Windows recipe pair: PDFsam Basic, the `.msi` of the project `torakiki/pdfsam` on GitHub.

**Status. Changed after the first dry run with AutoPkg 2.9.0, and run again after the change (2026-10-04). The first run (before the change) stopped at `GitHubAssetDigest` with "GitHub asset 202307085: the record has no digest (older assets have none)". That asset was `pdfsam-5.2.9.msi`, a file of October 2024, and not one of the newest release: the pattern of that run, `pdfsam-[0-9.]+\.msi$`, matches no file of any release from `v5.3.0` on, because the project now names its installer `pdfsam-basic-<version>-windows-x64.msi`. AutoPkg 2.9.0 takes the first release (in GitHub's order, newest first, a pre-release skipped) that has a file whose name the pattern matches from its start (`GitHubReleasesInfoProvider.py`, `select_asset`, `re.match`), however old, so it went back to `v5.2.9`. The test file writes that selection down as a function: on the saved list the old pattern takes `pdfsam-5.2.9.msi` and the new one takes the newest. The newest release's MSI does have a digest on GitHub, so the download stays verified. After the change a dry run under AutoPkg 2.9.0 selected `pdfsam-basic-6.0.6-windows-x64.msi` of `v6.0.6` and verified it against GitHub's digest. Later that day the first import with the package tool (the command of step a.3 below, run with `--no-prompt` and `--build`) made the item `pdfsam` (an MSI item, architectures `x64`, the catalog `Production`; the MSI's own version has four parts, the tag `v6.0.6` and a fourth part `0`; its summary says platform `x64` and its Property table has `ALLUSERS=1`), and the real run of the override of `PDFsam.pcman` (`make-override` with `--override-dir`, `ParentRecipe` right, `verify-trust-info` OK, `pcman_dry_run` false) ended with `PcmanImporter: Nothing new: pdfsam <the label> is in the repository already. Nothing was written.` The first import went beside the Chocolatey item `pdfsam` (version 1.0) without any option of the tool; the Chocolatey item file and its `pdfsam-1.0` pkginfo remain until a person removes them by hand, and `pcman validate` warns that the item has two versions until then. `pcman catalogs` ran a second time later on 2026-10-04, after the first imports of this and three other programs: the same command wrote the catalogs `All` and `Production`, 110 items each (106 before), with exit 0, and `Production` lists both versions of this name (the Chocolatey item's `1.0` and the new one). The silent install is the client's (`/qn /norestart` for an MSI) and was NOT tested on a PC; nothing has been installed on a PC. Facts of the source were read by the writer on 2026-10-04 from GitHub's public release list of `torakiki/pdfsam` (`https://api.github.com/repos/torakiki/pdfsam/releases`, the newest 14 releases, `v6.0.6` to `v5.2.9`; read only, no file was downloaded). READ: (1) the newest release that is not a pre-release is `v6.0.6` (published 2026-10-02); `v6.0.0.M1` is flagged as a pre-release and has no MSI; (2) from `v5.3.0` the Windows files of a release are `pdfsam-basic-<version>-windows-x64.msi` and `pdfsam-basic-<version>-windows-x64.zip` (for `v6.0.6`: `pdfsam-basic-6.0.6-windows-x64.msi`, 97030144 bytes), and in `v6.0.6` each has a detached signature file with `.asc` added to its name, which no step checks; up to `v5.2.9` the installer is `pdfsam-<version>.msi`; (3) GitHub records a SHA-256 digest for the MSI of every release from `v5.3.2` (2025-07-24) to `v6.0.6`, and for none of `v5.3.1` (2025-04-18) and older; (4) the pattern is now `pdfsam-basic-[0-9.]+-windows-x64\.msi$`, which takes exactly the MSI of each release from `v5.3.0` to `v6.0.6` that has one, and not the `.zip` or the `.asc`. If a later release has an MSI without a digest, `GitHubAssetDigest` stops the run with its error, nothing is written, and the program is a hand import until a release with a digest exists. NOT established: that the MSI installs silently on a PC; that a new release has the same UpgradeCode as the template; that the next release keeps this spelling of the name (if the project renames the file again, the provider goes back to the newest older release that matches, as it did on 2026-10-04: read the line of the first dry run that names the selected asset and release); that the digest check proves more than that the file is what GitHub holds (the `.asc` signature is not checked); any install on a PC. An install on a test PC is the check of each of them. When a run fails (no asset matches, no digest, an error from the package tool), stop: nothing was written. Read the real release page and the real asset list, correct the recipe (the pattern, the repository, the template name), and only then look at the trust information: never accept trust information to make a failure go away. Where a line below says "expected", it is what the code and the pattern lead to, not something that was printed. Every override command here carries `--override-dir`: see the next paragraph.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `PDFsam-Win.download.recipe` | `com.github.serrc-techops.download.PDFsam-Win` | Takes the newest non-pre-release of `torakiki/pdfsam` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match |
| `PDFsam.cimian.recipe` | `com.github.serrc-techops.cimian.PDFsam` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `PDFsam.pcman.recipe` | `com.github.serrc-techops.pcman.PDFsam` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `PDFsam.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `PDFsam.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

No shared download recipe is the parent. Neither recipe stops on an unchanged
download, so an import that failed is tried again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/PDFsam.cimian.recipe

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

This way needs AutoPkg, `msiinfo` (msitools: `brew install msitools`) for the MSI, and nothing of the owner's: no package tool. It uses `PDFsam.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `pdfsam`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **For an `.msi` nothing needs completing for a silent install:** the client runs `msiexec /i <file> /qn /norestart` itself and then the arguments of the item (`InstallerService.cs:936-948`), so the recipe gives no silent arguments, and `CimianImporter` writes the install check of an MSI (an `installs` entry of type `msi` with the MSI's codes and version). What the MSI's own properties allow (features, per-user or per-machine) is the template's business: give them as `installer: {args: [...]}` in the override's `pkginfo`. An MSI whose upgrade code is not the template's, or that has none where the template's item had one, is refused (Windows Installer does not upgrade across upgrade codes): `cimian_allow_product_change` set to true in the override allows it, with a WARNING.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i PDFsam-Win
    autopkg list-recipes | grep -i PDFsam.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> PDFsam.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `PDFsam.cimian`, not a path. It writes `<the Windows overrides folder>/PDFsam.cimian.recipe` with the identifier `local.cimian.PDFsam` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.PDFsam`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the line of the provider that names the selected asset and release (`Selected asset ... from release ...`) is printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.PDFsam`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.msi (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/PDFsam.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `PDFsam.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `PDFsam.pcman` where this README used to say `PDFsam.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `PDFsam.cimian.recipe` (when that recipe ran the package tool) must be made again from `PDFsam.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `PDFsam.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   it replaces. An item `pdfsam` of the kind `choco` is not the template (see the status line: the
   first import of 2026-10-04 went beside it without any option, and a person removes the Chocolatey item
   by hand). The command, in the form that ran on 2026-10-04 (it worked as written), with a real MSI of the project:

       pcman import <path of the downloaded pdfsam-basic-<version>-windows-x64.msi> --name pdfsam \
           --display-name "PDFsam Basic" --category <the category> \
           --developer <the developer's name> --description <the description> \
           --directory <the folder of the item> --architectures x64 \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version (four parts on 2026-10-04: the tag and a
   fourth part). The install arguments are the package tool's own for an MSI (`/qn /norestart` from the client; not tested
   on a PC): do not add an install path for an MSI unless the package tool's README asks for one. `--architectures x64` is
   from the name of the file (`windows-x64`); the MSI's summary says platform `x64` (read on 2026-10-04).
   Give the category, the developer and the description the package tool's README
   describes. A person changes the template later; nothing else does. **If the
   template is made from the installer that is current on GitHub, the first run says
   "Nothing new" (see step c). To see a dry run that would publish, make the
   template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i PDFsam-Win
    autopkg list-recipes | grep -i PDFsam.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> PDFsam.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `PDFsam.pcman`, not a path. It writes
`<the Windows overrides folder>/PDFsam.pcman.recipe` with the identifier
`local.pcman.PDFsam` and the trust information of the two recipes and the three
processors. **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.PDFsam`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the line of the provider that names the selected asset and release (`Selected asset ... from release ...`) is printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.PDFsam`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected (the lines are those that `Win-7Zip` printed in its rehearsal, with this
product's name; the real run of this recipe on 2026-10-04 printed `Nothing new` as the status line says), also without `-v`, when the current version is
not yet in the repository. `<version>` is the MSI's own version, which has a fourth part beyond the release's tag
(the tag `v6.0.6` gave an MSI version of four parts on 2026-10-04):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name   Version  Catalogs    Result
    pdfsam <version>  Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: pdfsam <version> is in the repository already. Nothing was written.`
instead. That is correct.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/PDFsam.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.pcman.recipe

The trust check still reports OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.pcman.recipe

   Expected: `Published pdfsam <version>.` and the table

       The following versions were published by the package tool:
       Name   Version  Catalogs    Result
       pdfsam <version>  Production  published

   The repository now has the MSI under `pkgs/` and its pkginfo under `pkgsinfo/`,
   in the folder of the template. The item file of the template is not changed.

2. `pcman versions pdfsam` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Run on 2026-10-04: `pcman catalogs` ran twice that day, the second time after the first imports of this and three other programs. The tool's configured command ran `makecatalogs` on the repository's server and wrote the catalogs `All` and `Production`, 110 items each in the second run, with exit 0. The package tool prints "nothing to run" when its catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.pcman.recipe

   It prints `Nothing new: pdfsam <version> is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.pcman.recipe

## g. A share that is not mounted

The rehearsal of `Win-7Zip` used an empty folder as the repository. Its recipe failed
(exit code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written there. Expected here too, not run. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `PDFsam` and `PCMAN_TEMPLATE` is `pdfsam`. Change the
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
  `SEARCH_PATTERN` (default `pdfsam-basic-[0-9.]+-windows-x64\.msi$`): change it in the override's
  `Input`, not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.
- AutoPkg's provider takes the first release, newest first, that has a file whose name
  matches `SEARCH_PATTERN`, however old. When a name changes, the recipe does not stop: it
  goes back. Read the `Selected asset` line of every dry run (run it with `-v`).

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
