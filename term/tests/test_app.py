"""Tests de la TUI con el harness headless de Textual.

Comprueban sobre todo los fallos que tenia la version anterior: paneles que no
se podian cerrar, /clear que no reiniciaba la sesion y ajustes que se perdian
al salir.
"""

from __future__ import annotations

import pytest

from term.app import AssistantMessage, ChatTab, TermApp, UserMessage
from term.config import load_config


@pytest.fixture
async def app(tmp_path):
    """App arrancada con los permisos ya concedidos, para saltar el dialogo."""
    from term import config

    config.save_config({**config.DEFAULTS, "permissions_granted": True,
                        "workdir": str(tmp_path)})
    application = TermApp(workdir=str(tmp_path))
    async with application.run_test() as pilot:
        await pilot.pause()
        yield application, pilot


class TestArranque:
    async def test_arranca_con_una_pestana(self, app):
        application, _ = app
        assert len(application._tabs) == 1
        assert application._active_tab_id() is not None

    async def test_el_dialogo_de_permisos_sale_la_primera_vez(self, tmp_path):
        from term import config
        config.save_config({**config.DEFAULTS, "permissions_granted": False})
        application = TermApp(workdir=str(tmp_path))
        async with application.run_test() as pilot:
            await pilot.pause(0.3)
            assert application._awaiting == "permissions"

    async def test_denegar_permisos_queda_registrado(self, tmp_path):
        """Denegar tiene consecuencias: la CLI se lanza en modo restringido."""
        from term import config
        config.save_config({**config.DEFAULTS, "permissions_granted": False})
        application = TermApp(workdir=str(tmp_path))
        async with application.run_test() as pilot:
            await pilot.pause(0.3)
            await application._handle_dialog("n", application._first_tab_id())
            assert application._permissions_granted is False
            chat = application._active_chat()
            cmd = chat.session.build_command(
                "hola", restricted=not application._permissions_granted)
            assert "--restricted" in cmd


class TestPaneles:
    @pytest.mark.parametrize("panel", ["help", "apps", "tools", "settings"])
    async def test_cada_panel_abre_y_cierra(self, app, panel):
        """Antes /help abria una pestana que ctrl+w no sabia cerrar."""
        application, pilot = app
        await application._show_panel(panel)
        await pilot.pause()
        assert application._active_panel_name() == panel

        await application.action_close_active()
        await pilot.pause()
        assert application._active_panel_name() is None
        assert application._active_tab_id() is not None

    async def test_escape_tambien_cierra_el_panel(self, app):
        application, pilot = app
        await application._show_panel("help")
        await pilot.pause()
        await application.action_cancel()
        await pilot.pause()
        assert application._active_panel_name() is None

    async def test_abrir_el_mismo_panel_dos_veces_no_duplica_pestanas(self, app):
        application, pilot = app
        await application._show_panel("help")
        await application._show_panel("help")
        await pilot.pause()
        panes = application.query("#pane-help")
        assert len(panes) == 1


class TestPestanas:
    async def test_nueva_y_cerrar(self, app):
        application, pilot = app
        await application.action_new_tab()
        await pilot.pause()
        assert len(application._tabs) == 2

        await application.action_close_active()
        await pilot.pause()
        assert len(application._tabs) == 1

    async def test_la_ultima_pestana_no_se_cierra(self, app):
        application, pilot = app
        await application.action_close_active()
        await pilot.pause()
        assert len(application._tabs) == 1

    async def test_saltar_a_una_pestana_por_numero(self, app):
        application, pilot = app
        await application.action_new_tab()
        await pilot.pause()
        primera = next(iter(application._tabs))
        application.action_goto_tab(1)
        await pilot.pause()
        assert application._active_tab_id() == primera

    async def test_un_numero_fuera_de_rango_no_hace_nada(self, app):
        application, pilot = app
        antes = application._active_tab_id()
        application.action_goto_tab(9)
        await pilot.pause()
        assert application._active_tab_id() == antes

    async def test_cerrar_una_pestana_mata_su_proceso(self, app):
        application, pilot = app
        await application.action_new_tab()
        await pilot.pause()
        chat = application._active_chat()

        matado = []

        class ProcFalso:
            def kill(self):
                matado.append(True)

        chat.session.proc = ProcFalso()
        await application.action_close_active()
        await pilot.pause()
        assert matado == [True]


class TestLimpiar:
    async def test_clear_reinicia_tambien_la_sesion(self, app):
        """Limpiar la pantalla sin reiniciar la sesion dejaba a Claude
        recordando una conversacion que el usuario ya no veia."""
        application, pilot = app
        chat = application._active_chat()
        sesion_previa = chat.session.session_id
        chat.session.started = True
        chat.message_count = 4
        chat.last_response = "algo"

        await application._clear_tab()
        await pilot.pause()

        assert chat.session.session_id != sesion_previa
        assert chat.session.started is False
        assert chat.message_count == 0
        assert chat.last_response == ""

    async def test_clear_deja_de_nuevo_el_estado_vacio(self, app):
        application, pilot = app
        chat = application._active_chat()
        await application._clear_tab()
        await pilot.pause()
        assert application.query(f"#empty-{chat.tab_id}")

    async def test_clear_descarta_los_adjuntos_pendientes(self, app):
        application, pilot = app
        chat = application._active_chat()
        chat.attachments.append(("/tmp/x", "contenido"))
        await application._clear_tab()
        await pilot.pause()
        assert chat.attachments == []


