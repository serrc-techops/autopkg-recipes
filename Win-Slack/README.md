# Win-Slack

A Windows recipe pair: Slack, the per-machine 64-bit `.msi`.

**NOT WORKING (expected). This recipe pair is expected to stop at its first run and publish nothing: the download answers 404. The first dry run with AutoPkg 2.9.0 (2026-10-04) passed the first step (the version from the release notes page) and stopped at `URLDownloader` with `curl: (56) The requested URL returned error: 404`. Read from Slack's own servers on 2026-10-04, with `curl`, by HEAD requests and four pages (no installer was downloaded): (1) `https://slack.com/release-notes/windows` answers 200; (2) the file that the recipe asks for, `slack-standalone-<version>.0.msi` in the folder `https://downloads.slack-edge.com/desktop-releases/windows/x64/<version>/`, answers 200 for the 13 versions of the page from `4.46.96` (2025-09-09) to `4.48.102` (2026-03-17) and 404 for the 13 versions from `4.49.81` (2026-04-02) to `4.52.171` (2026-09-28), the newest (the 26 newest versions of the page were tried and no older one); (3) Slack's own call for the latest MSI, `https://slack.com/api/desktop.latestRelease?variant=msi&arch=x64`, answers a JSON object whose `download_url` is that same file for `4.52.171`, and with `redirect=1` it answers 302 to it, so the vendor's permanent address leads to the missing file; (4) the link `https://slack.com/ssb/download-win64-msi`, which names an MSI for 64-bit Windows, answers 404; (5) Slack's Windows download page, `https://slack.com/downloads/windows`, offers three builds (`win64`, `arm64` and `win64_msix`) and the word MSI is not on it; (6) `Slack.msix` in the same folder answers 200 for all 26 versions, and `SlackSetup.exe` answers 200 for `4.52.171` (the one version tried); (7) the release notes page does not say that the MSI is discontinued (its text names the MSI once, in a fix of the launch-on-login setting). So no address of an MSI can be established. What the vendor serves today is an MSIX and an EXE: the package tool does not take an MSIX, and an EXE would be another kind of item with another template and other silent arguments, which is the owner's decision and not made here. When Slack serves the MSI again at that address the recipe works unchanged. Whether the pair stays in this repository is the owner's decision at the merge.**

**Status. One dry run with AutoPkg 2.9.0 (2026-10-04) stopped at the download (see the mark above). Nothing of this pair has run with the package tool, a share or a PC. Facts of the source were read on 2026-10-04 with `curl` (the pages and the answers named in the mark; no installer was downloaded). READ: (1) the address of the release notes page, `https://slack.com/release-notes/windows`, answers 200 with an HTML page whose first match of the pattern `Slack\s+(?P<version>[0-9]+\.[0-9]+\.[0-9]+)` is `Slack 4.52.171` (September 28, 2026), followed by `Slack 4.52.162` (September 21, 2026) and `Slack 4.52.155` (August 31, 2026), so the FIRST match on that page is the newest release, and the text is in the HTML that `curl` gets (it is not built by script); (2) the first step passed in the run: `URLTextSearcher` stops with `No match found on URL` when the pattern finds nothing, and the run went on to the downloader, and `URLTextSearcher` sets each named group of the pattern in the run under its own name, here `version` (`URLTextSearcher.py`, `main`, of AutoPkg 2.9.0); (3) the address of the file, `https://downloads.slack-edge.com/desktop-releases/windows/x64/<version>/slack-standalone-<version>.0.msi`, was right for the versions up to `4.48.102` and answers 404 since `4.49.81` (see the mark); `Slack.msix` is in the same folder (see the mark), and the package tool does not take an MSIX. NOT established: that this MSI, when it exists, is the per-machine installer and that its own version is the one that the package tool will read from it (nobody downloaded one); why Slack stopped serving the MSI, and whether it will serve it again; any run with AutoPkg beyond the download. When the address works again, the first run on the build Mac is the check of the rest. When it fails, stop: nothing was written. Read the real page or the real release and correct the recipe, never the trust information first.**

**Not verified. The download is NOT verified: Slack publishes no hash for the file, and the shared signature check (`AuthenticodeVerifier`) is not part of this recipe. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true. Do not set it before a signature check is part of this recipe. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template slack` (no `--version` for an MSI). A real run of this recipe has NOT been run by anyone, not against a share and not on a PC, and its one dry run (2026-10-04) stopped at the download. `pcman catalogs` was NOT run either. The Windows overrides folder is not one of AutoPkg's override folders, so every override command here carries `--override-dir`: see the paragraph below.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Slack-Win.download.recipe` | `com.github.serrc-techops.download.Slack-Win` | Reads the newest version from Slack's release notes page (`URLTextSearcher`), then downloads the per-machine MSI from the address that has this version in it. It has no hard check |
| `Slack.cimian.recipe` | `com.github.serrc-techops.cimian.Slack` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new |
| `Slack.pcman.recipe` | `com.github.serrc-techops.pcman.Slack` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `Slack.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `Slack.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The version that the download recipe reads is used only to build the address. It
is not passed to the package tool: for an MSI the package tool takes the MSI's own
version.

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What protects, and what does not

