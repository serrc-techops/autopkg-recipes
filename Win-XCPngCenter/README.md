# Win-XCPngCenter

A Windows recipe pair: XCP-ng Center, the `.msi` of the project `xcp-ng/xenadmin` on GitHub.

**Status. The download is NOT verified: GitHub records no digest for the asset that the recipe takes, the release's text names no hash and no signature, and the shared signature check (`AuthenticodeVerifier`) is not part of this recipe. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true. Do not set it before a signature check is part of this recipe. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template xcp-ng-center` (no `--version` for an MSI). A digest step (`GitHubAssetDigest`, then `ChecksumVerifier`) can come back into the download recipe when a release has a digest. The recipe was changed after the first dry run with AutoPkg 2.9.0, and run again after the change (2026-10-04). The first run (before the change) stopped at `GitHubAssetDigest` with "GitHub asset 29445639: the record has no digest (older assets have none)": the asset was the installer of release `v20.04.01.33` (named `XCP-ng-Center-<version>.msi`), a file of December 2020, and not one of the newest release, because the pattern of that run, `XCP-ng-Center-(?!99\.)[0-9.]+\.msi$`, matches no file of any release after the one of 2020: the newest release names its installer `XCP-ng.Center.msi`. AutoPkg 2.9.0 takes the first release (in GitHub's order, newest first, a pre-release skipped) that has a file whose name the pattern matches from its start (`GitHubReleasesInfoProvider.py`, `select_asset`, `re.match`), however old, so it went back to the release of 2020. The test file writes that selection down as a function: on the saved list the old pattern takes the file of 2020 and the new one takes the newest. After the change a dry run under AutoPkg 2.9.0 selected `XCP-ng.Center.msi` of `v25.04` (GitHub records no digest for it, so no digest step ran: the unverified route). Later that day the first import with the package tool (the command of step a.3 below, run with `--no-prompt` and `--build`) made the item `xcp-ng-center` (an MSI item, version `25.04` read from the MSI: two parts, the second keeping its leading zero; architectures `x86,x64`, because the MSI's summary says platform `Intel`, a 32-bit package; the catalog `Production`), and the real run of the override of `XCPngCenter.pcman` (`make-override` with `--override-dir`, `ParentRecipe` right, `verify-trust-info` OK, `pcman_dry_run` false) was REFUSED with `The download was not verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file. Nothing was published. ...` (exit 70), which is what an unverified download must get; `pcman_allow_unverified` was not set. The override downloaded the file again, and its hash was the imported file's. The hand-import form `pcman import <file> --template xcp-ng-center --no-prompt --if-new --dry-run` printed `Nothing new: xcp-ng-center 25.04 exists already ...` with exit 3. The first import went beside the Chocolatey item `xcp-ng-center` (version 1.0) without any option of the tool; the Chocolatey item file and its `xcp-ng-center-1.0` pkginfo remain until a person removes them by hand, and `pcman validate` warns that the item has two versions until then. `pcman versions xcp-ng-center` lists the Chocolatey item too (`1.0`, no installer), so its listing does not show that a template exists: look at the item's kind. `pcman catalogs` ran a second time later on 2026-10-04, after the first imports of this and three other programs: the same command wrote the catalogs `All` and `Production`, 110 items each (106 before), with exit 0, and `Production` lists both versions of this name (the Chocolatey item's `1.0` and the new one). **The MSI has no `ALLUSERS` property** in its Property table (the MSI of PDFsam has `ALLUSERS=1`), and the release's text says that it was built with a custom tool in place of WiX. Without `ALLUSERS` Windows Installer installs per user, so an install that the client runs as SYSTEM may install the program for the SYSTEM account only; that is Windows Installer's rule, and it was NOT tested here. The template may need the install argument `ALLUSERS=1`; whether to add it is the owner's decision after a test on a PC. Nothing has been installed on a PC. Facts of the source were read by the writer on 2026-10-04 from GitHub's public release list of `xcp-ng/xenadmin` (`https://api.github.com/repos/xcp-ng/xenadmin/releases`, the newest 12 releases; read only, no file was downloaded). READ: (1) the newest release that is not a pre-release is `v25.04` (published 2025-04-29); its assets are `XCP-ng.Center.msi` (9298220 bytes), `XCP-ng.Center.zip` (8534206 bytes) and `XCP-ng.Center_pdb.zip` (789012 bytes); (2) GitHub records no digest for any asset of the 12 releases, so `GitHubAssetDigest` could stop this run for no release of the list; (3) the text of `v25.04` (3787 characters) names no hash, no signature and no certificate (searched for those words); it says that the release uses a new MSI installer built with a custom tool in place of WiX, and that it should upgrade installations made with WiX, which is the author's word and not tried; (4) the releases before it name the installer `XCP-ng-Center-<version>.msi`, one release (`vNext-24307`) has a `.zip` only, and the tags of the `99.99.99` kind are pre-releases (nightly builds; their files are `.zip` or `installer-xcp-ng-nightly-<version>.msi`); (5) the pattern is now `XCP-ng\.Center\.msi$`, which takes the file of `v25.04` and nothing in the other 11 releases. NOT established: that a new release has the same UpgradeCode as the template (the package tool refuses another one); that the MSI installs silently on a PC and for all users (see `ALLUSERS` above); that the next release keeps the name `XCP-ng.Center.msi` (if the project renames the file, the provider goes back to the newest older release that matches: read the line of the first dry run that names the selected asset and release); any install on a PC. An install on a test PC is the check of each of them. When a run fails, stop: nothing was written. Read the real release page and the real asset list, and correct the recipe. Never correct the trust information first. Every override command here carries `--override-dir`: see the next paragraph.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `XCPngCenter-Win.download.recipe` | `com.github.serrc-techops.download.XCPngCenter-Win` | Takes the newest non-pre-release of `xcp-ng/xenadmin` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. It has no hard check: GitHub records no digest for the file (see the status line) |
| `XCPngCenter.cimian.recipe` | `com.github.serrc-techops.cimian.XCPngCenter` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `XCPngCenter.pcman.recipe` | `com.github.serrc-techops.pcman.XCPngCenter` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `XCPngCenter.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `XCPngCenter.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

