# Win-SharedProcessors

Four AutoPkg processors for Windows installers, and the stub recipe that lets
other recipes use them.

AutoPkg looks only one folder below a search directory. So the processors, the
stub recipe and `tests/` sit here, and a recipe in another folder names a
processor like this: `com.github.serrc-techops.SharedProcessors/<Processor>`.

| File | What it is |
| --- | --- |
| `PcmanImporter.py` | Hands a downloaded `.msi` or `.exe` to the package tool (`pcman`). The last step of a recipe |
| `ChecksumVerifier.py` | Stops the recipe when a file does not have the SHA-256 that its publisher gives |
| `GitHubAssetDigest.py` | Reads the SHA-256 that GitHub records for a release asset |
| `WindowsExeVersion.py` | Reads the version of a downloaded `.exe` from the file itself, for the version label that the package tool needs |
| `SharedProcessors.recipe` | Stub. Carries the identifier `com.github.serrc-techops.SharedProcessors`. Does nothing |
| `tests/` | Tests. They need no AutoPkg and no network |

## PcmanImporter

The package tool decides whether a version is new, whether it is the same
product, and what goes into the repository. This processor does these things:

1. It checks the inputs. Nothing runs when a check fails.
2. It runs the package tool as a list (no shell), with standard input closed
   and a time limit.
3. It reads the tool's result file and turns it into AutoPkg outputs.

The command:

    <pcman_python> <pcman_root>/bin/pcman import <pathname> --template <pcman_template> \
        [--version <pcman_version>] --no-prompt --if-new --result-file <file> [--dry-run]

The result file is made in a temporary folder that the processor creates and
removes. The processor never passes `--force`, `--allow-duplicate`,
`--allow-product-change` or `--allow-version-label`, and has no input that could.

**A dry run is the default.** The tool is asked for its plan (`--dry-run`) and
writes nothing. The plan itself is NOT printed: it contains the text of the
pkginfo. What is printed, at any verbosity (also without `-v`), is one line that
begins with `WARNING: DRY RUN.` and says that nothing was written. A dry run also
gives a summary result with the result `dry run, nothing written`, so that it
does not look like a run that had nothing to do. `pcman_repo_changed` is false.
A real run needs `pcman_dry_run` set to `false` (see "Switching on a real run").
The line "Nothing new: ..." is also printed at any verbosity.

**A download that no step verified is refused.** A download counts as verified
only when two things hold: `checksum_verified` is a boolean `true` (`ChecksumVerifier`
sets it), and `checksum_sha256` (`ChecksumVerifier` outputs it: the hash of the file it
checked) is a SHA-256 that equals the hash of the file about to be imported.
`PcmanImporter` hashes that file itself, once, in blocks. The hash is read like `ChecksumVerifier` reads an expected value: 64 hex
digits, any letter case, with or without the prefix `sha256:`. A **real** run
(`pcman_dry_run` false) of a download that does not count (the flag is not `true`, or
`checksum_sha256` is missing or is not a SHA-256) is refused with a `ProcessorError`
before the tool starts:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file. Nothing was published. Publish by hand after
    checking the file, or set pcman_allow_unverified to true in the override.

With `pcman_allow_unverified` true in the override the run goes on. It prints one
`WARNING: published WITHOUT a verified download ...` at any verbosity, and the summary
row's result is `published, NOT verified`. A dry run of an unverified download prints
a `WARNING: the download was NOT verified ...` and its summary row says
`dry run, nothing written, NOT verified`. A recipe whose download goes through
`ChecksumVerifier` is not changed by this.

**A checksum for another file stops the run.** When `checksum_verified` is `true` and
`checksum_sha256` is a SHA-256 that is NOT the hash of the file to import, the file that
was verified is not the file that is imported. That is not "unverified": it is a
`ProcessorError` that shows both hashes shortened, also in a dry run, and
`pcman_allow_unverified` does not override it.

A boolean `checksum_verified` written into an override's `Input` (or an AutoPkg
preference) therefore counts only together with the right hash. That is a pinned hash,
chosen by whoever wrote the override, and the override's trust information does not
cover its `Input`.

`signature_verified` does not count: no step sets it. A later signature step must output
the hash of the file it checked under a named key, and this guard must then accept that
key in the same way, with the same comparison with the file that is imported.

### Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `pathname` | yes | | The downloaded installer. It must exist and end in `.msi` or `.exe` |
| `pcman_template` | yes | | The item name of the program's template in the package tool: letters, numbers, dots, underscores and hyphens, as the tool allows. Not a path, no white space, no control character, not beginning with `-` or `.` |
| `pcman_version` | `.exe` only | | The version label: numeric parts separated by dots, such as `2.5.1.300`. No white space, control character, path separator or leading `-`. Leave it out for an `.msi`: the tool takes the MSI's own version. An empty or blank value counts as not given |
| `pcman_root` | yes | none | The folder of the package tool. A leading `~` is expanded. Set it as an AutoPkg preference or in an override, never in a recipe |
| `pcman_python` | no | `<pcman_root>/.venv/bin/python3` | The Python of the tool. AutoPkg's own Python is not used |
| `pcman_dry_run` | no | `true` | `true`: plan only. `false`: a real run. Only a boolean or the text `false`, `no` or `0` (any letter case) makes a real run; `off`, `n`, `f`, an empty value or a number other than the text `0` is an error |
| `pcman_allow_unverified` | no | `false` | `true`: a real run of an unverified download goes on, with a WARNING (see above). Parsed like `pcman_dry_run`: only a boolean or the text `true`, `yes`, `1`, `false`, `no`, `0` (any letter case); anything else is an error, also for a verified download. Set it in an override, never in a recipe |
| `pcman_timeout` | no | 1800 | Seconds to wait for the tool, from 60 to 14400. On a time-out, on Ctrl-C and on a termination of AutoPkg the tool and its child processes are killed |
| `pcman_path` | no | `/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin` | The `PATH` of the tool. For an `.msi`, `msiinfo` must be found here |
| `pcman_cimian_repo` | no | | Passed to the tool as `PCMAN_CIMIAN_REPO` |
| `pcman_config` | no | | Passed as `PCMAN_CONFIG` |
| `pcman_cimian_catalogs` | no | | Passed as `PCMAN_CIMIAN_CATALOGS` |
| `pcman_state_dir` | no | | Passed as `PCMAN_STATE_DIR` |

The last four can also be set in the environment of the process that runs
AutoPkg. An input wins over the environment.

**The tool gets only this environment:** `PATH`, `HOME`, and the four `PCMAN_`
variables above when they are set. Nothing else is passed on. The processor
never prints the environment and never opens the tool's `pcman.yaml`.

### Outputs

| Output | Meaning |
| --- | --- |
| `pcman_result` | `published`, `finished-earlier-publish`, `dry-run` or `nothing-new` |
| `pcman_name` | The item name |
| `pcman_version_published` | The version label of the result (the planned one after a dry run) |
| `pcman_pkginfo_path` | The pkginfo in the repository (planned after a dry run) |
| `pcman_installer_path` | The installer in the repository (planned after a dry run) |
| `pcman_repo_changed` | True only when the tool wrote to the repository in this run |
| `pcman_importer_summary_result` | For AutoPkg's report. Set after a publish (result `published` or `finished-earlier-publish`; `published, NOT verified` for an unverified download) and after a dry run (result `dry run, nothing written`; `dry run, nothing written, NOT verified` for an unverified download). Columns: name, version, catalogs, result. No path: reports are mailed. The paths are the two output variables above |

### What the exit codes of the tool become

| Tool exit | Meaning | Processor |
| --- | --- | --- |
| 0 | Published, finished an earlier publish, or a dry run | Outputs set. `pcman_repo_changed` is true, except after a dry run |
| 3 | Nothing new: the repository has this version and this installer | One line. `pcman_repo_changed` false. Not an error |
| 1 | The tool stopped with an error (a label it refuses, another installer under the same version, a repository that is not complete, a lock time-out) | `ProcessorError` |
| 2 | The command line cannot be read, or the result file cannot be written | `ProcessorError`: a mistake in the recipe or the setup |
| other, a time-out, no result file, a result file that cannot be read | | `ProcessorError` |

A result that does not fit the run (for example `dry-run` after a real run) is
an error too. So is a result value that the tool does not document, and a
`published` or `finished-earlier-publish` result whose `name`, `version`,
`pkginfo_path` or `installer_path` is missing or empty.

