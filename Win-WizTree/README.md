# Win-WizTree

A Windows recipe pair: WizTree, the Windows `.exe` installer, the current release from the publisher's own download page, with the version label taken from the file's name.

**Status. New and not rehearsed: nothing of this folder has run under AutoPkg, no installer was downloaded, nothing was imported and nothing was installed on a PC. LICENCE: WizTree is free for personal use only. The publisher's download page, read on 2026-11-13, says of the free version "Personal use only" and "Commercial use not allowed", and sells a Supporter licence priced by the number of staff and an Enterprise licence. Whether a school or its IT staff need a licence is the owner's question, to settle before the item goes into any manifest. The facts of the source were read by the writer on 2026-11-13 from `https://diskanalyzer.com/download` (read only). READ: (1) the page answers 200 without a redirect, the same page with a browser's user agent, with curl's own and with the processor's (`autopkg-WizTreeInfoProvider`); (2) near its top it has exactly one link to the installer, the relative address `files/wiztree_<numbers joined by underscores>_setup.exe` (the release of 16 September 2026 was `files/wiztree_4_33_setup.exe`), and one link to the portable `.zip` of the same release (`files/wiztree_<numbers>_portable.zip`); the page has `<base href="/">`, so the installer's address is `https://diskanalyzer.com/files/<file name>`; (3) each of the two links is one `<a>` element whose content holds the release (`V 4.33`, the date and the size, with `&nbsp;` between them) and a `<div class="shacopy">` with the SHA-256 of that file in full twice, in its attribute `data-sha` and in its title (`SHA-256: <64 hex digits> (click to copy)`), while its text shows only the first and last eight digits; so the hash belongs to a file by sitting inside that file's link; (4) the history of releases further down the page is text only (headings from `WizTree 4.33` down to `WizTree 3.33`), with no link to an installer; one entry names an old installer's file name inside a `<samp>`, not as a link; older installers are on another page of the site, which the processor does not read; (5) a HEAD request for `https://diskanalyzer.com/files/wiztree_4_33_setup.exe` was answered with a redirect (301) to the publisher's content delivery host, `antibodysoftware-17031.kxcdn.com`, same path; that host was not asked; (6) the page's history (the entry of 4.14, June 2023) gives the installer's command line for a silent install: `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-`, with `/DIR=`, `/MERGETASKS=!desktopicon` and the vendor's own `/runasadmin=`, `/checkforupdates=` and `/supportercode=`; those are the switches of an Inno Setup installer, but that the installer is one was NOT read from the file. NOT established: that the switches install silently on a PC (NOT tested); the install path (the page says only that the installed program lives under "Program Files"); whether the installer has a version resource; the version that the installed program reports about itself and whether it is written as the label is; whether the publisher ever replaces a file under the same name (see "The version label"); that the publisher keeps this page's layout for the next release; any run under AutoPkg; any install on a PC. The excerpt of the tests is lines cut unchanged from the real page of 2026-11-13. An install on a test PC is the check of what is NOT established, and the first dry run (step c) of what is still not known. When a run fails, stop. A failure of the processor or of the hash check writes nothing, and the run is a dry run until the owner switches a real run on. Read the real page again, correct the processor or the recipe, and only then touch the trust information: never accept a trust change to make a failing run go through. If the run shows a redirect for the page, stop and tell the owner: the site has changed, and the processor refuses a page read from another address on purpose. Where a line below says "expected", it is what the code leads to, not something that was printed. Every override command here carries `--override-dir`: see the paragraph "Run every override with `--override-dir`" below.**

