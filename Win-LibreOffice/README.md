# Win-LibreOffice

A Windows recipe pair: LibreOffice, the 64-bit `.msi` of the "fresh" line (the newer of the two lines that The Document Foundation offers).

**NOT WORKING (expected). This recipe pair is expected to stop at its first run and publish nothing. The provider reads a hash file (`<the MSI's name>.sha256`) that the vendor's server did not show on 2026-10-02 (the address answered 404 once and 500 once, and the folder holds no such file), so the run is expected to fail at `LibreOfficeInfoProvider` before the download is checked, and LibreOffice stays a hand import until the provider is changed to read a hash from where the server shows it. The first dry run with AutoPkg 2.9.0 (2026-10-04) stopped there, as expected: `LibreOfficeInfoProvider` said "The server answered 404 Not Found for the hash file." and nothing after the provider has run. Whether the pair stays in this repository is the owner's decision at the merge.**

**Status. One dry run with AutoPkg 2.9.0 (2026-10-04) stopped at the provider, as expected: `LibreOfficeInfoProvider` said "The server answered 404 Not Found for the hash file." Nothing after the provider has run, and nothing of this pair has run with the package tool, a share or a PC. Some facts of the source were fetched by the writer on 2026-10-02: the server answered only now and then. VERIFIED: (1) `https://download.documentfoundation.org/libreoffice/stable/` answered 200 with no redirect; it is a mirrorbrain HTML index whose version links are exactly `25.8.7/`, `26.2.5/`, `26.2.6/`, `26.8.0/` and `26.8.1/` (three lines at once, with two versions in two of them), beside other links (the sort links `?C=N;O=D`, `/libreoffice/`, `/mirrorbrain.css`, a mailto and `http://mirrorbrain.org/`) that are not version folders; the processor read a saved copy of it as `fresh` 26.8.1 and `still` 26.2.6; (2) `.../stable/26.8.1/win/` answered 200 and lists `aarch64/`, `x86/` and `x86_64/`; (3) the listing of `.../stable/26.8.1/win/x86_64/` (it answered once) holds, for the main MSI and for every helppack and langpack, four files: `LibreOffice_26.8.1_Win_x86-64.msi`, `...msi.mirrorlist`, `...msi.asc` and `...msi.asc.mirrorlist`, and the `_sdk.msi` set in the same way. **THE HASH FILE THAT THE PROVIDER EXPECTS DOES NOT EXIST: there is no `.sha256`, `.md5` or `.sha1` file in that folder.** The address `<index>/<version>/win/x86_64/LibreOffice_<version>_Win_x86-64.msi.sha256` answered 404 once and 500 once. The folder offers a `.mirrorlist` page per file (mirrorbrain, which usually shows the file's hashes on that page) and a `.asc` signature. Until the owner reads the `.mirrorlist` page of the MSI on the build Mac and the provider is changed to read the hash from wherever it is shown, this recipe stays a dry run that fails at the provider (`LibreOffice hash file:` or `The server answered 404 ... for the hash file`), nothing is written, and LibreOffice stays a hand import. The code and the tests of the provider still have the shape of the hash file that does not exist; they are the pattern for the next step, not a working check. NOT VERIFIED: the `.mirrorlist` page and a `.meta4` address never answered, so where mirrorbrain shows a hash, and in what form, is not established; a HEAD of the MSI answered 500 once, so the MSI's address and redirect behaviour are not established either; nor are the MSI's ProductVersion and UpgradeCode, the template, `pcman catalogs`, and any run with AutoPkg beyond the provider. When the provider is changed, the first run on the build Mac is the check of each fact it relies on. When a run fails, stop: nothing was written. Read the real page, and correct the recipe or `LibreOfficeInfoProvider.py` to what it shows; never accept the trust information first, and never write a hash into a recipe. If a hash is ever read from a mirror's page, stop and tell the owner, because a hash read from a mirror is not the publisher's. Where a line below says "expected", it is what the code is written to print, not something that was printed. Every override command here carries `--override-dir`: see the next paragraph.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `LibreOffice-Win.download.recipe` | `com.github.serrc-techops.download.LibreOffice-Win` | Reads the vendor's index of stable releases, takes the version of the line in `LIBREOFFICE_LINE` (default `fresh`), downloads its MSI, and stops when the file does not match the SHA-256 in the vendor's hash file |
| `LibreOffice.cimian.recipe` | `com.github.serrc-techops.cimian.LibreOffice` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `LibreOffice.pcman.recipe` | `com.github.serrc-techops.pcman.LibreOffice` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `LibreOffice.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `LibreOffice.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The processor `LibreOfficeInfoProvider.py` is in this folder. It reads the index
`https://download.documentfoundation.org/libreoffice/stable/` and keeps the links
that are exactly three numbers and a slash. The first two numbers of a version are
its line (`25.8`). `fresh` takes the highest version of the highest line and `still`
takes the highest version of the line just below it. Versions are compared **by their
numbers** (`25.10.0` is newer than `25.8.1`), never by their text or by the order of
the links. When the index holds only one line there is no `still`: that is an error,
not a fall back to `fresh`. It then reads the hash file of that version, which must
hold one line, 64 hex digits, two spaces and exactly the name of the MSI. It outputs
`url`, `version` and `expected_sha256`.

Both fetches of the processor go to one fixed host, follow **no redirect**, have a
size limit and a time limit. A redirect, a status other than 200, a page that is not
UTF-8 text or is larger than the limit, a hash file with more or less than one line,
or a file name on that line that is not the MSI's stops the run with a line that
begins `LibreOffice download index:` or `LibreOffice hash file:` (or says what could
not be fetched) and publishes nothing.

The other processors are in `../Win-SharedProcessors/` (see its README). Neither
recipe stops on an unchanged download, so an import that failed is tried again at
the next run.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What the checks prove

- **The hash.** The hash file that the provider reads does not exist on the vendor's server
  (2026-10-02, and again in the first run of 2026-10-04), so this recipe stays a dry run that fails at the provider, and LibreOffice stays
  a hand import until the provider reads the hash from where the server shows it. Once it does,
  the check shows that the file is what the publisher's page names; it does not help if the
  vendor's own server is changed.
- **The same product.** The package tool refuses an MSI whose upgrade code differs from
  the template's. Whether the two lines have the same upgrade code is not established.
- **The label.** The recipe gives no version label. For an MSI the package tool takes
  the MSI's own ProductVersion, which is not the release's three numbers. A label of
  three numbers could be refused.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg, `msiinfo` (msitools: `brew install msitools`) for the MSI, and nothing of the owner's: no package tool. It uses `LibreOffice.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `libreoffice-fresh`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **For an `.msi` nothing needs completing for a silent install:** the client runs `msiexec /i <file> /qn /norestart` itself and then the arguments of the item (`InstallerService.cs:936-948`), so the recipe gives no silent arguments, and `CimianImporter` writes the install check of an MSI (an `installs` entry of type `msi` with the MSI's codes and version). What the MSI's own properties allow (features, per-user or per-machine) is the template's business: give them as `installer: {args: [...]}` in the override's `pkginfo`. An MSI whose upgrade code is not the template's, or that has none where the template's item had one, is refused (Windows Installer does not upgrade across upgrade codes): `cimian_allow_product_change` set to true in the override allows it, with a WARNING.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i LibreOffice-Win
    autopkg list-recipes | grep -i LibreOffice.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> LibreOffice.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `LibreOffice.cimian`, not a path. It writes `<the Windows overrides folder>/LibreOffice.cimian.recipe` with the identifier `local.cimian.LibreOffice` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.LibreOffice`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.LibreOffice`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.msi (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/LibreOffice.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `LibreOffice.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `LibreOffice.pcman` where this README used to say `LibreOffice.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `LibreOffice.cimian.recipe` (when that recipe ran the package tool) must be made again from `LibreOffice.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `LibreOffice.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   it replaces. The command, with a real MSI of the fresh line:

       pcman import <path of LibreOffice_<version>_Win_x86-64.msi> --name libreoffice-fresh \
           --directory <the folder of the item> --display-name LibreOffice \
           --category <the category> --developer "The Document Foundation" \
           --description "<the description>" --architectures x64 --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. The icon is
   added as the package tool's README describes. The install arguments are not given
   here: for an MSI the package tool uses the MSI's own installer arguments. LibreOffice's
   MSI also takes properties of its own (which components, which file types it
   registers), and the vendor documents them (from the writer's knowledge, not read in
   the installer): read the vendor's documentation first, and give them to this first
   import, if the owner wants any. A person changes the template later; nothing else
   does. **If the template is made from the release that is current on the vendor's
   server, the first run says "Nothing new" (see step c). To see a dry run that would
   publish, make the template from an older release.**

4. **`still` needs its own template.** The line `still` is another product line. Do not
   point it at `libreoffice-fresh`. Make a template of its own (for example
   `libreoffice-still`, from a release of that line), and an override of its own whose
   `Input` has `LIBREOFFICE_LINE` `still` and `PCMAN_TEMPLATE` `libreoffice-still`.
   Whether the package tool would accept the older line as a new version of the fresh
   template is not established, and this README does not rely on it.

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i LibreOffice-Win
    autopkg list-recipes | grep -i LibreOffice.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> LibreOffice.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `LibreOffice.pcman`, not a path. Expected:
it writes `<the Windows overrides folder>/LibreOffice.pcman.recipe` with the
identifier `local.pcman.LibreOffice` and the trust information of the two
recipes and the three processors that are not part of AutoPkg itself
(`LibreOfficeInfoProvider`, `ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.LibreOffice`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.LibreOffice`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current release is not yet in the
repository (the lines of the 7-Zip rehearsal, with this program's name; this
program was NOT run beyond the provider, and the version is the MSI's own):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name               Version                Catalogs    Result
    libreoffice-fresh  <the MSI's version>    Production  dry run, nothing written

With `-v` the run also prints `Release of the fresh line: ...` and the vendor's
SHA-256, and then `SHA-256 verified: ...`. If the current release is in the
repository already (the template was made from it), the line is `Nothing new:
libreoffice-fresh ... is in the repository already. Nothing was written.` instead.
That is correct.

If the first run fails here, stop. It is the check of the facts in the status paragraph
at the top: a line that begins `LibreOffice download index:` or `LibreOffice hash file:`
means the page is not what the code expects, and `The server answered 30x` means a
redirect. Nothing was written. Do not accept trust information to get past it.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/LibreOffice.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.pcman.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip, not with this
program). Do not use `-k pcman_dry_run=false` instead: on the command line it applies
to every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.pcman.recipe

   Expected: `Published libreoffice-fresh <the MSI's version>.` and the table

       The following versions were published by the package tool:
       Name               Version              Catalogs    Result
       libreoffice-fresh  <the MSI's version>  Production  published

   The repository then has the MSI under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions libreoffice-fresh` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line (not seen for this program: its run of 2026-10-04 stopped at the provider):

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- A new release has a new ProductCode. Whether the UpgradeCode is the same across
  releases and across the two lines, and what happens on a PC that has LibreOffice
  from another source, is not established: test it on one PC before the PCs get the
  version.
- The inputs of the download recipe are `NAME` and `LIBREOFFICE_LINE` (default
  `fresh`). Change the line in the override's `Input`, not in the recipe. Any value
  other than `fresh` or `still` stops the run.
- Three lines at once. The index of 2026-10-02 offered three lines (`25.8`, `26.2`,
  `26.8`), two of them with two versions. The processor takes `fresh` as the highest
  version of the highest line (`26.8.1`) and `still` as the middle line (`26.2.6`), not
  the oldest. Whether that is what the owner wants is not decided.
- The index may list a version folder whose files are not yet all there. The processor
  then stops at the hash file (a status other than 200) and publishes nothing. Run
  again later.
- A version folder that is not three numbers is ignored.
- The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which the
  shared importer compares with the file it imports, so it allows a real run of this
  recipe without `pcman_allow_unverified`.
- The recipe's `NAME` is `LibreOffice` and `PCMAN_TEMPLATE` is `libreoffice-fresh`.
  Change the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the
  recipe.
- `-p` (a local file instead of the download) fails the checksum unless the file is
  the vendor's file.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of index and hash file
(`tests/stable_index_excerpt.html` is a **copy of the real index of 2026-10-02** with one
comment line added; the hash files in the tests are **written by hand in the format the
writer knows, not read on the real server**, and the other pages are made up too), that both files are property lists, that every argument is an
input that the processor declares, that no recipe sets `pcman_version` for an MSI,
that this README says what was not done, has no `make-override` without
`--override-dir` and runs no recipe by its identifier, and that nothing site-specific
and no hash is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
