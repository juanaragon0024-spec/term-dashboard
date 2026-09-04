"""Tests del nivel de permisos.

Existen por un caso concreto: pedir «pon la siguiente canción» respondía que
hacía falta aprobación para osascript. Conceder permisos en Term no se traducía
en permisos para la CLI, que seguía preguntando y en modo -p no puede.
"""

from __future__ import annotations

import pytest

from term.permissions import DEFAULT_LEVEL, LEVELS, get_level, level_names
from term.session import ChatSession
from term.tools import TOOLS


class TestCatalogo:
    def test_tres_niveles_con_nombre_y_explicación(self):
        assert level_names() == ["lectura", "normal", "todo"]
        for nivel in LEVELS.values():
            assert nivel.name and nivel.summary and nivel.detail

    def test_el_recomendado_existe(self):
        assert DEFAULT_LEVEL in LEVELS

    def test_van_de_menos_a_más_permisivo(self):
        lectura, normal = get_level("lectura"), get_level("normal")
        assert set(lectura.cli_tools) < set(normal.cli_tools)
        assert lectura.own_tools < normal.own_tools

    def test_las_herramientas_propias_existen(self):
        for nivel in LEVELS.values():
            assert nivel.own_tools <= set(TOOLS), nivel.key

    def test_los_nombres_viejos_siguen_valiendo(self):
        """Una configuración anterior no debe dejar a la IA sin poder nada."""
        assert get_level("segura").key == "normal"
        assert get_level("bypassPermissions").key == "todo"
        assert get_level("nada").key == "lectura"
        assert get_level("").key == DEFAULT_LEVEL
        assert get_level("inventado").key == DEFAULT_LEVEL


class TestLoQuePermiteCadaNivel:
    def test_solo_lectura_no_toca_el_sistema(self):
        lectura = get_level("lectura")
        assert lectura.system is False
        assert "Bash(osascript:*)" not in lectura.cli_tools
        assert "Write" not in lectura.cli_tools
        assert "ejecutar_shell" not in lectura.own_tools

    def test_normal_permite_la_música_sin_preguntar(self):
        """El caso que lo motivó todo: pasar de canción."""
        normal = get_level("normal")
        assert "Bash(osascript:*)" in normal.cli_tools
        assert "controlar_musica" in normal.own_tools
        assert normal.system is True

    def test_normal_permite_trabajar_en_un_proyecto(self):
        normal = get_level("normal")
        for patron in ("Write", "Edit", "Bash(git:*)", "Bash(npm:*)",
                       "Bash(python3:*)", "Bash(pytest:*)"):
            assert patron in normal.cli_tools, patron

    def test_todo_no_pone_lista_sino_que_desactiva_la_comprobación(self):
        todo = get_level("todo")
        assert todo.cli_mode == "bypassPermissions"
        assert todo.own_tools == frozenset()   # vacío = sin restricción


class TestTraduccionALaCli:
    def test_el_nivel_llega_como_allowedTools(self):
        """Sin esto la CLI se paraba a preguntar y el turno moría."""
        sesion = ChatSession()
        cmd = sesion.build_command("hola", cli_tools=get_level("normal").cli_tools)
        assert "--allowedTools" in cmd
        assert "Bash(osascript:*)" in cmd

    def test_solo_lectura_no_deja_pasar_osascript(self):
        sesion = ChatSession()
        cmd = sesion.build_command("hola", cli_tools=get_level("lectura").cli_tools)
        assert "Bash(osascript:*)" not in cmd
        assert "Read" in cmd

    def test_el_nivel_todo_usa_el_modo_de_la_cli(self):
        sesion = ChatSession()
        todo = get_level("todo")
        cmd = sesion.build_command("hola", cli_tools=todo.cli_tools,
                                   permission_mode=todo.cli_mode)
        assert cmd[cmd.index("--permission-mode") + 1] == "bypassPermissions"

    def test_sin_patrones_no_se_pasa_el_flag(self):
        cmd = ChatSession().build_command("hola")
        assert "--allowedTools" not in cmd

    @pytest.mark.parametrize("clave", ["lectura", "normal", "todo"])
    def test_ningún_nivel_revienta_al_construir_el_comando(self, clave):
        nivel = get_level(clave)
        cmd = ChatSession().build_command(
            "hola", cli_tools=nivel.cli_tools, permission_mode=nivel.cli_mode)
        assert cmd[0] == "claude"
