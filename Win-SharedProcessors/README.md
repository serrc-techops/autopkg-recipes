# Win-SharedProcessors

Eight AutoPkg processors for Windows installers, and the stub recipe that lets
other recipes use them. None of them needs the package tool or any other program
that is not in this repository or in AutoPkg, except `AuthenticodeVerifier`, which needs
`osslsigncode`: they work with any Cimian repository.
(The processor for the owner's own package tool, `pcman`, is in
`../Win-PcmanProcessors/`.)

AutoPkg looks only one folder below a search directory. So the processors, the
stub recipe and `tests/` sit here, and a recipe in another folder names a
processor like this: `com.github.serrc-techops.SharedProcessors/<Processor>`.

| File | What it is |
| --- | --- |
| `CimianImporter.py` | Publishes a downloaded `.msi`, `.exe` or app package (`.msix`, `.appx`, `.msixbundle`, `.appxbundle`) as a new version into a Cimian repository. The last step of a recipe. It is to a Cimian repository what AutoPkg's `MunkiImporter` is to a Munki repository |
| `ChecksumVerifier.py` | Stops the recipe when a file does not have the SHA-256 that its publisher gives |
| `AuthenticodeVerifier.py` | Stops the recipe unless a downloaded `.exe` or `.msi` carries a valid, timestamped Authenticode signature of the expected publisher, under a root that the recipe names. The `.pem` files `digicert-trusted-root-g4.pem`, `globalsign-code-signing-root-r45.pem`, `globalsign-root-r6.pem` and `microsoft-identity-verification-root-2020.pem` beside it are those public roots. It needs `osslsigncode` |
| `GitHubAssetDigest.py` | Reads the SHA-256 that GitHub records for a release asset |
| `GitHubNewestReleaseGuard.py` | Stops the recipe when the release that `GitHubReleasesInfoProvider` selected is not the newest one, so that a vendor's new spelling of a file name cannot send the recipe back to an old release unseen |
| `WindowsExeVersion.py` | Reads the version of a downloaded `.exe` from the file itself, for the version label that `CimianImporter` needs |
| `VersionFromName.py` | Reads the version label from the name of a downloaded file and checks its shape, for an `.exe` that has no version resource of its own |
| `MicrosoftStorePackageDownloader.py` | Downloads the one package of a free Microsoft Store product from Microsoft's delivery service, without the Store, and keeps it only when it has the SHA-256 that the Store's catalog gives. `microsoft-root-2011.pem` beside it is the public root that the delivery service's certificate is issued under |
| `SharedProcessors.recipe` | Stub. Carries the identifier `com.github.serrc-techops.SharedProcessors`. Does nothing |
| `tests/` | Tests. They need no AutoPkg and no network. The tests of `CimianImporter` need PyYAML (see below) |

**Line numbers.** Where this file gives a file and a line of the Cimian client (for
example `StatusService.cs:632`), the source is the repository `windowsadmins/cimian` at
commit `e10498b`; a line of AutoPkg is of AutoPkg 2.9.0. They were read by the writer on
2026-10-04 and have not been checked against any later version. A behaviour that no line
is given for is a decision of this repository, not a fact about Cimian.

## CimianImporter

The importer decides whether a version is new and what goes into the repository. It
does these things:

1. It checks the inputs. Nothing is read from the repository or written when a check
   fails. It hashes the installer once (SHA-256, in blocks), and checks the download's
   guard (see "A download that no step verified is refused").
2. It reads every pkginfo of the repository that has the item's name.
3. It stops with "Nothing new" when the repository has the version, or the installer file.
4. For an MSI it reads the version and the codes with `msiinfo`. For an app package it has read the
   identity name and the version from the package's manifest with the input checks (see "An app package's facts").
5. It makes the pkginfo of the new version: a copy of the template, or built from the
   inputs.
6. A dry run says what it would write. A real run copies the installer to `pkgs/`, then
   writes the pkginfo to `pkgsinfo/`.

It does **not build catalogs**. Run `makecatalogs` (Cimian's tool) after a publish: until
it has run, no PC sees the new version.

### The repository

The input `cimian_repo` is the root of the repository: the folder that holds `pkgs/` and
`pkgsinfo/` (`makecatalogs` reads `pkgsinfo/` and writes the catalogs; `CatalogBuilder.cs:42-49`).
When the input is not given, the AutoPkg preference `CIMIAN_REPO` is used: AutoPkg copies all its
preferences into the variables of a run (`autopkg`, lines 2232 to 2245), so a preference is a
variable of the same name. Set it with

    defaults write com.github.autopkg CIMIAN_REPO -string "<the repository's root>"

or in an override, never in a recipe. A repository that is not a folder, or that has no
`pkgs/` or no `pkgsinfo/`, is an error that asks whether the share is mounted. The
processor never makes the root, `pkgs/` or `pkgsinfo/`.

### The template is the repository

There is no template file. The template of a new version is the pkginfo with the same
`name` and the **highest version** under `pkgsinfo/`, in any folder. The name is compared
without regard to letter case, as the client looks names up (`CatalogService.cs:395-399`);
the new pkginfo keeps the spelling that the template has. Only files that end in `.yaml` are
read, as `makecatalogs` does (`CatalogBuilder.cs:49`). The highest version is the highest by
the client's own order (`CatalogService.cs:260-372`: numbers, not text, so `1.10` is higher than
`1.9`; `2.0` and `2.0.0` are one version; `alpha`, `beta` and `rc` sort before the release; a
three-part version that can only be a build date such as `26.8.1712` is read as one). A pkginfo
whose version the client cannot read is not ranked. Two of the same version: the one whose path
sorts later.

An item can have pkginfo files for several architectures (`supported_architectures`). The client
first drops the items that are not for the PC's architecture and then keeps the highest version
(`CatalogService.cs:43-56`; an item with no list is for all). So when the files of the item name
**different** lists, the run stops and asks for the input `cimian_architecture` (`x64`, `x86`,
`arm64`; `amd64` and `x86_64` are `x64`, as the client reads them, `CatalogService.cs:239-249`). With it, only the
files for that architecture (and those for all) are the template and decide "nothing new"; a new
version without such a file is built from the inputs with `supported_architectures: [<it>]`.
When the template is for all architectures (no list) and another file of the item names one, the new version is written
for the given architecture only (`supported_architectures: [<it>]`, with a NOTE): a copy for all would take the PCs of the other
architecture to this installer, since the client keeps the highest version among the files for its architecture or for all. A list that
the input `pkginfo` gives is the person's own. Files for all architectures and files for **one** named architecture need no input (the
installer is taken to be for that one, with a NOTE); files that name **two or more** different lists do. "Nothing new" by the installer's hash is
decided among the files for the given architecture too.
Files are named after the item and the version only, so another architecture's file of the same
version in the same folder is never overwritten: the run says whose it is and asks for a
`cimian_subdirectory`.

A pkginfo file is read only when its text holds the item's name (it cannot be the template
otherwise). A file that cannot be read (not text, not YAML) is named in a NOTE and left
out. When **no template is found** and such a file exists, the run stops: the template may be
among the unreadable files. It also stops when the repository has files of this item but none
with a version the client can read.

### What the new pkginfo gets, and from where

The new pkginfo is a copy of the template with these changes, and nothing else (the key
order of the template is kept):

| Key | Becomes | The client reads it at |
| --- | --- | --- |
| `version` | the label (see "The label") | `StatusService.cs:196-219`, `:632`, `:716` |
| `installer.location` | `<folder>/<name>-<version>.<extension>`, forward slashes, relative to `pkgs/`; the extension is the file's own (an app package keeps `.msixbundle`, say) | `DownloadService.cs:442-456` |
| `installer.hash` | the SHA-256 of the file, lower-case | `DownloadService.cs:193-200` |
| `installer.size` | the file's size in bytes | `StatusService.cs:2076-2079` |
| `installer.type` | `msi` or `exe`, from the file's extension; `msix` for each of the four extensions of an app package | `InstallerService.cs:871-873` |
| the `installs` entry of type `msix` (an app package): `identity_name`, `version` | the package's identity name and version; added, with a NOTE, when the template has none (see "An app package's facts") | `InstallerService.cs`, `BuildMsixInstallScript`; `StatusService.cs`, the msix check |
| an `installs` entry of type `msi` (written, or implied by a code): `product_code`, `upgrade_code`, `version` | the codes and the ProductVersion of the new MSI | `StatusService.cs:713-718` |
| `installer.product_code`, `installer.upgrade_code`, if the template has them (the older form) | the codes of the new MSI | `StatusService.cs:221-266` |
| `uninstaller[].product_code` of type `msi`, when it is the old product code | the new product code (the client runs `uninstaller[0]` first and counts an unknown product as removed) | `InstallerService.cs:727-737`, `:1507-1548` |
| `check.file.version`, `check.registry.version`, `version` of an `installs` entry that is **the template's version** (as the client reads versions) | the label | `StatusService.cs:1578-1587` (file), `:1496-1499` (registry), `:632` (installs) |
| `check.file.hash`, `md5checksum` of an `installs` entry | **dropped**, with a NOTE: they are the hash of an installed file of the old version. When that leaves a check that cannot work the run **stops** (see below) | `StatusService.cs:1613-1633`, `:606-621` |
| `force_install_after_date` | **dropped**, with a NOTE: once its date has passed the client installs the version wherever the item is optional and ignores the install window, and whoever publishes a version decides that for it | `UpdateEngine.cs:610-619`, `:1241-1290` |
| every other key (`catalogs`, `display_name`, `description`, `developer`, `category`, `icon_name`, arguments, scripts, blocking applications, `supported_architectures`, `unattended_*`, ...) | kept as the template has it. The input `pkginfo` does not change them (see "The input `pkginfo`"); every key it would have changed is named in a NOTE | |

Four things are said and not changed: a `version` inside `check` or `installs` that is **not**
the template's version is kept, with a WARNING that names the key (it may be right: a file's
version can differ from the product's); a text that holds the template's version as a whole token
(a script, a path) is kept, with a WARNING that names the key; an `installs` entry of type `msi` in
an `.exe` item is kept, with a WARNING; and for an MSI, an `installs` entry that is **another**
product's (a prerequisite) and an `uninstaller` code that is not the old product code are kept, with a WARNING.

**Which MSI entry is this product's.** The only `msi` entry of `installs`; when there are several, the one that
has the new MSI's upgrade code (if none or several do, the run stops: it cannot be told). Its codes and
version are replaced; the others are not.

