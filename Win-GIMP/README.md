# Win-GIMP

A Windows recipe pair: GIMP, the `.exe` installer, the newest version of the newest stable series, from the project's download server.

**Status. New, NOT run with AutoPkg: nothing was downloaded, imported or installed. THE HASH CHECK OF THIS DOWNLOAD IS A TRANSFER CHECK, NOT PROOF OF ORIGIN: `download.gimp.org` answers `SHA256SUMS` with a redirect to a mirror, so the hash comes from a mirror as the installer does, and the check proves only that the installer is the file that a mirror's `SHA256SUMS` names, undamaged. The shared importers count the download as verified all the same (`ChecksumVerifier` sets `checksum_verified`), so a real run needs no `cimian_allow_unverified` or `pcman_allow_unverified`. No signature check is built. Facts of the source that the writer read on 2026-11-13: (1) `https://download.gimp.org/gimp/` answered 200 with no redirect and is an HTML directory index whose links include the series folders `v2.10/` ... `v3.0/`, `v3.1/` and `v3.2/` (the highest); (2) `https://download.gimp.org/gimp/v3.2/windows/` answered 200 with no redirect and lists `gimp-3.2.0-RC1-setup.exe` to `RC3`, `gimp-3.2.0-setup.exe`, `gimp-3.2.2-setup.exe`, `gimp-3.2.4-setup.exe`, `gimp-3.2.6-setup.exe` and `gimp-3.2.8-setup.exe` (177M, 03-Nov-2026), a `.torrent` beside each, `SHA256SUMS`, `SHA512SUMS` and a marker file `0.0_LATEST-IS-3.2.8`; (3) `v3.0/windows/` holds `gimp-3.0.8-setup.exe`, `gimp-3.0.8-setup-1.exe` and `gimp-3.0.8-setup-2.exe` (and `v2.10` the same shape): re-issued installers of one GIMP version; `v3.1/windows/` holds `gimp-3.1.2-setup.exe` and `gimp-3.1.4-setup.exe`; (4) `SHA256SUMS` of `v3.2` has one line per installer: 64 hex digits, two spaces, the file name; (5) both `gimp-3.2.8-setup.exe` and `SHA256SUMS` answered `302 Found` with a `Location` on a mirror host whose path ended with `/gimp/v3.2/windows/<file>`. NOT established: that a series with an odd second number is a development series (the writer's knowledge of the project's convention, not read from the project's pages); that the installer is an Inno Setup installer and its silent switches (`/VERYSILENT /NORESTART /ALLUSERS /SUPPRESSMSGBOXES`, the writer's knowledge, not tested); the install path; whether the file has a version resource and what the installed program reports as its version; that the installer carries GIMP's Authenticode signature (stated by the writer, not read from a file here); which mirror a run gets; any install on a PC. The index copies in `tests/` are the real pages of 2026-11-13; the lines of `tests/sha256sums_excerpt.txt` have the real file names and made-up digits. The first dry run (step 3 or step c) is the check of the recipe; an install on a test PC is the check of what is NOT established. When a run fails, STOP: nothing was written. Read the real pages again, correct the processor or the recipe, and only then look at the trust information. Never accept new trust information first. If the run says that an index page answered with a redirect, or that a redirect of `SHA256SUMS` led somewhere the processor refuses, stop and tell the owner. Where a line below says "expected", it is what the code leads to, not something that was printed. Every override command here carries `--override-dir`: see the paragraph "Run every override with `--override-dir`" below.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `GIMP-Win.download.recipe` | `com.github.serrc-techops.download.GIMP-Win` | Reads the server's index of series and the index of the chosen series' `windows` folder, downloads the newest installer, and stops when the file does not match the SHA-256 that the folder's `SHA256SUMS` (served by a mirror) gives for that file |
| `GIMP.cimian.recipe` | `com.github.serrc-techops.cimian.GIMP` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `GIMP.pcman.recipe` | `com.github.serrc-techops.pcman.GIMP` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `GIMP.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `GIMP.pcman.recipe` is the package tool's way, with `PcmanImporter`. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The processor `GimpInfoProvider.py` is in this folder. It reads the index
`https://download.gimp.org/gimp/` and keeps the links that are exactly
`v<number>.<number>/`. By default it takes the highest series whose second number is
even (`3.2`, not `3.1`); the input `gimp_series` pins one (for example `3.0`), which
must be in the index; the input `gimp_allow_development` (default false) allows a
series with an odd second number, also a pinned one. It then reads
`https://download.gimp.org/gimp/v<series>/windows/` and keeps the links that are exactly
`gimp-<version>-setup.exe` or `gimp-<version>-setup-<n>.exe`, with a version of three
numbers (a release candidate such as `gimp-3.2.0-RC1-setup.exe` is not one). It takes the
highest version, compared by its numbers, and for it the highest revision (no suffix is
revision 0). An installer of another series in the folder stops the run. The marker
file `0.0_LATEST-IS-<version>` is not used. Last it reads `SHA256SUMS` of that folder:
every line must be 64 hex digits, two spaces and a file name, and the line of the chosen
installer must be there exactly once. It outputs `url` (the `download.gimp.org` address
of the installer), `version`, `expected_sha256`, `gimp_chosen_series`,
`gimp_installer_name` and `gimp_sha256sums_host`.

The two index pages follow no redirect: a redirect is an error. `SHA256SUMS` follows at
most one redirect, and only to an https address with a plain host name, no user name,
port, query or fragment, whose path ends with `/gimp/v<series>/windows/SHA256SUMS`; the
address it leads to must answer 200 itself. The run prints the host that served the
file. Size limits: 1 MiB for an index page, 64 KiB for `SHA256SUMS`; a time limit of 120
seconds for each request. The processor never guesses: a page or a file that is not
what it expects is an error.

The other processors are in `../Win-SharedProcessors/` (see its README). Neither
recipe stops on an unchanged download, so an import that failed is tried again at
the next run. `URLDownloader` keeps the file under the name of the address
(`gimp-<version>-setup.exe`, no space).

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What the checks prove

- **The hash.** A transfer check, not proof of origin. `download.gimp.org` redirects
  both `SHA256SUMS` and the installer to a mirror (the mirror differs by time and place,
  and the two requests may get different mirrors). The check shows that the installer is
  the file that a mirror's `SHA256SUMS` names, and that it was not damaged on the way. It
  does not show that either file is what the project published: a mirror that changed
  both would pass. It does not check a signature. GIMP's installer is said to be signed
  with Authenticode (not read here); a check of that signature is not built.
- **The same product.** `CimianImporter` compares only the upgrade code of an MSI, and
  whether the package tool has an equivalent check for an EXE was NOT established. For
  this recipe the checks are the hash, the dry run and a person's look at what the dry
  run plans.
- **The label.** An EXE has no version that the importers read for themselves, so the
  recipe passes the GIMP version from the installer's file name (`3.2.8`). The revision
  of a re-issued installer (`-setup-2`) is not part of the label: **a later revision of
  a version that the repository has already is "Nothing new" and is NOT published.** A
  person imports such a revision by hand if it matters. Whether the label equals a
  version resource of the file, or what the installed program reports, is NOT
  established: the first dry run shows what the importer says.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `GIMP.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `StatusService.cs:194`) are from `windowsadmins/cimian` at commit `e10498b`, read on 2026-10-04 and not checked against a later version.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **The version label** is the download recipe's `version` (the GIMP version of the installer's file name), and this recipe passes it on as `%version%`. `CimianImporter` takes it as the label and does not check it against the file: the first dry run shows it, and a person compares it with what the installer's own properties show.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `gimp`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the installer is said to be an Inno Setup installer, whose usual switches are `/VERYSILENT /NORESTART /ALLUSERS /SUPPRESSMSGBOXES`: the writer's knowledge, not tested), so they are left for a person who has read them in the project's documentation and tried them on a test PC. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i GIMP-Win
    autopkg list-recipes | grep -i GIMP.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> GIMP.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `GIMP.cimian`, not a path. It writes `<the Windows overrides folder>/GIMP.cimian.recipe` with the identifier `local.cimian.GIMP` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.GIMP`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GIMP.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.GIMP`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

With `-v` the run also prints the series, the installer and the host that served `SHA256SUMS`. Read that host: it is a mirror.

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/GIMP.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GIMP.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GIMP.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GIMP.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GIMP.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GIMP.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `GIMP.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `GIMP.pcman`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool.

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
   installer are in the repository. If the package tool's repository has an item
   `gimp` already, look at it first: an item of the kind `choco` is not the template;
   an item that an earlier run of this step made is, and this step is then not needed.
   The command, with a real installer of the current version (NOT run):

       pcman import <path of gimp-3.2.8-setup.exe> --name gimp --version 3.2.8 \
           --directory <the folder of the item> \
           --install-arguments '/VERYSILENT /NORESTART /ALLUSERS /SUPPRESSMSGBOXES' \
           --install-path '<the path of the installed program>' --architectures x64 \
           --display-name GIMP --category <the category of the item> --developer 'The GIMP Team' \
           --description <one sentence about the item> --icon <the file name of an icon that the repository has> --no-prompt --build

   The label after `--version` is the GIMP version, the same text that the recipe
   passes. The install arguments are the usual switches of an Inno Setup installer
   (from the writer's knowledge, not read in the installer): that the file is an Inno
   Setup installer, the switches and the install path are **NOT tested**: check them
   in the project's documentation and on one PC before PCs get the item. A person
   changes the template later; nothing else does. **If the template is made from the
   version that is current on the server, the first run says "Nothing new" (see step c).
   To see a dry run that would publish, make the template from an older version.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i GIMP-Win
    autopkg list-recipes | grep -i GIMP.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> GIMP.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `GIMP.pcman`, not a path. Expected (not
run): it writes `<the Windows overrides folder>/GIMP.pcman.recipe` with the
identifier `local.pcman.GIMP` and the trust information of the two recipes and
the three processors that are not part of AutoPkg itself (`GimpInfoProvider`,
`ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.GIMP`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GIMP.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.GIMP`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**`-vv` prints `pcman_root` and the repository: keep this log private.** Expected, from
the code and the rehearsals of the other folders, NOT printed by this recipe yet, when
the current version is not yet in the repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name  Version  Catalogs    Result
    gimp  3.2.8    Production  dry run, nothing written

The run also prints `Series 3.2: GIMP 3.2.8, installer ...`, the SHA-256 and the host that
served `SHA256SUMS`, and then `SHA-256 verified: ...`. If the current version is in the
repository already (the template was made from it), the line is `Nothing new: gimp ...
is in the repository already. Nothing was written.` instead. That is correct.

If the server's layout is not what the processor expects, the run fails with a line that
begins `GIMP index:`, `GIMP index of v<series>/windows/:`, `GIMP SHA256SUMS` or
`SHA256SUMS:` (or with `The server answered ...`) and publishes nothing. If the line says
that an address answered with a redirect, stop and tell the owner: the index pages are
read from `download.gimp.org` only, and `SHA256SUMS` follows one redirect of a fixed shape.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/GIMP.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GIMP.pcman.recipe

A change of the `Input` does not break trust (found with 7-Zip). Do not use
`-k pcman_dry_run=false` instead: on the command line it applies to every recipe
of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GIMP.pcman.recipe

   Expected: `Published gimp 3.2.8.` and a table with the result `published`. The
   repository then has the installer under `pkgs/` and its pkginfo under `pkgsinfo/`.
   The item file of the template is not changed.

2. `pcman versions gimp` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GIMP.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` (A new override gets a new cache folder, so its first run downloads the
   file again before it says so.)

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GIMP.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GIMP.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again. (Not run with this recipe.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The inputs of the download recipe are `gimp_series` (empty by default: the newest
  stable series) and `gimp_allow_development` (default false). Change them in the
  override's `Input`, not in the recipe. A series that was never tried needs a person's
  look first; a pinned older series stays on its last version and gets no newer series.
- When a new stable series appears (`v3.4/`), the default moves to it at the next run.
  A person looks then: the install path or the switches may change.
- A known limit: the label is the GIMP version, so a re-issued installer
  (`gimp-<version>-setup-<n>.exe`) of a version that the repository has is "Nothing new"
  and is not published. Import it by hand if it matters.
- The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which the
  shared importer compares with the file it imports, so it allows a real run of this
  recipe without `pcman_allow_unverified` or `cimian_allow_unverified`, although the hash
  is a mirror's (see "What the checks prove").
- The recipe's `NAME` is `GIMP`, `CIMIAN_NAME` and `PCMAN_TEMPLATE` are `gimp`. Change
  the template name in the override's `Input`, not in the recipe.
- `-p` (a local file instead of the download) fails the checksum unless the file is
  the one that the mirror's `SHA256SUMS` names.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of index page, `SHA256SUMS` and redirect
(the two index copies in `tests/` are the real pages of 2026-11-13, the top one shortened;
`tests/sha256sums_excerpt.txt` has the real file names with made-up digits; the other texts
are made up), that the three recipes are property lists, that every argument is an input
that the processor declares, that the recipe for the EXE passes the label, that this
README has no `make-override` without `--override-dir`, runs no recipe by its
identifier and says what was NOT done, and that nothing site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
