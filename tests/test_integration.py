import textwrap

import py.path
import toml
from tox.session import setup_reporter, load_config, set_os_env_var, build_session

FIX_PROJECT = py.path.local(__file__).dirpath("fixture-project")


def setup_project(tmpdir, tox_config):
    for filename in ("demo.py", "pdm.lock", "pyproject.toml"):
        FIX_PROJECT.join(filename).copy(tmpdir.join(filename))
    with tmpdir.join("tox.ini").open("w", ensure=True) as f:
        f.write(tox_config)


def test_install_conditional_deps(tmpdir):
    test_config = textwrap.dedent(
        """
        [tox]
        envlist = django{2,3}
        isolated_build = true

        [testenv]
        sections =
            lint
        deps =
            django2: Django~=2.0
            django3: Django~=3.0
        commands =
            django-admin --version
            flake8 --version
        """
    )
    setup_project(tmpdir, test_config)
    with tmpdir.as_cwd():
        setup_reporter([])
        config = load_config([])
        config.logdir.ensure(dir=1)
        with set_os_env_var(str("TOX_WORK_DIR"), config.toxworkdir):
            session = build_session(config)
            exit_code = session.runcommand()
        assert exit_code == 0

    assert tmpdir.join(".tox/.package/demo-0.1.0.tar.gz").exists()

    data = toml.loads(tmpdir.join(".tox/django2/pyproject.toml").read_text("UTF-8"))
    assert data["project"]["optional-dependencies"]["__tox__"] == ["Django~=2.0"]
    data = toml.loads(tmpdir.join(".tox/django3/pyproject.toml").read_text("UTF-8"))
    assert data["project"]["optional-dependencies"]["__tox__"] == ["Django~=3.0"]
