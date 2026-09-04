"""Herramientas que Term ejecuta por su cuenta.

Cuando Term habla con una API en vez de con una CLI, no hay nadie al otro lado
que sepa crear una carpeta o mirar que cancion suena: lo hace Term. Aqui estan
esas capacidades, cada una con el esquema que se le manda al modelo y la
funcion que la ejecuta.

Es lo que permite que Gemini, Grok o un modelo local hagan las mismas cosas que
Claude Code, sin que ninguno de ellos necesite una CLI propia.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import syscontrol as sysctl

__all__ = [
    "TOOLS",
    "Tool",
    "ToolContext",
    "available_tools",
    "execute",
    "schemas_anthropic",
    "schemas_gemini",
    "schemas_openai",
]

# Cuanto texto de vuelta cabe en un resultado. Un resultado enorme se come el
# contexto de la conversacion y no aporta nada mas que el principio.
_MAX_RESULT = 6_000


@dataclass
class ToolContext:
    """Lo que una herramienta necesita saber del entorno."""

    workdir: str = ""
    # Sin permisos concedidos, las herramientas que tocan el sistema no se le
    # llegan a ofrecer al modelo.
    allow_system: bool = True
    # Lista blanca por nombre de herramienta. Vacia significa "todas las que
    # permita allow_system"; con contenido, solo esas. Es lo que permite dejar
    # que lea y busque pero no que ejecute comandos.
    allowed: frozenset[str] = frozenset()
    denied: frozenset[str] = frozenset()
    # Registro de servidores MCP, si los hay. Sus herramientas se ofrecen junto
    # a las nativas y el modelo no distingue unas de otras.
    mcp: object = None

    def permits(self, tool: Tool) -> tuple[bool, str]:
        """Si una herramienta se puede usar aqui, y por que no."""
        if tool.name in self.denied:
            return False, f"«{tool.name}» está en la lista de denegadas."
        if self.allowed and tool.name not in self.allowed:
            return False, (f"«{tool.name}» no está en la lista de permitidas "
                           f"({', '.join(sorted(self.allowed))}).")
        if tool.system and not self.allow_system:
            return False, ("El usuario no ha concedido permisos de sistema, "
                           "así que esta herramienta no está disponible.")
        return True, ""


@dataclass
class Tool:
    name: str
    description: str
    params: dict[str, dict[str, Any]] = field(default_factory=dict)
    required: tuple[str, ...] = ()
    handler: Callable[..., sysctl.SysResult] | None = None
    # Toca el sistema: ejecutar comandos, abrir apps, cambiar el volumen.
    system: bool = False


def _truncate(text: str) -> str:
    if len(text) <= _MAX_RESULT:
        return text
    return text[:_MAX_RESULT] + f"\n… (recortado, {len(text)} caracteres en total)"


# ---------------------------------------------------------------------------
# Implementaciones
# ---------------------------------------------------------------------------


def _crear_carpeta(ctx: ToolContext, path: str = "") -> sysctl.SysResult:
    result = sysctl.make_dir(path, ctx.workdir)
    if result:
        return sysctl.SysResult(True, output=f"Carpeta creada: {result.output}")
    return result


def _crear_archivo(ctx: ToolContext, path: str = "", content: str = "") -> sysctl.SysResult:
    result = sysctl.write_file(path, content, ctx.workdir)
    if result:
        return sysctl.SysResult(True, output=f"Archivo creado: {result.output}")
    return result


def _leer_archivo(ctx: ToolContext, path: str = "") -> sysctl.SysResult:
    target = Path(path).expanduser()
    if not target.is_absolute():
        target = Path(ctx.workdir) / target
    if not target.is_file():
        return sysctl.SysResult(False, reason=f"leer|no existe: {target}")
    try:
        return sysctl.SysResult(True, output=_truncate(target.read_text(errors="replace")))
    except OSError as exc:
        return sysctl.SysResult(False, reason=f"leer|{exc}")


def _listar(ctx: ToolContext, path: str = "") -> sysctl.SysResult:
    target = Path(path or ctx.workdir).expanduser()
    if not target.is_absolute():
        target = Path(ctx.workdir) / target
    if not target.is_dir():
        return sysctl.SysResult(False, reason=f"listar|no es una carpeta: {target}")
    try:
        entradas = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError as exc:
        return sysctl.SysResult(False, reason=f"listar|{exc}")
    lineas = [f"{'d' if e.is_dir() else '-'} {e.name}" for e in entradas[:200]]
    return sysctl.SysResult(True, output=f"{target}\n" + "\n".join(lineas))


def _buscar_archivos(
    ctx: ToolContext, pattern: str = "", todo_el_disco: bool = False,
) -> sysctl.SysResult:
    return sysctl.find_files(
        pattern, "" if todo_el_disco else ctx.workdir, spotlight=todo_el_disco)


def _buscar_texto(ctx: ToolContext, text: str = "") -> sysctl.SysResult:
    return sysctl.search_text(text, ctx.workdir)


def _shell(ctx: ToolContext, command: str = "") -> sysctl.SysResult:
    return sysctl.run_shell(command, ctx.workdir, timeout=30)


def _musica(ctx: ToolContext, action: str = "track") -> sysctl.SysResult:
    return sysctl.music(action)


def _volumen(ctx: ToolContext, level: int | None = None) -> sysctl.SysResult:
    if level is None:
        actual = sysctl.get_volume()
        return sysctl.SysResult(actual.ok, output=f"Volumen: {actual.output}%",
                                reason=actual.reason)
    result = sysctl.set_volume(int(level))
    return sysctl.SysResult(result.ok, output=f"Volumen puesto a {level}%",
                            reason=result.reason)


def _web(ctx: ToolContext, query: str = "", engine: str = "google") -> sysctl.SysResult:
    result = sysctl.web_search(query, engine)
    if result:
        return sysctl.SysResult(True, output=f"Abierto en el navegador: {result.output}")
    return result


def _abrir_app(ctx: ToolContext, name: str = "") -> sysctl.SysResult:
    result = sysctl.open_app(name)
    return sysctl.SysResult(result.ok, output=f"Abierta: {name}", reason=result.reason)


def _info(ctx: ToolContext) -> sysctl.SysResult:
    return sysctl.system_info()


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

_LISTA: list[Tool] = [
    Tool(
        name="crear_carpeta",
        description="Crear una carpeta, con sus carpetas padre si hacen falta.",
        params={"path": {"type": "string",
                         "description": "Ruta de la carpeta, absoluta o relativa al directorio de trabajo"}},
        required=("path",),
        handler=_crear_carpeta,
    ),
    Tool(
        name="crear_archivo",
        description="Crear un archivo con contenido. Falla si el archivo ya existe.",
        params={
            "path": {"type": "string", "description": "Ruta del archivo"},
            "content": {"type": "string", "description": "Contenido del archivo"},
        },
        required=("path",),
        handler=_crear_archivo,
    ),
    Tool(
        name="leer_archivo",
        description="Leer el contenido de un archivo de texto.",
        params={"path": {"type": "string", "description": "Ruta del archivo"}},
        required=("path",),
        handler=_leer_archivo,
    ),
    Tool(
        name="listar_carpeta",
        description="Listar lo que hay en una carpeta.",
        params={"path": {"type": "string",
                         "description": "Ruta de la carpeta; vacío para el directorio de trabajo"}},
        handler=_listar,
    ),
    Tool(
        name="buscar_archivos",
        description=(
            "Buscar archivos por nombre y devolver sus rutas absolutas. "
            "Usa todo_el_disco para buscar fuera del directorio de trabajo."
        ),
        params={
            "pattern": {"type": "string",
                        "description": "Parte del nombre, o un patrón con * y ?"},
            "todo_el_disco": {"type": "boolean",
                              "description": "Buscar en todo el disco con Spotlight"},
        },
        required=("pattern",),
        handler=_buscar_archivos,
    ),
    Tool(
        name="buscar_texto",
        description="Buscar un texto dentro de los archivos y devolver ruta, línea y coincidencia.",
        params={"text": {"type": "string", "description": "Texto a buscar"}},
        required=("text",),
        handler=_buscar_texto,
    ),
    Tool(
        name="ejecutar_shell",
        description=(
            "Ejecutar un comando de shell en el directorio de trabajo y devolver su salida. "
            "No lo uses para borrar ni sobrescribir sin haberlo consultado antes."
        ),
        params={"command": {"type": "string", "description": "Comando a ejecutar"}},
        required=("command",),
        handler=_shell,
        system=True,
    ),
    Tool(
        name="controlar_musica",
        description=(
            "Controlar el reproductor de música que esté abierto (Spotify o Music). "
            "Acciones: play, pause, playpause, next, previous, track."
        ),
        params={"action": {
            "type": "string",
            "enum": ["play", "pause", "playpause", "next", "previous", "track"],
            "description": "Qué hacer con la reproducción",
        }},
        required=("action",),
        handler=_musica,
        system=True,
    ),
    Tool(
        name="ajustar_volumen",
        description="Ver o cambiar el volumen del sistema. Sin nivel, devuelve el actual.",
        params={"level": {"type": "integer", "description": "Volumen de 0 a 100"}},
        handler=_volumen,
        system=True,
    ),
    Tool(
        name="buscar_en_web",
        description="Abrir una búsqueda en el navegador del usuario.",
        params={
            "query": {"type": "string", "description": "Qué buscar"},
            "engine": {"type": "string",
                       "enum": ["google", "ddg", "bing", "youtube", "github", "maps"],
                       "description": "Dónde buscar"},
        },
        required=("query",),
        handler=_web,
        system=True,
    ),
    Tool(
        name="abrir_app",
        description="Abrir una aplicación por su nombre, por ejemplo Safari o Spotify.",
        params={"name": {"type": "string", "description": "Nombre de la aplicación"}},
        required=("name",),
        handler=_abrir_app,
        system=True,
    ),
    Tool(
        name="info_sistema",
        description="Resumen del estado: batería, disco, red, volumen y música sonando.",
        handler=_info,
        system=True,
    ),
]

TOOLS: dict[str, Tool] = {t.name: t for t in _LISTA}


def mcp_tools(ctx: ToolContext) -> list[Tool]:
    """Las herramientas MCP, envueltas como herramientas de Term.

    Se marcan como de sistema porque un servidor externo puede hacer cualquier
    cosa: sin permisos concedidos, no se ofrecen.
    """
    registro = ctx.mcp
    if registro is None:
        return []
    envueltas: list[Tool] = []
    for herramienta in registro.tools():  # type: ignore[attr-defined]
        esquema = herramienta.schema or {}
        propiedades = esquema.get("properties") or {}
        requeridos = esquema.get("required") or []
        envueltas.append(Tool(
            name=herramienta.qualified,
            description=(f"[{herramienta.server}] " + (herramienta.description or ""))[:1000],
            params=propiedades if isinstance(propiedades, dict) else {},
            required=tuple(r for r in requeridos if isinstance(r, str)),
            handler=None,   # las ejecuta el registro, no una funcion local
            system=True,
        ))
    return envueltas


def available_tools(ctx: ToolContext) -> list[Tool]:
    """Herramientas que se le ofrecen al modelo en este contexto.

    Lo que no se puede usar ni se menciona: es mas honesto que ofrecerlo y
    negarlo despues.
    """
    candidatas = [*TOOLS.values(), *mcp_tools(ctx)]
    return [t for t in candidatas if ctx.permits(t)[0]]


async def execute_async(name: str, args: dict, ctx: ToolContext) -> tuple[bool, str]:
    """Ejecutar una herramienta, sea nativa o de un servidor MCP."""
    if name.startswith("mcp_") and ctx.mcp is not None:
        envueltas = {t.name: t for t in mcp_tools(ctx)}
        tool = envueltas.get(name)
        if tool is None:
            return False, f"No existe la herramienta «{name}»."
        permitida, motivo = ctx.permits(tool)
        if not permitida:
            return False, motivo
        return await ctx.mcp.call(name, args or {})  # type: ignore[attr-defined]
    return execute(name, args, ctx)


def execute(name: str, args: dict, ctx: ToolContext) -> tuple[bool, str]:
    """Ejecutar una herramienta nativa y devolver `(ok, texto para el modelo)`."""
    tool = TOOLS.get(name)
    if tool is None:
        return False, f"No existe la herramienta «{name}»."
    permitida, motivo = ctx.permits(tool)
    if not permitida:
        return False, motivo
    if tool.handler is None:
        return False, f"La herramienta «{name}» no está implementada."

    # Solo se le pasan los parametros declarados: un modelo puede inventarse
    # campos y eso reventaria la llamada.
    limpios = {k: v for k, v in (args or {}).items() if k in tool.params}
    faltan = [p for p in tool.required if not limpios.get(p)]
    if faltan:
        return False, f"Faltan parámetros obligatorios: {', '.join(faltan)}."

    try:
        result = tool.handler(ctx, **limpios)
    except TypeError as exc:
        return False, f"Parámetros incorrectos: {exc}"
    except Exception as exc:  # una herramienta rota no debe tumbar el turno
        return False, f"Error al ejecutar «{name}»: {exc}"

    if result.ok:
        return True, _truncate(result.output or "Hecho.")
    return False, result.reason.replace("|", ": ") or "No se pudo completar."


# ---------------------------------------------------------------------------
# Esquemas por formato de API
# ---------------------------------------------------------------------------


def _json_schema(tool: Tool) -> dict:
    return {
        "type": "object",
        "properties": tool.params,
        "required": list(tool.required),
    }


def schemas_openai(ctx: ToolContext) -> list[dict]:
    """Formato de OpenAI, que usan tambien OpenRouter, Grok, Groq y DeepSeek."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": _json_schema(t),
            },
        }
        for t in available_tools(ctx)
    ]


def schemas_anthropic(ctx: ToolContext) -> list[dict]:
    return [
        {"name": t.name, "description": t.description, "input_schema": _json_schema(t)}
        for t in available_tools(ctx)
    ]


def schemas_gemini(ctx: ToolContext) -> list[dict]:
    """Gemini agrupa todas las funciones en una sola declaracion."""
    return [{
        "function_declarations": [
            {
                "name": t.name,
                "description": t.description,
                "parameters": _json_schema(t) if t.params else {"type": "object",
                                                                "properties": {}},
            }
            for t in available_tools(ctx)
        ]
    }]
