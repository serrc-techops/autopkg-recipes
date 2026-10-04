# Win-Slack

A Windows recipe pair: Slack, the per-machine 64-bit `.msi`.

**Status. NOT rehearsed, and the facts of the source NOT fetched by the writer: the writer had no network and read neither Slack's pages nor its download server. Nothing in this folder has run with AutoPkg. These facts are from the writer's knowledge or from another recipe, not from the source: (1) the address of the release notes page, `https://slack.com/release-notes/windows`, and the pattern `Slack\s+(?P<version>[0-9]+\.[0-9]+\.[0-9]+)`, taken from the Cimian authors' own recipe for Slack, which reads the version in the same way, and the assumption that the FIRST match on that page is the newest release; the page may also be built by script, so that the text is not in the HTML that AutoPkg gets; (2) that the processor `URLTextSearcher` outputs a named group of the pattern under its own name, here `version`; (3) the address of the file, `https://downloads.slack-edge.com/desktop-releases/windows/x64/<version>/slack-standalone-<version>.0.msi`, and the name of the per-machine MSI in it (the authors download `Slack.msix` from the same folder instead; the package tool does not take an MSIX); (4) that this MSI is the per-machine installer and that its own version is the one that the package tool will read from it. The first run on the build Mac is the check of every one of them. When it fails, stop: nothing was written. Read the real page or the real release and correct the recipe, never the trust information first.**

**Not verified. The download is NOT verified: Slack publishes no hash for the file, and a check of the signature is not built. Because of this the shared importer REFUSES a real run of this recipe (nothing is published) unless the override sets `pcman_allow_unverified` to true. Do not set it before the signature check exists. Until then run the dry run only, and import by hand after a person has checked the file: `pcman import <file> --template slack` (no `--version` for an MSI). A real run of this recipe has NOT been run by anyone, not against a share and not on a PC, and neither has a dry run. `pcman catalogs` was NOT run either. The Windows overrides folder is not one of AutoPkg's override folders, so every override command here carries `--override-dir`: see the paragraph below.**

| Recipe | Identifier | What it does |
| --- | --- | --- |
| `Slack-Win.download.recipe` | `com.github.serrc-techops.download.Slack-Win` | Reads the newest version from Slack's release notes page (`URLTextSearcher`), then downloads the per-machine MSI from the address that has this version in it. It has no hard check |
| `Slack.cimian.recipe` | `com.github.serrc-techops.cimian.Slack` | Parent: the download recipe. Hands the file to the package tool (`pcman`), which publishes it as a new version of the template item, or says that nothing is new |

The version that the download recipe reads is used only to build the address. It
is not passed to the package tool: for an MSI the package tool takes the MSI's own
version.

Neither recipe stops on an unchanged download, so an import that failed is tried
again at the next run. The processor is in `../Win-SharedProcessors/` (see its
README).

Below, `pcman` stands for
`<the package tool's folder>/.venv/bin/python3 <the package tool's folder>/bin/pcman`.

## What protects, and what does not

Nothing proves that the downloaded file is what Slack published: there is no vendor
hash, and a signature check is not built. The shared importer knows this: no step of
the recipe sets `checksum_verified` with the hash of the file, so a real run is refused
before the package tool starts. Two checks of the package tool remain. They do not
replace a verification.

- **The same product.** The package tool refuses an MSI whose upgrade code
  differs from the template's. So another product cannot be published under the
  name of this template.
- **The label.** The recipe gives no version label. For an MSI the package tool
  takes the MSI's own ProductVersion and refuses a label that is not the MSI's
  own version.

An MSI of the right product with other content (a changed file of the vendor, or a
changed download on the way) would pass both checks. The version read from the page
is not a check: it only chooses which address is asked for.

**No hash source.** Slack publishes no hash for the file, and the recipe has no other
source for one, so the transfer is protected by TLS to the vendor's host and by one rule
of the recipe: **the downloader refuses a redirect that leads to anything but https**
(`curl_opts` `--proto-redir` `=https` on the download step). A redirect to plain HTTP,
from a mirror or from an attacker on the way, stops the run with curl's error (macOS curl
8.7.1 said `Protocol "http" disabled (in redirect)`), and nothing is written. The rule is
about the transfer only: a file that comes over https from the right host, or from a host
that it redirects to, is not checked against anything. The page that gives the version is
fetched without the rule; what it says only chooses the address.

