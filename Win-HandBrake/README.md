# Win-HandBrake

A Windows recipe pair: HandBrake, the x86_64 `.exe` installer of the Windows GUI, with the version label taken from the file's name.

**Status. New and not rehearsed (written 2026-11-13): nothing has run under AutoPkg, no installer was downloaded and nothing was installed on a PC. The Cimian item also needs a `requires` on a Microsoft .NET Desktop Runtime item that this repository has a recipe pair for, `Win-DotNetDesktopRuntime` (run once into a scratch repository on 2026-11-16), and no item yet in any real repository (see "The .NET Desktop Runtime"). READ on 2026-11-13, by the writer, from GitHub's public release list of `HandBrake/HandBrake` (`https://api.github.com/repos/HandBrake/HandBrake/releases`, the newest 30 releases; read only, no file was downloaded): (1) the tags are bare versions (`1.11.2`, published 2026-06-07, is the newest release and is not a pre-release); the one pre-release of the list, `1.4.0-beta.1`, has macOS files only; (2) each release of 1.4.1 and later, except 1.6.0, has two Windows installers, `HandBrake-<version>-x86_64-Win_GUI.exe` (25331264 bytes in `1.11.2`) and `HandBrake-<version>-arm64-Win_GUI.exe` (21 of the 30 releases have the arm64 one), and each of the 29 non-pre-releases has a `.zip` build of the x86_64 GUI and a CLI archive (`HandBrakeCLI-<version>-win-x86_64.zip`), the newer ones `LibHB-...` archives, and almost every file has a `.sig` file beside it (`1.2.1`'s GUI `.zip` has none); the pattern takes none of these and nobody opened them; (3) the pattern is `HandBrake-([0-9]+(?:\.[0-9]+)+)-x86_64-Win_GUI\.exe$`, which takes exactly one file in each of the 29 releases that have a Windows installer, the x86_64 installer, and none in the pre-release, and its one group is the label; (4) the label equals the release tag in every one of those 29 releases, so the first dry run has nothing to say about a difference; (5) GitHub records a SHA-256 digest for the installers of `1.10.0` (2025-08-09) and later and for none of `1.9.2` and older, so `GitHubAssetDigest` finds one for the release that the recipe takes. **The label is taken from the file's name by `VersionFromName` as a precaution, not as a finding:** whether the installer has a version resource (RT_VERSION) was NOT read, because no file was downloaded, so `WindowsExeVersion` was not chosen; the project sets the number in the name, and it equals the tag in every release of the list. NOT established: that the installer is an NSIS installer, that `/S` installs it silently, and that its uninstaller is `uninst.exe /S` in the install folder (third-party packaging guides say so; the writer did not read the vendor's own word and tested nothing); the install path and the architecture of the installed program; that the installer does not bring the .NET Desktop Runtime; the version that the installed program reports about itself; that the next release keeps this spelling of the name (if the project renames the file, the provider goes back to the newest older release that matches: read the line of the first dry run that names the selected asset and release); the Cimian client's order of the label; any run with AutoPkg; any install on a PC. An install on a test PC is the check of each of them. When a run fails, stop. Nothing was written. Read the real release page or the real release, and correct the recipe. Never change the trust information first.**

