from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

_EXACT_TCL_PATTERN = re.compile(r"package require -exact Tcl \d+\.\d+\.\d+")


def _candidate_pairs() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        frozen_base = Path(getattr(sys, "_MEIPASS")) / "tcl"
        pairs.append((frozen_base / "tcl8.6", frozen_base / "tk8.6"))

    for prefix in {sys.base_prefix, sys.exec_prefix}:
        base = Path(prefix) / "tcl"
        pairs.append((base / "tcl8.6", base / "tk8.6"))

    return pairs


def _patch_runtime_dirs(tcl_dir: Path, tk_dir: Path) -> tuple[Path, Path]:
    init_tcl = tcl_dir / "init.tcl"
    if not init_tcl.exists():
        return tcl_dir, tk_dir

    content = init_tcl.read_text(encoding="utf-8")
    patched = _EXACT_TCL_PATTERN.sub("package require Tcl 8.6", content, count=1)
    if patched == content:
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
