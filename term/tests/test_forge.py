"""Tests de la integración con GitHub.

`gh` no está instalado en el entorno de pruebas, así que se comprueba sobre
todo que la ausencia se comunica bien y que la salida de gh se traduce como
debe.
"""

from __future__ import annotations

import json

from term import forge


class TestSinGh:
    def test_todo_avisa_de_que_falta(self, monkeypatch):
        monkeypatch.setattr(forge, "available", lambda: False)
        for resultado in (
            forge.list_prs("."), forge.list_issues("."), forge.repo_info("."),
            forge.view_pr(".", 1), forge.checkout_pr(".", 1),
        ):
            assert not resultado
            assert "gh" in resultado.reason
            assert forge.GH_HINT in resultado.reason


class TestValidacion:
    def test_una_incidencia_sin_título_no_se_crea(self):
        resultado = forge.create_issue(".", "   ")
        assert not resultado
        assert "título" in resultado.reason


class TestTraduccionDeErrores:
    """Los tropiezos habituales, dichos en cristiano."""

    def _con_error(self, monkeypatch, mensaje: str):
        import subprocess

        monkeypatch.setattr(forge, "available", lambda: True)

        class Proc:
            returncode = 1
            stdout = ""
            stderr = mensaje

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: Proc())
        return forge.list_prs(".")

    def test_sin_sesión(self, monkeypatch):
        resultado = self._con_error(monkeypatch, "not logged into any hosts")
        assert "gh auth login" in resultado.reason

    def test_fuera_de_un_repositorio(self, monkeypatch):
        resultado = self._con_error(monkeypatch, "not a git repository")
        assert "repositorio" in resultado.reason

    def test_repositorio_que_no_está_en_github(self, monkeypatch):
        resultado = self._con_error(monkeypatch, "no default remote repository")
        assert "GitHub" in resultado.reason


class TestFormato:
    def _con_salida(self, monkeypatch, datos):
        import subprocess

        monkeypatch.setattr(forge, "available", lambda: True)

        class Proc:
            returncode = 0
            stdout = json.dumps(datos)
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: Proc())

    def test_lista_de_pull_requests(self, monkeypatch):
        self._con_salida(monkeypatch, [
            {"number": 7, "title": "Arreglar el scroll",
             "author": {"login": "juan"}, "state": "OPEN",
             "isDraft": False, "headRefName": "fix/scroll"},
        ])
        salida = forge.list_prs(".").output
        assert "#7" in salida and "Arreglar el scroll" in salida
        assert "juan" in salida and "fix/scroll" in salida

    def test_un_borrador_se_marca(self, monkeypatch):
        self._con_salida(monkeypatch, [
            {"number": 8, "title": "A medias", "author": {"login": "a"},
             "state": "OPEN", "isDraft": True, "headRefName": "wip"},
        ])
        assert "borrador" in forge.list_prs(".").output

    def test_lista_vacía(self, monkeypatch):
        self._con_salida(monkeypatch, [])
        assert "No hay pull requests" in forge.list_prs(".").output

    def test_incidencias_con_etiquetas(self, monkeypatch):
        self._con_salida(monkeypatch, [
            {"number": 3, "title": "Falla en macOS", "author": {"login": "ana"},
             "state": "OPEN", "labels": [{"name": "bug"}, {"name": "macos"}]},
        ])
        salida = forge.list_issues(".").output
        assert "#3" in salida and "bug" in salida and "macos" in salida

    def test_detalle_con_comentarios(self, monkeypatch):
        self._con_salida(monkeypatch, {
            "number": 7, "title": "Arreglar el scroll", "body": "No baja.",
            "author": {"login": "juan"}, "state": "OPEN",
            "comments": [{"author": {"login": "ana"}, "body": "Confirmado"}],
            "files": [{"path": "a.py"}, {"path": "b.py"}],
        })
        salida = forge.view_pr(".", 7).output
        assert "No baja." in salida
        assert "ana" in salida and "Confirmado" in salida
        assert "2 archivos" in salida

    def test_un_json_roto_no_revienta(self, monkeypatch):
        import subprocess

        monkeypatch.setattr(forge, "available", lambda: True)

        class Proc:
            returncode = 0
            stdout = "esto no es json"
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: Proc())
        resultado = forge.list_prs(".")
        assert not resultado
        assert "JSON" in resultado.reason