The recipe gives no version label. For an MSI the package tool takes the MSI's own
ProductVersion. A label that the recipe gave would be wrong for an MSI.

## What protects, and what does not

Nothing proves that the downloaded file is what the project published: GitHub records no
digest for it, the release's text names no hash, and the shared signature check (`AuthenticodeVerifier`) is not part of this recipe. The
shared importer knows this: no step of the recipe sets `checksum_verified` with the hash of the
file, so a real run is refused before the package tool starts. Two checks of the package tool
remain. They do not replace a verification.

- **The same product.** The package tool refuses an MSI whose upgrade code
  differs from the template's. So another product cannot be published under the
  name of this template.
- **The label.** The recipe gives no version label. For an MSI the package tool
  takes the MSI's own ProductVersion and refuses a label that is not the MSI's
  own version.

An MSI of the right product with other content (a changed file of the project, or a
changed download on the way) would pass both checks. A digest step can come back into the
download recipe when a release has a digest on GitHub: the steps are `GitHubAssetDigest` with
`github_asset_api_url` set to `%asset_url%`, then `ChecksumVerifier` with `pathname` and
`expected_sha256` set to `%pathname%` and `%expected_sha256%` (see their section in the shared README); the recipes
of `Win-PDFsam` and `Win-AngryIPScanner` have them.

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

## With any Cimian repository

This way needs AutoPkg, `msiinfo` (msitools: `brew install msitools`) for the MSI, and nothing of the owner's: no package tool. It uses `XCPngCenter.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

An override that was made from this recipe before the recipes were separated from the package tool belongs to the package tool's way: see the paragraph at the start of that section.

