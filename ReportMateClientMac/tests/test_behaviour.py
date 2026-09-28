"""Behavioural tests for the replacement Munki-postflight-integration block.

Each scenario builds real on-disk state in a fresh temporary directory,
with every path the installer or postflight touches rewritten into that
directory (MUNKI_DIR, and the log directory both the wrapper and
reportmate.sh use). The installer's Munki section -- either the original,
unpatched one or ReportMatePostinstallPatcher's replacement -- is then run
for real as a standalone script (log_message() is the only thing it
depends on from the rest of postinstall, so that is stubbed in), and one
simulated Munki postflight run (`postflight auto`, what launchd invokes
after managedsoftwareupdate) is run afterward under a short time limit.

Nothing here ever runs under /usr/local, /Library or /Applications; nothing
is installed. Every subprocess is started in its own process group
(start_new_session=True) and that whole group is killed in a `finally`
whether the process finished, failed, or timed out -- see
run_in_own_group() -- so scenario 7's intentionally non-terminating control
case cannot leave anything running. tearDownModule() sweeps any process
group a test did not get to clean up itself, as a last resort.

Zentral's real Munki postflight runner is used (fixtures/
zentral_postflight_runner.py; only its interpreter line and POSTFLIGHT_DIR
constant are rewritten -- see that file's own header). The per-run script
it runs from postflight.d/ ("zentral", analogous to Zentral's own
zentral_postflight) and every other stand-in script used to populate
postflight.d/ in these scenarios are original to this test suite: each
just appends "<name> ran" to a shared runs.log, which is how "every script
in postflight.d/ ran exactly once" is checked for scenarios where nothing
upstream (like reportmate.sh) already logs distinctively. reportmate.sh is
real, unmodified in substance (only /usr/local/munki and the log directory
are rewritten, the same as for the wrapper), and its own real log line
("Munki run finished (runtype:") is used to count its invocations instead.
"""
import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from collections import Counter

from _support import patcher, read_fixture

FIXTURE = read_fixture("postinstall_fixture.sh")

NORMAL_TIMEOUT = 8.0   # generous upper bound; these should return almost instantly
CONTROL_TIMEOUT = 2.0  # scenario 7 is *expected* to still be running at this point
INSTALLER_TIMEOUT = 10.0  # the installer step itself never loops; a hang here is a bug


def _section(text, heading, end_log, name):
    start, end = patcher.find_section(text, heading, end_log, name)
    return "\n".join(text.splitlines()[start : end + 1])


ORIGINAL_MUNKI_SECTION = _section(
    FIXTURE, patcher.MUNKI_HEADING, patcher.MUNKI_END_LOG, patcher.MUNKI_SECTION_NAME
)
PATCHED_FIXTURE = patcher.patch_postinstall(FIXTURE)
PATCHED_MUNKI_SECTION = _section(
    PATCHED_FIXTURE, patcher.MUNKI_HEADING, patcher.MUNKI_END_LOG, patcher.MUNKI_SECTION_NAME
)
ORIGINAL_WRAPPER_BODY = patcher.extract_heredoc(ORIGINAL_MUNKI_SECTION, "WRAPPER_EOF")


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


def run_in_own_group(argv, timeout, stdout_path=None):
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
# Scenario construction helpers.
# --------------------------------------------------------------------------

def write_executable(path, text):
    with open(path, "w") as handle:
        handle.write(text)
    os.chmod(path, 0o755)


def make_recorder_script(name, runs_log_path):
    """A trivial, original-to-this-suite stand-in for a postflight.d/ entry
    (or, for scenario 4, for $POSTFLIGHT itself): it only records that it
    ran, once, into the shared runs.log."""
    return '#!/bin/sh\necho "%s ran" >> "%s"\n' % (name, runs_log_path)


def rewrite_paths(text, munki_dir, log_dir):
    text = text.replace("/usr/local/munki", munki_dir)
    text = text.replace("/Library/Managed Reports/logs", log_dir)
    return text


class BehaviourTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="reportmate-behaviour-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.munki_dir = os.path.join(self.root, "munki")
        self.log_dir = os.path.join(self.root, "logs")
        self.runs_log = os.path.join(self.root, "runs.log")
        self.zentral_runtime = os.path.join(self.root, "zentral-runtime")
        self._installer_count = 0

    # -- installer / postflight execution -------------------------------

    def run_installer(self, section_text, timeout=INSTALLER_TIMEOUT, capture=False):
        """Run an installer's Munki section for real, as a standalone
        script (log_message() stubbed, paths rewritten into this test's
        temporary directory). Returns the captured stdout+stderr text when
        `capture` is true, else None. Asserts the installer step itself
        completed -- it should never loop; only the postflight it installs
        might (that is what run_postflight()/scenario 7 checks)."""
        self._installer_count += 1
        script_path = os.path.join(self.root, "installer-%d.sh" % self._installer_count)
        body = rewrite_paths(section_text, self.munki_dir, self.log_dir)
        write_executable(
            script_path,
            '#!/bin/bash\nlog_message() { echo "[installer] $1"; }\n' + body + "\n",
        )
        capture_path = os.path.join(self.root, "installer-%d.out" % self._installer_count) if capture else None
        ended, returncode = run_in_own_group(
            ["/bin/bash", script_path], timeout=timeout, stdout_path=capture_path
        )
        self.assertTrue(ended, "the installer step itself did not end within %ss (it never loops -- this is a harness bug, not the bug under test)" % timeout)
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

    # -- shared scenario-1-shaped setup ("Zentral already correctly in place") --

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

    # -- assertions on the shared runs.log and reportmate.sh's own log --

    def run_count(self, name):
        if not os.path.exists(self.runs_log):
            return 0
        with open(self.runs_log) as handle:
            lines = handle.read().splitlines()
        return Counter(lines)["%s ran" % name]

    def reportmate_ran_count(self):
        log_path = os.path.join(self.log_dir, "reportmate-postflight.log")
        if not os.path.exists(log_path):
            return 0
        with open(log_path) as handle:
            content = handle.read()
        # reportmate.sh's own, real, unmodified log line -- distinct from
        # anything the wrapper or Zentral's runner logs, so counting it
        # tells us how many times reportmate.sh itself ran, regardless of
        # which runner invoked it.
        return content.count("Munki run finished (runtype:")


# --------------------------------------------------------------------------
# Scenario 1: Zentral's runner already correctly in place.
# --------------------------------------------------------------------------

class Scenario1ZentralRunnerAlreadyInPlace(BehaviourTestCase):
    def test_postflight_unchanged_reportmate_added_and_both_run_once(self):
        runner_path = self.make_zentral_layout()
        postflight_path = os.path.join(self.munki_dir, "postflight")
        target_before = os.path.realpath(postflight_path)
        self.assertEqual(target_before, os.path.realpath(runner_path))

        self.run_installer(PATCHED_MUNKI_SECTION)

        # postflight is still the very same link.
        self.assertTrue(os.path.islink(postflight_path))
        self.assertEqual(os.path.realpath(postflight_path), target_before)

        reportmate_sh = os.path.join(self.munki_dir, "postflight.d", "reportmate.sh")
        self.assertTrue(os.path.isfile(reportmate_sh))
        self.assertTrue(os.access(reportmate_sh, os.X_OK))

        ended, returncode = self.run_postflight()
        self.assertTrue(ended, "simulated postflight did not end within the time limit")
        self.assertEqual(returncode, 0)
        self.assertEqual(self.run_count("zentral"), 1)
        self.assertEqual(self.reportmate_ran_count(), 1)


# --------------------------------------------------------------------------
# Scenario 2: the damaged state upstream's unpatched installer leaves,
# repaired to scenario 1's state.
# --------------------------------------------------------------------------

class Scenario2RepairsDamagedState(BehaviourTestCase):
    def test_repaired_to_scenario_1_state(self):
        runner_path = self.make_zentral_layout()
        postflight_path = os.path.join(self.munki_dir, "postflight")
        postflight_d = os.path.join(self.munki_dir, "postflight.d")
        original_target = os.path.realpath(postflight_path)

        # Damage it exactly the way upstream's unpatched installer does.
        self.run_installer(ORIGINAL_MUNKI_SECTION)
        sal_sh = os.path.join(postflight_d, "sal.sh")
        self.assertTrue(os.path.lexists(sal_sh), "expected upstream to move the runner to postflight.d/sal.sh")
        self.assertEqual(os.path.realpath(sal_sh), original_target)
        with open(postflight_path) as handle:
            self.assertIn("Deployed by: ReportMate macOS Client", handle.read())

        # Now run the patched installer on top of that damage: repair.
        self.run_installer(PATCHED_MUNKI_SECTION)

        self.assertFalse(os.path.lexists(sal_sh), "sal.sh should have been moved back")
        self.assertTrue(os.path.islink(postflight_path))
        self.assertEqual(os.path.realpath(postflight_path), original_target)
        self.assertEqual(os.path.realpath(postflight_path), os.path.realpath(runner_path))

        reportmate_sh = os.path.join(postflight_d, "reportmate.sh")
        self.assertTrue(os.path.isfile(reportmate_sh))

        # postflight.d/ is back to exactly scenario 1's contents.
        self.assertEqual(sorted(os.listdir(postflight_d)), ["reportmate.sh", "zentral"])

        ended, returncode = self.run_postflight()
        self.assertTrue(ended, "simulated postflight did not end within the time limit")
        self.assertEqual(returncode, 0)
        self.assertEqual(self.run_count("zentral"), 1)
        self.assertEqual(self.reportmate_ran_count(), 1)


