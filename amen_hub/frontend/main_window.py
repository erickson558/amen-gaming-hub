from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from amen_hub.backend import MockHPVictusFanController
from amen_hub.config import ConfigManager
from amen_hub.logger import setup_logger
from amen_hub.version import APP_VERSION_TAG


class MainWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.logger = setup_logger()
        self.config_manager = ConfigManager()
        self.controller = MockHPVictusFanController()
        self.ui_queue: queue.Queue[str] = queue.Queue()

        self._countdown_remaining = 0
        self._countdown_job: str | None = None

        self.root.title(f"Amen Gaming Hub {APP_VERSION_TAG}")
        self.root.geometry(self.config_manager.config.window_geometry)
        self.root.minsize(760, 480)
        self.root.protocol("WM_DELETE_WINDOW", self._on_exit)

        self._build_variables()
        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()
        self._load_state()

        self.root.after(100, self._drain_queue)
        self.root.after(250, self._ensure_countdown_state)

        if self.autostart_var.get():
            self._apply_async()

    def _build_variables(self) -> None:
        cfg = self.config_manager.config
        self.cpu_var = tk.IntVar(value=cfg.cpu_fan_percent)
        self.gpu_var = tk.IntVar(value=cfg.gpu_fan_percent)
        self.autostart_var = tk.BooleanVar(value=cfg.autostart_process)
        self.autoclose_enabled_var = tk.BooleanVar(value=cfg.autoclose_enabled)
        self.autoclose_seconds_var = tk.IntVar(value=cfg.autoclose_seconds)
        self.password_var = tk.StringVar(value=cfg.app_password)
        self.show_password_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Listo")

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)

        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Aplicar\tCtrl+A", command=self._apply_async)
        file_menu.add_separator()
        file_menu.add_command(label="Salir\tAlt+F4", command=self._on_exit)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About\tF1", command=self._show_about)

        menu.add_cascade(label="Archivo", menu=file_menu)
        menu.add_cascade(label="Ayuda", menu=help_menu)
        self.root.config(menu=menu)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        title = ttk.Label(container, text=f"Amen Gaming Hub {APP_VERSION_TAG}", font=("Segoe UI", 14, "bold"))
        title.pack(anchor="w", pady=(0, 10))

        sliders = ttk.Frame(container)
        sliders.pack(fill="x", pady=4)

        cpu_frame = ttk.LabelFrame(sliders, text="Dial FAN CPU")
        cpu_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.cpu_scale = ttk.Scale(
            cpu_frame,
            from_=0,
            to=100,
            orient="horizontal",
            command=lambda _v: self._on_live_change(),
            variable=self.cpu_var,
        )
        self.cpu_scale.pack(fill="x", padx=12, pady=(14, 6))
        self.cpu_value_label = ttk.Label(cpu_frame, text=f"{self.cpu_var.get()}%")
        self.cpu_value_label.pack(anchor="e", padx=12, pady=(0, 10))

        gpu_frame = ttk.LabelFrame(sliders, text="Dial FAN GPU")
        gpu_frame.pack(side="left", fill="both", expand=True, padx=(8, 0))

        self.gpu_scale = ttk.Scale(
            gpu_frame,
            from_=0,
            to=100,
            orient="horizontal",
            command=lambda _v: self._on_live_change(),
            variable=self.gpu_var,
        )
        self.gpu_scale.pack(fill="x", padx=12, pady=(14, 6))
        self.gpu_value_label = ttk.Label(gpu_frame, text=f"{self.gpu_var.get()}%")
        self.gpu_value_label.pack(anchor="e", padx=12, pady=(0, 10))

        options = ttk.LabelFrame(container, text="Opciones")
        options.pack(fill="x", pady=10)

        self.autostart_check = ttk.Checkbutton(
            options,
            text="Autoiniciar proceso al abrir",
            variable=self.autostart_var,
            command=self._on_live_change,
            underline=0,
        )
        self.autostart_check.grid(row=0, column=0, sticky="w", padx=10, pady=6)

        self.autoclose_check = ttk.Checkbutton(
            options,
            text="Autocerrar",
            variable=self.autoclose_enabled_var,
            command=self._on_live_change,
            underline=0,
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
        self.autoclose_spin.grid(row=1, column=2, sticky="w", padx=(0, 10))

        ttk.Label(options, text="Password (opcional):").grid(row=2, column=0, sticky="w", padx=10, pady=(6, 10))
        self.password_entry = ttk.Entry(options, textvariable=self.password_var, show="*")
        self.password_entry.grid(row=2, column=1, sticky="ew", padx=(10, 4), pady=(6, 10))
        self.toggle_pass_button = ttk.Button(options, text="Mostrar", command=self._toggle_password, underline=0)
        self.toggle_pass_button.grid(row=2, column=2, sticky="w", padx=(0, 10), pady=(6, 10))

        options.columnconfigure(1, weight=1)

        actions = ttk.Frame(container)
        actions.pack(fill="x", pady=(2, 8))

        self.apply_button = ttk.Button(actions, text="Aplicar", command=self._apply_async, underline=0)
        self.apply_button.pack(side="left")

        self.exit_button = ttk.Button(actions, text="Salir", command=self._on_exit, underline=0)
        self.exit_button.pack(side="left", padx=(8, 0))

        status = ttk.Label(container, textvariable=self.status_var, anchor="w", relief="sunken")
        status.pack(fill="x", side="bottom", pady=(6, 0), ipady=4)

    def _bind_shortcuts(self) -> None:
        self.root.bind_all("<Control-a>", lambda _e: self._apply_async())
        self.root.bind_all("<Alt-a>", lambda _e: self._apply_async())
        self.root.bind_all("<Alt-s>", lambda _e: self._on_exit())
        self.root.bind_all("<F1>", lambda _e: self._show_about())

        self.cpu_var.trace_add("write", lambda *_: self._on_live_change())
        self.gpu_var.trace_add("write", lambda *_: self._on_live_change())
        self.autoclose_seconds_var.trace_add("write", lambda *_: self._on_live_change())
        self.password_var.trace_add("write", lambda *_: self._on_live_change())

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

    def _save_config(self) -> None:
        self.config_manager.update(
            cpu_fan_percent=int(self.cpu_var.get()),
            gpu_fan_percent=int(self.gpu_var.get()),
            autostart_process=bool(self.autostart_var.get()),
            autoclose_enabled=bool(self.autoclose_enabled_var.get()),
            autoclose_seconds=int(self.autoclose_seconds_var.get()),
            app_password=self.password_var.get(),
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

    def _drain_queue(self) -> None:
        while not self.ui_queue.empty():
            msg = self.ui_queue.get_nowait()
            if msg == "__enable_apply__":
                self.apply_button.configure(state="normal")
                continue
            self._set_status(msg)
        self.root.after(120, self._drain_queue)

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)

    def _ensure_countdown_state(self) -> None:
        if self.autoclose_enabled_var.get():
            if self._countdown_job is None:
                self._countdown_remaining = max(5, int(self.autoclose_seconds_var.get()))
                self._tick_countdown()
        else:
            if self._countdown_job is not None:
                self.root.after_cancel(self._countdown_job)
                self._countdown_job = None
            self._set_status("Listo")

    def _tick_countdown(self) -> None:
        if not self.autoclose_enabled_var.get():
            self._countdown_job = None
            return

        if self._countdown_remaining <= 0:
            self._set_status("Autocierre ejecutado")
            self._on_exit()
            return

        self._set_status(f"Autocierre en {self._countdown_remaining}s")
        self._countdown_remaining -= 1
        self._countdown_job = self.root.after(1000, self._tick_countdown)

    def _show_about(self) -> None:
        year = datetime.now().year
        top = tk.Toplevel(self.root)
        top.title("About")
        top.resizable(False, False)
        top.transient(self.root)

        ttk.Label(
            top,
            text=f"{APP_VERSION_TAG} x.x creado por Synyster Rick, {year} Derechos Reservados",
            padding=14,
            justify="left",
        ).pack(fill="x")

        ttk.Button(top, text="Cerrar", command=top.destroy).pack(pady=(0, 12))

    def _on_exit(self) -> None:
        self._save_config()
        self.logger.info("Application exit requested")
        self.root.destroy()


def run_app() -> None:
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()
