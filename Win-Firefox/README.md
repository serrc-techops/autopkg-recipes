# Win-Firefox

A Windows recipe pair: Mozilla Firefox, the 64-bit `.exe` installer, `en-US`, release channel, upgraded in place (not the MSI).

**Status. Run on 2026-10-04 under AutoPkg 2.9.0, as follows. The first import (the command of step a.3 below, run with `--no-prompt` and `--build`) made the template `firefox` (an EXE item, label `157.0`, `--install-arguments /S`, the install path of that step, architectures `x64`) in the package tool's repository, in the catalog `Production`. The first import went beside the Chocolatey item `firefox` (version 1.0) without any option of the tool; the Chocolatey item file and its `firefox-1.0` pkginfo remain until a person removes them by hand, and `pcman validate` warns that the item has two versions until then. The override of `Firefox.pcman` (`make-override` with `--override-dir`, `ParentRecipe` right, `verify-trust-info` OK, `pcman_dry_run` false) then ran for real: the version file, the download and Mozilla's `SHA256SUMS` check went through and the run ended with `PcmanImporter: Nothing new: firefox 157.0 is in the repository already. Nothing was written.` `pcman catalogs` ran once for all the new items together (2026-10-04): the tool's configured command ran `makecatalogs` on the repository's server, with exit 0, and wrote the catalogs `All` and `Production`, 106 items each. The switch `/S` and the install path are the ones that this README proposed from the writer's knowledge; they were **used on 2026-10-04, not tested on a PC** (the file is a 7-Zip self-extracting stub). Still NOT established after those runs: the switch and the install check on a PC; any install; that an upgrade in place keeps `distribution\policies.json`. Facts of the source that the writer fetched on 2026-10-02, before those runs: Read from Mozilla's servers on that day (the files were saved and the processor's functions were run on them): (1) `https://product-details.mozilla.org/1.0/firefox_versions.json` answered 200 with no redirect, and holds the keys `LATEST_FIREFOX_VERSION` (`157.0`) and `FIREFOX_ESR` (`140.17.0esr`, so the ESR value does end in `esr`); the beta key holds a `b` version, which the processor never reads; (2) `https://download-installer.cdn.mozilla.net/pub/firefox/releases/157.0/SHA256SUMS` answered 200 with no redirect (about 540 KB, far under the limit of 8 MB); every one of its lines is 64 hex digits, two spaces and a path; it holds both `win64/en-US/Firefox Setup 157.0.exe` and `win64/en-US/Firefox Setup 157.0.msi`, and the processor takes the `.exe` line only; (3) a HEAD request for `https://download-installer.cdn.mozilla.net/pub/firefox/releases/157.0/win64/en-US/Firefox%20Setup%20157.0.exe` answered 200 with no redirect (the spaces of the file name are `%20`). NOT established: that the ESR release folder and its file carry the suffix (`140.17.0esr`) as the processor assumes (only the version file was read for ESR); that the version label `157.0` is what the installer itself shows as its version; the silent switch `/S` and the install path on a PC (used on 2026-10-04, not tested); that an upgrade in place keeps `distribution\policies.json` (the owner's decision note, not tried); any install on a PC. The tests use a version file and a SHA256SUMS excerpt that the writer wrote by hand after the real files of 2026-10-02, with made-up digits, so they prove what the code does with answers of that form and nothing about Mozilla today. The first install on a test PC is the check of what is NOT established. When a run fails, STOP: nothing was written (a run that fails before the import writes nothing). Read the real version file, the real release folder and the real SHA256SUMS in a browser, correct the processor or the recipe, and only then look at the trust information. Never accept new trust information first to make a failure go away.**


| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Firefox-Win.download.recipe` | `com.github.serrc-techops.download.Firefox-Win` | Reads Mozilla's version file, takes the current version of the channel (default `release`), downloads its installer, and stops when the file does not match the SHA-256 that Mozilla's `SHA256SUMS` gives for that file |
| `Firefox.cimian.recipe` | `com.github.serrc-techops.cimian.Firefox` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `Firefox.pcman.recipe` | `com.github.serrc-techops.pcman.Firefox` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `Firefox.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `Firefox.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The processor `MozillaFirefoxInfoProvider.py` is in this folder. It reads two files
of Mozilla's servers: the version file (a JSON object) and the `SHA256SUMS` of that
release (a text file). It outputs `url`, `version` and `expected_sha256`. No shared
recipe reads these files. The shared processors are in `../Win-SharedProcessors/`
(see its README). Neither recipe stops on an unchanged download, so an import that
failed is tried again at the next run.

How strict the processor is:

- Both fetches go to a fixed address over https (`product-details.mozilla.org` and
  `download-installer.cdn.mozilla.net`). A redirect is not followed: it is an error.
  A status other than 200 is an error. The version file may be at most 1 MB and
  `SHA256SUMS` at most 8 MB; each fetch has a time limit of 120 seconds; the answer must be
  UTF-8 text.
- The channel is `release` or `esr`. Any other value is an error. The platform and the
  locale are letters, digits, `-` and `_`; a path is an error.
- The version in the version file must have the form of a version (two or three numbers;
  for the ESR channel, an optional `esr` after them). No address is built from another form.
- Every line of `SHA256SUMS` must be 64 hex digits, two spaces and a path. A line of
  another form stops the run. The one line whose path is exactly
  `<platform>/<locale>/Firefox Setup <version>.exe` is taken; no line, or more than one,
  stops the run.
- The address of the file is built from the same parts as the path that was looked up
  in `SHA256SUMS`, so the hash is the hash of that file.

The recipe gives `URLDownloader` the file name
`Firefox-Setup-<version>-<platform>-<locale>.exe`, so that the cached file has no space
and no `%20` in its name.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What the checks prove

- **The hash.** The file and the hash come from one vendor's download server, from the
  same release folder. The check shows that the file is what Mozilla published. It does
  not help if Mozilla's server is changed. It does not check a signature.
- **The same product.** For an MSI the package tool refuses a different upgrade code. Whether
  it has an equivalent check for an EXE was NOT established by the writer. For this recipe the
  checks are the hash, the dry run and a person's look at what the dry run plans.
- **The label.** An EXE has no version that the package tool can read for itself, so the
  recipe passes the version of Mozilla's version file as numbers (`141.0`, `141.0.1`). On the
  ESR channel the suffix `esr` is left out. Whether this label equals the version that a
  person reads in the installer is NOT established: the first dry run shows what the
  package tool says, and the label must then be what the installer itself shows.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `Firefox.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

3. **The version label** is the download recipe's `version` (the version in Mozilla's version file), and this recipe passes it on as `%version%`. `CimianImporter` takes it as the label and does not check it against the file: the first dry run shows it, and a person compares it with the version that the installer's own properties show.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `firefox`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the first step of the package tool's way below marks what is only the writer's knowledge or was not read), so they are left for a person who has read them in the vendor's documentation and tried them on a test PC. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i Firefox-Win
    autopkg list-recipes | grep -i Firefox.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Firefox.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `Firefox.cimian`, not a path. It writes `<the Windows overrides folder>/Firefox.cimian.recipe` with the identifier `local.cimian.Firefox` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.Firefox`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.Firefox`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/Firefox.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `Firefox.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `Firefox.pcman` where this README used to say `Firefox.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `Firefox.cimian.recipe` (when that recipe ran the package tool) must be made again from `Firefox.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `Firefox.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   it replaces. If the package tool's repository has an item `firefox` already, look
   at it first: an item of the kind `choco` is not the template (see the status line: the first
   import of 2026-10-04 went beside it without any option, and a person removes the Chocolatey item
   by hand); an item that an earlier run of this step made is, and this step is then not needed. The command,
   in the form that ran on 2026-10-04 (with `--icon <the file name of an icon that the repository has>` added), with a real installer of the current release:

       pcman import <path of "Firefox Setup 141.0.exe"> --name firefox --version 141.0 \
           --directory <the folder of the item> --install-arguments /S \
           --install-path 'C:\Program Files\Mozilla Firefox\firefox.exe' --architectures x64 \
           --display-name Firefox --category <the category of the item> --developer Mozilla \
           --description <one sentence about the item> --icon <the file name of an icon that the repository has> --no-prompt --build

   The label after `--version` is the version of the installer as the installer shows it
   (for an EXE the package tool is given it; here it is the same text that the recipe
   passes). `--install-arguments /S` and the install path are the writer's knowledge of
   the Firefox installer (from the writer's knowledge, not read in the installer); they were
   **used on 2026-10-04 as written, not tested on a PC**: check both in Mozilla's documentation and
   on one PC before PCs get the item. A person
   changes the template later; nothing else does. **If the template is made from the
   release that is current on Mozilla's server, the first run says "Nothing new" (see
   step c). To see a dry run that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others (several shared AutoPkg recipe repositories
have recipes for Firefox):

    autopkg list-recipes | grep -i Firefox-Win
    autopkg list-recipes | grep -i Firefox.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Firefox.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Firefox.pcman`, not a path. Expected (not
run): it writes `<the Windows overrides folder>/Firefox.pcman.recipe` with the
identifier `local.pcman.Firefox` and the trust information of the two recipes and
the three processors that are not part of AutoPkg itself (`MozillaFirefoxInfoProvider`,
`ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Firefox`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.Firefox`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**`-vv` prints `pcman_root` and the repository: keep this log private.** Expected, from
the code and the rehearsals of the other folders, NOT printed by this recipe yet, when
the current version is not yet in the repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name     Version  Catalogs    Result
    firefox  141.0    Production  dry run, nothing written

