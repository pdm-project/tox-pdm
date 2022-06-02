from __future__ import annotations

import os
import shutil
from pathlib import Path

import toml


def setup_env() -> None:
    os.environ.update({"PDM_IGNORE_SAVED_PYTHON": "1", "PDM_USE_VENV": "1"})
    old_passenv = os.getenv("TOX_TESTENV_PASSENV")
    new_env = ["PDM_*"]
    if old_passenv:
        new_env.append(old_passenv)
    os.environ["TOX_TESTENV_PASSENV"] = " ".join(new_env)


def clone_pdm_files(env_path: str | Path, root: str | Path) -> None:
    """Initialize the PDM project for the given VirtualEnv by cloning
    the pyproject.toml and pdm.lock files to the venv path.
    """
    env_path = Path(env_path)
    if not env_path.exists():
        env_path.mkdir(parents=True)
    root = Path(root)
    if not root.joinpath("pyproject.toml").exists():
        return
    old_pyproject = toml.load(root.joinpath("pyproject.toml").open("r"))
    if "name" in old_pyproject.get("project", {}):
        del old_pyproject["project"]["name"]
    with env_path.joinpath("pyproject.toml").open("w") as f:
        toml.dump(old_pyproject, f)

    if root.joinpath("pdm.lock").exists():
        shutil.copy2(root.joinpath("pdm.lock"), env_path.joinpath("pdm.lock"))


def detect_pdm_files(root: str | Path) -> bool:
    root = Path(root)
    pyproject = root.joinpath("pyproject.toml")
    if not pyproject.exists():
        return False
    with pyproject.open("r") as f:
        toml_data = toml.load(f)
        return "project" in toml_data
