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


class TestCarpetasYArchivos:
    def test_crear_carpeta_con_sus_padres(self, tmp_path):
        r = sysctl.make_dir("uno/dos/tres", str(tmp_path))
        assert r.ok
        assert (tmp_path / "uno" / "dos" / "tres").is_dir()

    def test_crear_una_carpeta_que_ya_existe_no_es_un_fallo(self, tmp_path):
        sysctl.make_dir("repetida", str(tmp_path))
        r = sysctl.make_dir("repetida", str(tmp_path))
        assert r.ok
        assert "ya existía" in r.reason

    def test_no_crea_una_carpeta_donde_hay_un_archivo(self, tmp_path):
        (tmp_path / "choque").write_text("x")
        assert not sysctl.make_dir("choque", str(tmp_path))

    def test_ruta_absoluta(self, tmp_path):
        destino = tmp_path / "absoluta"
        assert sysctl.make_dir(str(destino), "/otro/sitio").ok
        assert destino.is_dir()

    def test_crear_archivo(self, tmp_path):
        r = sysctl.write_file("notas/hola.txt", "contenido", str(tmp_path))
        assert r.ok
        assert (tmp_path / "notas" / "hola.txt").read_text() == "contenido"

    def test_no_pisa_un_archivo_existente(self, tmp_path):
        """Sobrescribir en silencio es la clase de error que no se deshace."""
        (tmp_path / "importante.txt").write_text("no me borres")
        r = sysctl.write_file("importante.txt", "nuevo", str(tmp_path))
        assert not r.ok
        assert (tmp_path / "importante.txt").read_text() == "no me borres"

    def test_ruta_vacia(self, tmp_path):
        assert not sysctl.make_dir("", str(tmp_path))
        assert not sysctl.write_file("   ", "x", str(tmp_path))


class TestBusquedaDeArchivos:
    def test_encuentra_por_parte_del_nombre(self, tmp_path):
        (tmp_path / "receta-pasta.txt").write_text("x")
        (tmp_path / "otro.md").write_text("x")
        salida = sysctl.find_files("receta", str(tmp_path)).output
        assert "receta-pasta.txt" in salida
        assert "otro.md" not in salida

    def test_devuelve_rutas_absolutas(self, tmp_path):
        """El usuario pide la ruta para usarla, así que tiene que ser completa."""
        (tmp_path / "buscado.txt").write_text("x")
        salida = sysctl.find_files("buscado", str(tmp_path)).output
        assert salida.startswith("/")
        assert str(tmp_path) in salida

    def test_acepta_comodines(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.txt").write_text("x")
        salida = sysctl.find_files("*.py", str(tmp_path)).output
        assert "a.py" in salida and "b.txt" not in salida

    def test_busca_en_subcarpetas(self, tmp_path):
        hondo = tmp_path / "uno" / "dos"
        hondo.mkdir(parents=True)
        (hondo / "escondido.txt").write_text("x")
        assert "escondido.txt" in sysctl.find_files("escondido", str(tmp_path)).output

    def test_salta_las_carpetas_de_ruido(self, tmp_path):
        """node_modules y .git harían la búsqueda eterna e inútil."""
        ruido = tmp_path / "node_modules" / "paquete"
        ruido.mkdir(parents=True)
        (ruido / "objetivo.txt").write_text("x")
        (tmp_path / "objetivo.txt").write_text("x")
        rutas = sysctl.find_files("objetivo", str(tmp_path)).output.splitlines()
        assert len(rutas) == 1
        assert "node_modules" not in rutas[0]

    def test_respeta_el_tope(self, tmp_path):
        for i in range(30):
            (tmp_path / f"m{i}.txt").write_text("x")
        assert len(sysctl.find_files("m", str(tmp_path), limit=5).output.splitlines()) == 5

    def test_patron_vacio(self, tmp_path):
        assert not sysctl.find_files("", str(tmp_path))

    def test_carpeta_que_no_existe(self):
        assert not sysctl.find_files("x", "/no/existe/en/absoluto")


class TestBusquedaDeTexto:
    def test_encuentra_con_ruta_y_linea(self, tmp_path):
        (tmp_path / "notas.txt").write_text("primera\nbuscame aquí\ntercera\n")
        salida = sysctl.search_text("buscame", str(tmp_path)).output
        assert "notas.txt" in salida
        assert "buscame" in salida

    def test_sin_coincidencias_no_es_un_fallo(self, tmp_path):
        (tmp_path / "a.txt").write_text("nada")
        r = sysctl.search_text("noexiste", str(tmp_path))
        assert r.ok
        assert r.output == ""

    def test_texto_vacio(self, tmp_path):
        assert not sysctl.search_text("", str(tmp_path))


class TestMusicaYWeb:
    def test_accion_desconocida(self):
        assert not sysctl.music("bailar")

    def test_fuera_de_macos_no_revienta(self, monkeypatch):
        monkeypatch.setattr(sysctl, "IS_MACOS", False)
        assert sysctl.music("play").reason.endswith("|macos-only")
        assert sysctl.running_music_app() == ""
        assert not sysctl.system_info()

    def test_la_busqueda_web_codifica_la_consulta(self, monkeypatch):
        """Un espacio o un acento sin codificar rompen la URL."""
        abiertas = []
        monkeypatch.setattr(sysctl, "open_url",
                            lambda url, browser="": (abiertas.append(url),
                                                     sysctl.SysResult(True))[1])
        sysctl.web_search("pizza en málaga")
        assert "pizza+en+m%C3%A1laga" in abiertas[0]

    def test_cada_motor_tiene_su_hueco_para_la_consulta(self):
        for plantilla in sysctl.SEARCH_ENGINES.values():
            assert "{q}" in plantilla

    def test_consulta_vacia(self):
        assert not sysctl.web_search("")