**What is shown from the tool's output.** After an error: the lines that begin
with `ERROR:` (standard output and error). After a good run: the lines that
begin with `WARNING:` or `NOTE:`, and they are shown at any verbosity. At most 10
lines of 1500 characters each. The limit is chosen from the longest message that
the tool prints today (the note for a minor upgrade of an MSI, about 500
characters, with its advice at the end). Output that is not UTF-8 does not stop
the processor. Nothing else is shown, because a dry run prints the text of the
pkginfo, which can hold install arguments. The lines can name paths of the
repository. So can the receipts that AutoPkg keeps for every run, and the output
of `-vv`, which shows every input (`pcman_root`, the repository): keep the logs
and the cache of the build machine private.

**The tool's environment** is `PATH`, `HOME` and the four `PCMAN_` variables. The
system or Python may add `LC_CTYPE` or `__CF_USER_TEXT_ENCODING`.

**Interrupts.** On Ctrl-C and on a termination of AutoPkg (SIGTERM) the processor
kills the tool and its child processes (its whole process group), and then removes
its temporary folder. A kill can leave one thing in the repository: a temporary
installer file, `..<installer>.pcman-new.<random>.tmp` in `pkgs/`, or
`.<pkginfo>.<random>.tmp` in `pkgsinfo/`, when the tool was stopped in the middle
of a copy or a write. The tool's README ("Temporary files") says the same: the next
publish to the same place removes it, `makecatalogs` ignores it, and `pcman
versions` names any that it sees. The repository stays consistent: the next run says
"nothing new" or finishes the publish. A kill by `SIGKILL` of AutoPkg itself cannot be
handled: the tool then runs on until it ends.

## ChecksumVerifier

Hashes the file itself, in blocks, and compares it with the expected value.

| Input | Required | Meaning |
| --- | --- | --- |
| `pathname` | yes | The downloaded file |
| `expected_sha256` | yes | 64 hex digits, in any letter case, with or without the prefix `sha256:`. Nothing else is accepted (no file name after the digest) |

| Output | Meaning |
| --- | --- |
| `checksum_verified` | True when the hash matched. `PcmanImporter` reads it, together with `checksum_sha256`: without both, and the hash of the file to import, a real run is refused |
| `checksum_sha256` | The hash of the file that was checked (lower-case hex). `PcmanImporter` compares it with the hash of the file it imports |

An empty value, a value that is not a SHA-256, a file that cannot be read, or a
different hash is a `ProcessorError`. The message shows both hashes shortened.

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

## WindowsExeVersion

Several Windows installers are `.exe` files at a fixed address, with no version in
the address and no hash from the vendor. The package tool needs `--version <label>`
for an `.exe` (`PcmanImporter` input `pcman_version`), and the label must be the
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
| `set_version` | no | `true` | `true`: set `version` (see below). `false`: leave `version` as it is. Parsed like `pcman_dry_run`: only a boolean or the text `true`, `yes`, `1`, `false`, `no`, `0` (any letter case); anything else is an error |

| Output | Meaning |
| --- | --- |
| `exe_product_version` | The `ProductVersion` string of the first string table, as written (for example `4.33`, `14.44.35211.0`, `26.03`). An empty string when the table has none |
| `exe_file_version` | The `FileVersion` string of the same table. An empty string when the table has none |
| `exe_product_version_numbers` | The product version of the fixed file information: four numbers joined by dots (for a file of 14, 44, 35211 and 0: `14.44.35211.0`) |
| `exe_file_version_numbers` | The file version of the fixed file information, the same way |
| `exe_product_name` | The `ProductName` string, or an empty string |
| `version` | Only when `set_version` is true. See "Which one `version` takes" |

**Which one `version` takes.** The `ProductVersion` string when it is made of numbers
and dots only (`[0-9]+(.[0-9]+)*`, ASCII digits, nothing stripped or cut: `4.33`,
`26.03` and `14.44.35211.0` qualify, `4.33 (x64)`, `v4.33` and an empty string do
not). Otherwise the numbers of the fixed file information, `exe_product_version_numbers`.
The string is preferred because it is what a person sees in the file's properties
and what the vendor means; the numbers are the fallback because they are always
four numbers and always numeric. The step prints which one was taken. A recipe then
passes it on: `pcman_version` is `%version%`. A recipe that wants the string as it is
reads `exe_product_version` and sets `set_version` to false.

When the string is not numeric (for example `4.33 (x64)`), the label is the four
numbers and has four parts, which may not look like what the vendor prints. The package
tool compares labels with its own rules, so check the first run's plan (a dry run
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
properties on a Windows PC and import by hand with a label that a person has read:
`pcman import <file> --template <item> --version <the label>`. With `set_version` false no
label is chosen, so nothing is refused.

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

