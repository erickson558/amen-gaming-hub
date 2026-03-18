from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List

from .paths import ensure_parent, resolve_in_base


@dataclass
class AppConfig:
    cpu_fan_percent: int = 50
    gpu_fan_percent: int = 50
    autostart_process: bool = False
    autoclose_enabled: bool = False
    autoclose_seconds: int = 60
    window_geometry: str = "900x560+120+80"
    app_password: str = ""
    fan_backend: str = "auto"
    fan_command_cpu: str = ""
    fan_command_gpu: str = ""
    telemetry_interval_seconds: int = 2
    omenmon_executable: str = "auto"
    nbfc_profile: str = "HP OMEN Notebook PC 15"
    nbfc_executable: str = "auto"
    nbfc_autodiscover_profile: bool = True


class ConfigManager:
    def __init__(self) -> None:
        self._path: Path = resolve_in_base("config.json")
        self._callbacks: List[Callable[[AppConfig], None]] = []
        self.config: AppConfig = self._load()

    @property
    def path(self) -> Path:
        return self._path

    def _load(self) -> AppConfig:
        if not self._path.exists():
            default_config = AppConfig()
            self._save(default_config)
            return default_config

        try:
            with self._path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            data = self._sanitize(raw)
            return AppConfig(**data)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            fallback = AppConfig()
            self._save(fallback)
            return fallback

    def _sanitize(self, data: Dict) -> Dict:
        safe = asdict(AppConfig())
        safe.update({k: v for k, v in data.items() if k in safe})
        safe["cpu_fan_percent"] = int(min(max(int(safe["cpu_fan_percent"]), 0), 100))
        safe["gpu_fan_percent"] = int(min(max(int(safe["gpu_fan_percent"]), 0), 100))
        safe["autoclose_seconds"] = int(min(max(int(safe["autoclose_seconds"]), 5), 3600))
        safe["telemetry_interval_seconds"] = int(min(max(int(safe["telemetry_interval_seconds"]), 1), 30))
        safe["autostart_process"] = bool(safe["autostart_process"])
        safe["autoclose_enabled"] = bool(safe["autoclose_enabled"])
        safe["window_geometry"] = str(safe["window_geometry"])
        safe["app_password"] = str(safe["app_password"])
        safe["fan_backend"] = str(safe["fan_backend"]).strip().lower()
        if safe["fan_backend"] not in {"auto", "mock", "nbfc", "omenmon", "command"}:
            safe["fan_backend"] = "auto"
        safe["fan_command_cpu"] = str(safe["fan_command_cpu"])
        safe["fan_command_gpu"] = str(safe["fan_command_gpu"])
        safe["omenmon_executable"] = str(safe["omenmon_executable"])
        safe["nbfc_profile"] = str(safe["nbfc_profile"])
        safe["nbfc_executable"] = str(safe["nbfc_executable"])
        safe["nbfc_autodiscover_profile"] = bool(safe["nbfc_autodiscover_profile"])

        profile_aliases = {
            "notebook pc 15": "HP OMEN Notebook PC 15",
            "omen notebook pc 15": "HP OMEN Notebook PC 15",
            "hp omen notebook pc 15": "HP OMEN Notebook PC 15",
        }
        key = safe["nbfc_profile"].strip().lower()
        if key in profile_aliases:
            safe["nbfc_profile"] = profile_aliases[key]

        return safe

    def save(self) -> None:
        self._save(self.config)

    def _save(self, config: AppConfig) -> None:
        ensure_parent(self._path)
        with self._path.open("w", encoding="utf-8") as f:
            json.dump(asdict(config), f, indent=2)

    def update(self, **kwargs) -> None:
        merged = asdict(self.config)
        merged.update(kwargs)
        self.config = AppConfig(**self._sanitize(merged))
        self._save(self.config)
        for cb in self._callbacks:
            cb(self.config)

    def subscribe(self, callback: Callable[[AppConfig], None]) -> None:
        self._callbacks.append(callback)
