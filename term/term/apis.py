"""Proveedores que se conectan por API, con el bucle de agente propio de Term.

Una CLI como la de Claude Code trae su agente puesto: se le manda el mensaje y
ella sola lee archivos, ejecuta comandos y responde. Una API no: devuelve texto
o pide que ejecutes una funcion, y alguien tiene que ejecutarla y contarle como
fue. Ese alguien es Term.

De ahi el bucle de este modulo: mandar la conversacion, mirar si el modelo pide
herramientas, ejecutarlas con `tools.execute`, devolverle los resultados y
volver a preguntar, hasta que conteste sin pedir nada mas. Es lo que hace que
Gemini, Grok o un modelo local puedan crear carpetas o cambiar de cancion sin
tener ninguna CLI propia.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from . import keys as keystore
from . import tools as toolkit
from .providers import ParsedEvent, Provider

__all__ = [
    "API_PROVIDERS",
    "AnthropicApiProvider",
    "ApiProvider",
    "GeminiProvider",
    "OpenAICompatProvider",
]

# Cuantas veces seguidas se le deja pedir herramientas antes de cortar. Sin
# tope, un modelo que se atasca repitiendo la misma llamada no para nunca.
_MAX_ROUNDS = 12

_TIMEOUT = 300.0


def _httpx():
    """Importar httpx solo cuando hace falta.

    Term arranca y funciona con las CLI sin tocar la red; quien no use APIs no
    deberia necesitar la dependencia instalada para abrir el programa.
    """
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "Falta httpx para conectar por API. Instálalo con: pip install httpx"
        ) from exc
    return httpx


class ApiProvider(Provider):
    """Base de los proveedores HTTP.

    Las subclases solo cambian tres cosas: como se arma la peticion, como se
    lee el stream y como se representan las llamadas a herramientas.
    """

    transport = "api"
    supports_sessions = False   # el historial lo lleva Term, no el servidor
    supports_tools = True
    base_url = ""
    env_hint = ""

    def available(self) -> bool:
        return bool(self.api_key())

    def api_key(self) -> str:
        return keystore.get_key(self.key)

    # -- lo que implementa cada subclase ---------------------------------

    def _headers(self) -> dict[str, str]:
        raise NotImplementedError

    def _url(self, model: str) -> str:
        raise NotImplementedError

    def _body(self, model: str, history: list[dict], system: str,
              schemas: list[dict]) -> dict:
        raise NotImplementedError

    def _read_chunk(self, data: dict, acc: dict) -> list[ParsedEvent]:
        """Traducir un trozo del stream y acumular en `acc` lo que haga falta."""
        raise NotImplementedError

    def _assistant_turn(self, acc: dict) -> dict:
        """El mensaje del asistente tal y como hay que devolverlo al historial."""
        raise NotImplementedError

    def _tool_results(self, resultados: list[tuple[str, str, str]]) -> list[dict]:
        """Los resultados de las herramientas, con la forma que espera la API."""
        raise NotImplementedError

    # -- contrato de Provider (las APIs no usan linea de comandos) --------

    def build_command(self, prompt: str, **kwargs: object) -> list[str]:
        raise NotImplementedError("los proveedores por API no usan comandos")

    def parse(self, payload: dict) -> list[ParsedEvent]:
        return []

    # -- el bucle --------------------------------------------------------

    async def converse(
        self,
        history: list[dict],
        *,
        model: str,
        system: str = "",
        ctx: toolkit.ToolContext | None = None,
    ) -> AsyncIterator[ParsedEvent]:
        """Un turno completo: preguntar, ejecutar herramientas y repetir.

        `history` se modifica sobre la marcha, asi que al terminar contiene la
        conversacion entera y el siguiente turno arranca con memoria.
        """
        httpx = _httpx()
        ctx = ctx or toolkit.ToolContext()
        schemas = self._schemas(ctx)

        clave = self.api_key()
        if not clave:
            yield ParsedEvent("error", text=f"nokey:{self.key}")
            return

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            for _ in range(_MAX_ROUNDS):
                acc: dict[str, Any] = {"text": "", "calls": {}}
                try:
                    async with client.stream(
                        "POST", self._url(model),
                        headers=self._headers(),
                        json=self._body(model, history, system, schemas),
                    ) as response:
                        if response.status_code >= 400:
                            cuerpo = (await response.aread()).decode(
                                "utf-8", errors="replace")
                            yield ParsedEvent(
                                "error",
                                text=self._explain_error(response.status_code, cuerpo),
                            )
                            return
                        async for linea in response.aiter_lines():
                            for evento in self._consume(linea, acc):
                                yield evento
                except Exception as exc:  # red caida, DNS, timeout...
                    yield ParsedEvent("error", text=f"{type(exc).__name__}: {exc}")
                    return

                history.append(self._assistant_turn(acc))

                llamadas = list(acc["calls"].values())
                if not llamadas:
                    yield ParsedEvent("result", text=acc["text"],
                                      usage=acc.get("usage", {}))
                    return

                resultados = []
                for llamada in llamadas:
                    nombre = llamada.get("name") or ""
                    try:
                        args = json.loads(llamada.get("arguments") or "{}")
                    except ValueError:
                        args = {}
                    if not isinstance(args, dict):
                        args = {}

                    yield ParsedEvent("tool", tool=nombre,
                                      detail=self._describe(args))
                    ok, salida = toolkit.execute(nombre, args, ctx)
                    prefijo = "" if ok else "ERROR: "
                    resultados.append((llamada.get("id", ""), nombre, prefijo + salida))

                history.extend(self._tool_results(resultados))

            yield ParsedEvent(
                "error",
                text=f"El modelo siguió pidiendo herramientas tras {_MAX_ROUNDS} rondas.",
            )

    # -- utilidades compartidas -----------------------------------------

    def _schemas(self, ctx: toolkit.ToolContext) -> list[dict]:
        return toolkit.schemas_openai(ctx)

    def _consume(self, linea: str, acc: dict) -> list[ParsedEvent]:
        """Leer una linea del stream en formato SSE."""
        linea = linea.strip()
        if not linea or not linea.startswith("data:"):
            return []
        data = linea[5:].strip()
        if not data or data == "[DONE]":
            return []
        try:
            return self._read_chunk(json.loads(data), acc)
        except ValueError:
            return []

    @staticmethod
    def _describe(args: dict) -> str:
        for clave in ("command", "path", "pattern", "text", "query", "name", "action"):
            valor = args.get(clave)
            if isinstance(valor, str) and valor.strip():
                plano = " ".join(valor.split())
                return plano[:80] + ("…" if len(plano) > 80 else "")
        return ""

    def _explain_error(self, status: int, cuerpo: str) -> str:
        """Convertir un error HTTP en algo que se pueda leer."""
        detalle = cuerpo.strip()
        try:
            data = json.loads(cuerpo)
            if isinstance(data, dict):
                error = data.get("error")
                if isinstance(error, dict):
                    detalle = str(error.get("message") or detalle)
                elif isinstance(error, str):
                    detalle = error
        except ValueError:
            pass
        detalle = detalle[:300]
        if status in (401, 403):
            return f"{self.name}: clave rechazada ({status}). {detalle}"
        if status == 402:
            return f"{self.name}: sin saldo ({status}). {detalle}"
        if status == 404:
            return f"{self.name}: modelo no encontrado ({status}). {detalle}"
        if status == 429:
            return f"{self.name}: demasiadas peticiones ({status}). {detalle}"
        return f"{self.name}: error {status}. {detalle}"


# ---------------------------------------------------------------------------
# Formato OpenAI: lo hablan OpenRouter, OpenAI, Grok, Groq, DeepSeek y Ollama
# ---------------------------------------------------------------------------


class OpenAICompatProvider(ApiProvider):
    """Cualquier servicio que hable el dialecto de OpenAI."""

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key()}",
                "Content-Type": "application/json"}

    def _url(self, model: str) -> str:
        return f"{self.base_url}/chat/completions"

    def _body(self, model: str, history: list[dict], system: str,
              schemas: list[dict]) -> dict:
        mensajes = ([{"role": "system", "content": system}] if system else []) + history
        cuerpo: dict[str, Any] = {
            "model": model,
            "messages": mensajes,
            "stream": True,
        }
        if schemas:
            cuerpo["tools"] = schemas
        return cuerpo

    def _read_chunk(self, data: dict, acc: dict) -> list[ParsedEvent]:
        if uso := data.get("usage"):
            acc["usage"] = {
                "input_tokens": int(uso.get("prompt_tokens") or 0),
                "output_tokens": int(uso.get("completion_tokens") or 0),
            }
        opciones = data.get("choices") or []
        if not opciones:
            return []
        delta = opciones[0].get("delta") or {}

        eventos = []
        if texto := delta.get("content"):
            acc["text"] += texto
            eventos.append(ParsedEvent("text", text=texto))

        # Las llamadas llegan a trozos: el nombre en una y los argumentos
        # repartidos entre varias, identificadas por su indice.
        for llamada in delta.get("tool_calls") or []:
            idx = llamada.get("index", 0)
            actual = acc["calls"].setdefault(
                idx, {"id": "", "name": "", "arguments": ""})
            if llamada.get("id"):
                actual["id"] = llamada["id"]
            funcion = llamada.get("function") or {}
            if funcion.get("name"):
                actual["name"] = funcion["name"]
            if funcion.get("arguments"):
                actual["arguments"] += funcion["arguments"]
        return eventos

    def _assistant_turn(self, acc: dict) -> dict:
        mensaje: dict[str, Any] = {"role": "assistant", "content": acc["text"] or None}
        if acc["calls"]:
            mensaje["tool_calls"] = [
                {"id": c["id"] or f"call_{i}", "type": "function",
                 "function": {"name": c["name"], "arguments": c["arguments"] or "{}"}}
                for i, c in enumerate(acc["calls"].values())
            ]
        return mensaje

    def _tool_results(self, resultados: list[tuple[str, str, str]]) -> list[dict]:
        return [
            {"role": "tool", "tool_call_id": cid or f"call_{i}",
             "name": nombre, "content": salida}
            for i, (cid, nombre, salida) in enumerate(resultados)
        ]


class OpenRouterProvider(OpenAICompatProvider):
    """Una sola clave para GPT, Gemini, Grok, Claude, Llama y cientos más."""

    key = "openrouter"
    name = "OpenRouter"
    base_url = "https://openrouter.ai/api/v1"
    env_hint = "OPENROUTER_API_KEY"
    install_hint = "consigue una clave en https://openrouter.ai/keys"
    suggested_models = (
        "openai/gpt-5.2",
        "google/gemini-3.6-flash",
        "x-ai/grok-4",
        "anthropic/claude-opus-4.5",
        "deepseek/deepseek-v4",
        "meta-llama/llama-4-maverick",
    )

    def _headers(self) -> dict[str, str]:
        cabeceras = super()._headers()
        # OpenRouter usa estas dos para atribuir el trafico.
        cabeceras["HTTP-Referer"] = "https://github.com/juanaragon/term-dashboard"
        cabeceras["X-Title"] = "Term"
        return cabeceras


class OpenAIProvider(OpenAICompatProvider):
    key = "openai"
    name = "OpenAI"
    base_url = "https://api.openai.com/v1"
    env_hint = "OPENAI_API_KEY"
    install_hint = "consigue una clave en https://platform.openai.com/api-keys"
    suggested_models = ("gpt-5.2", "gpt-5.2-mini", "o4")


class GrokProvider(OpenAICompatProvider):
    key = "grok"
    name = "xAI Grok"
    base_url = "https://api.x.ai/v1"
    env_hint = "XAI_API_KEY"
    install_hint = "consigue una clave en https://console.x.ai"
    suggested_models = ("grok-4", "grok-4-fast")


class GroqProvider(OpenAICompatProvider):
    key = "groq"
    name = "Groq"
    base_url = "https://api.groq.com/openai/v1"
    env_hint = "GROQ_API_KEY"
    install_hint = "consigue una clave en https://console.groq.com/keys"
    suggested_models = ("llama-4-maverick", "qwen3-32b")


class DeepSeekProvider(OpenAICompatProvider):
    key = "deepseek"
    name = "DeepSeek"
    base_url = "https://api.deepseek.com/v1"
    env_hint = "DEEPSEEK_API_KEY"
    install_hint = "consigue una clave en https://platform.deepseek.com"
    suggested_models = ("deepseek-chat", "deepseek-reasoner")


class OllamaApiProvider(OpenAICompatProvider):
    """Ollama local. No lleva clave: basta con que el servidor esté levantado."""

    key = "ollama-api"
    name = "Ollama (local)"
    base_url = "http://localhost:11434/v1"
    install_hint = "arranca el servidor con: ollama serve"
    suggested_models = ("llama3.3", "qwen3", "mistral")

    def api_key(self) -> str:
        return "ollama"   # el servidor local no la mira, pero el header debe ir

    def available(self) -> bool:
        import shutil
        return shutil.which("ollama") is not None


# ---------------------------------------------------------------------------
# Gemini: formato propio
# ---------------------------------------------------------------------------


class GeminiProvider(ApiProvider):
    key = "gemini"
    name = "Google Gemini"
    base_url = "https://generativelanguage.googleapis.com/v1beta"
    env_hint = "GEMINI_API_KEY"
    install_hint = "consigue una clave en https://aistudio.google.com/apikey"
    suggested_models = ("gemini-3.6-flash", "gemini-3.1-pro", "gemini-3-flash")

    def _schemas(self, ctx: toolkit.ToolContext) -> list[dict]:
        return toolkit.schemas_gemini(ctx)

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json",
                "x-goog-api-key": self.api_key()}

    def _url(self, model: str) -> str:
        return f"{self.base_url}/models/{model}:streamGenerateContent?alt=sse"

    def _body(self, model: str, history: list[dict], system: str,
              schemas: list[dict]) -> dict:
        cuerpo: dict[str, Any] = {"contents": history}
        if system:
            cuerpo["systemInstruction"] = {"parts": [{"text": system}]}
        if schemas and schemas[0].get("function_declarations"):
            cuerpo["tools"] = schemas
        return cuerpo

    def _read_chunk(self, data: dict, acc: dict) -> list[ParsedEvent]:
        if uso := data.get("usageMetadata"):
            acc["usage"] = {
                "input_tokens": int(uso.get("promptTokenCount") or 0),
                "output_tokens": int(uso.get("candidatesTokenCount") or 0),
            }
        candidatos = data.get("candidates") or []
        if not candidatos:
            return []

        eventos = []
        for parte in (candidatos[0].get("content") or {}).get("parts") or []:
            if texto := parte.get("text"):
                acc["text"] += texto
                eventos.append(ParsedEvent("text", text=texto))
            if llamada := parte.get("functionCall"):
                idx = len(acc["calls"])
                acc["calls"][idx] = {
                    "id": f"call_{idx}",
                    "name": llamada.get("name", ""),
                    # El bucle espera los argumentos como texto JSON.
                    "arguments": json.dumps(llamada.get("args") or {}),
                }
        return eventos

    def _assistant_turn(self, acc: dict) -> dict:
        partes: list[dict] = []
        if acc["text"]:
            partes.append({"text": acc["text"]})
        for llamada in acc["calls"].values():
            try:
                args = json.loads(llamada["arguments"])
            except ValueError:
                args = {}
            partes.append({"functionCall": {"name": llamada["name"], "args": args}})
        return {"role": "model", "parts": partes or [{"text": ""}]}

    def _tool_results(self, resultados: list[tuple[str, str, str]]) -> list[dict]:
        return [{
            "role": "user",
            "parts": [
                {"functionResponse": {"name": nombre, "response": {"result": salida}}}
                for _, nombre, salida in resultados
            ],
        }]


# ---------------------------------------------------------------------------
# Anthropic por API
# ---------------------------------------------------------------------------


class AnthropicApiProvider(ApiProvider):
    key = "anthropic"
    name = "Anthropic API"
    base_url = "https://api.anthropic.com/v1"
    env_hint = "ANTHROPIC_API_KEY"
    install_hint = "consigue una clave en https://console.anthropic.com"
    suggested_models = ("claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5")

    def _schemas(self, ctx: toolkit.ToolContext) -> list[dict]:
        return toolkit.schemas_anthropic(ctx)

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _url(self, model: str) -> str:
        return f"{self.base_url}/messages"

    def _body(self, model: str, history: list[dict], system: str,
              schemas: list[dict]) -> dict:
        cuerpo: dict[str, Any] = {
            "model": model,
            "max_tokens": 8192,
            "messages": history,
            "stream": True,
        }
        if system:
            cuerpo["system"] = system
        if schemas:
            cuerpo["tools"] = schemas
        return cuerpo

    def _read_chunk(self, data: dict, acc: dict) -> list[ParsedEvent]:
        tipo = data.get("type")

        if tipo == "content_block_start":
            bloque = data.get("content_block") or {}
            if bloque.get("type") == "tool_use":
                acc["calls"][data.get("index", 0)] = {
                    "id": bloque.get("id", ""),
                    "name": bloque.get("name", ""),
                    "arguments": "",
                }
            return []

        if tipo == "content_block_delta":
            delta = data.get("delta") or {}
            if delta.get("type") == "text_delta":
                texto = delta.get("text", "")
                acc["text"] += texto
                return [ParsedEvent("text", text=texto)]
            if delta.get("type") == "input_json_delta":
                llamada = acc["calls"].get(data.get("index", 0))
                if llamada is not None:
                    llamada["arguments"] += delta.get("partial_json", "")
            return []

        if tipo == "message_delta":
            if uso := data.get("usage"):
                acc.setdefault("usage", {})["output_tokens"] = int(
                    uso.get("output_tokens") or 0)
        elif tipo == "message_start":
            uso = (data.get("message") or {}).get("usage") or {}
            acc["usage"] = {"input_tokens": int(uso.get("input_tokens") or 0),
                            "output_tokens": 0}
        return []

    def _assistant_turn(self, acc: dict) -> dict:
        contenido: list[dict] = []
        if acc["text"]:
            contenido.append({"type": "text", "text": acc["text"]})
        for llamada in acc["calls"].values():
            try:
                args = json.loads(llamada["arguments"] or "{}")
            except ValueError:
                args = {}
            contenido.append({"type": "tool_use", "id": llamada["id"],
                              "name": llamada["name"], "input": args})
        return {"role": "assistant", "content": contenido or [{"type": "text", "text": ""}]}

    def _tool_results(self, resultados: list[tuple[str, str, str]]) -> list[dict]:
        return [{
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": cid, "content": salida}
                for cid, _, salida in resultados
            ],
        }]


API_PROVIDERS: dict[str, ApiProvider] = {
    p.key: p for p in (
        OpenRouterProvider(), OpenAIProvider(), GeminiProvider(),
        GrokProvider(), GroqProvider(), DeepSeekProvider(),
        AnthropicApiProvider(), OllamaApiProvider(),
    )
}
