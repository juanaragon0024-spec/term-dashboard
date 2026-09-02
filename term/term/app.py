"""Term -- TUI con tabs, temas y control del sistema."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.reactive import reactive, var
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
)

# ---------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------

_LOGO = [
    r" ████████╗ ███████╗ ██████╗  ███╗   ███╗",
    r" ╚══██╔══╝ ██╔════╝ ██╔══██╗ ████╗ ████║",
    r"    ██║    █████╗   ██████╔╝ ██╔████╔██║",
    r"    ██║    ██╔══╝   ██╔══██╗ ██║╚██╔╝██║",
    r"    ██║    ███████╗ ██║  ██║ ██║ ╚═╝ ██║",
    r"    ╚═╝    ╚══════╝ ╚═╝  ╚═╝ ╚═╝     ╚═╝",
]

# ---------------------------------------------------------------------------
# Themes (all with BLACK backgrounds)
# ---------------------------------------------------------------------------

THEMES: dict[str, dict] = {
    "neon": {
        "name": "Neon",
        "bg1": "#050508", "bg2": "#0c0c14", "bg3": "#14142a",
        "border": "#1e1e3a", "accent1": "#00e5ff", "accent2": "#ff00e5",
        "accent3": "#39ff14", "accent4": "#ff6600", "text": "#e0e0ff",
        "muted": "#444466",
        "grad": ["#b388ff", "#9e8eff", "#8a94ff", "#759aff", "#5fa0ff",
                 "#4aa6ff", "#34acff", "#1fb2ff", "#0abcff", "#00e5ff"],
    },
    "dracula": {
        "name": "Dracula",
        "bg1": "#1a1b26", "bg2": "#21222c", "bg3": "#343746",
        "border": "#44475a", "accent1": "#8be9fd", "accent2": "#ff79c6",
        "accent3": "#50fa7b", "accent4": "#ffb86c", "text": "#f8f8f2",
        "muted": "#6272a4",
        "grad": ["#bd93f9", "#b094f9", "#a395f9", "#9696f9", "#8997f9",
                 "#7c98f9", "#7099f9", "#639af9", "#569bf9", "#8be9fd"],
    },
    "monokai": {
        "name": "Monokai",
        "bg1": "#1a1a18", "bg2": "#1e1f1c", "bg3": "#3e3d32",
        "border": "#49483e", "accent1": "#66d9ef", "accent2": "#f92672",
        "accent3": "#a6e22e", "accent4": "#fd971f", "text": "#f8f8f2",
        "muted": "#75715e",
        "grad": ["#ae81ff", "#a085f5", "#9289eb", "#848de1", "#7691d7",
                 "#6895cd", "#5a99c3", "#4c9db9", "#3ea1af", "#66d9ef"],
    },
    "catppuccin": {
        "name": "Catppuccin",
        "bg1": "#11111b", "bg2": "#181825", "bg3": "#313244",
        "border": "#45475a", "accent1": "#89dceb", "accent2": "#f5c2e7",
        "accent3": "#a6e3a1", "accent4": "#fab387", "text": "#cdd6f4",
        "muted": "#585b70",
        "grad": ["#cba6f7", "#c0a8f7", "#b5aaf7", "#aaacf7", "#9faef7",
                 "#94b0f7", "#89b2f7", "#7eb4f7", "#73b6f7", "#89dceb"],
    },
    "gruvbox": {
        "name": "Gruvbox",
        "bg1": "#0d0e0f", "bg2": "#1d2021", "bg3": "#3c3836",
        "border": "#504945", "accent1": "#83a598", "accent2": "#d3869b",
        "accent3": "#b8bb26", "accent4": "#fe8019", "text": "#ebdbb2",
        "muted": "#665c54",
        "grad": ["#d3869b", "#cd8a9d", "#c78e9f", "#c192a1", "#bb96a3",
                 "#b59aa5", "#af9ea7", "#a9a2a9", "#93a69b", "#83a598"],
    },
    "tokyo": {
        "name": "Tokyo Night",
        "bg1": "#0f0f17", "bg2": "#16161e", "bg3": "#24283b",
        "border": "#3b4261", "accent1": "#7dcfff", "accent2": "#bb9af7",
        "accent3": "#9ece6a", "accent4": "#ff9e64", "text": "#c0caf5",
        "muted": "#565f89",
        "grad": ["#bb9af7", "#b19ef7", "#a7a2f7", "#9da6f7", "#93aaf7",
                 "#89aef7", "#7fb2f7", "#75b6f7", "#6bbaf7", "#7dcfff"],
    },
}

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

AI_MODELS: dict[str, dict] = {
    "claude": {
        "name": "Claude",
        "cmd": ["claude", "-p"],
        "args": ["--max-turns", "15"],
    },
    "claude-opus": {
        "name": "Claude Opus",
        "cmd": ["claude", "-p"],
        "args": ["--max-turns", "15", "--model", "opus"],
    },
    "claude-haiku": {
        "name": "Claude Haiku",
        "cmd": ["claude", "-p"],
        "args": ["--max-turns", "15", "--model", "haiku"],
    },
}

EFFORT_LEVELS = ["low", "medium", "high", "max"]

VERSION = "2.0.0"

# ---------------------------------------------------------------------------
# System prompt for macOS control
# ---------------------------------------------------------------------------

SYSTEM_CONTEXT = (
    "Eres Term, un asistente de terminal con IA. Puedes controlar esta Mac.\n"
    "Cuando el usuario pida abrir apps, cambiar canciones, ajustar volumen, etc., usa osascript/AppleScript.\n\n"
    "Ejemplos:\n"
    "- Abrir Safari: osascript -e 'tell application \"Safari\" to activate'\n"
    "- Play/pausa Spotify: osascript -e 'tell application \"Spotify\" to playpause'\n"
    "- Siguiente cancion: osascript -e 'tell application \"Spotify\" to next track'\n"
    "- Cancion anterior: osascript -e 'tell application \"Spotify\" to previous track'\n"
    "- Ajustar volumen: osascript -e 'set volume output volume 50'\n"
    "- Abrir Finder: open ~/Desktop\n"
    "- Abrir app: open -a \"App Name\"\n"
    "- Cancion actual: osascript -e 'tell application \"Spotify\" to name of current track'\n\n"
    "Tienes acceso completo al shell. Ejecuta comandos directamente. Se conciso."
)

# ---------------------------------------------------------------------------
# Command reference (Spanish)
# ---------------------------------------------------------------------------

COMMANDS_HELP: dict[str, str] = {
    "/theme <nombre>":        "Cambiar tema (neon, dracula, monokai, catppuccin, gruvbox, tokyo)",
    "/effort <nivel>":        "Nivel de esfuerzo (low, medium, high, max)",
    "/model <nombre>":        "Cambiar modelo (claude, claude-opus, claude-haiku)",
    "/name <texto>":          "Renombrar la tab activa",
    "/workdir <ruta>":        "Cambiar directorio de trabajo",
    "/new [nombre] [modelo]": "Nueva tab (ej. /new MiChat claude-opus)",
    "/close":                 "Cerrar tab activa",
    "/clear":                 "Limpiar chat",
    "/save":                  "Guardar configuracion",
    "/help":                  "Panel de ayuda",
    "/apps":                  "Panel de aplicaciones",
    "/tools":                 "Panel de herramientas",
    "/settings":              "Panel de ajustes",
    "/about":                 "Acerca de Term",
    "/models":                "Listar modelos con estado de conexion",
    "/themes":                "Listar temas con el activo marcado",
    "/status":                "Estado actual (tema, modelo, esfuerzo, directorio)",
    "/reset":                 "Reiniciar contexto estimado a 0",
    "/version":               "Mostrar version de Term",
    "/open <app>":            "Abrir una aplicacion (ej. /open Safari)",
    "/run <cmd>":             "Ejecutar comando shell y mostrar salida",
    "/volume <0-100>":        "Ajustar volumen del sistema",
    "/play":                  "Play/Pausa en Spotify",
    "/next":                  "Siguiente cancion en Spotify",
    "/prev":                  "Cancion anterior en Spotify",
    "/copy":                  "Copiar ultima respuesta al portapapeles",
    "/history":               "Cantidad de mensajes en esta tab",
    "/export":                "Guardar chat en archivo de texto",
    "/compact":               "Consejo: resumir chats largos para ahorrar contexto",
    "/restart":               "Cerrar y reiniciar Term",
}

SHORTCUTS_HELP: dict[str, str] = {
    "ctrl+t": "Nueva tab",
    "ctrl+w": "Cerrar tab",
    "ctrl+l": "Limpiar chat",
    "ctrl+e": "Cambiar esfuerzo",
    "escape":  "Cancelar generacion",
}

# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------

CONFIG_PATH = Path.home() / ".config" / "term" / "config.json"


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {
        "theme": "neon",
        "workdir": str(Path.home()),
        "effort": "high",
        "model": "claude",
        "permissions_granted": False,
    }


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

# ---------------------------------------------------------------------------
# Detect installed CLI apps
# ---------------------------------------------------------------------------


def _detect_apps() -> list[dict]:
    candidates = [
        ("vim", "Vim", "Editor"),
        ("nvim", "Neovim", "Editor"),
        ("nano", "Nano", "Editor"),
        ("htop", "htop", "Monitor"),
        ("btop", "btop", "Monitor"),
        ("top", "top", "Monitor"),
        ("python3", "Python REPL", "Dev"),
        ("node", "Node.js REPL", "Dev"),
        ("git", "Git", "Dev"),
        ("docker", "Docker", "Dev"),
        ("lazygit", "LazyGit", "Dev"),
        ("tmux", "tmux", "Terminal"),
        ("mc", "Midnight Commander", "Archivos"),
    ]
    return [
        {"cmd": cmd, "name": name, "category": cat}
        for cmd, name, cat in candidates
        if shutil.which(cmd)
    ]

# ---------------------------------------------------------------------------
# Logo builder with gradient colouring
# ---------------------------------------------------------------------------


def _build_logo(theme_key: str = "neon") -> str:
    grad = THEMES.get(theme_key, THEMES["neon"])["grad"]
    mx = max(len(ln) for ln in _LOGO)
    lines: list[str] = []
    for ln in _LOGO:
        buf = ""
        for i, ch in enumerate(ln):
            if ch == " ":
                buf += " "
            else:
                idx = int(i / max(mx, 1) * (len(grad) - 1))
                buf += f"[bold {grad[idx]}]{ch}[/]"
        lines.append(buf)
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# CSS -- uses $variables resolved by get_css_variables()
# ---------------------------------------------------------------------------

APP_CSS = """
Screen {
    background: $bg1;
}

