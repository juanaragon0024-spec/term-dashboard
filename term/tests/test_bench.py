"""Tests del banco de pruebas.

Un banco cuyas comprobaciones no detectan un acierto no mide nada, así que
aquí se resuelven las tareas a mano y se comprueba que las da por buenas.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench"
sys.path.insert(0, str(BENCH))

from tasks import TASKS, by_name, by_tag  # noqa: E402


def montar(task, tmp_path: Path) -> Path:
    for ruta, contenido in task.setup.items():
        destino = tmp_path / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")
    return tmp_path


class TestCatalogo:
    def test_los_nombres_no_se_repiten(self):
        nombres = [t.name for t in TASKS]
        assert len(nombres) == len(set(nombres))

    def test_toda_tarea_está_etiquetada_por_dificultad(self):
        for task in TASKS:
            assert {"facil", "medio", "dificil"} & set(task.tags), task.name

    def test_toda_tarea_pide_algo_concreto(self):
        for task in TASKS:
            assert len(task.prompt) > 30, task.name
            assert task.max_turns >= 4, task.name

    def test_búsqueda_por_nombre_y_etiqueta(self):
        assert by_name("crear-carpeta") is not None
        assert by_name("no-existe") is None
        assert by_tag("facil")


class TestSinResolver:
    """Al empezar, ninguna tarea debe darse por buena."""

    @pytest.mark.parametrize("task", TASKS, ids=lambda t: t.name)
    def test_parte_de_un_estado_sin_resolver(self, task, tmp_path):
        raiz = montar(task, tmp_path)
        ok, _ = task.check(raiz)
        assert not ok, f"{task.name} se da por buena sin hacer nada"


class TestResueltas:
    """Y resueltas a mano, todas deben darse por buenas.

    Es la mitad que suele faltar: una comprobación que siempre dice «mal»
    parece estricta y en realidad no mide nada.
    """

    def test_crear_carpeta(self, tmp_path):
        task = by_name("crear-carpeta")
        raiz = montar(task, tmp_path)
        (raiz / "notas").mkdir()
        (raiz / "notas" / "README.md").write_text("Aquí van las notas.\n")
        assert task.check(raiz)[0]

    def test_renombrar(self, tmp_path):
        task = by_name("renombrar")
        raiz = montar(task, tmp_path)
        (raiz / "viejo.txt").rename(raiz / "nuevo.txt")
        assert task.check(raiz)[0]

    def test_renombrar_no_vale_perdiendo_el_contenido(self, tmp_path):
        task = by_name("renombrar")
        raiz = montar(task, tmp_path)
        (raiz / "viejo.txt").unlink()
        (raiz / "nuevo.txt").write_text("otra cosa\n")
        assert not task.check(raiz)[0]

    def test_buscar_archivo(self, tmp_path):
        task = by_name("buscar-archivo")
        raiz = montar(task, tmp_path)
        (raiz / "RESPUESTA.txt").write_text("config/ajustes.json\n")
        assert task.check(raiz)[0]

    def test_buscar_archivo_con_ruta_equivocada(self, tmp_path):
        task = by_name("buscar-archivo")
        raiz = montar(task, tmp_path)
        (raiz / "RESPUESTA.txt").write_text("src/main.py\n")
        assert not task.check(raiz)[0]

    def test_contar_archivos(self, tmp_path):
        task = by_name("contar-archivos")
        raiz = montar(task, tmp_path)
        (raiz / "RESPUESTA.txt").write_text("3\n")
        assert task.check(raiz)[0]

    def test_arreglar_bug(self, tmp_path):
        task = by_name("arreglar-bug")
        raiz = montar(task, tmp_path)
        (raiz / "calculadora.py").write_text(
            "def media(numeros):\n"
            "    if not numeros:\n"
            "        return 0\n"
            "    return sum(numeros) / len(numeros)\n")
        assert task.check(raiz)[0]

    def test_arreglar_bug_sin_arreglar(self, tmp_path):
        task = by_name("arreglar-bug")
        raiz = montar(task, tmp_path)
        assert not task.check(raiz)[0]

    def test_arreglar_test(self, tmp_path):
        task = by_name("arreglar-test")
        raiz = montar(task, tmp_path)
        (raiz / "saludo.py").write_text(
            "def saludar(nombre):\n    return f'¡Hola, {nombre}!'\n")
        assert task.check(raiz)[0]

    def test_funcion_nueva(self, tmp_path):
        task = by_name("funcion-nueva")
        raiz = montar(task, tmp_path)
        (raiz / "utilidades.py").write_text(
            "import unicodedata\n\n"
            "def es_palindromo(texto):\n"
            "    limpio = ''.join(\n"
            "        c for c in unicodedata.normalize('NFD', texto.lower())\n"
            "        if c.isalnum())\n"
            "    return limpio == limpio[::-1]\n")
        assert task.check(raiz)[0]

    def test_refactor(self, tmp_path):
        task = by_name("refactor")
        raiz = montar(task, tmp_path)
        (raiz / "informe.py").write_text(
            "import logging\n\n"
            "def generar(datos):\n"
            "    logging.info('empezando el informe')\n"
            "    total = sum(datos)\n"
            "    logging.info('total: %s', total)\n"
            "    return total\n")
        assert task.check(raiz)[0]

    def test_refactor_no_vale_rompiendo_el_modulo(self, tmp_path):
        task = by_name("refactor")
        raiz = montar(task, tmp_path)
        (raiz / "informe.py").write_text(
            "import logging\ndef generar(datos)\n    pass\n")   # sintaxis rota
        assert not task.check(raiz)[0]

    def test_respetar_convenciones(self, tmp_path):
        task = by_name("respetar-convenciones")
        raiz = montar(task, tmp_path)
        (raiz / "saludos.py").write_text(
            'def saludar(nombre):\n'
            '    """Devuelve un saludo para el nombre indicado."""\n'
            "    return f'Hola, {nombre}'\n")
        assert task.check(raiz)[0]

    def test_respetar_convenciones_sin_docstring(self, tmp_path):
        """Escribir la función pero saltarse el AGENTS.md no cuenta."""
        task = by_name("respetar-convenciones")
        raiz = montar(task, tmp_path)
        (raiz / "saludos.py").write_text(
            "def saludar(nombre):\n    return f'Hola, {nombre}'\n")
        assert not task.check(raiz)[0]
