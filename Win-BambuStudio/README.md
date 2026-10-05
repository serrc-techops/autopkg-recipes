# Win-BambuStudio

A Windows recipe pair: Bambu Studio, the public Windows `.exe` installer, with the version label read from the file itself.

**Status. NOT rehearsed, and the facts of the source NOT fetched by the writer: the network was closed, so nothing here was run with AutoPkg and nothing was read from GitHub or from the vendor. Every fact below is from the writer's knowledge or from the pattern of another recipe of this repository, and the first run on the build Mac is the check of each one: (1) the repository is `bambulab/BambuStudio` and it publishes its Windows installer as a release asset; (2) the asset name has the shape `Bambu_Studio_win_public-v<version>-<number>.exe`, where the number after the version is a build date (for the newest tag it would be `Bambu_Studio_win_public-v02.08.04.61-<build date>`, with the build date and the file name's end NOT known), which is what `SEARCH_PATTERN` matches; (3) the release tag is `v` followed by the version, with leading zeros (four parts of two digits), so AutoPkg 2.9.0 (which strips the leading `v`, read in its source) makes `version` from it; the download recipe then overwrites `version` with the `ProductVersion` that `WindowsExeVersion` reads from the installer, so the tag is no longer the label; (4) GitHub records a digest for the asset, so that `GitHubAssetDigest` finds one; (5) the installer is an NSIS installer that takes `/S` as its silent switch (from the writer's knowledge, not read in the installer). Read through git on 2026-10-02 (tags only; the release assets and their digests were NOT fetched): the newest tags of `bambulab/BambuStudio` are `v02.08.03.65`, `v02.08.03.66`, `v02.08.04.57` and `v02.08.04.61`. The shape of the installer's own ProductVersion is NOT known: if it keeps the tag's leading zeros, the label has them too, and whether the package tool accepts a version part with a leading zero, and whether the Cimian client orders that label as the EXE's own version, is NOT established. The first dry run shows the label and the package tool's answer, and the label must then equal the EXE's own ProductVersion as a person reads it on a PC. When any of this fails, stop. Nothing was written. Read the real release page or the real release, and correct the recipe. Never change the trust information first. A real run has NOT been run by anyone, not against a share and not on a PC. `pcman catalogs` was NOT rehearsed either.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `BambuStudio-Win.download.recipe` | `com.github.serrc-techops.download.BambuStudio-Win` | Takes the newest non-pre-release of `bambulab/BambuStudio` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match. Last, reads the `ProductVersion` from the `.exe` itself and sets `version` to it |
| `BambuStudio.cimian.recipe` | `com.github.serrc-techops.cimian.BambuStudio` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new. It passes the version label that the download recipe read from the `.exe` (`%version%`) |
| `BambuStudio.pcman.recipe` | `com.github.serrc-techops.pcman.BambuStudio` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new. It passes the version label that the download recipe read from the `.exe` (`%version%`) |

**Three recipes.** The download recipe is the parent of both of the others. `BambuStudio.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `BambuStudio.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

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

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `BambuStudio.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

3. **The version label** needs no program: the download recipe's step `WindowsExeVersion` reads it from the `.exe` itself, and this recipe passes it on as `%version%`.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `bambustudio`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the first step of the package tool's way below marks what is only the writer's knowledge or was not read), so they are left for a person who has read them in the vendor's documentation and tried them on a test PC. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i BambuStudio-Win
    autopkg list-recipes | grep -i BambuStudio.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> BambuStudio.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `BambuStudio.cimian`, not a path. It writes `<the Windows overrides folder>/BambuStudio.cimian.recipe` with the identifier `local.cimian.BambuStudio` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.BambuStudio`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.BambuStudio`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/BambuStudio.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `BambuStudio.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `BambuStudio.pcman` where this README used to say `BambuStudio.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `BambuStudio.cimian.recipe` (when that recipe ran the package tool) must be made again from `BambuStudio.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `BambuStudio.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
    autopkg list-recipes | grep -i BambuStudio.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> BambuStudio.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `BambuStudio.pcman`, not a path. It writes
`<the Windows overrides folder>/BambuStudio.pcman.recipe` with the identifier
`local.pcman.BambuStudio` and the trust information of the two recipes and the four
processors that are not part of AutoPkg itself (`GitHubAssetDigest`, `ChecksumVerifier`,
`WindowsExeVersion`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.BambuStudio`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the
lines of the label step are printed (`-v` prints what each processor says about its own
work; `-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the
repository among them, and such a log would have to be kept private):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.BambuStudio`) runs the recipe itself, not the
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
        <the Windows overrides folder>/BambuStudio.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.pcman.recipe

The trust check should still report OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.pcman.recipe

   Expected: `Published bambustudio <label>.` and a table of the published version
   with the result `published`. The repository then has the installer and the pkginfo of
   the new version. The item file of the template is not changed.

2. `pcman versions bambustudio` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Not rehearsed. The package tool prints "nothing to run" when its
   catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.pcman.recipe

   It should print `Nothing new: bambustudio <label> is in the repository already.
   Nothing was written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/BambuStudio.pcman.recipe

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

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
