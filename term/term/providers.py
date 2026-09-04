"""Proveedores de IA.

Term no habla con ningun modelo directamente: habla con la CLI de un proveedor.
Cada proveedor sabe dos cosas, y solo dos: como construir la linea de comandos
de un turno y como traducir las lineas JSON que escupe a los eventos que la TUI
entiende. Anadir un proveedor nuevo es escribir esas dos funciones.

Un modelo se nombra `proveedor/modelo` -- `claude/opus`, `opencode/gpt-5.2`,
`ollama/llama3` -- para que una pestana pueda usar una IA distinta de la de al
lado sin que ninguna se entere.
"""

from __future__ import annotations

import json
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "PROVIDERS",
    "ParsedEvent",
    "Provider",
    "available_providers",
    "get_provider",
    "join_ref",
    "split_ref",
]


@dataclass
class ParsedEvent:
    """Evento normalizado, comun a todos los proveedores.

    Es deliberadamente pobre: texto, herramienta, final o error. Lo que un
    proveedor sepa contar de mas se resume aqui o se descarta, porque la TUI
    solo sabe pintar estas cuatro cosas.
    """

    kind: str                      # text | tool | result | error | init
    text: str = ""
    tool: str = ""
    detail: str = ""
    session_id: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


def _summarise_input(data: object) -> str:
    """Resumen de una linea de la entrada de una herramienta."""
    if not isinstance(data, dict):
        return ""
    for key in ("command", "filePath", "file_path", "path", "pattern",
                "query", "url", "prompt", "description"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            flat = " ".join(value.split())
            return flat[:80] + ("..." if len(flat) > 80 else "")
    return ""


class Provider(ABC):
    """Contrato que cumple cada CLI de IA."""

    key: str = ""
    name: str = ""
    binary: str = ""
    # "cli" habla con un programa por su linea de comandos; "api" habla por
    # HTTP y ejecuta las herramientas dentro de Term.
    transport: str = "cli"
    # Si la CLI sabe retomar una conversacion. Sin esto, cada turno empieza
    # de cero y la pestana no tiene memoria.
    supports_sessions: bool = False
    # Si la CLI ejecuta herramientas (leer ficheros, correr comandos).
    supports_tools: bool = False
    # Sugerencias para el selector; no es una lista cerrada.
    suggested_models: tuple[str, ...] = ()
    install_hint: str = ""

    def available(self) -> bool:
        return bool(self.binary) and shutil.which(self.binary) is not None

    @abstractmethod
    def build_command(
        self,
        prompt: str,
        *,
        model: str = "",
        session_id: str = "",
        resume: bool = False,
        workdir: str = "",
        effort: str = "",
        system_prompt: str = "",
        restricted: bool = False,
        permission_mode: str = "",
        allowed_tools: tuple[str, ...] = (),
        max_turns: int = 15,
    ) -> list[str]:
        """Linea de comandos completa para un turno."""

    @abstractmethod
    def parse(self, payload: dict) -> list[ParsedEvent]:
        """Traducir una linea de salida JSON a eventos de Term."""

    def parse_line(self, raw: str) -> list[ParsedEvent]:
        """Parsear una linea de texto. Las que no son JSON se ignoran."""
        raw = raw.strip()
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except ValueError:
            return []
        if not isinstance(payload, dict):
            return []
        return self.parse(payload)


# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------


class ClaudeProvider(Provider):
    """La CLI de Claude Code. Es la unica verificada de punta a punta."""

    key = "claude"
    name = "Claude Code"
    binary = "claude"
    supports_sessions = True
    supports_tools = True
    suggested_models = ("default", "opus", "sonnet", "haiku")
    install_hint = "npm install -g @anthropic-ai/claude-code"

    # Alias que la CLI acepta en --model. Cualquier otra cosa se pasa tal cual,
    # asi que un identificador con fecha tambien funciona.
    _ALIASES = {"default": None, "opus": "opus", "sonnet": "sonnet",
                "haiku": "haiku"}

    def build_command(
        self, prompt: str, *, model: str = "", session_id: str = "",
        resume: bool = False, workdir: str = "", effort: str = "",
        system_prompt: str = "", restricted: bool = False,
        permission_mode: str = "", allowed_tools: tuple[str, ...] = (),
        max_turns: int = 15,
    ) -> list[str]:
        cmd = [self.binary, "-p", prompt]

        if session_id:
            cmd += (["--resume", session_id] if resume
                    else ["--session-id", session_id])

        cmd += [
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--verbose",
            "--max-turns", str(max_turns),
        ]

        alias = self._ALIASES.get(model, model or None)
        if alias:
            cmd += ["--model", alias]
        if effort:
            cmd += ["--effort", effort]
        # El nivel de permisos llega ya traducido a lo que la CLI entiende.
        # Sin esto la CLI se paraba a preguntar y, en modo -p, no puede: por
        # eso «pon la siguiente canción» acababa en «necesito tu aprobación».
        if restricted:
            cmd += ["--restricted"]
        else:
            if allowed_tools:
                cmd += ["--allowedTools", *allowed_tools]
            if permission_mode and permission_mode != "default":
                cmd += ["--permission-mode", permission_mode]
        if system_prompt:
            cmd += ["--append-system-prompt", system_prompt]
        if workdir:
            cmd += ["--add-dir", workdir]
        return cmd

    def parse(self, payload: dict) -> list[ParsedEvent]:
        kind = payload.get("type")
        sid = payload.get("session_id", "")

        if kind == "system" and payload.get("subtype") == "init":
            return [ParsedEvent("init", session_id=sid)]

        if kind == "stream_event":
            event = payload.get("event") or {}
            if event.get("type") == "content_block_delta":
                delta = event.get("delta") or {}
                if delta.get("type") == "text_delta":
                    return [ParsedEvent("text", text=delta.get("text", ""))]
            return []

        if kind == "assistant":
            out = []
            message = payload.get("message") or {}
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    out.append(ParsedEvent(
                        "tool",
                        tool=str(block.get("name", "")),
                        detail=_summarise_input(block.get("input")),
                    ))
            return out

        if kind == "result":
            raw = payload.get("usage") or {}
            window = 0
            model_usage = payload.get("modelUsage")
            if isinstance(model_usage, dict):
                for entry in model_usage.values():
                    if isinstance(entry, dict) and entry.get("contextWindow"):
                        window = int(entry["contextWindow"])
                        break
            usage = {
                "input_tokens": int(raw.get("input_tokens") or 0),
                "output_tokens": int(raw.get("output_tokens") or 0),
                "cache_read_tokens": int(raw.get("cache_read_input_tokens") or 0),
                "cache_creation_tokens": int(
                    raw.get("cache_creation_input_tokens") or 0),
                "total_cost_usd": float(payload.get("total_cost_usd") or 0.0),
                "context_window": window,
                "num_turns": int(payload.get("num_turns") or 0),
                "duration_ms": int(payload.get("duration_ms") or 0),
            }
            out = [ParsedEvent("result", text=str(payload.get("result") or ""),
                               usage=usage, session_id=sid)]
            if payload.get("is_error"):
                out.append(ParsedEvent("error",
                                       text=str(payload.get("subtype") or "error")))
            return out

        return []


# ---------------------------------------------------------------------------
# opencode
# ---------------------------------------------------------------------------


class OpencodeProvider(Provider):
    """opencode: una sola CLI para GPT, Gemini, Grok, DeepSeek, Qwen y demas.

    El modelo se nombra `casa/modelo` dentro de opencode (por ejemplo
    `opencode/gpt-5.2` o `anthropic/claude-opus-4-5`), asi que aqui el modelo
    llega ya con esa forma y se pasa tal cual a `-m`.
    """

    key = "opencode"
    name = "opencode"
    binary = "opencode"
    supports_sessions = True
    supports_tools = True
    # Sin casa delante se entiende la pasarela propia de opencode, que es de
    # donde salen GPT, Gemini, Grok y compania. Con casa (`anthropic/...`) se
    # respeta la que se pida.
    suggested_models = (
        "gpt-5.2",
        "gemini-3.6-flash",
        "grok-4",
        "deepseek-v4-pro",
        "qwen3.6-plus",
        "anthropic/claude-opus-4-5",
    )
    install_hint = "npm install -g opencode-ai"

    def build_command(
        self, prompt: str, *, model: str = "", session_id: str = "",
        resume: bool = False, workdir: str = "", effort: str = "",
        system_prompt: str = "", restricted: bool = False,
        permission_mode: str = "", allowed_tools: tuple[str, ...] = (),
        max_turns: int = 15,
    ) -> list[str]:
        cmd = [self.binary, "run", "--format", "json"]

        # opencode retoma por id de sesion; sin --session abre una nueva y nos
        # dice cual en el primer evento.
        if resume and session_id:
            cmd += ["--session", session_id]
        if model:
            cmd += ["-m", self.qualify(model)]
        # `--variant` es el equivalente de effort: alto, maximo, minimo.
        if effort:
            cmd += ["--variant", effort]
        if workdir:
            cmd += ["--dir", workdir]

        # opencode no tiene un flag de prompt de sistema, asi que se antepone
        # al mensaje. No es equivalente, pero es lo que la CLI permite.
        message = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        cmd += ["--", message]
        return cmd

    @staticmethod
    def qualify(model: str) -> str:
        """Completar el modelo con su casa.

        Term ya usa la primera barra para separar el proveedor, asi que aqui
        llega `gpt-5.2` en lugar de `opencode/gpt-5.2`. Un modelo que ya trae
        casa (`anthropic/claude-opus-4-5`) se respeta tal cual.
        """
        return model if "/" in model else f"opencode/{model}"

    def parse(self, payload: dict) -> list[ParsedEvent]:
        kind = payload.get("type", "")
        props = payload.get("properties") or {}
        sid = (payload.get("sessionID") or props.get("sessionID")
               or (props.get("info") or {}).get("id") or "")

        if kind == "session.error" or kind == "error":
            error = payload.get("error") or props.get("error") or {}
            data = error.get("data") if isinstance(error, dict) else None
            message = ""
            if isinstance(data, dict):
                message = str(data.get("message") or "")
            if not message and isinstance(error, dict):
                message = str(error.get("name") or "")
            return [ParsedEvent("error", text=message or "error de opencode")]

        if kind == "message.part.updated":
            part = props.get("part") or {}
            ptype = part.get("type")
            if ptype == "text":
                # opencode manda el texto acumulado, no el trozo nuevo, asi que
                # se marca como texto completo y quien lo pinta reemplaza.
                return [ParsedEvent("text", text=str(part.get("text") or ""),
                                    detail="full", session_id=sid)]
            if ptype in ("tool", "tool-invocation"):
                state = part.get("state") or {}
                return [ParsedEvent(
                    "tool",
                    tool=str(part.get("tool") or state.get("title") or ""),
                    detail=_summarise_input(state.get("input") or part.get("input")),
                    session_id=sid,
                )]
            return []

        if kind == "session.idle":
            return [ParsedEvent("result", session_id=sid)]

        # El primer evento de una sesion nos da su id, que hace falta para
        # poder retomarla luego.
        if sid and kind in ("session.updated", "message.updated"):
            return [ParsedEvent("init", session_id=sid)]

        return []


# ---------------------------------------------------------------------------
# Ollama (modelos locales)
# ---------------------------------------------------------------------------


class OllamaProvider(Provider):
    """Modelos locales con Ollama.

    No ejecuta herramientas ni guarda sesiones: es una conversacion suelta,
    util para preguntas rapidas sin salir de la maquina.
    """

    key = "ollama"
    name = "Ollama (local)"
    binary = "ollama"
    supports_sessions = False
    supports_tools = False
    suggested_models = ("llama3.3", "qwen3", "mistral", "phi4")
    install_hint = "brew install ollama"

    def build_command(
        self, prompt: str, *, model: str = "", session_id: str = "",
        resume: bool = False, workdir: str = "", effort: str = "",
        system_prompt: str = "", restricted: bool = False,
        permission_mode: str = "", allowed_tools: tuple[str, ...] = (),
        max_turns: int = 15,
    ) -> list[str]:
        message = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        return [self.binary, "run", model or "llama3.3", message]

    def parse(self, payload: dict) -> list[ParsedEvent]:
        # `ollama run` escribe texto plano, no JSON: parse_line no llega aqui.
        return []

    def parse_line(self, raw: str) -> list[ParsedEvent]:
        return [ParsedEvent("text", text=raw)] if raw else []


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, Provider] = {
    p.key: p for p in (ClaudeProvider(), OpencodeProvider(), OllamaProvider())
}