# --------------------------------------------------------------------------
# Scenario 3: no postflight at all.
# --------------------------------------------------------------------------

class Scenario3NoPostflight(BehaviourTestCase):
    def test_wrapper_installed(self):
        os.makedirs(self.munki_dir, exist_ok=True)
        postflight_path = os.path.join(self.munki_dir, "postflight")
        self.assertFalse(os.path.lexists(postflight_path))

        self.run_installer(PATCHED_MUNKI_SECTION)

        self.assertTrue(os.path.isfile(postflight_path))
        self.assertFalse(os.path.islink(postflight_path))
        with open(postflight_path) as handle:
            content = handle.read()
        self.assertIn("Deployed by: ReportMate macOS Client", content)
        self.assertTrue(os.access(postflight_path, os.X_OK))

        reportmate_sh = os.path.join(self.munki_dir, "postflight.d", "reportmate.sh")
        self.assertTrue(os.path.isfile(reportmate_sh))

        ended, returncode = self.run_postflight()
        self.assertTrue(ended)
        self.assertEqual(returncode, 0)
        self.assertEqual(self.reportmate_ran_count(), 1)


# --------------------------------------------------------------------------
# Added on review: a dangling link at $POSTFLIGHT (a link whose target does
# not exist). "Missing" means neither a file nor a link is present -- a
# dangling link is something else already in place, not missing. The
# installer must leave it exactly as it is: "cat > $POSTFLIGHT" on a
# dangling link writes through it and creates a file at the target, which
# is a different path entirely (and, on a real Mac, could be a path this
# build has no business creating).
# --------------------------------------------------------------------------

class ScenarioDanglingPostflightLink(BehaviourTestCase):
    def test_dangling_link_left_alone_nothing_created_at_its_target(self):
        os.makedirs(self.munki_dir, exist_ok=True)
        postflight_path = os.path.join(self.munki_dir, "postflight")
        missing_target = os.path.join(self.root, "postflight-not-installed-yet")
        self.assertFalse(os.path.lexists(missing_target))
        os.symlink(missing_target, postflight_path)

        installer_output = self.run_installer(PATCHED_MUNKI_SECTION, capture=True)

        # The link itself is untouched: still a link, still pointing at the
        # same, still-nonexistent target.
        self.assertTrue(os.path.islink(postflight_path))
        self.assertEqual(os.readlink(postflight_path), missing_target)
        self.assertFalse(
            os.path.lexists(missing_target),
            "nothing should have been created at the dangling link's target",
        )
        self.assertIn("link whose target does not exist", installer_output)

        # Writing postflight.d/reportmate.sh is unconditional either way.
        reportmate_sh = os.path.join(self.munki_dir, "postflight.d", "reportmate.sh")
        self.assertTrue(os.path.isfile(reportmate_sh))


# --------------------------------------------------------------------------
# Scenario 4: an unrelated, plain reporting script sits at $POSTFLIGHT.
# --------------------------------------------------------------------------

class Scenario4PlainReportingScript(BehaviourTestCase):
    def test_untouched_byte_for_byte_and_not_a_runner_log_line_printed(self):
        os.makedirs(self.munki_dir, exist_ok=True)
        postflight_path = os.path.join(self.munki_dir, "postflight")
        original_text = make_recorder_script("legacy-postflight", self.runs_log)
        write_executable(postflight_path, original_text)
        before = os.stat(postflight_path)

        installer_output = self.run_installer(PATCHED_MUNKI_SECTION, capture=True)

        with open(postflight_path) as handle:
            after_text = handle.read()
        self.assertEqual(original_text, after_text, "postflight must be untouched, byte for byte")
        after = os.stat(postflight_path)
        self.assertEqual(before.st_mode, after.st_mode)

        self.assertIn(
            "installs collection will not start after a Munki run until a "
            "runner of postflight.d is in place",
            installer_output,
        )

        # reportmate.sh is still written into postflight.d/ regardless
        # (that step is unconditional) -- it simply never gets invoked,
        # because the existing postflight does not run postflight.d/ at all.
        reportmate_sh = os.path.join(self.munki_dir, "postflight.d", "reportmate.sh")
        self.assertTrue(os.path.isfile(reportmate_sh))

        ended, returncode = self.run_postflight()
        self.assertTrue(ended)
        self.assertEqual(returncode, 0)
        self.assertEqual(self.run_count("legacy-postflight"), 1)
        self.assertEqual(self.reportmate_ran_count(), 0)


