# Amen Gaming Hub

Aplicacion de escritorio en Python para ajustar ventiladores CPU/GPU con interfaz tipo hub, configuracion persistente y empaquetado a EXE sin consola.

## Caracteristicas

- Control separado para FAN CPU y FAN GPU.
- Backend de ventiladores configurable (`auto`, `nbfc`, `command`, `mock`).
- Interfaz sin bloqueos (worker thread + cola de eventos).
- Interfaz estilo gaming (tema oscuro con medidores termicos CPU/GPU).
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

Nota: para control real de ventiladores en Victus (NBFC) y lectura CPU por WMI, ejecuta como Administrador.

## Compilar EXE (sin ventana CMD)

El build usa icono automaticamente con esta prioridad:

1. `app.ico` en la raiz.
2. Primer archivo `*.ico` encontrado en la raiz.
3. Si no hay icono, compila sin icono personalizado.

Ejecuta:

```powershell
.\build.ps1
```

El ejecutable generado quedara en la misma carpeta del proyecto.
El EXE se genera con requerimiento UAC (`--uac-admin`) para permisos de hardware.

## Modo portable para otros PCs (misma carpeta del EXE)

La app ahora busca `nbfc.exe` en este orden:

1. Ruta configurada en `config.json` (`nbfc_executable`) si no es `auto`.
2. Binario asociado al servicio instalado `NbfcService` (ruta oficial de NBFC).
3. Misma carpeta del `.exe` (`./nbfc.exe`).
4. `./tools/nbfc/nbfc.exe`.
5. `./NoteBook FanControl/nbfc.exe`.
6. PATH del sistema.

Para preparar la carpeta portable:

```powershell
.\install_nbfc_local.ps1
```

Eso deja NBFC dentro de `tools/nbfc/` junto a tu app para que funcione al moverla a otro equipo.
Importante: se copia la carpeta completa de NBFC (no solo `nbfc.exe`) para evitar errores de servicio/pipe.

La app ejecuta comandos de hardware en modo silencioso (`CREATE_NO_WINDOW`) para evitar popups de PowerShell/cmd.
Tambien aplica recuperacion inteligente de `NbfcService` (sin reinicios agresivos y con reset duro solo cuando detecta estado roto).
Para mejorar estabilidad, la app usa `config --set` + `set --speed` y evita `nbfc start` en cada aplicacion.

## Versionado

Formato oficial: `Vx.x.x`.

Fuente unica de verdad:
- `APP_VERSION` en `amen_hub/version.py`.
- `APP_VERSION_TAG` se deriva automaticamente como `f"V{APP_VERSION}"`.

Antes de cada commit, incrementa patch (`+0.0.1`):

```powershell
python bump_version.py
```

El workflow de release usa el mismo valor y publica tags en GitHub con formato `Vx.x.x`.

## Seguridad y buenas practicas aplicadas

- Sanitizacion de datos de entrada en configuracion.
- Limites de rango para valores criticos.
- Sin ejecucion de shell dinamica en runtime.
- Sin bloqueo del hilo principal GUI.
- Logging rotativo para evitar crecimiento no controlado.

## Nota tecnica de hardware

La app intenta control real por backend segun `config.json`:

- `fan_backend: auto`: usa `nbfc.exe` si esta instalado; si no, usa backend por comandos y finalmente mock.
- `fan_backend: nbfc`: fuerza el uso de NBFC (`nbfc.exe set -f 0/1 -s {valor}`).
- `fan_backend: command`: ejecuta `fan_command_cpu` y `fan_command_gpu` con placeholder `{value}`.
- `fan_backend: mock`: modo simulacion.
- `nbfc_autodiscover_profile: true`: intenta auto-detectar perfil HP compatible si el perfil actual no aplica fan speed.

En algunos equipos HP Victus, el control de ventilador no esta expuesto oficialmente por API publica; en esos casos se recomienda `nbfc` o comandos propios del controlador que ya uses.

## Licencia

Apache License 2.0. Ver archivo `LICENSE`.
