"""Cliente de MCP (Model Context Protocol).

MCP es como el resto de herramientas del sector se extienden: un servidor
externo publica sus herramientas y el agente las usa como si fueran suyas. Hay
servidores hechos para bases de datos, GitHub, navegadores, Slack y casi todo
lo demas, asi que hablarlo sale mucho mas a cuenta que reimplementar cada
integracion aqui.

Term habla la variante de stdio: arranca el servidor como un proceso hijo e
intercambia JSON-RPC 2.0, un mensaje por linea.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import CONFIG_DIR

__all__ = [
    "MCP_PATH",
    "McpClient",
    "McpRegistry",
    "McpServer",
    "McpTool",
    "load_servers",
    "sanitize_name",
    "save_servers",
]

MCP_PATH = CONFIG_DIR / "mcp.json"

# Version del protocolo que pedimos. El servidor puede responder con otra; se
# acepta igualmente porque las partes que Term usa (tools/list y tools/call)
# no han cambiado entre versiones.
PROTOCOL_VERSION = "2025-06-18"

# Un servidor que no contesta en este tiempo se da por colgado. Sin tope, un
# servidor roto dejaria la TUI esperando para siempre. Es generoso porque un
# servidor lanzado con `npx` se descarga entero la primera vez.
_HANDSHAKE_TIMEOUT = 90.0
_CALL_TIMEOUT = 120.0

_STREAM_LIMIT = 8 * 1024 * 1024
_MAX_RESULT = 8_000


def sanitize_name(text: str) -> str:
    """Dejar un nombre que las APIs acepten como nombre de funcion.

    Los tres formatos exigen `[A-Za-z0-9_-]`, asi que un servidor llamado
    «mi servidor» o una herramienta con puntos romperian la llamada.
    """
    limpio = "".join(c if c.isalnum() or c in "_-" else "_" for c in text)
    return limpio.strip("_") or "mcp"


@dataclass
class McpServer:
    """Un servidor declarado en la configuracion."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    @property
    def available(self) -> bool:
        return bool(shutil.which(self.command))


@dataclass
class McpTool:
    """Una herramienta publicada por un servidor."""

    server: str
    name: str
    description: str = ""
    schema: dict[str, Any] = field(default_factory=dict)

    @property
    def qualified(self) -> str:
        """Nombre con el que Term la ofrece, con el servidor por delante."""
        return f"mcp_{sanitize_name(self.server)}_{sanitize_name(self.name)}"


class McpClient:
    """Conversacion con un servidor MCP por stdio."""

    def __init__(self, server: McpServer) -> None:
        self.server = server
        self.proc: asyncio.subprocess.Process | None = None
        self.tools: list[McpTool] = []
        self.error: str = ""
        self._id = 0
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    # ------------------------------------------------------------ ciclo de vida

    async def start(self) -> bool:
        """Arrancar el servidor y hacer el saludo inicial."""
        if self.running:
            return True
        if not self.server.available:
            self.error = f"no se encuentra «{self.server.command}»"
            return False

        entorno = {**os.environ, **self.server.env}
        try:
            self.proc = await asyncio.create_subprocess_exec(
                self.server.command, *self.server.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=entorno,
                limit=_STREAM_LIMIT,
            )
        except OSError as exc:
            self.error = str(exc)
            return False

        try:
            await asyncio.wait_for(self._handshake(), _HANDSHAKE_TIMEOUT)
        except TimeoutError:
            self.error = "el servidor no respondió al saludo inicial"
            await self.stop()
            return False
        except Exception as exc:
            self.error = str(exc)
            await self.stop()
            return False

        self.error = ""
        return True

    async def _handshake(self) -> None:
        await self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "Term", "version": "3"},
        })
        # El servidor no responde a esta, solo la espera antes de aceptar
        # peticiones de verdad.
        await self._notify("notifications/initialized")
        await self.refresh_tools()

    async def stop(self) -> None:
        proc, self.proc = self.proc, None
        if proc is None or proc.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError, OSError):
            proc.terminate()
        with contextlib.suppress(TimeoutError, Exception):
            await asyncio.wait_for(proc.wait(), 5)
        if proc.returncode is None:
            with contextlib.suppress(ProcessLookupError, OSError):
                proc.kill()

    # ------------------------------------------------------------ herramientas

    async def refresh_tools(self) -> list[McpTool]:
        respuesta = await self._request("tools/list", {})
        self.tools = [
            McpTool(
                server=self.server.name,
                name=str(t.get("name", "")),
                description=str(t.get("description", "")),
                schema=t.get("inputSchema") or {"type": "object", "properties": {}},
            )
            for t in (respuesta.get("tools") or [])
            if isinstance(t, dict) and t.get("name")
        ]
        return self.tools

    async def call(self, name: str, args: dict) -> tuple[bool, str]:
        """Ejecutar una herramienta del servidor."""
        if not self.running and not await self.start():
            return False, f"{self.server.name}: {self.error}"
        try:
            respuesta = await asyncio.wait_for(
                self._request("tools/call", {"name": name, "arguments": args or {}}),
                _CALL_TIMEOUT,
            )
        except TimeoutError:
            return False, f"{self.server.name}: la herramienta tardó demasiado"
        except Exception as exc:
            return False, f"{self.server.name}: {exc}"

        texto = _flatten_content(respuesta.get("content"))
        if len(texto) > _MAX_RESULT:
            texto = texto[:_MAX_RESULT] + "\n… (recortado)"
        # isError marca un fallo de la herramienta, no del protocolo.
        return not respuesta.get("isError", False), texto or "(sin salida)"

    # ------------------------------------------------------------ JSON-RPC

    async def _request(self, method: str, params: dict | None = None) -> dict:
        """Enviar una peticion y esperar su respuesta.

        El candado serializa las peticiones: sobre un solo par de tuberias, dos
        a la vez se pisarian las respuestas.
        """
        async with self._lock:
            self._id += 1
            ident = self._id
            await self._send({"jsonrpc": "2.0", "id": ident,
                              "method": method, "params": params or {}})

            while True:
                mensaje = await self._receive()
                if mensaje.get("id") != ident:
                    # Notificaciones y avisos del servidor: no nos incumben.
                    continue
                if error := mensaje.get("error"):
                    raise RuntimeError(str(error.get("message") or error))
                return mensaje.get("result") or {}

    async def _notify(self, method: str, params: dict | None = None) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def _send(self, mensaje: dict) -> None:
        if self.proc is None or self.proc.stdin is None:
            raise RuntimeError("el servidor no está arrancado")
        self.proc.stdin.write((json.dumps(mensaje) + "\n").encode())
        await self.proc.stdin.drain()

    async def _receive(self) -> dict:
        if self.proc is None or self.proc.stdout is None:
            raise RuntimeError("el servidor no está arrancado")
        while True:
            linea = await self.proc.stdout.readline()
            if not linea:
                raise RuntimeError("el servidor cerró la conexión")
            texto = linea.decode("utf-8", errors="replace").strip()
            if not texto:
                continue
            try:
                mensaje = json.loads(texto)
            except ValueError:
                # Algunos servidores escriben avisos sueltos en stdout.
                continue
            if isinstance(mensaje, dict):
                return mensaje


