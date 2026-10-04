# Win-GoogleDrive

A Windows recipe pair: Google Drive for desktop, the `.exe` installer, with the version label read from the EXE itself.

**Status. NOT rehearsed with AutoPkg. Some facts of the source were fetched by the writer on 2026-10-02: no run of AutoPkg was made, and nothing was written to a repository. Read from Google's server on that day: `https://dl.google.com/drive-file-stream/GoogleDriveSetup.exe` answered 200 with no redirect, 291173528 bytes, last modified 2026-10-01 14:26 GMT; the address holds no version, and no hash was found for the file. The real file (291173528 bytes, downloaded from that address) was also read with `WindowsExeVersion` on 2026-10-02: it has a version resource, `exe_product_version` and `exe_file_version` are both the four numbers 131, 0, 2 and 0 joined by dots, the fixed file information holds the same four numbers, `exe_product_name` is `Google Drive`, and so `version` is those four numbers, with no text in them. NOT established: that Google publishes no hash or signature check for this file (the writer saw none and knows of none); that the EXE's own ProductVersion (the four numbers above) equals the version number that Google publishes for Drive; that the package tool has a check of the product for an EXE (for an MSI it refuses another upgrade code); the silent switch of the installer and the path of the installed program (the first import below leaves both as placeholders); the name of the template item (`googledrive` is the proposed name, and the writer did not look whether the repository has an item of that name); that Google's server answers the questions that AutoPkg asks about a changed file (a last-modified date was seen, nothing else was looked at); `pcman catalogs`; any run with AutoPkg. The first run on the build Mac is the check of everything that is NOT established. When it fails, STOP: nothing was written (a run that fails before the import writes nothing). Read the real address in a browser, and the file's properties on a Windows PC, correct the recipe, and only then look at the trust information. Never accept new trust information first to make a failure go away.**

**Not verified. The download is NOT verified: Google publishes no hash for the file, and a check of the signature is not built. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true. Do not set it before the signature check exists. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template googledrive --version <label>` (the label of an EXE: see "The label" below). A real run of this recipe has NOT been run by anyone, not against a share and not on a PC, and neither has a dry run. `pcman catalogs` was NOT run either. The Windows overrides folder is not one of AutoPkg's override folders, so every override command here carries `--override-dir`: see the paragraph below.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `GoogleDrive-Win.download.recipe` | `com.github.serrc-techops.download.GoogleDrive-Win` | Downloads the Google Drive for desktop installer that Google serves at a fixed address (an EXE), kept under the file name of the address, and reads its version from the file itself (`WindowsExeVersion`). It has no hard check |
| `GoogleDrive.cimian.recipe` | `com.github.serrc-techops.cimian.GoogleDrive` | Parent: the download recipe. Hands the file and its label to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

The steps of the download recipe are `URLDownloader`, `EndOfCheckPhase` and then
`WindowsExeVersion`, which is a shared processor: it reads the ProductVersion of the
downloaded EXE and outputs it as `version`, and the cimian recipe passes that as the
package tool's `pcman_version`. How the processor reads the file and which string it
takes is in the README of `../Win-SharedProcessors/`.

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (see its
README).

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What protects, and what does not

Nothing proves that the downloaded file is what Google published: there is no vendor
hash, and a signature check is not built. The shared importer knows this: no step of
the recipe sets `checksum_verified` with the hash of the file, so a real run is refused
before the package tool starts. What remains does not replace a verification.

- **The label.** An EXE has no version that the package tool can read for itself, so
  the recipe passes the label that `WindowsExeVersion` read from the file. That is data
  in the file: it shows what the file claims, and proves nothing about where the file
  came from. The label must equal what a person reads in the file's properties (the
  Details tab of a Windows PC); the first dry run shows it.
- **The same product.** For an MSI the package tool refuses a different upgrade code.
  Whether it has an equivalent check for an EXE was NOT established by the writer. For
  this recipe the checks are the dry run and a person's look at what it plans.

A file of another product, or with other content (a changed file of the vendor, or a
changed download on the way), could pass these checks.

## The label

The processor prints, when the run is verbose (`-v`), a line with the file's name, its
`ProductVersion`, its fixed version numbers and its `FileVersion`, and a second line,
`version is ..., taken from ...`. It takes the ProductVersion string when that is
numbers and dots only, else the four numbers of the fixed file information. Read both
lines at the first dry run and compare them with the file's properties on a Windows PC.
If the processor stops (no version resource, a file that is not a PE file), the run fails,
nothing is written, and the file is not what the recipe expects: read it before anything
else.

## The label is the installer's version, and nothing compares it with the product's

**The label that the package tool gets is the `ProductVersion` of the downloaded setup file
(`GoogleDriveSetup.exe`), and not the version of Drive for desktop that it installs. No step
of this recipe compares the two, and the recipe has no other version to compare it with: the
address has none, and the recipe reads no other page.** If the setup program stopped
tracking the product, the recipe would still publish under the setup file's number, and that
number orders the versions in the repository. The recipe does not check this at any run. A
person checks it, at the first dry run:

1. Run the dry run with `-v` (step c) and read the line `version is ..., taken from ...`
   of `WindowsExeVersion`. On 2026-10-02 the label was the four numbers 131, 0, 2 and 0
   joined by dots (the ProductVersion string, the FileVersion string and the fixed file
   information agreed).
2. Compare the label with the file's properties on a Windows PC (the Details tab): they
   must agree. Nobody has looked at the properties on a PC.
3. Compare the label with the version that Google gives for the current Drive for desktop
   (Google's release notes for administrators; the writer did not read them), and, after
   the first install on a test PC, with the version that the installed program shows. If
   they do not agree by their numbers, stop and tell the owner before anything is published.
   Nobody has done that comparison.

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
   (the share mounted).

3. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. The template keeps the name of the item that
   it replaces. If the package tool's repository has an item for Google Drive
   already, look at it first: it must be an item for this EXE, and this step is
   not needed; set its name in the override (step b). The command, with a real
   installer:

       pcman import <path of GoogleDriveSetup.exe> --name googledrive \
           --version <the ProductVersion of that file, as its properties show it> \
           --directory <the folder of the item> \
           --install-arguments <the installer's silent switch, read in the vendor's documentation first> \
           --install-path <the path of the installed program, read on one PC after an install> \
           --architectures <the architectures of the installer, NOT read by the writer> \
           --display-name "Google Drive" --category <the category of the item> --developer Google \
           --description "<one line about the item>" --no-prompt --build

   The label after `--version` is the version of the installer as its properties show
   it. For an EXE the package tool is given it; here it is the same text that the recipe
   passes (see "The label"). The install arguments, the install path and the
   architectures are facts of the installer that the writer has NOT read: Google's
   documentation for administrators, and one PC, give them before this command is run.
   A person changes the template later; nothing else does. **If the template is made
   from the installer that is current at the vendor, the first run says "Nothing new"
   (see step c). To see a dry run that would publish, make the template from an older
   installer.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i GoogleDrive-Win
    autopkg list-recipes | grep -i GoogleDrive.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> GoogleDrive.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `GoogleDrive.cimian`, not a path. Expected (not
run for this recipe): it writes `<the Windows overrides folder>/GoogleDrive.cimian.recipe`
with the identifier `local.cimian.GoogleDrive` and the trust information of the two
recipes and of the two processors that are not part of AutoPkg itself
(`WindowsExeVersion`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.GoogleDrive-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleDrive.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.GoogleDrive`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**`-v` prints what each processor says about its own work; `-vv` would add every processor's
inputs and outputs, `pcman_root` and the repository among them, to the log: keep such a log private.** Expected, from
the code and the rehearsals of the other folders, NOT seen for this recipe, when the
current version is not yet in the repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name          Version                   Catalogs    Result
    googledrive   <the label of the EXE>    Production  dry run, nothing written, NOT verified

