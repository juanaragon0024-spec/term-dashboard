// Generado por scripts/gen_commands.py — no editar a mano.
// Se genera desde term/commands.py para que la ayuda de la web y la
// de la terminal no puedan desincronizarse.

export interface CommandEntry {
  cmd: string
  desc: string
  /** Si el navegador sabe ejecutarlo; si no, es solo de terminal. */
  web: boolean
}

export interface CommandGroup {
  key: string
  title: string
  commands: CommandEntry[]
}

export const COMMAND_GROUPS: CommandGroup[] = [
  {
    "key": "grp_chat",
    "title": "Conversación",
    "commands": [
      {
        "cmd": "/new [nombre] [modelo]",
        "desc": "Nueva pestaña, opcionalmente con su IA",
        "web": true
      },
      {
        "cmd": "/close",
        "desc": "Cerrar la pestaña activa",
        "web": true
      },
      {
        "cmd": "/clear",
        "desc": "Limpiar el chat y empezar una sesión nueva",
        "web": true
      },
      {
        "cmd": "/sessions",
        "desc": "Listar las conversaciones guardadas",
        "web": false
      },
      {
        "cmd": "/resume <n>",
        "desc": "Retomar una conversación guardada",
        "web": false
      },
      {
        "cmd": "/search <texto>",
        "desc": "Buscar dentro de esta conversación",
        "web": true
      },
      {
        "cmd": "/name <texto>",
        "desc": "Renombrar la pestaña activa",
        "web": true
      },
      {
        "cmd": "/history",
        "desc": "Cuántos mensajes lleva esta pestaña",
        "web": false
      },
      {
        "cmd": "/export",
        "desc": "Guardar la conversación en un archivo",
        "web": true
      },
      {
        "cmd": "/copy",
        "desc": "Copiar la última respuesta",
        "web": true
      },
      {
        "cmd": "/code [n]",
        "desc": "Copiar el bloque de código n de la última respuesta",
        "web": false
      }
    ]
  },
  {
    "key": "grp_ai",
    "title": "Modelos e IA",
    "commands": [
      {
        "cmd": "/model <proveedor/modelo>",
        "desc": "Cambiar la IA de esta pestaña",
        "web": true
      },
      {
        "cmd": "/providers",
        "desc": "Ver cómo está conectada cada IA",
        "web": false
      },
      {
        "cmd": "/key <proveedor> <clave>",
        "desc": "Guardar la API key de un proveedor",
        "web": false
      },
      {
        "cmd": "/key-del <proveedor>",
        "desc": "Borrar una API key guardada",
        "web": false
      },
      {
        "cmd": "/effort <nivel>",
        "desc": "Nivel de esfuerzo (low, medium, high, max)",
        "web": true
      },
      {
        "cmd": "/architect [modelo]",
        "desc": "Que otro modelo planifique antes de ejecutar",
        "web": false
      },
      {
        "cmd": "/skeleton",
        "desc": "Pasar el esqueleto del código en vez de la lista de archivos",
        "web": false
      },
      {
        "cmd": "/permissions [modo]",
        "desc": "Modo de permisos (default, acceptEdits, plan, bypassPermissions)",
        "web": false
      },
      {
        "cmd": "/allow [perfil]",
        "desc": "Qué herramientas puede usar la IA (todo, lectura, segura, nada)",
        "web": false
      },
      {
        "cmd": "/mcp",
        "desc": "Servidores MCP y sus herramientas",
        "web": false
      },
      {
        "cmd": "/mcp-add <nombre> <cmd>",
        "desc": "Añadir un servidor MCP",
        "web": false
      },
      {
        "cmd": "/mcp-del <nombre>",
        "desc": "Quitar un servidor MCP",
        "web": false
      },
      {
        "cmd": "/compact",
        "desc": "Resumir la conversación para liberar contexto",
        "web": false
      }
    ]
  },
  {
    "key": "grp_git",
    "title": "Git",
    "commands": [
      {
        "cmd": "/git",
        "desc": "Panel de git: preparar archivos y confirmar (ctrl+g)",
        "web": false
      },
      {
        "cmd": "/status",
        "desc": "Qué has cambiado en el repositorio",
        "web": false
      },
      {
        "cmd": "/diff",
        "desc": "Ver los cambios sin confirmar",
        "web": false
      },
      {
        "cmd": "/commit [mensaje]",
        "desc": "Guardar los cambios; sin mensaje lo escribe la IA",
        "web": false
      },
      {
        "cmd": "/undo",
        "desc": "Deshacer el último commit sin perder el trabajo",
        "web": false
      },
      {
        "cmd": "/gitlog",
        "desc": "Últimos commits",
        "web": false
      },
      {
        "cmd": "/prs",
        "desc": "Pull requests abiertas",
        "web": false
      },
      {
        "cmd": "/issues",
        "desc": "Incidencias abiertas",
        "web": false
      },
      {
        "cmd": "/pr <n>",
        "desc": "Ver una pull request",
        "web": false
      },
      {
        "cmd": "/issue <n>",
        "desc": "Ver una incidencia",
        "web": false
      },
      {
        "cmd": "/pr-checkout <n>",
        "desc": "Traer la rama de una pull request",
        "web": false
      },
      {
        "cmd": "/issue-new <título>",
        "desc": "Abrir una incidencia",
        "web": false
      },
      {
        "cmd": "/repo",
        "desc": "Datos del repositorio en GitHub",
        "web": false
      }
    ]
  },
  {
    "key": "grp_files",
    "title": "Archivos y búsqueda",
    "commands": [
      {
        "cmd": "/mkdir <ruta>",
        "desc": "Crear una carpeta, con sus padres si hacen falta",
        "web": false
      },
      {
        "cmd": "/touch <ruta>",
        "desc": "Crear un archivo vacío",
        "web": false
      },
      {
        "cmd": "/find <patrón>",
        "desc": "Buscar archivos aquí y mostrar sus rutas",
        "web": false
      },
      {
        "cmd": "/findall <patrón>",
        "desc": "Buscar en todo el disco con Spotlight",
        "web": false
      },
      {
        "cmd": "/grep <texto>",
        "desc": "Buscar un texto dentro de los archivos",
        "web": false
      },
      {
        "cmd": "/files",
        "desc": "Mostrar u ocultar el panel de archivos",
        "web": true
      },
      {
        "cmd": "/add <ruta>",
        "desc": "Meter un archivo en el contexto de la conversación",
        "web": false
      },
      {
        "cmd": "/drop <ruta>",
        "desc": "Sacar un archivo del contexto",
        "web": false
      },
      {
        "cmd": "/context",
        "desc": "Ver qué archivos están en el contexto",
        "web": false
      },
      {
        "cmd": "/f",
        "desc": "Buscador difuso de archivos (también ctrl+p)",
        "web": false
      },
      {
        "cmd": "/map",
        "desc": "Ver el mapa del proyecto",
        "web": true
      },
      {
        "cmd": "/outline [ruta]",
        "desc": "Ver clases y funciones con su firma",
        "web": false
      },
      {
        "cmd": "/attach <ruta>",
        "desc": "Adjuntar un archivo solo al siguiente mensaje",
        "web": false
      },
      {
        "cmd": "/detach",
        "desc": "Descartar los archivos adjuntos pendientes",
        "web": false
      },
      {
        "cmd": "/workdir <ruta>",
        "desc": "Cambiar el directorio de trabajo",
        "web": true
      }
    ]
  },
  {
    "key": "grp_system",
    "title": "Sistema",
    "commands": [
      {
        "cmd": "/run <cmd>",
        "desc": "Ejecutar un comando y esperar su salida",
        "web": false
      },
      {
        "cmd": "/bg <cmd>",
        "desc": "Lanzar un comando en segundo plano (servidor, tests…)",
        "web": false
      },
      {
        "cmd": "/jobs",
        "desc": "Ver los procesos en segundo plano",
        "web": false
      },
      {
        "cmd": "/logs [n] [texto]",
        "desc": "Ver la salida de un proceso, filtrando si quieres",
        "web": false
      },
      {
        "cmd": "/stop [n]",
        "desc": "Parar un proceso; sin número, todos",
        "web": false
      },
      {
        "cmd": "/open <app>",
        "desc": "Abrir una aplicación",
        "web": false
      },
      {
        "cmd": "/close-app <app>",
        "desc": "Cerrar una aplicación",
        "web": false
      },
      {
        "cmd": "/web <consulta>",
        "desc": "Buscar en Google desde el navegador",
        "web": false
      },
      {
        "cmd": "/yt <consulta>",
        "desc": "Buscar en YouTube",
        "web": false
      },
      {
        "cmd": "/maps <lugar>",
        "desc": "Buscar un lugar en Google Maps",
        "web": false
      },
      {
        "cmd": "/browse [url]",
        "desc": "Abrir una URL en el navegador",
        "web": false
      },
      {
        "cmd": "/browser <nombre>",
        "desc": "Elegir el navegador por defecto",
        "web": false
      },
      {
        "cmd": "/play",
        "desc": "Reanudar la música",
        "web": false
      },
      {
        "cmd": "/pause",
        "desc": "Pausar la música",
        "web": false
      },
      {
        "cmd": "/next",
        "desc": "Siguiente canción",
        "web": false
      },
      {
        "cmd": "/prev",
        "desc": "Canción anterior",
        "web": false
      },
      {
        "cmd": "/track",
        "desc": "Qué canción suena ahora",
        "web": false
      },
      {
        "cmd": "/volume [0-100]",
        "desc": "Ver o ajustar el volumen",
        "web": false
      },
      {
        "cmd": "/sysinfo",
        "desc": "Batería, disco, red, volumen y música",
        "web": false
      }
    ]
  },
  {
    "key": "grp_look",
    "title": "Aspecto y paneles",
    "commands": [
      {
        "cmd": "/theme <nombre>",
        "desc": "Cambiar el tema de color",
        "web": true
      },
      {
        "cmd": "/lang [código]",
        "desc": "Cambiar el idioma (es, en, pt, fr, de, it, zh, ja, ko, ar)",
        "web": false
      },
      {
        "cmd": "/settings",
        "desc": "Panel de ajustes",
        "web": true
      },
      {
        "cmd": "/apps",
        "desc": "Aplicaciones detectadas",
        "web": true
      },
      {
        "cmd": "/tools",
        "desc": "Herramientas detectadas",
        "web": true
      },
      {
        "cmd": "/help",
        "desc": "Esta ayuda",
        "web": true
      }
    ]
  },
  {
    "key": "grp_meta",
    "title": "Term",
    "commands": [
      {
        "cmd": "/tab",
        "desc": "Estado de la pestaña activa",
        "web": true
      },
      {
        "cmd": "/reset",
        "desc": "Poner a cero el contador de contexto",
        "web": false
      },
      {
        "cmd": "/save",
        "desc": "Guardar la configuración en disco",
        "web": true
      },
      {
        "cmd": "/version",
        "desc": "Versión de Term",
        "web": true
      },
      {
        "cmd": "/about",
        "desc": "Acerca de Term",
        "web": true
      },
      {
        "cmd": "/quit",
        "desc": "Salir",
        "web": false
      }
    ]
  }
]

