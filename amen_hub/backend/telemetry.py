from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class TemperatureReading:
    cpu_c: Optional[float]
    gpu_c: Optional[float]


class TemperatureService:
    def __init__(self, nbfc_executable: str | None = None) -> None:
        self.nbfc_executable = nbfc_executable

    def read(self) -> TemperatureReading:
        return TemperatureReading(cpu_c=self._read_cpu_temp(), gpu_c=self._read_gpu_temp())

    def _read_gpu_temp(self) -> Optional[float]:
        cmd = [
            "nvidia-smi",
            "--query-gpu=temperature.gpu",
            "--format=csv,noheader,nounits",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=4, check=False)
            if proc.returncode != 0:
                return None
            value = proc.stdout.strip().splitlines()[0].strip()
            return float(value)
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            return None

    def _read_cpu_temp(self) -> Optional[float]:
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

    def _run_temp_command(self, cmd: list[str]) -> Optional[float]:
        cmd = [
            *cmd,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
            if proc.returncode == 0:
                match = re.search(r"([0-9]+(?:\.[0-9]+)?)", proc.stdout)
                if match:
                    raw = float(match.group(1))
                    if raw > 200:
                        celsius = (raw / 10.0) - 273.15
                    else:
                        celsius = raw
                    if -20 < celsius < 130:
                        return round(celsius, 1)
            return None
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
