# Changelog

## V0.0.16 - 2026-03-17

- Se corrige la invocacion de `OmenMon.exe` para rutas con espacios.
- Se elimina el wrapper roto por `cmd.exe` que producia el error `"OmenMon.exe" no se reconoce como un comando interno o externo`.
- La ejecucion de `OmenMon` queda por `CreateProcess` directo desde Python, evitando el bug de quoting en el `.exe`.

## V0.0.15 - 2026-03-17

- Se agrega backend `omenmon` para equipos HP Victus/OMEN.
- `auto` ahora prioriza `OmenMon` antes de `NBFC` cuando la herramienta local existe.
- La app normaliza `tools/omenmon/OmenMon.xml` para mejorar compatibilidad en Victus/OMEN.
- Se mejora el fallback cuando falta un backend real, devolviendo errores claros en lugar de caer silenciosamente a un backend incorrecto.
- Se documenta el flujo recomendado HP/OMEN en `README.md`.
