"""Qué puede hacer la IA. Un solo ajuste, tres niveles.

Antes esto vivía en tres sitios que no se hablaban: un booleano de «permisos
concedidos», un modo de permisos con cuatro valores técnicos y un perfil de
herramientas con otros cuatro. Ninguno de los tres conseguía que la IA pudiera
pasar de canción, porque conceder permisos en Term no se traducía en permisos
para la CLI, que seguía preguntando y en modo no interactivo no puede.

Ahora hay un nivel y ese nivel se traduce a lo que cada motor entiende: a los
`--allowedTools` de la CLI y a la lista de herramientas del motor propio.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["DEFAULT_LEVEL", "LEVELS", "Level", "get_level", "level_names"]

DEFAULT_LEVEL = "normal"


@dataclass(frozen=True)
class Level:
    key: str
    name: str
    summary: str
    detail: str
    # Patrones para `claude --allowedTools`. Vacío significa no pasar el flag.
    cli_tools: tuple[str, ...] = ()
    # Modo de permisos de la CLI, cuando hace falta uno concreto.
    cli_mode: str = ""
    # Herramientas propias de Term que se le ofrecen al modelo por API.
    own_tools: frozenset[str] = field(default_factory=frozenset)
    # Si el nivel deja tocar el sistema (música, apps, volumen, shell).
    system: bool = True


# Lo que hace falta para leer y entender un proyecto, sin cambiar nada.
_LECTURA_CLI = (
    "Read", "Glob", "Grep", "WebFetch", "WebSearch",
    "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)",
    "Bash(rg:*)", "Bash(grep:*)", "Bash(find:*)", "Bash(wc:*)",
    "Bash(git status:*)", "Bash(git log:*)", "Bash(git diff:*)",
    "Bash(pwd)", "Bash(which:*)", "Bash(file:*)",
)

_LECTURA_PROPIAS = frozenset({
    "leer_archivo", "listar_carpeta", "buscar_archivos", "buscar_texto",
})

# Lo de arriba más lo que hace falta para trabajar de verdad: escribir, correr
# las herramientas del proyecto y manejar el ordenador.
_NORMAL_CLI = (
    *_LECTURA_CLI,
    "Write", "Edit", "NotebookEdit", "TodoWrite", "Task",
    # Control del sistema: es lo que se pide al decir «pon la siguiente
    # canción», y sin esto la CLI se para a preguntar.
    "Bash(osascript:*)", "Bash(open:*)", "Bash(pbcopy:*)", "Bash(pbpaste:*)",
    "Bash(say:*)", "Bash(pmset:*)", "Bash(networksetup:*)", "Bash(df:*)",
    # Trabajo normal en un proyecto.
    "Bash(mkdir:*)", "Bash(touch:*)", "Bash(cp:*)", "Bash(mv:*)",
    "Bash(echo:*)", "Bash(sed:*)", "Bash(awk:*)", "Bash(sort:*)",
    "Bash(git:*)", "Bash(gh:*)",
    "Bash(npm:*)", "Bash(npx:*)", "Bash(yarn:*)", "Bash(pnpm:*)", "Bash(node:*)",
    "Bash(python3:*)", "Bash(python:*)", "Bash(pip:*)", "Bash(pip3:*)",
    "Bash(pytest:*)", "Bash(ruff:*)", "Bash(make:*)", "Bash(cargo:*)",
    "Bash(go:*)", "Bash(docker:*)", "Bash(curl:*)",
)

_NORMAL_PROPIAS = _LECTURA_PROPIAS | frozenset({
    "crear_carpeta", "crear_archivo", "controlar_musica", "ajustar_volumen",
    "buscar_en_web", "abrir_app", "info_sistema", "ejecutar_shell",
    "procesos_en_marcha", "ver_logs",
})


LEVELS: dict[str, Level] = {
    "lectura": Level(
        key="lectura",
        name="Solo mirar",
        summary="Lee y busca, pero no cambia nada",
        detail=(
            "Puede leer archivos, buscar por el proyecto y consultar el estado "
            "de git. No escribe, no ejecuta comandos y no toca el sistema."
        ),
        cli_tools=_LECTURA_CLI,
        own_tools=_LECTURA_PROPIAS,
        system=False,
    ),
    "normal": Level(
        key="normal",
        name="Trabajar",
        summary="Crea archivos, ejecuta comandos y maneja el ordenador",
        detail=(
            "Lo anterior, más escribir archivos, ejecutar las herramientas del "
            "proyecto (git, npm, pytest…) y controlar la música, el volumen y "
            "las aplicaciones. No borra nada sin decírtelo."
        ),
        cli_tools=_NORMAL_CLI,
        own_tools=_NORMAL_PROPIAS,
    ),
    "todo": Level(
        key="todo",
        name="Sin preguntar",
        summary="Cualquier comando, sin pedir permiso",
        detail=(
            "No se comprueba nada. Incluye borrar archivos y ejecutar cualquier "
            "cosa. Úsalo solo si sabes lo que estás haciendo."
        ),
        cli_mode="bypassPermissions",
        own_tools=frozenset(),   # vacío = sin restricción
    ),
}

# Nombres que usaban las versiones anteriores, para que una configuración
# vieja no deje a la IA sin poder hacer nada.
_LEGACY = {
    "segura": "normal", "default": "normal", "acceptEdits": "normal",
    "plan": "lectura", "nada": "lectura", "manual": "lectura",
    "bypassPermissions": "todo",
}


def get_level(key: str) -> Level:
    """Nivel por su nombre, con reserva al normal."""
    clave = (key or "").strip()
    clave = _LEGACY.get(clave, clave)
    return LEVELS.get(clave, LEVELS[DEFAULT_LEVEL])


def level_names() -> list[str]:
    return list(LEVELS)
