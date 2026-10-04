# Win-BambuStudio

A Windows recipe pair: Bambu Studio, the public Windows `.exe` installer, with the version label read from the file itself.

**Status. NOT rehearsed, and the facts of the source NOT fetched by the writer: the network was closed, so nothing here was run with AutoPkg and nothing was read from GitHub or from the vendor. Every fact below is from the writer's knowledge or from the pattern of another recipe of this repository, and the first run on the build Mac is the check of each one: (1) the repository is `bambulab/BambuStudio` and it publishes its Windows installer as a release asset; (2) the asset name has the shape `Bambu_Studio_win_public-v<version>-<number>.exe`, where the number after the version is a build date (for the newest tag it would be `Bambu_Studio_win_public-v02.08.04.61-<build date>`, with the build date and the file name's end NOT known), which is what `SEARCH_PATTERN` matches; (3) the release tag is `v` followed by the version, with leading zeros (four parts of two digits), so AutoPkg 2.9.0 (which strips the leading `v`, read in its source) makes `version` from it; the download recipe then overwrites `version` with the `ProductVersion` that `WindowsExeVersion` reads from the installer, so the tag is no longer the label; (4) GitHub records a digest for the asset, so that `GitHubAssetDigest` finds one; (5) the installer is an NSIS installer that takes `/S` as its silent switch (from the writer's knowledge, not read in the installer). Read through git on 2026-10-02 (tags only; the release assets and their digests were NOT fetched): the newest tags of `bambulab/BambuStudio` are `v02.08.03.65`, `v02.08.03.66`, `v02.08.04.57` and `v02.08.04.61`. The shape of the installer's own ProductVersion is NOT known: if it keeps the tag's leading zeros, the label has them too, and whether the package tool accepts a version part with a leading zero, and whether the Cimian client orders that label as the EXE's own version, is NOT established. The first dry run shows the label and the package tool's answer, and the label must then equal the EXE's own ProductVersion as a person reads it on a PC. When any of this fails, stop. Nothing was written. Read the real release page or the real release, and correct the recipe. Never change the trust information first. A real run has NOT been run by anyone, not against a share and not on a PC. `pcman catalogs` was NOT rehearsed either.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `BambuStudio-Win.download.recipe` | `com.github.serrc-techops.download.BambuStudio-Win` | Takes the newest non-pre-release of `bambulab/BambuStudio` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match. Last, reads the `ProductVersion` from the `.exe` itself and sets `version` to it |
| `BambuStudio.cimian.recipe` | `com.github.serrc-techops.cimian.BambuStudio` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new. It passes the version label that the download recipe read from the `.exe` (`%version%`) |

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (see its
README).

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/BambuStudio.cimian.recipe

(For an override that was made before this key existed, use
`Add :Input:include_prereleases bool true` instead.) Keep it a boolean: AutoPkg only
tests whether the value is empty, so the text `false` would count as true. The recipe's
step does not set it, because AutoPkg applies the arguments of a step after the
override's `Input`, and they would beat it.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## The version label

The installer is an `.exe`, so the recipe passes the label to the package tool
(`pcman_version` is `%version%`): the tool never reads a version from an EXE. The label
is the file's own. AutoPkg makes `version` from the release tag and removes the leading
`v` (the tag has four parts of two digits each, so `version` keeps their leading zeros),
and the last step of the download recipe, `WindowsExeVersion` (shared, see its README),
reads the `ProductVersion` of the downloaded installer and overwrites `version` with it
(when that string is numbers and dots only; otherwise it takes the four numbers of the
fixed file information; a label of zeros stops the run). The tag is not used as the
label: it belongs to the release and not to the file, and a release whose tag and file
disagree would be published under the tag.

The shape of the installer's own ProductVersion is NOT known. If it keeps the tag's
leading zeros, two questions are open, and nobody has answered them:

- Does the package tool accept a part with a leading zero? The first dry run shows its
  answer. A refusal is an error of the tool, shown by the processor; nothing is written.
- Does the Cimian client order that label as the EXE's own version? The label must
  equal the EXE's own ProductVersion as a person reads it on a PC (the file's
  properties, after a hand install). If it does not, stop and tell the owner: a label
  that the client orders wrongly would hide a newer version or offer an older one.