`URLDownloader` of AutoPkg 2.9.0 declares `curl_opts` and adds each item of it to the
download's curl command (`URLDownloader.py`, `prepare_download_curl_cmd`; `URLGetter.py`,
`add_curl_common_opts`), which is why the option and its value are two items. The tests run
curl itself, with these options, against a server on the machine that runs them. Spell the
key exactly: AutoPkg 2.9.0 ignores an argument that it does not know, without a message.

**The page's version and the MSI's own version.** Nothing compares them. The version on
the release notes page only chooses the address; the label of the package tool is the MSI's
own ProductVersion, which the package tool reads from the file, and the two are not written
alike (the address has `<version>.0` in the file name). The comparison is a person's, once,
at the first dry run (step c, run with `-v`): the run prints `URLTextSearcher: Found
matching text (version): ...` for the page, and the dry run's table shows the MSI's own
version in its Version column. Compare their numbers. If they differ in more than a
trailing part, stop and tell the owner before anything is published: the file may not be
the version that the page announced. The recipe does not repeat the comparison at later
runs.

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
   (the share mounted). For an MSI the package tool needs `msiinfo` (the processor
   looks for it in its default `PATH`, which has the Homebrew folders).

3. **The template item, made once by a first import**, so that its pkginfo and
   installer are in the repository. The template keeps the name of the item that
   it replaces. The command, with a real MSI:

       pcman import <path of the MSI> --name slack \
           --display-name Slack --category <the category of the item> \
           --developer "Slack Technologies" --description "<one line about the item>" \
           --directory <the folder of the item> --architectures x64 --no-prompt --build

   There is no `--version`: the package tool takes the MSI's own version. The
   install arguments are not given: the package tool knows the arguments of an MSI
   (silent, no restart); read what it wrote into the pkginfo and check it. Add the
   icon as the package tool's README describes. A person changes the template
   later; nothing else does. **If the template is made from the installer that is
   current at the vendor, the first run says "Nothing new" (see step c). To see a
   dry run that would publish, make the template from an older version.**

## b. Make the override INTO THE WINDOWS OVERRIDES FOLDER

First check that no other recipe has the same name. AutoPkg takes the first match
by name and says nothing about the others:

    autopkg list-recipes | grep -i Slack-Win
    autopkg list-recipes | grep -i Slack.cimian

Each name must be listed once, from this repository. (Not run: the lines of the
output are not known.) Then make the override:

    autopkg make-override --override-dir=<the Windows overrides folder> Slack.cimian

**Why: without `--override-dir` the override lands in AutoPkg's normal overrides
folder, and a nightly script that runs every override there would run it too.**
The command takes the recipe's name, `Slack.cimian`, not a path. Expected: it
writes `<the Windows overrides folder>/Slack.cimian.recipe` with the identifier
`local.cimian.Slack` and the trust information of the two recipes and of the
one processor that is not part of AutoPkg itself (`PcmanImporter`). **Open the written file and read
`ParentRecipe`: it must be `com.github.serrc-techops.download.Slack-Win`.** Another value
means that AutoPkg found another recipe of the same name.

## c. First try: a dry run

Run the override BY PATH and with `--override-dir` (see above), with `-v` so that the
version found on the page is printed (`-v` prints what each processor says about its own
work; `-vv` would add every processor's inputs and outputs to the log, `pcman_root` and the
repository among them, and such a log would have to be kept private):

    autopkg run -v --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.cimian.recipe

**Why by path:** the recipe's name or identifier
(`com.github.serrc-techops.cimian.Slack`) runs the recipe itself, not the
override. The recipe itself never leaves the dry run, so the real run of step e
would never happen.

