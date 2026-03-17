from __future__ import annotations

import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from threading import Lock

from amen_hub.config import AppConfig


@dataclass
class FanApplyResult:
    ok: bool
    message: str


class FanController:
    backend_name = "base"

    def apply_fan_speeds(self, cpu_percent: int, gpu_percent: int) -> FanApplyResult:
        raise NotImplementedError

    def describe(self) -> str:
        return self.backend_name


class MockHPVictusFanController(FanController):
    backend_name = "mock"

    def __init__(self) -> None:
        self._lock = Lock()
        self._last_cpu = 0
        self._last_gpu = 0

    def apply_fan_speeds(self, cpu_percent: int, gpu_percent: int) -> FanApplyResult:
        cpu = int(min(max(cpu_percent, 0), 100))
        gpu = int(min(max(gpu_percent, 0), 100))

        with self._lock:
            time.sleep(0.15)
            self._last_cpu = cpu
            self._last_gpu = gpu

        return FanApplyResult(
            ok=True,
            message=f"Velocidades aplicadas (modo seguro/simulacion): CPU {cpu}% | GPU {gpu}%",
        )


class NBFCFanController(FanController):
    backend_name = "nbfc"

    def __init__(self, executable: str = "nbfc.exe") -> None:
        self.executable = executable
        self._lock = Lock()

    def apply_fan_speeds(self, cpu_percent: int, gpu_percent: int) -> FanApplyResult:
        cpu = int(min(max(cpu_percent, 0), 100))
        gpu = int(min(max(gpu_percent, 0), 100))

        with self._lock:
            for fan_index, value in ((0, cpu), (1, gpu)):
                cmd = [self.executable, "set", "-f", str(fan_index), "-s", str(value)]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7, check=False)
                if proc.returncode != 0:
                    stderr = proc.stderr.strip() or proc.stdout.strip() or "sin detalle"
                    return FanApplyResult(False, f"NBFC fallo fan {fan_index}: {stderr}")

        return FanApplyResult(True, f"Velocidades aplicadas por NBFC: CPU {cpu}% | GPU {gpu}%")


class CommandTemplateFanController(FanController):
    backend_name = "command"

    def __init__(self, cpu_template: str, gpu_template: str) -> None:
        self._cpu_template = cpu_template.strip()
        self._gpu_template = gpu_template.strip()
        self._lock = Lock()

    def apply_fan_speeds(self, cpu_percent: int, gpu_percent: int) -> FanApplyResult:
        if not self._cpu_template or not self._gpu_template:
            return FanApplyResult(False, "Configura fan_command_cpu y fan_command_gpu en config.json")

        cpu = int(min(max(cpu_percent, 0), 100))
        gpu = int(min(max(gpu_percent, 0), 100))
        cpu_cmd = shlex.split(self._cpu_template.format(value=cpu))
        gpu_cmd = shlex.split(self._gpu_template.format(value=gpu))

        with self._lock:
            for cmd in (cpu_cmd, gpu_cmd):
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
                if proc.returncode != 0:
                    stderr = proc.stderr.strip() or proc.stdout.strip() or "sin detalle"
                    return FanApplyResult(False, f"Comando fallo: {stderr}")

        return FanApplyResult(True, f"Velocidades aplicadas por comando: CPU {cpu}% | GPU {gpu}%")


def build_fan_controller(config: AppConfig) -> FanController:
    if config.fan_backend == "mock":
        return MockHPVictusFanController()

    if config.fan_backend == "nbfc":
        return NBFCFanController()

    if config.fan_backend == "command":
        return CommandTemplateFanController(config.fan_command_cpu, config.fan_command_gpu)

    nbfc_path = shutil.which("nbfc.exe")
    if nbfc_path:
        return NBFCFanController(nbfc_path)

    return CommandTemplateFanController(config.fan_command_cpu, config.fan_command_gpu)
