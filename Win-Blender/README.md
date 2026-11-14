# Win-Blender

A Windows recipe pair: Blender, the x64 `.msi` of the newest series (or of one series that the override pins).

**Status. NOT run under AutoPkg: this pair is new, and nothing of it has run with AutoPkg, the package tool, a share or a PC. Nothing was downloaded or installed when it was written. The facts below were read by the writer on 2026-11-13. VERIFIED: (1) `https://download.blender.org/release/` answered 200 with no redirect; it is an nginx-style HTML index with 92 links that begin with `Blender`, 75 of them `Blender<major>.<minor>/` (one, `Blender2.04/`, with a leading zero that the processor does not accept), the newest `Blender5.3/`, beside older folders of other shapes (`Blender2.28a/`, `Blender2.50alpha/`, `Blender2.27-newpy/`, `BlenderBenchmark2.0/`) and some files; the processor read a saved copy of it as the series 5.3; (2) the folder `Blender5.3/` lists `blender-5.3.0-windows-x64.msi` (383557632 bytes, about 366 MiB, dated 10-Nov-2026), the arm64 MSI, `.msix` and `.zip` builds, Linux and macOS files, and `blender-5.3.0.sha256` and `blender-5.3.0.md5`; the processor read a saved copy of it as the one version 5.3.0; (3) the folder `Blender5.2/` holds 5.2.0 to 5.2.4, each with its own `blender-<version>.sha256`; (4) `blender-5.3.0.sha256` has one line per file of that version, 64 hex digits, two spaces and the file name (eight lines, one of them for the x64 MSI); (5) a HEAD of the MSI answered 200 with its size, directly from `download.blender.org`, with no redirect. NOT VERIFIED: whether a series folder ever holds release candidates, or appears before its first stable file (the processor is written for both, see below); which series are long-term lines; the MSI's ProductVersion and UpgradeCode, and whether the ProductVersion equals the three numbers of the file name; whether the UpgradeCode stays the same from one series to the next; what `msiexec /qn` does with this MSI; where it installs (each series may install into its own folder, so a new series may leave the old one installed); the template, `pcman catalogs`, and any run with AutoPkg. The first run on the build Mac is the check of each fact it relies on. When a run fails, stop: nothing was written. Read the real page, and correct the recipe or `BlenderInfoProvider.py` to what it shows; never accept the trust information first, and never write a hash into a recipe. Where a line below says "expected", it is what the code is written to print, not something that was printed. Every override command here carries `--override-dir`: see the next paragraph.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Blender-Win.download.recipe` | `com.github.serrc-techops.download.Blender-Win` | Reads the vendor's index of releases, takes the newest series that has an x64 MSI (or the series in `BLENDER_SERIES`), downloads the newest MSI of that series, and stops when the file does not match the SHA-256 in the vendor's hash file |
| `Blender.cimian.recipe` | `com.github.serrc-techops.cimian.Blender` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `Blender.pcman.recipe` | `com.github.serrc-techops.pcman.Blender` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `Blender.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `Blender.pcman.recipe` is the package tool's way, with `PcmanImporter`. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The processor `BlenderInfoProvider.py` is in this folder. It reads the index
`https://download.blender.org/release/` and keeps the links that are exactly
`Blender<two numbers>/` (a series, such as `5.3`). Series are compared **by their
numbers** (`5.10` is newer than `5.9`), never by their text or by the order of the
links. It reads the folder of the highest series and keeps the links that are
exactly `blender-<three numbers>-windows-x64.msi`; a name with anything else in
place of the three numbers is ignored, not an error. It takes the highest of those
versions. **A newest folder without such an MSI is not an error by itself**: the
processor reads the next lower series, at most three folders in all, and says in its
output which folder it used (`Folder used: Blender5.3/ (newest)`). It then reads
`blender-<version>.sha256` in the same folder and takes the one line whose file name
is exactly the MSI's name. It outputs `url`, `version` and `expected_sha256`. In the
normal case it sends three requests: the index, the series folder, the hash file.

**To stay on a long-term line**, set `BLENDER_SERIES` in the override's `Input` to
that series, such as `4.5`. Then only the folder of that series is read, and a folder
without an x64 MSI stops the run: there is no fall back to another series. Which
series are long-term lines was not read here: read Blender's own pages first. Empty
(the default) means the newest series.

