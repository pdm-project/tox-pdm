from unittest import mock

import py
import pytest


class MockConfig:
    def __init__(self) -> None:
        self.toxinidir = py.path.local(".")


class MockEnvConfig:
    def __init__(self) -> None:
        self.config = MockConfig()
        self.deps = []
        self.sections = []
        self.commands = []


class MockVenv:
    def __init__(self, path) -> None:
        self.path = path
        self.envconfig = MockEnvConfig()
        self._pcall = mock.Mock()
        self._install = mock.Mock()

    def get_resolved_dependencies(self):
        return self.envconfig.deps


@pytest.fixture
def venv(tmpdir):
    return MockVenv(tmpdir)


@pytest.fixture
def action():
    return mock.MagicMock()
