# Amen Gaming Hub

Aplicacion de escritorio en Python para monitorear temperatura y aplicar perfiles de ventilacion en equipos Windows, con enfoque practico para laptops HP Victus/OMEN.

## Que hace el programa

- Muestra temperatura CPU/GPU en una interfaz Tkinter.
- Aplica velocidades de ventilador desde una GUI sin bloquear el hilo principal.
- Guarda configuracion persistente en `config.json`.
- Permite usar distintos backends de control:
  - `omenmon`: control HP/OMEN basado en WMI/EC para equipos compatibles.
  - `nbfc`: NoteBook FanControl.
  - `command`: comandos externos parametrizados.
  - `mock`: simulacion segura.
  - `auto`: prioriza `omenmon`, luego `nbfc`, y por ultimo `command`.
- Genera un ejecutable `AmenGamingHub.exe` en la raiz del proyecto.

## Estado del proyecto

- Plataforma objetivo: Windows 10/11.
- Lenguaje: Python 3.12 recomendado.
- Licencia: Apache License 2.0.
- Versionado: `Vx.x.x`, con `APP_VERSION` como fuente unica de verdad.

## Estructura principal

- `app.py`: punto de entrada.
- `amen_hub/frontend/main_window.py`: interfaz grafica.
- `amen_hub/backend/fan_controller.py`: logica de control de ventiladores.
- `amen_hub/backend/telemetry.py`: lectura de temperatura.
- `amen_hub/config.py`: carga, sanitizacion y persistencia de configuracion.
- `amen_hub/version.py`: version de la aplicacion.
- `CHANGELOG.md`: historial resumido por version.
- `build.ps1`: build del `.exe` en la raiz del proyecto.
- `bump_version.py`: incremento automatizado de version patch.
- `.github/workflows/release.yml`: build y release al hacer push a `main`.

## Dependencias

### Python

Las dependencias Python estan definidas en [requirements.txt](D:\OneDrive\Regional\1 pendientes para analisis\proyectospython\Amen gaming hub\requirements.txt):

- `pyinstaller==6.19.0`

### Dependencias del sistema

- PowerShell 7 o Windows PowerShell.
- Tcl/Tk disponible en la instalacion de Python usada para compilar.
- Permisos de administrador para control real por NBFC o drivers HP.

### Dependencias opcionales de hardware

- `NBFC` para backend `nbfc`.
- `OMEN Gaming Hub` y drivers HP (`HP Omen Driver`, `HP Application Driver`) para equipos Victus/OMEN.
- `OmenMon` como herramienta alternativa para hardware HP compatible.

## Instalacion local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Ejecucion en desarrollo

```powershell
python app.py
```

Para control real de hardware, ejecuta la app como Administrador.

## Compilacion del EXE

El build genera `AmenGamingHub.exe` en la misma carpeta donde esta `app.py`.

Prioridad del icono:

1. `app.ico` en la raiz.
2. Primer archivo `*.ico` encontrado en la raiz.
3. Si no hay icono, compila sin icono personalizado.

Comando:

```powershell
.\build.ps1
```

El build:

- usa `python.exe` de `.venv` si existe.
- valida `tkinter` antes de empaquetar.
- incluye hooks locales de PyInstaller.
- empaqueta datos Tcl/Tk necesarios para el runtime.
- genera un `.exe` silencioso con `--uac-admin`.

## Backends soportados

### NBFC

Uso previsto para equipos donde `nbfc.exe` y `NbfcService` funcionan de forma estable.

Instalacion local:

```powershell
.\install_nbfc_local.ps1
```

Busqueda de `nbfc.exe`:

1. `config.json` (`nbfc_executable`) si no es `auto`.
2. Binario del servicio `NbfcService`.
3. `./nbfc.exe`
4. `./tools/nbfc/nbfc.exe`
5. `./NoteBook FanControl/nbfc.exe`
6. `PATH`

