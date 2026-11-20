# Win-AdobeReader

A Windows recipe pair: Adobe Acrobat Reader, the `.exe` installer (English by default), with the version label read from the installer file itself.

**Status. Run on 2026-10-04 under AutoPkg 2.9.0, as follows. The first import (the command of step a.3 below, run with `--no-prompt` and `--build`) made the template `adobereader` (an EXE item, label `26.2.21931.0`, architectures `x86,x64`) in the package tool's repository, in the catalog `Production`. The first import went beside the Chocolatey item `adobereader` (version 1.0) without any option of the tool; the Chocolatey item file and its `adobereader-1.0` pkginfo remain until a person removes them by hand, and `pcman validate` warns that the item has two versions until then. The override of `AdobeReader.pcman` (`make-override` with `--override-dir`, `ParentRecipe` right, `verify-trust-info` OK, `pcman_dry_run` false) then ran for real: the products file, the download and the label step went through, and the importer REFUSED the run with `The download was not verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file. Nothing was published. ...` (exit 70), which is what an unverified download must get; `pcman_allow_unverified` was not set. The override downloaded the file again about ten minutes after the first import, and its hash was the imported file's. The hand-import form `pcman import <file> --template adobereader --version <the label> --no-prompt --if-new --dry-run` printed `Nothing new: adobereader <label> exists already ...` with exit 3. `pcman catalogs` ran once for all the new items together (2026-10-04): the tool's configured command ran `makecatalogs` on the repository's server, with exit 0, and wrote the catalogs `All` and `Production`, 106 items each. The silent switch `/sAll /rs /msi EULA_ACCEPT=YES` was used on 2026-10-04: the operator took it from Adobe's documentation for administrators, and the string `/sAll` is in the file; it was NOT tested on a PC. No `--install-path` was given (it must be read on a PC after an install), so the template has NO install check until a person adds one; the client then relies on the ManagedInstalls registry. Still NOT established after those runs: that the switch installs silently on a PC; an install check; any install; what the installed Reader shows as its version. Facts of the source that the writer fetched on 2026-10-02, before those runs: Read from Adobe's servers on that day (no browser identity was needed; an earlier HEAD request got 403, a GET answers 200): (1) `https://rdc.adobe.io/reader/products?lang=en&platformArch=64&site=landing&os=Windows%2010&preInstalled=&country=US&nativeOs=Windows%2010&api_key=dc-get-adobereader-cdn`, the public endpoint that Adobe's own download page calls, answered 200 with a JSON object (378 bytes): `products.reader` is a list of one element with `displayName` `Reader 2026.002.21931 English for Windows (Recommended)`, `fileSize` 748.0 and `version` `26.002.21931`; `products.dcPro` and `addons` are beside it and are not used; the processor's parsing function was run on a saved copy of this answer and gave the version, the packed version `2600221931` and the two installer addresses below; (2) a HEAD request for `https://ardownload2.adobe.com/pub/adobe/reader/win/AcrobatDC/2600221931/AcroRdrDC2600221931_en_US.exe` (643995232 bytes) and one for `.../AcroRdrDC2600221931_MUI.exe` (739174432 bytes) answered 200; the same names with `x64` (`AcroRdrDCx64...`) answered 404 under this scheme; (3) the real file `AcroRdrDC2600221931_en_US.exe` (643995232 bytes) was downloaded, with no browser identity, and read with `WindowsExeVersion`: its ProductVersion is `26.2.21931.0` (the FileVersion and the numbers of the fixed file information are the same), so the label `version` is `26.2.21931.0`; its ProductName is `Adobe Self Extractor`, the outer self-extracting wrapper and not `Adobe Acrobat Reader`, so a check of the product name would mislead; the products file's `26.002.21931` and the file's `26.2.21931.0` are one version by their numbers (26, 2 and 21931), the middle part of the products file written with leading zeros and the file's with a fourth part. NOT established: that the products file is stable (it is not documented by Adobe, and its `api_key` is the fixed public key that the download page sends); that the installer scheme, seen for one version, holds for the next; whether Adobe offers an installer for x64 under another scheme (the two that were seen are the 32-bit installers); the silent switch on a PC, the install path and an install check (the switch and the architecture list `x86,x64`, read from the PE header of the wrapper, which is a 32-bit program, were used on 2026-10-04); the version text that the installed Reader shows after the wrapper has installed it (only the wrapper's was read); that the next release keeps this spelling; any install on a PC. The download is NOT verified: Adobe publishes no hash for the file, and the shared signature check (`AuthenticodeVerifier`) is not part of this recipe. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true. Do not set it before a signature check is part of this recipe. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template adobereader --version <the label>` (the installer's own ProductVersion, as the dry run shows it). The tests use a products file excerpt that the writer wrote by hand after the real answer of 2026-10-02 (the shape of `reader` and `dcPro`, not saved from the real server, and with the other keys cut), so they prove what the code does with an answer of that form and nothing about Adobe today. The first install on a test PC is the check of what is NOT established. When a run fails, STOP: nothing was written (a run that fails before the import writes nothing). Read the real products file and Adobe's download page in a browser, correct the processor or the recipe, and only then look at the trust information. Never accept new trust information first to make a failure go away. Every override command here carries `--override-dir`: see the paragraph "Run every override with `--override-dir`" below. No run of this recipe has published anything, and none can while the download is unverified; nothing has been installed on a PC.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `AdobeReader-Win.download.recipe` | `com.github.serrc-techops.download.AdobeReader-Win` | Reads the current Reader version from Adobe's products file, builds the address of the installer from it, downloads it, and reads the version that the installer file carries. It has no hard check |
| `AdobeReader.cimian.recipe` | `com.github.serrc-techops.cimian.AdobeReader` | Parent: the download recipe. Hands the file to `CimianImporter` with the installer's own version as the label, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `AdobeReader.pcman.recipe` | `com.github.serrc-techops.pcman.AdobeReader` | Parent: the download recipe. Hands the file to the package tool (`pcman`) with the installer's own version as the label, which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `AdobeReader.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `AdobeReader.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The processor `AdobeReaderInfoProvider.py` is in this folder. It reads one file of
Adobe's servers (the products file, a JSON object) and outputs `url`, `version` (the
products file's text, `26.002.21931`) and `adobe_packed_version` (`2600221931`). It outputs
no hash: Adobe publishes none. The processor `WindowsExeVersion` is shared
(`../Win-SharedProcessors/`, see its README): after the download it reads the
ProductVersion from the installer file and sets `version` to it, so that the label for the
package tool is the file's own, not the products file's. Neither recipe stops on an
unchanged download, so an import that failed is tried again at the next run.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

How strict the provider is:

- The one fetch goes to a fixed host over https (`rdc.adobe.io`). A redirect is not
  followed: it is an error. A status other than 200 is an error. The answer may be at most
  64 KiB, the fetch has a time limit of 120 seconds, and the answer must be UTF-8 text.
- The answer must be a JSON object whose `products.reader` is a list of exactly one element,
  and the element's `version` must have the form `NN.NNN.NNNNN` (two, three and five
  digits). Anything else stops the run, and no address is built from it.
- The language input is `en_US` or `MUI` and nothing else. The address is
  `https://ardownload2.adobe.com/pub/adobe/reader/win/AcrobatDC/<packed>/AcroRdrDC<packed>_<language>.exe`;
  the provider does not fetch it, the downloader does.

