# Win-GoogleEarthPro

A Windows recipe pair: Google Earth Pro, the Windows Installer database (`.msi`) cut out of the full (offline) `.exe` installer that Google serves at a fixed address.

**Status. Changed after its first run, NOT run in its new form. The first run under AutoPkg 2.9.0, on 2026-11-13 (`make-override` and `verify-trust-info` OK, then the dry run and two later runs), downloaded `googleearthprowin-x64.exe` (100802200 bytes) and stopped each time at the step `WindowsExeVersion` with `googleearthprowin-x64.exe: the file has no version resource (RT_VERSION).` (exit 70); nothing was published. 7-Zip's listing of that file, the same day, showed a PE32 GUI executable (Intel 80386, linker 14.0, created 2026-08-17) with one resource `.rsrc/1033/BINARY/ID_MSI` of 63475712 bytes: a Windows Installer database ("This installer database contains the logic and data required to install Google Earth Pro") whose cabinet 7-Zip lists as 317 files. So the EXE is a wrapper around one MSI. Because of this the recipe was changed: `WindowsExeVersion` is gone, and this folder's processor `GoogleEarthProMsiExtractor` cuts the MSI out of the EXE; the importers then get the `.msi` and read its version from it themselves. The extractor was run on a copy of that file, outside AutoPkg: it wrote an MSI of 63475712 bytes that begins with the signature of a Windows Installer database, and the same bytes on a second run. Other facts read on 2026-11-13: `https://dl.google.com/dl/earth/client/advanced/current/googleearthprowin-x64.exe` answered a HEAD request with 200 and no redirect, `Content-Length` 100802200, `Last-Modified` 2026-08-20; the address holds no version; no hash was found for the file. Google's page `https://www.google.com/earth/about/versions/` (read the same day) says that Earth Pro on desktop will no longer be available for download from June 25, 2027. TO BE FILLED IN after a reading on a machine with `msiinfo` and a test install (NOT established until then): the MSI's ProductVersion: `<not read; expected four numbers, 7.3.x.y>`; that the extracted MSI installs alone with `msiexec /i <file> /qn`: `<not tested; the wrapper may pass properties or run steps of its own, unread>`. Also NOT established: that Google's own download page links exactly this address, that Google publishes a hash or a signature check for this file (the writer saw none and knows of none), the MSI's upgrade code, whether it installs per machine, the path of the installed program, that Google's server answers the questions that AutoPkg asks about a changed file, and any install on a PC. The earlier note that the full installer takes `OMAHA=1` as its silent argument (the writer's knowledge, NOT read from Google and NOT tested) now concerns only the wrapper, which the recipe no longer publishes. When a run fails, STOP: nothing was written; correct the recipe, and only then look at the trust information. Never accept new trust information first.**

