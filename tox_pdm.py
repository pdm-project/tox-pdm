import sys
from typing import Any, Tuple

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
    project_root: py.path.local = venv.envconfig.config.toxinidir
    old_pyproject = toml.loads(project_root.join("pyproject.toml").read())
    if "name" in old_pyproject.get("project", {}):
        del old_pyproject["project"]["name"]
    with venv.path.join("pyproject.toml").open("w", ensure=True) as f:
        toml.dump(old_pyproject, f)

    project_root.join("pdm.lock").copy(venv.path.join("pdm.lock"))
    with venv.path.join(".pdm.toml").open("w") as f:
        toml.dump({"use_venv": True}, f)


@hookimpl
def tox_addoption(parser: config.Parser) -> Any:
    parser.add_testenv_attribute(
        "sections", "line-list", "Specify the dependency sections to install"
    )


def get_package(session: session.Session) -> Tuple[py.path.local, py.path.local]:
    config = session.config
    if config.skipsdist:
        reporter.info("skipping sdist step")
        return None
    lock_file = session.config.toxworkdir.join(
        "{}.lock".format(session.config.isolated_build_env)
    )

    with hold_lock(lock_file, reporter.verbosity0):
        package = acquire_package(config, session)
        session_package = create_session_view(package, config.temp_dir)
        return session_package, package


def acquire_package(config: config.Config, session: session.Session) -> py.path.local:
    package_venv: venv.VirtualEnv = session.getvenv(config.isolated_build_env)
    package_venv.envconfig.sections = []
    if package_venv.setupenv():
        package_venv.finishvenv()
    if isinstance(package_venv.status, Exception):
        raise package_venv.status

    project = Project(config.toxinidir)
    with EnvBuilder(
        project.root, project.environment
    ) as builder, package_venv.new_action("buildpkg") as action:
        builder.executable = package_venv.getsupportedinterpreter()
        path = builder.build_sdist(package_venv.path)
        action.setactivity("buildpkg", path)
        return py.path.local(path)


@hookimpl
def tox_package(session: session.Session, venv: venv.VirtualEnv) -> Any:
    if not hasattr(session, "package"):
        session.package, session.dist = get_package(session)
    return session.package


@hookimpl
def tox_testenv_install_deps(venv: venv.VirtualEnv, action: action.Action) -> Any:
    _clone_pdm_files(venv)
    sections = venv.envconfig.sections or []
    deps = venv.envconfig.deps
    if deps:
        old_pyproject = toml.loads(venv.path.join("pyproject.toml").read())
        old_pyproject["project"].setdefault("optional-dependencies", {})["__tox__"] = [
            str(dep) for dep in deps
        ]
        venv.path.join("pyproject.toml").write(toml.dumps(old_pyproject))
        sections.append("__tox__")

    args = [sys.executable, "-m", "pdm", "install", "-p", str(venv.path)]
    if "default" in sections:
        sections.remove("default")
    action.setactivity("installdeps", sections)
    for section in sections:
        args.extend(["-s", section])
    venv._pcall(
        args,
        cwd=venv.envconfig.config.toxinidir,
        venv=True,
        action=action,
    )
    return True


@hookimpl
def tox_runenvreport(venv: venv.VirtualEnv, action: action.Action) -> Any:
    args = [sys.executable, "-m", "pdm", "list", "-p", str(venv.path), "--graph"]
    output = venv._pcall(
        args, cwd=venv.envconfig.config.toxinidir, venv=True, action=action
    )
    return output.splitlines()