## What protects, and what does not

Nothing proves that the downloaded file is what Adobe published: there is no vendor
hash, and the shared signature check (`AuthenticodeVerifier`) is not part of this recipe. The shared importer knows this: no step of
the recipe sets `checksum_verified` with the hash of the file, so a real run is refused
before the package tool starts. What remains does not replace a verification.

- **The label.** The recipe passes the ProductVersion that the installer file itself
  carries (from `WindowsExeVersion`), not the version of the products file. It is
  data in the file, so it proves nothing about where the file came from. The dry run shows
  both: the provider prints the products file's version, and `WindowsExeVersion` prints
  the file's strings and the label it took. A person reads them and checks that they
  agree by their numbers. They are not written in the same way: on 2026-10-02 the products
  file had `26.002.21931` and the file `26.2.21931.0` (see the status line). The file's
  ProductName is the wrapper's (`Adobe Self Extractor`), so nothing here checks the product
  name.
- **The same product.** For an MSI the package tool refuses a different upgrade code.
  Whether it has an equivalent check for an EXE was NOT established by the writer. For
  this recipe the checks are the dry run and a person's look at what it plans.

A changed file of the vendor, or a changed download on the way, would pass both.

## The label is the wrapper's version, and nothing compares it with the product's

**The label that the package tool gets is the `ProductVersion` of the downloaded installer
file, which is Adobe's self-extracting wrapper (its ProductName is `Adobe Self Extractor`),
and not the version of the Reader that the wrapper installs. No step of this recipe compares
the two.** The version of Adobe's products file (`26.002.21931` on 2026-10-02) only builds
the address, and the version that the installed Reader shows has not been read by anyone. If
Adobe's wrapper stopped tracking the product (a number older or newer than the Reader's), the
recipe would still publish under the wrapper's number, and that number orders the versions in
the repository. The recipe does not check this at any run. A person checks it, at the first
dry run:

