"""Term -- Multi-AI TUI with tabs, themes, tools, and system control."""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import json
import time
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.reactive import reactive, var
from textual.widgets import (
    Footer,
    Input,
    Label,
    Markdown,
    Static,
    Button,
    TabbedContent,
    TabPane,
    ListView,
    ListItem,
)

# ── Logo ─────────────────────────────────────────────────────────────────────

_LOGO_LINES = [
    r" ████████╗ ███████╗ ██████╗  ███╗   ███╗",
    r" ╚══██╔══╝ ██╔════╝ ██╔══██╗ ████╗ ████║",
    r"    ██║    █████╗   ██████╔╝ ██╔████╔██║",
    r"    ██║    ██╔══╝   ██╔══██╗ ██║╚██╔╝██║",
    r"    ██║    ███████╗ ██║  ██║ ██║ ╚═╝ ██║",
    r"    ╚═╝    ╚══════╝ ╚═╝  ╚═╝ ╚═╝     ╚═╝",
]

# ── Themes ───────────────────────────────────────────────────────────────────

THEMES = {
    "neon": {
        "name": "Neon",
        "bg1": "#050508", "bg2": "#0c0c14", "bg3": "#14142a",
        "border": "#1e1e3a", "accent1": "#00e5ff", "accent2": "#ff00e5",
        "accent3": "#39ff14", "accent4": "#ff6600", "text": "#e0e0ff",
        "muted": "#444466",
        "grad": ["#b388ff","#9e8eff","#8a94ff","#759aff","#5fa0ff",
                 "#4aa6ff","#34acff","#1fb2ff","#0abcff","#00e5ff"],
    },
    "dracula": {
        "name": "Dracula",
        "bg1": "#1a1b26", "bg2": "#21222c", "bg3": "#343746",
        "border": "#44475a", "accent1": "#8be9fd", "accent2": "#ff79c6",
        "accent3": "#50fa7b", "accent4": "#ffb86c", "text": "#f8f8f2",
        "muted": "#6272a4",
        "grad": ["#bd93f9","#b094f9","#a395f9","#9696f9","#8997f9",
                 "#7c98f9","#7099f9","#639af9","#569bf9","#8be9fd"],
    },
    "monokai": {
        "name": "Monokai",
        "bg1": "#1a1a18", "bg2": "#1e1f1c", "bg3": "#3e3d32",
        "border": "#49483e", "accent1": "#66d9ef", "accent2": "#f92672",
        "accent3": "#a6e22e", "accent4": "#fd971f", "text": "#f8f8f2",
        "muted": "#75715e",
        "grad": ["#ae81ff","#a085f5","#9289eb","#848de1","#7691d7",
                 "#6895cd","#5a99c3","#4c9db9","#3ea1af","#66d9ef"],
    },
    "catppuccin": {
        "name": "Catppuccin",
        "bg1": "#11111b", "bg2": "#181825", "bg3": "#313244",
        "border": "#45475a", "accent1": "#89dceb", "accent2": "#f5c2e7",
        "accent3": "#a6e3a1", "accent4": "#fab387", "text": "#cdd6f4",
        "muted": "#585b70",
        "grad": ["#cba6f7","#c0a8f7","#b5aaf7","#aaacf7","#9faef7",
                 "#94b0f7","#89b2f7","#7eb4f7","#73b6f7","#89dceb"],
    },
    "gruvbox": {
        "name": "Gruvbox",
        "bg1": "#0d0e0f", "bg2": "#1d2021", "bg3": "#3c3836",
        "border": "#504945", "accent1": "#83a598", "accent2": "#d3869b",
        "accent3": "#b8bb26", "accent4": "#fe8019", "text": "#ebdbb2",
        "muted": "#665c54",
        "grad": ["#d3869b","#cd8a9d","#c78e9f","#c192a1","#bb96a3",
                 "#b59aa5","#af9ea7","#a9a2a9","#93a69b","#83a598"],
    },
    "tokyo": {
        "name": "Tokyo Night",
        "bg1": "#0f0f17", "bg2": "#16161e", "bg3": "#24283b",
        "border": "#3b4261", "accent1": "#7dcfff", "accent2": "#bb9af7",
        "accent3": "#9ece6a", "accent4": "#ff9e64", "text": "#c0caf5",
        "muted": "#565f89",
        "grad": ["#bb9af7","#b19ef7","#a7a2f7","#9da6f7","#93aaf7",
                 "#89aef7","#7fb2f7","#75b6f7","#6bbaf7","#7dcfff"],
    },
}

# ── Models ───────────────────────────────────────────────────────────────────

