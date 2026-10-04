# Win-Greenshot

A Windows recipe pair: Greenshot, the installer `.exe`, with the version label read from the file itself.

**Status. NOT rehearsed with AutoPkg: nothing in this folder has run with AutoPkg, the package tool, a share or a PC. Some facts of the source were read on 2026-10-04 from GitHub's public release list of `greenshot/greenshot` (`https://api.github.com/repos/greenshot/greenshot/releases`, the newest twelve releases; read only, no file was downloaded). READ: (1) the project publishes its releases there, and its tags begin with `v`; the newest release that is not flagged as a pre-release is `v1.3.315` (published 2026-03-20, titled "Greenshot 1.3.315"), then `v1.3.312` and `v1.3.311` (both published 2026-01-07); (2) the other nine of the twelve are flagged as pre-releases and titled "(continuous build)": every `v1.4.` build (the newest, `v1.4.289-g7bee683e93`, was published on 2026-10-04) and the 1.3 builds whose files are named `-UNSTABLE-UNSIGNED`; (3) the files of `v1.3.315` are `Greenshot-INSTALLER-1.3.315-RELEASE.exe` (3967064 bytes) and `Greenshot-PORTABLE-1.3.315-RELEASE.zip` (3722113 bytes), and `v1.3.312` and `v1.3.311` have the same two kinds of name; the installers of the pre-releases are named like `Greenshot-INSTALLER-1.4.289-g7bee683e93-UNSTABLE-UNSIGNED.exe`, and the 1.4 builds have a second installer, `Greenshot-Light-INSTALLER-...`; (4) the pattern `Greenshot-INSTALLER-[0-9.]+-RELEASE\.exe$` matches the installer of each of the three releases that are not flagged and no other file of the twelve releases; (5) GitHub records a SHA-256 digest for every file of the twelve releases, the `.exe` files included. So, by these names, AutoPkg 2.9.0 (which takes the first release, in GitHub's order, that is not flagged and has a file whose name the pattern matches from its start: `GitHubReleasesInfoProvider.py`, `select_asset`, `re.match`) is expected to take `Greenshot-INSTALLER-1.3.315-RELEASE.exe` of `v1.3.315`, and `GitHubAssetDigest` is expected to find its digest. NOT established: that the installer has a version resource, and what its `ProductVersion` text is (it becomes the label: the tag gives `1.3.315`, but the step `WindowsExeVersion` overwrites `version` with the one in the file, see "The label"); that the installer is built with Inno Setup, so that the silent switches are `/VERYSILENT /NORESTART` (from the writer's knowledge, the installer was not opened); its architecture and its install path; the template item; that the next release keeps these names; `pcman catalogs`; any run with AutoPkg. The first run on the build Mac is the check of each of them. When a run fails (no asset matches, the asset has no digest, the digest does not match, the executable has no version resource or says zeros, the package tool refuses the label): stop; nothing was written. Read the real release page and the real asset list of the project, and correct the recipe or the template, never the trust information first. Where a line below says "expected", it is what the recipes and the other folders lead to, not something that was printed. Every override command here carries `--override-dir`: see the paragraph below.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Greenshot-Win.download.recipe` | `com.github.serrc-techops.download.Greenshot-Win` | Takes the newest non-pre-release of `greenshot/greenshot` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match. Last, reads the `ProductVersion` from the `.exe` itself and sets `version` to it |
| `Greenshot.cimian.recipe` | `com.github.serrc-techops.cimian.Greenshot` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new. It passes the version label that the download recipe read from the `.exe` (`%version%`), because the installer is an `.exe` |

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (see its
README).

## The label

The release's tag is not a label. AutoPkg's `GitHubReleasesInfoProvider` makes `version`
from the tag by removing a leading `v` or `.`; the tag of the release that the recipe is
expected to take is `v1.3.315`, which gives `1.3.315`, and the tag of a pre-release such as
`v1.4.289-g7bee683e93` gives `1.4.289-g7bee683e93`, with the commit's short name in it,
which is not a label. The last step of the download recipe, `WindowsExeVersion`, reads the
`ProductVersion` of the downloaded file and overwrites `version` with it (when that
string is numbers and dots only; otherwise it takes the four numbers of the fixed file
information; see its section in the shared README). The cimian recipe passes that
`version` as `pcman_version`.

The first dry run prints two lines from that step: `ProductVersion '...', product
version numbers ..., file version '...', file version numbers ...` and `version is ...,
taken from ...`. A person reads them and compares: the label must be the version that
the file's properties show, and the first import (step a) must be made with the same
label. If the `ProductVersion` is not numbers and dots only, the label has four numbers
and may not look like what the project prints; the package tool's plan shows what it
makes of it. Whether the label orders correctly against the template's version is NOT
established, and so is the shape of Greenshot's `ProductVersion`.

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/Greenshot.cimian.recipe

(For an override that was made before this key existed, use
`Add :Input:include_prereleases bool true` instead.) Keep it a boolean: AutoPkg only
tests whether the value is empty, so the text `false` would count as true. The recipe's
step does not set it, because AutoPkg applies the arguments of a step after the
override's `Input`, and they would beat it.

**The 1.4 line.** In the twelve releases read, the 1.4 builds are published only as pre-releases, and the names of their
installers (`Greenshot-INSTALLER-1.4.289-g7bee683e93-UNSTABLE-UNSIGNED.exe`) do not match the
pattern. With `include_prereleases` set to true and nothing else changed, the recipe still
takes `Greenshot-INSTALLER-1.3.315-RELEASE.exe` of `v1.3.315`, because that is the first
release with a matching file. Taking a 1.4 build would need two changes in the override's
`Input`, and the recipe makes neither: `include_prereleases` true, and `SEARCH_PATTERN`
changed to a pattern that matches the 1.4 installer and not the `Greenshot-Light-INSTALLER-...`
file beside it, for example `Greenshot-INSTALLER-[0-9.]+-g[0-9a-f]+-UNSTABLE-UNSIGNED\.exe$`.
Whether a continuous build with `UNSTABLE-UNSIGNED` in its name goes to the PCs is the
owner's decision.

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
   (the share mounted).

3. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. The command, with the real installer (NOT run;
   the facts of the installer are marked):

       pcman import <path of the installer, a file that matches the pattern> --name greenshot \
           --version <the installer's own ProductVersion, as the file's properties or the first dry run show it> \
           --directory <the repository folder for this item> \
           --display-name "Greenshot" --category <the category> \
           --developer "Greenshot" --description "<one sentence>" \
           --install-arguments '/VERYSILENT /NORESTART' \
           --install-path '<the path of the installed Greenshot.exe, read after a test install>' \
           --architectures x64 --no-prompt --build

   The silent switches `/VERYSILENT /NORESTART` are an Inno Setup installer's
   (from the writer's knowledge, not read in the installer): confirm that the
   installer is Inno Setup, and that the switches install without a window, on a
   test PC first. `--architectures x64` is an expectation, not a fact: nobody opened the
   installer, so its architecture is NOT established (see the status line); read it in the
   installer before the import. The install path is not given here: read it on that PC. The label
   after `--version` is for an `.exe`: it must be the installer's own version, as a
   person reads it in its properties, and the same that the first dry run prints
   (see "The label"). Give the flags `--category`,
   `--developer` and `--description` as the package tool's README describes. A person
   changes the template later; nothing else does. **If the template is made from the
   installer that is current on GitHub, the first run says "Nothing new" (see step c).
   To see a dry run that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Greenshot-Win
    autopkg list-recipes | grep -i Greenshot.cimian

Each name must be listed once, from this repository. (Not run, so the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Greenshot.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Greenshot.cimian`, not a path. It writes
`<the Windows overrides folder>/Greenshot.cimian.recipe` with the identifier
`local.cimian.Greenshot` and the trust information of the two recipes and the four
processors that are not part of AutoPkg itself (`GitHubAssetDigest`, `ChecksumVerifier`,
`WindowsExeVersion`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.Greenshot-Win`.** Another value
means that AutoPkg found another recipe of the same name. (Whether another recipe of this name exists was NOT checked: the writer had no AutoPkg.)

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the
lines of the label step are printed (`-v` prints what each processor says about its own
work; `-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the
repository among them, and such a log would have to be kept private):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.Greenshot`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected (from the rehearsal of the 7-Zip folder, not printed for this program), also without `-v`, when the current version is not yet in the
repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name       Version      Catalogs    Result
    greenshot  <the label>  Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: greenshot <the label> is in the repository already. Nothing was written.`
instead. That is correct.

Before the table the run prints the lines of the step that reads the label: `... ProductVersion
'...' ...` and `version is ..., taken from ...` (see "The label"). **Read them first.** Read
the provider's line `Selected asset '...' from release '...'` too (`GitHubReleasesInfoProvider.py`,
`select_asset`): by the release list of 2026-10-04 it names `Greenshot-INSTALLER-1.3.315-RELEASE.exe`
and `Greenshot 1.3.315`, and a newer release that is not flagged would show its own names. If it
names a file with `UNSTABLE`, `Light` or `PORTABLE` in its name, stop and tell the owner: the pattern
or the override is not what this README says. A `ProductVersion` with text in it
means that the label is the four numbers: compare it with the file's properties.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Greenshot.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.cimian.recipe

   Expected (from the 7-Zip rehearsal): `Published greenshot <the label>.` and the table

       The following versions were published by the package tool:
       Name       Version      Catalogs    Result
       greenshot  <the label>  Production  published

   The repository now has `pkgs/<the item folder>/greenshot-<the label>.exe` and
   `pkgsinfo/<the item folder>/greenshot-<the label>.yaml`. The item file of the template is not changed.

2. `pcman versions greenshot` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Not rehearsed, for no program. The package tool prints "nothing to run" when its
   catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.cimian.recipe

   It prints `Nothing new: greenshot <the label> is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Greenshot.cimian.recipe

## g. A share that is not mounted

When the repository cannot be read, the 7-Zip rehearsal (an empty folder as the
repository) failed with exit code 70 and the tool's line (NOT seen for this program):

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written; the folder stayed empty. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `Greenshot` and `PCMAN_TEMPLATE` is `greenshot`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares (`WindowsExeVersion` included, and that it is the
last step of the download recipe, after the checksum), that the pattern matches the
installer and not the other files of a release, that this README has no `make-override`
without `--override-dir` and runs no recipe by its identifier, and that nothing
site-specific is in the folder.
