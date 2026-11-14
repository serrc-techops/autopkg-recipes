# Win-GoogleEarthPro

A Windows recipe pair: Google Earth Pro, the full (offline) `.exe` installer, with the version label read from the EXE itself.

**Status. New and not rehearsed: nothing of this folder has run under AutoPkg, no installer was downloaded, and nothing has been installed on a PC. Some facts of the source were read by the writer on 2026-11-13: `https://dl.google.com/dl/earth/client/advanced/current/googleearthprowin-x64.exe` answered a HEAD request with 200 and no redirect, `Content-Length` 100802200, `Last-Modified` 2026-08-20; the address holds no version; no hash was found for the file. Google's page `https://www.google.com/earth/about/versions/` (read the same day) says that Earth Pro on desktop will no longer be available for download from June 25, 2027. NOT established: that Google's own download page links exactly this address (the writer could not read the link from the page, which is built by script, and Google's help page for administrators could not be fetched), that Google publishes a hash or a signature check for this file (the writer saw none and knows of none), that the file has a version resource (`WindowsExeVersion` needs one; the first dry run shows it), what kind of installer it is, that it takes `OMAHA=1` as its silent argument and installs per machine (this is the writer's knowledge, NOT read from Google and NOT tested), the path of the installed program, that the package tool has a check of the product for an EXE, that Google's server answers the questions that AutoPkg asks about a changed file, and any install on a PC. The first install on a test PC is the check of what is NOT established. When a run fails, STOP: nothing was written; correct the recipe, and only then look at the trust information. Never accept new trust information first.**

**Not verified. The download is NOT verified: Google publishes no hash for the file, and a check of the signature is not built. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true. Do not set it before the signature check exists. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template google-earth-pro --version <label>` (the label of an EXE: see "The label" below). Nothing has been run and nothing has been installed on a PC. The Windows overrides folder is not one of AutoPkg's override folders, so every override command here carries `--override-dir`: see the paragraph below.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `GoogleEarthPro-Win.download.recipe` | `com.github.serrc-techops.download.GoogleEarthPro-Win` | Downloads the Google Earth Pro installer that Google serves at a fixed address (an EXE), kept under the file name of the address, and reads its version from the file itself (`WindowsExeVersion`). It has no hard check |
| `GoogleEarthPro.cimian.recipe` | `com.github.serrc-techops.cimian.GoogleEarthPro` | Parent: the download recipe. Hands the file and its label to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `GoogleEarthPro.pcman.recipe` | `com.github.serrc-techops.pcman.GoogleEarthPro` | Parent: the download recipe. Hands the file and its label to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `GoogleEarthPro.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `GoogleEarthPro.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The steps of the download recipe are `URLDownloader`, `EndOfCheckPhase` and then
`WindowsExeVersion`, which is a shared processor: it reads the ProductVersion of the
downloaded EXE and outputs it as `version`; the cimian recipe passes that as `version`, and the
pcman recipe as the package tool's `pcman_version`. How the processor reads the file and which string it
takes is in the README of `../Win-SharedProcessors/`.

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What protects, and what does not

Nothing proves that the downloaded file is what Google published: there is no vendor
hash, and a signature check is not built. The shared importer knows this: no step of
the recipe sets `checksum_verified` with the hash of the file, so a real run is refused
before the package tool starts. What remains does not replace a verification.

- **The label.** An EXE has no version that the package tool can read for itself, so
  the recipe passes the label that `WindowsExeVersion` read from the file. That is data
  in the file: it shows what the file claims, and proves nothing about where the file
  came from. The label must equal what a person reads in the file's properties (the
  Details tab of a Windows PC); the first dry run shows it.
- **The same product.** For an MSI the package tool refuses a different upgrade code.
  Whether it has an equivalent check for an EXE was NOT established by the writer. For
  this recipe the checks are the dry run and a person's look at what it plans.

A file of another product, or with other content (a changed file of the vendor, or a
changed download on the way), could pass these checks.

## The label

The processor prints, when the run is verbose (`-v`), a line with the file's name, its
`ProductVersion`, its fixed version numbers and its `FileVersion`, and a second line,
`version is ..., taken from ...`. It takes the ProductVersion string when that is
numbers and dots only, else the four numbers of the fixed file information. Read both
lines at the first dry run and compare them with the file's properties on a Windows PC.
If the processor stops (no version resource, a file that is not a PE file), the run fails,
nothing is written, and the file is not what the recipe expects: read it before anything
else.

## The label is the installer's version, and nothing compares it with the product's

**The label that the package tool gets is the `ProductVersion` of the downloaded setup file
(`googleearthprowin-x64.exe`), and not necessarily the version of Earth Pro that it installs. No step
of this recipe compares the two, and the recipe has no other version to compare it with: the
address has none, and the recipe reads no other page.** If the setup program did not track the
product, the recipe would still publish under the setup file's number, and that number orders the
versions in the repository. The recipe does not check this at any run. A person checks it, at the
first dry run:

1. Run the dry run with `-v` (step c) and read the line `version is ..., taken from ...`
   of `WindowsExeVersion`. Nobody has seen it: the file was not downloaded.
2. Compare the label with the file's properties on a Windows PC (the Details tab): they
   must agree. Nobody has looked at the properties on a PC.
3. Compare the label with the version that Google gives for the current Earth Pro (the writer
   did not read it), and, after the first install on a test PC, with the version that the installed
   program shows. If they do not agree by their numbers, stop and tell the owner before anything is
   published. Nobody has done that comparison.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.**

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `GoogleEarthPro.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `google-earth-pro`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the first step of the package tool's way below marks what is only the writer's knowledge or was not read), so they are left for a person who has read them in the vendor's documentation and tried them on a test PC. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i GoogleEarthPro-Win
    autopkg list-recipes | grep -i GoogleEarthPro.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> GoogleEarthPro.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `GoogleEarthPro.cimian`, not a path. It writes `<the Windows overrides folder>/GoogleEarthPro.cimian.recipe` with the identifier `local.cimian.GoogleEarthPro` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.GoogleEarthPro`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.GoogleEarthPro`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on (NOT YET: see the status line)

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/GoogleEarthPro.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

