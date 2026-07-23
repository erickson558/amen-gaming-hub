---
name: github-publish
description: Publica cambios de Amen Gaming Hub en GitHub (repo erickson558/amen-gaming-hub) con versionado, commit, tag y push siguiendo el patrón ya usado en el proyecto. Usar cuando el usuario pida "sube a GitHub", "haz commit y push", "crea el release" o al cerrar el flujo del skill debug-fix-release.
---

# GitHub Publish

Publica el repo usando la cuenta de GitHub **ya autenticada localmente** (`erickson558`,
vía `gh` CLI, protocolo `https`). Nunca pidas, imprimas ni commitees un token — el `gh`
CLI ya gestiona la sesión con el keyring del sistema.

## Antes de empezar

```powershell
gh auth status
git remote -v
git status
```

Confirma que `origin` apunta a `https://github.com/erickson558/amen-gaming-hub.git` y que
la cuenta activa es `erickson558`. Si `gh auth status` falla, avisa al usuario — este
skill no gestiona login interactivo.

## Qué NO se sube nunca

Respeta `.gitignore` tal cual está (no fuerces `git add -f`):

- `config.json` (estado local por máquina — `ConfigManager` lo regenera si falta).
- `log.txt`, `*.exe`, `build/`, `*.spec`, `.venv/`, `__pycache__/`.
- `tools/nbfc/`, `tools/omenmon/` (herramientas descargadas localmente).

Antes de un `git add` amplio, corre `git status` y revisa la lista — si aparece algo de
la lista de arriba o cualquier archivo con datos sensibles, no lo agregues.

## Pasos

1. Si el cambio incluye una nueva versión, confirma que ya se corrió
   `python bump_version.py` (o que `amen_hub/version.py` ya se editó a mano de forma
   consistente) y que `CHANGELOG.md`/`README.md` mencionan la misma versión.
2. `git add` de los archivos concretos que cambiaron (nunca `git add -A`/`git add .`
   a ciegas).
3. Commit con conventional commits, mensaje en el mismo estilo que el historial del
   proyecto, terminando con la versión entre paréntesis:

   ```
   fix: <resumen del cambio real> (Vx.x.x)
   ```

   (o `feat:`/`chore:`/`docs:` según corresponda).
4. Tag local anotado con la misma versión:

   ```powershell
   git tag Vx.x.x
   ```

5. Push de la rama:

   ```powershell
   git push origin main
   ```

   **No hace falta `git push origin Vx.x.x`.** El workflow
   `.github/workflows/release.yml` corre en cada push a `main`, reconstruye el `.exe`,
   crea el tag remoto `Vx.x.x` si no existe y publica el GitHub Release con el `.exe`
   como artefacto — así es como se publicaron todas las versiones anteriores del
   proyecto (confirmado con `gh release list`).
6. Verifica que terminó bien:

   ```powershell
   gh run list --limit 1
   gh release view Vx.x.x --repo erickson558/amen-gaming-hub
   ```

## Si algo falla

- Si el push es rechazado por estar desactualizado, hacé `git pull --rebase origin main`
  y resolvé conflictos antes de reintentar — nunca `push --force` sin que el usuario lo
  pida explícitamente.
- Si el workflow de GitHub Actions falla, revisa el log con `gh run view --log-failed`
  antes de volver a intentar.
