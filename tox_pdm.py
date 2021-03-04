import inspect
import os
import sys
from typing import Any, List, Tuple

import toml
import py
from pdm.models.builders import EnvBuilder
from pdm.project import Project
from tox import action
from tox import config
from tox import hookimpl
from tox import reporter
from tox import session
from tox import venv
from tox.util.lock import hold_lock
from tox.package.view import create_session_view


def _clone_pdm_files(venv: venv.VirtualEnv) -> None:
    venv.path.ensure(dir=1)
    project_root: py.path.local = venv.envconfig.config.toxinidir
    old_pyproject = toml.loads(project_root.join("pyproject.toml").read())
    if "name" in old_pyproject.get("project", {}):
        del old_pyproject["project"]["name"]
    with venv.path.join("pyproject.toml").open("w", ensure=True) as f:
        toml.dump(old_pyproject, f)

    if project_root.join("pdm.lock").exists():
        project_root.join("pdm.lock").copy(venv.path.join("pdm.lock"))


def _set_default_kwargs(func_or_method, **kwargs):
    func = getattr(func_or_method, "__func__", func_or_method)
    args = inspect.signature(func).parameters
    defaults = {k: v.default for k, v in args.items() if v.default is not v.empty}
    for k, v in kwargs.items():
        if k in defaults:
            defaults[k] = v
    func.__defaults__ = tuple(defaults.values())


def _inject_pdm_to_commands(venv: venv.VirtualEnv) -> None:
    project = Project(venv.path)
    cmd_prefix = [sys.executable, "-m", "pdm", "run", "-p", str(project.root)]
    pip_postfix = ["-t", str(project.environment.packages_path / "lib")]

    def inject_pdm(commands: List[List[str]]) -> None:
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
            argv[inject_pos:inject_pos] = cmd_prefix

    inject_pdm(venv.envconfig.commands_pre)
    inject_pdm(venv.envconfig.commands)
    inject_pdm(venv.envconfig.commands_post)


@hookimpl
def tox_addoption(parser: config.Parser) -> Any:
    parser.add_testenv_attribute(
        "sections", "line-list", "Specify the dependency sections to install"
    )
    os.environ["TOX_TESTENV_PASSENV"] = "PYTHONPATH"
    _set_default_kwargs(venv.VirtualEnv._pcall, venv=False)
    _set_default_kwargs(venv.VirtualEnv.getcommandpath, venv=False)


@hookimpl
def tox_testenv_create(venv: venv.VirtualEnv, action: action.Action) -> Any:
    _clone_pdm_files(venv)

    config_interpreter = venv.getsupportedinterpreter()
    venv._pcall(
        [sys.executable, "-m", "pdm", "use", "-f", config_interpreter],
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
    target_dir = config.toxworkdir.join(config.isolated_build_env)
    target_dir.ensure(dir=1)
    project = Project(config.toxinidir)
    with EnvBuilder(project.root, project.environment) as builder, venv.new_action(
        "buildpkg"
    ) as action:
        builder.executable = venv.getsupportedinterpreter()
        path = builder.build_sdist(target_dir)
        action.setactivity("buildpkg", path)
        return py.path.local(path)


@hookimpl
def tox_package(session: session.Session, venv: venv.VirtualEnv) -> Any:
    if not hasattr(session, "package"):
        session.package, session.dist = get_package(session, venv)
    return session.package


@hookimpl
def tox_testenv_install_deps(venv: venv.VirtualEnv, action: action.Action) -> Any:
    _clone_pdm_files(venv)
    sections = venv.envconfig.sections or []
    # Install to local __pypackages__ folder
    venv.envconfig.install_command.extend(
        ["-t", str(Project(venv.path).environment.packages_path / "lib")]
    )
    if venv.envconfig.skip_install and not sections:
        return

    action.setactivity("pdminstall", sections)
    args = [sys.executable, "-m", "pdm", "install", "-p", str(venv.path)]
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


@hookimpl
def tox_runtest_pre(venv: venv.VirtualEnv) -> Any:
    _inject_pdm_to_commands(venv)


@hookimpl
def tox_runenvreport(venv, action):
    venv.envconfig.list_dependencies_command.extend(
        ["--path", str(Project(venv.path).environment.packages_path / "lib")]
    )
