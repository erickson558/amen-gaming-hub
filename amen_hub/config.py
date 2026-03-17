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
        safe["autostart_process"] = bool(safe["autostart_process"])
        safe["autoclose_enabled"] = bool(safe["autoclose_enabled"])
        safe["window_geometry"] = str(safe["window_geometry"])
        safe["app_password"] = str(safe["app_password"])
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