**Not verified. The download is NOT verified: Google publishes no hash for the file, and a check of the signature is not built. The MSI is a part cut out of that unverified file, so it is NOT verified either. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true. Do not set it before the signature check exists. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template google-earth-pro` (no `--version` for an MSI). Nothing has been installed on a PC. The Windows overrides folder is not one of AutoPkg's override folders, so every override command here carries `--override-dir`: see the paragraph below.**

**Results of 2026-11-13, newer than the status above; where the two differ, this paragraph holds. A version of four numbers is written here as `7.3.7(.1327)`** (the three numbers and, in brackets, the fourth). The recipe in its new form ran under AutoPkg 2.9.0 into a scratch Cimian repository with a hand-made first pkginfo of the item (`verify-trust-info` OK, a dry run, a real run with `cimian_allow_unverified`, a second real run): the extractor wrote the MSI, the real run published `google-earth-pro-7.3.7(.1327).msi` (63475712 bytes), and the second run said that nothing is new. Read from the MSI: ProductVersion `7.3.7(.1327)`, product code `{3D62248F-DE98-4CEB-A1D9-E69073E085D3}`, upgrade code `{57BB4BEB-FE55-4FAD-98E2-1C6C73B0D054}`, `ALLUSERS` 1. On one Windows 11 test PC, as SYSTEM from a scheduled task: the wrapper `<the .exe> OMAHA=1` ended with exit code 0 after 15 seconds and installed the product; after `msiexec /x` of the product code, **the extracted MSI alone, `msiexec /i <file> /qn /norestart`, ended with exit code 0 after 7 seconds**; both files' signatures were valid (Google LLC); the PC listed `Google Earth Pro` with DisplayVersion `7.3.7(.1327)` and had `C:\Program Files\Google\Google Earth Pro\client\googleearth.exe`. The program was not started, an upgrade over an older version was not tested, whether the wrapper sets up anything that the MSI alone does not was not compared, and no Cimian client installed it. The download is still NOT verified.

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `GoogleEarthPro-Win.download.recipe` | `com.github.serrc-techops.download.GoogleEarthPro-Win` | Downloads the Google Earth Pro installer that Google serves at a fixed address (an EXE), kept under the file name of the address, and cuts the MSI out of it (`GoogleEarthProMsiExtractor`, in this folder). It has no hard check |
| `GoogleEarthPro.cimian.recipe` | `com.github.serrc-techops.cimian.GoogleEarthPro` | Parent: the download recipe. Hands the MSI to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `GoogleEarthPro.pcman.recipe` | `com.github.serrc-techops.pcman.GoogleEarthPro` | Parent: the download recipe. Hands the MSI to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `GoogleEarthPro.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `GoogleEarthPro.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The steps of the download recipe are `URLDownloader`, `EndOfCheckPhase` and then
`GoogleEarthProMsiExtractor`, a processor of this folder (see "The MSI inside the EXE"
below). It writes the MSI beside the download and sets `pathname` to it; the EXE's path
is kept in `googleearthpro_wrapper_pathname`. Neither importer is given a version label:
for an MSI both read the MSI's own ProductVersion.

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What protects, and what does not

Nothing proves that the downloaded file is what Google published: there is no vendor
hash, and a signature check is not built. The MSI is cut out of that file, so nothing
proves it either. The shared importer knows this: no step of the recipe sets
`checksum_verified` with the hash of the file, so a real run is refused before the
package tool starts. What remains does not replace a verification.

- **The same product.** The package tool refuses an MSI whose upgrade code differs
  from the template's (`CimianImporter` likewise, unless the override sets
  `cimian_allow_product_change`). So another product cannot be published under the
  name of this template once the template exists. The MSI's upgrade code was NOT read.
- **The label.** The recipe gives no version label. For an MSI the importers take the
  MSI's own ProductVersion. That is data in the file: it shows what the file claims, and
  proves nothing about where the file came from.
- **The extractor's checks.** `GoogleEarthProMsiExtractor` takes only the one resource
  named `BINARY`/`ID_MSI` with exactly one language, inside the file and its section, at
  most 512 MiB, beginning with the signature of a Windows Installer database. These
  checks say that the part has the shape of an MSI; they say nothing about its origin.

An MSI of the right product with other content (a changed file of the vendor, or a
changed download on the way) would pass these checks.

## The MSI inside the EXE

The EXE has no version resource, so no version can be read from it. It holds one
resource of the type `BINARY` with the name `ID_MSI`, both stored as names, not numbers.
`GoogleEarthProMsiExtractor` reads the PE file's resource directory in Python (it runs
no program and never executes the file), finds that resource, checks it as said above,
and copies its bytes as they are into `googleearthprowin-x64.msi` beside the download,
through a temporary file and a rename: no partial file is left, and a link at the target
is refused. The same EXE gives the same MSI, byte for byte, so the importers' "Nothing
new" (by the file's hash) holds. With `-v` it prints one line with the EXE's size and
the MSI's size. If it stops (no such resource, two of them, two languages, a part that
is not an MSI, a part that leaves the file), the run fails, nothing is written, and the
file is not what the recipe expects: read it before anything else.

The importers then read the MSI's ProductVersion, upgrade code and product code with
`msiinfo`. Whether that version is the number that Google's pages call the version of
Earth Pro is NOT established: compare them at the first dry run.

## The MSI may need what the wrapper gives it

**The recipe publishes the MSI alone. The wrapper is not published and not run. Whether
the wrapper passes properties to the MSI, runs steps of its own before or after it, or
installs something beside it, was NOT read.** If it does, the MSI alone may install
differently from the EXE, or not at all. A person checks it before any PC other than a
test PC gets the item:

1. Read the MSI's ProductVersion with `msiinfo` (step c shows it too). Nobody has read it.
2. Install the MSI alone on a test PC with `msiexec /i <file> /qn` and read its log;
   start Earth Pro afterwards. Nobody has done that.
3. Compare the version that the installed program shows with the label. If they do not
   agree by their numbers, stop and tell the owner before anything is published.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.**

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

**An override made before this change** has the trust information of `WindowsExeVersion` and not of `GoogleEarthProMsiExtractor`: its trust check fails after the update of this repository. That is the expected failure. Read the change (`autopkg verify-trust-info -vv`, see step 6 or f), then accept it.

## With any Cimian repository

This way needs AutoPkg, `msiinfo` (msitools: `brew install msitools`) for the MSI, and nothing of the owner's: no package tool. It uses `GoogleEarthPro.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

