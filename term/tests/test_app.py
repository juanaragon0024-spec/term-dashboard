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
        assert application.current_model == "claude/claude-opus-4-5-20251101"

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


class TestDisposicion:
    """Los fallos de layout que trajo compactar la interfaz."""

    async def test_la_barra_de_estado_no_se_solapa_con_el_pie(self, app):
        """Con las dos barras a una línea, ambas peleaban por la última fila
        y la de estado quedaba invisible bajo el pie."""
        from textual.widgets import Footer

        application, _ = app
        estado = application.query_one("#status-bar")
        pie = application.query_one(Footer)
        assert estado.region.y != pie.region.y
        assert estado.region.y < pie.region.y

    async def test_la_barra_superior_tiene_alto_util(self, app):
        """Con height 1, el borde inferior se comía la única línea y dejaba
        la barra con cero filas de contenido."""
        application, _ = app
        assert application.query_one("#top-bar").size.height >= 1

    async def test_una_respuesta_corta_no_dibuja_un_marco_enorme(self, app):
        """Un Vertical se estira a todo el alto disponible: sin height auto,
        una línea de respuesta ocupaba media pantalla."""
        application, pilot = app
        area = await application._msgs(application._active_tab_id())
        mensaje = AssistantMessage()
        await area.mount(mensaje)
        await pilot.pause()
        await mensaje.append("una línea")
        await mensaje.flush()
        await pilot.pause()
        assert mensaje.region.height <= 6

    async def test_el_globo_del_usuario_se_ajusta_al_texto(self, app):
        """Un 'Gracias' no debería ocupar el ancho entero de la terminal."""
        application, pilot = app
        area = await application._msgs(application._active_tab_id())
        corto = UserMessage("Hola")
        largo = UserMessage("Hola, " + "texto de relleno " * 6)
        await area.mount(corto)
        await area.mount(largo)
        await pilot.pause()
        assert corto.region.width < largo.region.width


class TestPestanasConIaPropia:
    """Cada pestaña usa la IA que quiera sin alterar a las demás."""

    async def test_cambiar_el_modelo_solo_afecta_a_la_pestana_activa(self, app):
        application, pilot = app
        primera = application._active_chat()
        await application.action_new_tab()
        await pilot.pause()
        segunda = application._active_chat()
        assert primera is not segunda

        await application._handle_command("/model claude/haiku", segunda.tab_id)
        await pilot.pause()

        assert segunda.model_ref == "claude/haiku"
        assert primera.model_ref != "claude/haiku"

    async def test_una_pestana_puede_usar_otro_proveedor(self, app):
        application, pilot = app
        await application.action_new_tab()
        await pilot.pause()
        chat = application._active_chat()

        # Solo se puede cambiar a un proveedor instalado; si opencode no está
        # en esta máquina, el comando avisa en lugar de dejar la pestaña rota.
        from term.providers import get_provider

        if not get_provider("opencode").available():
            pytest.skip("opencode no está instalado")

        await application._handle_command("/model opencode/gpt-5.2", chat.tab_id)
        await pilot.pause()
        assert chat.session.provider_key == "opencode"
        assert chat.session.build_command("hola")[0] == "opencode"

    async def test_no_deja_elegir_un_proveedor_que_no_esta_instalado(self, app):
        application, pilot = app
        chat = application._active_chat()
        antes = chat.model_ref
        # ollama no está instalado en el entorno de pruebas.
        from term.providers import get_provider

        if get_provider("ollama").available():
            pytest.skip("ollama sí está instalado aquí")

        await application._handle_command("/model ollama/llama3.3", chat.tab_id)
        await pilot.pause()
        assert chat.model_ref == antes

    async def test_las_pestanas_nuevas_heredan_la_ultima_eleccion(self, app):
        application, pilot = app
        await application._handle_command(
            "/model claude/sonnet", application._active_tab_id())
        await pilot.pause()
        await application.action_new_tab()
        await pilot.pause()
        assert application._active_chat().model_ref == "claude/sonnet"

    async def test_new_con_modelo_explicito(self, app):
        application, pilot = app
        await application._handle_command(
            "/new Pruebas claude/haiku", application._active_tab_id())
        await pilot.pause()
        chat = application._active_chat()
        assert chat.model_ref == "claude/haiku"
        assert chat.title == "Pruebas"

    async def test_cada_pestana_lleva_su_propio_hilo(self, app):
        application, pilot = app
        primera = application._active_chat()
        await application.action_new_tab()
        await pilot.pause()
        segunda = application._active_chat()
        assert primera.session.session_id != segunda.session.session_id


