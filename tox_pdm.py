import os
import sys
from typing import Any, Tuple

import toml
import py
from pdm.models.builders import EnvBuilder
from pdm.project import Project
from tox import action
from tox import config
from tox import exception
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
def tox_testenv_create(venv: venv.VirtualEnv, action: action.Action) -> Any:
    venv_path = venv.path
    venv_path.ensure(dir=1)
    _clone_pdm_files(venv)
    # Install to local __pypackages__ folder
    venv.envconfig.install_command.extend(
        ["-t", str(Project(venv.path).environment.packages_path / "lib")]
    )

    config_interpreter = venv.getsupportedinterpreter()
    venv._pcall(
        [sys.executable, "-m", "pdm", "use", "-f", config_interpreter],
        cwd=venv_path,
        venv=False,
        action=action,
    )
    return True


@hookimpl
def tox_testenv_install_deps(venv: venv.VirtualEnv, action: action.Action) -> Any:
    sections = venv.envconfig.sections or []
    deps = venv.envconfig.deps
    if deps:
        old_pyproject = toml.loads(venv.path.join("pyproject.toml").read())
        old_pyproject["project"].setdefault("optional-dependencies", {})["__tox__"] = [
            str(dep) for dep in deps
        ]
        venv.path.join("pyproject.toml").write(toml.dumps(old_pyproject))
        sections.append("__tox__")

    if not sections:
        return True

    args = [sys.executable, "-m", "pdm", "install", "-p", str(venv.path)]
    if "default" in sections:
        sections.remove("default")
    action.setactivity("installdeps", sections)
    for section in sections:
        args.extend(["-s", section])
    venv._pcall(args, cwd=venv.envconfig.config.toxinidir, venv=False, action=action)
    return True


@hookimpl
def tox_runenvreport(venv: venv.VirtualEnv, action: action.Action) -> Any:
    args = [sys.executable, "-m", "pdm", "list", "-p", str(venv.path), "--graph"]
    output = venv._pcall(
        args, cwd=venv.envconfig.config.toxinidir, venv=False, action=action
    )
    return output.splitlines()


@hookimpl
def tox_runtest(venv, redirect):
    action = venv.new_action("runtests")
    action.setactivity("runtests", "PYTHONHASHSEED=%r" % os.getenv("PYTHONHASHSEED"))
    for i, argv in enumerate(venv.envconfig.commands):
        # have to make strings as _pcall changes argv[0] to a local()
        # happens if the same environment is invoked twice
        cwd = venv.envconfig.changedir
        message = "commands[%s] | %s" % (i, " ".join([str(x) for x in argv]))
        action.setactivity("runtests", message)
        # check to see if we need to ignore the return code
        # if so, we need to alter the command line arguments
        if argv[0].startswith("-"):
            ignore_ret = True
            if argv[0] == "-":
                del argv[0]
            else:
                argv[0] = argv[0].lstrip("-")
        else:
            ignore_ret = False
        args = [sys.executable, "-m", "pdm", "run", "-p", venv.path] + argv
        try:
            venv._pcall(
                args,
                venv=False,
                cwd=cwd,
                action=action,
                redirect=redirect,
                ignore_ret=ignore_ret,
            )
        except exception.InvocationError as err:
            if venv.envconfig.ignore_outcome:
                reporter.warning(
                    "command failed but result from testenv is ignored\n"
                    "  cmd: %s" % (str(err),)
                )
                venv.status = "ignored failed command"
                continue  # keep processing commands

            reporter.error(str(err))
            venv.status = "commands failed"
            if not venv.envconfig.ignore_errors:
                break  # Don't process remaining commands
        except KeyboardInterrupt:
            venv.status = "keyboardinterrupt"
            reporter.error(venv.status)
            raise

    return True
