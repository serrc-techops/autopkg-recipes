# Win-Scratch

A Windows recipe pair: Scratch 3, the desktop app of the Scratch Foundation, the `.exe` installer, with the version label taken from the file name that the download address redirects to.

**Status. First thing to prove on a test PC: whether this installer installs for the whole machine when the Cimian client runs it as SYSTEM. By the writer's knowledge (NOT read from the vendor, NOT tested) the file is an installer made with electron-builder's NSIS target, `/S` makes it silent, and `/allusers` (with `/S`: `/S /allusers`) asks for a per-machine install where the build allows it; without it such an installer often installs PER USER, into the profile of the account that runs it. Run by SYSTEM, a per-user install would put Scratch into SYSTEM's profile and no person would get it, and an install check on a per-user path would never be true for anyone else. So the item must NOT go into a manifest until a person has proven on a test PC that a signed-in standard user gets Scratch after an install by SYSTEM, and where it was installed. This recipe set is new and NOT rehearsed: nothing was run under AutoPkg, nothing was downloaded, nothing was imported into any repository and nothing was installed on a PC. Read on 2026-11-13, with header requests and one GET that followed no redirect (no file was downloaded): `https://downloads.scratch.mit.edu/desktop/Scratch%20Setup.exe` answered `301` with `location: https://downloads.scratch.mit.edu/desktop/Scratch%203.32.1%20Setup.exe` and `Content-Length` 0 (the server names itself `AmazonS3`); a GET of the same address with the processor's user agent answered the same `301` with no body; `https://downloads.scratch.mit.edu/desktop/Scratch%203.32.1%20Setup.exe` answered a header request with 200, `Content-Type` `application/x-msdownload`, `Content-Length` 204843840 and `Last-Modified` 2026-08-12. The Scratch download page (`https://scratch.mit.edu/download`) is built by scripts; its script `download.bundle.js` names `https://downloads.scratch.mit.edu/desktop/Scratch%20Setup.exe` as the direct Windows download (beside a Microsoft Store link). No hash for the file was found. So the version is in the redirect's file name, `Scratch <version> Setup.exe`, and the recipe takes the label from there. NOT established: that the file has a version resource, and whether its `ProductVersion` equals the version in the name (the file was not downloaded); the version that the installed program reports; the architecture of the EXE; the publisher named in its signature (the developer in the recipe is the vendor's name, not read from the file); that `/S` and `/allusers` work as described above, where the program is installed, and any install check; that the server answers the questions that AutoPkg asks about a changed file (a last-modified date was seen, nothing else was looked at); any install on a PC. The download is NOT verified: no hash was found, and a check of the signature is not built. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true. Do not set it before the signature check exists. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template scratch --version <the label>` (an EXE needs `--version`). The tests use answers that the writer wrote by hand after the real answer of 2026-11-13, so they prove what the code does with answers of that form and nothing about the server today. The first install on a test PC is the check of what is NOT established. When a run fails, STOP: nothing was written (a run that fails before the import writes nothing). Read the real address with a header request or in a browser, correct the processor or the recipe, and only then look at the trust information. Never accept new trust information first to make a failure go away.**


| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Scratch-Win.download.recipe` | `com.github.serrc-techops.download.Scratch-Win` | Finds the address of the current installer and its version with `ScratchInfoProvider`, and downloads it under a name without spaces. It has no hard check |
| `Scratch.cimian.recipe` | `com.github.serrc-techops.cimian.Scratch` | Parent: the download recipe. Hands the file to `CimianImporter` with the version of the file name as the label, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `Scratch.pcman.recipe` | `com.github.serrc-techops.pcman.Scratch` | Parent: the download recipe. Hands the file to the package tool (`pcman`) with the version of the file name as the label, which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `Scratch.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `Scratch.pcman.recipe` is the package tool's way, with `PcmanImporter`. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The processor `ScratchInfoProvider.py` is in this folder. The Scratch Foundation serves
the installer through one redirect (301) from a fixed address. The processor reads the
`Location` header of that answer and follows no redirect. It outputs `url` (the address
that the `Location` names) and `version` (the version in that address's file name,
`3.32.1` on 2026-11-13). It outputs no hash, because none was found published. The
shared processors are in `../Win-SharedProcessors/`. Neither recipe stops on an
unchanged download, so an import that failed is tried again at the next run.

How strict the processor is:

- Exactly one request is made, with a time limit of 120 seconds, to
  `https://downloads.scratch.mit.edu/desktop/Scratch%20Setup.exe`. No body is read. No
  redirect is followed: the answer must be a redirect (301, 302, 303, 307 or 308) with
  exactly one `Location` header, and any other status is an error.