**Results of 2026-11-13, newer than the status above; where the two differ, this paragraph holds.** Under AutoPkg 2.9.0, into a scratch Cimian repository with a hand-made first pkginfo of the item (`make-override` with `--override-dir`, `verify-trust-info` OK, a dry run, a real run, a second real run): the real run published `handbrake-1.11.2.exe`, and the second run said that nothing is new. On one Windows 11 test PC, as SYSTEM from a scheduled task, `<file> /S` ended with exit code 0 after 9 seconds; the file's signature was valid (Open Source Developer, Scott Rae); the PC then listed `HandBrake 1.11.2` with DisplayVersion `1.11.2` (in the 32-bit view of the registry), installed in `C:\Program Files\HandBrake`, uninstall string `C:\Program Files\HandBrake\uninst.exe`. The EXE has no version resource. The PC had no .NET desktop runtime, and the installer did not stop for it; whether HandBrake starts without it was not tested. The program was not started, an upgrade over an older version and the uninstall were not tested, and no Cimian client installed it.

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `HandBrake-Win.download.recipe` | `com.github.serrc-techops.download.HandBrake-Win` | Takes the newest non-pre-release of `HandBrake/HandBrake` on GitHub that has a file matching `SEARCH_PATTERN`. Downloads it under its own file name. Reads the SHA-256 that GitHub records for the file and stops when the file does not match. Last, takes the version label from the file's name (`VersionFromName`: the one group of `SEARCH_PATTERN`, checked for its shape) and sets `version` to it |
| `HandBrake.cimian.recipe` | `com.github.serrc-techops.cimian.HandBrake` | Parent: the download recipe. Hands the file to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository (a copy of the repository's newest pkginfo of the item, with what belongs to the installer file replaced), or says that nothing is new. It passes the version label that the download recipe took from the file's name (`%version%`) |
| `HandBrake.pcman.recipe` | `com.github.serrc-techops.pcman.HandBrake` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new. It passes the version label that the download recipe took from the file's name (`%version%`) |

## The .NET Desktop Runtime

**HandBrake's Windows GUI needs Microsoft's .NET Desktop Runtime, and this repository has a recipe pair for it (`Win-DotNetDesktopRuntime`, run once into a scratch repository on 2026-11-16) and no item yet in any real repository. Do not publish this program to PCs until the runtime item is there.** READ on 2026-11-16, from the GitHub release of the tag `1.11.2`: HandBrake 1.11.2's own release notes name ".NET Desktop Runtime version 10.0" and link `https://aka.ms/dotnet/10.0/windowsdesktop-runtime-win-x64.exe`. Third-party packaging guides had said 8.0 (x64); the vendor's own notes govern for this release, and a person reads them again for each release. NOT read: the runtime version of any release other than `1.11.2`, and whether the installer brings the runtime itself. As far as is known it does not, silently; that is NOT established. On 2026-11-16, on one Windows 11 test PC, the runtime installer (`/install /quiet /norestart`, as SYSTEM) ended with exit code 0, and HandBrake `1.11.2`, started as SYSTEM afterwards, was still running after 40 seconds with no dialog window seen; that is weak evidence only (no window of it would be seen in session 0 either), not proof that HandBrake works. So the Cimian item needs a `requires` on a .NET Desktop Runtime item of the right version. The item is made by the recipe pair of `../Win-DotNetDesktopRuntime/` (its default channel is 10.0), and the `requires` is then added by a person to the template item (see "What a person completes by hand for an `.exe`"). Until then an install of this item on a PC that has no runtime may succeed and the program may not start.

**Three recipes.** The download recipe is the parent of both of the others. `HandBrake.cimian.recipe` is for any Cimian repository: its last step is `CimianImporter`, and no other tool is needed. `HandBrake.pcman.recipe` is the package tool's way, with `PcmanImporter`: it is what the `.cimian.recipe` was before the processors were separated from the package tool. The section "With any Cimian repository" comes first below, then "With the package tool (pcman)".

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter` and the checks) and `../Win-PcmanProcessors/` (`PcmanImporter`, for the package tool); see their READMEs.

**Pre-releases.** The download recipe takes the newest release that GitHub does not
flag as a pre-release. The switch is the key `include_prereleases` in the recipe's
`Input`, a boolean that is `false`; `make-override` copies it into the override. To take
pre-releases as well, set it to true in the override, never in the recipe:

    /usr/libexec/PlistBuddy -c 'Set :Input:include_prereleases true' \
        <the Windows overrides folder>/HandBrake.cimian.recipe

(For an override that was made before this key existed, use
`Add :Input:include_prereleases bool true` instead.) Keep it a boolean: AutoPkg only
tests whether the value is empty, so the text `false` would count as true. The recipe's
step does not set it, because AutoPkg applies the arguments of a step after the
override's `Input`, and they would beat it.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## The version label

The installer is an `.exe`, so the recipes pass the label on: the pcman recipe to the package tool
(`pcman_version` is `%version%`), the cimian recipe to `CimianImporter` (`version` is `%version%`); neither tool reads a version from an EXE. Whether this installer has a version resource of its own was NOT read (no file was downloaded). So the label is the version in the file's name, which is a precaution and not a finding. AutoPkg makes `version` from the
release tag first, and the last step of the download recipe, `VersionFromName` (shared, see its
section in the shared README), matches the downloaded file's name with `SEARCH_PATTERN`, whose
one group is the label, checks that the group is two to four numbers joined by dots, and
overwrites `version` with it. In every release of the list that was read the label equals the tag (see the status line), so the tag would have given the same text; the file's name is used because it belongs to the file, and the tag belongs to the release.

**What the label is not.** It is not read from the file (nothing was opened), and it is not
what the installed program says about itself: that is NOT established, because nobody has
installed the program. The project sets the number in the name, and the label is only as good as
that word. If the installer does have a version resource, `WindowsExeVersion` could read it instead: that is for the owner to decide after reading the file.

Two questions are open:

- **Open: does the package tool accept this label?** The label has three parts and no leading zero; what the package tool says to it has NOT been seen, and the first dry run shows it.
- **Open: does the Cimian client order that label as the program's own version?** It compares the parts
  of a version as numbers (`int.TryParse` in `CatalogService.CompareVersions`,
  `CatalogService.cs:260-292`, and `ParseVersionPart`, `:374-389`, of `cli/managedsoftwareupdate/Services`; `long.TryParse`
  in `VersionService.ParseVersion` of `shared/core`; these lines were read at commit `3cf02c4` of `windowsadmins/cimian` on 2026-10-04 for another program, a second reader found the same code at `e10498b`, and nobody read them again for this one). The client has a rule that reads a label of exactly three parts, `yy.M.ddHH`, with `yy` from 20 to 99, a month from 1 to 12 and a third part of three or four digits, as a build time (`CatalogService.ExpandBuildTimestamp`). This label has three parts, and its first part, 1, is below 20, so by that description the rule would not take it; nobody has run the client on it, and nobody has checked what happens if a later HandBrake version has a first part of 20 or more. What the program itself shows has still to be compared with the label, on a PC after
  a hand install (its About box, or Apps & features). If the numbers differ, stop and tell the owner: a label that the
  client orders wrongly would hide a newer version or offer an older one.

The first dry run (with `-v`) prints the lines of the provider that name the selected asset and
release (`Selected asset ... from release ...`) and one line from the label step: `version is ...,
taken from the file name ...`. **Read them first**: the selected release must be the newest that
is not a pre-release (see the status line for why).

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** (Seen with AutoPkg 2.9.0 on 2026-10-01: `verify-trust-info` without the option said "No trust information present" for an override that has it.)

As an alternative the operator may set the AutoPkg preference `FAIL_RECIPES_WITHOUT_TRUST_INFO` to true: then any recipe without verified trust information fails. It is not set on the build machine today, and it would also change how the Mac recipes run, so it is the owner's decision.

## With any Cimian repository

This way needs AutoPkg and nothing of the owner's: no package tool. It uses `HandBrake.cimian.recipe` and the processor `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

**Line numbers.** A file and a line of the Cimian client that this section names (for example `InstallerService.cs:936`) are from `windowsadmins/cimian` at commit `e10498b`, read on 2026-10-04 for another program of this repository and not read again for this one or checked against a later version.

### 1. What must exist first

1. **The recipe repository is added to AutoPkg**, so that its folders are in AutoPkg's search directories:

       autopkg repo-add <the URL of the recipe repository>

   This matters because `make-override` (step 2) takes a recipe NAME and refuses a path.

2. **The repository's root, as an AutoPkg preference** (or later in the override):

       defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"

   The root is the folder that has `pkgs/` and `pkgsinfo/`. Write the value as a string. The share must be mounted;
   `CimianImporter` never makes the root, `pkgs/` or `pkgsinfo/`. The input is named `cimian_repo`; the preference is the one name in upper case.

3. **The version label** needs no program: the download recipe's step `VersionFromName` takes it from the installer's file name, and this recipe passes it on as `%version%`.

4. **The item.** The item's name is the recipe's input `CIMIAN_NAME`, `handbrake`. If the repository has an item of that name, its newest pkginfo (by the client's order of versions) is the template: nothing is to be made, and its catalogs, arguments, scripts and checks are carried into the new version. The recipe's `pkginfo` does not change a template: a key that the template lacks is added, a key that the template has with another value keeps the template's, and a NOTE names each (the display name of the recipe does not rename an item that has another). `cimian_pkginfo_wins` set to true in the override lets the recipe's `pkginfo` win instead, for example `pkginfo: {catalogs: [Testing]}` to put new versions into another catalog first. If it has no item of that name, the first real run builds a pkginfo from the recipe's `pkginfo` (the display name and the developer) and the inputs, in the catalog `Development`; that pkginfo is then the template of every later version. If the repository has pkginfo files of the item for several architectures, the run stops until the override gives `cimian_architecture` (for example `x64`).

   **What a person completes by hand for an `.exe`, in the override's `pkginfo`:** the requirement on a .NET Desktop Runtime item (a `requires` list: see "The .NET Desktop Runtime"; the recipe pair that makes the item ran only into a scratch repository, so no item exists in a real one yet), the silent arguments (`installer: {args: [...]}`; `args` is the key the client reads, `UpdateModels.cs:772-773`) and an install check (`installs`, or `check`), because without a check the client treats the item as not installed unless the ManagedInstalls registry has a trace of it (`StatusService.cs:194-219` and `:268-298`). The recipe's `pkginfo` does NOT give the silent arguments: this folder's README does not establish them (the first step of the package tool's way below marks what is only the writer's knowledge or was not read), so they are left for a person who has read them in the vendor's documentation and tried them on a test PC. The run says in a WARNING that the pkginfo has no install check.

### 2. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

    autopkg list-recipes | grep -i HandBrake-Win
    autopkg list-recipes | grep -i HandBrake.cimian

Each name must be listed once, from this repository. (Not run: the lines of the output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> HandBrake.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides folder, and a nightly script that runs every override there would run it too.** The command takes the recipe's name, `HandBrake.cimian`, not a path. It writes `<the Windows overrides folder>/HandBrake.cimian.recipe` with the identifier `local.cimian.HandBrake` and the trust information of the recipes and the processors. **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.HandBrake`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value means that AutoPkg found another recipe of the same name. The override's `Input` now has `CIMIAN_NAME`, `CIMIAN_SUBDIRECTORY` and `pkginfo`: set `CIMIAN_NAME` to the name of the repository's item if it differs, and `CIMIAN_SUBDIRECTORY` only to put new files in another folder (empty: the folder of the template's installer, else directly under `pkgs/`).

### 3. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the lines of the provider and of the label step are printed:

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/HandBrake.cimian.recipe

**Why by path:** the recipe's name or identifier (`com.github.serrc-techops.cimian.HandBrake`) runs the recipe itself, not the override. The recipe itself never leaves the dry run, so the real run of step 5 would never happen.

Expected, also without `-v` (the lines that `CimianImporter` prints, read in its code and tests; NOT seen from a run with AutoPkg; AutoPkg puts the processor's name and a colon before each):

    WARNING: DRY RUN. Nothing was written, because cimian_dry_run is on. Set cimian_dry_run to false in the override for a real run.
    Would write <CIMIAN_NAME> <version>: pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml and pkgs/<the item's folder>/<CIMIAN_NAME>-<version>.exe (<size> bytes).
    Template: <CIMIAN_NAME> <the newest version in the repository> (pkgsinfo/<the item's folder>/...).

followed by the NOTE and WARNING lines about what is carried from the template, and at the end the report row with the result `dry run, nothing written`. The plan itself (the pkginfo's text) is not printed. The repository is unchanged. If the repository has this version already, the line is `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.` instead. That is correct. If the repository has no item of this name, the second line is `No template: the pkginfo is built from the inputs.`

If the run stops before this, with an error from the download recipe's steps, nothing was written: read the error, and correct the recipe, never the trust information first.

### 4. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
        <the Windows overrides folder>/HandBrake.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/HandBrake.cimian.recipe

The trust check still reports OK: a change of the `Input` does not break trust. Do not use `-k cimian_dry_run=false` instead: on the command line it applies to every recipe of that run.

### 5. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/HandBrake.cimian.recipe

   Expected: `Published <CIMIAN_NAME> <version> (pkgsinfo/<the item's folder>/<CIMIAN_NAME>-<version>.yaml). Build the catalogs with makecatalogs.` and a report row with the result `published`. The repository now has the installer under `pkgs/` (copied beside its place, checked against the SHA-256 that was verified, and moved into place), then the pkginfo under `pkgsinfo/`. Neither file replaces another: a file that is there already stops the run. (Where the share does not allow hard links the check and the rename are two steps: do not run two runs of one item at the same time.)

2. **Build the catalogs with Cimian's `makecatalogs`** against the repository (`CimianImporter` does not do it; see Cimian's documentation for how it is run). Without it no PC sees the new version. (Not run.)

3. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/HandBrake.cimian.recipe

   It prints `Nothing new: <CIMIAN_NAME> <version> is in the repository already (it has this version). Nothing was written.`

### 6. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/HandBrake.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/HandBrake.cimian.recipe

### A share that is not mounted

`CimianImporter` stops with `The Cimian repository is not a folder: ... Is the share mounted?` (or, for a folder without `pkgs/` or `pkgsinfo/`, `The Cimian repository is not complete`) before it reads or writes anything. Mount the share, then run again.

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**; it uses `HandBrake.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. Everything below up to "Other facts" is about it, and its commands name `HandBrake.pcman` where this README used to say `HandBrake.cimian`. The recipe's `PCMAN_TEMPLATE` is the item's name in the package tool. Make the override from `HandBrake.pcman.recipe`: it has `PCMAN_TEMPLATE` in its `Input`, which `HandBrake.cimian.recipe` does not read.

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
   installer are in the repository. The command, in the form that ran for other programs of this
   repository (it has NOT been run for this one), with a real installer that a person has downloaded and checked:

       pcman import <path of the installer> --name handbrake --version <label> \
           --display-name "HandBrake" --category <the category> \
           --developer "The HandBrake Team" --description "<the description>" \
           --directory <the folder of the item> \
           --install-arguments /S --architectures x64 \
           --icon <the file name of an icon that the repository has> --no-prompt --build

   `--version <label>` is for an EXE only, and the label is the one that step c will
   show (see "The version label"). Third-party packaging guides call the installer an NSIS installer with the silent switch `/S`, and say that its
   uninstaller is `uninst.exe /S` in the install folder. **That is the writer's knowledge only: the vendor's own word was not read, the installer was
   not opened and `/S` was not tried on a PC** (the same holds for the uninstaller): read it, and test that the installer installs without a window on a test PC, before the command is run.
   **Still to fill in:** the architecture and the install path. The name says `x86_64`, so `--architectures x64` is an
   expectation, and `--install-path` was left out because the path must be read on a PC after a hand install; the template
   then has no install check, and a wrong path would install again at every run, so add it only after reading it.
   **Also still to fill in: the .NET Desktop Runtime** (see "The .NET Desktop Runtime"): the template needs a requirement on a runtime item, whose recipe pair (`Win-DotNetDesktopRuntime`) ran only into a scratch repository, so no item exists in a real one yet. A person changes the
   template later; nothing else does. **If the template is made from the installer that
   is current on GitHub, the first run says "Nothing new" (see step c). To see a dry run
   that would publish, make the template from an older release.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i HandBrake-Win
    autopkg list-recipes | grep -i HandBrake.pcman

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> HandBrake.pcman

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `HandBrake.pcman`, not a path. It writes
`<the Windows overrides folder>/HandBrake.pcman.recipe` with the identifier
`local.pcman.HandBrake` and the trust information of the two recipes and the five
processors that are not part of AutoPkg itself (`GitHubNewestReleaseGuard`, `GitHubAssetDigest`, `ChecksumVerifier`,
`VersionFromName`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.pcman.HandBrake`**, the identifier of the recipe that the override was made from (AutoPkg writes the identifier of the recipe it found by that name). Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the
lines of the label step are printed (`-v` prints what each processor says about its own
work; `-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the
repository among them, and such a log would have to be kept private):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/HandBrake.pcman.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.pcman.HandBrake`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

This is the first check of every fact in the status line. The run may stop before the
dry run, and that is the check working:

- **No asset matches** (the lines of the provider name the pattern and the release):
  the real asset name is not one that the pattern knows. Read the release's real asset
  list and correct `SEARCH_PATTERN`.
- **`GitHubNewestReleaseGuard` stops** (its message names the selected release, the newest release and the files
  of the newest release): the newest release has a file name that the pattern does not take, and the provider
  went back to an older release. Nothing was written. Correct `SEARCH_PATTERN` in the override's `Input`, or, for a newest release that has no Windows installer on
  purpose (no file ending in `.msi`, `.exe` or `.msix`), accept exactly that release with `accepted_newest_release` in the override.
  The guard is new and has not run under AutoPkg.
- **The run goes on, but with an old release** (the line `Selected asset ... from release ...`
  names a release that is not the newest non-pre-release): the newest one has a name that the
  pattern does not take, and the provider went back to an older one. Stop. The guard now stops this case, so a line that names an old release means that the guard did not run. Correct `SEARCH_PATTERN` before anything is published.
- **`GitHubAssetDigest` stops with its error** (the record has no digest): GitHub
  recorded none for this asset. Nothing was written. The program is a hand import
  until a release with a digest exists.
- **`VersionFromName` stops** (the file's name does not match the pattern, or the number in
  it is not two to four numbers joined by dots): the name is not what the recipe expects.
  Nothing was written. Read the release's real asset list, and import by hand with a label
  that a person has read.
- **The package tool refuses the label**: see "The version label".

Expected when everything holds and the current version is not yet in the repository
(the lines are what the shared processor prints; the real run has not been seen):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name          Version  Catalogs    Result
    handbrake   <label>  Production  dry run, nothing written

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line
is `Nothing new: handbrake <label> is in the repository already. Nothing was written.`
instead. That is correct. **Read the label in that line and compare it with the version that the
installed program shows** (see "The version label").

## d. Switch a real run on

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/HandBrake.pcman.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/HandBrake.pcman.recipe

The trust check should still report OK: a change of the `Input` does not break trust.
Do not use `-k pcman_dry_run=false` instead: on the command line it applies to
every recipe of that run.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/HandBrake.pcman.recipe

   Expected: `Published handbrake <label>.` and a table of the published version
   with the result `published`. The repository then has the installer and the pkginfo of
   the new version. The item file of the template is not changed.

2. `pcman versions handbrake` lists the template and the new version; the new one is
   marked "published by pcman import".

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version. (Not run for this program. The package tool prints "nothing to run" when its catalogs command is not set.)

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/HandBrake.pcman.recipe

   It should print `Nothing new: handbrake <label> is in the repository already.
   Nothing was written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/HandBrake.pcman.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/HandBrake.pcman.recipe

## g. A share that is not mounted

The recipe fails (exit code 70) with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing is written. Mount the share, then run again. (The shared processors'
tests show this failure; it was NOT seen on this program.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The recipe's `NAME` is `HandBrake` and `PCMAN_TEMPLATE` is `handbrake`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) fails the checksum, because the
  digest is the one of the GitHub asset.
- The recipe takes the newest non-pre-release only. A beta that the project marks as a
  pre-release is not downloaded, unless the override sets `include_prereleases` (see
  "Pre-releases" at the top).
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
  Read the `Selected asset` line of every dry run (the run is made with `-v`).

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that every argument is an input
that the shared processor declares, that this README opens with the status line
that says what was not done, has no `make-override` without `--override-dir` and
runs no recipe by its identifier, and that nothing site-specific is in the folder.

The tests of this folder also read the `.cimian.recipe` (its last step is `CimianImporter`, its inputs are the ones above, and nothing of the package tool is in it), the `.pcman.recipe` (what the `.cimian.recipe` was before: the same inputs, with the processor `PcmanProcessors/PcmanImporter`), and run each against a stand-in: the package tool's for the one, a temporary Cimian repository for the other (that one needs PyYAML and is skipped without it).
