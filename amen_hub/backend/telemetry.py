from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from amen_hub.subprocess_utils import run_hidden


@dataclass
class TemperatureReading:
    cpu_c: Optional[float]
    gpu_c: Optional[float]


class TemperatureService:
    def __init__(self, nbfc_executable: str | None = None, omenmon_executable: str | None = None) -> None:
        self.nbfc_executable = nbfc_executable
        self.omenmon_executable = omenmon_executable

    def read(self) -> TemperatureReading:
        return TemperatureReading(cpu_c=self._read_cpu_temp(), gpu_c=self._read_gpu_temp())

    def _read_gpu_temp(self) -> Optional[float]:
        cmd = [
            "nvidia-smi",
            "--query-gpu=temperature.gpu",
            "--format=csv,noheader,nounits",
        ]
        try:
            proc = run_hidden(
                cmd,
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            if proc.returncode != 0:
                return None
            value = proc.stdout.strip().splitlines()[0].strip()
            return float(value)
        except (OSError, ValueError, IndexError):
            return None

    def _read_cpu_temp(self) -> Optional[float]:
        omenmon_temp = self._read_omenmon_temp()
        if omenmon_temp is not None:
            return omenmon_temp

        for cmd in (
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor -ErrorAction SilentlyContinue | "
                "Where-Object {$_.SensorType -eq 'Temperature' -and $_.Name -match 'CPU'} | "
                "Select-Object -First 1 -ExpandProperty Value)",
            ],
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance -Namespace root/OpenHardwareMonitor -ClassName Sensor -ErrorAction SilentlyContinue | "
                "Where-Object {$_.SensorType -eq 'Temperature' -and $_.Name -match 'CPU'} | "
                "Select-Object -First 1 -ExpandProperty Value)",
            ],
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature | "
                "Select-Object -First 1 -ExpandProperty CurrentTemperature)",
            ],
        ):
            value = self._run_temp_command(cmd)
            if value is not None:
                return value
        return None

    def _read_omenmon_temp(self) -> Optional[float]:
        if not self.omenmon_executable:
            return None

        executable = Path(self.omenmon_executable)
        try:
            proc = run_hidden(
                [str(executable), "-Bios", "Temp"],
                capture_output=True,
                text=True,
                timeout=6,
                check=False,
                cwd=str(executable.parent),
            )
        except OSError:
            return None

        if proc.returncode != 0:
            return None

        return self._extract_temperature(proc.stdout)

    def _run_temp_command(self, cmd: list[str]) -> Optional[float]:
        try:
            proc = run_hidden(
                [*cmd],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if proc.returncode == 0:
                return self._extract_temperature(proc.stdout)
            return None
        except (OSError, ValueError):
            return None

    def _extract_temperature(self, text: str) -> Optional[float]:
        candidates: list[float] = []
        for token in re.findall(r"(?<![A-Za-z0-9])([0-9]+(?:\.[0-9]+)?)", text):
            raw = float(token)
            if raw > 200:
                celsius = (raw / 10.0) - 273.15
            else:
                celsius = raw
            if -20 < celsius < 130:
                candidates.append(round(celsius, 1))

        if not candidates:
            return None
        return candidates[-1]
