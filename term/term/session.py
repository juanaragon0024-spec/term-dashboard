"""Conversaciones con la CLI de Claude Code.

Cada pestana de Term tiene una `ClaudeSession` con un id estable. El primer
turno arranca la sesion con `--session-id` y los siguientes la continuan con
`--resume`, que es lo que da a Term memoria de la conversacion: sin esto cada
mensaje seria un proceso nuevo sin ningun recuerdo del anterior.

La salida se pide en `stream-json`, asi que en vez de un bloque de texto opaco
recibimos eventos tipados: texto, uso de herramientas y un resultado final con
tokens, coste y ventana de contexto reales.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal

from .models import resolve_model

__all__ = ["ClaudeSession", "StreamEvent", "Usage", "claude_available"]

# Una linea de stream-json puede llevar el resultado entero de una herramienta,
# muy por encima del limite de 64 KB que asyncio usa por defecto para readline.
# Sin subirlo, readline() revienta con ValueError en cuanto Claude lee un
# fichero grande.
_STREAM_LIMIT = 16 * 1024 * 1024

# Cuanto stderr guardamos para el diagnostico. stderr se lee siempre en una
# tarea aparte: si se dejara sin leer, el pipe se llenaria y el proceso se
# quedaria bloqueado para siempre a mitad de respuesta.
_STDERR_CAP = 8_000


def claude_available() -> bool:
    return shutil.which("claude") is not None


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


EventKind = Literal["init", "text", "tool", "tool_result", "result", "error"]


@dataclass
class StreamEvent:
    kind: EventKind
    text: str = ""
    tool: str = ""
    detail: str = ""
    usage: Usage | None = None
    session_id: str = ""


@dataclass
class ClaudeSession:
    """Una conversacion con la CLI, con su id y su historial."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started: bool = False
    proc: asyncio.subprocess.Process | None = None
    usage: Usage = field(default_factory=Usage)
    turns: int = 0

    def reset(self) -> None:
        """Empezar de cero: id nuevo, sin memoria del hilo anterior."""
        self.session_id = str(uuid.uuid4())
        self.started = False
        self.usage = Usage()
        self.turns = 0

    def adopt(self, session_id: str) -> None:
        """Continuar una sesion existente de la CLI."""
        self.session_id = session_id
        self.started = True

    def build_command(
        self,
        prompt: str,
        *,
        model: str = "default",
        effort: str = "high",
        workdir: str = "",
        system_prompt: str = "",
        permission_mode: str = "default",
        restricted: bool = False,
        max_turns: int = 15,
    ) -> list[str]:
        """Argumentos completos para lanzar un turno.

        Se expone aparte de `run` para poder comprobarlo en los tests sin
        arrancar ningun proceso.
        """
        cmd = ["claude", "-p", prompt]

        # Continuar la conversacion en curso, o abrirla con un id conocido para
        # poder retomarla mas tarde.
        if self.started:
            cmd += ["--resume", self.session_id]
        else:
            cmd += ["--session-id", self.session_id]

        cmd += [
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--verbose",
            "--max-turns", str(max_turns),
        ]

        _, alias = resolve_model(model)
        if alias:
            cmd += ["--model", alias]
        if effort:
            cmd += ["--effort", effort]

        # El usuario que rechaza los permisos obtiene una CLI sin herramientas
        # que ejecuten codigo, no solo un aviso: el dialogo tiene que significar
        # algo.
        if restricted:
            cmd += ["--restricted"]
        elif permission_mode and permission_mode != "default":
            cmd += ["--permission-mode", permission_mode]

        if system_prompt:
            cmd += ["--append-system-prompt", system_prompt]
        if workdir:
            cmd += ["--add-dir", workdir]
        return cmd

    async def run(self, prompt: str, **kwargs: object) -> AsyncIterator[StreamEvent]:
        """Ejecutar un turno y emitir sus eventos segun llegan."""
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
            yield StreamEvent("error", text="claude-not-found")
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
                    # Linea por encima del limite: la saltamos en vez de matar
                    # el turno entero.
                    continue
                if not line:
                    break
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except ValueError:
                    continue
                for event in self._parse(payload):
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
                "error",
                text=detail or f"claude terminó con código {code}",
            )

    # ------------------------------------------------------------------ parseo

    def _parse(self, payload: dict) -> list[StreamEvent]:
        """Traducir una linea de stream-json a eventos de Term."""
        kind = payload.get("type")
        sid = payload.get("session_id", "")
        events: list[StreamEvent] = []

        if kind == "system" and payload.get("subtype") == "init":
            if sid:
                self.session_id = sid
                self.started = True
            events.append(StreamEvent("init", session_id=sid))

        elif kind == "stream_event":
            # Deltas token a token: es lo que hace que la respuesta aparezca
            # escribiendose en vez de de golpe.
            event = payload.get("event") or {}
            if event.get("type") == "content_block_delta":
                delta = event.get("delta") or {}
                if delta.get("type") == "text_delta":
                    events.append(StreamEvent("text", text=delta.get("text", "")))

        elif kind == "assistant":
            message = payload.get("message") or {}
            for block in message.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    events.append(StreamEvent(
                        "tool",
                        tool=str(block.get("name", "")),
                        detail=_describe_tool_input(block.get("input")),
                    ))

        elif kind == "result":
            self.usage = _usage_from_result(payload)
            self.turns += int(payload.get("num_turns") or 0)
            events.append(StreamEvent(
                "result",
                text=str(payload.get("result") or ""),
                usage=self.usage,
                session_id=sid,
            ))
            if payload.get("is_error"):
                subtype = str(payload.get("subtype") or "error")
                events.append(StreamEvent("error", text=subtype))

        return events


def _describe_tool_input(data: object) -> str:
    """Resumen de una linea de la entrada de una herramienta, para la UI."""
    if not isinstance(data, dict):
        return ""
    for key in ("command", "file_path", "path", "pattern", "query", "url", "prompt"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            flat = " ".join(value.split())
            return flat[:80] + ("..." if len(flat) > 80 else "")
    return ""


def _usage_from_result(payload: dict) -> Usage:
    raw = payload.get("usage") or {}
    cache_creation = raw.get("cache_creation_input_tokens") or 0

    context_window = 0
    model_usage = payload.get("modelUsage")
    if isinstance(model_usage, dict):
        for entry in model_usage.values():
            if isinstance(entry, dict) and entry.get("contextWindow"):
                context_window = int(entry["contextWindow"])
                break

    return Usage(
        input_tokens=int(raw.get("input_tokens") or 0),
        output_tokens=int(raw.get("output_tokens") or 0),
        cache_read_tokens=int(raw.get("cache_read_input_tokens") or 0),
        cache_creation_tokens=int(cache_creation),
        total_cost_usd=float(payload.get("total_cost_usd") or 0.0),
        context_window=context_window,
        num_turns=int(payload.get("num_turns") or 0),
        duration_ms=int(payload.get("duration_ms") or 0),
    )
