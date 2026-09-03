"""Tests de las herramientas que Term ejecuta por su cuenta."""

from __future__ import annotations

import pytest

from term.tools import (
    TOOLS,
    ToolContext,
    available_tools,
    execute,
    schemas_anthropic,
    schemas_gemini,
    schemas_openai,
)


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(workdir=str(tmp_path))


class TestCatalogo:
    def test_toda_herramienta_esta_descrita_y_tiene_implementacion(self):
        for nombre, tool in TOOLS.items():
            assert tool.name == nombre
            assert tool.description.strip()
            assert tool.handler is not None

    def test_los_parametros_obligatorios_estan_declarados(self):
        for tool in TOOLS.values():
            for obligatorio in tool.required:
                assert obligatorio in tool.params

    def test_sin_permisos_no_se_ofrecen_las_del_sistema(self):
        """Ofrecer una herramienta y luego negarla confunde al modelo."""
        con = available_tools(ToolContext(allow_system=True))
        sin = available_tools(ToolContext(allow_system=False))
        assert len(sin) < len(con)
        assert not any(t.system for t in sin)


class TestEjecucion:
    def test_crear_carpeta(self, ctx, tmp_path):
        ok, salida = execute("crear_carpeta", {"path": "uno/dos"}, ctx)
        assert ok
        assert (tmp_path / "uno" / "dos").is_dir()
        assert str(tmp_path) in salida

    def test_crear_y_leer_archivo(self, ctx):
        ok, _ = execute("crear_archivo",
                        {"path": "nota.txt", "content": "hola mundo"}, ctx)
        assert ok
        ok, contenido = execute("leer_archivo", {"path": "nota.txt"}, ctx)
        assert ok and contenido == "hola mundo"

    def test_leer_algo_que_no_existe(self, ctx):
        ok, salida = execute("leer_archivo", {"path": "fantasma.txt"}, ctx)
        assert not ok and "no existe" in salida

    def test_listar_carpeta(self, ctx, tmp_path):
        (tmp_path / "archivo.txt").write_text("x")
        (tmp_path / "carpeta").mkdir()
        ok, salida = execute("listar_carpeta", {}, ctx)
        assert ok
        assert "d carpeta" in salida
        assert "- archivo.txt" in salida

    def test_buscar_archivos_devuelve_rutas(self, ctx, tmp_path):
        (tmp_path / "objetivo.md").write_text("x")
        ok, salida = execute("buscar_archivos", {"pattern": "objetivo"}, ctx)
        assert ok and str(tmp_path) in salida

    def test_buscar_texto(self, ctx, tmp_path):
        (tmp_path / "doc.txt").write_text("una aguja en el pajar\n")
        ok, salida = execute("buscar_texto", {"text": "aguja"}, ctx)
        assert ok and "doc.txt" in salida

    def test_herramienta_inexistente(self, ctx):
        ok, salida = execute("volar", {}, ctx)
        assert not ok and "volar" in salida

    def test_falta_un_parametro_obligatorio(self, ctx):
        ok, salida = execute("crear_carpeta", {}, ctx)
        assert not ok and "path" in salida

    def test_se_descartan_los_parametros_inventados(self, ctx, tmp_path):
        """Un modelo puede añadir campos de su cosecha; pasarlos reventaría."""
        ok, _ = execute("crear_carpeta",
                        {"path": "buena", "modo": "0777", "raro": 1}, ctx)
        assert ok
        assert (tmp_path / "buena").is_dir()

    def test_sin_permisos_la_del_sistema_se_niega(self, tmp_path):
        ctx = ToolContext(workdir=str(tmp_path), allow_system=False)
        ok, salida = execute("ejecutar_shell", {"command": "touch colado.txt"}, ctx)
        assert not ok
        assert "permisos" in salida
        assert not (tmp_path / "colado.txt").exists()

    def test_con_permisos_el_shell_funciona(self, ctx, tmp_path):
        ok, _ = execute("ejecutar_shell", {"command": "touch hecho.txt"}, ctx)
        assert ok and (tmp_path / "hecho.txt").exists()

    def test_una_herramienta_que_falla_no_tumba_el_turno(self, ctx, monkeypatch):
        import term.tools as tk

        def explota(*a, **k):
            raise RuntimeError("boom")

        monkeypatch.setattr(tk.TOOLS["info_sistema"], "handler", explota)
        ok, salida = execute("info_sistema", {}, ctx)
        assert not ok and "boom" in salida

    def test_el_resultado_enorme_se_recorta(self, ctx, tmp_path):
        """Un resultado sin tope se come el contexto de la conversación."""
        (tmp_path / "grande.txt").write_text("x" * 50_000)
        ok, salida = execute("leer_archivo", {"path": "grande.txt"}, ctx)
        assert ok and len(salida) < 10_000 and "recortado" in salida


class TestEsquemas:
    def test_openai(self, ctx):
        esquemas = schemas_openai(ctx)
        assert all(e["type"] == "function" for e in esquemas)
        assert all(e["function"]["name"] in TOOLS for e in esquemas)

    def test_anthropic(self, ctx):
        for esquema in schemas_anthropic(ctx):
            assert esquema["name"] in TOOLS
            assert esquema["input_schema"]["type"] == "object"

    def test_gemini_agrupa_en_una_sola_declaracion(self, ctx):
        esquemas = schemas_gemini(ctx)
        assert len(esquemas) == 1
        assert len(esquemas[0]["function_declarations"]) == len(available_tools(ctx))

    def test_los_tres_formatos_exponen_las_mismas_herramientas(self, ctx):
        openai = {e["function"]["name"] for e in schemas_openai(ctx)}
        anthropic = {e["name"] for e in schemas_anthropic(ctx)}
        gemini = {f["name"] for f in schemas_gemini(ctx)[0]["function_declarations"]}
        assert openai == anthropic == gemini