# --------------------------------------------------------------------------
# Scenario 5: ReportMate's wrapper already in place, with a plain script.
# --------------------------------------------------------------------------

class Scenario5WrapperWithPlainScript(BehaviourTestCase):
    def test_wrapper_rewritten_script_stays(self):
        os.makedirs(self.munki_dir, exist_ok=True)
        postflight_d = os.path.join(self.munki_dir, "postflight.d")
        os.makedirs(postflight_d, exist_ok=True)

        postflight_path = os.path.join(self.munki_dir, "postflight")
        wrapper_text = rewrite_paths(ORIGINAL_WRAPPER_BODY, self.munki_dir, self.log_dir)
        write_executable(postflight_path, wrapper_text)

        other_path = os.path.join(postflight_d, "10-other.sh")
        other_text = make_recorder_script("10-other.sh", self.runs_log)
        write_executable(other_path, other_text)

        self.run_installer(PATCHED_MUNKI_SECTION)

        with open(postflight_path) as handle:
            new_wrapper_text = handle.read()
        self.assertIn("Deployed by: ReportMate macOS Client", new_wrapper_text)
        self.assertTrue(os.access(postflight_path, os.X_OK))

        with open(other_path) as handle:
            self.assertEqual(other_text, handle.read(), "the pre-existing script must stay untouched")

        reportmate_sh = os.path.join(postflight_d, "reportmate.sh")
        self.assertTrue(os.path.isfile(reportmate_sh))

        ended, returncode = self.run_postflight()
        self.assertTrue(ended)
        self.assertEqual(returncode, 0)
        self.assertEqual(self.run_count("10-other.sh"), 1)
        self.assertEqual(self.reportmate_ran_count(), 1)


# --------------------------------------------------------------------------
# Scenario 6: the patched installer run twice on scenario 1's state.
# --------------------------------------------------------------------------

class Scenario6RunTwiceIsIdempotent(BehaviourTestCase):
    def test_same_result_when_run_twice(self):
        runner_path = self.make_zentral_layout()
        postflight_path = os.path.join(self.munki_dir, "postflight")
        postflight_d = os.path.join(self.munki_dir, "postflight.d")
        reportmate_sh = os.path.join(postflight_d, "reportmate.sh")

        self.run_installer(PATCHED_MUNKI_SECTION)
        target_after_first = os.path.realpath(postflight_path)
        with open(reportmate_sh) as handle:
            content_after_first = handle.read()
        listing_after_first = sorted(os.listdir(postflight_d))

        self.run_installer(PATCHED_MUNKI_SECTION)  # again, same inputs

        self.assertEqual(os.path.realpath(postflight_path), target_after_first)
        self.assertEqual(os.path.realpath(postflight_path), os.path.realpath(runner_path))
        with open(reportmate_sh) as handle:
            content_after_second = handle.read()
        self.assertEqual(content_after_first, content_after_second)
        self.assertEqual(sorted(os.listdir(postflight_d)), listing_after_first)

        ended, returncode = self.run_postflight()
        self.assertTrue(ended)
        self.assertEqual(returncode, 0)
        self.assertEqual(self.run_count("zentral"), 1)
        self.assertEqual(self.reportmate_ran_count(), 1)


# --------------------------------------------------------------------------
# Scenario 7: control. Upstream's unpatched section, run against scenario
# 1's initial state, must NOT end within the time limit -- this is the bug
# this whole build exists to fix, reproduced to prove the test rig (and the
# fix in the other scenarios) is real.
# --------------------------------------------------------------------------

class Scenario7ControlUnpatchedHangs(BehaviourTestCase):
    def test_unpatched_section_does_not_end_within_the_time_limit(self):
        self.make_zentral_layout()
        # Upstream's own (unpatched) installer, run once: this is exactly
        # what a site running the *unpatched* upstream package would have.
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


if __name__ == "__main__":
    unittest.main()