**The download of this program is NOT verified** (see the status line above, which speaks of `pcman_allow_unverified` for the package tool's way). For this way the same rule holds with the input `cimian_allow_unverified`: `CimianImporter` REFUSES a real run of a download that no step verified (nothing is published) unless the override sets `cimian_allow_unverified` to true. Do not set it before a verification step exists. A dry run is allowed, and prints a `WARNING: the download was NOT verified` line.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `InstallerService.cs:936`) are from `windowsadmins/cimian` at commit `e10498b`, read on 2026-10-04 and not checked against a later version.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **`msiinfo` on the PATH of the run** (`brew install msitools`): `CimianImporter` reads the MSI's ProductVersion and its two codes with it, and does not parse an MSI itself. A job that `launchd` starts may have no Homebrew on its `PATH`, so the importer looks in `/opt/homebrew/bin` and `/usr/local/bin` too; the input `cimian_path` changes that list. This recipe cannot run without it: its step passes an empty `version` (so that a release tag is not taken for the MSI's own version), and an argument of a step wins over an override's `Input`, so the label can only come from the MSI. The run stops and names the facts that are missing.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `xcp-ng-center`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **For an `.msi` nothing needs completing for a silent install:** the client runs `msiexec /i <file> /qn /norestart` itself and then the arguments of the item (`InstallerService.cs:936-948`), so the recipe gives no silent arguments, and `CimianImporter` writes the install check of an MSI (an `installs` entry of type `msi` with the MSI's codes and version). What the MSI's own properties allow (features, per-user or per-machine) is the template's business: give them as `installer: {args: [...]}` in the override's `pkginfo`. An MSI whose upgrade code is not the template's, or that has none where the template's item had one, is refused (Windows Installer does not upgrade across upgrade codes): `cimian_allow_product_change` set to true in the override allows it, with a WARNING.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i XCPngCenter-Win
    autopkg list-recipes | grep -i XCPngCenter.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> XCPngCenter.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `XCPngCenter.cimian`, not a path. It writes `<the Windows overrides folder>/XCPngCenter.cimian.recipe` with the identifier `local.cimian.XCPngCenter` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.XCPngCenter`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the lines of the provider (`Selected asset ... from release ...`) are printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.XCPngCenter`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.msi (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file, or signature_verified together with the signature_sha256 of this file. ...

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written, NOT verified`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first. **Read the line `Selected asset ... from release ...`**: the release must be the newest that is not a pre-release (see the status line for why).

### 4. Switch a real run on (NOT YET: see the status line)

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/XCPngCenter.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

**Not yet.** This download has no verification step, so `CimianImporter` refuses the real run below until the override also sets `cimian_allow_unverified` to true, which a person decides only after the file was checked by hand, and which is then written in the override's `Input`, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_allow_unverified bool true' \
        <the Windows overrides folder>/XCPngCenter.cimian.recipe

With it the run prints `WARNING: published WITHOUT a verified download` and the report row says `published, NOT verified`.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `XCPngCenter.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `XCPngCenter.pcman` where this README used to say `XCPngCenter.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `XCPngCenter.cimian.recipe` (when that recipe ran the package tool) must be made again from `XCPngCenter.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `XCPngCenter.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   it replaces. If an item of the kind `msi` exists already (an import by hand), it is the
   template and this step is not needed. An item `xcp-ng-center` of the kind `choco` (version 1.0, no
   installer) is not the template, and `pcman versions xcp-ng-center` lists it too, so look at the kind (see the
   status line: the first import of 2026-10-04 went beside it without any option, and a person removes the
   Chocolatey item by hand). The command, in the form that ran on 2026-10-04 (it worked as written), with a
   real MSI of the program that a person has downloaded and checked:

       pcman import <path of the XCP-ng Center MSI> --name xcp-ng-center \
           --display-name "XCP-ng Center" --category <the category> \
           --developer <the developer> --description <the description> \
           --directory <the folder of the item> \
           --architectures x86,x64 --icon <the file name of an icon that the repository has> --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version (`25.04` on 2026-10-04). There is
   no `--install-arguments`: for an MSI the client runs `msiexec /i <file> /qn /norestart` itself (not tested on a PC).
   `--architectures x86,x64` is because the MSI's summary says platform `Intel`, a 32-bit package (read on 2026-10-04).
   **Still to decide after a test on a PC:** whether the template needs the install argument `ALLUSERS=1`, because the
   MSI has no `ALLUSERS` property (see the status line). A person changes the template
   later; nothing else does. **If the template is made from the release that is
   current on GitHub, the first run says "Nothing new" (see step c). To see a dry
   run that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i XCPngCenter-Win
    autopkg list-recipes | grep -i XCPngCenter.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> XCPngCenter.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `XCPngCenter.pcman`, not a path. Expected:
it writes `<the Windows overrides folder>/XCPngCenter.pcman.recipe` with the
identifier `local.pcman.XCPngCenter` and the trust information of the two recipes
and the two processors that are not part of AutoPkg itself (`GitHubNewestReleaseGuard`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.XCPngCenter`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the lines of the provider (`Selected asset ... from release ...`) are printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.XCPngCenter`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current release is not yet in the
repository (the lines of the 7-Zip rehearsal, with this program's name; not seen
for this program):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file, or signature_verified together with the signature_sha256 of this file. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name           Version    Catalogs    Result
    xcp-ng-center  <version>  Production  dry run, nothing written, NOT verified

If the current release is in the repository already (the template was made from
it), the line is `Nothing new: xcp-ng-center ... is in the repository already.
Nothing was written.` instead. That is correct.

If the run stops before the table, read the first error line. These are the
failures that this README expects, each with nothing written:

- No asset matches `SEARCH_PATTERN`: the asset name is not one that the pattern knows.
  Read the release's asset list and correct the pattern in the recipe's `Input`.
- `GitHubNewestReleaseGuard` stops (its message names the selected release, the newest release and the files
  of the newest release): the newest release has a file name that the pattern does not take, and the provider
  went back to an older release. Nothing was written. Correct `SEARCH_PATTERN` in the override's `Input` (this is what
  happened on 2026-10-04, before the guard existed), or, for a newest release that has no Windows installer on
  purpose (no file ending in `.msi`, `.exe` or `.msix`), accept exactly that release with `accepted_newest_release` in the override.
  The guard is new and has not run under AutoPkg.
- The run goes on, but with an old release (the line `Selected asset ... from release ...`
  names a release that is not the newest non-pre-release): the newest one has a name that the
  pattern does not take, and the provider went back to an older one. Stop. This is what
  happened on 2026-10-04. Correct `SEARCH_PATTERN` before anything is published. The guard now stops this case.
- The package tool refuses the label or the architecture: read its line.

## d. Switch a real run on (NOT YET: see the status line)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file, or signature_verified together with the
    signature_sha256 of this file. Nothing was published. Publish by hand after checking
    the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template xcp-ng-center

Do not add `--version` for an MSI: the package tool takes the MSI's own version. Then
`pcman catalogs` (step e.3).

**Only after the signature check exists, or when a person has decided to accept an
unverified download:** the override allows it. Both lines are needed.

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/XCPngCenter.pcman.recipe
    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_allow_unverified bool true' \
        <the Windows overrides folder>/XCPngCenter.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.pcman.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip). Do not use `-k`
instead: on the command line it applies to every recipe of that run. A run then prints
`WARNING: published WITHOUT a verified download ...` at any verbosity, and the report's
row says `published, NOT verified`.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.pcman.recipe

   Only after both lines of step d. Expected: `Published xcp-ng-center ...`, the warning
   `published WITHOUT a verified download`, and the table

       The following versions were published by the package tool:
       Name           Version    Catalogs    Result
       xcp-ng-center  <version>  Production  published, NOT verified

   The repository then has the MSI under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions xcp-ng-center` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/XCPngCenter.pcman.recipe

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
- The download has no checksum step, so the shared importer refuses a real run without
  `pcman_allow_unverified` (see step d).
- AutoPkg's provider takes the first release, newest first, that has a file whose name
  matches `SEARCH_PATTERN`, however old. When a name changes, the provider does not stop: it
  goes back. The step `GitHubNewestReleaseGuard`, right after it, now stops the run when the
  release that the provider selected is not the newest release that is not a pre-release; its
  message names the newest release and its files. Then correct `SEARCH_PATTERN` in the
  override's `Input`, or, for a newest release that has no Windows installer file (none ending in
  `.msi`, `.exe` or `.msix`) on purpose, accept exactly that release with the key
  `accepted_newest_release` of the override (its tag: offered only for a release without such a file,
  and not when a release between it and the selected one has one; the run goes on only while that
  release is the newest, says so in every run, and stops again when a newer one appears; never in the
  recipe). The guard compares positions in GitHub's list, not versions. It is new and has not run under
  AutoPkg. It compares releases, not files.
  Read the `Selected asset` line of every dry run (run it with `-v`).
- Whether a new release has the same UpgradeCode as the one in the template is not
  established. The package tool refuses an MSI whose upgrade code differs. What
  happens on a PC that has the program from another source: test it on one PC
  before the PCs get the version.
- `-p` (a local file instead of the download) skips the download. The file is not
  checked at all.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that the Description of both recipes
and the top of this README say that the download is not verified and that a real run is
refused, that this README states no hash, that the pattern takes `XCP-ng.Center.msi` of the
newest release and the old pattern took the file of 2020, that every argument is an input
that the shared processor declares, that no recipe sets `pcman_version` for an
MSI, that this README has no `make-override` without `--override-dir` and runs no recipe
by its identifier, and that nothing site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