**Results of 2026-11-13, newer than the status above; where the two differ, this paragraph holds.** Under AutoPkg 2.9.0, into a scratch Cimian repository with a hand-made first pkginfo of the item (`make-override` with `--override-dir`, `verify-trust-info` OK, a dry run, a real run, a second real run): the real run published `wiztree-4.33.exe`, and the second run said that nothing is new. The installer was NOT run on a PC: the vendor's page says that the free version is for personal use, and that question is open.

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `WizTree-Win.download.recipe` | `com.github.serrc-techops.download.WizTree-Win` | Reads the publisher's download page, takes the one installer link and the SHA-256 inside it, downloads the file, and stops when the file does not match that SHA-256. The provider sets `version` to the label from the file's name |
| `WizTree.cimian.recipe` | `com.github.serrc-techops.cimian.WizTree` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new. It passes the label (`%version%`) |
| `WizTree.pcman.recipe` | `com.github.serrc-techops.pcman.WizTree` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new. It passes the label (`%version%`) |

**Three recipes.** The download recipe is the parent of both of the others. `WizTree.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `WizTree.pcman.recipe` is the package tool's way, with `PcmanImporter`. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

The processor `WizTreeInfoProvider.py` is in this folder. It reads the page
`https://diskanalyzer.com/download` and its links. It requires **exactly one link**
whose address names a WizTree `.exe` (any address with `wiztree` and `.exe` in it, in any
case), and that link must be exactly
`files/wiztree_<two to four numbers joined by underscores>_setup.exe`: a second such
link (an old release, say) stops the run, and so does one in another form (an absolute
address, another folder, a query). It then reads the content of that `<a>` element up to its own
`</a>`, which must hold no other `<a>`, exactly one `data-sha="<64 hex digits>"` and no
other 64-digit hex number than that one (the title repeats it). The hash of the portable
`.zip` sits inside the other link and is never read; the history of releases has no link
and cannot be taken. Last, the same content must hold exactly one release text
`V <numbers and dots>`, and it must be the label of the file name. It outputs `url`
(`https://diskanalyzer.com/files/<the file name>`), `version` (the label) and
`expected_sha256`.

The request goes to one fixed address over https, follows no redirect, has a size limit
(512 KiB) and a time limit of 120 seconds. The processor has no input. It never
guesses: a page that is not what it expects is an error.

The other processors are in `../Win-SharedProcessors/` (`CimianImporter` and
`ChecksumVerifier`) and `../Win-PcmanProcessors/` (`PcmanImporter`); see their READMEs.
Neither recipe stops on an unchanged download, so an import that failed is tried again
at the next run.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What the checks prove

- **The hash.** The hash and the file come from the same publisher: the hash from its
  page on `diskanalyzer.com`, the file from the address that page names, which the
  publisher's site redirects to its content delivery host. The check shows that the
  downloaded file is the one whose hash the page gave at the moment the page was read,
  so a damaged download or a file changed on the delivery host alone is caught. It does
  NOT help if the publisher's site itself is changed: whoever can change the page can
  change the hash with the file. No signature of the file (Authenticode) is checked; that
  the file is signed was not read.
- **The installer, not the zip.** The hash is taken only from inside the installer's own
  link, never from the portable `.zip`'s, and the run stops unless that link holds exactly
  one hash.
- **The label.** The label is the publisher's word in the file name, checked against the
  release text of the same link. It is not read from the file: see "The version label".

## The version label

The installer is an `.exe`, so the recipes pass the label on: the pcman recipe to the
package tool (`pcman_version` is `%version%`), the cimian recipe to `CimianImporter`
(`version` is `%version%`); neither tool reads a version from an EXE. The label is made by
the processor from the file's name: the numbers between `wiztree_` and `_setup.exe`, with
dots for the underscores (`wiztree_4_33_setup.exe` gives `4.33`). It is kept exactly as
the name gives it: a leading zero stays. No step reads a version resource of the file:
whether the installer has one was NOT read.

**What the label is not.** It is not what the installed program says about itself: that
is NOT established, because nobody has installed the program. The publisher sets the
number in the name, and the label is only as good as that word.

