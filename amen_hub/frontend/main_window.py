from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Any

from amen_hub.backend import build_fan_controller
from amen_hub.backend import is_running_as_admin
from amen_hub.backend.fan_controller import find_omenmon_executable
from amen_hub.backend.fan_controller import find_nbfc_executable
from amen_hub.backend.telemetry import TemperatureService
from amen_hub.config import ConfigManager
from amen_hub.logger import setup_logger
from amen_hub.version import APP_VERSION_TAG


class MainWindow:
    AUTO_FAN_CURVE = (
        (35.0, 20),
        (45.0, 25),
        (55.0, 35),
        (65.0, 50),
        (72.0, 65),
        (78.0, 75),
        (84.0, 85),
        (90.0, 100),
    )

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.logger = setup_logger()
        self.config_manager = ConfigManager()
        self._nbfc_path = find_nbfc_executable(self.config_manager.config.nbfc_executable)
        self._omenmon_path = find_omenmon_executable(self.config_manager.config.omenmon_executable)
        self.controller = build_fan_controller(self.config_manager.config)
        self.telemetry = TemperatureService(self._nbfc_path, self._omenmon_path)
        self.ui_queue: queue.Queue[Any] = queue.Queue()

        self._countdown_remaining = 0
        self._countdown_job: str | None = None
        self._telemetry_job: str | None = None
        self._live_apply_job: str | None = None
        self._telemetry_inflight = False
        self._live_apply_inflight = False
        self._suspend_live_change = False
        self._manual_cpu_percent = int(self.config_manager.config.cpu_fan_percent)
        self._manual_gpu_percent = int(self.config_manager.config.gpu_fan_percent)
        self._pending_live_apply_targets: tuple[int, int] | None = None
        self._last_live_apply_targets: tuple[int, int] | None = None
        self._auto_mode_enabled = bool(self.config_manager.config.fan_auto_mode)
        self._last_auto_targets: tuple[int, int] | None = None
        self._last_auto_apply_at = 0.0
        self._last_auto_status = ""
        self._base_status = "Listo"

        self.root.title(f"Amen Gaming Hub {APP_VERSION_TAG}")
        self.root.geometry(self.config_manager.config.window_geometry)
        self.root.minsize(980, 620)
        self.root.protocol("WM_DELETE_WINDOW", self._on_exit)

        self._configure_theme()
        self._build_variables()
        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()
        self._load_state()

        self.root.after(100, self._drain_queue)
        self.root.after(250, self._ensure_countdown_state)
        self._telemetry_async()
        if not is_running_as_admin():
            self._set_status(
                f"Backend activo: {self.controller.describe()} | Ejecuta como Administrador para control real y CPU temp",
            )
        else:
            self._set_status(f"Backend activo: {self.controller.describe()}")

        if self.autostart_var.get():
            self._apply_async()

    def _configure_theme(self) -> None:
        self.root.configure(bg="#0a0f14")
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure("Root.TFrame", background="#0a0f14")
        style.configure("Card.TFrame", background="#121a22")
        style.configure("Card.TLabelframe", background="#121a22", foreground="#f2f6ff", bordercolor="#1f2a36")
        style.configure("Card.TLabelframe.Label", background="#121a22", foreground="#7de3b6")
        style.configure("Title.TLabel", background="#0a0f14", foreground="#e6f7ff", font=("Segoe UI Semibold", 23))
        style.configure("SubTitle.TLabel", background="#0a0f14", foreground="#6fb7de", font=("Segoe UI", 11))
        style.configure("Value.TLabel", background="#121a22", foreground="#9ee7ff", font=("Consolas", 13, "bold"))
        style.configure("Status.TLabel", background="#0f141b", foreground="#7de3b6", borderwidth=1, relief="solid")
        style.configure("TLabel", background="#121a22", foreground="#d9e8ff")
        style.configure("TCheckbutton", background="#121a22", foreground="#d9e8ff")
        style.map("TCheckbutton", background=[("active", "#121a22")])

        style.configure("Accent.Horizontal.TScale", background="#121a22", troughcolor="#293644")
        style.configure("Action.TButton", background="#00a564", foreground="white", padding=(12, 7), borderwidth=0)
        style.map("Action.TButton", background=[("active", "#00be73"), ("disabled", "#3d5b50")])
        style.configure("Danger.TButton", background="#b02f3c", foreground="white", padding=(12, 7), borderwidth=0)
        style.map("Danger.TButton", background=[("active", "#ca3a49")])

    def _build_variables(self) -> None:
        cfg = self.config_manager.config
        self.cpu_var = tk.IntVar(value=cfg.cpu_fan_percent)
        self.gpu_var = tk.IntVar(value=cfg.gpu_fan_percent)
        self.auto_fan_var = tk.BooleanVar(value=cfg.fan_auto_mode)
        self.live_apply_var = tk.BooleanVar(value=cfg.live_apply_enabled)
        self.restore_auto_on_exit_var = tk.BooleanVar(value=cfg.restore_auto_on_exit)
        self.autostart_var = tk.BooleanVar(value=cfg.autostart_process)
        self.autoclose_enabled_var = tk.BooleanVar(value=cfg.autoclose_enabled)
        self.autoclose_seconds_var = tk.IntVar(value=cfg.autoclose_seconds)
        self.password_var = tk.StringVar(value=cfg.app_password)
        self.backend_var = tk.StringVar(value=cfg.fan_backend)
        self.nbfc_profile_var = tk.StringVar(value=cfg.nbfc_profile)
        self.show_password_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Listo")
        self.cpu_temp_var = tk.StringVar(value="--.- °C")
        self.gpu_temp_var = tk.StringVar(value="--.- °C")

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)

        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Aplicar", accelerator="Ctrl+Enter", command=self._apply_async)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", accelerator="Alt+F4", command=self._on_exit)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About", accelerator="F1", command=self._show_about)

        menu.add_cascade(label="Archivo", menu=file_menu, underline=0)
        menu.add_cascade(label="Ayuda", menu=help_menu, underline=0)
        self.root.config(menu=menu)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=16, style="Root.TFrame")
        container.pack(fill="both", expand=True)

        title = ttk.Label(container, text=f"Amen Gaming Hub {APP_VERSION_TAG}", style="Title.TLabel")
        title.pack(anchor="w", pady=(0, 2))
        subtitle = ttk.Label(container, text="Control Termico y Potencia", style="SubTitle.TLabel")
        subtitle.pack(anchor="w", pady=(0, 12))

        top_row = ttk.Frame(container, style="Root.TFrame")
        top_row.pack(fill="x", pady=(0, 10))

        temp_card = ttk.LabelFrame(top_row, text="Temperaturas (°C)", style="Card.TLabelframe")
        temp_card.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.cpu_temp_canvas, self.cpu_temp_label = self._build_temp_meter(temp_card, "CPU", self.cpu_temp_var)
        self.cpu_temp_canvas.grid(row=0, column=0, padx=24, pady=16)

        self.gpu_temp_canvas, self.gpu_temp_label = self._build_temp_meter(temp_card, "GPU", self.gpu_temp_var)
        self.gpu_temp_canvas.grid(row=0, column=1, padx=24, pady=16)

        speed_card = ttk.LabelFrame(top_row, text="Ventiladores", style="Card.TLabelframe")
        speed_card.pack(side="left", fill="both", expand=True, padx=(8, 0))

        ttk.Label(speed_card, text="Dial FAN CPU").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self.cpu_scale = ttk.Scale(
            speed_card,
            from_=0,
            to=100,
            orient="horizontal",
            command=lambda _v: self._on_live_change(),
            variable=self.cpu_var,
            style="Accent.Horizontal.TScale",
        )
        self.cpu_scale.grid(row=1, column=0, sticky="ew", padx=12)
        self.cpu_value_label = ttk.Label(speed_card, text=f"{self.cpu_var.get()}%", style="Value.TLabel")
        self.cpu_value_label.grid(row=2, column=0, sticky="e", padx=12, pady=(4, 12))

        ttk.Label(speed_card, text="Dial FAN GPU").grid(row=3, column=0, sticky="w", padx=12, pady=(8, 4))
        self.gpu_scale = ttk.Scale(
            speed_card,
            from_=0,
            to=100,
            orient="horizontal",
            command=lambda _v: self._on_live_change(),
            variable=self.gpu_var,
            style="Accent.Horizontal.TScale",
        )
        self.gpu_scale.grid(row=4, column=0, sticky="ew", padx=12)
        self.gpu_value_label = ttk.Label(speed_card, text=f"{self.gpu_var.get()}%", style="Value.TLabel")
        self.gpu_value_label.grid(row=5, column=0, sticky="e", padx=12, pady=(4, 12))
        speed_card.columnconfigure(0, weight=1)

        options = ttk.LabelFrame(container, text="Opciones", style="Card.TLabelframe")
        options.pack(fill="x", pady=(0, 10))

        self.autostart_check = ttk.Checkbutton(
            options,
            text="Autoiniciar proceso al abrir",
            variable=self.autostart_var,
            command=self._on_live_change,
        )
        self.autostart_check.grid(row=0, column=0, sticky="w", padx=10, pady=6)

        self.auto_fan_check = ttk.Checkbutton(
            options,
            text="Modo auto termico",
            variable=self.auto_fan_var,
            command=self._on_auto_mode_changed,
        )
        self.auto_fan_check.grid(row=0, column=5, sticky="w", padx=(0, 10), pady=6)

        self.live_apply_check = ttk.Checkbutton(
            options,
            text="Aplicar en vivo",
            variable=self.live_apply_var,
            command=self._on_live_apply_option_changed,
        )
        self.live_apply_check.grid(row=1, column=5, sticky="w", padx=(0, 10), pady=6)

        self.restore_auto_check = ttk.Checkbutton(
            options,
            text="Volver a auto al salir",
            variable=self.restore_auto_on_exit_var,
            command=self._on_live_change,
        )
        self.restore_auto_check.grid(row=2, column=5, sticky="w", padx=(0, 10), pady=(6, 10))

        self.autoclose_check = ttk.Checkbutton(
            options,
            text="Autocerrar",
            variable=self.autoclose_enabled_var,
            command=self._on_live_change,
        )
        self.autoclose_check.grid(row=1, column=0, sticky="w", padx=10, pady=6)

        ttk.Label(options, text="Segundos autocierre:").grid(row=1, column=1, sticky="e", padx=(10, 4))
        self.autoclose_spin = ttk.Spinbox(
            options,
            from_=5,
            to=3600,
            textvariable=self.autoclose_seconds_var,
            width=8,
            command=self._on_live_change,
        )
        self.autoclose_spin.grid(row=1, column=2, sticky="w", padx=(0, 14))

        ttk.Label(options, text="Backend ventiladores:").grid(row=0, column=1, sticky="e", padx=(10, 4))
        self.backend_combo = ttk.Combobox(
            options,
            textvariable=self.backend_var,
            values=["auto", "omenmon", "nbfc", "command", "mock"],
            state="readonly",
            width=12,
        )
        self.backend_combo.grid(row=0, column=2, sticky="w", padx=(0, 14), pady=6)
        self.backend_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_backend_changed())

        ttk.Label(options, text="Perfil NBFC:").grid(row=0, column=3, sticky="e", padx=(10, 4))
        self.nbfc_profile_entry = ttk.Entry(options, textvariable=self.nbfc_profile_var, width=26)
        self.nbfc_profile_entry.grid(row=0, column=4, sticky="w", padx=(0, 14), pady=6)

        ttk.Label(options, text="Password (opcional):").grid(row=2, column=0, sticky="w", padx=10, pady=(6, 10))
        self.password_entry = ttk.Entry(options, textvariable=self.password_var, show="*")
        self.password_entry.grid(row=2, column=1, sticky="ew", padx=(10, 4), pady=(6, 10))
        self.toggle_pass_button = ttk.Button(options, text="Mostrar", command=self._toggle_password)
        self.toggle_pass_button.grid(row=2, column=2, sticky="w", padx=(0, 10), pady=(6, 10))

        options.columnconfigure(1, weight=1)
        options.columnconfigure(4, weight=1)

        actions = ttk.Frame(container, style="Root.TFrame")
        actions.pack(fill="x", pady=(0, 8))

        self.apply_button = ttk.Button(actions, text="Aplicar", command=self._apply_async, style="Action.TButton")
        self.apply_button.pack(side="left")

        self.repair_button = ttk.Button(actions, text="Reparar NBFC", command=self._repair_nbfc, style="Accent.Horizontal.TScale")
        self.repair_button.pack(side="left", padx=(8, 0))

        self.diagnose_button = ttk.Button(actions, text="Diagnóstico NBFC", command=self._diagnose_nbfc, style="Accent.Horizontal.TScale")
        self.diagnose_button.pack(side="left", padx=(8, 0))

        self.exit_button = ttk.Button(actions, text="Salir", command=self._on_exit, style="Danger.TButton")
        self.exit_button.pack(side="left", padx=(8, 0))

        # Barra de estado
        status = ttk.Label(container, textvariable=self.status_var, anchor="w", style="Status.TLabel", padding=(10, 6))
        status.pack(fill="x", side="bottom", pady=(6, 0), ipady=4)

    def _diagnose_nbfc(self) -> None:
        self.diagnose_button.configure(state="disabled")
        self._set_status("Ejecutando diagnóstico NBFC...")

        def worker():
            try:
                from amen_hub.backend.fan_controller import NBFCFanController
                if isinstance(self.controller, NBFCFanController):
                    report = self.controller.diagnosticar_nbfc()
                else:
                    report = "El backend activo no es NBFC. Cambia a NBFC para diagnóstico."
                self.ui_queue.put(("__diagnose__", report))
            except Exception as ex:
                self.ui_queue.put(("__diagnose__", f"Error en diagnóstico: {ex}"))
            finally:
                self.ui_queue.put("__enable_diagnose__")

        threading.Thread(target=worker, daemon=True).start()


    def _repair_nbfc(self) -> None:
        self.repair_button.configure(state="disabled")
        self._set_status("Intentando reparar NBFC...")

        def worker():
            try:
                from amen_hub.backend.fan_controller import NBFCFanController
                if isinstance(self.controller, NBFCFanController):
                    repaired, report = self.controller.repair_nbfc_service_with_report()
                    msg = report
                else:
                    repaired = False
                    msg = "El backend activo no es NBFC. Cambia a NBFC para reparar."
                self.ui_queue.put(msg)
            except Exception as ex:
                self.ui_queue.put(f"Error al reparar NBFC: {ex}")
            finally:
                self.ui_queue.put("__enable_repair__")

        threading.Thread(target=worker, daemon=True).start()

    def _drain_queue(self) -> None:
        while not self.ui_queue.empty():
            msg = self.ui_queue.get_nowait()
            if msg == "__enable_apply__":
                self._refresh_auto_mode_ui()
                continue
            if msg == "__enable_repair__":
                self.repair_button.configure(state="normal")
                continue
            if msg == "__enable_diagnose__":
                self.diagnose_button.configure(state="normal")
                continue
            if isinstance(msg, tuple) and msg[0] == "__temps__":
                self._render_temps(msg[1], msg[2])
                continue
            if msg == "__telemetry_done__":
                self._telemetry_inflight = False
                continue
            if isinstance(msg, tuple) and msg[0] == "__live_apply_done__":
                self._handle_live_apply_done(msg[1], msg[2], msg[3], msg[4])
                continue
            if isinstance(msg, tuple) and msg[0] == "__auto__":
                self._handle_auto_update(msg[1], msg[2], msg[3])
                continue
            if isinstance(msg, tuple) and msg[0] == "__diagnose__":
                self._show_diagnose_popup(msg[1])
                self._set_status("Diagnóstico NBFC completado. Haz clic en el botón para ver detalles.")
                continue
            self._set_status(str(msg))
        self.root.after(120, self._drain_queue)

    def _show_diagnose_popup(self, report: str) -> None:
        popup = tk.Toplevel(self.root)
        popup.title("Diagnóstico NBFC")
        popup.geometry("700x500")
        popup.configure(bg="#181f24")
        txt = tk.Text(popup, wrap="word", bg="#181f24", fg="#e6f7ff", font=("Consolas", 10))
        txt.insert("1.0", report)
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        btn = ttk.Button(popup, text="Cerrar", command=popup.destroy)
        btn.pack(pady=8)


    def _build_temp_meter(self, parent: ttk.LabelFrame, name: str, variable: tk.StringVar) -> tuple[tk.Canvas, ttk.Label]:
        canvas = tk.Canvas(parent, width=158, height=158, bg="#121a22", highlightthickness=0)
        canvas.create_oval(18, 18, 140, 140, outline="#223244", width=8, tags="ring")
        canvas.create_arc(18, 18, 140, 140, start=90, extent=0, style="arc", outline="#f5455c", width=10, tags="arc")
        canvas.create_text(79, 70, text=name, fill="#8fbdd8", font=("Segoe UI", 11, "bold"), tags="name")
        canvas.create_text(79, 95, text=variable.get(), fill="#f3f8ff", font=("Consolas", 14, "bold"), tags="value")
        label = ttk.Label(parent, text=f"{name}: {variable.get()}", style="Value.TLabel")
        label.grid_remove()
        return canvas, label

    def _bind_shortcuts(self) -> None:
        self.root.bind_all("<Control-Return>", lambda _e: self._apply_async())
        self.root.bind_all("<Alt-a>", lambda _e: self._apply_async())
        self.root.bind_all("<Alt-s>", lambda _e: self._on_exit())
        self.root.bind_all("<F1>", lambda _e: self._show_about())

        self.cpu_var.trace_add("write", lambda *_: self._on_live_change())
        self.gpu_var.trace_add("write", lambda *_: self._on_live_change())
        self.autoclose_seconds_var.trace_add("write", lambda *_: self._on_live_change())
        self.password_var.trace_add("write", lambda *_: self._on_live_change())
        self.nbfc_profile_var.trace_add("write", lambda *_: self._on_live_change())

    def _load_state(self) -> None:
        self._update_value_labels()
        self._refresh_auto_mode_ui()
        self._save_config()

    def _on_live_change(self) -> None:
        if self._suspend_live_change:
            self._update_value_labels()
            return
        if not self.auto_fan_var.get():
            self._manual_cpu_percent = int(self.cpu_var.get())
            self._manual_gpu_percent = int(self.gpu_var.get())
        self._update_value_labels()
        self._save_config()
        self._ensure_countdown_state()
        self._schedule_live_apply()

    def _update_value_labels(self) -> None:
        self.cpu_value_label.configure(text=f"{int(self.cpu_var.get())}%")
        self.gpu_value_label.configure(text=f"{int(self.gpu_var.get())}%")

    def _toggle_password(self) -> None:
        showing = not self.show_password_var.get()
        self.show_password_var.set(showing)
        self.password_entry.configure(show="" if showing else "*")
        self.toggle_pass_button.configure(text="Ocultar" if showing else "Mostrar")
        self._set_status("Cambio de visibilidad de password")

    def _on_backend_changed(self) -> None:
        self._save_config()
        self._nbfc_path = find_nbfc_executable(self.config_manager.config.nbfc_executable)
        self._omenmon_path = find_omenmon_executable(self.config_manager.config.omenmon_executable)
        self.controller = build_fan_controller(self.config_manager.config)
        self.telemetry = TemperatureService(self._nbfc_path, self._omenmon_path)
        self._set_status(f"Backend cambiado a: {self.controller.describe()}")
        if self.auto_fan_var.get():
            self._telemetry_async()

    def _on_auto_mode_changed(self) -> None:
        self._auto_mode_enabled = bool(self.auto_fan_var.get())
        self._last_auto_targets = None
        self._last_auto_apply_at = 0.0
        self._last_auto_status = ""
        self._cancel_live_apply()
        self._refresh_auto_mode_ui()
        if self._auto_mode_enabled:
            self._set_status("Modo auto termico activo. La app ajustara ventiladores segun la temperatura.")
            self._save_config()
            self._telemetry_async()
            return

        self._set_display_fan_values(self._manual_cpu_percent, self._manual_gpu_percent)
        self._save_config()
        self._set_status("Modo auto termico desactivado. Controles manuales restaurados.")

    def _on_live_apply_option_changed(self) -> None:
        self._save_config()
        self._refresh_auto_mode_ui()
        if self.live_apply_var.get():
            self._set_status("Aplicacion en vivo activada.")
            self._schedule_live_apply()
            return
        self._cancel_live_apply()
        self._set_status("Aplicacion en vivo desactivada.")

    def _refresh_auto_mode_ui(self) -> None:
        auto_enabled = bool(self.auto_fan_var.get())
        if auto_enabled:
            self.cpu_scale.state(["disabled"])
            self.gpu_scale.state(["disabled"])
            self.apply_button.configure(state="disabled")
            self.live_apply_check.state(["disabled"])
            return

        self.cpu_scale.state(["!disabled"])
        self.gpu_scale.state(["!disabled"])
        self.live_apply_check.state(["!disabled"])
        self.apply_button.configure(state="normal")

    def _save_config(self) -> None:
        try:
            autoclose_secs = int(self.autoclose_seconds_var.get())
        except (TypeError, ValueError):
            autoclose_secs = 60
            self.autoclose_seconds_var.set(autoclose_secs)

        self.config_manager.update(
            cpu_fan_percent=int(self._manual_cpu_percent),
            gpu_fan_percent=int(self._manual_gpu_percent),
            fan_auto_mode=bool(self.auto_fan_var.get()),
            live_apply_enabled=bool(self.live_apply_var.get()),
            restore_auto_on_exit=bool(self.restore_auto_on_exit_var.get()),
            autostart_process=bool(self.autostart_var.get()),
            autoclose_enabled=bool(self.autoclose_enabled_var.get()),
            autoclose_seconds=autoclose_secs,
            app_password=self.password_var.get(),
            fan_backend=self.backend_var.get(),
            nbfc_profile=self.nbfc_profile_var.get(),
            window_geometry=self.root.geometry(),
        )

    def _apply_async(self) -> None:
        if self.auto_fan_var.get():
            self._set_status("Modo auto termico activo. Desactivalo si quieres aplicar valores manuales.")
            return

        self.apply_button.configure(state="disabled")
        self._set_status("Aplicando velocidades de ventilador...")

        cpu = int(self.cpu_var.get())
        gpu = int(self.gpu_var.get())

        thread = threading.Thread(
            target=self._worker_apply,
            args=(cpu, gpu, False),
            name="FanApplyWorker",
            daemon=True,
        )
        thread.start()

    def _worker_apply(self, cpu: int, gpu: int, live_apply: bool = False) -> None:
        try:
            result = self.controller.apply_fan_speeds(cpu, gpu)
            now = datetime.now().strftime("%H:%M:%S")
            if result.ok:
                self.logger.info(result.message)
                if live_apply:
                    self.ui_queue.put(("__live_apply_done__", cpu, gpu, True, f"{result.message} | {now}"))
                else:
                    self.ui_queue.put(f"{result.message} | {now}")
            else:
                self.logger.warning(result.message)
                if live_apply:
                    self.ui_queue.put(("__live_apply_done__", cpu, gpu, False, f"No aplicado: {result.message} | {now}"))
                else:
                    self.ui_queue.put(f"No aplicado: {result.message} | {now}")
        except Exception as ex:  # noqa: BLE001
            self.logger.exception("Error applying fan speeds: %s", ex)
            if live_apply:
                self.ui_queue.put(("__live_apply_done__", cpu, gpu, False, f"Error inesperado: {ex}"))
            else:
                self.ui_queue.put(f"Error inesperado: {ex}")
        finally:
            if not live_apply:
                self.ui_queue.put("__enable_apply__")

    def _schedule_telemetry(self) -> None:
        interval = max(1, int(self.config_manager.config.telemetry_interval_seconds))
        self._telemetry_job = self.root.after(interval * 1000, self._telemetry_async)

    def _telemetry_async(self) -> None:
        if self._telemetry_inflight:
            self._schedule_telemetry()
            return
        self._telemetry_inflight = True
        thread = threading.Thread(target=self._worker_telemetry, name="TelemetryWorker", daemon=True)
        thread.start()
        self._schedule_telemetry()

    def _worker_telemetry(self) -> None:
        try:
            reading = self.telemetry.read()
            self.ui_queue.put(("__temps__", reading.cpu_c, reading.gpu_c))
            auto_payload = self._evaluate_auto_mode(reading.cpu_c, reading.gpu_c)
            if auto_payload is not None:
                self.ui_queue.put(("__auto__", auto_payload[0], auto_payload[1], auto_payload[2]))
        finally:
            self.ui_queue.put("__telemetry_done__")

    def _render_temps(self, cpu_c: float | None, gpu_c: float | None) -> None:
        self._update_meter(self.cpu_temp_canvas, cpu_c, self.cpu_temp_var)
        self._update_meter(self.gpu_temp_canvas, gpu_c, self.gpu_temp_var)

    def _update_meter(self, canvas: tk.Canvas, temp_c: float | None, var: tk.StringVar) -> None:
        if temp_c is None:
            value_text = "--.- °C"
            ratio = 0
        else:
            value_text = f"{temp_c:.1f} °C"
            ratio = min(max(temp_c / 100.0, 0.0), 1.0)

        var.set(value_text)
        extent = -int(360 * ratio)
        color = "#46d483" if ratio < 0.65 else "#ffb347" if ratio < 0.82 else "#ff5f6d"
        canvas.itemconfigure("arc", extent=extent, outline=color)
        canvas.itemconfigure("value", text=value_text)

    def _set_display_fan_values(self, cpu_percent: int, gpu_percent: int) -> None:
        self._suspend_live_change = True
        try:
            self.cpu_var.set(int(min(max(cpu_percent, 0), 100)))
            self.gpu_var.set(int(min(max(gpu_percent, 0), 100)))
        finally:
            self._suspend_live_change = False
        self._update_value_labels()

    def _handle_auto_update(self, cpu_percent: int | None, gpu_percent: int | None, status_text: str | None) -> None:
        if not self.auto_fan_var.get():
            return
        if cpu_percent is not None and gpu_percent is not None:
            self._set_display_fan_values(cpu_percent, gpu_percent)
        if status_text:
            self._set_status(status_text)

    def _schedule_live_apply(self) -> None:
        if self.auto_fan_var.get() or not self.live_apply_var.get():
            return

        self._pending_live_apply_targets = (int(self.cpu_var.get()), int(self.gpu_var.get()))
        if self._live_apply_job is not None:
            self.root.after_cancel(self._live_apply_job)
        self._live_apply_job = self.root.after(180, self._flush_live_apply)

    def _cancel_live_apply(self) -> None:
        if self._live_apply_job is not None:
            self.root.after_cancel(self._live_apply_job)
            self._live_apply_job = None
        self._pending_live_apply_targets = None

    def _flush_live_apply(self) -> None:
        self._live_apply_job = None
        if self.auto_fan_var.get() or not self.live_apply_var.get() or self._live_apply_inflight:
            return

        targets = self._pending_live_apply_targets
        if targets is None or targets == self._last_live_apply_targets:
            return

        self._live_apply_inflight = True
        thread = threading.Thread(
            target=self._worker_apply,
            args=(targets[0], targets[1], True),
            name="LiveFanApplyWorker",
            daemon=True,
        )
        thread.start()

    def _handle_live_apply_done(self, cpu: int, gpu: int, ok: bool, message: str) -> None:
        self._live_apply_inflight = False
        if ok:
            self._last_live_apply_targets = (cpu, gpu)
        self._set_status(message)

        if self.auto_fan_var.get() or not self.live_apply_var.get():
            return

        if self._pending_live_apply_targets is not None and self._pending_live_apply_targets != self._last_live_apply_targets:
            self._schedule_live_apply()

    def _evaluate_auto_mode(self, cpu_c: float | None, gpu_c: float | None) -> tuple[int | None, int | None, str | None] | None:
        if not self._auto_mode_enabled:
            return None

        targets = self._calculate_auto_targets(cpu_c, gpu_c)
        if targets is None:
            status = "Modo auto termico activo. Esperando telemetria de temperatura."
            return None, None, self._dedupe_auto_status(status)

        cpu_target, gpu_target = targets
        status = (
            "Modo auto termico: "
            f"CPU {self._format_temp(cpu_c)} -> {cpu_target}% | "
            f"GPU {self._format_temp(gpu_c)} -> {gpu_target}%"
        )

        if not is_running_as_admin():
            return cpu_target, gpu_target, self._dedupe_auto_status(status + " | requiere Administrador para aplicar")

        desired = (cpu_target, gpu_target)
        cooldown_s = max(3.0, float(self.config_manager.config.telemetry_interval_seconds))
        should_apply = self._last_auto_targets != desired and (
            self._last_auto_targets is None or (time.monotonic() - self._last_auto_apply_at) >= cooldown_s
        )

        if should_apply:
            result = self.controller.apply_fan_speeds(cpu_target, gpu_target)
            if result.ok:
                self._last_auto_targets = desired
                self._last_auto_apply_at = time.monotonic()
                return cpu_target, gpu_target, self._dedupe_auto_status(status + " | aplicado")
            return cpu_target, gpu_target, self._dedupe_auto_status(f"Modo auto no pudo aplicar: {result.message}")

        if self._last_auto_targets is None:
            return cpu_target, gpu_target, self._dedupe_auto_status(status + " | calculado")
        return cpu_target, gpu_target, self._dedupe_auto_status(status + " | manteniendo curva")

    def _calculate_auto_targets(self, cpu_c: float | None, gpu_c: float | None) -> tuple[int, int] | None:
        available = [temp for temp in (cpu_c, gpu_c) if temp is not None]
        if not available:
            return None

        fallback_temp = max(available)
        cpu_target = self._curve_to_percent(cpu_c if cpu_c is not None else fallback_temp)
        gpu_target = self._curve_to_percent(gpu_c if gpu_c is not None else fallback_temp)
        return cpu_target, gpu_target

    def _curve_to_percent(self, temp_c: float) -> int:
        curve = self.AUTO_FAN_CURVE
        if temp_c <= curve[0][0]:
            return curve[0][1]

        for index in range(1, len(curve)):
            low_temp, low_percent = curve[index - 1]
            high_temp, high_percent = curve[index]
            if temp_c <= high_temp:
                span = high_temp - low_temp
                ratio = 0.0 if span <= 0 else (temp_c - low_temp) / span
                interpolated = low_percent + ((high_percent - low_percent) * ratio)
                return int(min(100, max(20, round(interpolated / 5.0) * 5)))

        return 100

    def _format_temp(self, temp_c: float | None) -> str:
        if temp_c is None:
            return "N/D"
        return f"{temp_c:.1f} °C"

    def _dedupe_auto_status(self, status: str) -> str | None:
        if status == self._last_auto_status:
            return None
        self._last_auto_status = status
        return status

    def _set_status(self, message: str) -> None:
        self._base_status = message
        self._render_status()

    def _render_status(self) -> None:
        if self.autoclose_enabled_var.get() and self._countdown_job is not None:
            self.status_var.set(f"{self._base_status} | Autocierre en {self._countdown_remaining}s")
            return
        self.status_var.set(self._base_status)

    def _ensure_countdown_state(self) -> None:
        if self.autoclose_enabled_var.get():
            if self._countdown_job is None:
                self._countdown_remaining = max(5, int(self.autoclose_seconds_var.get()))
                self._tick_countdown()
            else:
                self._render_status()
        else:
            if self._countdown_job is not None:
                self.root.after_cancel(self._countdown_job)
                self._countdown_job = None
            self._render_status()

    def _tick_countdown(self) -> None:
        if not self.autoclose_enabled_var.get():
            self._countdown_job = None
            return

        if self._countdown_remaining <= 0:
            self._set_status("Autocierre ejecutado")
            self._on_exit()
            return

        self._render_status()
        self._countdown_remaining -= 1
        self._countdown_job = self.root.after(1000, self._tick_countdown)

    def _show_about(self) -> None:
        year = datetime.now().year
        top = tk.Toplevel(self.root)
        top.title("About")
        top.resizable(False, False)
        top.transient(self.root)
        top.configure(bg="#121a22")

        ttk.Label(
            top,
            text=f"Amen Gaming Hub {APP_VERSION_TAG}\nApache License 2.0\nSynyster Rick, {year}",
            padding=14,
            justify="left",
        ).pack(fill="x")

        ttk.Button(top, text="Cerrar", command=top.destroy).pack(pady=(0, 12))

    def _on_exit(self) -> None:
        self._cancel_live_apply()
        if self._telemetry_job is not None:
            self.root.after_cancel(self._telemetry_job)
            self._telemetry_job = None

        if self.restore_auto_on_exit_var.get():
            try:
                result = self.controller.restore_automatic_control()
                if result.ok:
                    self.logger.info(result.message)
                else:
                    self.logger.warning(result.message)
            except Exception as ex:  # noqa: BLE001
                self.logger.exception("Error restoring automatic control on exit: %s", ex)

        self._save_config()
        self.logger.info("Application exit requested")
        self.root.destroy()


def run_app() -> None:
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()
