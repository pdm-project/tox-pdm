import os
import shutil
from typing import Any, Tuple

import py
from tox import action, config, hookimpl, reporter, session, venv
from tox.package.view import create_session_view
from tox.util.lock import hold_lock
from tox.util.path import ensure_empty_dir

from .utils import (
    clone_pdm_files,
    get_env_lib_path,
    inject_pdm_to_commands,
    set_default_kwargs,
)


@hookimpl
def tox_addoption(parser: config.Parser) -> Any:
    parser.add_testenv_attribute(
        "sections", "line-list", "Specify the dependency sections to install"
    )
    os.environ["TOX_TESTENV_PASSENV"] = "PYTHONPATH"
    parser.add_argument("--pdm", default="pdm", help="The executable path of PDM")
    set_default_kwargs(venv.VirtualEnv._pcall, venv=False)
    set_default_kwargs(venv.VirtualEnv.getcommandpath, venv=False)


@hookimpl
def tox_testenv_create(venv: venv.VirtualEnv, action: action.Action) -> Any:
    clone_pdm_files(venv)

    config_interpreter = venv.getsupportedinterpreter()
    venv._pcall(
        [venv.envconfig.config.option.pdm, "use", "-f", config_interpreter],
        cwd=venv.path,
        venv=False,
        action=action,
    )
    return True


def get_package(
    session: session.Session, venv: venv.VirtualEnv
) -> Tuple[py.path.local, py.path.local]:
    config = session.config
    if config.skipsdist:
        reporter.info("skipping sdist step")
        return None
    lock_file = session.config.toxworkdir.join(
        "{}.lock".format(session.config.isolated_build_env)
    )

    with hold_lock(lock_file, reporter.verbosity0):
        package = acquire_package(config, venv)
        session_package = create_session_view(package, config.temp_dir)
        return session_package, package


def acquire_package(config: config.Config, venv: venv.VirtualEnv) -> py.path.local:
    target_dir: py.path.local = config.toxworkdir.join(config.isolated_build_env)
    ensure_empty_dir(target_dir)
    args = [venv.envconfig.config.option.pdm, "build", "--no-wheel", "-d", target_dir]
    with venv.new_action("buildpkg") as action:
        venv._pcall(
            args, cwd=venv.envconfig.config.toxinidir, venv=False, action=action
        )
        path = next(target_dir.visit("*.tar.gz"))
        action.setactivity("buildpkg", path)
        return path


@hookimpl
def tox_package(session: session.Session, venv: venv.VirtualEnv) -> Any:
    if not hasattr(session, "package"):
        session.package, session.dist = get_package(session, venv)
    # Patch the install command to install to local __pypackages__ folder
    for i, arg in enumerate(venv.envconfig.install_command):
        if arg == "python":
            venv.envconfig.install_command[i] = venv.getsupportedinterpreter()
    venv.envconfig.install_command.extend(["-t", get_env_lib_path(venv)])
    return session.package


@hookimpl
def tox_testenv_install_deps(venv: venv.VirtualEnv, action: action.Action) -> Any:
    clone_pdm_files(venv)
    sections = venv.envconfig.sections or []
    if not venv.envconfig.skip_install or sections:
        action.setactivity("pdminstall", sections)
        args = [venv.envconfig.config.option.pdm, "install", "-p", str(venv.path)]
        if "default" in sections:
            sections.remove("default")
        elif venv.envconfig.skip_install:
            args.append("--no-default")
        for section in sections:
            args.extend(["-s", section])
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

    lib_path = get_env_lib_path(venv)
    bin_dir = lib_path.join("bin")
    scripts_dir = lib_path.dirpath("Scripts" if os.name == "nt" else "bin")
    print(scripts_dir)
    if os.path.exists(bin_dir):
        for item in os.listdir(bin_dir):
            bin_item = os.path.join(bin_dir, item)
            shutil.move(bin_item, os.path.join(scripts_dir, item))
    return True


@hookimpl
def tox_runtest_pre(venv: venv.VirtualEnv) -> Any:
    inject_pdm_to_commands(venv, venv.envconfig.commands_pre)
    inject_pdm_to_commands(venv, venv.envconfig.commands)
    inject_pdm_to_commands(venv, venv.envconfig.commands_post)


@hookimpl
def tox_runenvreport(venv: venv.VirtualEnv, action: action.Action):
    command = venv.envconfig.list_dependencies_command
    for i, arg in enumerate(command):
        if arg == "python":
            command[i] = venv.getsupportedinterpreter()
    venv.envconfig.list_dependencies_command.extend(["--path", get_env_lib_path(venv)])
