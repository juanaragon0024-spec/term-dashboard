from __future__ import annotations

import json

from term import config


def test_valores_por_defecto_cuando_no_hay_fichero():
    cfg = config.load_config()
    assert cfg == config.DEFAULTS
    assert cfg is not config.DEFAULTS  # una copia, no el original


def test_ida_y_vuelta():
    cfg = config.load_config()
    cfg["theme"] = "dracula"
    cfg["lang"] = "ja"
    assert config.save_config(cfg) is True
    assert config.load_config()["theme"] == "dracula"
    assert config.load_config()["lang"] == "ja"


def test_json_corrupto_no_impide_arrancar():
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.CONFIG_PATH.write_text("{esto no es json")
    assert config.load_config() == config.DEFAULTS


def test_claves_nuevas_aparecen_con_su_valor_por_defecto():
    """Una config escrita por una version anterior no debe faltar claves."""
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.CONFIG_PATH.write_text(json.dumps({"theme": "gruvbox"}))
    cfg = config.load_config()
    assert cfg["theme"] == "gruvbox"
    assert cfg["permission_level"] == ""


def test_claves_desconocidas_se_descartan():
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.CONFIG_PATH.write_text(json.dumps({"theme": "neon", "basura": 1}))
    assert "basura" not in config.load_config()


def test_la_escritura_es_atomica():
    """Tras guardar no queda ningun .tmp suelto."""
    config.save_config(config.load_config())
    assert list(config.CONFIG_DIR.glob("*.tmp")) == []