Every fetch of the processor goes to `https://download.blender.org/release/`, follows
**no redirect**, has a size limit and a time limit. A redirect, a status other than
200, a page that is not UTF-8 text or is larger than the limit, a version in a series
folder that belongs to another series, any line of the hash file that is not 64 hex
digits, two spaces and a file name, or no line (or more than one) for the MSI stops
the run with a line that begins `Blender download index:`, `Blender folder` or
`Blender hash file of` (or says what could not be fetched) and publishes nothing.

The other processors are in `../Win-SharedProcessors/` (see its README). Neither
recipe stops on an unchanged download, so an import that failed is tried again at
the next run.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What the checks prove

- **The hash.** The MSI and its hash file come from the same server. The check shows
  that the downloaded file is the file that the server's hash file names; it does not
  help if the vendor's own server is changed. The MSI itself is downloaded by
  AutoPkg's `URLDownloader`, which follows a redirect (the MSI answered without one on
  2026-11-13); the hash check after it is what protects the run.
- **The same product.** The importers refuse an MSI whose upgrade code differs from
  the template's. Whether Blender's MSIs keep one upgrade code across series is not
  established: if they do not, the first run after a new series stops there, and a
  person decides.
- **The label.** The recipe gives no version label. For an MSI the importers take
  the MSI's own ProductVersion. Whether it equals the release's three numbers is not
  established. A label of three numbers could be refused.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01 with another recipe of this repository: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg, `msiinfo` (msitools: `brew install msitools`) for the MSI, and nothing of the owner's: no package tool. It uses `Blender.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `InstallerService.cs:936`) are from `windowsadmins/cimian` at commit `e10498b`, read on 2026-10-04 and not checked against a later version.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **`msiinfo` on the PATH of the run** (`brew install msitools`): `CimianImporter` reads the MSI's ProductVersion and its two codes with it, and does not parse an MSI itself. A job that `launchd` starts may have no Homebrew on its `PATH`, so the importer looks in `/opt/homebrew/bin` and `/usr/local/bin` too; the input `cimian_path` changes that list. This recipe cannot run without it: its step passes an empty `version` (so that the release's three numbers are not taken for the MSI's own version), and an argument of a step wins over an override's `Input`, so the label can only come from the MSI. The run stops and names the facts that are missing.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `blender`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **For an `.msi` nothing needs completing for a silent install:** the client runs `msiexec /i <file> /qn /norestart` itself and then the arguments of the item (`InstallerService.cs:936-948`), so the recipe gives no silent arguments, and `CimianImporter` writes the install check of an MSI (an `installs` entry of type `msi` with the MSI's codes and version). Whether Blender's MSI installs cleanly that way was not tested: try it on a test PC first. What the MSI's own properties allow (features, the install folder) is the template's business: give them as `installer: {args: [...]}` in the override's `pkginfo`. An MSI whose upgrade code is not the template's, or that has none where the template's item had one, is refused (Windows Installer does not upgrade across upgrade codes): `cimian_allow_product_change` set to true in the override allows it, with a WARNING.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i Blender-Win
    autopkg list-recipes | grep -i Blender.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Blender.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `Blender.cimian`, not a path. It writes `<the Windows overrides folder>/Blender.cimian.recipe` with the identifier `local.cimian.Blender` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.Blender`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`). To pin a series, add `BLENDER_SERIES` to the `Input`.

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Blender.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.Blender`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.msi (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/Blender.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Blender.cimian.recipe

The trust check is expected to still report OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Blender.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Blender.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Blender.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Blender.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `Blender.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `Blender.pcman`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool.

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
   installer are in the repository. The command, with a real MSI of the series that
   the override will follow:

       pcman import <path of blender-<version>-windows-x64.msi> --name blender \
           --directory <the folder of the item> --display-name Blender \
           --category <the category> --developer "Blender Foundation" \
           --description "<the description>" --architectures x64 --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. The icon is
   added as the package tool's README describes. The install arguments are not given
   here: for an MSI the package tool uses the MSI's own installer arguments. Whether
   Blender's MSI takes properties of its own (an install folder, file associations) was
   not read: read the vendor's documentation first, and give them to this first import,
   if the owner wants any. A person changes the template later; nothing else does.
   **If the template is made from the release that is current on the vendor's
   server, the first run says "Nothing new" (see step c). To see a dry run that would
   publish, make the template from an older release.**

