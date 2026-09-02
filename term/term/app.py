"""Term -- Multi-AI TUI with tabs, themes, tools, and app launcher."""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import json
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll, Container
from textual.css.query import NoMatches
from textual.reactive import reactive, var
from textual.widgets import (
    Footer,
    Input,
    Label,
    Markdown,
    Static,
    Select,
    Switch,
    Button,
    TabbedContent,
    TabPane,
    ListView,
    ListItem,
)


# ── ASCII Logo ───────────────────────────────────────────────────────────────

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
        "bg_primary": "#0a0a0f",
        "bg_secondary": "#12121a",
        "bg_tertiary": "#1a1a2e",
        "border": "#2a2a4a",
        "accent1": "#00e5ff",
        "accent2": "#ff00e5",
        "accent3": "#39ff14",
        "accent4": "#ff6600",
        "text": "#e0e0ff",
        "text_muted": "#555577",
        "gradient": ["#b388ff", "#9e8eff", "#8a94ff", "#759aff", "#5fa0ff",
                      "#4aa6ff", "#34acff", "#1fb2ff", "#0abcff", "#00e5ff"],
    },
    "dracula": {
        "name": "Dracula",
        "bg_primary": "#282a36",
        "bg_secondary": "#21222c",
        "bg_tertiary": "#343746",
        "border": "#44475a",
        "accent1": "#8be9fd",
        "accent2": "#ff79c6",
        "accent3": "#50fa7b",
        "accent4": "#ffb86c",
        "text": "#f8f8f2",
        "text_muted": "#6272a4",
        "gradient": ["#bd93f9", "#b094f9", "#a395f9", "#9696f9", "#8997f9",
                      "#7c98f9", "#7099f9", "#639af9", "#569bf9", "#8be9fd"],
    },
    "monokai": {
        "name": "Monokai",
        "bg_primary": "#272822",
        "bg_secondary": "#1e1f1c",
        "bg_tertiary": "#3e3d32",
        "border": "#49483e",
        "accent1": "#66d9ef",
        "accent2": "#f92672",
        "accent3": "#a6e22e",
        "accent4": "#fd971f",
        "text": "#f8f8f2",
        "text_muted": "#75715e",
        "gradient": ["#ae81ff", "#a085f5", "#9289eb", "#848de1", "#7691d7",
                      "#6895cd", "#5a99c3", "#4c9db9", "#3ea1af", "#66d9ef"],
    },
    "catppuccin": {
        "name": "Catppuccin",
        "bg_primary": "#1e1e2e",
        "bg_secondary": "#181825",
        "bg_tertiary": "#313244",
        "border": "#45475a",
        "accent1": "#89dceb",
        "accent2": "#f5c2e7",
        "accent3": "#a6e3a1",
        "accent4": "#fab387",
        "text": "#cdd6f4",
        "text_muted": "#585b70",
        "gradient": ["#cba6f7", "#c0a8f7", "#b5aaf7", "#aaacf7", "#9faef7",
                      "#94b0f7", "#89b2f7", "#7eb4f7", "#73b6f7", "#89dceb"],
    },
    "gruvbox": {
        "name": "Gruvbox",
        "bg_primary": "#1d2021",
        "bg_secondary": "#282828",
        "bg_tertiary": "#3c3836",
        "border": "#504945",
        "accent1": "#83a598",
        "accent2": "#d3869b",
        "accent3": "#b8bb26",
        "accent4": "#fe8019",
        "text": "#ebdbb2",
        "text_muted": "#665c54",
        "gradient": ["#d3869b", "#cd8a9d", "#c78e9f", "#c192a1", "#bb96a3",
                      "#b59aa5", "#af9ea7", "#a9a2a9", "#93a69b", "#83a598"],
    },
    "tokyo": {
        "name": "Tokyo Night",
        "bg_primary": "#1a1b26",
        "bg_secondary": "#16161e",
        "bg_tertiary": "#24283b",
        "border": "#3b4261",
        "accent1": "#7dcfff",
        "accent2": "#bb9af7",
        "accent3": "#9ece6a",
        "accent4": "#ff9e64",
        "text": "#c0caf5",
        "text_muted": "#565f89",
        "gradient": ["#bb9af7", "#b19ef7", "#a7a2f7", "#9da6f7", "#93aaf7",
                      "#89aef7", "#7fb2f7", "#75b6f7", "#6bbaf7", "#7dcfff"],
    },
}

