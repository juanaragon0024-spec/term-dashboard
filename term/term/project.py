"""Lo que Term sabe del proyecto en el que esta trabajando.

Dos cosas que hoy hay que explicarle a mano a cada IA en cada conversacion:
las convenciones del repo y que forma tiene. Aqui se leen del disco y se le
pasan solas.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "AGENT_FILES",
    "FileContext",
    "build_repo_map",
    "project_summary",
    "read_agent_docs",
]

# Nombres que las herramientas del sector usan para las instrucciones del
# repositorio. Se leen todos los que haya, en este orden.
AGENT_FILES = ("AGENTS.md", "CLAUDE.md", ".cursorrules", "CONVENTIONS.md")

# Tope de lo que se inyecta en el prompt. Un AGENTS.md enorme se comeria el
# contexto que hace falta para la conversacion.
_MAX_DOC = 12_000
_MAX_MAP_FILES = 120

_SKIP = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", ".cache", ".pytest_cache", ".ruff_cache", "target", "vendor",
    ".idea", ".vscode", "coverage", ".terraform",
}

# Extensiones que cuentan como codigo para el mapa del proyecto.
_CODE_EXT = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".rb", ".java", ".kt",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".php", ".swift", ".sh", ".sql",
    ".html", ".css", ".scss", ".vue", ".svelte", ".lua", ".ex", ".exs",
}


def read_agent_docs(workdir: str) -> str:
    """Instrucciones del repositorio, si las hay.

    Se busca hacia arriba desde el directorio de trabajo hasta la raiz del
    repositorio, porque el AGENTS.md suele estar arriba y se trabaja abajo.
    """
    base = Path(workdir or ".").expanduser().resolve()
    vistos: list[str] = []
    total = 0

    for carpeta in [base, *base.parents]:
        for nombre in AGENT_FILES:
            ruta = carpeta / nombre
            if not ruta.is_file():
                continue
            try:
                texto = ruta.read_text(errors="replace").strip()
            except OSError:
                continue
            if not texto:
                continue
            if total + len(texto) > _MAX_DOC:
                texto = texto[: max(0, _MAX_DOC - total)] + "\n… (recortado)"
            vistos.append(f"# {ruta}\n\n{texto}")
            total += len(texto)
            if total >= _MAX_DOC:
                return "\n\n".join(vistos)
        # No seguimos subiendo por encima de la raiz del repositorio.
        if (carpeta / ".git").exists():
            break
    return "\n\n".join(vistos)


def list_code_files(workdir: str, limit: int = _MAX_MAP_FILES) -> list[Path]:
    """Los archivos de codigo del proyecto, ya filtrados."""
    base = Path(workdir or ".").expanduser().resolve()
    if not base.is_dir():
        return []
    rutas = _tracked_files(base) or _walk(base)
    codigo = [r for r in rutas if Path(r).suffix in _CODE_EXT]
    return [base / r for r in sorted(codigo)[:limit]]


def build_code_outline(workdir: str, budget: int = 12_000) -> str:
    """Esqueleto del codigo del proyecto: clases, funciones y sus firmas.

    Cuesta mas que la lista de archivos, pero evita tener que volcar archivos
    enteros para que el modelo sepa a que puede llamar, que sale mucho mas caro.
    """
    from .outline import build_outline

    archivos = list_code_files(workdir, limit=60)
    return build_outline(archivos, budget=budget) if archivos else ""


def _tracked_files(base: Path) -> list[str]:
    """Los archivos que git conoce, que ya respetan el .gitignore."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(base), "ls-files"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    if proc.returncode != 0:
        return []
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def build_repo_map(workdir: str, limit: int = _MAX_MAP_FILES) -> str:
    """Un mapa corto del proyecto: que archivos de codigo hay y donde.

    No es un indice semantico como el de Aider; es la lista de archivos que
    importan, agrupada por carpeta. Basta para que el modelo pida el archivo
    correcto en vez de adivinar rutas.
    """
    base = Path(workdir or ".").expanduser().resolve()
    if not base.is_dir():
        return ""

    archivos = _tracked_files(base) or _walk(base)

    interesantes = [a for a in archivos if Path(a).suffix in _CODE_EXT]
    if not interesantes:
        interesantes = archivos
    interesantes = sorted(interesantes)[:limit]
    if not interesantes:
        return ""

    por_carpeta: dict[str, list[str]] = {}
    for ruta in interesantes:
        carpeta = str(Path(ruta).parent)
        por_carpeta.setdefault("." if carpeta == "." else carpeta, []).append(
            Path(ruta).name)

    lineas = [f"Proyecto en {base}:"]
    for carpeta in sorted(por_carpeta):
        nombres = ", ".join(sorted(por_carpeta[carpeta])[:20])
        lineas.append(f"  {carpeta}/  {nombres}")
    if len(archivos) > len(interesantes):
        lineas.append(f"  … y {len(archivos) - len(interesantes)} archivos más")
    return "\n".join(lineas)


