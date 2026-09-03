"""Catalogo de comandos, atajos y prompt de sistema."""

from __future__ import annotations

from .i18n import LANGUAGES

__all__ = [
    "COMMANDS_HELP",
    "COMMAND_NAMES",
    "SHORTCUTS_HELP",
    "build_system_context",
    "complete_command",
]

COMMANDS_HELP: dict[str, str] = {
    # Conversacion
    "/new [nombre] [modelo]": "Nueva tab (ej. /new MiChat opus)",
    "/close":                 "Cerrar tab activa",
    "/clear":                 "Limpiar chat y empezar una sesión nueva",
    "/sessions":              "Listar sesiones guardadas",
    "/resume <n>":            "Retomar una sesión guardada",
    "/search <texto>":        "Buscar en la conversación de esta tab",
    "/name <texto>":          "Renombrar la tab activa",
    "/history":               "Cantidad de mensajes en esta tab",
    "/export":                "Guardar la conversación en un archivo",
    "/copy":                  "Copiar la última respuesta al portapapeles",
    "/code [n]":              "Copiar el bloque de código n de la última respuesta",
    # Configuracion
    "/model <nombre|id>":     "Cambiar modelo (default, opus, sonnet, haiku o un id)",
    "/effort <nivel>":        "Nivel de esfuerzo (low, medium, high, max)",
    "/theme <nombre>":        "Cambiar tema (neon, dracula, monokai, catppuccin, gruvbox, tokyo)",
    "/lang [código]":         f"Cambiar idioma ({', '.join(LANGUAGES)})",
    "/permissions [modo]":    "Modo de permisos (default, acceptEdits, plan, bypassPermissions)",
    "/workdir <ruta>":        "Cambiar directorio de trabajo",
    "/save":                  "Guardar la configuración en disco",
    # Archivos
    "/files":                 "Mostrar u ocultar el panel de archivos",
    "/attach <ruta>":         "Adjuntar un archivo al siguiente mensaje",
    "/detach":                "Descartar los archivos adjuntos pendientes",
    # Paneles
    "/help":                  "Panel de ayuda",
    "/apps":                  "Panel de aplicaciones",
    "/tools":                 "Panel de herramientas",
    "/settings":              "Panel de ajustes",
    # Sistema
    "/run <cmd>":             "Ejecutar un comando de shell y mostrar la salida",
    "/open <app>":            "Abrir una aplicación (ej. /open Safari)",
    "/browse [url]":          "Abrir una URL en el navegador",
    "/browser <nombre>":      "Establecer el navegador por defecto",
    "/volume <0-100>":        "Ajustar el volumen del sistema",
    "/play":                  "Play/pausa en Spotify",
    "/next":                  "Siguiente canción en Spotify",
    "/prev":                  "Canción anterior en Spotify",
    "/track":                 "Canción que suena ahora en Spotify",
    # Meta
    "/status":                "Estado actual de la tab",
    "/reset":                 "Reiniciar el contador de contexto",
    "/version":               "Versión de Term",
    "/about":                 "Acerca de Term",
    "/quit":                  "Salir de Term",
}

# Nombre pelado de cada comando, para autocompletar.
COMMAND_NAMES: list[str] = [c.split()[0] for c in COMMANDS_HELP]

SHORTCUTS_HELP: dict[str, str] = {
    "enter":        "Enviar el mensaje",
    "alt+enter":    "Salto de línea dentro del mensaje",
    "up / down":    "Recorrer los mensajes que ya has enviado",
    "tab":          "Autocompletar el comando que estás escribiendo",
    "ctrl+t":       "Nueva tab",
    "ctrl+w":       "Cerrar la tab o el panel activo",
    "ctrl+1..9":    "Saltar a la tab n",
    "ctrl+l":       "Limpiar el chat",
    "ctrl+e":       "Cambiar el nivel de esfuerzo",
    "ctrl+b":       "Mostrar u ocultar el panel de archivos",
    "ctrl+y":       "Copiar la última respuesta",
    "escape":       "Cancelar la generación o cerrar el panel",
    "ctrl+c":       "Salir",
}


def complete_command(prefix: str) -> tuple[str, list[str]]:
    """Completar un comando a medio escribir.

    Devuelve `(completado, candidatos)`. `completado` es el prefijo comun mas
    largo, para que pulsar tab avance aunque haya varias opciones.
    """
    prefix = prefix.strip()
    if not prefix.startswith("/"):
        return prefix, []
    matches = [c for c in COMMAND_NAMES if c.startswith(prefix)]
    if not matches:
        return prefix, []
    if len(matches) == 1:
        return matches[0] + " ", matches

    common = matches[0]
    for candidate in matches[1:]:
        while not candidate.startswith(common):
            common = common[:-1]
    return common, matches


_SYSTEM_BASE = (
    "Eres Term, un asistente que vive en una TUI de terminal.\n"
    "Tienes acceso al shell del usuario a través de tus herramientas.\n\n"
    "Formato: tus respuestas se pintan como Markdown en un terminal estrecho. "
    "Sé conciso, usa bloques de código con su lenguaje y evita tablas anchas.\n"
)

_MACOS_HINTS = (
    "\nEstás en macOS. Para controlar el sistema usa osascript:\n"
    "- Abrir una app: open -a \"Safari\"\n"
    "- Play/pausa: osascript -e 'tell application \"Spotify\" to playpause'\n"
    "- Canción siguiente: osascript -e 'tell application \"Spotify\" to next track'\n"
    "- Volumen: osascript -e 'set volume output volume 50'\n"
)


def build_system_context(lang: str, *, macos: bool = True) -> str:
    """Prompt de sistema que Term aporta en cada turno."""
    lang_name = LANGUAGES.get(lang, LANGUAGES["es"])
    parts = [_SYSTEM_BASE]
    if macos:
        parts.append(_MACOS_HINTS)
    parts.append(f"\nIMPORTANTE: responde siempre en {lang_name} ({lang}).")
    return "".join(parts)