AI_MODELS = {
    "claude": {"name": "Claude", "cmd": ["claude","-p"], "args": ["--max-turns","15"]},
    "claude-opus": {"name": "Claude Opus", "cmd": ["claude","-p"], "args": ["--max-turns","15","--model","opus"]},
    "claude-haiku": {"name": "Claude Haiku", "cmd": ["claude","-p"], "args": ["--max-turns","15","--model","haiku"]},
}

EFFORT_LEVELS = ["low", "medium", "high", "max"]

# ── System prompt for PC control ─────────────────────────────────────────────

SYSTEM_CONTEXT = """You are Term, a terminal AI assistant. You can control this macOS computer.
When the user asks you to open apps, change songs, adjust volume, etc., use osascript/AppleScript.

Examples:
- Open Safari: osascript -e 'tell application "Safari" to activate'
- Play/pause Spotify: osascript -e 'tell application "Spotify" to playpause'
- Next song: osascript -e 'tell application "Spotify" to next track'
- Previous song: osascript -e 'tell application "Spotify" to previous track'
- Set volume: osascript -e 'set volume output volume 50'
- Open Finder: open ~/Desktop
- Open any app: open -a "App Name"
- Get current song: osascript -e 'tell application "Spotify" to name of current track'

You have full shell access. Execute commands directly. Be concise."""

# ── Commands ─────────────────────────────────────────────────────────────────

COMMANDS_HELP = {
    "/theme <name>":    "Cambiar tema (neon, dracula, monokai, catppuccin, gruvbox, tokyo)",
    "/effort <level>":  "Cambiar esfuerzo (low, medium, high, max)",
    "/model <name>":    "Cambiar modelo (claude, claude-opus, claude-haiku)",
    "/name <texto>":    "Renombrar la pestana activa",
    "/workdir <ruta>":  "Cambiar directorio de trabajo",
    "/new [nombre] [modelo]": "Nueva pestana (ej: /new MiChat claude-opus)",
    "/close":           "Cerrar pestana activa",
    "/clear":           "Limpiar chat",
    "/save":            "Guardar configuracion",
    "/help":            "Mostrar ayuda completa",
    "/apps":            "Ir al panel de apps",
    "/tools":           "Ir al panel de herramientas",
    "/settings":        "Ir al panel de configuracion",
    "/about":           "Info sobre Term",
    "/models":          "Listar modelos disponibles con estado",
    "/themes":          "Listar temas disponibles",
    "/status":          "Mostrar estado actual (tema, modelo, effort, workdir)",
    "/reset":           "Resetear contexto estimado a 0",
    "/version":         "Version de Term",
    "/open <app>":      "Abrir una aplicacion (ej: /open Safari)",
    "/run <comando>":   "Ejecutar comando shell y mostrar resultado",
    "/volume <0-100>":  "Ajustar volumen del sistema",
    "/play":            "Play/pause Spotify",
    "/next":            "Siguiente cancion Spotify",
    "/prev":            "Cancion anterior Spotify",
    "ctrl+t":           "Nueva pestana",
    "ctrl+w":           "Cerrar pestana",
    "ctrl+l":           "Limpiar chat",
    "ctrl+e":           "Ciclar effort",
    "escape":           "Cancelar generacion",
}

# ── Config ───────────────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".config" / "term" / "config.json"

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try: return json.loads(CONFIG_PATH.read_text())
        except Exception: pass
    return {"theme": "neon", "workdir": str(Path.home()), "effort": "high", "model": "claude"}

def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

# ── Apps ─────────────────────────────────────────────────────────────────────

def _find_apps() -> list[dict]:
    apps = []
    for cmd, name, cat in [
        ("vim","Vim","Editor"), ("nvim","Neovim","Editor"), ("nano","Nano","Editor"),
        ("htop","htop","Monitor"), ("btop","btop","Monitor"), ("top","top","Monitor"),
        ("python3","Python REPL","Dev"), ("node","Node.js REPL","Dev"),
        ("git","Git","Dev"), ("docker","Docker","Dev"), ("lazygit","LazyGit","Dev"),
        ("tmux","tmux","Terminal"), ("mc","Midnight Commander","Files"),
    ]:
        if shutil.which(cmd):
            apps.append({"cmd": cmd, "name": name, "category": cat})
    return apps

# ── Logo builder ─────────────────────────────────────────────────────────────

def build_logo(theme_key: str = "neon") -> str:
    grad = THEMES.get(theme_key, THEMES["neon"])["grad"]
    lines = []
    mx = max(len(l) for l in _LOGO_LINES)
    for line in _LOGO_LINES:
        colored = ""
        for i, ch in enumerate(line):
            if ch == " ":
                colored += " "
            else:
                p = int(i / max(mx, 1) * (len(grad) - 1))
                colored += f"[bold {grad[p]}]{ch}[/]"
        lines.append(colored)
    return "\n".join(lines)

