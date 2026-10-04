# Win-TemurinJRE8

A Windows recipe pair: Eclipse Temurin JRE 8, the 64-bit `.msi`, the latest release as the Adoptium project publishes it. **The owner decided on 2026-10-02 that Temurin replaces Oracle's JRE 8, and that the new item is named `temurin`** (see "The product decision" below). Nothing is in use until the template is made and a real run is switched on.

**Status. NOT rehearsed with AutoPkg. Some facts of the source were fetched by the writer on 2026-10-02: no run of AutoPkg was made, and nothing was written to a repository. Read from the Adoptium project's API on that day: `https://api.adoptium.net/v3/assets/latest/8/hotspot?os=windows&architecture=x64&image_type=jre&vendor=eclipse` answered 200 with no redirect and holds a JSON array of one element, with `release_name` `jdk8u504-b01`, `version.semver` `8.0.504+1`, and a `binary` whose `image_type` is `jre`, `os` is `windows` and `architecture` is `x64`; the binary has an `installer` with `name` `OpenJDK8U-jre_x64_windows_hotspot_8u504b01.msi`, a size of 32010240, a `link` on `https://github.com/adoptium/temurin8-binaries/releases/download/` and a `checksum` that is a SHA-256 (64 hex digits), and also a `package`, which is a zip file that the processor never takes. The provider's `main()` ran end to end on the saved real answer (the network fetch replaced by the saved text, default inputs) and gave the `url` `https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u504-b01/OpenJDK8U-jre_x64_windows_hotspot_8u504b01.msi`, the `version` `jdk8u504-b01` and an installer SHA-256 beginning 087a6724. NOT established: that the file at that link can be downloaded and that its hash equals the checksum (the writer did not request GitHub); that GitHub's answer for a release file (from the writer's knowledge, a redirect to a storage host) is one that `URLDownloader` follows without trouble; what the API answers for another feature version, image type or architecture (never read); the MSI's own ProductVersion, its UpgradeCode, its features and its properties; that the upgrade code differs from Oracle's JRE (the writer's knowledge, not read in an MSI); that the template exists, and what kind of item `jre8` is today (the Chocolatey item file of Oracle's JRE); `pcman catalogs`; any run with AutoPkg. The owner decided on 2026-10-02 that Temurin replaces Oracle's JRE 8 (the new item is named `temurin`); how Oracle's JRE 8 is removed on a PC, and whether a preinstall step of the template can do it, is NOT established and is read on the test PC first. The tests use an excerpt of the API's answer that the writer wrote by hand after the real answer of 2026-10-02, with made-up digits for the checksums, so they prove what the code does with an answer of that form and nothing about the project's servers today. The first run on the build Mac is the check of everything that is NOT established. When it fails, STOP: nothing was written (a run that fails before the import writes nothing). Read the real API answer and the real release on GitHub in a browser, correct the processor or the recipe, and only then look at the trust information. Never accept new trust information first to make a failure go away.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `TemurinJRE8-Win.download.recipe` | `com.github.serrc-techops.download.TemurinJRE8-Win` | Reads the Adoptium API's answer for the latest Temurin JRE of Java 8 for Windows, downloads its MSI from GitHub, and stops when the file does not match the SHA-256 that the API gives for that file |
| `TemurinJRE8.cimian.recipe` | `com.github.serrc-techops.cimian.TemurinJRE8` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

