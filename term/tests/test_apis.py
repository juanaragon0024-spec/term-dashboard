"""Tests del motor de API y de su bucle de agente.

Ninguno toca la red: los formatos de stream se comprueban chunk a chunk, que es
donde de verdad se rompen las cosas.
"""

from __future__ import annotations

import json

import pytest

from term.apis import (
    API_PROVIDERS,
    AnthropicApiProvider,
    GeminiProvider,
    OpenRouterProvider,
)
from term.tools import ToolContext


class TestRegistro:
    def test_todos_declaran_transporte_api(self):
        for provider in API_PROVIDERS.values():
            assert provider.transport == "api"
            assert provider.name and provider.base_url

    def test_ninguno_promete_sesiones_del_servidor(self):
        """La memoria la lleva Term en su historial, no el servidor."""
        for provider in API_PROVIDERS.values():
            assert provider.supports_sessions is False

    def test_todos_sugieren_algun_modelo(self):
        for provider in API_PROVIDERS.values():
            assert provider.suggested_models

    def test_sin_clave_no_estan_disponibles(self, monkeypatch):
        monkeypatch.setattr("term.keys.get_key", lambda p: "")
        assert not OpenRouterProvider().available()

    def test_con_clave_si(self, monkeypatch):
        monkeypatch.setattr("term.keys.get_key", lambda p: "sk-x")
        assert OpenRouterProvider().available()

    def test_ollama_local_no_necesita_clave(self):
        assert API_PROVIDERS["ollama-api"].api_key()


class TestFormatoOpenAI:
    def setup_method(self):
        self.p = OpenRouterProvider()

    def chunk(self, delta, acc):
        return self.p._read_chunk({"choices": [{"delta": delta}]}, acc)

    def test_texto(self):
        acc = {"text": "", "calls": {}}
        eventos = self.chunk({"content": "Hola"}, acc)
        assert [(e.kind, e.text) for e in eventos] == [("text", "Hola")]
        assert acc["text"] == "Hola"

    def test_una_llamada_repartida_en_varios_trozos(self):
        """El nombre llega en un chunk y los argumentos en varios; ensamblarlos
        mal deja un JSON roto y la herramienta no se ejecuta."""
        acc = {"text": "", "calls": {}}
        self.chunk({"tool_calls": [{"index": 0, "id": "call_1",
                                    "function": {"name": "crear_carpeta"}}]}, acc)
        self.chunk({"tool_calls": [{"index": 0,
                                    "function": {"arguments": '{"path":'}}]}, acc)
        self.chunk({"tool_calls": [{"index": 0,
                                    "function": {"arguments": '"demo"}'}}]}, acc)

        llamada = acc["calls"][0]
        assert llamada["name"] == "crear_carpeta"
        assert json.loads(llamada["arguments"]) == {"path": "demo"}

    def test_dos_llamadas_a_la_vez_no_se_mezclan(self):
        acc = {"text": "", "calls": {}}
        self.chunk({"tool_calls": [
            {"index": 0, "id": "a", "function": {"name": "uno", "arguments": "{}"}},
            {"index": 1, "id": "b", "function": {"name": "dos", "arguments": "{}"}},
        ]}, acc)
        assert acc["calls"][0]["name"] == "uno"
        assert acc["calls"][1]["name"] == "dos"

    def test_el_consumo_se_recoge(self):
        acc = {"text": "", "calls": {}}
        self.p._read_chunk(
            {"usage": {"prompt_tokens": 12, "completion_tokens": 7}, "choices": []}, acc)
        assert acc["usage"] == {"input_tokens": 12, "output_tokens": 7}

    def test_el_turno_del_asistente_conserva_las_llamadas(self):
        acc = {"text": "voy a ello", "calls": {
            0: {"id": "c1", "name": "listar_carpeta", "arguments": "{}"}}}
        turno = self.p._assistant_turn(acc)
        assert turno["role"] == "assistant"
        assert turno["tool_calls"][0]["function"]["name"] == "listar_carpeta"

    def test_los_resultados_se_devuelven_con_su_identificador(self):
        """Sin el id correcto, la API no sabe a qué llamada responde."""
        mensajes = self.p._tool_results([("c1", "listar_carpeta", "dos archivos")])
        assert mensajes[0]["role"] == "tool"
        assert mensajes[0]["tool_call_id"] == "c1"
        assert mensajes[0]["content"] == "dos archivos"

    def test_openrouter_se_identifica(self, monkeypatch):
        monkeypatch.setattr("term.keys.get_key", lambda p: "sk-x")
        cabeceras = self.p._headers()
        assert cabeceras["Authorization"] == "Bearer sk-x"
        assert "X-Title" in cabeceras

    def test_el_cuerpo_lleva_sistema_y_herramientas(self):
        cuerpo = self.p._body("gpt-5.2", [{"role": "user", "content": "hola"}],
                              "eres Term", [{"type": "function"}])
        assert cuerpo["messages"][0] == {"role": "system", "content": "eres Term"}
        assert cuerpo["stream"] is True
        assert cuerpo["tools"]


