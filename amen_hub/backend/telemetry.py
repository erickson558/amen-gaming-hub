from __future__ import annotations

# Lectura de temperatura CPU/GPU. Nunca lanza excepciones hacia afuera: cada
# metodo devuelve None cuando no logra leer un sensor, para que la UI muestre
# "--.- C" en vez de romperse cuando falta hardware/permisos/driver.
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
    # Orden de preferencia de sensores EC de OmenMon para la temperatura de
    # CPU. CPUT es el mas confiable en HP Victus/OMEN; BIOS queda de ultimo
    # recurso porque en varios modelos devuelve 0 C (lectura invalida).
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
        """Lee CPU y GPU en una sola llamada (usado por el worker de telemetria)."""
        return TemperatureReading(cpu_c=self._read_cpu_temp(), gpu_c=self._read_gpu_temp())

    def _read_gpu_temp(self) -> Optional[float]:
        # GPU: unica fuente es nvidia-smi (equipos sin GPU NVIDIA -> None).
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
        # 1) OmenMon (EC directo, mas preciso en HP Victus/OMEN).
        omenmon_temp = self._read_omenmon_temp()
        if omenmon_temp is not None:
            return omenmon_temp

        # 2) Fallback generico via WMI/PowerShell (LibreHardwareMonitor,
        # OpenHardwareMonitor, o el namespace ACPI estandar de Windows).
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
        # Tres variantes de argumentos, de la mas completa a la mas basica:
        # si OmenMon.exe no reconoce todos los sensores EC en este equipo,
        # se reintenta con menos sensores hasta con solo -Bios Temp.
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
        """Fallback generico: busca numeros en *text* y se queda con el ultimo
        valor que parezca una temperatura razonable en Celsius (0-130).

        Usado para la salida de PowerShell/WMI, que no tiene un formato tan
        estructurado como el de OmenMon. Los valores de WMI ACPI vienen en
        decikelvin, por eso raw > 200 se convierte con la formula
        Kelvin/10 - 273.15 antes de validar el rango.
        """
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
        """Parsea la salida de OmenMon a un dict {etiqueta_sensor: valor_C}.

        OmenMon imprime lineas del estilo "CPUT = 55 [C]" o "TNT2 = 98 [C]";
        la regex captura el valor numerico y la unidad entre corchetes.
        """
        sensors: dict[str, float] = {}
        for line in text.splitlines():
            match = re.search(r"=\s*(-?\d+(?:\.\d+)?)\s*\[([^\]]+)\]\s*$", line.strip())
            if not match:
                continue

            value = float(match.group(1))
            label = match.group(2).strip().upper()
            if label in {"°C", "C"}:
                # Algunas lineas usan la unidad como etiqueta (sensor BIOS Temp).
                label = "BIOS"

            normalized = self._normalize_omenmon_temp(label, value)
            if normalized is None:
                continue

            sensors[label] = normalized
        return sensors

    def _select_omenmon_cpu_temp(self, sensors: dict[str, float]) -> Optional[float]:
        """Elige la temperatura de CPU segun OMENMON_CPU_SENSOR_PRIORITY.

        Si ninguno de los sensores priorizados esta presente, usa el maximo
        de los sensores restantes (excluyendo GPTM, que es temperatura de GPU)
        como mejor estimacion disponible.
        """
        for label in self.OMENMON_CPU_SENSOR_PRIORITY:
            value = sensors.get(label)
            if value is not None:
                return value

        fallback = [value for label, value in sensors.items() if label != "GPTM"]
        if not fallback:
            return None
        return max(fallback)

    def _normalize_omenmon_temp(self, label: str, value: float) -> Optional[float]:
        """Descarta lecturas de sensor que no son temperaturas reales."""
        if value <= 0 or value >= 130:
            return None

        # En varios HP Victus, el sensor TNT2 se queda pegado en 98 C: no es
        # una lectura real, asi que se descarta para no confundir al usuario
        # ni a la curva de modo auto termico.
        if label == "TNT2" and value >= 98:
            return None

        return round(value, 1)
