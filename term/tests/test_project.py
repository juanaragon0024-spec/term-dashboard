"""Tests del contexto de proyecto: instrucciones, mapa y archivos elegidos."""

from __future__ import annotations

import subprocess

from term.project import FileContext, build_repo_map, project_summary, read_agent_docs


class TestInstruccionesDelRepo:
    def test_lee_agents_md(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# Reglas\n\nComentarios en español.")
        docs = read_agent_docs(str(tmp_path))
        assert "Comentarios en español" in docs

    def test_lee_varios_nombres_conocidos(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("de agents")
        (tmp_path / "CLAUDE.md").write_text("de claude")
        docs = read_agent_docs(str(tmp_path))
        assert "de agents" in docs and "de claude" in docs

    def test_sube_hasta_la_raiz_del_repositorio(self, tmp_path):
        """El AGENTS.md vive arriba y se suele trabajar en un subdirectorio."""
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        (tmp_path / "AGENTS.md").write_text("regla de la raíz")
        hondo = tmp_path / "src" / "modulo"
        hondo.mkdir(parents=True)
        assert "regla de la raíz" in read_agent_docs(str(hondo))

    def test_sin_instrucciones_devuelve_vacio(self, tmp_path):
        assert read_agent_docs(str(tmp_path)) == ""

    def test_un_documento_enorme_se_recorta(self, tmp_path):
        """Un AGENTS.md sin tope se comería el contexto de la conversación."""
        (tmp_path / "AGENTS.md").write_text("x" * 50_000)
        docs = read_agent_docs(str(tmp_path))
        assert len(docs) < 15_000
        assert "recortado" in docs


class TestMapaDelProyecto:
    def test_agrupa_por_carpeta(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "uno.py").write_text("x")
        (tmp_path / "src" / "dos.py").write_text("x")
        mapa = build_repo_map(str(tmp_path))
        assert "src/" in mapa
        assert "uno.py" in mapa and "dos.py" in mapa

    def test_se_salta_el_ruido(self, tmp_path):
        ruido = tmp_path / "node_modules" / "paquete"
        ruido.mkdir(parents=True)
        (ruido / "index.js").write_text("x")
        (tmp_path / "mio.py").write_text("x")
        mapa = build_repo_map(str(tmp_path))
        assert "mio.py" in mapa
        assert "node_modules" not in mapa

    def test_respeta_el_gitignore(self, tmp_path):
        """git ls-files ya sabe qué está ignorado; no hay que reimplementarlo."""
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        (tmp_path / ".gitignore").write_text("secreto.py\n")
        (tmp_path / "publico.py").write_text("x")
        (tmp_path / "secreto.py").write_text("x")
        subprocess.run(["git", "-C", str(tmp_path), "add", "-A"],
                       capture_output=True, check=True)
        mapa = build_repo_map(str(tmp_path))
        assert "publico.py" in mapa
        assert "secreto.py" not in mapa

    def test_carpeta_que_no_existe(self):
        assert build_repo_map("/no/existe/nada") == ""


class TestContextoDeArchivos:
    def test_anadir_y_listar(self, tmp_path):
        (tmp_path / "uno.py").write_text("contenido")
        ctx = FileContext()
        ok, _ = ctx.add("uno.py", str(tmp_path))
        assert ok
        assert ctx.summary() == "uno.py"
        assert "contenido" in ctx.render()

    def test_no_se_anade_dos_veces(self, tmp_path):
        (tmp_path / "uno.py").write_text("x")
        ctx = FileContext()
        ctx.add("uno.py", str(tmp_path))
        ok, motivo = ctx.add("uno.py", str(tmp_path))
        assert not ok and "ya estaba" in motivo
        assert len(ctx.paths) == 1

    def test_un_archivo_que_no_existe(self, tmp_path):
        ok, motivo = FileContext().add("fantasma.py", str(tmp_path))
        assert not ok and "no existe" in motivo

    def test_se_relee_en_cada_turno(self, tmp_path):
        """Si se cacheara, el modelo trabajaría sobre una copia vieja."""
        archivo = tmp_path / "vivo.py"
        archivo.write_text("primera versión")
        ctx = FileContext()
        ctx.add("vivo.py", str(tmp_path))
        assert "primera versión" in ctx.render()

        archivo.write_text("segunda versión")
        assert "segunda versión" in ctx.render()

    def test_un_archivo_borrado_se_cae_solo(self, tmp_path):
        archivo = tmp_path / "efimero.py"
        archivo.write_text("x")
        ctx = FileContext()
        ctx.add("efimero.py", str(tmp_path))
        archivo.unlink()
        ctx.render()
        assert ctx.paths == []

    def test_quitar_por_nombre_o_por_ruta(self, tmp_path):
        (tmp_path / "uno.py").write_text("x")
        ctx = FileContext()
        _, ruta = ctx.add("uno.py", str(tmp_path))
        assert ctx.drop("uno.py")[0]
        ctx.add("uno.py", str(tmp_path))
        assert ctx.drop(ruta)[0]
        assert ctx.paths == []

    def test_vaciar(self, tmp_path):
        for nombre in ("a.py", "b.py"):
            (tmp_path / nombre).write_text("x")
            FileContext()
        ctx = FileContext()
        ctx.add("a.py", str(tmp_path))
        ctx.add("b.py", str(tmp_path))
        assert ctx.clear() == 2
        assert ctx.render() == ""


def test_resumen_junta_instrucciones_y_mapa(tmp_path):
    (tmp_path / "AGENTS.md").write_text("usa pytest")
    (tmp_path / "codigo.py").write_text("x")
    resumen = project_summary(str(tmp_path))
    assert "usa pytest" in resumen
    assert "codigo.py" in resumen
