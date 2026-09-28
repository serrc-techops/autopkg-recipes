"""Behavioural tests for the replacement Munki-postflight-integration block.

The block now has two independent effects: it edits the already-installed
com.github.reportmate.installs launchd job (TriggerTests, below) and it
undoes whatever an earlier, unpatched install left under /usr/local/munki
(ScenarioN classes) -- it never creates anything new there. Every test
builds real on-disk state in a fresh temporary directory, with every path
the block touches rewritten into it (MUNKI_DIR, the launchd job's
directory, and -- only where the *original*, unpatched section is run, to
build a "damaged" starting state -- the log directory its wrapper/
reportmate.sh would otherwise write to), then runs the block for real as a
standalone script (log_message() is the only thing it depends on from the
rest of postinstall, so that is stubbed in).

Hard rule: no job is ever loaded into real launchd. Every installer run
gets a fake `launchctl` prepended to PATH (see run_in_own_group's `env`
support and BehaviourTestCase.run_installer/TriggerTestCase.run_installer)
that only records its own invocations to a file. rewrite_paths() turns
the block's /bin/launchctl into that stand-in, so the real one is never
called.

Every subprocess is started in its own process group
(start_new_session=True) and that whole group is killed in a `finally`
whether the process finished, failed, or timed out -- see
run_in_own_group() -- so scenario 9's intentionally non-terminating
control case cannot leave anything running. tearDownModule() sweeps any
process group a test did not get to clean up itself, as a last resort.

Timeouts here are generous: this sandbox's process-spawn overhead varies
and has been observed well over 0.5s per fork/exec, and a single installer
run spawns many.

Zentral's real Munki postflight runner is used (fixtures/
zentral_postflight_runner.py; only its interpreter line and POSTFLIGHT_DIR
constant are rewritten -- see that file's own header). The per-run script
it runs from postflight.d/ ("zentral", analogous to Zentral's own
zentral_postflight) and every other stand-in script used to populate
postflight.d/ in these scenarios are original to this test suite: each
just appends "<name> ran" to a shared runs.log.

"Compare the tree... names, link targets and checksums" is
snapshot_munki_tree(): a dict of every path under MUNKI_DIR to ("link",
target), ("dir", None), or ("file", sha256) -- symlinks are never
followed, so a dangling one is captured correctly and a checksum is only
ever computed for a real file.
"""
import hashlib
import os
import plistlib
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from collections import Counter

from _support import patcher, read_fixture, FIXTURES_DIR

FIXTURE = read_fixture("postinstall_fixture.sh")

INSTALLER_TIMEOUT = 60.0  # an installer run spawns many processes; generous
NORMAL_TIMEOUT = 45.0     # simulated postflight run, when it should finish
CONTROL_TIMEOUT = 10.0    # scenario 9 is *expected* to still be running at this point


def _section(text, heading, end_log, name):
    start, end = patcher.find_section(text, heading, end_log, name)
    return "\n".join(text.splitlines()[start : end + 1])


ORIGINAL_MUNKI_SECTION = _section(
    FIXTURE, patcher.MUNKI_HEADING, patcher.MUNKI_END_LOG, patcher.MUNKI_SECTION_NAME
)
# The new replacement is fixed text (no per-package substitution beyond the
# marker), so build it directly rather than round-tripping through a patched
# postinstall and re-locating it -- the new block has no "fi" of its own for
# find_section() to anchor on, by design (it no longer depends on whether
# /usr/local/munki exists at all).
PATCHED_MUNKI_SECTION = patcher.build_munki_replacement()

# Upstream's real, unmodified wrapper and postflight.d/reportmate.sh bodies,
# used to build "ReportMate's wrapper/script already here" fixture states.
# Never used as anything this build itself would write -- it writes neither.
ORIGINAL_WRAPPER_BODY = patcher.extract_heredoc(ORIGINAL_MUNKI_SECTION, "WRAPPER_EOF")
ORIGINAL_REPORTMATE_BODY = patcher.extract_heredoc(ORIGINAL_MUNKI_SECTION, "REPORTMATE_EOF")

