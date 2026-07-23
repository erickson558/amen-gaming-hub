from __future__ import annotations

import subprocess
from typing import Any


def run_hidden(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Wrapper de subprocess.run que nunca muestra una ventana de consola.

    Todos los backends (OmenMon, NBFC, comandos custom, nvidia-smi, sc,
    tasklist, powershell) pasan por aqui para que, al ejecutar la app
    empaquetada, no aparezcan ventanas negras de CMD parpadeando en pantalla.
    """
    # CREATE_NO_WINDOW evita que Windows cree una consola nueva para el hijo.
    creationflags = int(kwargs.pop("creationflags", 0)) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    startupinfo = kwargs.pop("startupinfo", None)

    if startupinfo is None and hasattr(subprocess, "STARTUPINFO"):
        # Refuerzo adicional: pide explicitamente que la ventana (si el
        # proceso hijo crease una) arranque oculta.
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)

    return subprocess.run(
        cmd,
        creationflags=creationflags,
        startupinfo=startupinfo,
        **kwargs,
    )