class TestPersistencia:
    async def test_cambiar_de_tema_se_guarda_solo(self, app):
        """Antes habia que acordarse de /save o se perdia al salir."""
        application, pilot = app
        application.theme_key = "dracula"
        await pilot.pause()
        assert load_config()["theme"] == "dracula"

    async def test_cambiar_de_esfuerzo_se_guarda_solo(self, app):
        application, pilot = app
        application.action_cycle_effort()
        await pilot.pause()
        assert load_config()["effort"] == application.effort

    async def test_el_panel_de_archivos_recuerda_si_estaba_abierto(self, app):
        application, pilot = app
        application.action_toggle_files()
        await pilot.pause()
        assert load_config()["show_file_panel"] is application._show_files

    async def test_cambiar_de_directorio_se_guarda(self, app, tmp_path):
        application, pilot = app
        destino = tmp_path / "sub"
        destino.mkdir()
        application._set_workdir(str(destino))
        await pilot.pause()
        assert load_config()["workdir"] == str(destino)

    async def test_un_directorio_inexistente_no_se_aplica(self, app):
        application, pilot = app
        antes = application.workdir
        application._set_workdir("/no/existe/de/verdad")
        await pilot.pause()
        assert application.workdir == antes


class TestEntrada:
    async def test_el_historial_recorre_los_mensajes_enviados(self, app):
        application, pilot = app
        chat = application._active_chat()
        chat.history = ["primero", "segundo"]
        chat.history_pos = 2
        inp = application.query_one(f"#input-{chat.tab_id}")

        from term.app import ChatInput
        application.on_chat_input_history_move(
            ChatInput.HistoryMove(-1, chat.tab_id))
        await pilot.pause()
        assert inp.text == "segundo"

        application.on_chat_input_history_move(
            ChatInput.HistoryMove(-1, chat.tab_id))
        await pilot.pause()
        assert inp.text == "primero"

        # No se pasa del principio.
        application.on_chat_input_history_move(
            ChatInput.HistoryMove(-1, chat.tab_id))
        await pilot.pause()
        assert inp.text == "primero"

    async def test_tab_autocompleta_el_comando(self, app):
        application, pilot = app
        chat = application._active_chat()
        inp = application.query_one(f"#input-{chat.tab_id}")
        inp.text = "/vol"

        from term.app import ChatInput
        application.on_chat_input_complete_requested(
            ChatInput.CompleteRequested(chat.tab_id))
        await pilot.pause()
        assert inp.text.strip() == "/volume"

    async def test_las_sugerencias_aparecen_al_escribir_una_barra(self, app):
        application, pilot = app
        chat = application._active_chat()
        application._show_suggestions(chat.tab_id, "/th")
        await pilot.pause()
        sug = application.query_one(f"#cmdsug-{chat.tab_id}")
        assert sug.has_class("visible")

    async def test_las_sugerencias_desaparecen_con_texto_normal(self, app):
        application, pilot = app
        chat = application._active_chat()
        application._show_suggestions(chat.tab_id, "/th")
        application._show_suggestions(chat.tab_id, "hola qué tal")
        await pilot.pause()
        assert not application.query_one(f"#cmdsug-{chat.tab_id}").has_class("visible")


