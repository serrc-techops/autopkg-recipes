#!/usr/local/autopkg/python
"""Hand a downloaded Windows installer to the package tool (pcman).

This is the last step of a Windows recipe. It runs

    <python> <root>/bin/pcman import <file> --template <item> [--version <v>]
        --no-prompt --if-new --result-file <file> [--dry-run]

as a list, without a shell, with standard input closed and a time limit. The
package tool decides everything about the program: whether the version is
new, whether it is the same product, and what goes into the repository. This
processor only finds the tool, passes a small environment, and turns the tool's
result file into AutoPkg's outputs.

A dry run is the default: the tool shows its plan and writes nothing. A real
run needs pcman_dry_run set to false, in the recipe's override on the machine
that runs it.

The processor never passes --force, --allow-duplicate, --allow-product-change
or --allow-version-label, and has no input that could.

What is passed on from the tool's output: the lines that begin with ERROR:
(when the run failed) and the lines that begin with WARNING: or NOTE: (when it
did not). The rest is never shown: a dry run prints the text of the pkginfo,
which may hold install arguments.

A dry run and "nothing new" are always shown, also without -v. A dry run also
leaves a summary result, so that a run that wrote nothing because of the
default cannot look like a run that had nothing to do.

When AutoPkg is interrupted (Ctrl-C) or terminated, the tool and its child
processes are killed before the temporary folder is removed.

Exit codes of the tool: 0 published or finished (or a dry run), 3 nothing new
(not an error), anything else stops the recipe.
"""
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile

from autopkglib import Processor, ProcessorError

__all__ = [
    "PcmanImporter",
    "build_command",
    "child_environment",
    "FORBIDDEN_FLAGS",
]

# The exit codes of `pcman import` (the tool's README, "Import from a script").
EXIT_DONE = 0
EXIT_USAGE = 2
EXIT_NOTHING_NEW = 3

# The values of "result" in the tool's result file that this processor accepts.
RESULT_PUBLISHED = "published"
RESULT_FINISHED_EARLIER_PUBLISH = "finished-earlier-publish"
RESULT_DRY_RUN = "dry-run"
RESULT_NOTHING_NEW = "nothing-new"
RESULTS_PUBLISHED = (RESULT_PUBLISHED, RESULT_FINISHED_EARLIER_PUBLISH)
# Every value of "result" that the tool documents. Another value is an error.
RESULTS_DOCUMENTED = (
    RESULT_PUBLISHED,
    RESULT_FINISHED_EARLIER_PUBLISH,
    "imported",
    "imported-and-built",
    "finished-earlier-import",
    RESULT_NOTHING_NEW,
    RESULT_DRY_RUN,
    "error",
)
# What a published result must carry (non-empty text).
PUBLISHED_RESULT_KEYS = ("name", "version", "pkginfo_path", "installer_path")

# Flags that a recipe must never be able to pass to the tool.
FORBIDDEN_FLAGS = (
    "--force",
    "--allow-duplicate",
    "--allow-product-change",
    "--allow-version-label",
)

INSTALLER_EXTENSIONS = (".msi", ".exe")
MSI_EXTENSION = ".msi"
EXE_EXTENSION = ".exe"
# `bin/pcman` of the tool and the Python of the tool's own virtual environment.
TOOL_SCRIPT = os.path.join("bin", "pcman")
DEFAULT_PYTHON = os.path.join(".venv", "bin", "python3")
MSIINFO = "msiinfo"

# The `PATH` that the tool gets. launchd's own `PATH` has no Homebrew, and
# `msiinfo` lives there.
DEFAULT_CHILD_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
# The only other variables the tool gets: HOME, and these when set.
PASSED_VARIABLES = (
    "PCMAN_CIMIAN_REPO",
    "PCMAN_CONFIG",
    "PCMAN_CIMIAN_CATALOGS",
    "PCMAN_STATE_DIR",
)

# The copy of a large installer to a share is the slowest step.
DEFAULT_TIMEOUT_SECONDS = 1800
MIN_TIMEOUT_SECONDS = 60
MAX_TIMEOUT_SECONDS = 4 * 3600
# After a kill, how long to wait for the tool's pipes to close.
REAP_TIMEOUT_SECONDS = 30

