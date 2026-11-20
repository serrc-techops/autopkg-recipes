# Win-GCPW

A Windows recipe pair: Google Credential Provider for Windows (GCPW), the 64-bit enterprise `.msi`.

**Status. Run on 2026-10-04 under AutoPkg 2.9.0, as follows. No item with the GCPW installer existed in the package tool's repository, so the first import (the command of step a.3 below, run with `--no-prompt` and `--build`) made the item `gcpw` (an MSI item, version `150.0.7871.100` read from the MSI, architectures `x64`, no icon because the repository had none for it) in the catalog `Production`; `gcpw` was the right name, and the override needed no change of `PCMAN_TEMPLATE`. The override of `GCPW.pcman` (`make-override` with `--override-dir`, `ParentRecipe` right, `verify-trust-info` OK, `pcman_dry_run` false) then ran for real: the download went through, and the importer REFUSED the run with `The download was not verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file. Nothing was published. ...` (exit 70), which is what an unverified download must get; `pcman_allow_unverified` was not set. The override downloaded the file again about ten minutes after the first import, and its hash was the imported file's. The hand-import form `pcman import <file> --template gcpw --no-prompt --if-new --dry-run` printed `Nothing new: gcpw <version> exists already ...` with exit 3. `pcman catalogs` ran once for all the new items together (2026-10-04): the tool's configured command ran `makecatalogs` on the repository's server, with exit 0, and wrote the catalogs `All` and `Production`, 106 items each. The MSI's own upgrade code was read at the import; the silent install is the client's (`/qn /norestart` for an MSI) and was NOT tested on a PC. Still NOT established after those runs: that the MSI installs silently on a PC; any install. Some facts of the source were fetched by the writer on 2026-10-02, before those runs: Read from Google's server on that day: (1) `https://dl.google.com/credentialprovider/gcpwstandaloneenterprise64.msi` answered 200 with no redirect, 47382528 bytes, last modified 2026-10-02 08:45 GMT; (2) the 32-bit file beside it, `gcpwstandaloneenterprise.msi`, is 25264128 bytes; the recipe takes the 64-bit file only, kept under the file name of the address. NOT established: that Google publishes no hash for this file and that no signature check exists for it (the writer knows of none); that Google's server answers the questions that AutoPkg asks about a changed file (a last-modified date was seen, nothing else was looked at); the silent install of the MSI on a PC. The first install on a test PC is the check of what is NOT established. When a run fails, STOP: nothing was written (a run that fails before the import writes nothing). Read the real address in a browser, correct the recipe, and only then look at the trust information. Never accept new trust information first to make a failure go away.**

**Not verified. The download is NOT verified: Google publishes no hash for the file, and the shared signature check (`AuthenticodeVerifier`) is not part of this recipe. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true. Do not set it before a signature check is part of this recipe. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template gcpw` (no `--version` for an MSI; use the real item name when it is not `gcpw`). A real run of this recipe was REFUSED on 2026-10-04 (see the status line above), and nothing has been installed on a PC. The Windows overrides folder is not one of AutoPkg's override folders, so every override command here carries `--override-dir`: see the paragraph below.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `GCPW-Win.download.recipe` | `com.github.serrc-techops.download.GCPW-Win` | Downloads the Google Credential Provider for Windows enterprise installer that Google serves at a fixed address (the 64-bit MSI), kept under the file name of the address. It has no hard check |
| `GCPW.cimian.recipe` | `com.github.serrc-techops.cimian.GCPW` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `GCPW.pcman.recipe` | `com.github.serrc-techops.pcman.GCPW` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `GCPW.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `GCPW.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

Why this installer is imported: items that configure GCPW need the installer
item, and this pair imports it with a dry run, a trust check and a record.

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What protects, and what does not

Nothing proves that the downloaded file is what Google published: there is no vendor
hash, and the shared signature check (`AuthenticodeVerifier`) is not part of this recipe. The shared importer knows this: no step of
the recipe sets `checksum_verified` with the hash of the file, so a real run is refused
before the package tool starts. Two checks of the package tool remain. They do not
replace a verification.

- **The same product.** The package tool refuses an MSI whose upgrade code
  differs from the template's. So another product cannot be published under the
  name of this template.
- **The label.** The recipe gives no version label. For an MSI the package tool
  takes the MSI's own ProductVersion and refuses a label that is not the MSI's
  own version.

An MSI of the right product with other content (a changed file of the vendor, or a
changed download on the way) would pass both checks.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg, `msiinfo` (msitools: `brew install msitools`) for the MSI, and nothing of the owner's: no package tool. It uses `GCPW.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