**How the publisher numbers its releases** (the history on the page, read on 2026-11-13,
from 3.33 to 4.33): a major number and a minor of always two digits: 4.00, 4.01, ... 4.09,
then 4.10, and on to 4.33; 3.41 was followed by 4.00. Once a fix release had four numbers
(the release of 4.14 of 5 June 2023 was followed the next day by one of four numbers that
start with 4 and 14); the file name of that fix was not read. The Cimian client compares
the parts of a version as numbers (`CatalogService.CompareVersions` and `ParseVersionPart`
of `cli/managedsoftwareupdate/Services`, read at commit `3cf02c4` of `windowsadmins/cimian`
on 2026-10-04 for the BambuStudio folder of this repository, and not read again for this
one), so a part `09` is 9 and `10` is 10: 4.09 comes before 4.10, and 4.33 after 4.04.
That order is right only while the publisher keeps writing the minor with two digits: a
release written `4.4` after `4.33` would be ordered before it. The history shows no such
case. A label of two parts meets neither of the client's rules that read a label as a
build time (a first part that is a year of four digits; exactly three parts). Whether the
package tool and the importer take a label of two parts was not tried: the first dry run
shows it.

**Open: does the publisher replace a file under the same name?** The fix of June 2023
says that people who had downloaded 4.14 should download it again; whether that fix had
a new file name or replaced the old file was not read. If a file is replaced under the
same name, the label does not change, and the importers answer "Nothing new" for a file
whose hash differs. A person compares the hash of the first dry run with the repository's
when the page shows a new date for the same version.

The first dry run (with `-v`) prints the processor's lines `Current installer: ... (label
...)` and `Page's SHA-256: ...`. **Read them first**, and compare the label with what the
installed program shows on a test PC (its About box, or Apps & features). If they differ,
stop and tell the owner: a label that the client orders wrongly would hide a newer version
or offer an older one.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01 with another recipe of this repository: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `WizTree.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `StatusService.cs:194-219`) are from `windowsadmins/cimian` at commit `e10498b`, read on 2026-10-04 for other folders of this repository and not checked against a later version.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **The version label** needs no program: the download recipe's processor takes it from the installer's file name, and this recipe passes it on as `%version%`.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `wiztree`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: the switches that the publisher's page gives (see the status line) were NOT tested, so they are left for a person who tries them on a test PC. A licence key (`/supportercode=`) never goes into this public repository: if the owner buys a licence, it belongs to the owner's own pkginfo. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i WizTree-Win
    autopkg list-recipes | grep -i WizTree.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> WizTree.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `WizTree.cimian`, not a path. It writes `<the Windows overrides folder>/WizTree.cimian.recipe` with the identifier `local.cimian.WizTree` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.WizTree`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the lines of the processor are printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WizTree.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.WizTree`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

Only after the owner has settled the licence question (see the status line):

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/WizTree.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WizTree.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WizTree.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WizTree.cimian.recipe

   Expected: `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WizTree.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WizTree.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `WizTree.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `WizTree.pcman`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool.

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
   installer are in the repository. The command, in the form used for the other EXE
   items of this repository (NOT run for WizTree), with a real installer that a person
   has downloaded and checked against the page's hash:

       pcman import <path of the installer> --name wiztree --version <label> \
           --display-name "WizTree" --category <the category> \
           --developer "Antibody Software" --description "<the description>" \
           --directory <the folder of the item> \
           --install-arguments <the silent arguments> --architectures x64 \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   `--version <label>` is for an EXE only, and the label is the one that step c will
   show (see "The version label"). **Still to fill in, each after a test on a PC:** the
   silent arguments (the publisher's page gives `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-`;
   NOT tested), the architecture (the page names one installer for 32 and 64 bit Windows;
   what it installs on a 64-bit PC was not read, so `x64` is an expectation) and the install
   path (not read; without it the template has NO install check, and a wrong path would
   install again at every run, so add it only after reading it on a PC). A licence key
   never goes into this public repository. A person changes the template later; nothing
   else does. **If the template is made from the installer that is current on the page,
   the first run says "Nothing new" (see step c).** The page links only the current
   release; an older installer is on another page of the site, which this folder did not read.

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i WizTree-Win
    autopkg list-recipes | grep -i WizTree.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> WizTree.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `WizTree.pcman`, not a path. It writes
`<the Windows overrides folder>/WizTree.pcman.recipe` with the identifier
`local.pcman.WizTree` and the trust information of the two recipes and the three
processors that are not part of AutoPkg itself (`WizTreeInfoProvider`, `ChecksumVerifier`,
`PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.WizTree`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the
lines of the processor are printed (`-v` prints what each processor says about its own
work; `-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the
repository among them, and such a log would have to be kept private):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WizTree.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.WizTree`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

This is the first check of every fact in the status line. The run may stop before the
dry run, and that is the check working:

- **The processor stops** (`WizTree download page: ...`): the page is not what the
  processor expects (no installer link, two of them, a link in another form, a hash that
  is not exactly one inside the link, or a release text that is not the file name's).
  Nothing was written. Read the real page and correct the processor.
- **The server answers a redirect for the page**: stop and tell the owner (see the status line).
- **`ChecksumVerifier` stops**: the downloaded file is not the one whose hash the page
  gave. Nothing was written. Run again later (the page may have changed between the two
  requests); if it stops again, tell the owner.
- **The package tool refuses the label**: see "The version label".

Expected when everything holds and the current version is not yet in the repository
(the lines are what the shared processor prints; no real run has been seen):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name     Version  Catalogs    Result
    wiztree  <label>  Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: wiztree <label> is in the repository already. Nothing was written.`
