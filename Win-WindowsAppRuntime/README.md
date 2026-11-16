# Win-WindowsAppRuntime

A Windows recipe set: the Windows App Runtime framework package (`Microsoft.WindowsAppRuntime.1.4`, an `.msix`, x64 by default), taken out of Microsoft's redistributable zip and published as a Cimian `msix` item of its own. It exists because the Store application in `../Win-Acellus/` declares this framework as a dependency.

**Status. Run once under AutoPkg 2.9.0 into a scratch Cimian repository on 2026-11-16, and the framework was provisioned alone on one Windows 11 test PC; NOT run through a Cimian client, and no real repository was touched. READ on 2026-11-16 over HTTPS: `https://aka.ms/windowsappsdk/1.4/latest/Microsoft.WindowsAppRuntime.Redist.1.4.zip` answers 301 to a file under `download.microsoft.com` named `Microsoft.WindowsAppRuntime.Redist.1.4.240802001.zip`, which answers 200 with `Content-Length` 251851408, `Last-Modified` 2025-03-03 and an `ETag` of 64 hex digits (it begins `0x8E966ABF`). That ETag is NOT the SHA-256 of the file (the SHA-256 is the `REDIST_SHA256` below, which begins `62af3d28`): it is not a hash to compare with. READ in a copy of that file (opened only with Python's zipfile, nothing run): the zip has 22 entries; under `MSIX/` it has, for each of `win10-x64`, `win10-x86` and `win10-arm64`, four packages (`Microsoft.WindowsAppRuntime.1.4.msix`, `.DDLM.1.4.msix`, `.Main.1.4.msix`, `.Singleton.1.4.msix`), and outside `MSIX/` three installer programs; the x64 framework package is 22310719 bytes and its manifest has the Identity Name `Microsoft.WindowsAppRuntime.1.4`, Version `4000.1309.2056.0`, ProcessorArchitecture `x64`, Publisher `CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US`, and `Properties/Framework` true (the Main package has the Identity Name `MicrosoftCorporationII.WinAppRuntime.Main.1.4`, and no Framework mark). The download recipe's default `REDIST_SHA256` is the SHA-256 of that copy: it is OUR record of the file read on 2026-11-16, NOT a checksum that Microsoft publishes (none was found). It proves that the zip is the same file; when Microsoft changes the file, the run stops at the checksum step and a person looks and sets the new value in the override. RUN on 2026-11-16 under AutoPkg 2.9.0, into a scratch Cimian repository that had no item of that name: `make-override` with `--override-dir`, `verify-trust-info` OK, a dry run, a real run and a second real run. `ChecksumVerifier` verified the zip's SHA-256; the extractor wrote `MSIX/win10-x64/Microsoft.WindowsAppRuntime.1.4.msix` (22310719 bytes) as `Microsoft.WindowsAppRuntime.1.4_4000.1309.2056.0_x64.msix`; `CimianImporter` published `WindowsAppRuntime.1.4` 4000.1309.2056(.0) in the catalog `Development`, reading the identity name, the version and the architecture x64 from the package; the second run said that nothing is new. TESTED on 2026-11-16 on one Windows 11 test PC that had neither Acellus nor this framework (it had other Windows App Runtime versions), as SYSTEM from a scheduled task: `Add-AppxProvisionedPackage -Online -PackagePath <the published x64 framework msix> -SkipLicense` succeeded for the framework ALONE (it then showed as a provisioned package and as a package, x64); then the same command for the Acellus bundle of 2026.1028.1836(.0) WITHOUT any `-DependencyPackagePath` succeeded, and within 20 seconds the PC's one signed-in user (a disconnected session) had `GoldKeyCorporation.Acellus` 40.0.22(.0) and the x64 framework in state Installed. So on that PC the x64 framework alone was enough for Acellus (the stand-alone test of 2026-11-10 had provisioned the x64 and the x86 framework together with the bundle through `-DependencyPackagePath`), and a framework can be provisioned by itself. Acellus was not started. NOT established: the same through the Cimian client (how the client installs an `msix` item was not exercised here); Windows 10; an x86 or ARM PC; a user who signs in for the first time after the provisioning; removal; a later Acellus version that names a higher minimum; and that the signature is accepted on every PC (it is not checked on the Mac). A known open finding of review: a template without an architecture lets a package for one architecture go to every PC; the first pkginfo of this item therefore must name the architecture (see "What protects"; the run above built it from the package, with `supported_architectures` x64 expected, not read back). Every command of this README carries `--override-dir`.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `WindowsAppRuntime-Win.download.recipe` | `com.github.serrc-techops.download.WindowsAppRuntime-Win` | Downloads the redistributable zip, checks it against `REDIST_SHA256` (`ChecksumVerifier`) and takes the framework package of one architecture out of it (`WindowsAppRuntimeFrameworkExtractor`, in this folder) |
| `WindowsAppRuntime.cimian.recipe` | `com.github.serrc-techops.cimian.WindowsAppRuntime` | Parent: the download recipe. Hands the package to `CimianImporter`, which publishes it as a new version of the item into any Cimian repository, or says that nothing is new |
| `WindowsAppRuntime.pcman.recipe` | `com.github.serrc-techops.pcman.WindowsAppRuntime` | Parent: the download recipe. Hands the package to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

**Three recipes.** The download recipe is the parent of both of the others. `WindowsAppRuntime.cimian.recipe` is for any Cimian repository (no other tool is needed); `WindowsAppRuntime.pcman.recipe` is the package tool's way. The item is named `WindowsAppRuntime.1.4` (the inputs `CIMIAN_NAME` and `PCMAN_TEMPLATE`); the override sets the repository's own name if it differs. Below, `pcman` stands for `<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

The steps of the download recipe are `URLDownloader` (address built from `WINDOWSAPPRUNTIME_RELEASE`, default `1.4`; the file name is set so that it does not depend on the redirect), `EndOfCheckPhase`, `ChecksumVerifier` on the ZIP, and `WindowsAppRuntimeFrameworkExtractor`. Neither importer is given a version label: they read the package's own Identity Version (four numbers that look like `4000.1309.2056.0`, not the release `1.4`). Neither recipe stops on an unchanged download, so an import that failed is tried again at the next run.

## What protects, and what does not

- **The zip is pinned, not vendor-verified.** `ChecksumVerifier` compares the zip with `REDIST_SHA256`. The value is our record of one file (see the status line). It does not prove that Microsoft published that file; it proves that the file is the one that was read. The file's `ETag` is not a hash and is not compared. A new file stops the run: look at it (the release, its size, its members) before setting a new value in the override's `Input`, never in the recipe.
- **From the zip's hash to the package's.** The importers accept a download as verified only when `checksum_sha256` is the hash of the file they import, and that file is the package, not the zip. So the extractor hashes the zip itself and, only when `checksum_verified` is true and `checksum_sha256` is the zip's hash, replaces `checksum_sha256` with the hash of the package. When the zip was not verified, nothing is changed and a real run is refused by the importers. The package is therefore verified in one sense only: it is bytes out of a zip with the pinned hash.
- **The extractor's checks.** It refuses a package whose manifest is not UTF-8 text, a damaged zip member or package (it stops with its own message, not a raw exception), and a package whose publisher is not the Microsoft one that was read on 2026-11-16 (so that a new `REDIST_SHA256` set after a look at another file cannot admit a package of another publisher). It also refuses a zip with a member name that is absolute, has a drive letter or a backslash, or has a `..` part; it takes exactly one member named `MSIX/win10-<architecture>/Microsoft.WindowsAppRuntime.<release>.msix` (never the Main, Singleton or DDLM packages), at most 256 MiB, and then reads the package's `AppxManifest.xml` (at most 1 MiB, no document type or entity declaration): the Identity Name must be `Microsoft.WindowsAppRuntime.<release>`, the ProcessorArchitecture the wanted one, and `Properties/Framework` true. It writes `<identity name>_<version>_<architecture>.msix` beside the zip through a temporary file and a rename, and refuses a link at the target. It runs nothing from the zip.
- **The same product.** The importers refuse a package whose identity name is not the template's.
- **The architecture.** Only the x64 framework is published by default (`WINDOWSAPPRUNTIME_ARCHITECTURE`). `CimianImporter` takes the package's ProcessorArchitecture as the architecture of the item: the first pkginfo it builds has `supported_architectures: [x64]` (from the importer's code; the pkginfo of the scratch run was not read back). A template that names no architecture would let a package for one architecture go to every PC, so with a template made by hand or by the package tool the architecture must be named in it (`supported_architectures: [x64]`; for the package tool `--architectures x64`). On one test PC the x64 framework alone was enough for Acellus (see the status line), which is one observation, not a rule; an x86 item would be a second override with `WINDOWSAPPRUNTIME_ARCHITECTURE` set to `x86` and its own item name, and is not made by this folder.
- **Not checked:** the package's signature (Windows checks it when it adds the package), and that it installs through the Cimian client.

## Run every override with `--override-dir`

**Give `--override-dir=<the Windows overrides folder>` to every `autopkg run`, `autopkg verify-trust-info` and `autopkg update-trust-info`, together with the override's path. Without it AutoPkg does not treat the file as an override: it skips the trust check with one warning line (`... is missing trust info ... Proceeding...`) and runs the recipe, and a changed processor is not caught. If that line ever appears in a run of an override, stop: the run was not checked.** `make-override` takes a recipe NAME and refuses a path, and it needs the same option.

## With any Cimian repository

This way needs AutoPkg and PyYAML (the importer reads the package itself; no `msiinfo`). It uses `WindowsAppRuntime.cimian.recipe` and `CimianImporter` of `../Win-SharedProcessors/`.

1. Add the recipe repository (`autopkg repo-add <the URL of the recipe repository>`) and set the Cimian repository's root once: `defaults write com.github.autopkg CIMIAN_REPO -string "<the Cimian repository's root>"`. The share must be mounted.

2. Make the override INTO THE WINDOWS OVERRIDES FOLDER:

       autopkg make-override --override-dir=<the Windows overrides folder> WindowsAppRuntime.cimian

3. Check the trust information, then run a dry run:

       autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WindowsAppRuntime.cimian.recipe

       autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WindowsAppRuntime.cimian.recipe

   A dry run writes nothing. Expected: the download step, `SHA-256 verified: <hash>`, the extractor's line, and the importer's NOTE and `WARNING: DRY RUN`. With no item of that name yet, the line `No template: the pkginfo is built from the inputs.` appears and the NOTE says that the version is read from the package. If the run stops at the checksum step, the file changed: do NOT accept anything; read the file.

4. Real run, only after the dry run was read: `Add :Input:cimian_dry_run bool false` in the override (PlistBuddy, `-c`), then `autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WindowsAppRuntime.cimian.recipe`, then Cimian's `makecatalogs`. A second run must say `Nothing new`.

5. The item the application needs: give Acellus's item a `requires` on `WindowsAppRuntime.1.4` (see `../Win-Acellus/README.md`). Check the first pkginfo for `supported_architectures: [x64]` before any PC receives it.

6. Install on one test PC through the Cimian client and read the result; this has NOT been done (only a direct `Add-AppxProvisionedPackage` was tried, see the status line).

## With the package tool (pcman)

It uses `WindowsAppRuntime.pcman.recipe` and `PcmanImporter` of `../Win-PcmanProcessors/`. The template item is made once by a first import; the bytes for it are the package that the dry run leaves in the recipe's cache (the first dry run stops at the import step because the template is missing). The command (NOT run for this package):

    pcman import <the extracted Microsoft.WindowsAppRuntime.1.4_<version>_x64.msix> --name WindowsAppRuntime.1.4 \
        --display-name "Windows App Runtime 1.4" --category <the category> --developer "Microsoft Corporation" \
        --description <the description> --architectures x64 --directory <the folder of the item> --no-prompt --build

There is no `--version`: the package tool takes the package's own version. Then:

    autopkg make-override --override-dir=<the Windows overrides folder> WindowsAppRuntime.pcman

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WindowsAppRuntime.pcman.recipe

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/WindowsAppRuntime.pcman.recipe

The real run needs `pcman_dry_run` false in the override and `pcman catalogs` afterwards; it carries the same `--override-dir` and the same path. The package tool's way has not been run; the other way ran once in a scratch repository (see the status line).

## Other facts

- A run prints the extractor's line: the member, its size, the file written, and the identity. When the zip was not verified, the line says so.
- The inputs of the download recipe are `REDIST_SHA256`, `WINDOWSAPPRUNTIME_RELEASE` (`1.4`) and `WINDOWSAPPRUNTIME_ARCHITECTURE` (`x64`). Another release means another item name (the override sets `CIMIAN_NAME` or `PCMAN_TEMPLATE`, and the display name; nothing enforces it, and with no template an empty repository would take a 1.x framework under the old name) and a new `REDIST_SHA256` (and the address is built from the release: `aka.ms` has to have it).
- No version is stated for any later release: only 1.4 was read.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They build tiny made-up zips (a framework package with decoys for the Main, Singleton and DDLM packages, another architecture, a double, a missing member, path tricks, a wrong identity) and check the extractor, the recipes and this README. No test uses the real redistributable.
