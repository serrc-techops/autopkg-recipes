# Win-Inkscape

A Windows recipe pair: Inkscape, the 64-bit `.msi`, the current release from the project's own site and its media server.

**Status. NOT rehearsed with AutoPkg. The facts of the source were fetched by the writer on 2026-10-02: no recipe, no processor and no test of this folder has run with AutoPkg, with the package tool or on a PC. What was read on the real servers (`inkscape.org` and `media.inkscape.org` are one publisher): (1) `https://inkscape.org/release/` answers 302 with a `Location` of `https://inkscape.org/release/inkscape-1.4.4/`, so the version is the last path element after `inkscape-`; (2) `https://inkscape.org/release/inkscape-<version>/windows/64-bit/msi/dl/` answers 200, an HTML page of about 28 KB, that holds exactly one link of the form `href="/gallery/item/<id>/<file name>"` whose file name ends in `.msi` (`/gallery/item/59504/inkscape-1.4.4_2026-05-05_dcaf3e7-x64.signed_xMx7DJV.msi` on that day), and the same path under language prefixes (`/de/release/...`), which are not gallery links; (3) `https://inkscape.org/gallery/item/<id>/` answers 200, an HTML page, that holds exactly one link `href="https://media.inkscape.org/media/resources/sigs/<name>.sha256"`; (4) that hash file answers 200 directly, without a redirect, and holds exactly one line of 64 hex digits, two spaces, the file name WITHOUT the download's `_<token>` (`inkscape-1.4.4_2026-05-05_dcaf3e7-x64.signed.msi`) and a new line; (5) the download `https://inkscape.org/gallery/item/<id>/<file name>` answers 302 to `https://media.inkscape.org/dl/resources/file/<file name>`, which answers 200 with `content-disposition: attachment` and 170323968 bytes. So the processor reads the redirect of (1) without following it, builds the media address of (5) itself and never follows the redirect of the download, and the downloader fetches that address directly. On 2026-10-02 the processor's `main()` was also run end to end on the saved real answers (the real `Location` of the release redirect, the saved download page, gallery page and hash file, default inputs): it made exactly the four requests in order and gave the media address of `inkscape-1.4.4_2026-05-05_dcaf3e7-x64.signed_xMx7DJV.msi`, version `1.4.4` and the hash of the real hash file, beginning 2fa033e9. What is still NOT known: the MSI's own ProductVersion and UpgradeCode, and whether the label has the shape that the package tool takes; the file names of the 32-bit installer (they were not read, and the processor refuses `32-bit`); that the publisher keeps these addresses and file names for the next releases; how the package tool handles this MSI, the template item `inkscape`, `pcman catalogs`, and anything about a run with AutoPkg. The page excerpts of the tests were written by hand from the real link lines of 2026-10-02 with everything else cut, and the hash line of the tests is made up, so they prove what the code does with answers of that form and nothing about the site today. The first run on the build Mac (step c) is the check of what is still not known. When it fails, stop. A failure of the processor or of the hash check writes nothing, and the run is a dry run until the owner switches a real run on. Read the real pages and the real hash file again, correct the processor or the recipe, and only then touch the trust information: never accept a trust change to make a failing run go through. If the run shows a redirect for a page or for the hash file, or no redirect for the current-release address, stop and tell the owner: the site has changed, and the processor refuses what it does not recognise on purpose. Where a line below says "expected", it is what the code leads to, not something that was printed. Every override command here carries `--override-dir`: see the paragraph "Run every override with `--override-dir`" below.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Inkscape-Win.download.recipe` | `com.github.serrc-techops.download.Inkscape-Win` | Reads the project's current-release redirect, the release's download page and the file's gallery page, downloads the MSI from the media server, and stops when the file does not match the SHA-256 in the publisher's hash file |
| `Inkscape.cimian.recipe` | `com.github.serrc-techops.cimian.Inkscape` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

The processor `InkscapeInfoProvider.py` is in this folder. It makes four requests:

1. `https://inkscape.org/release/` answers with a redirect. The processor does **not**
   follow it: it reads the `Location` header of that one answer, requires the host
   `inkscape.org` and a path of exactly `/release/inkscape-<version>/` with a version of
   numbers and dots, and takes the version.
2. `https://inkscape.org/release/inkscape-<version>/windows/64-bit/msi/dl/` is a page with
   **exactly one** link `/gallery/item/<id>/<file name>` whose file name ends in `.msi`.
   The file name must begin with `inkscape-<version>_` and end with
   `-x64.signed_<token>.msi`, where the token is letters and digits that the publisher adds.
   A link of another form, or a second different link, stops the run.
3. `https://inkscape.org/gallery/item/<id>/` is a page with exactly one link
   `https://media.inkscape.org/media/resources/sigs/<name>.sha256`. Its host must be
   `media.inkscape.org`, its path must begin with `/media/resources/sigs/` and end with
   `.sha256`.
4. That hash file holds one line (64 hex digits, two spaces, a file name). The file name
   must equal the gallery file name with `_<token>` removed before `.msi`.

It outputs `url` (the media address `https://media.inkscape.org/dl/resources/file/<file name>`,
built from the file name, not followed from the gallery), `version` and `expected_sha256`.
The recipe gives `URLDownloader` the `filename` `inkscape-%version%-x64.msi`, so that the
cached file has a stable name, without the publisher's date, commit and token.

