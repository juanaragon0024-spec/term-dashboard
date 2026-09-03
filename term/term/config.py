"""Configuracion persistente en ~/.config/term/.

La escritura es atomica (fichero temporal + rename) para que un cierre a mitad
de guardado no deje un config.json truncado que impida arrancar la proxima vez.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

__all__ = [
    "CONFIG_DIR",
    "CONFIG_PATH",
    "DEFAULTS",
    "EXPORT_DIR",
    "SESSIONS_PATH",
    "load_config",
    "save_config",
]

CONFIG_DIR = Path(
    os.environ.get("TERM_CONFIG_DIR") or (Path.home() / ".config" / "term")
)
CONFIG_PATH = CONFIG_DIR / "config.json"
SESSIONS_PATH = CONFIG_DIR / "sessions.json"
EXPORT_DIR = CONFIG_DIR / "exports"

DEFAULTS: dict[str, Any] = {
    "theme": "neon",
    "workdir": str(Path.home()),
    "effort": "high",
    "model": "default",
    "permissions_granted": False,
    "lang": "es",
    "default_browser": "",
    "permission_mode": "default",
    "show_file_panel": False,
}


def load_config() -> dict[str, Any]:
    """Config del disco fusionada sobre los valores por defecto.

    Una clave nueva anadida en una version posterior aparece con su valor por
    defecto en lugar de faltar, y un JSON corrupto no impide arrancar.
    """
    cfg = dict(DEFAULTS)
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    if isinstance(raw, dict):
        cfg.update({k: v for k, v in raw.items() if k in DEFAULTS})
    return cfg


def save_config(cfg: dict[str, Any]) -> bool:
    """Guardar la config. Devuelve False si el disco no lo permitio."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=CONFIG_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_PATH)
    except OSError:
        return False
    return True
