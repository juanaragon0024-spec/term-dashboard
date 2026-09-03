"""Modelos y niveles de esfuerzo que Term ofrece a la CLI de Claude Code."""

from __future__ import annotations

__all__ = [
    "AI_MODELS",
    "DEFAULT_MODEL",
    "EFFORT_LEVELS",
    "PERMISSION_MODES",
    "model_label",
    "resolve_model",
]

# `alias` es lo que se le pasa a `claude --model`. None significa no pasar el
# flag y dejar que la CLI use el modelo configurado por el usuario.
AI_MODELS: dict[str, dict[str, str | None]] = {
    "default": {"name": "Claude", "alias": None},
    "opus": {"name": "Claude Opus", "alias": "opus"},
    "sonnet": {"name": "Claude Sonnet", "alias": "sonnet"},
    "haiku": {"name": "Claude Haiku", "alias": "haiku"},
}

DEFAULT_MODEL = "default"

EFFORT_LEVELS = ["low", "medium", "high", "max"]

# Los modos que acepta `claude --permission-mode`.
PERMISSION_MODES = ["default", "acceptEdits", "plan", "bypassPermissions"]

# Claves que existian en versiones anteriores de Term y que seguimos aceptando
# para que una config vieja no arranque con un modelo invalido.
_LEGACY = {
    "claude": "default",
    "claude-opus": "opus",
    "claude-haiku": "haiku",
    "claude-sonnet": "sonnet",
}


def resolve_model(key: str) -> tuple[str, str | None]:
    """Normalizar una clave de modelo a `(clave, alias para --model)`.

    Una clave desconocida se trata como un identificador de modelo literal
    (por ejemplo `claude-opus-4-5-20251101`), asi que `/model <id>` funciona
    con cualquier modelo que la CLI acepte sin tener que tocar esta tabla.
    """
    key = (key or "").strip()
    key = _LEGACY.get(key, key)
    if not key:
        return DEFAULT_MODEL, None
    if key in AI_MODELS:
        return key, AI_MODELS[key]["alias"]  # type: ignore[return-value]
    return key, key


def model_label(key: str) -> str:
    """Nombre legible de un modelo, incluidos los identificadores literales."""
    key = _LEGACY.get(key, key)
    entry = AI_MODELS.get(key)
    return str(entry["name"]) if entry else key
