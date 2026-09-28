#!/usr/bin/env python3
# Thanks to Graham Gilbert for
# https://github.com/salsoftware/sal/blob/master/scripts/postflight
import sys
import os
import subprocess

POSTFLIGHT_DIR = '__POSTFLIGHT_D__'


def iter_postflight_scripts(postflight_dir):
    for script in os.listdir(postflight_dir):
        script_path = os.path.join(postflight_dir, script)
        if not os.access(script_path, os.X_OK):
            print(f"'{script_path}' is not executable or has bad permissions")
        else:
            yield script_path


def execute_postflight_scripts(postflight_dir):
    for script_path in iter_postflight_scripts(postflight_dir):
        try:
            subprocess.call([script_path, sys.argv[1]])
        except OSError:
            print(f"Could not execute script '{script_path}'!")


if __name__ == '__main__':
    execute_postflight_scripts(POSTFLIGHT_DIR)

# --- test fixture notice (not part of the original file) -----------------
# This is Zentral's Munki postflight runner, used here, unmodified in
# substance, to reproduce the bug this build exists to avoid: a postflight
# that itself runs everything in postflight.d/. Apache License 2.0; see
# LICENSE-zentral next to this file.
#
# Origin: zentral/contrib/munki/osx_package/build.tmpl/root/usr/local/zentral/munki/postflight
# (github.com/zentralopensource/zentral, outside the ee/ directory, so
# Apache-licensed per that repository's own LICENSE file). Two things were
# changed from the shipped script, both noted where they appear above:
# the interpreter line (was "#!/usr/local/munki/munki-python", which does
# not exist off a real Munki install) and the POSTFLIGHT_DIR value (was the
# literal "/usr/local/munki/postflight.d"; the placeholder above is
# substituted with a temporary-directory path by the tests that use it).
# Everything else, including the comment crediting Graham Gilbert's Sal
# postflight script this was adapted from, is unchanged.
