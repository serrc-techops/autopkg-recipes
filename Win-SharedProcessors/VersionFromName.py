#!/usr/local/autopkg/python
"""Read a version label from the NAME of a downloaded file, and check its shape.

Some installers carry no version of their own (their file has no version
resource, so WindowsExeVersion stops), but the name that the vendor gave the
file has one, for example `setup-3.10.0.exe`. An importer needs a label for
such an .exe. This processor takes it from the name: it matches a regular
expression from the start of the file's name (like the asset_regex of
GitHubReleasesInfoProvider, which a recipe may even share) with exactly one
capturing group, and the text of that group is the label.

The label is checked for its shape before it is set: two to four numbers
joined by dots, each of at most nine digits, and at least one digit that is
not zero. A build date such as 20260128215914 is not a part of a version, and
the group of a wrong pattern would take it for one; the check stops that. A
label is never repaired (leading zeros stay), never guessed and never read
from the folder part of the path.

The label proves nothing about the file: a file name is chosen by whoever
published the file. It only gives the label that the importer and the client
compare. It does not replace a check of the download.

The recipe stops (ProcessorError) when the pathname has no file name, when the
pattern is not a regular expression or does not have exactly one group, when
the name does not match, when the group did not take part in the match, or
when its text does not have the shape above.
"""
import os
import re

from autopkglib import Processor, ProcessorError

__all__ = ["VersionFromName", "label_from_name", "check_label_shape"]

# Two to four numbers joined by dots. A part of ten or more digits is a build
# date or an identifier, not a version part.
MIN_PARTS = 2
MAX_PARTS = 4
MAX_PART_DIGITS = 9
LABEL_PATTERN = re.compile(
    r"[0-9]{1,%d}(?:\.[0-9]{1,%d}){%d,%d}"
    % (MAX_PART_DIGITS, MAX_PART_DIGITS, MIN_PARTS - 1, MAX_PARTS - 1)
)
NONZERO_DIGIT_PATTERN = re.compile(r"[1-9]")
# A value of the name or of the pattern is cut to this many characters in a message.
MAX_SHOWN_CHARACTERS = 80


def shown(text):
    """A value of a name or a pattern, cut for a message."""
    if len(text) <= MAX_SHOWN_CHARACTERS:
        return text
    return text[:MAX_SHOWN_CHARACTERS] + "..."


def check_label_shape(text):
    """Return `text` when it has the shape of a label, else raise ValueError
    with a reason that is safe to show. ASCII digits only: `str.isdigit`, and a
    regular expression class for "digits", would take other scripts' digits."""
    if not LABEL_PATTERN.fullmatch(text):
        raise ValueError(
            "%r is not a version label: it must be %d to %d numbers of at most %d digits, joined by dots"
            % (shown(text), MIN_PARTS, MAX_PARTS, MAX_PART_DIGITS)
        )
    if not NONZERO_DIGIT_PATTERN.search(text):
        raise ValueError("%r is made of zeros, and zeros are not a version" % shown(text))
    return text


def label_from_name(name, pattern):
    """Return the label that `pattern` finds in the file name `name`. Raises
    ValueError with a reason that is safe to show."""
    try:
        compiled = re.compile(pattern)
    except re.error as err:
        raise ValueError("version_pattern is not a regular expression: %s" % err)
    if compiled.groups != 1:
        raise ValueError(
            "version_pattern must have exactly one group, the label (it has %d): %s"
            % (compiled.groups, shown(pattern))
        )
    found = compiled.match(name)
    if found is None:
        raise ValueError("the file name does not match version_pattern %s" % shown(pattern))
    text = found.group(1)
    if text is None:
        raise ValueError("the group of version_pattern did not take part in the match: %s" % shown(pattern))
    return check_label_shape(text)


class VersionFromName(Processor):
    description = __doc__
    input_variables = {
        "pathname": {
            "required": True,
            "description": (
                "Path to the downloaded file. Only its file name is read, never the folders. "
                "In a recipe it is fed from the output of URLDownloader (expected: pathname)."
            ),
        },
        "version_pattern": {
            "required": True,
            "description": (
                "A regular expression with exactly one group, matched from the start of the file "
                "name (re.match). The group's text is the label. A recipe may pass the same "
                "pattern that it gives GitHubReleasesInfoProvider as asset_regex, with the label "
                "in a group."
            ),
        },
    }
    output_variables = {
        "version": {
            "description": "The label that the pattern found in the file name, checked for its shape.",
        },
    }

    def main(self):
        path = self.env.get("pathname")
        name = os.path.basename(path) if isinstance(path, str) else ""
        if not name:
            raise ProcessorError("pathname has no file name: %r" % (shown(path) if isinstance(path, str) else path,))
        pattern = self.env.get("version_pattern")
        if not isinstance(pattern, str) or not pattern:
            raise ProcessorError("version_pattern is empty or is not text: %r" % (pattern,))
        try:
            label = label_from_name(name, pattern)
        except ValueError as err:
            raise ProcessorError("%s: %s." % (shown(name), err))
        self.env["version"] = label
        self.output("version is %s, taken from the file name %s" % (label, shown(name)))


if __name__ == "__main__":
    processor = VersionFromName()
    processor.execute_shell()
