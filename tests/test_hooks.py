import os
import sys
from pathlib import Path

import toml

from tox_pdm.plugin import (
    tox_runenvreport,
    tox_runtest_pre,
    tox_testenv_create,
    tox_testenv_install_deps,
)
from tox_pdm.utils import get_env_lib_path


def test_tox_install_deps(venv, action):
    result = tox_testenv_install_deps(venv, action)
    assert result is True

    venv._pcall.assert_called_once_with(
        ["pdm", "install", "-p", str(venv.path)],
        cwd=venv.envconfig.config.toxinidir,
        venv=False,
        action=action,
    )

    assert venv.path.join("pyproject.toml").exists()

    data = toml.loads(venv.path.join("pyproject.toml").read_text("utf-8"))
    assert not data["project"].get("name")

    assert venv.path.join("pdm.lock").exists()


def test_tox_install_sections(venv, action):
    venv.envconfig.sections = ["test"]
    result = tox_testenv_install_deps(venv, action)
    assert result is True

    venv._pcall.assert_called_once_with(
        [
            "pdm",
            "install",
            "-p",
            str(venv.path),
            "-s",
            "test",
        ],
        cwd=venv.envconfig.config.toxinidir,
        venv=False,
        action=action,
    )


def test_tox_skip_install(venv, action):
    venv.envconfig.skip_install = True
    result = tox_testenv_install_deps(venv, action)
    assert result is True

    venv._pcall.assert_not_called()


def test_tox_install_deps_with_deps(venv, action):
    venv.envconfig.deps = ["Flask"]

    def fake_install(*args, **kwargs):
        bin_dir = Path(get_env_lib_path(venv).join("bin"))
        bin_dir.mkdir(parents=True, exist_ok=True)
        bin_dir.joinpath("fake_bin").touch()

    venv._install.side_effect = fake_install
    result = tox_testenv_install_deps(venv, action)
    assert result is True

    venv._pcall.assert_called_once_with(
        [
            "pdm",
            "install",
            "-p",
            str(venv.path),
        ],
        cwd=venv.envconfig.config.toxinidir,
        venv=False,
        action=action,
    )

    venv._install.assert_called_once_with(["Flask"], action=action)
    scripts = Path(
        get_env_lib_path(venv).dirpath("Scripts" if os.name == "nt" else "bin")
    )
    assert scripts.joinpath("fake_bin").exists()


def test_tox_runenvreport(venv, action):
    result = tox_runenvreport(venv, action)
    assert result is None
    assert venv.envconfig.list_dependencies_command == (
        [
            venv.getsupportedinterpreter(),
            "-m",
            "pip",
            "freeze",
            "--path",
            get_env_lib_path(venv),
        ]
    )


def test_tox_testenv_create(venv, action):
    result = tox_testenv_create(venv, action)
    assert result is True

    venv._pcall.assert_called_once_with(
        ["pdm", "use", "-f", sys.executable],
        cwd=venv.path,
        venv=False,
        action=action,
    )


def test_tox_runtest_pre(venv):
    venv.envconfig.commands = [
        ["flake8"],
        ["-python", "script.py"],
        ["-", "pip", "install", "flask"],
        ["python", "-m", "pip", "install", "django"],
        ["pdm", "install"],
        ["-python", "-m", "pdm", "run", "release"],
        ["pdm", "show", "flask"],
    ]
    result = tox_runtest_pre(venv)
    lib_path = get_env_lib_path(venv)
    assert result is None
    assert venv.envconfig.commands == [
        ["pdm", "run", "-p", venv.path, "flake8"],
        [
            "-",
            "pdm",
            "run",
            "-p",
            venv.path,
            "python",
            "script.py",
        ],
        [
            "-",
            "pdm",
            "run",
            "-p",
            venv.path,
            "pip",
            "install",
            "flask",
            "-t",
            lib_path,
        ],
        [
            "pdm",
            "run",
            "-p",
            venv.path,
            "python",
            "-m",
            "pip",
            "install",
            "django",
            "-t",
            lib_path,
        ],
        ["pdm", "install", "-p", venv.path],
        ["-", "pdm", "run", "-p", venv.path, "release"],
        ["pdm", "show", "flask"],
    ]