### Command

Ejecuta comandos custom definidos en `config.json` usando el placeholder `{value}`.

### Mock

Backend de simulacion seguro para validar UI, threading y persistencia.

### Alternativa HP Victus / OMEN

En varios modelos Victus recientes, `NBFC` no es la via mas confiable. Si tu equipo ya tiene `OMEN Gaming Hub`, `HP Omen Driver` y `HP Application Driver`, la ruta HP/OMEN suele ser mejor.

Instalacion local de `OmenMon`:

```powershell
.\install_omenmon_local.ps1
```

`OmenMon` se instala localmente en `tools/omenmon/` y no se versiona en Git.

## Configuracion

Los valores persistentes viven en `config.json`. Campos relevantes:

- `cpu_fan_percent`
- `gpu_fan_percent`
- `fan_backend`
- `fan_command_cpu`
- `fan_command_gpu`
- `omenmon_executable`
- `nbfc_profile`
- `nbfc_executable`
- `nbfc_autodiscover_profile`
- `window_geometry`

`config.json` es configuracion local y no debe considerarse parte del codigo fuente.

## Versionado

Formato oficial: `Vx.x.x`.

Fuente unica de verdad:

- `APP_VERSION` en [version.py](D:\OneDrive\Regional\1 pendientes para analisis\proyectospython\Amen gaming hub\amen_hub\version.py)
- `APP_VERSION_TAG = f"V{APP_VERSION}"`

Antes de cada commit:

```powershell
python bump_version.py
```

Regla operativa del proyecto:

- cada commit funcional genera una nueva version patch.
- la version del codigo, la version mostrada en la app y el tag de GitHub deben coincidir.

## Release en GitHub

El workflow de [release.yml](D:\OneDrive\Regional\1 pendientes para analisis\proyectospython\Amen gaming hub\.github\workflows\release.yml):

- corre en `push` a `main`.
- usa Python 3.12.
- valida importacion y compilacion basica del source.
- ejecuta `build.ps1`.
- crea release con tag `Vx.x.x`.
- publica `AmenGamingHub.exe` como artefacto de release.

## Practicas de mantenimiento

- No versionar binarios generados ni herramientas descargadas (`*.exe`, `tools/nbfc/`, `tools/omenmon/`).
- Mantener `requirements.txt` pinneado para builds reproducibles.
- Hacer build y smoke test antes de commitear.
- Evitar meter `config.json` local en commits.
- Mantener el mensaje de commit alineado con el cambio real y con la version creada.

## Troubleshooting

### `ModuleNotFoundError: tkinter`

El build usa hooks de PyInstaller y empaqueta Tcl/Tk. Recompila con:

```powershell
.\build.ps1
```

### NBFC detecta multiples procesos / service unavailable

- Ejecuta la app como Administrador.
- Verifica el estado de `NbfcService`.
- Usa el boton `Diagnostico NBFC`.
- Si el modelo es Victus reciente y NBFC sigue fallando, prioriza la via HP/OMEN.

### OmenMon muestra excepciones o no aplica niveles

- Ejecuta la app compilada como Administrador.
- Usa backend `auto` u `omenmon` para evitar seguir forzando `nbfc` en Victus/OMEN.
- Verifica que `tools/omenmon/OmenMon.exe` exista.
- La app normaliza `OmenMon.xml` en local para Victus/OMEN con `BiosErrorReporting=false`, `FanLevelNeedManual=true` y `FanLevelUseEc=true`.

### No se puede recompilar el `.exe`

Probablemente `AmenGamingHub.exe` sigue abierto. Cierra todas las instancias del programa y vuelve a ejecutar:

```powershell
.\build.ps1
```

## Licencia

Este proyecto se distribuye bajo Apache License 2.0. Revisa [LICENSE](D:\OneDrive\Regional\1 pendientes para analisis\proyectospython\Amen gaming hub\LICENSE).