Nothing proves that the downloaded file is what Slack published: there is no vendor
hash, and the shared signature check (`AuthenticodeVerifier`) is not part of this recipe. The shared importer knows this: no step of
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
changed download on the way) would pass both checks. The version read from the page
is not a check: it only chooses which address is asked for.

**No hash source.** Slack publishes no hash for the file, and the recipe has no other
source for one, so the transfer is protected by TLS to the vendor's host and by one rule
of the recipe: **the downloader refuses a redirect that leads to anything but https**
(`curl_opts` `--proto-redir` `=https` on the download step). A redirect to plain HTTP,
from a mirror or from an attacker on the way, stops the run with curl's error (macOS curl
8.7.1 said `Protocol "http" disabled (in redirect)`), and nothing is written. The rule is
about the transfer only: a file that comes over https from the right host, or from a host
that it redirects to, is not checked against anything. The page that gives the version is
fetched without the rule; what it says only chooses the address.

`URLDownloader` of AutoPkg 2.9.0 declares `curl_opts` and adds each item of it to the
download's curl command (`URLDownloader.py`, `prepare_download_curl_cmd`; `URLGetter.py`,
`add_curl_common_opts`), which is why the option and its value are two items. The tests run
curl itself, with these options, against a server on the machine that runs them. Spell the
key exactly: AutoPkg 2.9.0 ignores an argument that it does not know, without a message.

**The page's version and the MSI's own version.** Nothing compares them. The version on
the release notes page only chooses the address; the label of the package tool is the MSI's
own ProductVersion, which the package tool reads from the file, and the two are not written
alike (the address has `<version>.0` in the file name). The comparison is a person's, once,
at the first dry run (step c, run with `-v`): the run prints `URLTextSearcher: Found
matching text (version): ...` for the page, and the dry run's table shows the MSI's own
version in its Version column. Compare their numbers. If they differ in more than a
trailing part, stop and tell the owner before anything is published: the file may not be
the version that the page announced. The recipe does not repeat the comparison at later
runs.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg, `msiinfo` (msitools: `brew install msitools`) for the MSI, and nothing of the owner's: no package tool. It uses `Slack.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

An override that was made from this recipe before the recipes were separated from the package tool belongs to the package tool's way: see the paragraph at the start of that section.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `InstallerService.cs:936`) are from `windowsadmins/cimian` at commit `e10498b`, read on 2026-10-04 and not checked against a later version.