class TestAyuda:
    async def test_los_corchetes_de_un_comando_sobreviven_al_marcado(self, app):
        """Rich trata [nombre] como una etiqueta de estilo: sin escaparlo, el
        usuario ve «/new» a secas y no sabe que admite argumentos."""
        application, _ = app
        ayuda = application._panel_help()
        assert "/new" in ayuda
        assert r"\[nombre]" in ayuda or "[nombre]" not in ayuda.replace(r"\[", "")

    async def test_lo_que_se_pinta_conserva_los_argumentos(self, app):
        from rich.console import Console

        application, _ = app
        consola = Console(file=__import__("io").StringIO(), width=200)
        consola.print(application._panel_help())
        pintado = consola.file.getvalue()
        assert "[nombre]" in pintado
        assert "[0-100]" in pintado

    async def test_la_ayuda_lista_todos_los_comandos(self, app):
        from term.commands import COMMANDS_HELP

        application, _ = app
        ayuda = application._panel_help()
        for cmd in COMMANDS_HELP:
            assert cmd.split()[0] in ayuda

    async def test_la_ayuda_explica_las_dos_formas_de_conectar(self, app):
        application, _ = app
        ayuda = application._panel_help()
        assert application._t("help_connect_cli") in ayuda
        assert application._t("help_connect_api") in ayuda
        # Y nombra los proveedores concretos.
        assert "Claude Code" in ayuda
        assert "OpenRouter" in ayuda

    async def test_la_ayuda_marca_lo_que_esta_listo(self, app):
        """Un punto verde en lo instalado y hueco en lo que falta."""
        application, _ = app
        ayuda = application._panel_help()
        assert "•" in ayuda and "◦" in ayuda

    async def test_la_ayuda_esta_en_el_idioma_activo(self, app):
        application, _ = app
        application._lang = "en"
        ayuda = application._panel_help()
        assert "Conversation" in ayuda
        application._lang = "es"
        assert "Conversación" in application._panel_help()

    async def test_las_sugerencias_escapan_los_corchetes(self, app):
        application, pilot = app
        chat = application._active_chat()
        application._show_suggestions(chat.tab_id, "/new")
        await pilot.pause()
        # Basta con que no reviente al pintar un comando con corchetes.
        assert application.query_one(f"#cmdsug-{chat.tab_id}").has_class("visible")