instead. That is correct. **Read the label in that line and compare it with the version that the
installed program shows** (see "The version label").

## d. Switch a real run on

Only after the owner has settled the licence question (see the status line):

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/WizTree.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WizTree.pcman.recipe

The trust check should still report OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WizTree.pcman.recipe

   Expected: `Published wiztree <label>.` and a table of the published version
   with the result `published`. The repository then has the installer and the pkginfo of
   the new version. The item file of the template is not changed.

2. `pcman versions wiztree` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Not run for this program. The package tool prints "nothing to run" when
   its catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WizTree.pcman.recipe

   Expected: `Nothing new: wiztree <label> is in the repository already.
   Nothing was written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WizTree.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WizTree.pcman.recipe

## g. A share that is not mounted

The recipe fails (exit code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing is written. Mount the share, then run again. (The shared processors'
tests show this failure; it was NOT seen on this program.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The page links only the current release. There is no input for a line of releases.
- A file name, a link or a hash that is not of the expected form is an error, never a
  guess. The portable `.zip`, the macOS `.dmg` and the history of releases are not the
  installer and are never taken.
  The checksum step sets `checksum_verified` and the hash `checksum_sha256`, which
  the shared importers compare with the file they import, so a real run of this recipe
  needs no `pcman_allow_unverified` or `cimian_allow_unverified`.
- The recipe's `NAME` is `WizTree`, `PCMAN_TEMPLATE` and `CIMIAN_NAME` are `wiztree`.
  Change them in the override's `Input`, not in the recipe.
- `-p` (a local file instead of the download) fails the checksum unless the file is
  the one whose hash the page gives.
- The page also offers the program through `winget` (`AntibodySoftware.WizTree`); this
  folder does not use it.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor finds the installer, its label and the hash inside its own
link on the excerpt (`tests/download_page_excerpt.html`, lines cut unchanged from the real
page of 2026-11-13) and refuses every other kind of page (made-up pages), that the three
recipes are property lists, that every argument is an input that the processor declares,
that both importer recipes pass the label, that this README says what was NOT done, has
no `make-override` without `--override-dir` and runs no recipe by its identifier, and
that nothing site-specific is in the folder.

The tests of this folder also run the `.pcman.recipe` against a stand-in for the package
tool and the `.cimian.recipe` against a temporary Cimian repository (that one needs
PyYAML and is skipped without it).
