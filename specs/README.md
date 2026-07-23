# Spec-Driven Development (SDD) — Amen Gaming Hub

Este proyecto usa un flujo simple de "spec antes que código": cualquier feature nueva o
cualquier corrección no trivial arranca con un spec corto en este directorio, **antes**
de tocar `amen_hub/` o `app.py`.

## Cuándo escribir un spec

- Feature nueva (ej.: nuevo backend de ventiladores, nuevo idioma, nueva pantalla).
- Cambio de comportamiento visible para el usuario (UI, versionado, empaquetado).
- Refactor que toca más de un módulo.

## Cuándo NO hace falta

- Typos, ajustes de estilo, fixes de una línea, bump de versión.
- Cambios ya cubiertos por un spec existente (actualiza ese spec en vez de crear uno nuevo).

## Cómo se numeran

`NNNN-titulo-corto.md`, incremental, empezando en `0001`. Usa
[TEMPLATE.md](TEMPLATE.md) como base.

## Ciclo de vida de un spec

1. Se crea con estado `Propuesto`.
2. Se implementa el código según el spec (o se ajusta el spec si la implementación revela
   algo que el spec no había previsto — el spec se actualiza, no queda desincronizado).
3. Al mergear a `main` pasa a estado `Implementado` y se referencia la versión (`Vx.x.x`)
   y el commit donde se completó.

## Relación con Agents y Skills

- El skill `sdd-spec` (`.claude/skills/sdd-spec/SKILL.md`) crea/gestiona estos archivos.
- El agente `python-qa-release-engineer` (`.claude/agents/python-qa-release-engineer.md`)
  revisa si un cambio pedido necesita spec antes de empezar a programar.
