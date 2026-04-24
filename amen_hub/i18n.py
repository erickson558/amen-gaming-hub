"""Multi-language support for Amen Gaming Hub.

Add new languages by inserting a new key into each TRANSLATIONS entry.
The Translator class picks the closest available language, falling back to
DEFAULT_LANGUAGE when an unknown code is requested.
"""
from __future__ import annotations

# Supported language codes -> display name shown in the menu
SUPPORTED_LANGUAGES: dict[str, str] = {
    "es": "Español",
    "en": "English",
}

# The language used when no valid language is configured
DEFAULT_LANGUAGE = "es"

# fmt: off
TRANSLATIONS: dict[str, dict[str, str]] = {

    # ---- Static UI labels ------------------------------------------------
    "subtitle":           {"es": "Control Termico y Potencia",   "en": "Thermal Control and Power"},
    "card_temps":         {"es": "Temperaturas (°C)",            "en": "Temperatures (°C)"},
    "card_fans":          {"es": "Ventiladores",                 "en": "Fans"},
    "card_options":       {"es": "Opciones",                     "en": "Options"},
    "fan_cpu_dial":       {"es": "Dial FAN CPU",                 "en": "FAN CPU Dial"},
    "fan_cpu_manual":     {"es": "CPU manual:",                  "en": "CPU manual:"},
    "fan_gpu_dial":       {"es": "Dial FAN GPU",                 "en": "FAN GPU Dial"},
    "fan_gpu_manual":     {"es": "GPU manual:",                  "en": "GPU manual:"},

    # ---- Options section -------------------------------------------------
    "opt_autostart":      {"es": "Autoiniciar proceso al abrir", "en": "Auto-start on open"},
    "opt_auto_thermal":   {"es": "Modo auto termico",            "en": "Auto thermal mode"},
    "opt_live_apply":     {"es": "Aplicar en vivo",              "en": "Apply live"},
    "opt_restore_auto":   {"es": "Volver a auto al salir",       "en": "Restore auto on exit"},
    "opt_autoclose":      {"es": "Autocerrar",                   "en": "Auto-close"},
    "opt_autoclose_secs": {"es": "Segundos autocierre:",         "en": "Auto-close seconds:"},
    "opt_backend":        {"es": "Backend ventiladores:",        "en": "Fan backend:"},
    "opt_nbfc_profile":   {"es": "Perfil NBFC:",                 "en": "NBFC Profile:"},
    "opt_password":       {"es": "Password (opcional):",         "en": "Password (optional):"},

    # ---- Buttons ---------------------------------------------------------
    "btn_show":           {"es": "Mostrar",                      "en": "Show"},
    "btn_hide":           {"es": "Ocultar",                      "en": "Hide"},
    "btn_apply":          {"es": "Aplicar",                      "en": "Apply"},
    "btn_repair_nbfc":    {"es": "Reparar NBFC",                 "en": "Repair NBFC"},
    "btn_diagnose_nbfc":  {"es": "Diagnóstico NBFC",             "en": "NBFC Diagnostics"},
    "btn_exit":           {"es": "Salir",                        "en": "Exit"},
    "btn_donate":         {"es": "☕ Comprame una cerveza",      "en": "☕ Buy me a beer"},
    "btn_close":          {"es": "Cerrar",                       "en": "Close"},

    # ---- Menu ------------------------------------------------------------
    "menu_file":          {"es": "Archivo",                      "en": "File"},
    "menu_apply":         {"es": "Aplicar",                      "en": "Apply"},
    "menu_exit":          {"es": "Salir",                        "en": "Exit"},
    "menu_help":          {"es": "Ayuda",                        "en": "Help"},
    "menu_about":         {"es": "About",                        "en": "About"},
    "menu_language":      {"es": "Idioma",                       "en": "Language"},
    "menu_donate":        {"es": "☕ Donar",                     "en": "☕ Donate"},

    # ---- Status messages (simple) ----------------------------------------
    "st_ready":           {"es": "Listo",                        "en": "Ready"},
    "st_applying":        {
        "es": "Aplicando velocidades de ventilador...",
        "en": "Applying fan speeds...",
    },
    "st_autoclose_done":  {"es": "Autocierre ejecutado",         "en": "Auto-close executed"},
    "st_pass_visibility": {
        "es": "Cambio de visibilidad de password",
        "en": "Password visibility changed",
    },
    "st_live_on":         {"es": "Aplicacion en vivo activada.", "en": "Live apply enabled."},
    "st_live_off":        {"es": "Aplicacion en vivo desactivada.", "en": "Live apply disabled."},
    "st_auto_on":         {
        "es": "Modo auto termico activo. La app ajustara ventiladores segun la temperatura.",
        "en": "Auto thermal mode active. The app will adjust fans based on temperature.",
    },
    "st_auto_off":        {
        "es": "Modo auto termico desactivado. Controles manuales restaurados.",
        "en": "Auto thermal mode disabled. Manual controls restored.",
    },
    "st_auto_block":      {
        "es": "Modo auto termico activo. Desactivalo si quieres aplicar valores manuales.",
        "en": "Auto thermal mode active. Disable it to apply manual values.",
    },
    "st_diagnosing":      {
        "es": "Ejecutando diagnóstico NBFC...",
        "en": "Running NBFC diagnostics...",
    },
    "st_diagnosis_done":  {
        "es": "Diagnóstico NBFC completado. Haz clic en el botón para ver detalles.",
        "en": "NBFC diagnostics completed. Click the button to see details.",
    },
    "st_repairing":       {"es": "Intentando reparar NBFC...",  "en": "Attempting NBFC repair..."},
    "st_repair_no_admin": {
        "es": "Reparar NBFC requiere ejecutar la app como Administrador.",
        "en": "Repairing NBFC requires running the app as Administrator.",
    },
    "st_no_nbfc_diag":    {
        "es": "El backend activo no es NBFC. Cambia a NBFC para diagnóstico.",
        "en": "Active backend is not NBFC. Switch to NBFC for diagnostics.",
    },
    "st_no_nbfc_repair":  {
        "es": "El backend activo no es NBFC. Cambia a NBFC para reparar.",
        "en": "Active backend is not NBFC. Switch to NBFC for repair.",
    },
    "st_auto_waiting":    {
        "es": "Modo auto termico activo. Esperando telemetria de temperatura.",
        "en": "Auto thermal mode active. Waiting for temperature telemetry.",
    },
    "st_auto_status":     {
        "es": "Modo auto termico: CPU {cpu_temp} -> {cpu_target}% | GPU {gpu_temp} -> {gpu_target}%",
        "en": "Auto thermal mode: CPU {cpu_temp} -> {cpu_target}% | GPU {gpu_temp} -> {gpu_target}%",
    },
    "st_auto_require_admin": {
        "es": "{status} | requiere Administrador para aplicar",
        "en": "{status} | requires Administrator to apply",
    },
    "st_auto_applied":    {"es": "{status} | aplicado",      "en": "{status} | applied"},
    "st_auto_failed":     {"es": "Modo auto no pudo aplicar: {message}", "en": "Auto mode could not apply: {message}"},
    "st_auto_calculated": {"es": "{status} | calculado",     "en": "{status} | calculated"},
    "st_auto_keep_curve": {"es": "{status} | manteniendo curva", "en": "{status} | keeping curve"},
    "st_browser_error":   {"es": "No se pudo abrir el navegador: {error}", "en": "Could not open browser: {error}"},

    # ---- Status format-string templates — call .format(**kwargs) ---------
    # {prefix}: prefix label, {backend}: backend description
    "st_backend_base":        {"es": "{prefix}: {backend}",      "en": "{prefix}: {backend}"},
    # {message}: the base backend message
    "st_backend_admin_block": {
        "es": "{message} | Control bloqueado: abre la app como Administrador",
        "en": "{message} | Control blocked: run the app as Administrator",
    },
    "st_backend_no_admin":    {
        "es": "{message} | Sin Administrador: algunas lecturas pueden ser limitadas",
        "en": "{message} | No Administrator: some readings may be limited",
    },
    # {backend}: controller description
    "st_perm_blocked":        {
        "es": "Control bloqueado: el backend {backend} requiere abrir la app como Administrador.",
        "en": "Control blocked: backend {backend} requires running the app as Administrator.",
    },

    # ---- Prefix labels for backend status (passed as {prefix}) ----------
    "prefix_active":      {"es": "Backend activo",               "en": "Active backend"},
    "prefix_changed":     {"es": "Backend cambiado",             "en": "Backend changed"},

    # ---- About dialog ----------------------------------------------------
    "about_title":        {"es": "About",                        "en": "About"},
    "about_body":         {
        "es": "Amen Gaming Hub {version}\nApache License 2.0\nSynyster Rick, {year}",
        "en": "Amen Gaming Hub {version}\nApache License 2.0\nSynyster Rick, {year}",
    },

    # ---- Diagnose popup --------------------------------------------------
    "diag_title":         {"es": "Diagnóstico NBFC",             "en": "NBFC Diagnostics"},
}
# fmt: on


class Translator:
    """Holds the active language and maps translation keys to strings.

    Usage:
        tr = Translator("en")
        tr.t("btn_apply")                  # -> "Apply"
        tr.t("st_backend_base", prefix="Active backend", backend="omenmon")
    """

    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        # Normalise to a known code; fall back to default quietly
        self._language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

    @property
    def language(self) -> str:
        return self._language

    @language.setter
    def language(self, lang: str) -> None:
        self._language = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

    def t(self, key: str, **kwargs: str) -> str:
        """Return the translated string for *key* in the active language.

        Keyword arguments are forwarded to ``str.format()`` for template keys.
        Falls back to DEFAULT_LANGUAGE if the active language has no entry,
        and to the raw key string if neither has an entry.
        """
        entry = TRANSLATIONS.get(key)
        if entry is None:
            return key
        text = entry.get(self._language) or entry.get(DEFAULT_LANGUAGE) or key
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError):
                return text
        return text