3. **`msiinfo` on the PATH of the run** (`brew install msitools`): `CimianImporter` reads the MSI's ProductVersion and its two codes with it, and does not parse an MSI itself. A job that `launchd` starts may have no Homebrew on its `PATH`, so the importer looks in `/opt/homebrew/bin` and `/usr/local/bin` too; the input `cimian_path` changes that list. This recipe cannot run without it: its step passes an empty `version`, and an argument of a step wins over an override's `Input`, so the label can only come from the MSI. The run stops and names the facts that are missing.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `google-earth-pro`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`). **An item made earlier from the EXE is not a template for the MSI:** its type and its check differ, and the upgrade code check has nothing to compare with. Look at it before the first real run.

   **For an `.msi` nothing needs completing for a silent install, IF the MSI installs alone:** the client runs `msiexec /i <file> /qn /norestart` itself and then the arguments of the item (`InstallerService.cs:936-948`), so the recipe gives no silent arguments, and `CimianImporter` writes the install check of an MSI (an `installs` entry of type `msi` with the MSI's codes and version). That this MSI installs alone was NOT tested (see "The MSI may need what the wrapper gives it"). What the MSI's own properties allow (features, per-user or per-machine) is the template's business: give them as `installer: {args: [...]}` in the override's `pkginfo`. An MSI whose upgrade code is not the template's, or that has none where the template's item had one, is refused (Windows Installer does not upgrade across upgrade codes): `cimian_allow_product_change` set to true in the override allows it, with a WARNING.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i GoogleEarthPro-Win
    autopkg list-recipes | grep -i GoogleEarthPro.cimian

Each name must be listed once, from this repository. Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> GoogleEarthPro.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `GoogleEarthPro.cimian`, not a path. It writes `<the Windows overrides folder>/GoogleEarthPro.cimian.recipe` with the identifier `local.cimian.GoogleEarthPro` and the trust information of the recipes and the processors (`GoogleEarthProMsiExtractor` among them). **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.GoogleEarthPro`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.GoogleEarthPro`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each): first the extractor's line with the two sizes, then

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.msi (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The `<version>` is the MSI's ProductVersion: read it and compare it with "The MSI may need what the wrapper gives it". The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on (NOT YET: see the status line)

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/GoogleEarthPro.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

**Not yet.** This download has no verification step, so `CimianImporter` refuses the real run below until the override also sets `cimian_allow_unverified` to true, which a person decides only after the file was checked by hand and the MSI was installed alone on a test PC, and which is then written in the override's `Input`, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_allow_unverified bool true' \
        <the Windows overrides folder>/GoogleEarthPro.cimian.recipe

With it the run prints `WARNING: published WITHOUT a verified download` and the report row says `published, NOT verified`.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleEarthPro.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the MSI under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

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
   (the share mounted). For an MSI the package tool needs `msiinfo` (the processor
   looks for it in its default `PATH`, which has the Homebrew folders).

3. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. The template keeps the name of the item that
   it replaces. If the package tool's repository has an item for Google Earth Pro
   already, look at it first: an item of the kind `choco` is not the template (the first import goes
   beside it without any option, and a person removes the Chocolatey item by hand); an item made
   from the EXE is not a template for the MSI either; an item that an earlier run of this step made
   from the MSI is, and this step is then not needed; set its name in the override (step b).
   The command, NOT run for this recipe, with the MSI that the extractor wrote (the
   dry run of step c leaves it beside the download in AutoPkg's cache):

       pcman import <path of googleearthprowin-x64.msi> --name google-earth-pro \
           --directory <the folder of the item> \
           --architectures x64 \
           --display-name "Google Earth Pro" --category <the category of the item> --developer Google \
           --description "<one line about the item>" \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. The install
   arguments are not given: for an MSI the client runs `msiexec /i <file> /qn /norestart`
   itself. **That the MSI installs alone this way was NOT tested on a PC** (see "The MSI
   may need what the wrapper gives it"): install it on a test PC before it goes to any
   other PC. `OMAHA=1`, the writer's knowledge of the wrapper's silent argument (NOT read
   from Google and NOT tested), is not given: it belongs to the EXE, which is not
   published. `--architectures x64` is from the name of the file (`-x64`), NOT from the
   MSI's own platform: read it before the first import. A person changes the template
   later; nothing else does. **If the template is made from the installer that is
   current at the vendor, the first run says "Nothing new" (see step c). To see a dry
   run that would publish, make the template from an older version.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i GoogleEarthPro-Win
    autopkg list-recipes | grep -i GoogleEarthPro.pcman

Each name must be listed once, from this repository. Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> GoogleEarthPro.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `GoogleEarthPro.pcman`, not a path. Expected (not
run for this recipe in its new form): it writes `<the Windows overrides folder>/GoogleEarthPro.pcman.recipe`
with the identifier `local.pcman.GoogleEarthPro` and the trust information of the two
recipes and of the two processors that are not part of AutoPkg itself
(`GoogleEarthProMsiExtractor`, `PcmanImporter`). **Open the written file and read
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
    google-earth-pro   <the MSI's version>    Production  dry run, nothing written, NOT verified

Before that, the run prints the extractor's line with the two sizes (see "The MSI inside
the EXE"). The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line is
`Nothing new: ... is in the repository already. Nothing was written.` instead. That is
correct.

## d. Switch a real run on (NOT YET: see the second paragraph at the top)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file. Nothing was published. Publish by hand after
    checking the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template google-earth-pro

The file is the MSI that the extractor wrote. Do not add `--version` for an MSI: the
package tool takes the MSI's own version. Then `pcman catalogs` (step e.3).

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
       google-earth-pro   <the MSI's version>    Production  published, NOT verified

   The repository then has the MSI under `pkgs/` and its pkginfo under
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
  every run downloads the whole file, that is the reason. The extractor runs at every
  run that gets past `EndOfCheckPhase`; the importers decide by the MSI's hash and its
  version.
- **Google's page `https://www.google.com/earth/about/versions/` says (read 2026-11-13) that Earth Pro on
  desktop will no longer be available for download beginning June 25, 2027.** After that the address
  may stop answering: the recipe then fails and publishes nothing, and the item stays at its last version.