1. Run the dry run with `-v` (step c) and read the two versions that it prints: the
   provider's line with the products file's version, and the line `version is ..., taken
   from ...` of `WindowsExeVersion` with the label.
2. Compare them by their numbers. On 2026-10-02 they were `26.002.21931` and `26.2.21931.0`:
   the same three numbers (26, 2 and 21931), the middle part written with leading zeros in
   the products file and the label with a fourth part. If the three numbers differ, stop and
   tell the owner before anything is published.
3. After the first install on a test PC, compare the label with the version that the
   installed Reader reports (its About page, or its entry in Windows' list of installed
   programs). Nobody has done that. Whether the Cimian client sees the label and that version
   as the same version is NOT established.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `AdobeReader.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `adobereader`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the first step of the package tool's way below marks what is only the writer's knowledge or was not read), so they are left for a person who has read them in the vendor's documentation and tried them on a test PC. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i AdobeReader-Win
    autopkg list-recipes | grep -i AdobeReader.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> AdobeReader.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `AdobeReader.cimian`, not a path. It writes `<the Windows overrides folder>/AdobeReader.cimian.recipe` with the identifier `local.cimian.AdobeReader` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.AdobeReader`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.AdobeReader`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on (NOT YET: see the status line)

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/AdobeReader.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

**Not yet.** This download has no verification step, so `CimianImporter` refuses the real run below until the override also sets `cimian_allow_unverified` to true, which a person decides only after the file was checked by hand, and which is then written in the override's `Input`, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_allow_unverified bool true' \
        <the Windows overrides folder>/AdobeReader.cimian.recipe

With it the run prints `WARNING: published WITHOUT a verified download` and the report row says `published, NOT verified`.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `AdobeReader.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `AdobeReader.pcman` where this README used to say `AdobeReader.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `AdobeReader.cimian.recipe` (when that recipe ran the package tool) must be made again from `AdobeReader.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `AdobeReader.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   it replaces. If the package tool's repository has an item `adobereader` already,
   look at it first: an item of the kind `choco` is not the template (see the status line:
   the first import of 2026-10-04 went beside it without any option, and a person removes the
   Chocolatey item by hand); an item that an earlier run of this step made is, and this step is then not needed.
   The command, in the form that ran on 2026-10-04, with a real installer of the current release:

       pcman import <path of the installer, AcroRdrDC<packed>_en_US.exe> --name adobereader \
           --version <the label that the first dry run prints> \
           --directory <the folder of the item> \
           --install-arguments '/sAll /rs /msi EULA_ACCEPT=YES' \
           --architectures x86,x64 \
           --display-name "Adobe Acrobat Reader" --category <the category of the item> \
           --developer Adobe --description <one sentence about the item> \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   The label after `--version` is what the recipe will pass for later versions: the
   ProductVersion of the installer file, as `WindowsExeVersion` reads it (`26.2.21931.0` for the
   file of 2026-10-02 and 2026-10-04, not the products file's `26.002.21931`). The silent
   switch `/sAll /rs /msi EULA_ACCEPT=YES` was **used on 2026-10-04, not tested on a PC**: it is from Adobe's
   documentation for administrators, and the string `/sAll` is in the file. `--architectures x86,x64` is from the
   PE header: the wrapper is a 32-bit program, and the address scheme that was seen gives the 32-bit
   installers (whether an x64 installer exists is NOT established). `--install-path` was left out because the path must be read on a PC after an
   install; the template then has no install check, and a wrong path would install again at every run, so add it
   only after reading it. A switch that begins with `-` needs the form `--install-arguments=<the switch>` (see the Google Drive README): this one begins with `/`.
   A person changes the template later; nothing else does. **If the template is made from the installer that is
   current at Adobe, the first run says "Nothing new" (see step c). To see a dry run
   that would publish, make the template from an older version.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i AdobeReader-Win
    autopkg list-recipes | grep -i AdobeReader.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> AdobeReader.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `AdobeReader.pcman`, not a path. Expected (not
run): it writes `<the Windows overrides folder>/AdobeReader.pcman.recipe` with the
identifier `local.pcman.AdobeReader` and the trust information of the two recipes and
the three processors that are not part of AutoPkg itself (`AdobeReaderInfoProvider`,
`WindowsExeVersion`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.AdobeReader`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.AdobeReader`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**`-v` prints what each processor says about its own work; `-vv` would add every processor's
inputs and outputs, `pcman_root` and the repository among them, to the log: keep such a log private.** Expected, from
the code and the rehearsals of the other folders, NOT printed by this recipe yet, when
the current version is not yet in the repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file, or signature_verified together with the signature_sha256 of this file. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name         Version                          Catalogs    Result
    adobereader  <the installer's ProductVersion>  Production  dry run, nothing written, NOT verified

The run also prints, before that, one line of the provider with the version of
Adobe's products file (`Current Adobe Acrobat Reader according to Adobe's products file: ...`)
and two lines of `WindowsExeVersion`: the file's ProductVersion, FileVersion and the
numbers of its fixed file information, and `version is <the label>, taken from <where>`.
**Read the two versions and compare them.** On 2026-10-02 they were `26.002.21931` (the
products file) and `26.2.21931.0` (the file), one version by its numbers. If they do not agree
by their numbers, stop and tell the owner: the label of the package tool is the file's. If the
current version is in the repository already (the template was made from it), the line
is `Nothing new: ... is in the repository already. Nothing was written.` instead. That is
correct.

