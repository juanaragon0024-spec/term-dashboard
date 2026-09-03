from __future__ import annotations

import os
import stat

from term import keys as keystore


def test_guardar_y_leer():
    assert keystore.set_key("openrouter", "sk-or-secreta")
    assert keystore.get_key("openrouter") == "sk-or-secreta"


def test_el_archivo_solo_lo_puede_leer_su_dueno():
    """Una API key filtrada se gasta el dinero de otro."""
    keystore.set_key("openai", "sk-test")
    modo = stat.S_IMODE(os.stat(keystore.KEYS_PATH).st_mode)
    assert modo == 0o600


def test_el_entorno_gana_al_archivo(monkeypatch):
    keystore.set_key("openai", "la-del-archivo")
    monkeypatch.setenv("OPENAI_API_KEY", "la-del-entorno")
    assert keystore.get_key("openai") == "la-del-entorno"


def test_gemini_acepta_las_dos_variables_habituales(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "desde-google")
    assert keystore.get_key("gemini") == "desde-google"


def test_sin_clave_devuelve_cadena_vacia():
    assert keystore.get_key("no-configurado") == ""


def test_borrar():
    keystore.set_key("grok", "x")
    assert keystore.delete_key("grok") is True
    assert keystore.get_key("grok") == ""
    assert keystore.delete_key("grok") is False


def test_archivo_corrupto_no_impide_arrancar():
    keystore.KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    keystore.KEYS_PATH.write_text("no soy json")
    assert keystore.load_keys() == {}


def test_la_mascara_no_deja_ver_la_clave():
    enmascarada = keystore.mask("sk-or-v1-1234567890abcdef")
    assert "1234567890abc" not in enmascarada
    assert enmascarada.startswith("sk-or-")
    assert keystore.mask("") == "(sin clave)"


def test_se_recortan_los_espacios():
    keystore.set_key("deepseek", "  con-espacios  ")
    assert keystore.get_key("deepseek") == "con-espacios"
