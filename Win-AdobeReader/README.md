# Win-AdobeReader

A Windows recipe pair: Adobe Acrobat Reader, the `.exe` installer (English by default), with the version label read from the installer file itself.

**Status. NOT rehearsed with AutoPkg. Some facts of the source were fetched by the writer on 2026-10-02: no run of AutoPkg was made, and nothing was written to a repository. Read from Adobe's servers on that day (no browser identity was needed; an earlier HEAD request got 403, a GET answers 200): (1) `https://rdc.adobe.io/reader/products?lang=en&platformArch=64&site=landing&os=Windows%2010&preInstalled=&country=US&nativeOs=Windows%2010&api_key=dc-get-adobereader-cdn`, the public endpoint that Adobe's own download page calls, answered 200 with a JSON object (378 bytes): `products.reader` is a list of one element with `displayName` `Reader 2026.002.21931 English for Windows (Recommended)`, `fileSize` 748.0 and `version` `26.002.21931`; `products.dcPro` and `addons` are beside it and are not used; the processor's parsing function was run on a saved copy of this answer and gave the version, the packed version `2600221931` and the two installer addresses below; (2) a HEAD request for `https://ardownload2.adobe.com/pub/adobe/reader/win/AcrobatDC/2600221931/AcroRdrDC2600221931_en_US.exe` (643995232 bytes) and one for `.../AcroRdrDC2600221931_MUI.exe` (739174432 bytes) answered 200; the same names with `x64` (`AcroRdrDCx64...`) answered 404 under this scheme; (3) the real file `AcroRdrDC2600221931_en_US.exe` (643995232 bytes) was downloaded, with no browser identity, and read with `WindowsExeVersion`: its ProductVersion is `26.2.21931.0` (the FileVersion and the numbers of the fixed file information are the same), so the label `version` is `26.2.21931.0`; its ProductName is `Adobe Self Extractor`, the outer self-extracting wrapper and not `Adobe Acrobat Reader`, so a check of the product name would mislead; the products file's `26.002.21931` and the file's `26.2.21931.0` are one version by their numbers (26, 2 and 21931), the middle part of the products file written with leading zeros and the file's with a fourth part. NOT established: that the products file is stable (it is not documented by Adobe, and its `api_key` is the fixed public key that the download page sends); that the installer scheme, seen for one version, holds for the next; whether Adobe offers an installer for x64 under another scheme (the two that were seen are the 32-bit installers); the silent switch of the installer, its install path and its architecture for the first import (not read); the version text that the installed Reader shows after the wrapper has installed it (only the wrapper's was read); that the next release keeps this spelling; that the template item `adobereader` exists and is an EXE item; `pcman catalogs`; any run with AutoPkg. The download is NOT verified: Adobe publishes no hash for the file, and a check of the signature is not built. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true. Do not set it before the signature check exists. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template adobereader --version <the label>` (the installer's own ProductVersion, as the dry run shows it). The tests use a products file excerpt that the writer wrote by hand after the real answer of 2026-10-02 (the shape of `reader` and `dcPro`, not saved from the real server, and with the other keys cut), so they prove what the code does with an answer of that form and nothing about Adobe today. The first run on the build Mac is the check of everything that is NOT established. When it fails, STOP: nothing was written (a run that fails before the import writes nothing). Read the real products file and Adobe's download page in a browser, correct the processor or the recipe, and only then look at the trust information. Never accept new trust information first to make a failure go away. Every override command here carries `--override-dir`: see the paragraph "Run every override with `--override-dir`" below. A real run of this recipe has NOT been run by anyone, not against a share and not on a PC. `pcman catalogs` was NOT rehearsed either.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `AdobeReader-Win.download.recipe` | `com.github.serrc-techops.download.AdobeReader-Win` | Reads the current Reader version from Adobe's products file, builds the address of the installer from it, downloads it, and reads the version that the installer file carries. It has no hard check |
| `AdobeReader.cimian.recipe` | `com.github.serrc-techops.cimian.AdobeReader` | Parent: the download recipe. Hands the file to the package tool (`pcman`) with the installer's own version as the label, which publishes it as a new version of the template item, or says that nothing is new |

The processor `AdobeReaderInfoProvider.py` is in this folder. It reads one file of
Adobe's servers (the products file, a JSON object) and outputs `url`, `version` (the
products file's text, `26.002.21931`) and `adobe_packed_version` (`2600221931`). It outputs
no hash: Adobe publishes none. The processor `WindowsExeVersion` is shared
(`../Win-SharedProcessors/`, see its README): after the download it reads the
ProductVersion from the installer file and sets `version` to it, so that the label for the
package tool is the file's own, not the products file's. Neither recipe stops on an
unchanged download, so an import that failed is tried again at the next run.

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

How strict the provider is:

