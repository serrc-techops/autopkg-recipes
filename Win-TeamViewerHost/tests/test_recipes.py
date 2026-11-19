"""Tests of the TeamViewer Host recipes. Nothing here runs AutoPkg or uses the network.

The recipes are read as property lists. The steps that name a processor of this
repository are compared with what that processor declares (see
../../Win-SharedProcessors and ../../Win-PcmanProcessors). The two core steps that
take the MSI out of the zip (Unarchiver, FileFinder) are run as a model of what
AutoPkg 2.9.0's source does with the recipe's own arguments, against small made-up
zips. No test uses the real vendor zip.

The download has NO hard check (no vendor hash, no signature check). The tests make
sure that nobody can overlook that: the Description of every recipe and the top of
the README say it, and no recipe invents a check.
"""
import glob
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.dirname(TESTS_DIR)
SHARED_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-SharedProcessors")
SHARED_TESTS_DIR = os.path.join(SHARED_DIR, "tests")
PCMAN_DIR = os.path.join(os.path.dirname(RECIPE_DIR), "Win-PcmanProcessors")
PCMAN_TESTS_DIR = os.path.join(PCMAN_DIR, "tests")
for _folder in (SHARED_TESTS_DIR, PCMAN_TESTS_DIR):
    if _folder not in sys.path:
        sys.path.insert(0, _folder)

import _win_support  # noqa: E402  (installs the autopkglib stand-in, imports the processors)
import _pcman_support  # noqa: E402  (the stand-in for the package tool, and its processor)
import test_public_repository as shared_hygiene  # noqa: E402

IDENTIFIER_PREFIX = "com.github.serrc-techops"
SHARED_PREFIX = IDENTIFIER_PREFIX + ".SharedProcessors/"
PCMAN_PREFIX = IDENTIFIER_PREFIX + ".PcmanProcessors/"
DOWNLOAD = os.path.join(RECIPE_DIR, "TeamViewerHost-Win.download.recipe")
CIMIAN = os.path.join(RECIPE_DIR, "TeamViewerHost.cimian.recipe")
PCMAN = os.path.join(RECIPE_DIR, "TeamViewerHost.pcman.recipe")
README = os.path.join(RECIPE_DIR, "README.md")
RECIPES = (DOWNLOAD, CIMIAN, PCMAN)
# Processors that are part of AutoPkg itself.
CORE_PROCESSORS = ("URLDownloader", "EndOfCheckPhase", "Unarchiver", "FileFinder")
VENDOR_URL = "https://download.teamviewer.com/download/version_15x/TeamViewer_MSI64.zip"
HOST_MEMBER = "Host/TeamViewer_Host.msi"
FULL_MEMBER = "Full/TeamViewer_Full.msi"
TEMPLATE = "teamviewer.host"
# Inputs that must never appear in a recipe of this repository.
NEVER_IN_A_RECIPE = ("pcman_root", "pcman_dry_run", "pcman_python", "pcman_path", "pcman_cimian_repo",
                     "pcman_config", "pcman_cimian_catalogs", "pcman_state_dir", "pcman_timeout",
                     "cimian_repo", "cimian_dry_run", "cimian_path", "cimian_catalogs", "CIMIAN_REPO")
HEX_64 = re.compile(r"(?i)\b[0-9a-f]{64}\b")


def load(path):
    with open(path, "rb") as handle:
        return plistlib.load(handle)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def flat(text):
    return re.sub(r"\s+", " ", text)


def first_sentence(text):
    return re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]


def step(recipe, processor):
    matches = [s for s in recipe["Process"] if s["Processor"] == processor]
    assert len(matches) == 1, processor
    return matches[0].get("Arguments", {})


def substitute(value, variables):
    """AutoPkg's %name% substitution, for a string argument."""
    if not isinstance(value, str):
        return value
    for name in re.findall(r"%([A-Za-z_]+)%", value):
        value = value.replace("%" + name + "%", str(variables[name]))
    return value


def write_vendor_zip(path, members):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


def vendor_members(host=b"HOST MSI", full=b"FULL MSI"):
    """The six members of the vendor's zip, with made-up bytes."""
    members = {
        "Full/Manuals/CommandLineParameters.url": b"[InternetShortcut]\n",
        "Full/Manuals/MassDeployment.url": b"[InternetShortcut]\n",
        "Host/Manuals/CommandLineParameters.url": b"[InternetShortcut]\n",
        "Host/Manuals/MassDeployment.url": b"[InternetShortcut]\n",
    }
    if full is not None:
        members[FULL_MEMBER] = full
    if host is not None:
        members[HOST_MEMBER] = host
    return members


