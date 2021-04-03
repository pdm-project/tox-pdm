import functools
import inspect
import os
import subprocess
from typing import List

import py
import toml
from tox import venv


def clone_pdm_files(venv: venv.VirtualEnv) -> None:
    """Initialize the PDM project for the given VirtualEnv by cloning
    the pyproject.toml and pdm.lock files to the venv path.
    """
    venv.path.ensure(dir=1)
    project_root: py.path.local = venv.envconfig.config.toxinidir
    old_pyproject = toml.loads(project_root.join("pyproject.toml").read())
    if "name" in old_pyproject.get("project", {}):
        del old_pyproject["project"]["name"]
    with venv.path.join("pyproject.toml").open("w", ensure=True) as f:
        toml.dump(old_pyproject, f)

    if project_root.join("pdm.lock").exists():
        project_root.join("pdm.lock").copy(venv.path.join("pdm.lock"))

    base_path = venv.path.join(
        f"__pypackages__/{get_version_bit(venv.getsupportedinterpreter())}"
    )
    for subdir in ("include", "lib", "Scripts" if os.name == "nt" else "bin", "src"):
        base_path.join(subdir).ensure(dir=1)


def set_default_kwargs(func_or_method, **kwargs):
    """Change the default value for keyword arguments."""
    func = getattr(func_or_method, "__func__", func_or_method)
    args = inspect.signature(func).parameters
    defaults = {k: v.default for k, v in args.items() if v.default is not v.empty}
    for k, v in kwargs.items():
        if k in defaults:
            defaults[k] = v
    func.__defaults__ = tuple(defaults.values())


@functools.lru_cache()
def get_version_bit(executable: os.PathLike) -> str:
    """Get the version of the Python interperter.

    :param executable: The path of the python executable
    :param as_string: return the version string if set to True
        and version tuple otherwise
    :param digits: the number of version parts to be returned
    :returns: A tuple of (version, is_64bit)
    """
    script = (
        'import os,sys;print(".".join(map(str, sys.version_info[:2])) '
        '+ ("-32" if os.name == "nt" and sys.maxsize <= 2**32 else ""))'
    )
    args = [executable, "-c", script]
    return subprocess.check_output(args).decode().strip()


def get_env_lib_path(venv: venv.VirtualEnv) -> py.path.local:
    """Return the PEP 582 library path for the given VirtualEnv."""
    version_bit = get_version_bit(venv.getsupportedinterpreter())
    return venv.path.join(f"__pypackages__/{version_bit}/lib")


NON_PROJECT_COMMANDS = ("cache", "show", "completion")


def inject_pdm_to_commands(venv: venv.VirtualEnv, commands: List[List[str]]) -> None:
    """Inject pdm run to the commands in place.

    Examples:
        - <cmd> -> pdm run <cmd>
        - pip install <pkg> -> pdm run pip install <pkg> -t <lib_path>
    """
    cmd_prefix = [venv.envconfig.config.option.pdm, "run", "-p", venv.path]
    pip_postfix = ["-t", get_env_lib_path(venv)]

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
            argv[inject_pos] = venv.envconfig.config.option.pdm
            if (
                inject_pos + 1 < len(argv)
                and argv[inject_pos + 1] not in NON_PROJECT_COMMANDS
                and not argv[inject_pos + 1].startswith("-")
            ):
                argv[inject_pos + 2 : inject_pos + 2] = ["-p", venv.path]
        else:
            argv[inject_pos:inject_pos] = cmd_prefix
