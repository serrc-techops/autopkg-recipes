# Win-PDFsam

A Windows recipe pair: PDFsam Basic, the `.msi` of the project `torakiki/pdfsam` on GitHub.

**Status. NOT rehearsed, and the facts of the source NOT fetched by the writer: this recipe pair was written with the network closed, from the writer's knowledge and from the pattern of the recipes `Win-7Zip` and `Win-ZabbixAgent2`. These facts are from the writer's knowledge and were NOT read from the source: that the project is `torakiki/pdfsam` on GitHub; that a release has an asset named like `pdfsam-6.0.6.msi` beside a `-windows.zip`, a `.dmg` and a `.deb`, so that the pattern `pdfsam-[0-9.]+\.msi$` takes the MSI only; that the MSI is the 64-bit installer; that GitHub records a SHA-256 digest for that asset (an asset uploaded before GitHub began to record digests has none, and then `GitHubAssetDigest` stops the run with its error, nothing is written, and the program is a hand import until a release with a digest exists); that the project does not mark a release as a pre-release when it is one (the recipe skips releases that GitHub marks as pre-releases, and cannot know of any other kind); and that the MSI installs silently with the usual MSI switches. The step list is the one of `Win-7Zip`, which was rehearsed on 2026-10-01 with another product; nothing of this folder was run by anyone, not AutoPkg, not the package tool, not a PC. The only fact read from the source, on 2026-10-02 through git and for tags only, is that the newest tags of `torakiki/pdfsam` are v6.0.3, v6.0.4, v6.0.5 and v6.0.6, so the 5.3.1 of the writer's knowledge is an old release and the asset would be `pdfsam-6.0.6.msi` if the naming holds (not verified: the release assets and their digests were NOT fetched). The first run on the build Mac is the check of every one of these facts. When it fails (no asset matches, no digest, an error from the package tool), stop: nothing was written. Read the real release page and the real asset list, correct the recipe (the pattern, the repository, the template name), and only then look at the trust information: never accept trust information to make a failure go away. Where a line below says "expected", it is what the code and the pattern lead to, not something that was printed. Every override command here carries `--override-dir`: see the next paragraph.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `PDFsam-Win.download.recipe` | `com.github.serrc-techops.download.PDFsam-Win` | Takes the newest non-pre-release of `torakiki/pdfsam` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match |
| `PDFsam.cimian.recipe` | `com.github.serrc-techops.cimian.PDFsam` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

No shared download recipe is the parent. Neither recipe stops on an unchanged
download, so an import that failed is tried again at the next run. The processors are in
`../Win-SharedProcessors/` (see its README).

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/PDFsam.cimian.recipe

(For an override that was made before this key existed, use
`Add :Input:include_prereleases bool true` instead.) Keep it a boolean: AutoPkg only
tests whether the value is empty, so the text `false` would count as true. The recipe's
step does not set it, because AutoPkg applies the arguments of a step after the
override's `Input`, and they would beat it.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## a. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in
   AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step b) takes a recipe NAME and refuses
   a path. The rehearsal of `Win-7Zip` printed: `make-override doesn't work with absolute recipe
   paths`.

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
   it replaces. The command, with a real MSI of the project:

       pcman import <path of the downloaded pdfsam-<version>.msi> --name pdfsam \
           --display-name "PDFsam Basic" --category <the category> \
           --developer <the developer's name> --description <the description> \
           --directory <the folder of the item> --architectures x64 --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. The
   install arguments are the package tool's own for an MSI (silent, `/qn`, from the
   writer's knowledge, not read in the package tool's README or in the installer):
   read the package tool's README before the first import, and do not add an
   install path for an MSI unless the README asks for one. `--architectures x64` is
   from the writer's knowledge that the MSI is 64-bit (not read in the installer).
   Give the category, the developer and the description the package tool's README
   describes. A person changes the template later; nothing else does. **If the
   template is made from the installer that is current on GitHub, the first run says
   "Nothing new" (see step c). To see a dry run that would publish, make the
   template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i PDFsam-Win
    autopkg list-recipes | grep -i PDFsam.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> PDFsam.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `PDFsam.cimian`, not a path. It writes
`<the Windows overrides folder>/PDFsam.cimian.recipe` with the identifier
`local.cimian.PDFsam` and the trust information of the two recipes and the three
processors. **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.PDFsam-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.PDFsam`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected (the lines are those that `Win-7Zip` printed in its rehearsal, with this
product's name; nothing here was run), also without `-v`, when the current version is
not yet in the repository. `<version>` is the MSI's own version, which may have more
numbers than the release's tag:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name   Version  Catalogs    Result
    pdfsam <version>  Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: pdfsam <version> is in the repository already. Nothing was written.`
instead. That is correct.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/PDFsam.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.cimian.recipe

   Expected: `Published pdfsam <version>.` and the table

       The following versions were published by the package tool:
       Name   Version  Catalogs    Result
       pdfsam <version>  Production  published

   The repository now has the MSI under `pkgs/` and its pkginfo under `pkgsinfo/`,
   in the folder of the template. The item file of the template is not changed.

2. `pcman versions pdfsam` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Not rehearsed. The package tool prints "nothing to run" when its
   catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.cimian.recipe

   It prints `Nothing new: pdfsam <version> is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/PDFsam.cimian.recipe

## g. A share that is not mounted

The rehearsal of `Win-7Zip` used an empty folder as the repository. Its recipe failed
(exit code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written there. Expected here too, not run. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `PDFsam` and `PCMAN_TEMPLATE` is `pdfsam`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- The recipe gives no version label: for an MSI the package tool takes the MSI's own
  version. Whether it equals the release's tag is NOT established. Read what the
  first dry run prints.
- Whether a new release keeps the same UpgradeCode as the template, so that the
  package tool accepts it as the same product, is NOT established. The package
  tool refuses an MSI whose upgrade code differs from the template's: that is
  the correct stop, not a fault of the recipe. Test the first published version on one PC before
  the PCs get it.
- The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which the
  shared importer compares with the file it imports, so it allows a real run of this
  recipe without `pcman_allow_unverified`. The input of the download recipe is
  `SEARCH_PATTERN` (default `pdfsam-[0-9.]+\.msi$`): change it in the override's
  `Input`, not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares, that no recipe sets `pcman_version` for an MSI,
that the pattern takes the MSI and none of the other assets, that this README
opens with the status line that says what was NOT done, that this README has no `make-override`
without `--override-dir` and runs no recipe by its identifier, and that nothing
site-specific is in the folder.