class CoreStepError(Exception):
    """What AutoPkg's ProcessorError would be in a run."""


def run_core_steps(cache_dir, zip_path, recipe=None):
    """The download recipe's steps after EndOfCheckPhase, with the recipe's own arguments.

    A model of AutoPkg 2.9.0 (Code/autopkglib/Unarchiver.py and FileFinder.py, read, not
    run): Unarchiver empties destination_path when it exists and purge_destination is
    true, refuses (native extractor) a member that resolves outside the folder, and
    extracts with zipfile; FileFinder globs `pattern`, stops with "No matching filename
    found" when nothing matches, and sets found_filename. Returns the run's variables."""
    recipe = recipe or load(DOWNLOAD)
    env = dict(recipe["Input"])
    env.update({"RECIPE_CACHE_DIR": cache_dir, "pathname": zip_path})
    unarchiver = {k: substitute(v, env) for k, v in step(recipe, "Unarchiver").items()}
    destination = unarchiver.get("destination_path", os.path.join(cache_dir, env["NAME"]))
    if unarchiver.get("archive_format") != "zip":
        raise CoreStepError("archive_format is not zip")
    if os.path.exists(destination):
        if unarchiver.get("purge_destination"):
            for entry in os.listdir(destination):
                path = os.path.join(destination, entry)
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.unlink(path)
    else:
        os.makedirs(destination)
    with zipfile.ZipFile(unarchiver["archive_path"]) as archive:
        if unarchiver.get("USE_PYTHON_NATIVE_EXTRACTOR"):
            real = os.path.realpath(destination)
            for name in archive.namelist():
                target = os.path.realpath(os.path.join(destination, name))
                if not (target == real or target.startswith(real + os.sep)):
                    raise CoreStepError("Archive contains path %r that would extract outside" % name)
        archive.extractall(destination)
    env.update(unarchiver)
    finder = {k: substitute(v, env) for k, v in step(recipe, "FileFinder").items()}
    matches = sorted(glob.glob(finder["pattern"], recursive=True))
    if not matches:
        raise CoreStepError("No matching filename found")
    env["found_filename"] = matches[-1]
    return env


def child_arguments(recipe_path, run):
    recipe = load(recipe_path)
    variables = dict(recipe["Input"])
    variables.update(run)  # what the run (or an override) set wins over the recipe's Input
    return {k: substitute(v, variables) for k, v in recipe["Process"][0]["Arguments"].items()}