JOB_PLIST_FIXTURE = os.path.join(FIXTURES_DIR, "reportmate_installs_job.plist")


# --------------------------------------------------------------------------
# Process-group harness (hard rule: own process group, always killed after).
# --------------------------------------------------------------------------

_SPAWNED_PGIDS = []


def _kill_group(pgid):
    if pgid is None:
        return
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if pgid in _SPAWNED_PGIDS:
        _SPAWNED_PGIDS.remove(pgid)


def run_in_own_group(argv, timeout, stdout_path=None, env=None):
    """Run `argv` in its own process group and always kill that whole group
    afterward -- on normal completion, on failure, and on timeout alike.
    Returns (ended, returncode); returncode is None when `ended` is False.
    """
    stdout_handle = open(stdout_path, "wb") if stdout_path else subprocess.DEVNULL
    try:
        proc = subprocess.Popen(
            argv,
            stdout=stdout_handle,
            stderr=subprocess.STDOUT if stdout_path else subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
    finally:
        if stdout_path:
            stdout_handle.close()

    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        pgid = None
    if pgid is not None:
        _SPAWNED_PGIDS.append(pgid)

    ended = True
    returncode = None
    try:
        returncode = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        ended = False
    finally:
        _kill_group(pgid)
        try:
            proc.wait(timeout=5.0)
        except Exception:
            pass
    return ended, returncode


def tearDownModule():
    # Last-resort sweep: every run_in_own_group() call already kills its own
    # group in a `finally`, so this should normally have nothing to do.
    for pgid in list(_SPAWNED_PGIDS):
        _kill_group(pgid)


# --------------------------------------------------------------------------
# Construction helpers.
# --------------------------------------------------------------------------

def write_executable(path, text):
    with open(path, "w") as handle:
        handle.write(text)
    os.chmod(path, 0o755)


def make_recorder_script(name, runs_log_path):
    """A trivial, original-to-this-suite stand-in for a postflight.d/ entry
    (or, for some scenarios, for $POSTFLIGHT itself): it only records that
    it ran, once, into the shared runs.log."""
    return '#!/bin/sh\necho "%s ran" >> "%s"\n' % (name, runs_log_path)


def make_fake_launchctl(bin_dir, calls_log, exit_code=0):
    """A stub `launchctl` that only records "$@" to `calls_log` and exits
    `exit_code`. Never touches real launchd -- this is how every test here
    satisfies "do not load a job into launchd"."""
    write_executable(
        os.path.join(bin_dir, "launchctl"),
        '#!/bin/bash\necho "$@" >> "%s"\nexit %d\n' % (calls_log, exit_code),
    )


def rewrite_paths(text, munki_dir, launchdaemons_dir, log_dir=None):
    text = text.replace("/usr/local/munki", munki_dir)
    text = text.replace("/Library/LaunchDaemons", launchdaemons_dir)
    # The block calls /bin/launchctl; the tests run a recording stand-in.
    text = text.replace("/bin/launchctl", "launchctl")
    if log_dir is not None:
        text = text.replace("/Library/Managed Reports/logs", log_dir)
    return text


def snapshot_munki_tree(munki_dir):
    """Every path under `munki_dir` to ("link", target), ("dir", None), or
    ("file", sha256-hex) -- names, link targets and checksums, exactly as
    required. Symlinks are never followed (so a dangling one, or one to a
    directory, is captured correctly as itself, not descended into)."""
    snapshot = {}
    if not os.path.isdir(munki_dir):
        return snapshot
    for root, dirs, files in os.walk(munki_dir, followlinks=False):
        for name in dirs + files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, munki_dir)
            if os.path.islink(full):
                snapshot[rel] = ("link", os.readlink(full))
            elif os.path.isdir(full):
                snapshot[rel] = ("dir", None)
            else:
                with open(full, "rb") as handle:
                    snapshot[rel] = ("file", hashlib.sha256(handle.read()).hexdigest())
    return snapshot


class BehaviourTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="reportmate-behaviour-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.munki_dir = os.path.join(self.root, "munki")
        self.log_dir = os.path.join(self.root, "logs")
        self.launchdaemons_dir = os.path.join(self.root, "LaunchDaemons")
        os.makedirs(self.launchdaemons_dir, exist_ok=True)
        self.job_plist = os.path.join(
            self.launchdaemons_dir, "com.github.reportmate.installs.plist"
        )
        shutil.copy(JOB_PLIST_FIXTURE, self.job_plist)  # realistic by default
        self.zentral_runtime = os.path.join(self.root, "zentral-runtime")
        self.runs_log = os.path.join(self.root, "runs.log")

        self.fake_bin = os.path.join(self.root, "fake-bin")
        os.makedirs(self.fake_bin, exist_ok=True)
        self.launchctl_calls_log = os.path.join(self.root, "launchctl-calls.log")
        make_fake_launchctl(self.fake_bin, self.launchctl_calls_log)

        self._installer_count = 0

    # -- installer / postflight execution -------------------------------

    def run_installer(self, section_text, timeout=INSTALLER_TIMEOUT, capture=False):
        """Run an installer's Munki section for real, as a standalone
        script (log_message() stubbed, paths rewritten into this test's
        temporary directory, a fake launchctl first on PATH). Returns the
        captured stdout+stderr text when `capture` is true, else None.
        Asserts the installer step itself completed -- it should never
        loop; only the postflight it might leave in place could (that is
        what run_postflight()/scenario 9 check)."""
        self._installer_count += 1
        script_path = os.path.join(self.root, "installer-%d.sh" % self._installer_count)
        body = rewrite_paths(section_text, self.munki_dir, self.launchdaemons_dir, self.log_dir)
        write_executable(
            script_path,
            '#!/bin/bash\nlog_message() { echo "[installer] $1"; }\n' + body + "\n",
        )
        capture_path = (
            os.path.join(self.root, "installer-%d.out" % self._installer_count)
            if capture
            else None
        )
        env = dict(os.environ)
        env["PATH"] = self.fake_bin + ":" + env["PATH"]
        ended, returncode = run_in_own_group(
            ["/bin/bash", script_path], timeout=timeout, stdout_path=capture_path, env=env
        )
        self.assertTrue(
            ended,
            "the installer step itself did not end within %ss (it never "
            "loops -- this is a harness bug, not the bug under test)" % timeout,
        )
        self.assertEqual(returncode, 0, "installer step exited %r" % (returncode,))
        if capture:
            with open(capture_path, "r") as handle:
                return handle.read()
        return None

    def run_postflight(self, timeout=NORMAL_TIMEOUT):
        """Simulate what launchd does after a Munki run: invoke
        $MUNKI_DIR/postflight with the runtype, in its own process group,
        under `timeout`. Returns (ended, returncode)."""
        postflight_path = os.path.join(self.munki_dir, "postflight")
        return run_in_own_group([postflight_path, "auto"], timeout=timeout)

    # -- shared "Zentral already correctly in place" setup ---------------

    def make_zentral_layout(self):
        """postflight -> Zentral's real runner; postflight.d/zentral ->
        the per-run collector it runs (analogous to Zentral's own
        zentral_postflight, but original/trivial for this test suite).
        Returns the runner's real path (not the symlink)."""
        os.makedirs(self.munki_dir, exist_ok=True)
        postflight_d = os.path.join(self.munki_dir, "postflight.d")
        os.makedirs(postflight_d, exist_ok=True)
        os.makedirs(self.zentral_runtime, exist_ok=True)

        runner_text = read_fixture("zentral_postflight_runner.py").replace(
            "__POSTFLIGHT_D__", postflight_d
        )
        runner_path = os.path.join(self.zentral_runtime, "postflight")
        write_executable(runner_path, runner_text)

        collector_path = os.path.join(self.zentral_runtime, "zentral_postflight")
        write_executable(collector_path, make_recorder_script("zentral", self.runs_log))

        os.symlink(runner_path, os.path.join(self.munki_dir, "postflight"))
        os.symlink(collector_path, os.path.join(postflight_d, "zentral"))
        return runner_path

    # -- assertion helpers -------------------------------------------------

    def snapshot(self):
        return snapshot_munki_tree(self.munki_dir)

    def run_count(self, name):
        if not os.path.exists(self.runs_log):
            return 0
        with open(self.runs_log) as handle:
            lines = handle.read().splitlines()
        return Counter(lines)["%s ran" % name]


