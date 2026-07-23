from __future__ import annotations

# Este modulo existe para que tkinter arranque tanto en desarrollo como
# empaquetado con PyInstaller, incluso cuando la version de Tcl instalada en
# el sistema no coincide exactamente con la que Python/Tk esperan. Debe
# llamarse (configure_tk_runtime) antes de "import tkinter" en app.py.
import os
import re
import shutil
import sys
from pathlib import Path

# init.tcl de algunas instalaciones exige una version EXACTA de Tcl
# ("package require -exact Tcl 8.6.x"), lo que rompe si el binario empaquetado
# trae una version de parche distinta. Se relaja a "package require Tcl 8.6"
# (cualquier 8.6.x sirve) en una copia parcheada, nunca en el original.
_EXACT_TCL_PATTERN = re.compile(r"package require -exact Tcl \d+\.\d+\.\d+")


def _candidate_pairs() -> list[tuple[Path, Path]]:
    """Posibles ubicaciones de las carpetas tcl8.6/tk8.6, de mas a menos especifica.

    Primero la carpeta que PyInstaller empaqueta dentro del .exe (_MEIPASS),
    despues las del interprete de Python que esta corriendo (desarrollo).
    """
    pairs: list[tuple[Path, Path]] = []

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        frozen_base = Path(getattr(sys, "_MEIPASS")) / "tcl"
        pairs.append((frozen_base / "tcl8.6", frozen_base / "tk8.6"))

    for prefix in {sys.base_prefix, sys.exec_prefix}:
        base = Path(prefix) / "tcl"
        pairs.append((base / "tcl8.6", base / "tk8.6"))

    return pairs


def _patch_runtime_dirs(tcl_dir: Path, tk_dir: Path) -> tuple[Path, Path]:
    """Si hace falta parchear init.tcl, devuelve una copia parcheada; si no, el original.

    Nunca modifica los archivos originales de Tcl/Tk: copia todo a
    .tcl_runtime_cache/<fingerprint> (basado en tamaño/mtime/PID de init.tcl,
    para no pisar una copia en uso por otro proceso) y solo ahi aplica el
    reemplazo de version exacta.
    """
    init_tcl = tcl_dir / "init.tcl"
    if not init_tcl.exists():
        return tcl_dir, tk_dir

    content = init_tcl.read_text(encoding="utf-8")
    patched = _EXACT_TCL_PATTERN.sub("package require Tcl 8.6", content, count=1)
    if patched == content:
        # No habia nada que parchear (version exacta no requerida): usar tal cual.
        return tcl_dir, tk_dir

    cache_root = Path(__file__).resolve().parents[1] / ".tcl_runtime_cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    fingerprint = f"{init_tcl.stat().st_size}-{init_tcl.stat().st_mtime_ns}-{os.getpid()}"
    target_root = cache_root / fingerprint
    target_tcl = target_root / "tcl8.6"
    target_tk = target_root / "tk8.6"

    if not target_tcl.exists():
        shutil.copytree(tcl_dir, target_tcl, dirs_exist_ok=True)
        (target_tcl / "init.tcl").write_text(patched, encoding="utf-8")

    if tk_dir.exists() and not target_tk.exists():
        shutil.copytree(tk_dir, target_tk, dirs_exist_ok=True)

    return target_tcl, (target_tk if target_tk.exists() else tk_dir)


def configure_tk_runtime() -> None:
    """Fija TCL_LIBRARY/TK_LIBRARY antes de que tkinter los lea al importarse.

    Si ya hay variables de entorno validas (carpetas existentes), no se toca
    nada. Si no, se prueba cada candidato de _candidate_pairs() en orden y se
    usa el primero que exista, parcheado si hizo falta.
    """
    env_tcl = os.environ.get("TCL_LIBRARY")
    env_tk = os.environ.get("TK_LIBRARY")
    if env_tcl and env_tk and Path(env_tcl).exists() and Path(env_tk).exists():
        return

    for tcl_dir, tk_dir in _candidate_pairs():
        if not tcl_dir.exists():
            continue
        resolved_tcl, resolved_tk = _patch_runtime_dirs(tcl_dir, tk_dir)
        if resolved_tcl.exists() and resolved_tk.exists():
            os.environ["TCL_LIBRARY"] = str(resolved_tcl)
            os.environ["TK_LIBRARY"] = str(resolved_tk)
            return