4. **A long-term line needs its own template.** A pinned series is another product
   line. Do not point it at `blender` while another override follows the newest
   series. Make a template of its own (for example `blender-<series>`, from a release
   of that series), and an override of its own whose `Input` has `BLENDER_SERIES` set
   to the series and `PCMAN_TEMPLATE` set to that template.

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Blender-Win
    autopkg list-recipes | grep -i Blender.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Blender.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Blender.pcman`, not a path. Expected:
it writes `<the Windows overrides folder>/Blender.pcman.recipe` with the
identifier `local.pcman.Blender` and the trust information of the two
recipes and the three processors that are not part of AutoPkg itself
(`BlenderInfoProvider`, `ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Blender`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Blender.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.Blender`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current release is not yet in the
repository (the lines of another program's rehearsal, with this program's name;
this program was NOT run, and the version is the MSI's own):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name     Version                Catalogs    Result
    blender  <the MSI's version>    Production  dry run, nothing written

With `-v` the run also prints `Folder used: Blender<series>/ (newest)`, the release and
the vendor's SHA-256, and then `SHA-256 verified: ...`. If the current release is in
the repository already (the template was made from it), the line is `Nothing new:
blender ... is in the repository already. Nothing was written.` instead. That is
correct.

If the first run fails here, stop. It is the check of the facts in the status paragraph
at the top: a line that begins `Blender download index:`, `Blender folder` or
`Blender hash file of` means the page is not what the code expects, and
`The server answered 30x` means a redirect. Nothing was written. Do not accept trust
information to get past it.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Blender.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Blender.pcman.recipe

A change of the `Input` does not break trust (rehearsed with another program, not with
this one). Do not use `-k pcman_dry_run=false` instead: on the command line it applies
to every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Blender.pcman.recipe

   Expected: `Published blender <the MSI's version>.` and the table

       The following versions were published by the package tool:
       Name     Version              Catalogs    Result
       blender  <the MSI's version>  Production  published

   The repository then has the MSI under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions blender` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Blender.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Blender.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Blender.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository another program's recipe failed (exit code 70)
with the tool's line (not seen for this program, which has not run):

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The MSI is about 366 MiB (383557632 bytes for 5.3.0). Each run that finds a new
  release downloads it once into AutoPkg's cache.
- A new release has a new ProductCode. Whether the UpgradeCode is the same across
  releases and across series, and what happens on a PC that has Blender from another
  source, is not established: test it on one PC before the PCs get the version.
- **A new series may install beside the old one.** Blender may install each series
  into its own folder (`Blender Foundation\Blender <series>`), so an upgrade to a new
  series may leave the old series installed. This was not read in the installer: a
  person checks it on a test PC and decides whether the template needs an uninstall
  of the old series.
- The inputs of the download recipe are `NAME` and `BLENDER_SERIES` (default empty:
  the newest series). Change the series in the override's `Input`, not in the recipe.
  A value that is not empty and not two numbers (`4.5`) stops the run before any
  request.
- A series folder that is not exactly `Blender<two numbers>/` is ignored, and so is
  an MSI name that is not exactly `blender-<three numbers>-windows-x64.msi` (a
  release candidate, if one ever appears there, among them).
- The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which the
  shared importers compare with the file they import, so it allows a real run of this
  recipe without `pcman_allow_unverified` or `cimian_allow_unverified`.
- The recipe's `NAME` is `Blender` and `PCMAN_TEMPLATE` and `CIMIAN_NAME` are
  `blender`. Change the name in the override's `Input`, not in the recipe.
- `-p` (a local file instead of the download) fails the checksum unless the file is
  the vendor's file.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of index, series folder and hash file
(`tests/release_index.html` and `tests/series_5.3_listing.html` are **copies of the real
pages of 2026-11-13** with one comment line added; the hash files in the tests have the
file names of the real `blender-5.3.0.sha256` of that day in its order, but **made-up
hashes**, and the other pages are written by hand), that the three files are property
lists, that every argument is an input that the processor declares, that no recipe sets
`pcman_version` for an MSI, that this README says what was not done, has no
`make-override` without `--override-dir` and runs no recipe by its identifier, and that
nothing site-specific and no hash is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it) and the `.pcman.recipe` (the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
