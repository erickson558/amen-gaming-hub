import os
import sys
from pathlib import Path


def get_base_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resolve_in_base(filename: str) -> Path:
    return get_base_path() / filename


def ensure_parent(path: Path) -> None:
    os.makedirs(path.parent, exist_ok=True)
