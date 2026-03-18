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
    OMENMON_CPU_SENSOR_PRIORITY = (
        "CPUT",
        "RTMP",
        "TMP1",
        "TNT5",
        "TNT4",
        "TNT3",
        "TNT2",
        "BIOS",
    )

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
        for args in (
            ["-Ec", "CPUT", "RTMP", "TMP1", "TNT2", "TNT3", "TNT4", "TNT5", "-Bios", "Temp"],
            ["-Ec", "CPUT", "-Bios", "Temp"],
            ["-Bios", "Temp"],
        ):
            try:
                proc = run_hidden(
                    [str(executable), *args],
                    capture_output=True,
                    text=True,
                    timeout=6,
                    check=False,
                    cwd=str(executable.parent),
                )
            except OSError:
                return None

            output = "\n".join(part for part in (proc.stdout, proc.stderr) if part).strip()
            if proc.returncode != 0 or not output:
                continue

            sensor_map = self._extract_omenmon_sensor_map(output)
            omenmon_temp = self._select_omenmon_cpu_temp(sensor_map)
            if omenmon_temp is not None:
                return omenmon_temp

            fallback = self._extract_temperature(output)
            if fallback is not None:
                return fallback

        return None

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
            if 0 < celsius < 130:
                candidates.append(round(celsius, 1))

        if not candidates:
            return None
        return candidates[-1]

    def _extract_omenmon_sensor_map(self, text: str) -> dict[str, float]:
        sensors: dict[str, float] = {}
        for line in text.splitlines():
            match = re.search(r"=\s*(-?\d+(?:\.\d+)?)\s*\[([^\]]+)\]\s*$", line.strip())
            if not match:
                continue

            value = float(match.group(1))
            label = match.group(2).strip().upper()
            if label in {"°C", "C"}:
                label = "BIOS"

            normalized = self._normalize_omenmon_temp(label, value)
            if normalized is None:
                continue

            sensors[label] = normalized
        return sensors

    def _select_omenmon_cpu_temp(self, sensors: dict[str, float]) -> Optional[float]:
        for label in self.OMENMON_CPU_SENSOR_PRIORITY:
            value = sensors.get(label)
            if value is not None:
                return value

        fallback = [value for label, value in sensors.items() if label != "GPTM"]
        if not fallback:
            return None
        return max(fallback)

    def _normalize_omenmon_temp(self, label: str, value: float) -> Optional[float]:
        if value <= 0 or value >= 130:
            return None

        # Some HP Victus models report TNT2 permanently stuck at 98 C.
        if label == "TNT2" and value >= 98:
            return None

        return round(value, 1)