# How much of the tool's output is passed on. The longest message that the
# tool prints today is the NOTE for a minor upgrade of an MSI (about 500
# characters, and its advice is at the end); the limit leaves room for
# names and paths in it.
MAX_LINES_PASSED_ON = 10
MAX_LINE_CHARS = 1500
# Always shown, also at the default verbosity of AutoPkg (a level of 1 or more
# is shown only with -v).
ALWAYS_SHOWN = 0
# The result text in the summary of a dry run.
DRY_RUN_SUMMARY_RESULT = "dry run, nothing written"

TRUE_WORDS = ("true", "yes", "1")
FALSE_WORDS = ("false", "no", "0")

ERROR_PREFIX = "ERROR:"
NOTE_PREFIXES = ("WARNING:", "NOTE:")


def parse_bool(value, name):
    """A bool from a recipe value: a plist boolean, or the text that a command
    line or a preference gives. Anything else is an error, never a guess."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        word = value.strip().lower()
        if word in TRUE_WORDS:
            return True
        if word in FALSE_WORDS:
            return False
    raise ProcessorError("%s must be true or false, not %r." % (name, value))


def parse_timeout(value):
    if isinstance(value, bool):
        raise ProcessorError("pcman_timeout must be a number of seconds.")
    try:
        seconds = int(str(value).strip())
    except ValueError:
        raise ProcessorError("pcman_timeout must be a number of seconds, not %r." % (value,))
    if not MIN_TIMEOUT_SECONDS <= seconds <= MAX_TIMEOUT_SECONDS:
        raise ProcessorError(
            "pcman_timeout must be between %d and %d seconds, not %d."
            % (MIN_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS, seconds)
        )
    return seconds


def raw_text(value):
    """An input as text, not stripped; None is an empty text."""
    return "" if value is None else str(value)


def text_or_empty(value):
    """An input as stripped text; None and an empty string are 'not given'."""
    if value is None:
        return ""
    return str(value).strip()


def child_environment(env, environ, path_value):
    """The whole environment of the tool: PATH, HOME, and the PCMAN_ variables
    that the processor was given (input of the lower-case name) or has in its
    own environment. Nothing else is passed on."""
    child = {
        "PATH": path_value,
        "HOME": environ.get("HOME") or os.path.expanduser("~"),
    }
    for name in PASSED_VARIABLES:
        value = text_or_empty(env.get(name.lower())) or text_or_empty(environ.get(name))
        if value:
            child[name] = value
    return child


def build_command(python, root, installer, template, version, result_file, dry_run):
    """The command line as a list. `version` is empty when none is given."""
    command = [
        python,
        os.path.join(root, TOOL_SCRIPT),
        "import",
        installer,
        "--template",
        template,
    ]
    if version:
        command += ["--version", version]
    command += ["--no-prompt", "--if-new", "--result-file", result_file]
    if dry_run:
        command.append("--dry-run")
    return command


# An item name of the package tool: letters, numbers, dots, underscores and
# hyphens, and it does not begin with a hyphen or a dot (it would be read as a
# flag or as a path).
TEMPLATE_PATTERN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")


def check_template(value):
    """The template is an item name, never a path and never a flag."""
    if not value:
        raise ProcessorError("pcman_template is empty.")
    if not TEMPLATE_PATTERN.fullmatch(value):
        raise ProcessorError(
            "pcman_template must be an item name (letters, numbers, dots, "
            "underscores, hyphens; not beginning with '-' or '.'): %r" % value[:40]
        )


def check_version(value):
    """A version label has no white space, no control character, no path
    separator, and does not begin with '-' (the tool would read a flag)."""
    bad = (
        value.startswith("-")
        or "/" in value
        or "\\" in value
        or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value)
    )
    if bad:
        raise ProcessorError(
            "pcman_version must be a version label without white space, "
            "control characters, path separators or a leading '-': %r" % value[:40]
        )


def clip(line):
    line = line.strip()
    if len(line) > MAX_LINE_CHARS:
        line = line[:MAX_LINE_CHARS] + "..."
    return line


def lines_with_prefix(text, prefixes):
    found = []
    for line in text.splitlines():
        if line.startswith(prefixes):
            found.append(clip(line))
        if len(found) >= MAX_LINES_PASSED_ON:
            break
    return found


def end_on_termination(signum, frame):
    """A termination of AutoPkg ends the processor as an exit would, so that
    the tool is stopped and the temporary folder removed."""
    raise SystemExit(128 + signum)


NOT_INSTALLED = object()


def install_termination_handler():
    """Returns what restore_termination_handler needs. Does nothing outside
    the main thread (only the main thread can handle a signal)."""
    try:
        return signal.signal(signal.SIGTERM, end_on_termination)
    except ValueError:
        return NOT_INSTALLED


def restore_termination_handler(previous):
    """A handler that signal.signal reports as None was set from C code and
    cannot be set again: it is left as it is."""
    if previous is not NOT_INSTALLED and previous is not None:
        signal.signal(signal.SIGTERM, previous)


def last_line(text):
    lines = [line for line in text.splitlines() if line.strip()]
    return clip(lines[-1]) if lines else ""


class PcmanImporter(Processor):
    description = __doc__
    input_variables = {
        "pathname": {
            "required": True,
            "description": "Path to the downloaded installer (.msi or .exe).",
        },
        "pcman_template": {
            "required": True,
            "description": "The item name of the program's template in the package tool.",
        },
        "pcman_version": {
            "required": False,
            "description": (
                "The version label. Required for an .exe: numeric parts "
                "separated by dots. Left out for an .msi (the tool takes the "
                "MSI's own ProductVersion). An empty string counts as not given."
            ),
        },
        "pcman_root": {
            "required": True,
            "description": (
                "The folder of the package tool. It comes from an AutoPkg "
                "preference or an override, never from a recipe."
            ),
        },
        "pcman_python": {
            "required": False,
            "description": "Python of the tool. Default: <pcman_root>/.venv/bin/python3.",
        },
        "pcman_dry_run": {
            "required": False,
            "default": True,
            "description": (
                "True (the default): the tool shows its plan and writes "
                "nothing. A real run needs the explicit value false."
            ),
        },
        "pcman_timeout": {
            "required": False,
            "default": DEFAULT_TIMEOUT_SECONDS,
            "description": (
                "Seconds to wait for the tool (%d to %d)."
                % (MIN_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS)
            ),
        },
        "pcman_path": {
            "required": False,
            "default": DEFAULT_CHILD_PATH,
            "description": "The PATH that the tool gets; msiinfo is looked for here.",
        },
        "pcman_cimian_repo": {
            "required": False,
            "description": "Passed to the tool as PCMAN_CIMIAN_REPO (a preference).",
        },
        "pcman_config": {
            "required": False,
            "description": "Passed to the tool as PCMAN_CONFIG.",
        },
        "pcman_cimian_catalogs": {
            "required": False,
            "description": "Passed to the tool as PCMAN_CIMIAN_CATALOGS.",
        },
        "pcman_state_dir": {
            "required": False,
            "description": "Passed to the tool as PCMAN_STATE_DIR.",
        },
    }
    output_variables = {
        "pcman_result": {
            "description": "The tool's result: published, finished-earlier-publish, dry-run or nothing-new.",
        },
        "pcman_name": {"description": "The item name that the tool used."},
        "pcman_version_published": {
            "description": "The version label of the result (the planned one after a dry run).",
        },
        "pcman_pkginfo_path": {"description": "The pkginfo in the repository (planned after a dry run)."},
        "pcman_installer_path": {"description": "The installer in the repository (planned after a dry run)."},
        "pcman_repo_changed": {
            "description": "True only when the tool wrote to the repository in this run.",
        },
        "pcman_importer_summary_result": {
            "description": (
                "Summary for AutoPkg's report: a published version, or a dry "
                "run (result 'dry run, nothing written'). No paths."
            ),
        },
    }

    # ---- checks before the call ----

    def read_inputs(self):
        """Check every input and return what the call needs."""
        installer = text_or_empty(self.env.get("pathname"))
        if not installer:
            raise ProcessorError("pathname is empty.")
        installer = os.path.abspath(installer)
        extension = os.path.splitext(installer)[1].lower()
        if extension not in INSTALLER_EXTENSIONS:
            raise ProcessorError(
                "The installer must end in .msi or .exe: %s" % os.path.basename(installer)
            )
        if not os.path.isfile(installer):
            raise ProcessorError("The installer does not exist: %s" % installer)

        template = raw_text(self.env.get("pcman_template"))
        check_template(template)

        version = raw_text(self.env.get("pcman_version"))
        if version.strip():
            check_version(version)
        else:
            version = ""
        if not version and extension == EXE_EXTENSION:
            raise ProcessorError(
                "An .exe needs pcman_version: the tool never takes a version "
                "from the file."
            )

        root_text = text_or_empty(self.env.get("pcman_root"))
        if not root_text:
            raise ProcessorError(
                "pcman_root is not set. Set it as an AutoPkg preference or in "
                "the override. It is never in a recipe."
            )
        root = os.path.abspath(os.path.expanduser(root_text))
        if not os.path.isdir(root):
            raise ProcessorError("pcman_root is not a folder: %s" % root)
        script = os.path.join(root, TOOL_SCRIPT)
        if not os.path.isfile(script):
            raise ProcessorError("The package tool is not in pcman_root: %s is missing." % script)

        python_text = text_or_empty(self.env.get("pcman_python"))
        python = (
            os.path.abspath(os.path.expanduser(python_text))
            if python_text
            else os.path.join(root, DEFAULT_PYTHON)
        )
        if not os.path.isfile(python):
            raise ProcessorError("The Python of the package tool does not exist: %s" % python)
        if not os.access(python, os.X_OK):
            raise ProcessorError(
                "The Python of the package tool exists but cannot be executed: %s" % python
            )

        dry_run = parse_bool(self.env.get("pcman_dry_run", True), "pcman_dry_run")
        timeout = parse_timeout(self.env.get("pcman_timeout", DEFAULT_TIMEOUT_SECONDS))
        path_value = text_or_empty(self.env.get("pcman_path")) or DEFAULT_CHILD_PATH

        if extension == MSI_EXTENSION and shutil.which(MSIINFO, path=path_value) is None:
            raise ProcessorError(
                "msiinfo is not on the PATH that the package tool gets (%s). "
                "Install msitools, or set pcman_path." % path_value
            )

        return {
            "installer": installer,
            "template": template,
            "version": version,
            "root": root,
            "python": python,
            "dry_run": dry_run,
            "timeout": timeout,
            "path": path_value,
        }

    # ---- the call ----

    @staticmethod
    def stop_tool(proc):
        """Kill the tool and all of its child processes (its process group),
        then collect it."""
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass
        try:
            proc.communicate(timeout=REAP_TIMEOUT_SECONDS)
        except (subprocess.TimeoutExpired, ValueError, OSError):
            pass

    def run_tool(self, command, child_env, timeout):
        """Run the tool: no shell, standard input closed, a time limit. On a
        time-out, on Ctrl-C and on a termination of this process, the tool's
        whole process group is killed before the caller goes on (and removes
        its temporary folder). Returns (exit code, stdout text, stderr text)."""
        previous = install_termination_handler()
        proc = None
        try:
            try:
                proc = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=child_env,
                    start_new_session=True,
                )
            except OSError as err:
                raise ProcessorError("The package tool could not be started: %s" % err)
            try:
                out, err = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.stop_tool(proc)
                raise ProcessorError(
                    "The package tool did not finish in %d seconds and was stopped. "
                    "Check whether the repository share is reachable." % timeout
                )
        except BaseException:
            if proc is not None and proc.poll() is None:
                self.stop_tool(proc)
            raise
        finally:
            restore_termination_handler(previous)
        return (
            proc.returncode,
            out.decode("utf-8", errors="replace"),
            err.decode("utf-8", errors="replace"),
        )

    @staticmethod
    def read_result_file(path):
        """The tool's result file as a dict, or None when it is missing or
        cannot be read."""
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or not isinstance(data.get("result"), str):
            return None
        return data

    # ---- after the call ----

    def fail(self, code, out, err, result):
        """Raise the error for an exit code that is not 0 or 3."""
        lines = lines_with_prefix(err, (ERROR_PREFIX,)) or lines_with_prefix(out, (ERROR_PREFIX,))
        if not lines and result and result.get("message"):
            lines = [clip(str(result["message"]))]
        if not lines:
            lines = [last_line(err) or "The tool printed no error line."]
        if code == EXIT_USAGE:
            reason = (
                "The package tool could not read its command line, or cannot "
                "write its result file: a mistake in the recipe or the setup."
            )
        elif code == 1:
            reason = "The package tool stopped with an error."
        else:
            reason = "The package tool ended with the unexpected exit code %s." % code
        raise ProcessorError("%s %s" % (reason, " ".join(lines)))

    def main(self):
        settings = self.read_inputs()
        child_env = child_environment(self.env, os.environ, settings["path"])

        tmp_dir = tempfile.mkdtemp(prefix="pcman-importer-")
        try:
            result_file = os.path.join(tmp_dir, "result.json")
            command = build_command(
                settings["python"],
                settings["root"],
                settings["installer"],
                settings["template"],
                settings["version"],
                result_file,
                settings["dry_run"],
            )
            self.output(
                "Running pcman import for %s as %s%s."
                % (
                    os.path.basename(settings["installer"]),
                    settings["template"],
                    " (dry run)" if settings["dry_run"] else "",
                )
            )
            code, out, err = self.run_tool(command, child_env, settings["timeout"])
            result = self.read_result_file(result_file)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        if code not in (EXIT_DONE, EXIT_NOTHING_NEW):
            self.fail(code, out, err, result)
        if result is None:
            raise ProcessorError(
                "The package tool ended with exit code %d but left no readable "
                "result file. Nothing can be trusted: look at the repository by hand."
                % code
            )
        self.finish(code, settings, result, out, err)

    def finish(self, code, settings, result, out, err):
        """Exit code 0 or 3 with a readable result file: check it, set the
        outputs, say what happened."""
        kind = result["result"]
        if kind not in RESULTS_DOCUMENTED:
            raise ProcessorError(
                "The package tool's result %r is not one that it documents." % kind[:40]
            )
        if code == EXIT_NOTHING_NEW:
            if kind != RESULT_NOTHING_NEW:
                raise ProcessorError(
                    "The package tool ended with exit code 3 but its result is %r." % kind
                )
            repo_changed = False
        else:
            if settings["dry_run"] and kind != RESULT_DRY_RUN:
                raise ProcessorError(
                    "A dry run was asked for, but the tool's result is %r." % kind
                )
            if not settings["dry_run"] and kind not in RESULTS_PUBLISHED:
                raise ProcessorError(
                    "A real run ended with exit code 0 but the tool's result is %r." % kind
                )
            repo_changed = kind in RESULTS_PUBLISHED
        if repo_changed:
            for key in PUBLISHED_RESULT_KEYS:
                value = result.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise ProcessorError(
                        "The package tool says %s but its result file has no %s."
                        % (kind, key)
                    )

        def field(key):
            value = result.get(key)
            return "" if value is None else str(value)

        self.env["pcman_result"] = kind
        self.env["pcman_name"] = field("name")
        self.env["pcman_version_published"] = field("version")
        self.env["pcman_pkginfo_path"] = field("pkginfo_path")
        self.env["pcman_installer_path"] = field("installer_path")
        self.env["pcman_repo_changed"] = repo_changed

        for line in lines_with_prefix(out, NOTE_PREFIXES) + lines_with_prefix(err, NOTE_PREFIXES):
            self.output(line, verbose_level=ALWAYS_SHOWN)

        if kind == RESULT_NOTHING_NEW:
            self.output(
                "Nothing new: %s %s is in the repository already. Nothing was written."
                % (field("name"), field("version")),
                verbose_level=ALWAYS_SHOWN,
            )
            return

        catalogs = result.get("catalogs")
        data = {
            "name": field("name"),
            "version": field("version"),
            "catalogs": ", ".join(str(c) for c in catalogs) if isinstance(catalogs, list) else "",
        }
        if kind == RESULT_DRY_RUN:
            self.output(
                "WARNING: DRY RUN. Nothing was written, because pcman_dry_run is on. "
                "Set pcman_dry_run to false in the override for a real run.",
                verbose_level=ALWAYS_SHOWN,
            )
            data["result"] = DRY_RUN_SUMMARY_RESULT
            summary_text = "Dry run: the package tool wrote nothing (pcman_dry_run is on):"
        else:
            self.output(
                "Published %s %s." % (field("name"), field("version")),
                verbose_level=ALWAYS_SHOWN,
            )
            data["result"] = kind
            summary_text = "The following versions were published by the package tool:"
        # No path of the repository in the summary: reports are mailed. The
        # paths are the outputs pcman_pkginfo_path and pcman_installer_path.
        self.env["pcman_importer_summary_result"] = {
            "summary_text": summary_text,
            "report_fields": ["name", "version", "catalogs", "result"],
            "data": data,
        }


if __name__ == "__main__":
    processor = PcmanImporter()
    processor.execute_shell()