- The `Location` must be https on `downloads.scratch.mit.edu`, with no user name, no
  port, no query and no fragment.
- The path must be exactly `/desktop/Scratch%20<version>%20Setup.exe`, with the spaces
  written as `%20` and `<version>` made of two to four numbers joined by dots (at most nine
  digits each, at least one digit that is not zero). Any other path stops the run.

The recipe gives `URLDownloader` the file name `Scratch-Setup-<version>.exe`, so that the
cached file has no space and no `%20` in its name. (AutoPkg 2.9.0's `URLDownloader`,
read in its source, takes the last part of the address as it stands when no `filename` is
given, so the cached file would otherwise be named `Scratch%203.32.1%20Setup.exe`.) The
downloader fetches the address that the processor gave; on 2026-11-13 that address
answered 200 itself, with no further redirect.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What protects, and what does not

Nothing proves that the downloaded file is what the Scratch Foundation published: no
hash was found, and a signature check is not built. The shared importer knows this: no
step of the recipe sets `checksum_verified` with the hash of the file, so a real run is
refused before the package tool starts. The checks that remain do not replace a verification.

- **The address.** The processor accepts only an address of exactly one form on one
  fixed host (`downloads.scratch.mit.edu`), reached through one answer of that same host.
  That shows where the address came from. It does not show what the file at that address is.
- **The same product.** For an MSI the package tool refuses a different upgrade code.
  Whether it has an equivalent check for an EXE was NOT established by the writer.
- **The label.** An EXE has no version that the package tool reads for itself, so the
  recipe passes the version in the file name that the redirect names (`3.32.1` on
  2026-11-13). The label is the publisher's word for the release and proves nothing about
  the content of the file.

An installer of another content under the same address would pass all of these.

## The label is the version in the file's name, and nothing compares it with the product's

**The label that the package tool gets is the version in the name of the file that the
download address redirects to, and not a version read from the file or from the installed
Scratch. No step of this recipe compares them.** The file's own `ProductVersion` was not
read (the file was not downloaded), and the version that the installed Scratch shows has
not been read by anyone. If the file name stopped tracking the product, the recipe would
still publish under the name's number, and that number orders the versions in the
repository. The recipe does not check this at any run. A person checks it, once:

1. Run the dry run with `-v` (step c) and read the line `Scratch's address names version
   ...` of `ScratchInfoProvider`: it gives the label.
2. On a Windows PC, read the downloaded file's properties (its `ProductVersion`). If it
   does not equal the label, or begins differently, stop and tell the owner before
   anything is published.
3. After the first install on a test PC, compare the label with the version that the
   installed Scratch reports (its About box, or its entry in Windows' list of installed
   programs). Nobody has done that. Whether the Cimian client sees the label and that
   version as the same version is NOT established.

