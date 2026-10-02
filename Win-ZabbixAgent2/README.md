# Win-ZabbixAgent2

A Windows recipe pair: Zabbix Agent 2, the 64-bit `.msi` with OpenSSL, of the 7.0 line.

**Status. Rehearsed on 2026-10-01 with AutoPkg 2.9.0 in a scratch folder: the provider read the vendor's real page, the real file was downloaded and its hash checked, and with a template of the same version the run said "Nothing new". With a template of an older version (made by hand) a dry run, a real publish ("Published zabbix-agent2 7.0.31.2400") and a third run ("Nothing downloaded, packaged or imported") were run. NOT run: against the real share, `pcman catalogs`, a PC. Where a line below says "expected", it is what the code and the rehearsals lead to, not something that was printed. In the rehearsal the scratch overrides folder was one of AutoPkg's override folders; on the build machine the Windows overrides folder is not, so every override command here carries `--override-dir`: see the next paragraph.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `ZabbixAgent2-Win.download.recipe` | `com.github.serrc-techops.download.ZabbixAgent2-Win` | Reads the vendor's download page, takes the newest release of the line (default `7.0`), downloads its MSI, and stops when the file does not match the SHA-256 that the page gives |
| `ZabbixAgent2.cimian.recipe` | `com.github.serrc-techops.cimian.ZabbixAgent2` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

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
           --directory <the folder of the item> --architectures x64 --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. Add
   `--display-name`, `--category`, `--developer`, `--description` and the icon as
   the package tool's README describes. A person changes the template later;
   nothing else does. **If the template is made from the release that is current
   on the vendor's page, the first run says "Nothing new" (see step c). To see a
   dry run that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i ZabbixAgent2-Win
    autopkg list-recipes | grep -i ZabbixAgent2.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> ZabbixAgent2.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `ZabbixAgent2.cimian`, not a path. Expected:
it writes `<the Windows overrides folder>/ZabbixAgent2.cimian.recipe` with the
identifier `local.cimian.ZabbixAgent2` and the trust information of the two
recipes and the three processors that are not part of AutoPkg itself
(`ZabbixAgentInfoProvider`, `ChecksumVerifier`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.ZabbixAgent2-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.ZabbixAgent2`) runs the recipe itself, not the
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
        <the Windows overrides folder>/ZabbixAgent2.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.cimian.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip). Do not use
`-k pcman_dry_run=false` instead: on the command line it applies to every recipe
of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.cimian.recipe

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

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.cimian.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/ZabbixAgent2.cimian.recipe

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