def _walk(base: Path) -> list[str]:
    """Recorrido a mano, para cuando no hay repositorio git."""
    encontrados: list[str] = []
    for ruta in base.rglob("*"):
        if not ruta.is_file():
            continue
        partes = ruta.relative_to(base).parts
        if any(p in _SKIP or p.startswith(".") for p in partes[:-1]):
            continue
        encontrados.append(str(ruta.relative_to(base)))
        if len(encontrados) > 2000:
            break
    return encontrados


# ---------------------------------------------------------------------------
# Contexto explicito de archivos
# ---------------------------------------------------------------------------

_MAX_FILE = 60_000


@dataclass
class FileContext:
    """Archivos que el usuario ha metido en la conversacion a proposito.

    Se releen en cada turno: si no, el modelo trabajaria sobre una copia vieja
    de un archivo que acaba de cambiar.
    """

    paths: list[str] = field(default_factory=list)

    def add(self, path: str, workdir: str) -> tuple[bool, str]:
        ruta = Path(path).expanduser()
        if not ruta.is_absolute():
            ruta = Path(workdir) / ruta
        ruta = ruta.resolve()
        if not ruta.is_file():
            return False, f"no existe: {ruta}"
        texto = str(ruta)
        if texto in self.paths:
            return False, f"ya estaba: {ruta.name}"
        self.paths.append(texto)
        return True, str(ruta)

    def drop(self, path: str) -> tuple[bool, str]:
        """Quitar por ruta o por nombre de archivo."""
        objetivo = path.strip()
        for guardado in list(self.paths):
            if guardado == objetivo or Path(guardado).name == objetivo:
                self.paths.remove(guardado)
                return True, guardado
        return False, objetivo

    def clear(self) -> int:
        cuantos = len(self.paths)
        self.paths.clear()
        return cuantos

    def render(self) -> str:
        """Los archivos, releidos, listos para meter en el prompt."""
        bloques: list[str] = []
        for ruta in list(self.paths):
            path = Path(ruta)
            if not path.is_file():
                # Se ha borrado por el camino: se cae solo del contexto.
                self.paths.remove(ruta)
                continue
            try:
                texto = path.read_text(errors="replace")
            except OSError:
                continue
            if len(texto) > _MAX_FILE:
                texto = texto[:_MAX_FILE] + "\n… (recortado)"
            bloques.append(f"--- {ruta} ---\n```\n{texto}\n```")
        return "\n\n".join(bloques)

    def summary(self) -> str:
        if not self.paths:
            return ""
        return ", ".join(Path(p).name for p in self.paths)


def project_summary(
    workdir: str, *, with_map: bool = True, with_outline: bool = False,
) -> str:
    """Todo lo que Term sabe del proyecto, listo para el prompt de sistema."""
    partes: list[str] = []
    if docs := read_agent_docs(workdir):
        partes.append(
            "Instrucciones del repositorio (respétalas por encima de tus "
            "costumbres):\n\n" + docs
        )
    if with_outline and (esqueleto := build_code_outline(workdir)):
        # El esqueleto ya dice qué archivos hay, así que sustituye al mapa.
        partes.append(
            "Esqueleto del código (clases y funciones con su firma; pide el "
            "archivo entero solo si necesitas el cuerpo):\n" + esqueleto)
    elif with_map and (mapa := build_repo_map(workdir)):
        partes.append("Estructura del proyecto:\n" + mapa)
    return "\n\n".join(partes)
