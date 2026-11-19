# Win-TeamViewerHost

A Windows recipe set: TeamViewer Host, the 64-bit `.msi`, taken out of the zip of MSI installers that TeamViewer serves.

**Status. The download is NOT verified: TeamViewer publishes no hash for the zip or the MSI, and a check of the signature is not built. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `cimian_allow_unverified` (or `pcman_allow_unverified` for the package tool) to true. Do not set it before a person has checked the file. READ on 2026-11-19, without a login: `https://download.teamviewer.com/download/version_15x/TeamViewer_MSI64.zip` answers 302 to `dl.teamviewer.com`, and the file there is 153,657,245 bytes with `Last-Modified` 2026-11-16. No page of TeamViewer names this address; it is known from third-party packaging scripts. It is not documented by the vendor and may change or stop without notice. READ in that zip: six members, `Full/Manuals/CommandLineParameters.url`, `Full/Manuals/MassDeployment.url`, `Full/TeamViewer_Full.msi`, `Host/Manuals/CommandLineParameters.url`, `Host/Manuals/MassDeployment.url` and `Host/TeamViewer_Host.msi` (58,937,344 bytes). That MSI is x64, ProductName `TeamViewer Host`, ProductVersion `15.83.7(.0)`, UpgradeCode `{82861EC3-25E9-4152-AAA0-BFB2467B60B7}`, ProductCode `{71322D69-066B-4B3A-8FEA-4476C914E7B3}` (only this one version was read), `ALLUSERS=1`. NOT established: any import into a repository, through either importer; an install through a Cimian client; the refusal (error 25001) on a PC that has an install from the vendor's EXE; an upgrade from one version to the next; and that a later version has the same upgrade code.**

**Results of 2026-11-19.** The download recipe ran under AutoPkg 2.9.0 on a Mac: the zip was downloaded, unpacked, and the Host MSI was found (its SHA-256 begins `6f3c7f15`). The first attempt ended with curl error 56 (connection reset by the server); the second went through. On one PC, as SYSTEM, the Host MSI of version `15.83.7(.0)` installed silently with `msiexec /i <file> /qn /norestart` (exit code 0 after 18 seconds) and was removed silently with `msiexec /x <ProductCode> /qn /norestart` (exit code 0 after 38 seconds). After the removal the uninstall entry and the service were gone; the program folder and the settings key, which holds the device's TeamViewer ID, stayed.

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `TeamViewerHost-Win.download.recipe` | `com.github.serrc-techops.download.TeamViewerHost-Win` | Downloads the zip, unpacks it into an emptied folder of the recipe's cache (`Unarchiver`) and names the Host MSI in it (`FileFinder`). It has no hard check |
| `TeamViewerHost.cimian.recipe` | `com.github.serrc-techops.cimian.TeamViewerHost` | Parent: the download recipe. Hands the Host MSI to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository, or says that nothing is new |
| `TeamViewerHost.pcman.recipe` | `com.github.serrc-techops.pcman.TeamViewerHost` | Parent: the download recipe. Hands the Host MSI to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `TeamViewerHost.cimian.recipe` is for any Cimian repository (no other tool is needed); `TeamViewerHost.pcman.recipe` is the package tool's way. The item is named `teamviewer.host` (the inputs `CIMIAN_NAME` and `PCMAN_TEMPLATE`); the override sets the repository's own name if it differs. Below, `pcman` stands for `<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

Neither recipe stops on an unchanged download, so an import that failed is tried again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter`) and `../Win-PcmanProcessors/` (`PcmanImporter`); see their READMEs.

## What the download recipe does

1. `URLDownloader` downloads `DOWNLOAD_URL` as `TeamViewer_MSI64.zip` (`DOWNLOAD_FILENAME`).
2. `EndOfCheckPhase`.
3. `Unarchiver` (part of AutoPkg) unpacks the zip into `<the recipe's cache>/unpacked`. It empties that folder first (`purge_destination`), so an MSI of an earlier run is never imported. It uses Python's own zip code (`USE_PYTHON_NATIVE_EXTRACTOR`; on a Mac AutoPkg would otherwise use `ditto`), which does not make symbolic links. In AutoPkg 2.9.0 and later it also refuses a member whose name would land outside the folder; older versions extract with Python's `zipfile` alone, which drops such parts of a name silently. The whole zip is unpacked, the Full MSI too.
4. `FileFinder` (part of AutoPkg) names the one member `TEAMVIEWER_MSI_MEMBER` (`Host/TeamViewer_Host.msi`) in that folder. Its output `found_filename` is the file that the child recipes give the importer as `pathname`. A zip without that member stops the run at this step with `No matching filename found`; nothing else in the zip is taken instead, and the Full MSI is never imported.

