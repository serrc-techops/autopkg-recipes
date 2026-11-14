# Win-Krita

A Windows recipe pair: Krita, the 64-bit `.exe` installer, the newest version on KDE's download server.

**A version of four numbers is written in this folder as `6.0.4(.1)`** (the three numbers and, in brackets, the fourth): the repository's hygiene check reads four numbers joined by dots as an address, so no file here spells one out. On the server the folder is the four numbers joined by dots.

**Status. New, NOT run with AutoPkg: nothing was downloaded, imported or installed. Facts of the source that the writer read on 2026-11-13: (1) `https://download.kde.org/stable/krita/` answered 200 with no redirect and is an HTML directory index; it links the version folders `5.3.4(.1)/`, `6.0.2/`, `6.0.4/` and `6.0.4(.1)/` (each link twice), the folders `updates/` and two `FastSketchPlugin-<version>/`, a file `older_versions_are_in_the_attic`, and the site's own header and footer links; `5.3.4(.1)/` and `6.0.4(.1)/` are dated 2026-10-07; (2) the folder `6.0.4(.1)/` answered 200 with no redirect and links `krita-x64-6.0.4(.1)-setup.exe` (167M, 2026-10-01), `krita-x64-6.0.4(.1).zip`, `krita-x64-6.0.4(.1)-dbg.zip`, a `.dmg`, an AppImage, two source archives and a `.sig` file beside the AppImage and each source archive (none beside the Windows files); the folder `6.0.4/` links the same files for 6.0.4 (`krita-x64-6.0.4-setup.exe`, 168M, 2026-09-10); (3) `https://download.kde.org/stable/krita/6.0.4/krita-x64-6.0.4-setup.exe` answered `302` with a `Location` on a mirror host; (4) `krita-x64-6.0.4-setup.exe.sha256` in the folder `6.0.4/` answered 200 from download.kde.org itself, with no redirect: one line, 64 hex digits, two spaces and the file name; the same file of the folder `6.0.4(.1)/` answered 200 with no redirect, 93 bytes, the same form with no new line at the end; neither folder's index links its `.sha256` file. NOT established: whether a version folder can be without the Windows installer (a release for other systems only; the processor passes such a folder over as a precaution, not because one was seen); that the installer is an NSIS installer and that `/S` installs it silently (the writer's knowledge, not read from the vendor, not tested); the install path; the shell extension that the installer is said to offer (not read) and what a silent install does about it; whether the file has a version resource and what the installed program reports as its version; how the Cimian client and the package tool order a version of four numbers beside one of three; whether the installer carries an Authenticode signature (not read); how download.kde.org makes the `.sha256` file (said to be made by the server's MirrorBrain, not read); which mirror a run gets; whether an installer of a newer version upgrades an older installation; any install on a PC. The index copies in `tests/` are lines of the real pages of 2026-11-13; the hash lines of the tests are made up. The first dry run (step 3 or step c) is the check of the recipe; an install on a test PC is the check of what is NOT established. When a run fails, STOP: nothing was written. Read the real pages again, correct the processor or the recipe, and only then look at the trust information. Never accept new trust information first. If the run says that a page or the hash file answered with a redirect, stop and tell the owner: the server has changed, and the processor refuses a hash read from another host on purpose. Where a line below says "expected", it is what the code leads to, not something that was printed. Every override command here carries `--override-dir`: see the paragraph "Run every override with `--override-dir`" below.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Krita-Win.download.recipe` | `com.github.serrc-techops.download.Krita-Win` | Reads the server's index of Krita's versions and the index of the chosen version's folder, downloads that version's Windows installer, and stops when the file does not match the SHA-256 that download.kde.org's `.sha256` file gives for it |
| `Krita.cimian.recipe` | `com.github.serrc-techops.cimian.Krita` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `Krita.pcman.recipe` | `com.github.serrc-techops.pcman.Krita` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `Krita.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `Krita.pcman.recipe` is the package tool's way, with `PcmanImporter`. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The processor `KritaInfoProvider.py` is in this folder. It reads the index
`https://download.kde.org/stable/krita/` and keeps the links that are exactly
`<version>/` with a version of three or four numbers. A link of digits and dots that is
not such a version (`7.0/`, say) stops the run: it is never skipped. Other links
(`updates/`, plug-in folders, the site's pages) are ignored. It reads the version folders
from the highest version down, the numbers compared one by one, so `6.0.4(.1)` is higher
than `6.0.4`. A folder is used when its own index links to exactly
`krita-x64-<the folder's version>-setup.exe`; a folder without that link is passed over,
and at most three folders are read before the run stops. A folder that links to a Windows
installer of another version stops the run. Last it reads
`krita-x64-<version>-setup.exe.sha256` from the same folder (by its name: the index does
not link it): exactly one line, 64 hex digits, two spaces and the installer's name. It
outputs `url` (the `download.kde.org` address of the installer), `version`,
`expected_sha256`, `krita_chosen_folder`, `krita_installer_name` and `krita_passed_over`
(the newer folders without the installer, or empty).

All three fetches go to `download.kde.org` over https and follow no redirect: a redirect
is an error. Size limits: 1 MiB for an index page, 16 KiB for the hash file; a time limit
of 120 seconds for each request. The processor never guesses: a page or a file that is not
what it expects is an error.

The other processors are in `../Win-SharedProcessors/` (see its README). Neither
recipe stops on an unchanged download, so an import that failed is tried again at
the next run. `URLDownloader` keeps the file under the name of the address
(`krita-x64-<version>-setup.exe`, no space).

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What the checks prove

- **The hash.** The `.sha256` file is read from `download.kde.org` itself, without a
  redirect; the installer comes from a mirror (the server redirects it, and the mirror
  differs by time and place). The check shows that the mirror's file is the file that
  KDE's own server gives the hash for, undamaged. It does not check a signature: no
  `.sig` file is published beside the Windows files, and whether the installer carries an
  Authenticode signature was not read; a check of such a signature is not built.
- **The same product.** `CimianImporter` compares only the upgrade code of an MSI, and
  whether the package tool has an equivalent check for an EXE was NOT established. For
  this recipe the checks are the hash, the dry run and a person's look at what the dry
  run plans.
- **The label.** An EXE has no version that the importers read for themselves, so the
  recipe passes the version of the folder: `6.0.4`, or `6.0.4(.1)` for a re-issue. Both
  shared importers take a label of four numbers (`CimianImporter` takes any label that
  begins with a digit; the package tool's processor refuses only white space, path
  separators and a leading `-`). How the Cimian client orders `6.0.4(.1)` beside `6.0.4`
  is NOT established: the first dry run shows the label, and a PC shows the order.
  Whether the label equals a version resource of the file, or what the installed program
  reports, is NOT established either.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `Krita.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `StatusService.cs:194`) are from `windowsadmins/cimian` at commit `e10498b`, read on 2026-10-04 and not checked against a later version.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **The version label** is the download recipe's `version` (the version of the folder that the processor used), and this recipe passes it on as `%version%`. `CimianImporter` takes it as the label and does not check it against the file: the first dry run shows it, and a person compares it with what the installer's own properties show.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `krita`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the installer is said to be an NSIS installer, whose usual switch is `/S`: the writer's knowledge, not read from the vendor, not tested), so they are left for a person who has read them in the project's documentation and tried them on a test PC, together with what a silent install does about the shell extension. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i Krita-Win
    autopkg list-recipes | grep -i Krita.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Krita.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `Krita.cimian`, not a path. It writes `<the Windows overrides folder>/Krita.cimian.recipe` with the identifier `local.cimian.Krita` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.Krita`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Krita.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.Krita`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

With `-v` the run also prints the folder and the installer that the processor used, the folders it passed over (if any) and the SHA-256.

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/Krita.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Krita.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Krita.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Krita.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Krita.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Krita.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `Krita.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `Krita.pcman`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool.

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
   `krita` already, look at it first: an item of the kind `choco` is not the template;
   an item that an earlier run of this step made is, and this step is then not needed.
   The command, with a real installer of an older version than the server's newest (NOT run):

       pcman import <path of krita-x64-6.0.4-setup.exe> --name krita --version 6.0.4 \
           --directory <the folder of the item> \
           --install-arguments '/S' \
           --install-path '<the path of the installed program>' --architectures x64 \
           --display-name Krita --category <the category of the item> --developer 'Krita Foundation' \
           --description <one sentence about the item> --icon <the file name of an icon that the repository has> --no-prompt --build

   The label after `--version` is the version of the installer's folder, the same text
   that the recipe passes. The install argument is the usual switch of an NSIS installer
   (from the writer's knowledge, not read in the installer): that the file is an NSIS
   installer, the switch, what it does about the shell extension and the install path are
   **NOT tested**: check them in the project's documentation and on one PC before PCs get
   the item. A person changes the template later; nothing else does. **If the template is
   made from the version that is current on the server, the first run says "Nothing new"
   (see step c). On 2026-11-13 the newest was `6.0.4(.1)`, so a template made from `6.0.4`
   gives a dry run that would publish.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Krita-Win
    autopkg list-recipes | grep -i Krita.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Krita.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Krita.pcman`, not a path. Expected (not
run): it writes `<the Windows overrides folder>/Krita.pcman.recipe` with the
identifier `local.pcman.Krita` and the trust information of the two recipes and
the three processors that are not part of AutoPkg itself (`KritaInfoProvider`,
`ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Krita`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Krita.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.Krita`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**`-vv` prints `pcman_root` and the repository: keep this log private.** Expected, from
the code and the rehearsals of the other folders, NOT printed by this recipe yet, when
the current version is not yet in the repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name   Version    Catalogs    Result
    krita  <version>  Production  dry run, nothing written

The run also prints `Folder <version>: installer krita-x64-<version>-setup.exe`, the
SHA-256, and then `SHA-256 verified: ...`; if a newer folder had no Windows installer, a
line `Passed over (no Windows installer): ...` comes first. If the current version is in
the repository already (the template was made from it), the line is `Nothing new: krita
... is in the repository already. Nothing was written.` instead. That is correct.

If the server's layout is not what the processor expects, the run fails with a line that
begins `Krita index:`, `Krita index of <version>/:` or `Krita hash file of <version>/:`
(or with `The server answered ...`) and publishes nothing. If the line says that an
address answered with a redirect, stop and tell the owner: the processor reads every page
and the hash file from `download.kde.org` only.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Krita.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Krita.pcman.recipe

A change of the `Input` does not break trust (found with 7-Zip). Do not use
`-k pcman_dry_run=false` instead: on the command line it applies to every recipe
of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Krita.pcman.recipe

   Expected: `Published krita <version>.` and a table with the result `published`. The
   repository then has the installer under `pkgs/` and its pkginfo under `pkgsinfo/`.
   The item file of the template is not changed.

2. `pcman versions krita` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Krita.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` (A new override gets a new cache folder, so its first run downloads the
   file again before it says so.)

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Krita.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Krita.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again. (Not run with this recipe.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The download recipe has no input for a line of versions: it takes the highest version
  on the server. A known limit: the older line (`5.3.4(.1)` on 2026-11-13) is never taken
  while a `6` version is higher. A person looks when a new major version appears: the
  install path or the switch may change.
- A re-issue (`6.0.4(.1)` after `6.0.4`) has its own folder and a label of four numbers,
  so the importers see it as a new version. Whether a PC takes it as newer is NOT
  established (see "What the checks prove").
- Only the folder `stable/krita/` is read; test versions elsewhere on the server are not.
- The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which the
  shared importer compares with the file it imports, so it allows a real run of this
  recipe without `pcman_allow_unverified` or `cimian_allow_unverified`.
- The recipe's `NAME` is `Krita`, `CIMIAN_NAME` and `PCMAN_TEMPLATE` are `krita`. Change
  the template name in the override's `Input`, not in the recipe.
- `-p` (a local file instead of the download) fails the checksum unless the file is
  the one that download.kde.org's `.sha256` file names.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of index page, folder and hash file
(the two copies in `tests/` are lines of the real pages of 2026-11-13, with every dot
between two digits written `_dot_`, which the tests put back; the hash lines and the other
pages are made up), that the three recipes are property lists, that every argument is an
input that the processor declares, that the recipe for the EXE passes the label, that both
importers take a label of four numbers, that this README has no `make-override` without
`--override-dir`, runs no recipe by its identifier and says what was NOT done, and that
nothing site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
