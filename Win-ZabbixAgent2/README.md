# Win-ZabbixAgent2

A Windows recipe pair: Zabbix Agent 2, the 64-bit `.msi` with OpenSSL, of the 7.0 line.

**Status. Rehearsed on 2026-10-01 with AutoPkg 2.9.0 in a scratch folder: the provider read the vendor's real page, the real file was downloaded and its hash checked, and with a template of the same version the run said "Nothing new". With a template of an older version (made by hand) a dry run, a real publish ("Published zabbix-agent2 7.0.31.2400") and a third run ("Nothing downloaded, packaged or imported") were run. On 2026-10-04, under AutoPkg 2.9.0, the first import (the command of step a.3 below, run with `--no-prompt` and `--build`) made the item `zabbix-agent2` (an MSI item, version `7.0.31.2400` read from the MSI, architectures `x64`) in the package tool's repository, in the catalog `Production`. The first import went beside the Chocolatey item `zabbix-agent2` (version 1.0) without any option of the tool; the Chocolatey item file and its `zabbix-agent2-1.0` pkginfo remain until a person removes them by hand, and `pcman validate` warns that the item has two versions until then. The override of `ZabbixAgent2.pcman` (`make-override` with `--override-dir`, `ParentRecipe` right, `verify-trust-info` OK, `pcman_dry_run` false) then ran for real against the repository: the provider read the vendor's page, the download was checked against the vendor's hash, and the run ended with `Nothing new: zabbix-agent2 7.0.31.2400 is in the repository already. Nothing was written.` `pcman catalogs` ran once for all the new items together (2026-10-04): the tool's configured command ran `makecatalogs` on the repository's server, with exit 0, and wrote the catalogs `All` and `Production`, 106 items each. **The new item has no MSI properties and none of the scripts of the Chocolatey item** (`preinstall_script`, `postinstall_script` and `pre_installcheck_script`; their content was not read). A note of 2026-10-01 says that the vendor's MSI writes a new configuration file on a command-line install unless properties are passed (not tried again here): so a PC that takes this item bare may have its agent configuration overwritten, and the properties or the scripts are to be added to the item before PCs get it. The silent install is the client's (`/qn /norestart` for an MSI) and was NOT tested on a PC. Still NOT established after those runs: that the MSI installs silently on a PC; any install; that a new release has the same upgrade code as the template. Where a line below says "expected", it is what the code and the rehearsals lead to, not something that was printed. In the rehearsal the scratch overrides folder was one of AutoPkg's override folders; on the build machine the Windows overrides folder is not, so every override command here carries `--override-dir`: see the next paragraph.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `ZabbixAgent2-Win.download.recipe` | `com.github.serrc-techops.download.ZabbixAgent2-Win` | Reads the vendor's download page, takes the newest release of the line (default `7.0`), downloads its MSI, and stops when the file does not match the SHA-256 that the page gives |
| `ZabbixAgent2.cimian.recipe` | `com.github.serrc-techops.cimian.ZabbixAgent2` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `ZabbixAgent2.pcman.recipe` | `com.github.serrc-techops.pcman.ZabbixAgent2` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `ZabbixAgent2.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `ZabbixAgent2.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The processor `ZabbixAgentInfoProvider.py` is in this folder. It reads the page
`https://www.zabbix.com/download_agents`. The page holds one record for each
file the vendor offers (release, platform, architecture, encryption, packaging,
path, SHA-256). The processor keeps the records that match the recipe's inputs
and takes the newest release **by comparing its three numbers** (7.0.31 is newer
than 7.0.5). It outputs `url`, `version` and `expected_sha256`. It stops the run
when the page is not what it expects. No shared recipe reads these records.

The processor also checks the file it returns against the record. The path must be
exactly `<line>/<release>/<file name>`, and the file name is built from the inputs
(`zabbix_agent2-7.0.31-windows-amd64-openssl.msi` for the defaults). Another file
name, or a sub-folder, stops the run. The flags `static` and `legacy` of a record are
read strictly: a boolean, `0` or `1`, or the text `true`, `false`, `yes`, `no`, `1`,
`0`. Any other value in a record that matches the inputs stops the run. The names can
be built for Windows, encryption `OpenSSL` or `No encryption`, and packaging `MSI` or
`Archive`; other inputs are refused.

The other processors are in `../Win-SharedProcessors/` (see its README). Neither
recipe stops on an unchanged download, so an import that failed is tried again at
the next run.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What the checks prove

- **The hash.** The file and the hash come from two host names of one vendor
  (the download server and the web page). The check shows that the file is what
  the vendor published. It does not help if the vendor's own servers are changed.
- **The same product.** The package tool refuses an MSI whose upgrade code
  differs from the template's. Two releases of Zabbix Agent 2 that were read have the
  same upgrade code.
- **The label.** The recipe gives no version label. For an MSI the package tool
  takes the MSI's own ProductVersion, which has four numbers (release `7.0.31` is
  `7.0.31.2400`). A label of three numbers would be refused.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg, `msiinfo` (msitools: `brew install msitools`) for the MSI, and nothing of the owner's: no package tool. It uses `ZabbixAgent2.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

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

