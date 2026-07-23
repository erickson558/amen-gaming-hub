# 0001 - Endurecimiento de subprocess, higiene de git y tooling SDD/Agents/Skills

- Estado: Implementado
- Versión objetivo: V0.0.26
- Autor/sesión: Sesión de corrección de errores + adopción de Spec-Driven Development

## Problema

1. `NBFCFanController._run` y `CommandTemplateFanController.apply_fan_speeds` en
   [amen_hub/backend/fan_controller.py](../amen_hub/backend/fan_controller.py) no
   capturaban `subprocess.TimeoutExpired`/`OSError`/`ValueError`, a diferencia de
   `OmenMonFanController._run`, que sí lo hacía. Un timeout o un ejecutable movido a
   mitad de ejecución producía una excepción sin manejar en vez de un mensaje de error
   limpio para el usuario.
2. `config.json` estaba versionado en git desde el primer commit, pese a que
   `README.md` y `CONTRIBUTING.md` dicen explícitamente que no debe versionarse
   (contiene estado local por máquina: `window_geometry`, y un campo `app_password`).
3. El proyecto no tenía ningún proceso formal de Spec-Driven Development, ni Agents ni
   Skills de Claude Code, así que cada sesión de trabajo debía re-explicar el flujo de
   versionado/commit/push desde cero.
4. El código no tenía comentarios explicando qué hace cada parte.

## Objetivo

- Los tres backends de ventiladores manejan errores de subprocess de forma consistente.
- `config.json` deja de versionarse (el archivo local no se toca; `ConfigManager` ya lo
  regenera si falta).
- Existe un directorio `specs/` con el proceso SDD documentado.
- Existen agentes (`.claude/agents/`) y skills (`.claude/skills/`) reutilizables para:
  crear specs, comentar código, y ejecutar el flujo completo de
  análisis→corrección→validación→versionado→commit→push→GitHub.
- El código fuente queda comentado en español, sin cambiar comportamiento.

## No-objetivo

- No se rediseña la arquitectura de backends (`omenmon`/`nbfc`/`command`/`mock`/`auto`).
- No se agregan idiomas nuevos ni se toca el botón de donación — ya existían desde
  `V0.0.24`/`V0.0.25` y quedan intactos.
- No se agregan tests automatizados (fuera de alcance de este spec).

## Diseño

- El fix de `fan_controller.py` espeja el patrón ya usado en `OmenMonFanController._run`:
  envolver el `subprocess.run` en `try/except` y devolver un mensaje accionable en vez de
  dejar escapar la excepción.
- `config.json` se destrackea con `git rm --cached` (no `rm` — el archivo sigue en disco)
  y se agrega a `.gitignore`.
- SDD vive en `specs/` en la raíz (no bajo `.claude/`) para que cualquier colaborador lo
  vea sin necesitar Claude Code.
- Agents (`.claude/agents/*.md`) definen personas con herramientas concretas; Skills
  (`.claude/skills/<nombre>/SKILL.md`) definen procedimientos reutilizables que esos
  agentes invocan en vez de reinventar los pasos cada sesión.
- Los comentarios de código se agregan a nivel de módulo/clase/función y en la lógica no
  obvia (parsing de sensores OmenMon, curva térmica, debounce de aplicar-en-vivo,
  bloqueo por permisos de Administrador) — nunca reescribiendo lo que el código ya dice
  por sí mismo con nombres claros.

## Criterio de aceptación

- [x] `python -m py_compile` sobre todos los `.py` tocados sin errores.
- [x] `python -c "import app"` sin errores.
- [x] `config.json` fuera de `git ls-files`, pero presente en disco.
- [x] `.claude/agents/` y `.claude/skills/` commiteados.
- [x] `AmenGamingHub.exe` recompilado en la raíz con el ícono existente.
- [x] Multi-idioma y botón de donación siguen funcionando (smoke test manual).
- [x] `CHANGELOG.md`, `README.md` y `CONTRIBUTING.md` actualizados a `V0.0.26`.
- [x] Commit + tag `V0.0.26` + push a `main` en `erickson558/amen-gaming-hub`.

## Riesgo / compatibilidad

Cambios de bajo riesgo: el fix de excepciones solo agrega manejo, no cambia la lógica de
éxito; destrackear `config.json` es seguro porque `ConfigManager._load()` autogenera el
archivo si no existe; comentar código y agregar `specs/`/`.claude/` no toca rutas de
ejecución.