An override that was made from this recipe before the recipes were separated from the package tool belongs to the package tool's way: see the paragraph at the start of that section.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `InstallerService.cs:936`) are from `windowsadmins/cimian` at commit `e10498b`, read on 2026-10-04 and not checked against a later version.

**The download of this program is NOT verified** (see the status line above, which speaks of `pcman_allow_unverified` for the package tool's way). For this way the same rule holds with the input `cimian_allow_unverified`: `CimianImporter` REFUSES a real run of a download that no step verified (nothing is published) unless the override sets `cimian_allow_unverified` to true. Do not set it before a verification step exists. A dry run is allowed, and prints a `WARNING: the download was NOT verified` line.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **`msiinfo` on the PATH of the run** (`brew install msitools`): `CimianImporter` reads the MSI's ProductVersion and its two codes with it, and does not parse an MSI itself. A job that `launchd` starts may have no Homebrew on its `PATH`, so the importer looks in `/opt/homebrew/bin` and `/usr/local/bin` too; the input `cimian_path` changes that list. This recipe cannot run without it: its step passes an empty `version` (so that a release tag is not taken for the MSI's own version), and an argument of a step wins over an override's `Input`, so the label can only come from the MSI. The run stops and names the facts that are missing.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `gcpw` (the name of the item that the first import of 2026-10-04 made; no GCPW item existed before). If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **For an `.msi` nothing needs completing for a silent install:** the client runs `msiexec /i <file> /qn /norestart` itself and then the arguments of the item (`InstallerService.cs:936-948`), so the recipe gives no silent arguments, and `CimianImporter` writes the install check of an MSI (an `installs` entry of type `msi` with the MSI's codes and version). What the MSI's own properties allow (features, per-user or per-machine) is the template's business: give them as `installer: {args: [...]}` in the override's `pkginfo`. An MSI whose upgrade code is not the template's, or that has none where the template's item had one, is refused (Windows Installer does not upgrade across upgrade codes): `cimian_allow_product_change` set to true in the override allows it, with a WARNING.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i GCPW-Win
    autopkg list-recipes | grep -i GCPW.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> GCPW.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `GCPW.cimian`, not a path. It writes `<the Windows overrides folder>/GCPW.cimian.recipe` with the identifier `local.cimian.GCPW` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.GCPW`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.GCPW`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.msi (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on (NOT YET: see the status line)

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/GCPW.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

**Not yet.** This download has no verification step, so `CimianImporter` refuses the real run below until the override also sets `cimian_allow_unverified` to true, which a person decides only after the file was checked by hand, and which is then written in the override's `Input`, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_allow_unverified bool true' \
        <the Windows overrides folder>/GCPW.cimian.recipe

With it the run prints `WARNING: published WITHOUT a verified download` and the report row says `published, NOT verified`.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `GCPW.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `GCPW.pcman` where this README used to say `GCPW.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `GCPW.cimian.recipe` (when that recipe ran the package tool) must be made again from `GCPW.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `GCPW.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   (the share mounted). For an MSI the package tool needs `msiinfo` (the processor
   looks for it in its default `PATH`, which has the Homebrew folders).

3. **The template item.** An item whose installer is the GCPW MSI may exist already
   (imported by hand, say). On 2026-10-04 none existed, and the first import below made `gcpw`, the name
   that the recipe has. Find out first whether one exists now:
   run `pcman versions <a name>` for the candidates, or look in the repository
   for the item whose pkginfo has the GCPW MSI as its installer. If it exists, do
   not make a second item: set its name in the override (step b). Only when no such item exists, make the template by a first import, so that
   its pkginfo and installer are in the repository. The template keeps the name of
   the item that it replaces. The command, with a real MSI:

       pcman import <path of the MSI> --name gcpw \
           --display-name "Google Credential Provider for Windows" --category <the category of the item> \
           --developer "Google" --description "<one line about the item>" \
           --directory <the folder of the item> --architectures x64 --no-prompt --build

   This is the form that ran on 2026-10-04 (it worked as written). There is no `--version`: the package tool takes the MSI's own version
   (`150.0.7871.100` on that day). The install arguments are not given: for an MSI the client runs `msiexec /i <file> /qn /norestart`
   itself (not tested on a PC). No icon was given because the repository had none for this item; add one with `--icon <the file name of an icon that the repository has>`
   as the package tool's README describes. A person changes the template
   later; nothing else does. **If the template is made from the installer that is
   current at the vendor, the first run says "Nothing new" (see step c). To see a
   dry run that would publish, make the template from an older version.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i GCPW-Win
    autopkg list-recipes | grep -i GCPW.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> GCPW.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `GCPW.pcman`, not a path. Expected: it
writes `<the Windows overrides folder>/GCPW.pcman.recipe` with the identifier
`local.pcman.GCPW` and the trust information of the two recipes and of the
one processor that is not part of AutoPkg itself (`PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.GCPW`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

**The template name.** `PCMAN_TEMPLATE` in the recipe is `gcpw`, the name of the item that the first import of 2026-10-04
made, and the override of that day needed no change of it. When the
real item has another name (step a.3), set it in the override, not in the recipe, and
check the trust information again (a change of the `Input` does not break trust):

    /usr/libexec/PlistBuddy -c 'Set :Input:PCMAN_TEMPLATE <the name of the item>' \
        <the Windows overrides folder>/GCPW.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW.pcman.recipe

`make-override` writes `Input` as the merged inputs of the recipe chain, so `:Input:PCMAN_TEMPLATE` exists in the written override and `Set` is the right command (read in the source of AutoPkg 2.9.0, `make_override`, on 2026-10-02; not run for this recipe).
A dry run with a template name that is not in the repository stops with the
line of step g.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.GCPW`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current version is not yet in the
repository (the lines of the 7-Zip rehearsal, with this program's name; they were
NOT seen for this recipe, and the version is the MSI's own):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file, or signature_verified together with the signature_sha256 of this file. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name   Version  Catalogs    Result
    gcpw   <the MSI's own version>  Production  dry run, nothing written, NOT verified

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line is
`Nothing new: ... is in the repository already. Nothing was written.` instead.
That is correct.

## d. Switch a real run on (NOT YET: see the second paragraph at the top)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file, or signature_verified together with the
    signature_sha256 of this file. Nothing was published. Publish by hand after checking
    the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template gcpw

Do not add `--version` for an MSI: the package tool takes the MSI's own version. Then
`pcman catalogs` (step e.3).

**Only after the signature check exists, or when a person has decided to accept an
unverified download:** the override allows it. Both lines are needed.

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/GCPW.pcman.recipe
    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_allow_unverified bool true' \
        <the Windows overrides folder>/GCPW.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW.pcman.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip). Do not use `-k`
instead: on the command line it applies to every recipe of that run. A run then prints
`WARNING: published WITHOUT a verified download ...` at any verbosity, and the report's
row says `published, NOT verified`.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW.pcman.recipe

   Only after both lines of step d. Expected: `Published gcpw ...`, the warning
   `published WITHOUT a verified download`, and the table

       The following versions were published by the package tool:
       Name   Version  Catalogs    Result
       gcpw   <the MSI's own version>  Production  published, NOT verified

   The repository then has the MSI under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions gcpw` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.` (On 2026-10-04 the first run of a fresh override printed the line `Nothing new: ...` after it had downloaded the file again, because a new override gets a new cache folder; `Nothing downloaded, packaged or imported.` was not seen in that run, and is the line of a later run of the same override.)

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GCPW.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The 32-bit installer, `gcpwstandaloneenterprise.msi` beside the 64-bit one, is not taken: a PC
  that needs it is not served by this pair.
- Google replaces the file at the same address without a new address (the file was
  last modified on 2026-10-02 when it was read). AutoPkg asks the server whether the
  file changed; whether this server answers that question is NOT established. If
  every run downloads the whole file, that is the reason. The package tool decides by
  the file's hash and the MSI's version.
- If the address answers "not found" or "access denied", Google moved the file. Read
  Google's page for GCPW in a browser, then correct the recipe.
- The file is about 45 MB (47382528 bytes on 2026-10-02). The processor waits 30 minutes
  by default (`pcman_timeout`), which is a limit for the copy to the share.
- Whether the MSI's own ProductVersion is the number that Google's pages call the version
  of GCPW is NOT established. The first dry run shows it.
- The recipe's `NAME` is `GCPW` and `PCMAN_TEMPLATE` is `gcpw` (the item that the first import made). Change
  the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that the Description of both recipes
and the top of this README say that the download is not verified, that a real run is
refused, and that nothing was rehearsed and what was fetched, that this README states no hash, that every
argument is an input that the shared processor declares, that the address is the 64-bit
enterprise MSI and its file name ends in `.msi`, that no recipe sets
`pcman_version` for an MSI, that this README has no `make-override` without
`--override-dir` and runs no recipe by its identifier, and that nothing
site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
