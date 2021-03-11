from argparse import Namespace
import sys
from unittest import mock

import py
import pytest

FIX_PROJECT = py.path.local(__file__).dirpath("fixture-project")


class MockConfig:
    def __init__(self) -> None:
        self.toxinidir = py.path.local(".")
        self.option = Namespace(pdm="pdm")


class MockEnvConfig:
    def __init__(self) -> None:
        self.config = MockConfig()
        self.deps = []
        self.sections = []
        self.commands = []
        self.install_command = []
        self.commands_pre = []
        self.commands_post = []
        self.skip_install = False
        self.list_dependencies_command = ["python", "-m", "pip", "freeze"]


class MockVenv:
    def __init__(self, path) -> None:
        self.path = path
        self.envconfig = MockEnvConfig()
        self._pcall = mock.Mock()
        self._install = mock.Mock()

        for filename in ("demo.py", "pdm.lock", "pyproject.toml"):
            FIX_PROJECT.join(filename).copy(path.join(filename))

    def get_resolved_dependencies(self):
        return self.envconfig.deps

    def getsupportedinterpreter(self):
        return sys.executable


@pytest.fixture
def venv(tmpdir):
    return MockVenv(tmpdir)


@pytest.fixture
def action():
    return mock.MagicMock()