The behaviour of `Unarchiver` and `FileFinder` above is read in the source of AutoPkg 2.9.0 (`Code/autopkglib/Unarchiver.py`, `FileFinder.py`). The good case (the zip unpacked, the Host MSI found) was seen in a run; the stops (a zip without the member, a member outside the folder) were NOT seen in a run.

AutoPkg's option `-p` gives the download step a local file instead of the download: give it the zip, not the MSI. The file is not checked at all.

## What protects, and what does not

Nothing proves that the downloaded file is what TeamViewer published: there is no vendor hash, and a signature check is not built (no processor of this repository checks an Authenticode signature). The shared importer knows this: no step of the recipe sets `checksum_verified` with the hash of the file, so a real run is refused before anything is written. Two checks of the importers remain. They do not replace a verification.

- **The same product.** Once the item exists, the importers refuse an MSI whose upgrade code differs from the template's (`CimianImporter` unless the override sets `cimian_allow_product_change`), so another product cannot be published under its name. On the first import there is no template, and so no upgrade code to compare.
- **The label.** The recipe gives no version label. For an MSI the importers take the MSI's own ProductVersion and refuse a label that is not the MSI's own version.

An MSI of the right product with other content (a changed file of the vendor, or a changed download on the way) would pass both checks.

A pinned SHA-256 of the zip (`ChecksumVerifier`) would not help by itself: both importers accept a checksum only when it is the hash of the file they import, which is the MSI, so a checksum of the zip stops the run. Pinning the zip needs a step that hands the zip's verified hash over to the MSI, as the extractor of `../Win-WindowsAppRuntime/` does for its package.

## What the MSI refuses to install over

Read in the MSI's tables on 2026-11-19 (version `15.83.7(.0)`), not tried on a PC:

- Its `LaunchCondition` table stops the install (error 25001) when one of these is on the PC: a TeamViewer installed from the vendor's EXE as Full 32-bit, Full 64-bit or Host 32-bit; an install from the vendor's EXE of the same or a newer version; a Full MSI (32-bit, 64-bit or ARM64); the ARM64 Host MSI; a newer 32-bit Host MSI.
- Its `Upgrade` table upgrades an older 32-bit Host MSI (UpgradeCode `{150798A5-21DE-431E-BDC7-A822769BE9A2}`) and older versions of itself.

So a PC that has a TeamViewer from the vendor's EXE, or a full client, needs it removed first. **That removal is the job of the item in the repository (the package tool's template item `teamviewer.host`, or the pkginfo that `CimianImporter` copies), not of these recipes.** The recipes only publish the MSI.

Assigning the PC to a TeamViewer company account is not part of this item either. An assignment needs a value of the account that does not belong in a public recipe; whoever runs the item decides how it is done.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** `make-override` takes a recipe NAME and refuses a path, and it needs the same option.

## With any Cimian repository

This way needs AutoPkg, `msiinfo` (msitools: `brew install msitools`) for the MSI, and no package tool. It uses `TeamViewerHost.cimian.recipe` and `CimianImporter` of `../Win-SharedProcessors/` (its README says how the template is chosen, which keys of the pkginfo are replaced, and what a person completes by hand). PyYAML is needed in the Python that runs AutoPkg; AutoPkg's own Python has it.

1. Add the recipe repository (`autopkg repo-add <the URL of the recipe repository>`) and set the Cimian repository's root once: `defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"`. The share must be mounted.

