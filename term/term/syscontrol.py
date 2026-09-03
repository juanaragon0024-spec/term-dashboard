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


# ---------------------------------------------------------------------------
# Archivos y carpetas
# ---------------------------------------------------------------------------


def _resolve(path: str, base: str) -> Path:
    """Resolver una ruta relativa contra el directorio de trabajo."""
    expanded = Path(path).expanduser()
    return expanded if expanded.is_absolute() else Path(base) / expanded


def make_dir(path: str, base: str = "") -> SysResult:
    """Crear una carpeta, con sus padres si hacen falta."""
    if not path.strip():
        return SysResult(False, reason="mkdir|falta la ruta")
    target = _resolve(path, base or str(Path.cwd()))
    if target.exists():
        if target.is_dir():
            return SysResult(True, output=str(target), reason="ya existía")
        return SysResult(False, reason=f"mkdir|ya existe un archivo en {target}")
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return SysResult(False, reason=f"mkdir|{exc}")
    return SysResult(True, output=str(target))


def write_file(path: str, content: str = "", base: str = "") -> SysResult:
    """Crear un archivo. No pisa uno que ya exista.

    Sobrescribir en silencio es la clase de error que no se puede deshacer,
    asi que un archivo existente se rechaza y quien llama decide.
    """
    if not path.strip():
        return SysResult(False, reason="archivo|falta la ruta")
    target = _resolve(path, base or str(Path.cwd()))
    if target.exists():
        return SysResult(False, reason=f"archivo|{target} ya existe")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return SysResult(False, reason=f"archivo|{exc}")
    return SysResult(True, output=str(target))


# Carpetas que nunca interesan en una busqueda y que la harian eterna.
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", ".cache", "Library", ".Trash", ".npm", ".cargo",
}


def find_files(
    pattern: str, root: str = "", limit: int = 40, spotlight: bool = False,
) -> SysResult:
    """Buscar archivos por nombre y devolver sus rutas.

    Con `spotlight` se busca en todo el disco con el indice de macOS, que es
    instantaneo. Sin el, se recorre `root`, que es lo que se quiere cuando la
    pregunta es "en este proyecto".
    """
    pattern = pattern.strip()
    if not pattern:
        return SysResult(False, reason="buscar|falta el patrón")

    if spotlight and IS_MACOS and shutil.which("mdfind"):
        try:
            proc = subprocess.run(
                ["mdfind", "-name", pattern],
                capture_output=True, text=True, timeout=15,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            return SysResult(False, reason=f"buscar|{exc}")
        rutas = [ln for ln in proc.stdout.splitlines() if ln.strip()][:limit]
        return SysResult(True, output="\n".join(rutas))

    base = Path(root or Path.cwd()).expanduser()
    if not base.is_dir():
        return SysResult(False, reason=f"buscar|{base} no es una carpeta")

    # Un patron sin comodines se entiende como "que contenga esto".
    glob_pattern = pattern if any(c in pattern for c in "*?[") else f"*{pattern}*"
    encontrados: list[str] = []
    try:
        for path in base.rglob(glob_pattern):
            if any(part in _SKIP_DIRS or part.startswith(".")
                   for part in path.relative_to(base).parts[:-1]):
                continue
            encontrados.append(str(path))
            if len(encontrados) >= limit:
                break
    except OSError as exc:
        return SysResult(False, reason=f"buscar|{exc}")
    return SysResult(True, output="\n".join(encontrados))


def search_text(text: str, root: str = "", limit: int = 40) -> SysResult:
    """Buscar un texto dentro de los archivos y devolver ruta:linea."""
    text = text.strip()
    if not text:
        return SysResult(False, reason="grep|falta el texto")
    base = str(Path(root or Path.cwd()).expanduser())

    if shutil.which("rg"):
        cmd = ["rg", "--line-number", "--no-heading", "--color", "never",
               "--max-count", "3", "-e", text, base]
    else:
        cmd = ["grep", "-rn", "--", text, base]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return SysResult(False, reason="grep|timeout")
    except OSError as exc:
        return SysResult(False, reason=f"grep|{exc}")

    # Codigo 1 en rg y grep significa "sin coincidencias", que no es un fallo.
    if proc.returncode not in (0, 1):
        return SysResult(False, reason=(proc.stderr or "grep|error").strip())
    lineas = [ln for ln in proc.stdout.splitlines() if ln.strip()][:limit]
    return SysResult(True, output="\n".join(lineas))


# ---------------------------------------------------------------------------
# Musica
# ---------------------------------------------------------------------------

# Nombre de la app y nombre del comando de pista, que difieren entre las dos.
_MUSIC_APPS = ("Spotify", "Music")


def running_music_app() -> str:
    """Cual de los reproductores esta abierto ahora mismo.

    Se prefiere el que ya este sonando, para que /play no abra Spotify cuando
    lo que suena es Apple Music.
    """
    if not IS_MACOS:
        return ""
    abiertos = []
    for app in _MUSIC_APPS:
        result = _osascript(
            f'tell application "System Events" to (name of processes) contains "{app}"',
            "música",
        )
        if result and result.output.strip().lower() == "true":
            abiertos.append(app)
    if not abiertos:
        return ""
    for app in abiertos:
        estado = _osascript(
            f'tell application "{app}" to player state as string', "música")
        if estado and "playing" in estado.output.lower():
            return app
    return abiertos[0]


def music(action: str, app: str = "") -> SysResult:
    """Controlar el reproductor: play, pause, playpause, next, previous, track."""
    if not IS_MACOS:
        return _needs_macos("música")
    target = app or running_music_app() or "Spotify"

    if action == "track":
        script = (
            f'tell application "{target}" to '
            'name of current track & " — " & artist of current track'
        )
        result = _osascript(script, "música")
        if result and result.output:
            return SysResult(True, output=f"{result.output}  [{target}]")
        return SysResult(False, reason=f"música|{target} no está reproduciendo nada")

    acciones = {
        "play": "play",
        "pause": "pause",
        "playpause": "playpause",
        "next": "next track",
        "previous": "previous track",
    }
    verbo = acciones.get(action)
    if verbo is None:
        return SysResult(False, reason=f"música|acción desconocida: {action}")

    result = _osascript(f'tell application "{target}" to {verbo}', "música")
    if not result:
        return result
    # Tras cambiar de pista interesa saber que suena ahora.
    if action in ("next", "previous", "play", "playpause"):
        pista = music("track", target)
        if pista:
            return SysResult(True, output=pista.output)
    return SysResult(True, output=target)


def get_volume() -> SysResult:
    """Volumen de salida actual, 0-100."""
    return _osascript("output volume of (get volume settings)", "volumen")


# ---------------------------------------------------------------------------
# Navegador y busqueda web
# ---------------------------------------------------------------------------

SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q={q}",
    "ddg": "https://duckduckgo.com/?q={q}",
    "bing": "https://www.bing.com/search?q={q}",
    "youtube": "https://www.youtube.com/results?search_query={q}",
    "github": "https://github.com/search?q={q}",
    "maps": "https://www.google.com/maps/search/{q}",
}


