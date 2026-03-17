from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock


@dataclass
class FanApplyResult:
    ok: bool
    message: str


class FanController:
    def apply_fan_speeds(self, cpu_percent: int, gpu_percent: int) -> FanApplyResult:
        raise NotImplementedError


class MockHPVictusFanController(FanController):
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
