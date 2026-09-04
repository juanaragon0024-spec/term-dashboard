"""Tests de la integración con git, sobre repositorios de verdad."""

from __future__ import annotations

import subprocess

import pytest

from term import vcs


@pytest.fixture
def repo(tmp_path):
    """Un repositorio con un commit inicial."""
    ruta = str(tmp_path)
    subprocess.run(["git", "init", "-q", ruta], check=True)
    for clave, valor in (("user.email", "t@t"), ("user.name", "T")):
        subprocess.run(["git", "-C", ruta, "config", clave, valor], check=True)
    (tmp_path / "a.py").write_text("uno\n")
    subprocess.run(["git", "-C", ruta, "add", "-A"], capture_output=True, check=True)
    subprocess.run(["git", "-C", ruta, "commit", "-qm", "inicial"],
                   capture_output=True, check=True)
    return tmp_path


class TestFueraDeRepo:
    def test_todo_avisa_en_vez_de_reventar(self, tmp_path):
        for funcion in (vcs.status, vcs.diff, vcs.undo, vcs.log):
            resultado = funcion(str(tmp_path))
            assert not resultado
            assert "repositorio" in resultado.reason

    def test_is_repo(self, tmp_path, repo):
        assert vcs.is_repo(str(repo))
        assert not vcs.is_repo(str(tmp_path.parent / "no-existe"))


class TestStatus:
    def test_sin_cambios(self, repo):
        salida = vcs.status(str(repo)).output
        assert "main" in salida or "master" in salida
        assert "sin cambios" in salida

    def test_distingue_modificado_preparado_y_sin_seguir(self, repo):
        """Las dos columnas de porcelain se confundían y salía «M a.py»."""
        (repo / "a.py").write_text("dos\n")
        (repo / "nuevo.py").write_text("x\n")
        (repo / "preparado.py").write_text("y\n")
        subprocess.run(["git", "-C", str(repo), "add", "preparado.py"],
                       capture_output=True, check=True)

        salida = vcs.status(str(repo)).output
        assert "modificado   a.py" in salida
        assert "sin seguir   nuevo.py" in salida
        # El + marca lo que ya está preparado para el commit.
        assert "+ añadido      preparado.py" in salida


class TestDiff:
    def test_sin_cambios(self, repo):
        assert vcs.diff(str(repo)).output == "(no hay cambios)"

    def test_muestra_el_cambio(self, repo):
        (repo / "a.py").write_text("uno\ndos\n")
        salida = vcs.diff(str(repo)).output
        assert "a.py" in salida and "+dos" in salida

    def test_un_diff_enorme_se_recorta(self, repo):
        """Un diff de miles de líneas no se lee y tarda en pintarse."""
        (repo / "a.py").write_text("línea\n" * 20_000)
        salida = vcs.diff(str(repo)).output
        assert len(salida) < vcs._MAX_DIFF + 200
        assert "recortado" in salida


class TestCommit:
    def test_guarda_los_cambios(self, repo):
        (repo / "a.py").write_text("dos\n")
        resultado = vcs.commit(str(repo), "cambio de prueba")
        assert resultado
        assert "cambio de prueba" in resultado.output
        assert "sin cambios" in vcs.status(str(repo)).output

    def test_sin_mensaje_no_commitea(self, repo):
        (repo / "a.py").write_text("dos\n")
        assert not vcs.commit(str(repo), "   ")
        assert "modificado" in vcs.status(str(repo)).output

    def test_sin_cambios_no_crea_un_commit_vacio(self, repo):
        resultado = vcs.commit(str(repo), "nada que ver")
        assert not resultado
        assert "nada que guardar" in resultado.reason


class TestUndo:
    def test_deshace_conservando_el_trabajo(self, repo):
        """Deshacer no debería poder costarte una tarde: reset --soft, no --hard."""
        (repo / "a.py").write_text("dos\n")
        vcs.commit(str(repo), "el que se deshace")

        resultado = vcs.undo(str(repo))
        assert resultado
        assert "el que se deshace" in resultado.output
        # El contenido sigue ahí, solo que sin confirmar.
        assert (repo / "a.py").read_text() == "dos\n"
        assert "a.py" in vcs.status(str(repo)).output

    def test_no_deshace_el_commit_inicial(self, repo):
        resultado = vcs.undo(str(repo))
        assert not resultado
        assert "primer commit" in resultado.reason


def test_log(repo):
    salida = vcs.log(str(repo), 5).output
    assert "inicial" in salida


class TestPrepararArchivos:
    def test_lista_los_cambios_troceados(self, repo):
        (repo / "a.py").write_text("dos\n")
        (repo / "nuevo.py").write_text("x\n")
        cambios = {c.path: c for c in vcs.changed_files(str(repo))}
        assert cambios["a.py"].label == "modificado"
        assert cambios["nuevo.py"].untracked
        assert not cambios["a.py"].staged

    def test_preparar_y_soltar_un_archivo(self, repo):
        (repo / "a.py").write_text("dos\n")
        assert vcs.stage(str(repo), "a.py")
        assert vcs.changed_files(str(repo))[0].staged

        assert vcs.unstage(str(repo), "a.py")
        assert not vcs.changed_files(str(repo))[0].staged

    def test_preparar_todo(self, repo):
        (repo / "a.py").write_text("dos\n")
        (repo / "b.py").write_text("x\n")
        vcs.stage(str(repo))
        assert all(c.staged for c in vcs.changed_files(str(repo)))

    def test_diff_de_un_solo_archivo(self, repo):
        (repo / "a.py").write_text("dos\n")
        (repo / "otro.py").write_text("no me mires\n")
        salida = vcs.diff_file(str(repo), "a.py").output
        assert "+dos" in salida
        assert "no me mires" not in salida

    def test_un_archivo_sin_seguir_enseña_su_contenido(self, repo):
        """No tiene diff todavía, pero se quiere ver qué lleva dentro."""
        (repo / "nuevo.py").write_text("contenido nuevo\n")
        assert "contenido nuevo" in vcs.diff_file(str(repo), "nuevo.py").output

    def test_descartar_exige_una_ruta(self, repo):
        """Un «descarta todo» a un teclazo es una tarde perdida esperando."""
        (repo / "a.py").write_text("dos\n")
        assert not vcs.discard(str(repo), "")
        assert (repo / "a.py").read_text() == "dos\n"

    def test_descartar_un_archivo(self, repo):
        (repo / "a.py").write_text("dos\n")
        assert vcs.discard(str(repo), "a.py")
        assert (repo / "a.py").read_text() == "uno\n"

    def test_un_renombrado_se_lista_por_su_nombre_nuevo(self, repo):
        import subprocess
        subprocess.run(["git", "-C", str(repo), "mv", "a.py", "renombrado.py"],
                       capture_output=True, check=True)
        rutas = [c.path for c in vcs.changed_files(str(repo))]
        assert "renombrado.py" in rutas