Expected, also without `-v`, when the current version is not yet in the
repository (the lines of the 7-Zip rehearsal, with this program's name; they were
NOT seen for this recipe, and the version is the MSI's own):

    WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. ...
    WARNING: the download was NOT verified: no step of the recipe set checksum_verified together with the checksum_sha256 of this file. ...
    Dry run: the package tool wrote nothing (pcman_dry_run is on):
    Name   Version  Catalogs    Result
    slack  <the MSI's own version>  Production  dry run, nothing written, NOT verified

The plan itself is not printed. The repository is unchanged. If the current
version is in the repository already (the template was made from it), the line is
`Nothing new: ... is in the repository already. Nothing was written.` instead.
That is correct.

## d. Switch a real run on (NOT YET: see the second paragraph at the top)

A real run of this recipe is refused. `pcman_dry_run` set to false is not enough:

    The download was not verified: no step of the recipe set checksum_verified together
    with the checksum_sha256 of this file. Nothing was published. Publish by hand after
    checking the file, or set pcman_allow_unverified to true in the override.

**The right way for now: import by hand.** A person checks the file first. The command
is the same for every new version. It uses the template, so it makes no second item:

    pcman import <the file> --template slack

Do not add `--version` for an MSI: the package tool takes the MSI's own version. Then
`pcman catalogs` (step e.3).

**Only after the signature check exists, or when a person has decided to accept an
unverified download:** the override allows it. Both lines are needed.

    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_dry_run bool false' \
        <the Windows overrides folder>/Slack.cimian.recipe
    /usr/libexec/PlistBuddy -c 'Add :Input:pcman_allow_unverified bool true' \
        <the Windows overrides folder>/Slack.cimian.recipe
    autopkg verify-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.cimian.recipe

A change of the `Input` does not break trust (rehearsed with 7-Zip). Do not use `-k`
instead: on the command line it applies to every recipe of that run. A run then prints
`WARNING: published WITHOUT a verified download ...` at any verbosity, and the report's
row says `published, NOT verified`.

## e. The real run, the catalogs, the second run

1. The real run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.cimian.recipe

   Only after both lines of step d. Expected: `Published slack ...`, the warning
   `published WITHOUT a verified download`, and the table

       The following versions were published by the package tool:
       Name   Version  Catalogs    Result
       slack  <the MSI's own version>  Production  published, NOT verified

   The repository then has the MSI under `pkgs/` and its pkginfo under
   `pkgsinfo/`. The item file of the template is not changed.

2. `pcman versions slack` lists the template and the new version.

3. **Build the catalogs: `pcman catalogs`.** Without it no PC sees the new
   version.

4. The second run, by path again:

       autopkg run --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.cimian.recipe

   Expected: `Nothing new: ... is in the repository already. Nothing was
   written.` and `Nothing downloaded, packaged or imported.`

## f. When a recipe or a processor changes upstream

The run fails and publishes nothing:

    Failed local trust verification ... contents differ from expected

Look at what changed, then accept it. Never do this automatically:

    autopkg verify-trust-info -vv --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.cimian.recipe
    autopkg update-trust-info --override-dir=<the Windows overrides folder> <the Windows overrides folder>/Slack.cimian.recipe

## g. A share that is not mounted

With an empty folder as the repository the 7-Zip recipe failed (exit code 70)
with the tool's line:

    the repository does not hold the pkginfo of the template ...: is the share mounted, and was the template built?

Nothing was written. Mount the share, then run again.

## Other facts

- A run prints at any verbosity: the dry-run warning, "Nothing new", "Published",
  and the tool's NOTE and WARNING lines. `-vv` also prints `pcman_root` and the
  repository: keep that log private.
- The version read from the release notes page builds the address and nothing
  else. It is not given to the package tool. The MSI's own ProductVersion may not
  be the text on the page (the address has `<version>.0` in the file name); the
  package tool takes the MSI's own. The first dry run shows it.
- If the pattern finds nothing, the run stops at the first step with a message of
  `URLTextSearcher`. That means the page's text is not in the HTML that AutoPkg
  gets, or its layout changed. Read the page, then correct the recipe.
- If the address of the file answers "not found" or "access denied", the name of
  the file or the version in it is wrong. The page may name a version before its
  installer is on the server.
- Whether the MSI is a per-machine or a per-user install is the installer's own
  property, not read here.
- The size of the file is not known to the writer. The processor waits 30 minutes
  by default (`pcman_timeout`), which is a limit for the copy to the share.
- The recipe's `NAME` is `Slack` and `PCMAN_TEMPLATE` is `slack`. Change
  the template name in the override's `Input` (`PCMAN_TEMPLATE`), not in the recipe.

## Tests

From this folder, no AutoPkg and no network needed:

    python3 -m unittest discover -s tests -t tests

They check that both files are property lists, that the Description of both recipes
and the top of this README say that the download is not verified, that a real run is
refused, and that nothing was rehearsed or fetched, that this README states no hash, that every
argument is an input that the shared processor declares, that the pattern that reads the version
matches `Slack 4.41.105` and outputs the group `version`, and does not match `Slack 4.41`,
that the address of the file has the version in it and ends in `.msi`, that the download
refuses a redirect to anything but https (and, with the local `curl`, that it does), that no recipe sets
`pcman_version` for an MSI, that this README has no `make-override` without
`--override-dir` and runs no recipe by its identifier, and that nothing
site-specific is in the folder.