**Not yet.** This download has no verification step, so `CimianImporter` refuses the real run below until the override also sets `cimian_allow_unverified` to true, which a person decides only after the file was checked by hand, and which is then written in the override's `Input`, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_allow_unverified bool true' \
        <the Windows overrides folder>/GoogleEarthPro.cimian.recipe

With it the run prints `WARNING: published WITHOUT a verified download` and the report row says `published, NOT verified`.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `GoogleEarthPro.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `GoogleEarthPro.pcman` where this README used to say `GoogleEarthPro.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `GoogleEarthPro.cimian.recipe` (when that recipe ran the package tool) must be made again from `GoogleEarthPro.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `GoogleEarthPro.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   it replaces. If the package tool's repository has an item for Google Earth Pro
   already, look at it first: an item of the kind `choco` is not the template (the first import goes
   beside it without any option, and a person removes the Chocolatey item by hand); an item that an
   earlier run of this step made is, and this step is then not needed; set its name in the override (step b).
   The command, NOT run for this recipe, with a real installer:

       pcman import <path of googleearthprowin-x64.exe> --name google-earth-pro \
           --version <the label that the first dry run prints> \
           --directory <the folder of the item> \
           --install-arguments=OMAHA=1 \
           --architectures x64 \
           --display-name "Google Earth Pro" --category <the category of the item> --developer Google \
           --description "<one line about the item>" \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   Give the switch with the equals sign, as `--install-arguments=OMAHA=1`. **`OMAHA=1` is the writer's
   knowledge of the full installer's silent argument: it was NOT read from Google and NOT tested on a
   PC.** Read Google's documentation for administrators and try it on a test PC before it goes to any
   other PC. Whether the file installs per machine is likewise NOT established. `--architectures x64`
   is from the name of the file (`-x64`), NOT from its header: read the header before the first import.
   `--install-path` is left out: the installed program's path was not read, and a wrong path would
   install again at every run; the template then has no install check until a person adds one. The
   label after `--version` is the version of the installer as its properties show it. For an EXE the
   package tool is given it; here it is the same text that the recipe passes (see "The label").
   A person changes the template later; nothing else does. **If the template is made
   from the installer that is current at the vendor, the first run says "Nothing new"
   (see step c). To see a dry run that would publish, make the template from an older
   installer.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i GoogleEarthPro-Win
    autopkg list-recipes | grep -i GoogleEarthPro.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> GoogleEarthPro.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `GoogleEarthPro.pcman`, not a path. Expected (not
run for this recipe): it writes `<the Windows overrides folder>/GoogleEarthPro.pcman.recipe`
with the identifier `local.pcman.GoogleEarthPro` and the trust information of the two
recipes and of the two processors that are not part of AutoPkg itself
(`WindowsExeVersion`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.GoogleEarthPro`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.GoogleEarthPro`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**`-v` prints what each processor says about its own work; `-vv` would add every processor's
inputs and outputs, `pcman_root` and the repository among them, to the log: keep such a log private.** Expected, from
the code of the processors, NOT seen for this recipe, when the
current version is not yet in the repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name          Version                   Catalogs    Result
    google-earth-pro   <the label of the EXE>    Production  dry run, nothing written, NOT verified

Before that, the run prints the two lines of the processor (see "The label"). The plan
itself is not printed. The repository is unchanged. If the current version is in the
repository already (the template was made from it), the line is `Nothing new: ... is in
the repository already. Nothing was written.` instead. That is correct.

## d. Switch a real run on (NOT YET: see the second paragraph at the top)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file. Nothing was published. Publish by hand after
    checking the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template google-earth-pro --version <the label>

The label of an EXE is needed: the package tool never takes it from the file (see "The
label"). Then `pcman catalogs` (step e.3).

**Only after the signature check exists, or when a person has decided to accept an
unverified download:** the override allows it. Both lines are needed.

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/GoogleEarthPro.pcman.recipe
    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_allow_unverified bool true' \
        <the Windows overrides folder>/GoogleEarthPro.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.pcman.recipe

A change of the `Input` does not break trust. Do not use `-k`
instead: on the command line it applies to every recipe of that run. A run then prints
`WARNING: published WITHOUT a verified download ...` at any verbosity, and the report's
row says `published, NOT verified`.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.pcman.recipe

   Only after both lines of step d. Expected: `Published google-earth-pro ...`, the warning
   `published WITHOUT a verified download`, and the table

       The following versions were published by the package tool:
       Name          Version                   Catalogs    Result
       google-earth-pro   <the label of the EXE>    Production  published, NOT verified

   The repository then has the installer under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions google-earth-pro` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- Whether Earth Pro updates itself on the PCs is NOT established here. If it does, a hosted
  version sets a floor, and what the Cimian client does with a PC that is newer than the hosted
  version is NOT established either.
- Google replaces the file at the same address without a new address (the file was
  last modified on 2026-08-20 when it was read). AutoPkg asks the server whether the
  file changed; whether this server answers that question is NOT established. If
  every run downloads the whole file, that is the reason. The package tool decides by
  the file's hash and the label.
- **Google's page `https://www.google.com/earth/about/versions/` says (read 2026-11-13) that Earth Pro on
  desktop will no longer be available for download beginning June 25, 2027.** After that the address
  may stop answering: the recipe then fails and publishes nothing, and the item stays at its last version.
- If the address answers "not found" or "access denied", Google moved the file. Read
  Google's page for Earth Pro in a browser, then correct the recipe.
- The file is about 100 MB (100802200 bytes on 2026-11-13). The copy to the share is
  the slowest step. The processor waits 30 minutes by default (`pcman_timeout`).
- The downloader keeps the file under the name of the address, `googleearthprowin-x64.exe`.
  The cache therefore holds one file, replaced by each new download.
- Whether the EXE's own ProductVersion is the number that Google's pages call the
  version of Earth Pro is NOT established. The first dry run shows it.
- The recipe's `NAME` is `GoogleEarthPro` and `PCMAN_TEMPLATE` is `google-earth-pro`. Change
  the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) skips the download. The file is not
  checked at all; the version is still read from it.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that the Description of both recipes
and the top of this README say that the download is not verified, that a real run is
refused, and that nothing was rehearsed and what was fetched, that this README states no
hash, that every argument is an input that the shared processors declare, that the
version step comes after the end of the check phase and the cimian recipe passes its
output as the label, that this README has no `make-override` without `--override-dir`
and runs no recipe by its identifier, and that nothing site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
