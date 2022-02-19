"""Plugin specification for Tox 4"""
from __future__ import annotations

import os
import shutil
import sys
import typing as t
from pathlib import Path

from tox.config.cli.parser import DEFAULT_VERBOSITY
from tox.config.sets import EnvConfigSet
from tox.execute.api import Execute
from tox.execute.local_sub_process import LocalSubProcessExecuteInstance
from tox.execute.request import StdinSource
from tox.plugin import impl
from tox.tox_env.package import Package, PackageToxEnv
from tox.tox_env.python.api import Python, PythonInfo
from tox.tox_env.python.package import WheelPackage
from tox.tox_env.python.pip.pip_install import Pip
from tox.tox_env.python.runner import PythonRun
from virtualenv.discovery.builtin import get_interpreter

from tox_pdm.utils import clone_pdm_files, get_env_lib_path, is_same_path, is_sub_array

if t.TYPE_CHECKING:

    from argparse import ArgumentParser

    from tox.execute.api import ExecuteInstance, ExecuteOptions
    from tox.execute.request import ExecuteRequest
    from tox.execute.stream import SyncWrite
    from tox.tox_env.api import ToxEnvCreateArgs
    from tox.tox_env.register import ToxEnvRegister


@impl
def tox_add_option(parser: ArgumentParser) -> None:
    os.environ["TOX_TESTENV_PASSENV"] = "PYTHONPATH"
    parser.add_argument("--pdm", default="pdm", help="The executable path of PDM")


@impl
def tox_register_tox_env(register: ToxEnvRegister) -> t.Optional[bool]:
    register.add_run_env(PdmRunner)
    register.add_package_env(PdmPackageEnv)
    register.default_env_runner = "pdm"


class Pdm(Python):
    def __init__(self, create_args: ToxEnvCreateArgs) -> None:
        self._executor: t.Optional[Execute] = None
        self._installer: t.Optional[Pip] = None
        self._package_path: t.Optional[Path] = None
        super().__init__(create_args)

    @property
    def executor(self) -> Execute:
        if not self._executor:
            self._executor = PDMRunExecutor(self.options.is_colored)
        return self._executor

    @property
    def installer(self) -> Pip:
        if self._installer is None:
            self._installer = PipPep582(self)
        return self._installer

    @property
    def package_path(self) -> Path:
        if not self._package_path:
            self._package_path = Path(
                get_env_lib_path(self.options.pdm, self.env_dir)
            ).parent
        return self._package_path

    @property
    def runs_on_platform(self) -> str:
        return sys.platform

    def create_python_env(self) -> None:
        clone_pdm_files(self.env_dir, self.core["toxinidir"])
        self.execute(
            ["pdm", "use", "-f", self.base_python.extra["executable"]], StdinSource.OFF
        )

    def _get_python(self, base_python: t.List[str]) -> t.Optional[PythonInfo]:
        interpreter = next(
            filter(None, (get_interpreter(p, []) for p in base_python)), None
        )
        if not interpreter:
            return None
        return PythonInfo(
            implementation=interpreter.implementation,
            version_info=interpreter.version_info,
            version=interpreter.version,
            is_64=(interpreter.architecture == 64),
            platform=interpreter.platform,
            extra={"executable": Path(interpreter.system_executable)},
        )

    def python_cache(self) -> t.Dict[str, t.Any]:
        base = super().python_cache()
        base.update({"executable": str(self.base_python.extra["executable"])})
        return base

    def env_bin_dir(self) -> Path:
        return self.package_path / ("Scripts" if os.name == "nt" else "bin")

    def env_python(self) -> Path:
        return t.cast(Path, self.base_python.extra["executable"])

    def env_site_package_dir(self) -> Path:
        return self.package_path / "lib"

    def prepend_env_var_path(self) -> t.List[Path]:
        return [self.env_bin_dir]


class PdmRunner(Pdm, PythonRun):
    def _setup_env(self) -> None:
        super()._setup_env()
        groups = self.conf["groups"]
        cmd = ["pdm", "install", "--no-self"]
        for group in groups:
            cmd.extend(("--group", group))
        self.execute(cmd, StdinSource.OFF)
        bin_path = self.env_site_package_dir() / "bin"
        if not bin_path.exists():
            return
        scripts_path = self.env_bin_dir()
        for file in bin_path.iterdir():
            shutil.move(os.fspath(file), os.fspath(scripts_path))

    def register_config(self) -> None:
        super().register_config()
        self.conf.add_config(
            "groups",
            of_type=t.List[str],
            default=[],
            desc="Specify the dependency groups to install",
        )

    @property
    def _package_tox_env_type(self) -> str:
        return "pdm-pep-517"

    @staticmethod
    def id() -> str:
        return "pdm"

    @property
    def _external_pkg_tox_env_type(self) -> str:
        return "virtualenv-cmd-builder"


class PdmPackageEnv(Pdm, PackageToxEnv):
    def register_config(self) -> None:
        super().register_config()
        self.conf.add_config(
            keys=["pkg_dir"],
            of_type=Path,
            default=lambda conf, name: self.env_dir / "dist",
            desc="directory where to put project packages",
        )

    @property
    def pkg_dir(self) -> Path:
        return t.cast(Path, self.conf["pkg_dir"])

    def perform_packaging(self, for_env: EnvConfigSet) -> t.List[Package]:
        of_type: str = for_env["package"]
        cmd = [
            "pdm",
            "build",
            "-p",
            str(self.conf["package_root"]),
            "-d",
            str(self.pkg_dir),
        ]
        if of_type == "wheel":
            cmd.append("--no-sdist")
            suffix = ".whl"
        else:
            cmd.append("--no-wheel")
            suffix = ".tar.gz"
        self.execute(cmd, StdinSource.OFF)
        path = next(self.pkg_dir.glob(f"*{suffix}"))
        package = WheelPackage(path, [])
        return [package]

    @staticmethod
    def id() -> str:
        return "pdm-pep-517"

    def child_pkg_envs(self, run_conf: EnvConfigSet) -> t.Iterator[PackageToxEnv]:
        return iter(())


class PipPep582(Pip):
    def installed(self) -> t.List[str]:
        cmd = ["pdm", "list", "--freeze"]
        result = self._env.execute(
            cmd=cmd,
            stdin=StdinSource.OFF,
            run_id="freeze",
            show=self._env.options.verbosity > DEFAULT_VERBOSITY,
        )
        result.assert_success()
        return [line.strip() for line in result.out.splitlines() if line.strip()]


class PDMRunExecutor(Execute):
    def build_instance(
        self,
        request: ExecuteRequest,
        options: ExecuteOptions,
        out: SyncWrite,
        err: SyncWrite,
    ) -> "ExecuteInstance":
        return PDMRunExecuteInstance(request, options, out, err)


class PDMRunExecuteInstance(LocalSubProcessExecuteInstance):
    @property
    def cmd(self) -> t.Sequence[str]:
        if self._cmd is None:
            pdm_exe = self.options._env.options.pdm
            cmd = self.request.cmd
            if cmd[0] == "pdm":
                cmd[0] = pdm_exe
            if is_same_path(cmd[0], pdm_exe):
                if "-p" not in cmd and "--project" not in cmd:
                    cmd[2:2] = ["-p", str(self.options._env.env_dir)]
            elif is_sub_array(["pip", "install"], cmd):
                cmd.extend(["-t", get_env_lib_path(pdm_exe, self.options._env.env_dir)])
            else:
                cmd = [pdm_exe, "run", "-p", str(self.options._env.env_dir)] + cmd
            self._cmd = cmd
        return self._cmd
