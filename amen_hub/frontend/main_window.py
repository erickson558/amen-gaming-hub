from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Any

from amen_hub.backend import build_fan_controller
from amen_hub.backend import is_running_as_admin
from amen_hub.backend.fan_controller import find_nbfc_executable
from amen_hub.backend.telemetry import TemperatureService
from amen_hub.config import ConfigManager
from amen_hub.logger import setup_logger
from amen_hub.version import APP_VERSION_TAG


class MainWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.logger = setup_logger()
        self.config_manager = ConfigManager()
        self._nbfc_path = find_nbfc_executable(self.config_manager.config.nbfc_executable)
        self.controller = build_fan_controller(self.config_manager.config)
        self.telemetry = TemperatureService(self._nbfc_path)
        self.ui_queue: queue.Queue[Any] = queue.Queue()

        self._countdown_remaining = 0
        self._countdown_job: str | None = None
        self._telemetry_job: str | None = None
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
        self._schedule_telemetry()
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
        self.autostart_var = tk.BooleanVar(value=cfg.autostart_process)
        self.autoclose_enabled_var = tk.BooleanVar(value=cfg.autoclose_enabled)
        self.autoclose_seconds_var = tk.IntVar(value=cfg.autoclose_seconds)
        self.password_var = tk.StringVar(value=cfg.app_password)
        self.backend_var = tk.StringVar(value=cfg.fan_backend)
        self.nbfc_profile_var = tk.StringVar(value=cfg.nbfc_profile)
        self.show_password_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Listo")
        self.cpu_temp_var = tk.StringVar(value="--.- C")
        self.gpu_temp_var = tk.StringVar(value="--.- C")

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

        temp_card = ttk.LabelFrame(top_row, text="Temperaturas", style="Card.TLabelframe")
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
            values=["auto", "nbfc", "command", "mock"],
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

        self.exit_button = ttk.Button(actions, text="Salir", command=self._on_exit, style="Danger.TButton")
        self.exit_button.pack(side="left", padx=(8, 0))
    def _repair_nbfc(self) -> None:
        self.repair_button.configure(state="disabled")
        self._set_status("Intentando reparar NBFC...")
        def worker():
            try:
                repaired = False
                # Solo si el controlador es NBFCFanController
                from amen_hub.backend.fan_controller import NBFCFanController
                if isinstance(self.controller, NBFCFanController):
                    repaired = self.controller.repair_nbfc_service()
                msg = "NBFC reparado correctamente." if repaired else "No se pudo reparar NBFC. Reinicia Windows para limpiar el servicio."
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
                self.apply_button.configure(state="normal")
                continue
            if msg == "__enable_repair__":
                self.repair_button.configure(state="normal")
                continue
            if isinstance(msg, tuple) and msg[0] == "__temps__":
                self._render_temps(msg[1], msg[2])
                continue
            self._set_status(str(msg))
        self.root.after(120, self._drain_queue)

        status = ttk.Label(container, textvariable=self.status_var, anchor="w", style="Status.TLabel", padding=(10, 6))
        status.pack(fill="x", side="bottom", pady=(6, 0), ipady=4)

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
        self._save_config()

    def _on_live_change(self) -> None:
        self._update_value_labels()
        self._save_config()
        self._ensure_countdown_state()

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
        self.controller = build_fan_controller(self.config_manager.config)
        self.telemetry = TemperatureService(self._nbfc_path)
        self._set_status(f"Backend cambiado a: {self.controller.describe()}")

    def _save_config(self) -> None:
        try:
            autoclose_secs = int(self.autoclose_seconds_var.get())
        except (TypeError, ValueError):
            autoclose_secs = 60
            self.autoclose_seconds_var.set(autoclose_secs)

        self.config_manager.update(
            cpu_fan_percent=int(self.cpu_var.get()),
            gpu_fan_percent=int(self.gpu_var.get()),
            autostart_process=bool(self.autostart_var.get()),
            autoclose_enabled=bool(self.autoclose_enabled_var.get()),
            autoclose_seconds=autoclose_secs,
            app_password=self.password_var.get(),
            fan_backend=self.backend_var.get(),
            nbfc_profile=self.nbfc_profile_var.get(),
            window_geometry=self.root.geometry(),
        )

    def _apply_async(self) -> None:
        self.apply_button.configure(state="disabled")
        self._set_status("Aplicando velocidades de ventilador...")

        cpu = int(self.cpu_var.get())
        gpu = int(self.gpu_var.get())

        thread = threading.Thread(
            target=self._worker_apply,
            args=(cpu, gpu),
            name="FanApplyWorker",
            daemon=True,
        )
        thread.start()

    def _worker_apply(self, cpu: int, gpu: int) -> None:
        try:
            result = self.controller.apply_fan_speeds(cpu, gpu)
            now = datetime.now().strftime("%H:%M:%S")
            if result.ok:
                self.logger.info(result.message)
                self.ui_queue.put(f"{result.message} | {now}")
            else:
                self.logger.warning(result.message)
                self.ui_queue.put(f"No aplicado: {result.message} | {now}")
        except Exception as ex:  # noqa: BLE001
            self.logger.exception("Error applying fan speeds: %s", ex)
            self.ui_queue.put(f"Error inesperado: {ex}")
        finally:
            self.ui_queue.put("__enable_apply__")

    def _schedule_telemetry(self) -> None:
        interval = max(1, int(self.config_manager.config.telemetry_interval_seconds))
        self._telemetry_job = self.root.after(interval * 1000, self._telemetry_async)

    def _telemetry_async(self) -> None:
        thread = threading.Thread(target=self._worker_telemetry, name="TelemetryWorker", daemon=True)
        thread.start()
        self._schedule_telemetry()

    def _worker_telemetry(self) -> None:
        reading = self.telemetry.read()
        self.ui_queue.put(("__temps__", reading.cpu_c, reading.gpu_c))

    def _drain_queue(self) -> None:
        while not self.ui_queue.empty():
            msg = self.ui_queue.get_nowait()
            if msg == "__enable_apply__":
                self.apply_button.configure(state="normal")
                continue

            if isinstance(msg, tuple) and msg[0] == "__temps__":
                self._render_temps(msg[1], msg[2])
                continue

            self._set_status(str(msg))
        self.root.after(120, self._drain_queue)

    def _render_temps(self, cpu_c: float | None, gpu_c: float | None) -> None:
        self._update_meter(self.cpu_temp_canvas, cpu_c, self.cpu_temp_var)
        self._update_meter(self.gpu_temp_canvas, gpu_c, self.gpu_temp_var)

    def _update_meter(self, canvas: tk.Canvas, temp_c: float | None, var: tk.StringVar) -> None:
        if temp_c is None:
            value_text = "N/D"
            ratio = 0
        else:
            value_text = f"{temp_c:.1f} C"
            ratio = min(max(temp_c / 100.0, 0.0), 1.0)

        var.set(value_text)
        extent = -int(360 * ratio)
        color = "#46d483" if ratio < 0.65 else "#ffb347" if ratio < 0.82 else "#ff5f6d"
        canvas.itemconfigure("arc", extent=extent, outline=color)
        canvas.itemconfigure("value", text=value_text)

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
            text=f"{APP_VERSION_TAG} x.x creado por Synyster Rick, {year} Derechos Reservados",
            padding=14,
            justify="left",
        ).pack(fill="x")

        ttk.Button(top, text="Cerrar", command=top.destroy).pack(pady=(0, 12))

    def _on_exit(self) -> None:
        if self._telemetry_job is not None:
            self.root.after_cancel(self._telemetry_job)
            self._telemetry_job = None

        self._save_config()
        self.logger.info("Application exit requested")
        self.root.destroy()


def run_app() -> None:
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()