- The one fetch goes to a fixed host over https (`rdc.adobe.io`). A redirect is not
  followed: it is an error. A status other than 200 is an error. The answer may be at most
  64 KiB, the fetch has a time limit of 120 seconds, and the answer must be UTF-8 text.
- The answer must be a JSON object whose `products.reader` is a list of exactly one element,
  and the element's `version` must have the form `NN.NNN.NNNNN` (two, three and five
  digits). Anything else stops the run, and no address is built from it.
- The language input is `en_US` or `MUI` and nothing else. The address is
  `https://ardownload2.adobe.com/pub/adobe/reader/win/AcrobatDC/<packed>/AcroRdrDC<packed>_<language>.exe`;
  the provider does not fetch it, the downloader does.

## What protects, and what does not

Nothing proves that the downloaded file is what Adobe published: there is no vendor
hash, and a signature check is not built. The shared importer knows this: no step of
the recipe sets `checksum_verified` with the hash of the file, so a real run is refused
before the package tool starts. What remains does not replace a verification.

- **The label.** The recipe passes the ProductVersion that the installer file itself
  carries (from `WindowsExeVersion`), not the version of the products file. It is
  data in the file, so it proves nothing about where the file came from. The dry run shows
  both: the provider prints the products file's version, and `WindowsExeVersion` prints
  the file's strings and the label it took. A person reads them and checks that they
  agree by their numbers. They are not written in the same way: on 2026-10-02 the products
  file had `26.002.21931` and the file `26.2.21931.0` (see the status line). The file's
  ProductName is the wrapper's (`Adobe Self Extractor`), so nothing here checks the product
  name.
- **The same product.** For an MSI the package tool refuses a different upgrade code.
  Whether it has an equivalent check for an EXE was NOT established by the writer. For
  this recipe the checks are the dry run and a person's look at what it plans.

A changed file of the vendor, or a changed download on the way, would pass both.

## The label is the wrapper's version, and nothing compares it with the product's

**The label that the package tool gets is the `ProductVersion` of the downloaded installer
file, which is Adobe's self-extracting wrapper (its ProductName is `Adobe Self Extractor`),
and not the version of the Reader that the wrapper installs. No step of this recipe compares
the two.** The version of Adobe's products file (`26.002.21931` on 2026-10-02) only builds
the address, and the version that the installed Reader shows has not been read by anyone. If
Adobe's wrapper stopped tracking the product (a number older or newer than the Reader's), the
recipe would still publish under the wrapper's number, and that number orders the versions in
the repository. The recipe does not check this at any run. A person checks it, at the first
dry run:

1. Run the dry run with `-v` (step c) and read the two versions that it prints: the
   provider's line with the products file's version, and the line `version is ..., taken
   from ...` of `WindowsExeVersion` with the label.
2. Compare them by their numbers. On 2026-10-02 they were `26.002.21931` and `26.2.21931.0`:
   the same three numbers (26, 2 and 21931), the middle part written with leading zeros in
   the products file and the label with a fourth part. If the three numbers differ, stop and
   tell the owner before anything is published.
