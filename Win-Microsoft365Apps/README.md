# Win-Microsoft365Apps

A Windows recipe pair: Microsoft 365 Apps (Office Click-to-Run), packed with its
source into one self-extracting EXE, so that a PC installs Office from the Cimian
repository and downloads nothing from the internet.

**NOT verified. Microsoft publishes no hash for the Office source files or for its
`setup.exe`, and no signature is checked on the build machine. The files come from
Microsoft's CDN over https, each with the size the server announced; nothing more is
proven. The importers therefore REFUSE a real run (nothing is published) unless the
override sets `cimian_allow_unverified` (`pcman_allow_unverified`) to true. On the PC,
Microsoft's `setup.exe` and the Click-to-Run client check the source files against
Microsoft's catalogs; nothing checks `setup.exe` itself.**

**Status (2026-11-13). Built, imported by hand and installed by the Cimian client once; NOT run under AutoPkg.**
The processor was run by hand with AutoPkg 2.9.0's Python on the build Mac (p7zip 17.05): from an
empty cache it read the Monthly Enterprise version (16.0.20527.20194), downloaded the 12 files and
`setup.exe` and built the EXE (3,329,210,368 bytes) in about two minutes; a second run with the
source in the cache took 12 seconds. That EXE was run as SYSTEM from a scheduled task on a Windows 11
Education test PC with no Office: exit 0 after 7.7 minutes, Office 16.0.20527.20194, `x64`, Word,
Excel and PowerPoint there, Outlook, Access, OneNote and Publisher not, updates off, the temp
folder removed. (That EXE was built with a list that lacked `OutlookForWindows` and `Teams`, and only the classic
programs were looked for: on the Cimian test PC below the new Outlook and the new Teams were found provisioned.) A second EXE made of the same stub and a `setup.bat` that ends with 7 ended with
7: a failure of what the stub runs comes back. Windows lists the product as
`Microsoft 365 Apps for business - en-us` with the version 16.0.20527.20194. The same day the EXE was imported with the package tool as an `exe` item (the
item text below), served by Zentral's Monolith, and installed by the Cimian client 2026.10.30.0858
on a Windows Server 2022 test PC with no Office: download, install and the client's record in 11.6
minutes, exit 0, and the next check called it installed with nothing pending (the item has no
`installs` list, so the client says "cannot verify, assuming success"; the check by name and
version is what tells). The EXE was then rebuilt with
`OutlookForWindows` and `Teams` excluded and with `prepare.ps1`, and run as SYSTEM on a Windows
Server 2025 test PC that had neither app: a fresh install (exit 0, 11.8 minutes) left the new
Outlook and the new Teams away and installed no classic Outlook; on the same PC with classic
Outlook added to the Business product, the EXE kept Outlook (exit 0, 13.6 minutes). The first
build was also run over a 32-bit Click-to-Run Office of 2018 (16.0.9126.2336, the products
`O365ProPlusRetail` and `O365HomePremRetail`): exit 0 after 14.2 minutes, everything 64-bit at
16.0.20527.20194, **the two products kept beside the new one** (Office's setup adds a product; it
removes none), and with them their apps, Outlook among them. The rebuilt EXE was then installed by
the Cimian client on a real staff PC with that same 32-bit Office of 2018, nobody signed in: exit 0
after 25.4 minutes (download included), everything 64-bit at 16.0.20527.20194, Outlook kept (the
Business product's excluded apps no longer name it there), the temp folder removed. NOT established: a
run of the three recipes by AutoPkg itself (the override, the trust information, `%version%`
reaching the importers); an install
over an MSI Office (`RemoveMSI`); an install while
an Office program is open; any language but `en-us`; any channel but Monthly Enterprise; that
`AllowCdnFallback="FALSE"` keeps a PC from Microsoft's servers (the test PC had internet access).

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Microsoft365Apps-Win.download.recipe` | `com.github.serrc-techops.download.Microsoft365Apps-Win` | One step, `Microsoft365AppsPackager` (in this folder): reads the channel's newest version, downloads the source and `setup.exe`, builds the EXE in the recipe's cache |
| `Microsoft365Apps.cimian.recipe` | `com.github.serrc-techops.cimian.Microsoft365Apps` | Parent: the download recipe. Hands the EXE and the Office version to `CimianImporter` |
| `Microsoft365Apps.pcman.recipe` | `com.github.serrc-techops.pcman.Microsoft365Apps` | Parent: the download recipe. Hands the EXE and the Office version to the package tool (`PcmanImporter`) |

## Why it is built this way

- **One installer for the suite.** Microsoft ships Office for Windows as one stream that
  holds every app (`stream.x64.x-none.dat`, 2.9 GB of the 3.3 GB). Word, Excel and
  PowerPoint are not separate downloads, so one item per app would store that stream once
  per app. Which apps are installed is a setting (`OFFICE_EXCLUDE_APPS`).
- **One file.** A Cimian item has one installer file. Of the containers the client can
  install, `.pkg` and `.nupkg` need `sbin-installer` or Chocolatey on the PC, and the client's
  source marks `.pkg` for removal. An EXE needs nothing.
- **The stub.** The EXE is `7zS2con.sfx` of the LZMA SDK (public domain) followed by a 7z
  archive. That stub unpacks into a new folder under the temp folder, runs `setup.bat` there
  (a `.bat` named `setup` in the archive's root comes first in its order), waits, removes the
  folder and **ends with the exit code of what it ran** (`C/Util/SfxSetup/SfxSetup.c` of SDK
  26.06). The SDK's other installer stub, `7zSD.sfx`, always ends with 0, so a failed Office
  setup would look like a success. The console form is used because the windowed form shows
  an error in a message box, which nobody can close in a run as SYSTEM.
- **The parts.** The stub is a 32-bit program and holds one whole file in memory while it
  unpacks it. So every file over 64 MiB is cut into parts of 64 MiB, the archive is stored
  (no compression: the files are compressed already) with one file per block, and `setup.bat`
  joins the parts on the PC and checks each joined file's size. The join is `join.ps1`, in
  the archive: one pass, each part appended once and deleted at once, so the folder never
  holds a file twice. (A first form, `copy /b file+part file` for each part, took 9 minutes
  on the test PC for the same files: `copy` rewrites the growing file every time.)
- **From the folder and from nowhere else.** `configuration.xml` names the version,
  `AllowCdnFallback="FALSE"`, and a `SourcePath` that `prepare.ps1` (run by `setup.bat`) sets to the
  folder the EXE unpacked into. A source that is not complete fails the install; it is not fetched from
  Microsoft behind the back of the repository.
- **One language.** Office's setup brings every product and every language on a PC to the
  version it installs, and it wants the source of each. The EXE holds one language and the
  fallback to Microsoft's servers is off, so on a PC whose Office also has Spanish and French
  (a factory image) setup ends with 17002 (the Click-to-Run log: "Failed to download Stream
  Cab. Fallback not allowed", error 30182) and leaves the PC between the versions; every later
  run fails the same way. So `prepare.ps1` reads the Click-to-Run entries of the Windows
  uninstall list (both registry views: it may run as a 32-bit program), writes `remove.xml`
  with every other language of every product, and `setup.bat` runs
  `setup.exe /configure remove.xml` before the install. A failed removal ends the EXE with
  setup's code. Reproduced and proven on 2026-11-16 on a Windows 11 test PC with
  16.0.20527.20150 (`O365HomePremRetail` and `OneNoteFreeRetail` in `en-us`, `es-es`, `fr-fr`,
  `O365BusinessRetail` in `en-us`): the EXE without this step ended with 17002 after 2.7
  minutes; the EXE with it, run over that failed state as SYSTEM, ended with 0 after 12
  minutes, the three products at 16.0.20527.20194 in `en-us` only. The two languages together
  are 680 MB more, which would bring the EXE to 4.0 GB; a third does not fit.
- **4 GiB.** Windows does not start an EXE of 4 GiB or more. The processor stops with a
  message when the source has outgrown that; nothing is built.

## What `setup.bat` returns

The exit code of the EXE is the exit code of Microsoft's `setup.exe /configure`, or one of:

| Code | Meaning |
| --- | --- |
| 1 | The stub could not unpack (no space in the temp folder, a damaged file) |
| 30 | The folder of `setup.bat` could not be made the current folder |
| 31 | A part could not be joined to its file |
| 32 | A joined file does not have the size of the original |
| 33 | `configuration.xml` could not be made ready for the PC (`prepare.ps1`) |

## The inputs (set them in the override, never in the recipe)

| Input | Default | Meaning |
| --- | --- | --- |
| `OFFICE_CHANNEL` | `MonthlyEnterprise` | `Current`, `MonthlyEnterprise` or `SemiAnnual`. The version is read from the channel's own folder on the CDN (`Office/Data/v64.cab`, the file Microsoft's tool reads) |
| `OFFICE_VERSION` | empty | A version to pack instead of the newest (`16.0.x.y`) |
| `OFFICE_LANGUAGE` | `en-us` | `en-us`, `es-es` or `fr-fr` (the processor's table has the number of each) |
| `OFFICE_PRODUCT_ID` | `O365BusinessRetail` | The product ID of the Office Deployment Tool |
| `OFFICE_EXCLUDE_APPS` | `Access Groove Lync OneDrive OneNote Outlook OutlookForWindows Publisher Teams` | The apps that are not installed (so: Word, Excel, PowerPoint). `Outlook` is the classic program only: without `OutlookForWindows` and `Teams` Microsoft's setup also provisions the new Outlook and the new Teams for all users (seen on a test PC on 2026-11-13 with the first list, which lacked the two) |
| `OFFICE_KEEP_IF_INSTALLED` | `Outlook` | Excluded apps that stay on a PC that has them (`Outlook`, `Access`, `OneNote`, `Publisher`: the classic programs). Office's setup removes an installed app that is excluded; for an app of this list the EXE first looks for the program on the PC (Click-to-Run or Windows Installer Office, 32-bit or 64-bit) and, where it is there, no longer excludes it. Empty: an excluded app is removed wherever it is |
| `OFFICE_UPDATES_ENABLED` | false | False: Office does not update itself; the version on a PC is the item's |
| `OFFICE_MIGRATE_ARCHITECTURE` | true | A 32-bit Click-to-Run Office is changed to 64-bit |
| `OFFICE_REMOVE_MSI` | true | An Office installed by Windows Installer is removed first |
| `OFFICE_REMOVE_OTHER_LANGUAGES` | true | Every language but `OFFICE_LANGUAGE` is removed from the Click-to-Run Office products a PC has, before the install (the products stay). False: on a PC with an Office in another language the install fails with 17002 |
| `OFFICE_INCLUDE_ARM64X` | false | True packs the stream for ARM PCs too (489 MB more; the EXE is then 3.8 GB, close to the 4 GiB that Windows allows). A 64-bit Intel or AMD PC installs without it |
| `OFFICE_FORCE_APP_SHUTDOWN` | false | True closes open Office programs for the install (unsaved work is lost). False: the install fails while one is open and the next run tries again |
| `SFX_SDK_URL`, `SFX_SDK_SHA256` | LZMA SDK 26.06 from the 7-Zip project's GitHub release | The archive that holds the stub, and its SHA-256 (the value GitHub records for the asset; compared on 2026-11-13). A different file stops the run |

A changed input builds a new EXE of the same version; the importers then say "nothing new"
for a version the repository has. To publish a changed configuration for the same Office
version, remove that version from the repository first, or wait for the next version.

## What the build machine needs

- A 7z program (`7zz`, `7z` or `7za` in `/opt/homebrew/bin`, `/usr/local/bin` or `/usr/bin`;
  or the input `sevenzip_path`). It unpacks `v64.cab` and the SDK and writes the archive.
- About 10 GB free in the recipe's cache while it builds, 6.6 GB afterwards (the source and
  the EXE of the current version; those of other versions are removed).
- Each published version is 3.3 GB in the repository and on every server that mirrors it.
  Remove old versions as the repository's rules allow.

## The files of the source

Microsoft's own tool decides the list. On 2026-11-13 `setup.exe /download` (16.0.20430.20146,
on Windows Server 2025) fetched 14 files for `O365BusinessRetail`, 64-bit, `en-us`, version
16.0.20527.20194: `v64_<version>.cab`, and in the version's folder `a640_exp.cab`,
`i640.cab`, `i640.cab.cat`, `i641033.cab`, `s640.cab`, `s641033.cab`, `sa640.cab`, the two
streams `stream.x64.en-us.dat` and `stream.x64.x-none.dat` each with its `.cat`, and
`stream.x64.x-none.arm64x.dat` with its `.cat`. The processor's list is that list, without
the last two unless `OFFICE_INCLUDE_ARM64X` is true. When a later version of Office fails
to install from the EXE with a source error, run `setup.exe /download` again on a Windows
machine and compare.

## The item (the template)

The first import makes the item; later versions are copies of it. With the package tool
(an `exe` item named `office365business`, the name of the Chocolatey item it replaces):

    pcman import <cache>/Microsoft365Apps-<version>-x64.exe --directory app --name office365business \
        --version <version> --display-name "Microsoft 365 Apps" --category Productivity --developer Microsoft \
        --build

and in the item file:

    supported_architectures: ['x64']
    # Seconds. The EXE unpacks 3.3 GB, joins the parts and runs Office's setup.
    installer_timeout: 3600
    # With OFFICE_FORCE_APP_SHUTDOWN false, Microsoft's setup ends with 17006 while an Office
    # program is open. The client leaves the item for a run in which one of these runs.
    blocking_applications: [WINWORD, EXCEL, POWERPNT, OUTLOOK, ONENOTE, MSACCESS, MSPUB]
    # No install arguments: the EXE runs its own setup.bat.
    # Windows lists the product as "Microsoft 365 Apps for business - en-us" with the Office version;
    # an equal or newer version counts as installed.
    check:
      registry:
        name: 'Microsoft 365 Apps for business'
        version: '<version>'

A 32-bit Click-to-Run Office of an equal or newer version has the same name and version in
the Windows list, so the check calls it installed and the item does not change it to
64-bit. Where that matters, use an `installcheck_script` that also reads `Platform` under
`HKLM\SOFTWARE\Microsoft\Office\ClickToRun\Configuration`.

## Removing Office

Windows records this removal command for the product; with `DisplayLevel=False` added it
is silent (exit 0 and Office gone after 2.5 minutes on Windows Server 2025, 2026-11-13):

    "C:\Program Files\Common Files\Microsoft Shared\ClickToRun\OfficeClickToRun.exe" scenario=install scenariosubtype=ARP sourcetype=None productstoremove=O365BusinessRetail.16_en-us_x-none culture=en-us version.16=16.0 DisplayLevel=False

In the package tool's item that is `uninstall_command` (the program) and
`uninstall_arguments` (the rest).

## Tests

    python3 -m unittest discover -s Win-Microsoft365Apps/tests -t .

They need no network, no 7z and no AutoPkg.
