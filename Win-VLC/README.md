# Win-VLC

A Windows recipe pair: VLC media player, the 64-bit `.msi`, the current release from the vendor's own download server.

**Status. NOT rehearsed with AutoPkg. The facts of the source were fetched by the writer on 2026-10-02: no recipe, no processor and no test of this folder has run with AutoPkg, with the package tool or on a PC. What was read on the real server: `https://download.videolan.org/vlc/last/win64/` answers 200 without a redirect and is an HTML directory index whose links are bare file names; it names one version, with the `.exe`, `.msi`, `.7z` and `.zip` of it, each with `.asc`, `.md5`, `.sha1` and `.sha256` files, and a `-debugsym.7z` set; `https://download.videolan.org/vlc/<version>/win64/vlc-<version>-win64.msi.sha256` answers 200 directly, without a redirect, and holds 64 lower-case hex digits, two spaces, the MSI's file name and a new line; the MSI on that host is answered with a redirect to `get.videolan.org`, which sends it on to a mirror. `get.videolan.org` itself answers the hash file and the MSI with a redirect to a mirror, so the processor reads the index and the hash file from `download.videolan.org`, the publisher's own server, and never from `get.videolan.org`: a hash read from a mirror is not the publisher's. The downloader follows the redirects of the MSI, and the check against the publisher's hash still shows that the file is what VideoLAN published. What is still NOT known: the MSI's own ProductVersion and UpgradeCode, how the package tool handles this MSI, the template item, `pcman catalogs`, and anything about a run with AutoPkg. The index excerpt of the tests is a copy of the real index of 2026-10-02; the hash lines of the tests are made up. The first run on the build Mac (step c) is the check of what is still not known. When it fails, stop. A failure of the processor or of the hash check writes nothing, and the run is a dry run until the owner switches a real run on. Read the real index and the real hash file again, correct the processor or the recipe, and only then touch the trust information: never accept a trust change to make a failing run go through. If the run shows a redirect for the index or for the hash file, stop and tell the owner: the server has changed, and the processor refuses a hash read from another host on purpose. Where a line below says "expected", it is what the code leads to, not something that was printed. Every override command here carries `--override-dir`: see the paragraph "Run every override with `--override-dir`" below.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `VLC-Win.download.recipe` | `com.github.serrc-techops.download.VLC-Win` | Reads the server's index of the current release, takes the MSI of that release from its own folder, and stops when the file does not match the SHA-256 in the vendor's hash file |
| `VLC.cimian.recipe` | `com.github.serrc-techops.cimian.VLC` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `VLC.pcman.recipe` | `com.github.serrc-techops.pcman.VLC` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `VLC.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `VLC.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The processor `VideoLANVlcInfoProvider.py` is in this folder. It reads the index
`https://download.videolan.org/vlc/last/win64/` and keeps the links that are exactly
`vlc-<version>-win64.msi` (the link to `vlc-<version>-win64.msi.sha256` is not
one). It requires **exactly one version** among them: none, or two, stops the run.
It then reads `https://download.videolan.org/vlc/<version>/win64/vlc-<version>-win64.msi.sha256`,
which must hold one line (64 hex digits, two spaces, a file name) whose file name is
the MSI's name. The file to download is in that same versioned folder, not in
`last`, so that the file and its hash name one release. It outputs `url`,
`version` and `expected_sha256`. The index and the hash file are read from
`download.videolan.org` only, never from `get.videolan.org`, which redirects both to a
mirror (see the status line). The MSI itself is redirected to a mirror when it is
downloaded; the downloader follows that, and the file is checked against the hash
of the publisher's own server.

Both requests go to one fixed host over https, follow no redirect, have a size limit
(1 MiB for the index, 16 KiB for the hash file) and a time limit of 120 seconds.
The input `VLC_ARCHITECTURE` is `win64` or `win32` and nothing else. A version is three
or four numbers and is compared by its numbers. The processor never guesses: a
page or a file that is not what it expects is an error.

The other processors are in `../Win-SharedProcessors/` (see its README). Neither
recipe stops on an unchanged download, so an import that failed is tried again at
the next run.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What the checks prove

- **The hash.** The hash file and the index come from the publisher's own server
  (`download.videolan.org`). The MSI is downloaded by name from the same folder, but the
  server redirects it to a mirror; the downloader follows that, the processor's own
  requests do not. The hash is the publisher's and the file may come from a mirror, so
  the check shows that the file is what VideoLAN published. It does not help if the
  publisher's own server is changed.
- **The same product.** The package tool refuses an MSI whose upgrade code differs from
  the template's. Whether the MSI of VLC has the same upgrade code in every release is
  NOT established; the first dry run against a template shows it.
