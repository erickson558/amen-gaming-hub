---
name: code-commenter
description: Agrega comentarios explicativos en español al código de Amen Gaming Hub sin cambiar su comportamiento. Usar cuando el usuario pida comentar el código, entender qué hace cada parte, o documentar una función/módulo.
---

# Code Commenter

Objetivo: que cualquiera pueda leer un archivo de este proyecto y entender qué hace cada
parte, sin tener que ejecutar el código. **Nunca cambia comportamiento.**

## Reglas

1. **Comentarios en español** (el resto de la documentación del proyecto — README,
   CHANGELOG, mensajes de estado de la UI — ya es mayormente en español).
2. Comentar:
   - Propósito del módulo (encabezado, 1-3 líneas).
   - Rol de cada clase y de cada método/función pública (qué hace, qué recibe, qué
     devuelve, sin repetir literalmente los tipos que ya están en la firma).
   - Lógica no obvia: expresiones regulares, fórmulas (ej. interpolación de la curva
     térmica en `main_window.py`, conversión de porcentaje a nivel de ventilador en
     `fan_controller.py`), condiciones de carrera evitadas (debounce de "aplicar en
     vivo"), decisiones de negocio (por qué se descarta una lectura de `98 °C` en
     `telemetry.py`, por qué se bloquean controles sin permisos de Administrador).
3. **No comentar lo obvio**: si el nombre de la variable/función ya lo dice
   (`_on_exit`, `is_running`), no repitas eso en un comentario.
4. No agregar docstrings multi-párrafo ni bloques de comentarios largos — una o dos
   líneas por bloque, altura de comentario proporcional a lo no obvio que es el código.
5. No tocar: nombres de variables/funciones, strings mostrados al usuario, valores por
   defecto, orden de ejecución, manejo de errores existente.
6. Si al leer el código encontrás algo que parece un bug real, **no lo arregles en este
   pase** — anótalo aparte para que se resuelva con el flujo de
   `debug-fix-release`/`python-qa-release-engineer`.

## Cómo aplicarlo

1. Leé el archivo completo antes de editar (para no comentar sin contexto).
2. Agregá los comentarios con la menor cantidad de diffs posible — no reformatees
   líneas que no estás comentando.
3. Después de cada archivo, corré:

   ```powershell
   python -m py_compile <archivo>
   ```

   para confirmar que sigue siendo sintácticamente válido.
4. Al terminar todos los archivos de una pasada, corré la validación completa:

   ```powershell
   python -m py_compile app.py amen_hub\backend\fan_controller.py amen_hub\backend\telemetry.py amen_hub\frontend\main_window.py amen_hub\config.py amen_hub\i18n.py amen_hub\logger.py amen_hub\paths.py amen_hub\subprocess_utils.py amen_hub\tk_runtime.py amen_hub\version.py
   python -c "import app; print('APP_IMPORT_OK')"
   ```
