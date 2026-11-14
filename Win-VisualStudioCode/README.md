# Win-VisualStudioCode

A Windows recipe pair: Microsoft Visual Studio Code, the System Installer for x64 (an `.exe`), stable release, upgraded in place (not the User Installer, not the zip).

**Status. New on 2026-11-13 and NOT rehearsed: nothing of this folder has run under AutoPkg, no installer was downloaded, no template was made and nothing was installed on a PC. Read from Microsoft's site on 2026-11-13 (the answer was saved and the processor's functions were run on the saved copy): (1) `https://code.visualstudio.com/sha?build=stable` answered 200 with a JSON object whose key `products` is a list of 25 elements, one for each download of release `1.146.0` (Windows, macOS, Linux and the command-line tool); each element has `url`, `name` and `productVersion` (`1.146.0`), `version` (the commit of the release, 40 hex digits), `hash`, `sha256hash` (64 hex digits), `timestamp`, `build` (`stable`) and `platform` with `os` and `prettyname`; (2) exactly one element has the os `win32-x64` ("Windows System Installer (x64)"), and its `url` is `https://vscode.download.prss.microsoft.com/dbazure/download/stable/<the commit>/VSCodeSetup-x64-1.146.0.exe`; the os `win32-x64-user` is the User Installer (`VSCodeUserSetup-x64-...`) and `win32-x64-archive` the zip; `win32-arm64` is the System Installer for Arm64 (`VSCodeSetup-arm64-...`); every element of the answer names the same download host. Not read: the other address that is known for this, `https://update.code.visualstudio.com/api/update/win32-x64/stable/latest` (its host could not be resolved from the writer's machine that day); the recipe does not use it. NOT established: that the address of the installer answers without a redirect, and the file's size; that the file is an Inno Setup installer and takes the switches `/VERYSILENT /NORESTART /MERGETASKS=!runcode` (from the writer's knowledge of Microsoft's documentation, not read that day and not tested); the install path; whether the file has a version resource, and that the label `1.146.0` is what the installer itself shows; how the program's own updater behaves for a standard user; the Arm64 installer (never tried); any run with AutoPkg; any install on a PC. The tests read an excerpt of 5 of the 25 elements, cut unchanged from the saved answer, so they prove what the code does with an answer of that form and nothing about Microsoft's site on a later day. The first dry run and the first install on a test PC are the check of what is NOT established. When a run fails, STOP: nothing was written (a run that fails before the import writes nothing). Read the real release file in a browser, correct the processor or the recipe, and only then look at the trust information. Never accept new trust information first to make a failure go away.**


| Recipe | Identifier | What it does |
| --- | --- | --- |
| `VisualStudioCode-Win.download.recipe` | `com.github.serrc-techops.download.VisualStudioCode-Win` | Reads Microsoft's release file, takes the one System Installer of the platform (default `win32-x64`), downloads it, and stops when the file does not match the SHA-256 that the release file gives for it |
| `VisualStudioCode.cimian.recipe` | `com.github.serrc-techops.cimian.VisualStudioCode` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `VisualStudioCode.pcman.recipe` | `com.github.serrc-techops.pcman.VisualStudioCode` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `VisualStudioCode.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `VisualStudioCode.pcman.recipe` is the package tool's way, with `PcmanImporter`. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The processor `VisualStudioCodeInfoProvider.py` is in this folder. It reads one file of
Microsoft's site, the release file (a JSON object), and outputs `url`, `version` and
`expected_sha256`. No shared recipe reads this file. The shared processors are in
`../Win-SharedProcessors/` (see its README). Neither recipe stops on an unchanged
download, so an import that failed is tried again at the next run.

How strict the processor is:

- The one fetch goes to a fixed address over https (`code.visualstudio.com`). A redirect
  is not followed: it is an error. A status other than 200 is an error. The answer may be
  at most 1 MB; the fetch has a time limit of 120 seconds; the answer must be UTF-8 text.
- The platform is `win32-x64` or `win32-arm64`: a System Installer. The User Installer
  (`win32-x64-user`, `win32-arm64-user`), the zip (`-archive`), the command-line tool and
  anything else are an error, and nothing is fetched.
- Every element of `products` must be an object with a platform whose `os` is text. The one
  element whose `os` is the platform is taken; no element, or more than one, stops the run.
- That element's `build` must be `stable`, its `productVersion` two to four numbers with dots,
  its `version` (the commit) 40 hex digits and its `sha256hash` exactly 64 hex digits.
- Its `url` must be exactly
  `https://vscode.download.prss.microsoft.com/dbazure/download/stable/<commit>/VSCodeSetup-<arch>-<productVersion>.exe`,
  with the element's own commit and version and `x64` or `arm64` for the platform. Another
  host, another folder, another name (the User Installer's, say), a query or a fragment
  stops the run. The host and the folder are fixed in the processor, not inputs: an
  override cannot widen them.

Why the System Installer: the Cimian client installs as SYSTEM, and the User Installer
installs into the profile of the account that runs it. The zip is not an installer.

The recipe gives `URLDownloader` the file name `VSCodeSetup-<version>-<platform>.exe`.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What the checks prove

- **The hash.** The hash and the address come from `code.visualstudio.com`, over https, in
  one answer; the file comes from Microsoft's download host. The check shows that the file is
  the file that Microsoft's site names for this release. It does not help if Microsoft's site
  is changed. It does not check a signature.
- **The same product.** For an MSI the package tool refuses a different upgrade code. Whether
  it has an equivalent check for an EXE was NOT established by the writer. For this recipe the
  checks are the hash, the dry run and a person's look at what the dry run plans.
- **The label.** The recipe passes the release file's `productVersion` (`1.146.0`) as the
  label. Whether this label equals the version that a person reads in the installer is NOT
  established: the first dry run shows what the package tool says, and the label must then be
  what the installer itself shows. A label such as `1.146.0` is not read as a build time by the
  Cimian client (its first part is not 20 to 99 and not a year; see `../Win-SharedProcessors/`).

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01 with another recipe of this repository: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `VisualStudioCode.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `StatusService.cs:194-219`) are from `windowsadmins/cimian` at commit `e10498b`, as the other folders of this repository cite them, and not checked against a later version.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **The version label** is the download recipe's `version` (the `productVersion` of Microsoft's release file), and this recipe passes it on as `%version%`. `CimianImporter` takes it as the label and does not check it against the file: the first dry run shows it, and a person compares it with the version that the installer's own properties show.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `vscode`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this README does not establish them (the switches in step a.3 below are only the writer's knowledge), so they are left for a person who has read them in Microsoft's documentation and tried them on a test PC. The run says in a WARNING that the pkginfo has no install check. **An install check by exact version is a decision** (see "Other facts": the program can update itself).

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i VisualStudioCode-Win
    autopkg list-recipes | grep -i VisualStudioCode.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> VisualStudioCode.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `VisualStudioCode.cimian`, not a path. Expected (not run): it writes `<the Windows overrides folder>/VisualStudioCode.cimian.recipe` with the identifier `local.cimian.VisualStudioCode` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.VisualStudioCode`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VisualStudioCode.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.VisualStudioCode`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/VisualStudioCode.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VisualStudioCode.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VisualStudioCode.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VisualStudioCode.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VisualStudioCode.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VisualStudioCode.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `VisualStudioCode.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `VisualStudioCode.pcman`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool.

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
   it replaces. If the package tool's repository has an item `vscode` already, look
   at it first: an item of the kind `choco` is not the template; an item that an earlier
   run of this step made is, and this step is then not needed. The command (NOT run), with a
   real installer of the current release:

       pcman import <path of VSCodeSetup-x64-1.146.0.exe> --name vscode --version 1.146.0 \
           --directory <the folder of the item> \
           --install-arguments '/VERYSILENT /NORESTART /MERGETASKS=!runcode' \
           --install-path 'C:\Program Files\Microsoft VS Code\Code.exe' --architectures x64 \
           --display-name "Visual Studio Code" --category <the category of the item> --developer Microsoft \
           --description "<one sentence about the item>" --icon <the file name of an icon that the repository has> --no-prompt --build

   The label after `--version` is the version of the installer as the installer shows it
   (for an EXE the package tool is given it; here it is the same text that the recipe
   passes). The switches and the install path are the writer's knowledge of the
   Inno Setup installer and of Microsoft's documentation (from the writer's knowledge, not
   read in the installer and not read that day): `/VERYSILENT /NORESTART` install without a
   window and without a restart, and `/MERGETASKS=!runcode` keeps the installer from starting
   the program at the end (it would start as SYSTEM). They are **NOT tested**: check them in
   Microsoft's documentation and on one PC before PCs get the item. A person
   changes the template later; nothing else does. **If the template is made from the
   release that is current on Microsoft's site, the first run says "Nothing new" (see
   step c). To see a dry run that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others (shared AutoPkg recipe repositories
may have recipes for Visual Studio Code):

    autopkg list-recipes | grep -i VisualStudioCode-Win
    autopkg list-recipes | grep -i VisualStudioCode.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> VisualStudioCode.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `VisualStudioCode.pcman`, not a path. Expected (not
run): it writes `<the Windows overrides folder>/VisualStudioCode.pcman.recipe` with the
identifier `local.pcman.VisualStudioCode` and the trust information of the two recipes and
the three processors that are not part of AutoPkg itself (`VisualStudioCodeInfoProvider`,
`ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.VisualStudioCode`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VisualStudioCode.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.VisualStudioCode`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**`-vv` prints `pcman_root` and the repository: keep this log private.** Expected, from
the code and the rehearsals of the other folders, NOT printed by this recipe yet, when
the current version is not yet in the repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name    Version  Catalogs    Result
    vscode  1.146.0  Production  dry run, nothing written

The run also prints `Current Visual Studio Code (win32-x64): ...` and Microsoft's SHA-256,
and then `SHA-256 verified: ...`. Read the version that it names and compare it with
the page of the release notes. If the current version is in the repository already (the
template was made from it), the line is `Nothing new: vscode ... is in the repository
already. Nothing was written.` instead. That is correct.

If Microsoft changes the release file so that the processor cannot read it, the run fails
with a line that begins `Microsoft's release file` and publishes nothing.
If the line says that an address answered with a redirect, or that the url is not the
expected address, stop and tell the owner: the recipe never reads a hash from another host
than `code.visualstudio.com` and never takes a file from another host than the fixed one.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/VisualStudioCode.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VisualStudioCode.pcman.recipe

A change of the `Input` does not break trust (found with 7-Zip). Do not use
`-k pcman_dry_run=false` instead: on the command line it applies to every recipe
of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VisualStudioCode.pcman.recipe

   Expected (not run): `Published vscode 1.146.0.` and the table

       The following versions were published by the package tool:
       Name    Version  Catalogs    Result
       vscode  1.146.0  Production  published

   The repository then has the installer under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions vscode` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VisualStudioCode.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` (A fresh override gets a new cache folder, so its first run downloads the
   file again before it says this.)

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VisualStudioCode.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VisualStudioCode.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again. (Not run with this recipe.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The input of the download recipe is `VSCODE_PLATFORM` (default `win32-x64`;
  `win32-arm64` takes the System Installer for Arm64, never tried). Change it in the
  override's `Input`, not in the recipe. The User Installer and the zip are refused by
  the processor, not only left out by the default.
- **The program updates itself, and that is a decision.** The System Installer's program
  has its own updater: by the writer's knowledge it updates in the background when the
  user can elevate, and otherwise offers the update; what it does for a standard user is
  NOT established. The setting `update.mode` can be set by policy. A person decides whether
  Cimian or the program's own updater keeps it current. An install check by exact version
  (a file version in `installs`, say) would fight an updater that moves ahead: the client
  would see a newer version than the catalog's, or would install the catalog's again.
  Decide this before PCs get the item.
- The recipe's `NAME` is `VisualStudioCode` and `PCMAN_TEMPLATE` is `vscode`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- Only the `stable` build is read: the address of the release file asks for it, and an
  element whose `build` is another word stops the run.
- The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which the
  shared importer compares with the file it imports, so it allows a real run of this
  recipe without `pcman_allow_unverified`.
- `-p` (a local file instead of the download) fails the checksum unless the file is
  Microsoft's file of the current release.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of release file (the excerpt in `tests/`
holds 5 of the 25 elements of the answer read on 2026-11-13, cut unchanged; the other texts
are made up), that the three recipes are property lists, that every argument is an input
that the processor declares, that the recipe for the EXE passes the label, that this README
has no `make-override` without `--override-dir` and runs no recipe by its identifier, that
it says what was NOT done, and that nothing site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