The processor `AdoptiumInfoProvider.py` is in this folder. It reads one address of the
project's API (`api.adoptium.net`): the latest release of a feature version for one
operating system, architecture and image type. It outputs `url` (the installer's link),
`version` (the project's `release_name`, `jdk8u504-b01` at the time of the reading) and
`expected_sha256`. No shared recipe reads this answer. The shared processors are in
`../Win-SharedProcessors/` (see its README). Neither recipe stops on an unchanged
download, so an import that failed is tried again at the next run.

How strict the processor is:

- The request goes to one fixed host over https. A redirect is not followed: it is an
  error. A status other than 200 is an error. The answer may be at most 1 MiB, the
  request has a time limit of 120 seconds, and the answer must be UTF-8 text.
- The feature version is digits only; the image type is `jre` or `jdk`; the architecture
  is `x64`, `x86` or `aarch64`; the operating system is `windows`. Anything else is an
  error, and nothing is fetched.
- The answer must be an array of exactly one element. The element's `binary.os`,
  `binary.architecture` and `binary.image_type` must equal the inputs.
- The installer must have a `name` that ends in `.msi`, a `link` that begins with
  `https://github.com/adoptium/temurin<feature>-binaries/releases/download/` followed by one
  folder and that file name and nothing more (no query, no fragment), and a `checksum` of
  64 hex digits. The zip file that the answer also holds (`binary.package`) is never taken.
- Nothing is output unless every check passed. An answer that is not what is expected is
  an error, never a guess.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## The product decision

**The owner decided on 2026-10-02 that Eclipse Temurin replaces Oracle's JRE 8, and that the new item is named `temurin`.** The item `jre8` installs
Oracle's JRE 8 today. Oracle's licence for business use needs a subscription, and its download
address changes with every version behind a login page, which is why no recipe can fetch
it. Eclipse Temurin is the OpenJDK build of the Adoptium project: free, with an MSI and a
published SHA-256.

- The template `temurin` is made from the Temurin MSI (step a.3). The recipe's default
  `PCMAN_TEMPLATE` is `temurin`. Temurin is a different product than Oracle's JRE, so it gets its own
  name and does not keep the name `jre8` (the other recipes keep the name of the item they
  replace; this one does not, for that reason).
- What changes with the name, all of it done by people and not by this recipe: the manifests
  that list `jre8` change to `temurin` (two lines in the content repository, done there);
  every item of the package tool whose `requires:` names `jre8` is changed to `temurin` by
  the owner before the catalogs are built; Oracle's item `jre8` (its item file and its
  pkginfo) is removed in the same commit as the new template.
- Temurin has another UpgradeCode than Oracle's JRE (from the writer's knowledge, NOT read in an
  MSI). A PC that has Oracle's JRE would get Temurin **beside it, not instead of it**. So the
  template `temurin` must remove Oracle's JRE 8 first: a preinstall step of the template, as
  the VLC template removes the EXE edition. That is the template's task, not this recipe's.
  How Oracle's JRE 8 is removed on a PC (its uninstaller, its product code, whether it leaves
  files or registry values) is NOT established: read it on the test PC first.
- The first import makes the new template under the name `temurin`. The Chocolatey item file
  of Oracle's JRE (`jre8`) is removed in the same commit as the new template, as for 7-Zip. How
  the package tool treats the two items side by side until then was NOT read.

## What the checks prove

- **The hash.** The hash comes from the project's API (`api.adoptium.net`) and the file from
  GitHub: two hosts. The check shows that the file is what the project published. It does
  not help if the project's release is changed on both.
- **The same product.** The package tool refuses an MSI whose upgrade code differs from the
  template's. Whether the MSI of Temurin has the same upgrade code in every release of
  Java 8 is NOT established; the first dry run against a template shows it.
- **The label.** The recipe gives no version label. For an MSI the package tool takes the
  MSI's own ProductVersion. What Temurin writes there for a release (the project's own
  version is `8.0.504+1`) is NOT established: the first dry run shows what the package tool
  reads, and nothing is passed by the recipe.

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

