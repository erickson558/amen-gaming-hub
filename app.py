# Punto de entrada de la aplicacion.
from amen_hub.tk_runtime import configure_tk_runtime

# Debe ejecutarse antes de importar tkinter/main_window: ajusta TCL_LIBRARY/TK_LIBRARY
# para que el runtime de Tcl/Tk funcione tanto en desarrollo como empaquetado en el .exe.
configure_tk_runtime()

from amen_hub.frontend.main_window import run_app


if __name__ == "__main__":
    # Construye la ventana principal (Tk root) y entra al mainloop de Tkinter.
    run_app()