- **The label.** The recipe gives no version label. For an MSI the package tool takes the
  MSI's own ProductVersion. What shape that has for VLC (three numbers, or four) is NOT
  established.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg, `msiinfo` (msitools: `brew install msitools`) for the MSI, and nothing of the owner's: no package tool. It uses `VLC.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `vlc`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **For an `.msi` nothing needs completing for a silent install:** the client runs `msiexec /i <file> /qn /norestart` itself and then the arguments of the item (`InstallerService.cs:936-948`), so the recipe gives no silent arguments, and `CimianImporter` writes the install check of an MSI (an `installs` entry of type `msi` with the MSI's codes and version). What the MSI's own properties allow (features, per-user or per-machine) is the template's business: give them as `installer: {args: [...]}` in the override's `pkginfo`. An MSI whose upgrade code is not the template's, or that has none where the template's item had one, is refused (Windows Installer does not upgrade across upgrade codes): `cimian_allow_product_change` set to true in the override allows it, with a WARNING.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i VLC-Win
    autopkg list-recipes | grep -i VLC.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> VLC.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `VLC.cimian`, not a path. It writes `<the Windows overrides folder>/VLC.cimian.recipe` with the identifier `local.cimian.VLC` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.VLC`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VLC.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.VLC`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.msi (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/VLC.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VLC.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VLC.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VLC.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VLC.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VLC.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `VLC.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `VLC.pcman` where this README used to say `VLC.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `VLC.cimian.recipe` (when that recipe ran the package tool) must be made again from `VLC.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `VLC.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   it replaces. The command, with a real MSI of the current release:

       pcman import <path of the vlc MSI> --name vlc \
           --directory <the folder of the item> --architectures x64 --no-prompt \
           --display-name "VLC media player" --category "<the category of the item>" \
           --developer VideoLAN --description "<a one-line description>" --build

   There is no `--version`: the package tool takes the MSI's own version. There are
   no install arguments here: the package tool knows the arguments of an MSI. Add the
   icon as the package tool's README describes. The template item removes the EXE
   edition of VLC from a PC itself; that is set in the item and is not the
   recipe's business. A person changes the template later; nothing else does.
   **If the template is made from the release that is current on the server, the
   first run says "Nothing new" (see step c). To see a dry run that would publish,
   make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i VLC-Win
    autopkg list-recipes | grep -i VLC.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> VLC.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `VLC.pcman`, not a path. Expected:
it writes `<the Windows overrides folder>/VLC.pcman.recipe` with the
identifier `local.pcman.VLC` and the trust information of the two
recipes and the three processors that are not part of AutoPkg itself
(`VideoLANVlcInfoProvider`, `ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.VLC`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VLC.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.VLC`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current release is not yet in the
repository (from the code and the other recipes of this repository, NOT seen; the
version is the MSI's own):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name  Version                   Catalogs    Result
    vlc   <the MSI's own version>   Production  dry run, nothing written

With `-v` the run also prints `Current release: ...` and the vendor's SHA-256,
and then `SHA-256 verified: ...`. If the current release is in the repository
already (the template was made from it), the line is `Nothing new:
vlc ... is in the repository already. Nothing was written.` instead. That is correct.

If the server's layout is not what the processor expects, the run fails with a
line that begins `VideoLAN index:` or `VideoLAN hash file:` (or with `The server
answered ...` or `The server could not be asked ...`) and publishes nothing. An answer
with `a redirect is not followed` means that the publisher's server now redirects the
index or the hash file: see the status line at the top and tell the owner.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/VLC.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VLC.pcman.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip, not with this
recipe). Do not use `-k pcman_dry_run=false` instead: on the command line it
applies to every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VLC.pcman.recipe

   Expected: `Published vlc <the MSI's own version>.` and a table with the result
   `published`. The repository then has the MSI under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions vlc` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VLC.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VLC.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/VLC.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The index at `last` has no input for a line of releases: it is whatever the vendor
  calls the current release. A person looks when the vendor changes that (a new
  major version): the template's upgrade code may not stay the same.
- The input of the download recipe is `VLC_ARCHITECTURE` (default `win64`). Change it
  in the override's `Input`, not in the recipe. A 32-bit template is another item.
- A file name or a version that is not of the expected form is an error, never a
  guess. A link such as `vlc-<version>-win64.msi.sha256` is not the MSI and is ignored.
  The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which
  the shared importer compares with the file it imports, so it allows a real run of
  this recipe without `pcman_allow_unverified`.
- The recipe's `NAME` is `VLC` and `PCMAN_TEMPLATE` is `vlc`. Change the template
  name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) fails the checksum unless the file is
  the vendor's file.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of index and hash file (the
excerpt in `tests/last_win64_index_excerpt.html` is a copy of the real index
of 2026-10-02, which holds no hash; the other pages and the hash lines are made up), that both recipes are
property lists, that every argument is an input that the processor declares, that no
recipe sets `pcman_version` for an MSI, that this README says what was NOT done, has
no `make-override` without `--override-dir` and runs no recipe by its identifier, and
that nothing site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
