# Win-OpenSSH

A Windows recipe pair: OpenSSH for Windows, the 64-bit `.msi` of the `PowerShell/Win32-OpenSSH` project.

**Status. NOT rehearsed, and the facts of the source NOT fetched by the writer: the network was closed when these recipes were written, so nothing here was run, and nothing was read from GitHub. Every one of these facts is from the writer's knowledge of the project, or from the 7-Zip recipe in this repository, and none is checked: the repository `PowerShell/Win32-OpenSSH`; the asset names (`OpenSSH-Win64-v<version>.msi` for the 64-bit MSI, beside `OpenSSH-Win32-...`, `OpenSSH-ARM64-...` and zip files), and so the pattern `OpenSSH-Win64-v[0-9.]+\.msi$`; that the project marks its betas as pre-releases, so that `include_prereleases` false finds a stable release; that the newest release that is not a pre-release has the MSI attached; that GitHub records a SHA-256 `digest` for that asset (from the 7-Zip recipe's use of GitHub's API; an asset uploaded before GitHub began to record digests has none); and the version label that the package tool takes from the MSI. What was read, on 2026-10-02 through git and only the tags: the newest tags of `PowerShell/Win32-OpenSSH` are `v9.8.0.0p1-Preview`, `v9.8.1.0p1-Preview`, `v9.8.2.0p2-Preview` and `v9.8.3.0p2-Preview`, and every tag of recent years carries `-Beta` or `-Preview`, so the version that AutoPkg derives from the tag would be `9.8.3.0p2-Preview` (the MSI recipe does not use it). What was NOT read: the release assets, their digests, and whether the project flags these releases as pre-releases on GitHub; the asset name `OpenSSH-Win64-v9.8.3.0.msi` is still from knowledge. The first dry run on the build Mac is the check of every one of them. When it fails, stop. Nothing was written. Read the real releases page and the real asset list, correct the recipe, and only then look at the trust information (never the trust information first). Where a line below says "expected", it is what the code and the other recipes lead to, not something that was printed.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `OpenSSHWin64-Win.download.recipe` | `com.github.serrc-techops.download.OpenSSHWin64-Win` | Takes the newest non-pre-release of `PowerShell/Win32-OpenSSH` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match |
| `OpenSSHWin64.cimian.recipe` | `com.github.serrc-techops.cimian.OpenSSHWin64` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (see its
README). The model of this folder is `../Win-7Zip/`, with an MSI instead of an EXE.

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/OpenSSHWin64.cimian.recipe

(For an override that was made before this key existed, use
`Add :Input:include_prereleases bool true` instead.) Keep it a boolean: AutoPkg only
tests whether the value is empty, so the text `false` would count as true. The recipe's
step does not set it, because AutoPkg applies the arguments of a step after the
override's `Input`, and they would beat it.

The project's tags all carry `-Beta` or `-Preview`. If GitHub flags its releases as
pre-releases, the recipe takes an older release that is not flagged, or, when there is
none, stops with `No releases found for repo ... on page ...`; this switch is the only
way to take the flagged ones, and whether a Beta or Preview build goes to the PCs is the
owner's decision. If GitHub does not flag them, nothing needs to be switched.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What the checks prove

- **The hash.** The file and the hash both come from GitHub (the release
  asset and the API's record of it). The check shows that the file is what GitHub
  holds. It does not help if the project's own release is changed.
- **When there is no digest.** An asset that GitHub holds without a recorded
  digest stops the run with the processor's error. Nothing is written. The program
  is then a hand import until a release with a digest exists.
- **The same product.** The package tool refuses an MSI whose upgrade code
  differs from the template's. Whether two releases of this MSI have the same upgrade
  code is NOT established; the first dry run shows the tool's answer.
- **The label.** The recipe gives no version label. For an MSI the package tool
  takes the MSI's own ProductVersion. The project's tag has letters in it (`v9.8.3.0p2-Preview`), so the
  tag is not the label, and the recipe does not use it.

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
   installer are in the repository. The template is the item `OpenSSH-Win64`. **If
   the repository has it already, do not run the command below; it is here for a
   repository that has no such item.** The command, with a real MSI of the project:

       pcman import <path of OpenSSH-Win64-v9.8.3.0.msi> --name OpenSSH-Win64 \
           --directory <the folder of the item> --architectures x64 \
           --display-name <the display name> --category <the category> \
           --developer <the developer> --description <the description> \
           --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. There is
   no install argument either: the package tool knows the arguments of an MSI
   (a silent install, `/qn`; from the writer's knowledge, not read in the installer).
   Take the display name, the category, the developer and the description from the
   existing item, so that the two do not differ. A person changes the template
   later; nothing else does. **If the template was made from the release that is
   current on GitHub, the first run says "Nothing new" (see step c). To see a dry
   run that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i OpenSSHWin64-Win
    autopkg list-recipes | grep -i OpenSSHWin64.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> OpenSSHWin64.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `OpenSSHWin64.cimian`, not a path. Expected:
it writes `<the Windows overrides folder>/OpenSSHWin64.cimian.recipe` with the
identifier `local.cimian.OpenSSHWin64` and the trust information of the two
recipes and the processors that are not part of AutoPkg itself
(`GitHubAssetDigest`, `ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.OpenSSHWin64-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OpenSSHWin64.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.OpenSSHWin64`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**This run is the check of the facts in the status paragraph.** The downloader must
find an asset, and the digest step must find a digest. If the run stops before the
table below, stop too: read the real release and the real asset list, and correct
the recipe (the pattern, or the repository), not the trust information.

Expected, also without `-v`, when the current release is not yet in the
repository (the lines of the 7-Zip rehearsal, with this program's name; the
version is the MSI's own):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name           Version                 Catalogs    Result
    OpenSSH-Win64  <the MSI's own version>  Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
release is in the repository already (the template was made from it), the line
is `Nothing new: OpenSSH-Win64 ... is in the repository already. Nothing was
written.` instead. That is correct. If the tool refuses the MSI as another
product than the template (the upgrade codes differ), stop and tell the owner.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/OpenSSHWin64.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OpenSSHWin64.cimian.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip). Do not use
`-k pcman_dry_run=false` instead: on the command line it applies to every recipe
of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OpenSSHWin64.cimian.recipe

   Expected: `Published OpenSSH-Win64 ...` with the MSI's own version, and the table

       The following versions were published by the package tool:
       Name           Version                 Catalogs    Result
       OpenSSH-Win64  <the MSI's own version>  Production  published

   The repository then has the MSI under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions OpenSSH-Win64` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OpenSSHWin64.cimian.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OpenSSHWin64.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/OpenSSHWin64.cimian.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `OpenSSHWin64` and `PCMAN_TEMPLATE` is `OpenSSH-Win64`.
  Change the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the
  recipe.
- The input `SEARCH_PATTERN` of the download recipe takes the 64-bit MSI only. The
  32-bit and ARM64 MSIs and the zip files do not match it. Change it in the
  override's `Input`, not in the recipe.
- A release that the project marks as a pre-release is ignored (`include_prereleases`
  is false unless the override sets it: see "Pre-releases" at the top). Whether the
  project marks its betas that way is NOT established; if the
  newest stable release found is much older than the project's current one, say so
  to the owner before importing it.
- The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which
  the shared importer compares with the file it imports, so it allows a real run of
  this recipe without `pcman_allow_unverified`.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares, that no recipe sets `pcman_version` for an MSI,
that the pattern takes the 64-bit MSI and no other asset, that this README says
what was NOT rehearsed or fetched, has no `make-override` without
`--override-dir` and runs no recipe by its identifier, and that nothing
site-specific is in the folder.