class TestProyectoYGit:
    async def test_el_prompt_lleva_las_instrucciones_del_repo(self, app, tmp_path):
        """Un AGENTS.md que nadie lee es un AGENTS.md que no sirve."""
        application, pilot = app
        (tmp_path / "AGENTS.md").write_text("Escribe los comentarios en español.")
        application._set_workdir(str(tmp_path))
        await pilot.pause()
        prompt = application._system_prompt(application._active_chat())
        assert "comentarios en español" in prompt.lower()

    async def test_el_prompt_lleva_el_mapa_del_proyecto(self, app, tmp_path):
        application, pilot = app
        (tmp_path / "modulo.py").write_text("x")
        application._set_workdir(str(tmp_path))
        await pilot.pause()
        assert "modulo.py" in application._system_prompt(application._active_chat())

    async def test_add_mete_el_archivo_en_el_prompt(self, app, tmp_path):
        application, pilot = app
        (tmp_path / "clave.py").write_text("SECRETO_DEL_TEST = 1")
        application._set_workdir(str(tmp_path))
        await application._handle_command("/add clave.py",
                                          application._active_tab_id())
        await pilot.pause()
        prompt = application._system_prompt(application._active_chat())
        assert "SECRETO_DEL_TEST" in prompt

    async def test_drop_lo_saca(self, app, tmp_path):
        application, pilot = app
        (tmp_path / "clave.py").write_text("SECRETO_DEL_TEST = 1")
        application._set_workdir(str(tmp_path))
        tab = application._active_tab_id()
        await application._handle_command("/add clave.py", tab)
        await application._handle_command("/drop clave.py", tab)
        await pilot.pause()
        assert "SECRETO_DEL_TEST" not in application._system_prompt(
            application._active_chat())

    async def test_el_contexto_es_de_cada_pestana(self, app, tmp_path):
        application, pilot = app
        (tmp_path / "solo-aqui.py").write_text("x")
        application._set_workdir(str(tmp_path))
        primera = application._active_tab_id()
        await application._handle_command("/add solo-aqui.py", primera)
        await application.action_new_tab()
        await pilot.pause()
        assert application._active_chat().context.paths == []

    async def test_git_fuera_de_un_repo_avisa(self, app, tmp_path):
        application, pilot = app
        application._set_workdir(str(tmp_path))
        await application._handle_command("/status", application._active_tab_id())
        await pilot.pause()  # basta con que no reviente

    async def test_allow_cambia_el_perfil_y_se_guarda(self, app):
        application, pilot = app
        await application._handle_command("/allow lectura",
                                          application._active_tab_id())
        await pilot.pause()
        assert application._tool_profile == "lectura"
        assert load_config()["tool_profile"] == "lectura"

    async def test_allow_rechaza_un_perfil_inventado(self, app):
        application, pilot = app
        antes = application._tool_profile
        await application._handle_command("/allow loquesea",
                                          application._active_tab_id())
        await pilot.pause()
        assert application._tool_profile == antes

    async def test_los_perfiles_nombran_herramientas_que_existen(self, app):
        from term.app import PERMISSION_PROFILES
        from term.tools import TOOLS

        for nombre, permitidas in PERMISSION_PROFILES.items():
            if permitidas is None:
                continue
            assert permitidas <= set(TOOLS), f"perfil {nombre} nombra algo que no existe"