Every request goes to one fixed host over https, follows no redirect (a redirect is an
error, except that request 1 must be one and only its `Location` is read), has a size
limit (256 KiB for a page, 4 KiB for the hash file) and a time limit of 120 seconds. The
input `INKSCAPE_ARCHITECTURE` is `64-bit` and nothing else: the file names of the 32-bit
installer were not read, so `32-bit` is refused with a message that says so. The processor
never guesses: a page or a file that is not what it expects is an error.

The other processors are in `../Win-SharedProcessors/` (see its README). Neither
recipe stops on an unchanged download, so an import that failed is tried again at
the next run.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What the checks prove

- **The hash.** The pages and the hash file come from the publisher's own hosts
  (`inkscape.org` and `media.inkscape.org`, one publisher), and so does the file. The check
  shows that the file is what the publisher published. It does not help if the publisher's
  own servers are changed.
- **The same product.** The package tool refuses an MSI whose upgrade code differs from
  the template's. Whether the MSI of Inkscape has the same upgrade code in every release is
  NOT established; the first dry run against a template shows it.
- **The label.** The recipe gives no version label. For an MSI the package tool takes the
  MSI's own ProductVersion. What shape that has for Inkscape (three numbers, or four) is NOT
  established.

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
   it replaces. The command, with a real MSI of the current release:

       pcman import <path of the Inkscape MSI> --name inkscape \
           --directory <the folder of the item> --architectures x64 --no-prompt \
           --display-name "Inkscape" --category "<the category of the item>" \
           --developer "Inkscape Project" --description "<a one-line description>" --build

   There is no `--version`: the package tool takes the MSI's own version. There are
   no install arguments here: the package tool knows the arguments of an MSI. Add the
   icon as the package tool's README describes. A person changes the template later;
   nothing else does.
   **If the template is made from the release that is current on the server, the
   first run says "Nothing new" (see step c). To see a dry run that would publish,
   make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Inkscape-Win
    autopkg list-recipes | grep -i Inkscape.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Inkscape.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Inkscape.cimian`, not a path. Expected:
it writes `<the Windows overrides folder>/Inkscape.cimian.recipe` with the
identifier `local.cimian.Inkscape` and the trust information of the two
recipes and the three processors that are not part of AutoPkg itself
(`InkscapeInfoProvider`, `ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.Inkscape-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Inkscape.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.Inkscape`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current release is not yet in the
repository (from the code and the other recipes of this repository, NOT seen; the
version is the MSI's own):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name       Version                   Catalogs    Result
    inkscape   <the MSI's own version>   Production  dry run, nothing written

With `-v` the run also prints `Current release: ...` and the vendor's SHA-256,
and then `SHA-256 verified: ...`. If the current release is in the repository
already (the template was made from it), the line is `Nothing new:
inkscape ... is in the repository already. Nothing was written.` instead. That is correct.

If the site's layout is not what the processor expects, the run fails with a
line that begins `Inkscape release address:`, `Inkscape download page:`,
`Inkscape gallery page:` or `Inkscape hash file:` (or with `The server answered ...`
or `The server could not be asked ...`) and publishes nothing. An answer with
`a redirect is not followed` means that a page or the hash file now redirects: see
the status line at the top and tell the owner. An answer for `the current release`
that says `not with a redirect` means that the project's current-release address
no longer redirects: the processor reads that redirect on purpose, so stop and tell
the owner.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Inkscape.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Inkscape.cimian.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip, not with this
recipe). Do not use `-k pcman_dry_run=false` instead: on the command line it
applies to every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Inkscape.cimian.recipe

   Expected: `Published inkscape <the MSI's own version>.` and a table with the result
   `published`. The repository then has the MSI under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions inkscape` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Inkscape.cimian.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Inkscape.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Inkscape.cimian.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The current-release address is whatever the project calls the current release. A person
  looks when the project changes that (a new major version): the template's upgrade code
  may not stay the same.
- The input of the download recipe is `INKSCAPE_ARCHITECTURE` (default `64-bit`). Change it
  in the override's `Input`, not in the recipe. A 32-bit template is another item and needs
  the 32-bit file names read first.
- A file name or a version that is not of the expected form is an error, never a
  guess. A second link, or a link to another kind of file, is an error and not ignored. The
  checksum step sets `checksum_verified` and the hash `checksum_sha256`, which the shared
  importer compares with the file it imports, so it allows a real run of this recipe
  without `pcman_allow_unverified`.
- The recipe's `NAME` is `Inkscape` and `PCMAN_TEMPLATE` is `inkscape`. Change the template
  name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) fails the checksum unless the file is
  the vendor's file.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of page and hash file (the two excerpts in
`tests/download_page_excerpt.html` and `tests/gallery_page_excerpt.html` were written by hand
from the real link lines of 2026-10-02; the other pages and the hash lines are made up), that
a 302 is read and not followed (against a server of the test machine), that both recipes are
property lists, that every argument is an input that the processor declares, that no
recipe sets `pcman_version` for an MSI, that this README says what was NOT done, has
no `make-override` without `--override-dir` and runs no recipe by its identifier, and
that nothing site-specific is in the folder.
