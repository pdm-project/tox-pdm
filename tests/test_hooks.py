import sys

import toml

from tox_pdm import tox_testenv_install_deps


def test_tox_install_deps(venv, action):
    result = tox_testenv_install_deps(venv, action)
    assert result is None

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


def test_tox_install_sections(venv, action):
    venv.envconfig.sections = ["test"]
    result = tox_testenv_install_deps(venv, action)
    assert result is None

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
        venv=True,
        action=action,
    )