class TestArquitectoYEsqueleto:
    async def test_architect_exige_un_proveedor_disponible(self, app):
        application, pilot = app
        chat = application._active_chat()
        await application._handle_command("/architect ollama/llama3.3", chat.tab_id)
        await pilot.pause()
        from term.providers import get_provider

        if not get_provider("ollama").available():
            assert chat.architect == ""

    async def test_architect_se_activa_y_se_apaga(self, app):
        application, pilot = app
        chat = application._active_chat()
        await application._handle_command("/architect claude/opus", chat.tab_id)
        await pilot.pause()
        assert chat.architect == "claude/opus"

        await application._handle_command("/architect off", chat.tab_id)
        await pilot.pause()
        assert chat.architect == ""

    async def test_el_arquitecto_es_de_cada_pestana(self, app):
        application, pilot = app
        primera = application._active_chat()
        await application._handle_command("/architect claude/opus", primera.tab_id)
        await application.action_new_tab()
        await pilot.pause()
        assert application._active_chat().architect == ""

    async def test_el_arquitecto_no_ejecuta_nada(self, app, monkeypatch):
        """Planifica, no toca: si pudiera actuar, el trabajo se haría dos veces."""
        application, _ = app
        chat = application._active_chat()
        chat.architect = "claude/opus"
        recibidos = {}

        async def falso_run(self, prompt, **kwargs):
            recibidos.update(kwargs)
            return
            yield  # pragma: no cover

        monkeypatch.setattr("term.session.ChatSession.run", falso_run)
        await application._plan_with_architect(chat, "haz algo")
        assert recibidos["restricted"] is True
        assert recibidos["allowed_tools"] == frozenset()

    async def test_si_el_arquitecto_falla_el_turno_sigue(self, app, monkeypatch):
        """Quedarse sin respuesta sería peor que quedarse sin plan."""
        application, _ = app
        chat = application._active_chat()
        chat.architect = "claude/opus"

        async def revienta(self, prompt, **kwargs):
            raise RuntimeError("sin red")
            yield  # pragma: no cover

        monkeypatch.setattr("term.session.ChatSession.run", revienta)
        assert await application._plan_with_architect(chat, "x") == ""

    async def test_skeleton_alterna_y_se_guarda(self, app):
        application, pilot = app
        antes = application._skeleton
        await application._handle_command("/skeleton", application._active_tab_id())
        await pilot.pause()
        assert application._skeleton is not antes
        assert load_config()["code_skeleton"] is application._skeleton

    async def test_con_skeleton_el_prompt_lleva_firmas(self, app, tmp_path):
        application, pilot = app
        (tmp_path / "m.py").write_text("def firma_reconocible(x: int) -> str: ...\n")
        application._set_workdir(str(tmp_path))
        application._skeleton = True
        await pilot.pause()
        prompt = application._system_prompt(application._active_chat())
        assert "def firma_reconocible(x: int) -> str" in prompt

    async def test_sin_skeleton_solo_va_la_lista(self, app, tmp_path):
        application, pilot = app
        (tmp_path / "m.py").write_text("def firma_reconocible(x: int) -> str: ...\n")
        application._set_workdir(str(tmp_path))
        application._skeleton = False
        await pilot.pause()
        prompt = application._system_prompt(application._active_chat())
        assert "m.py" in prompt
        assert "firma_reconocible" not in prompt


class TestScrollDeLosPaneles:
    """El panel de ayuda no cabía en pantalla y no había forma de bajarlo."""

    @pytest.mark.parametrize("panel", ["help", "settings", "apps", "tools"])
    async def test_el_panel_no_se_estira_mas_que_la_pantalla(self, app, panel):
        """El TabPane crecía hasta el alto del texto, así que max_scroll_y era
        cero y no había nada que desplazar."""
        from textual.widgets import TabPane

        application, pilot = app
        await application._show_panel(panel)
        await pilot.pause()
        pane = application.query_one(f"#pane-{panel}", TabPane)
        assert pane.size.height <= application.size.height

    async def test_la_ayuda_se_puede_desplazar(self, app):
        from textual.containers import VerticalScroll

        application, pilot = app
        await application._show_panel("help")
        await pilot.pause()
        scroll = application.query_one("#pane-help .panel-scroll", VerticalScroll)
        assert scroll.max_scroll_y > 0

        await pilot.press("pagedown")
        await pilot.pause()
        assert scroll.scroll_y > 0

        await pilot.press("end")
        await pilot.pause()
        assert scroll.scroll_y == pytest.approx(scroll.max_scroll_y, abs=1)

    async def test_el_foco_va_al_panel_para_poder_desplazar(self, app):
        """Sin foco habría que pinchar antes de usar las flechas."""
        from textual.containers import VerticalScroll

        application, pilot = app
        await application._show_panel("help")
        await pilot.pause()
        assert isinstance(application.focused, VerticalScroll)

    @pytest.mark.parametrize("tecla", ["escape", "ctrl+w"])
    async def test_se_sigue_cerrando_con_el_foco_en_el_panel(self, app, tecla):
        from term.app import ChatInput

        application, pilot = app
        await application._show_panel("help")
        await pilot.pause()
        await pilot.press(tecla)
        await pilot.pause()
        assert application._active_panel_name() is None
        # Y el foco vuelve al chat, para poder seguir escribiendo.
        assert isinstance(application.focused, ChatInput)


