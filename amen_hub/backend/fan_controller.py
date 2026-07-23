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
from amen_hub.subprocess_utils import run_hidden


@dataclass
class FanApplyResult:
    """Resultado uniforme de cualquier operacion de un FanController."""

    ok: bool
    message: str


@dataclass
class ServiceInfo:
    """Estado del servicio Windows NbfcService, segun `sc queryex`."""

    state_code: int | None
    pid: int | None
    raw_output: str

    @property
    def is_running(self) -> bool:
        # 4 = SERVICE_RUNNING en el modelo de estados de Windows Service Control Manager.
        return self.state_code == 4


class FanController:
    """Interfaz comun para todos los backends de control de ventiladores."""

    backend_name = "base"

    def apply_fan_speeds(self, cpu_percent: int, gpu_percent: int) -> FanApplyResult:
        raise NotImplementedError

    def requires_admin_for_control(self) -> bool:
        return False

    def restore_automatic_control(self) -> FanApplyResult:
        return FanApplyResult(True, f"{self.describe()}: sin restauracion explicita")

    def describe(self) -> str:
        return self.backend_name


class UnavailableFanController(FanController):
    """Backend "nulo": se usa cuando el backend pedido no se pudo inicializar
    (ejecutable no encontrado, etc.). Cualquier operacion falla con un mensaje
    explicando por que, en vez de lanzar una excepcion o fallar en silencio.
    """

    def __init__(self, backend_name: str, message: str) -> None:
        self.backend_name = f"{backend_name} (no disponible)"
        self._message = message

    def apply_fan_speeds(self, cpu_percent: int, gpu_percent: int) -> FanApplyResult:
        return FanApplyResult(False, self._message)

    def restore_automatic_control(self) -> FanApplyResult:
        return FanApplyResult(False, self._message)


class MockHPVictusFanController(FanController):
    """Backend de simulacion: no toca hardware real. Sirve para probar la UI,
    el threading y la persistencia de configuracion sin una laptop HP a mano.
    """

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

    def restore_automatic_control(self) -> FanApplyResult:
        return FanApplyResult(True, "Modo seguro/simulacion: control automatico restaurado")