/* -- Nav sidebar -- */
#nav {
    width: 18;
    background: $bg2;
    border-right: solid $border;
    padding: 1 0;
}
#nav-title {
    color: $accent1;
    text-style: bold;
    text-align: center;
    padding: 0 0 1 0;
}
.nav-btn {
    width: 100%;
    background: transparent;
    color: $muted;
    border: none;
    padding: 0 2;
    margin: 0;
    text-align: left;
    min-width: 16;
}
.nav-btn:hover {
    color: $text;
    background: $bg3;
}
.nav-btn.-active, .nav-btn:focus {
    color: $accent1;
    background: $bg3;
    text-style: bold;
}

/* -- Main area -- */
#main {
    background: $bg1;
}
TabbedContent {
    background: $bg1;
}
ContentSwitcher {
    background: $bg1;
}
TabPane {
    background: $bg1;
    padding: 0;
}
Tabs {
    background: $bg2;
    border-bottom: solid $border;
}
Tab {
    background: $bg2;
    color: $muted;
    padding: 0 2;
}
Tab:hover {
    color: $accent1;
}
Tab.-active {
    background: $bg1;
    color: $accent1;
    text-style: bold;
}
Underline {
    color: $accent1;
}

/* -- Chat area -- */
.chat-wrap {
    background: $bg1;
}
.messages {
    background: $bg1;
    padding: 1 2;
    scrollbar-color: $border;
    scrollbar-color-hover: $accent1;
}
.user-msg {
    color: $text;
    margin: 1 2 0 16;
    padding: 1 2;
    border: none;
    background: transparent;
    text-align: right;
}
.user-msg-inner {
    background: $bg3;
    color: $text;
    padding: 1 2;
    border: solid $accent2;
    text-align: left;
}
.assistant-msg {
    background: transparent;
    color: $text;
    margin: 0 8 1 2;
    padding: 0 2 1 2;
    border: none;
}
.assistant-msg Markdown {
    margin: 0;
    padding: 0;
}
.assistant-msg MarkdownFence {
    background: #0d1117;
    border: solid $border;
    margin: 1 0;
}
.assistant-msg MarkdownH1,
.assistant-msg MarkdownH2,
.assistant-msg MarkdownH3 {
    color: $accent2;
    text-style: bold;
}
.assistant-msg MarkdownBlockQuote {
    border-left: outer $accent1;
    padding: 0 0 0 2;
    color: $muted;
}

