"""Conversaciones con la CLI de un proveedor de IA.

Cada pestana de Term tiene su propia `ClaudeSession`: su proveedor, su modelo,
su id de sesion y su proceso. Dos pestanas pueden estar hablando con dos IA
distintas a la vez sin enterarse la una de la otra.

El primer turno abre la conversacion y los siguientes la continuan, que es lo
que da memoria a la pestana. La salida se pide en JSON para poder mostrar el
uso de herramientas y el consumo real en lugar de un bloque de texto opaco.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal

from . import tools as toolkit
from .providers import DEFAULT_PROVIDER, Provider, get_provider, join_ref, split_ref

__all__ = [
    "ChatSession",
    "ClaudeSession",
    "StreamEvent",
    "Usage",
    "claude_available",
]

# Una linea de salida puede llevar el resultado entero de una herramienta, muy
# por encima del limite de 64 KB que asyncio usa por defecto para readline.
_STREAM_LIMIT = 16 * 1024 * 1024

# Cuanto stderr se guarda para diagnostico. Se lee siempre en una tarea aparte:
# si se dejara sin leer, el pipe se llenaria y el proceso quedaria bloqueado a
# mitad de respuesta.
_STDERR_CAP = 8_000


def claude_available() -> bool:
    """Si la CLI de Claude esta instalada."""
    return get_provider("claude").available()


@dataclass
class Usage:
    """Consumo real informado por la CLI al terminar el turno."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    total_cost_usd: float = 0.0
    context_window: int = 0
    num_turns: int = 0
    duration_ms: int = 0

    @property
    def context_tokens(self) -> int:
        """Tokens que ocupan la ventana de contexto tras este turno."""
        return (
            self.input_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
            + self.output_tokens
        )

    @classmethod
    def from_dict(cls, data: dict) -> Usage:
        campos = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in campos})


EventKind = Literal["init", "text", "tool", "result", "error"]


@dataclass
class StreamEvent:
    kind: EventKind
    text: str = ""
    tool: str = ""
    detail: str = ""
    usage: Usage | None = None
    session_id: str = ""

    @property
    def replaces_text(self) -> bool:
        """Si el texto sustituye a lo anterior en vez de anadirse.

        Unos proveedores mandan el trozo nuevo y otros el texto acumulado; el
        adaptador lo marca aqui para que quien pinta no duplique la respuesta.
        """
        return self.kind == "text" and self.detail == "full"