class OmenMonFanController(FanController):
    """Backend para HP Victus/OMEN usando la herramienta externa OmenMon,
    que habla directo con el EC (Embedded Controller) via WMI/BIOS calls.
    """

    backend_name = "omenmon"

    def __init__(self, executable: str = "OmenMon.exe") -> None:
        self.executable = str(Path(executable).resolve())
        self._lock = Lock()

    @property
    def executable_path(self) -> Path:
        return Path(self.executable)

    @property
    def config_path(self) -> Path:
        return self.executable_path.with_name("OmenMon.xml")

    def _run(self, args: list[str], timeout: int = 20) -> tuple[bool, str]:
        """Ejecuta OmenMon.exe y devuelve (exito, salida combinada stdout+stderr).

        Nunca deja escapar una excepcion: un timeout o un error de SO se
        traduce en (False, mensaje) para que el llamador pueda mostrarlo tal
        cual en la UI en vez de crashear el worker thread.
        """
        try:
            proc = run_hidden(
                [self.executable, *args],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                cwd=str(self.executable_path.parent),
            )
        except subprocess.TimeoutExpired:
            return False, f"OmenMon excedio el timeout de {timeout}s"
        except OSError as ex:
            return False, str(ex)

        output = (proc.stdout or "").strip()
        error = (proc.stderr or "").strip()
        combined = "\n".join(part for part in (output, error) if part).strip()
        lowered = combined.lower()
        # OmenMon puede devolver returncode 0 incluso cuando en realidad fallo
        # (imprime la excepcion a stdout), asi que ademas del codigo de salida
        # se revisa el texto por palabras clave de error conocidas.
        error_tokens = ("exception:", "error", "failed", "access denied", "acceso denegado")
        ok = proc.returncode == 0 and not any(token in lowered for token in error_tokens)
        return ok, combined

    def _ensure_local_config(self) -> None:
        """Ajusta OmenMon.xml (si existe) para permitir control manual real de
        ventiladores en Victus/OMEN: desactiva el reporte de errores de BIOS
        y fuerza el modo de nivel manual via EC. Se edita con regex en vez de
        un parser XML completo para preservar formato/comentarios del archivo
        tal como lo genero OmenMon.
        """
        if not self.config_path.exists():
            return

        text = self.config_path.read_text(encoding="utf-8")
        replacements = {
            "BiosErrorReporting": "false",
            "FanLevelNeedManual": "true",
            "FanLevelUseEc": "true",
        }
        changed = False

        for tag, value in replacements.items():
            updated, count = re.subn(
                rf"(<{tag}>\s*)([^<]+)(\s*</{tag}>)",
                rf"\g<1>{value}\g<3>",
                text,
                count=1,
            )
            if count and updated != text:
                changed = True
                text = updated

        if changed:
            self.config_path.write_text(text, encoding="utf-8")

    def _fan_level_bounds(self) -> tuple[int, int]:
        """Rango de niveles de ventilador (unidades EC, no porcentaje) que
        OmenMon.xml define para este equipo; si no esta definido, usa un
        rango conservador (20-55) razonable para Victus/OMEN.
        """
        default_min = 20
        default_max = 55
        if not self.config_path.exists():
            return default_min, default_max

        text = self.config_path.read_text(encoding="utf-8", errors="ignore")
        min_match = re.search(r"<FanLevelMin>\s*(\d+)\s*</FanLevelMin>", text)
        max_match = re.search(r"<FanLevelMax>\s*(\d+)\s*</FanLevelMax>", text)
        min_level = int(min_match.group(1)) if min_match else default_min
        max_level = int(max_match.group(1)) if max_match else default_max

        min_level = max(0, min(min_level, 255))
        max_level = max(min_level, min(max_level, 255))
        return min_level, max_level

    def _percent_to_level(self, percent: int) -> int:
        """Convierte un porcentaje 0-100 de la UI al nivel EC real que
        OmenMon necesita, interpolando linealmente dentro de _fan_level_bounds().
        0% siempre es nivel 0 (apagado/automatico), nunca el minimo de la curva.
        """
        value = int(min(max(percent, 0), 100))
        if value <= 0:
            return 0
        min_level, max_level = self._fan_level_bounds()
        if max_level <= min_level:
            return max_level
        return int(round(min_level + ((max_level - min_level) * (value / 100.0))))

    def requires_admin_for_control(self) -> bool:
        return True

    def apply_fan_speeds(self, cpu_percent: int, gpu_percent: int) -> FanApplyResult:
        if not is_running_as_admin():
            return FanApplyResult(
                False,
                "Control real requiere ejecutar como Administrador (OmenMon/HP WMI).",
            )

        cpu = int(min(max(cpu_percent, 0), 100))
        gpu = int(min(max(gpu_percent, 0), 100))

        with self._lock:
            self._ensure_local_config()

            # 0% en ambos = volver al modo termico por defecto del equipo,
            # no "forzar nivel 0" (que dejaria los ventiladores apagados).
            if cpu == 0 and gpu == 0:
                ok, out = self._run(["-Bios", "FanMode=LegacyDefault"])
                if not ok:
                    return FanApplyResult(
                        False,
                        f"OmenMon no pudo restaurar el modo termico por defecto: {out or 'sin detalle'}",
                    )
                return FanApplyResult(True, "OmenMon restablecio el modo termico por defecto")

            cpu_level = self._percent_to_level(cpu)
            gpu_level = self._percent_to_level(gpu)

            # Se intenta primero con dos canales (CPU y GPU independientes);
            # algunos equipos solo aceptan un unico valor de FanLevel, asi que
            # si falla se reintenta con el mayor de los dos como canal unico.
            ok, out = self._run(["-Bios", f"FanLevel={cpu_level},{gpu_level}"])
            if not ok:
                fallback_level = max(cpu_level, gpu_level)
                ok, out = self._run(["-Bios", f"FanLevel={fallback_level}"])
                if not ok:
                    return FanApplyResult(False, f"OmenMon no pudo fijar velocidad: {out or 'sin detalle'}")
                return FanApplyResult(
                    True,
                    (
                        "Velocidad aplicada por OmenMon (canal unico): "
                        f"CPU {cpu}%->{fallback_level} | GPU {gpu}%->{fallback_level}"
                    ),
                )

            return FanApplyResult(
                True,
                f"Velocidad aplicada por OmenMon: CPU {cpu}%->{cpu_level} | GPU {gpu}%->{gpu_level}",
            )

    def restore_automatic_control(self) -> FanApplyResult:
        if not is_running_as_admin():
            return FanApplyResult(
                False,
                "Restaurar modo automatico requiere ejecutar como Administrador (OmenMon/HP WMI).",
            )

        with self._lock:
            self._ensure_local_config()
            ok, out = self._run(["-Bios", "FanMode=LegacyDefault"])
            if not ok:
                return FanApplyResult(
                    False,
                    f"OmenMon no pudo restaurar el modo automatico: {out or 'sin detalle'}",
                )
            return FanApplyResult(True, "OmenMon restablecio el modo automatico del sistema")


