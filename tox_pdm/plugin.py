"""Plugin specification for Tox 4"""
from __future__ import annotations

import os
import typing as t
from pathlib import Path

from packaging.requirements import Requirement
from tox.config.set_env import SetEnv
from tox.config.sets import EnvConfigSet
from tox.execute.request import StdinSource
from tox.plugin import impl
from tox.tox_env.python.virtual_env.package.pyproject import Pep517VirtualEnvPackager
from tox.tox_env.python.virtual_env.runner import VirtualEnvRunner

from .utils import pdm_scripts

if t.TYPE_CHECKING:
    from argparse import ArgumentParser

    from tox.execute.api import Execute, Outcome
    from tox.tox_env.register import ToxEnvRegister

os.environ.pop("NO_SITE_PACKAGES", None)


@impl
def tox_add_option(parser: ArgumentParser) -> None:
    parser.add_argument("--pdm", default="pdm", help="The executable path of PDM")


@impl
def tox_register_tox_env(register: ToxEnvRegister) -> t.Optional[bool]:
    register.add_run_env(PdmRunner)
    register.add_package_env(PdmPep517Packager)
    register.default_env_runner = "pdm"


class PdmRunner(VirtualEnvRunner):
    def _setup_env(self) -> None:
        super()._setup_env()
        pdm = self.options.pdm
        if pdm not in self.conf["allowlist_externals"]:
            self.conf["allowlist_externals"].append(pdm)
        if self.conf["skip_install"]:
            return
        groups = self.conf["groups"]
        op = "sync" if self.conf["pdm_sync"] else "install"
        cmd = [pdm, op, "--no-self"]
        for group in groups:
            cmd.extend(("--group", group))
        set_env: SetEnv = self.conf["setenv"]
        if "VIRTUAL_ENV" not in set_env:
            set_env.update({"VIRTUAL_ENV": str(self.env_dir)})
        outcome = self.execute(cmd, StdinSource.OFF, run_id="install_deps")
        outcome.assert_success()

    @staticmethod
    def _load_pass_env(pass_env: list[str]) -> dict[str, str]:
        env = VirtualEnvRunner._load_pass_env(pass_env)
        env.update({"PDM_IGNORE_SAVED_PYTHON": "1", "PDM_USE_VENV": "1"})
        return env

    def register_config(self) -> None:
        super().register_config()
        self.conf.add_config(
            "groups",
            of_type=t.List[str],
            default=[],
            desc="Specify the dependency groups to install",
        )
        self.conf.add_config(
            "pdm_sync",
            of_type=bool,
            default=True,
            desc="Disable to use 'pdm install' instead of 'pdm sync'.",
        )

    @staticmethod
    def id() -> str:
        return "pdm"

    @property
    def _package_tox_env_type(self) -> str:
        return "pdm-pep-517"

    def execute(
        self,
        cmd: t.Sequence[Path | str],
        stdin: StdinSource,
        show: bool | None = None,
        cwd: Path | None = None,
        run_id: str = "",
        executor: Execute | None = None,
    ) -> Outcome:
        scripts = pdm_scripts(self.core["tox_root"])
        if scripts and cmd[0] in scripts:
            cmd = ["pdm", "run", *cmd]
        return super().execute(cmd, stdin, show, cwd, run_id, executor)


class PdmPep517Packager(Pep517VirtualEnvPackager):
    """A subclass of Pep517VirtualEnvPackager that doesn't
    analyze package dependencies, since they will be installed by PDM.
    """

    @staticmethod
    def id() -> str:
        return "pdm-pep-517"

    def _load_deps(self, for_env: EnvConfigSet) -> list[Requirement]:
        return []