The first dry run (with `-v`) prints two lines from the label step: `... ProductVersion
'...', product version numbers ..., file version '...', file version numbers ...` and
`version is ..., taken from ...`. **Read them first**, and compare the label with the
file's properties on a PC.

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
   installer are in the repository. The command, with a real installer that a
   person has downloaded and checked:

       pcman import <path of the installer> --name bambustudio --version <label> \
           --display-name "Bambu Studio" --category <the category> \
           --developer "Bambu Lab" --description "<the description>" \
           --directory <the folder of the item> \
           --install-arguments /S \
           --install-path '<the path of the installed program, read on a PC after a hand install>' \
           --architectures x64 --no-prompt --build

   `--version <label>` is for an EXE only, and the label is the one that step c will
   show (see "The version label"). `/S` is the silent switch of an NSIS installer: it
   is from the writer's knowledge, not read in the installer. Read the installer's own
   behaviour on a test PC before the first import, and use what you find. The install
   path is a fact of the installer too: it is not given here because the writer did not
   read it. Add the icon as the package tool's README describes. A person changes the
   template later; nothing else does. **If the template is made from the installer that
   is current on GitHub, the first run says "Nothing new" (see step c). To see a dry run
   that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i BambuStudio-Win
    autopkg list-recipes | grep -i BambuStudio.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> BambuStudio.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `BambuStudio.cimian`, not a path. It writes
`<the Windows overrides folder>/BambuStudio.cimian.recipe` with the identifier
`local.cimian.BambuStudio` and the trust information of the two recipes and the four
processors that are not part of AutoPkg itself (`GitHubAssetDigest`, `ChecksumVerifier`,
`WindowsExeVersion`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.BambuStudio-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the
lines of the label step are printed (`-v` prints what each processor says about its own
work; `-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the
repository among them, and such a log would have to be kept private):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.BambuStudio`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

This is the first check of every fact in the status line. The run may stop before the
dry run, and that is the check working:

- **No asset matches** (the lines of the provider name the pattern and the release):
  the real asset name is not the one the writer knows. Read the release's real asset
  list and correct `SEARCH_PATTERN`.
- **`GitHubAssetDigest` stops with its error** (the record has no digest): GitHub
  recorded none for this asset. Nothing was written. The program is a hand import
  until a release with a digest exists.
- **`WindowsExeVersion` stops** (the file has no version resource, is not a PE file, or
  says a version of zeros): the file is not what the recipe expects. Nothing was written.
  Read the file's properties on a Windows PC, and import by hand with a label that a
  person has read.
- **The package tool refuses the label**: see "The version label".

Expected when everything holds and the current version is not yet in the repository
(the lines are what the shared processor prints; the real run has not been seen):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name          Version  Catalogs    Result
    bambustudio   <label>  Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: bambustudio <label> is in the repository already. Nothing was written.`
instead. That is correct. **Read the label in that line and compare it with the EXE's own
ProductVersion** (see "The version label").

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/BambuStudio.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.cimian.recipe

The trust check should still report OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.cimian.recipe

   Expected: `Published bambustudio <label>.` and a table of the published version
   with the result `published`. The repository then has the installer and the pkginfo of
   the new version. The item file of the template is not changed.

2. `pcman versions bambustudio` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Not rehearsed. The package tool prints "nothing to run" when its
   catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.cimian.recipe

   It should print `Nothing new: bambustudio <label> is in the repository already.
   Nothing was written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.cimian.recipe

## g. A share that is not mounted

The recipe fails (exit code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing is written. Mount the share, then run again. (The shared processors'
tests show this failure; it was NOT seen on this program.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `BambuStudio` and `PCMAN_TEMPLATE` is `bambustudio`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.
- The recipe takes the newest non-pre-release only. A beta that the project marks as a
  pre-release is not downloaded, unless the override sets `include_prereleases` (see
  "Pre-releases" at the top).

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares, that this README opens with the status line
that says what was not done, has no `make-override` without `--override-dir` and
runs no recipe by its identifier, and that nothing site-specific is in the folder.