**The download of this program is NOT verified** (see the status line above, which speaks of `pcman_allow_unverified` for the package tool's way). For this way the same rule holds with the input `cimian_allow_unverified`: `CimianImporter` REFUSES a real run of a download that no step verified (nothing is published) unless the override sets `cimian_allow_unverified` to true. Do not set it before a verification step exists. A dry run is allowed, and prints a `WARNING: the download was NOT verified` line.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **`msiinfo` on the PATH of the run** (`brew install msitools`): `CimianImporter` reads the MSI's ProductVersion and its two codes with it, and does not parse an MSI itself. A job that `launchd` starts may have no Homebrew on its `PATH`, so the importer looks in `/opt/homebrew/bin` and `/usr/local/bin` too; the input `cimian_path` changes that list. This recipe cannot run without it: its step passes an empty `version` (so that a release tag is not taken for the MSI's own version), and an argument of a step wins over an override's `Input`, so the label can only come from the MSI. The run stops and names the facts that are missing.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `slack`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **For an `.msi` nothing needs completing for a silent install:** the client runs `msiexec /i <file> /qn /norestart` itself and then the arguments of the item (`InstallerService.cs:936-948`), so the recipe gives no silent arguments, and `CimianImporter` writes the install check of an MSI (an `installs` entry of type `msi` with the MSI's codes and version). What the MSI's own properties allow (features, per-user or per-machine) is the template's business: give them as `installer: {args: [...]}` in the override's `pkginfo`. An MSI whose upgrade code is not the template's, or that has none where the template's item had one, is refused (Windows Installer does not upgrade across upgrade codes): `cimian_allow_product_change` set to true in the override allows it, with a WARNING.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i Slack-Win
    autopkg list-recipes | grep -i Slack.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Slack.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `Slack.cimian`, not a path. It writes `<the Windows overrides folder>/Slack.cimian.recipe` with the identifier `local.cimian.Slack` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.Slack`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.Slack`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.msi (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on (NOT YET: see the status line)

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/Slack.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

**Not yet.** This download has no verification step, so `CimianImporter` refuses the real run below until the override also sets `cimian_allow_unverified` to true, which a person decides only after the file was checked by hand, and which is then written in the override's `Input`, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_allow_unverified bool true' \
        <the Windows overrides folder>/Slack.cimian.recipe

With it the run prints `WARNING: published WITHOUT a verified download` and the report row says `published, NOT verified`.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `Slack.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `Slack.pcman` where this README used to say `Slack.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. **An override that was made from the old `Slack.cimian.recipe` (when that recipe ran the package tool) must be made again from `Slack.pcman.recipe`:** it has `PCMAN_TEMPLATE` in its `Input`, which the new `Slack.cimian.recipe` does not read, and once its trust information is accepted again it would run `CimianImporter` instead of the package tool.

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

       pcman import <path of the MSI> --name slack \
           --display-name Slack --category <the category of the item> \
           --developer "Slack Technologies" --description "<one line about the item>" \
           --directory <the folder of the item> --architectures x64 --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. The
   install arguments are not given: the package tool knows the arguments of an MSI
   (silent, no restart); read what it wrote into the pkginfo and check it. Add the
   icon as the package tool's README describes. A person changes the template
   later; nothing else does. **If the template is made from the installer that is
   current at the vendor, the first run says "Nothing new" (see step c). To see a
   dry run that would publish, make the template from an older version.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Slack-Win
    autopkg list-recipes | grep -i Slack.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Slack.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Slack.pcman`, not a path. Expected: it
writes `<the Windows overrides folder>/Slack.pcman.recipe` with the identifier
`local.pcman.Slack` and the trust information of the two recipes and of the
one processor that is not part of AutoPkg itself (`PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.Slack`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the
version found on the page is printed (`-v` prints what each processor says about its own
work; `-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the
repository among them, and such a log would have to be kept private):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.Slack`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current version is not yet in the
repository (the lines of the 7-Zip rehearsal, with this program's name; they were
NOT seen for this recipe, and the version is the MSI's own):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file, or signature_verified together with the signature_sha256 of this file. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name   Version  Catalogs    Result
    slack  <the MSI's own version>  Production  dry run, nothing written, NOT verified

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line is
`Nothing new: ... is in the repository already. Nothing was written.` instead.
That is correct.

## d. Switch a real run on (NOT YET: see the second paragraph at the top)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file, or signature_verified together with the
    signature_sha256 of this file. Nothing was published. Publish by hand after checking
    the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template slack

Do not add `--version` for an MSI: the package tool takes the MSI's own version. Then
`pcman catalogs` (step e.3).

**Only after the signature check exists, or when a person has decided to accept an
unverified download:** the override allows it. Both lines are needed.

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Slack.pcman.recipe
    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_allow_unverified bool true' \
        <the Windows overrides folder>/Slack.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.pcman.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip). Do not use `-k`
instead: on the command line it applies to every recipe of that run. A run then prints
`WARNING: published WITHOUT a verified download ...` at any verbosity, and the report's
row says `published, NOT verified`.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.pcman.recipe

   Only after both lines of step d. Expected: `Published slack ...`, the warning
   `published WITHOUT a verified download`, and the table

       The following versions were published by the package tool:
       Name   Version  Catalogs    Result
       slack  <the MSI's own version>  Production  published, NOT verified

   The repository then has the MSI under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions slack` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.pcman.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.pcman.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The version read from the release notes page builds the address and nothing
  else. It is not given to the package tool. The MSI's own ProductVersion may not
  be the text on the page (the address has `<version>.0` in the file name); the
  package tool takes the MSI's own. The first dry run shows it.
- If the pattern finds nothing, the run stops at the first step with a message of
  `URLTextSearcher`. That means the page's text is not in the HTML that AutoPkg
  gets, or its layout changed. Read the page, then correct the recipe.
- If the address of the file answers "not found" or "access denied", the name of
  the file or the version in it is wrong. The page may name a version before its
  installer is on the server. This is the case now, for every version since `4.49.81`: see
  the mark at the top.
- Whether the MSI is a per-machine or a per-user install is the installer's own
  property, not read here.
- The size of the file is not known to the writer. The processor waits 30 minutes
  by default (`pcman_timeout`), which is a limit for the copy to the share.
- The recipe's `NAME` is `Slack` and `PCMAN_TEMPLATE` is `slack`. Change
  the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that the Description of the three recipes
and the top of this README say that the pair is NOT WORKING (expected) and that the download is
not verified, that a real run is refused, that this README states no hash, that every
argument is an input that the shared processor declares, that the pattern that reads the version
matches `Slack 4.41.105` and outputs the group `version`, and does not match `Slack 4.41`,
that the address of the file has the version in it and ends in `.msi`, that the download
refuses a redirect to anything but https (and, with the local `curl`, that it does), that no recipe sets
`pcman_version` for an MSI, that this README has no `make-override` without
`--override-dir` and runs no recipe by its identifier, and that nothing
site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