class RecipeFileTests(unittest.TestCase):
    def test_the_three_files_are_valid_property_lists_with_the_keys_that_autopkg_reads(self):
        for path in RECIPES:
            with self.subTest(path=os.path.basename(path)):
                if os.path.exists("/usr/bin/plutil"):
                    result = subprocess.run(["plutil", "-lint", path], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                recipe = load(path)
                for key in ("Description", "Identifier", "Input", "MinimumVersion", "Process"):
                    self.assertIn(key, recipe)

    def test_identifiers_and_parents(self):
        download, cimian, pcman = load(DOWNLOAD), load(CIMIAN), load(PCMAN)
        self.assertEqual(download["Identifier"], IDENTIFIER_PREFIX + ".download.TeamViewerHost-Win")
        self.assertEqual(cimian["Identifier"], IDENTIFIER_PREFIX + ".cimian.TeamViewerHost")
        self.assertEqual(pcman["Identifier"], IDENTIFIER_PREFIX + ".pcman.TeamViewerHost")
        self.assertEqual(cimian["ParentRecipe"], download["Identifier"])
        self.assertEqual(pcman["ParentRecipe"], download["Identifier"])
        self.assertNotIn("ParentRecipe", download)
        self.assertEqual(cimian["MinimumVersion"], pcman["MinimumVersion"])

    def test_the_download_steps_in_order(self):
        steps = [s["Processor"] for s in load(DOWNLOAD)["Process"]]
        self.assertEqual(steps, ["URLDownloader", "EndOfCheckPhase", "Unarchiver", "FileFinder"])

    def test_the_downloader_arguments(self):
        recipe = load(DOWNLOAD)
        self.assertEqual(step(recipe, "URLDownloader"), {"url": "%DOWNLOAD_URL%", "filename": "%DOWNLOAD_FILENAME%"})
        self.assertEqual(recipe["Input"]["DOWNLOAD_URL"], VENDOR_URL)
        self.assertEqual(recipe["Input"]["DOWNLOAD_FILENAME"], "TeamViewer_MSI64.zip")

    def test_the_inputs_of_the_download_recipe(self):
        self.assertEqual(load(DOWNLOAD)["Input"], {
            "NAME": "TeamViewerHost", "DOWNLOAD_URL": VENDOR_URL, "DOWNLOAD_FILENAME": "TeamViewer_MSI64.zip",
            "TEAMVIEWER_MSI_MEMBER": HOST_MEMBER})

    def test_the_unarchiver_empties_its_folder_and_uses_the_native_extractor(self):
        args = step(load(DOWNLOAD), "Unarchiver")
        self.assertEqual(args["archive_path"], "%pathname%")
        self.assertEqual(args["destination_path"], "%RECIPE_CACHE_DIR%/unpacked")
        self.assertIs(args["purge_destination"], True)  # a boolean, not the text "true"
        self.assertEqual(args["archive_format"], "zip")
        self.assertIs(args["USE_PYTHON_NATIVE_EXTRACTOR"], True)
        self.assertEqual(sorted(args), ["USE_PYTHON_NATIVE_EXTRACTOR", "archive_format", "archive_path",
                                        "destination_path", "purge_destination"])

    def test_the_file_finder_looks_for_the_one_member_in_the_unarchivers_folder(self):
        recipe = load(DOWNLOAD)
        pattern = step(recipe, "FileFinder")["pattern"]
        self.assertEqual(pattern, step(recipe, "Unarchiver")["destination_path"] + "/%TEAMVIEWER_MSI_MEMBER%")
        self.assertEqual(sorted(step(recipe, "FileFinder")), ["pattern"])

    def test_the_member_is_the_host_msi_and_no_glob(self):
        member = load(DOWNLOAD)["Input"]["TEAMVIEWER_MSI_MEMBER"]
        self.assertEqual(member, HOST_MEMBER)
        self.assertNotRegex(member, r"[*?\[\]]")  # FileFinder globs: a pattern could match another file
        self.assertNotIn("Full", member)
        self.assertFalse(member.startswith("/"))
        self.assertNotIn("..", member.split("/"))

    def test_the_child_recipes_import_the_found_file_not_the_zip(self):
        for path in (CIMIAN, PCMAN):
            with self.subTest(path=os.path.basename(path)):
                self.assertEqual(load(path)["Process"][0]["Arguments"]["pathname"], "%found_filename%")

    def test_the_inputs_and_arguments_of_the_cimian_recipe(self):
        recipe = load(CIMIAN)
        self.assertEqual([s["Processor"] for s in recipe["Process"]], [SHARED_PREFIX + "CimianImporter"])
        self.assertEqual(recipe["Input"], {"CIMIAN_NAME": TEMPLATE, "CIMIAN_SUBDIRECTORY": "", "NAME": "TeamViewerHost",
                                           "pkginfo": {"display_name": "TeamViewer Host"}})
        self.assertEqual(recipe["Process"][0]["Arguments"], {
            "pathname": "%found_filename%", "cimian_name": "%CIMIAN_NAME%",
            "cimian_subdirectory": "%CIMIAN_SUBDIRECTORY%", "version": ""})

    def test_the_inputs_and_arguments_of_the_pcman_recipe(self):
        recipe = load(PCMAN)
        self.assertEqual([s["Processor"] for s in recipe["Process"]], [PCMAN_PREFIX + "PcmanImporter"])
        self.assertEqual(recipe["Input"], {"NAME": "TeamViewerHost", "PCMAN_TEMPLATE": TEMPLATE})
        self.assertEqual(recipe["Process"][0]["Arguments"],
                         {"pathname": "%found_filename%", "pcman_template": "%PCMAN_TEMPLATE%"})

    def test_no_version_label_for_an_msi(self):
        """The importers take the MSI's own ProductVersion. A label from the recipe would be refused or
        would hide the real version; the cimian recipe passes an empty version so that nothing of the run
        is taken for it."""
        for path in RECIPES:
            text = read(path)
            self.assertNotIn("pcman_version", text)
            self.assertNotIn("%version%", text)
        self.assertNotIn("<key>version</key>", read(PCMAN))
        self.assertNotIn("<key>version</key>", read(DOWNLOAD))

    def test_no_stop_on_an_unchanged_download_and_no_latest_only(self):
        for path in RECIPES:
            text = read(path)
            for word in ("StopProcessingIf", "latest_only", "blocking_applications"):
                self.assertNotIn(word, text)
        self.assertIn("never stops on an unchanged download", flat(load(DOWNLOAD)["Description"]))

    def test_nothing_of_the_build_machine_is_in_a_recipe(self):
        for path in RECIPES:
            text = read(path)
            for name in NEVER_IN_A_RECIPE + ("catalogs", "catalog", "repo", "directory"):
                with self.subTest(path=os.path.basename(path), name=name):
                    self.assertNotIn("<key>%s</key>" % name, text)

    def test_no_value_of_a_recipe_is_a_path_or_a_catalog(self):
        for path in RECIPES:
            recipe = load(path)
            values = list(recipe["Input"].values())
            for s in recipe["Process"]:
                values.extend(s.get("Arguments", {}).values())
            for value in values:
                if not isinstance(value, str) or value.startswith("https://"):
                    continue
                with self.subTest(path=os.path.basename(path), value=value):
                    self.assertFalse(value.startswith(("/", "~", ".")), value)
                    self.assertNotIn("\\", value)
                    self.assertNotIn("Production", value)
                    self.assertNotIn("Testing", value)


class NotVerifiedTests(unittest.TestCase):
    def test_every_description_begins_by_saying_that_nothing_is_verified(self):
        for path in RECIPES:
            with self.subTest(path=os.path.basename(path)):
                self.assertIn("NOT verified yet", first_sentence(load(path)["Description"]))

    def test_the_download_description_names_the_missing_checks_and_both_flags(self):
        text = flat(load(DOWNLOAD)["Description"])
        self.assertIn("no hash", first_sentence(text))
        self.assertIn("signature", first_sentence(text))
        self.assertIn("refuses a real run of the cimian recipe unless the override sets cimian_allow_unverified to true "
                      "(pcman_allow_unverified for the package tool's recipe)", text)

    def test_the_download_description_says_that_the_vendor_does_not_document_the_address(self):
        text = flat(load(DOWNLOAD)["Description"])
        self.assertIn(VENDOR_URL, text)
        self.assertIn("No page of TeamViewer names this address", text)
        self.assertIn("not documented by the vendor", text)
        self.assertNotIn("documented by TeamViewer", text)
        self.assertIn("known from third-party packaging scripts", text)
        self.assertNotIn("winget", text.lower())  # no winget manifest names this address

    def test_the_download_description_says_from_which_autopkg_the_member_guard_is(self):
        self.assertIn("in AutoPkg 2.9.0 and later it refuses a member that would land outside the folder",
                      flat(load(DOWNLOAD)["Description"]))

    def test_the_child_descriptions_say_what_still_protects_and_what_is_refused(self):
        for path, flag in ((CIMIAN, "cimian_allow_unverified"), (PCMAN, "pcman_allow_unverified")):
            text = flat(load(path)["Description"])
            with self.subTest(path=os.path.basename(path)):
                self.assertIn("A real run is refused", text)
                self.assertIn(flag, text)
                self.assertIn("published, NOT verified", text)
                self.assertIn("upgrade code differs from the template's", text)
                self.assertIn("a label that is not the MSI's own version", text)
                self.assertIn("dry run", text)
                self.assertIn("not of this recipe", text)
        self.assertNotIn("pcman", load(CIMIAN)["Description"])
        self.assertNotIn("package tool", load(CIMIAN)["Description"])

    def test_no_recipe_sets_an_allowance_or_a_verified_flag_or_a_checksum(self):
        for path in RECIPES:
            text = read(path)
            with self.subTest(path=os.path.basename(path)):
                for word in ("<key>pcman_allow_unverified</key>", "<key>cimian_allow_unverified</key>",
                             "<key>cimian_allow_product_change</key>", "checksum_verified", "signature_verified",
                             "ChecksumVerifier", "expected_sha256", "CodeSignatureVerifier"):
                    self.assertNotIn(word, text)
                self.assertNotIn("sha256", text.lower())
                self.assertIsNone(HEX_64.search(text))


class SharedProcessorTests(unittest.TestCase):
    CLASSES = {"CimianImporter": _win_support.cimian.CimianImporter,
               "PcmanImporter": _pcman_support.importer.PcmanImporter}

    def test_every_named_processor_exists(self):
        for path in RECIPES:
            for s in load(path)["Process"]:
                name = s["Processor"]
                if name.startswith(SHARED_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(SHARED_DIR, name[len(SHARED_PREFIX):] + ".py")), name)
                elif name.startswith(PCMAN_PREFIX):
                    self.assertTrue(os.path.isfile(os.path.join(PCMAN_DIR, name[len(PCMAN_PREFIX):] + ".py")), name)
                else:
                    self.assertIn(name, CORE_PROCESSORS)

    def test_every_argument_is_a_declared_input_and_every_required_input_is_given(self):
        for path in (CIMIAN, PCMAN):
            s = load(path)["Process"][0]
            name = s["Processor"].rsplit("/", 1)[-1]
            declared = self.CLASSES[name].input_variables
            for key in s["Arguments"]:
                with self.subTest(processor=name, argument=key):
                    self.assertIn(key, declared)
            for key, flags in declared.items():
                if flags.get("required") and "default" not in flags and key != "pcman_root":
                    with self.subTest(processor=name, required=key):
                        self.assertIn(key, s["Arguments"])
            self.assertNotIn("pcman_root", s["Arguments"])  # an AutoPkg preference of the machine