**What the version proves.** Nothing about the file's origin. It is data in the file,
and whoever made the file chose it. It only gives the label that the package tool and
the client compare. It does not replace a check of the download (`ChecksumVerifier`,
a vendor signature, or the pinned address of the vendor).

## An example: the last steps of a recipe

The names are made up. The first steps (download, version) are the recipe's own.

```xml
<dict>
    <key>Processor</key>
    <string>GitHubReleasesInfoProvider</string>
    <key>Arguments</key>
    <dict>
        <key>github_repo</key>
        <string>example-owner/example-app</string>
        <key>asset_regex</key>
        <string>example-app-.*-x64\.exe$</string>
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
    <string>com.github.serrc-techops.SharedProcessors/PcmanImporter</string>
    <key>Arguments</key>
    <dict>
        <key>pcman_template</key>
        <string>Example-App</string>
        <key>pcman_version</key>
        <string>%version%</string>
    </dict>
</dict>
```

`ChecksumVerifier` reads `pathname` and `expected_sha256` from the run's
variables, so it needs no arguments here. It also sets `checksum_verified` and
`checksum_sha256`, which `PcmanImporter` needs for a real run. `pcman_root` is not in the recipe.

## Switching on a real run

A recipe never turns on a real run. The step list, with the commands and the
lines to expect, is in the README of the product folder (for example
`../Win-7Zip/README.md`). The facts that matter:

1. **Make the override by name, into its own folder.** `autopkg make-override
   --override-dir=<the Windows overrides folder> <recipe name>`. Without
   `--override-dir` the override lands in AutoPkg's normal overrides folder, where a
   nightly script may run it.
2. **Run the override by path, with `--override-dir`**, `autopkg run
   --override-dir=<the Windows overrides folder> <the Windows overrides folder>/<recipe
   name>.recipe`. Without `--override-dir` AutoPkg does not treat the file as an
   override and skips the trust check with one warning line (`is missing trust info
   ... Proceeding...`): if that line appears, stop, the run was not checked. The recipe's name or identifier runs the recipe itself, which
   stays a dry run. A dry run prints a `WARNING: DRY RUN.` line at any verbosity
   and gives a summary row with the result `dry run, nothing written`.
3. **A real run is one key in the override's `Input` (for a download that a step
   verified):**

```xml
<key>pcman_dry_run</key>
<false/>
```

   (or `/usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' <override>`).
   A change of the `Input` does not break the trust information.
4. **After a publish, build the catalogs** with `pcman catalogs`. Without it no PC
   sees the new version.

**Other ways, and their traps.**

- A preference: write the value as a string. `defaults write com.github.autopkg
  pcman_dry_run -string false`. A boolean written with `-bool false` may reach
  the processor as the number `0`, and the processor refuses it with an error. A
  preference applies to every recipe that has this input: prefer the override.
- On the command line, `-k pcman_dry_run=false` applies to EVERY recipe of that
  `autopkg run`. Use it for one recipe only, and never in a list run.
- A preference named in upper case (`PCMAN_CIMIAN_REPO`) is not read. The input
  names are lower case (`pcman_cimian_repo`). Only a variable of the process
  environment has the upper-case name.

The download must have a file name that ends in `.msi` or `.exe`. If the vendor's
URL has none, set `filename` for `URLDownloader` in the download recipe.

When a processor or a recipe changes, the override fails with "Failed local trust
verification" until a person has looked (`autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <override>`)
and accepted it (`autopkg update-trust-info --override-dir=<the Windows overrides folder> <override>`).

## Tests

From this folder (no AutoPkg needed; a stand-in for `autopkglib` is used when
AutoPkg is not installed):

    python3 -m unittest discover -s tests -t tests

The tests that run the real package tool are skipped unless these are set:

    PCMAN_TOOL_SOURCE=<folder of the package tool> \
    PCMAN_TOOL_PYTHON=<a Python that has the tool's requirements> \
    python3 -m unittest discover -s tests -t tests -p 'test_importer_real_tool.py'

They copy the tool's code to a temporary folder and use a temporary repository.

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
- No path to the package tool, to the repository share or to a user's folder.
  They are AutoPkg preferences or overrides on the machine that runs AutoPkg.
- No file of the package tool's own settings (`pcman.yaml`), no state folder.
- No log of a real run.

`tests/test_public_repository.py` looks for some of these in this folder. It
cannot know a site's own names: a person checks those.
