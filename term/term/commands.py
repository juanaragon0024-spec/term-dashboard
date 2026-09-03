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
    "/providers":             "Ver cómo está conectada cada IA",
    "/key <proveedor> <clave>": "Guardar la API key de un proveedor",
    "/key-del <proveedor>":   "Borrar la API key guardada de un proveedor",
    "/workdir <ruta>":        "Cambiar directorio de trabajo",
    "/save":                  "Guardar la configuración en disco",
    # Archivos
    "/files":                 "Mostrar u ocultar el panel de archivos",
    "/attach <ruta>":         "Adjuntar un archivo al siguiente mensaje",
    "/detach":                "Descartar los archivos adjuntos pendientes",
    "/mkdir <ruta>":          "Crear una carpeta (con sus padres si hacen falta)",
    "/touch <ruta>":          "Crear un archivo vacío",
    "/find <patrón>":         "Buscar archivos por nombre y mostrar sus rutas",
    "/findall <patrón>":      "Buscar en todo el disco con Spotlight",
    "/grep <texto>":          "Buscar un texto dentro de los archivos",
    # Paneles
    "/help":                  "Panel de ayuda",
    "/apps":                  "Panel de aplicaciones",
    "/tools":                 "Panel de herramientas",
    "/settings":              "Panel de ajustes",
    # Sistema
    "/run <cmd>":             "Ejecutar un comando de shell y mostrar la salida",
    "/open <app>":            "Abrir una aplicación (ej. /open Safari)",
    "/close-app <app>":       "Cerrar una aplicación",
    "/browse [url]":          "Abrir una URL en el navegador",
    "/browser <nombre>":      "Establecer el navegador por defecto",
    "/web <consulta>":        "Buscar en Google desde el navegador",
    "/yt <consulta>":         "Buscar en YouTube",
    "/maps <lugar>":          "Buscar un lugar en Google Maps",
    "/volume [0-100]":        "Ver o ajustar el volumen del sistema",
    "/play":                  "Reanudar la música",
    "/pause":                 "Pausar la música",
    "/next":                  "Siguiente canción",
    "/prev":                  "Canción anterior",
    "/track":                 "Qué canción suena ahora",
    "/sysinfo":               "Batería, disco, red, volumen y música",
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
    "\nEstás en macOS y tienes shell, así que puedes actuar sobre el sistema.\n"
    "Recetas que funcionan:\n"
    "- Crear una carpeta: mkdir -p ruta/de/la/carpeta\n"
    "- Buscar archivos por nombre: mdfind -name 'parte-del-nombre'\n"
    "  (rápido, usa el índice de Spotlight; para un proyecto concreto usa `rg --files`)\n"
    "- Buscar texto dentro de archivos: rg -n 'texto' ruta/\n"
    "- Abrir una app: open -a \"Safari\"\n"
    "- Abrir una web: open 'https://ejemplo.com'\n"
    "- Buscar en Google: open 'https://www.google.com/search?q=lo+que+sea'\n"
    "- Música (Spotify o Music, el que esté abierto):\n"
    "    osascript -e 'tell application \"Spotify\" to playpause'\n"
    "    osascript -e 'tell application \"Spotify\" to next track'\n"
    "    osascript -e 'tell application \"Spotify\" to name of current track'\n"
    "- Volumen: osascript -e 'set volume output volume 50'\n\n"
    "Cuando el usuario te pida una ruta, dásela completa y absoluta.\n"
    "Antes de borrar o sobrescribir algo, pregunta.\n"
)


def build_system_context(lang: str, *, macos: bool = True) -> str:
    """Prompt de sistema que Term aporta en cada turno."""
    lang_name = LANGUAGES.get(lang, LANGUAGES["es"])
    parts = [_SYSTEM_BASE]
    if macos:
        parts.append(_MACOS_HINTS)
    parts.append(f"\nIMPORTANTE: responde siempre en {lang_name} ({lang}).")
    return "".join(parts)