class CoreStepTests(unittest.TestCase):
    """The two core steps, as AutoPkg 2.9.0's source reads, with the recipe's own arguments."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="win-teamviewer-tests-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = os.path.realpath(self._tmp.name)
        self.cache = os.path.join(self.tmp, "recipe cache")  # a space on purpose
        os.makedirs(os.path.join(self.cache, "downloads"))

    def vendor_zip(self, name="TeamViewer_MSI64.zip", **members):
        return write_vendor_zip(os.path.join(self.cache, "downloads", name), vendor_members(**members))

    def test_the_host_msi_is_found_and_not_the_full_one(self):
        env = run_core_steps(self.cache, self.vendor_zip())
        self.assertEqual(env["found_filename"], os.path.join(self.cache, "unpacked", "Host", "TeamViewer_Host.msi"))
        with open(env["found_filename"], "rb") as handle:
            self.assertEqual(handle.read(), b"HOST MSI")

    def test_a_file_of_an_earlier_run_is_gone_before_the_next_unpack(self):
        run_core_steps(self.cache, self.vendor_zip(host=b"OLD HOST"))
        stray = os.path.join(self.cache, "unpacked", "left over.txt")
        with open(stray, "w") as handle:
            handle.write("x")
        env = run_core_steps(self.cache, self.vendor_zip(host=b"NEW HOST"))
        self.assertFalse(os.path.exists(stray))
        with open(env["found_filename"], "rb") as handle:
            self.assertEqual(handle.read(), b"NEW HOST")

    def test_a_zip_without_the_member_stops_the_run_and_an_old_msi_is_not_taken(self):
        run_core_steps(self.cache, self.vendor_zip())
        self.assertTrue(os.path.exists(os.path.join(self.cache, "unpacked", HOST_MEMBER)))
        with self.assertRaises(CoreStepError) as caught:
            run_core_steps(self.cache, self.vendor_zip(host=None))
        self.assertIn("No matching filename found", str(caught.exception))
        self.assertFalse(os.path.exists(os.path.join(self.cache, "unpacked", HOST_MEMBER)))

    def test_a_zip_with_the_host_msi_elsewhere_finds_nothing(self):
        members = vendor_members(host=None)
        members["Other/TeamViewer_Host.msi"] = b"ELSEWHERE"
        write_vendor_zip(os.path.join(self.cache, "downloads", "moved.zip"), members)
        with self.assertRaises(CoreStepError):
            run_core_steps(self.cache, os.path.join(self.cache, "downloads", "moved.zip"))

    def test_a_member_that_would_land_outside_the_folder_is_refused(self):
        """The refusal is the model's copy of AutoPkg 2.9.0's member check, switched on by the recipe's
        USE_PYTHON_NATIVE_EXTRACTOR. The second assertion would hold without any check (zipfile drops a ".."
        part by itself); it is kept to show that nothing lands outside either way."""
        members = vendor_members()
        members["../outside.txt"] = b"x"
        path = write_vendor_zip(os.path.join(self.cache, "downloads", "tricky.zip"), members)
        with self.assertRaises(CoreStepError):
            run_core_steps(self.cache, path)
        self.assertFalse(os.path.exists(os.path.join(self.cache, "outside.txt")))

    def test_the_child_recipes_get_the_host_msi_as_pathname(self):
        env = run_core_steps(self.cache, self.vendor_zip())
        for path in (CIMIAN, PCMAN):
            with self.subTest(path=os.path.basename(path)):
                self.assertEqual(child_arguments(path, env)["pathname"], env["found_filename"])
                self.assertNotEqual(child_arguments(path, env)["pathname"], env["pathname"])  # not the zip


class CimianChainTests(_win_support.RepoTestCase):
    """The real CimianImporter with the file that the core steps found, into a temporary repository."""

    def found(self):
        with open(self.msi, "rb") as handle:
            host = handle.read()
        cache = os.path.join(self.tmp, "recipe cache")
        os.makedirs(os.path.join(cache, "downloads"), exist_ok=True)
        zip_path = write_vendor_zip(os.path.join(cache, "downloads", "TeamViewer_MSI64.zip"),
                                    vendor_members(host=host, full=b"\xd0\xcf\x11\xe0 another product"))
        return run_core_steps(cache, zip_path)

    def run_chain(self, run, **extra):
        env = dict(run)
        env.update(load(CIMIAN)["Input"])
        env.update({"cimian_repo": self.repo, "cimian_dry_run": False, "cimian_path": self.msi_bin})
        env.update(child_arguments(CIMIAN, env))
        env.update(extra)
        return _win_support.run_processor(_win_support.cimian.CimianImporter, env)

    @_win_support.needs_yaml
    def test_a_real_run_is_refused_without_the_allowance_and_writes_nothing(self):
        run = self.found()
        before = self.repo_tree()
        with self.assertRaises(_win_support.ProcessorError) as caught:
            self.run_chain(run)
        self.assertIn(_win_support.cimian.UNVERIFIED_REASON, str(caught.exception))
        self.assertEqual(self.repo_tree(), before)

    @_win_support.needs_yaml
    def test_with_the_allowance_the_host_msi_is_published_not_verified(self):
        run = self.found()
        processor, _ = self.run_chain(run, cimian_allow_unverified=True)
        self.assertEqual(processor.env["cimian_importer_summary_result"]["data"]["result"], "published, NOT verified")
        new = self.read_pkginfo("%s-%s.yaml" % (TEMPLATE, processor.env["cimian_version_imported"]))
        self.assertEqual(new["name"], TEMPLATE)
        self.assertEqual(new["display_name"], "TeamViewer Host")
        self.assertEqual(new["installer"]["type"], "msi")
        self.assertEqual(new["installer"]["hash"], _win_support.sha256_hex(self.msi))
        self.assertEqual(processor.env["cimian_version_imported"], "2.5.0")  # the MSI's own version


class PcmanChainTests(_pcman_support.ToolTestCase):
    """The real PcmanImporter with the file that the core steps found; the package tool is a stand-in."""

    def found(self):
        cache = os.path.join(self.tmp, "recipe cache")
        os.makedirs(os.path.join(cache, "downloads"), exist_ok=True)
        zip_path = write_vendor_zip(os.path.join(cache, "downloads", "TeamViewer_MSI64.zip"), vendor_members())
        return run_core_steps(cache, zip_path)

    def run_chain(self, run, **extra):
        env = dict(run)
        env.update({"pcman_root": self.root, "pcman_dry_run": False, "pcman_path": self.msi_bin})
        env.update(child_arguments(PCMAN, env))
        env.update(extra)
        return _win_support.run_processor(_pcman_support.importer.PcmanImporter, env)

    def test_a_real_run_is_refused_before_the_tool_starts(self):
        with self.assertRaises(_win_support.ProcessorError) as caught:
            self.run_chain(self.found())
        self.assertIn(_pcman_support.importer.UNVERIFIED_REASON, str(caught.exception))
        self.assertFalse(self.was_run())

    def test_with_the_allowance_the_tool_gets_the_host_msi_and_the_template(self):
        run = self.found()
        self.run_chain(run, pcman_allow_unverified=True)
        argv = self.record()["argv"]
        self.assertIn(run["found_filename"], argv)
        self.assertNotIn(run["pathname"], argv)  # never the zip
        self.assertIn(TEMPLATE, argv)
        self.assertNotIn("--version", argv)


class HygieneTests(unittest.TestCase):
    def files(self):
        for folder, dirs, files in os.walk(RECIPE_DIR):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if not name.endswith(".pyc"):
                    yield os.path.join(folder, name)

    def test_no_file_holds_a_value_that_belongs_to_one_site(self):
        for path in self.files():
            text = read(path)
            for kind, pattern in shared_hygiene.FORBIDDEN_PATTERNS.items():
                with self.subTest(file=os.path.relpath(path, RECIPE_DIR), kind=kind):
                    self.assertIsNone(pattern.search(text))

    def test_nothing_deeper_than_the_tests_folder(self):
        for path in self.files():
            self.assertLessEqual(len(os.path.relpath(path, RECIPE_DIR).split(os.sep)), 2, path)

    def test_the_folder_holds_only_what_is_expected(self):
        names = sorted(os.path.relpath(path, RECIPE_DIR) for path in self.files())
        self.assertEqual(names, sorted([
            "TeamViewerHost-Win.download.recipe", "TeamViewerHost.cimian.recipe", "TeamViewerHost.pcman.recipe",
            "README.md", os.path.join("tests", "__init__.py"), os.path.join("tests", "test_recipes.py"),
        ]))


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.raw = read(README)
        self.text = flat(self.raw)
        self.status = [line for line in self.raw.splitlines() if line.startswith("**Status.")][0]

    def test_the_readme_opens_with_a_bold_status_line(self):
        lines = [line for line in self.raw.splitlines() if line.strip()]
        self.assertEqual(lines[0], "# Win-TeamViewerHost")
        self.assertTrue(lines[2].startswith("**Status.") and lines[2].endswith("**"))
        for needle in ("The download is NOT verified", "signature", "REFUSES a real run", "cimian_allow_unverified",
                       "pcman_allow_unverified", VENDOR_URL, "No page of TeamViewer names this address",
                       "It is not documented by the vendor", "known from third-party packaging scripts",
                       "(only this one version was read)", "NOT established", "through either importer",
                       "an install through a Cimian client", "the refusal (error 25001) on a PC",
                       "an upgrade from one version to the next"):
            self.assertIn(needle, self.status)
        self.assertNotIn("winget", self.raw.lower())
        self.assertNotIn("any install on a PC", self.status)
        self.assertNotIn("changes with each version", self.raw)

    def test_the_results_of_the_day_follow_the_status_line(self):
        lines = [line for line in self.raw.splitlines() if line.strip()]
        self.assertTrue(lines[3].startswith("**Results of 2026-11-19.**"), lines[3][:60])
        results = lines[3]
        for needle in ("ran under AutoPkg 2.9.0 on a Mac", "the Host MSI was found", "begins `6f3c7f15`",
                       "curl error 56", "the second went through", "as SYSTEM",
                       "`msiexec /i <file> /qn /norestart` (exit code 0 after 18 seconds)",
                       "`msiexec /x <ProductCode> /qn /norestart` (exit code 0 after 38 seconds)",
                       "the uninstall entry and the service were gone",
                       "the program folder and the settings key, which holds the device's TeamViewer ID, stayed"):
            self.assertIn(needle, results)

    def test_the_readme_says_what_still_protects_and_that_it_is_not_enough(self):
        for needle in ("The same product", "refuse an MSI whose upgrade code differs from the template's",
                       "refuse a label that is not the MSI's own version", "They do not replace a verification",
                       "no processor of this repository checks an Authenticode signature",
                       "Once the item exists, the importers refuse",
                       "On the first import there is no template, and so no upgrade code to compare",
                       "a checksum of the zip stops the run",
                       "hands the zip's verified hash over to the MSI"):
            self.assertIn(needle, self.text)
        self.assertNotIn("the Full client among them", self.text)

    def test_the_conflicts_and_whose_job_the_removal_is(self):
        section = flat(self.raw[self.raw.index("## What the MSI refuses to install over"):
                                self.raw.index("## Run every override")])
        for needle in ("error 25001", "Full 32-bit, Full 64-bit or Host 32-bit", "a Full MSI (32-bit, 64-bit or ARM64)",
                       "the ARM64 Host MSI", "a newer 32-bit Host MSI", "{150798A5-21DE-431E-BDC7-A822769BE9A2}",
                       "**That removal is the job of the item in the repository", "not of these recipes.**",
                       "company account is not part of this item"):
            self.assertIn(needle, section)

    def test_the_two_core_steps_are_described_and_marked_as_read_not_run(self):
        for needle in ("`purge_destination`", "`USE_PYTHON_NATIVE_EXTRACTOR`", "`TEAMVIEWER_MSI_MEMBER`",
                       "`found_filename`", "No matching filename found", "read in the source of AutoPkg 2.9.0",
                       "the stops (a zip without the member, a member outside the folder) were NOT seen in a run", "In AutoPkg 2.9.0 and later it also refuses a member",
                       "older versions extract with Python's `zipfile` alone"):
            self.assertIn(needle, self.text)

    def test_every_autopkg_command_carries_the_override_dir_and_names_its_own_recipe(self):
        lines = re.findall(r"^[ \t]*(autopkg (?:run|verify-trust-info|update-trust-info|make-override)\b[^\n]*)",
                           self.raw, re.M)
        self.assertEqual(len(lines), 9)  # cimian: make-override, verify, two runs, update; pcman: make-override, verify, run, update
        for line in lines:
            with self.subTest(line=line):
                self.assertIn("--override-dir=<the Windows overrides folder>", line)
                self.assertNotIn("com.github.", line)
                if not line.startswith("autopkg make-override"):
                    self.assertRegex(line, r"<the Windows overrides folder>/TeamViewerHost\.(cimian|pcman)\.recipe$")
        for match in re.finditer(r"`(autopkg (?:run|verify-trust-info|update-trust-info|make-override)[^`]*<[^`]*)`",
                                 self.raw):
            self.assertIn("--override-dir=", match.group(1))

    def test_the_parent_is_read_after_the_override_is_made(self):
        for kind in ("cimian", "pcman"):
            self.assertIn("**Open the written file and read `ParentRecipe`: it must be "
                          "`com.github.serrc-techops.%s.TeamViewerHost`" % kind, self.text)
        self.assertIn("First check that no other recipe has the same name.", self.text)

    def test_the_refusal_text_is_the_importers_own(self):
        refusal = "The download was not verified: %s. Nothing was published." % \
            _pcman_support.importer.UNVERIFIED_REASON
        self.assertIn(refusal, self.text)
        for needle in ("Add :Input:cimian_dry_run bool false", "Add :Input:cimian_allow_unverified bool true",
                       "Add :Input:pcman_dry_run bool false", "Add :Input:pcman_allow_unverified bool true",
                       "Both lines are needed", "published WITHOUT a verified download", "published, NOT verified",
                       "Failed local trust verification", "makecatalogs", "pcman catalogs"):
            self.assertIn(needle, self.text)

    def test_the_hand_import_uses_the_template_and_no_version(self):
        commands = re.findall(r"^    (pcman import [^\n]*)$", self.raw, re.M)
        self.assertEqual(commands, ["pcman import <path of the MSI> --name teamviewer.host \\",
                                    "pcman import <the file> --template teamviewer.host"])

    def test_the_first_import_makes_the_template_and_says_what_it_must_carry(self):
        match = re.search(r"pcman import <path of the MSI>([^`]*?--build)", self.raw, re.S)
        self.assertTrue(match)
        command = flat(match.group(1))
        for needle in ("--name teamviewer.host", "--architectures x64", "--display-name \"TeamViewer Host\"",
                       "--no-prompt"):
            self.assertIn(needle, command)
        self.assertNotIn("--version", command)
        self.assertLess(self.raw.index("pcman import <path of the MSI>"),
                        self.raw.index("pcman import <the file> --template"))
        self.assertIn("**The template must then carry the pre-install step that removes a TeamViewer installed from "
                      "the vendor's EXE, or a full client, before the MSI runs**", self.text)
        self.assertIn("NOT run for this item", self.text)

    def test_the_readme_states_no_hash(self):
        self.assertIsNone(HEX_64.search(self.raw))


if __name__ == "__main__":
    unittest.main()