2. First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

       autopkg list-recipes | grep -i TeamViewerHost

   Each name must be listed once, from this repository. Then make the override INTO THE WINDOWS OVERRIDES FOLDER:

       autopkg make-override --override-dir=<the Windows overrides folder> TeamViewerHost.cimian

   **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.TeamViewerHost`.** Another value means that AutoPkg found another recipe of the same name.

3. Check the trust information, then run a dry run, BY PATH (the recipe's identifier runs the recipe itself, which never leaves the dry run):

       autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TeamViewerHost.cimian.recipe

       autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TeamViewerHost.cimian.recipe

   A dry run writes nothing. Expected: the download, `Unarchived ...`, `Found file match: '<...>/unpacked/Host/TeamViewer_Host.msi' ...`, then the importer's `WARNING: DRY RUN` and `WARNING: the download was NOT verified` lines. With no item of that name yet, the line `No template: the pkginfo is built from the inputs.` appears. (These lines are read in the code, NOT seen from a run.)

4. Switch a real run on (NOT YET: only after a person has checked the file). Both lines are needed:

       /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
           <the Windows overrides folder>/TeamViewerHost.cimian.recipe
       /usr/libexec/PlistBuddy -c 'Add :Input:cimian_allow_unverified bool true' \
           <the Windows overrides folder>/TeamViewerHost.cimian.recipe

   A change of the `Input` does not break trust. Do not use `-k` instead: on the command line it applies to every recipe of that run. A run then prints `WARNING: published WITHOUT a verified download`, and the report row says `published, NOT verified`.

5. The real run, by path again, then Cimian's `makecatalogs` (without it no PC sees the new version). A second run must say `Nothing new`:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TeamViewerHost.cimian.recipe

6. When a recipe or a processor changes upstream, the run fails with `Failed local trust verification ... contents differ from expected` and publishes nothing. Look at what changed, then accept it; never do this automatically:

       autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TeamViewerHost.cimian.recipe

**For an `.msi` nothing needs completing for a silent install:** the client runs `msiexec /i <file> /qn /norestart` itself and then the arguments of the item. What the item must do before the install (remove an EXE install or a full client, see above) is the template's business, as are any MSI properties (`installer: {args: [...]}` in the override's `pkginfo`).

## With the package tool (pcman)

This way needs the owner's package tool, `pcman`, which is **not part of this repository**. It uses `TeamViewerHost.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`; the settings `pcman_root` (and `pcman_python` if needed) are AutoPkg preferences, as that folder's README says.

The template item `teamviewer.host` must exist before the first run. It is made once by a first import, from the MSI that a dry run leaves in the recipe's cache (`<the recipe's cache>/unpacked/Host/TeamViewer_Host.msi`), after a person has checked the file. The command (NOT run for this item):

    pcman import <path of the MSI> --name teamviewer.host \
        --directory <the folder of the item> --architectures x64 \
        --display-name "TeamViewer Host" --category <the category of the item> --developer "TeamViewer" \
        --description <one sentence about the item> \
        --icon <the file name of an icon that the repository has> --no-prompt --build

There is no `--version`: the package tool takes the MSI's own version. **The template must then carry the pre-install step that removes a TeamViewer installed from the vendor's EXE, or a full client, before the MSI runs** (see "What the MSI refuses to install over"); a person adds it to the template in the package tool. The recipe does not.

For every later version a person can import by hand after checking the file; the command uses the template, so it makes no second item:

    pcman import <the file> --template teamviewer.host

Do not add `--version` for an MSI: the package tool takes the MSI's own version. Then:

    autopkg make-override --override-dir=<the Windows overrides folder> TeamViewerHost.pcman

**Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.pcman.TeamViewerHost`.**

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TeamViewerHost.pcman.recipe

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TeamViewerHost.pcman.recipe

The first run is a dry run (`pcman_dry_run` is on by default). A real run is refused with

    The download was not verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file. Nothing was published.

until the override sets both `pcman_dry_run` false and `pcman_allow_unverified` true (`Add :Input:pcman_dry_run bool false` and `Add :Input:pcman_allow_unverified bool true` with PlistBuddy). Then `pcman catalogs`. When the trust check fails after a change upstream:

    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TeamViewerHost.pcman.recipe

## Other facts

- The inputs of the download recipe are `DOWNLOAD_URL`, `DOWNLOAD_FILENAME`, `TEAMVIEWER_MSI_MEMBER` and `NAME` (`TeamViewerHost`). Change them in the override's `Input`, not in the recipe.
- The zip is about 150 MB. `URLDownloader` asks the server whether the file changed since the last run (the server sent a `Last-Modified`); whether it then answers "not modified" is NOT established. The zip is unpacked at every run.
- A run prints at any verbosity the importer's dry-run warning, `Nothing new`, `Published`, and its NOTE and WARNING lines. `-vv` also prints the repository's path: keep that log private.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They read the three recipes as property lists (identifiers, parents, the steps in order, the arguments of each step and that each is an input that the shared processor declares), check that the Unarchiver's folder and the FileFinder's pattern are the same folder, run the two steps as they are read in AutoPkg's source against small made-up zips (the Host MSI is found; a stale file of an earlier run is gone; a zip without the member finds nothing), run the real `CimianImporter` with that file into a temporary repository, and check this README and the hygiene of the folder for a public repository. No test uses the real vendor zip.
