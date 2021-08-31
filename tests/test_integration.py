import textwrap

import py

FIX_PROJECT = py.path.local(__file__).dirpath("fixture-project")


def setup_project(tmpdir, tox_config):
    for filename in ("demo.py", "pdm.lock", "pyproject.toml"):
        FIX_PROJECT.join(filename).copy(tmpdir.join(filename))
    with tmpdir.join("tox.ini").open("w", ensure=True) as f:
        f.write(tox_config)


def test_install_conditional_deps(tmpdir):
    from tox.run import main
    from tox import __version__ as TOX_VERSION

    test_config = textwrap.dedent(
        """
        [tox]
        envlist = django{2,3}
        passenv = LD_PRELOAD

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
        main(["-c", str(tmpdir.join("tox.ini"))])

    if TOX_VERSION[0] == "4":
        package = tmpdir.join(".tox/4/.pkg/dist/demo-0.1.0.tar.gz")
    else:
        package = tmpdir.join(".tox/.package/demo-0.1.0.tar.gz")
    assert package.exists()
