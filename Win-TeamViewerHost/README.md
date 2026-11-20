# Win-TeamViewerHost

A Windows recipe set: TeamViewer Host, the 64-bit `.msi`, taken out of the zip of MSI installers that TeamViewer serves.

**Status. The download is verified by the signature of the Host MSI, not by a hash (TeamViewer publishes none for the zip or the MSI): the step `AuthenticodeVerifier` checks that the MSI that the recipe takes out of the zip carries a valid, timestamped Authenticode signature of TeamViewer Germany GmbH (see "What protects, and what does not"), and the importers then accept a real run. That step was NOT run with AutoPkg; its processor was run on 2026-11-19 against the Host MSI of that day (see there). READ on 2026-11-19, without a login: `https://download.teamviewer.com/download/version_15x/TeamViewer_MSI64.zip` answers 302 to `dl.teamviewer.com`, and the file there is 153,657,245 bytes with `Last-Modified` 2026-11-16. No page of TeamViewer names this address; it is known from third-party packaging scripts. It is not documented by the vendor and may change or stop without notice. READ in that zip: six members, `Full/Manuals/CommandLineParameters.url`, `Full/Manuals/MassDeployment.url`, `Full/TeamViewer_Full.msi`, `Host/Manuals/CommandLineParameters.url`, `Host/Manuals/MassDeployment.url` and `Host/TeamViewer_Host.msi` (58,937,344 bytes). That MSI is x64, ProductName `TeamViewer Host`, ProductVersion `15.83.7(.0)`, UpgradeCode `{82861EC3-25E9-4152-AAA0-BFB2467B60B7}`, ProductCode `{71322D69-066B-4B3A-8FEA-4476C914E7B3}` (only this one version was read), `ALLUSERS=1`. NOT established: any import into a repository, through either importer; an install through a Cimian client; the refusal (error 25001) on a PC that has an install from the vendor's EXE; an upgrade from one version to the next; and that a later version has the same upgrade code.**

**Results of 2026-11-19.** The download recipe ran under AutoPkg 2.9.0 on a Mac: the zip was downloaded, unpacked, and the Host MSI was found (its SHA-256 begins `6f3c7f15`). The first attempt ended with curl error 56 (connection reset by the server); the second went through. On one PC, as SYSTEM, the Host MSI of version `15.83.7(.0)` installed silently with `msiexec /i <file> /qn /norestart` (exit code 0 after 18 seconds) and was removed silently with `msiexec /x <ProductCode> /qn /norestart` (exit code 0 after 38 seconds). After the removal the uninstall entry and the service were gone; the program folder and the settings key, which holds the device's TeamViewer ID, stayed.

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `TeamViewerHost-Win.download.recipe` | `com.github.serrc-techops.download.TeamViewerHost-Win` | Downloads the zip, unpacks it into an emptied folder of the recipe's cache (`Unarchiver`) and names the Host MSI in it (`FileFinder`), then checks the MSI's signature (`AuthenticodeVerifier`) |
| `TeamViewerHost.cimian.recipe` | `com.github.serrc-techops.cimian.TeamViewerHost` | Parent: the download recipe. Hands the Host MSI to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository, or says that nothing is new |
| `TeamViewerHost.pcman.recipe` | `com.github.serrc-techops.pcman.TeamViewerHost` | Parent: the download recipe. Hands the Host MSI to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `TeamViewerHost.cimian.recipe` is for any Cimian repository (no other tool is needed); `TeamViewerHost.pcman.recipe` is the package tool's way. The item is named `teamviewer.host` (the inputs `CIMIAN_NAME` and `PCMAN_TEMPLATE`); the override sets the repository's own name if it differs. Below, `pcman` stands for `<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

Neither recipe stops on an unchanged download, so an import that failed is tried again at the next run. The processors are in `../Win-SharedProcessors/` (`CimianImporter`) and `../Win-PcmanProcessors/` (`PcmanImporter`); see their READMEs.

## What the download recipe does

1. `URLDownloader` downloads `DOWNLOAD_URL` as `TeamViewer_MSI64.zip` (`DOWNLOAD_FILENAME`).
2. `EndOfCheckPhase`.
3. `Unarchiver` (part of AutoPkg) unpacks the zip into `<the recipe's cache>/unpacked`. It empties that folder first (`purge_destination`), so an MSI of an earlier run is never imported. It uses Python's own zip code (`USE_PYTHON_NATIVE_EXTRACTOR`; on a Mac AutoPkg would otherwise use `ditto`), which does not make symbolic links. In AutoPkg 2.9.0 and later it also refuses a member whose name would land outside the folder; older versions extract with Python's `zipfile` alone, which drops such parts of a name silently. The whole zip is unpacked, the Full MSI too.
4. `FileFinder` (part of AutoPkg) names the one member `TEAMVIEWER_MSI_MEMBER` (`Host/TeamViewer_Host.msi`) in that folder. Its output `found_filename` is the file that the child recipes give the importer as `pathname`. A zip without that member stops the run at this step with `No matching filename found`; nothing else in the zip is taken instead, and the Full MSI is never imported.
5. `AuthenticodeVerifier` (in `../Win-SharedProcessors/`) checks the signature of `found_filename`, the MSI that the importers import (see "What protects, and what does not").