The run also prints `Current Firefox of channel release: ...` and Mozilla's SHA-256,
and then `SHA-256 verified: ...`. Read the version that it names and compare it with
the page of the release notes. If the current version is in the repository already (the
template was made from it), the line is `Nothing new: firefox ... is in the repository
already. Nothing was written.` instead. That is correct.

If Mozilla changes a file so that the processor cannot read it, the run fails with a line
that begins `Mozilla's version file:` or `Mozilla's SHA256SUMS` and publishes nothing.
If the line says that an address answered with a redirect, stop and tell the owner:
the recipe never reads a hash from another host than Mozilla's two fixed ones.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Firefox.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.pcman.recipe

A change of the `Input` does not break trust (found with 7-Zip). Do not use
`-k pcman_dry_run=false` instead: on the command line it applies to every recipe
of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.pcman.recipe

   Expected: `Published firefox 141.0.` and the table

       The following versions were published by the package tool:
       Name     Version  Catalogs    Result
       firefox  141.0    Production  published

   The repository then has the installer under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions firefox` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.` (On 2026-10-04 the first run of a fresh override printed the line `Nothing new: ...` after it had downloaded the file again, because a new override gets a new cache folder; `Nothing downloaded, packaged or imported.` was not seen in that run, and is the line of a later run of the same override.)

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again. (Not run with this recipe.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The inputs of the download recipe are `FIREFOX_CHANNEL` (default `release`; `esr`
  takes the ESR key), `FIREFOX_PLATFORM` (default `win64`) and `FIREFOX_LOCALE`
  (default `en-US`). Change them in the override's `Input`, not in the recipe. A
  channel, platform or locale that was never tried needs a person's look first. The
  cached file name has no channel in it: use one channel for one override.
- The ESR version in the version file carries the suffix `esr` (read on 2026-10-02:
  `140.17.0esr`). The processor builds the release folder from the text as Mozilla
  writes it, and passes the numbers only as the label. That the suffix is also in the
  folder and the file name is from the writer's knowledge and NOT read from the server:
  the ESR release folder was not read.
- The installer is upgraded in place. That it keeps `distribution\policies.json` is the
  owner's note, NOT tried here: test it on one PC before the PCs get the version.
- The recipe's `NAME` is `Firefox` and `PCMAN_TEMPLATE` is `firefox`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- A version that is not numbers (a beta, with `b`, or a nightly) is never taken: the
  version file keys of the beta and the nightly are not read at all.
- The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which the
  shared importer compares with the file it imports, so it allows a real run of this
  recipe without `pcman_allow_unverified`.
- `-p` (a local file instead of the download) fails the checksum unless the file is
  Mozilla's file.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of version file and `SHA256SUMS`
(the two excerpts in `tests/` are written by hand after the real files of 2026-10-02,
with made-up digits, not saved from the real servers; the other texts are made up), that both recipes are
property lists, that every argument is an input that the processor declares, that the
recipe for the EXE passes the label and the file name has no space, that this README
has no `make-override` without `--override-dir` and runs no recipe by its identifier,
that it says what was NOT done, and that nothing site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
