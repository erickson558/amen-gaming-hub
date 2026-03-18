from __future__ import annotations

import subprocess
from typing import Any


def run_hidden(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    creationflags = int(kwargs.pop("creationflags", 0)) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    startupinfo = kwargs.pop("startupinfo", None)

    if startupinfo is None and hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)

    return subprocess.run(
        cmd,
        creationflags=creationflags,
        startupinfo=startupinfo,
        **kwargs,
    )