/* -- Input bar -- */
.input-bar {
    dock: bottom;
    height: auto;
    max-height: 8;
    background: $bg2;
    border-top: solid $border;
    padding: 1 2 0 2;
}
.input-bar Input {
    background: $bg3;
    color: $text;
    border: tall $border;
}
.input-bar Input:focus {
    border: tall $accent1;
}

/* -- Status bar -- */
#status-bar {
    dock: bottom;
    height: 1;
    background: $bg2;
    color: $muted;
    padding: 0 2;
}
#status-effort {
    color: $accent4;
    text-style: bold;
}
#status-context {
    color: $accent1;
}
#status-model {
    color: $accent2;
}
#status-workdir {
    color: $muted;
}

/* -- Loading indicator -- */
.loading {
    color: $accent1;
    text-style: bold italic;
    margin: 0 2;
    display: none;
}
.loading.visible {
    display: block;
}

/* -- Empty state / info blocks -- */
.info-block {
    color: $muted;
    text-align: center;
    margin: 2 0;
    padding: 2;
}

/* -- Panels -- */
.panel {
    padding: 2 4;
    background: $bg1;
}
.panel Label {
    color: $text;
}

/* -- Footer -- */
Footer {
    background: $bg2;
    color: $muted;
}
"""

# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------


class UserMessage(Static):
    """Un mensaje del usuario."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.add_class("user-msg")


class AssistantMessage(Vertical):
    """Respuesta del asistente con streaming -- envuelve un Markdown."""

    def __init__(self) -> None:
        super().__init__()
        self.add_class("assistant-msg")
        self._text = ""
        self._md: Markdown | None = None

    def compose(self) -> ComposeResult:
        self._md = Markdown("")
        yield self._md

    async def stream(self, text: str) -> None:
        self._text = text
        if self._md is not None:
            await self._md.update(text)

# ---------------------------------------------------------------------------
# ChatTab -- one per conversation
# ---------------------------------------------------------------------------


class ChatTab(Vertical):
    """Interfaz de chat completa: mensajes scrolleables + barra de entrada."""

    def __init__(
        self,
        model_key: str,
        tab_id: str,
        theme_key: str,
        workdir: str,
    ) -> None:
        super().__init__()
        self.model_key = model_key
        self.tab_id = tab_id
        self.theme_key = theme_key
        self.workdir = workdir
        self.proc: asyncio.subprocess.Process | None = None
        self.assistant_widget: AssistantMessage | None = None
        self.is_loading = False
        self.message_count = 0
        self.last_response = ""

    def compose(self) -> ComposeResult:
        model = AI_MODELS.get(self.model_key, AI_MODELS["claude"])
        logo = _build_logo(self.theme_key)
        with Vertical(classes="chat-wrap"):
            with VerticalScroll(classes="messages", id=f"msgs-{self.tab_id}"):
                yield Static(
                    logo + "\n\n"
                    f"[dim]{model['name']} | Escribe un mensaje o /help para comandos[/]",
                    classes="info-block",
                    id=f"empty-{self.tab_id}",
                )
            yield Label(" Procesando...", classes="loading", id=f"load-{self.tab_id}")
            with Horizontal(classes="input-bar"):
                yield Input(
                    placeholder="Mensaje o /comando...",
                    id=f"input-{self.tab_id}",
                )

# ---------------------------------------------------------------------------
# TermApp -- the main application
# ---------------------------------------------------------------------------


