# Win-GeoGebra

A Windows recipe pair: GeoGebra Classic 6, the `.msi` that GeoGebra serves for installations on many computers, with the version label read from the MSI.

**Status. New, and NOT run: nothing of this folder has run under AutoPkg, no installer was downloaded, and nothing was installed on a PC. The download is NOT verified: GeoGebra publishes no hash for the file, and a check of the signature is not built. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true (`cimian_allow_unverified` for the cimian recipe). Do not set it before the signature check exists. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template geogebra` (no `--version` for an MSI). Read by the writer on 2026-11-13, with header and small page requests only and no browser identity: (1) `https://download.geogebra.org/package/win-msi6` answered 302 with the relative Location `/installers/6.0/GeoGebra-Windows-Installer-6-0-936-0.msi`; (2) `https://download.geogebra.org/package/win` answered 302 to `/installers/5.4/GeoGebra-Windows-Installer-5-4-936-0.exe`, the Classic 5 EXE, which this recipe does not use; (3) the folder `https://download.geogebra.org/installers/6.0/` is a plain index that lists four MSIs (`6-0-932-1`, `6-0-933-1`, `6-0-934-0`, `6-0-936-0`; the last one 108032000 bytes, dated 11-Nov-2026), an EXE beside each, portable ZIP files, files for macOS and `version.txt`, whose content was `6-0-936-0`; it lists no hash, checksum or signature file; (4) GeoGebra's page on mass installation (`https://geogebra.github.io/docs/reference/en/GeoGebra_Mass_Installation/`) names the address of (1) as the MSI of GeoGebra 6 for many Windows computers, says that it holds `GeoGebra.exe` (Classic 6) beside the apps of the Calculator Suite (`GeoGebraCalculator.exe`, `GeoGebraCAS.exe`, `GeoGebraGeometry.exe`, `GeoGebraGraphing.exe`), gives `msiexec /i <the MSI> ALLUSERS=2 /qn` as the silent command, and says that mass installations of Classic 6 do not update themselves; (5) GeoGebra's pages say that its installers are subject to the GeoGebra non-commercial license (the licence text itself was NOT read: whether a school's use fits it is the owner's question). NOT established: the MSI's own ProductVersion, and whether it has the same four numbers as the address (`6.0.936.0`); the MSI's UpgradeCode and whether the next release keeps it; the MSI's platform; that the client's silent install (`/qn /norestart`, without `ALLUSERS=2`) installs for every user when it runs as SYSTEM; the install path and the shortcuts that a user sees; that the program does not update itself after such an install (only the vendor's sentence was read); that the signature of the file is valid (nothing checks it); that the next release stays in the folder `6.0` with this form of name; any run with AutoPkg; any install on a PC. The tests use answers that the writer wrote by hand after the real answer of 2026-11-13, so they prove what the code does with answers of that form and nothing about GeoGebra's server today. The first dry run and the first install on a test PC are the check of what is NOT established. When a run fails, STOP: nothing was written (a run that fails before the import writes nothing). Read GeoGebra's real address with a header request or in a browser, correct the processor or the recipe, and only then look at the trust information. Never accept new trust information first to make a failure go away.**

**Results of 2026-11-13, newer than the status above; where the two differ, this paragraph holds.** Under AutoPkg 2.9.0, into a scratch Cimian repository with a hand-made first pkginfo of the item (`make-override` with `--override-dir`, `verify-trust-info` OK, a dry run, a real run, a second real run): the real run published `geogebra-6.0.936.0.msi`, and the second run said that nothing is new. On one Windows 11 test PC, as SYSTEM from a scheduled task, `msiexec /i <file> /qn /norestart` ended with exit code 0 after 17 seconds; the file's signature was valid (GeoGebra GmbH); the PC then listed `GeoGebra Classic` with DisplayVersion `6.0.936.0` (in the 32-bit view of the registry), installed in `C:\Program Files (x86)\GeoGebra Classic`, product code `{4748282E-2448-11E8-81BC-53A8D56EE868}`. No property such as `ALLUSERS` was passed. The program was not started, an upgrade over an older version and the uninstall were not tested, and no Cimian client installed it.


