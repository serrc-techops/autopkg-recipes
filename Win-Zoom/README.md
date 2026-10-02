# Win-Zoom

A Windows recipe pair: Zoom Workplace, the 64-bit `.msi`.

**Status. The download is NOT verified: Zoom publishes no hash for the file, and a check of the signature is not built. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true. Do not set it before the signature check exists. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template zoom` (no `--version` for an MSI). On 2026-10-01 it ran with the real AutoPkg 2.9.0 in a scratch folder up to "Nothing new", against a template of the same version (the download, the dry-run default and the importer ran). In that rehearsal the scratch overrides folder was one of AutoPkg's override folders; on the build machine the Windows overrides folder is not, so every override command here carries `--override-dir`: see the paragraph below. A real run of this recipe has NOT been run by anyone, not against a share and not on a PC. `pcman catalogs` was NOT rehearsed either.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `ZoomWorkplaceX64-Win.download.recipe` | `com.github.serrc-techops.download.ZoomWorkplaceX64-Win` | Downloads the Zoom Workplace installer that Zoom serves at a fixed address (the 64-bit MSI). The address has a query string, so the recipe sets a file name that ends in `.msi`. It has no hard check |
| `Zoom.cimian.recipe` | `com.github.serrc-techops.cimian.Zoom` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

The shared Penn State recipe `Zoom64-Win.download` is not the parent: it would bring a version step that this flow does not need, and a parent outside this repository changes without us.

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processor is in `../Win-SharedProcessors/` (see its
README).

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What protects, and what does not

Nothing proves that the downloaded file is what Zoom published: there is no vendor
hash, and a signature check is not built. The shared importer knows this: no step of
the recipe sets `checksum_verified` with the hash of the file, so a real run is refused
before the package tool starts. Two checks of the package tool remain. They do not
replace a verification.

- **The same product.** The package tool refuses an MSI whose upgrade code
  differs from the template's. So another product cannot be published under the
  name of this template.
- **The label.** The recipe gives no version label. For an MSI the package tool
  takes the MSI's own ProductVersion and refuses a label that is not the MSI's
  own version.

An MSI of the right product with other content (a changed file of the vendor, or a
changed download on the way) would pass both checks.

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
   it replaces. The command, with a real MSI:

       pcman import <path of the MSI> --name zoom \
           --directory <the folder of the item> --architectures x64 --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. Add
   `--display-name`, `--category`, `--developer`, `--description` and the icon as
   the package tool's README describes. A person changes the template later;
   nothing else does. **If the template is made from the installer that is
   current at the vendor, the first run says "Nothing new" (see step c). To see a
   dry run that would publish, make the template from an older version.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i ZoomWorkplaceX64
    autopkg list-recipes | grep -i Zoom.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Zoom.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Zoom.cimian`, not a path. Expected: it
writes `<the Windows overrides folder>/Zoom.cimian.recipe` with the identifier
`local.cimian.Zoom` and the trust information of the two recipes and of the
one processor that is not part of AutoPkg itself (`PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.ZoomWorkplaceX64-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Zoom.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.Zoom`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current version is not yet in the
repository (the lines of the 7-Zip rehearsal, with this program's name; the
version is the MSI's own):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name   Version  Catalogs    Result
    zoom   7.2.48556  Production  dry run, nothing written, NOT verified

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line is
`Nothing new: ... is in the repository already. Nothing was written.` instead.
That is correct.

## d. Switch a real run on (NOT YET: see the status line)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file. Nothing was published. Publish by hand after
    checking the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template zoom

Do not add `--version` for an MSI: the package tool takes the MSI's own version. Then
`pcman catalogs` (step e.3).

**Only after the signature check exists, or when a person has decided to accept an
unverified download:** the override allows it. Both lines are needed.

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Zoom.cimian.recipe
    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_allow_unverified bool true' \
        <the Windows overrides folder>/Zoom.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Zoom.cimian.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip). Do not use `-k`
instead: on the command line it applies to every recipe of that run. A run then prints
`WARNING: published WITHOUT a verified download ...` at any verbosity, and the report's
row says `published, NOT verified`.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Zoom.cimian.recipe

   Only after both lines of step d. Expected: `Published zoom ...`, the warning
   `published WITHOUT a verified download`, and the table

       The following versions were published by the package tool:
       Name   Version  Catalogs    Result
       zoom   7.2.48556  Production  published, NOT verified

   The repository then has the MSI under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions zoom` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Zoom.cimian.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Zoom.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Zoom.cimian.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- Zoom's address redirects to a versioned address on another host. The address says
  `7.2.1.48556`; the MSI's own ProductVersion is `7.2.48556`. The package tool takes
  the MSI's own version (from the installer facts read on 2026-10-01, nothing run).
- The MSI has `ALLUSERS=2` and no `MSIINSTALLPERUSER`. Which install the PC then
  gets is Microsoft's rule, not tested.
- The file is about 220 MB. The copy to the share is the slowest step. The
  processor waits 30 minutes by default (`pcman_timeout`).
- The recipe's `NAME` is `Zoom` and `PCMAN_TEMPLATE` is `zoom`. Change
  the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) skips the download. The file is not
  checked at all.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that the Description of both recipes
and the top of this README say that the download is not verified and that a real run is
refused, that this README states no hash, that every
argument is an input that the shared processor declares, that no recipe sets
`pcman_version` for an MSI, that this README has no `make-override` without
`--override-dir` and runs no recipe by its identifier, and that nothing
site-specific is in the folder.
