# Win-Acellus

A Windows recipe set: Acellus, a Microsoft Store application (Store product `9NXWFBJHRXKC`, package `GoldKeyCorporation.Acellus`), taken from the Store's own package without the Store.

**Status. New, and not rehearsed (written 2026-11-13). Nothing of this folder has run under AutoPkg, no file was downloaded for it and nothing was installed on a PC with it. The processor `MicrosoftStorePackageDownloader` has never run under AutoPkg and has never contacted Microsoft's delivery service. READ on 2026-11-13 from the Store's catalog record of the product (`https://displaycatalog.mp.microsoft.com/v7.0/products/9NXWFBJHRXKC`, market `US`, language `en-us`; read once, no file downloaded): the title `Acellus`; the publisher `GoldKey Corporation` (the record's developer name is empty); two SKUs that name the same one package, `GoldKeyCorporation.Acellus_2026.1028.1836.0_neutral_~_v2rn50m687qry`, a `.msixbundle` of 88033841 bytes at most, free, for x86 and x64; one framework dependency, `Microsoft.WindowsAppRuntime.1.4`, minimum version 4000.1309.2056.0. READ from the record of a stand-alone tool with the same protocol, which fetched that bundle on 2026-11-10 and was tested on a Windows 11 test PC that day: the package family is `GoldKeyCorporation.Acellus_v2rn50m687qry`; the bundle's version was 2026.1028.1836.0, 88033841 bytes. That is the BUNDLE's version, which looks like a date; the application inside it was version 40.0.22 (with a fourth part 0). Windows reports the bundle's version for the provisioned package (`Get-AppxProvisionedPackage`) and the application's for a user's package (`Get-AppxPackage`): compare each with its own. The bundle is signed by the Store, so no certificate and no sideloading setting are needed (seen on the test PC). The application's manifest asks for the Windows App Runtime 1.4 framework, version 4000.1136.2333.0 or later; the catalog pairs it with 4000.1309.2056.0. On the test PC a script provisioned the bundle with the framework in about 35 s, and a user with a disconnected session moved to the new version without signing in again. That test ran a script, NOT the Cimian client. The vendor offers no other download (its own page for the Windows app led to a missing file in 2026-11): the Store package is the source. The framework is NOT fetched by this recipe: the item needs a `requires` on a framework item that the repository must hold (see "What a person completes by hand"), and the download step prints the framework dependencies with their minimum versions at every run: compare that line with the framework item at every new version. NOT established: an install through the Cimian client; a user with Acellus open during the install; Windows 10; ARM; whether the x64 framework alone is enough (the tested script provisioned the x64 and the x86 framework); that the delivery service answers the processor as it answered the stand-alone tool; that its file hosts are under the default `store_file_host_suffixes` (assumed by the processor, not read). The first dry run is the test. It can stop in four ways, each with nothing written: a refused file host (the message names the host: a person checks that the host is Microsoft's, and only then corrects `store_file_host_suffixes` in the override); the delivery service offers no file; no offered file has the catalog's SHA-256; the catalog names more than one package. When a run stops, read the error and correct the recipe or the override; never accept trust information to make a failure go away. Every command of this README carries `--override-dir`.**

**Results of 2026-11-13, newer than the status above; where the two differ, this paragraph holds.** Under AutoPkg 2.9.0, into a scratch Cimian repository with a hand-made first pkginfo of the item (`make-override` with `--override-dir`, `verify-trust-info` OK, a dry run, a real run, a second real run): the real run published `Acellus-2026.1028.1836.0.msixbundle`, and the second run said that nothing is new. The catalog's SHA-256 matched the file; the run reported that the bundle needs `Microsoft.WindowsAppRuntime.1.4` 4000.1309.2056.0 or later; a later run took the file from the cache without a new download. The bundle was NOT installed on a PC in this run.

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Acellus-Win.download.recipe` | `com.github.serrc-techops.download.Acellus-Win` | Reads the Store's catalog record of `STORE_PRODUCT_ID`, asks Microsoft's delivery service for the package's file and downloads it under the package's full name. Checks it against the SHA-256 that the catalog gives and stops when the file does not match |
| `Acellus.cimian.recipe` | `com.github.serrc-techops.cimian.Acellus` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `Acellus.pcman.recipe` | `com.github.serrc-techops.pcman.Acellus` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `Acellus.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `Acellus.pcman.recipe` is the package tool's way, with `PcmanImporter`. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

