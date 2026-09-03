from __future__ import annotations

import time

from term.store import SessionStore


def test_touch_crea_y_luego_actualiza(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    store.touch("id-1", title="Primera", messages=2)
    assert len(store.records) == 1

    store.touch("id-1", messages=5)
    assert len(store.records) == 1
    assert store.records[0].messages == 5
    assert store.records[0].title == "Primera"  # no se pierde al no repetirlo


def test_la_mas_reciente_queda_arriba(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    store.touch("id-1", title="A")
    store.touch("id-2", title="B")
    store.touch("id-1", messages=1)
    assert [r.session_id for r in store.records] == ["id-1", "id-2"]


def test_get_es_uno_indexado_como_lo_ve_el_usuario(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    store.touch("id-1", title="A")
    assert store.get(1).session_id == "id-1"
    assert store.get(0) is None
    assert store.get(99) is None


def test_persiste_entre_instancias(tmp_path):
    path = tmp_path / "s.json"
    SessionStore(path).touch("id-1", title="Persistida", messages=3)
    recargado = SessionStore(path)
    assert recargado.records[0].title == "Persistida"
    assert recargado.records[0].messages == 3


def test_fichero_corrupto_no_revienta(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("no soy json")
    assert SessionStore(path).records == []


def test_registros_invalidos_se_saltan(tmp_path):
    path = tmp_path / "s.json"
    path.write_text('[{"session_id": "ok"}, {"sin_id": 1}, "texto suelto"]')
    store = SessionStore(path)
    assert [r.session_id for r in store.records] == ["ok"]


def test_tope_de_registros(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    for i in range(60):
        store.touch(f"id-{i}")
    assert len(store.records) <= 50


def test_etiqueta_de_antiguedad(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    record = store.touch("id-1")
    assert record.age_label == "ahora"
    record.updated = time.time() - 7200
    assert record.age_label == "hace 2 h"


def test_remove(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    store.touch("id-1")
    assert store.remove("id-1") is True
    assert store.remove("id-1") is False