**A dropped hash must not leave a check that cannot work.** A `check.file` that had a hash and
no version only tests that the file exists once the hash is gone (`StatusService.cs:1578-1610`),
so every old version would count as installed and the item would never be updated: the run stops and
names the entry, **but only when the client will use that check**: it consults, in this order, `installcheck_script`,
`version_script`, a non-empty `installs`, `check.registry`, `check.file` (`StatusService.cs:117-186`; an `OnDemand` item has none), so a
hash-only `check.file` beside an `installcheck_script`, a `version_script` or any `installs` does not stop the run. An `installs` entry of a file that had a hash and no version is compared with the item's
version afterwards (`StatusService.cs:632`); for a file with no version data of its own the client can
never confirm it (`:670-680`) and the item would install again at every run: the run stops. For a file that ends
in `.exe` or `.dll` it only warns, because the file may carry a version. **How to end the stop:** add `version:`, with the
template's own version, to that check in the template's pkginfo in the repository (this importer replaces a version that is the
template's with the new label on every publish, so each release gets its own), or give a literal version in the input `pkginfo` (it then
stays that version until it is changed), or use another install check. A version in the input `pkginfo` ends the stop only
if it is a version the client can read (next paragraph).

**A version the client cannot read is refused.** A `version` inside `check` or `installs` that is not a version (`latest`, an
unreplaced `%version%`, ...) is read by the client as equal to every version (`CatalogService.cs:260-275`), so the item would
count as installed whatever is on the PC. The run stops and names the entry, whether the value came from the template or from
`pkginfo`; an empty value is no version.

**Variables in the input `pkginfo`.** AutoPkg replaces the `%name%` variables of a recipe's `Input` once, before the first step runs
(`autopkglib/__init__.py:783-797`), and leaves the ones that nothing has set yet as they stand (`:432-437`), so `%version%`, which a
download step sets, reaches the importer as the text `%version%`. The importer therefore replaces, in the input `pkginfo` (nested
dictionaries and lists too), every `%name%` for which the run has a text or a number, and `%version%` by the label (for an MSI its own
ProductVersion). A `%name%` that remains is a name that nothing sets: the run stops before anything is written and names it and
its place (a typo would otherwise be written into the pkginfo). Windows environment variables such as `%ProgramFiles%` and `%TEMP%`
(a fixed list, any letter case) are meant as they stand and are kept. Only the input `pkginfo` is read this way: the text a template
carries is not (a script may hold any `%...%`).

**The new version goes into the template's catalogs.** A template in `Production` makes the
new version a candidate for `Production` as soon as `makecatalogs` has run. To put new versions
into another catalog first, give `catalogs` in the input `pkginfo` and set `cimian_pkginfo_wins` to
true in the override (see "The input `pkginfo`"). `cimian_catalogs` is only for a pkginfo that has no template.

The kind of installer cannot change: a template whose `installer.type` is `exe` stops the run for
an `.msi` and the other way round (its arguments and its checks are those of the other kind). The same
holds between an app package and an `.msi` or `.exe`, both ways. A template whose `installer.type` is
`msix` or `appx` is of the app package's kind (the client installs both the same way); an `appx` is written
`msix`, with a NOTE.
An MSI whose upgrade code is not the template's, or that has none where the template's item had one, is **refused**: it may be another product, or the
vendor changed the code, and Windows Installer does not upgrade across upgrade codes, so PCs could end
up with both. The input `cimian_allow_product_change`, set to true in the override, lets it go on with
a WARNING.

### The label