3. **`msiinfo` on the PATH of the run** (`brew install msitools`): `CimianImporter` reads the MSI's ProductVersion and its two codes with it, and does not parse an MSI itself. A job that `launchd` starts may have no Homebrew on its `PATH`, so the importer looks in `/opt/homebrew/bin` and `/usr/local/bin` too; the input `cimian_path` changes that list. This recipe cannot run without it: its step passes an empty `version` (so that a release tag is not taken for the MSI's own version), and an argument of a step wins over an override's `Input`, so the label can only come from the MSI. The run stops and names the facts that are missing.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `zabbix-agent2`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **For an `.msi` nothing needs completing for a silent install:** the client runs `msiexec /i <file> /qn /norestart` itself and then the arguments of the item (`InstallerService.cs:936-948`), so the recipe gives no silent arguments, and `CimianImporter` writes the install check of an MSI (an `installs` entry of type `msi` with the MSI's codes and version). What the MSI's own properties allow (features, per-user or per-machine) is the template's business: give them as `installer: {args: [...]}` in the override's `pkginfo`. An MSI whose upgrade code is not the template's, or that has none where the template's item had one, is refused (Windows Installer does not upgrade across upgrade codes): `cimian_allow_product_change` set to true in the override allows it, with a WARNING.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i ZabbixAgent2-Win
    autopkg list-recipes | grep -i ZabbixAgent2.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> ZabbixAgent2.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `ZabbixAgent2.cimian`, not a path. It writes `<the Windows overrides folder>/ZabbixAgent2.cimian.recipe` with the identifier `local.cimian.ZabbixAgent2` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.ZabbixAgent2`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.ZabbixAgent2`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.msi (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/ZabbixAgent2.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `ZabbixAgent2.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `ZabbixAgent2.pcman` where this README used to say `ZabbixAgent2.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `ZabbixAgent2.cimian.recipe` (when that recipe ran the package tool) must be made again from `ZabbixAgent2.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `ZabbixAgent2.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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
   it replaces. The command, with a real MSI of the line:

       pcman import <path of zabbix_agent2-7.0.31-windows-amd64-openssl.msi> --name zabbix-agent2 \
           --directory <the folder of the item> --architectures x64 \
           --display-name "Zabbix Agent 2" --category <the category of the item> --developer Zabbix \
           --description <one sentence about the item> \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   This is the form that ran on 2026-10-04 (it worked as written); it made the item without MSI properties and without scripts (see the status line).
   There is no `--version`: the package tool takes the MSI's own version (`7.0.31.2400` on that day). A person changes the template later;
   nothing else does. **If the template is made from the release that is current
   on the vendor's page, the first run says "Nothing new" (see step c). To see a
   dry run that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i ZabbixAgent2-Win
    autopkg list-recipes | grep -i ZabbixAgent2.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> ZabbixAgent2.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `ZabbixAgent2.pcman`, not a path. Expected:
it writes `<the Windows overrides folder>/ZabbixAgent2.pcman.recipe` with the
identifier `local.pcman.ZabbixAgent2` and the trust information of the two
recipes and the three processors that are not part of AutoPkg itself
(`ZabbixAgentInfoProvider`, `ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.ZabbixAgent2`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.ZabbixAgent2`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current release is not yet in the
repository (the lines of the 7-Zip rehearsal, with this program's name; the
version is the MSI's own, four numbers):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name           Version      Catalogs    Result
    zabbix-agent2  7.0.31.2400  Production  dry run, nothing written

With `-v` the run also prints `Newest release of line 7.0: ...` and the vendor's
SHA-256, and then `SHA-256 verified: ...`. If the current release is in the
repository already (the template was made from it), the line is `Nothing new:
zabbix-agent2 ... is in the repository already. Nothing was written.` instead.
That is correct.

If the vendor changes the page so that the processor cannot read it, the run
fails with a line that begins `Zabbix download page:` and publishes nothing.

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/ZabbixAgent2.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.pcman.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip). Do not use
`-k pcman_dry_run=false` instead: on the command line it applies to every recipe
of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.pcman.recipe

   Expected: `Published zabbix-agent2 7.0.31.2400.` and the table

       The following versions were published by the package tool:
       Name           Version      Catalogs    Result
       zabbix-agent2  7.0.31.2400  Production  published

   The repository then has the MSI under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions zabbix-agent2` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.` (On 2026-10-04 the first run of a fresh override printed the line `Nothing new: ...` after it had downloaded the file again, because a new override gets a new cache folder; `Nothing downloaded, packaged or imported.` was not seen in that run, and is the line of a later run of the same override.)

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- A new release has a new ProductCode and the same UpgradeCode (read in two
  releases). Windows Installer treats it as a major upgrade, and the client finds
  the installed product through the UpgradeCode. What happens on a PC that has the
  agent from another source: test it on one PC before the PCs get the version.
- The inputs of the download recipe are `ZABBIX_LINE` (default `7.0`),
  `ZABBIX_PLATFORM`, `ZABBIX_ARCHITECTURE`, `ZABBIX_ENCRYPTION` and
  `ZABBIX_PACKAGING`. Change them in the override's `Input`, not in the recipe.
  Another line needs a person's look first: whether the template's upgrade code
  stays the same is not established.
- A release that is not three numbers (a pre-release) is ignored. A record of a
  static build or a legacy download is ignored. The checksum step sets
  `checksum_verified` and the hash `checksum_sha256`, which the shared importer
  compares with the file it imports, so it allows a real run of this recipe
  without `pcman_allow_unverified`.
- The recipe's `NAME` is `ZabbixAgent2` and `PCMAN_TEMPLATE` is `zabbix-agent2`.
  Change the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the
  recipe.
- `-p` (a local file instead of the download) fails the checksum unless the file is
  the vendor's file.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of page (the saved excerpt in
`tests/download_agents_excerpt.html` is a few real records; the other pages are
made up), that both files are property lists, that every argument is an input that
the processor declares, that no recipe sets `pcman_version` for an MSI, that this
README has no `make-override` without `--override-dir` and runs no recipe by its
identifier, and that nothing site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
