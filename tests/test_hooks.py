import sys

import toml

from tox_pdm import tox_testenv_install_deps, tox_runenvreport


def test_tox_install_no_deps(venv, action):
    result = tox_testenv_install_deps(venv, action)
    assert result is True

    venv._pcall.assert_called_once_with(
        [sys.executable, "-m", "pdm", "install", "-p", str(venv.path)],
        cwd=venv.envconfig.config.toxinidir,
        venv=True,
        action=action,
    )

    assert venv.path.join("pyproject.toml").exists()
    assert venv.path.join("pdm.lock").exists()
    with venv.path.join(".pdm.toml").open() as f:
        data = toml.load(f)
    assert data["use_venv"]


def test_tox_install_deps(venv, action):
    venv.envconfig.deps = ["click"]
    result = tox_testenv_install_deps(venv, action)
    assert result is True

    venv._pcall.assert_called_once_with(
        [sys.executable, "-m", "pdm", "install", "-p", str(venv.path), "-s", "__tox__"],
        cwd=venv.envconfig.config.toxinidir,
        venv=True,
        action=action,
    )

    with venv.path.join("pyproject.toml").open() as f:
        data = toml.load(f)
        assert data["project"]["optional-dependencies"]["__tox__"] == ["click"]


def test_tox_install_sections(venv, action):
    venv.envconfig.deps = ["click"]
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
            "-s",
            "__tox__",
        ],
        cwd=venv.envconfig.config.toxinidir,
        venv=True,
        action=action,
    )


def test_tox_runenvreport(venv, action):
    tox_runenvreport(venv, action)
    venv._pcall.assert_called_once_with(
        [sys.executable, "-m", "pdm", "list", "-p", str(venv.path), "--graph"],
        cwd=venv.envconfig.config.toxinidir,
        venv=True,
        action=action,
    )
