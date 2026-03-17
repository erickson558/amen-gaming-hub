from __future__ import annotations

import ctypes
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Optional

from amen_hub.config import AppConfig
from amen_hub.paths import get_base_path


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

    def __init__(
        self,
        executable: str = "nbfc.exe",
        profile: str = "HP OMEN Notebook PC 15",
        autodiscover_profile: bool = True,
    ) -> None:
        self.executable = executable
        self.profile = profile
        self.autodiscover_profile = autodiscover_profile
        self._lock = Lock()
        self._no_window_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def _run(self, args: list[str], timeout: int = 10) -> tuple[bool, str]:
        cmd = [self.executable] + args
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=self._no_window_flag,
        )
        output = (proc.stdout or "").strip()
        error = (proc.stderr or "").strip()
        combined = "\n".join([line for line in (output, error) if line]).strip()
        lowered = combined.lower()

        has_error_text = any(
            token in lowered
            for token in (
                "error",
                "service is unavailable",
                "could not",
                "access denied",
                "acceso denegado",
                "not recognized",
            )
        )
        ok = proc.returncode == 0 and not has_error_text
        return ok, combined

    def _run_system(self, cmd: list[str], timeout: int = 12) -> tuple[int, str]:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                creationflags=self._no_window_flag,
            )
            out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            return proc.returncode, out
        except (OSError, subprocess.SubprocessError):
            return 1, "system command failed"

    def _service_process_count(self) -> int:
        code, out = self._run_system(["tasklist", "/FI", "IMAGENAME eq NbfcService.exe", "/FO", "CSV", "/NH"], timeout=6)
        if code != 0 or not out:
            return 0
        lines = [ln.strip() for ln in out.splitlines() if ln.strip() and "No tasks" not in ln]
        return len(lines)

    def _is_service_running(self) -> bool:
        code, out = self._run_system(["sc", "query", "NbfcService"], timeout=8)
        if code != 0:
            return False
        return "RUNNING" in out.upper()

    def _wait_service_running(self, timeout_s: float = 8.0) -> bool:
        end = time.time() + timeout_s
        while time.time() < end:
            if self._is_service_running():
                return True
            time.sleep(0.35)
        return False

    def _hard_reset_service(self) -> bool:
        self._run_system(["sc", "stop", "NbfcService"], timeout=10)
        time.sleep(0.4)
        self._run_system(["taskkill", "/F", "/IM", "NbfcService.exe"], timeout=6)
        time.sleep(0.4)
        self._run_system(["sc", "start", "NbfcService"], timeout=12)
        return self._wait_service_running(timeout_s=10.0)

    def _ensure_service_ready(self) -> bool:
        running = self._is_service_running()
        count = self._service_process_count()

        if running and count == 1:
            return True

        if running and count > 1:
            return self._hard_reset_service()

        self._run_system(["sc", "start", "NbfcService"], timeout=10)
        if self._wait_service_running(timeout_s=8.0):
            if self._service_process_count() <= 1:
                return True
            return self._hard_reset_service()

        return self._hard_reset_service()

    def _candidate_profiles(self) -> list[str]:
        ok, out = self._run(["config", "--list"], timeout=12)
        if not ok or not out:
            return []
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        hp_like = [ln for ln in lines if ln.lower().startswith("hp ")]
        victus_omen = [ln for ln in hp_like if ("omen" in ln.lower() or "victus" in ln.lower())]
        if victus_omen:
            return victus_omen
        return hp_like

    def _try_profile(self, profile: str, requested: int) -> tuple[bool, str]:
        ok, out = self._run(["config", "--set", profile])
        if not ok:
            return False, out
        ok, out = self._run(["set", "--fan", "0", "--speed", str(requested)], timeout=7)
        if not ok:
            return False, out
        auto_enabled, _current, target = self._read_status()
        if target is None or auto_enabled == 1.0 or target <= 0:
            return False, "target no aplicable"
        self.profile = profile
        return True, "ok"

    def _autodiscover_profile(self, requested: int) -> bool:
        if not self.autodiscover_profile:
            return False
        for profile in self._candidate_profiles():
            ok, _ = self._try_profile(profile, requested)
            if ok:
                return True
        return False

    def _read_status(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        ok, out = self._run(["status", "--fan", "0"])
        if not ok or not out:
            return None, None, None

        auto_value: Optional[float] = None
        current_value: Optional[float] = None
        target_value: Optional[float] = None

        for raw in out.splitlines():
            line = raw.strip().lower()
            if line.startswith("auto control enabled"):
                auto_value = 1.0 if "true" in line else 0.0
            elif line.startswith("current fan speed"):
                try:
                    current_value = float(raw.split(":", 1)[1].strip())
                except (IndexError, ValueError):
                    current_value = None
            elif line.startswith("target fan speed"):
                try:
                    target_value = float(raw.split(":", 1)[1].strip())
                except (IndexError, ValueError):
                    target_value = None

        return auto_value, current_value, target_value

    def apply_fan_speeds(self, cpu_percent: int, gpu_percent: int) -> FanApplyResult:
        if not is_running_as_admin():
            return FanApplyResult(
                False,
                "Control real requiere ejecutar como Administrador (NBFC service/WMI).",
            )

        cpu = int(min(max(cpu_percent, 0), 100))
        gpu = int(min(max(gpu_percent, 0), 100))
        requested = max(cpu, gpu)

        with self._lock:
            if not self._ensure_service_ready():
                return FanApplyResult(
                    False,
                    "NBFC service no llega a RUNNING. Reinstala NBFC o reinicia el equipo.",
                )

            if self._service_process_count() > 1:
                repaired = self.repair_nbfc_service()
                if not repaired or self._service_process_count() > 1:
                    return FanApplyResult(
                        False,
                        "NBFC detecta multiples procesos de servicio. Reparacion automatica fallida. Reinicia Windows para limpiar el servicio.",
                    )

            ok, out = self._run(["config", "--set", self.profile])
            if (not ok) and ("service is unavailable" in out.lower()):
                if self._hard_reset_service():
                    ok, out = self._run(["config", "--set", self.profile])
            if not ok:
                if self._autodiscover_profile(requested):
                    ok, out = self._run(["config", "--set", self.profile])
                if not ok:
                    return FanApplyResult(False, f"NBFC no pudo aplicar perfil '{self.profile}': {out or 'sin detalle'}")

            ok, out = self._run(["set", "--fan", "0", "--speed", str(requested)], timeout=7)
            if not ok:
                if "232" in out:
                    return FanApplyResult(
                        False,
                        "NBFC reporta canalizacion rota (232). Ejecuta la app como Administrador y valida perfil NBFC.",
                    )
                return FanApplyResult(False, f"NBFC no pudo fijar velocidad: {out or 'sin detalle'}")

            auto_enabled, current, target = self._read_status()
            if target is None:
                return FanApplyResult(
                    False,
                    "NBFC no devolvio estado de ventilador. Cambia perfil NBFC o ejecuta como Administrador.",
                )

            if auto_enabled == 1.0 or target <= 0:
                if self._autodiscover_profile(requested):
                    auto_enabled, current, target = self._read_status()
                    if target is not None and auto_enabled != 1.0 and target > 0:
                        return FanApplyResult(
                            True,
                            f"Perfil auto-detectado: {self.profile} | target {target:.1f}% | actual {current or 0:.1f}%",
                        )
                return FanApplyResult(
                    False,
                    "NBFC mantiene auto-control o target en 0. Perfil no compatible con este Victus.",
                )

            return FanApplyResult(
                True,
                f"Velocidad aplicada por NBFC: solicitado {requested}% | target {target:.1f}% | actual {current or 0:.1f}%",
            )

    def diagnosticar_nbfc(self) -> str:
        lines = [
            "=== Diagnostico NBFC ===",
            f"Ejecutable: {self.executable}",
            f"Perfil actual: {self.profile}",
            f"Administrador: {'si' if is_running_as_admin() else 'no'}",
        ]

        with self._lock:
            lines.append(f"Servicio RUNNING: {'si' if self._is_service_running() else 'no'}")
            lines.append(f"Procesos NbfcService.exe: {self._service_process_count()}")

            ok_status, status_out = self._run(["status", "--fan", "0"], timeout=8)
            lines.append("")
            lines.append("--- status --fan 0 ---")
            lines.append(status_out if status_out else "(sin salida)")
            if not ok_status:
                lines.append("Resultado status: error detectado.")

            ok_profiles, profiles_out = self._run(["config", "--list"], timeout=12)
            lines.append("")
            lines.append("--- perfiles (primeros 20) ---")
            if ok_profiles and profiles_out:
                profiles = [p.strip() for p in profiles_out.splitlines() if p.strip()]
                if profiles:
                    lines.extend(profiles[:20])
                    if len(profiles) > 20:
                        lines.append(f"... {len(profiles) - 20} perfiles adicionales.")
                else:
                    lines.append("(sin perfiles)")
            else:
                lines.append(profiles_out or "No se pudo consultar la lista de perfiles.")

        return "\n".join(lines)

    def repair_nbfc_service(self) -> bool:
        try:
            self._run_system(["sc", "stop", "NbfcService"], timeout=10)
            time.sleep(0.4)
            self._run_system(["taskkill", "/F", "/IM", "NbfcService.exe"], timeout=6)
            time.sleep(0.4)
            self._run_system(["sc", "start", "NbfcService"], timeout=12)
            return self._wait_service_running(timeout_s=10.0)
        except Exception:
            return False


class CommandTemplateFanController(FanController):
    backend_name = "command"

    def __init__(self, cpu_template: str, gpu_template: str) -> None:
        self._cpu_template = cpu_template.strip()
        self._gpu_template = gpu_template.strip()
        self._lock = Lock()
        self._no_window_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def apply_fan_speeds(self, cpu_percent: int, gpu_percent: int) -> FanApplyResult:
        if not self._cpu_template or not self._gpu_template:
            return FanApplyResult(False, "Configura fan_command_cpu y fan_command_gpu en config.json")

        cpu = int(min(max(cpu_percent, 0), 100))
        gpu = int(min(max(gpu_percent, 0), 100))
        cpu_cmd = shlex.split(self._cpu_template.format(value=cpu))
        gpu_cmd = shlex.split(self._gpu_template.format(value=gpu))

        with self._lock:
            for cmd in (cpu_cmd, gpu_cmd):
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                    creationflags=self._no_window_flag,
                )
                if proc.returncode != 0:
                    stderr = proc.stderr.strip() or proc.stdout.strip() or "sin detalle"
                    return FanApplyResult(False, f"Comando fallo: {stderr}")

        return FanApplyResult(True, f"Velocidades aplicadas por comando: CPU {cpu}% | GPU {gpu}%")