# --------------------------------------------------------------------------
# Scenario 1: Zentral's runner already correctly in place.
# --------------------------------------------------------------------------

class Scenario1ZentralRunnerAlreadyInPlace(BehaviourTestCase):
    def test_nothing_under_the_folder_changed_and_script_ran_once(self):
        self.make_zentral_layout()
        before = self.snapshot()

        self.run_installer(PATCHED_MUNKI_SECTION)

        self.assertEqual(self.snapshot(), before, "nothing under the folder should have changed")

        ended, returncode = self.run_postflight()
        self.assertTrue(ended, "simulated postflight did not end within the time limit")
        self.assertEqual(returncode, 0)
        self.assertEqual(self.run_count("zentral"), 1)

    def test_run_twice_changes_nothing(self):
        # Scenario 8.
        self.make_zentral_layout()
        self.run_installer(PATCHED_MUNKI_SECTION)
        after_first = self.snapshot()

        self.run_installer(PATCHED_MUNKI_SECTION)

        self.assertEqual(self.snapshot(), after_first)


# --------------------------------------------------------------------------
# Scenario 2: the state upstream's unpatched installer leaves on such a
# Mac, repaired to scenario 1's state.
# --------------------------------------------------------------------------

class Scenario2RepairsToScenario1State(BehaviourTestCase):
    def _damage(self):
        self.make_zentral_layout()
        scenario1_snapshot = self.snapshot()

        # Upstream's own (unpatched) installer, run once: this is exactly
        # what a site running the *unpatched* upstream package would have
        # produced on top of scenario 1's state.
        self.run_installer(ORIGINAL_MUNKI_SECTION)

        postflight_d = os.path.join(self.munki_dir, "postflight.d")
        sal_sh = os.path.join(postflight_d, "sal.sh")
        self.assertTrue(
            os.path.lexists(sal_sh),
            "expected upstream to move the runner to postflight.d/sal.sh",
        )
        with open(os.path.join(self.munki_dir, "postflight")) as handle:
            self.assertIn("Deployed by: ReportMate macOS Client", handle.read())

        return scenario1_snapshot

    def test_repaired_to_scenario_1_state(self):
        scenario1_snapshot = self._damage()

        self.run_installer(PATCHED_MUNKI_SECTION)

        self.assertEqual(self.snapshot(), scenario1_snapshot)

        ended, returncode = self.run_postflight()
        self.assertTrue(ended, "simulated postflight did not end within the time limit")
        self.assertEqual(returncode, 0)
        self.assertEqual(self.run_count("zentral"), 1)

    def test_run_twice_changes_nothing(self):
        # Scenario 8.
        self._damage()
        self.run_installer(PATCHED_MUNKI_SECTION)
        after_first = self.snapshot()

        self.run_installer(PATCHED_MUNKI_SECTION)

        self.assertEqual(self.snapshot(), after_first)


# --------------------------------------------------------------------------
# Scenario 3: no postflight and no postflight.d.
# --------------------------------------------------------------------------

class Scenario3NoPostflightNoDirectory(BehaviourTestCase):
    def test_nothing_was_created(self):
        os.makedirs(self.munki_dir, exist_ok=True)
        self.assertEqual(self.snapshot(), {})

        self.run_installer(PATCHED_MUNKI_SECTION)

        self.assertEqual(self.snapshot(), {}, "nothing should have been created")
        self.assertFalse(os.path.lexists(os.path.join(self.munki_dir, "postflight")))
        self.assertFalse(os.path.isdir(os.path.join(self.munki_dir, "postflight.d")))


# --------------------------------------------------------------------------
# Scenario 4: a plain, unrelated reporting script at $POSTFLIGHT.
# --------------------------------------------------------------------------

