# Win-Firefox

A Windows recipe pair: Mozilla Firefox, the 64-bit `.exe` installer, `en-US`, release channel, upgraded in place (not the MSI).

**Status. NOT rehearsed with AutoPkg. The facts of the source were fetched by the writer on 2026-10-02: no run of AutoPkg was made, and nothing was written to a repository. Read from Mozilla's servers on that day (the files were saved and the processor's functions were run on them): (1) `https://product-details.mozilla.org/1.0/firefox_versions.json` answered 200 with no redirect, and holds the keys `LATEST_FIREFOX_VERSION` (`157.0`) and `FIREFOX_ESR` (`140.17.0esr`, so the ESR value does end in `esr`); the beta key holds a `b` version, which the processor never reads; (2) `https://download-installer.cdn.mozilla.net/pub/firefox/releases/157.0/SHA256SUMS` answered 200 with no redirect (about 540 KB, far under the limit of 8 MB); every one of its lines is 64 hex digits, two spaces and a path; it holds both `win64/en-US/Firefox Setup 157.0.exe` and `win64/en-US/Firefox Setup 157.0.msi`, and the processor takes the `.exe` line only; (3) a HEAD request for `https://download-installer.cdn.mozilla.net/pub/firefox/releases/157.0/win64/en-US/Firefox%20Setup%20157.0.exe` answered 200 with no redirect (the spaces of the file name are `%20`). NOT established: that the ESR release folder and its file carry the suffix (`140.17.0esr`) as the processor assumes (only the version file was read for ESR); that the version label `157.0` is what the installer itself shows as its version; the silent switch `/S`, the install path of the first import and that an upgrade in place keeps `distribution\policies.json` (the owner's decision note, not tried); that the template item `firefox` exists and is an EXE item; `pcman catalogs`; any run with AutoPkg. The tests use a version file and a SHA256SUMS excerpt that the writer wrote by hand after the real files of 2026-10-02, with made-up digits, so they prove what the code does with answers of that form and nothing about Mozilla today. The first run on the build Mac is the check of everything that is NOT established. When it fails, STOP: nothing was written (a run that fails before the import writes nothing). Read the real version file, the real release folder and the real SHA256SUMS in a browser, correct the processor or the recipe, and only then look at the trust information. Never accept new trust information first to make a failure go away.**


| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Firefox-Win.download.recipe` | `com.github.serrc-techops.download.Firefox-Win` | Reads Mozilla's version file, takes the current version of the channel (default `release`), downloads its installer, and stops when the file does not match the SHA-256 that Mozilla's `SHA256SUMS` gives for that file |
| `Firefox.cimian.recipe` | `com.github.serrc-techops.cimian.Firefox` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

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
   at it first: it must be an item for the EXE, and this step is not needed. The command,
   with a real installer of the current release:

       pcman import <path of "Firefox Setup 141.0.exe"> --name firefox --version 141.0 \
           --directory <the folder of the item> --install-arguments /S \
           --install-path 'C:\Program Files\Mozilla Firefox\firefox.exe' --architectures x64 \
           --display-name Firefox --category <the category of the item> --developer Mozilla \
           --description <one sentence about the item> --no-prompt --build

   The label after `--version` is the version of the installer as the installer shows it
   (for an EXE the package tool is given it; here it is the same text that the recipe
   passes). `--install-arguments /S` and the install path are the writer's knowledge of
   the Firefox installer (from the writer's knowledge, not read in the installer): check
   both in Mozilla's documentation and on one PC before this command is run. A person
   changes the template later; nothing else does. **If the template is made from the
   release that is current on Mozilla's server, the first run says "Nothing new" (see
   step c). To see a dry run that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others (several shared AutoPkg recipe repositories
have recipes for Firefox):

    autopkg list-recipes | grep -i Firefox-Win
    autopkg list-recipes | grep -i Firefox.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Firefox.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Firefox.cimian`, not a path. Expected (not
run): it writes `<the Windows overrides folder>/Firefox.cimian.recipe` with the
identifier `local.cimian.Firefox` and the trust information of the two recipes and
the three processors that are not part of AutoPkg itself (`MozillaFirefoxInfoProvider`,
`ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.Firefox-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.Firefox`) runs the recipe itself, not the
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
        <the Windows overrides folder>/Firefox.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.cimian.recipe

A change of the `Input` does not break trust (found with 7-Zip). Do not use
`-k pcman_dry_run=false` instead: on the command line it applies to every recipe
of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.cimian.recipe

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

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.cimian.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Firefox.cimian.recipe

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