If Adobe changes the products file so that the processor cannot read it, the run fails
with a line that begins `Adobe's products file` and publishes nothing. If the line says
that the address answered with a redirect, stop and tell the owner. If the downloader
reports that the installer's address answered 404, the scheme of the addresses has changed:
read Adobe's download page in a browser and correct the processor.

## d. Switch a real run on (NOT YET: see the status line)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file, or signature_verified together with the
    signature_sha256 of this file. Nothing was published. Publish by hand after checking
    the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template adobereader --version <the label>

The label is the installer's own ProductVersion, as the dry run shows it (an EXE has no
version that the package tool can read for itself). Then `pcman catalogs` (step e.3).

**Only after the signature check exists, or when a person has decided to accept an
unverified download:** the override allows it. Both lines are needed.

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/AdobeReader.pcman.recipe
    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_allow_unverified bool true' \
        <the Windows overrides folder>/AdobeReader.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.pcman.recipe

A change of the `Input` does not break trust (found with 7-Zip). Do not use `-k`
instead: on the command line it applies to every recipe of that run. A run then prints
`WARNING: published WITHOUT a verified download ...` at any verbosity, and the report's
row says `published, NOT verified`.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.pcman.recipe

   Only after both lines of step d. Expected: `Published adobereader ...`, the warning
   `published WITHOUT a verified download`, and the table

       The following versions were published by the package tool:
       Name         Version                          Catalogs    Result
       adobereader  <the installer's ProductVersion>  Production  published, NOT verified

   The repository then has the installer under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions adobereader` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.` (On 2026-10-04 the first run of a fresh override printed the line `Nothing new: ...` after it had downloaded the file again, because a new override gets a new cache folder; `Nothing downloaded, packaged or imported.` was not seen in that run, and is the line of a later run of the same override.)

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again. (Not run with this recipe.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The input of the download recipe is `ADOBE_LANGUAGE` (default `en_US`, English; `MUI`
  is the installer for all languages). Change it in the override's `Input`, not in the
  recipe. The cached file's name has the packed version and the language in it
  (`AcroRdrDC<packed>_<language>.exe`): use one language for one override.
- The products file also lists the paid Acrobat (`dcPro`) and add-ons. The processor reads
  `reader` only.
- The installer is about 640 MB (`en_US`) or 740 MB (`MUI`). `WindowsExeVersion` reads only
  the headers and the version block, never the whole file. The copy to the share is the
  slowest step. The processor waits 30 minutes by default (`pcman_timeout`); if that is
  not enough, set `pcman_timeout` in the override's `Input`.
- The version of the products file has the form `26.002.21931`; the installer's name
  has the same digits without dots (`2600221931`); the installer file carries `26.2.21931.0`
  as its ProductVersion (read on 2026-10-02). The packed version is made from the products
  file's text, not from the file's.
- The installer is a self-extracting wrapper (ProductName `Adobe Self Extractor`). The version
  that the installed Reader shows is NOT established.
- The recipe's `NAME` is `AdobeReader` and `PCMAN_TEMPLATE` is `adobereader`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) skips the download. The file is not
  checked at all.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of products file (the excerpt in `tests/`
is written by hand after the real answer of 2026-10-02, not saved from the real server; the
other texts are made up), that both recipes are property lists, that every argument is an
input that the processor declares, that the cimian recipe passes the label of
`WindowsExeVersion`, that the Description of both recipes and the top of this README say
that the download is not verified and that a real run is refused, that this README states
no hash, that it has no `make-override` without `--override-dir` and runs no recipe by its
identifier, that it says what was NOT done, and that nothing site-specific is in the
folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
