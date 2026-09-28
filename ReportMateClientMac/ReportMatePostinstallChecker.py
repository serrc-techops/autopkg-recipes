#!/usr/local/autopkg/python
"""Refuse to import a ReportMate package that is not the patched build.

First step of ReportMateClientMac.munki.recipe. Expands the package that is
about to be imported (pkg_path) into a temporary directory with pkgutil --
a signed package expands the same way an unsigned one does -- and inspects
its Scripts/postinstall: only a package built by
ReportMateClientMac.pkg.recipe, carrying ReportMatePostinstallPatcher.py's
marker with every upstream behaviour it always replaces still absent --
the unconditional "Backing up existing postflight"; the postflight wrapper
and postflight.d/reportmate.sh here-documents, since this build starts the
installs collection through launchd and writes neither; and the osquery
download/install -- may be imported. Otherwise the recipe stops before
MunkiImporter runs.

check_postinstall_text() is a plain function so the check itself can be
unit tested without AutoPkg or pkgutil; see tests/test_checker.py.
"""
import os
import shutil
import subprocess
import tempfile

from autopkglib import Processor, ProcessorError

# Kept in sync with ReportMatePostinstallPatcher.py by tests/test_checker.py,
# which imports both and compares the constants directly.
MARKER = (
    "# serrc-techops custom build: ReportMateClientMac postflight "
    "integration rule 3, osquery-not-installed rule 1"
)
FORBIDDEN_BACKUP_TEXT = "Backing up existing postflight"
FORBIDDEN_WRAPPER_HEREDOC = "<< 'WRAPPER_EOF'"
FORBIDDEN_REPORTMATE_HEREDOC = "<< 'REPORTMATE_EOF'"
FORBIDDEN_OSQUERY_URL = "github.com/osquery/osquery/releases"
FORBIDDEN_INSTALLER_CALL = "/usr/sbin/installer"

__all__ = ["ReportMatePostinstallChecker", "check_postinstall_text"]


def check_postinstall_text(text):
    """Raise ValueError with a clear reason when `text` -- the content of an
    about-to-be-imported package's Scripts/postinstall -- is not the custom
    build's. Returns None (no exception) when it is."""
    if MARKER not in text:
        raise ValueError(
            "Scripts/postinstall does not carry the custom-build marker "
            "(%r); this is upstream's package, not the patched build." % MARKER
        )
    if FORBIDDEN_BACKUP_TEXT in text:
        raise ValueError(
            "Scripts/postinstall still contains %r; this is upstream's "
            "unpatched Munki postflight integration." % FORBIDDEN_BACKUP_TEXT
        )
    if FORBIDDEN_WRAPPER_HEREDOC in text or FORBIDDEN_REPORTMATE_HEREDOC in text:
        raise ValueError(
            "Scripts/postinstall still opens %r or %r; this build starts "
            "the installs collection through launchd and must write "
            "neither the postflight wrapper nor postflight.d/reportmate.sh."
            % (FORBIDDEN_WRAPPER_HEREDOC, FORBIDDEN_REPORTMATE_HEREDOC)
        )
    if FORBIDDEN_OSQUERY_URL in text or FORBIDDEN_INSTALLER_CALL in text:
        raise ValueError(
            "Scripts/postinstall still contains %r or a call of %r; this "
            "is upstream's unpatched osquery download/install -- osquery "
            "must be provided by Munki, never installed by this package."
            % (FORBIDDEN_OSQUERY_URL, FORBIDDEN_INSTALLER_CALL)
        )


class ReportMatePostinstallChecker(Processor):
    description = __doc__
    input_variables = {
        "pkg_path": {
            "required": True,
            "description": "Path to the package about to be imported.",
        },
    }
    output_variables = {
        "reportmate_postinstall_checked": {
            "description": "True once the custom-build check has passed.",
        },
    }

    def expand_and_read_postinstall(self, pkg_path):
        """Expand `pkg_path` with pkgutil into a temporary directory and
        return the text of its Scripts/postinstall. The temporary directory
        is always removed before returning."""
        tmp_dir = tempfile.mkdtemp(prefix="reportmate-postinstall-check-")
        try:
            expand_dir = os.path.join(tmp_dir, "expanded")
            try:
                proc = subprocess.run(
                    ["/usr/sbin/pkgutil", "--expand", pkg_path, expand_dir],
                    capture_output=True,
                    text=True,
                )
            except OSError as err:
                raise ProcessorError("Could not run pkgutil --expand: %s" % err)
            if proc.returncode != 0:
                raise ProcessorError(
                    "pkgutil --expand of %s failed: %s"
                    % (pkg_path, proc.stderr.strip())
                )

            postinstall_path = os.path.join(expand_dir, "Scripts", "postinstall")
            try:
                with open(postinstall_path, "r") as handle:
                    return handle.read()
            except OSError as err:
                raise ProcessorError(
                    "Could not read %s from the expanded package: %s"
                    % (postinstall_path, err)
                )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def main(self):
        pkg_path = self.env["pkg_path"]
        text = self.expand_and_read_postinstall(pkg_path)

        try:
            check_postinstall_text(text)
        except ValueError as err:
            raise ProcessorError(
                "Refusing to import %s: %s" % (pkg_path, err)
            )

        self.env["reportmate_postinstall_checked"] = True
        self.output("Confirmed custom build: %s" % pkg_path)


if __name__ == "__main__":
    processor = ReportMatePostinstallChecker()
    processor.execute_shell()