| Recipe | Identifier | What it does |
| --- | --- | --- |
| `GeoGebra-Win.download.recipe` | `com.github.serrc-techops.download.GeoGebra-Win` | Finds the address of the current MSI with `GeoGebraInfoProvider` and downloads it under a name made of the address's four numbers. It has no hard check |
| `GeoGebra.cimian.recipe` | `com.github.serrc-techops.cimian.GeoGebra` | Parent: the download recipe. Hands the file to `CimianImporter`, which takes the MSI's own version and publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `GeoGebra.pcman.recipe` | `com.github.serrc-techops.pcman.GeoGebra` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which takes the MSI's own version and publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `GeoGebra.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `GeoGebra.pcman.recipe` is the package tool's way, with `PcmanImporter`. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The processor `GeoGebraInfoProvider.py` is in this folder. GeoGebra serves the MSI
through one redirect, whose `Location` is relative. The processor reads the
`Location` header of that answer and follows no redirect. It outputs `url` (the
address on `download.geogebra.org`) and `geogebra_address_version` (the four numbers
of the file name with dots, `6.0.936.0` on 2026-11-13). It outputs no hash, because
GeoGebra publishes none, and no `version`: the label comes from the MSI. The shared
processors are in `../Win-SharedProcessors/` and `../Win-PcmanProcessors/` (see their
READMEs). Neither recipe stops on an unchanged download, so an import that failed is
tried again at the next run.

How strict the processor is:

- Exactly one request is made, to the fixed address `https://download.geogebra.org/package/win-msi6`,
  with a time limit of 120 seconds. No body is read. No redirect is followed: the answer must be a
  redirect (301, 302, 303, 307 or 308) with exactly one `Location` header, and any other status is an error.
- A relative `Location` is resolved against the fixed address. The result must be https on
  `download.geogebra.org`, with no user name, no port, no query and no fragment.
- The path must be exactly `/installers/6.0/GeoGebra-Windows-Installer-<n>-<n>-<n>-<n>.msi`,
  each `<n>` made of digits. Any other path stops the run, also a new folder such as `6.1`.
- The processor has no inputs.

The recipe gives `URLDownloader` the file name
`GeoGebra-Windows-Installer-<version of the address>.msi`, so that the cached file has
a stable name that ends in `.msi`.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What protects, and what does not

Nothing proves that the downloaded file is what GeoGebra published: there is no vendor
hash, and a signature check is not built. The shared importer knows this: no step of
the recipe sets `checksum_verified` with the hash of the file, so a real run is refused
before the package tool starts. The checks that remain do not replace a verification.

- **The address.** The processor accepts only an address of exactly one form on one
  fixed host (`download.geogebra.org`), reached through one answer of that host. That
  shows where the address came from. It does not show what the file at that address is.
- **The same product.** Both importers refuse an MSI whose upgrade code differs from
  the template's (`CimianImporter` unless the override sets `cimian_allow_product_change`).
  So another product cannot be published under the name of this item.
- **The label.** The recipe gives no version label. Both importers take the MSI's own
  ProductVersion.

An MSI of the right product with other content (a changed file of the vendor, or a
changed download on the way) would pass all of these.

## The label is the MSI's version, and nothing compares it with the address's

**The label that the importers get is the ProductVersion inside the downloaded MSI. No
step of this recipe compares it with the four numbers of the address.** `GeoGebraInfoProvider`
prints the address's version (`6.0.936.0` on 2026-11-13), and nothing compares it with the
label. Nobody has read the MSI's ProductVersion: whether it has the same four numbers is NOT
established. A person checks it, at the first dry run:

1. Run the dry run with `-v` (step 3 or step c) and read the two versions that it prints: the
   provider's line `GeoGebra's address names version ...`, and the version in the importer's
   lines and report row, which is the MSI's own.
2. If they differ, stop and tell the owner before anything is published. A label that only
   adds or drops parts may still order the versions in another way than GeoGebra's numbers do.
3. After the first install on a test PC, compare the label with the version that Windows'
   list of installed programs shows. Nobody has done that.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01 with another recipe of this repository: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg, `msiinfo` (msitools: `brew install msitools`) for the MSI, and nothing of the owner's: no package tool. It uses `GeoGebra.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `InstallerService.cs:936`) are from `windowsadmins/cimian` at commit `e10498b`, read on 2026-10-04 for another folder of this repository and not checked against a later version.