@dataclass
class ChatSession:
    """Una conversacion: su proveedor, su modelo y su hilo."""

    provider_key: str = DEFAULT_PROVIDER
    model: str = "default"
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started: bool = False
    proc: asyncio.subprocess.Process | None = None
    usage: Usage = field(default_factory=Usage)
    turns: int = 0
    # Historial de la conversacion cuando se habla por API. Una CLI se acuerda
    # sola de lo dicho; una API no recuerda nada, asi que la memoria de la
    # pestana es literalmente esta lista.
    history: list[dict] = field(default_factory=list)

    @property
    def is_api(self) -> bool:
        return self.provider.transport == "api"

    # ------------------------------------------------------------- proveedor

    @property
    def provider(self) -> Provider:
        return get_provider(self.provider_key)

    @property
    def model_ref(self) -> str:
        """Nombre completo `proveedor/modelo`."""
        return join_ref(self.provider_key, self.model)

    def set_model_ref(self, ref: str) -> None:
        """Cambiar de proveedor o de modelo.

        Cambiar de proveedor abre una conversacion nueva: el id de sesion de
        una CLI no significa nada para otra.
        """
        provider_key, model = split_ref(ref)
        if provider_key != self.provider_key:
            self.provider_key = provider_key
            self.reset()
        self.model = model

    # ---------------------------------------------------------------- estado

    def reset(self) -> None:
        """Empezar de cero: id nuevo, sin memoria del hilo anterior."""
        self.session_id = str(uuid.uuid4())
        self.started = False
        self.usage = Usage()
        self.turns = 0
        self.history.clear()

    def adopt(self, session_id: str) -> None:
        """Continuar una conversacion que ya existe en la CLI."""
        self.session_id = session_id
        self.started = True

    # ----------------------------------------------------------------- turno

    def build_command(
        self,
        prompt: str,
        *,
        effort: str = "high",
        workdir: str = "",
        system_prompt: str = "",
        restricted: bool = False,
        permission_mode: str = "",
        max_turns: int = 15,
    ) -> list[str]:
        """Argumentos del turno. Aparte de `run` para poder comprobarlos
        en los tests sin arrancar ningun proceso."""
        provider = self.provider
        return provider.build_command(
            prompt,
            model=self.model,
            # Un proveedor sin sesiones recibe la cadena vacia y no intenta
            # retomar nada.
            session_id=self.session_id if provider.supports_sessions else "",
            resume=self.started and provider.supports_sessions,
            workdir=workdir,
            effort=effort,
            system_prompt=system_prompt,
            restricted=restricted,
            permission_mode=permission_mode,
            max_turns=max_turns,
        )

    async def run(self, prompt: str, **kwargs: object) -> AsyncIterator[StreamEvent]:
        """Ejecutar un turno y emitir sus eventos segun llegan."""
        if self.is_api:
            async for event in self._run_api(prompt, **kwargs):
                yield event
            return
        async for event in self._run_cli(prompt, **kwargs):
            yield event

    async def _run_api(self, prompt: str, **kwargs: object) -> AsyncIterator[StreamEvent]:
        """Turno contra una API, con Term ejecutando las herramientas."""
        provider = self.provider
        ctx = toolkit.ToolContext(
            workdir=str(kwargs.get("workdir") or ""),
            allow_system=not bool(kwargs.get("restricted")),
        )
        self.history.append(provider_user_turn(provider, prompt))
        self.started = True

        async for parsed in provider.converse(  # type: ignore[attr-defined]
            self.history,
            model=self.model,
            system=str(kwargs.get("system_prompt") or ""),
            ctx=ctx,
        ):
            yield self._adopt(parsed)

    async def _run_cli(self, prompt: str, **kwargs: object) -> AsyncIterator[StreamEvent]:
        provider = self.provider
        workdir = str(kwargs.get("workdir") or "")
        cmd = self.build_command(prompt, **kwargs)  # type: ignore[arg-type]

        try:
            self.proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir or None,
                limit=_STREAM_LIMIT,
            )
        except FileNotFoundError:
            yield StreamEvent("error", text=f"missing:{provider.binary}")
            return
        except OSError as exc:
            yield StreamEvent("error", text=str(exc))
            return

        proc = self.proc
        assert proc.stdout is not None and proc.stderr is not None

        stderr_buf: list[str] = []

        async def drain_stderr() -> None:
            """Vaciar stderr en paralelo para que el pipe nunca se llene."""
            total = 0
            while True:
                chunk = await proc.stderr.read(4096)  # type: ignore[union-attr]
                if not chunk:
                    break
                if total < _STDERR_CAP:
                    text = chunk.decode("utf-8", errors="replace")
                    stderr_buf.append(text)
                    total += len(text)

        stderr_task = asyncio.create_task(drain_stderr())
        saw_result = False

        try:
            while True:
                try:
                    line = await proc.stdout.readline()
                except (ValueError, asyncio.LimitOverrunError):
                    # Linea por encima del limite: se salta en vez de matar el
                    # turno entero.
                    continue
                if not line:
                    break
                raw = line.decode("utf-8", errors="replace")
                for parsed in provider.parse_line(raw):
                    event = self._adopt(parsed)
                    if event.kind == "result":
                        saw_result = True
                    yield event

            await proc.wait()
        finally:
            stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stderr_task
            self.proc = None

        code = proc.returncode
        if code not in (0, None) and not saw_result:
            detail = "".join(stderr_buf).strip()
            yield StreamEvent(
                "error", text=detail or f"{provider.binary} terminó con código {code}"
            )

    def _adopt(self, parsed) -> StreamEvent:
        """Pasar un evento del proveedor a evento de Term, quedandose por el
        camino con el id de sesion y el consumo."""
        if parsed.session_id and self.provider.supports_sessions:
            self.session_id = parsed.session_id
            self.started = True

        usage = None
        if parsed.usage:
            usage = Usage.from_dict(parsed.usage)
            self.usage = usage
            self.turns += usage.num_turns

        return StreamEvent(
            kind=parsed.kind,  # type: ignore[arg-type]
            text=parsed.text,
            tool=parsed.tool,
            detail=parsed.detail,
            usage=usage,
            session_id=parsed.session_id,
        )


def provider_user_turn(provider: Provider, prompt: str) -> dict:
    """El mensaje del usuario con la forma que espera cada API.

    Gemini llama `parts` a lo que el resto llama `content`; escribirlo mal no
    da un error claro, solo una conversacion que el modelo no entiende.
    """
    if provider.key == "gemini":
        return {"role": "user", "parts": [{"text": prompt}]}
    return {"role": "user", "content": prompt}


# Las versiones anteriores solo hablaban con Claude y el nombre se quedo por el
# camino; se mantiene para no romper lo que ya lo importa.
ClaudeSession = ChatSession
