"""Tests de la capa de sesion: construccion del comando y parseo de eventos."""

from __future__ import annotations

import json

import pytest

from term.session import ChatSession as ClaudeSession
from term.session import StreamEvent, Usage

# Lineas reales capturadas de `claude -p --output-format stream-json --verbose`,
# recortadas a los campos que Term lee.
INIT_LINE = json.dumps({
    "type": "system", "subtype": "init",
    "session_id": "aa5f235e-fe19-41fc-bc32-eb6524574bab",
    "model": "claude-opus-5[1m]", "cwd": "/tmp",
})
DELTA_LINE = json.dumps({
    "type": "stream_event",
    "event": {
        "type": "content_block_delta",
        "delta": {"type": "text_delta", "text": "Hola"},
    },
    "session_id": "aa5f235e",
})
TOOL_LINE = json.dumps({
    "type": "assistant",
    "message": {"content": [
        {"type": "text", "text": "Voy a mirarlo"},
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls -la /tmp"}},
    ]},
    "session_id": "aa5f235e",
})
RESULT_LINE = json.dumps({
    "type": "result", "subtype": "success", "is_error": False,
    "result": "Hola", "num_turns": 1, "duration_ms": 2371,
    "total_cost_usd": 0.332025,
    "session_id": "aa5f235e-fe19-41fc-bc32-eb6524574bab",
    "usage": {
        "input_tokens": 2, "output_tokens": 5,
        "cache_read_input_tokens": 0, "cache_creation_input_tokens": 33189,
    },
    "modelUsage": {"claude-opus-5[1m]": {"contextWindow": 1000000}},
})


def parse(session: ClaudeSession, line: str) -> list[StreamEvent]:
    return [session._adopt(p) for p in session.provider.parse_line(line)]


class TestBuildCommand:
    def test_primer_turno_abre_la_sesion_con_session_id(self):
        s = ClaudeSession(session_id="abc-123")
        cmd = s.build_command("hola")
        assert "--session-id" in cmd
        assert cmd[cmd.index("--session-id") + 1] == "abc-123"
        assert "--resume" not in cmd

    def test_turnos_siguientes_continuan_con_resume(self):
        """El bug que hacia que Claude no recordase nada entre mensajes."""
        s = ClaudeSession(session_id="abc-123", started=True)
        cmd = s.build_command("y ahora?")
        assert "--resume" in cmd
        assert cmd[cmd.index("--resume") + 1] == "abc-123"
        assert "--session-id" not in cmd

    def test_pide_siempre_stream_json(self):
        cmd = ClaudeSession().build_command("hola")
        assert cmd[cmd.index("--output-format") + 1] == "stream-json"
        assert "--include-partial-messages" in cmd
        assert "--verbose" in cmd

    def test_modelo_predeterminado_no_pasa_el_flag(self):
        s = ClaudeSession()
        s.set_model_ref("claude/default")
        assert "--model" not in s.build_command("hola")

    def test_alias_de_modelo(self):
        s = ClaudeSession()
        s.set_model_ref("claude/opus")
        cmd = s.build_command("hola")
        assert cmd[cmd.index("--model") + 1] == "opus"

    def test_identificador_de_modelo_literal(self):
        s = ClaudeSession()
        s.set_model_ref("claude/claude-opus-4-5-20251101")
        cmd = s.build_command("hola")
        assert cmd[cmd.index("--model") + 1] == "claude-opus-4-5-20251101"

    def test_restricted_cuando_se_deniegan_permisos(self):
        """Denegar permisos tiene que quitar herramientas de verdad."""
        cmd = ClaudeSession().build_command("hola", restricted=True)
        assert "--restricted" in cmd
        assert "--permission-mode" not in cmd

    def test_permission_mode_solo_si_no_es_el_predeterminado(self):
        assert "--permission-mode" not in ClaudeSession().build_command(
            "hola", permission_mode="default")
        cmd = ClaudeSession().build_command("hola", permission_mode="acceptEdits")
        assert cmd[cmd.index("--permission-mode") + 1] == "acceptEdits"

    def test_el_prompt_va_como_argumento_no_por_shell(self):
        """Sin shell de por medio, un prompt con comillas o ; es solo texto."""
        peligro = 'hola"; rm -rf /; echo "'
        cmd = ClaudeSession().build_command(peligro)
        assert peligro in cmd