3. After the first install on a test PC, compare the label with the version that the
   installed Reader reports (its About page, or its entry in Windows' list of installed
   programs). Nobody has done that. Whether the Cimian client sees the label and that version
   as the same version is NOT established.

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
   it replaces. If the package tool's repository has an item `adobereader` already,
   look at it first: it must be an item for the EXE, and this step is not needed.
   The command, with a real installer of the current release:

       pcman import <path of the installer, AcroRdrDC<packed>_en_US.exe> --name adobereader \
           --version <the installer's own ProductVersion, read in the file's properties> \
           --directory <the folder of the item> \
           --install-arguments <the installer's silent switch, read in the vendor's documentation first> \
           --install-path <the path of the installed program, read on a PC first> \
           --architectures <the installer's architecture, read in the installer first> \
           --display-name "Adobe Acrobat Reader" --category <the category of the item> \
           --developer Adobe --description <one sentence about the item> --no-prompt --build

   The label after `--version` is what the recipe will pass for later versions: the
   ProductVersion of the installer file, as `WindowsExeVersion` reads it (`26.2.21931.0` for the
   file of 2026-10-02, not the products file's `26.002.21931`). The silent
   switch, the install path and the architecture are facts of the installer that the
   writer did NOT read: the address scheme that was seen gives the 32-bit installers, and
   whether an x64 installer exists is NOT established. A person changes the template
   later; nothing else does. **If the template is made from the installer that is
   current at Adobe, the first run says "Nothing new" (see step c). To see a dry run
   that would publish, make the template from an older version.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i AdobeReader-Win
    autopkg list-recipes | grep -i AdobeReader.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> AdobeReader.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `AdobeReader.cimian`, not a path. Expected (not
run): it writes `<the Windows overrides folder>/AdobeReader.cimian.recipe` with the
identifier `local.cimian.AdobeReader` and the trust information of the two recipes and
the three processors that are not part of AutoPkg itself (`AdobeReaderInfoProvider`,
`WindowsExeVersion`, `PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.AdobeReader-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.AdobeReader`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

**`-v` prints what each processor says about its own work; `-vv` would add every processor's
inputs and outputs, `pcman_root` and the repository among them, to the log: keep such a log private.** Expected, from
the code and the rehearsals of the other folders, NOT printed by this recipe yet, when
the current version is not yet in the repository:

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name         Version                          Catalogs    Result
    adobereader  <the installer's ProductVersion>  Production  dry run, nothing written, NOT verified

The run also prints, before that, one line of the provider with the version of
Adobe's products file (`Current Adobe Acrobat Reader according to Adobe's products file: ...`)
and two lines of `WindowsExeVersion`: the file's ProductVersion, FileVersion and the
numbers of its fixed file information, and `version is <the label>, taken from <where>`.
**Read the two versions and compare them.** On 2026-10-02 they were `26.002.21931` (the
products file) and `26.2.21931.0` (the file), one version by its numbers. If they do not agree
by their numbers, stop and tell the owner: the label of the package tool is the file's. If the
current version is in the repository already (the template was made from it), the line
is `Nothing new: ... is in the repository already. Nothing was written.` instead. That is
correct.

If Adobe changes the products file so that the processor cannot read it, the run fails
with a line that begins `Adobe's products file` and publishes nothing. If the line says
that the address answered with a redirect, stop and tell the owner. If the downloader
reports that the installer's address answered 404, the scheme of the addresses has changed:
read Adobe's download page in a browser and correct the processor.

## d. Switch a real run on (NOT YET: see the status line)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file. Nothing was published. Publish by hand after
    checking the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template adobereader --version <the label>

The label is the installer's own ProductVersion, as the dry run shows it (an EXE has no
version that the package tool can read for itself). Then `pcman catalogs` (step e.3).

**Only after the signature check exists, or when a person has decided to accept an
unverified download:** the override allows it. Both lines are needed.

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/AdobeReader.cimian.recipe
    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_allow_unverified bool true' \
        <the Windows overrides folder>/AdobeReader.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.cimian.recipe

A change of the `Input` does not break trust (found with 7-Zip). Do not use `-k`
instead: on the command line it applies to every recipe of that run. A run then prints
`WARNING: published WITHOUT a verified download ...` at any verbosity, and the report's
row says `published, NOT verified`.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.cimian.recipe

   Only after both lines of step d. Expected: `Published adobereader ...`, the warning
   `published WITHOUT a verified download`, and the table

       The following versions were published by the package tool:
       Name         Version                          Catalogs    Result
       adobereader  <the installer's ProductVersion>  Production  published, NOT verified

   The repository then has the installer under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions adobereader` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.cimian.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/AdobeReader.cimian.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again. (Not run with this recipe.)

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The input of the download recipe is `ADOBE_LANGUAGE` (default `en_US`, English; `MUI`
  is the installer for all languages). Change it in the override's `Input`, not in the
  recipe. The cached file's name has the packed version and the language in it
  (`AcroRdrDC<packed>_<language>.exe`): use one language for one override.
- The products file also lists the paid Acrobat (`dcPro`) and add-ons. The processor reads
  `reader` only.
- The installer is about 640 MB (`en_US`) or 740 MB (`MUI`). `WindowsExeVersion` reads only
  the headers and the version block, never the whole file. The copy to the share is the
  slowest step. The processor waits 30 minutes by default (`pcman_timeout`); if that is
  not enough, set `pcman_timeout` in the override's `Input`.
- The version of the products file has the form `26.002.21931`; the installer's name
  has the same digits without dots (`2600221931`); the installer file carries `26.2.21931.0`
  as its ProductVersion (read on 2026-10-02). The packed version is made from the products
  file's text, not from the file's.
- The installer is a self-extracting wrapper (ProductName `Adobe Self Extractor`). The version
  that the installed Reader shows is NOT established.
- The recipe's `NAME` is `AdobeReader` and `PCMAN_TEMPLATE` is `adobereader`. Change the
  template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.
- `-p` (a local file instead of the download) skips the download. The file is not
  checked at all.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that the processor handles every kind of products file (the excerpt in `tests/`
is written by hand after the real answer of 2026-10-02, not saved from the real server; the
other texts are made up), that both recipes are property lists, that every argument is an
input that the processor declares, that the cimian recipe passes the label of
`WindowsExeVersion`, that the Description of both recipes and the top of this README say
that the download is not verified and that a real run is refused, that this README states
no hash, that it has no `make-override` without `--override-dir` and runs no recipe by its
identifier, that it says what was NOT done, and that nothing site-specific is in the
folder.
