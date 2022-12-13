from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def pdm_scripts(root: Path) -> dict[str, Any]:
    pyproject_toml = root / "pyproject.toml"
    if pyproject_toml.exists():
        with open(pyproject_toml, "rb") as f:
            pyproject = tomllib.load(f)
        return pyproject.get("tool", {}).get("pdm", {}).get("scripts", {})
    return {}
