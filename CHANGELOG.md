# Changelog

## V0.0.21 - 2026-03-17

- Se corrige la lectura de temperatura CPU en equipos HP Victus/OMEN para priorizar sensores EC de `OmenMon` en lugar de depender solo de `BIOS Temp`.
- La telemetria ahora prioriza `CPUT` y hace fallback por otros sensores termicos EC antes de caer a lecturas genericas.
- Se descartan lecturas invalidas de `0 °C` y el valor atascado `98 °C` de `TNT2`, que en algunos modelos Victus no representa una temperatura real.

## V0.0.20 - 2026-03-17

- La app detecta cuando el backend activo requiere permisos de Administrador y el proceso no esta elevado.
- En ese caso, la UI bloquea `Aplicar`, sliders, `Modo auto termico`, `Aplicar en vivo` y `Volver a auto al salir`, para evitar intentos a medias.
- Si el usuario abre la app sin elevacion, cualquier `Modo auto termico` persistido se desactiva para no dejar el sistema en un estado ambiguo.
- Se agrega una advertencia visible en la UI y mensajes de estado mas claros al cambiar backend o intentar usar funciones restringidas.
- `Reparar NBFC` ahora se bloquea desde UI cuando no hay permisos de Administrador.

## V0.0.19 - 2026-03-17

- Se agrega `Aplicar en vivo` para que los ventiladores se ajusten al mover los diales, sin usar el boton `Aplicar`.
- La aplicacion en vivo usa debounce para evitar saturar el hardware con cambios continuos mientras arrastras los sliders.
- Se agrega `Volver a auto al salir` para restaurar el control automatico del sistema antes de cerrar la app.
- El backend implementa restauracion explicita de auto-control para `OmenMon` y `NBFC`.

## V0.0.18 - 2026-03-17

- Se agrega `Modo auto termico` para ajustar ventiladores segun la temperatura CPU/GPU.
- El modo auto usa una curva termica balanceada y evita re-aplicar cambios identicos en cada ciclo.
- Mientras el modo auto esta activo, los controles manuales quedan bloqueados y la UI muestra el porcentaje objetivo calculado.
- Los ultimos valores manuales se conservan para restaurarlos al desactivar el modo auto.

## V0.0.17 - 2026-03-17

- Se ocultan de forma consistente las ventanas de consola de procesos auxiliares (`OmenMon`, `PowerShell`, `nvidia-smi`, `NBFC`) usando un wrapper comun para subprocesos Windows.
- La telemetria se dispara al abrir la app y sigue en ciclo sin solapar hilos, para que el monitoreo sea mas fluido.
- La UI muestra temperaturas con notacion explicita `°C`.
- Se agrega una ruta HP/OMEN para lectura de temperatura CPU usando `OmenMon` cuando esta disponible.

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