No shared download recipe is the parent. Neither recipe stops on an unchanged
download, so an import that failed is tried again at the next run. "Nothing new" is decided by the importers from the package's own version (and its SHA-256); the download step does not ask the delivery service when the recipe's cache already holds the file with the catalog's SHA-256 (it reads the catalog at every run). The processors are in `../Win-SharedProcessors/` (`MicrosoftStorePackageDownloader`, `CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

**The file hosts.** The delivery service gives the addresses of the package's file. The download step uses an address only when its host is under one of the suffixes of the input `store_file_host_suffixes` (default, in the processor: `.dl.delivery.mp.microsoft.com` and `.microsoft.com`; assumed by the processor, not read). A refused address stops the run and its message names the host. Then a person checks that the host is Microsoft's, and only then sets the input in the override, never in the recipe, as one text with commas that keeps the two defaults:

    /usr/libexec/PlistBuddy -c 'Add :Input:store_file_host_suffixes string .dl.delivery.mp.microsoft.com,.microsoft.com,<the suffix that was checked>' \
        <the Windows overrides folder>/Acellus.cimian.recipe

(The same for `Acellus.pcman.recipe`.) The recipe's step does not set it, because AutoPkg applies the arguments of a step after the
override's `Input`, and they would beat it. The file is accepted only on the catalog's SHA-256, whatever its host.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01 for another recipe of this repository: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool, and no `msiinfo` (the importer reads the package itself). It uses `Acellus.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, what it reads from an app package, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

**The client's install.** The Cimian client installs an app package itself, for every user of the PC, with `Add-AppxProvisionedPackage -Online -PackagePath <file> -SkipLicense`, and takes no install arguments. The pkginfo's `installs` entry of type `msix` (the identity name and the version) is the install check. Both are read in `CimianImporter`'s README, which cites `InstallerService.cs`, `BuildMsixInstallScript`; that client code was not read for this folder.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **The framework item.** An item of its own in the repository that installs the Windows App Runtime 1.4 framework, at least the version that the download step prints. This recipe does not make it (see "What a person completes by hand" below).

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `Acellus` (with a capital A: the name that packagers of this program are likely to have given it; the override sets the repository's own name if it differs). If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: its catalogs, its `requires`, its scripts and its checks are carried into the new version, and the version of its `msix` `installs` entry is set to the package's. Its identity name must be `GoldKeyCorporation.Acellus`: a package with another identity name is refused as another product. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`, with one `installs` entry of type `msix`; that pkginfo is then the template of every later version. A bundle names no architecture, so nothing is guessed for it: if the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`). The recipe's `developer`, `GoldKey Corporation`, is the publisher that the Store's catalog names; the catalog's developer name is empty.

   **What a person completes by hand for an app package.** Nothing for a silent install: the client takes no arguments for it, and an app package refuses `installer.args`, `switches`, `flags`, `subcommand`, `success_codes`, `product_code` and `upgrade_code`. But the framework:

   - **Make the framework item once**, before the first real run: an `msix` item of its own, from Microsoft's redistributable `https://aka.ms/windowsappsdk/1.4/latest/Microsoft.WindowsAppRuntime.Redist.1.4.zip`, which holds the framework package under `MSIX/win10-x64/` (and `MSIX/win10-x86/`). Its version must be at least the minimum that the download step prints. The stand-alone tool of 2026-11-10 used that redistributable at version 1.4.240802001, whose framework package has the version 4000.1309.2056.0 (read in its record, not checked here).
   - **Give the item a `requires` on it**: the template's `requires: [<the framework item>]`, or, before the first publish (no template yet), the override's `pkginfo`:

         /usr/libexec/PlistBuddy -c 'Add :Input:pkginfo:requires array' \
             -c 'Add :Input:pkginfo:requires:0 string <the framework item>' \
             <the Windows overrides folder>/Acellus.cimian.recipe

     A template's `requires` is carried into each new version.
   - **At every new version, compare the line that the download step prints** (`needs Microsoft.WindowsAppRuntime.1.4 <minimum> or later`) with the framework item. When it names a higher minimum of the same runtime, publish a newer version of the framework item from the redistributable first, build the catalogs, and only then let the real run of this recipe publish Acellus. When it names another runtime (another name than `Microsoft.WindowsAppRuntime.1.4`), make a new framework item from that runtime's redistributable and change the `requires` of the item's newest pkginfo to it by hand. Until then keep the override in the dry run (`cimian_dry_run` true): the package does not install without its framework.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i Acellus-Win
    autopkg list-recipes | grep -i Acellus.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Acellus.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `Acellus.cimian`, not a path. It writes `<the Windows overrides folder>/Acellus.cimian.recipe` with the identifier `local.cimian.Acellus` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.Acellus`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the download step's line about the cache or the download is printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Acellus.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.Acellus`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

