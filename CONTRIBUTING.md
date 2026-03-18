# Contributing

## Flujo recomendado

1. Crear y activar `.venv`.
2. Instalar dependencias con `pip install -r requirements.txt`.
3. Validar source:

```powershell
python -m py_compile app.py amen_hub\backend\fan_controller.py amen_hub\frontend\main_window.py amen_hub\version.py bump_version.py
python -c "import app; print('APP_IMPORT_OK')"
```

4. Incrementar version antes de commitear:

```powershell
python bump_version.py
```

5. Recompilar:

```powershell
.\build.ps1
```

## Reglas del repositorio

- Cada commit funcional debe crear una nueva version `Vx.x.x`.
- `APP_VERSION` en `amen_hub/version.py` es la fuente unica de verdad.
- No versionar `config.json` local.
- No versionar binarios descargados en `tools/`.
- No versionar ejecutables generados.

## Releases

- El push a `main` dispara el workflow de release.
- El tag de GitHub debe coincidir con la version mostrada por la app.
- El artefacto publicado es `AmenGamingHub.exe`.

## Licencia

Al contribuir aceptas que los cambios se distribuyen bajo Apache License 2.0.