class TestFormatoGemini:
    def setup_method(self):
        self.p = GeminiProvider()

    def test_texto(self):
        acc = {"text": "", "calls": {}}
        eventos = self.p._read_chunk(
            {"candidates": [{"content": {"parts": [{"text": "Hola"}]}}]}, acc)
        assert [(e.kind, e.text) for e in eventos] == [("text", "Hola")]

    def test_llamada_a_funcion(self):
        """Gemini manda los argumentos ya parseados, no como texto."""
        acc = {"text": "", "calls": {}}
        self.p._read_chunk({"candidates": [{"content": {"parts": [
            {"functionCall": {"name": "crear_carpeta", "args": {"path": "x"}}}]}}]}, acc)
        llamada = acc["calls"][0]
        assert llamada["name"] == "crear_carpeta"
        assert json.loads(llamada["arguments"]) == {"path": "x"}

    def test_el_turno_del_modelo_usa_parts(self):
        acc = {"text": "hola", "calls": {}}
        assert self.p._assistant_turn(acc) == {"role": "model",
                                               "parts": [{"text": "hola"}]}

    def test_los_resultados_van_como_functionResponse(self):
        mensajes = self.p._tool_results([("c1", "listar_carpeta", "vacía")])
        parte = mensajes[0]["parts"][0]["functionResponse"]
        assert parte["name"] == "listar_carpeta"
        assert parte["response"]["result"] == "vacía"

    def test_la_clave_viaja_en_su_cabecera(self, monkeypatch):
        monkeypatch.setattr("term.keys.get_key", lambda p: "AIza-x")
        assert self.p._headers()["x-goog-api-key"] == "AIza-x"

    def test_el_sistema_va_en_su_campo(self):
        cuerpo = self.p._body("gemini-3.6-flash", [], "eres Term", [])
        assert cuerpo["systemInstruction"]["parts"][0]["text"] == "eres Term"


class TestFormatoAnthropic:
    def setup_method(self):
        self.p = AnthropicApiProvider()

    def test_texto(self):
        acc = {"text": "", "calls": {}}
        eventos = self.p._read_chunk(
            {"type": "content_block_delta",
             "delta": {"type": "text_delta", "text": "Hola"}}, acc)
        assert [(e.kind, e.text) for e in eventos] == [("text", "Hola")]

    def test_llamada_ensamblada_desde_json_parcial(self):
        acc = {"text": "", "calls": {}}
        self.p._read_chunk({"type": "content_block_start", "index": 1,
                            "content_block": {"type": "tool_use", "id": "tu_1",
                                              "name": "buscar_texto"}}, acc)
        self.p._read_chunk({"type": "content_block_delta", "index": 1,
                            "delta": {"type": "input_json_delta",
                                      "partial_json": '{"text":'}}, acc)
        self.p._read_chunk({"type": "content_block_delta", "index": 1,
                            "delta": {"type": "input_json_delta",
                                      "partial_json": '"hola"}'}}, acc)
        llamada = acc["calls"][1]
        assert llamada["name"] == "buscar_texto"
        assert json.loads(llamada["arguments"]) == {"text": "hola"}

    def test_el_consumo_de_entrada_llega_al_principio(self):
        acc = {"text": "", "calls": {}}
        self.p._read_chunk(
            {"type": "message_start", "message": {"usage": {"input_tokens": 40}}}, acc)
        assert acc["usage"]["input_tokens"] == 40

    def test_los_resultados_van_como_tool_result(self):
        mensajes = self.p._tool_results([("tu_1", "buscar_texto", "3 líneas")])
        bloque = mensajes[0]["content"][0]
        assert bloque["type"] == "tool_result"
        assert bloque["tool_use_id"] == "tu_1"


class TestErrores:
    def setup_method(self):
        self.p = OpenRouterProvider()

    @pytest.mark.parametrize("status,esperado", [
        (401, "clave rechazada"),
        (402, "sin saldo"),
        (404, "modelo no encontrado"),
        (429, "demasiadas peticiones"),
    ])
    def test_cada_codigo_se_explica(self, status, esperado):
        assert esperado in self.p._explain_error(status, "{}")

    def test_se_rescata_el_mensaje_de_la_api(self):
        cuerpo = json.dumps({"error": {"message": "No credits remaining"}})
        assert "No credits remaining" in self.p._explain_error(402, cuerpo)

    def test_un_cuerpo_que_no_es_json_no_revienta(self):
        assert "502" in self.p._explain_error(502, "<html>Bad Gateway</html>")


