"""Control del sistema operativo, aislado tras una capa que falla con elegancia.

El resto de Term nunca llama a `osascript`, `open` ni `pbcopy` directamente.
Todo pasa por aqui, y fuera de macOS cada operacion devuelve un
`SysResult(ok=False)` con un motivo legible en lugar de reventar con
FileNotFoundError o de fallar en silencio.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "BROWSER_ALIASES",
    "IS_MACOS",
    "SysResult",
    "copy_to_clipboard",
    "detect_browsers",
    "detect_cli_apps",
    "git_branch",
    "open_app",
    "open_url",
    "run_shell",
    "set_volume",
    "spotify",
]

IS_MACOS = sys.platform == "darwin"

# Tope de salida que aceptamos de un comando de shell. Sin esto, un `cat` sobre
# un binario grande intenta pintar megabytes en la TUI y la congela.
_MAX_OUTPUT = 20_000


@dataclass(frozen=True)
class SysResult:
    """Resultado de una operacion de sistema.

    `ok` False no es una excepcion: es el caso normal cuando la funcion no
    existe en esta plataforma o el binario no esta instalado. `reason` es el
    texto que la TUI muestra al usuario.
    """

    ok: bool
    output: str = ""
    reason: str = ""

    def __bool__(self) -> bool:
        return self.ok


def _needs_macos(feature: str) -> SysResult:
    return SysResult(False, reason=f"{feature}|macos-only")


def _osascript(script: str, feature: str) -> SysResult:
    if not IS_MACOS:
        return _needs_macos(feature)
    if not shutil.which("osascript"):
        return SysResult(False, reason=f"{feature}|osascript-missing")
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        return SysResult(False, reason=f"{feature}|timeout")
    except OSError as exc:
        return SysResult(False, reason=f"{feature}|{exc}")
    if proc.returncode != 0:
        return SysResult(False, reason=(proc.stderr or "").strip() or f"{feature}|failed")
    return SysResult(True, output=proc.stdout.strip())


def open_app(name: str) -> SysResult:
    """Abrir una aplicacion por nombre."""
    if not IS_MACOS:
        return _needs_macos("open")
    try:
        subprocess.Popen(
            ["open", "-a", name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        return SysResult(False, reason=str(exc))
    return SysResult(True)


def open_url(url: str, browser: str = "") -> SysResult:
    """Abrir una URL, opcionalmente forzando un navegador concreto."""
    if not IS_MACOS:
        return _needs_macos("open")
    args = ["open"] + (["-a", browser] if browser else []) + [url]
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return SysResult(False, reason=str(exc))
    return SysResult(True)


def set_volume(level: int) -> SysResult:
    """Volumen de salida del sistema, 0-100."""
    level = max(0, min(100, level))
    return _osascript(f"set volume output volume {level}", "volume")


def spotify(action: str) -> SysResult:
    """Controlar Spotify. `action`: playpause, next, previous, track."""
    scripts = {
        "playpause": 'tell application "Spotify" to playpause',
        "next": 'tell application "Spotify" to next track',
        "previous": 'tell application "Spotify" to previous track',
        "track": 'tell application "Spotify" to name of current track'
                 ' & " -- " & artist of current track',
    }
    script = scripts.get(action)
    if script is None:
        return SysResult(False, reason=f"spotify|accion desconocida: {action}")
    return _osascript(script, "Spotify")


def copy_to_clipboard(text: str) -> SysResult:
    """Copiar al portapapeles con el binario que exista en esta plataforma."""
    for cmd in (["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"], ["clip"]):
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text.encode(), check=True, timeout=10)
            except (subprocess.SubprocessError, OSError) as exc:
                return SysResult(False, reason=str(exc))
            return SysResult(True)
    return SysResult(False, reason="portapapeles|sin pbcopy, wl-copy, xclip ni clip")


def run_shell(command: str, cwd: str, timeout: int = 10) -> SysResult:
    """Ejecutar un comando de shell y devolver su salida acotada."""
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd or None,
        )
    except subprocess.TimeoutExpired:
        return SysResult(False, reason="timeout")
    except OSError as exc:
        return SysResult(False, reason=str(exc))
    out = proc.stdout or proc.stderr or ""
    if len(out) > _MAX_OUTPUT:
        out = out[:_MAX_OUTPUT] + f"\n... (truncado en {_MAX_OUTPUT} caracteres)"
    return SysResult(True, output=out.strip())


BROWSER_ALIASES: dict[str, str] = {
    "safari": "Safari",
    "chrome": "Google Chrome",
    "brave": "Brave Browser",
    "firefox": "Firefox",
    "edge": "Microsoft Edge",
    "opera": "Opera",
    "arc": "Arc",
    "vivaldi": "Vivaldi",
    "zen": "Zen Browser",
}


def detect_browsers() -> list[dict[str, str]]:
    """Navegadores instalados, buscando tambien en ~/Applications."""
    if not IS_MACOS:
        return []
    roots = [Path("/Applications"), Path.home() / "Applications"]
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for app_name in BROWSER_ALIASES.values():
        if app_name in seen:
            continue
        for root in roots:
            if (root / f"{app_name}.app").exists():
                found.append({"name": app_name, "app": app_name})
                seen.add(app_name)
                break
    return found


_CLI_CANDIDATES = [
    ("vim", "Vim", "Editor"),
    ("nvim", "Neovim", "Editor"),
    ("nano", "Nano", "Editor"),
    ("hx", "Helix", "Editor"),
    ("htop", "htop", "Monitor"),
    ("btop", "btop", "Monitor"),
    ("top", "top", "Monitor"),
    ("python3", "Python REPL", "Dev"),
    ("node", "Node.js REPL", "Dev"),
    ("git", "Git", "Dev"),
    ("docker", "Docker", "Dev"),
    ("lazygit", "LazyGit", "Dev"),
    ("gh", "GitHub CLI", "Dev"),
    ("rg", "ripgrep", "Dev"),
    ("jq", "jq", "Dev"),
    ("tmux", "tmux", "Terminal"),
    ("mc", "Midnight Commander", "Archivos"),
    ("fzf", "fzf", "Archivos"),
]


def detect_cli_apps() -> list[dict[str, str]]:
    """Herramientas de linea de comandos presentes en el PATH."""
    return [
        {"cmd": cmd, "name": name, "category": cat}
        for cmd, name, cat in _CLI_CANDIDATES
        if shutil.which(cmd)
    ]


def git_branch(cwd: str) -> str:
    """Rama actual mas un `*` si hay cambios sin confirmar. Vacio si no hay repo."""
    if not shutil.which("git"):
        return ""
    try:
        head = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        if head.returncode != 0:
            return ""
        branch = head.stdout.strip()
        status = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain"],
            capture_output=True, text=True, timeout=3,
        )
        dirty = "*" if status.returncode == 0 and status.stdout.strip() else ""
        return f"{branch}{dirty}"
    except (subprocess.SubprocessError, OSError):
        return ""