The label is the `version` input. For an `.exe` it is **required**: this processor never reads a
version from a file (that is `WindowsExeVersion`'s job, below). For an `.msi` the default is the
MSI's own ProductVersion, and another label is refused when `msiinfo` can read the MSI: the client
compares the label with the version that Windows Installer records. A recipe for an MSI passes an
empty `version` in its step, so that a version that an earlier step set (a release tag, say) is not
taken for the MSI's own. For an app package the rule is the same: the label is the package's own
Identity Version (for a bundle the bundle's), and a `version` input that is not that text is refused,
also in a dry run. The label begins with a digit and has letters, numbers, dots, underscores
and hyphens only (it becomes part of two file names).

### Without a template

The pkginfo is built from the inputs: `name`, `version`, `catalogs` (the input `cimian_catalogs`,
default `Development`: the catalog that Cimian's own tools use when none is named;
`cli/makepkginfo/Program.cs:49` and `:297`, `shared/import/Models/ImportModels.cs:276`), the
`installer` block (`type`, `size`, `location`, `hash`), for an MSI one `installs` entry of type `msi`,
for an app package one `installs` entry of type `msix` (and the single package's architecture, see "An app
package's facts"), and everything in the input `pkginfo`. The keys are written in the order of the model of Cimian's own
`makepkginfo` (`cli/makepkginfo/Models/PkgsInfo.cs:64-157`); keys it does not name follow in the
order they were given. **A person should then complete by hand**, in the input `pkginfo`, what the
processor cannot know:

- for an `.exe`, a way to tell that it is installed: an `installs` entry or a `check`. Without one the
  client treats an item that has none as not installed, unless the ManagedInstalls registry has a
  trace of it (`StatusService.cs:194-219` and `:268-298`); the run says so in a WARNING (not for an app
  package: its `installs` entry is the check);
- the silent arguments of the installer (not for an app package, which takes none), as `installer: {args: [...]}` (`args` is the key the client
  reads, `UpdateModels.cs:772-773`; `makepkginfo` writes `arguments`, `PkgsInfo.cs:24`);
- `display_name`, `developer`, `category`, `description`, `icon_name` and `unattended_install` if wanted.

The first publish makes the template of every later one. No default for the silent arguments or for
`unattended_install` is guessed.

### The input `pkginfo`

A dictionary of pkginfo keys. **Without a template** it is merged over the pkginfo that was built: a
dictionary in both is merged key by key, anything else (a list, a text, a number) replaces.

**With a template it does not change what the template has.** The recipes of this repository carry a
`pkginfo` in their `Input` (a display name, a developer) on every run, so a template is not to be renamed or given a
second set of arguments by it. A key that the template **lacks** is added, with a NOTE. A key that the template has with
**another value** keeps the template's value, with a NOTE that names the key and says how to change that. A dictionary
in both is compared key by key. The arguments of an installer are one group (`args`, `switches`, `flags`, `subcommand`;
the client joins them all, `UpdateModels.cs:804-827`): when the template gives them in one key, `pkginfo` does not add another.
With **`cimian_pkginfo_wins` set to true** in the override the values of `pkginfo` replace the template's instead, and a NOTE names
each key that was replaced (and each of the template's argument keys that was dropped for the group that `pkginfo` gave). A dry
run prints the same notes as a real run.

It cannot set `name`, `version` or `installer.location`, `.hash`, `.size`, `.type`: those belong to the file and the
inputs, and a run that tries is refused. After the merge the codes and the version of the MSI are set again (see "What the new
pkginfo gets"), and, for a pkginfo without a template, an `installs` entry for an MSI is added when there is none; there, an
`installs` entry of type `msi` in `pkginfo` gets the codes it lacks, and one with other codes than the MSI's is refused.

AutoPkg replaces `%variable%` in the strings of a dictionary too, also in nested ones
(`autopkglib/__init__.py`, `update_data`, lines 424 to 455), so a recipe can write `%CIMIAN_NAME%`
in its `pkginfo`. A `%variable%` that holds something that is not text stops the whole run with
an error of AutoPkg's, so none of the recipes in this repository does that.

### Nothing new

**The same version, or the same installer file, is in the repository: nothing is written, and it
is not an error.** The line `Nothing new: <name> <version> is in the repository already (...)`
is printed at every verbosity. The same version is decided as the client reads versions (`2.0`
and `2.0.0` are one); the same file is a pkginfo of this item whose `installer.hash` is the
file's SHA-256. When the version is there but with another installer file, the run also says
so in a NOTE and writes nothing: give the file a version of its own to publish it. The run
sets `cimian_result` to `nothing-new` and `cimian_repo_changed` to false.

For an MSI, "the same installer file" is decided before `msiinfo` is asked, so a run for a file
that is known needs no MSI facts. For an app package the version that is compared is its identity
version, and the rules are the same.

### A dry run is the default

`cimian_dry_run` is true unless the override sets it to false. A dry run **writes nothing**: not a
file, not a folder. It prints, at every verbosity (also without `-v`), a line that begins with
`WARNING: DRY RUN.`, the line `Would write <name> <version>: <pkginfo path> and <installer path>
(<size> bytes).` (paths relative to the repository), the template used, and the notes. It does not
print the pkginfo's text (it may hold install arguments or scripts); its lines name keys and versions, never other values.
It sets the outputs (the planned paths) and a summary row with the result `dry run, nothing
written`, so that a run that wrote nothing because of the default does not look like a run with
nothing to do. A dry run refuses what a real run refuses (a target that exists, missing MSI
facts, a pkginfo that cannot be written as YAML, a download that is not the file that was
verified).

A real run needs `cimian_dry_run` set to `false` (see "Switching on a real run").

### What a real run writes

1. The installer: copied to `pkgs/<folder>/<name>-<version>.<ext>`. It is copied to a temporary
   file beside the target (`.<file>.<random>.cimian-new.tmp`), hashed while it is written, and
   moved into place only when the copy has the SHA-256 that was verified. A mismatch is an error
   and removes the temporary file.
2. The pkginfo: written to `pkgsinfo/<folder>/<name>-<version>.yaml` the same way (a temporary
   file `.<file>.<random>.tmp`), after it was read back and found equal to what was meant. It is
   written **after** the installer, so a pkginfo never names a missing installer.

Neither file ever replaces another: a file is moved into place with a hard link, which fails when
the target exists (where hard links are not possible, as on some network shares, the target is checked and the file
is renamed: that is two steps, so **two runs of one item at the same moment could both pass the check and one
could overwrite the other's file; do not run two at once there**). A pkginfo at the target that is not a readable pkginfo of this item, an installer at
the target with other content, a link at the target: each is an error that names the file, and
nothing is overwritten. An installer at the target that has the same SHA-256 (an earlier run
stopped between the two writes) is kept, with a NOTE, and the pkginfo is written. A run stopped
by an error removes its temporary files; a kill of AutoPkg with `SIGKILL` can leave one (they
start with a dot and `makecatalogs` ignores them: it reads only `*.yaml`).

The folder is `cimian_subdirectory`, else the folder of the template's `installer.location`
(its leading slashes or backslashes are dropped first: Cimian's own importer writes a leading slash, and the client and
`makecatalogs` read the location as relative to `pkgs/`, `DownloadService.cs:442-452`, `CatalogBuilder.cs:96`),
else none (the files go directly into `pkgs/` and `pkgsinfo/`). It is a relative path of plain
folder names (letters, numbers, dots, underscores, hyphens, spaces; backslashes read as slashes);
`..`, an empty part, a leading slash or tilde and a drive letter are refused in `cimian_subdirectory`. A link **below**
`pkgs/` or `pkgsinfo/` that leads out of it is refused (`pkgs/` itself may be a link to another
disk). The permissions of both files are `0644`.

### A download that no step verified is refused

A download counts as verified only when one of two pairs of variables holds:

- `checksum_verified` is a boolean `true` (`ChecksumVerifier` sets it), and `checksum_sha256`
  (`ChecksumVerifier` outputs it: the hash of the file it checked) is a SHA-256 that equals the hash of
  the file about to be imported; or
- `signature_verified` is a boolean `true` (`AuthenticodeVerifier` sets it), and `signature_sha256`
  (`AuthenticodeVerifier` outputs it: the hash of the file whose signature it checked) is a SHA-256 that
  equals the hash of the file about to be imported.

`CimianImporter` hashes that file itself, once, in blocks, and uses the same hash for the
pkginfo and for the copy. Each hash is read like `ChecksumVerifier` reads an expected value:
64 hex digits, any letter case, with or without the prefix `sha256:`. A **real** run
(`cimian_dry_run` false) of a download that does not count (no pair has a flag that is `true`
together with a SHA-256) is refused with a `ProcessorError` before anything is read from the
repository:

    The download was not verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file, or signature_verified together with the signature_sha256 of this file. Nothing was published. Publish by hand after checking the file, or set cimian_allow_unverified to true in the override.

With `cimian_allow_unverified` true in the override the run goes on. It prints one
`WARNING: published WITHOUT a verified download ...` at every verbosity, and the summary row's
result is `published, NOT verified`. A dry run of an unverified download prints a `WARNING: the
download was NOT verified ...` and its summary row says `dry run, nothing written, NOT verified`.
A recipe whose download goes through `ChecksumVerifier` or `AuthenticodeVerifier` is not changed by this.

**A checksum for another file stops the run.** When a flag is `true` and its hash is a SHA-256 that
is NOT the hash of the file to import, the file that was verified is not the file that is imported.
That is not "unverified": it is a `ProcessorError` that names the pair (`whose checksum was verified`
or `whose signature was verified`) and shows both hashes shortened, also in a dry run, and
`cimian_allow_unverified` does not override it. Both pairs are checked: a good checksum does not hide
a signature of another file, nor the other way round.

A boolean `checksum_verified` or `signature_verified` written into an override's `Input` (or an AutoPkg
preference) therefore counts only together with the right hash. That is a pinned hash, chosen by whoever wrote
the override, and the override's trust information does not cover its `Input`.

### An MSI's facts

For an `.msi` the processor needs the ProductVersion, the ProductCode and the UpgradeCode. It
reads them with `msiinfo export <file> Property` (a program of msitools), started as a list without
a shell, with standard input closed, a time limit of 60 seconds and an environment of `PATH` and
`HOME` only. `msiinfo` is looked for on the `PATH` that the input `cimian_path` gives (default
`/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin`, because launchd's own `PATH` has
no Homebrew). The output is read tolerantly: the lines that have two fields separated by a tab and
whose first field is `ProductVersion`, `ProductCode` or `UpgradeCode`; a property named twice with
two values is an error; the codes must be GUIDs in braces. **This processor does not parse an MSI
itself.**

Where `msiinfo` is not on the path, the facts must come from the recipe or the override:
`version`, `msi_product_code` and `msi_upgrade_code`. **An argument of a recipe's step wins over an override's
`Input`** (AutoPkg applies a step's arguments after the `Input`, `autopkglib/__init__.py:617-620`), so a recipe whose step
passes an empty `version` (the MSI recipes of this repository do) cannot be given a version by its override: for those
recipes `msiinfo` is required. A run that lacks any of them stops, also in a
dry run, and names what is missing. When `msiinfo` is there and a given code is not the one it
reads, the run stops: the input is wrong or the file is another product. When `msiinfo` is not
there the facts that were given are used, and a NOTE says that nothing checked them against the
MSI. An MSI without an UpgradeCode is allowed, with a WARNING (the template's stale upgrade code is
removed).

### An app package's facts

An app package (`.msix`, `.appx`, `.msixbundle`, `.appxbundle`, any letter case) is installed by the
client itself, for every user of the PC, with `Add-AppxProvisionedPackage -Online -PackagePath <file>
-SkipLicense` (`InstallerService.cs`, `BuildMsixInstallScript`): it takes no arguments. **What is read.**
The package is a zip file. The processor opens it, reads one member into memory, at most 4 MiB
(`MAX_MANIFEST_BYTES`, checked against the size the zip records and again while reading), and extracts
nothing: `AppxMetadata/AppxBundleManifest.xml` for a bundle, else `AppxManifest.xml` (names compared with
forward slashes and without regard to letter case). A manifest with a document type or an entity
declaration is refused, so that no entity can expand. From the first `Identity` element under the root it
takes `Name` (letters, numbers, dots, underscores, hyphens), `Version` (two to four numbers, as the client
compares it with PowerShell's `[System.Version]`) and, for a single package, `ProcessorArchitecture`. For a
bundle the version is **the bundle's own**, which looks like a date (`2026.1028.1836.0`) and is not the
version of the application inside it: it is the version that Windows reports for the provisioned package.
A package that cannot be read stops the run, also in a dry run. The package is not run, and its signature
is not checked.

**What the pkginfo then holds.** `installer.type: msix`, `installer.location` with the file's own
extension, `installer.hash`, `installer.size`, `version` (the identity version), and one `installs` entry
`{type: msix, identity_name: <Name>, version: <Version>}`. That entry is the install check, and the client
finds and removes the package by its identity name. With a template, the template's only `msix` entry gets
the new version; its identity name must be the package's (compared without regard to letter case; the
package's spelling is written), or the run is **refused**: it is another product. When the template has
several `msix` entries, the one with the package's identity name is this package's (if none or several have
it, the run stops), and the others are kept, with a WARNING. A template without an `msix` entry is given one,
with a NOTE. Every other entry of `installs` and `check` follows the rules above. Without a template, an
`msix` entry that the input `pkginfo` gives must name this package and gets its version. An app package
takes no `installer.args`, `switches`, `flags`, `subcommand`, `success_codes`, `product_code` or
`upgrade_code`: one of them, from the template or from the input `pkginfo`, stops the run. The inputs
`msi_product_code` and `msi_upgrade_code` are not used.

**Architecture.** A single package whose `ProcessorArchitecture` is `x64`, `x86`, `arm` or `arm64` is for
that architecture: it is the default of `cimian_architecture` (a value that names another is refused), and
the rules of "The template is the repository" follow, so a pkginfo without a template gets
`supported_architectures: [<it>]` and a template keeps its own list. `neutral` names none. A bundle names
none: nothing is guessed for it, and `cimian_architecture` is used as for an MSI. Another value is said in a
NOTE and not used.

### Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `pathname` | yes | | The downloaded installer. It must exist and end in `.msi`, `.exe`, `.msix`, `.appx`, `.msixbundle` or `.appxbundle` (any letter case) |
| `cimian_name` | yes | | The item's name, the pkginfo's `name`: letters, numbers, dots, underscores and hyphens, not beginning with `-` or `.`, at most 100 characters. With a template the template's spelling is kept |
| `cimian_repo` | no | the preference `CIMIAN_REPO` | The repository's root. A leading `~` is expanded. Never in a recipe |
| `version` | `.exe` only | | The label. See "The label" |
| `cimian_subdirectory` | no | the template's folder, else none | The folder under `pkgs/` and `pkgsinfo/` |
| `pkginfo` | no | none | A dictionary of pkginfo keys. Without a template it is merged over the pkginfo that was built. With a template it only adds what the template lacks (see "The input `pkginfo`") |
| `cimian_pkginfo_wins` | no | `false` | `true`: the input `pkginfo` replaces the template's values (each key named in a NOTE). Parsed like `cimian_dry_run`. Set it in an override, never in a recipe |
| `cimian_architecture` | no | | `x64`, `x86` or `arm64` (`amd64` and `x86_64` are `x64`). Needed when the item's pkginfo files name different `supported_architectures`. For a single app package that names its architecture, that is the default and another value is refused |
| `cimian_allow_product_change` | no | `false` | `true`: an MSI whose upgrade code is not the template's goes on, with a WARNING. Parsed like `cimian_allow_unverified`. Set it in an override, never in a recipe |
| `cimian_catalogs` | no | `Development` | The catalogs of a pkginfo without a template: a list, or a text with commas |
| `cimian_dry_run` | no | `true` | `true`: plan only. `false`: a real run. Only a boolean or the text `false`, `no` or `0` (any letter case) makes a real run; `off`, `n`, `f`, an empty value or a number other than the text `0` is an error |
| `cimian_allow_unverified` | no | `false` | `true`: a real run of an unverified download goes on, with a WARNING. Parsed like `cimian_dry_run`: only a boolean or the text `true`, `yes`, `1`, `false`, `no`, `0`; anything else is an error, also for a verified download. Set it in an override, never in a recipe |
| `cimian_path` | no | `/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin` | The `PATH` where `msiinfo` is looked for |
| `msi_product_code` | no | | The MSI's ProductCode, `{GUID}`. Needed when `msiinfo` is not available |
| `msi_upgrade_code` | no | | The MSI's UpgradeCode, `{GUID}`. Needed when `msiinfo` is not available |

### Outputs

| Output | Meaning |
| --- | --- |
| `cimian_result` | `published`, `dry-run` or `nothing-new` |
| `cimian_version_imported` | The version label of the result (the planned one after a dry run; the one in the repository after "nothing new") |
| `cimian_pkginfo_path` | The pkginfo in the repository (planned after a dry run) |
| `cimian_installer_path` | The installer in the repository (planned after a dry run; not set after "nothing new") |
| `cimian_repo_changed` | True only when this run wrote to the repository |
| `cimian_importer_summary_result` | For AutoPkg's report. Set after a publish (result `published`; `published, NOT verified` for an unverified download) and after a dry run (result `dry run, nothing written`; `dry run, nothing written, NOT verified`). Columns: name, version, catalogs, result. No path: reports are mailed. The paths are the two output variables above |

The result line (`Published ...`, or the dry run's lines) and the warning for an unverified download are printed first and are
never cut; the notes after them are cut at 12 lines of at most 1500 characters each. The lines name paths relative
to the repository; `-vv` shows every input, among them the repository's root: keep the logs and
the cache of the machine that runs AutoPkg private (receipts hold the run's variables).

### What is written with PyYAML

The pkginfo files are read and written with PyYAML, which AutoPkg's own Python has (AutoPkg imports
it at `autopkglib/__init__.py:35`). It is imported inside the processor's `main`, after the inputs are
checked; a Python without it stops the run with an error that says so and writes nothing. The tests
that read or write a pkginfo are skipped in a Python without PyYAML. Only the booleans and null of YAML 1.2's core schema (`true`, `True`, `TRUE`, `false`, `False`, `FALSE`; `null`, `Null`, `NULL`, `~` and an empty value) and plain decimal integers (`900`, not `007`, `0x1F`, `1_000` or `+5`)
are read as such; **every other plain scalar is read as text**, as Cimian's own reader (YamlDotNet, into typed fields) takes it. PyYAML's own
rules are YAML 1.1: there `22:00` is the integer 1320 (an install window of 22:00 to 06:00 would become 1320), `2025.10` the number
2025.1, and `yes`, `no`, `on`, `off` booleans. A text that PyYAML would read as another type is written quoted (`'22:00'`), so it
comes back as the same text; a `version` is always text; a multi-line text is written as a literal block; the pkginfo is written in block style
with no anchors, as in the pkginfo files that Cimian's own tools write. Before a file is written
its text is read back and must equal what was meant.

### Measured against the package tool (2026-10-04)

On 2026-10-04, on scratch copies of a repository (never on the share), the importer was run for real under AutoPkg 2.9.0 against the package tool's pkginfo of three programs that the tool had imported:
an MSI program, an EXE program and one more MSI program. In each copy the tool's pkginfo had been made older (its version, its installer's name and its hash), so that the importer found a template of an
older version and published the new one. **With a template, the importer's pkginfo was byte for byte the package tool's** for each of the three (`diff` found nothing; the keys, their values and their
order were equal: the display data, the catalog, the icon, the architectures, `unattended_install` and `unattended_uninstall`, the installer's location, hash, size and type, for the EXE program its
arguments and its `check`, and for the MSI programs the `installs` entry). The importer's one NOTE was that the repository has pkginfo files of the item for all architectures beside the x64 template.
**Without a template**, the importer's pkginfo has `name`, `display_name`, `version`, the installer's hash, size and type, for an MSI the whole `installs` entry, and `developer` where the recipe's
`pkginfo` gives it; it lands in the catalog `Development`. It lacks, compared with the package tool's: the catalog `Production` (a PC that reads `Production` does not see the version at all), the item's folder
in `installer.location` (no difference for a PC), `supported_architectures` (the version is offered to every processor), `unattended_install` and `unattended_uninstall` (the client defers an install in an
automatic run while a user is active when `unattended_install` is false: `UpdateEngine.cs:684-712` at `3cf02c4`, as read by the operator of that day), the installer's arguments and the install check of an EXE
(the importer warns that there is no check; without it the item counts as installed only through the ManagedInstalls registry), `category`, `description` and `icon_name` (Managed Software Center only), and
`developer` where the recipe's `pkginfo` does not give it. That is what a person completes by hand, as the sections above say. One of the three runs needed `cimian_allow_unverified` (its download had no
verification step); it was set in the scratch override only. The order of the keys differs without a template (`name` first, as Cimian's own `makepkginfo` writes them) and nothing depends on it.

### Not established

Until 2026-10-04 nothing here had run with AutoPkg, with a real Cimian repository or with a real `msiinfo`. Since then the importer has run under AutoPkg 2.9.0 on scratch copies of a repository
(the section above) and with the machine's `msiinfo` for MSI files, and its dry runs against the real repository ended in `Nothing new` for the three programs whose template was an MSI or an EXE item. The ten programs whose item was a Chocolatey `nopkg` item were refused, as designed ("The template ... is of the kind nopkg, and the file is an .exe ..."). The tests
use a temporary repository, files with bytes in them, and a stand-in for `msiinfo` whose output
follows the description above. NOT established: the exact output of a real `msiinfo` for an MSI other than those of 2026-10-04
(the parser is tolerant on purpose); that a pkginfo written by this processor is accepted by
every version of the client and of `makecatalogs`; that `makecatalogs` finds nothing to complain
about in the result (its `--hash_check` option compares an MD5 with `installer.hash`,
`CatalogBuilder.cs:120-127`, while the client checks a SHA-256, `DownloadService.cs:193-200`: do not
take a mismatch of that option for a bad file); how the owner's catalogs treat a new version in the
template's catalog; what Cimian's YamlDotNet and the client's time parsing do with a text such as `22:00` or `1320` (the rules above are
YAML's, and the reading of the client was not run); whether Cimian's own tools write such values quoted or not; which PyYAML AutoPkg's
Python carries (the code needs 5.1 or later for `sort_keys`). App packages: the tests use made-up zip files with a manifest
in them; no real Store package has been published by this processor, and no PC has installed one from a pkginfo it wrote.

## ChecksumVerifier

Hashes the file itself, in blocks, and compares it with the expected value.

| Input | Required | Meaning |
| --- | --- | --- |
| `pathname` | yes | The downloaded file |
| `expected_sha256` | yes | 64 hex digits, in any letter case, with or without the prefix `sha256:`. Nothing else is accepted (no file name after the digest) |

| Output | Meaning |
| --- | --- |
| `checksum_verified` | True when the hash matched. An importer reads it, together with `checksum_sha256` (`CimianImporter`: see its section): without both, and the hash of the file to import, a real run is refused |
| `checksum_sha256` | The hash of the file that was checked (lower-case hex). The importer compares it with the hash of the file it imports |

An empty value, a value that is not a SHA-256, a file that cannot be read, or a
different hash is a `ProcessorError`. The message shows both hashes shortened.

## AuthenticodeVerifier

Some vendors publish no hash for their Windows installer, but sign it. This processor checks that
signature with `osslsigncode` and stops the recipe unless all of this holds, for the signature and for
every signature nested in it:

1. **What the signature covers.** `osslsigncode` confirms the signature over what Authenticode covers.
   For a PE file (`.exe`) that is every byte of the file except the checksum field of the header, the
   certificate table's entry in the header, and the certificate table itself. For an MSI it is the content of
   every stream except the two signature streams, and, through the stream `MsiDigitalSignatureEx`, the
   streams' metadata. An MSI without `MsiDigitalSignatureEx` is refused (`osslsigncode` 2.16 only warns).
2. **Nothing outside it, for a PE file.** The certificate table, which the signature does not cover, must hold
   exactly one entry, of the PKCS#7 kind (revision 2), which starts on 8 bytes, ends at the end of the file, and
   holds the signature that was read and nothing but zero bytes of padding to the next 8 bytes. A second entry,
   bytes inside the entry after the signature, or bytes after the table are refused.
   **What remains inside the table.** The signature itself has parts that it does not cover, and anyone could add
   bytes there without breaking it. These are closed, in the signature, in each nested one and in the timestamp
   (its token or its countersignature):
   - an unsigned attribute of a `SignerInfo` may only be Microsoft's RFC 3161 timestamp token, the older PKCS #9
     countersignature or Microsoft's nested signature (their identifiers are in the processor,
     `ALLOWED_UNSIGNED_ATTRIBUTES`), each at most once and at most one timestamp; any other is refused with its
     identifier in the message, and a timestamp may carry none of its own;
   - a CRL field is refused;
   - the parameters of every algorithm identifier that is read (the `digestAlgorithms` entries, a `SignerInfo`'s
     digest and signature algorithm) must be absent or NULL. None of the four real signatures read on 2026-11-19
     had others; a publisher that signs with RSASSA-PSS or ECDSA parameters is refused until that shape is added;
   - `digestAlgorithms` must hold exactly the digest algorithm of the one `SignerInfo`, nothing more;
   - the version numbers must be the ones the standards give, each written as one byte
     (`SIGNATURE_SIGNED_DATA_VERSIONS` 1, `TOKEN_SIGNED_DATA_VERSIONS` 3, `SIGNER_INFO_VERSIONS` 1).

   **The certificates are the only unsigned kind left.** The certificates that the signature carries, and those
   that the timestamp token carries, are not covered by the signature, and an added certificate can hold bytes of
   anyone's choosing (real signatures carry certificates that are on no chain, cross-certificates and the same
   certificate twice, so a stricter rule would refuse genuine files). Windows accepts such a file too. It matters
   only for an installer that reads its own signature area; for the others those bytes are never read, but the file
   is then not byte for byte the publisher's. So for a PE file, every byte is covered by the signature or checked
   here, except the checksum field, the table's entry in the header, and the certificates inside the signature.
3. **The roots.** The chain of the signing certificate ends in a root that the recipe names in
   `code_signing_roots`, and the chain of the timestamp in a root that the recipe names in `timestamp_roots`.
   The tool is given those roots and no others (`-CAfile`, `-TSA-CAfile`); the system's roots are not used.
   Each root is a `.pem` file beside the processor, and the processor holds the SHA-256 of its DER form
   (`PINNED_ROOTS`): a file with another one, or with more than one certificate, is refused. The last
   certificate of each chain that the tool prints must be one of the named roots (compared by serial number).
4. **The timestamp.** The signature must have a timestamp, and the tool must have verified it. The chain is
   then judged at the time of the timestamp, so a signing certificate that has expired since, or that lived a
   few days only (a signing service that issues a new certificate for every release), still counts. A signature
   without a timestamp is refused, by the processor's own reading of the signature and by the tool's output.
5. **Revocation.** The tool reads the CRL that the signing certificate names (its CRL distribution point) and
   the CRL that the timestamp's certificate names, over HTTP, while it verifies. The output must say
   `Signature CRL verification: ok` and `Timestamp Server Signature CRL verification: ok`: a CRL that cannot be
   fetched (no network, a server that is down, an answer that is not a CRL), a revoked certificate, and a
   certificate that names no CRL are each a refusal.
6. **The digest algorithm.** The digest of the file that was signed and the signer's digest must use an
   algorithm that the recipe allows in `digest_algorithms`: `sha256` by default; `sha1`, `sha384` and `sha512`
   when the recipe names them. The timestamp's own `SignerInfo` (the timestamp authority's digest) must use one of
   them too. MD5 is never accepted.
7. **The signer.** The certificate that signed has exactly the subject fields that the recipe gives in
   `expected_signer`. See "Which certificate signed".

### Which certificate signed

A signature's PKCS#7 carries a bag of certificates, and anyone can add a certificate to that bag, also one with
the expected publisher's name. So the processor does not look for a name in the bag or in the tool's printed
text. It reads the signature itself (`osslsigncode extract-signature`, in DER, with a small reader in the
processor that accepts DER only): the one `SignerInfo` names its certificate by issuer and serial number, and that
certificate is taken from the bag. Then:

- the bag must hold exactly one certificate with that serial number (the same certificate twice, byte for byte,
  counts as one: a signing service was seen to add it twice), and its issuer must be the one that the
  `SignerInfo` names; two different certificates with the serial number are refused, whatever their issuer;
- the certificate whose chain the tool prints as verified (its `Signer #0`) must have that serial number;
- its subject is decoded field by field (`UTF8String`, `PrintableString`, `IA5String`, `BMPString`,
  `UniversalString`; another string type is refused), so an escaped comma (`Example\, Inc.` in the tool's text),
  quotes and letters such as `ö` need no parsing of a printed name.

**The fields.** `expected_signer` must give `CN`, `O` and `C`, and it gives every one of `OU`, `L` and `ST` that
the signing certificate carries. Each field that it gives must be in the subject exactly once and equal the given
text exactly (letter case included; no other normalisation). Each of these six fields that it does not give must
be **absent** from the subject: a recipe for a publisher whose certificate has no `ST` names none, and a
certificate with an `ST` is then refused. Other kinds of field (such as `emailAddress`) are not compared. `CN`,
`O` and `C` alone do not identify one legal entity (the same name can be registered in another state or at
another register court), which is why the recipes give `L` and `ST` too. When a publisher's next certificate
names another place (an office move), the step stops the run until a person has looked and changed the recipe:
that is intended.

A `SignerInfo` that names its certificate by a key identifier, a SignedData with more than one `SignerInfo`,
signed content that is not Authenticode's `SpcIndirectDataContent`, and anything that is not DER (an indefinite
length, say) are refused. The certificate itself (its thumbprint or serial number) is never pinned: certificates
are renewed, and some publishers get a new one for every release.

### An MSI's container is not checked

For an MSI, the processor checks the signature and the stream `MsiDigitalSignatureEx`, not the layout of the
compound file that holds the streams. Tried with `osslsigncode` 2.16 on a signed MSI, all of these pass the tool
and this processor: bytes appended after the last sector; a changed byte in the unused part of a stream's last
sector; a changed byte in an unused directory entry. They are not part of any stream, and Windows Installer reads
streams; but such an MSI is not byte for byte the file that the publisher signed, and the hash that the importers
compare is the hash of those bytes. Closing this needs a reader of the whole compound file (its sector tables, the
unused parts of sectors and of the directory, the small-stream area), which this processor does not have. So for
an MSI, "verified" means: the streams are the publisher's; not that every byte of the file is.

An MSI with a nested signature (for example one signed with SHA-1 and again with SHA-256) is refused as the
processor stands: it requires exactly one `MsiDigitalSignatureEx` line in the whole output, and whether the tool
prints one for each signature was not tried (no such MSI was at hand). That fails closed; a recipe for such an MSI
needs that rule changed and tried first.

### What it runs

The file is first copied to a new private temporary folder and hashed while it is copied; every check runs on
the copy, and the folder is removed afterwards. The processor sets no size limit of its own: a very large
download is copied whole into the temporary folder. The tool runs as a list, without a shell, with standard
input closed and an environment of `PATH=/usr/bin:/bin` and `HOME` only (so a proxy setting of the run is not
passed on):

    osslsigncode --version
    osslsigncode extract-signature -in <copy> -out <folder>/signature.p7
    osslsigncode verify -in <copy> -CAfile <folder>/code-roots.pem -TSA-CAfile <folder>/timestamp-roots.pem

The two `.pem` files of the third command are written from the checked DER of the named roots. The version must
be 2.16 or later: the output was read with 2.16 (with OpenSSL 4.1), and a version that prints otherwise is
refused by the checks of its output. The verify step has a time limit of 300 seconds (it fetches CRLs), the
others 60.

The verify step must end with exit code 0 and the line `Succeeded`, report as many verified signatures as the
file holds, and print for each signature, in the order of the file: `Timestamp Server Signature CRL
verification: ok`, `Timestamp Server Signature verification: ok`, `Signature CRL verification: ok`, `Signature
verification: ok`, one `Signature verification time:`, and both chains it verified; `Timestamp is not
available` is a refusal. For an MSI it must also print `Current MsiDigitalSignatureEx` and `Calculated
MsiDigitalSignatureEx` with the same value. Only the standard output is read for this; a refusal shows up to 8
lines of either output that say what failed.

`osslsigncode` is looked for in `/opt/homebrew/bin` and in `/usr/local/bin`, Homebrew's two places, and
nowhere else: not on the run's `PATH`, and not where an input says. No input of a recipe, an override or `-k`
can name another program. Without it the run stops: `brew install osslsigncode`.

| Input | Required | Meaning |
| --- | --- | --- |
| `pathname` | yes | The downloaded `.exe` or `.msi` (any letter case). Another kind of file is refused, and so is a file whose first bytes are not those of its kind |
| `expected_signer` | yes | A dictionary of the signing certificate's subject fields: `CN`, `O` and `C`, and every one of `OU`, `L` and `ST` that the certificate carries. Each is compared exactly, as text; a field of these six that is not given must be absent. Another key is refused |
| `code_signing_roots` | yes | The names of the pinned roots that the signing chain may end in: a list, or one text with commas |
| `timestamp_roots` | yes | The same for the timestamp's chain |
| `digest_algorithms` | no | The digest algorithms that the file digest and the signer may use: a list, or one text with commas, of `sha1`, `sha256`, `sha384`, `sha512`. Default `sha256` only. `md5` is refused as an input |

| Output | Meaning |
| --- | --- |
| `signature_verified` | True when every check passed. An importer reads it together with `signature_sha256` (see "A download that no step verified is refused") |
| `signature_sha256` | The hash of the file that was checked (lower-case hex). The importer compares it with the hash of the file it imports |
| `authenticode_signer` | The fields that were compared, as `CN=..., O=..., C=...` |
| `authenticode_signing_time` | The time of the timestamp, as the tool prints it: the time at which the chain was judged |
| `authenticode_tool` | The versions of `osslsigncode` and OpenSSL that checked the file |

Every failure is a `ProcessorError` that names the file and the reason, and sets no output.

**The pinned roots.** A recipe names roots by these names. The SHA-256 of each is in the processor; compare it
with the owner's own page before a root is added or changed. DigiCert's page gives SHA-256 fingerprints;
GlobalSign's and Microsoft's pages give only SHA-1 thumbprints, so for those the SHA-1 is what was compared.

| Name | Root | Valid until |
| --- | --- | --- |
| `digicert-trusted-root-g4` | DigiCert Trusted Root G4 | 2038-01-15 |
| `globalsign-code-signing-root-r45` | GlobalSign Code Signing Root R45, a root for code signing only | 2045-03-18 |
| `globalsign-root-r6` | GlobalSign Root CA - R6. A timestamp chain of GlobalSign's "Timestamping Root R45" reaches it through the cross-certificate that the timestamps carry | 2034-12-10 |
| `microsoft-identity-verification-root-2020` | Microsoft Identity Verification Root Certificate Authority 2020, the root of Microsoft's signing service for other publishers and of its timestamps | 2045-04-16 |

**The timestamp authority.** Only its root is pinned: any certificate with the time-stamping purpose under the
named timestamp root can timestamp. That matters only together with a stolen publisher key (a timestamp dated
back to before a revocation).

**What it proves.** The file is one that the expected publisher signed, under a root that the recipe chose, with
a timestamp, and the signing certificate was not on its CA's CRL when the run read it; for a PE file, that every
byte is covered by the signature or checked here, except the checksum field, the table's entry in the header and
the certificates that the signature carries (see item 2).
**What it does not prove.**
- That the release is harmless: a bad release that the real publisher signed passes.
- That it is the product and the version that the recipe wants: an older release, or another program that the
  same publisher signed, passes this step. The recipes check that elsewhere: for an MSI the importers compare
  the upgrade code with the item's; for an EXE the recipe's `WindowsExeVersion` step compares the version
  resource's product and company names (the resource lies inside what the signature covers) and takes the label
  from it.
- That the publisher's key was not stolen before the CA revoked the certificate.
- That a certificate revoked within the last CRL period is caught: the CRL comes over HTTP, and someone on the
  way can hand over an older CRL that is still within its validity.
- Anything about the revocation of an intermediate certificate: only the signing certificate's and the
  timestamp certificate's CRLs are read, and OCSP is not used.
- For an MSI, that every byte of the file is the publisher's (see "An MSI's container is not checked").
- That the certificates inside the signature are the publisher's: an added one passes (see item 2).

A recipe that names a broad root (one that issues for many publishers) depends on the `expected_signer` fields to
tell publishers apart, and those fields are what the CA verified about the publisher.

## GitHubAssetDigest

GitHub's API gives each release asset a `digest` (`sha256:<hex>`). The core
processor `GitHubReleasesInfoProvider` has no output for it. This processor
fetches the record of one asset, anonymously, from `api.github.com`, and
outputs the hash for `ChecksumVerifier`. A redirect is not followed: it is an
error that names the status.

| Input | Required | Meaning |
| --- | --- | --- |
| `github_asset_api_url` | yes | `https://api.github.com/repos/<owner>/<repo>/releases/assets/<id>`. Any other URL is refused |

| Output | Meaning |
| --- | --- |
| `expected_sha256` | The hash of the asset (lower-case hex, no prefix) |

A failed request, an answer that is not JSON, a record without a `digest`, or a
digest that is not a SHA-256 is a `ProcessorError`. The file and the hash come
from the same place: this check shows that the file is what GitHub holds.

## GitHubNewestReleaseGuard

AutoPkg's `GitHubReleasesInfoProvider` walks the releases of a repository in the order that GitHub lists them (newest first), skips a pre-release unless
`include_prereleases` is set, skips a release that has no files, and takes the first release that has a file whose name matches `asset_regex`, however old that
release is (AutoPkg 2.9.0, `GitHubReleasesInfoProvider.py:173-201`, `select_asset`). The provider has no rule for drafts; GitHub lists them only for people with push
access to the repository (its documentation, not re-read on 2026-10-04), and none of the eight lists read anonymously on 2026-10-04 held one. When a
vendor changes the spelling of a file name the provider goes back to the last release with the old spelling and says nothing (see "When a vendor renames a file").
This processor stops the run in that case. It sits right after the provider and before `URLDownloader`, so nothing is downloaded when it stops, and it also runs in
the check phase.

**How it learns which release was selected.** The provider keeps the selected release and asset in its own object (`:204-205`) and puts only `url`, `asset_url`,
`asset_created_at`, `version` and `release_notes` into the run (`:235-255`). `version` is the tag with a leading `v` and dots stripped (`:244-248`), which is not
enough to find a release. `asset_url` is the API URL of the selected asset and ends with the asset's number (`:238`). The record of an asset has no key that names its
release (its keys are `browser_download_url`, `content_type`, `created_at`, `digest`, `download_count`, `id`, `label`, `name`, `node_id`, `size`, `state`,
`updated_at`, `uploader` and `url`), so the asset's record cannot say which release it belongs to. The guard therefore reads the owner, the repository and the asset's
number from `asset_url` (the repository cannot differ from the provider's), fetches the release list, takes the newest release that the provider could take, and looks
for the asset's number among the files of that release. Found: the run goes on. Not found: `ProcessorError`.

**The rule for the newest release.** The first release of GitHub's list (the order that the provider walks) that is not a draft, is not a pre-release unless `include_prereleases` is
true, and, when `release_tag_pattern` is given, has a tag that matches it. **The guard compares positions in the list, not versions.** `include_prereleases` is
read from the run's variables and tested for truth like the provider tests it (any non-empty value counts, the text
`false` included; keep it a boolean). It is not passed by a step: a `%variable%` that holds a boolean stops the whole run with a TypeError. A release **without files
counts**: when the newest release has none, the run stops, and the message says that the release has no files. When a whole page of thirty releases
is pre-releases, drafts or of another line, the next page is read, up to three pages; when no release can be compared the run stops and says so.

**Two lines of releases side by side.** A vendor that keeps publishing releases of an older line between the releases of a newer one breaks the plain rule in both
directions, and the provider has no idea of a line either: it takes the first release in the list that has a file matching `asset_regex`. Replayed on the saved list of
one such vendor (Greenshot, 2026-10-04), a recipe that follows the 1.4 builds (the 1.4 pattern, `include_prereleases` true) took the right 1.4 build every time, and the guard stopped
it whenever a 1.3 release was on top, from 2026-01-05 until 2026-10-02. In the other direction, a maintenance release of the old line published after the first release of the new line is first in the list; when
`asset_regex` matches the files of both lines the provider takes the old line and a guard without a pattern passes it unseen. So **a recipe that follows one line says
so explicitly**: the override's `release_tag_pattern`, a regular expression matched from the start of the tag (`re.match`, like the provider matches `asset_regex`), for example `v1\.4\.`.
Only a release whose tag matches counts as the newest (the pre-release and draft rules apply inside the line). The pattern does not choose the provider's file: `asset_regex`
does; the guard only compares. Without the pattern every release is of one line. The provider's own remedy for odd release orders, `sort_by_highest_tag_names`, is not supported (below).
**A pattern hides the releases it leaves out, so it says which ones, in every run, not only with `-v`**: when releases that would count (not a draft, and passing the pre-release rule) are listed
above the newest release of the line, one line names the newer ones: `release_tag_pattern '<pattern>' left out <n> newer release(s) of <owner>/<repo>: '<tag>', ... (and <m> more).
If one of them carries the installer that this recipe should take, the pattern hides a rename.` (at most five tags are named, then how many more). Replayed on the saved list of a vendor whose
installer was renamed in its newest release, a pattern that follows the old line (`v20\.`) passed the run in silence; now the line names the newer releases it left out. The pattern is for two
lines of releases, not a cure for a rename: the stop messages say so.

**A newest release that has no installer on purpose.** A development build with only a `.zip` can be the newest release. The guard stops
the run, and the provider has rightly taken the installer below it. Once somebody has looked at that release, the override's `accepted_newest_release` names its **tag**, as text (the message
gives the exact `PlistBuddy` command with the tag when the tag has only letters, digits and `._+-`; a tag with another character gets no command, because it comes from GitHub and a shell reads it,
and the message says to copy the tag exactly as the vendor's release page writes it). The guard still asks GitHub. **An acceptance is offered, and honoured, only for a release without a Windows
installer file**, a file whose name ends in `.msi`, `.exe` or `.msix` (`INSTALLER_EXTENSIONS`, in any letter case): a release that has one is a renamed installer, and the cure is the pattern. For such a
release the message names the installer files, says so and prints no command; a tag that was accepted while the release held only a `.zip` stops passing when an installer file is added to that release later.
A release that is only still being filled in passes by itself on the next run. The acceptance also does not cover **a rename below it**: it holds only when no release that lies between the newest one and the selected one
(a release that would count, in the list) has a Windows installer file either, and the selected release is not listed above the newest (with a tag pattern it can be); otherwise the run stops and the message names
the releases between, with their files, and says that an acceptance does not cover them. Two releases without an installer in a row are accepted with the tag of the newest one. The run goes on **only
while that release is the newest**, and it says so in every run, not only with `-v`, in one line, and in AutoPkg's end-of-run table (below): `An older release is taken
on purpose: the newest release of <owner>/<repo>, '<tag>', has <n> file(s) (<names>) and the override accepts it as the newest (accepted_newest_release); the provider took ...`. When a newer release appears
(for example the vendor renames its installer in the next release) the tag no longer matches and the run stops again, naming the new release and its files. A tag that is set but not needed (the selected
release is the newest) is said with `-v`. The input is text: `true` or any non-text value is an error. It replaces a switch of the first version, `allow_older_release`, which turned the whole check off
and so hid every later rename; a recipe that still sets it is refused with a message.

| Input | Required | Meaning |
| --- | --- | --- |
| `github_asset_api_url` | yes | `https://api.github.com/repos/<owner>/<repo>/releases/assets/<id>`, from the provider's output `asset_url`. Any other URL is refused. The repository that is asked about is the one in it |
| `include_prereleases` | no | Not passed by a step. The recipe's `Input` key of the provider, read from the run |
| `accepted_newest_release` | no (default empty) | A key of the override's `Input`, never of the recipe. The tag of the newest release that has no Windows installer file on purpose (see above). Empty: no release is accepted |
| `release_tag_pattern` | no (default empty) | A key of the override's `Input`. A regular expression matched from the start of a tag: only a release whose tag matches can be the newest (see "Two lines of releases"). Empty: every release |
| `sort_by_highest_tag_names` | no | The provider's input of that name. Not supported: when it is set (any non-empty value) the guard refuses the recipe |
| `latest_only` | no | The provider's input of that name. Not supported: when it is set the guard refuses the recipe |
| `url` | no | The provider's download URL. Used only to name the selected release in the message when the list does not hold the asset |

**The provider's `sort_by_highest_tag_names` and `latest_only` are refused.** The first sorts each page by `APLooseVersion` of the tag (`:222-225`), the second asks only for the release that the
vendor marked as latest (`:148-149`); both change which release the provider takes, so the guard's idea of the newest release (GitHub's order) would differ from the provider's without a word.
The guard does not model them: a recipe that sets either input stops with a message that says so, whatever else is set, before anything is asked. Remove the input from the override;
for a vendor with two lines use `release_tag_pattern`. (A fact of AutoPkg 2.9.0, outside the guard: with `latest_only` and no matching asset the provider's loop, `:214-232`, asks again and again,
because `get_releases` ignores the page in that mode, `:148-151`.)

**The output.** The processor has one output variable, `github_newest_release_guard_summary_result`, set only when a run goes on with something that a person should look at: an older release taken on
purpose, or newer releases that `release_tag_pattern` left out. AutoPkg collects every variable whose name ends in `_summary_result` (the neighbours: `cimian_importer_summary_result`, `url_downloader_summary_result`)
into its end-of-run table and its report plist: `summary_text`, `report_fields` (`repository`, `newest_release`, `release_taken`, `reason`) and a `data` dict of text, as AutoPkg's table needs. It holds tags and a reason: no
secret, no path. The variable is cleared at the start of each run of the processor, so that a result of an earlier recipe is not reported again. With `-v` the processor prints `The selected release '<tag>' of <owner>/<repo> is the newest release that is not a pre-release.` when it passes;
the release is written as `'<tag>' (titled '<title>')` when GitHub's title is another text than the tag (4 of the 8 repositories on 2026-10-04), and `whose tag matches '<pattern>'` follows
when `release_tag_pattern` is set.

**The message of a stop** names the selected release and file, the newest release and **all its files up to thirty** (the new spelling of the installer's name is among
them), **the releases between the newest and the selected one, with their files** (up to five; a rename below a dev build is seen there), says how the provider chooses, and what to do: correct
`SEARCH_PATTERN` (the provider's `asset_regex`) in the override; or, only when none of those releases has a Windows installer file, accept the newest release by its tag; or, for two lines of releases and
only then, name the line with `release_tag_pattern`. When the selected file is **not in the list that was read** the message says that the list may have changed after the provider read it (the guard's request is anonymous and
the answers to anonymous requests carry `cache-control: public, max-age=60`, so a list may be up to a minute old, which was not established; the provider's request is the machine's own), so that a run should be repeated before anything is changed, or that the release is older than the releases
that were read. Text that comes from GitHub is shown with printable characters only (a backtick is shown as a single quote, because a message marks its commands with backticks) and cut at 80 characters.

**The request.** One anonymous `GET` of `https://api.github.com/repos/<owner>/<repo>/releases?per_page=30&page=1` with a time limit of 30 seconds and no credential: it
reads no token file, no preference and no environment variable, so no token reaches the run's variables (AutoPkg writes them into its receipts). The host is fixed in
the code. A redirect is not followed: it is an error that names the status. An answer is read up to 8 MiB (a page of up to thirty releases was 0.13 to 0.82 MB in the eight
repositories read on 2026-10-04). A 404 names the repository (it does not exist or is not public; a repository without releases answers 200 with an empty list, which stops the run with its own message). A 403 or 429 with `X-RateLimit-Remaining: 0` (or a `Retry-After`) is said as GitHub's limit for anonymous
requests, with the time at which it ends; any other status is named. An answer that is not JSON, not a list of releases or too large is an error.

**Requests of a run, and GitHub's limit.** The limit for anonymous requests is 60 an hour for one address (`X-RateLimit-Limit: 60` on every answer of 2026-10-04), and
every other anonymous use of the address counts. A run of one download recipe asks the guard's one request, `GitHubAssetDigest`'s one (when the recipe has that step), and
the provider's own (one page of thirty releases, with the machine's token when it has one: the provider reads it itself, from AutoPkg's preference or a file). A run of the
eight recipes that use the provider makes **8 anonymous requests with the guard and 7 with `GitHubAssetDigest`** (one of the eight has no digest step): 15 anonymous requests,
where the digest alone made 7, plus the provider's 8 (authenticated with a token, anonymous without one: 23 in all). That counts one override of each product: when a nightly run
runs both overrides of a product (the generic one and the package tool's), each runs the download recipe's steps and the numbers double (30, and 46 without a token). That fits one run an hour with room. At 15 requests a run, four runs of
all eight in an hour (for example a dry run and a real run, twice) use the whole limit; at 23 (no token) two runs do, and a third stops on it. A run that stops on the
limit says so and is run again later. The guard could save its request by passing the digest of the asset on (the list holds each asset's `digest`): that is not built.

## WindowsExeVersion

Several Windows installers are `.exe` files at a fixed address, with no version in
the address and no hash from the vendor. `CimianImporter` needs a version label
for an `.exe` (its input `version`), and the label must be the
`ProductVersion` that a person reads in the file's properties. This processor reads
it from the downloaded file, in Python, with no other program. It writes nothing
and uses no network.

**What it reads.** The file is a PE file. The processor reads the DOS header and the
PE header, the optional header (PE32 and PE32+) with its data directories, and the
section table. It follows the resource directory (root, type `RT_VERSION`, the first
name, the first language) to the data entry, and reads that one block: the
`VS_VERSIONINFO` structure. In it are the fixed file information (`VS_FIXEDFILEINFO`,
four numbers for the file version and four for the product version) and the strings
of the first `StringTable` (`FileVersion`, `ProductVersion`, `ProductName`, and
others). The blocks are walked by their own length and by the padding to four bytes,
never by fixed offsets. A string ends at its first null character and is stripped of
white space.

Only what is needed is read: the headers, the section table, the resource directory
and the one version block. The whole file is never read (an installer can be hundreds
of megabytes). A version block of more than 1 MiB is an error.

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `pathname` | yes | | The downloaded `.exe` |
| `set_version` | no | `true` | `true`: set `version` (see below). `false`: leave `version` as it is. Parsed like `cimian_dry_run`: only a boolean or the text `true`, `yes`, `1`, `false`, `no`, `0` (any letter case); anything else is an error |
| `expected_product_name` | no | empty | When given: the `ProductName` string must be exactly this text, or the run stops |
| `expected_company_name` | no | empty | When given: the `CompanyName` string must be exactly this text, or the run stops |
| `expected_version` | no | empty | When given (with `set_version` true): the label that this processor chooses must be exactly this text, or the run stops. A cross-check of a version that an earlier step took from elsewhere, such as a file name |

| Output | Meaning |
| --- | --- |
| `exe_product_version` | The `ProductVersion` string of the first string table, as written (for example `4.33`, `14.44.35211.0`, `26.03`). An empty string when the table has none |
| `exe_file_version` | The `FileVersion` string of the same table. An empty string when the table has none |
| `exe_product_version_numbers` | The product version of the fixed file information: four numbers joined by dots (for a file of 14, 44, 35211 and 0: `14.44.35211.0`) |
| `exe_file_version_numbers` | The file version of the fixed file information, the same way |
| `exe_product_name` | The `ProductName` string, or an empty string |
| `exe_company_name` | The `CompanyName` string, or an empty string |
| `version` | Only when `set_version` is true. See "Which one `version` takes" |

**Which one `version` takes.** The `ProductVersion` string when it is made of numbers
and dots only (`[0-9]+(.[0-9]+)*`, ASCII digits, nothing stripped or cut: `4.33`,
`26.03` and `14.44.35211.0` qualify, `4.33 (x64)`, `v4.33` and an empty string do
not). Otherwise the numbers of the fixed file information, `exe_product_version_numbers`.
The string is preferred because it is what a person sees in the file's properties
and what the vendor means; the numbers are the fallback because they are always
four numbers and always numeric. The step prints which one was taken. A recipe then
passes it on: the argument `version` of the importer's step is `%version%`. A recipe that
wants the string as it is reads `exe_product_version` and sets `set_version` to false.

When the string is not numeric (for example `4.33 (x64)`), the label is the four
numbers and has four parts, which may not look like what the vendor prints. The client
compares labels with its own rules, so check the first run's plan (a dry run
prints it).

**A label of zeros is never passed on.** When the label that this rule picks has no
digit other than zero, the processor stops with a `ProcessorError` and sets nothing
(`version` keeps what it had). That is the case when the string is made of zeros (`0`,
`0.0`), and when the string is text and the four numbers of the fixed file information
are zeros. The second case is real: an installer built with no version set carries zeros
in the numbers, and one built with a text version (a .NET "informational version" such as
`10.0.7-servicing.26217.108+<commit>`) carries that text in the string. The message names
the label, where it came from, the `ProductVersion` and `FileVersion` strings (cut at 60
characters) and the file version numbers. The processor does not try the other value or
the `FileVersion` instead, because choosing between them would be a guess. Read the file's
properties on a Windows PC and give the label that a person has read as the `version`
input in the override. With `set_version` false no label is chosen, so nothing is
refused.

**Errors** (`ProcessorError`, with the reason and the file's name, never a guess):

- `pathname` is not a file, or cannot be read.
- The file is not a PE file (no `MZ`, no `PE` signature, an optional header that is
  neither PE32 nor PE32+, a PE header outside the file, no sections or more than 96).
- The file has no resource directory (no entry, or an address of zero, or fewer than
  three data directories).
- The file has no `RT_VERSION` resource, or the resource tree is not built as
  expected (the type or the first name is not a directory, the first language is not
  a data entry, a directory has no entry or more than 4096).
- A read would leave the file, or an address is not in any section's raw data (a
  truncated file).
- The version block is larger than 1 MiB, does not start with `VS_VERSION_INFO`, has
  no fixed file information, or has a wrong signature (`0xFEEF04BD`) there.
- The block walk runs out of bounds: a block longer than its parent, shorter than its
  own header, a key without an end, or bytes that are not zero after the last child.
- A string is not valid UTF-16, or a string table has a key that is not eight hex
  digits.
- There is no `StringFileInfo` with a string table, or the first table has neither a
  `ProductVersion` nor a `FileVersion`.
- The label that `version` would get has no digit other than zero (see "A label of zeros
  is never passed on"). Only when `set_version` is true.

A string whose declared length goes past its block is cut at the block's end. That is
the one place where the walk is not strict: some tools write the length in bytes
instead of characters, and the text still ends at its null character.

**The expected values.** A recipe whose download is checked by `AuthenticodeVerifier` runs this step after
it and gives the product's and the company's name as the vendor writes them in the file, and, where an earlier
step took a version from somewhere else (a file name), that version as `expected_version`. A value that differs
stops the run before anything is set, and the message names both. The version resource lies inside what an
Authenticode signature covers, so after the signature step these strings and the label are the publisher's own
for this file. A new spelling of a name by the vendor stops the run until a person has looked and changed the
recipe.

**What the version proves.** Nothing about the file's origin. It is data in the file,
and whoever made the file chose it. It only gives the label that the importer and
the client compare. It does not replace a check of the download (`ChecksumVerifier`,
a vendor signature, or the pinned address of the vendor).

## VersionFromName

Some `.exe` installers have no version resource, so `WindowsExeVersion` stops on them (its
error is "the file has no version resource (RT_VERSION)"). When the name that the vendor gave
the file has the version in it (a release asset such as `setup-3.10.0.exe`), this processor
takes the label from the name. It runs no program, opens no file, writes nothing and uses no
network.

| Input | Required | Meaning |
| --- | --- | --- |
| `pathname` | yes | The downloaded file. Only its file name is read, never a folder of the path |
| `version_pattern` | yes | A regular expression with **exactly one group**, matched from the start of the file name (`re.match`, like the `asset_regex` of `GitHubReleasesInfoProvider`, so a recipe may give both the same pattern). The text of the group is the label |

| Output | Meaning |
| --- | --- |
| `version` | The label, as it stands in the name (leading zeros stay), checked for its shape |

**The shape.** Two to four numbers joined by dots, each of at most nine ASCII digits, with at
least one digit that is not zero. A build date such as `20260128215914` is not a part of a
version: the group of a pattern that was written for the wrong part of a name would take it,
and the check stops that. The label is never repaired, shortened or guessed. The step prints
`version is ..., taken from the file name ...`.

**Errors** (`ProcessorError`, and `version` stays as it was): the pathname has no file name;
the pattern is empty, is not text or is not a regular expression; it has no group or more than
one; the file name does not match it; the group did not take part in the match; or its text does
not have the shape above (one number, five parts, a letter, a part of ten digits, zeros only).

**What the label proves.** Nothing about the file: the name is chosen by whoever published the
file, and the version in it is the publisher's word for the release. It does not say what the
installed program reports about itself, so the first dry run is read against the program on a
test PC (each recipe's README says so). It does not replace a check of the download
(`ChecksumVerifier`, a vendor signature).

**Three-part labels.** The client reads some labels as a build time. `CatalogService.ExpandBuildTimestamp`, the code that
orders catalog versions and checks installed ones (`cli/managedsoftwareupdate/Services/CatalogService.cs`, the same at
`3cf02c4` and `e10498b`), reads a label of exactly three parts, `yy.M.ddHH`, with the first part from 20 to 99, a month from 1 to 12 and a third part of
three or four digits, as a build time; `VersionService.TryParseCalendarBuildStamp` reads a label of three or more numeric parts whose first part is a year of four digits as a build time. This
processor accepts such a label (a label of two to four parts that has a digit other than zero) and does not warn about it. For a recipe whose label has
three parts, read the order that the dry run's plan gives before the first import. A label of four parts, such as the four numbers of a Bambu Studio
file name, meets neither rule.

## MicrosoftStorePackageDownloader

**Nothing of this processor has run under AutoPkg.** The protocol is ported from a stand-alone
tool of the owner that fetched a real Store bundle on 2026-11-10; the processor itself is tested
only with stand-ins for every answer.

It downloads the package of a Microsoft Store product without the Store and without an account,
the way a Windows PC asks for it:

1. It reads the product in the Store's catalog (`displaycatalog.mp.microsoft.com`, the system's
   trust, no redirect followed, at most 4 MB). Every SKU of the product must name the same one
   package; a product with several packages (or SKUs that disagree) is refused. It reads the
   package's full name, format, SHA-256, largest download size, framework dependencies and update
   category.
2. It asks Microsoft's delivery service (`fe3.delivery.mp.microsoft.com`) for the file addresses
   of that category: a cookie, then up to eight rounds of `SyncUpdates`, then
   `GetExtendedUpdateInfo2` for each update that has a file. The service's certificate is issued
   under "Microsoft Root Certificate Authority 2011", which macOS does not trust;
   `microsoft-root-2011.pem` beside the processor is that public root (Microsoft publishes it at
   `http://www.microsoft.com/pki/certs/MicRooCerAut2011_2011_03_22.crt`). It is used only when its
   fingerprint is the one written in the processor, and only for this one host. No redirect is
   followed.
3. It downloads the offered files in turn to a `.partial` file in `downloads/` of the recipe's
   cache, each with a size limit (the catalog's largest download size and 1 MiB), hashing while it
   writes. The one with the catalog's SHA-256 becomes `downloads/<PackageFullName>.<extension>`;
   every other file is deleted, and no `.partial` file is left behind, also after an error.

When that file is in the cache already with the catalog's SHA-256, the delivery service is not
asked and `download_changed` is false.

| Input | Required | Meaning |
| --- | --- | --- |
| `store_product_id` | yes | The product id, 12 letters and digits, as in the address of the product's page |
| `store_market` | no | The catalog's market, two letters. Default `US` |
| `store_language` | no | The catalog's language. Default `en-us` |
| `store_file_host_suffixes` | no | The hosts that a file address may have (a list, or one text with commas). Default `.dl.delivery.mp.microsoft.com`, `.microsoft.com`. **Assumed, not read**: the tool of 2026-11-10 did not record the hosts. A refused address stops the run and names its host |

| Output | Meaning |
| --- | --- |
| `pathname` | The package, `<PackageFullName>.<extension>` in `downloads/` of the cache |
| `expected_sha256` | The catalog's SHA-256 (lower-case hex). The next step is `ChecksumVerifier` with `pathname` and this |
| `store_package_full_name` | The package's full name |
| `store_package_version` | The four numbers of the version in the full name. For a bundle that is the bundle's version, which looks like a date, not the application's |
| `store_package_format` | `msixbundle`, `appxbundle`, `msix` or `appx` |
| `store_framework_dependencies` | One line: each framework's name and minimum version, or `none` |
| `download_changed` | False when the cached file was used |
| `microsoft_store_package_downloader_summary_result` | For AutoPkg's summary when a new file was downloaded: product id, full name, version, frameworks. No path |

It sets no `checksum_verified`: the recipe's next step is `ChecksumVerifier`, as in every other
recipe.

**What it proves.** The file has the SHA-256 that Microsoft's catalog gives, and the catalog was
read over verified TLS. The file addresses may be plain http: that is acceptable only because the
file is accepted on that hash alone. **What it does not prove.** The package's signature is not
checked (the Store signs the package; Windows checks the signature when it adds the package).
Every value taken from an answer is checked for its shape before it goes into a request or a file
name.

**Free products with one package only.** A paid product, or one with several packages, is not
for this processor.

**What a person reads in the output.** The step prints the package's name, its size and every
framework dependency with its minimum version (for example `needs Example.Runtime.1.4
4000.1309.2056.0 or later`). The package does not install without its framework: compare that
line with the framework item in your repository before the first import, and after every new
version.

## When a vendor renames a file

The recipes that take a file from a GitHub release choose it with AutoPkg's `GitHubReleasesInfoProvider` and an `asset_regex`: the **first release, newest first and a
pre-release skipped, that has a file whose name matches the pattern** (AutoPkg 2.9.0, `GitHubReleasesInfoProvider.py`, `select_asset` and `main`). When a vendor
renames its file so that the pattern no longer matches the newest release, the provider does not stop and says nothing: it goes on to the next older release whose
file matches, and the run goes on with that file. If that older release has a digest, the digest and checksum steps pass; the label is the old file's; the importer
finds that version in the repository and says `Nothing new`. The run then ends clean at the old version every time it is made, and it stops only when no release of the whole list
matches. This happened in the first AutoPkg runs of 2026-10-04 to three recipes whose patterns knew only an old spelling of the name (they took files of January 2026,
October 2024 and December 2020, and then stopped on a property of those old files).

The eight download recipes that use the provider now have a **guard**: the step `GitHubNewestReleaseGuard` (its section is above), right after the provider, stops the run when the
release that the provider selected is not the newest release that is not a pre-release, and names the files of the newest release, so that the new spelling is in the
message. A newest release that has no Windows installer on purpose is accepted by its tag in the override's `Input` key `accepted_newest_release`, and the run goes on only while that release is the newest.
The guard is new and has not run under AutoPkg: its tests use made-up lists, and it was run (with no network, as a function) on the saved lists of GitHub's release API of the eight repositories
of 2026-10-04 by the recipes' own tests. What was checked on 2026-10-04 on the first page of each list (thirty releases, newest first): the release that Angry IP Scanner,
Bambu Studio, PDFsam, XCP-ng Center, osquery, Greenshot, 7-Zip and OpenSSH take is the newest release that is not a pre-release (for 7-Zip and OpenSSH this is a new reading: before it only their dry runs
were known; the tags of OpenSSH all say Preview or Beta, and GitHub does not flag them as pre-releases, so its newest release is taken; the lists of Bambu Studio and Greenshot have pre-releases
on top, which are skipped). For Bambu Studio, PDFsam and XCP-ng Center it was also compared with GitHub's `latest` of that day.

**What the operator still compares in a dry run** (run it with `-v`): the
line `Selected asset ... from release ...` against the vendor's releases page. The release that it names must be the newest one that is not a pre-release. The guard compares
the release, not the file: it cannot see a vendor that has moved the installer away from GitHub's releases, or a newest release whose matching file is the wrong one. A run that ends in
`Nothing new` is not proof that the newest release was taken.

## An example: the last steps of a recipe

The names are made up. The first steps (download, version) are the recipe's own. This is an
MSI: the step passes an empty `version`, so that the importer takes the MSI's own ProductVersion
and not the release tag that `GitHubReleasesInfoProvider` left in the run. For an `.exe` the
step reads `<string>%version%</string>`, the label that `WindowsExeVersion` set.

```xml
<dict>
    <key>Processor</key>
    <string>GitHubReleasesInfoProvider</string>
    <key>Arguments</key>
    <dict>
        <key>github_repo</key>
        <string>example-owner/example-app</string>
        <key>asset_regex</key>
        <string>example-app-.*-x64\.msi$</string>
    </dict>
</dict>
<dict>
    <key>Processor</key>
    <string>com.github.serrc-techops.SharedProcessors/GitHubNewestReleaseGuard</string>
    <key>Arguments</key>
    <dict>
        <key>github_asset_api_url</key>
        <string>%asset_url%</string>
    </dict>
</dict>
<dict>
    <key>Processor</key>
    <string>URLDownloader</string>
</dict>
<dict>
    <key>Processor</key>
    <string>EndOfCheckPhase</string>
</dict>
<dict>
    <key>Processor</key>
    <string>com.github.serrc-techops.SharedProcessors/GitHubAssetDigest</string>
    <key>Arguments</key>
    <dict>
        <key>github_asset_api_url</key>
        <string>%asset_url%</string>
    </dict>
</dict>
<dict>
    <key>Processor</key>
    <string>com.github.serrc-techops.SharedProcessors/ChecksumVerifier</string>
</dict>
<dict>
    <key>Processor</key>
    <string>com.github.serrc-techops.SharedProcessors/CimianImporter</string>
    <key>Arguments</key>
    <dict>
        <key>pathname</key>
        <string>%pathname%</string>
        <key>cimian_name</key>
        <string>%CIMIAN_NAME%</string>
        <key>cimian_subdirectory</key>
        <string>%CIMIAN_SUBDIRECTORY%</string>
        <key>version</key>
        <string></string>
        <key>pkginfo</key>
        <dict>
            <key>display_name</key>
            <string>Example App</string>
        </dict>
    </dict>
</dict>
```

`GitHubNewestReleaseGuard` follows the provider and comes before the download. The recipe's `Input` has the keys `include_prereleases` (false),
`accepted_newest_release` and `release_tag_pattern` (both empty), so that `make-override` copies them into an override; no step names them.

`ChecksumVerifier` reads `pathname` and `expected_sha256` from the run's variables, so it needs
no arguments here. It also sets `checksum_verified` and `checksum_sha256`, which `CimianImporter`
needs for a real run. `cimian_repo` is not in the recipe.

## Switching on a real run

A recipe never turns on a real run. The step list, with the commands and the lines to expect, is in
the README of the product folder (for example `../Win-7Zip/README.md`). The facts that matter:

1. **Make the override by name, into its own folder.** `autopkg make-override
   --override-dir=<the Windows overrides folder> <recipe name>`. Without
   `--override-dir` the override lands in AutoPkg's normal overrides folder, where a
   nightly script may run it.
2. **Run the override by path, with `--override-dir`**, `autopkg run
   --override-dir=<the Windows overrides folder> <the Windows overrides folder>/<recipe
   name>.recipe`. Without `--override-dir` AutoPkg does not treat the file as an
   override and skips the trust check with one warning line (`is missing trust
   info ... Proceeding...`): if that line appears, stop, the run was not checked. The recipe's name or identifier runs the recipe itself, which
   stays a dry run. A dry run prints a `WARNING: DRY RUN.` line at any verbosity
   and gives a summary row with the result `dry run, nothing written`.
3. **A real run is one key in the override's `Input` (for a download that a step
   verified):**

```xml
<key>cimian_dry_run</key>
<false/>
```

   (or `/usr/libexec/PlistBuddy -c 'Add :Input:cimian_dry_run bool false' <override>`).
   A change of the `Input` does not break the trust information.
4. **After a publish, build the catalogs** with Cimian's `makecatalogs`. Without it no PC
   sees the new version.

**Other ways, and their traps.**

- A preference: write the value as a string. `defaults write com.github.autopkg
  cimian_dry_run -string false`. A boolean written with `-bool false` may reach
  the processor as the number `0`, and the processor refuses it with an error. A
  preference applies to every recipe that has this input: prefer the override.
- On the command line, `-k cimian_dry_run=false` applies to EVERY recipe of that
  `autopkg run`. Use it for one recipe only, and never in a list run.
- The preference for the repository is the one name in upper case: `CIMIAN_REPO`. The input
  names are lower case (`cimian_repo`, `cimian_dry_run`); a preference with an upper-case spelling of
  one of them is not read.

The download must have a file name that ends in `.msi` or `.exe`. If the vendor's
URL has none, set `filename` for `URLDownloader` in the download recipe.

When a processor or a recipe changes, the override fails with "Failed local trust verification" until
a person has looked (`autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <override>`)
and accepted it (`autopkg update-trust-info --override-dir=<the Windows overrides folder> <override>`).

## Tests

From this folder (no AutoPkg needed; a stand-in for `autopkglib` is used when
AutoPkg is not installed):

    python3 -m unittest discover -s tests -t tests

The tests of `CimianImporter` make a temporary Cimian repository, installers that are only files with
bytes in them, and a stand-in for `msiinfo` that starts with the real interpreter's path. They need
PyYAML, which AutoPkg's own Python has; in a Python without it they are skipped (the tests of the
version order, of the declarations and of the missing-PyYAML error still run).

The tests of `VersionFromName` read only names and patterns; they open no file.

The tests of `AuthenticodeVerifier` that sign and verify build everything in a temporary folder at test
time: throwaway roots, signing and timestamp certificates (with `openssl`), a small PE file, signatures with
a local timestamp (`osslsigncode sign` with `-TSA-certs`, `-TSA-key` and `-TSA-time`, so no timestamp server
is asked), and the CRLs, served by a server on the loopback address. They change signed files in the ways
that the certificate table allows (bytes after the table, inside the entry, a second entry, padding that is not
zero, another entry type) and sign with SHA-1, SHA-384 and MD5. They need `osslsigncode` and OpenSSL 3.4
or later, and are skipped with the reason where either is missing. No MSI is built (no tool here writes one):
the MSI rules are tested on the tool's output only. The tests of the inputs, of the pinned roots, of the DER
reader (with signatures written byte by byte for the cases that no signing tool makes: two `SignerInfo`s, a key
identifier, a certificate with the signer's serial number and another issuer) and of the reading of the tool's
output need no tool. None uses the network. One more test runs the step of each download recipe that has one on a real
installer, and a copy of it with one byte changed, and is skipped unless a folder is named (it fetches the CRLs
over the network):

    AUTHENTICODE_SAMPLES=<folder> python3 -m unittest discover -s tests -t tests -p 'test_authenticode.py'

The folder holds the installers under the name of the recipe's folder, for example `Win-Scratch.exe` or
`Win-GeoGebra.msi`; a recipe without a file there is not checked.

The tests of `GitHubNewestReleaseGuard` use made-up lists of releases in the shape of GitHub's answer and replace the function that sends the request; the tests of
the request replace the lowest function (`open_request`), and a server on the loopback address answers the redirect tests. The recipes' own tests of the eight download
recipes run the guard on the saved list of each repository (`releases_excerpt.json` of their folders), with AutoPkg 2.9.0's choice written as a function. None uses the network.

The tests of `WindowsExeVersion` build a small PE file in a temporary folder; no real
`.exe` is in this repository. One more test reads real files and is skipped unless a
folder is named:

    WIN_EXE_SAMPLES=<folder> python3 -m unittest discover -s tests -t tests -p 'test_exe_version.py'

For each `<name>.exe` in the folder that has a `<name>.expected` beside it, the
processor's outputs must equal the lines of that file (`exe_product_version=...`,
`exe_product_version_numbers=...`, any of the output names).

## What must never be in this repository

This repository is public.

- No secret: no password, key, token, certificate or enrollment value.
- No value that belongs to one site: no host name, address, share path,
  organisation name, PC name or person's name. Use made-up names such as
  `Example App` and `example.test` in code, comments, tests and examples.
- No path to a package tool, to the repository share or to a user's folder.
  They are AutoPkg preferences or overrides on the machine that runs AutoPkg.
- No log of a real run, and no copy of the files of a real Cimian repository.

`tests/test_public_repository.py` looks for some of these in this folder. It
cannot know a site's own names: a person checks those.
