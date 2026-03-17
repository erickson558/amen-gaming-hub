from amen_hub.tk_runtime import configure_tk_runtime

configure_tk_runtime()

from amen_hub.frontend.main_window import run_app


if __name__ == "__main__":
    run_app()
