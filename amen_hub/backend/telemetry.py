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
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature | "
            "Select-Object -First 1 -ExpandProperty CurrentTemperature)",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
            if proc.returncode != 0:
                return None
            match = re.search(r"(\d+)", proc.stdout)
            if not match:
                return None
            kelvin_x10 = int(match.group(1))
            celsius = (kelvin_x10 / 10.0) - 273.15
            return round(celsius, 1)
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
