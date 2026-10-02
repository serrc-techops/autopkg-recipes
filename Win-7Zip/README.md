# Win-7Zip

The first Windows recipe pair: 7-Zip, the 64-bit `.exe`.

**Status.** Rehearsed on 2026-10-01 with AutoPkg 2.9.0 and the real installer in
a scratch repository (a folder with `pkgs/` and `pkgsinfo/`): a dry run, a publish,
"Nothing new", a trust failure (a changed processor) and a missing repository. NOT
yet run against the real share. `pcman catalogs` was NOT rehearsed. The lines quoted
below are those that the rehearsal printed; spacing of the tables may differ. (In the
rehearsal the scratch overrides folder was one of AutoPkg's override folders. On the
build machine the Windows overrides folder is not, so every override command here
carries `--override-dir`: see the next paragraph.)

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `7Zip-Win.download.recipe` | `com.github.serrc-techops.download.7Zip-Win` | Takes the newest non-pre-release of `ip7z/7zip` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match |
| `7Zip.cimian.recipe` | `com.github.serrc-techops.cimian.7Zip` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

The shared 7zip-Win64 download recipe is not the parent: its pattern and file
name are for the `.msi`. Neither recipe stops on an unchanged download, so an
import that failed is tried again at the next run. The processors are in
`../Win-SharedProcessors/` (see its README).

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
   a path. The rehearsal printed: `make-override doesn't work with absolute recipe
   paths`.

2. **The settings of the processor, as AutoPkg preferences.** One line each:

       defaults write com.github.autopkg pcman_root -string "<the package tool's folder>"
       defaults write com.github.autopkg pcman_python -string "<the package tool's Python>"

   `pcman_python` is only needed when it is not `<the package tool's folder>/.venv/bin/python3`.
   Write the values as strings. The repository is not a setting here: the package
   tool's own configuration says where it is. The repository must be reachable
   (the share mounted).

3. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. The command of the rehearsal, with a real
   installer:

       pcman import <path of 7z2603-x64.exe> --name 7zip --version 26.03 \
           --directory util --install-arguments /S \
           --install-path 'C:\Program Files\7-Zip\7z.exe' --architectures x64 \
           --no-prompt --build

   Add `--display-name`, `--category`, `--developer` and `--description` as the
   package tool's README describes. A person changes the template later; nothing
   else does. **If the template is made from the installer that is current on
   GitHub, the first run says "Nothing new" (see step c). To see a dry run that
   would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i 7Zip-Win
    autopkg list-recipes | grep -i 7Zip.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> 7Zip.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `7Zip.cimian`, not a path. It writes
`<the Windows overrides folder>/7Zip.cimian.recipe` with the identifier
`local.cimian.7Zip` and the trust information of the two recipes and the three
processors. **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.7Zip-Win`.** Another value
means that AutoPkg found another recipe of the same name. (No collision is known: the shared recipe `7zip-Win64.download` has another name.)

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.7Zip`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current version is not yet in the
repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name   Version  Catalogs    Result
    7zip   26.03    Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: 7zip 26.03 is in the repository already. Nothing was written.`
instead. That is correct.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/7Zip.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.cimian.recipe

   Expected: `Published 7zip 26.03.` and the table

       The following versions were published by the package tool:
       Name   Version  Catalogs    Result
       7zip   26.03    Production  published

   The repository now has `pkgs/util/7zip-26.03.exe` and
   `pkgsinfo/util/7zip-26.03.yaml`. The item file of the template is not changed.

2. `pcman versions 7zip` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Not rehearsed. The package tool prints "nothing to run" when its
   catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.cimian.recipe

   It prints `Nothing new: 7zip 26.03 is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/7Zip.cimian.recipe

## g. A share that is not mounted

The rehearsal used an empty folder as the repository. The recipe failed (exit
code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written; the folder stayed empty. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `7Zip` and `PCMAN_TEMPLATE` is `7zip`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares, that this README has no `make-override`
without `--override-dir` and runs no recipe by its identifier, and that nothing
site-specific is in the folder.