The behaviour of `Unarchiver` and `FileFinder` above is read in the source of AutoPkg 2.9.0 (`Code/autopkglib/Unarchiver.py`, `FileFinder.py`). The good case (the zip unpacked, the Host MSI found) was seen in a run; the stops (a zip without the member, a member outside the folder) were NOT seen in a run.

AutoPkg's option `-p` gives the download step a local file instead of the download: give it the zip, not the MSI. The signature step still checks the MSI found in it.

## What protects, and what does not

TeamViewer publishes no hash for the zip or the MSI. **The download is verified by the MSI's signature.**
After `FileFinder` the shared step `AuthenticodeVerifier` (see `../Win-SharedProcessors/README.md`) checks the
Host MSI that was found (`found_filename`) with `osslsigncode`, and stops the run unless all of this holds:

- the signature covers the content of every stream of the MSI, and through the stream
  `MsiDigitalSignatureEx` (required) the streams' metadata. The compound file around the streams is not
  checked: bytes after the last sector, in the unused part of a sector or in an unused directory entry pass
  (see "An MSI's container is not checked" in the shared README), so the MSI's streams are TeamViewer's, but
  not necessarily every byte of the file;
- the certificate that signed has exactly the subject `CN=TeamViewer Germany GmbH`, `O=TeamViewer Germany GmbH`,
  `L=Göppingen`, `C=DE`, and no `ST` and no `OU` (compared field by field, exactly; a certificate with an `ST`
  is refused). When TeamViewer's next certificate names another place, the step stops the run until a person
  has looked and changed the recipe: that is intended;
- the digest is SHA-256 (the default; SHA-1 and MD5 are refused);
- its chain, and the chain of its timestamp, end in the pinned root `digicert-trusted-root-g4` (DigiCert
  Trusted Root G4);
- the signature has a timestamp that the tool verified, and the CRL of the signing certificate and of the
  timestamp's certificate could be read and does not list them.

The step outputs `signature_verified` and `signature_sha256` (the hash of the MSI), and both importers accept
a real run only when that hash is the hash of the file they import. The step checks the MSI itself, the file
that is imported, so no hash has to be handed over from the zip (as the extractor of `../Win-WindowsAppRuntime/`
does for its package). The zip and its other members (the Full MSI, the two `.url` files) are not checked:
they are not imported.

