# Win-KyoceraKXDriver

A Windows recipe pair: Kyocera's KX print driver (one driver package for all KX printers), repacked from the vendor's zip into a zip of one folder with a version label, and handed to the package tool (`pcman`) as a new version of a print driver item. There is no `.cimian.recipe` in this folder: the direct Cimian importer writes the pkginfo of an installer, and a print driver item needs the package tool's scripts.

**Status. RUN on 2026-11-17 under AutoPkg 2.9.0 in a scratch folder, into a scratch Cimian repository with a scratch copy of the package tool: `make-override` and `verify-trust-info` were OK for `KyoceraKXDriver.pcman`; a dry run downloaded the vendor zip with AutoPkg's own downloader (no special request header), the repacker wrote `KyoceraKXDriver-8.7.0917.0.zip` (718 files) from `64bit/` (INF `DriverVer=09/17/2026,8.7.0917.0`, 549 driver names) and the package tool's dry run named the 9 driver names of its template as present and wrote nothing; a real run without `pcman_allow_unverified` was refused (exit 70); with it the package tool published `KyoceraKXDriver` 8.7.0917.0 (SHA-256 of the zip `938a3b8a4ee6089b9ffde2d5f9aa38a4f4e32ec5c310622935e70be3e34f4c33`, the same as two repacks on another Mac under three Python versions); a second run said `Nothing new` and wrote nothing. Every run downloaded the whole vendor zip again: the server sends no ETag, no Last-Modified and no Content-Length (header request of 2026-11-17: 200, `content-disposition: attachment; filename=KX Driver 8.7.0917.zip`), and a `Range` request was answered 200. THE PUBLISHER'S CERTIFICATE decides whether a PC installs this version silently (it does so only when the vendor's signing certificate is a trusted publisher on it): on one Windows 11 test PC, as SYSTEM, with driver 8.4.1716.0 installed, `pnputil /add-driver` REFUSED the 8.7.0917.0 package ("The publisher of an Authenticode(tm) signed catalog has not yet been established as trusted"), because the catalog `kyomita.cat` of `64bit/` in 8.7.0917 is signed by the vendor's own code-signing certificate (subject `CN=KYOCERA Document Solutions Inc.`, valid until 2026-12-08), not by Microsoft's Windows Hardware Compatibility Publisher as the 8.4.1716 package was. After that certificate was put into the PC's LocalMachine TrustedPublisher store, the same install added the package and the registered drivers moved from 8.4.1716.0 to 8.7.917.0 (two names read), also after a restart of the spooler. Whether to trust that certificate on the fleet is a decision for whoever runs it; the recipe does not add trust and must not. The certificate changes when it expires, the recipe does not check who signed the catalog, and whether a later version is signed by Microsoft again is NOT established. Also NOT established: a run through the Cimian client, an install of 8.7.0917.0 on a PC without an older version, and the folders `32bit/` and `arm64/` (only `64bit/` was used). The download is NOT verified: Kyocera publishes no checksum and this recipe pins none, so the shared importer REFUSES a real run unless the override sets `pcman_allow_unverified` to true. When a run fails, STOP: nothing was written. Read the real answer of the server and the file, correct the recipe or the processor, and only then look at the trust information. Never accept new trust information first to make a failure go away.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `KyoceraKXDriver-Win.download.recipe` | `com.github.serrc-techops.download.KyoceraKXDriver-Win` | Downloads the vendor zip from the fixed address and repacks the folder `64bit/` with `KyoceraKXDriverRepacker` (in this folder) into `KyoceraKXDriver-<version>.zip` |
| `KyoceraKXDriver.pcman.recipe` | `com.github.serrc-techops.pcman.KyoceraKXDriver` | Parent: the download recipe. Hands the new zip and its version to the package tool (`pcman`), template `KyoceraKXDriver`, which publishes it as a new version of the print driver item, or says that nothing is new |

The processor `KyoceraKXDriverRepacker.py` takes the folder `64bit/` out of the vendor zip (input `kx_architecture_folder`, default `64bit`), reads `OEMSETUP.INF` in it and writes `KyoceraKXDriver-<a.b.c.d>.zip` beside the vendor zip. The new zip holds ONE folder, `KyoceraKXDriver-<a.b.c.d>/` (for a folder other than the default `64bit`, the folder's name is in both, `KyoceraKXDriver-<folder>-<a.b.c.d>`, so that two architectures never give one name; one template and one override per architecture, never two architectures into one item; the default keeps the plain name) with the files of the chosen folder and its sub-folders: the layout that the package tool takes for a print driver (one folder named like the zip, with the driver's `.inf` and its files). The version is the four numbers of the INF's `DriverVer=<date>,<a.b.c.d>` line; a missing line, two lines or a version that is not four numbers stops the run. Below, `pcman` stands for `<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What the repacker checks

All of it before anything is written; a failed run leaves nothing behind (no new zip, no temporary file).

