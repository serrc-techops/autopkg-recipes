# Win-XCPngCenter

A Windows recipe pair: XCP-ng Center, the `.msi`.

**Status. NOT rehearsed, and the facts of the source NOT fetched by the writer: the network was closed, so no GitHub page, no release and no API answer was read. Every fact below about the source is from the writer's knowledge or from another recipe of this repository, and none is checked: (1) the repository `xcp-ng/xenadmin` is where the project publishes its releases; (2) a release carries an asset named `XCP-ng-Center-<version numbers>.msi`, and no other asset matches the pattern `XCP-ng-Center-(?!99\.)[0-9.]+\.msi$` (the look-ahead refuses a version that begins with `99.`, see the `v99.99.99` tags below); (3) the project marks its pre-releases as pre-releases on GitHub; (4) the release assets have the digest that GitHub records, which `GitHubAssetDigest` reads (the way it reads it is from the 7-Zip rehearsal of 2026-10-01, not from this program); (5) the MSI's own ProductVersion is a version label that the package tool accepts, and a newer release has the same UpgradeCode as the older one; (6) the MSI's architecture, which is NOT known here. The project releases rarely, and a release asset that was uploaded before GitHub began to record digests has no digest. Then `GitHubAssetDigest` stops the run with its error, nothing is written, and the program is a hand import until a release with a digest exists. The tags of the repository, read through git on 2026-10-02 (the release assets, their digests and the pre-release flags were NOT fetched), are irregular: `v8.0.1.26`, `v20.03.00.29`, `v20.04.00.32`, `v20.04.01.33`, `v25.04`, `v99.99.99.23`, `v99.99.99.27`, `v99.99.99.29`, `vNext-24307`, `v.7.4.2`, `v.8.0.0`, and one more of the `v99.99.99` kind with a dot after the `v`; so which release GitHub calls the latest non-pre-release, and what its MSI is named, is NOT known, and the `v99.99.99` tags look like test builds. The default pattern therefore does not take a file whose version begins with `99.`: that is a precaution taken from the tags, and nobody has read the release list to see whether such a build is a release with an MSI. A person must still read the first dry run before anything else, because the newest release may be another kind of test build, and the recipe takes whatever GitHub returns first with a matching asset. The first run on the build Mac is the check of every one of these facts. When it fails, stop: nothing was written. Read the real release page and the real asset list, and correct the recipe. Never correct the trust information first.** The commands below are those of the 7-Zip folder, which was rehearsed; for this program they are expected, not seen. Every override command here carries `--override-dir`: see the next paragraph.

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `XCPngCenter-Win.download.recipe` | `com.github.serrc-techops.download.XCPngCenter-Win` | Takes the newest non-pre-release of `xcp-ng/xenadmin` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match, or when GitHub records none |
| `XCPngCenter.cimian.recipe` | `com.github.serrc-techops.cimian.XCPngCenter` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (see its
README).

The recipe gives no version label. For an MSI the package tool takes the MSI's own
ProductVersion. A label that the recipe gave would be wrong for an MSI.

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/XCPngCenter.cimian.recipe

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
   it replaces. If that item exists already (an import by hand), the template
   exists and this step is not needed: `pcman versions xcp-ng-center` lists it. The
   command, with a real MSI of the program:

       pcman import <path of the XCP-ng Center MSI> --name xcp-ng-center \
           --display-name "XCP-ng Center" --category <the category> \
           --developer <the developer> --description <the description> \
           --directory <the folder of the item> \
           --architectures <the MSI's architecture, read in the MSI first> --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. There is
   no `--install-arguments`: for an MSI the package tool knows the arguments (from
   the writer's knowledge, not read in the package tool's README). The architecture
   is not known to the writer: read it in the MSI before the first import. Add the
   icon as the package tool's README describes. A person changes the template
   later; nothing else does. **If the template is made from the release that is
   current on GitHub, the first run says "Nothing new" (see step c). To see a dry
   run that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i XCPngCenter-Win
    autopkg list-recipes | grep -i XCPngCenter.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> XCPngCenter.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `XCPngCenter.cimian`, not a path. Expected:
it writes `<the Windows overrides folder>/XCPngCenter.cimian.recipe` with the
identifier `local.cimian.XCPngCenter` and the trust information of the two recipes
and the three processors that are not part of AutoPkg itself (`GitHubAssetDigest`,
`ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.XCPngCenter-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.XCPngCenter`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current release is not yet in the
repository (the lines of the 7-Zip rehearsal, with this program's name; not seen
for this program):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name           Version    Catalogs    Result
    xcp-ng-center  <version>  Production  dry run, nothing written

If the current release is in the repository already (the template was made from
it), the line is `Nothing new: xcp-ng-center ... is in the repository already.
Nothing was written.` instead. That is correct.

If the run stops before the table, read the first error line. These are the
failures that this README expects, each with nothing written:

- No asset matches `SEARCH_PATTERN`: the asset name is not what the writer knew.
  Read the release's asset list and correct the pattern in the recipe's `Input`.
- `GitHubAssetDigest` stops because the asset has no digest: the release was
  uploaded before GitHub recorded digests. Nothing can verify the file. Publish
  it by hand after checking it, and wait for a release with a digest.
- The package tool refuses the label or the architecture: read its line.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/XCPngCenter.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.cimian.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip). Do not use
`-k pcman_dry_run=false` instead: on the command line it applies to every recipe
of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.cimian.recipe

   Expected: `Published xcp-ng-center <version>.` and the table

       The following versions were published by the package tool:
       Name           Version    Catalogs    Result
       xcp-ng-center  <version>  Production  published

   The repository then has the MSI under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions xcp-ng-center` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.cimian.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.cimian.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `XCPngCenter` and `PCMAN_TEMPLATE` is `xcp-ng-center`.
  Change the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the
  recipe.
- The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which
  the shared importer compares with the file it imports, so it allows a real run of
  this recipe without `pcman_allow_unverified`.
- Whether a new release has the same UpgradeCode as the one in the template is not
  established. The package tool refuses an MSI whose upgrade code differs. What
  happens on a PC that has the program from another source: test it on one PC
  before the PCs get the version.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares, that no recipe sets `pcman_version` for an
MSI, that this README says what was not rehearsed or fetched, has no
`make-override` without `--override-dir` and runs no recipe by its identifier,
and that nothing site-specific is in the folder.