_apis_registradas = False


def _ensure_api_providers() -> None:
    """Sumar los proveedores por API al registro, la primera vez que se miran.

    El registro es perezoso a proposito: `apis` importa de aqui, asi que
    hacerlo al cargar el modulo produce un import circular en cuanto alguien
    importa `apis` antes que `providers`.
    """
    global _apis_registradas
    if _apis_registradas:
        return
    _apis_registradas = True
    from .apis import API_PROVIDERS

    PROVIDERS.update(API_PROVIDERS)

DEFAULT_PROVIDER = "claude"


def all_providers() -> dict[str, Provider]:
    """El registro completo, con los de API ya cargados."""
    _ensure_api_providers()
    return PROVIDERS


def get_provider(key: str) -> Provider:
    """Proveedor por clave, con reserva al predeterminado."""
    registro = all_providers()
    return registro.get(key) or registro[DEFAULT_PROVIDER]


def available_providers() -> list[Provider]:
    """Los que se pueden usar aqui: instalados, o con su clave puesta."""
    return [p for p in all_providers().values() if p.available()]


def api_providers() -> list[Provider]:
    """Los que se conectan por HTTP, esten configurados o no."""
    return [p for p in all_providers().values() if p.transport == "api"]


def split_ref(ref: str) -> tuple[str, str]:
    """Partir `proveedor/modelo` en sus dos mitades.

    Una referencia sin barra se entiende como un modelo de Claude, que es lo
    que guardaban las versiones anteriores de la configuracion.
    """
    ref = (ref or "").strip()
    if not ref:
        return DEFAULT_PROVIDER, "default"
    registro = all_providers()
    head, _, tail = ref.partition("/")
    if head in registro and tail:
        return head, tail
    if head in registro and not tail:
        return head, "default"
    return DEFAULT_PROVIDER, ref


def join_ref(provider_key: str, model: str) -> str:
    return f"{provider_key}/{model}" if model else provider_key