def build_fan_controller(config: AppConfig) -> FanController:
    if config.fan_backend == "mock":
        return MockHPVictusFanController()

    if config.fan_backend == "nbfc":
        nbfc_path = find_nbfc_executable(config.nbfc_executable)
        if nbfc_path:
            return NBFCFanController(
                nbfc_path,
                profile=config.nbfc_profile,
                autodiscover_profile=config.nbfc_autodiscover_profile,
            )
        return CommandTemplateFanController(config.fan_command_cpu, config.fan_command_gpu)

    if config.fan_backend == "command":
        return CommandTemplateFanController(config.fan_command_cpu, config.fan_command_gpu)

    nbfc_path = find_nbfc_executable(config.nbfc_executable)
    if nbfc_path:
        return NBFCFanController(
            nbfc_path,
            profile=config.nbfc_profile,
            autodiscover_profile=config.nbfc_autodiscover_profile,
        )

    return CommandTemplateFanController(config.fan_command_cpu, config.fan_command_gpu)


def find_nbfc_executable(config_value: str = "auto") -> str | None:
    if config_value and config_value.strip().lower() != "auto":
        custom = Path(config_value.strip())
        if custom.exists():
            return str(custom)

    service_path = _find_nbfc_cli_from_service()
    if service_path:
        return service_path

    base = get_base_path()
    local_candidates = [
        base / "nbfc.exe",
        base / "tools" / "nbfc" / "nbfc.exe",
        base / "NoteBook FanControl" / "nbfc.exe",
    ]
    for candidate in local_candidates:
        if candidate.exists():
            return str(candidate)

    from_path = shutil.which("nbfc.exe")
    if from_path:
        return from_path

    candidates = [
        Path("C:/Program Files (x86)/NoteBook FanControl/nbfc.exe"),
        Path("C:/Program Files/NoteBook FanControl/nbfc.exe"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return None


def _find_nbfc_cli_from_service() -> str | None:
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            ["sc", "qc", "NbfcService"],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
            creationflags=no_window,
        )
        if proc.returncode != 0:
            return None

        match = re.search(r"BINARY_PATH_NAME\s*:\s*\"?([^\r\n\"]+)\"?", proc.stdout)
        if not match:
            return None

        service_exe = Path(match.group(1).strip())
        if not service_exe.exists():
            return None

        cli = service_exe.parent / "nbfc.exe"
        if cli.exists():
            return str(cli)
        return None
    except (OSError, subprocess.SubprocessError):
        return None


def is_running_as_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False
