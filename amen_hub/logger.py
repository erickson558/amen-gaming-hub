import logging
from logging.handlers import RotatingFileHandler

from .paths import ensure_parent, resolve_in_base


LOG_FILE = resolve_in_base("log.txt")


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("amen_hub")
    if logger.handlers:
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