class TermApp(App):
    TITLE = "Term"
    CSS = APP_CSS

    BINDINGS = [
        Binding("ctrl+c", "quit", "Salir"),
        Binding("ctrl+l", "clear_tab", "Limpiar"),
        Binding("ctrl+t", "new_tab", "Nueva tab"),
        Binding("ctrl+w", "close_tab", "Cerrar tab"),
        Binding("ctrl+e", "cycle_effort", "Esfuerzo"),
        Binding("escape", "cancel", "Cancelar"),
    ]

    theme_key: reactive[str] = reactive("neon")
    effort: reactive[str] = reactive("high")
    current_model: reactive[str] = reactive("claude")
    tab_counter: var[int] = var(0)

    # ------------------------------------------------------------------ init

    def __init__(self, workdir: str = "", theme: str = "") -> None:
        self._context_tokens = 0
        self._max_context = 200_000
        self._tabs: dict[str, ChatTab] = {}
        self._apps = _detect_apps()
        self._active_panel = "chat"
        self._awaiting_model_selection: str | None = None
        self._pending_new_tab_name: str | None = None
        self._awaiting_permissions = False
        super().__init__()
        cfg = _load_config()
        self.workdir: str = workdir or cfg.get("workdir", str(Path.home()))
        self.theme_key = theme or cfg.get("theme", "neon")
        self.effort = cfg.get("effort", "high")
        self.current_model = cfg.get("model", "claude")
        self._permissions_granted: bool = cfg.get("permissions_granted", False)

    # ----------------------------------------------------- CSS variables (COMPLETE)

    def get_css_variables(self) -> dict[str, str]:
        t = THEMES.get(self.theme_key, THEMES["neon"])
        bg1, bg2, bg3 = t["bg1"], t["bg2"], t["bg3"]
        brd = t["border"]
        a1, a2, a3, a4 = t["accent1"], t["accent2"], t["accent3"], t["accent4"]
        txt, mut = t["text"], t["muted"]

        return {
            # Core
            "background": bg1, "foreground": txt,
            "panel": bg2, "surface": bg2,
            "primary": a1, "secondary": a2, "accent": a3,
            "warning": a4, "error": a2, "success": a3,
            "boost": bg3,
            "border": brd, "border-blurred": brd,
            # Foreground variants
            "foreground-darken-1": mut, "foreground-muted": mut,
            # Panel variants
            "panel-darken-1": bg1, "panel-darken-2": bg1, "panel-lighten-1": bg3,
            # Surface variants
            "surface-darken-1": bg1,
            "surface-lighten-1": bg3, "surface-lighten-2": bg3, "surface-lighten-3": bg3,
            # Primary variants
            "primary-darken-2": a1, "primary-darken-3": a1,
            "primary-lighten-3": a1, "primary-muted": mut,
            # Accent variants
            "accent-darken-1": a3, "accent-muted": mut,
            # Error variants
            "error-darken-1": a2, "error-darken-2": a2,
            "error-darken-3": a2, "error-lighten-2": a2, "error-muted": mut,
            # Success variants
            "success-darken-2": a3, "success-darken-3": a3,
            "success-lighten-1": a3, "success-lighten-2": a3, "success-muted": mut,
            # Warning variants
            "warning-darken-1": a4, "warning-darken-2": a4,
            "warning-darken-3": a4, "warning-lighten-2": a4,
            "warning-muted": mut, "warning-text": bg1,
            # Secondary
            "secondary-muted": mut,
            # Screen selection
            "screen-selection-background": a1, "screen-selection-foreground": bg1,
            # Input cursor
            "input-cursor-background": a1, "input-cursor-foreground": bg1,
            "input-cursor-text-style": "bold",
            "input-selection-background": a1, "input-selection-foreground": bg1,
            # Block cursor
            "block-cursor-background": a1, "block-cursor-foreground": bg1,
            "block-cursor-text-style": "bold",
            "block-cursor-blurred-background": mut,
            "block-cursor-blurred-foreground": txt,
            "block-cursor-blurred-text-style": "none",
            "block-hover-background": bg3,
            # Scrollbar
            "scrollbar": brd, "scrollbar-hover": a1, "scrollbar-active": a1,
            "scrollbar-background": bg1,
            "scrollbar-background-hover": bg1,
            "scrollbar-background-active": bg1,
            "scrollbar-corner-color": bg1,
            # Footer
            "footer-background": bg2, "footer-foreground": mut,
            "footer-key-background": bg3, "footer-key-foreground": a1,
            "footer-description-background": bg2,
            "footer-description-foreground": mut,
            "footer-item-background": bg2,
            # Button
            "button-foreground": txt, "button-color-foreground": txt,
            "button-focus-text-style": "bold",
            # Link
            "link-background": "transparent", "link-background-hover": bg3,
            "link-color": a1, "link-color-hover": a1,
            "link-style": "underline", "link-style-hover": "bold underline",
            # Text semantic colours
            "text": txt, "text-muted": mut, "text-disabled": mut,
            "text-accent": a1, "text-primary": a1, "text-secondary": a2,
            "text-success": a3, "text-warning": a4, "text-error": a2,
            # ANSI
            "ansi-background": bg1, "ansi-foreground": txt,
            # Markdown headings
            "markdown-h1-color": a2, "markdown-h1-background": "transparent",
            "markdown-h1-text-style": "bold",
            "markdown-h2-color": a2, "markdown-h2-background": "transparent",
            "markdown-h2-text-style": "bold",
            "markdown-h3-color": a1, "markdown-h3-background": "transparent",
            "markdown-h3-text-style": "bold",
            "markdown-h4-color": a1, "markdown-h4-background": "transparent",
            "markdown-h4-text-style": "bold",
            "markdown-h5-color": txt, "markdown-h5-background": "transparent",
            "markdown-h5-text-style": "bold",
            "markdown-h6-color": mut, "markdown-h6-background": "transparent",
            "markdown-h6-text-style": "bold",
            # Custom variables used in CSS
            "bg1": bg1, "bg2": bg2, "bg3": bg3,
            "accent1": a1, "accent2": a2, "accent3": a3, "accent4": a4,
            "muted": mut,
        }

    # ------------------------------------------------------------ compose

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="nav"):
                yield Label("[bold]TERM[/]", id="nav-title")
                yield Button("Chat", classes="nav-btn -active", id="nav-chat")
                yield Button("Ajustes", classes="nav-btn", id="nav-settings")
                yield Button("Apps", classes="nav-btn", id="nav-apps")
                yield Button("Herramientas", classes="nav-btn", id="nav-tools")
                yield Button("Ayuda", classes="nav-btn", id="nav-help")
            with Vertical(id="main"):
                with TabbedContent(id="main-tabs"):
                    tab_id = self._next_tab_id()
                    chat = ChatTab(
                        self.current_model, tab_id, self.theme_key, self.workdir,
                    )
                    self._tabs[tab_id] = chat
                    with TabPane("Chat", id=f"pane-{tab_id}"):
                        yield chat
        yield Horizontal(
            Label("", id="status-effort"),
            Label("  ", id="status-sep1"),
            Label("", id="status-context"),
            Label("  ", id="status-sep2"),
            Label("", id="status-model"),
            Label("  ", id="status-sep3"),
            Label("", id="status-workdir"),
            id="status-bar",
        )
        yield Footer()

    # ------------------------------------------------------------ lifecycle

    async def on_mount(self) -> None:
        self._refresh_status()
        if not self._permissions_granted:
            # Schedule permissions dialog after mount completes
            self.set_timer(0.1, self._show_permissions_dialog_deferred)
        else:
            try:
                first = next(iter(self._tabs.values()))
                self.query_one(f"#input-{first.tab_id}", Input).focus()
            except (NoMatches, StopIteration):
                pass

    def _show_permissions_dialog_deferred(self) -> None:
        """Schedule the async permissions dialog from a sync timer callback."""
        self.run_worker(self._show_permissions_dialog(), exclusive=True)

    async def _show_permissions_dialog(self) -> None:
        self._awaiting_permissions = True
        first_tab = next(iter(self._tabs.values()), None)
        if not first_tab:
            return
        try:
            msgs = self.query_one(f"#msgs-{first_tab.tab_id}", VerticalScroll)
            try:
                self.query_one(f"#empty-{first_tab.tab_id}").remove()
            except NoMatches:
                pass
            perm_text = (
                "[bold]Term necesita permisos para funcionar correctamente.[/]\n\n"
                "Al aceptar, Term podra:\n\n"
                "  [bold]Aplicaciones[/]     Abrir y controlar apps (Safari, Spotify, etc.)\n"
                "  [bold]Archivos[/]         Leer y escribir archivos en tu directorio de trabajo\n"
                "  [bold]Sistema[/]          Ajustar volumen, ejecutar comandos shell\n"
                "  [bold]Configuracion[/]    Guardar preferencias en ~/.config/term/\n"
                "  [bold]Red[/]              Conectar con la IA via OAuth\n\n"
                "Todos los comandos se ejecutan localmente en tu maquina.\n"
                "Term usa tu autenticacion OAuth existente.\n\n"
                "[bold]Aceptar permisos? (s/n)[/]"
            )
            await msgs.mount(Static(perm_text, classes="info-block", id="perm-dialog"))
            msgs.scroll_end(animate=False)
        except NoMatches:
            pass

    # ------------------------------------------------------------ theme watcher

    def watch_theme_key(self, value: str) -> None:
        """Force CSS variable re-evaluation when theme changes."""
        if not self.is_running:
            return
        self._refresh_status()
        self.call_later(self._apply_theme)

    def _apply_theme(self) -> None:
        """Re-parse stylesheet with updated CSS variables."""
        try:
            self.stylesheet.reparse()
        except Exception:
            pass
        self.refresh(layout=True)
        try:
            self.screen.refresh(layout=True)
        except Exception:
            pass

    # ------------------------------------------------------------ helpers

    def _next_tab_id(self) -> str:
        self.tab_counter += 1
        return f"chat{self.tab_counter}"

    def _refresh_status(self) -> None:
        pct = min(100, int(self._context_tokens / self._max_context * 100))
        bar_len = 15
        filled = int(pct / 100 * bar_len)
        bar = ">" * filled + "-" * (bar_len - filled)
        try:
            self.query_one("#status-effort", Label).update(
                f"[bold]Esfuerzo:[/] {self.effort}"
            )
            self.query_one("#status-context", Label).update(
                f"[bold]Contexto:[/] [{bar}] {pct}% ({self._context_tokens:,}/{self._max_context:,})"
            )
            model_name = AI_MODELS.get(self.current_model, AI_MODELS["claude"])["name"]
            self.query_one("#status-model", Label).update(
                f"[bold]Modelo:[/] {model_name}"
            )
            wd = self.workdir
            if len(wd) > 30:
                wd = "..." + wd[-27:]
            self.query_one("#status-workdir", Label).update(f"[bold]Dir:[/] {wd}")
        except NoMatches:
            pass

    def _set_nav_active(self, panel: str) -> None:
        self._active_panel = panel
        for suffix in ("chat", "settings", "apps", "tools", "help"):
            try:
                btn = self.query_one(f"#nav-{suffix}", Button)
                if suffix == panel:
                    btn.add_class("-active")
                else:
                    btn.remove_class("-active")
            except NoMatches:
                pass

    def _persist_config(self) -> None:
        _save_config({
            "theme": self.theme_key,
            "workdir": self.workdir,
            "effort": self.effort,
            "model": self.current_model,
            "permissions_granted": self._permissions_granted,
        })

    def _active_tab_id(self) -> str | None:
        """Return the tab_id of the currently active chat pane, or None."""
        try:
            tc = self.query_one("#main-tabs", TabbedContent)
            active = tc.active
            if active and active.startswith("pane-chat"):
                return active.replace("pane-", "")
        except NoMatches:
            pass
        return None

    # ------------------------------------------------------------ panel switching

    async def _show_panel(self, panel: str) -> None:
        self._set_nav_active(panel)
        tc = self.query_one("#main-tabs", TabbedContent)

        if panel == "chat":
            for tid in self._tabs:
                tc.active = f"pane-{tid}"
                break
            return

        pane_id = f"pane-{panel}"
        try:
            await tc.remove_pane(pane_id)
        except Exception:
            pass

        pane = TabPane(panel.capitalize(), id=pane_id)
        await tc.add_pane(pane)
        tc.active = pane_id

        if panel == "settings":
            theme_name = THEMES[self.theme_key]["name"]
            model_name = AI_MODELS.get(self.current_model, AI_MODELS["claude"])["name"]
            content = (
                f"[bold]Ajustes[/]\n\n"
                f"Tema: [bold]{theme_name}[/]\n"
                f"  Disponibles: {', '.join(THEMES.keys())}\n"
                f"  Cambiar: [bold]/theme <nombre>[/]\n\n"
                f"Modelo: [bold]{model_name}[/]\n"
                f"  Disponibles: {', '.join(AI_MODELS.keys())}\n"
                f"  Cambiar: [bold]/model <nombre>[/]\n\n"
                f"Esfuerzo: [bold]{self.effort}[/]\n"
                f"  Niveles: {', '.join(EFFORT_LEVELS)}\n"
                f"  Cambiar: [bold]/effort <nivel>[/]\n\n"
                f"Directorio: [bold]{self.workdir}[/]\n"
                f"  Cambiar: [bold]/workdir <ruta>[/]\n\n"
                f"[bold]/save[/] para guardar ajustes en disco"
            )
            await pane.mount(Static(content, classes="panel"))

        elif panel == "apps":
            cats: dict[str, list[dict]] = {}
            for app in self._apps:
                cats.setdefault(app["category"], []).append(app)
            lines = ["[bold]Aplicaciones CLI instaladas[/]\n"]
            for cat, items in cats.items():
                lines.append(f"\n[bold]{cat}[/]")
                for it in items:
                    lines.append(f"  {it['name']} [dim]({it['cmd']})[/]")
            lines.append(
                "\n[dim]Tambien puedes pedir en el chat: 'abrir Safari', "
                "'pon musica en Spotify', etc.[/]"
            )
            await pane.mount(Static("\n".join(lines), classes="panel"))

        elif panel == "tools":
            checks = [
                ("Claude CLI", "claude", "IA principal"),
                ("Git", "git", "Control de versiones"),
                ("Node.js", "node", "Runtime JS"),
                ("Python", "python3", "Runtime Python"),
                ("Docker", "docker", "Contenedores"),
                ("osascript", "osascript", "Control del sistema macOS"),
            ]
            lines = ["[bold]Herramientas conectadas[/]\n"]
            for name, cmd, desc in checks:
                found = shutil.which(cmd) is not None
                marker = "[green bold]OK[/]" if found else "[red]NO[/]"
                lines.append(f"  {marker} [bold]{name}[/] - {desc}")
            await pane.mount(Static("\n".join(lines), classes="panel"))

        elif panel == "help":
            models_info = []
            for k, m in AI_MODELS.items():
                connected = shutil.which(m["cmd"][0]) is not None
                status = "[green]conectado[/]" if connected else "[red]desconectado[/]"
                models_info.append(f"  [bold]{m['name']}[/] ({k}) {status}")

            lines = [
                _build_logo(self.theme_key),
                "",
                "[bold]Term[/] -- TUI con IA",
                "",
                "[bold]Que es Term?[/]",
                "  Una TUI que conecta con modelos de IA via OAuth CLI.",
                "  Chatea, controla tu Mac, abre apps, cambia musica,",
                "  y mas -- todo desde tu terminal.",
                "",
                "[bold]Modelos disponibles:[/]",
                *models_info,
                "",
                "[bold]Comandos:[/]",
            ]
            for cmd, desc in COMMANDS_HELP.items():
                lines.append(f"  [bold]{cmd:28s}[/] {desc}")
            lines.append("")
            lines.append("[bold]Atajos de teclado:[/]")
            for key, desc in SHORTCUTS_HELP.items():
                lines.append(f"  [bold]{key:28s}[/] {desc}")
            lines.extend([
                "",
                "[bold]Ejemplos de control del sistema:[/]",
                "  'abrir Safari'",
                "  'siguiente cancion en Spotify'",
                "  'pon el volumen a 50'",
                "  'abre la terminal'",
                "",
                f"[dim]Config: {CONFIG_PATH}[/]",
            ])
            await pane.mount(Static("\n".join(lines), classes="panel"))

    def _show_panel_sync(self, panel: str) -> None:
        self.run_worker(self._show_panel(panel), exclusive=True)

    # ------------------------------------------------------------ nav buttons

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        mapping = {
            "nav-chat": "chat",
            "nav-settings": "settings",
            "nav-apps": "apps",
            "nav-tools": "tools",
            "nav-help": "help",
        }
        panel = mapping.get(bid)
        if panel:
            self._show_panel_sync(panel)

    # ------------------------------------------------------------ input handler

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        iid = event.input.id or ""
        if not iid.startswith("input-chat"):
            return

        raw = event.value
        text = raw.strip()
        if not text:
            return

        tab_id = iid.replace("input-", "")

        # Permissions dialog response
        if self._awaiting_permissions:
            event.input.value = ""
            self._awaiting_permissions = False
            try:
                self.query_one("#perm-dialog").remove()
            except NoMatches:
                pass
            if text.lower() in ("s", "si", "y", "yes", "1"):
                self._permissions_granted = True
                cfg = _load_config()
                cfg["permissions_granted"] = True
                _save_config(cfg)
                self.notify("Permisos concedidos", timeout=2)
                first_tab = next(iter(self._tabs.values()), None)
                if first_tab:
                    try:
                        msgs = self.query_one(f"#msgs-{first_tab.tab_id}", VerticalScroll)
                        logo = _build_logo(self.theme_key)
                        model = AI_MODELS.get(first_tab.model_key, AI_MODELS["claude"])
                        await msgs.mount(Static(
                            logo + "\n\n"
                            f"[dim]{model['name']} | Escribe un mensaje o /help para comandos[/]",
                            classes="info-block",
                        ))
                    except NoMatches:
                        pass
            else:
                self.notify("Permisos denegados -- funciones de sistema desactivadas", timeout=3)
            return

        # Model selection flow for /new
        if self._awaiting_model_selection == tab_id:
            event.input.value = ""
            self._awaiting_model_selection = None
            try:
                self.query_one("#model-selector").remove()
            except NoMatches:
                pass
            model_keys = list(AI_MODELS.keys())
            selected: str | None = None
            if text.isdigit() and 1 <= int(text) <= len(model_keys):
                selected = model_keys[int(text) - 1]
            elif text in AI_MODELS:
                selected = text
            else:
                self.notify(f"Modelo invalido: {text}", timeout=2)
                return
            await self._create_tab(self._pending_new_tab_name, selected)
            self._pending_new_tab_name = None
            return

        chat = self._tabs.get(tab_id)
        if chat is None or chat.is_loading:
            return

        event.input.value = ""

        # Bare "/" shows command list
        if text == "/":
            lines = ["[bold]Comandos disponibles:[/]\n"]
            for c, d in COMMANDS_HELP.items():
                lines.append(f"  [bold]{c:28s}[/] {d}")
            try:
                msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                await msgs.mount(Static("\n".join(lines), classes="info-block"))
                msgs.scroll_end(animate=False)
            except NoMatches:
                pass
            return

        if text.startswith("/"):
            await self._handle_command(text, tab_id)
            return

        # Remove empty-state placeholder
        try:
            self.query_one(f"#empty-{tab_id}").remove()
        except NoMatches:
            pass

        # Mount user message
        try:
            msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
        except NoMatches:
            return
        await msgs.mount(UserMessage(text))

        # Mount assistant placeholder
        assistant = AssistantMessage()
        await msgs.mount(assistant)
        chat.assistant_widget = assistant
        chat.message_count += 1
        msgs.scroll_end(animate=False)

        chat.is_loading = True
        try:
            self.query_one(f"#load-{tab_id}", Label).add_class("visible")
        except NoMatches:
            pass

        self._run_ai(chat, text)

    # ------------------------------------------------------------ slash commands

    async def _handle_command(self, text: str, tab_id: str) -> None:
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/theme":
            if arg in THEMES:
                self.theme_key = arg
                self.notify(f"Tema: {THEMES[arg]['name']}", timeout=1)
            else:
                self.notify(f"Temas: {', '.join(THEMES.keys())}", timeout=3)

        elif cmd == "/effort":
            if arg in EFFORT_LEVELS:
                self.effort = arg
                self._refresh_status()
                self.notify(f"Esfuerzo: {arg}", timeout=1)
            else:
                self.notify(f"Niveles: {', '.join(EFFORT_LEVELS)}", timeout=2)

        elif cmd == "/model":
            if arg in AI_MODELS:
                self.current_model = arg
                chat = self._tabs.get(tab_id)
                if chat:
                    chat.model_key = arg
                self._refresh_status()
                self.notify(f"Modelo: {AI_MODELS[arg]['name']}", timeout=1)
            else:
                self.notify(f"Modelos: {', '.join(AI_MODELS.keys())}", timeout=2)

        elif cmd == "/name":
            if arg:
                try:
                    tc = self.query_one("#main-tabs", TabbedContent)
                    tab = tc.get_tab(f"pane-{tab_id}")
                    tab.label = arg
                except Exception:
                    pass

        elif cmd == "/workdir":
            if arg:
                expanded = os.path.expanduser(arg)
                if os.path.isdir(expanded):
                    self.workdir = expanded
                    chat = self._tabs.get(tab_id)
                    if chat:
                        chat.workdir = expanded
                    self._refresh_status()
                    self.notify(f"Dir: {expanded}", timeout=1)
                else:
                    self.notify(f"No encontrado: {arg}", timeout=2)

        elif cmd == "/new":
            tokens = arg.split() if arg else []
            name: str | None = None
            model: str | None = None
            for tok in tokens:
                if tok in AI_MODELS:
                    model = tok
                elif name is None:
                    name = tok
                else:
                    name += " " + tok
            if model:
                await self._create_tab(name, model)
            else:
                self._pending_new_tab_name = name
                items = []
                for i, (k, m) in enumerate(AI_MODELS.items(), 1):
                    connected = shutil.which(m["cmd"][0]) is not None
                    status = "[green]conectado[/]" if connected else "[red]desconectado[/]"
                    items.append(
                        f"  [bold]{i}[/]) [bold]{m['name']}[/] ({k}) {status}"
                    )
                try:
                    msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                    await msgs.mount(Static(
                        "[bold]Selecciona modelo para la nueva tab:[/]\n\n"
                        + "\n".join(items)
                        + f"\n\n[dim]Escribe el numero (1-{len(AI_MODELS)}) "
                        "o el nombre del modelo[/]",
                        classes="info-block",
                        id="model-selector",
                    ))
                    msgs.scroll_end(animate=False)
                except NoMatches:
                    pass
                self._awaiting_model_selection = tab_id

        elif cmd == "/close":
            await self.action_close_tab()

        elif cmd == "/clear":
            self.action_clear_tab()

        elif cmd == "/save":
            self._persist_config()
            self.notify("Configuracion guardada", timeout=2)

        elif cmd == "/help":
            self._show_panel_sync("help")

        elif cmd == "/apps":
            self._show_panel_sync("apps")

        elif cmd == "/tools":
            self._show_panel_sync("tools")

        elif cmd == "/settings":
            self._show_panel_sync("settings")

        elif cmd == "/about":
            self.notify(f"Term v{VERSION}", timeout=3)

        elif cmd == "/models":
            lines = ["[bold]Modelos disponibles:[/]\n"]
            for i, (k, m) in enumerate(AI_MODELS.items(), 1):
                connected = shutil.which(m["cmd"][0]) is not None
                status = "[green]conectado[/]" if connected else "[red]desconectado[/]"
                current = " [bold cyan]<< activo[/]" if k == self.current_model else ""
                lines.append(
                    f"  {i}) [bold]{m['name']}[/] ({k}) {status}{current}"
                )
            try:
                msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                await msgs.mount(Static("\n".join(lines), classes="info-block"))
                msgs.scroll_end(animate=False)
            except NoMatches:
                pass

        elif cmd == "/themes":
            lines = ["[bold]Temas disponibles:[/]\n"]
            for k, t in THEMES.items():
                current = " [bold cyan]<< activo[/]" if k == self.theme_key else ""
                lines.append(f"  [bold]{t['name']}[/] ({k}){current}")
            try:
                msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                await msgs.mount(Static("\n".join(lines), classes="info-block"))
                msgs.scroll_end(animate=False)
            except NoMatches:
                pass

        elif cmd == "/status":
            self.notify(
                f"Tema: {THEMES[self.theme_key]['name']} | "
                f"Modelo: {AI_MODELS[self.current_model]['name']} | "
                f"Esfuerzo: {self.effort} | "
                f"Dir: {self.workdir}",
                timeout=5,
            )

        elif cmd == "/reset":
            self._context_tokens = 0
            self._refresh_status()
            self.notify("Contexto reiniciado a 0", timeout=1)

        elif cmd == "/version":
            self.notify(f"Term v{VERSION}", timeout=2)

        elif cmd == "/open":
            if arg:
                try:
                    subprocess.Popen(["open", "-a", arg])
                    self.notify(f"Abriendo {arg}...", timeout=1)
                except Exception as e:
                    self.notify(f"Error: {e}", timeout=2)
            else:
                self.notify("Uso: /open <nombre de app>", timeout=2)

        elif cmd == "/run":
            if arg:
                try:
                    result = subprocess.run(
                        arg,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10,
                        cwd=self.workdir,
                    )
                    output = result.stdout or result.stderr or "(sin salida)"
                    try:
                        msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                        await msgs.mount(Static(
                            f"[dim]$ {arg}[/]\n\n{output.strip()}",
                            classes="info-block",
                        ))
                        msgs.scroll_end(animate=False)
                    except NoMatches:
                        pass
                except subprocess.TimeoutExpired:
                    self.notify("Comando agotado (10s)", timeout=2)
                except Exception as e:
                    self.notify(f"Error: {e}", timeout=2)
            else:
                self.notify("Uso: /run <comando>", timeout=2)

        elif cmd == "/volume":
            if arg and arg.isdigit() and 0 <= int(arg) <= 100:
                subprocess.run(
                    ["osascript", "-e", f"set volume output volume {arg}"],
                    capture_output=True,
                )
                self.notify(f"Volumen: {arg}%", timeout=1)
            else:
                self.notify("Uso: /volume <0-100>", timeout=2)

        elif cmd == "/play":
            subprocess.run(
                ["osascript", "-e", 'tell application "Spotify" to playpause'],
                capture_output=True,
            )
            self.notify("Play/Pausa", timeout=1)

        elif cmd == "/next":
            subprocess.run(
                ["osascript", "-e", 'tell application "Spotify" to next track'],
                capture_output=True,
            )
            self.notify("Siguiente cancion", timeout=1)

        elif cmd == "/prev":
            subprocess.run(
                ["osascript", "-e", 'tell application "Spotify" to previous track'],
                capture_output=True,
            )
            self.notify("Cancion anterior", timeout=1)

        elif cmd == "/copy":
            chat = self._tabs.get(tab_id)
            if chat and chat.last_response:
                try:
                    subprocess.run(
                        ["pbcopy"],
                        input=chat.last_response.encode(),
                        check=True,
                    )
                    self.notify("Copiado al portapapeles", timeout=1)
                except Exception as e:
                    self.notify(f"Error al copiar: {e}", timeout=2)
            else:
                self.notify("No hay respuesta para copiar", timeout=2)

        elif cmd == "/history":
            chat = self._tabs.get(tab_id)
            count = chat.message_count if chat else 0
            self.notify(f"Mensajes en esta tab: {count}", timeout=2)

        elif cmd == "/export":
            chat = self._tabs.get(tab_id)
            if chat:
                export_dir = Path.home() / ".config" / "term" / "exports"
                export_dir.mkdir(parents=True, exist_ok=True)
                ts = time.strftime("%Y%m%d_%H%M%S")
                path = export_dir / f"chat_{ts}.txt"
                try:
                    msgs_area = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                    texts = []
                    for child in msgs_area.children:
                        if isinstance(child, UserMessage):
                            texts.append(f"[Usuario] {child.renderable}")
                        elif isinstance(child, AssistantMessage):
                            texts.append(f"[Asistente] {child._text}")
                        elif isinstance(child, Static):
                            texts.append(str(child.renderable))
                    path.write_text("\n\n".join(texts))
                    self.notify(f"Exportado a {path}", timeout=3)
                except Exception as e:
                    self.notify(f"Error al exportar: {e}", timeout=2)
            else:
                self.notify("No hay chat activo", timeout=2)

        elif cmd == "/compact":
            self.notify(
                "Consejo: conversaciones largas usan mas contexto. "
                "Usa /clear para empezar de nuevo, o /reset para reiniciar el contador.",
                timeout=5,
            )

        elif cmd == "/restart":
            self.exit()
            os.execv(sys.executable, [sys.executable, "-m", "term.app"])

        else:
            self.notify(f"Comando desconocido: {cmd}. Prueba /help", timeout=2)

    # ------------------------------------------------------------ tab management

    async def _create_tab(
        self, name: str | None = None, model_key: str | None = None,
    ) -> None:
        tab_id = self._next_tab_id()
        mk = model_key or self.current_model
        chat = ChatTab(mk, tab_id, self.theme_key, self.workdir)
        self._tabs[tab_id] = chat

        tab_name = name or f"Chat {len(self._tabs)}"
        tc = self.query_one("#main-tabs", TabbedContent)
        pane = TabPane(tab_name, id=f"pane-{tab_id}")
        await tc.add_pane(pane)
        await pane.mount(chat)
        tc.active = f"pane-{tab_id}"
        self._set_nav_active("chat")

        await asyncio.sleep(0.1)
        try:
            self.query_one(f"#input-{tab_id}", Input).focus()
        except NoMatches:
            pass

    async def action_new_tab(self) -> None:
        await self._create_tab()

    async def action_close_tab(self) -> None:
        if len(self._tabs) <= 1:
            self.notify("No se puede cerrar la ultima tab", timeout=1)
            return
        tc = self.query_one("#main-tabs", TabbedContent)
        active = tc.active
        if active and active.startswith("pane-chat"):
            tab_id = active.replace("pane-", "")
            chat = self._tabs.pop(tab_id, None)
            if chat and chat.proc:
                try:
                    chat.proc.kill()
                except ProcessLookupError:
                    pass
            await tc.remove_pane(active)
            # Rename last tab to "Chat" when only one remains
            if len(self._tabs) == 1:
                remaining_id = next(iter(self._tabs))
                try:
                    tab = tc.get_tab(f"pane-{remaining_id}")
                    tab.label = "Chat"
                except Exception:
                    pass

    def action_clear_tab(self) -> None:
        try:
            tc = self.query_one("#main-tabs", TabbedContent)
            active = tc.active
            if active and active.startswith("pane-chat"):
                tab_id = active.replace("pane-", "")
                self.query_one(f"#msgs-{tab_id}", VerticalScroll).remove_children()
        except NoMatches:
            pass

    async def action_cancel(self) -> None:
        try:
            tc = self.query_one("#main-tabs", TabbedContent)
            active = tc.active
            if active and active.startswith("pane-chat"):
                tab_id = active.replace("pane-", "")
                chat = self._tabs.get(tab_id)
                if chat and chat.proc:
                    try:
                        chat.proc.kill()
                    except ProcessLookupError:
                        pass
                    chat.proc = None
                    chat.is_loading = False
                    try:
                        self.query_one(f"#load-{tab_id}", Label).remove_class("visible")
                    except NoMatches:
                        pass
        except NoMatches:
            pass

    def action_cycle_effort(self) -> None:
        idx = EFFORT_LEVELS.index(self.effort) if self.effort in EFFORT_LEVELS else 2
        self.effort = EFFORT_LEVELS[(idx + 1) % len(EFFORT_LEVELS)]
        self._refresh_status()
        self.notify(f"Esfuerzo: {self.effort}", timeout=1)

    # ------------------------------------------------------------ AI execution

    @work(exclusive=False, thread=False)
    async def _run_ai(self, chat: ChatTab, prompt: str) -> None:
        model = AI_MODELS.get(chat.model_key, AI_MODELS["claude"])
        full_output = ""

        try:
            cmd_line = (
                model["cmd"]
                + [prompt]
                + model["args"]
                + ["--effort", self.effort]
                + ["--append-system-prompt", SYSTEM_CONTEXT]
            )

            chat.proc = await asyncio.create_subprocess_exec(
                *cmd_line,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=chat.workdir or self.workdir,
            )
            assert chat.proc.stdout is not None

            while True:
                chunk = await chat.proc.stdout.read(512)
                if not chunk:
                    break
                decoded = chunk.decode("utf-8", errors="replace")
                full_output += decoded
                self._context_tokens += len(decoded.split()) * 2
                if chat.assistant_widget is not None:
                    await chat.assistant_widget.stream(full_output)
                try:
                    self.query_one(
                        f"#msgs-{chat.tab_id}", VerticalScroll,
                    ).scroll_end(animate=False)
                except NoMatches:
                    pass
                self._refresh_status()

            await chat.proc.wait()

        except FileNotFoundError:
            full_output = (
                "Error: `claude` no encontrado.\n\n"
                "Instalar: `npm install -g @anthropic-ai/claude-code`\n"
                "Autenticar: `claude auth login`"
            )
            if chat.assistant_widget is not None:
                await chat.assistant_widget.stream(full_output)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if chat.assistant_widget is not None:
                await chat.assistant_widget.stream(
                    full_output + f"\n\nError: {exc}"
                )
        finally:
            chat.last_response = full_output
            chat.proc = None
            chat.is_loading = False
            chat.assistant_widget = None
            try:
                self.query_one(
                    f"#load-{chat.tab_id}", Label,
                ).remove_class("visible")
            except NoMatches:
                pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="term", description="Term -- TUI con IA",
    )
    parser.add_argument("--workdir", "-w", default="", help="Directorio de trabajo")
    parser.add_argument(
        "--theme", "-t", default="", choices=list(THEMES.keys()), help="Tema",
    )
    args = parser.parse_args()
    TermApp(workdir=args.workdir, theme=args.theme).run()


if __name__ == "__main__":
    main()
