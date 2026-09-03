from __future__ import annotations

import term.syscontrol as sysctl


class TestFalloElegante:
    def test_fuera_de_macos_no_lanza_excepcion(self, monkeypatch):
        """En Linux estas llamadas devolvian FileNotFoundError sin control."""
        monkeypatch.setattr(sysctl, "IS_MACOS", False)
        for result in (
            sysctl.open_app("Safari"),
            sysctl.open_url("https://example.com"),
            sysctl.set_volume(50),
            sysctl.spotify("playpause"),
        ):
            assert result.ok is False
            assert result.reason.endswith("|macos-only")

    def test_fuera_de_macos_no_detecta_navegadores(self, monkeypatch):
        monkeypatch.setattr(sysctl, "IS_MACOS", False)
        assert sysctl.detect_browsers() == []

    def test_accion_de_spotify_desconocida(self):
        result = sysctl.spotify("bailar")
        assert result.ok is False
        assert "bailar" in result.reason


class TestResultado:
    def test_es_falsy_cuando_falla(self):
        assert not sysctl.SysResult(False, reason="x")
        assert sysctl.SysResult(True)


class TestShell:
    def test_captura_la_salida(self, tmp_path):
        result = sysctl.run_shell("echo hola", str(tmp_path))
        assert result.ok
        assert result.output == "hola"

    def test_se_ejecuta_en_el_directorio_indicado(self, tmp_path):
        (tmp_path / "marca.txt").write_text("x")
        result = sysctl.run_shell("ls", str(tmp_path))
        assert "marca.txt" in result.output

    def test_la_salida_enorme_se_recorta(self, tmp_path):
        """Sin tope, un cat de un fichero grande congela la TUI al pintarlo."""
        result = sysctl.run_shell("yes hola | head -20000", str(tmp_path))
        assert len(result.output) <= sysctl._MAX_OUTPUT + 100
        assert "truncado" in result.output

    def test_el_timeout_se_informa_como_motivo(self, tmp_path):
        result = sysctl.run_shell("sleep 5", str(tmp_path), timeout=1)
        assert result.ok is False
        assert result.reason == "timeout"

    def test_un_comando_que_falla_devuelve_su_stderr(self, tmp_path):
        result = sysctl.run_shell("ls /no/existe/nada", str(tmp_path))
        assert result.ok
        assert result.output


class TestGit:
    def test_dentro_de_un_repo_da_la_rama(self):
        import pathlib
        raiz = str(pathlib.Path(__file__).resolve().parents[2])
        assert sysctl.git_branch(raiz)

    def test_fuera_de_un_repo_devuelve_vacio(self, tmp_path):
        assert sysctl.git_branch(str(tmp_path)) == ""


class TestDeteccion:
    def test_las_apps_detectadas_estan_de_verdad_en_el_path(self):
        import shutil
        for app in sysctl.detect_cli_apps():
            assert shutil.which(app["cmd"])

    def test_los_alias_de_navegador_apuntan_a_nombres_de_app(self):
        for alias, app in sysctl.BROWSER_ALIASES.items():
            assert alias.islower()
            assert app[0].isupper()
