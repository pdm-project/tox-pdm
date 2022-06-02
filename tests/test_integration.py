import sys
import textwrap

import py
import pytest
from tox import __version__ as TOX_VERSION

FIX_PROJECT = py.path.local(__file__).dirpath("fixture-project")
IS_TOX_4 = TOX_VERSION[0] == "4"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("TOX_ENV_NAME", raising=False)
    monkeypatch.delenv("TOX_WORK_DIR", raising=False)
    monkeypatch.delenv("TOX_ENV_DIR", raising=False)


def setup_project(tmpdir, tox_config):
    for filename in ("demo.py", "pdm.lock", "pyproject.toml"):
        FIX_PROJECT.join(filename).copy(tmpdir.join(filename))
    with tmpdir.join("tox.ini").open("w", ensure=True) as f:
        f.write(tox_config)
    with tmpdir.join(".pdm.toml").open("w", ensure=True) as f:
        f.write(
            """[python]
path = "{}"
""".format(
                sys.executable.replace("\\", "/")
            )
        )


def test_install_conditional_deps(tmpdir):
    if IS_TOX_4:
        from tox.run import main
    else:
        from tox.session import main

    test_config = textwrap.dedent(
        """
        [tox]
        envlist = django{2,3}
        passenv = LD_PRELOAD
        isolated_build = True

        [testenv]
        groups =
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
        try:
            main([])
        except SystemExit as e:
            if e.code != 0:
                raise RuntimeError(f"non-zero exit code: {e.code}")

    if TOX_VERSION[0] == "4":
        package = tmpdir.join(".tox/.pkg/dist/demo-0.1.0.tar.gz")
    else:
        package = tmpdir.join(".tox/dist/demo-0.1.0.tar.gz")
    assert package.exists()
