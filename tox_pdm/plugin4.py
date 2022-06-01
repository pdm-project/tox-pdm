"""Plugin specification for Tox 4"""
from __future__ import annotations

import typing as t

from tox.config.set_env import SetEnv
from tox.execute.request import StdinSource
from tox.plugin import impl
from tox.tox_env.python.virtual_env.runner import VirtualEnvRunner

if t.TYPE_CHECKING:
    from argparse import ArgumentParser

    from tox.tox_env.register import ToxEnvRegister


@impl
def tox_add_option(parser: ArgumentParser) -> None:
    parser.add_argument("--pdm", default="pdm", help="The executable path of PDM")


@impl
def tox_register_tox_env(register: ToxEnvRegister) -> t.Optional[bool]:
    register.add_run_env(PdmRunner)
    register.default_env_runner = "pdm"


class PdmRunner(VirtualEnvRunner):
    def _setup_env(self) -> None:
        super()._setup_env()
        groups = self.conf["groups"]
        pdm = self.options.pdm
        cmd = [pdm, "install", "--no-self"]
        for group in groups:
            cmd.extend(("--group", group))
        if pdm not in self.conf["allowlist_externals"]:
            self.conf["allowlist_externals"].append(pdm)
        set_env: SetEnv = self.conf["setenv"]
        if "VIRTUAL_ENV" not in set_env:
            set_env.update({"VIRTUAL_ENV": str(self.env_dir)})
        self.execute(cmd, StdinSource.OFF)

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

    @staticmethod
    def id() -> str:
        return "pdm"