# ── CSS (uses CSS variables for live theme switching) ────────────────────────

MAIN_CSS = """
Screen {
    background: $bg1;
}

/* ── Nav sidebar ── */
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

/* ── Main content ── */
#main {
    background: $bg1;
}

/* ── Tab bar ── */
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

/* ── Chat ── */
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

/* ── Input area ── */
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

/* ── Status bar ── */
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

/* ── Loading ── */
.loading {
    color: $accent1;
    text-style: bold italic;
    margin: 0 2;
    display: none;
}
.loading.visible {
    display: block;
}

/* ── Empty state ── */
.empty-state {
    color: $muted;
    text-align: center;
    margin: 2 0;
    padding: 2;
}

/* ── Panels ── */
.panel {
    padding: 2 4;
    background: $bg1;
}
.panel Label {
    color: $text;
}
.panel .section-title {
    color: $accent1;
    text-style: bold;
    margin: 1 0 1 0;
}
.panel ListView {
    background: $bg2;
    border: solid $border;
    margin: 1 0;
    height: auto;
    max-height: 20;
}
.panel ListItem {
    background: $bg2;
    color: $text;
    padding: 0 2;
}
.panel ListItem:hover {
    background: $bg3;
}
.panel ListItem.-highlight {
    background: $bg3;
    color: $accent1;
}
.panel .tool-item {
    background: $bg2;
    border: solid $border;
    padding: 1 2;
    margin: 0 0 1 0;
}
.panel Button {
    background: $bg3;
    color: $text;
    border: solid $border;
    margin: 0 1 1 0;
}
.panel Button:hover {
    border: solid $accent1;
    color: $accent1;
}
.panel Input {
    background: $bg3;
    color: $text;
    border: tall $border;
    margin: 0 0 1 0;
}
.panel Input:focus {
    border: tall $accent1;
}

Footer {
    background: $bg2;
    color: $muted;
}
"""

# ── Widgets ──────────────────────────────────────────────────────────────────

class UserMessage(Static):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.add_class("user-msg")

class AssistantMessage(Vertical):
    def __init__(self) -> None:
        super().__init__()
        self.add_class("assistant-msg")
        self._text = ""
        self._md: Markdown | None = None

    def compose(self) -> ComposeResult:
        self._md = Markdown("")
        yield self._md

    async def update_content(self, text: str) -> None:
        self._text = text
        if self._md is not None:
            await self._md.update(text)

# ── Chat tab ─────────────────────────────────────────────────────────────────

class ChatTab(Vertical):
    def __init__(self, model_key: str, tab_id: str, theme_key: str, workdir: str) -> None:
        super().__init__()
        self.model_key = model_key
        self.tab_id = tab_id
        self.theme_key = theme_key
        self.workdir = workdir
        self._proc: asyncio.subprocess.Process | None = None
        self._assistant_widget: AssistantMessage | None = None
        self._is_loading = False
        self._tokens_used = 0
        self._start_time = time.time()

    def compose(self) -> ComposeResult:
        model = AI_MODELS.get(self.model_key, AI_MODELS["claude"])
        logo = build_logo(self.theme_key)
        with Vertical(classes="chat-wrap"):
            with VerticalScroll(classes="messages", id=f"msgs-{self.tab_id}"):
                yield Static(
                    logo + "\n\n"
                    f"[dim]{model['name']} | Escribe un mensaje o /help para comandos[/]",
                    classes="empty-state",
                    id=f"empty-{self.tab_id}",
                )
            yield Label(" Procesando...", classes="loading", id=f"load-{self.tab_id}")
            with Horizontal(classes="input-bar"):
                yield Input(placeholder=f"Mensaje o /comando...", id=f"input-{self.tab_id}")

# ── Main App ─────────────────────────────────────────────────────────────────