class NBFCFanController(FanController):
    """Backend para NoteBook FanControl (NBFC): habla con nbfc.exe, que a su
    vez depende del servicio Windows NbfcService. Buena parte de esta clase
    existe para detectar y recuperar el servicio cuando queda en un estado
    raro (parado, colgado, con la CLI sin responder), algo comun en NBFC.
    """

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

    def _run(self, args: list[str], timeout: int = 10) -> tuple[bool, str]:
        """Ejecuta nbfc.exe. Misma logica defensiva que OmenMonFanController._run:
        nunca deja escapar TimeoutExpired/OSError, los traduce a (False, mensaje).
        """
        cmd = [self.executable] + args
        try:
            proc = run_hidden(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False, f"NBFC excedio el timeout de {timeout}s"
        except OSError as ex:
            return False, str(ex)

        output = (proc.stdout or "").strip()
        error = (proc.stderr or "").strip()
        combined = "\n".join([line for line in (output, error) if line]).strip()
        lowered = combined.lower()

        # Igual que con OmenMon: nbfc.exe puede devolver returncode 0 y aun
        # asi haber fallado (mensaje de error en el texto), por eso se revisan
        # ademas palabras clave conocidas de fallo del servicio/CLI.
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
        """Ejecuta comandos de sistema (sc, tasklist) usados para inspeccionar
        y controlar el servicio NbfcService, no la CLI de NBFC en si."""
        try:
            proc = run_hidden(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            return proc.returncode, out
        except (OSError, subprocess.SubprocessError):
            return 1, "system command failed"

    def _query_service_info(self) -> ServiceInfo:
        """Consulta el estado actual de NbfcService via `sc queryex`.

        El regex de estado acepta tanto "STATE" (Windows en ingles) como
        "ESTADO" (Windows en espanol), ya que el texto de `sc` cambia segun
        el idioma del sistema operativo.
        """
        code, out = self._run_system(["sc", "queryex", "NbfcService"], timeout=8)
        if code != 0:
            return ServiceInfo(None, None, out)

        state_match = re.search(r"(?:STATE|ESTADO)\s*:\s*(\d+)", out, re.IGNORECASE)
        pid_match = re.search(r"\bPID\s*:\s*(\d+)", out, re.IGNORECASE)

        state_code = int(state_match.group(1)) if state_match else None
        pid = int(pid_match.group(1)) if pid_match else None
        return ServiceInfo(state_code, pid, out)

    def _list_service_process_pids(self) -> list[int]:
        """PIDs de todos los procesos NbfcService.exe corriendo (deberia haber
        como mucho uno; mas de uno indica un servicio en estado inconsistente)."""
        try:
            proc = run_hidden(
                ["tasklist", "/FI", "IMAGENAME eq NbfcService.exe", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=6,
                check=False,
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
        """Sondea el estado del servicio hasta que entre en *expected_states*
        o se agote el timeout. Se usa para esperar transiciones (parando,
        arrancando) en vez de asumir que un comando `sc` es instantaneo."""
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
        # El servicio puede reportarse RUNNING y aun asi tener el pipe de
        # comunicacion con nbfc.exe roto; por eso se hace una llamada real de
        # bajo costo (status --fan 0) en vez de confiar solo en `sc`.
        try:
            proc = run_hidden(
                [self.executable, "status", "--fan", "0"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
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
        """Deja NbfcService listo para recibir comandos antes de aplicar/leer,
        escalando gradualmente: si ya esta OK no hace nada; si esta en una
        transicion (arrancando/parando, codigos 2/3) espera a que se asiente;
        si esta parado (1) intenta arrancarlo; y si nada de eso funciona,
        recurre al reinicio forzado de _hard_reset_service().
        """
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
        """Perfiles NBFC candidatos para auto-descubrimiento: se prioriza
        cualquier perfil HP que mencione Omen/Victus; si no hay ninguno, se
        usa cualquier perfil que empiece con "HP " como segunda opcion."""
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
        """Prueba *profile* aplicando la velocidad pedida y verificando que
        NBFC realmente tome control (no quede en auto y el target sea > 0).
        Si funciona, deja ese perfil activo en self.profile."""
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
        """Prueba cada perfil candidato hasta encontrar uno que este equipo
        realmente acepte, para no depender de que el usuario conozca el
        nombre exacto del perfil NBFC de su modelo."""
        if not self.autodiscover_profile:
            return False
        for profile in self._candidate_profiles():
            ok, _ = self._try_profile(profile, requested)
            if ok:
                return True
        return False

    def _read_status(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """Lee (auto_control_habilitado, velocidad_actual, velocidad_objetivo)
        parseando la salida de texto de `nbfc status --fan 0`."""
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

    def requires_admin_for_control(self) -> bool:
        return True

    def apply_fan_speeds(self, cpu_percent: int, gpu_percent: int) -> FanApplyResult:
        if not is_running_as_admin():
            return FanApplyResult(
                False,
                "Control real requiere ejecutar como Administrador (NBFC service/WMI).",
            )

        cpu = int(min(max(cpu_percent, 0), 100))
        gpu = int(min(max(gpu_percent, 0), 100))
        # NBFC controla un unico ventilador logico (indice 0): se usa el mayor
        # de CPU/GPU pedido para no quedar por debajo de lo que el usuario
        # necesita en cualquiera de los dos componentes.
        requested = max(cpu, gpu)

        with self._lock:
            if not self._ensure_service_ready():
                return FanApplyResult(
                    False,
                    "NBFC service no queda operativo. Intenta Reparar NBFC y valida permisos de Administrador.",
                )

            ok, out = self._run(["config", "--set", self.profile])
            if (not ok) and ("service is unavailable" in out.lower()):
                # El servicio se cayo entre _ensure_service_ready() y este
                # comando: se intenta una reparacion completa antes de rendirse.
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
                    # Error de Windows 232 = "el pipe se esta cerrando": sintoma
                    # tipico de NbfcService en mal estado, mensaje mas claro que
                    # el codigo crudo.
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

            # Si el perfil configurado no aplica realmente a este equipo, NBFC
            # se queda en auto-control o con target 0: se intenta descubrir un
            # perfil que si funcione antes de reportar el fallo al usuario.
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

    def restore_automatic_control(self) -> FanApplyResult:
        if not is_running_as_admin():
            return FanApplyResult(
                False,
                "Restaurar modo automatico requiere ejecutar como Administrador (NBFC service/WMI).",
            )

        with self._lock:
            if not self._ensure_service_ready():
                return FanApplyResult(False, "NBFC service no queda operativo para restaurar modo automatico.")

            ok, out = self._run(["config", "--set", self.profile])
            if not ok:
                return FanApplyResult(False, f"NBFC no pudo fijar perfil para restaurar auto: {out or 'sin detalle'}")

            ok, out = self._run(["set", "--fan", "0", "--auto"], timeout=7)
            if not ok:
                return FanApplyResult(False, f"NBFC no pudo restaurar auto-control: {out or 'sin detalle'}")

            return FanApplyResult(True, "NBFC restablecio el auto-control del ventilador")

    def diagnosticar_nbfc(self) -> str:
        """Genera un reporte de texto legible (para el boton "Diagnostico NBFC"
        de la UI) con el estado del servicio, la CLI y los perfiles disponibles."""
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
        """Reinicio "duro" de NbfcService: para el servicio (matando el
        proceso a la fuerza si no responde a `sc stop`), espera, lo vuelve a
        arrancar y confirma que la CLI responde. Devuelve un reporte paso a
        paso para mostrarlo en el boton "Reparar NBFC" de la UI.
        Requiere llamarse con self._lock ya tomado por el metodo publico.
        """
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
                # `sc stop` no fue suficiente (servicio colgado): se fuerza el
                # cierre del proceso, primero por PID conocido y despues por
                # nombre de imagen como red de seguridad.
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
    """Backend generico: ejecuta comandos externos definidos por el usuario en
    config.json (fan_command_cpu/fan_command_gpu), con "{value}" reemplazado
    por el porcentaje 0-100. Util para equipos sin OmenMon ni NBFC pero con
    alguna otra herramienta de linea de comandos para controlar ventiladores.
    """

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

        # shlex.split raises ValueError on malformed shell syntax
        try:
            cpu_cmd = shlex.split(self._cpu_template.format(value=cpu))
            gpu_cmd = shlex.split(self._gpu_template.format(value=gpu))
        except ValueError as ex:
            return FanApplyResult(False, f"Plantilla de comando invalida: {ex}")

        with self._lock:
            for cmd in (cpu_cmd, gpu_cmd):
                try:
                    proc = run_hidden(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                except (OSError, subprocess.SubprocessError) as ex:
                    return FanApplyResult(False, f"Error ejecutando comando: {ex}")
                if proc.returncode != 0:
                    stderr = proc.stderr.strip() or proc.stdout.strip() or "sin detalle"
                    return FanApplyResult(False, f"Comando fallo: {stderr}")

        return FanApplyResult(True, f"Velocidades aplicadas por comando: CPU {cpu}% | GPU {gpu}%")

    def restore_automatic_control(self) -> FanApplyResult:
        return FanApplyResult(True, "Backend command: sin restauracion automatica explicita")


def build_fan_controller(config: AppConfig) -> FanController:
    """Fabrica el FanController activo segun config.fan_backend.

    Con "auto", prioriza OmenMon (mejor soporte HP Victus/OMEN), luego NBFC,
    luego un comando custom si esta configurado; si nada esta disponible,
    devuelve un UnavailableFanController con un mensaje explicando que falta.
    """
    omenmon_path = find_omenmon_executable(config.omenmon_executable)
    nbfc_path = find_nbfc_executable(config.nbfc_executable)

    if config.fan_backend == "mock":
        return MockHPVictusFanController()

    if config.fan_backend == "omenmon":
        if omenmon_path:
            return OmenMonFanController(omenmon_path)
        return UnavailableFanController(
            "omenmon",
            "OmenMon.exe no encontrado. Ejecuta install_omenmon_local.ps1 o configura omenmon_executable.",
        )

    if config.fan_backend == "nbfc":
        if nbfc_path:
            return NBFCFanController(
                nbfc_path,
                profile=config.nbfc_profile,
                autodiscover_profile=config.nbfc_autodiscover_profile,
            )
        return UnavailableFanController(
            "nbfc",
            "nbfc.exe no encontrado. Instala NBFC o ajusta nbfc_executable.",
        )

    if config.fan_backend == "command":
        return CommandTemplateFanController(config.fan_command_cpu, config.fan_command_gpu)

    if omenmon_path:
        return OmenMonFanController(omenmon_path)

    if nbfc_path:
        return NBFCFanController(
            nbfc_path,
            profile=config.nbfc_profile,
            autodiscover_profile=config.nbfc_autodiscover_profile,
        )

    if config.fan_command_cpu.strip() and config.fan_command_gpu.strip():
        return CommandTemplateFanController(config.fan_command_cpu, config.fan_command_gpu)

    return UnavailableFanController(
        "auto",
        "No se encontro un backend compatible. Instala OmenMon o NBFC, o configura fan_command_cpu/fan_command_gpu.",
    )


def find_omenmon_executable(config_value: str = "auto") -> str | None:
    """Localiza OmenMon.exe: ruta configurada explicitamente, carpeta local
    del proyecto/`.exe`, tools/omenmon/, o finalmente el PATH del sistema."""
    if config_value and config_value.strip().lower() != "auto":
        custom = Path(config_value.strip())
        if custom.exists():
            return str(custom)

    base = get_base_path()
    local_candidates = [
        base / "OmenMon.exe",
        base / "tools" / "omenmon" / "OmenMon.exe",
    ]
    for candidate in local_candidates:
        if candidate.exists():
            return str(candidate)

    from_path = shutil.which("OmenMon.exe")
    if from_path:
        return from_path

    return None


def find_nbfc_executable(config_value: str = "auto") -> str | None:
    """Localiza nbfc.exe: ruta configurada explicitamente, el binario del
    propio servicio NbfcService instalado, rutas locales conocidas, PATH, o
    finalmente las rutas de instalacion por defecto de NBFC en Program Files."""
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
    """Deriva la ruta de nbfc.exe a partir de donde esta instalado el
    servicio NbfcService (`sc qc`), asumiendo que el CLI vive junto al
    binario del servicio. Mas confiable que asumir una ruta fija."""
    try:
        proc = run_hidden(
            ["sc", "qc", "NbfcService"],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
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
    """True si el proceso actual corre elevado (Administrador de Windows).

    Todos los backends reales (OmenMon, NBFC) lo requieren para poder escribir
    en el EC/hardware; la UI usa esto para bloquear controles preventivamente
    en vez de dejar que el usuario intente y reciba un error de permisos.
    """
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False
