"""Catalogo de modelos, niveles de esfuerzo y modos de permisos.

El catalogo se arma a partir de los proveedores instalados, asi que la lista
que ve el usuario cambia sola segun lo que tenga en la maquina.
"""

from __future__ import annotations

from .providers import (
    DEFAULT_PROVIDER,
    PROVIDERS,
    available_providers,
    get_provider,
    join_ref,
    split_ref,
)

__all__ = [
    "DEFAULT_MODEL_REF",
    "EFFORT_LEVELS",
    "PERMISSION_MODES",
    "catalog",
    "model_label",
    "normalise_ref",
    "provider_label",
]

EFFORT_LEVELS = ["low", "medium", "high", "max"]

# Los modos que acepta `claude --permission-mode`.
PERMISSION_MODES = ["default", "acceptEdits", "plan", "bypassPermissions"]

DEFAULT_MODEL_REF = f"{DEFAULT_PROVIDER}/default"

# Referencias que usaban las versiones anteriores, cuando Term solo hablaba con
# Claude. Se siguen aceptando para que una configuracion vieja no arranque con
# un modelo invalido.
_LEGACY = {
    "claude": "claude/default",
    "default": "claude/default",
    "claude-opus": "claude/opus",
    "claude-sonnet": "claude/sonnet",
    "claude-haiku": "claude/haiku",
    "opus": "claude/opus",
    "sonnet": "claude/sonnet",
    "haiku": "claude/haiku",
}


def normalise_ref(ref: str) -> str:
    """Dejar una referencia en la forma `proveedor/modelo`."""
    ref = (ref or "").strip()
    if not ref:
        return DEFAULT_MODEL_REF
    if ref in _LEGACY:
        return _LEGACY[ref]
    provider_key, model = split_ref(ref)
    return join_ref(provider_key, model)


def catalog(only_installed: bool = True) -> list[tuple[str, str, str]]:
    """Modelos sugeridos como `(referencia, etiqueta, proveedor)`.

    Solo se ofrecen por defecto los proveedores instalados: proponer un modelo
    que no se puede ejecutar solo produce un error mas tarde.
    """
    proveedores = available_providers() if only_installed else list(PROVIDERS.values())
    entradas: list[tuple[str, str, str]] = []
    for provider in proveedores:
        for model in provider.suggested_models:
            entradas.append((join_ref(provider.key, model), model, provider.name))
    return entradas


def provider_label(ref: str) -> str:
    """Nombre legible del proveedor de una referencia."""
    provider_key, _ = split_ref(normalise_ref(ref))
    return get_provider(provider_key).name


def model_label(ref: str) -> str:
    """Etiqueta corta para la barra de estado: `proveedor · modelo`."""
    provider_key, model = split_ref(normalise_ref(ref))
    provider = get_provider(provider_key)
    if provider_key == DEFAULT_PROVIDER and model == "default":
        return "Claude"
    # El modelo de opencode ya lleva su casa delante; se recorta para que
    # quepa en la barra.
    short = model.rsplit("/", 1)[-1]
    return f"{provider.name} · {short}"
