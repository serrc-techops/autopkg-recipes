# Win-LibreOffice

A Windows recipe pair: LibreOffice, the 64-bit `.msi` of the "fresh" line (the newer of the two lines that The Document Foundation offers).

**NOT WORKING (expected). This recipe pair is expected to stop at its first run and publish nothing. The provider reads a hash file (`<the MSI's name>.sha256`) that the vendor's server did not show on 2026-10-02 (the address answered 404 once and 500 once, and the folder holds no such file), so the run is expected to fail at `LibreOfficeInfoProvider` before the download is checked, and LibreOffice stays a hand import until the provider is changed to read a hash from where the server shows it. Whether the pair stays in this repository is the owner's decision at the merge.**

**Status. NOT rehearsed with AutoPkg. Some facts of the source were fetched by the writer on 2026-10-02: the server answered only now and then. VERIFIED: (1) `https://download.documentfoundation.org/libreoffice/stable/` answered 200 with no redirect; it is a mirrorbrain HTML index whose version links are exactly `25.8.7/`, `26.2.5/`, `26.2.6/`, `26.8.0/` and `26.8.1/` (three lines at once, with two versions in two of them), beside other links (the sort links `?C=N;O=D`, `/libreoffice/`, `/mirrorbrain.css`, a mailto and `http://mirrorbrain.org/`) that are not version folders; the processor read a saved copy of it as `fresh` 26.8.1 and `still` 26.2.6; (2) `.../stable/26.8.1/win/` answered 200 and lists `aarch64/`, `x86/` and `x86_64/`; (3) the listing of `.../stable/26.8.1/win/x86_64/` (it answered once) holds, for the main MSI and for every helppack and langpack, four files: `LibreOffice_26.8.1_Win_x86-64.msi`, `...msi.mirrorlist`, `...msi.asc` and `...msi.asc.mirrorlist`, and the `_sdk.msi` set in the same way. **THE HASH FILE THAT THE PROVIDER EXPECTS DOES NOT EXIST: there is no `.sha256`, `.md5` or `.sha1` file in that folder.** The address `<index>/<version>/win/x86_64/LibreOffice_<version>_Win_x86-64.msi.sha256` answered 404 once and 500 once. The folder offers a `.mirrorlist` page per file (mirrorbrain, which usually shows the file's hashes on that page) and a `.asc` signature. Until the owner reads the `.mirrorlist` page of the MSI on the build Mac and the provider is changed to read the hash from wherever it is shown, this recipe stays a dry run that fails at the provider (`LibreOffice hash file:` or `The server answered 404 ... for the hash file`), nothing is written, and LibreOffice stays a hand import. The code and the tests of the provider still have the shape of the hash file that does not exist; they are the pattern for the next step, not a working check. NOT VERIFIED: the `.mirrorlist` page and a `.meta4` address never answered, so where mirrorbrain shows a hash, and in what form, is not established; a HEAD of the MSI answered 500 once, so the MSI's address and redirect behaviour are not established either; nor are the MSI's ProductVersion and UpgradeCode, the template, `pcman catalogs`, and any run with AutoPkg. When the provider is changed, the first run on the build Mac is the check of each fact it relies on. When a run fails, stop: nothing was written. Read the real page, and correct the recipe or `LibreOfficeInfoProvider.py` to what it shows; never accept the trust information first, and never write a hash into a recipe. If a hash is ever read from a mirror's page, stop and tell the owner, because a hash read from a mirror is not the publisher's. Where a line below says "expected", it is what the code is written to print, not something that was printed. Every override command here carries `--override-dir`: see the next paragraph.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `LibreOffice-Win.download.recipe` | `com.github.serrc-techops.download.LibreOffice-Win` | Reads the vendor's index of stable releases, takes the version of the line in `LIBREOFFICE_LINE` (default `fresh`), downloads its MSI, and stops when the file does not match the SHA-256 in the vendor's hash file |
| `LibreOffice.cimian.recipe` | `com.github.serrc-techops.cimian.LibreOffice` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

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
  (2026-10-02), so this recipe stays a dry run that fails at the provider, and LibreOffice stays
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
    autopkg list-recipes | grep -i LibreOffice.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> LibreOffice.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `LibreOffice.cimian`, not a path. Expected:
it writes `<the Windows overrides folder>/LibreOffice.cimian.recipe` with the
identifier `local.cimian.LibreOffice` and the trust information of the two
recipes and the three processors that are not part of AutoPkg itself
(`LibreOfficeInfoProvider`, `ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.LibreOffice-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.LibreOffice`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current release is not yet in the
repository (the lines of the 7-Zip rehearsal, with this program's name; this
program was NOT run, and the version is the MSI's own):

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
        <the Windows overrides folder>/LibreOffice.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.cimian.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip, not with this
program). Do not use `-k pcman_dry_run=false` instead: on the command line it applies
to every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.cimian.recipe

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

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.cimian.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/LibreOffice.cimian.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line (not run for this program):

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