# ── AI Models ────────────────────────────────────────────────────────────────

AI_MODELS = {
    "claude": {
        "name": "Claude (OAuth)",
        "cmd": ["claude", "-p"],
        "args": ["--max-turns", "15"],
        "color": "#b388ff",
    },
    "claude-opus": {
        "name": "Claude Opus",
        "cmd": ["claude", "-p"],
        "args": ["--max-turns", "15", "--model", "opus"],
        "color": "#ff79c6",
    },
    "claude-haiku": {
        "name": "Claude Haiku",
        "cmd": ["claude", "-p"],
        "args": ["--max-turns", "15", "--model", "haiku"],
        "color": "#50fa7b",
    },
}

EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max"]

# ── Launchable apps ──────────────────────────────────────────────────────────

def _find_apps() -> list[dict]:
    apps = []
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
        ("mc", "Midnight Commander", "Files"),
        ("ranger", "Ranger", "Files"),
    ]
    for cmd, name, cat in candidates:
        if shutil.which(cmd):
            apps.append({"cmd": cmd, "name": name, "category": cat})
    return apps


# ── Config persistence ───────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".config" / "term" / "config.json"

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {"theme": "neon", "workdir": str(Path.home())}

def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


# ── Gradient helper ──────────────────────────────────────────────────────────

def build_logo(theme_key: str = "neon") -> str:
    gradient = THEMES.get(theme_key, THEMES["neon"])["gradient"]
    lines = []
    max_len = max(len(l) for l in _LOGO_LINES)
    for line in _LOGO_LINES:
        colored = ""
        for i, ch in enumerate(line):
            if ch == " ":
                colored += " "
            else:
                pos = int(i / max(max_len, 1) * (len(gradient) - 1))
                colored += f"[bold {gradient[pos]}]{ch}[/]"
        lines.append(colored)
    return "\n".join(lines)


# ── CSS generator ────────────────────────────────────────────────────────────