class TestBuscadorDeArchivos:
    async def test_se_abre_y_filtra(self, app, tmp_path):
        from term.app import FileFinder

        application, pilot = app
        (tmp_path / "session.py").write_text("x")
        (tmp_path / "store.py").write_text("x")
        application._set_workdir(str(tmp_path))
        application.action_find_file()
        await pilot.pause()
        assert isinstance(application.screen, FileFinder)

        for tecla in "sess":
            await pilot.press(tecla)
        await pilot.pause()
        assert application.screen.resultados[0].endswith("session.py")

    async def test_al_elegir_lo_mete_en_el_contexto(self, app, tmp_path):
        application, pilot = app
        (tmp_path / "elegido.py").write_text("SEÑA = 1")
        application._set_workdir(str(tmp_path))
        application.action_find_file()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert application._active_chat().context.paths

    async def test_escape_lo_cierra_sin_tocar_nada(self, app, tmp_path):
        from term.app import FileFinder

        application, pilot = app
        (tmp_path / "a.py").write_text("x")
        application._set_workdir(str(tmp_path))
        application.action_find_file()
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(application.screen, FileFinder)
        assert application._active_chat().context.paths == []

    async def test_sin_archivos_avisa(self, app, tmp_path):
        from term.app import FileFinder

        application, pilot = app
        vacia = tmp_path / "vacia"
        vacia.mkdir()
        application._set_workdir(str(vacia))
        application.action_find_file()
        await pilot.pause()
        assert not isinstance(application.screen, FileFinder)


class TestPanelDeGit:
    async def test_fuera_de_un_repo_no_se_abre(self, app, tmp_path):
        from term.app import GitPanel

        application, pilot = app
        application._set_workdir(str(tmp_path))
        application.action_git_panel()
        await pilot.pause()
        assert not isinstance(application.screen, GitPanel)

    async def test_lista_los_cambios_y_prepara_con_espacio(self, app, tmp_path):
        import subprocess

        from term import vcs
        from term.app import GitPanel

        application, pilot = app
        # En su propia carpeta: la config de Term vive en tmp_path y saldría
        # como un cambio más del repositorio.
        repo = tmp_path / "repo"
        repo.mkdir()
        ruta = str(repo)
        subprocess.run(["git", "init", "-q", ruta], check=True)
        for clave, valor in (("user.email", "t@t"), ("user.name", "T")):
            subprocess.run(["git", "-C", ruta, "config", clave, valor], check=True)
        (repo / "a.py").write_text("uno\n")
        subprocess.run(["git", "-C", ruta, "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", ruta, "commit", "-qm", "i"], capture_output=True)
        (repo / "a.py").write_text("dos\n")

        application._set_workdir(ruta)
        application.action_git_panel()
        await pilot.pause()
        assert isinstance(application.screen, GitPanel)
        assert len(application.screen.cambios) == 1

        await pilot.press("space")
        await pilot.pause()
        assert vcs.changed_files(ruta)[0].staged

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(application.screen, GitPanel)


class TestGitHub:
    async def test_sin_gh_avisa_en_vez_de_reventar(self, app, monkeypatch):
        from term import forge

        monkeypatch.setattr(forge, "available", lambda: False)
        application, pilot = app
        for comando in ("/prs", "/issues", "/repo"):
            await application._handle_command(comando, application._active_tab_id())
            await pilot.pause()

    async def test_un_numero_que_no_es_numero(self, app):
        application, pilot = app
        await application._handle_command("/pr abc", application._active_tab_id())
        await pilot.pause()  # basta con que no reviente


