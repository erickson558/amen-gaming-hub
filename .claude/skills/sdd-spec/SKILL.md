---
name: sdd-spec
description: Crea o actualiza specs de Spec-Driven Development bajo specs/ antes de implementar una feature nueva o un cambio de comportamiento visible en Amen Gaming Hub. Usar cuando el usuario pida una feature, un cambio de UI, o cuando vayas a tocar más de un módulo.
---

# SDD Spec

Este proyecto documenta cambios no triviales en `specs/` **antes** de tocar código
(ver `specs/README.md`). Este skill crea/actualiza esos archivos.

## Cuándo usarlo

- Feature nueva (nuevo backend, nuevo idioma, nueva pantalla, nueva opción persistente).
- Cambio de comportamiento visible (UI, versionado, empaquetado del `.exe`).
- Refactor que toca más de un módulo de `amen_hub/`.

No lo uses para: typos, fixes de una línea, bump de versión, cambios ya cubiertos por un
spec existente (en ese caso, actualiza el spec existente en vez de crear uno nuevo).

## Pasos

1. Lee `specs/README.md` y `specs/TEMPLATE.md`.
2. Revisa `specs/` para encontrar el número más alto usado y calcula el siguiente
   (`NNNN`, cuatro dígitos, incremental).
3. Copia la estructura de `TEMPLATE.md` a `specs/NNNN-titulo-corto.md` con:
   - Problema (qué falta/falla y por qué se pide).
   - Objetivo y no-objetivo (para evitar scope creep).
   - Diseño: archivos afectados, approach elegido, alternativas descartadas.
   - Criterio de aceptación: checklist verificable (comandos o pasos manuales en la UI).
   - Riesgo/compatibilidad: qué podría romper y cómo se mitiga.
4. Marca el spec como `Propuesto` hasta implementar, `Implementado` al terminar
   (referenciando la versión `Vx.x.x` final).
5. Si durante la implementación algo del spec cambia, actualiza el spec — no lo dejes
   desincronizado del código real.

No implementes código dentro de este skill: su única salida es el archivo de spec.
