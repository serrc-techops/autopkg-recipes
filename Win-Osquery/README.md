# Win-Osquery

A Windows recipe pair: osquery, the `.msi` (the only MSI in each of the six releases that were read, so presumably the x64 package: the ARM64 build is published as a zip).

**Status. NOT rehearsed with AutoPkg: nothing in this folder has run with AutoPkg, the package tool, a share or a PC. The facts of the source were read by the writer on 2026-10-04 from GitHub's public API (read only, no file was downloaded): the release list (`https://api.github.com/repos/osquery/osquery/releases`, the newest six releases) and the record of one asset (`https://api.github.com/repos/osquery/osquery/releases/assets/<id>` of the MSI of `5.23.1`, the kind of address that `GitHubAssetDigest` reads). READ: (1) `osquery/osquery` publishes its releases there; the newest six (`5.23.1`, `5.23.0`, `5.22.1`, `5.21.0`, `5.20.0` and `5.19.0`) have plain numbers as tags, without a `v`, and none is flagged as a pre-release; (2) each has 17 assets and exactly one of them is an MSI, named `osquery-<version>.msi` (`osquery-5.23.1.msi`, 19984384 bytes); the pattern `osquery-[0-9.]+\.msi$` matches that file and none of the others; the other Windows files are `osquery-<version>.windows_x86_64.zip` and `osquery-<version>.windows_arm64.zip`, and there is a NuGet package `osquery.<version>.nupkg`; there is no arm64 MSI in these six releases, so the one MSI cannot be confused with one; AutoPkg 2.9.0 takes the first release (in GitHub's order, newest first, a pre-release skipped) that has a file whose name the pattern matches from its start (`GitHubReleasesInfoProvider.py`, `select_asset`, `re.match`); the test file writes that down as a function, and run on the saved list it takes `osquery-5.23.1.msi` of `5.23.1`; (3) GitHub records a SHA-256 digest for every asset of all six releases, and the record of the MSI of `5.23.1`, fetched anonymously as `GitHubAssetDigest` does it, holds one (`sha256:` and 64 hex digits); (4) the tag is a plain number, so `version` would be `5.23.1`; the recipe does not pass it on, because for an MSI the package tool takes the MSI's own version. NOT established: that the MSI is x64 (its name carries no architecture; it is the one MSI beside an x86_64 zip and an arm64 zip, and nobody opened it); the MSI's own ProductVersion and UpgradeCode (it may be the tag or the tag with a fourth part, and a newer release must have the same UpgradeCode as the template); the silent switch of the MSI; the template item; `pcman catalogs`; any run with AutoPkg. The steps and the lines quoted below are those of the rehearsal of `../Win-7Zip/`, which is another program: they show the shape of a run, not what this recipe printed. The first run on the build Mac is the check of everything that is NOT established. When it fails: stop. Nothing was written. Read the real release page and the real asset list, correct the recipe, and never the trust information first. Every override command here carries `--override-dir`: see the next paragraph.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Osquery-Win.download.recipe` | `com.github.serrc-techops.download.Osquery-Win` | Takes the newest non-pre-release of `osquery/osquery` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match |
| `Osquery.cimian.recipe` | `com.github.serrc-techops.cimian.Osquery` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

The recipe gives no version label to the package tool: for an MSI the tool takes
the MSI's own version. Neither recipe stops on an unchanged download, so an
import that failed is tried again at the next run. The processors are in
`../Win-SharedProcessors/` (see its README).

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/Osquery.cimian.recipe

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
   a path.

2. **The settings of the processor, as AutoPkg preferences.** One line each:

       defaults write com.github.autopkg pcman_root -string "<the package tool's folder>"
       defaults write com.github.autopkg pcman_python -string "<the package tool's Python>"

   `pcman_python` is only needed when it is not `<the package tool's folder>/.venv/bin/python3`.
   Write the values as strings. The repository is not a setting here: the package
   tool's own configuration says where it is. The repository must be reachable
   (the share mounted). For an MSI the tool needs `msiinfo` on its `PATH`.

3. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. If the repository has no item named `osquery`,
   make it once with this import, from a real MSI of osquery; if it has one, do not
   run the command. The command:

       pcman import <path of osquery-5.23.1.msi> --name osquery \
           --directory <the folder of the item> --architectures x64 \
           --display-name osquery --category <the category> \
           --developer <the developer> --description <one line> \
           --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. There
   is no `--install-arguments`: the package tool knows the arguments of an MSI
   (`/qn`; from the writer's knowledge, not read in the tool's code), so check on
   this first import that the pkginfo it wrote installs the MSI silently.
   `--architectures x64` is an expectation, not a fact: nobody opened the MSI, so its
   architecture is NOT established (see the status line); read it in the MSI before the
   import. The values of `--category`, `--developer` and `--description` are the owner's: see
   the package tool's README for the flags. What the template does about the
   osquery service and about its enrollment is the template's business, not the
   recipe's. A person changes the template later; nothing else does. **If the
   template is made from the release that is current on GitHub, the first run
   says "Nothing new" (see step c). To see a dry run that would publish, make the
   template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Osquery-Win
    autopkg list-recipes | grep -i Osquery.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Osquery.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Osquery.cimian`, not a path. It writes
`<the Windows overrides folder>/Osquery.cimian.recipe` with the identifier
`local.cimian.Osquery` and the trust information of the two recipes and the three
processors. **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.Osquery-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.Osquery`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected (the shape from the rehearsal of Win-7Zip, NOT seen for this recipe),
also without `-v`, when the current version is not yet in the repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name      Version    Catalogs    Result
    osquery   5.23.1  Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: osquery 5.23.1 is in the repository already. Nothing was written.`
instead. That is correct.

If the run stops before this, with an error from `GitHubReleasesInfoProvider`
(no matching asset) or from `GitHubAssetDigest` (no digest), the status line at the
top applies: nothing was written; read the real release; correct the recipe.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Osquery.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.cimian.recipe

   Expected: `Published osquery 5.23.1.` and a table with the result
   `published`. The repository now has the installer under `pkgs/` and the
   pkginfo under `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions osquery` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Not rehearsed. The package tool prints "nothing to run" when its
   catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.cimian.recipe

   It prints `Nothing new: osquery 5.23.1 is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Osquery.cimian.recipe

## g. A share that is not mounted

The rehearsal of Win-7Zip used an empty folder as the repository. The recipe failed
(exit code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written; the folder stayed empty. Mount the share, then run again.
Here the same line also appears when the template `osquery` was never made (step a, 3).

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `Osquery` and `PCMAN_TEMPLATE` is `osquery`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares, that the asset pattern takes the one MSI of each
release that was read and no other file, that this README has no `make-override` without `--override-dir`
and runs no recipe by its identifier, that its status line says what was NOT done,
and that nothing site-specific is in the folder.
