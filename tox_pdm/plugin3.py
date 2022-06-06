"""Plugin specification for Tox 3"""
import os
from typing import Any

from tox import action, config, hookimpl
from tox.venv import VirtualEnv

from .utils import pdm_scripts


def setup_env() -> None:
    os.environ.update({"PDM_IGNORE_SAVED_PYTHON": "1", "PDM_USE_VENV": "1"})
    old_passenv = os.getenv("TOX_TESTENV_PASSENV")
    new_env = ["PDM_*"]
    if old_passenv:
        new_env.append(old_passenv)
    os.environ["TOX_TESTENV_PASSENV"] = " ".join(new_env)


@hookimpl
def tox_addoption(parser: config.Parser) -> Any:
    parser.add_testenv_attribute(
        "groups", "line-list", "Specify the dependency groups to install"
    )
    setup_env()
    parser.add_argument("--pdm", default="pdm", help="The executable path of PDM")


@hookimpl
def tox_configure(config: config.Config):
    scripts = pdm_scripts(config.toxinidir)
    if scripts:
        for cfg in config.envconfigs.values():
            cfg.allowlist_externals.append("pdm")
            for lineno, cmd in enumerate(cfg.commands):
                if cmd[0] in scripts:
                    cfg.commands[lineno] = ["pdm", "run", *cmd]


@hookimpl
def tox_testenv_install_deps(venv: VirtualEnv, action: action.Action) -> Any:
    groups = venv.envconfig.groups or []
    if not venv.envconfig.skip_install or groups:
        action.setactivity("pdminstall", groups)
        args = [venv.envconfig.config.option.pdm, "install"]
        if "default" in groups:
            groups.remove("default")
        elif venv.envconfig.skip_install:
            args.append("--no-default")
        for group in groups:
            args.extend(["--group", group])
        args.append("--no-self")
        venv._pcall(
            args,
            cwd=venv.envconfig.config.toxinidir,
            venv=False,
            action=action,
        )

    deps = venv.get_resolved_dependencies()
    if deps:
        depinfo = ", ".join(map(str, deps))
        action.setactivity("installdeps", depinfo)
        venv._install(deps, action=action)
    return True