export const SHORTCUTS: Record<string, string> = {
  "ctrl+t": "Nueva pestaña",
  "ctrl+w": "Cerrar pestaña",
  "ctrl+l": "Limpiar el chat",
  "ctrl+e": "Cambiar el nivel de esfuerzo",
  "ctrl+k": "Ir a un panel",
  "enter": "Enviar el mensaje",
  "shift+enter": "Salto de línea",
  "escape": "Cancelar la generación"
}

export const TERMINAL_SHORTCUTS: Record<string, string> = {
  "enter": "Enviar el mensaje",
  "alt+enter": "Salto de línea dentro del mensaje",
  "up / down": "Recorrer los mensajes que ya has enviado",
  "tab": "Autocompletar el comando que estás escribiendo",
  "ctrl+t": "Nueva pestaña",
  "ctrl+w": "Cerrar la pestaña o el panel activo",
  "ctrl+1..9": "Saltar a la pestaña n",
  "ctrl+l": "Limpiar el chat",
  "ctrl+e": "Cambiar el nivel de esfuerzo",
  "ctrl+b": "Mostrar u ocultar el panel de archivos",
  "ctrl+p": "Buscar un archivo y meterlo en el contexto",
  "ctrl+g": "Panel de git",
  "ctrl+y": "Copiar la última respuesta",
  "escape": "Cancelar la generación o cerrar el panel",
  "ctrl+c": "Salir"
}

export const WEB_COMMANDS: string[] = COMMAND_GROUPS.flatMap((g) =>
  g.commands.filter((c) => c.web).map((c) => c.cmd.split(' ')[0]),
)
