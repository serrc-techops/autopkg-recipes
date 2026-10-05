# Win-FoxitReader

A Windows recipe pair: Foxit PDF Reader, the 64-bit multi-language `.exe` installer, with the version label read from the file.

**Status. NOT rehearsed with AutoPkg. Some facts of the source were fetched by the writer on 2026-10-02: no run of AutoPkg was made, and nothing was written to a repository. The download is NOT verified: Foxit publishes no hash for the file, and a check of the signature is not built. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true. Do not set it before the signature check exists. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template foxitreader --version <the label>` (an EXE needs `--version`). Read from Foxit's servers on 2026-10-02, with no browser identity: (1) `https://www.foxit.com/downloads/latest.html?product=Foxit-Reader&platform=Windows&version=&package_type=exe&language=L10N` answered 301 to `https://www.foxit.com/downloads/latest/?product=...` (the same query); (2) that address answered 307 to `https://cdn01.foxitsoftware.com/product/reader/desktop/win/2026.2.1/FoxitPDFReader202621_L10N_Setup_Prom_x64.exe`; (3) that address answered 302 to a signed, short-lived address on a cloud storage host. Verified on the same day: the file at that address, downloaded through its signed redirect (291221048 bytes), was read with the shared `WindowsExeVersion`: `ProductVersion` `2026.2.1.39815`, `FileVersion` the same, the numbers of the fixed file information the same, `ProductName` `Foxit PDF Reader`. So the label that the recipe passes is `2026.2.1.39815`, and the version in the address, `2026.2.1`, is its first three parts (one release was compared). NOT established: that the next release keeps that relation between the address and the file; that the signature of the file is valid (nothing checks it); the host and the lifetime of the signed address (the processor never reads that answer: the downloader follows it); that another product, language or package type than the defaults has the same layout (only the defaults were read); the silent switch and the install path of the installer (not read: the first import's command below has placeholders); that the template item `foxitreader` exists; `pcman catalogs`; any run with AutoPkg. The tests use answers that the writer wrote by hand after the real addresses of 2026-10-02, so they prove what the code does with answers of that form and nothing about Foxit today. The first run on the build Mac is the check of everything that is NOT established. When it fails, STOP: nothing was written (a run that fails before the import writes nothing). Read Foxit's real addresses with a header request or in a browser, correct the processor or the recipe, and only then look at the trust information. Never accept new trust information first to make a failure go away.**


| Recipe | Identifier | What it does |
| --- | --- | --- |
| `FoxitReader-Win.download.recipe` | `com.github.serrc-techops.download.FoxitReader-Win` | Finds the address of the current installer with `FoxitInfoProvider`, downloads it under a name made of the release folder's version, and reads the file's own version with the shared `WindowsExeVersion`. It has no hard check |
| `FoxitReader.cimian.recipe` | `com.github.serrc-techops.cimian.FoxitReader` | Parent: the download recipe. Hands the file to `CimianImporter` with the file's own version as the label, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `FoxitReader.pcman.recipe` | `com.github.serrc-techops.pcman.FoxitReader` | Parent: the download recipe. Hands the file to the package tool (`pcman`) with the file's own version as the label, which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `FoxitReader.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `FoxitReader.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The processor `FoxitInfoProvider.py` is in this folder. Foxit serves the installer
through a chain of redirects (301, 307, then 302 to a signed address). The processor
reads the `Location` header of the first two answers and follows no redirect. It
outputs `url` (the address on `cdn01.foxitsoftware.com`) and `foxit_address_version`
(the version that the address names, `2026.2.1`). It outputs no hash, because Foxit
publishes none, and no `version`: the label comes from the file. The shared
processors are in `../Win-SharedProcessors/` (see its README, the section
`WindowsExeVersion`). Neither recipe stops on an unchanged download, so an import
that failed is tried again at the next run.

How strict the processor is:

- Exactly two requests are made, with a time limit of 120 seconds each. The first goes to
  `www.foxit.com`, built from the three inputs. No body is read. No redirect is followed:
  each answer must be a redirect (301, 302, 303, 307 or 308) with exactly one `Location`
  header, and any other status is an error.
- The first `Location` must be https on `www.foxit.com`. The second must be https on
  `cdn01.foxitsoftware.com`, with no user name, no port, no query and no fragment.
- The second `Location` must be exactly
  `/product/reader/desktop/win/<version>/FoxitPDFReader<digits>_<language>_Setup_Prom_x64.exe`
  with `<version>` of numbers and dots and `<language>` equal to the input. Any other path
  stops the run.
- The three inputs (`FOXIT_PRODUCT`, `FOXIT_LANGUAGE`, `FOXIT_PACKAGE_TYPE`; defaults
  `Foxit-Reader`, `L10N`, `exe`) are letters, digits and `-`; a path is an error.

The recipe gives `URLDownloader` the file name
`FoxitPDFReader-<version of the address>-<language>-x64.exe`, so that the cached file has
a stable name. The downloader follows the third redirect, to the signed address.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What protects, and what does not