Before that, the run prints the two lines of the processor (see "The label"). The plan
itself is not printed. The repository is unchanged. If the current version is in the
repository already (the template was made from it), the line is `Nothing new: ... is in
the repository already. Nothing was written.` instead. That is correct.

## d. Switch a real run on (NOT YET: see the second paragraph at the top)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file. Nothing was published. Publish by hand after
    checking the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template googledrive --version <the label>

The label of an EXE is needed: the package tool never takes it from the file (see "The
label"). Then `pcman catalogs` (step e.3).

**Only after the signature check exists, or when a person has decided to accept an
unverified download:** the override allows it. Both lines are needed.

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/GoogleDrive.cimian.recipe
    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_allow_unverified bool true' \
        <the Windows overrides folder>/GoogleDrive.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleDrive.cimian.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip). Do not use `-k`
instead: on the command line it applies to every recipe of that run. A run then prints
`WARNING: published WITHOUT a verified download ...` at any verbosity, and the report's
row says `published, NOT verified`.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleDrive.cimian.recipe

   Only after both lines of step d. Expected: `Published googledrive ...`, the warning
   `published WITHOUT a verified download`, and the table

       The following versions were published by the package tool:
       Name          Version                   Catalogs    Result
       googledrive   <the label of the EXE>    Production  published, NOT verified

   The repository then has the installer under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions googledrive` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleDrive.cimian.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleDrive.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/GoogleDrive.cimian.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- **Drive updates itself on the PCs, so a hosted version sets a floor** (the owner's
  remark of 2026-10-01, made about Chrome and Zoom). A PC that has updated itself is
  newer than the version in the repository. What the Cimian client does with a PC that
  is newer than the hosted version is NOT established here.
- Google replaces the file at the same address without a new address (the file was
  last modified on 2026-10-01 when it was read). AutoPkg asks the server whether the
  file changed; whether this server answers that question is NOT established. If
  every run downloads the whole file, that is the reason. The package tool decides by
  the file's hash and the label.
- If the address answers "not found" or "access denied", Google moved the file. Read
  Google's page for Drive in a browser, then correct the recipe.
- The file is about 290 MB (291173528 bytes on 2026-10-02). The copy to the share is
  the slowest step. The processor waits 30 minutes by default (`pcman_timeout`).
- The downloader keeps the file under the name of the address, `GoogleDriveSetup.exe`.
  The cache therefore holds one file, replaced by each new download.
- Whether the EXE's own ProductVersion is the number that Google's pages call the
  version of Drive is NOT established. The first dry run shows it.
- The recipe's `NAME` is `GoogleDrive` and `PCMAN_TEMPLATE` is `googledrive`. Change
  the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) skips the download. The file is not
  checked at all; the version is still read from it.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that the Description of both recipes
and the top of this README say that the download is not verified, that a real run is
refused, and that nothing was rehearsed and what was fetched, that this README states no
hash, that every argument is an input that the shared processors declare, that the
version step comes after the end of the check phase and the cimian recipe passes its
output as the label, that this README has no `make-override` without `--override-dir`
and runs no recipe by its identifier, and that nothing site-specific is in the folder.
