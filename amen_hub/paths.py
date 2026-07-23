import os
import sys
from pathlib import Path


def get_base_path() -> Path:
    """Carpeta base para leer/escribir archivos junto a la app.

    Si esta empaquetada por PyInstaller (``sys.frozen``), es la carpeta del
    .exe. En desarrollo, es la raiz del proyecto (dos niveles arriba de este
    archivo: amen_hub/paths.py -> amen_hub -> raiz).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resolve_in_base(filename: str) -> Path:
    """Ruta absoluta de *filename* relativa a la carpeta base de la app."""
    return get_base_path() / filename


def ensure_parent(path: Path) -> None:
    """Crea la carpeta contenedora de *path* si todavia no existe."""
    os.makedirs(path.parent, exist_ok=True)