Nothing proves that the downloaded file is what Foxit published: there is no vendor
hash, and a signature check is not built. The shared importer knows this: no step of
the recipe sets `checksum_verified` with the hash of the file, so a real run is refused
before the package tool starts. The checks that remain do not replace a verification.

- **The address.** The processor accepts only an address of exactly one form on one
  fixed host (`cdn01.foxitsoftware.com`), reached through two answers of `www.foxit.com`.
  That shows where the address came from. It does not show what the signed address
  that follows it serves.
- **The same product.** For an MSI the package tool refuses a different upgrade code.
  Whether it has an equivalent check for an EXE was NOT established by the writer.
- **The label.** An EXE has no version that the package tool reads for itself, so the
  recipe passes the version that `WindowsExeVersion` read from the file: the
  `ProductVersion` string when it is numbers and dots, otherwise the four numbers of the
  fixed file information. On 2026-10-02 that was `2026.2.1.39815`, and the version in the
  address was `2026.2.1`, its first three parts. The label is data in the file and proves
  nothing about where the file came from. That the next release keeps the relation is NOT
  established: the first dry run prints both, and a person compares them.

An installer of another content under the same address would pass all of these.

## The label is the installer's version, and nothing compares it with the product's

**The label that the package tool gets is the `ProductVersion` of the downloaded setup file,
and not the version of the Foxit PDF Reader that it installs. No step of this recipe compares
the two.** The only other version that the recipe knows is the one in the address
(`2026.2.1` on 2026-10-02): `FoxitInfoProvider` prints it, nothing compares it with the
label, and the version that the installed Reader shows has not been read by anyone. If Foxit's
setup program stopped tracking the product, the recipe would still publish under the setup
file's number, and that number orders the versions in the repository. The recipe does not
check this at any run. A person checks it, at the first dry run:

1. Run the dry run with `-v` (step c) and read the two versions that it prints: the first
   line, with the version of the release folder in Foxit's address, and the line `version
   is ..., taken from ...` of `WindowsExeVersion` with the label.
2. The label must begin with the address's version (on 2026-10-02: `2026.2.1` and
   `2026.2.1.39815`). If it does not, stop and tell the owner before anything is published.
3. After the first install on a test PC, compare the label with the version that the
   installed Reader reports (its About page, or its entry in Windows' list of installed
   programs). Nobody has done that. Whether the Cimian client sees the label and that version
   as the same version is NOT established.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `FoxitReader.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

3. **The version label** needs no program: the download recipe's step `WindowsExeVersion` reads it from the `.exe` itself, and this recipe passes it on as `%version%`.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `foxitreader`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the first step of the package tool's way below marks what is only the writer's knowledge or was not read), so they are left for a person who has read them in the vendor's documentation and tried them on a test PC. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i FoxitReader-Win
    autopkg list-recipes | grep -i FoxitReader.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> FoxitReader.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `FoxitReader.cimian`, not a path. It writes `<the Windows overrides folder>/FoxitReader.cimian.recipe` with the identifier `local.cimian.FoxitReader` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.FoxitReader`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/FoxitReader.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.FoxitReader`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on (NOT YET: see the status line)

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/FoxitReader.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/FoxitReader.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

**Not yet.** This download has no verification step, so `CimianImporter` refuses the real run below until the override also sets `cimian_allow_unverified` to true, which a person decides only after the file was checked by hand, and which is then written in the override's `Input`, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_allow_unverified bool true' \
        <the Windows overrides folder>/FoxitReader.cimian.recipe

With it the run prints `WARNING: published WITHOUT a verified download` and the report row says `published, NOT verified`.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/FoxitReader.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/FoxitReader.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/FoxitReader.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/FoxitReader.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `FoxitReader.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `FoxitReader.pcman` where this README used to say `FoxitReader.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `FoxitReader.cimian.recipe` (when that recipe ran the package tool) must be made again from `FoxitReader.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `FoxitReader.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   (the share mounted).

3. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. The template keeps the name of the item that
   it replaces. If the package tool's repository has an item `foxitreader` already, look
   at it first: it must be an item for the EXE, and this step is not needed. The command,
   with a real installer of the current release:

       pcman import <path of the installer> --name foxitreader \
           --version <the ProductVersion that the file's properties show> \
           --directory <the folder of the item> \
           --install-arguments <the installer's silent switch, read in the vendor's documentation first> \
           --install-path <the path of the installed program, read on one PC after an install> \
           --architectures x64 --display-name "Foxit PDF Reader" \
           --category <the category of the item> --developer "Foxit Software" \
           --description <one sentence about the item> --no-prompt --build

   The silent switch and the install path are facts of the installer. The writer did NOT
   read them: the Foxit installer's documentation was not read, so the command has no
   value for them. Read the vendor's documentation first, and try both on one PC before
   this command is run. The label after `--version` is the version of the file as its
   properties show it (the same text that `WindowsExeVersion` reads from the file; for the
   file of 2026-10-02 it is `2026.2.1.39815`).
   Add the icon as the package tool's README describes. A person changes the template
   later; nothing else does. **If the template is made from the release that is current
   at Foxit, the first run says "Nothing new" (see step c). To see a dry run that would
   publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i FoxitReader-Win
    autopkg list-recipes | grep -i FoxitReader.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> FoxitReader.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `FoxitReader.pcman`, not a path. Expected (not
run): it writes `<the Windows overrides folder>/FoxitReader.pcman.recipe` with the
identifier `local.pcman.FoxitReader` and the trust information of the two recipes and
the three processors that are not part of AutoPkg itself (`FoxitInfoProvider`,
`WindowsExeVersion`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.FoxitReader`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/FoxitReader.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.FoxitReader`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**`-v` prints what each processor says about its own work; `-vv` would add every processor's
inputs and outputs, `pcman_root` and the repository among them, to the log: keep such a log private.** Expected, from
the code and the rehearsals of the other folders, NOT printed by this recipe yet, when
the current version is not yet in the repository:

    Foxit's address names version 2026.2.1: https://cdn01.foxitsoftware.com/product/reader/desktop/win/2026.2.1/...
    FoxitPDFReader-2026.2.1-L10N-x64.exe: ProductVersion '...', product version numbers ..., file version '...', file version numbers ...
    version is ..., taken from the ProductVersion string
    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name         Version  Catalogs    Result
    foxitreader  <label>  Production  dry run, nothing written, NOT verified

**Read the two versions.** The first line gives the version of the release folder in
Foxit's address. The line `version is ...` gives the label that the file itself shows,
and it is the label that goes to the package tool. On 2026-10-02 they were `2026.2.1`
and `2026.2.1.39815`: the address's version is the first three parts of the label. Does
the label begin with the address's version? That the next release keeps this is NOT
established; if the label does not begin with it, stop and tell the owner before anything
is published. The plan itself is not printed. If the current version is in the
repository already (the template was made from it), the line is `Nothing new: ... is
in the repository already. Nothing was written.` instead. That is correct.

If Foxit changes an answer so that the processor cannot read it, the run fails with a line
that begins `Foxit's download address` or `Foxit's second download address` and publishes
nothing. If the line says that an address answered with something that is not a redirect,
or leads to another host, stop and tell the owner: the recipe never reads an address from
another host than Foxit's two fixed ones.

## d. Switch a real run on (NOT YET: see the status line)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file. Nothing was published. Publish by hand after
    checking the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template foxitreader --version <the label>

The label is the one that `WindowsExeVersion` showed in the dry run. Then `pcman
catalogs` (step e.3).

**Only after the signature check exists, or when a person has decided to accept an
unverified download:** the override allows it. Both lines are needed.

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/FoxitReader.pcman.recipe
    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_allow_unverified bool true' \
        <the Windows overrides folder>/FoxitReader.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/FoxitReader.pcman.recipe

A change of the `Input` does not break trust (found with 7-Zip). Do not use `-k`
instead: on the command line it applies to every recipe of that run. A run then prints
`WARNING: published WITHOUT a verified download ...` at any verbosity, and the report's
row says `published, NOT verified`.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/FoxitReader.pcman.recipe

   Only after both lines of step d. Expected (not run): `Published foxitreader ...`,
   the warning `published WITHOUT a verified download`, and the table

       The following versions were published by the package tool:
       Name         Version  Catalogs    Result
       foxitreader  <label>  Production  published, NOT verified

   The repository then has the installer under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions foxitreader` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/FoxitReader.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/FoxitReader.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/FoxitReader.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again. (Not run with this recipe.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private. The lines of `FoxitInfoProvider` and
  `WindowsExeVersion` are printed with `-v` or `-vv`.
- The inputs of the download recipe are `FOXIT_PRODUCT`, `FOXIT_LANGUAGE` and
  `FOXIT_PACKAGE_TYPE`. Change them in the override's `Input`, not in the recipe. Only the
  defaults were read from Foxit's servers: a person looks at any other value first. The
  cached file name has the language in it, so one override has one language.
- The processor needs no browser identity: the writer's requests of 2026-10-02 had none.
  The processor sends the plain name `autopkg-FoxitInfoProvider`. Whether Foxit answers the
  build Mac's network the same way is NOT established.
- The address of the first answer, `https://www.foxit.com/downloads/latest/?product=...`,
  is Foxit's page for the product; the processor does not read the page.
- The recipe's `NAME` is `FoxitReader` and `PCMAN_TEMPLATE` is `foxitreader`. Change
  the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) skips the download. The file is not
  checked at all, and `WindowsExeVersion` reads its version all the same.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of answer (the addresses in `tests/` are
written by hand after the real answers of 2026-10-02, not saved from the real server),
that both recipes are property lists, that every argument is an input that the processors
declare, that the version step comes after the end of the check phase and the cimian
recipe passes its label as `pcman_version`, that the descriptions and the top of this
README say that the download is not verified and that a real run is refused, that this
README states no hash and has no `make-override` without `--override-dir` and runs no
recipe by its identifier, that it says what was NOT done, and that nothing site-specific is
in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
