# tox-pdm

A plugin for tox that utilizes PDM as the package manager and installer.

[![Github Actions](https://github.com/pdm-project/tox-pdm/workflows/Tests/badge.svg)](https://github.com/pdm-project/tox-pdm/actions)
[![PyPI](https://img.shields.io/pypi/v/tox-pdm?logo=python&logoColor=%23cccccc)](https://pypi.org/project/tox-pdm)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
![Tox Versions](https://img.shields.io/badge/tox-v3%20%7C%20v4-yellowgreen)

With this plugin, you can migrate your project to PDM while retaining the ability to test against multiple versions.

## Installation

```console
$ pip install tox-pdm
```

Or,

```console
$ pdm add -d tox-pdm
```

Or if you installed `tox` via `pipx`, you can inject the plugin by:

```console
$ pipx inject tox tox-pdm
```

## Example tox.ini

The following simple example installs `dev` and `test` dependencies into the venv created by Tox and uses pytest to execute the tests, on both Python 3.7 and 3.8.

```ini
[tox]
envlist = py37,py38
isolated_build = True  ; This is required for a pyproject.toml based project.

[testenv]
groups =  ; Dependency groups in pyproject.toml
    dev
    test
deps =      ; Additional dependencies, it will be installed into the library path via normal pip method
    flake8
commands =
    pytest test/
```

Here is another one installing the `test` dependencies and executing the `test` PDM script

```ini
[tox]
envlist = py3{8,9,10}
isolated_build = True  ; This is required for a pyproject.toml based project.

[testenv]
groups = test
commands = test
```

A real-world example can be found at this repository's [tox.ini](https://github.com/pdm-project/tox-pdm/blob/main/tox.ini) and
[GitHub Action workflow](https://github.com/pdm-project/tox-pdm/blob/main/.github/workflows/ci.yml).

## Some best practices:

1. `pdm` executable must be exposed in `PATH`, if it is not the case, give the absolute path to tox by `tox --pdm <path_to_pdm>`.
2. Make sure you have generated `pdm.lock` before running the test, it will greatly accelerate the testing.
3. If you don't set `skip_install = true`, the current package will be built and installed into the testing environment together with the `dependencies` from `pyproject.toml`.
4. Reuse your PDM scripts to avoid duplication