The download step downloads the bundle (about 88 MB) also in a dry run: only the import is dry. Expected (the lines that the processors print, read in their code and tests and, for `CimianImporter`, seen with a made-up bundle in a temporary repository; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each). The download step, also without `-v`:

    Acellus: GoldKeyCorporation.Acellus_<version>_neutral_~_v2rn50m687qry (<size> bytes at most)
      needs Microsoft.WindowsAppRuntime.1.4 <minimum> or later

and with `-v` either `Downloaded and matched the catalog's SHA-256 <hash>` or `The package with the catalog's SHA-256 is in the cache; the delivery service was not asked.` Then the import, also without `-v`:

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.msixbundle (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).
    NOTE: read from the bundle: identity name GoldKeyCorporation.Acellus, version <version> (the bundle's own version, not the application's).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. `<version>` is the bundle's version (2026.1028.1836.0 in the catalog of 2026-11-13). The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (...). Nothing was written.` instead. That is correct. If the repository has no item of this name, the third line is `No template: the pkginfo is built from the inputs.`

Compare the `needs` line with the framework item now (see step 1.4). If the run stops before the import, with an error from the download recipe's steps, nothing was written: read the error (the status line lists the four ways), and correct the recipe or the override, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/Acellus.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Acellus.cimian.recipe

Only once the framework item is in the repository and the item has its `requires` (step 1.4). The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Acellus.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the bundle under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`, with `installer.type: msix` and one `installs` entry `{type: msix, identity_name: GoldKeyCorporation.Acellus, version: <version>}`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Acellus.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (...). Nothing was written.` The download step uses the file in the cache and does not ask the delivery service.

