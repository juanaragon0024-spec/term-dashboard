"""Tests de la búsqueda difusa."""

from __future__ import annotations

from term.fuzzy import highlight, score, search

RUTAS = [
    "term/session.py", "term/tests/test_session.py", "term/store.py",
    "term/app.py", "frontend/src/App.tsx", "term/apis.py",
    "sessions/viejas/a.py", "term/styles.py", "backend/server.js",
]


class TestPuntuacion:
    def test_las_letras_tienen_que_ir_en_orden(self):
        assert score("abc", "a_b_c") is not None
        assert score("cba", "a_b_c") is None

    def test_lo_consecutivo_gana_a_lo_desperdigado(self):
        """Sin esto, `app` encontraba antes a/p/p.py que app.py."""
        juntas = score("app", "app.py")[0]
        sueltas = score("app", "a/p/p.py")[0]
        assert juntas > sueltas

    def test_el_inicio_de_palabra_puntúa(self):
        inicio = score("ts", "test_session.py")[0]
        medio = score("ts", "contest_bases.py")[0]
        assert inicio > medio

    def test_el_nombre_pesa_más_que_la_ruta(self):
        """Quien escribe «session» busca session.py, no la carpeta sessions/."""
        en_nombre = score("session", "term/session.py")[0]
        en_ruta = score("session", "sessions/viejas/a.py")[0]
        assert en_nombre > en_ruta

    def test_una_consulta_vacía_no_descarta_nada(self):
        assert score("", "lo que sea") == (0, ())

    def test_devuelve_dónde_ha_encajado(self):
        _, posiciones = score("ap", "app.py")
        assert posiciones == (0, 1)


class TestBusqueda:
    def test_encuentra_lo_que_se_busca(self):
        assert search("sesion", RUTAS)[0].text == "term/session.py"
        assert search("tesses", RUTAS)[0].text == "term/tests/test_session.py"
        assert search("srv", RUTAS)[0].text == "backend/server.js"

    def test_ordena_de_más_a_menos_parecido(self):
        puntos = [m.score for m in search("app", RUTAS)]
        assert puntos == sorted(puntos, reverse=True)

    def test_sin_coincidencias(self):
        assert search("zzzzz", RUTAS) == []

    def test_consulta_vacía_devuelve_las_primeras(self):
        assert len(search("", RUTAS, limit=3)) == 3

    def test_respeta_el_límite(self):
        assert len(search("s", RUTAS, limit=2)) == 2

    def test_no_distingue_mayúsculas(self):
        assert search("APP", RUTAS)[0].text == search("app", RUTAS)[0].text

    def test_entre_dos_iguales_gana_la_ruta_corta(self):
        corta, larga = "a/b.py", "a/muy/larga/carpeta/b.py"
        assert score("ab", corta)[0] > score("ab", larga)[0]


class TestResaltado:
    def test_marca_las_letras_que_encajan(self):
        match = search("app", ["app.py"])[0]
        resaltado = highlight(match, on="X")
        assert resaltado.startswith("[X]a[/]")

    def test_sin_posiciones_devuelve_el_texto(self):
        match = search("", ["app.py"])[0]
        assert highlight(match) == "app.py"
