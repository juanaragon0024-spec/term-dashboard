"""Git, lo justo para trabajar sin salir de Term.

No pretende sustituir a git: cubre el ciclo corto de ver que ha cambiado,
guardarlo y deshacerlo si no era eso. Todo lo demas se hace con /run.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

__all__ = ["GitResult", "commit", "diff", "is_repo", "log", "status", "undo"]

# Tope del diff que se pinta. Un diff de miles de lineas no se lee en una TUI
# y ademas tarda en renderizarse.
_MAX_DIFF = 20_000


@dataclass(frozen=True)
class GitResult:
    ok: bool
    output: str = ""
    reason: str = ""

    def __bool__(self) -> bool:
        return self.ok


def _git(cwd: str, *args: str, timeout: int = 20) -> GitResult:
    if not shutil.which("git"):
        return GitResult(False, reason="git no está instalado")
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return GitResult(False, reason="git tardó demasiado")
    except OSError as exc:
        return GitResult(False, reason=str(exc))
    if proc.returncode != 0:
        return GitResult(False, reason=(proc.stderr or proc.stdout).strip())
    return GitResult(True, output=proc.stdout)


@dataclass(frozen=True)
class FileChange:
    """Un archivo con cambios, tal y como lo cuenta git."""

    path: str
    index: str          # estado en el area de preparacion
    worktree: str       # estado en el directorio de trabajo

    @property
    def staged(self) -> bool:
        return self.index not in (" ", "?")

    @property
    def untracked(self) -> bool:
        return self.index == "?" and self.worktree == "?"

    @property
    def label(self) -> str:
        etiquetas = {"M": "modificado", "A": "añadido", "D": "borrado",
                     "R": "renombrado", "C": "copiado", "U": "en conflicto"}
        if self.untracked:
            return "sin seguir"
        estado = self.worktree if self.worktree != " " else self.index
        return etiquetas.get(estado, estado)


def changed_files(cwd: str) -> list[FileChange]:
    """Los archivos con cambios, ya troceados para pintarlos en una lista."""
    if not is_repo(cwd):
        return []
    result = _git(cwd, "status", "--porcelain=v1")
    if not result:
        return []
    cambios: list[FileChange] = []
    for linea in result.output.splitlines():
        if len(linea) < 4:
            continue
        # Un renombrado viene como «viejo -> nuevo»; interesa el nuevo.
        ruta = linea[3:].strip()
        if " -> " in ruta:
            ruta = ruta.split(" -> ", 1)[1]
        cambios.append(FileChange(path=ruta.strip('"'),
                                  index=linea[0], worktree=linea[1]))
    return cambios


def diff_file(cwd: str, path: str, staged: bool = False) -> GitResult:
    """El diff de un solo archivo."""
    if not is_repo(cwd):
        return GitResult(False, reason="no es un repositorio git")
    args = ["diff"] + (["--staged"] if staged else []) + ["--", path]
    result = _git(cwd, *args)
    if not result:
        return result
    texto = result.output.strip()
    if not texto:
        # Un archivo sin seguir no tiene diff: se enseña su contenido.
        contenido = _git(cwd, "show", f":{path}") if staged else None
        if contenido is None or not contenido:
            ruta = Path(cwd) / path
            if ruta.is_file():
                try:
                    crudo = ruta.read_text(errors="replace")
                except OSError:
                    crudo = ""
                texto = "\n".join(f"+{ln}" for ln in crudo.splitlines()[:400])
    if len(texto) > _MAX_DIFF:
        texto = texto[:_MAX_DIFF] + "\n… (recortado)"
    return GitResult(True, output=texto or "(sin cambios en este archivo)")


def stage(cwd: str, path: str = "") -> GitResult:
    """Preparar un archivo, o todos si no se dice cual."""
    if not is_repo(cwd):
        return GitResult(False, reason="no es un repositorio git")
    return _git(cwd, "add", "--", path) if path else _git(cwd, "add", "-A")


def unstage(cwd: str, path: str = "") -> GitResult:
    """Sacar un archivo del área de preparación."""
    if not is_repo(cwd):
        return GitResult(False, reason="no es un repositorio git")
    args = ["restore", "--staged"] + ([path] if path else ["."])
    return _git(cwd, *args)


def discard(cwd: str, path: str) -> GitResult:
    """Tirar los cambios de un archivo.

    Es la única operación de aquí que pierde trabajo, así que exige una ruta
    concreta: un «descarta todo» a un teclazo de distancia es una tarde
    perdida esperando a ocurrir.
    """
    if not is_repo(cwd):
        return GitResult(False, reason="no es un repositorio git")
    if not path.strip():
        return GitResult(False, reason="hay que decir qué archivo descartar")
    return _git(cwd, "checkout", "--", path)


def is_repo(cwd: str) -> bool:
    return _git(cwd, "rev-parse", "--git-dir", timeout=5).ok


def status(cwd: str) -> GitResult:
    """Resumen legible de lo que hay sin guardar."""
    if not is_repo(cwd):
        return GitResult(False, reason="no es un repositorio git")
    crudo = _git(cwd, "status", "--porcelain=v1", "--branch")
    if not crudo:
        return crudo

    lineas = crudo.output.splitlines()
    rama = ""
    cambios: list[str] = []
    for linea in lineas:
        if linea.startswith("##"):
            rama = linea[2:].strip()
            continue
        if not linea.strip():
            continue
        # En porcelain v1 el estado son dos columnas fijas: la primera es lo
        # preparado y la segunda lo que hay suelto en el directorio.
        indice, arbol, ruta = linea[0], linea[1], linea[3:].strip()
        etiquetas = {"M": "modificado", "A": "añadido", "D": "borrado",
                     "R": "renombrado", "C": "copiado", "U": "en conflicto"}
        if indice == "?" and arbol == "?":
            etiqueta, preparado = "sin seguir", " "
        else:
            # Se describe el cambio más reciente, y se marca si está preparado.
            estado = arbol if arbol != " " else indice
            etiqueta = etiquetas.get(estado, estado)
            preparado = "+" if indice not in (" ", "?") else " "
        cambios.append(f"  {preparado} {etiqueta:12s} {ruta}")

    if not cambios:
        return GitResult(True, output=f"Rama {rama}\n  sin cambios pendientes")
    return GitResult(True, output=f"Rama {rama}\n" + "\n".join(cambios))


def diff(cwd: str, staged: bool = False) -> GitResult:
    if not is_repo(cwd):
        return GitResult(False, reason="no es un repositorio git")
    args = ["diff", "--stat", "--patch"]
    if staged:
        args.insert(1, "--staged")
    result = _git(cwd, *args)
    if not result:
        return result
    texto = result.output.strip()
    if not texto:
        return GitResult(True, output="(no hay cambios)")
    if len(texto) > _MAX_DIFF:
        texto = texto[:_MAX_DIFF] + "\n… (diff recortado)"
    return GitResult(True, output=texto)


def commit(cwd: str, message: str, add_all: bool = True) -> GitResult:
    """Guardar los cambios. Sin mensaje no se commitea nada."""
    if not is_repo(cwd):
        return GitResult(False, reason="no es un repositorio git")
    if not message.strip():
        return GitResult(False, reason="hace falta un mensaje de commit")
    if add_all:
        preparado = _git(cwd, "add", "-A")
        if not preparado:
            return preparado

    pendiente = _git(cwd, "diff", "--staged", "--name-only")
    if pendiente and not pendiente.output.strip():
        return GitResult(False, reason="no hay nada que guardar")

    result = _git(cwd, "commit", "-m", message)
    if not result:
        return result
    corto = _git(cwd, "rev-parse", "--short", "HEAD")
    return GitResult(True, output=f"{corto.output.strip()} {message.splitlines()[0]}")


def undo(cwd: str) -> GitResult:
    """Deshacer el último commit dejando los cambios en el directorio.

    Se usa `reset --soft` a proposito: `--hard` borraria trabajo sin
    posibilidad de recuperarlo, y deshacer no deberia poder costarte una tarde.
    """
    if not is_repo(cwd):
        return GitResult(False, reason="no es un repositorio git")
    cabeza = _git(cwd, "log", "-1", "--pretty=%h %s")
    if not cabeza or not cabeza.output.strip():
        return GitResult(False, reason="no hay ningún commit que deshacer")
    padres = _git(cwd, "rev-list", "--count", "HEAD")
    if padres and padres.output.strip() == "1":
        return GitResult(False, reason="no se puede deshacer el primer commit")

    result = _git(cwd, "reset", "--soft", "HEAD~1")
    if not result:
        return result
    return GitResult(
        True,
        output=f"Deshecho: {cabeza.output.strip()}\n"
               "Los cambios siguen en el directorio, sin confirmar.",
    )


def log(cwd: str, count: int = 10) -> GitResult:
    if not is_repo(cwd):
        return GitResult(False, reason="no es un repositorio git")
    return _git(cwd, "log", f"-{count}", "--pretty=%h  %ar  %s")
