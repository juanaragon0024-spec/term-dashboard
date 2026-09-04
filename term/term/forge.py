"""GitHub desde Term, apoyandose en la CLI `gh`.

Ver una pull request o abrir una incidencia son de las pocas cosas que todavia
obligan a irse al navegador. `gh` ya resuelve la autenticacion y la API, asi
que aqui solo se traduce su salida a algo que quepa en la TUI.

Sin `gh` instalado, cada operacion lo dice y explica como instalarlo, en vez de
fallar con un error de binario no encontrado.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass

__all__ = [
    "GH_HINT",
    "ForgeResult",
    "available",
    "checkout_pr",
    "create_issue",
    "list_issues",
    "list_prs",
    "repo_info",
    "view_issue",
    "view_pr",
]

GH_HINT = "brew install gh && gh auth login"

_TIMEOUT = 30


@dataclass(frozen=True)
class ForgeResult:
    ok: bool
    output: str = ""
    reason: str = ""

    def __bool__(self) -> bool:
        return self.ok


def available() -> bool:
    return shutil.which("gh") is not None


def _gh(cwd: str, *args: str) -> ForgeResult:
    if not available():
        return ForgeResult(False, reason=f"`gh` no está instalado. {GH_HINT}")
    try:
        proc = subprocess.run(
            ["gh", *args], capture_output=True, text=True,
            timeout=_TIMEOUT, cwd=cwd or None,
        )
    except subprocess.TimeoutExpired:
        return ForgeResult(False, reason="gh tardó demasiado")
    except OSError as exc:
        return ForgeResult(False, reason=str(exc))

    if proc.returncode != 0:
        detalle = (proc.stderr or proc.stdout).strip()
        # Los dos tropiezos habituales, dichos en cristiano.
        if "not logged" in detalle or "authentication" in detalle.lower():
            return ForgeResult(False, reason="no has iniciado sesión: gh auth login")
        if "not a git repository" in detalle.lower():
            return ForgeResult(False, reason="aquí no hay ningún repositorio")
        if "no default remote" in detalle.lower() or "Could not resolve" in detalle:
            return ForgeResult(False, reason="este repositorio no está en GitHub")
        return ForgeResult(False, reason=detalle[:300] or "gh falló")
    return ForgeResult(True, output=proc.stdout)


def _json(cwd: str, *args: str) -> tuple[bool, list | dict | str]:
    result = _gh(cwd, *args)
    if not result:
        return False, result.reason
    try:
        return True, json.loads(result.output or "[]")
    except ValueError:
        return False, "gh devolvió algo que no es JSON"


def repo_info(cwd: str) -> ForgeResult:
    ok, datos = _json(cwd, "repo", "view", "--json",
                      "nameWithOwner,description,defaultBranchRef")
    if not ok or not isinstance(datos, dict):
        return ForgeResult(False, reason=str(datos))
    rama = (datos.get("defaultBranchRef") or {}).get("name", "")
    lineas = [f"[bold]{datos.get('nameWithOwner', '')}[/]"]
    if descripcion := datos.get("description"):
        lineas.append(f"  {descripcion}")
    if rama:
        lineas.append(f"  [dim]rama principal: {rama}[/]")
    return ForgeResult(True, output="\n".join(lineas))


def _estado(item: dict) -> str:
    estado = (item.get("state") or "").lower()
    if item.get("isDraft"):
        return "borrador"
    return {"open": "abierta", "closed": "cerrada", "merged": "fusionada"}.get(
        estado, estado)


def list_prs(cwd: str, limit: int = 20, mine: bool = False) -> ForgeResult:
    """Pull requests abiertas del repositorio."""
    args = ["pr", "list", "--limit", str(limit), "--json",
            "number,title,author,state,isDraft,headRefName,updatedAt"]
    if mine:
        args += ["--author", "@me"]
    ok, datos = _json(cwd, *args)
    if not ok or not isinstance(datos, list):
        return ForgeResult(False, reason=str(datos))
    if not datos:
        return ForgeResult(True, output="No hay pull requests abiertas.")

    lineas = ["[bold]Pull requests[/]\n"]
    for pr in datos:
        autor = (pr.get("author") or {}).get("login", "?")
        lineas.append(
            f"  [bold]#{pr.get('number')}[/]  {pr.get('title', '')}\n"
            f"      [dim]{autor} · {_estado(pr)} · {pr.get('headRefName', '')}[/]")
    lineas.append("\n[dim]/pr <número> para verla · /pr-checkout <número> para probarla[/]")
    return ForgeResult(True, output="\n".join(lineas))


def list_issues(cwd: str, limit: int = 20, mine: bool = False) -> ForgeResult:
    args = ["issue", "list", "--limit", str(limit), "--json",
            "number,title,author,state,labels,updatedAt"]
    if mine:
        args += ["--assignee", "@me"]
    ok, datos = _json(cwd, *args)
    if not ok or not isinstance(datos, list):
        return ForgeResult(False, reason=str(datos))
    if not datos:
        return ForgeResult(True, output="No hay incidencias abiertas.")

    lineas = ["[bold]Incidencias[/]\n"]
    for issue in datos:
        autor = (issue.get("author") or {}).get("login", "?")
        etiquetas = ", ".join(
            e.get("name", "") for e in (issue.get("labels") or [])[:3])
        extra = f" · {etiquetas}" if etiquetas else ""
        lineas.append(
            f"  [bold]#{issue.get('number')}[/]  {issue.get('title', '')}\n"
            f"      [dim]{autor}{extra}[/]")
    lineas.append("\n[dim]/issue <número> para verla[/]")
    return ForgeResult(True, output="\n".join(lineas))


def _render_detalle(datos: dict, kind: str) -> str:
    autor = (datos.get("author") or {}).get("login", "?")
    lineas = [
        f"[bold]#{datos.get('number')} {datos.get('title', '')}[/]",
        f"[dim]{autor} · {_estado(datos)}[/]",
    ]
    if cuerpo := (datos.get("body") or "").strip():
        lineas += ["", cuerpo[:4000]]
    for comentario in (datos.get("comments") or [])[-5:]:
        quien = (comentario.get("author") or {}).get("login", "?")
        texto = (comentario.get("body") or "").strip()[:600]
        lineas += ["", f"[bold]{quien}:[/] {texto}"]
    if kind == "pr" and (archivos := datos.get("files")):
        lineas += ["", f"[dim]{len(archivos)} archivos cambiados[/]"]
    return "\n".join(lineas)


def view_pr(cwd: str, number: int) -> ForgeResult:
    ok, datos = _json(cwd, "pr", "view", str(number), "--json",
                      "number,title,body,author,state,isDraft,comments,files")
    if not ok or not isinstance(datos, dict):
        return ForgeResult(False, reason=str(datos))
    return ForgeResult(True, output=_render_detalle(datos, "pr"))


def view_issue(cwd: str, number: int) -> ForgeResult:
    ok, datos = _json(cwd, "issue", "view", str(number), "--json",
                      "number,title,body,author,state,comments")
    if not ok or not isinstance(datos, dict):
        return ForgeResult(False, reason=str(datos))
    return ForgeResult(True, output=_render_detalle(datos, "issue"))


def checkout_pr(cwd: str, number: int) -> ForgeResult:
    """Traer la rama de una pull request para probarla en local."""
    result = _gh(cwd, "pr", "checkout", str(number))
    if not result:
        return result
    return ForgeResult(True, output=f"Cambiado a la rama de la PR #{number}")


def create_issue(cwd: str, title: str, body: str = "") -> ForgeResult:
    """Abrir una incidencia. Sin titulo no se crea nada."""
    if not title.strip():
        return ForgeResult(False, reason="hace falta un título")
    args = ["issue", "create", "--title", title.strip()]
    args += ["--body", body.strip() or title.strip()]
    result = _gh(cwd, *args)
    if not result:
        return result
    # gh devuelve la URL de lo que acaba de crear.
    return ForgeResult(True, output=result.output.strip())