The label has three parts (`3.32.1`). The client reads some three-part labels as a build
time (see `../Win-SharedProcessors/README.md`, the section `VersionFromName`, "Three-part
labels"): one whose first part is 20 to 99, or a year of four digits. A first part of `3`
meets neither rule.

Why the label is taken from the name and not from the file: the shared `WindowsExeVersion`
stops the run when the file has no version resource, and whether this file has one was
NOT read. The name was read. If the file turns out to have a `ProductVersion` equal to the
name's version, reading the file with `WindowsExeVersion` is the owner's choice.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01 with another recipe of this repository: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `Scratch.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `StatusService.cs:194-219`) are from `windowsadmins/cimian` at commit `e10498b`, as `../Win-SharedProcessors/README.md` gives them, and not checked against a later version.

**The download of this program is NOT verified** (see the status line above, which speaks of `pcman_allow_unverified` for the package tool's way). For this way the same rule holds with the input `cimian_allow_unverified`: `CimianImporter` REFUSES a real run of a download that no step verified (nothing is published) unless the override sets `cimian_allow_unverified` to true. Do not set it before a verification step exists. A dry run is allowed, and prints a `WARNING: the download was NOT verified` line.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **The version label** needs no program: `ScratchInfoProvider` reads it from the file name that the redirect names, and this recipe passes it on as `%version%`.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `scratch`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: they are only the writer's knowledge (see the status line), so they are left for a person who has tried them on a test PC, together with the question of a per-machine install. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i Scratch-Win
    autopkg list-recipes | grep -i Scratch.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Scratch.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `Scratch.cimian`, not a path. It writes `<the Windows overrides folder>/Scratch.cimian.recipe` with the identifier `local.cimian.Scratch` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.Scratch`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Scratch.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.Scratch`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on (NOT YET: see the status line)

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/Scratch.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Scratch.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

**Not yet.** This download has no verification step, so `CimianImporter` refuses the real run below until the override also sets `cimian_allow_unverified` to true, which a person decides only after the file was checked by hand, and which is then written in the override's `Input`, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_allow_unverified bool true' \
        <the Windows overrides folder>/Scratch.cimian.recipe

With it the run prints `WARNING: published WITHOUT a verified download` and the report row says `published, NOT verified`.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Scratch.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Scratch.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Scratch.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Scratch.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `Scratch.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `Scratch.pcman`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool.

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
   it replaces. If the package tool's repository has an item `scratch` already, look
   at it first: an item of the kind `choco` is not the template; an item that an earlier
   run of this step made is, and this step is then not needed. The command, as a proposal
   that was NOT run, with a real installer of the current release:

       pcman import <path of the installer> --name scratch \
           --version <the label that the first dry run prints> \
           --directory <the folder of the item> \
           --install-arguments '/S /allusers' \
           --display-name "Scratch 3" \
           --category <the category of the item> --developer "Scratch Foundation" \
           --description <one sentence about the item> \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   The switches `/S /allusers` are the **writer's knowledge of electron-builder's NSIS
   installers, NOT read from the vendor and NOT tested on a PC** (see the status line): a
   person tries them on a test PC first, as SYSTEM, and changes them if the install is
   per user or not silent. `--architectures` is left out because the architecture of the
   EXE was not read. `--install-path` is left out too: the path must be read on one PC
   after an install, and a wrong path would install again at every run, so add it only
   after reading it; until then the template has no install check, and the client relies
   on the ManagedInstalls registry.
   The label after `--version` is the version in the file name, as the first dry run
   prints it (for the file of 2026-11-13: `3.32.1`).
   Add the icon as the package tool's README describes. A person changes the template
   later; nothing else does. **If the template is made from the release that is current
   at the vendor, the first run says "Nothing new" (see step c). To see a dry run that would
   publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Scratch-Win
    autopkg list-recipes | grep -i Scratch.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Scratch.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Scratch.pcman`, not a path. Expected (not
run): it writes `<the Windows overrides folder>/Scratch.pcman.recipe` with the
identifier `local.pcman.Scratch` and the trust information of the two recipes and
the two processors that are not part of AutoPkg itself (`ScratchInfoProvider`,
`PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Scratch`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Scratch.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.Scratch`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**`-v` prints what each processor says about its own work; `-vv` would add every processor's
inputs and outputs, `pcman_root` and the repository among them, to the log: keep such a log private.** Expected, from
the code and the rehearsals of the other folders, NOT printed by this recipe yet, when
the current version is not yet in the repository:

    Scratch's address names version 3.32.1: https://downloads.scratch.mit.edu/desktop/Scratch%203.32.1%20Setup.exe
    This is the version in the file's name: the file itself and the installed program were not compared with it.
    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name     Version  Catalogs    Result
    scratch  <label>  Production  dry run, nothing written, NOT verified

**Read the label.** The first line gives the version in the file name, and it is the label
that goes to the package tool. Compare it once with the file's `ProductVersion` on a Windows
PC (see "The label is the version in the file's name"); if they differ, stop and tell the
owner before anything is published. The plan itself is not printed. If the current version
is in the repository already (the template was made from it), the line is `Nothing new: ...
is in the repository already. Nothing was written.` instead. That is correct.

If the server changes its answer so that the processor cannot read it, the run fails with a
line that begins `Scratch's download address` and publishes nothing. If the line says that
the address answered with something that is not a redirect, or leads to another host, stop
and tell the owner: the recipe never reads an address from another host than
`downloads.scratch.mit.edu`.

## d. Switch a real run on (NOT YET: see the status line)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file. Nothing was published. Publish by hand after
    checking the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template scratch --version <the label>

The label is the one that `ScratchInfoProvider` showed in the dry run. Then `pcman
catalogs` (step e.3).

**Only after the signature check exists, or when a person has decided to accept an
unverified download:** the override allows it. Both lines are needed.

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Scratch.pcman.recipe
    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_allow_unverified bool true' \
        <the Windows overrides folder>/Scratch.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Scratch.pcman.recipe

A change of the `Input` does not break trust (found with another recipe of this repository).
Do not use `-k` instead: on the command line it applies to every recipe of that run. A run
then prints `WARNING: published WITHOUT a verified download ...` at any verbosity, and the
report's row says `published, NOT verified`.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Scratch.pcman.recipe

   Only after both lines of step d. Expected (not run): `Published scratch ...`,
   the warning `published WITHOUT a verified download`, and the table

       The following versions were published by the package tool:
       Name     Version  Catalogs    Result
       scratch  <label>  Production  published, NOT verified

   The repository then has the installer under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions scratch` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Scratch.pcman.recipe

   Expected (not run): `Nothing new: ... is in the repository already. Nothing was
   written.` (A new override gets a new cache folder, so its first run downloads the file
   again before it says so.)

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Scratch.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Scratch.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository another recipe of this repository failed
(exit code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again. (Not run with this recipe.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private. The lines of `ScratchInfoProvider` are printed
  with `-v` or `-vv`.
- The download recipe has no input of its own besides `NAME`: the address is fixed in
  the processor.
- The processor needs no browser identity: the writer's GET of 2026-11-13 with the
  processor's plain name `autopkg-ScratchInfoProvider` got the same answer as a header
  request with a browser's name. Whether the server answers the build Mac's network the
  same way is NOT established.
- The vendor also offers Scratch through the Microsoft Store (the download page links it).
  This recipe takes only the direct download.
- The recipe's `NAME` is `Scratch` and `PCMAN_TEMPLATE` is `scratch`. Change
  the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) skips the download. The file is not
  checked at all, and the label is still the one from the address that the processor read.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of answer (the addresses in `tests/` are
written by hand after the real answer of 2026-11-13, not saved from the real server), that
the three recipes are property lists, that every argument is an input that the processors
declare, that the label comes from the processor and the cimian recipe passes it as
`version` and the pcman recipe as `pcman_version`, that the file name has no space, that the
descriptions and the top of this README say that the download is not verified and that a
real run is refused, that the status line names the per-machine question first, that this
README states no hash and has no `make-override` without `--override-dir` and runs no
recipe by its identifier, that it says what was NOT done, and that nothing site-specific is
in the folder.

The tests of this folder also run each importer recipe against a stand-in: the package
tool's for the `.pcman.recipe`, a temporary Cimian repository for the `.cimian.recipe`
(that one needs PyYAML and is skipped without it).
