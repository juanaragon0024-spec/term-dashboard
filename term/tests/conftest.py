"""Cada test corre contra un ~/.config/term aislado."""

from __future__ import annotations

import importlib
import os

import pytest


@pytest.fixture(autouse=True)
def config_aislado(tmp_path, monkeypatch):
    """Evitar que los tests lean o pisen la configuracion real del usuario."""
    monkeypatch.setenv("TERM_CONFIG_DIR", str(tmp_path / "term"))
    import term.config

    importlib.reload(term.config)
    yield tmp_path
    os.environ.pop("TERM_CONFIG_DIR", None)