class Scenario4PlainReportingScript(BehaviourTestCase):
    def test_unchanged(self):
        os.makedirs(self.munki_dir, exist_ok=True)
        postflight_path = os.path.join(self.munki_dir, "postflight")
        write_executable(postflight_path, make_recorder_script("legacy-postflight", self.runs_log))
        before = self.snapshot()

        self.run_installer(PATCHED_MUNKI_SECTION)

        self.assertEqual(self.snapshot(), before, "must be unchanged, byte for byte")


# --------------------------------------------------------------------------
# Scenario 5: ReportMate's wrapper, with a plain script as munkireport.sh
# and reportmate.sh.
# --------------------------------------------------------------------------

class Scenario5WrapperWithPlainMunkireportScript(BehaviourTestCase):
    def _setup(self):
        os.makedirs(self.munki_dir, exist_ok=True)
        postflight_d = os.path.join(self.munki_dir, "postflight.d")
        os.makedirs(postflight_d, exist_ok=True)

        postflight_path = os.path.join(self.munki_dir, "postflight")
        wrapper_text = rewrite_paths(ORIGINAL_WRAPPER_BODY, self.munki_dir, self.launchdaemons_dir, self.log_dir)
        write_executable(postflight_path, wrapper_text)

        munkireport_path = os.path.join(postflight_d, "munkireport.sh")
        munkireport_text = make_recorder_script("munkireport.sh", self.runs_log)
        write_executable(munkireport_path, munkireport_text)

        reportmate_sh = os.path.join(postflight_d, "reportmate.sh")
        reportmate_text = rewrite_paths(ORIGINAL_REPORTMATE_BODY, self.munki_dir, self.launchdaemons_dir, self.log_dir)
        write_executable(reportmate_sh, reportmate_text)

        return postflight_path, munkireport_path, reportmate_sh, munkireport_text

    def test_plain_script_becomes_postflight_wrapper_and_reportmate_gone(self):
        postflight_path, munkireport_path, reportmate_sh, munkireport_text = self._setup()

        self.run_installer(PATCHED_MUNKI_SECTION)

        self.assertFalse(os.path.lexists(munkireport_path), "should have been moved")
        self.assertFalse(os.path.lexists(reportmate_sh), "should have been removed")
        self.assertTrue(os.path.isfile(postflight_path))
        self.assertFalse(os.path.islink(postflight_path))
        with open(postflight_path) as handle:
            self.assertEqual(handle.read(), munkireport_text, "postflight must be the plain script, byte for byte")

    def test_run_twice_changes_nothing(self):
        # Scenario 8.
        self._setup()
        self.run_installer(PATCHED_MUNKI_SECTION)
        after_first = self.snapshot()

        self.run_installer(PATCHED_MUNKI_SECTION)

        self.assertEqual(self.snapshot(), after_first)


# --------------------------------------------------------------------------
# Scenario 6: ReportMate's wrapper alone, with reportmate.sh.
# --------------------------------------------------------------------------

class Scenario6WrapperAloneWithReportmateScript(BehaviourTestCase):
    def test_no_postflight_no_reportmate_sh(self):
        os.makedirs(self.munki_dir, exist_ok=True)
        postflight_d = os.path.join(self.munki_dir, "postflight.d")
        os.makedirs(postflight_d, exist_ok=True)

        postflight_path = os.path.join(self.munki_dir, "postflight")
        wrapper_text = rewrite_paths(ORIGINAL_WRAPPER_BODY, self.munki_dir, self.launchdaemons_dir, self.log_dir)
        write_executable(postflight_path, wrapper_text)

        reportmate_sh = os.path.join(postflight_d, "reportmate.sh")
        reportmate_text = rewrite_paths(ORIGINAL_REPORTMATE_BODY, self.munki_dir, self.launchdaemons_dir, self.log_dir)
        write_executable(reportmate_sh, reportmate_text)

        self.run_installer(PATCHED_MUNKI_SECTION)

        self.assertFalse(os.path.lexists(postflight_path))
        self.assertFalse(os.path.lexists(reportmate_sh))
        # postflight.d/ itself stays, even now empty.
        self.assertTrue(os.path.isdir(postflight_d))
        self.assertEqual(os.listdir(postflight_d), [])


