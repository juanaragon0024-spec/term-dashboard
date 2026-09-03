from __future__ import annotations

from term.commands import (
    COMMAND_NAMES,
    COMMANDS_HELP,
    build_system_context,
    complete_command,
)


def test_no_hay_comandos_duplicados():
    assert len(COMMAND_NAMES) == len(set(COMMAND_NAMES))


def test_todos_los_comandos_empiezan_por_barra():
    assert all(name.startswith("/") for name in COMMAND_NAMES)


def test_todos_los_comandos_estan_descritos():
    assert all(desc.strip() for desc in COMMANDS_HELP.values())


class TestCompletar:
    def test_una_sola_opcion_se_completa_y_deja_un_espacio(self):
        completado, matches = complete_command("/vol")
        assert completado == "/volume "
        assert matches == ["/volume"]

    def test_varias_opciones_avanzan_hasta_el_prefijo_comun(self):
        completado, matches = complete_command("/se")
        assert len(matches) > 1
        assert all(m.startswith(completado) for m in matches)

    def test_sin_coincidencias_no_toca_el_texto(self):
        assert complete_command("/zzz") == ("/zzz", [])

    def test_texto_normal_no_se_completa(self):
        assert complete_command("hola") == ("hola", [])

    def test_comando_ya_completo_se_respeta(self):
        completado, _ = complete_command("/help")
        assert completado.strip() == "/help"


class TestPromptDeSistema:
    def test_incluye_el_idioma_pedido(self):
        assert "Japanese" in build_system_context("ja")
        assert "(ja)" in build_system_context("ja")

    def test_fuera_de_macos_no_sugiere_osascript(self):
        """Sugerir AppleScript en Linux solo produce comandos que fallan."""
        assert "osascript" not in build_system_context("es", macos=False)
        assert "osascript" in build_system_context("es", macos=True)

    def test_un_idioma_desconocido_cae_en_el_predeterminado(self):
        assert build_system_context("xx")