- Google's help page `https://support.google.com/earth/answer/168344` (read 2026-11-13) lists direct
  addresses with three numbers of the version in the name, for example
  `https://dl.google.com/dl/earth/client/advanced/current/googleearthprowin-7.3.7-x64.exe` (and 7.3.6,
  7.3.4, 7.3.3 and older). They give no fourth number and no hash, and the recipe does not use them. A
  person who wants to pin a release may set `DOWNLOAD_URL` in the override to one of them; whether
  such a file has the same `BINARY`/`ID_MSI` resource was NOT read.
- If the address answers "not found" or "access denied", Google moved the file. Read
  Google's page for Earth Pro in a browser, then correct the recipe.
- The download is about 100 MB (100802200 bytes on 2026-11-13), the MSI about 63 MB
  (63475712 bytes). The copy to the share is the slowest step. The processor waits 30
  minutes by default (`pcman_timeout`).
- The downloader keeps the file under the name of the address, `googleearthprowin-x64.exe`,
  and the extractor writes `googleearthprowin-x64.msi` beside it. The cache therefore
  holds these two files, each replaced by the next run.
- The recipe's `NAME` is `GoogleEarthPro` and `PCMAN_TEMPLATE` is `google-earth-pro`. Change
  the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) skips the download. The file is not
  checked at all; the extractor still cuts the MSI out of it, so it must be the EXE.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the three files are property lists, that the Description of the recipes
and the top of this README say that the download is not verified, that a real run is
refused, and what was run and what was not, that this README states no hash, that every
argument is an input that the processors declare, that the extractor comes after the end
of the check phase and that no recipe passes a version label for the MSI, that this
README has no `make-override` without `--override-dir` and runs no recipe by its
identifier, and that nothing site-specific is in the folder.

`tests/test_msi_extractor.py` tests `GoogleEarthProMsiExtractor` on small PE files that
the test builds itself (no real installer is in this repository): the resource found and
written byte for byte, the same bytes twice, no resource, two of them, two languages, a
part without the MSI signature, a part that leaves its section or the file, a part over
the size limit, a link at the target, and no file left behind after a failure.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
