# tox-pdm

A plugin for tox that utilizes PDM as the package manager and installer.

[![Github Actions](https://github.com/pdm-project/tox-pdm/workflows/Tests/badge.svg)](https://github.com/pdm-project/tox-pdm/actions)
[![PyPI](https://img.shields.io/pypi/v/tox-pdm?logo=python&logoColor=%23cccccc)](https://pypi.org/project/tox-pdm)

With this plugin, you can migrate your project to PDM while retaining the ability to test against multiple versions.

## Installation

```console
$ pip install tox-pdm
```

Or,

```console
$ pdm add -d tox-pdm
```

## Example tox.ini

The following simple example installs `dev` and `test` dependencies into the venv created by Tox and uses pytest to execute the tests, on both Python 3.7 and 3.8.

```ini
[tox]
envlist = py37,py38
isolated_build = true ; IMPORTANT, projects that are built by PEP 517 must turn on this flag.

[testenv]
sections =  ; Dependency sections in pyproject.toml
    dev
    test
deps =      ; Additional dependencies, it will involve extra building time for dependency resolution.
    flake8
commands =
    pytest test/
```

A real-world example can be found at this repository's [tox.ini](/tox.ini) and [GitHub Action workflow](/.github/workflows/ci.yml).