class TestParse:
    def test_init_fija_el_id_de_sesion_de_la_cli(self):
        s = ClaudeSession(session_id="provisional")
        events = parse(s, INIT_LINE)
        assert [e.kind for e in events] == ["init"]
        assert s.session_id == "aa5f235e-fe19-41fc-bc32-eb6524574bab"
        assert s.started is True

    def test_delta_de_texto(self):
        events = parse(ClaudeSession(), DELTA_LINE)
        assert [(e.kind, e.text) for e in events] == [("text", "Hola")]

    def test_uso_de_herramienta_con_resumen_de_la_entrada(self):
        events = parse(ClaudeSession(), TOOL_LINE)
        assert len(events) == 1
        assert events[0].kind == "tool"
        assert events[0].tool == "Bash"
        assert events[0].detail == "ls -la /tmp"

    def test_resultado_trae_tokens_coste_y_ventana_reales(self):
        s = ClaudeSession()
        events = parse(s, RESULT_LINE)
        assert events[0].kind == "result"
        u = events[0].usage
        assert u is not None
        assert u.input_tokens == 2
        assert u.output_tokens == 5
        assert u.cache_creation_tokens == 33189
        assert u.total_cost_usd == pytest.approx(0.332025)
        assert u.context_window == 1_000_000
        # 2 + 0 + 33189 + 5
        assert u.context_tokens == 33196

    def test_resultado_con_error_emite_tambien_un_evento_de_error(self):
        payload = json.loads(RESULT_LINE)
        payload["is_error"] = True
        payload["subtype"] = "error_max_turns"
        events = parse(ClaudeSession(), json.dumps(payload))
        assert [e.kind for e in events] == ["result", "error"]
        assert events[1].text == "error_max_turns"

    def test_lineas_desconocidas_se_ignoran(self):
        s = ClaudeSession()
        assert parse(s, '{"type": "rate_limit_event"}') == []
        assert parse(s, '{"type": "system", "subtype": "hook_started"}') == []
        assert parse(s, "{}") == []

    def test_bloque_sin_forma_esperada_no_revienta(self):
        payload = '{"type": "assistant", "message": {"content": ["x", null]}}'
        assert parse(ClaudeSession(), payload) == []


class TestReset:
    def test_reset_da_una_sesion_nueva_sin_memoria(self):
        s = ClaudeSession(session_id="viejo", started=True)
        s.usage = Usage(output_tokens=999)
        s.reset()
        assert s.session_id != "viejo"
        assert s.started is False
        assert s.usage.output_tokens == 0
        assert "--session-id" in s.build_command("hola")

    def test_adopt_continua_una_sesion_existente(self):
        s = ClaudeSession()
        s.adopt("sesion-guardada")
        assert s.started is True
        assert "--resume" in s.build_command("sigue")


class TestPestanasIndependientes:
    """Cada pestaña es una conversación aparte, con su IA y su hilo."""

    def test_dos_sesiones_no_comparten_hilo(self):
        a, b = ClaudeSession(), ClaudeSession()
        assert a.session_id != b.session_id

    def test_cada_una_puede_usar_un_proveedor_distinto(self):
        a, b = ClaudeSession(), ClaudeSession()
        a.set_model_ref("claude/opus")
        b.set_model_ref("opencode/gpt-5.2")

        assert a.provider_key == "claude"
        assert b.provider_key == "opencode"
        assert a.build_command("hola")[0] == "claude"
        assert b.build_command("hola")[0] == "opencode"

    def test_cambiar_el_modelo_de_una_no_toca_a_la_otra(self):
        a, b = ClaudeSession(), ClaudeSession()
        a.set_model_ref("claude/opus")
        b.set_model_ref("claude/haiku")
        a.set_model_ref("opencode/grok-4")

        assert b.model_ref == "claude/haiku"
        assert b.provider_key == "claude"

    def test_cambiar_de_proveedor_abre_un_hilo_nuevo(self):
        """El id de sesión de una CLI no significa nada para otra: seguir
        usándolo pediría retomar una conversación que no existe."""
        s = ClaudeSession()
        s.adopt("sesion-de-claude")
        assert s.started is True

        s.set_model_ref("opencode/gpt-5.2")
        assert s.session_id != "sesion-de-claude"
        assert s.started is False

    def test_cambiar_de_modelo_dentro_del_mismo_proveedor_conserva_el_hilo(self):
        """Pasar de opus a haiku es la misma conversación; no hay que perderla."""
        s = ClaudeSession()
        s.set_model_ref("claude/opus")
        s.adopt("mismo-hilo")
        s.set_model_ref("claude/haiku")

        assert s.session_id == "mismo-hilo"
        assert s.started is True
        assert s.model == "haiku"

    def test_un_proveedor_sin_sesiones_no_intenta_retomar(self):
        """Ollama no guarda conversaciones: pedirle --resume sería un error."""
        s = ClaudeSession()
        s.set_model_ref("ollama/llama3.3")
        s.started = True
        cmd = s.build_command("hola")
        assert "--resume" not in cmd
        assert "--session" not in cmd

    def test_el_consumo_se_cuenta_por_separado(self):
        a, b = ClaudeSession(), ClaudeSession()
        a.usage = Usage(output_tokens=100, total_cost_usd=0.5)
        assert b.usage.output_tokens == 0
        assert b.usage.total_cost_usd == 0.0


class TestTextoAcumulado:
    def test_claude_manda_trozos_y_opencode_el_texto_entero(self):
        """Unos proveedores mandan el delta y otros el acumulado; sin
        distinguirlos, la respuesta saldría duplicada."""
        claude = ClaudeSession()
        eventos = parse(claude, DELTA_LINE)
        assert eventos[0].replaces_text is False

        oc = ClaudeSession()
        oc.set_model_ref("opencode/gpt-5.2")
        linea = json.dumps({
            "type": "message.part.updated",
            "properties": {"part": {"type": "text", "text": "Hola"}},
        })
        eventos = parse(oc, linea)
        assert eventos[0].replaces_text is True
