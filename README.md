# Amen Gaming Hub

Aplicacion de escritorio en Python para ajustar ventiladores CPU/GPU con interfaz tipo hub, configuracion persistente y empaquetado a EXE sin consola.

## Caracteristicas

- Control separado para FAN CPU y FAN GPU.
- Interfaz sin bloqueos (worker thread + cola de eventos).
- Configuracion auto-guardada en `config.json`.
- Version en GUI (`Vx.y.z`) y flujo de incremento por commit.
- Log con timestamp en `log.txt`.
- Menu con About y atajos de teclado estilo Windows.
- Boton salir, autoinicio y autocierre configurable con countdown en barra de estado.
- Arquitectura separada entre backend y frontend.

## Estructura

- `app.py`: entrada principal.
- `amen_hub/frontend/main_window.py`: GUI.
- `amen_hub/backend/fan_controller.py`: controlador de ventiladores.
- `amen_hub/config.py`: carga/sanitizacion/guardado de config.
- `amen_hub/logger.py`: log con timestamp y rotacion.
- `amen_hub/version.py`: version unica de la app.
- `build.ps1`: compilacion a EXE en modo silencioso.
- `.github/workflows/release.yml`: build/release automatico en push a `main`.

## Requisitos

- Python 3.11+
- Windows 10/11
- PowerShell

## Instalacion local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

## Ejecutar

```powershell
python app.py
```

## Compilar EXE (sin ventana CMD)

Coloca tu icono como `app.ico` en la raiz del proyecto y ejecuta:

```powershell
.\build.ps1
```

El ejecutable generado quedara en la misma carpeta del proyecto.

## Versionado

Version inicial: `0.0.1`

Para incrementar patch (`+0.0.1`) antes de cada commit:

```powershell
python bump_version.py
```

## Seguridad y buenas practicas aplicadas

- Sanitizacion de datos de entrada en configuracion.
- Limites de rango para valores criticos.
- Sin ejecucion de shell dinamica en runtime.
- Sin bloqueo del hilo principal GUI.
- Logging rotativo para evitar crecimiento no controlado.

## Nota tecnica de hardware

El backend actual usa modo seguro/simulacion (`MockHPVictusFanController`) para no forzar llamadas no documentadas al EC/BIOS. Si luego quieres integrar control real de HP Victus/OMEN, se puede conectar una implementacion especifica dentro de `amen_hub/backend/` sin tocar la GUI.

## Licencia

Apache License 2.0. Ver archivo `LICENSE`.