class TestPanelDeArchivos:
    """El panel listaba las carpetas pero no se podía entrar en ninguna."""

    @pytest.fixture
    def con_archivos(self, tmp_path):
        (tmp_path / "proyecto" / "src").mkdir(parents=True)
        (tmp_path / "proyecto" / "src" / "main.py").write_text("x")
        (tmp_path / "archivo.txt").write_text("y")
        (tmp_path / ".oculto").write_text("z")
        return tmp_path

    async def _abrir(self, application, pilot, raiz):
        """Dejar el panel visible: no se puede pinchar lo que no se ve."""
        application._set_workdir(str(raiz))
        panel = application.query_one("#file-panel")
        if not panel.has_class("visible"):
            application.action_toggle_files()
        await pilot.pause()

    async def test_lista_carpetas_y_archivos_sin_los_ocultos(self, app, con_archivos):
        from textual.widgets import ListView

        application, pilot = app
        application._set_workdir(str(con_archivos))
        await pilot.pause()
        lista = application.query_one("#file-list", ListView)
        nombres = [c.path.name for c in lista.children]
        assert "proyecto" in nombres and "archivo.txt" in nombres
        assert ".oculto" not in nombres

    async def test_un_clic_entra_en_la_carpeta(self, app, con_archivos):
        """Leer la ruta del texto pintado lanzaba AttributeError, y un
        except lo tragaba: el clic no hacía nada."""
        from textual.widgets import ListView

        application, pilot = app
        await self._abrir(application, pilot, con_archivos)
        lista = application.query_one("#file-list", ListView)
        carpeta = next(c for c in lista.children if c.path.name == "proyecto")

        await pilot.click(carpeta)
        await pilot.pause()
        assert application.workdir == str(con_archivos / "proyecto")

    async def test_enter_también_entra(self, app, con_archivos):
        from textual.widgets import ListView

        application, pilot = app
        application._set_workdir(str(con_archivos))
        await pilot.pause()
        lista = application.query_one("#file-list", ListView)
        lista.focus()
        lista.index = next(i for i, c in enumerate(lista.children)
                           if c.path.name == "proyecto")
        await pilot.press("enter")
        await pilot.pause()
        assert application.workdir == str(con_archivos / "proyecto")

    async def test_la_primera_entrada_sube_un_nivel(self, app, con_archivos):
        from textual.widgets import ListView

        application, pilot = app
        await self._abrir(application, pilot, con_archivos / "proyecto")
        lista = application.query_one("#file-list", ListView)
        await pilot.click(lista.children[0])
        await pilot.pause()
        assert application.workdir == str(con_archivos)

    async def test_al_elegir_un_archivo_su_ruta_va_al_mensaje(self, app, con_archivos):
        from textual.widgets import ListView

        from term.app import ChatInput

        application, pilot = app
        await self._abrir(application, pilot, con_archivos)
        lista = application.query_one("#file-list", ListView)
        archivo = next(c for c in lista.children if c.path.name == "archivo.txt")

        await pilot.click(archivo)
        await pilot.pause()
        entrada = application.query_one(
            f"#input-{application._active_tab_id()}", ChatInput)
        assert "archivo.txt" in entrada.text
        # Y el directorio no cambia por pinchar un archivo.
        assert application.workdir == str(con_archivos)

    async def test_al_abrirlo_el_foco_va_a_la_lista(self, app, con_archivos):
        """Sin foco, las flechas no sirven de nada."""
        from textual.widgets import ListView

        application, pilot = app
        application._set_workdir(str(con_archivos))
        if application._show_files:
            application.action_toggle_files()
            await pilot.pause()
        application.action_toggle_files()
        await pilot.pause()
        assert application.focused is application.query_one("#file-list", ListView)

    async def test_escape_devuelve_el_foco_al_chat(self, app, con_archivos):
        from textual.widgets import ListView

        from term.app import ChatInput

        application, pilot = app
        application._set_workdir(str(con_archivos))
        await pilot.pause()
        application.query_one("#file-list", ListView).focus()
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(application.focused, ChatInput)

    async def test_las_listas_de_otros_paneles_no_navegan_el_workdir(
            self, app, con_archivos):
        """El buscador y el panel de git tienen sus propias listas; sus
        eventos burbujean hasta aquí si no se filtran."""
        from term.app import FileFinder

        application, pilot = app
        application._set_workdir(str(con_archivos))
        antes = application.workdir
        application.action_find_file()
        await pilot.pause()
        assert isinstance(application.screen, FileFinder)
        await pilot.press("escape")
        await pilot.pause()
        assert application.workdir == antes
