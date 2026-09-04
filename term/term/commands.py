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

# Los comandos van agrupados porque la ayuda los enseña asi: cincuenta
# comandos en una sola lista son un muro que nadie lee. La clave de cada grupo
# es la de su titulo traducido.
COMMAND_GROUPS: dict[str, dict[str, str]] = {
    "grp_chat": {
        "/new [nombre] [modelo]": "Nueva pestaña, opcionalmente con su IA",
        "/close":                 "Cerrar la pestaña activa",
        "/clear":                 "Limpiar el chat y empezar una sesión nueva",
        "/sessions":              "Listar las conversaciones guardadas",
        "/resume <n>":            "Retomar una conversación guardada",
        "/search <texto>":        "Buscar dentro de esta conversación",
        "/name <texto>":          "Renombrar la pestaña activa",
        "/history":               "Cuántos mensajes lleva esta pestaña",
        "/export":                "Guardar la conversación en un archivo",
        "/copy":                  "Copiar la última respuesta",
        "/code [n]":              "Copiar el bloque de código n de la última respuesta",
    },
    "grp_ai": {
        "/model <proveedor/modelo>": "Cambiar la IA de esta pestaña",
        "/providers":             "Ver cómo está conectada cada IA",
        "/key <proveedor> <clave>": "Guardar la API key de un proveedor",
        "/key-del <proveedor>":   "Borrar una API key guardada",
        "/effort <nivel>":        "Nivel de esfuerzo (low, medium, high, max)",
        "/architect [modelo]":    "Que otro modelo planifique antes de ejecutar",
        "/skeleton":              "Pasar el esqueleto del código en vez de la lista de archivos",
        "/permissions [modo]":    "Modo de permisos (default, acceptEdits, plan, bypassPermissions)",
        "/allow [perfil]":        "Qué herramientas puede usar la IA (todo, lectura, segura, nada)",
        "/mcp":                   "Servidores MCP y sus herramientas",
        "/mcp-add <nombre> <cmd>": "Añadir un servidor MCP",
        "/mcp-del <nombre>":      "Quitar un servidor MCP",
        "/compact":               "Resumir la conversación para liberar contexto",
    },
    "grp_git": {
        "/status":                "Qué has cambiado en el repositorio",
        "/diff":                  "Ver los cambios sin confirmar",
        "/commit [mensaje]":      "Guardar los cambios; sin mensaje lo escribe la IA",
        "/undo":                  "Deshacer el último commit sin perder el trabajo",
        "/gitlog":                "Últimos commits",
    },
    "grp_files": {
        "/mkdir <ruta>":          "Crear una carpeta, con sus padres si hacen falta",
        "/touch <ruta>":          "Crear un archivo vacío",
        "/find <patrón>":         "Buscar archivos aquí y mostrar sus rutas",
        "/findall <patrón>":      "Buscar en todo el disco con Spotlight",
        "/grep <texto>":          "Buscar un texto dentro de los archivos",
        "/files":                 "Mostrar u ocultar el panel de archivos",
        "/add <ruta>":            "Meter un archivo en el contexto de la conversación",
        "/drop <ruta>":           "Sacar un archivo del contexto",
        "/context":               "Ver qué archivos están en el contexto",
        "/map":                   "Ver el mapa del proyecto",
        "/outline [ruta]":        "Ver clases y funciones con su firma",
        "/attach <ruta>":         "Adjuntar un archivo solo al siguiente mensaje",
        "/detach":                "Descartar los archivos adjuntos pendientes",
        "/workdir <ruta>":        "Cambiar el directorio de trabajo",
    },
    "grp_system": {
        "/run <cmd>":             "Ejecutar un comando y esperar su salida",
        "/bg <cmd>":              "Lanzar un comando en segundo plano (servidor, tests…)",
        "/jobs":                  "Ver los procesos en segundo plano",
        "/logs [n] [texto]":      "Ver la salida de un proceso, filtrando si quieres",
        "/stop [n]":              "Parar un proceso; sin número, todos",
        "/open <app>":            "Abrir una aplicación",
        "/close-app <app>":       "Cerrar una aplicación",
        "/web <consulta>":        "Buscar en Google desde el navegador",
        "/yt <consulta>":         "Buscar en YouTube",
        "/maps <lugar>":          "Buscar un lugar en Google Maps",
        "/browse [url]":          "Abrir una URL en el navegador",
        "/browser <nombre>":      "Elegir el navegador por defecto",
        "/play":                  "Reanudar la música",
        "/pause":                 "Pausar la música",
        "/next":                  "Siguiente canción",
        "/prev":                  "Canción anterior",
        "/track":                 "Qué canción suena ahora",
        "/volume [0-100]":        "Ver o ajustar el volumen",
        "/sysinfo":               "Batería, disco, red, volumen y música",
    },
    "grp_look": {
        "/theme <nombre>":        "Cambiar el tema de color",
        "/lang [código]":         f"Cambiar el idioma ({', '.join(LANGUAGES)})",
        "/settings":              "Panel de ajustes",
        "/apps":                  "Aplicaciones detectadas",
        "/tools":                 "Herramientas detectadas",
        "/help":                  "Esta ayuda",
    },
    "grp_meta": {
        "/tab":                   "Estado de la pestaña activa",
        "/reset":                 "Poner a cero el contador de contexto",
        "/save":                  "Guardar la configuración en disco",
        "/version":               "Versión de Term",
        "/about":                 "Acerca de Term",
        "/quit":                  "Salir",
    },
}

# Vista plana de todos los comandos, que es lo que consultan el autocompletado
# y las sugerencias mientras se escribe.
COMMANDS_HELP: dict[str, str] = {
    cmd: desc for grupo in COMMAND_GROUPS.values() for cmd, desc in grupo.items()
}

# Nombre pelado de cada comando, para autocompletar.
COMMAND_NAMES: list[str] = [c.split()[0] for c in COMMANDS_HELP]

SHORTCUTS_HELP: dict[str, str] = {
    "enter":        "Enviar el mensaje",
    "alt+enter":    "Salto de línea dentro del mensaje",
    "up / down":    "Recorrer los mensajes que ya has enviado",
    "tab":          "Autocompletar el comando que estás escribiendo",
    "ctrl+t":       "Nueva pestaña",
    "ctrl+w":       "Cerrar la pestaña o el panel activo",
    "ctrl+1..9":    "Saltar a la pestaña n",
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