def web_search(query: str, engine: str = "google", browser: str = "") -> SysResult:
    """Abrir una busqueda en el navegador."""
    from urllib.parse import quote_plus

    query = query.strip()
    if not query:
        return SysResult(False, reason="buscar|falta qué buscar")
    plantilla = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["google"])
    url = plantilla.format(q=quote_plus(query))
    result = open_url(url, browser)
    return SysResult(result.ok, output=url, reason=result.reason)


def quit_app(name: str) -> SysResult:
    """Cerrar una aplicacion."""
    return _osascript(f'tell application "{name}" to quit', "cerrar app")


# ---------------------------------------------------------------------------
# Estado del sistema
# ---------------------------------------------------------------------------


def system_info() -> SysResult:
    """Resumen corto: bateria, disco y red."""
    if not IS_MACOS:
        return _needs_macos("info del sistema")
    lineas: list[str] = []

    bateria = run_shell("pmset -g batt | head -2", "", timeout=5)
    if bateria and bateria.output:
        for linea in bateria.output.splitlines():
            if "%" in linea:
                lineas.append("Batería: " + linea.split("\t")[-1].strip().strip(";"))
                break

    disco = run_shell("df -h / | tail -1", "", timeout=5)
    if disco and disco.output:
        partes = disco.output.split()
        if len(partes) >= 5:
            lineas.append(f"Disco: {partes[3]} libres de {partes[1]} ({partes[4]} usado)")

    wifi = run_shell(
        "networksetup -getairportnetwork en0 2>/dev/null", "", timeout=5)
    if wifi and wifi.output and ":" in wifi.output:
        lineas.append("Red: " + wifi.output.split(":", 1)[1].strip())

    volumen = get_volume()
    if volumen and volumen.output:
        lineas.append(f"Volumen: {volumen.output}%")

    sonando = music("track")
    if sonando:
        lineas.append(f"Sonando: {sonando.output}")

    return SysResult(True, output="\n".join(lineas) or "sin datos")