class TermApp(App):
    TITLE = "Term"
    CSS = MAIN_CSS

    BINDINGS = [
        Binding("ctrl+c", "quit", "Salir"),
        Binding("ctrl+l", "clear_tab", "Limpiar"),
        Binding("ctrl+t", "new_tab", "Nueva tab"),
        Binding("ctrl+w", "close_tab", "Cerrar tab"),
        Binding("ctrl+e", "cycle_effort", "Effort"),
        Binding("escape", "cancel", "Cancelar"),
    ]

    theme_key: reactive[str] = reactive("neon")
    effort: reactive[str] = reactive("high")
    current_model: reactive[str] = reactive("claude")
    tab_counter: var[int] = var(0)

    def __init__(self, workdir: str = "", theme: str = "") -> None:
        super().__init__()
        cfg = load_config()
        self.workdir = workdir or cfg.get("workdir", str(Path.home()))
        self.theme_key = theme or cfg.get("theme", "neon")
        self.effort = cfg.get("effort", "high")
        self.current_model = cfg.get("model", "claude")
        self._chat_tabs: dict[str, ChatTab] = {}
        self._available_apps = _find_apps()
        self._active_panel = "chat"
        self._context_tokens = 0
        self._max_context = 200000
        self._awaiting_model_selection: str | None = None
        self._pending_new_tab_name: str | None = None

    def get_css_variables(self) -> dict[str, str]:
        t = THEMES.get(self.theme_key, THEMES["neon"])
        bg1, bg2, bg3 = t["bg1"], t["bg2"], t["bg3"]
        brd, a1, a2, a3, a4 = t["border"], t["accent1"], t["accent2"], t["accent3"], t["accent4"]
        txt, mut = t["text"], t["muted"]
        return {
            "background": bg1, "foreground": txt, "panel": bg2, "surface": bg2,
            "primary": a1, "secondary": a2, "accent": a3,
            "warning": a4, "error": a2, "success": a3, "boost": bg3,
            "border": brd, "border-blurred": brd,
            # Darken/lighten variants
            "foreground-darken-1": mut, "foreground-muted": mut,
            "panel-darken-1": bg1, "panel-darken-2": bg1, "panel-lighten-1": bg3,
            "surface-darken-1": bg1, "surface-lighten-1": bg3,
            "surface-lighten-2": bg3, "surface-lighten-3": bg3,
            "primary-darken-2": a1, "primary-darken-3": a1, "primary-lighten-3": a1,
            "accent-darken-1": a3,
            "error-darken-1": a2, "error-darken-2": a2, "error-darken-3": a2, "error-lighten-2": a2,
            "success-darken-2": a3, "success-darken-3": a3,
            "success-lighten-1": a3, "success-lighten-2": a3,
            "warning-darken-1": a4, "warning-darken-2": a4,
            "warning-darken-3": a4, "warning-lighten-2": a4, "warning-text": bg1,
            # Muted
            "primary-muted": mut, "secondary-muted": mut, "accent-muted": mut,
            "error-muted": mut, "success-muted": mut, "warning-muted": mut,
            # Screen
            "screen-selection-background": a1, "screen-selection-foreground": bg1,
            # Input
            "input-cursor-background": a1, "input-cursor-foreground": bg1,
            "input-cursor-text-style": "bold",
            "input-selection-background": a1, "input-selection-foreground": bg1,
            # Block cursor
            "block-cursor-background": a1, "block-cursor-foreground": bg1,
            "block-cursor-text-style": "bold",
            "block-cursor-blurred-background": mut, "block-cursor-blurred-foreground": txt,
            "block-cursor-blurred-text-style": "none", "block-hover-background": bg3,
            # Scrollbar
            "scrollbar": brd, "scrollbar-hover": a1, "scrollbar-active": a1,
            "scrollbar-background": bg1, "scrollbar-background-hover": bg1,
            "scrollbar-background-active": bg1, "scrollbar-corner-color": bg1,
            # Footer
            "footer-background": bg2, "footer-foreground": mut,
            "footer-key-background": bg3, "footer-key-foreground": a1,
            "footer-description-background": bg2, "footer-description-foreground": mut,
            "footer-item-background": bg2,
            # Button
            "button-foreground": txt, "button-color-foreground": txt,
            "button-focus-text-style": "bold",
            # Link
            "link-background": "transparent", "link-background-hover": bg3,
            "link-color": a1, "link-color-hover": a1,
            "link-style": "underline", "link-style-hover": "bold underline",
            # Text
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
            # Custom
            "bg1": bg1, "bg2": bg2, "bg3": bg3,
            "accent1": a1, "accent2": a2, "accent3": a3, "accent4": a4,
            "muted": mut,
        }

    def compose(self) -> ComposeResult:
        with Horizontal():
            # Nav sidebar
            with Vertical(id="nav"):
                yield Label("[bold]TERM[/]", id="nav-title")
                yield Button("Chat", classes="nav-btn -active", id="nav-chat")
                yield Button("Settings", classes="nav-btn", id="nav-settings")
                yield Button("Apps", classes="nav-btn", id="nav-apps")
                yield Button("Tools", classes="nav-btn", id="nav-tools")
                yield Button("Help", classes="nav-btn", id="nav-help")
            # Main area
            with Vertical(id="main"):
                with TabbedContent(id="main-tabs"):
                    tab_id = self._make_tab_id()
                    chat = ChatTab(self.current_model, tab_id, self.theme_key, self.workdir)
                    self._chat_tabs[tab_id] = chat
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

    def _make_tab_id(self) -> str:
        self.tab_counter += 1
        return f"chat{self.tab_counter}"

    def on_mount(self) -> None:
        self._update_status()
        try:
            first = list(self._chat_tabs.values())[0]
            self.query_one(f"#input-{first.tab_id}", Input).focus()
        except (NoMatches, IndexError):
            pass

    def _update_status(self) -> None:
        pct = min(100, int(self._context_tokens / self._max_context * 100))
        bar_len = 15
        filled = int(pct / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        try:
            self.query_one("#status-effort", Label).update(
                f"[bold]Effort:[/] {self.effort}"
            )
            self.query_one("#status-context", Label).update(
                f"[bold]Contexto:[/] {bar} {pct}% ({self._context_tokens:,}/{self._max_context:,})"
            )
            self.query_one("#status-model", Label).update(
                f"[bold]Modelo:[/] {AI_MODELS.get(self.current_model, AI_MODELS['claude'])['name']}"
            )
            wd = self.workdir
            if len(wd) > 30:
                wd = "..." + wd[-27:]
            self.query_one("#status-workdir", Label).update(f"[bold]Dir:[/] {wd}")
        except NoMatches:
            pass

    # ── Nav panel switching ──

    def _set_nav_active(self, panel: str) -> None:
        self._active_panel = panel
        for btn_id in ["nav-chat", "nav-settings", "nav-apps", "nav-tools", "nav-help"]:
            try:
                btn = self.query_one(f"#{btn_id}", Button)
                if btn_id == f"nav-{panel}":
                    btn.add_class("-active")
                else:
                    btn.remove_class("-active")
            except NoMatches:
                pass

    async def _show_panel(self, panel: str) -> None:
        self._set_nav_active(panel)
        tabs = self.query_one("#main-tabs", TabbedContent)

        if panel == "chat":
            # Switch to first chat tab
            for tid in self._chat_tabs:
                tabs.active = f"pane-{tid}"
                break
            return

        pane_id = f"pane-{panel}"
        # Remove old panel pane if exists
        try:
            await tabs.remove_pane(pane_id)
        except Exception:
            pass

        pane = TabPane(panel.capitalize(), id=pane_id)
        await tabs.add_pane(pane)
        tabs.active = pane_id

        # Mount content directly
        if panel == "settings":
            content = (
                f"[bold]Configuracion[/]\n\n"
                f"Tema actual: [bold]{THEMES[self.theme_key]['name']}[/]\n"
                f"Temas: {', '.join(THEMES.keys())}\n"
                f"Usa [bold]/theme <nombre>[/] para cambiar\n\n"
                f"Modelo: [bold]{AI_MODELS[self.current_model]['name']}[/]\n"
                f"Usa [bold]/model <nombre>[/] para cambiar\n\n"
                f"Effort: [bold]{self.effort}[/]\n"
                f"Usa [bold]/effort <level>[/] para cambiar\n\n"
                f"Workdir: [bold]{self.workdir}[/]\n"
                f"Usa [bold]/workdir <ruta>[/] para cambiar\n\n"
                f"[bold]/save[/] para guardar configuracion"
            )
            await pane.mount(Static(content, classes="panel"))

        elif panel == "apps":
            categories: dict[str, list] = {}
            for app in self._available_apps:
                categories.setdefault(app["category"], []).append(app)
            lines = ["[bold]Aplicaciones disponibles[/]\n"]
            for cat, items in categories.items():
                lines.append(f"\n[bold]{cat}[/]")
                for item in items:
                    lines.append(f"  {item['name']} [dim]({item['cmd']})[/]")
            lines.append("\n[dim]Tambien puedes pedir en el chat: 'abre Safari', 'pon musica en Spotify', etc.[/]")
            await pane.mount(Static("\n".join(lines), classes="panel"))

        elif panel == "tools":
            lines = ["[bold]Herramientas conectadas[/]\n"]
            for name, cmd, desc in [
                ("Claude CLI","claude","IA principal"),
                ("Git","git","Control de versiones"),
                ("Node.js","node","Runtime JS"),
                ("Python","python3","Runtime Python"),
                ("Docker","docker","Contenedores"),
                ("osascript","osascript","Control del sistema macOS"),
            ]:
                found = shutil.which(cmd) is not None
                s = "[green bold]OK[/]" if found else "[red]NO[/]"
                lines.append(f"  {s} [bold]{name}[/] - {desc}")
            await pane.mount(Static("\n".join(lines), classes="panel"))

        elif panel == "help":
            models_info = []
            for k, m in AI_MODELS.items():
                connected = shutil.which(m["cmd"][0]) is not None
                status = "[green]conectado[/]" if connected else "[red]desconectado[/]"
                models_info.append(f"  [bold]{m['name']}[/] ({k}) {status}")

            lines = [
                build_logo(self.theme_key),
                "",
                "[bold]Term[/] -- Dashboard multi-IA para terminal",
                "",
                "[bold]Que es Term?[/]",
                "  Un TUI que conecta con Claude Code via OAuth CLI.",
                "  Puedes chatear, controlar tu Mac, abrir apps,",
                "  cambiar musica, y mas. Todo desde la terminal.",
                "",
                "[bold]Modelos disponibles:[/]",
                *models_info,
                "",
                "[bold]Comandos:[/]",
            ]
            for cmd, desc in COMMANDS_HELP.items():
                lines.append(f"  [bold]{cmd:28s}[/] {desc}")
            lines.extend([
                "",
                "[bold]Control del sistema:[/]",
                "  Pide cosas como:",
                "  'abre Safari'",
                "  'pon la siguiente cancion en Spotify'",
                "  'sube el volumen'",
                "  'abre la terminal'",
                "",
                f"[dim]Config: {CONFIG_PATH}[/]",
            ])
            await pane.mount(Static("\n".join(lines), classes="panel"))

    # ── Event handlers ──

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "nav-chat":
            self._show_panel_sync("chat")
        elif bid == "nav-settings":
            self._show_panel_sync("settings")
        elif bid == "nav-apps":
            self._show_panel_sync("apps")
        elif bid == "nav-tools":
            self._show_panel_sync("tools")
        elif bid == "nav-help":
            self._show_panel_sync("help")

    def _show_panel_sync(self, panel: str) -> None:
        self.run_worker(self._show_panel(panel), exclusive=True)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        input_id = event.input.id or ""
        if not input_id.startswith("input-chat"):
            return

        text = event.value.strip()
        if not text:
            return

        tab_id = input_id.replace("input-", "")

        # Handle model selection for /new
        if self._awaiting_model_selection == tab_id:
            event.input.value = ""
            self._awaiting_model_selection = None
            # Remove selector
            try:
                self.query_one("#model-selector").remove()
            except NoMatches:
                pass
            # Parse selection: number or model name
            model_keys = list(AI_MODELS.keys())
            selected = None
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

        chat = self._chat_tabs.get(tab_id)
        if chat is None or chat._is_loading:
            return

        event.input.value = ""

        # Handle commands
        if text == "/":
            # Show command list
            cmds_only = {k: v for k, v in COMMANDS_HELP.items() if k.startswith("/")}
            lines = ["[bold]Comandos disponibles:[/]\n"]
            for c, d in cmds_only.items():
                lines.append(f"  [bold]{c:28s}[/] {d}")
            try:
                msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                await msgs.mount(Static("\n".join(lines), classes="empty-state"))
                msgs.scroll_end(animate=False)
            except NoMatches:
                pass
            return
        if text.startswith("/"):
            await self._handle_command(text, tab_id)
            return

        # Remove empty state
        try:
            self.query_one(f"#empty-{tab_id}").remove()
        except NoMatches:
            pass

        # Add user msg
        msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
        await msgs.mount(UserMessage(text))

        # Add assistant placeholder
        assistant_w = AssistantMessage()
        await msgs.mount(assistant_w)
        chat._assistant_widget = assistant_w
        msgs.scroll_end(animate=False)

        chat._is_loading = True
        try:
            self.query_one(f"#load-{tab_id}", Label).add_class("visible")
        except NoMatches:
            pass

        self._run_ai(chat, text)

    # ── Commands ──

    async def _handle_command(self, text: str, tab_id: str) -> None:
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/theme":
            if arg in THEMES:
                self.theme_key = arg
                self.refresh_css()
                self.notify(f"Tema: {THEMES[arg]['name']}", timeout=1)
            else:
                self.notify(f"Temas: {', '.join(THEMES.keys())}", timeout=3)

        elif cmd == "/effort":
            if arg in EFFORT_LEVELS:
                self.effort = arg
                self._update_status()
                self.notify(f"Effort: {arg}", timeout=1)
            else:
                self.notify(f"Niveles: {', '.join(EFFORT_LEVELS)}", timeout=2)

        elif cmd == "/model":
            if arg in AI_MODELS:
                self.current_model = arg
                chat = self._chat_tabs.get(tab_id)
                if chat:
                    chat.model_key = arg
                self._update_status()
                self.notify(f"Modelo: {AI_MODELS[arg]['name']}", timeout=1)
            else:
                self.notify(f"Modelos: {', '.join(AI_MODELS.keys())}", timeout=2)

        elif cmd == "/name":
            if arg:
                tabs = self.query_one("#main-tabs", TabbedContent)
                try:
                    tab = tabs.get_tab(f"pane-{tab_id}")
                    tab.label = arg
                except Exception:
                    pass

        elif cmd == "/workdir":
            if arg:
                expanded = os.path.expanduser(arg)
                if os.path.isdir(expanded):
                    self.workdir = expanded
                    chat = self._chat_tabs.get(tab_id)
                    if chat:
                        chat.workdir = expanded
                    self._update_status()
                    self.notify(f"Dir: {expanded}", timeout=1)
                else:
                    self.notify(f"No existe: {arg}", timeout=2)

        elif cmd == "/new":
            # /new [nombre] [modelo]
            # Si no se pasa modelo, muestra selector
            parts2 = arg.split() if arg else []
            name = None
            model = None
            for p in parts2:
                if p in AI_MODELS:
                    model = p
                elif name is None:
                    name = p
                else:
                    name += " " + p
            if model:
                await self._create_tab(name, model)
            else:
                # Show model selector in chat
                self._pending_new_tab_name = name
                models_list = []
                for i, (k, m) in enumerate(AI_MODELS.items(), 1):
                    connected = shutil.which(m["cmd"][0]) is not None
                    status = "[green]conectado[/]" if connected else "[red]desconectado[/]"
                    models_list.append(f"  [bold]{i}[/]) [bold]{m['name']}[/] ({k}) {status}")
                try:
                    msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                    await msgs.mount(Static(
                        "[bold]Selecciona modelo para la nueva tab:[/]\n\n"
                        + "\n".join(models_list) +
                        "\n\n[dim]Escribe el numero (1-" + str(len(AI_MODELS)) + ") o el nombre del modelo[/]",
                        classes="empty-state",
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
            self._save_config()

        elif cmd == "/help":
            self._show_panel_sync("help")

        elif cmd == "/apps":
            self._show_panel_sync("apps")

        elif cmd == "/tools":
            self._show_panel_sync("tools")

        elif cmd == "/settings":
            self._show_panel_sync("settings")

        elif cmd == "/about":
            self.notify("Term v0.1.0 -- Dashboard multi-IA para terminal", timeout=3)

        elif cmd == "/models":
            lines = ["[bold]Modelos disponibles:[/]\n"]
            for i, (k, m) in enumerate(AI_MODELS.items(), 1):
                connected = shutil.which(m["cmd"][0]) is not None
                status = "[green]conectado[/]" if connected else "[red]desconectado[/]"
                current = " [bold cyan]<< activo[/]" if k == self.current_model else ""
                lines.append(f"  {i}) [bold]{m['name']}[/] ({k}) {status}{current}")
            try:
                msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                await msgs.mount(Static("\n".join(lines), classes="empty-state"))
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
                await msgs.mount(Static("\n".join(lines), classes="empty-state"))
                msgs.scroll_end(animate=False)
            except NoMatches:
                pass

        elif cmd == "/status":
            self.notify(
                f"Tema: {THEMES[self.theme_key]['name']} | "
                f"Modelo: {AI_MODELS[self.current_model]['name']} | "
                f"Effort: {self.effort} | "
                f"Dir: {self.workdir}",
                timeout=5,
            )

        elif cmd == "/reset":
            self._context_tokens = 0
            self._update_status()
            self.notify("Contexto reseteado", timeout=1)

        elif cmd == "/version":
            self.notify("Term v0.1.0", timeout=2)

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
                        arg, shell=True, capture_output=True, text=True, timeout=10,
                        cwd=self.workdir,
                    )
                    output = result.stdout or result.stderr or "(sin output)"
                    try:
                        msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                        await msgs.mount(Static(
                            f"[dim]$ {arg}[/]\n\n{output.strip()}",
                            classes="empty-state",
                        ))
                        msgs.scroll_end(animate=False)
                    except NoMatches:
                        pass
                except subprocess.TimeoutExpired:
                    self.notify("Comando excedio timeout (10s)", timeout=2)
                except Exception as e:
                    self.notify(f"Error: {e}", timeout=2)
            else:
                self.notify("Uso: /run <comando>", timeout=2)

        elif cmd == "/volume":
            if arg and arg.isdigit() and 0 <= int(arg) <= 100:
                subprocess.run(
                    ["osascript", "-e", f'set volume output volume {arg}'],
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
            self.notify("Play/Pause", timeout=1)

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

        else:
            self.notify(f"Comando desconocido: {cmd}. Usa /help", timeout=2)

    # ── Tab management ──

    async def _create_tab(self, name: str | None = None, model_key: str | None = None) -> None:
        tab_id = self._make_tab_id()
        mk = model_key or self.current_model
        model = AI_MODELS.get(mk, AI_MODELS["claude"])
        chat = ChatTab(mk, tab_id, self.theme_key, self.workdir)
        self._chat_tabs[tab_id] = chat

        # Name logic: first tab is "Chat", additional are "Chat N" or custom
        tab_name = name or f"Chat {len(self._chat_tabs)}"
        tabs = self.query_one("#main-tabs", TabbedContent)
        pane = TabPane(tab_name, id=f"pane-{tab_id}")
        await tabs.add_pane(pane)
        await pane.mount(chat)
        tabs.active = f"pane-{tab_id}"
        self._set_nav_active("chat")

        await asyncio.sleep(0.1)
        try:
            self.query_one(f"#input-{tab_id}", Input).focus()
        except NoMatches:
            pass

    async def action_new_tab(self) -> None:
        await self._create_tab()

    async def action_close_tab(self) -> None:
        if len(self._chat_tabs) <= 1:
            self.notify("No puedes cerrar la ultima tab", timeout=1)
            return
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        if active and active.startswith("pane-chat"):
            tab_id = active.replace("pane-", "")
            chat = self._chat_tabs.pop(tab_id, None)
            if chat and chat._proc:
                try: chat._proc.kill()
                except ProcessLookupError: pass
            await tabs.remove_pane(active)
            # If only one tab left, rename it to "Chat"
            if len(self._chat_tabs) == 1:
                remaining_id = list(self._chat_tabs.keys())[0]
                try:
                    tab = tabs.get_tab(f"pane-{remaining_id}")
                    tab.label = "Chat"
                except Exception:
                    pass

    def action_clear_tab(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        if active and active.startswith("pane-chat"):
            tab_id = active.replace("pane-", "")
            try:
                self.query_one(f"#msgs-{tab_id}", VerticalScroll).remove_children()
            except NoMatches:
                pass

    async def action_cancel(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        if active and active.startswith("pane-chat"):
            tab_id = active.replace("pane-", "")
            chat = self._chat_tabs.get(tab_id)
            if chat and chat._proc:
                try: chat._proc.kill()
                except ProcessLookupError: pass
                chat._proc = None
                chat._is_loading = False
                try: self.query_one(f"#load-{tab_id}", Label).remove_class("visible")
                except NoMatches: pass

    def action_cycle_effort(self) -> None:
        idx = EFFORT_LEVELS.index(self.effort) if self.effort in EFFORT_LEVELS else 2
        self.effort = EFFORT_LEVELS[(idx + 1) % len(EFFORT_LEVELS)]
        self._update_status()
        self.notify(f"Effort: {self.effort}", timeout=1)

    # ── Config ──

    def _save_config(self) -> None:
        save_config({
            "theme": self.theme_key,
            "workdir": self.workdir,
            "effort": self.effort,
            "model": self.current_model,
        })
        self.notify("Config guardada", timeout=2)

    # ── AI execution ──

    @work(exclusive=False, thread=False)
    async def _run_ai(self, chat: ChatTab, prompt: str) -> None:
        model = AI_MODELS.get(chat.model_key, AI_MODELS["claude"])
        full_output = ""

        try:
            effort_args = ["--effort", self.effort]
            # Prepend system context for PC control
            full_prompt = SYSTEM_CONTEXT + "\n\nUser request: " + prompt
            cmd = model["cmd"] + [full_prompt] + model["args"] + effort_args

            chat._proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=chat.workdir or self.workdir,
            )
            assert chat._proc.stdout is not None

            while True:
                chunk = await chat._proc.stdout.read(512)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                full_output += text
                # Rough token estimate
                self._context_tokens += len(text.split()) * 2
                if chat._assistant_widget is not None:
                    await chat._assistant_widget.update_content(full_output)
                try:
                    self.query_one(f"#msgs-{chat.tab_id}", VerticalScroll).scroll_end(animate=False)
                except NoMatches:
                    pass
                self._update_status()

            await chat._proc.wait()

        except FileNotFoundError:
            full_output = (
                "Error: `claude` no encontrado.\n\n"
                "Instala: `npm install -g @anthropic-ai/claude-code`\n"
                "Auth: `claude auth login`"
            )
            if chat._assistant_widget is not None:
                await chat._assistant_widget.update_content(full_output)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if chat._assistant_widget is not None:
                await chat._assistant_widget.update_content(full_output + f"\n\nError: {e}")
        finally:
            chat._proc = None
            chat._is_loading = False
            chat._assistant_widget = None
            try:
                self.query_one(f"#load-{chat.tab_id}", Label).remove_class("visible")
            except NoMatches:
                pass

# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(prog="term", description="Term -- Multi-AI TUI Dashboard")
    parser.add_argument("--workdir", "-w", default="", help="Directorio de trabajo")
    parser.add_argument("--theme", "-t", default="", choices=list(THEMES.keys()), help="Tema")
    args = parser.parse_args()
    TermApp(workdir=args.workdir, theme=args.theme).run()

if __name__ == "__main__":
    main()
