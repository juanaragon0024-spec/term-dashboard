from __future__ import annotations

import re
import string

import pytest

from term.i18n import DEFAULT_LANG, LANGUAGES, TRANSLATIONS, translate


def test_todos_los_idiomas_anunciados_tienen_tabla():
    assert set(LANGUAGES) == set(TRANSLATIONS)


@pytest.mark.parametrize("code", list(LANGUAGES))
def test_ningun_idioma_pierde_claves(code):
    faltan = set(TRANSLATIONS[DEFAULT_LANG]) - set(TRANSLATIONS[code])
    assert not faltan, f"{code} no traduce: {sorted(faltan)}"


@pytest.mark.parametrize("code", [c for c in LANGUAGES if c != DEFAULT_LANG])
def test_ningun_idioma_es_espanol_copiado(code):
    """El selector de idioma prometia 10 idiomas y 6 mostraban espanol."""
    es = TRANSLATIONS[DEFAULT_LANG]
    iguales = sum(1 for k, v in es.items() if TRANSLATIONS[code].get(k) == v)
    assert iguales < len(es) * 0.5, f"{code} parece espanol sin traducir"


@pytest.mark.parametrize("code", list(LANGUAGES))
def test_los_marcadores_coinciden_con_el_original(code):
    """Una traduccion con {nombre} mal escrito romperia el formateo."""
    def marcadores(text: str) -> set[str]:
        return {
            name for _, name, _, _ in string.Formatter().parse(text) if name
        }

    for key, original in TRANSLATIONS[DEFAULT_LANG].items():
        assert marcadores(TRANSLATIONS[code][key]) == marcadores(original), (
            f"{code}/{key}"
        )


def test_reserva_a_espanol_y_luego_a_la_clave():
    assert translate("es", "clave_que_no_existe") == "clave_que_no_existe"


def test_interpolacion():
    assert "Safari" in translate("es", "opening", name="Safari")
    assert "Safari" in translate("ja", "opening", name="Safari")


def test_un_marcador_de_mas_no_revienta():
    assert translate("es", "opening") == "Abriendo {name}..."


@pytest.mark.parametrize("code", list(LANGUAGES))
def test_las_cadenas_no_llevan_marcado_rich_sin_cerrar(code):
    for key, text in TRANSLATIONS[code].items():
        abre = len(re.findall(r"\[(?!/)[a-z ]+\]", text))
        cierra = text.count("[/]")
        assert abre == cierra, f"{code}/{key}: marcado descuadrado"


def test_una_cadena_con_marcador_lang_no_choca_con_el_parametro():
    """`lang_current` lleva un {lang}: si el parametro fuese nombrado, la
    llamada reventaria con 'multiple values for argument'."""
    assert "Español" in translate("es", "lang_current", lang="Español")
    assert translate("es", "about", version="3.0.0") == "Term v3.0.0"
