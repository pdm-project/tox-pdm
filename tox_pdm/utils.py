from __future__ import annotations

import inspect
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Sequence

import toml


def clone_pdm_files(env_path: str | Path, root: str | Path) -> None:
    """Initialize the PDM project for the given VirtualEnv by cloning
    the pyproject.toml and pdm.lock files to the venv path.
    """
    env_path = Path(env_path)
    if not env_path.exists():
        env_path.mkdir(parents=True)
    root = Path(root)
    old_pyproject = toml.load(root.joinpath("pyproject.toml").open("r"))
    if "name" in old_pyproject.get("project", {}):
        del old_pyproject["project"]["name"]
    with env_path.joinpath("pyproject.toml").open("w") as f:
        toml.dump(old_pyproject, f)

    if root.joinpath("pdm.lock").exists():
        shutil.copy2(root.joinpath("pdm.lock"), env_path.joinpath("pdm.lock"))


def set_default_kwargs(func_or_method, **kwargs):
    """Change the default value for keyword arguments."""
    func = getattr(func_or_method, "__func__", func_or_method)
    args = inspect.signature(func).parameters
    defaults = {k: v.default for k, v in args.items() if v.default is not v.empty}
    for k, v in kwargs.items():
        if k in defaults:
            defaults[k] = v
    func.__defaults__ = tuple(defaults.values())


def get_env_lib_path(pdm_exe: str, env_path: str | Path) -> str:
    """Return the PEP 582 library path for the given VirtualEnv."""
    cmd = [pdm_exe, "info", "-p", str(env_path), "--packages"]
    return os.path.join(subprocess.check_output(cmd).decode().strip(), "lib")


NON_PROJECT_COMMANDS = ("cache", "show", "completion")


def inject_pdm_to_commands(
    pdm_exe: str, env_path: str | Path, commands: List[List[str]]
) -> None:
    """Inject pdm run to the commands in place.

    Examples:
        - <cmd> -> pdm run <cmd>
        - pip install <pkg> -> pdm run pip install <pkg> -t <lib_path>
    """
    cmd_prefix = [pdm_exe, "run", "-p", str(env_path)]
    pip_postfix = ["-t", get_env_lib_path(pdm_exe, env_path)]

    for argv in commands:
        cmd = argv[0]
        inject_pos = 0
        if cmd == "-":
            cmd = argv[1]
            inject_pos = 1
        elif cmd.startswith("-"):
            cmd = cmd.lstrip("-")
            argv[:1] = ["-", cmd]
            inject_pos = 1
        if argv[inject_pos : inject_pos + 2] == ["pip", "install"] or argv[
            inject_pos : inject_pos + 4
        ] == ["python", "-m", "pip", "install"]:
            argv.extend(pip_postfix)
        if argv[inject_pos : inject_pos + 3] == ["python", "-m", "pdm"]:
            argv[inject_pos : inject_pos + 3] = ["pdm"]
        if argv[inject_pos] == "pdm":
            argv[inject_pos] = pdm_exe
            if (
                inject_pos + 1 < len(argv)
                and argv[inject_pos + 1] not in NON_PROJECT_COMMANDS
                and not argv[inject_pos + 1].startswith("-")
            ):
                argv[inject_pos + 2 : inject_pos + 2] = ["-p", str(env_path)]
        else:
            argv[inject_pos:inject_pos] = cmd_prefix


def is_same_path(left: str | Path, right: str | Path) -> bool:
    """Check if the two paths are the same"""
    return Path(left).expanduser().resolve() == Path(right).expanduser().resolve()


def is_sub_array(source: Sequence, target: Sequence) -> bool:
    """Check if the given source is a sub-array of the target"""
    if len(source) > len(target):
        return False
    for i in range(0, len(target) - len(source) + 1):
        if target[i : i + len(source)] == source:
            return True
    return False