def _flatten_content(content: object) -> str:
    """Aplanar el contenido de una respuesta a texto."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    trozos: list[str] = []
    for bloque in content:
        if isinstance(bloque, str):
            trozos.append(bloque)
        elif isinstance(bloque, dict):
            if texto := bloque.get("text"):
                trozos.append(str(texto))
            elif bloque.get("type") == "image":
                trozos.append("(imagen devuelta por la herramienta)")
            elif recurso := bloque.get("resource"):
                trozos.append(str(recurso.get("text") or recurso.get("uri") or ""))
    return "\n".join(t for t in trozos if t)


# ---------------------------------------------------------------------------
# Configuracion y registro
# ---------------------------------------------------------------------------


def load_servers(path: Path | None = None) -> list[McpServer]:
    """Servidores declarados en mcp.json.

    Se usa el mismo formato `mcpServers` que el resto del sector, para poder
    copiar y pegar una configuracion que ya se tenga.
    """
    ruta = path or MCP_PATH
    try:
        raw = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entradas = raw.get("mcpServers") if isinstance(raw, dict) else None
    if not isinstance(entradas, dict):
        return []

    servidores: list[McpServer] = []
    for nombre, datos in entradas.items():
        if not isinstance(datos, dict) or not datos.get("command"):
            continue
        args = datos.get("args") or []
        env = datos.get("env") or {}
        servidores.append(McpServer(
            name=str(nombre),
            command=str(datos["command"]),
            args=[str(a) for a in args] if isinstance(args, list) else [],
            env={str(k): str(v) for k, v in env.items()} if isinstance(env, dict) else {},
            enabled=bool(datos.get("enabled", True)),
        ))
    return servidores


def save_servers(servidores: list[McpServer], path: Path | None = None) -> bool:
    ruta = path or MCP_PATH
    datos = {
        "mcpServers": {
            s.name: {"command": s.command, "args": s.args,
                     **({"env": s.env} if s.env else {}),
                     **({} if s.enabled else {"enabled": False})}
            for s in servidores
        }
    }
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=ruta.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(datos, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, ruta)
    except OSError:
        return False
    return True


class McpRegistry:
    """Los servidores MCP de esta sesion y sus herramientas.

    Los servidores se arrancan a la primera que hacen falta, no al abrir Term:
    lanzar cinco procesos en el arranque para que a lo mejor no se use ninguno
    es un mal negocio.
    """

    def __init__(self, servers: list[McpServer] | None = None) -> None:
        self.servers = servers if servers is not None else load_servers()
        self.clients: dict[str, McpClient] = {}
        self.started = False

    async def start_all(self) -> dict[str, str]:
        """Arrancar los servidores activos. Devuelve los que fallaron."""
        fallos: dict[str, str] = {}
        for server in self.servers:
            if not server.enabled:
                continue
            client = self.clients.get(server.name) or McpClient(server)
            self.clients[server.name] = client
            if not await client.start():
                fallos[server.name] = client.error
        self.started = True
        return fallos

    async def stop_all(self) -> None:
        for client in self.clients.values():
            await client.stop()
        self.clients.clear()
        self.started = False

    def tools(self) -> list[McpTool]:
        """Todas las herramientas publicadas por los servidores en marcha."""
        return [t for c in self.clients.values() for t in c.tools]

    def find(self, qualified: str) -> tuple[McpClient, McpTool] | None:
        """Localizar una herramienta por el nombre con el que Term la ofrece."""
        for client in self.clients.values():
            for tool in client.tools:
                if tool.qualified == qualified:
                    return client, tool
        return None

    async def call(self, qualified: str, args: dict) -> tuple[bool, str]:
        encontrado = self.find(qualified)
        if encontrado is None:
            return False, f"No hay ninguna herramienta MCP llamada «{qualified}»."
        client, tool = encontrado
        return await client.call(tool.name, args)