class TestBucleDeAgente:
    """El bucle completo, con un servidor de mentira."""

    @staticmethod
    def sse(objetos):
        return [f"data: {json.dumps(o)}" for o in objetos] + ["data: [DONE]"]

    @pytest.fixture
    def falso_httpx(self, monkeypatch):
        """Sustituye httpx por uno que devuelve respuestas guionizadas."""
        respuestas: list[list[str]] = []
        enviados: list[dict] = []

        class RespuestaFalsa:
            status_code = 200

            def __init__(self, lineas):
                self._lineas = lineas

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def aiter_lines(self):
                for linea in self._lineas:
                    yield linea

        class ClienteFalso:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            def stream(self, method, url, headers=None, json=None):
                enviados.append(json)
                return RespuestaFalsa(respuestas.pop(0))

        class ModuloFalso:
            AsyncClient = ClienteFalso

        monkeypatch.setattr("term.apis._httpx", lambda: ModuloFalso)
        return respuestas, enviados

    async def test_una_respuesta_de_texto_termina_el_turno(self, falso_httpx, monkeypatch):
        respuestas, _ = falso_httpx
        monkeypatch.setattr("term.keys.get_key", lambda p: "sk-x")
        respuestas.append(self.sse([
            {"choices": [{"delta": {"content": "Hola "}}]},
            {"choices": [{"delta": {"content": "mundo"}}]},
        ]))

        historial = [{"role": "user", "content": "saluda"}]
        eventos = [e async for e in OpenRouterProvider().converse(
            historial, model="gpt-5.2")]

        assert [e.text for e in eventos if e.kind == "text"] == ["Hola ", "mundo"]
        assert eventos[-1].kind == "result"
        assert eventos[-1].text == "Hola mundo"

    async def test_ejecuta_la_herramienta_y_vuelve_a_preguntar(
            self, falso_httpx, monkeypatch, tmp_path):
        """El corazón del asunto: el modelo pide, Term hace, el modelo responde."""
        respuestas, enviados = falso_httpx
        monkeypatch.setattr("term.keys.get_key", lambda p: "sk-x")

        respuestas.append(self.sse([
            {"choices": [{"delta": {"tool_calls": [{
                "index": 0, "id": "c1",
                "function": {"name": "crear_carpeta",
                             "arguments": '{"path": "creada-por-la-ia"}'},
            }]}}]},
        ]))
        respuestas.append(self.sse([
            {"choices": [{"delta": {"content": "Listo, ya está creada."}}]},
        ]))

        historial = [{"role": "user", "content": "crea una carpeta"}]
        eventos = [e async for e in OpenRouterProvider().converse(
            historial, model="gpt-5.2",
            ctx=ToolContext(workdir=str(tmp_path)))]

        # La carpeta existe de verdad.
        assert (tmp_path / "creada-por-la-ia").is_dir()
        # Se avisó del uso de la herramienta.
        assert [e.tool for e in eventos if e.kind == "tool"] == ["crear_carpeta"]
        # Y el turno acabó con la respuesta final.
        assert eventos[-1].kind == "result"
        assert "ya está creada" in eventos[-1].text
        # El resultado de la herramienta se le devolvió al modelo.
        segundo_envio = enviados[1]["messages"]
        assert any(m.get("role") == "tool" for m in segundo_envio)

    async def test_el_historial_queda_listo_para_el_turno_siguiente(
            self, falso_httpx, monkeypatch):
        """Sin esto, la conversación por API no tendría memoria."""
        respuestas, _ = falso_httpx
        monkeypatch.setattr("term.keys.get_key", lambda p: "sk-x")
        respuestas.append(self.sse([
            {"choices": [{"delta": {"content": "Encantado"}}]}]))

        historial = [{"role": "user", "content": "hola"}]
        async for _ in OpenRouterProvider().converse(historial, model="gpt-5.2"):
            pass

        assert len(historial) == 2
        assert historial[1]["role"] == "assistant"
        assert historial[1]["content"] == "Encantado"

    async def test_sin_clave_avisa_en_lugar_de_llamar(self, monkeypatch):
        monkeypatch.setattr("term.keys.get_key", lambda p: "")
        eventos = [e async for e in OpenRouterProvider().converse([], model="x")]
        assert eventos[0].kind == "error"
        assert eventos[0].text == "nokey:openrouter"

    async def test_una_herramienta_negada_se_le_cuenta_al_modelo(
            self, falso_httpx, monkeypatch, tmp_path):
        """Al modelo hay que decirle por qué falló, no dejarlo a ciegas."""
        respuestas, enviados = falso_httpx
        monkeypatch.setattr("term.keys.get_key", lambda p: "sk-x")
        respuestas.append(self.sse([
            {"choices": [{"delta": {"tool_calls": [{
                "index": 0, "id": "c1",
                "function": {"name": "ejecutar_shell",
                             "arguments": '{"command": "rm -rf /"}'},
            }]}}]},
        ]))
        respuestas.append(self.sse([
            {"choices": [{"delta": {"content": "Entendido, no puedo."}}]}]))

        historial = [{"role": "user", "content": "borra todo"}]
        async for _ in OpenRouterProvider().converse(
            historial, model="gpt-5.2",
            ctx=ToolContext(workdir=str(tmp_path), allow_system=False),
        ):
            pass

        resultado = next(m for m in enviados[1]["messages"] if m.get("role") == "tool")
        assert resultado["content"].startswith("ERROR:")
        assert "permisos" in resultado["content"]