3. **The template item `temurin`, made once by a first import, in the same commit that removes
   Oracle's item `jre8`** (see "The product decision"), so that its pkginfo and installer are in
   the repository. The command, with a real MSI of the latest release:

       pcman import <path of OpenJDK8U-jre_x64_windows_hotspot_8u504b01.msi> --name temurin \
           --directory <the folder of the item> --architectures x64 \
           --display-name "Eclipse Temurin JRE 8" --category <the category of the item> \
           --developer "Eclipse Adoptium" --description <one sentence about the item> \
           --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. There are no
   install arguments: the package tool knows the arguments of an MSI. The developer's name
   is the project's name from the writer's knowledge. Which features and properties of the
   MSI the site wants (for example whether `JAVA_HOME` is set, whether the PATH is changed,
   whether `.jar` files are associated) is the owner's decision and was NOT read in the
   installer: the Temurin MSI has public properties for them (from the writer's knowledge,
   not read in the installer), and the Adoptium documentation lists them. A person changes
   the template later (the preinstall step that removes Oracle's JRE 8 is made there,
   after it has been read on the test PC); nothing else does. **If the template is made from the release that is
   latest on the project's API, the first run says "Nothing new" (see step c). To see a dry
   run that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i TemurinJRE8-Win
    autopkg list-recipes | grep -i TemurinJRE8.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> TemurinJRE8.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `TemurinJRE8.cimian`, not a path. Expected (not
run): it writes `<the Windows overrides folder>/TemurinJRE8.cimian.recipe` with the
identifier `local.cimian.TemurinJRE8` and the trust information of the two recipes and
the three processors that are not part of AutoPkg itself (`AdoptiumInfoProvider`,
`ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.TemurinJRE8-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TemurinJRE8.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.TemurinJRE8`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**`-vv` prints `pcman_root` and the repository: keep this log private.** Expected, from
the code and the rehearsals of the other folders, NOT printed by this recipe yet, when
the latest release is not yet in the repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name                   Version                 Catalogs    Result
    <the template's name>  <the MSI's own version>  Production  dry run, nothing written

The run also prints `Latest Temurin jre windows of Java 8: ...` and the project's SHA-256,
and then `SHA-256 verified: ...`. If the latest release is in the repository already (the
template was made from it), the line is `Nothing new: ... is in the repository already.
Nothing was written.` instead. That is correct.

If the project changes its API so that the processor cannot read it, the run fails with a
line that begins `The Adoptium API` and publishes nothing. If the line says that the API
answered with a redirect, stop and tell the owner: the recipe never reads a hash from
another host than the project's fixed one. If `URLDownloader` fails on GitHub's address,
stop, read the real release in a browser, and tell the owner: a hash for a file that
was not downloaded checks nothing.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/TemurinJRE8.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TemurinJRE8.cimian.recipe

A change of the `Input` does not break trust (found with 7-Zip). Do not use
`-k pcman_dry_run=false` instead: on the command line it applies to every recipe
of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TemurinJRE8.cimian.recipe

   Expected: `Published <the template's name> <the MSI's own version>.` and the table
   `The following versions were published by the package tool:` with the same columns as
   in step c and the result `published`. The repository then has the MSI under `pkgs/` and
   its pkginfo under `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions <the template's name>` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TemurinJRE8.cimian.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TemurinJRE8.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TemurinJRE8.cimian.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again. (Not run with this recipe.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The inputs of the download recipe are `TEMURIN_FEATURE_VERSION` (default `8`),
  `TEMURIN_IMAGE_TYPE` (default `jre`), `TEMURIN_ARCHITECTURE` (default `x64`) and
  `TEMURIN_OS` (default `windows`). Change them in the override's `Input`, not in the
  recipe. Another value was never tried: it is another product with another template, and
  the names of this folder say JRE8, so it needs a person's look first.
- A new release of Temurin may have another ProductCode and the same UpgradeCode (the
  usual way of an MSI, NOT read in two releases of this product). What happens on a PC that
  has Oracle's JRE 8 or another Java: test it on the test PC before the PCs get the version.
- The recipe's `NAME` is `TemurinJRE8` and `PCMAN_TEMPLATE` is `temurin`. Change the template
  name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- The file is stored under the name that the link has
  (`OpenJDK8U-jre_x64_windows_hotspot_8u504b01.msi` at the time of the reading), which ends
  in `.msi`; the importer takes `.msi` or `.exe`.
- The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which the
  shared importer compares with the file it imports, so it allows a real run of this
  recipe without `pcman_allow_unverified`.
- `-p` (a local file instead of the download) fails the checksum unless the file is
  the project's file.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of API answer (the excerpt in
`tests/adoptium_latest_excerpt.json` is written by hand after the real answer of
2026-10-02, with made-up digits for the checksums, not saved from the real server; the other
texts are made up), that both recipes are property lists, that every argument is an input
that the processor declares, that no recipe sets `pcman_version` for an MSI, that this
README has no `make-override` without `--override-dir` and runs no recipe by its
identifier, that it says what was NOT done and the owner's decision of 2026-10-02, and
that nothing site-specific is in the folder.
