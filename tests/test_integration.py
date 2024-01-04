import shutil
import sys
import textwrap
from pathlib import Path

import pytest

FIX_PROJECT = Path(__file__).with_name("fixture-project")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("TOX_ENV_NAME", raising=False)
    monkeypatch.delenv("TOX_WORK_DIR", raising=False)
    monkeypatch.delenv("TOX_ENV_DIR", raising=False)


def setup_project(tmpdir, tox_config):
    for filename in ("demo.py", "pdm.lock", "pyproject.toml"):
        shutil.copy(FIX_PROJECT / filename, tmpdir)
    with tmpdir.join("tox.ini").open("w", ensure=True) as f:
        f.write(tox_config)
    with tmpdir.join(".pdm.toml").open("w", ensure=True) as f:
        f.write(
            """[python]
path = "{}"
""".format(sys.executable.replace("\\", "/"))
        )


def execute_config(tmpdir, config: str):
    __tracebackhide__ = True
    from tox.run import run as main

    setup_project(tmpdir, textwrap.dedent(config))

    code = -1
    with tmpdir.as_cwd():
        try:
            main([])
        except SystemExit as e:
            print("e", e)
            code = e.code
    if code != 0:
        pytest.fail(f"non-zero exit code: {code}")

    package = tmpdir.join(".tox/.pkg/dist/demo-0.1.0.tar.gz")
    assert package.exists()


def test_install_conditional_deps(tmpdir):
    execute_config(
        tmpdir,
        """
        [tox]
        envlist = django{3,4}
        passenv = LD_PRELOAD
        isolated_build = True

        [testenv]
        groups =
            lint
        deps =
            django3: Django~=3.0
            django4: Django~=4.0
        commands =
            django-admin --version
            flake8 --version
        """,
    )


def test_use_pdm_scripts(tmpdir):
    execute_config(
        tmpdir,
        """
        [tox]
        envlist = py3
        passenv = LD_PRELOAD
        isolated_build = True

        [testenv]
        groups = lint
        commands = lint
        """,
    )


def test_use_pdm_shell_scripts(tmpdir):
    execute_config(
        tmpdir,
        """
        [tox]
        envlist = py3
        passenv = LD_PRELOAD
        isolated_build = True

        [testenv]
        groups = lint
        commands = lint-shell
        """,
    )


def test_pdm_install_not_sync(tmpdir):
    execute_config(
        tmpdir,
        """
        [tox]
        envlist = py3
        passenv = LD_PRELOAD
        isolated_build = True

        [testenv]
        groups = lint
        pdm_sync = False
        commands = flake8 --version
        """,
    )