**Checked on 2026-11-19** (the processor itself, with `osslsigncode` 2.16 and the network for the CRLs; not the
recipe under AutoPkg), against the Host MSI `15.83.7(.0)` of that day (its SHA-256 begins `6f3c7f15`): it
passed, signed by TeamViewer Germany GmbH, timestamped `Nov 13 12:04:23 2026 GMT`; the same file with one byte
changed was refused; with another `O` expected, or without `L`, it was refused; with another pinned root for the
code or for the timestamp it was refused (the recipe's own arguments).

**What the signature does not prove.** That the release is harmless: a bad release that TeamViewer itself
signed passes. That TeamViewer's key was not stolen before the certificate was revoked. That a certificate revoked
within the last CRL period is caught (the CRL comes over HTTP, and an older one that is still valid can be handed
over). The revocation of the intermediate certificate (only the signing certificate's CRL is read). That it is the
newest release (see "An older release, signed for real"). It also does not make the address
documented: no page of TeamViewer names it, and it may change or stop without notice; a file from another
address that TeamViewer signed would pass too. **The step needs `osslsigncode`** (`brew install osslsigncode`)
and HTTP access to the CRL addresses in the certificates (DigiCert's); without either it stops the run, also a
dry run.

**An older release, signed for real.** The signature step passes any file that the publisher signed, also an
older release of the same product served again at the address. What then happens is the importers' rule, not
the signature's: `CimianImporter` says "Nothing new" when the repository has that version or that file, and
otherwise publishes it as one more version of the item, also when it is older than the newest one there (seen in
a test on 2026-11-19: a template of 2.5.0 and a file labelled 1.0.0 gave `published 1.0.0`). It does not refuse
an older version. The client installs the highest version of an item that is for its PC
(`CatalogService.cs:43-56`, as the shared README reads it), so the older version is not installed while the
newer one is in the catalog, but it is in the repository until a person removes it. With the package tool, its own `--if-new` decides (see `../Win-PcmanProcessors/README.md`); what it does
with an older version was NOT established.

Two checks of the importers remain beside the signature:

- **The same product.** Once the item exists, the importers refuse an MSI whose upgrade code differs from the template's (`CimianImporter` unless the override sets `cimian_allow_product_change`), so another product cannot be published under its name. On the first import there is no template, and so no upgrade code to compare.
- **The label.** The recipe gives no version label. For an MSI the importers take the MSI's own ProductVersion and refuse a label that is not the MSI's own version.

Without the signature step, an MSI of the right product with other content (a changed file of the vendor, or a changed download on the way) would pass both checks. They do not replace a verification.

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

1. Add the recipe repository (`autopkg repo-add <the URL of the recipe repository>`) and set the Cimian repository's root once: `defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"`. The share must be mounted. **`osslsigncode`** must be on the build machine (`brew install osslsigncode`): the signature step looks for it only in `/opt/homebrew/bin` and `/usr/local/bin` (not on the `PATH`; no input names another program); without it every run stops, also a dry run.

2. First check that no other recipe has the same name. AutoPkg takes the first match by name and says nothing about the others:

       autopkg list-recipes | grep -i TeamViewerHost

   Each name must be listed once, from this repository. Then make the override INTO THE WINDOWS OVERRIDES FOLDER:

       autopkg make-override --override-dir=<the Windows overrides folder> TeamViewerHost.cimian

   **Open the written file and read `ParentRecipe`: it must be `com.github.serrc-techops.cimian.TeamViewerHost`.** Another value means that AutoPkg found another recipe of the same name.

3. Check the trust information, then run a dry run, BY PATH (the recipe's identifier runs the recipe itself, which never leaves the dry run):

       autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TeamViewerHost.cimian.recipe

       autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TeamViewerHost.cimian.recipe

   A dry run writes nothing. Expected: the download, `Unarchived ...`, `Found file match: '<...>/unpacked/Host/TeamViewer_Host.msi' ...`, `Signature verified: TeamViewer_Host.msi, signed by CN=TeamViewer Germany GmbH, O=TeamViewer Germany GmbH, C=DE, ...`, then the importer's `WARNING: DRY RUN` line and a report row with the result `dry run, nothing written`. With no item of that name yet, the line `No template: the pkginfo is built from the inputs.` appears. (These lines are read in the code, NOT seen from a run.)

4. Switch a real run on. The signature step verifies the download, so one line is enough:

       /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
           <the Windows overrides folder>/TeamViewerHost.cimian.recipe

   A change of the `Input` does not break trust. Do not use `-k` instead: on the command line it applies to every recipe of that run. **Only when the signature step cannot be used** (for example when TeamViewer signs under another name and a person has checked the file by hand) may the override also set `cimian_allow_unverified`, and then the step must be taken out of a copy of the recipe, because it stops the run first. Both lines are needed then:

       /usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' \
           <the Windows overrides folder>/TeamViewerHost.cimian.recipe
       /usr/libexec/PlistBuddy -c 'Add :Input:cimian_allow_unverified bool true' \
           <the Windows overrides folder>/TeamViewerHost.cimian.recipe

   A run of an unverified download prints `WARNING: published WITHOUT a verified download`, and the report row says `published, NOT verified`.

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

The first run is a dry run (`pcman_dry_run` is on by default). The signature step verifies the download, so a real run needs only `pcman_dry_run` false in the override (`Add :Input:pcman_dry_run bool false` with PlistBuddy). Then `pcman catalogs`. **Without the signature step** (a copy of the recipe without it) a real run is refused with

    The download was not verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file, or signature_verified together with the signature_sha256 of this file. Nothing was published.

until the override sets both `pcman_dry_run` false and `pcman_allow_unverified` true (`Add :Input:pcman_dry_run bool false` and `Add :Input:pcman_allow_unverified bool true` with PlistBuddy). When the trust check fails after a change upstream:

    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/TeamViewerHost.pcman.recipe

## Other facts

- The inputs of the download recipe are `DOWNLOAD_URL`, `DOWNLOAD_FILENAME`, `TEAMVIEWER_MSI_MEMBER` and `NAME` (`TeamViewerHost`). Change them in the override's `Input`, not in the recipe.
- The zip is about 150 MB. `URLDownloader` asks the server whether the file changed since the last run (the server sent a `Last-Modified`); whether it then answers "not modified" is NOT established. The zip is unpacked at every run.
- A run prints at any verbosity the importer's dry-run warning, `Nothing new`, `Published`, and its NOTE and WARNING lines. `-vv` also prints the repository's path: keep that log private.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They read the three recipes as property lists (identifiers, parents, the steps in order, the arguments of each step and that each is an input that the shared processor declares, the signature step with TeamViewer's name and the pinned root on the found MSI), check that the Unarchiver's folder and the FileFinder's pattern are the same folder, run the two steps as they are read in AutoPkg's source against small made-up zips (the Host MSI is found; a stale file of an earlier run is gone; a zip without the member finds nothing), run the real `CimianImporter` with that file into a temporary repository, and check this README and the hygiene of the folder for a public repository. No test uses the real vendor zip.