class TestComandos:
    async def test_comando_desconocido_avisa(self, app):
        application, pilot = app
        await application._handle_command("/noexiste", application._active_tab_id())
        await pilot.pause()  # basta con que no reviente

    async def test_theme_cambia_el_tema(self, app):
        application, pilot = app
        await application._handle_command("/theme gruvbox", application._active_tab_id())
        await pilot.pause()
        assert application.theme_key == "gruvbox"

    async def test_theme_invalido_no_cambia_nada(self, app):
        application, pilot = app
        antes = application.theme_key
        await application._handle_command("/theme inventado", application._active_tab_id())
        await pilot.pause()
        assert application.theme_key == antes

    async def test_model_acepta_un_identificador_literal(self, app):
        application, pilot = app
        await application._handle_command(
            "/model claude-opus-4-5-20251101", application._active_tab_id())
        await pilot.pause()
        assert application.current_model == "claude-opus-4-5-20251101"

    async def test_lang_cambia_el_idioma_y_lo_guarda(self, app):
        application, pilot = app
        await application._handle_command("/lang ja", application._active_tab_id())
        await pilot.pause()
        assert application._lang == "ja"
        assert load_config()["lang"] == "ja"

    async def test_permissions_solo_acepta_modos_validos(self, app):
        application, _ = app
        await application._handle_command("/permissions acceptEdits",
                                          application._active_tab_id())
        assert application._permission_mode == "acceptEdits"
        await application._handle_command("/permissions inventado",
                                          application._active_tab_id())
        assert application._permission_mode == "acceptEdits"

    async def test_attach_registra_el_fichero(self, app, tmp_path):
        application, pilot = app
        fichero = tmp_path / "notas.txt"
        fichero.write_text("contenido de prueba")
        await application._handle_command(f"/attach {fichero}",
                                          application._active_tab_id())
        await pilot.pause()
        chat = application._active_chat()
        assert len(chat.attachments) == 1
        assert "contenido de prueba" in chat.attachments[0][1]

    async def test_attach_de_un_fichero_que_no_existe(self, app):
        application, pilot = app
        await application._handle_command("/attach /no/existe.txt",
                                          application._active_tab_id())
        await pilot.pause()
        assert application._active_chat().attachments == []

    async def test_detach_vacia_los_adjuntos(self, app, tmp_path):
        application, pilot = app
        fichero = tmp_path / "a.txt"
        fichero.write_text("x")
        tab = application._active_tab_id()
        await application._handle_command(f"/attach {fichero}", tab)
        await application._handle_command("/detach", tab)
        await pilot.pause()
        assert application._active_chat().attachments == []

    async def test_run_no_ejecuta_nada_sin_permisos(self, app, tmp_path):
        """El dialogo de permisos tiene que significar algo de verdad."""
        application, pilot = app
        application._permissions_granted = False
        marca = tmp_path / "no-deberia-existir.txt"
        await application._handle_command(
            f"/run touch {marca}", application._active_tab_id())
        await pilot.pause()
        assert not marca.exists()

    async def test_run_ejecuta_con_permisos(self, app, tmp_path):
        application, pilot = app
        application._permissions_granted = True
        application.workdir = str(tmp_path)
        marca = tmp_path / "creado.txt"
        await application._handle_command(
            f"/run touch {marca}", application._active_tab_id())
        await pilot.pause()
        assert marca.exists()

    async def test_search_sin_texto_no_revienta(self, app):
        application, pilot = app
        await application._handle_command("/search", application._active_tab_id())
        await pilot.pause()

    async def test_search_encuentra_en_los_mensajes(self, app):
        application, pilot = app
        tab = application._active_tab_id()
        area = await application._msgs(tab)
        await area.mount(UserMessage("hablemos de tortugas marinas"))
        await pilot.pause()
        await application._handle_command("/search tortugas", tab)
        await pilot.pause()
        assert application.query(".search-hit")

    async def test_export_escribe_el_fichero(self, app):
        application, pilot = app
        from term.config import EXPORT_DIR
        tab = application._active_tab_id()
        area = await application._msgs(tab)
        await area.mount(UserMessage("hola"))
        await pilot.pause()
        await application._handle_command("/export", tab)
        await pilot.pause()
        assert list(EXPORT_DIR.glob("chat_*.md"))

    async def test_sessions_sin_ninguna_guardada(self, app):
        application, pilot = app
        await application._handle_command("/sessions", application._active_tab_id())
        await pilot.pause()

    async def test_resume_recupera_una_sesion_guardada(self, app):
        application, pilot = app
        application._store.touch("sesion-guardada", title="Vieja", messages=7)
        await application._handle_command("/resume 1", application._active_tab_id())
        await pilot.pause()
        chat = application._active_chat()
        assert chat.session.session_id == "sesion-guardada"
        assert chat.session.started is True  # el siguiente turno usara --resume

    async def test_resume_con_un_numero_que_no_existe(self, app):
        application, pilot = app
        antes = len(application._tabs)
        await application._handle_command("/resume 99", application._active_tab_id())
        await pilot.pause()
        assert len(application._tabs) == antes


class TestRespuesta:
    async def test_el_markdown_solo_se_repinta_a_intervalos(self, app):
        """Repintar en cada delta obliga a reparsear todo el texto una y otra vez."""
        application, pilot = app
        area = await application._msgs(application._active_tab_id())
        mensaje = AssistantMessage()
        await area.mount(mensaje)
        await pilot.pause()

        repintados = []
        original = mensaje._md.update

        async def contar(text):
            repintados.append(text)
            return await original(text)

        mensaje._md.update = contar
        for _ in range(50):
            await mensaje.append("x")
        assert len(repintados) < 50

        await mensaje.flush()
        assert mensaje.text == "x" * 50

    async def test_extrae_los_bloques_de_codigo(self, app):
        mensaje = AssistantMessage()
        mensaje.text = "Mira:\n```python\nprint(1)\n```\ny otro\n```\nls\n```\n"
        assert mensaje.code_blocks() == ["print(1)", "ls"]

    async def test_sin_bloques_de_codigo(self, app):
        mensaje = AssistantMessage()
        mensaje.text = "solo texto"
        assert mensaje.code_blocks() == []


class TestPestanaDeChat:
    def test_cada_pestana_tiene_su_propia_sesion(self):
        """Sesiones compartidas mezclarian dos conversaciones distintas."""
        a = ChatTab("default", "chat1", "neon", "/tmp")
        b = ChatTab("default", "chat2", "neon", "/tmp")
        assert a.session.session_id != b.session.session_id
