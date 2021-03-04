from pathlib import Path
import sys

import toml
from pdm.project import Project

from tox_pdm import (
    tox_testenv_install_deps,
    tox_testenv_create,
    tox_runtest_pre,
    tox_runenvreport,
)


def test_tox_install_deps(venv, action):
    result = tox_testenv_install_deps(venv, action)
    assert result is True

    venv._pcall.assert_called_once_with(
        [sys.executable, "-m", "pdm", "install", "-p", str(venv.path)],
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
            sys.executable,
            "-m",
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
    project = Project(venv.path)

    def fake_install(*args, **kwargs):
        bin_dir = Path(project.environment.get_paths()["purelib"], "bin")
        bin_dir.mkdir(parents=True, exist_ok=True)
        bin_dir.joinpath("fake_bin").touch()

    venv._install.side_effect = fake_install
    result = tox_testenv_install_deps(venv, action)
    assert result is True

    venv._pcall.assert_called_once_with(
        [
            sys.executable,
            "-m",
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
    scripts = Path(project.environment.get_paths()["scripts"])
    assert scripts.joinpath("fake_bin").exists()


def test_tox_runenvreport(venv, action):
    result = tox_runenvreport(venv, action)
    assert result is None
    assert venv.envconfig.list_dependencies_command == (
        [
            "python",
            "-m",
            "pip",
            "freeze",
            "--path",
            str(Project(venv.path).environment.packages_path / "lib"),
        ]
    )


def test_tox_testenv_create(venv, action):
    result = tox_testenv_create(venv, action)
    assert result is True

    venv._pcall.assert_called_once_with(
        [sys.executable, "-m", "pdm", "use", "-f", sys.executable],
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
    ]
    result = tox_runtest_pre(venv)
    project = Project(venv.path)
    assert result is None
    assert venv.envconfig.commands == [
        [sys.executable, "-m", "pdm", "run", "-p", str(project.root), "flake8"],
        [
            "-",
            sys.executable,
            "-m",
            "pdm",
            "run",
            "-p",
            str(project.root),
            "python",
            "script.py",
        ],
        [
            "-",
            sys.executable,
            "-m",
            "pdm",
            "run",
            "-p",
            str(project.root),
            "pip",
            "install",
            "flask",
            "-t",
            str(project.environment.packages_path / "lib"),
        ],
        [
            sys.executable,
            "-m",
            "pdm",
            "run",
            "-p",
            str(project.root),
            "python",
            "-m",
            "pip",
            "install",
            "django",
            "-t",
            str(project.environment.packages_path / "lib"),
        ],
    ]