**The download of this program is NOT verified** (see the status line above). `CimianImporter` REFUSES a real run of a download that no step verified (nothing is published) unless the override sets `cimian_allow_unverified` to true. Do not set it before a verification step exists. A dry run is allowed, and prints a `WARNING: the download was NOT verified` line.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **`msiinfo` on the PATH of the run** (`brew install msitools`): `CimianImporter` reads the MSI's ProductVersion and its two codes with it, and does not parse an MSI itself. A job that `launchd` starts may have no Homebrew on its `PATH`, so the importer looks in `/opt/homebrew/bin` and `/usr/local/bin` too; the input `cimian_path` changes that list. This recipe cannot run without it: its step passes an empty `version`, and an argument of a step wins over an override's `Input`, so the label can only come from the MSI. The run stops and names the facts that are missing.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `geogebra`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name `GeoGebra Classic 6` and the developer `GeoGebra`) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture`.

   **For an `.msi` nothing needs completing for a silent install:** the client runs `msiexec /i <file> /qn /norestart` itself and then the arguments of the item (`InstallerService.cs:936-948`), so the recipe gives no silent arguments, and `CimianImporter` writes the install check of an MSI (an `installs` entry of type `msi` with the MSI's codes and version). What the MSI's own properties allow (features, per-user or per-machine) is the template's business: give them as `installer: {args: [...]}` in the override's `pkginfo`. GeoGebra's page on mass installation adds `ALLUSERS=2` to its silent command; the client's command does not have it. Whether the MSI installs for every user without it, when the client runs as SYSTEM, is NOT established: a person decides after the first test PC whether the item needs `ALLUSERS=2` as an argument. An MSI whose upgrade code is not the template's, or that has none where the template's item had one, is refused (Windows Installer does not upgrade across upgrade codes): `cimian_allow_product_change` set to true in the override allows it, with a WARNING.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i GeoGebra-Win
    autopkg list-recipes | grep -i GeoGebra.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> GeoGebra.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `GeoGebra.cimian`, not a path. Expected (not run): it writes `<the Windows overrides folder>/GeoGebra.cimian.recipe` with the identifier `local.cimian.GeoGebra` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.GeoGebra`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the provider's line with the address's version is printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GeoGebra.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.GeoGebra`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.msi (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written, NOT verified`. `<version>` is the MSI's own: compare it with the provider's line (see the section on the label). The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on (NOT YET: see the status line)

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/GeoGebra.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GeoGebra.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust (seen with another recipe of this repository). Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

**Not yet.** This download has no verification step, so `CimianImporter` refuses the real run below until the override also sets `cimian_allow_unverified` to true, which a person decides only after the file was checked by hand, and which is then written in the override's `Input`, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_allow_unverified bool true' \
        <the Windows overrides folder>/GeoGebra.cimian.recipe

With it the run prints `WARNING: published WITHOUT a verified download` and the report row says `published, NOT verified`.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GeoGebra.cimian.recipe

   Expected (not run): `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published, NOT verified`. The repository now has the installer under `pkgs/`, then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GeoGebra.cimian.recipe

   Expected (not run): `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GeoGebra.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GeoGebra.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `GeoGebra.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool.

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

3. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. If the package tool's repository has an item
   `geogebra` already, look at it first: an item of the kind `choco` is not the
   template; an item that an earlier import of the GeoGebra MSI made is, and this step
   is then not needed. The command, with a real MSI that a person has checked (NOT run
   for this program):

       pcman import <path of the MSI> --name geogebra \
           --display-name "GeoGebra Classic 6" --category <the category of the item> \
           --developer "GeoGebra" --description <one sentence about the item> \
           --directory <the folder of the item> --architectures <the MSI's platform> \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. The MSI's
   platform was NOT read: read it from the MSI's summary (`msiinfo suminfo <the MSI>`)
   before the import. The install arguments are the client's for an MSI (`/qn /norestart`);
   GeoGebra's page adds `ALLUSERS=2`, and whether the package tool can carry that property
   for an MSI was NOT established by the writer: read the package tool's README, and decide
   after the first test PC. A person changes the template later; nothing else does. **If
   the template is made from the MSI that is current at GeoGebra, the first run says
   "Nothing new" (see step c).**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i GeoGebra-Win
    autopkg list-recipes | grep -i GeoGebra.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> GeoGebra.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `GeoGebra.pcman`, not a path. Expected (not
run): it writes `<the Windows overrides folder>/GeoGebra.pcman.recipe` with the
identifier `local.pcman.GeoGebra` and the trust information of the two recipes and
the two processors that are not part of AutoPkg itself (`GeoGebraInfoProvider`,
`PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.GeoGebra`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GeoGebra.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.GeoGebra`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**`-v` prints what each processor says about its own work; `-vv` would add every processor's
inputs and outputs, `pcman_root` and the repository among them, to the log: keep such a log private.**
Expected, from the code and the runs of other folders, NOT printed by this recipe yet, when
the current version is not yet in the repository:

    GeoGebra's address names version 6.0.936.0: https://download.geogebra.org/installers/6.0/GeoGebra-Windows-Installer-6-0-936-0.msi
    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name      Version                  Catalogs    Result
    geogebra  <the MSI's own version>  Production  dry run, nothing written, NOT verified

**Read the two versions.** The first line gives the version of the address. The table
gives the MSI's own version, which is the label. Are they the same four numbers? That is
NOT established; if they differ, stop and tell the owner before anything is published.
The plan itself is not printed. If the current version is in the repository already
(the template was made from it), the line is `Nothing new: ... is in the repository
already. Nothing was written.` instead. That is correct.

If GeoGebra changes its answer so that the processor cannot read it, the run fails with a
line that begins `GeoGebra's download address` and publishes nothing. If the line says that
the address answered with something that is not a redirect, or leads to another host or
another folder, stop and tell the owner: the recipe never reads an address from another
host than GeoGebra's one fixed one.

## d. Switch a real run on (NOT YET: see the status line)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file. Nothing was published. Publish by hand after
    checking the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template geogebra

Do not add `--version` for an MSI: the package tool takes the MSI's own version. Then
`pcman catalogs` (step e.3).

**Only after the signature check exists, or when a person has decided to accept an
unverified download:** the override allows it. Both lines are needed.

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/GeoGebra.pcman.recipe
    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_allow_unverified bool true' \
        <the Windows overrides folder>/GeoGebra.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GeoGebra.pcman.recipe

A change of the `Input` does not break trust (seen with another recipe of this
repository). Do not use `-k` instead: on the command line it applies to every recipe of
that run. A run then prints `WARNING: published WITHOUT a verified download ...` at any
verbosity, and the report's row says `published, NOT verified`.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GeoGebra.pcman.recipe

   Only after both lines of step d. Expected (not run): `Published geogebra ...`,
   the warning `published WITHOUT a verified download`, and the table

       The following versions were published by the package tool:
       Name      Version                  Catalogs    Result
       geogebra  <the MSI's own version>  Production  published, NOT verified

   The repository then has the MSI under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions geogebra` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GeoGebra.pcman.recipe

   Expected (not run): `Nothing new: ... is in the repository already. Nothing was
   written.` A fresh override gets a new cache folder, so its first run downloads the
   file again before it says so.

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GeoGebra.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GeoGebra.pcman.recipe

## g. A share that is not mounted

Other recipes of this repository, run with an empty folder as the repository, failed
(exit code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again. (Not run with this recipe.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private. The lines of `GeoGebraInfoProvider` are printed
  with `-v` or `-vv`.
- The download recipe has no inputs besides `NAME`: the address is fixed in the
  processor. Another edition of GeoGebra (the Classic 5 EXE, the Calculator Suite's own
  installer, a portable ZIP) is not what this recipe takes.
- The processor needs no browser identity: the writer's requests of 2026-11-13 had none.
  The processor sends the plain name `autopkg-GeoGebraInfoProvider`. Whether GeoGebra
  answers the build machine's network the same way is NOT established.
- `version.txt` in the folder `6.0` had the same four numbers as the address on 2026-11-13.
  The processor does not read it.
- The recipe's `NAME` is `GeoGebra` and `PCMAN_TEMPLATE` is `geogebra`. Change
  the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) skips the download. The file is not
  checked at all.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of answer (the addresses in `tests/` are
written by hand after the real answer of 2026-11-13, not saved from the real server), that
the three recipes are property lists, that every argument is an input that the processors
declare, that no recipe passes a version label for the MSI, that the descriptions and the top
of this README say that the download is not verified and that a real run is refused, that
this README states no hash, has no `make-override` without `--override-dir` and runs no
recipe by its identifier, that it says what was NOT done, and that nothing site-specific is
in the folder. They also run each importer against a stand-in: the package tool's for the
one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped
without it). A small cut of GeoGebra's folder index of 2026-11-13 (`tests/index_excerpt.html`,
its Windows lines and the line of `version.txt`) shows that the folder lists no hash file and that the newest MSI
has the address's name.