# --------------------------------------------------------------------------
# Scenario 7: a dangling link at $POSTFLIGHT.
# --------------------------------------------------------------------------

class Scenario7DanglingPostflightLink(BehaviourTestCase):
    def test_unchanged_nothing_created_at_its_target(self):
        os.makedirs(self.munki_dir, exist_ok=True)
        postflight_path = os.path.join(self.munki_dir, "postflight")
        missing_target = os.path.join(self.root, "postflight-not-installed-yet")
        self.assertFalse(os.path.lexists(missing_target))
        os.symlink(missing_target, postflight_path)
        before = self.snapshot()

        self.run_installer(PATCHED_MUNKI_SECTION)

        self.assertEqual(self.snapshot(), before)
        self.assertTrue(os.path.islink(postflight_path))
        self.assertEqual(os.readlink(postflight_path), missing_target)
        self.assertFalse(
            os.path.lexists(missing_target),
            "nothing should have been created at the dangling link's target",
        )


# --------------------------------------------------------------------------
# Scenario 9: control. Upstream's unpatched section, run against scenario
# 1's initial state, must NOT end within the time limit -- this is the bug
# this whole build exists to fix, reproduced to prove the test rig is real.
# --------------------------------------------------------------------------

class Scenario9ControlUnpatchedHangs(BehaviourTestCase):
    def test_unpatched_section_does_not_end_within_the_time_limit(self):
        self.make_zentral_layout()
        # Upstream's own (unpatched) installer, run once: exactly what a
        # site running the *unpatched* upstream package would have.
        self.run_installer(ORIGINAL_MUNKI_SECTION)

        started = time.monotonic()
        ended, returncode = self.run_postflight(timeout=CONTROL_TIMEOUT)
        elapsed = time.monotonic() - started

        self.assertFalse(
            ended,
            "expected upstream's unpatched postflight integration to still "
            "be running after %ss (it recurses into itself); it ended "
            "instead, which would mean the bug this build fixes no longer "
            "reproduces and this whole test suite needs another look" % CONTROL_TIMEOUT,
        )
        self.assertIsNone(returncode)
        self.assertGreaterEqual(elapsed, CONTROL_TIMEOUT)


# --------------------------------------------------------------------------
# The trigger: rule 1, tested against a copy of upstream's own job file.
# Running the whole block (not a hand-sliced "first part") against a
# temporary directory that holds only the job file exercises exactly the
# same code path as "the block's first part" -- the undo steps below it
# only ever act when something is found under /usr/local/munki, and
# nothing is here, so they are no-ops.
# --------------------------------------------------------------------------

class TriggerTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="reportmate-trigger-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.munki_dir = os.path.join(self.root, "munki")  # deliberately never created
        self.launchdaemons_dir = os.path.join(self.root, "LaunchDaemons")
        os.makedirs(self.launchdaemons_dir, exist_ok=True)
        self.job_plist = os.path.join(
            self.launchdaemons_dir, "com.github.reportmate.installs.plist"
        )
        shutil.copy(JOB_PLIST_FIXTURE, self.job_plist)

        self.fake_bin = os.path.join(self.root, "fake-bin")
        os.makedirs(self.fake_bin, exist_ok=True)
        self.launchctl_calls_log = os.path.join(self.root, "launchctl-calls.log")

        self._installer_count = 0

    def run_installer(self, timeout=INSTALLER_TIMEOUT, capture=False):
        self._installer_count += 1
        script_path = os.path.join(self.root, "installer-%d.sh" % self._installer_count)
        body = rewrite_paths(PATCHED_MUNKI_SECTION, self.munki_dir, self.launchdaemons_dir)
        write_executable(
            script_path,
            '#!/bin/bash\nlog_message() { echo "[installer] $1"; }\n' + body + "\n",
        )
        capture_path = (
            os.path.join(self.root, "installer-%d.out" % self._installer_count)
            if capture
            else None
        )
        env = dict(os.environ)
        env["PATH"] = self.fake_bin + ":" + env["PATH"]
        ended, returncode = run_in_own_group(
            ["/bin/bash", script_path], timeout=timeout, stdout_path=capture_path, env=env
        )
        self.assertTrue(ended, "the installer step itself did not end within %ss" % timeout)
        self.assertEqual(returncode, 0)
        if capture:
            with open(capture_path, "r") as handle:
                return handle.read()
        return None

    def read_job_plist(self):
        with open(self.job_plist, "rb") as handle:
            return plistlib.load(handle)

    def read_calls(self):
        if not os.path.exists(self.launchctl_calls_log):
            return []
        with open(self.launchctl_calls_log) as handle:
            return handle.read().splitlines()

    def test_watchpaths_and_throttle_interval_other_keys_unchanged(self):
        with open(JOB_PLIST_FIXTURE, "rb") as handle:
            original = plistlib.load(handle)

        make_fake_launchctl(self.fake_bin, self.launchctl_calls_log)
        self.run_installer()

        new = self.read_job_plist()
        self.assertEqual(new["WatchPaths"], ["/Library/Managed Installs/ManagedInstallReport.plist"])
        self.assertEqual(new["ThrottleInterval"], 60)
        for key in set(original) | set(new):
            if key in ("WatchPaths", "ThrottleInterval"):
                continue
            self.assertEqual(
                original.get(key), new.get(key), "key %r should equal upstream's" % key
            )

    def test_setting_is_idempotent_regardless_of_prior_state(self):
        # "the result is the same whether the key existed or not" -- start
        # from a file that already has different values for both keys.
        with open(self.job_plist, "rb") as handle:
            plist = plistlib.load(handle)
        plist["WatchPaths"] = ["/some/other/path"]
        plist["ThrottleInterval"] = 5
        with open(self.job_plist, "wb") as handle:
            plistlib.dump(plist, handle)

        make_fake_launchctl(self.fake_bin, self.launchctl_calls_log)
        self.run_installer()

        new = self.read_job_plist()
        self.assertEqual(new["WatchPaths"], ["/Library/Managed Installs/ManagedInstallReport.plist"])
        self.assertEqual(new["ThrottleInterval"], 60)

    def test_calls_are_unload_before_load_after(self):
        make_fake_launchctl(self.fake_bin, self.launchctl_calls_log)
        self.run_installer()

        calls = self.read_calls()
        self.assertEqual(len(calls), 2, "expected exactly one unload and one load: %r" % calls)
        self.assertTrue(calls[0].startswith("bootout system "), calls[0])
        self.assertTrue(calls[1].startswith("bootstrap system "), calls[1])
        self.assertIn(self.job_plist, calls[0])
        self.assertIn(self.job_plist, calls[1])

    def test_second_run_gives_the_same_file(self):
        make_fake_launchctl(self.fake_bin, self.launchctl_calls_log)
        self.run_installer()
        after_first = self.read_job_plist()

        self.run_installer()

        self.assertEqual(self.read_job_plist(), after_first)

    def test_missing_file_creates_and_loads_nothing(self):
        os.remove(self.job_plist)
        make_fake_launchctl(self.fake_bin, self.launchctl_calls_log)

        output = self.run_installer(capture=True)

        self.assertFalse(os.path.exists(self.job_plist), "nothing should have been created")
        self.assertEqual(self.read_calls(), [], "nothing should have been loaded")
        self.assertIn("com.github.reportmate.installs.plist not found", output)

    def test_warning_logged_when_load_fails(self):
        # bootout (the first call) succeeds; bootstrap (the second) fails --
        # a stub that only fails on its second invocation.
        write_executable(
            os.path.join(self.fake_bin, "launchctl"),
            "#!/bin/bash\n"
            'echo "$@" >> "%s"\n'
            'if [ "$1" = "bootstrap" ]; then exit 1; fi\n'
            "exit 0\n" % self.launchctl_calls_log,
        )

        output = self.run_installer(capture=True)

        self.assertIn(
            "WARNING: failed to load com.github.reportmate.installs - "
            "collection scheduled by this daemon will not run",
            output,
        )
        # The edit itself still happened before the failed load attempt.
        new = self.read_job_plist()
        self.assertEqual(new["ThrottleInterval"], 60)


if __name__ == "__main__":
    unittest.main()
