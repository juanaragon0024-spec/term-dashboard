"""Tests de los adaptadores de proveedor.

Solo el de Claude está verificado contra la salida real de su CLI; los demás
se comprueban contra los formatos que documentan sus binarios.
"""

from __future__ import annotations

import json

import pytest

from term.providers import (
    PROVIDERS,
    ClaudeProvider,
    OllamaProvider,
    OpencodeProvider,
    get_provider,
    join_ref,
    split_ref,
)


class TestRegistro:
    def test_cada_proveedor_se_registra_con_su_clave(self):
        for key, provider in PROVIDERS.items():
            assert provider.key == key
            assert provider.name
            assert provider.binary

    def test_un_proveedor_desconocido_cae_en_claude(self):
        assert get_provider("no-existe").key == "claude"

    def test_partir_y_juntar_referencias(self):
        for ref in ("claude/opus", "opencode/gpt-5.2", "ollama/llama3.3"):
            provider_key, model = split_ref(ref)
            assert join_ref(provider_key, model) == ref

    def test_una_linea_que_no_es_json_se_ignora(self):
        """Las CLI mezclan avisos en texto plano con los eventos JSON."""
        provider = ClaudeProvider()
        assert provider.parse_line("Actualizando...") == []
        assert provider.parse_line("") == []
        assert provider.parse_line("[1, 2, 3]") == []


class TestClaude:
    def setup_method(self):
        self.p = ClaudeProvider()

    def test_abre_la_sesion_con_session_id(self):
        cmd = self.p.build_command("hola", session_id="abc")
        assert cmd[cmd.index("--session-id") + 1] == "abc"
        assert "--resume" not in cmd

    def test_la_continua_con_resume(self):
        cmd = self.p.build_command("hola", session_id="abc", resume=True)
        assert cmd[cmd.index("--resume") + 1] == "abc"
        assert "--session-id" not in cmd

    def test_el_modelo_por_defecto_no_pasa_el_flag(self):
        assert "--model" not in self.p.build_command("hola", model="default")

    def test_un_identificador_literal_se_pasa_tal_cual(self):
        cmd = self.p.build_command("hola", model="claude-opus-4-5-20251101")
        assert cmd[cmd.index("--model") + 1] == "claude-opus-4-5-20251101"

    def test_restricted(self):
        assert "--restricted" in self.p.build_command("hola", restricted=True)

    def test_delta_de_texto(self):
        linea = json.dumps({
            "type": "stream_event",
            "event": {"type": "content_block_delta",
                      "delta": {"type": "text_delta", "text": "Hola"}},
        })
        eventos = self.p.parse_line(linea)
        assert [(e.kind, e.text) for e in eventos] == [("text", "Hola")]

    def test_uso_de_herramienta(self):
        linea = json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls /tmp"}},
            ]},
        })
        evento = self.p.parse_line(linea)[0]
        assert (evento.kind, evento.tool, evento.detail) == ("tool", "Bash", "ls /tmp")

    def test_resultado_con_consumo_real(self):
        linea = json.dumps({
            "type": "result", "subtype": "success", "is_error": False,
            "result": "Hola", "num_turns": 1, "total_cost_usd": 0.332,
            "session_id": "s1",
            "usage": {"input_tokens": 2, "output_tokens": 5,
                      "cache_creation_input_tokens": 33189},
            "modelUsage": {"claude-opus-5": {"contextWindow": 1000000}},
        })
        evento = self.p.parse_line(linea)[0]
        assert evento.kind == "result"
        assert evento.usage["context_window"] == 1_000_000
        assert evento.usage["total_cost_usd"] == pytest.approx(0.332)


class TestOpencode:
    def setup_method(self):
        self.p = OpencodeProvider()

    def test_pide_salida_json(self):
        cmd = self.p.build_command("hola")
        assert cmd[:4] == ["opencode", "run", "--format", "json"]

    def test_el_modelo_sin_casa_usa_la_pasarela_de_opencode(self):
        """Term ya gasta la primera barra en el proveedor, así que aquí el
        modelo llega sin su casa y hay que devolvérsela."""
        cmd = self.p.build_command("hola", model="gpt-5.2")
        assert cmd[cmd.index("-m") + 1] == "opencode/gpt-5.2"

    def test_el_modelo_con_casa_se_respeta(self):
        cmd = self.p.build_command("hola", model="anthropic/claude-opus-4-5")
        assert cmd[cmd.index("-m") + 1] == "anthropic/claude-opus-4-5"

    def test_solo_retoma_cuando_se_le_pide(self):
        assert "--session" not in self.p.build_command("hola", session_id="s1")
        cmd = self.p.build_command("hola", session_id="s1", resume=True)
        assert cmd[cmd.index("--session") + 1] == "s1"

    def test_el_esfuerzo_viaja_como_variante(self):
        cmd = self.p.build_command("hola", effort="high")
        assert cmd[cmd.index("--variant") + 1] == "high"

    def test_el_mensaje_va_tras_el_separador(self):
        """Con `--` por delante, un mensaje que empiece por guion no se
        confunde con una opción."""
        cmd = self.p.build_command("--ayuda a interpretar esto")
        assert cmd[-2] == "--"
        assert cmd[-1] == "--ayuda a interpretar esto"

    def test_texto_en_streaming(self):
        linea = json.dumps({
            "type": "message.part.updated",
            "properties": {"part": {"type": "text", "text": "Hola qué tal",
                                    "sessionID": "ses_1"}},
        })
        evento = self.p.parse_line(linea)[0]
        assert evento.kind == "text"
        assert evento.text == "Hola qué tal"
        # opencode manda el texto acumulado, no el trozo nuevo.
        assert evento.detail == "full"

    def test_uso_de_herramienta(self):
        linea = json.dumps({
            "type": "message.part.updated",
            "properties": {"part": {"type": "tool", "tool": "bash",
                                    "state": {"input": {"command": "ls"}}}},
        })
        evento = self.p.parse_line(linea)[0]
        assert (evento.kind, evento.tool, evento.detail) == ("tool", "bash", "ls")

    def test_el_final_de_la_sesion_cierra_el_turno(self):
        linea = json.dumps({"type": "session.idle", "properties": {"sessionID": "s1"}})
        assert self.p.parse_line(linea)[0].kind == "result"

    def test_error_de_credenciales(self):
        """Formato real capturado de opencode sin método de pago."""
        linea = json.dumps({
            "type": "error", "sessionID": "ses_1",
            "error": {"name": "APIError",
                      "data": {"message": "Unauthorized: CreditsError"}},
        })
        evento = self.p.parse_line(linea)[0]
        assert evento.kind == "error"
        assert "CreditsError" in evento.text


class TestOllama:
    def setup_method(self):
        self.p = OllamaProvider()

    def test_no_promete_sesiones_ni_herramientas(self):
        """Term no debe intentar retomar una conversación que no existe."""
        assert self.p.supports_sessions is False
        assert self.p.supports_tools is False

    def test_su_salida_es_texto_plano(self):
        eventos = self.p.parse_line("una línea suelta")
        assert [(e.kind, e.text) for e in eventos] == [("text", "una línea suelta")]

    def test_lleva_modelo_y_mensaje(self):
        cmd = self.p.build_command("hola", model="llama3.3")
        assert cmd == ["ollama", "run", "llama3.3", "hola"]