4. **Install on one test PC through the Cimian client before the PCs get it.** That has never been done for this program (see the status line).

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Acellus.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Acellus.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `Acellus.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `Acellus.pcman` where the section above says `Acellus.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool, `Acellus` (the override sets the repository's own name if it differs). The package tool imports an app package as an item of the kind `msix`, reads the identity name and the version from the package itself, and writes the item's `dependencies` as the pkginfo's `requires` (its README, "`kind: msix`").

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
   (the share mounted). An app package needs no `msiinfo`.

3. **The framework item**, an `msix` item of its own made from Microsoft's redistributable (see "What a person completes by hand" in the section above: the same rules). This recipe does not make it.

4. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. The template keeps the name of the item that
   it replaces. An old item `Acellus` of another kind (a script item, say) is not the template: a person decides what happens to it. The bundle for the first import: run the dry run of step c once; the download step keeps the bundle in the recipe's cache (`downloads/` of AutoPkg's `RECIPE_CACHE_DIR` for the override), and the import step then stops, because the template is not there yet. The command (the form of the package tool's README; NOT run for this program):

       pcman import <path of the downloaded GoldKeyCorporation.Acellus_<version>_neutral_~_v2rn50m687qry.msixbundle> --name Acellus \
           --display-name "Acellus" --category <the category> \
           --developer <the developer's name> --description <the description> \
           --directory <the folder of the item> --dependencies <the framework item> \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   There is no `--version`: the package tool takes the package's own version, the bundle's (2026.1028.1836.0 in the catalog of 2026-11-13). There is no `--architectures`: a bundle names none, and the package tool sets none for a bundle (the catalog lists x86 and x64). There are no install arguments: the client takes none for an app package.
   Give the category, the developer (the catalog's publisher is `GoldKey Corporation`) and the description the package tool's README
   describes. A person changes the template later; nothing else does. **If the
   template is made from the package that is current in the Store, the first run says
   "Nothing new" (see step c).** The catalog names only its current package, so there is no older one to make a template from.

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Acellus-Win
    autopkg list-recipes | grep -i Acellus.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Acellus.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Acellus.pcman`, not a path. It writes
`<the Windows overrides folder>/Acellus.pcman.recipe` with the identifier
`local.pcman.Acellus` and the trust information of the two recipes and the three
processors. **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Acellus`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the download step's line about the cache or the download is printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Acellus.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.Acellus`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, after the download step's lines (see step 3 above): the lines that `Win-7Zip`
printed in its rehearsal, with this product's name (NOT seen for this program), also without `-v`, when the current version is
not yet in the repository. `<version>` is the bundle's version:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name   Version  Catalogs    Result
    Acellus <version>  <the template's catalogs>  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: Acellus <version> is in the repository already. Nothing was written.`
instead. That is correct. A package whose identity name is not the template's is
refused by the package tool: that is the correct stop.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Acellus.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Acellus.pcman.recipe

The trust check still reports OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Acellus.pcman.recipe

   Expected: `Published Acellus <version>.` and the table

       The following versions were published by the package tool:
       Name   Version  Catalogs    Result
       Acellus <version>  <the template's catalogs>  published

   The repository now has the bundle under `pkgs/` and its pkginfo under `pkgsinfo/`,
   in the folder of the template. The item file of the template is not changed.

2. `pcman versions Acellus` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Not run.) The package tool prints "nothing to run" when its catalogs command is not set.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Acellus.pcman.recipe

   It prints `Nothing new: Acellus <version> is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Acellus.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Acellus.pcman.recipe

## g. A share that is not mounted

The rehearsal of `Win-7Zip` used an empty folder as the repository. Its recipe failed
(exit code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written there. Expected here too, not run. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the package's full name and the framework lines of the
  download step, the dry-run warning, "Nothing new", "Published", and the importer's NOTE
  and WARNING lines. `-vv` also prints `pcman_root` and the repository: keep that log private.
- The recipe's `NAME` is `Acellus`, `PCMAN_TEMPLATE` and `CIMIAN_NAME` are `Acellus`. Change the
  item's name in the override's `Input`, not in the recipe.
- The recipes give no version label: the importers take the package's own Identity Version,
  which for this bundle is the bundle's version (2026.1028.1836.0 on 2026-11-13), not the
  application's. The download step's output `store_package_version` is the same four numbers,
  read from the full name; no step passes it on as a label.
- The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which the
  importers compare with the file they import, so it allows a real run of this
  recipe without `pcman_allow_unverified` or `cimian_allow_unverified`. The SHA-256 is the
  one of the Store's catalog, read over verified TLS. The package's signature is not checked
  on the Mac: Windows checks it when it adds the package.
- The inputs of the download recipe are `STORE_PRODUCT_ID` (`9NXWFBJHRXKC`) and, in the
  override only, `store_file_host_suffixes`, `store_market` (default `US`) and
  `store_language` (default `en-us`).
- `-p` (a local file instead of the download) is not read by the download step: it reads
  the catalog and the recipe's cache.
- The ways the download step stops, each with an error and nothing written: the catalog names
  more than one package, or its SKUs describe the package differently (this processor handles a
  product with one package); a refused file host (the message names it: check that the host is
  Microsoft's, then correct `store_file_host_suffixes` in the override, see "The file hosts");
  `The delivery service offered no file.` or `The delivery service named no update with a file
  for this product.`; `No offered file has the catalog's SHA-256: ...`. A paid product is not
  for this processor; Acellus was free in the catalog of 2026-11-13.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the three files are property lists with the right identifiers, parents
and steps, that every argument is an input that the shared processor declares (the
download step's included), that no recipe gives a version label, that this README
opens with the status line that says what was NOT done, that this README has no `make-override`
without `--override-dir` and runs no recipe by its identifier, and that nothing
site-specific is in the folder.

The chain tests run the `.cimian.recipe`'s importer against a temporary Cimian repository
(they need PyYAML and are skipped without it) and the `.pcman.recipe`'s against the package
tool's stand-in, each with a tiny made-up bundle (a zip with a bundle manifest, built by the
helpers of the shared tests) after the real `ChecksumVerifier`. No test asks the Store.
