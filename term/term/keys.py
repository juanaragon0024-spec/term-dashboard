"""Credenciales de los proveedores que se conectan por API.

Las claves nunca van al config.json normal: viven en su propio archivo con
permisos 600, porque una API key filtrada se gasta el dinero de otro. Una
variable de entorno tiene preferencia sobre el archivo, para que quien ya las
tenga exportadas no tenga que volver a escribirlas.
"""

from __future__ import annotations

import json
import os
import tempfile

from .config import CONFIG_DIR

__all__ = ["KEYS_PATH", "delete_key", "get_key", "load_keys", "mask", "set_key"]

KEYS_PATH = CONFIG_DIR / "keys.json"

# Variable de entorno que se consulta antes que el archivo, por proveedor.
ENV_VARS: dict[str, tuple[str, ...]] = {
    "openrouter": ("OPENROUTER_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "grok": ("XAI_API_KEY", "GROK_API_KEY"),
    "groq": ("GROQ_API_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "mistral": ("MISTRAL_API_KEY",),
    "together": ("TOGETHER_API_KEY",),
}


def load_keys() -> dict[str, str]:
    """Claves guardadas en disco. Un archivo ilegible no impide arrancar."""
    try:
        raw = json.loads(KEYS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, str)} if isinstance(raw, dict) else {}


def get_key(provider: str) -> str:
    """Clave de un proveedor: primero el entorno, luego el archivo."""
    for var in ENV_VARS.get(provider, ()):
        value = os.environ.get(var, "").strip()
        if value:
            return value
    return load_keys().get(provider, "").strip()


def set_key(provider: str, key: str) -> bool:
    """Guardar una clave con el archivo cerrado a cal y canto."""
    keys = load_keys()
    keys[provider] = key.strip()
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=CONFIG_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(keys, fh, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, KEYS_PATH)
        os.chmod(KEYS_PATH, 0o600)
    except OSError:
        return False
    return True


def delete_key(provider: str) -> bool:
    keys = load_keys()
    if provider not in keys:
        return False
    del keys[provider]
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=CONFIG_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(keys, fh, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, KEYS_PATH)
    except OSError:
        return False
    return True


def mask(key: str) -> str:
    """Version de una clave que se puede enseñar por pantalla."""
    if not key:
        return "(sin clave)"
    if len(key) <= 10:
        return key[:2] + "…"
    return f"{key[:6]}…{key[-4:]}"
