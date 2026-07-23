# Logging a archivo (log.txt) para poder diagnosticar la app ya empaquetada,
# donde no hay consola visible (--noconsole en build.ps1).
import logging
from logging.handlers import RotatingFileHandler

from .paths import ensure_parent, resolve_in_base


LOG_FILE = resolve_in_base("log.txt")


def setup_logger() -> logging.Logger:
    """Logger singleton "amen_hub" que escribe en log.txt junto al .exe.

    Se rota automaticamente (max 2 MB, 3 backups) para que el log no crezca
    sin limite. El nombre del thread se incluye en el formato porque el
    trabajo real (aplicar ventiladores, telemetria) corre en workers, no en
    el hilo principal de Tkinter.
    """
    logger = logging.getLogger("amen_hub")
    if logger.handlers:
        # Ya se configuro antes (p.ej. si algo vuelve a llamar setup_logger);
        # evita duplicar handlers y por lo tanto duplicar cada linea de log.
        return logger

    ensure_parent(LOG_FILE)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(threadName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.propagate = False
    logger.info("Logger initialized")
    return logger
