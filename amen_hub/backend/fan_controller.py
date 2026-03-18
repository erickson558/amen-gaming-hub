from __future__ import annotations

import csv
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


@dataclass
class ServiceInfo:
    state_code: int | None
    pid: int | None
    raw_output: str

    @property
    def is_running(self) -> bool:
        return self.state_code == 4


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

    def _query_service_info(self) -> ServiceInfo:
        code, out = self._run_system(["sc", "queryex", "NbfcService"], timeout=8)
        if code != 0:
            return ServiceInfo(None, None, out)

        state_match = re.search(r"(?:STATE|ESTADO)\s*:\s*(\d+)", out, re.IGNORECASE)
        pid_match = re.search(r"\bPID\s*:\s*(\d+)", out, re.IGNORECASE)

        state_code = int(state_match.group(1)) if state_match else None
        pid = int(pid_match.group(1)) if pid_match else None
        return ServiceInfo(state_code, pid, out)

    def _list_service_process_pids(self) -> list[int]:
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq NbfcService.exe", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=6,
                check=False,
                creationflags=self._no_window_flag,
            )
        except (OSError, subprocess.SubprocessError):
            return []

        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        pids: list[int] = []
        for row in csv.reader(line for line in proc.stdout.splitlines() if line.strip()):
            if not row or row[0].strip().lower() != "nbfcservice.exe":
                continue
            try:
                pids.append(int(row[1]))
            except (IndexError, ValueError):
                continue
        return pids

    def _service_process_count(self) -> int:
        return len(self._list_service_process_pids())

    def _is_service_running(self) -> bool:
        return self._query_service_info().is_running

    def _wait_for_service_state(self, expected_states: set[int], timeout_s: float = 8.0) -> ServiceInfo | None:
        end = time.time() + timeout_s
        while time.time() < end:
            info = self._query_service_info()
            if info.state_code in expected_states:
                return info
            time.sleep(0.35)
        return None

    def _wait_service_running(self, timeout_s: float = 8.0) -> bool:
        return self._wait_for_service_state({4}, timeout_s=timeout_s) is not None

    def _is_cli_available(self) -> bool:
        try:
            proc = subprocess.run(
                [self.executable, "status", "--fan", "0"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
                creationflags=self._no_window_flag,
            )
        except (OSError, subprocess.SubprocessError):
            return False

        combined = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        lowered = combined.lower()
        unavailable_tokens = (
            "service is unavailable",
            "broken pipe",
            "pipe is being closed",
            "nullreference",
            "null reference",
        )
        if any(token in lowered for token in unavailable_tokens):
            return False
        return proc.returncode == 0

    def _wait_for_cli_available(self, timeout_s: float = 8.0) -> bool:
        end = time.time() + timeout_s
        while time.time() < end:
            if self._is_cli_available():
                return True
            time.sleep(0.4)
        return False

    def _hard_reset_service(self) -> bool:
        ok, _message = self._repair_nbfc_service_locked()
        return ok

    def _ensure_service_ready(self) -> bool:
        info = self._query_service_info()

        if info.is_running and self._wait_for_cli_available(timeout_s=5.0):
            return True

        if info.state_code in {2, 3}:
            waited = self._wait_for_service_state({1, 4}, timeout_s=10.0)
            if waited is not None and waited.is_running and self._wait_for_cli_available(timeout_s=5.0):
                return True

        if info.state_code == 1:
            self._run_system(["sc", "start", "NbfcService"], timeout=12)
            if self._wait_service_running(timeout_s=12.0) and self._wait_for_cli_available(timeout_s=6.0):
                return True

        if info.is_running and self._wait_for_cli_available(timeout_s=3.0):
            return True

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
                    "NBFC service no queda operativo. Intenta Reparar NBFC y valida permisos de Administrador.",
                )

            ok, out = self._run(["config", "--set", self.profile])
            if (not ok) and ("service is unavailable" in out.lower()):
                repaired, _repair_report = self._repair_nbfc_service_locked()
                if repaired:
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
        service_info = self._query_service_info()
        process_pids = self._list_service_process_pids()
        lines = [
            "=== Diagnostico NBFC ===",
            f"Ejecutable: {self.executable}",
            f"Perfil actual: {self.profile}",
            f"Administrador: {'si' if is_running_as_admin() else 'no'}",
            f"Estado servicio: {service_info.state_code if service_info.state_code is not None else 'N/D'}",
            f"PID servicio: {service_info.pid if service_info.pid is not None else 'N/D'}",
            f"PIDs NbfcService.exe: {process_pids if process_pids else '[]'}",
        ]

        with self._lock:
            lines.append(f"Servicio RUNNING: {'si' if service_info.is_running else 'no'}")
            lines.append(f"Procesos NbfcService.exe: {self._service_process_count()}")
            lines.append(f"CLI disponible: {'si' if self._is_cli_available() else 'no'}")

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

    def _repair_nbfc_service_locked(self) -> tuple[bool, str]:
        if not is_running_as_admin():
            return False, "La reparacion NBFC requiere ejecutar la app como Administrador."

        steps: list[str] = []
        try:
            initial = self._query_service_info()
            steps.append(
                f"Estado inicial: state={initial.state_code if initial.state_code is not None else 'N/D'} "
                f"pid={initial.pid if initial.pid is not None else 'N/D'} pids={self._list_service_process_pids()}"
            )

            self._run_system(["sc", "stop", "NbfcService"], timeout=10)
            stopped = self._wait_for_service_state({1}, timeout_s=10.0)
            if stopped is None:
                current = self._query_service_info()
                if current.pid:
                    self._run_system(["taskkill", "/PID", str(current.pid), "/T", "/F"], timeout=8)
                    steps.append(f"Se forzo cierre del PID del servicio: {current.pid}")

                extra_pids = self._list_service_process_pids()
                if extra_pids:
                    self._run_system(["taskkill", "/F", "/IM", "NbfcService.exe"], timeout=8)
                    steps.append(f"Se forzo cierre por imagen. PIDs detectados: {extra_pids}")

                self._wait_for_service_state({1}, timeout_s=8.0)

            time.sleep(1.0)
            self._run_system(["sc", "start", "NbfcService"], timeout=12)
            running = self._wait_for_service_state({4}, timeout_s=12.0)
            if running is None:
                current = self._query_service_info()
                steps.append(
                    f"El servicio no llego a RUNNING. state={current.state_code if current.state_code is not None else 'N/D'} "
                    f"pid={current.pid if current.pid is not None else 'N/D'}"
                )
                return False, "No se pudo levantar NbfcService. " + " | ".join(steps)

            if not self._wait_for_cli_available(timeout_s=12.0):
                current = self._query_service_info()
                steps.append(
                    f"El servicio arranco pero la CLI no responde. state={current.state_code if current.state_code is not None else 'N/D'} "
                    f"pid={current.pid if current.pid is not None else 'N/D'} pids={self._list_service_process_pids()}"
                )
                return False, "NbfcService arranco pero sigue no disponible para nbfc.exe. " + " | ".join(steps)

            final_info = self._query_service_info()
            final_pids = self._list_service_process_pids()
            return True, (
                "NBFC reparado correctamente. "
                f"state={final_info.state_code if final_info.state_code is not None else 'N/D'} "
                f"pid={final_info.pid if final_info.pid is not None else 'N/D'} "
                f"pids={final_pids}"
            )
        except Exception as ex:
            return False, f"Error inesperado reparando NBFC: {ex}"

    def repair_nbfc_service(self) -> bool:
        with self._lock:
            ok, _message = self._repair_nbfc_service_locked()
            return ok

    def repair_nbfc_service_with_report(self) -> tuple[bool, str]:
        with self._lock:
            return self._repair_nbfc_service_locked()


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