def generate_css(theme_key: str = "neon") -> str:
    t = THEMES.get(theme_key, THEMES["neon"])
    return f"""
Screen {{
    background: {t['bg_primary']};
}}

#top-bar {{
    dock: top;
    height: 3;
    background: {t['bg_secondary']};
    border-bottom: solid {t['border']};
    padding: 0 1;
}}

#top-bar Label {{
    color: {t['accent1']};
    text-style: bold;
    padding: 1 2;
}}

#top-bar Button {{
    min-width: 5;
    margin: 0 1;
    background: {t['bg_tertiary']};
    color: {t['accent1']};
    border: solid {t['border']};
}}

#top-bar Button:hover {{
    background: {t['accent1']};
    color: {t['bg_primary']};
}}

#main-tabs {{
    background: {t['bg_primary']};
}}

ContentSwitcher {{
    background: {t['bg_primary']};
}}

TabbedContent {{
    background: {t['bg_primary']};
}}

TabPane {{
    background: {t['bg_primary']};
    padding: 0;
}}

Tabs {{
    background: {t['bg_secondary']};
    border-bottom: solid {t['border']};
}}

Tab {{
    background: {t['bg_secondary']};
    color: {t['text_muted']};
    padding: 0 2;
}}

Tab:hover {{
    color: {t['accent1']};
}}

Tab.-active {{
    background: {t['bg_primary']};
    color: {t['accent1']};
    text-style: bold;
}}

Underline {{
    color: {t['accent1']};
}}

#sidebar {{
    width: 30;
    background: {t['bg_secondary']};
    border-right: solid {t['border']};
    padding: 1 2;
}}

#sidebar Label {{
    color: {t['text_muted']};
    margin-bottom: 0;
}}

#sidebar .section-title {{
    color: {t['accent1']};
    text-style: bold;
    margin: 1 0 0 0;
}}

#sidebar Select {{
    margin: 0 0 1 0;
}}

#sidebar Button {{
    width: 100%;
    margin: 0 0 1 0;
    background: {t['bg_tertiary']};
    color: {t['text']};
    border: solid {t['border']};
}}

#sidebar Button:hover {{
    border: solid {t['accent2']};
    color: {t['accent2']};
}}

Footer {{
    background: {t['bg_secondary']};
    color: {t['text_muted']};
}}

.chat-area {{
    background: {t['bg_primary']};
}}

.messages {{
    background: {t['bg_primary']};
    padding: 1 2;
    scrollbar-color: {t['border']};
    scrollbar-color-hover: {t['accent1']};
}}

.user-msg {{
    background: {t['bg_tertiary']};
    color: {t['text']};
    border: solid {t['accent2']};
    margin: 1 4 1 12;
    padding: 1 2;
}}

.assistant-msg {{
    background: {t['bg_secondary']};
    color: {t['text']};
    border: solid {t['border']};
    margin: 1 8 1 2;
    padding: 1 2;
}}

.assistant-msg MarkdownFence {{
    background: #0d1117;
    border: solid {t['border']};
    margin: 1 0;
}}

.assistant-msg MarkdownH1,
.assistant-msg MarkdownH2,
.assistant-msg MarkdownH3 {{
    color: {t['accent2']};
    text-style: bold;
}}

.input-bar {{
    dock: bottom;
    height: auto;
    max-height: 6;
    background: {t['bg_secondary']};
    border-top: solid {t['border']};
    padding: 1 2;
}}

.input-bar Input {{
    background: {t['bg_tertiary']};
    color: {t['text']};
    border: tall {t['border']};
}}

.input-bar Input:focus {{
    border: tall {t['accent1']};
}}

.loading {{
    color: {t['accent1']};
    text-style: bold italic;
    margin: 0 2;
    display: none;
}}

.loading.visible {{
    display: block;
}}

.empty-state {{
    color: {t['text_muted']};
    text-align: center;
    margin: 4 0;
    padding: 2;
}}

/* Settings panel */
.settings-panel {{
    padding: 2 4;
    background: {t['bg_primary']};
}}

.settings-panel Label {{
    color: {t['text']};
    margin: 1 0 0 0;
}}

.settings-panel .section-title {{
    color: {t['accent1']};
    text-style: bold;
    margin: 2 0 1 0;
}}

.settings-panel Select {{
    margin: 0 0 1 0;
}}

.settings-panel Input {{
    background: {t['bg_tertiary']};
    color: {t['text']};
    border: tall {t['border']};
    margin: 0 0 1 0;
}}

.settings-panel Input:focus {{
    border: tall {t['accent1']};
}}

.settings-panel Button {{
    margin: 1 1 1 0;
    background: {t['bg_tertiary']};
    color: {t['text']};
    border: solid {t['border']};
}}

.settings-panel Button:hover {{
    border: solid {t['accent1']};
    color: {t['accent1']};
}}

/* Apps panel */
.apps-panel {{
    padding: 2 4;
    background: {t['bg_primary']};
}}

.apps-panel Label {{
    color: {t['text']};
}}

.apps-panel .section-title {{
    color: {t['accent1']};
    text-style: bold;
    margin: 1 0 1 0;
}}

.apps-panel ListView {{
    background: {t['bg_secondary']};
    border: solid {t['border']};
    margin: 1 0;
    height: auto;
    max-height: 20;
}}

.apps-panel ListItem {{
    background: {t['bg_secondary']};
    color: {t['text']};
    padding: 0 2;
}}

.apps-panel ListItem:hover {{
    background: {t['bg_tertiary']};
}}

.apps-panel ListItem.-highlight {{
    background: {t['bg_tertiary']};
    color: {t['accent1']};
}}

/* Tools panel */
.tools-panel {{
    padding: 2 4;
    background: {t['bg_primary']};
}}

.tools-panel Label {{
    color: {t['text']};
}}

.tools-panel .section-title {{
    color: {t['accent1']};
    text-style: bold;
    margin: 1 0 1 0;
}}

.tools-panel .tool-item {{
    background: {t['bg_secondary']};
    border: solid {t['border']};
    padding: 1 2;
    margin: 0 0 1 0;
}}

.tools-panel .tool-item Label {{
    color: {t['text']};
}}

.tools-status {{
    color: {t['accent3']};
}}
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


# ── Chat tab content ─────────────────────────────────────────────────────────

class ChatTab(Vertical):
    """A single AI chat tab."""

    def __init__(self, model_key: str, tab_id: str, theme_key: str, workdir: str, effort: str = "high") -> None:
        super().__init__()
        self.model_key = model_key
        self.tab_id = tab_id
        self.theme_key = theme_key
        self.workdir = workdir
        self.effort = effort
        self._proc: asyncio.subprocess.Process | None = None
        self._assistant_widget: AssistantMessage | None = None
        self._is_loading = False

    def compose(self) -> ComposeResult:
        model = AI_MODELS.get(self.model_key, AI_MODELS["claude"])
        logo = build_logo(self.theme_key)
        with Vertical(classes="chat-area"):
            with VerticalScroll(classes="messages", id=f"msgs-{self.tab_id}"):
                yield Static(
                    logo + "\n\n"
                    f"[dim]{model['name']}[/]\n\n"
                    "[dim]Escribe un mensaje abajo. ctrl+l limpiar | escape cancelar[/]",
                    classes="empty-state",
                    id=f"empty-{self.tab_id}",
                )
            yield Label(" Procesando...", classes="loading", id=f"load-{self.tab_id}")
            with Horizontal(classes="input-bar"):
                yield Input(
                    placeholder=f"Mensaje a {model['name']}...",
                    id=f"input-{self.tab_id}",
                )


# ── Main App ─────────────────────────────────────────────────────────────────

class TermApp(App):
    TITLE = "Term"
    CSS = generate_css("neon")

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
    tab_counter: var[int] = var(0)

    def __init__(self, workdir: str = "", theme: str = "neon") -> None:
        super().__init__()
        cfg = load_config()
        self.workdir = workdir or cfg.get("workdir", str(Path.home()))
        self.theme_key = theme or cfg.get("theme", "neon")
        self.CSS = generate_css(self.theme_key)
        self._chat_tabs: dict[str, ChatTab] = {}
        self._available_apps = _find_apps()

    def compose(self) -> ComposeResult:
        with Horizontal(id="top-bar"):
            yield Label("[bold]TERM[/]")
            yield Button("+ Nueva Tab", id="btn-new-tab")
            yield Button("Tema", id="btn-cycle-theme")
            yield Button("Effort: high", id="btn-effort")
            yield Button("Tab+E Effort", id="btn-effort-hint")
        with TabbedContent(id="main-tabs"):
            # First chat tab
            tab_id = self._make_tab_id()
            chat = ChatTab("claude", tab_id, self.theme_key, self.workdir)
            self._chat_tabs[tab_id] = chat
            with TabPane("Claude", id=f"pane-{tab_id}"):
                yield chat
            # Settings tab
            with TabPane("Settings", id="pane-settings"):
                yield from self._compose_settings()
            # Apps tab
            with TabPane("Apps", id="pane-apps"):
                yield from self._compose_apps()
            # Tools tab
            with TabPane("Tools", id="pane-tools"):
                yield from self._compose_tools()
        yield Footer()

    def _make_tab_id(self) -> str:
        self.tab_counter += 1
        return f"chat{self.tab_counter}"

    # ── Settings panel ──

    def _compose_settings(self) -> ComposeResult:
        with VerticalScroll(classes="settings-panel"):
            yield Label("Personalizacion", classes="section-title")
            yield Label("Tema:")
            yield Select(
                [(THEMES[k]["name"], k) for k in THEMES],
                value=self.theme_key,
                id="theme-select",
            )
            yield Label("Directorio de trabajo:")
            yield Input(value=self.workdir, id="workdir-input", placeholder="/ruta/a/tu/proyecto")
            yield Label("Modelo por defecto para nuevas tabs:")
            yield Select(
                [(AI_MODELS[k]["name"], k) for k in AI_MODELS],
                value="claude",
                id="default-model-select",
            )
            yield Button("Guardar config", id="btn-save-config")

    # ── Apps panel ──

    def _compose_apps(self) -> ComposeResult:
        with VerticalScroll(classes="apps-panel"):
            yield Label("Aplicaciones disponibles", classes="section-title")
            yield Label("[dim]Enter para lanzar en una nueva ventana de terminal[/]")
            categories: dict[str, list] = {}
            for app in self._available_apps:
                categories.setdefault(app["category"], []).append(app)
            for cat, items in categories.items():
                yield Label(f"\n[bold]{cat}[/]")
                list_items = []
                for item in items:
                    li = ListItem(Label(f"  {item['name']} [dim]({item['cmd']})[/]"))
                    li._app_cmd = item["cmd"]  # type: ignore
                    list_items.append(li)
                yield ListView(*list_items, id=f"applist-{cat}")

    # ── Tools panel ──

    def _compose_tools(self) -> ComposeResult:
        with VerticalScroll(classes="tools-panel"):
            yield Label("Herramientas conectadas", classes="section-title")
            tools_info = [
                ("Claude CLI", "claude", "OAuth activo"),
                ("Git", "git", "Control de versiones"),
                ("Node.js", "node", "Runtime JS"),
                ("Python", "python3", "Runtime Python"),
                ("Docker", "docker", "Contenedores"),
            ]
            for name, cmd, desc in tools_info:
                found = shutil.which(cmd) is not None
                status = "[green bold]activo[/]" if found else "[red]no encontrado[/]"
                with Horizontal(classes="tool-item"):
                    yield Label(f"[bold]{name}[/]  {desc}  {status}")

    # ── Event handlers ──

    def on_mount(self) -> None:
        # Focus first input
        try:
            first_tab = list(self._chat_tabs.values())[0]
            self.query_one(f"#input-{first_tab.tab_id}", Input).focus()
        except (NoMatches, IndexError):
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-new-tab":
            self.action_new_tab()
        elif event.button.id == "btn-cycle-theme":
            self._cycle_theme()
        elif event.button.id == "btn-effort":
            self.action_cycle_effort()
        elif event.button.id == "btn-save-config":
            self._save_current_config()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "theme-select" and event.value is not None:
            self._apply_theme(str(event.value))

    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "workdir-input":
            self.workdir = event.value

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        input_id = event.input.id or ""
        if not input_id.startswith("input-chat"):
            return

        text = event.value.strip()
        if not text:
            return

        tab_id = input_id.replace("input-", "")
        chat = self._chat_tabs.get(tab_id)
        if chat is None or chat._is_loading:
            return

        event.input.value = ""

        # Remove empty state
        try:
            self.query_one(f"#empty-{tab_id}").remove()
        except NoMatches:
            pass

        # Add user message
        msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
        user_w = UserMessage(text)
        await msgs.mount(user_w)

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

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        cmd = getattr(item, "_app_cmd", None)
        if cmd:
            # Launch in a new terminal window
            try:
                subprocess.Popen(
                    ["open", "-a", "Terminal", cmd] if os.uname().sysname == "Darwin"
                    else ["x-terminal-emulator", "-e", cmd],
                )
            except Exception:
                pass

    # ── Actions ──

    async def action_new_tab(self) -> None:
        tab_id = self._make_tab_id()
        try:
            default_model_sel = self.query_one("#default-model-select", Select)
            model_key = str(default_model_sel.value) if default_model_sel.value else "claude"
        except NoMatches:
            model_key = "claude"

        model = AI_MODELS.get(model_key, AI_MODELS["claude"])
        chat = ChatTab(model_key, tab_id, self.theme_key, self.workdir)
        self._chat_tabs[tab_id] = chat

        tabs = self.query_one("#main-tabs", TabbedContent)
        pane = TabPane(model["name"], id=f"pane-{tab_id}")
        await tabs.add_pane(pane)
        await pane.mount(chat)
        tabs.active = f"pane-{tab_id}"

        # Focus new input
        await asyncio.sleep(0.1)
        try:
            self.query_one(f"#input-{tab_id}", Input).focus()
        except NoMatches:
            pass

    async def action_close_tab(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        if active and active.startswith("pane-chat"):
            tab_id = active.replace("pane-", "")
            chat = self._chat_tabs.pop(tab_id, None)
            if chat and chat._proc:
                try:
                    chat._proc.kill()
                except ProcessLookupError:
                    pass
            await tabs.remove_pane(active)

    def action_clear_tab(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        if active and active.startswith("pane-chat"):
            tab_id = active.replace("pane-", "")
            try:
                msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                msgs.remove_children()
            except NoMatches:
                pass

    async def action_cancel(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        if active and active.startswith("pane-chat"):
            tab_id = active.replace("pane-", "")
            chat = self._chat_tabs.get(tab_id)
            if chat and chat._proc:
                try:
                    chat._proc.kill()
                except ProcessLookupError:
                    pass
                chat._proc = None
                chat._is_loading = False
                try:
                    self.query_one(f"#load-{tab_id}", Label).remove_class("visible")
                except NoMatches:
                    pass

    # ── Effort ──

    def action_cycle_effort(self) -> None:
        idx = EFFORT_LEVELS.index(self.effort) if self.effort in EFFORT_LEVELS else 2
        self.effort = EFFORT_LEVELS[(idx + 1) % len(EFFORT_LEVELS)]
        try:
            self.query_one("#btn-effort", Button).label = f"Effort: {self.effort}"
        except NoMatches:
            pass
        self.notify(f"Effort: {self.effort}", timeout=1)

    # ── Theme ──

    def _cycle_theme(self) -> None:
        keys = list(THEMES.keys())
        idx = keys.index(self.theme_key) if self.theme_key in keys else 0
        next_key = keys[(idx + 1) % len(keys)]
        self._apply_theme(next_key)

    def _apply_theme(self, key: str) -> None:
        self.theme_key = key
        self.stylesheet.set(generate_css(key))
        self.stylesheet.reparse()
        self.refresh(layout=True)
        # Update select if exists
        try:
            sel = self.query_one("#theme-select", Select)
            sel.value = key
        except NoMatches:
            pass

    # ── Config ──

    def _save_current_config(self) -> None:
        save_config({
            "theme": self.theme_key,
            "workdir": self.workdir,
        })
        self.notify("Config guardada", timeout=2)

    # ── AI execution ──

    @work(exclusive=False, thread=False)
    async def _run_ai(self, chat: ChatTab, prompt: str) -> None:
        model = AI_MODELS.get(chat.model_key, AI_MODELS["claude"])
        full_output = ""

        try:
            effort_args = ["--effort", self.effort] if self.effort != "high" else []
            cmd = model["cmd"] + [prompt] + model["args"] + effort_args
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
                if chat._assistant_widget is not None:
                    await chat._assistant_widget.update_content(full_output)
                try:
                    self.query_one(f"#msgs-{chat.tab_id}", VerticalScroll).scroll_end(animate=False)
                except NoMatches:
                    pass

            await chat._proc.wait()

        except FileNotFoundError:
            full_output = (
                "Error: comando no encontrado.\n\n"
                "Instala Claude Code: `npm install -g @anthropic-ai/claude-code`\n"
                "Y autenticate: `claude auth login`"
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
    parser = argparse.ArgumentParser(prog="term", description="Term -- Multi-AI TUI")
    parser.add_argument("--workdir", "-w", default="", help="Directorio de trabajo")
    parser.add_argument("--theme", "-t", default="", choices=list(THEMES.keys()), help="Tema de colores")
    args = parser.parse_args()

    app = TermApp(workdir=args.workdir, theme=args.theme)
    app.run()


if __name__ == "__main__":
    main()
