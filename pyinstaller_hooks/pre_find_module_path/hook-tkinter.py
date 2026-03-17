from __future__ import annotations


def pre_find_module_path(hook_api):
    # PyInstaller marca esta instalacion de Tk como "broken" por la validacion de
    # Tcl/Tk, pero el modulo `tkinter` y la extension `_tkinter` si existen.
    # El proyecto empaqueta manualmente los datos Tcl/Tk y configura el runtime
    # antes del primer import de `tkinter`, por eso no debemos excluir el modulo.
    return