- **Member names.** An absolute name, a drive letter, a backslash, a NUL, a part named `..`, an empty name or a name that appears twice in the zip refuses the file. A symbolic link in the chosen folder is refused, and so are two members of it that differ only in letter case.
- **Size.** More than 20,000 members, or more than 1 GiB of files in the chosen folder (counted from the sizes the zip declares), refuses the file. The folder of 8.7.0917 held 81 MB.
- **The INF.** Exactly one `OEMSETUP.INF` in the chosen folder, at most 16 MiB, read as UTF-16 (with or without a byte order mark, either byte order), UTF-8 (with or without a mark) or 8-bit text.
- **The driver names.** The input `kx_required_driver_names` (a list; default `KX DRIVER for Universal Printing`) is checked against the INF: every name must be a model line, that is the text left of the equals sign of a line in a model section that `[Manufacturer]` lists (`%key%` names are looked up in `[Strings]`; a `;` comment is ignored). The comparison ignores letter case, as the package tool's does; the missing names are listed in the error as the recipe wrote them. The package tool checks the names of its template too; this check says it earlier and in a dry run. It is the list input of the recipe's `Input`, read directly (not through a `%variable%`, which would turn the list into text): set it in the override as an array of the names that the printer items use.
- **The INF has model lines at all.** An INF with none is refused.

## The new zip is deterministic

The members are sorted by name, carry one fixed time stamp (1980-01-01), one fixed attribute value (a regular file, mode 0644), no extra field and no comment, and are stored without compression, so that the bytes do not depend on the zlib of the machine that ran the recipe. The same vendor zip always gives the same bytes and the same SHA-256, also when the vendor zip is ordered or compressed differently inside. Only files are written, no folder entries, so an empty folder of the vendor's is lost. The cost is the size: the new zip is about 81 MB for 8.7.0917.

## What protects, and what does not

Nothing proves that the downloaded file is what Kyocera published: no hash is pinned and none is published, and a signature check is not built (Windows checks the driver's catalog when it is installed). The repacker sets `checksum_sha256` to the SHA-256 of the NEW zip (the file that the importer imports) and sets `checksum_verified` to false, whatever it was before, so the shared importer REFUSES a real run until a person has checked the file and set `pcman_allow_unverified` to true in the override; the run then publishes with a warning and the report says `published, NOT verified`. This is the same arrangement as `../Win-Scratch/`, which has the same problem. That checks only that the importer's own file is the one that was hashed, not where it came from. Because the server gives AutoPkg nothing to compare, the recipe downloads the 252 MB file at every run.

## The publisher's certificate

A PC installs this driver version silently only when the vendor's own signing certificate is a trusted publisher on it. The catalog (`kyomita.cat`) of `64bit/` in 8.7.0917 is signed by Kyocera's code-signing certificate (subject `CN=KYOCERA Document Solutions Inc.`, valid until 2026-12-08), not by Microsoft's Windows Hardware Compatibility Publisher as the earlier package that was tested (8.4.1716) was. Without that certificate in the PC's LocalMachine TrustedPublisher store, `pnputil /add-driver` refuses the package with "The publisher of an Authenticode(tm) signed catalog has not yet been established as trusted"; with it, the package was added on one Windows 11 test PC and the registered drivers moved to 8.7.917.0. Whether to trust that certificate on the fleet is a decision for whoever runs it. This recipe does not add trust and must not: trusting whatever signed the download would defeat the check. The certificate changes when it expires, the recipe does not check who signed the catalog, and whether a later version is signed by Microsoft again is NOT established.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path.** Without it AutoPkg does not treat the file as an override and skips the trust check with one warning line. The shared notes are in `../Win-PcmanProcessors/README.md`.

## With the package tool (pcman)

The template is an item of the kind `printer_driver` with the driver names that the printer items use; it must exist before the first import (make it with the package tool). The shared importer accepts a `.zip` for such a template only together with a version, which this recipe gives. The package tool refuses a `.zip` for a template of another kind, and refuses the import when a driver name of the template is not a model line of the INF.

    autopkg make-override --override-dir=<the Windows overrides folder> KyoceraKXDriver.pcman

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/KyoceraKXDriver.pcman.recipe

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/KyoceraKXDriver.pcman.recipe

The first run is a dry run. Expected: the repacker's line (the file written, the file count, the version, `NOT verified`) and the importer's `WARNING` that nothing was published. The override's `Input` sets `kx_required_driver_names` to the names of the printer items. A real run needs `pcman_dry_run` false and `pcman_allow_unverified` true in the override, and `pcman catalogs` afterwards; read the dry run and look at the vendor's file first.

## Other facts

- The recipes' inputs are `KX_ARCHITECTURE_FOLDER` (`64bit`), `kx_required_driver_names` (a list), `NAME` and, for the pcman recipe, `PCMAN_TEMPLATE` (`KyoceraKXDriver`).
- The importer processor `PcmanImporter` in `../Win-PcmanProcessors/` accepts `.zip` as a fourth kind of file (a print driver zip, version required, no `msiinfo`); the change is described in that folder's README.
- The repacker's outputs are `pathname` (the new zip), `version`, `checksum_sha256`, `checksum_verified` (false), `kx_vendor_zip_pathname`, `kx_vendor_zip_sha256`, `kx_inf_driver_date`, `kx_driver_folder`, `kx_driver_name_count` and `kx_file_count`.

## Tests

From the root of the repository, no AutoPkg and no network needed:

    python3 -m unittest discover -s Win-KyoceraKXDriver/tests -t Win-KyoceraKXDriver/tests

They build small made-up vendor zips (the folders `32bit/`, `64bit/`, `arm64/`, `Utility/`, an INF of the vendor's shape in each encoding) and check the layout, determinism (two runs, another order and compression of the input, the fixed attributes), each refusal, the version line, the driver names check, the recipes as property lists, the chain with a stand-in for the package tool, this README and the hygiene of the folder for a public repository. No test uses the real vendor zip.
