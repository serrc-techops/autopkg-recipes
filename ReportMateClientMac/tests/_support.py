"""Shared test support: import the processor modules with or without a real
AutoPkg install, and locate fixtures.

The processor modules import `from autopkglib import Processor,
ProcessorError` at module load time, matching every other processor in this
directory (see ../ReportMateChecksumVerifier.py). AutoPkg is not installed
in every environment these tests run in, so this module installs a minimal
stand-in for `autopkglib` -- just enough of Processor/ProcessorError for the
processor classes to load and run -- only when a real `autopkglib` cannot be
imported. A real AutoPkg install, if present on the machine running the
tests, is used instead and takes precedence.
"""
import importlib
import os
import sys
import types

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DIR = os.path.dirname(TESTS_DIR)
FIXTURES_DIR = os.path.join(TESTS_DIR, "fixtures")

if RECIPE_DIR not in sys.path:
    sys.path.insert(0, RECIPE_DIR)


def _install_autopkglib_stub():
    try:
        importlib.import_module("autopkglib")
        return
    except ImportError:
        pass

    module = types.ModuleType("autopkglib")

    class ProcessorError(Exception):
        pass

    class Processor:
        def __init__(self, env=None):
            self.env = env or {}

        def output(self, msg, verbose_level=1):
            pass

        def execute_shell(self):
            raise NotImplementedError("not needed by the tests")

    module.Processor = Processor
    module.ProcessorError = ProcessorError
    sys.modules["autopkglib"] = module


_install_autopkglib_stub()

import ReportMatePostinstallPatcher as patcher  # noqa: E402
import ReportMatePostinstallChecker as checker  # noqa: E402

ProcessorError = sys.modules["autopkglib"].ProcessorError


def read_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), "r") as handle:
        return handle.read()
