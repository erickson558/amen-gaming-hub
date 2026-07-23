---
name: debug-fix-release
description: Flujo completo de ingeniero senior Python + QA + DevOps para Amen Gaming Hub - analiza errores reales, corrige sin romper funcionalidad, valida, versiona (Vx.x.x), comenta el código, recompila el .exe y publica en GitHub. Usar cuando el usuario pida corregir errores del proyecto y subir una nueva versión.
---

# Debug → Fix → Release

Flujo de 6 fases para corregir errores de **Amen Gaming Hub** sin romper nada, dejar el
código comentado, y terminar en un release versionado publicado en GitHub. Este skill
compone `sdd-spec`, `code-commenter` y `github-publish` — no repitas sus pasos aquí,
invócalos.

## Reglas críticas (no negociables)

- **No romper funcionalidades.** El sistema ya funciona. No eliminar features
  existentes. Mantener el comportamiento actual intacto (multi-idioma, botón de
  donación, backends de ventiladores, auto-modo térmico, etc.).
- **No hacer fixes a ciegas.** Primero analizar, identificar causa raíz, luego corregir.
- **Consistencia de versión**: formato `Vx.x.x`. Incrementar según impacto (normalmente
  patch). La versión debe coincidir en: `amen_hub/version.py` (fuente única de verdad),
  título de la ventana, `README.md`, `CHANGELOG.md`, mensaje de commit, tag de git y
  release de GitHub.

## Fase 1 — Análisis (obligatoria, antes de tocar código)

Identifica errores o problemas potenciales reales (no inventados): bugs funcionales,
errores de lógica, manejo incorrecto de excepciones, problemas de rendimiento,
problemas de concurrencia (GUI que se congela — revisa que todo trabajo pesado siga
yendo por `threading.Thread` + `queue.Queue` + `root.after`, nunca en el hilo principal
de Tkinter). Para cada hallazgo: causa raíz, impacto, riesgo de corregirlo. Si el
hallazgo implica una feature nueva o un cambio de comportamiento visible, usa el skill
`sdd-spec` para documentarlo antes de seguir.

## Fase 2 — Corrección

Corrige solo lo identificado en la Fase 1. Mejora manejo de errores/validaciones/
estabilidad donde haga falta, sin sobre-ingeniería. Código limpio y legible.

## Fase 3 — Validación

Antes de commitear:

```powershell
python -m py_compile app.py amen_hub\backend\fan_controller.py amen_hub\backend\telemetry.py amen_hub\frontend\main_window.py amen_hub\config.py amen_hub\i18n.py amen_hub\logger.py amen_hub\paths.py amen_hub\subprocess_utils.py amen_hub\tk_runtime.py amen_hub\version.py bump_version.py
python -c "import app; print('APP_IMPORT_OK')"
```

Smoke test manual con `python app.py` (backend `mock` si no hay hardware HP a mano):
abrir, cambiar idioma, click en donar, aplicar velocidades, activar/desactivar modo auto.

Si el usuario también pidió comentar el código, usa el skill `code-commenter` aquí,
antes de congelar la versión final.

## Fase 4 — Versionado

```powershell
python bump_version.py
```

Actualiza `CHANGELOG.md` (nueva entrada `Vx.x.x` con fecha y resumen real de lo
corregido) y la línea de versión en `README.md`.

## Fase 5 — Recompilar el `.exe`

```powershell
.\build.ps1
```

Confirma que `AmenGamingHub.exe` quedó en la raíz junto a `app.py`, usando el `.ico`
que ya exista (prioriza `app.ico`, si no el primer `*.ico`). Si falla porque el `.exe`
sigue abierto, pídele al usuario cerrarlo y reintenta.

## Fase 6 — Commit + tag + push

Usa el skill `github-publish` para el commit (conventional commit terminando en
`(Vx.x.x)`), tag local y push a `main`.

## Entregables (responder siempre en este orden)

1. **Análisis de errores**: lista de problemas encontrados, causa raíz, impacto.
2. **Cambios realizados**: qué se corrigió y cómo.
3. **Nueva versión**: número y justificación (patch/minor/major).
4. **Código actualizado**: diffs concretos (no fragmentos ambiguos si el cambio es
   crítico).
5. **Commit message** propuesto.
6. **Comandos paso a paso** (`git add`, `git commit`, `git tag`, `git push origin main`)
   con una explicación breve de cada uno.
