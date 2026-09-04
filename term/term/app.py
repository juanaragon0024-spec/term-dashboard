"""Term -- TUI multipestana sobre la CLI de Claude Code."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import re
import sys
import time
from pathlib import Path

from rich.markup import escape
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.reactive import reactive, var
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from . import config as cfg_mod
from . import forge, vcs
from . import jobs as jobs_mod
from . import keys as keystore
from . import mcp as mcp_mod
from . import permissions as perms
from . import syscontrol as sysctl
from .commands import (
    COMMAND_GROUPS,
    COMMANDS_HELP,
    SHORTCUTS_HELP,
    build_system_context,
    complete_command,
)
from .i18n import LANGUAGES, translate
from .models import (
    DEFAULT_MODEL_REF,
    EFFORT_LEVELS,
    catalog,
    model_label,
    normalise_ref,
)
from .project import FileContext, project_summary
from .providers import get_provider, split_ref
from .session import ChatSession, claude_available
from .store import SessionStore
from .styles import APP_CSS
from .themes import DEFAULT_THEME, THEMES, build_logo, theme_names
from .version import VERSION

# Cada cuanto se repinta el Markdown mientras llega la respuesta. Repintar en
# cada delta obliga a reparsear el texto entero una y otra vez, que es lo que
# hacia que las respuestas largas se arrastrasen.
_RENDER_INTERVAL = 0.12

# Tope de lo que se adjunta de un archivo, para no vaciar un fichero enorme
# dentro del prompt.
_ATTACH_LIMIT = 40_000

_PANELS = ("help", "apps", "tools", "settings")



def _human_size(num: int) -> str:
    for unit in ("B", "KB", "MB"):
        if num < 1024 or unit == "MB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num / 1:.1f} {unit}"
        num //= 1024
    return f"{num} B"


def _summarise_history(mensajes: list[dict]) -> str:
    """Resumen de una tanda de mensajes, hecho en local.

    No se le pide al modelo a proposito: compactar existe justamente para
    gastar menos, y una llamada extra iria en contra. Se queda con lo que el
    usuario pidio y con las herramientas que se usaron, que es lo que hace
    falta para seguir el hilo.
    """
    peticiones: list[str] = []
    herramientas: list[str] = []
    for mensaje in mensajes:
        rol = mensaje.get("role")
        contenido = mensaje.get("content")
        if rol == "user" and isinstance(contenido, str):
            plano = " ".join(contenido.split())
            if plano and not plano.startswith("Resumen de lo hablado"):
                peticiones.append(plano[:160])
        elif rol == "assistant":
            for llamada in mensaje.get("tool_calls") or []:
                nombre = (llamada.get("function") or {}).get("name")
                if nombre and nombre not in herramientas:
                    herramientas.append(nombre)

    partes = []
    if peticiones:
        partes.append("Lo que se pidió:\n" + "\n".join(
            f"- {p}" for p in peticiones[-12:]))
    if herramientas:
        partes.append("Herramientas usadas: " + ", ".join(herramientas))
    return "\n\n".join(partes) or "(sin nada reseñable)"


def _fmt_size(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        return "?"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


# ---------------------------------------------------------------------------
# Widgets de mensaje
# ---------------------------------------------------------------------------


class FileItem(ListItem):
    """Una entrada del panel de archivos.

    Guarda su ruta en lugar de dejar que se deduzca del texto pintado: leer la
    etiqueta para saber a dónde ir es frágil y además obliga a inventarse
    prefijos como «[dir] » que luego hay que volver a quitar.
    """

    def __init__(self, path: Path, is_dir: bool, label: str) -> None:
        super().__init__(Label(label))
        self.path = path
        self.is_dir = is_dir


class UserMessage(Static):
    """Un mensaje escrito por el usuario."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.raw_text = text
        self.add_class("user-msg")


class ToolEvent(Static):
    """Aviso de que Claude ha usado una herramienta."""

    def __init__(self, tool: str, detail: str) -> None:
        label = f"  {tool}"
        if detail:
            label += f"  [dim]{detail}[/]"
        super().__init__(label)
        self.add_class("tool-event")


class AssistantMessage(Vertical):
    """Respuesta de Claude. Acumula texto y repinta a intervalos."""

    def __init__(self) -> None:
        super().__init__()
        self.add_class("assistant-msg")
        self.text = ""
        self._md: Markdown | None = None
        self._last_render = 0.0
        self._dirty = False

    def compose(self) -> ComposeResult:
        self._md = Markdown("")
        yield self._md

    async def append(self, chunk: str) -> None:
        """Anadir un trozo de texto y repintar solo si toca."""
        await self._set(self.text + chunk)

    async def replace(self, text: str) -> None:
        """Sustituir el texto entero.

        Hay proveedores que en cada evento mandan la respuesta acumulada en
        lugar del trozo nuevo; anadirla la duplicaria.
        """
        await self._set(text)

    async def _set(self, text: str) -> None:
        self.text = text
        self._dirty = True
        now = time.monotonic()
        if now - self._last_render >= _RENDER_INTERVAL:
            await self.flush()

    async def flush(self) -> None:
        """Forzar el repintado del texto acumulado."""
        if self._md is None or not self._dirty:
            return
        self._dirty = False
        self._last_render = time.monotonic()
        with contextlib.suppress(Exception):
            await self._md.update(self.text)

    def code_blocks(self) -> list[str]:
        """Bloques ``` de la respuesta, para poder copiarlos sueltos."""
        return [
            block.strip()
            for block in re.findall(r"```[^\n]*\n(.*?)```", self.text, re.DOTALL)
        ]


class ChatInput(TextArea):
    """Entrada de varias lineas.

    Enter envia el mensaje y alt+enter (o shift+enter, segun lo que el terminal
    sepa mandar) inserta un salto de linea. Las flechas recorren el historial
    solo cuando el cursor esta en el borde del texto, para no estorbar al
    moverse por un mensaje de varias lineas.
    """

    class Submitted(events.Message):
        def __init__(self, text: str, tab_id: str) -> None:
            super().__init__()
            self.text = text
            self.tab_id = tab_id

    class HistoryMove(events.Message):
        def __init__(self, delta: int, tab_id: str) -> None:
            super().__init__()
            self.delta = delta
            self.tab_id = tab_id

    class CompleteRequested(events.Message):
        def __init__(self, tab_id: str) -> None:
            super().__init__()
            self.tab_id = tab_id

    def __init__(self, tab_id: str, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.tab_id = tab_id
        self.show_line_numbers = False
        self.add_class("chat-input")

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.post_message(self.Submitted(self.text, self.tab_id))
            return
        if event.key in ("alt+enter", "shift+enter", "ctrl+j"):
            event.prevent_default()
            event.stop()
            self.insert("\n")
            return
        if event.key == "tab" and self.text.lstrip().startswith("/"):
            event.prevent_default()
            event.stop()
            self.post_message(self.CompleteRequested(self.tab_id))
            return
        if event.key in ("up", "down"):
            row, _ = self.cursor_location
            last_row = self.document.line_count - 1
            at_edge = (event.key == "up" and row == 0) or (
                event.key == "down" and row == last_row
            )
            if at_edge:
                event.prevent_default()
                event.stop()
                self.post_message(
                    self.HistoryMove(-1 if event.key == "up" else 1, self.tab_id)
                )
                return
        await super()._on_key(event)


# ---------------------------------------------------------------------------
# Buscador difuso de archivos
# ---------------------------------------------------------------------------


class FileFinder(ModalScreen[str]):
    """Buscador de archivos al estilo de fzf.

    Se abre encima de todo, filtra segun se escribe y devuelve la ruta elegida.
    Ahorra el ciclo de /find, leer la ruta y copiarla a mano.
    """

    BINDINGS = [
        Binding("escape", "dismiss_finder", "Cerrar", show=False),
        Binding("down", "mover(1)", "Bajar", show=False),
        Binding("up", "mover(-1)", "Subir", show=False),
        Binding("enter", "elegir", "Elegir", show=False),
    ]

    def __init__(self, archivos: list[str], base: str) -> None:
        super().__init__()
        self.archivos = archivos
        self.base = base
        self.resultados: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="finder"):
            yield Input(placeholder="Escribe parte del nombre…", id="finder-input")
            yield ListView(id="finder-list")

    def on_mount(self) -> None:
        self._filtrar("")
        self.query_one("#finder-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "finder-input":
            self._filtrar(event.value)

    def _filtrar(self, consulta: str) -> None:
        from .fuzzy import highlight, search

        lista = self.query_one("#finder-list", ListView)
        lista.clear()
        coincidencias = search(consulta, self.archivos, limit=40)
        self.resultados = [m.text for m in coincidencias]
        for match in coincidencias:
            lista.append(ListItem(Label(highlight(match, on="bold $accent1"))))
        if self.resultados:
            lista.index = 0

    def action_mover(self, paso: int) -> None:
        lista = self.query_one("#finder-list", ListView)
        if not self.resultados:
            return
        actual = lista.index or 0
        lista.index = max(0, min(len(self.resultados) - 1, actual + paso))

    def action_elegir(self) -> None:
        lista = self.query_one("#finder-list", ListView)
        indice = lista.index
        if indice is not None and 0 <= indice < len(self.resultados):
            self.dismiss(self.resultados[indice])
        else:
            self.dismiss("")

    def action_dismiss_finder(self) -> None:
        self.dismiss("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.action_elegir()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        self.action_elegir()


class GitPanel(ModalScreen[None]):
    """Panel de git: archivos a la izquierda, diff a la derecha.

    Es la parte de lazygit que se usa a diario: mirar qué ha cambiado, elegir
    qué entra en el commit y confirmarlo. Lo demás sigue estando en /run.
    """

    BINDINGS = [
        Binding("escape,q", "cerrar", "Cerrar", show=False),
        Binding("space", "alternar", "Preparar", show=False),
        Binding("a", "preparar_todo", "Todo", show=False),
        Binding("c", "confirmar", "Commit", show=False),
        Binding("r", "recargar", "Recargar", show=False),
        Binding("down,j", "mover(1)", "Bajar", show=False),
        Binding("up,k", "mover(-1)", "Subir", show=False),
    ]

    def __init__(self, workdir: str, on_commit) -> None:
        super().__init__()
        self.workdir = workdir
        self.on_commit = on_commit
        self.cambios: list = []

    def compose(self) -> ComposeResult:
        with Vertical(id="gitpanel"):
            yield Label("", id="git-branch")
            with Horizontal(id="git-body"):
                yield ListView(id="git-files")
                with VerticalScroll(id="git-diff-wrap"):
                    yield Static("", id="git-diff")
            yield Label(
                "[dim]espacio preparar · a todo · c commit · r recargar · esc cerrar[/]",
                id="git-hint")

    def on_mount(self) -> None:
        self.action_recargar()
        self.query_one("#git-files", ListView).focus()

    def action_recargar(self) -> None:
        lista = self.query_one("#git-files", ListView)
        indice = lista.index or 0
        lista.clear()
        self.cambios = vcs.changed_files(self.workdir)

        rama = sysctl.git_branch(self.workdir)
        preparados = sum(1 for c in self.cambios if c.staged)
        self.query_one("#git-branch", Label).update(
            f"[bold]{rama or 'sin rama'}[/]  [dim]{len(self.cambios)} "
            f"{'cambio' if len(self.cambios) == 1 else 'cambios'}, "
            f"{preparados} {'preparado' if preparados == 1 else 'preparados'}[/]")

        for cambio in self.cambios:
            marca = "[bold green]●[/]" if cambio.staged else "[dim]○[/]"
            lista.append(ListItem(Label(
                f"{marca} {cambio.label[:11]:11s} {escape(cambio.path)}")))
        if self.cambios:
            lista.index = min(indice, len(self.cambios) - 1)
            self._mostrar_diff()
        else:
            self.query_one("#git-diff", Static).update(
                "[dim]No hay nada que confirmar.[/]")

    def _seleccionado(self):
        lista = self.query_one("#git-files", ListView)
        indice = lista.index
        if indice is None or not (0 <= indice < len(self.cambios)):
            return None
        return self.cambios[indice]

    def _mostrar_diff(self) -> None:
        cambio = self._seleccionado()
        if cambio is None:
            return
        result = vcs.diff_file(self.workdir, cambio.path, staged=cambio.staged)
        self.query_one("#git-diff", Static).update(
            escape(result.output if result else result.reason))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        self._mostrar_diff()

    def action_mover(self, paso: int) -> None:
        lista = self.query_one("#git-files", ListView)
        if not self.cambios:
            return
        lista.index = max(0, min(len(self.cambios) - 1, (lista.index or 0) + paso))

    def action_alternar(self) -> None:
        """Preparar o dejar de preparar el archivo señalado."""
        cambio = self._seleccionado()
        if cambio is None:
            return
        if cambio.staged:
            vcs.unstage(self.workdir, cambio.path)
        else:
            vcs.stage(self.workdir, cambio.path)
        self.action_recargar()

    def action_preparar_todo(self) -> None:
        vcs.stage(self.workdir)
        self.action_recargar()

    def action_confirmar(self) -> None:
        """Salir del panel y dejar el commit en manos del usuario."""
        self.dismiss(None)
        self.on_commit()

    def action_cerrar(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Pestana de chat
# ---------------------------------------------------------------------------


class ChatTab(Vertical):
    """Una conversacion: mensajes, entrada y su sesion de Claude."""

    def __init__(self, model_ref: str, tab_id: str, theme_key: str, workdir: str) -> None:
        super().__init__()
        self.tab_id = tab_id
        self.theme_key = theme_key
        self.workdir = workdir
        # Cada pestana lleva su propia sesion, con su proveedor y su modelo:
        # cambiar de IA aqui no toca ninguna otra pestana.
        self.session = ChatSession()
        self.session.set_model_ref(normalise_ref(model_ref))
        self.assistant_widget: AssistantMessage | None = None
        self.is_loading = False
        self.message_count = 0
        self.last_response = ""
        self.history: list[str] = []
        self.history_pos = 0
        self.attachments: list[tuple[str, str]] = []
        # Archivos que el usuario ha metido a proposito en la conversacion.
        # A diferencia de los adjuntos, siguen ahi en los turnos siguientes.
        self.context = FileContext()
        # Modelo que planifica antes de que este ejecute. Vacío: sin arquitecto.
        self.architect: str = ""
        self.title = ""

    @property
    def model_ref(self) -> str:
        return self.session.model_ref

    def compose(self) -> ComposeResult:
        with Vertical(classes="chat-wrap"):
            with VerticalScroll(classes="messages", id=f"msgs-{self.tab_id}"):
                yield Static(
                    build_logo(self.theme_key),
                    classes="info-block",
                    id=f"empty-{self.tab_id}",
                )
            yield Label("", classes="loading", id=f"load-{self.tab_id}")
            yield Static("", classes="cmd-suggestions", id=f"cmdsug-{self.tab_id}")
            yield Label("", classes="input-hint", id=f"hint-{self.tab_id}")
            with Horizontal(classes="input-bar"):
                yield ChatInput(self.tab_id, id=f"input-{self.tab_id}")


# ---------------------------------------------------------------------------
# Aplicacion
# ---------------------------------------------------------------------------


class TermApp(App):
    TITLE = "Term"
    CSS = APP_CSS
    COMMANDS = set()  # Term trae su propia lista de comandos con "/".

    BINDINGS = [
        Binding("ctrl+c", "quit", "Salir"),
        Binding("ctrl+t", "new_tab", "Nueva tab"),
        Binding("ctrl+w", "close_active", "Cerrar"),
        Binding("ctrl+l", "clear_tab", "Limpiar"),
        Binding("ctrl+e", "cycle_effort", "Esfuerzo"),
        Binding("ctrl+b", "toggle_files", "Archivos"),
        Binding("ctrl+y", "copy_last", "Copiar", show=False),
        Binding("ctrl+p", "find_file", "Buscar archivo"),
        Binding("ctrl+g", "git_panel", "Git"),
        Binding("escape", "cancel", "Cancelar"),
        *[
            Binding(f"ctrl+{n}", f"goto_tab({n})", f"Tab {n}", show=False)
            for n in range(1, 10)
        ],
    ]

    theme_key: reactive[str] = reactive(DEFAULT_THEME)
    effort: reactive[str] = reactive("high")
    # Modelo con el que nace una pestana nueva. Las que ya existen no lo miran.
    current_model: reactive[str] = reactive(DEFAULT_MODEL_REF)
    tab_counter: var[int] = var(0)

    def __init__(self, workdir: str = "", theme: str = "", lang: str = "") -> None:
        cfg = cfg_mod.load_config()
        self._cfg = cfg
        self._tabs: dict[str, ChatTab] = {}
        self._apps = sysctl.detect_cli_apps()
        self._browsers = sysctl.detect_browsers()
        self._default_browser: str = cfg["default_browser"]
        # Vacío significa que aún no ha elegido: se le pregunta al arrancar.
        self._permission_level: str = cfg["permission_level"]
        self._lang: str = lang or cfg["lang"]
        self._show_files: bool = cfg["show_file_panel"]
        self._store = SessionStore()
        self._awaiting: str | None = None      # dialogo modal en curso
        self._awaiting_tab: str = ""
        self._pending_tab_name: str | None = None
        self._pending_url: str = ""
        self._git_branch = ""
        # Los servidores MCP se arrancan a la primera que hacen falta, no al
        # abrir Term: lanzar procesos por si acaso es un mal negocio.
        self._mcp = mcp_mod.McpRegistry()
        self._skeleton: bool = cfg["code_skeleton"]
        self._jobs = jobs_mod.JobManager()
        super().__init__()
        self.workdir = workdir or cfg["workdir"]
        self.theme_key = theme or cfg["theme"]
        self.effort = cfg["effort"]
        self.current_model = normalise_ref(cfg["model"])

    # ------------------------------------------------------------------ i18n

    def _t(self, key: str, **kwargs: object) -> str:
        return translate(self._lang, key, **kwargs)

    @property
    def _nivel(self) -> perms.Level:
        """Lo que la IA puede hacer ahora mismo."""
        return perms.get_level(self._permission_level or perms.DEFAULT_LEVEL)

    # ------------------------------------------------------- variables de CSS

    def get_css_variables(self) -> dict[str, str]:
        t = THEMES.get(self.theme_key, THEMES[DEFAULT_THEME])
        bg1, bg2, bg3 = t["bg1"], t["bg2"], t["bg3"]
        brd = t["border"]
        a1, a2, a3, a4 = t["accent1"], t["accent2"], t["accent3"], t["accent4"]
        txt, mut = t["text"], t["muted"]

        return {
            "background": bg1, "foreground": txt,
            "panel": bg2, "surface": bg2,
            "primary": a1, "secondary": a2, "accent": a3,
            "warning": a4, "error": a2, "success": a3,
            "boost": bg3,
            "border": brd, "border-blurred": brd,
            "foreground-darken-1": mut, "foreground-muted": mut,
            "panel-darken-1": bg1, "panel-darken-2": bg1, "panel-lighten-1": bg3,
            "surface-darken-1": bg1,
            "surface-lighten-1": bg3, "surface-lighten-2": bg3,
            "surface-lighten-3": bg3,
            "primary-darken-2": a1, "primary-darken-3": a1,
            "primary-lighten-3": a1, "primary-muted": mut,
            "accent-darken-1": a3, "accent-muted": mut,
            "error-darken-1": a2, "error-darken-2": a2,
            "error-darken-3": a2, "error-lighten-2": a2, "error-muted": mut,
            "success-darken-2": a3, "success-darken-3": a3,
            "success-lighten-1": a3, "success-lighten-2": a3, "success-muted": mut,
            "warning-darken-1": a4, "warning-darken-2": a4,
            "warning-darken-3": a4, "warning-lighten-2": a4,
            "warning-muted": mut, "warning-text": bg1,
            "secondary-muted": mut,
            "screen-selection-background": a1, "screen-selection-foreground": bg1,
            "input-cursor-background": a1, "input-cursor-foreground": bg1,
            "input-cursor-text-style": "bold",
            "input-selection-background": a1, "input-selection-foreground": bg1,
            "block-cursor-background": a1, "block-cursor-foreground": bg1,
            "block-cursor-text-style": "bold",
            "block-cursor-blurred-background": mut,
            "block-cursor-blurred-foreground": txt,
            "block-cursor-blurred-text-style": "none",
            "block-hover-background": bg3,
            "scrollbar": brd, "scrollbar-hover": a1, "scrollbar-active": a1,
            "scrollbar-background": bg1,
            "scrollbar-background-hover": bg1,
            "scrollbar-background-active": bg1,
            "scrollbar-corner-color": bg1,
            "footer-background": bg2, "footer-foreground": mut,
            "footer-key-background": bg3, "footer-key-foreground": a1,
            "footer-description-background": bg2,
            "footer-description-foreground": mut,
            "footer-item-background": bg2,
            "button-foreground": txt, "button-color-foreground": txt,
            "button-focus-text-style": "bold",
            "link-background": "transparent", "link-background-hover": bg3,
            "link-color": a1, "link-color-hover": a1,
            "link-style": "underline", "link-style-hover": "bold underline",
            "text": txt, "text-muted": mut, "text-disabled": mut,
            "text-accent": a1, "text-primary": a1, "text-secondary": a2,
            "text-success": a3, "text-warning": a4, "text-error": a2,
            "ansi-background": bg1, "ansi-foreground": txt,
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
            "bg1": bg1, "bg2": bg2, "bg3": bg3,
            "accent1": a1, "accent2": a2, "accent3": a3, "accent4": a4,
            "muted": mut,
        }

    # --------------------------------------------------------------- composicion

    def compose(self) -> ComposeResult:
        theme_name = THEMES.get(self.theme_key, THEMES[DEFAULT_THEME])["name"]
        yield Horizontal(
            Label("[bold]TERM[/]", id="top-bar-title"),
            Button(f"{self._t('theme_set')}: {theme_name}", id="theme-cycle-btn"),
            id="top-bar",
        )
        with Horizontal(id="main"):
            with Vertical(id="chat-col"), TabbedContent(id="main-tabs"):
                tab_id = self._next_tab_id()
                chat = ChatTab(
                    self.current_model, tab_id, self.theme_key, self.workdir
                )
                self._tabs[tab_id] = chat
                with TabPane("Chat", id=f"pane-{tab_id}"):
                    yield chat
            with Vertical(id="file-panel"):
                yield Label(self.workdir, id="file-panel-title")
                yield ListView(id="file-list")
        yield Horizontal(
            Label("", id="status-effort"),
            Label("  ", classes="status-sep"),
            Label("", id="status-context"),
            Label("  ", classes="status-sep"),
            Label("", id="status-cost"),
            Label("  ", classes="status-sep"),
            Label("", id="status-model"),
            Label("  ", classes="status-sep"),
            Label("", id="status-git"),
            Label("  ", classes="status-sep"),
            Label("", id="status-workdir"),
            id="status-bar",
        )
        yield Footer()

    # ----------------------------------------------------------------- arranque

    async def on_mount(self) -> None:
        if self._show_files:
            self.query_one("#file-panel").add_class("visible")
        self._refresh_git()
        self._refresh_status()
        self._refresh_file_panel()
        self._refresh_hint()

        if not claude_available():
            await self._post_error(self._first_tab_id(), self._t("claude_missing"))

        if not self._permission_level:
            self.set_timer(0.1, lambda: self.run_worker(self._ask_permissions()))
        else:
            self._focus_input(self._first_tab_id())

    def _first_tab_id(self) -> str:
        return next(iter(self._tabs), "")

    def _next_tab_id(self) -> str:
        self.tab_counter += 1
        return f"chat{self.tab_counter}"

    def _focus_input(self, tab_id: str) -> None:
        with contextlib.suppress(NoMatches):
            self.query_one(f"#input-{tab_id}", ChatInput).focus()

    # ------------------------------------------------------------ tema en vivo

    def watch_theme_key(self, value: str) -> None:
        if not self.is_running:
            return
        self._refresh_status()
        try:
            name = THEMES.get(value, THEMES[DEFAULT_THEME])["name"]
            self.query_one("#theme-cycle-btn", Button).label = (
                f"{self._t('theme_set')}: {name}"
            )
        except NoMatches:
            pass
        self.stylesheet.set_variables(self.get_css_variables())
        self.stylesheet.reparse()
        self.screen.update_node_styles()
        self.screen.refresh(layout=True)
        self._persist()

    def watch_effort(self, value: str) -> None:
        if self.is_running:
            self._refresh_status()
            self._persist()

    def watch_current_model(self, value: str) -> None:
        if self.is_running:
            self._refresh_status()
            self._persist()

    def _persist(self) -> None:
        """Guardar la configuracion en cuanto cambia algo.

        Antes solo se guardaba con /save, asi que cerrar Term perdia el tema,
        el modelo y el directorio que acababas de elegir.
        """
        self._cfg.update({
            "theme": self.theme_key,
            "workdir": self.workdir,
            "effort": self.effort,
            "model": self.current_model,
            "lang": self._lang,
            "default_browser": self._default_browser,
            "show_file_panel": self._show_files,
            "permission_level": self._permission_level,
            "code_skeleton": self._skeleton,
        })
        cfg_mod.save_config(self._cfg)

    # ------------------------------------------------------------ barra de estado

    def _refresh_git(self) -> None:
        self._git_branch = sysctl.git_branch(self.workdir)

    def _refresh_status(self) -> None:
        chat = self._active_chat()
        usage = chat.session.usage if chat else None

        window = (usage.context_window if usage and usage.context_window else 0) or 200_000
        used = usage.context_tokens if usage else 0
        pct = min(100, int(used / window * 100)) if window else 0
        filled = int(pct / 100 * 15)
        bar = ">" * filled + "-" * (15 - filled)

        def put(selector: str, text: str) -> None:
            with contextlib.suppress(NoMatches):
                self.query_one(selector, Label).update(text)

        put("#status-effort", f"[bold]{self._t('effort_label')}:[/] {self.effort}")
        put("#status-context",
            f"[bold]{self._t('context_label')}:[/] [{bar}] {pct}% "
            f"({used:,}/{window:,})")

        cost = usage.total_cost_usd if usage else 0.0
        put("#status-cost",
            f"[bold]{self._t('cost_label')}:[/] ${cost:.4f}" if cost else "")

        ref = chat.model_ref if chat else self.current_model
        put("#status-model", f"[bold]{self._t('model_label')}:[/] {model_label(ref)}")
        corriendo = len(self._jobs.running())
        put("#status-git",
            (f" {self._git_branch}" if self._git_branch else "")
            + (f"  ▶{corriendo}" if corriendo else ""))

        wd = self.workdir
        home = str(Path.home())
        if wd.startswith(home):
            wd = "~" + wd[len(home):]
        if len(wd) > 28:
            wd = "..." + wd[-25:]
        put("#status-workdir", f"[bold]{self._t('dir_label')}:[/] {wd}")

    def _refresh_hint(self) -> None:
        chat = self._active_chat()
        if chat is None:
            return
        parts = [self._t("multiline_hint")]
        if chat.attachments:
            parts.append(self._t("attach_pending", count=len(chat.attachments)))
        if resumen := chat.context.summary():
            parts.append(f"contexto: {resumen}")
        with contextlib.suppress(NoMatches):
            self.query_one(f"#hint-{chat.tab_id}", Label).update(
                "[dim]" + "  ·  ".join(parts) + "[/]"
            )

    # ------------------------------------------------------------ panel de archivos

    def _refresh_file_panel(self) -> None:
        try:
            lv = self.query_one("#file-list", ListView)
            title = self.query_one("#file-panel-title", Label)
        except NoMatches:
            return
        lv.clear()
        wd = self.workdir
        title.update(f"[bold]{Path(wd).name or wd}[/]")
        workpath = Path(wd)
        if not workpath.is_dir():
            return
        lv.append(FileItem(workpath.parent, True, "  ..", ))
        try:
            entries = sorted(
                workpath.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except OSError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            es_carpeta = entry.is_dir()
            icono = "▸" if es_carpeta else " "
            lv.append(FileItem(entry, es_carpeta,
                               f"{icono} {escape(entry.name)}"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Entrar en una carpeta, o meter un archivo en el mensaje."""
        # Las listas del buscador y del panel de git tienen sus propios
        # manejadores; sin este filtro, sus eventos llegarían aquí al burbujear.
        if not isinstance(event.item, FileItem):
            return
        event.stop()
        self._abrir_entrada(event.item)

    def _abrir_entrada(self, item: FileItem) -> None:
        if item.is_dir:
            if item.path.is_dir():
                self._set_workdir(str(item.path))
            return
        chat = self._active_chat()
        if chat is None:
            return
        try:
            inp = self.query_one(f"#input-{chat.tab_id}", ChatInput)
        except NoMatches:
            return
        ruta = str(item.path)
        inp.text = f"{inp.text} {ruta}".strip() if inp.text else ruta
        inp.move_cursor(inp.document.end)
        inp.focus()

    def _set_workdir(self, path: str) -> None:
        if not os.path.isdir(path):
            self.notify(f"{self._t('not_found')}: {path}", timeout=2)
            return
        self.workdir = path
        for chat in self._tabs.values():
            chat.workdir = path
        self._refresh_git()
        self._refresh_status()
        self._refresh_file_panel()
        self._persist()

    # ------------------------------------------------------------ acceso a tabs

    def _active_pane(self) -> str:
        try:
            return self.query_one("#main-tabs", TabbedContent).active or ""
        except NoMatches:
            return ""

    def _active_tab_id(self) -> str | None:
        pane = self._active_pane()
        if pane.startswith("pane-chat"):
            return pane[5:]
        return None

    def _active_chat(self) -> ChatTab | None:
        tab_id = self._active_tab_id()
        return self._tabs.get(tab_id) if tab_id else None

    def _active_panel_name(self) -> str | None:
        """Nombre del panel abierto (help, apps...), o None si hay un chat."""
        pane = self._active_pane()
        for panel in _PANELS:
            if pane == f"pane-{panel}":
                return panel
        return None

    async def _msgs(self, tab_id: str) -> VerticalScroll | None:
        try:
            return self.query_one(f"#msgs-{tab_id}", VerticalScroll)
        except NoMatches:
            return None

    async def _post(self, tab_id: str, widget: Static) -> None:
        area = await self._msgs(tab_id)
        if area is None:
            return
        await area.mount(widget)
        area.scroll_end(animate=False)

    async def _post_info(
        self, tab_id: str, text: str, widget_id: str = "", listing: bool = False,
    ) -> None:
        kwargs = {"id": widget_id} if widget_id else {}
        clases = "info-block listing" if listing else "info-block"
        await self._post(tab_id, Static(text, classes=clases, **kwargs))

    def _hits_label(self, count: int, query: str) -> str:
        """Encabezado de un listado, con el singular escrito aparte."""
        key = "search_results_one" if count == 1 else "search_results"
        return self._t(key, count=count, query=query)

    async def _post_error(self, tab_id: str, text: str) -> None:
        await self._post(tab_id, Static(text, classes="error-block"))

    def _clear_empty_state(self, tab_id: str) -> None:
        with contextlib.suppress(NoMatches):
            self.query_one(f"#empty-{tab_id}").remove()

    # ------------------------------------------------------------ boton del tema

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "theme-cycle-btn":
            keys = theme_names()
            idx = keys.index(self.theme_key) if self.theme_key in keys else 0
            self.theme_key = keys[(idx + 1) % len(keys)]

    # ------------------------------------------------------------ tabs y paneles

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        self._refresh_status()
        self._refresh_hint()

    async def _create_tab(self, name: str | None = None, model_ref: str | None = None) -> None:
        tab_id = self._next_tab_id()
        chat = ChatTab(
            model_ref or self.current_model, tab_id, self.theme_key, self.workdir
        )
        self._tabs[tab_id] = chat
        chat.title = name or f"Chat {len(self._tabs)}"

        tc = self.query_one("#main-tabs", TabbedContent)
        pane = TabPane(chat.title, id=f"pane-{tab_id}")
        await tc.add_pane(pane)
        await pane.mount(chat)
        tc.active = f"pane-{tab_id}"
        self.call_after_refresh(self._focus_input, tab_id)

    async def action_new_tab(self) -> None:
        await self._create_tab()

    def action_goto_tab(self, number: int) -> None:
        ids = list(self._tabs)
        if 1 <= number <= len(ids):
            with contextlib.suppress(NoMatches):
                self.query_one("#main-tabs", TabbedContent).active = f"pane-{ids[number - 1]}"

    async def action_close_active(self) -> None:
        """ctrl+w cierra tanto un panel como una tab.

        Antes solo cerraba tabs de chat, asi que abrir /help dejaba una pestana
        que no habia forma de cerrar.
        """
        panel = self._active_panel_name()
        if panel:
            await self._close_panel(panel)
            return
        await self._close_tab()

    async def _close_panel(self, panel: str) -> None:
        tc = self.query_one("#main-tabs", TabbedContent)
        with contextlib.suppress(Exception):
            await tc.remove_pane(f"pane-{panel}")
        first = self._first_tab_id()
        if first:
            tc.active = f"pane-{first}"
            self._focus_input(first)

    async def _close_tab(self) -> None:
        tab_id = self._active_tab_id()
        if tab_id is None:
            return
        if len(self._tabs) <= 1:
            self.notify(self._t("cannot_close_last"), timeout=1)
            return
        chat = self._tabs.pop(tab_id, None)
        if chat and chat.session.proc:
            with contextlib.suppress(ProcessLookupError, OSError):
                chat.session.proc.kill()
        tc = self.query_one("#main-tabs", TabbedContent)
        with contextlib.suppress(Exception):
            await tc.remove_pane(f"pane-{tab_id}")

    def action_find_file(self) -> None:
        """Abrir el buscador difuso y meter en el contexto lo que se elija."""
        from .project import list_code_files

        base = Path(self.workdir)
        archivos = [str(f.relative_to(base)) if f.is_relative_to(base) else str(f)
                    for f in list_code_files(self.workdir, limit=4000)]
        if not archivos:
            self.notify("no hay archivos que buscar aquí", timeout=3)
            return

        def elegido(ruta: str | None) -> None:
            if not ruta:
                return
            chat = self._active_chat()
            if chat is None:
                return
            ok, detalle = chat.context.add(ruta, self.workdir)
            self._refresh_hint()
            self.notify(
                self._t("context_added", name=Path(detalle).name) if ok else detalle,
                timeout=3)

        self.push_screen(FileFinder(archivos, self.workdir), elegido)

    def action_git_panel(self) -> None:
        """Abrir el panel de git."""
        if not vcs.is_repo(self.workdir):
            self.notify(self._t("no_repo"), timeout=3)
            return

        def al_confirmar() -> None:
            tab = self._active_tab_id()
            if tab:
                self.run_worker(self._cmd_commit("", tab))

        self.push_screen(GitPanel(self.workdir, al_confirmar))

    def action_toggle_files(self) -> None:
        """Mostrar u ocultar el panel de archivos.

        Al abrirlo el foco va a la lista, que es lo que hace que las flechas
        sirvan para algo; al cerrarlo vuelve al chat para poder seguir
        escribiendo sin tocar el ratón.
        """
        try:
            panel = self.query_one("#file-panel")
        except NoMatches:
            return
        panel.toggle_class("visible")
        self._show_files = panel.has_class("visible")
        if self._show_files:
            self._refresh_file_panel()
            with contextlib.suppress(NoMatches):
                self.query_one("#file-list", ListView).focus()
        else:
            tab = self._active_tab_id()
            if tab:
                self._focus_input(tab)
        self._persist()

    def action_cycle_effort(self) -> None:
        idx = EFFORT_LEVELS.index(self.effort) if self.effort in EFFORT_LEVELS else 2
        self.effort = EFFORT_LEVELS[(idx + 1) % len(EFFORT_LEVELS)]
        self.notify(f"{self._t('effort_set')}: {self.effort}", timeout=1)

    def action_clear_tab(self) -> None:
        self.run_worker(self._clear_tab())

    async def _clear_tab(self) -> None:
        """Vaciar el chat y abrir una sesion nueva.

        Limpiar la pantalla sin reiniciar la sesion dejaba a Claude recordando
        una conversacion que el usuario ya no veia.
        """
        chat = self._active_chat()
        if chat is None:
            return
        area = await self._msgs(chat.tab_id)
        if area is not None:
            await area.remove_children()
        chat.session.reset()
        chat.message_count = 0
        chat.last_response = ""
        chat.attachments.clear()
        chat.assistant_widget = None
        await self._post_info(
            chat.tab_id, build_logo(self.theme_key), widget_id=f"empty-{chat.tab_id}"
        )
        self._refresh_status()
        self._refresh_hint()
        self.notify(self._t("session_cleared"), timeout=3)

    async def on_unmount(self) -> None:
        """No dejar nada corriendo al cerrar Term."""
        await self._jobs.stop_all()
        await self._mcp.stop_all()

    async def action_cancel(self) -> None:
        """Esc cierra lo que esté abierto, o cancela la generación."""
        panel = self._active_panel_name()
        if panel:
            await self._close_panel(panel)
            return
        # Con el foco en el panel de archivos, Esc devuelve el foco al chat.
        if isinstance(self.focused, ListView) and self.focused.id == "file-list":
            tab = self._active_tab_id()
            if tab:
                self._focus_input(tab)
            return
        chat = self._active_chat()
        if chat is None or not chat.is_loading:
            return
        proc = chat.session.proc
        if proc is not None:
            with contextlib.suppress(ProcessLookupError, OSError):
                proc.terminate()
        self.notify(self._t("cancelled"), timeout=2)

    def action_copy_last(self) -> None:
        chat = self._active_chat()
        if chat is None or not chat.last_response:
            self.notify(self._t("no_response_copy"), timeout=2)
            return
        result = sysctl.copy_to_clipboard(chat.last_response)
        self.notify(
            self._t("copied") if result else self._t("copy_error", err=result.reason),
            timeout=2,
        )

    # ------------------------------------------------------------ entrada

    def on_chat_input_complete_requested(self, event: ChatInput.CompleteRequested) -> None:
        """Tab autocompleta el comando a medio escribir."""
        try:
            inp = self.query_one(f"#input-{event.tab_id}", ChatInput)
        except NoMatches:
            return
        completed, matches = complete_command(inp.text.strip())
        if matches:
            inp.text = completed
            inp.move_cursor(inp.document.end)
        self._show_suggestions(event.tab_id, inp.text)

    def on_chat_input_history_move(self, event: ChatInput.HistoryMove) -> None:
        """Recorrer los mensajes ya enviados con las flechas."""
        chat = self._tabs.get(event.tab_id)
        if chat is None or not chat.history:
            return
        try:
            inp = self.query_one(f"#input-{event.tab_id}", ChatInput)
        except NoMatches:
            return
        pos = chat.history_pos + event.delta
        pos = max(0, min(len(chat.history), pos))
        chat.history_pos = pos
        inp.text = "" if pos == len(chat.history) else chat.history[pos]
        inp.move_cursor(inp.document.end)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        area = event.text_area
        if isinstance(area, ChatInput):
            self._show_suggestions(area.tab_id, area.text)

    def _show_suggestions(self, tab_id: str, text: str) -> None:
        """Lista de comandos que encajan con lo que se lleva escrito."""
        try:
            sug = self.query_one(f"#cmdsug-{tab_id}", Static)
        except NoMatches:
            return
        stripped = text.strip()
        if not stripped.startswith("/") or "\n" in text:
            sug.update("")
            sug.remove_class("visible")
            return
        head = stripped.split()[0].lower()
        matches = [
            # Los corchetes de /new [nombre] son sintaxis de marcado: sin
            # escaparlos, Rich se los come y el comando aparece a medias.
            f"  [bold]{escape(cmd)}[/]  [dim]{escape(desc)}[/]"
            for cmd, desc in COMMANDS_HELP.items()
            if stripped == "/" or cmd.split()[0].startswith(head)
        ]
        if matches:
            sug.update("\n".join(matches[:10]))
            sug.add_class("visible")
        else:
            sug.update("")
            sug.remove_class("visible")

    async def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        tab_id = event.tab_id
        text = event.text.strip()
        try:
            inp = self.query_one(f"#input-{tab_id}", ChatInput)
        except NoMatches:
            return

        with contextlib.suppress(NoMatches):
            self.query_one(f"#cmdsug-{tab_id}", Static).remove_class("visible")

        # Un dialogo abierto (permisos, eleccion de modelo o de navegador)
        # se queda con lo que se escriba antes que el chat.
        if self._awaiting and self._awaiting_tab == tab_id:
            inp.text = ""
            await self._handle_dialog(text, tab_id)
            return

        if not text:
            return

        chat = self._tabs.get(tab_id)
        if chat is None or chat.is_loading:
            return

        inp.text = ""
        # Una clave en el historial de flechas acabaría en un /export.
        chat.history.append("/key …" if text.startswith("/key ") else text)
        chat.history_pos = len(chat.history)

        if text == "/":
            lines = [f"[bold]{self._t('commands_available')}:[/]\n"]
            lines += [f"  [bold]{escape(f'{c:26s}')}[/] {escape(d)}"
                      for c, d in COMMANDS_HELP.items()]
            await self._post_info(tab_id, "\n".join(lines))
            return

        if text.startswith("/"):
            await self._handle_command(text, tab_id)
            return

        await self._send_message(chat, text)

    # ------------------------------------------------------------ envio

    async def _send_message(self, chat: ChatTab, text: str) -> None:
        self._clear_empty_state(chat.tab_id)
        area = await self._msgs(chat.tab_id)
        if area is None:
            return

        await area.mount(UserMessage(text))
        assistant = AssistantMessage()
        await area.mount(assistant)
        chat.assistant_widget = assistant
        chat.message_count += 1
        area.scroll_end(animate=False)

        prompt = text
        if chat.attachments:
            blocks = [
                f"[Archivo adjunto: {path}]\n```\n{content}\n```"
                for path, content in chat.attachments
            ]
            prompt = "\n\n".join(blocks) + "\n\n" + text
            chat.attachments.clear()
            self._refresh_hint()

        if not chat.title:
            chat.title = text[:24]

        chat.is_loading = True
        self._set_loading(chat.tab_id, self._t("processing"))
        self._run_ai(chat, prompt)

    async def _plan_with_architect(self, chat: ChatTab, peticion: str) -> str:
        """Pedirle el plan al modelo arquitecto.

        Se hace en una sesión aparte y sin herramientas: el arquitecto piensa,
        no toca nada. Si falla, se devuelve cadena vacía y el turno sigue sin
        plan, porque quedarse sin respuesta sería peor que quedarse sin plan.
        """
        planificador = ChatSession()
        planificador.set_model_ref(chat.architect)
        instruccion = (
            "Eres el arquitecto. Traza un plan corto y concreto para lo que se "
            "pide, en pasos numerados, diciendo qué archivos tocar y por qué. "
            "No escribas el código: alguien lo va a ejecutar a partir de tu plan."
        )
        trozos: list[str] = []
        try:
            async for evento in planificador.run(
                peticion,
                effort=self.effort,
                workdir=chat.workdir or self.workdir,
                system_prompt=instruccion + "\n\n" + self._system_prompt(chat),
                restricted=True,          # el arquitecto no ejecuta nada
                allowed_tools=frozenset(),
            ):
                if evento.kind == "text":
                    if evento.replaces_text:
                        trozos = [evento.text]
                    else:
                        trozos.append(evento.text)
                elif evento.kind == "result" and evento.text and not trozos:
                    trozos.append(evento.text)
                elif evento.kind == "error":
                    return ""
        except Exception:
            return ""
        return "".join(trozos).strip()

    def _system_prompt(self, chat: ChatTab) -> str:
        """Prompt de sistema del turno, con lo que Term sabe del proyecto.

        Las instrucciones del repositorio y el mapa del proyecto se leen en
        cada turno: si se cachearan, un AGENTS.md recién editado no se vería
        hasta reiniciar.
        """
        partes = [build_system_context(self._lang, macos=sysctl.IS_MACOS)]
        if resumen := project_summary(chat.workdir or self.workdir,
                                      with_outline=self._skeleton):
            partes.append(resumen)
        if archivos := chat.context.render():
            partes.append(
                "Archivos que el usuario ha puesto en el contexto:\n\n" + archivos)
        return "\n\n".join(partes)

    def _set_loading(self, tab_id: str, text: str) -> None:
        try:
            label = self.query_one(f"#load-{tab_id}", Label)
        except NoMatches:
            return
        if text:
            label.update(text)
            label.add_class("visible")
        else:
            label.remove_class("visible")

    @work(exclusive=False)
    async def _run_ai(self, chat: ChatTab, prompt: str) -> None:
        """Un turno de conversacion, pintando los eventos segun llegan."""
        assistant = chat.assistant_widget
        area = await self._msgs(chat.tab_id)
        errored = False

        try:
            # Con arquitecto, primero se traza el plan y luego se ejecuta.
            if chat.architect:
                self._set_loading(chat.tab_id, self._t("planning"))
                plan = await self._plan_with_architect(chat, prompt)
                if plan:
                    if area is not None:
                        await area.mount(ToolEvent(
                            model_label(chat.architect), "plan"))
                        area.scroll_end(animate=False)
                    prompt = (
                        f"{prompt}\n\n"
                        f"Plan trazado por {model_label(chat.architect)}; síguelo "
                        f"salvo que veas un error:\n\n{plan}"
                    )
                self._set_loading(chat.tab_id, self._t("processing"))

            # Los servidores se levantan al primer turno que los pueda usar.
            if self._mcp.servers and not self._mcp.started:
                await self._mcp.start_all()

            stream = chat.session.run(
                prompt,
                effort=self.effort,
                workdir=chat.workdir or self.workdir,
                system_prompt=self._system_prompt(chat),
                permission_mode=self._nivel.cli_mode,
                cli_tools=self._nivel.cli_tools,
                restricted=False,
                allowed_tools=self._nivel.own_tools or None,
                mcp=self._mcp if self._mcp.clients else None,
                jobs=self._jobs if self._jobs.jobs else None,
            )
            async for event in stream:
                if event.kind == "text" and assistant is not None:
                    if event.replaces_text:
                        await assistant.replace(event.text)
                    else:
                        await assistant.append(event.text)
                    if area is not None:
                        area.scroll_end(animate=False)

                elif event.kind == "tool":
                    self._set_loading(
                        chat.tab_id, self._t("using_tool", tool=event.tool)
                    )
                    if area is not None:
                        await area.mount(ToolEvent(event.tool, event.detail))
                        area.scroll_end(animate=False)

                elif event.kind == "result":
                    if assistant is not None:
                        # La CLI manda el texto final completo: si los deltas
                        # parciales no llegaron, esto lo rescata igualmente.
                        if event.text and not assistant.text.strip():
                            await assistant.append(event.text)
                        await assistant.flush()
                    self._refresh_status()

                elif event.kind == "error":
                    errored = True
                    if event.text.startswith("nokey:"):
                        nombre = event.text.split(":", 1)[1]
                        provider = chat.session.provider
                        message = (
                            f"{provider.name} no tiene clave configurada.\n\n"
                            f"Guárdala con:  /key {nombre} <tu-clave>\n"
                            f"O expórtala como {getattr(provider, 'env_hint', '')}\n\n"
                            f"{provider.install_hint}"
                        )
                    elif event.text.startswith("missing:"):
                        binario = event.text.split(":", 1)[1]
                        provider = chat.session.provider
                        message = (
                            self._t("claude_missing") if binario == "claude"
                            else f"{provider.name}: no se encuentra `{binario}`."
                                 f" Instala con: {provider.install_hint}"
                        )
                    else:
                        message = f"Error: {event.text}"
                    await self._post_error(chat.tab_id, message)

        except asyncio.CancelledError:
            raise
        except Exception as exc:  # la TUI no debe caerse por un turno fallido
            await self._post_error(chat.tab_id, f"Error: {exc}")
            errored = True
        finally:
            if assistant is not None:
                await assistant.flush()
                chat.last_response = assistant.text
            chat.is_loading = False
            chat.assistant_widget = None
            self._set_loading(chat.tab_id, "")
            self._refresh_status()

        if not errored:
            self._store.touch(
                chat.session.session_id,
                title=chat.title,
                workdir=chat.workdir or self.workdir,
                model=chat.model_ref,
                messages=chat.message_count,
            )

    # ------------------------------------------------------------ dialogos

    async def _ask_permissions(self) -> None:
        """Preguntar una vez qué puede hacer la IA, y recordarlo."""
        tab_id = self._first_tab_id()
        if not tab_id:
            return
        self._awaiting = "permissions"
        self._awaiting_tab = tab_id
        self._clear_empty_state(tab_id)

        lineas = [f"[bold]{self._t('perms_title')}[/]\n"]
        for i, nivel in enumerate(perms.LEVELS.values(), 1):
            marca = "  [dim](recomendado)[/]" if nivel.key == perms.DEFAULT_LEVEL else ""
            lineas.append(f"  [bold]{i}[/]) [bold]{nivel.name}[/]{marca}")
            lineas.append(f"      {nivel.detail}")
            lineas.append("")
        lineas.append(f"[dim]{self._t('perms_choose')}[/]")
        lineas.append(f"[dim]{self._t('perms_change_later')}[/]")

        await self._post_info(tab_id, "\n".join(lineas), widget_id="dialog",
                              listing=True)
        self._focus_input(tab_id)

    async def _handle_dialog(self, text: str, tab_id: str) -> None:
        kind = self._awaiting
        self._awaiting = None
        self._awaiting_tab = ""
        with contextlib.suppress(NoMatches):
            self.query_one("#dialog").remove()

        if kind == "permissions":
            claves = perms.level_names()
            escrito = text.strip().lower()
            if escrito.isdigit() and 1 <= int(escrito) <= len(claves):
                elegido = claves[int(escrito) - 1]
            elif escrito in claves:
                elegido = escrito
            else:
                # Enter a secas acepta el recomendado, que es lo que se espera.
                elegido = perms.DEFAULT_LEVEL
            self._permission_level = elegido
            self._persist()
            nivel = perms.get_level(elegido)
            self.notify(
                self._t("perms_set", level=nivel.name, summary=nivel.summary),
                timeout=4)
            await self._post_info(tab_id, build_logo(self.theme_key),
                                  widget_id=f"empty-{tab_id}")
            self._focus_input(tab_id)

        elif kind == "model":
            refs = [ref for ref, _, _ in catalog()]
            choice = ""
            if text.isdigit() and 1 <= int(text) <= len(refs):
                choice = refs[int(text) - 1]
            elif text:
                # Cualquier `proveedor/modelo` vale, aunque no este en la lista.
                choice = normalise_ref(text)
            if choice:
                await self._create_tab(self._pending_tab_name, choice)
            else:
                self.notify(self._t("invalid_model", text=text), timeout=2)
            self._pending_tab_name = None

        elif kind == "browser":
            app_name = ""
            if text.isdigit() and 1 <= int(text) <= len(self._browsers):
                app_name = self._browsers[int(text) - 1]["app"]
            else:
                for browser in self._browsers:
                    if text.lower() in browser["name"].lower():
                        app_name = browser["app"]
                        break
            if app_name:
                self._open_url(self._pending_url or "https://www.google.com", app_name)
            else:
                self.notify(self._t("browser_not_found", text=text), timeout=2)
            self._pending_url = ""

    def _open_url(self, url: str, browser: str = "") -> None:
        result = sysctl.open_url(url, browser)
        if result:
            self.notify(self._t("opening", name=browser or url), timeout=1)
        else:
            self._notify_sys_failure(result)

    def _notify_sys_failure(self, result: sysctl.SysResult) -> None:
        """Traducir el motivo de un fallo de sistema a algo legible."""
        reason = result.reason
        if reason.endswith("|macos-only"):
            feature = reason.split("|")[0]
            self.notify(self._t("platform_unsupported", feature=feature), timeout=3)
        else:
            self.notify(reason.replace("|", ": "), timeout=3)

    # ------------------------------------------------------------ comandos

    async def _handle_command(self, text: str, tab_id: str) -> None:
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        chat = self._tabs.get(tab_id)

        # -- conversacion ---------------------------------------------------
        if cmd == "/new":
            await self._cmd_new(arg, tab_id)

        elif cmd == "/close":
            await self._close_tab()

        elif cmd == "/clear":
            await self._clear_tab()

        elif cmd == "/sessions":
            await self._cmd_sessions(tab_id)

        elif cmd == "/resume":
            await self._cmd_resume(arg, tab_id)

        elif cmd == "/search":
            await self._cmd_search(arg, tab_id)

        elif cmd == "/name":
            if arg and chat:
                chat.title = arg
                with contextlib.suppress(Exception):
                    self.query_one("#main-tabs", TabbedContent).get_tab(
                        f"pane-{tab_id}"
                    ).label = arg

        elif cmd == "/history":
            self.notify(
                self._t("messages_count", count=chat.message_count if chat else 0),
                timeout=2,
            )

        elif cmd == "/export":
            await self._cmd_export(tab_id)

        elif cmd == "/copy":
            self.action_copy_last()

        elif cmd == "/code":
            self._cmd_code(arg, chat)

        # -- configuracion --------------------------------------------------
        elif cmd == "/model":
            self._cmd_model(arg, chat)

        elif cmd == "/effort":
            if arg in EFFORT_LEVELS:
                self.effort = arg
                self.notify(f"{self._t('effort_set')}: {arg}", timeout=1)
            else:
                self.notify(f"{self._t('levels')}: {', '.join(EFFORT_LEVELS)}", timeout=2)

        elif cmd == "/theme":
            if arg in THEMES:
                self.theme_key = arg
                self.notify(f"{self._t('theme_set')}: {THEMES[arg]['name']}", timeout=1)
            else:
                self.notify(f"{self._t('themes_list')}: {', '.join(theme_names())}",
                            timeout=3)

        elif cmd == "/lang":
            await self._cmd_lang(arg, tab_id)

        elif cmd == "/permissions":
            self._cmd_permissions(arg)

        elif cmd == "/providers":
            await self._cmd_providers(tab_id)

        elif cmd == "/key":
            self._cmd_key(arg)

        elif cmd == "/key-del":
            self._cmd_key_delete(arg)

        elif cmd == "/workdir":
            self._set_workdir(os.path.expanduser(arg) if arg else self.workdir)

        elif cmd == "/save":
            self._persist()
            self.notify(self._t("save_done"), timeout=2)

        # -- archivos -------------------------------------------------------
        elif cmd == "/files":
            self.action_toggle_files()

        elif cmd == "/attach":
            self._cmd_attach(arg, chat)

        elif cmd == "/git":
            self.action_git_panel()

        elif cmd == "/status":
            await self._cmd_git(vcs.status, tab_id)

        elif cmd == "/diff":
            await self._cmd_git(vcs.diff, tab_id)

        elif cmd == "/gitlog":
            await self._cmd_git(vcs.log, tab_id)

        elif cmd == "/commit":
            await self._cmd_commit(arg, tab_id)

        elif cmd == "/undo":
            await self._cmd_git(vcs.undo, tab_id)

        elif cmd in ("/prs", "/issues", "/repo"):
            await self._cmd_forge_list(cmd, arg, tab_id)

        elif cmd in ("/pr", "/issue", "/pr-checkout"):
            await self._cmd_forge_item(cmd, arg, tab_id)

        elif cmd == "/issue-new":
            await self._cmd_issue_new(arg, tab_id)

        elif cmd == "/add":
            await self._cmd_add(arg, tab_id)

        elif cmd == "/drop":
            self._cmd_drop(arg, chat)

        elif cmd == "/context":
            await self._cmd_context(tab_id)

        elif cmd == "/f":
            self.action_find_file()

        elif cmd == "/map":
            await self._cmd_map(tab_id)

        elif cmd == "/outline":
            await self._cmd_outline(arg, tab_id)

        elif cmd == "/architect":
            self._cmd_architect(arg, chat)

        elif cmd == "/skeleton":
            self._skeleton = not self._skeleton
            self._persist()
            self.notify(self._t("skeleton_on" if self._skeleton
                                else "skeleton_off"), timeout=3)

        elif cmd == "/allow":
            # Alias de /permissions: eran dos comandos para lo mismo.
            self._cmd_permissions(arg)

        elif cmd == "/mcp":
            await self._cmd_mcp(tab_id)

        elif cmd == "/mcp-add":
            self._cmd_mcp_add(arg)

        elif cmd == "/mcp-del":
            self._cmd_mcp_del(arg)

        elif cmd == "/compact":
            await self._cmd_compact(tab_id)

        elif cmd == "/mkdir":
            await self._cmd_mkdir(arg, tab_id)

        elif cmd == "/touch":
            await self._cmd_touch(arg, tab_id)

        elif cmd in ("/find", "/findall"):
            await self._cmd_find(arg, tab_id, spotlight=(cmd == "/findall"))

        elif cmd == "/grep":
            await self._cmd_grep(arg, tab_id)

        elif cmd == "/detach":
            if chat:
                chat.attachments.clear()
                self._refresh_hint()
            self.notify(self._t("attach_cleared"), timeout=2)

        # -- paneles --------------------------------------------------------
        elif cmd in ("/help", "/apps", "/tools", "/settings"):
            await self._show_panel(cmd[1:])

        # -- sistema --------------------------------------------------------
        elif cmd == "/run":
            await self._cmd_run(arg, tab_id)

        elif cmd == "/bg":
            await self._cmd_bg(arg, tab_id)

        elif cmd == "/jobs":
            await self._cmd_jobs(tab_id)

        elif cmd == "/logs":
            await self._cmd_logs(arg, tab_id)

        elif cmd == "/stop":
            await self._cmd_stop(arg)

        elif cmd == "/open":
            if arg:
                result = sysctl.open_app(arg)
                if result:
                    self.notify(self._t("opening", name=arg), timeout=1)
                else:
                    self._notify_sys_failure(result)
            else:
                self.notify(self._t("open_usage"), timeout=2)

        elif cmd == "/browse":
            await self._cmd_browse(arg, tab_id)

        elif cmd == "/browser":
            self._cmd_browser(arg)

        elif cmd == "/volume":
            if not arg:
                actual = sysctl.get_volume()
                self.notify(
                    self._t("volume_set", val=actual.output) if actual
                    else self._t("volume_usage"), timeout=2)
            elif arg.isdigit() and 0 <= int(arg) <= 100:
                result = sysctl.set_volume(int(arg))
                if result:
                    self.notify(self._t("volume_set", val=arg), timeout=1)
                else:
                    self._notify_sys_failure(result)
            else:
                self.notify(self._t("volume_usage"), timeout=2)

        elif cmd in ("/play", "/pause", "/next", "/prev", "/track"):
            self._cmd_music(cmd)

        elif cmd in ("/web", "/yt", "/maps"):
            self._cmd_web(cmd, arg)

        elif cmd == "/close-app":
            if arg:
                result = sysctl.quit_app(arg)
                self.notify(f"{arg}: cerrada" if result else result.reason, timeout=2)
            else:
                self.notify(self._t("open_usage"), timeout=2)

        elif cmd == "/sysinfo":
            result = sysctl.system_info()
            if result:
                await self._post_info(tab_id, result.output, listing=True)
            else:
                self._notify_sys_failure(result)

        # -- meta -----------------------------------------------------------
        elif cmd == "/tab":
            usage = chat.session.usage if chat else None
            self.notify(
                f"{self._t('model_label')}: {model_label(chat.model_ref if chat else self.current_model)} | "
                f"{self._t('effort_label')}: {self.effort} | "
                f"{self._t('theme_set')}: {THEMES[self.theme_key]['name']} | "
                f"{self._t('cost_label')}: ${usage.total_cost_usd:.4f}" if usage
                else f"{self._t('effort_label')}: {self.effort}",
                timeout=5,
            )

        elif cmd == "/reset":
            if chat:
                chat.session.usage.__init__()  # type: ignore[misc]
            self._refresh_status()
            self.notify(self._t("context_reset"), timeout=1)

        elif cmd in ("/version", "/about"):
            self.notify(self._t("about", version=VERSION), timeout=3)

        elif cmd == "/quit":
            self.exit()

        else:
            self.notify(self._t("unknown_cmd", cmd=cmd), timeout=2)

    # ------------------------------------------------------- comandos concretos

    async def _cmd_new(self, arg: str, tab_id: str) -> None:
        conocidos = {ref for ref, _, _ in catalog()}
        name: str | None = None
        model: str | None = None
        for token in arg.split():
            # Un token con barra o de la lista es el modelo; el resto, el nombre.
            if token in conocidos or "/" in token:
                model = normalise_ref(token)
            elif name is None:
                name = token
            else:
                name += " " + token
        if model:
            await self._create_tab(name, model)
            return

        self._pending_tab_name = name
        entradas = catalog()
        lines = []
        proveedor_actual = ""
        for i, (ref, etiqueta, proveedor) in enumerate(entradas, 1):
            if proveedor != proveedor_actual:
                lines.append(f"\n  [bold]{proveedor}[/]")
                proveedor_actual = proveedor
            lines.append(f"    [bold]{i}[/]) {etiqueta}  [dim]{ref}[/]")
        await self._post_info(
            tab_id,
            f"[bold]{self._t('select_model')}:[/]\n" + "\n".join(lines)
            + f"\n\n[dim]{self._t('type_number', n=len(entradas))}[/]",
            widget_id="dialog",
        )
        self._awaiting = "model"
        self._awaiting_tab = tab_id

    async def _cmd_sessions(self, tab_id: str) -> None:
        records = self._store.records
        if not records:
            await self._post_info(tab_id, self._t("no_sessions"))
            return
        lines = [f"[bold]{self._t('sessions_title')}:[/]\n"]
        for i, record in enumerate(records[:20], 1):
            title = record.title or record.session_id[:8]
            lines.append(
                f"  [bold]{i}[/]) {title}  "
                f"[dim]{model_label(record.model)} · {record.messages} msg · "
                f"{record.age_label}[/]"
            )
        lines.append(f"\n[dim]{self._t('resume_usage')}[/]")
        await self._post_info(tab_id, "\n".join(lines))

    async def _cmd_resume(self, arg: str, tab_id: str) -> None:
        if not arg.isdigit():
            self.notify(self._t("resume_usage"), timeout=3)
            return
        record = self._store.get(int(arg))
        if record is None:
            self.notify(self._t("session_not_found", n=arg), timeout=2)
            return
        await self._create_tab(record.title or None, record.model)
        chat = self._active_chat()
        if chat is None:
            return
        chat.session.adopt(record.session_id)
        chat.message_count = record.messages
        if record.workdir and os.path.isdir(record.workdir):
            chat.workdir = record.workdir
        self._clear_empty_state(chat.tab_id)
        await self._post_info(
            chat.tab_id,
            f"[bold]{self._t('session_resumed', n=record.messages)}[/]\n"
            f"[dim]{record.session_id}[/]",
        )
        self.notify(self._t("session_resumed", n=record.messages), timeout=2)

    async def _cmd_search(self, arg: str, tab_id: str) -> None:
        if not arg:
            self.notify(self._t("search_usage"), timeout=2)
            return
        area = await self._msgs(tab_id)
        if area is None:
            return
        needle = arg.lower()
        hits: list[str] = []
        for child in area.children:
            if isinstance(child, UserMessage):
                body, who = child.raw_text, self._t("user_label")
            elif isinstance(child, AssistantMessage):
                body, who = child.text, self._t("assistant_label")
            else:
                continue
            for line in body.splitlines():
                if needle in line.lower():
                    flat = line.strip()[:100]
                    hits.append(f"  [bold]{who}[/] {flat}")
        if not hits:
            self.notify(self._t("search_none", query=arg), timeout=3)
            return
        header = self._hits_label(len(hits), arg)
        await self._post(
            tab_id,
            Static(f"[bold]{header}[/]\n\n" + "\n".join(hits[:25]), classes="search-hit"),
        )

    async def _cmd_export(self, tab_id: str) -> None:
        area = await self._msgs(tab_id)
        if area is None:
            self.notify(self._t("no_active_chat"), timeout=2)
            return
        blocks: list[str] = []
        for child in area.children:
            if isinstance(child, UserMessage):
                blocks.append(f"## {self._t('user_label')}\n\n{child.raw_text}")
            elif isinstance(child, AssistantMessage):
                blocks.append(f"## {self._t('assistant_label')}\n\n{child.text}")
        try:
            cfg_mod.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            path = cfg_mod.EXPORT_DIR / f"chat_{time.strftime('%Y%m%d_%H%M%S')}.md"
            path.write_text("\n\n".join(blocks), encoding="utf-8")
        except OSError as exc:
            self.notify(self._t("export_error", err=exc), timeout=3)
            return
        self.notify(self._t("exported", path=path), timeout=4)

    def _cmd_code(self, arg: str, chat: ChatTab | None) -> None:
        """Copiar un bloque de codigo suelto de la ultima respuesta."""
        if chat is None or not chat.last_response:
            self.notify(self._t("no_response_copy"), timeout=2)
            return
        blocks = re.findall(r"```[^\n]*\n(.*?)```", chat.last_response, re.DOTALL)
        if not blocks:
            self.notify(self._t("no_code_blocks"), timeout=3)
            return
        index = int(arg) if arg.isdigit() and 1 <= int(arg) <= len(blocks) else 1
        result = sysctl.copy_to_clipboard(blocks[index - 1].strip())
        if result:
            self.notify(self._t("code_copied", n=index), timeout=2)
        else:
            self.notify(self._t("copy_error", err=result.reason), timeout=3)

    def _cmd_model(self, arg: str, chat: ChatTab | None) -> None:
        """Cambiar el modelo de ESTA pestana, sin tocar las demas."""
        if not arg:
            self.notify(
                f"{self._t('models_list')}: "
                + ", ".join(ref for ref, _, _ in catalog()[:6]),
                timeout=4,
            )
            return
        ref = normalise_ref(arg)
        provider_key, _ = split_ref(ref)
        provider = get_provider(provider_key)
        if not provider.available():
            self.notify(
                f"{provider.name}: {self._t('not_installed', name=provider.binary)}"
                f" · {provider.install_hint}",
                timeout=6,
            )
            return
        if chat:
            chat.session.set_model_ref(ref)
        # Las pestanas nuevas heredan la ultima eleccion; las abiertas, no.
        self.current_model = ref
        self._refresh_status()
        conocidos = {r for r, _, _ in catalog()}
        self.notify(
            f"{self._t('model_set')}: {model_label(ref)}" if ref in conocidos
            else self._t("model_set_custom", name=ref),
            timeout=2,
        )

    async def _cmd_lang(self, arg: str, tab_id: str) -> None:
        if arg:
            code = arg.lower()
            if code in LANGUAGES:
                self._lang = code
                self._persist()
                self._refresh_status()
                self._refresh_hint()
                self.notify(self._t("lang_set", lang=LANGUAGES[code]), timeout=2)
            else:
                self.notify(self._t("lang_invalid", code=arg), timeout=3)
            return
        lines = [f"[bold]{self._t('lang_available')}:[/]\n"]
        for code, name in LANGUAGES.items():
            mark = f" [bold]{self._t('active_marker')}[/]" if code == self._lang else ""
            lines.append(f"  [bold]{code}[/] - {name}{mark}")
        lines.append(f"\n[dim]{self._t('lang_usage')}[/]")
        await self._post_info(tab_id, "\n".join(lines))

    async def _cmd_providers(self, tab_id: str) -> None:
        """Estado de cada forma de conectar una IA."""
        from .providers import all_providers

        cli, api = [], []
        for provider in all_providers().values():
            listo = provider.available()
            marca = "[bold green]LISTO[/]" if listo else "[dim]--[/]"
            if provider.transport == "api":
                clave = keystore.get_key(provider.key)
                detalle = (f"[dim]{keystore.mask(clave)}[/]" if clave
                           else f"[dim]{provider.install_hint}[/]")
                api.append(f"  {marca}  [bold]{provider.name}[/] "
                           f"([bold]{provider.key}[/])  {detalle}")
            else:
                detalle = ("" if listo else f"[dim]{provider.install_hint}[/]")
                cli.append(f"  {marca}  [bold]{provider.name}[/] "
                           f"([bold]{provider.key}[/])  {detalle}")

        lineas = ["[bold]Por línea de comandos[/]  [dim]traen su propio agente[/]\n"]
        lineas += cli
        lineas.append("\n[bold]Por API[/]  [dim]Term ejecuta las herramientas[/]\n")
        lineas += api
        lineas.append("\n[dim]Guarda una clave con: /key <proveedor> <clave>[/]")
        lineas.append("[dim]También se leen de las variables de entorno.[/]")
        await self._post_info(tab_id, "\n".join(lineas), listing=True)

    def _cmd_key(self, arg: str) -> None:
        """Guardar la clave de un proveedor.

        La clave no se repite por pantalla ni queda en el historial de la
        pestaña: se muestra enmascarada y ya.
        """
        from .providers import all_providers

        partes = arg.split(None, 1)
        if len(partes) < 2:
            self.notify("Uso: /key <proveedor> <clave>", timeout=4)
            return
        nombre, clave = partes[0].lower(), partes[1].strip()
        registro = all_providers()
        provider = registro.get(nombre)
        if provider is None or provider.transport != "api":
            disponibles = ", ".join(
                p.key for p in registro.values() if p.transport == "api")
            self.notify(f"Proveedor por API no válido. Prueba: {disponibles}",
                        timeout=6)
            return
        if keystore.set_key(nombre, clave):
            self.notify(f"{provider.name}: clave guardada ({keystore.mask(clave)})",
                        timeout=3)
        else:
            self.notify("No se pudo guardar la clave", timeout=3)

    def _cmd_key_delete(self, arg: str) -> None:
        nombre = arg.strip().lower()
        if keystore.delete_key(nombre):
            self.notify(f"{nombre}: clave borrada", timeout=2)
        else:
            self.notify(f"{nombre}: no había ninguna clave guardada", timeout=3)

    def _cmd_permissions(self, arg: str) -> None:
        """Ver o cambiar lo que la IA puede hacer."""
        clave = arg.strip().lower()
        if not clave:
            actual = self._nivel
            lineas = [f"[bold]{self._t('perms_current', level=actual.name)}[/]\n"]
            for nivel in perms.LEVELS.values():
                marca = "[bold green]●[/]" if nivel.key == actual.key else "[dim]○[/]"
                lineas.append(f"  {marca} [bold]{nivel.key}[/] — {nivel.summary}")
            lineas.append("\n[dim]/permissions <nivel> para cambiarlo[/]")
            self.notify("\n".join(lineas).replace("[bold]", "").replace("[/]", "")
                        .replace("[dim]", "").replace("[bold green]", ""), timeout=8)
            return
        if clave not in perms.LEVELS:
            self.notify(
                self._t("perms_levels", levels=", ".join(perms.level_names())),
                timeout=5)
            return
        self._permission_level = clave
        self._persist()
        nivel = perms.get_level(clave)
        self.notify(self._t("perms_set", level=nivel.name, summary=nivel.summary),
                    timeout=4)

    def _cmd_attach(self, arg: str, chat: ChatTab | None) -> None:
        if not arg or chat is None:
            self.notify(self._t("attach_usage"), timeout=2)
            return
        path = Path(os.path.expanduser(arg))
        if not path.is_absolute():
            path = Path(self.workdir) / path
        if not path.is_file():
            self.notify(self._t("attach_not_found", path=path), timeout=3)
            return
        try:
            content = path.read_text(errors="replace")
        except OSError as exc:
            self.notify(self._t("attach_error", err=exc), timeout=3)
            return
        if len(content) > _ATTACH_LIMIT:
            content = content[:_ATTACH_LIMIT] + "\n... (truncado)"
        chat.attachments.append((str(path), content))
        self._refresh_hint()
        self.notify(
            self._t("attach_ok", name=path.name, size=_fmt_size(path)), timeout=2
        )

    async def _cmd_run(self, arg: str, tab_id: str) -> None:
        if not arg:
            self.notify(self._t("run_usage"), timeout=2)
            return
        if not self._nivel.system:
            self.notify(self._t("perms_read_only", level=self._nivel.name), timeout=4)
            return
        if jobs_mod.looks_long_running(arg):
            # Esperar a un servidor con /run cuelga la interfaz hasta que salta
            # el tope de diez segundos.
            self.notify(f"Eso no termina solo. Prueba: /bg {arg}", timeout=6)
            return
        result = sysctl.run_shell(arg, self.workdir)
        if not result:
            self.notify(
                self._t("cmd_timeout") if result.reason == "timeout" else result.reason,
                timeout=3,
            )
            return
        await self._post_info(
            tab_id,
            f"[dim]$ {escape(arg)}[/]\n\n"
            f"{escape(result.output or self._t('no_output'))}",
            listing=True,
        )

    async def _cmd_bg(self, arg: str, tab_id: str) -> None:
        """Lanzar un comando sin quedarse esperándolo."""
        if not arg:
            self.notify("Uso: /bg <comando>", timeout=3)
            return
        if not self._nivel.system:
            self.notify(self._t("perms_read_only", level=self._nivel.name), timeout=4)
            return
        job = await self._jobs.start(arg, self.workdir)
        await self._post_info(
            tab_id,
            f"[bold]Lanzado[/] {escape(f'[{job.id}] {arg}')}\n"
            f"[dim]/logs {job.id} para ver la salida · /stop {job.id} para pararlo[/]",
            listing=True,
        )
        self._refresh_status()

    async def _cmd_jobs(self, tab_id: str) -> None:
        trabajos = self._jobs.listing()
        if not trabajos:
            await self._post_info(tab_id, (
                "No hay procesos en segundo plano.\n\n"
                "  [bold]/bg npm run dev[/]   lanza uno sin bloquear Term"
            ), listing=True)
            return
        lineas = ["[bold]Procesos en segundo plano[/]\n"]
        for job in trabajos:
            marca = ("[bold green]•[/]" if job.running
                     else "[dim]◦[/]" if job.stopped or job.exit_code == 0
                     else "[bold red]×[/]")
            lineas.append(
                f"  {marca} [bold]{job.id}[/]  {escape(job.command)}\n"
                f"      [dim]{job.status} · {job.elapsed_label} · "
                f"{len(job.lines)} líneas[/]")
        lineas.append("\n[dim]/logs <n> para la salida · /stop <n> para pararlo[/]")
        await self._post_info(tab_id, "\n".join(lineas), listing=True)

    async def _cmd_logs(self, arg: str, tab_id: str) -> None:
        """Salida de un proceso, con filtro opcional."""
        partes = arg.split(None, 1)
        numero = int(partes[0]) if partes and partes[0].isdigit() else None
        filtro = partes[1] if numero is not None and len(partes) > 1 else arg.strip()

        job = self._jobs.get(numero) if numero else self._jobs.latest()
        if job is None:
            self.notify("No hay ningún proceso con ese número", timeout=3)
            return
        cuerpo = job.search(filtro, 60) if filtro else job.tail(60)
        if not cuerpo:
            cuerpo = f"(ninguna línea contiene «{filtro}»)"
        await self._post_info(
            tab_id,
            f"[bold]{escape(f'[{job.id}] {job.command}')}[/]  [dim]{job.status}[/]"
            f"\n\n{escape(cuerpo)}",
            listing=True,
        )

    async def _cmd_stop(self, arg: str) -> None:
        if arg.strip().isdigit():
            numero = int(arg.strip())
            parado = await self._jobs.stop(numero)
            self.notify(f"Proceso {numero} parado" if parado
                        else f"El proceso {numero} no estaba corriendo", timeout=2)
        else:
            cuantos = await self._jobs.stop_all()
            self.notify(f"{cuantos} proceso(s) parados" if cuantos
                        else "No había ninguno corriendo", timeout=2)
        self._refresh_status()

    async def _cmd_browse(self, arg: str, tab_id: str) -> None:
        url = arg or "https://www.google.com"
        if self._default_browser:
            self._open_url(url, self._default_browser)
            return
        if len(self._browsers) == 1:
            self._open_url(url, self._browsers[0]["app"])
            return
        if not self._browsers:
            self.notify(self._t("no_browsers"), timeout=2)
            return
        self._pending_url = url
        lines = [f"  [bold]{i}[/]) {b['name']}"
                 for i, b in enumerate(self._browsers, 1)]
        await self._post_info(
            tab_id,
            f"[bold]{self._t('select_browser')}:[/]\n\n" + "\n".join(lines)
            + f"\n\n[dim]{self._t('type_browser_number', n=len(self._browsers))}[/]"
            + f"\n[dim]{self._t('set_default_browser')}[/]",
            widget_id="dialog",
        )
        self._awaiting = "browser"
        self._awaiting_tab = tab_id

    def _cmd_browser(self, arg: str) -> None:
        if not arg:
            self.notify(
                self._t("current_browser", name=self._default_browser)
                if self._default_browser else self._t("no_default_browser"),
                timeout=3,
            )
            return
        app_name = sysctl.BROWSER_ALIASES.get(arg.lower())
        if not app_name:
            self.notify(
                self._t("valid_names", names=", ".join(sysctl.BROWSER_ALIASES)),
                timeout=4,
            )
            return
        if not any(b["app"] == app_name for b in self._browsers):
            self.notify(self._t("not_installed", name=app_name), timeout=3)
            return
        self._default_browser = app_name
        self._persist()
        self.notify(self._t("default_browser_set", name=app_name), timeout=2)

    def _cmd_music(self, cmd: str) -> None:
        """Control del reproductor que esté abierto, sea Spotify o Music."""
        actions = {
            "/play": ("play", "play_pause"),
            "/pause": ("pause", "play_pause"),
            "/next": ("next", "next_track"),
            "/prev": ("previous", "prev_track"),
            "/track": ("track", ""),
        }
        action, key = actions[cmd]
        result = sysctl.music(action)
        if not result:
            self._notify_sys_failure(result)
            return
        self.notify(result.output or self._t(key), timeout=3)

    def _cmd_web(self, cmd: str, arg: str) -> None:
        """Abrir una búsqueda en el navegador."""
        engines = {"/web": "google", "/yt": "youtube", "/maps": "maps"}
        if not arg:
            self.notify(self._t("search_usage"), timeout=2)
            return
        result = sysctl.web_search(
            arg, engines[cmd], self._default_browser)
        if result:
            self.notify(self._t("opening", name=arg), timeout=2)
        else:
            self._notify_sys_failure(result)

    async def _cmd_git(self, funcion, tab_id: str) -> None:
        """Ejecutar una orden de git y pintar su salida."""
        result = funcion(self.workdir)
        if not result:
            self.notify(result.reason or self._t("no_repo"), timeout=4)
            return
        self._refresh_git()
        self._refresh_status()
        await self._post_info(tab_id, result.output, listing=True)

    async def _cmd_commit(self, arg: str, tab_id: str) -> None:
        """Guardar los cambios. Sin mensaje, se lo pide a la IA de la pestaña."""
        if not vcs.is_repo(self.workdir):
            self.notify(self._t("no_repo"), timeout=3)
            return
        if arg.strip():
            result = vcs.commit(self.workdir, arg.strip())
            if result:
                self._refresh_git()
                self._refresh_status()
                await self._post_info(tab_id, result.output, listing=True)
            else:
                self.notify(result.reason, timeout=4)
            return

        cambios = vcs.diff(self.workdir)
        if not cambios or cambios.output == "(no hay cambios)":
            self.notify(cambios.reason or "no hay nada que guardar", timeout=3)
            return
        chat = self._tabs.get(tab_id)
        if chat is None:
            return
        # El mensaje lo redacta la IA, pero el commit lo confirma el usuario:
        # Term no escribe en el repositorio por su cuenta.
        await self._send_message(chat, (
            "Escribe un mensaje de commit para estos cambios. Responde solo con "
            "el mensaje, sin comillas ni explicación; yo lo confirmo luego con "
            "/commit <mensaje>.\n\n"
            f"```diff\n{cambios.output[:8000]}\n```"
        ))

    async def _cmd_forge_list(self, cmd: str, arg: str, tab_id: str) -> None:
        """Listados de GitHub. `mias` los acota a lo tuyo."""
        mias = arg.strip().lower() in ("mias", "mías", "me", "@me")
        funciones = {
            "/prs": lambda: forge.list_prs(self.workdir, mine=mias),
            "/issues": lambda: forge.list_issues(self.workdir, mine=mias),
            "/repo": lambda: forge.repo_info(self.workdir),
        }
        self._set_loading(tab_id, self._t("processing"))
        result = funciones[cmd]()
        self._set_loading(tab_id, "")
        if result:
            await self._post_info(tab_id, result.output, listing=True)
        else:
            self.notify(result.reason, timeout=6)

    async def _cmd_forge_item(self, cmd: str, arg: str, tab_id: str) -> None:
        """Ver una PR o una incidencia, o traerse su rama."""
        if not arg.strip().lstrip("#").isdigit():
            self.notify(f"Uso: {cmd} <número>", timeout=3)
            return
        numero = int(arg.strip().lstrip("#"))
        self._set_loading(tab_id, self._t("processing"))
        if cmd == "/pr":
            result = forge.view_pr(self.workdir, numero)
        elif cmd == "/issue":
            result = forge.view_issue(self.workdir, numero)
        else:
            result = forge.checkout_pr(self.workdir, numero)
            if result:
                self._refresh_git()
                self._refresh_status()
        self._set_loading(tab_id, "")
        if result:
            await self._post_info(tab_id, result.output, listing=True)
        else:
            self.notify(result.reason, timeout=6)

    async def _cmd_issue_new(self, arg: str, tab_id: str) -> None:
        if not arg.strip():
            self.notify("Uso: /issue-new <título>", timeout=3)
            return
        self._set_loading(tab_id, self._t("processing"))
        result = forge.create_issue(self.workdir, arg.strip())
        self._set_loading(tab_id, "")
        if result:
            await self._post_info(tab_id, f"Incidencia creada: {result.output}",
                                  listing=True)
        else:
            self.notify(result.reason, timeout=6)

    async def _cmd_add(self, arg: str, tab_id: str) -> None:
        chat = self._tabs.get(tab_id)
        if chat is None or not arg:
            self.notify("Uso: /add <ruta>", timeout=2)
            return
        anadidos, fallos = [], []
        for pieza in arg.split():
            ok, detalle = chat.context.add(pieza, self.workdir)
            (anadidos if ok else fallos).append(detalle)
        if anadidos:
            self._refresh_hint()
            self.notify(self._t("context_added",
                                name=", ".join(Path(a).name for a in anadidos)),
                        timeout=2)
        for fallo in fallos:
            self.notify(fallo, timeout=3)

    def _cmd_drop(self, arg: str, chat: ChatTab | None) -> None:
        if chat is None:
            return
        if not arg.strip():
            cuantos = chat.context.clear()
            self._refresh_hint()
            self.notify(self._t("context_dropped", name=f"{cuantos} archivo(s)"),
                        timeout=2)
            return
        ok, nombre = chat.context.drop(arg.strip())
        self._refresh_hint()
        self.notify(
            self._t("context_dropped", name=Path(nombre).name) if ok
            else f"no estaba en el contexto: {arg}", timeout=2)

    async def _cmd_context(self, tab_id: str) -> None:
        chat = self._tabs.get(tab_id)
        if chat is None or not chat.context.paths:
            await self._post_info(tab_id, self._t("context_empty"), listing=True)
            return
        lineas = [f"[bold]{self._t('context_title')}[/]\n"]
        for ruta in chat.context.paths:
            path = Path(ruta)
            tamano = _fmt_size(path) if path.is_file() else "?"
            lineas.append(f"  {ruta}  [dim]{tamano}[/]")
        lineas.append("\n[dim]/drop <nombre> para sacar uno · /drop para vaciar[/]")
        await self._post_info(tab_id, "\n".join(lineas), listing=True)

    async def _cmd_map(self, tab_id: str) -> None:
        from .project import build_repo_map

        mapa = build_repo_map(self.workdir)
        await self._post_info(tab_id, mapa or "(proyecto vacío)", listing=True)

    async def _cmd_mcp(self, tab_id: str) -> None:
        """Servidores MCP declarados, con sus herramientas si están en marcha."""
        if not self._mcp.servers:
            await self._post_info(tab_id, (
                "[bold]MCP[/]  [dim]sin servidores configurados[/]\n\n"
                "  Un servidor MCP presta sus herramientas a Term: bases de datos,\n"
                "  GitHub, navegadores y demás, sin escribirlas aquí.\n\n"
                "  [bold]/mcp-add github npx -y @modelcontextprotocol/server-github[/]\n\n"
                f"  [dim]También puedes editar {mcp_mod.MCP_PATH}[/]"
            ), listing=True)
            return

        self._set_loading(tab_id, self._t("processing"))
        fallos = await self._mcp.start_all()
        self._set_loading(tab_id, "")

        lineas = ["[bold]Servidores MCP[/]\n"]
        for server in self._mcp.servers:
            client = self._mcp.clients.get(server.name)
            if not server.enabled:
                marca, detalle = "[dim]◦[/]", "[dim]desactivado[/]"
            elif server.name in fallos:
                marca, detalle = "[bold red]×[/]", f"[dim]{fallos[server.name]}[/]"
            elif client and client.running:
                marca = "[bold green]•[/]"
                detalle = f"[dim]{len(client.tools)} herramientas[/]"
            else:
                marca, detalle = "[dim]◦[/]", "[dim]parado[/]"
            lineas.append(f"  {marca} [bold]{server.name}[/]  {detalle}")
            lineas.append(f"      [dim]{server.command} {' '.join(server.args)}[/]")
            if client and client.running:
                for tool in client.tools[:8]:
                    lineas.append(f"      [dim]· {tool.name}[/]")
                if len(client.tools) > 8:
                    lineas.append(f"      [dim]… y {len(client.tools) - 8} más[/]")
        await self._post_info(tab_id, "\n".join(lineas), listing=True)

    def _cmd_mcp_add(self, arg: str) -> None:
        partes = arg.split()
        if len(partes) < 2:
            self.notify("Uso: /mcp-add <nombre> <comando> [argumentos…]", timeout=5)
            return
        nombre, comando, *args = partes
        if any(s.name == nombre for s in self._mcp.servers):
            self.notify(f"Ya existe un servidor llamado «{nombre}»", timeout=3)
            return
        self._mcp.servers.append(
            mcp_mod.McpServer(name=nombre, command=comando, args=args))
        if mcp_mod.save_servers(self._mcp.servers):
            self.notify(f"Servidor MCP añadido: {nombre}. Compruébalo con /mcp",
                        timeout=4)
        else:
            self.notify("No se pudo guardar la configuración MCP", timeout=3)

    def _cmd_mcp_del(self, arg: str) -> None:
        nombre = arg.strip()
        antes = len(self._mcp.servers)
        self._mcp.servers = [s for s in self._mcp.servers if s.name != nombre]
        if len(self._mcp.servers) == antes:
            self.notify(f"No hay ningún servidor llamado «{nombre}»", timeout=3)
            return
        mcp_mod.save_servers(self._mcp.servers)
        self.notify(f"Servidor MCP quitado: {nombre}", timeout=2)

    async def _cmd_outline(self, arg: str, tab_id: str) -> None:
        """Clases y funciones con su firma, de un archivo o de todo el proyecto."""
        from .outline import outline_file
        from .project import build_code_outline

        if arg.strip():
            ruta = Path(arg.strip()).expanduser()
            if not ruta.is_absolute():
                ruta = Path(self.workdir) / ruta
            texto = outline_file(ruta)
            if not texto:
                self.notify(f"no se pudo leer el esqueleto de {ruta.name}", timeout=3)
                return
        else:
            texto = build_code_outline(self.workdir, budget=20_000)
            if not texto:
                self.notify("no hay código que resumir aquí", timeout=3)
                return
        await self._post_info(tab_id, texto, listing=True)

    def _cmd_architect(self, arg: str, chat: ChatTab | None) -> None:
        """Poner a otro modelo a planificar antes de ejecutar.

        La idea es de Aider: un modelo bueno razonando traza el plan y otro más
        barato lo lleva a cabo. Aquí sale casi gratis porque cada pestaña ya
        sabe hablar con el modelo que sea.
        """
        if chat is None:
            return
        objetivo = arg.strip()
        if not objetivo or objetivo in ("off", "no", "-"):
            chat.architect = ""
            self.notify(self._t("architect_off"), timeout=2)
            return

        ref = normalise_ref(objetivo)
        provider_key, _ = split_ref(ref)
        provider = get_provider(provider_key)
        if not provider.available():
            self.notify(
                f"{provider.name}: {self._t('not_installed', name=provider.binary)}",
                timeout=5)
            return
        chat.architect = ref
        self.notify(
            self._t("architect_on", model=model_label(ref),
                    worker=model_label(chat.model_ref)),
            timeout=4)

    async def _cmd_compact(self, tab_id: str) -> None:
        """Resumir la conversación para liberar contexto.

        En una pestaña conectada por API sustituye los mensajes viejos por un
        resumen y deja los últimos intactos. Con una CLI el historial lo lleva
        ella, así que no hay nada que compactar desde aquí.
        """
        chat = self._tabs.get(tab_id)
        if chat is None:
            return
        historial = chat.session.history
        if not chat.session.is_api:
            # Con una CLI el historial lo lleva ella; decir «es corta» aquí
            # sería mentir, porque puede ser larguísima.
            self.notify(self._t("compact_cli"), timeout=6)
            return
        if len(historial) < 8:
            self.notify(self._t("compact_not_needed"), timeout=4)
            return

        antes = len(historial)
        conservar = 4
        viejos, recientes = historial[:-conservar], historial[-conservar:]
        historial[:] = [
            {"role": "user", "content":
             "Resumen de lo hablado antes en esta conversación:\n"
             + _summarise_history(viejos)},
            {"role": "assistant", "content": "Entendido, sigo con eso en mente."},
            *recientes,
        ]
        self._refresh_status()
        await self._post_info(
            tab_id, self._t("compact_done", before=antes, after=len(historial)),
            listing=True)

    async def _cmd_mkdir(self, arg: str, tab_id: str) -> None:
        if not arg:
            self.notify("Uso: /mkdir <ruta>", timeout=2)
            return
        result = sysctl.make_dir(arg, self.workdir)
        if not result:
            self.notify(result.reason.replace("|", ": "), timeout=4)
            return
        self._refresh_file_panel()
        detalle = f" ({result.reason})" if result.reason else ""
        await self._post_info(
            tab_id, f"[bold]Carpeta[/] {result.output}{detalle}", listing=True)

    async def _cmd_touch(self, arg: str, tab_id: str) -> None:
        if not arg:
            self.notify("Uso: /touch <ruta>", timeout=2)
            return
        result = sysctl.write_file(arg, "", self.workdir)
        if not result:
            self.notify(result.reason.replace("|", ": "), timeout=4)
            return
        self._refresh_file_panel()
        await self._post_info(
            tab_id, f"[bold]Archivo[/] {result.output}", listing=True)

    async def _cmd_find(self, arg: str, tab_id: str, *, spotlight: bool) -> None:
        """Buscar archivos y devolver sus rutas completas."""
        if not arg:
            self.notify("Uso: /find <patrón>", timeout=2)
            return
        result = sysctl.find_files(
            arg, "" if spotlight else self.workdir, spotlight=spotlight)
        if not result:
            self.notify(result.reason.replace("|", ": "), timeout=4)
            return
        rutas = [r for r in result.output.splitlines() if r]
        if not rutas:
            self.notify(self._t("search_none", query=arg), timeout=3)
            return
        cuerpo = "\n".join(f"  {r}" for r in rutas)
        await self._post_info(
            tab_id,
            f"[bold]{self._hits_label(len(rutas), arg)}[/]\n\n{cuerpo}",
            listing=True,
        )

    async def _cmd_grep(self, arg: str, tab_id: str) -> None:
        if not arg:
            self.notify("Uso: /grep <texto>", timeout=2)
            return
        result = sysctl.search_text(arg, self.workdir)
        if not result:
            self.notify(result.reason.replace("|", ": "), timeout=4)
            return
        lineas = [ln for ln in result.output.splitlines() if ln]
        if not lineas:
            self.notify(self._t("search_none", query=arg), timeout=3)
            return
        cuerpo = "\n".join(f"  {ln}" for ln in lineas)
        await self._post_info(
            tab_id,
            f"[bold]{self._hits_label(len(lineas), arg)}[/]\n\n{cuerpo}",
            listing=True,
        )

    # ------------------------------------------------------------ paneles

    async def _show_panel(self, panel: str) -> None:
        """Abrir un panel como pestana. Se cierra con Esc o ctrl+w."""
        tc = self.query_one("#main-tabs", TabbedContent)
        pane_id = f"pane-{panel}"
        with contextlib.suppress(Exception):
            await tc.remove_pane(pane_id)

        pane = TabPane(panel.capitalize(), id=pane_id)
        await tc.add_pane(pane)
        tc.active = pane_id

        builders = {
            "settings": self._panel_settings,
            "apps": self._panel_apps,
            "tools": self._panel_tools,
            "help": self._panel_help,
        }
        body = builders[panel]()
        scroll = VerticalScroll(classes="panel-scroll")
        await pane.mount(scroll)
        await scroll.mount(Static(body, classes="panel"))
        await pane.mount(Static(f"[dim]{self._t('panel_close_hint')}[/]",
                                classes="panel-hint"))
        # El foco va al contenedor para que las flechas y AvPág desplacen sin
        # tener que pinchar antes.
        scroll.can_focus = True
        scroll.focus()

    def _panel_settings(self) -> str:
        chat = self._active_chat()
        model_key = chat.model_ref if chat else self.current_model
        return (
            f"[bold]{self._t('settings_title')}[/]\n\n"
            f"{self._t('theme_set')}: [bold]{THEMES[self.theme_key]['name']}[/]\n"
            f"  {self._t('available')}: {', '.join(theme_names())}\n"
            f"  {self._t('change_cmd')}: [bold]/theme <nombre>[/]\n\n"
            f"{self._t('model_label')}: [bold]{model_label(model_key)}[/]\n"
            f"  {self._t('available')}: "
            f"{', '.join(ref for ref, _, _ in catalog()[:8])}\n"
            f"  {self._t('change_cmd')}: [bold]/model <nombre>[/]\n\n"
            f"{self._t('effort_label')}: [bold]{self.effort}[/]\n"
            f"  {self._t('levels')}: {', '.join(EFFORT_LEVELS)}\n"
            f"  {self._t('change_cmd')}: [bold]/effort <nivel>[/]\n\n"
            f"{self._t('perms_current', level=self._nivel.name)}\n"
            f"  {self._nivel.summary}\n"
            f"  {self._t('perms_levels', levels=', '.join(perms.level_names()))}\n"
            f"  {self._t('change_cmd')}: [bold]/permissions <nivel>[/]\n\n"
            f"{self._t('lang_current', lang=LANGUAGES.get(self._lang, self._lang))}\n"
            f"  {self._t('change_cmd')}: [bold]/lang <código>[/]\n\n"
            f"{self._t('dir_label')}: [bold]{self.workdir}[/]\n"
            f"  {self._t('change_cmd')}: [bold]/workdir <ruta>[/]\n\n"
            f"[dim]{self._t('config_path', path=cfg_mod.CONFIG_PATH)}[/]"
        )

    def _panel_apps(self) -> str:
        by_category: dict[str, list[dict[str, str]]] = {}
        for app in self._apps:
            by_category.setdefault(app["category"], []).append(app)
        lines = [f"[bold]{self._t('cli_apps_title')}[/]\n"]
        for category, items in by_category.items():
            lines.append(f"\n[bold]{category}[/]")
            lines += [f"  {it['name']} [dim]({it['cmd']})[/]" for it in items]
        if self._browsers:
            lines.append(f"\n[bold]{self._t('select_browser')}[/]")
            lines += [f"  {b['name']}" for b in self._browsers]
        lines.append(f"\n[dim]{self._t('apps_hint')}[/]")
        return "\n".join(lines)

    def _panel_tools(self) -> str:
        import shutil as _shutil

        checks = [
            ("Claude CLI", "claude"),
            ("Git", "git"),
            ("Node.js", "node"),
            ("Python", "python3"),
            ("Docker", "docker"),
            ("ripgrep", "rg"),
        ]
        if sysctl.IS_MACOS:
            checks.append(("osascript", "osascript"))
        lines = [f"[bold]{self._t('tools_title')}[/]\n"]
        for name, cmd in checks:
            ok = _shutil.which(cmd) is not None
            mark = "[bold green]OK[/]" if ok else "[bold red]--[/]"
            lines.append(f"  {mark}  [bold]{name}[/]")
        if not sysctl.IS_MACOS:
            lines.append(
                f"\n[dim]{self._t('platform_unsupported', feature='Spotify / osascript')}[/]"
            )
        return "\n".join(lines)

    def _panel_help(self) -> str:
        """Ayuda del panel /help.

        Se arma por secciones y con los comandos agrupados: la version anterior
        volcaba los cincuenta de golpe y no habia forma de encontrar ninguno.
        """
        from .providers import all_providers

        ancho = 26
        lineas = [
            build_logo(self.theme_key),
            "",
            f"[bold]Term v{VERSION}[/]  [dim]{self._t('term_subtitle')}[/]",
            "",
            f"  {self._t('what_is_desc')}",
            f"  [dim]{self._t('help_tabs')}[/]",
            "",
        ]

        # -- como conectar una IA, con lo que hay listo en esta maquina
        lineas.append(f"[bold]{self._t('help_connect')}[/]")
        for transporte, titulo in (("cli", "help_connect_cli"), ("api", "help_connect_api")):
            proveedores = [p for p in all_providers().values()
                           if p.transport == transporte]
            lineas.append(f"\n  [bold]{self._t(titulo)}[/]")
            for provider in proveedores:
                marca = "[bold green]•[/]" if provider.available() else "[dim]◦[/]"
                nombre = f"{provider.name} [dim]({provider.key})[/]"
                lineas.append(f"    {marca} {nombre}")
        lineas += [
            "",
            "    [dim]/key openrouter <clave>      guardar una clave[/]",
            "    [dim]/model openrouter/x-ai/grok-4   usar esa IA aquí[/]",
            "",
        ]

        # -- ejemplos de lo que entiende en lenguaje normal
        lineas.append(f"[bold]{self._t('help_can_do')}[/]")
        lineas += [
            "  [dim]«crea una carpeta notas y mete dentro un README»[/]",
            "  [dim]«busca dónde está el archivo de configuración»[/]",
            "  [dim]«pon la siguiente canción»[/]",
            "  [dim]«abre el navegador y busca vuelos a Lisboa»[/]",
            "  [dim]«qué archivos de este proyecto mencionan ChatSession»[/]",
            "",
        ]

        # -- comandos, por grupos
        for grupo, comandos in COMMAND_GROUPS.items():
            lineas.append(f"[bold]{self._t(grupo)}[/]")
            lineas += [f"  [bold]{escape(f'{cmd:{ancho}s}')}[/] {escape(desc)}"
                       for cmd, desc in comandos.items()]
            lineas.append("")

        lineas.append(f"[bold]{self._t('shortcuts_title')}[/]")
        lineas += [f"  [bold]{escape(f'{key:{ancho}s}')}[/] {escape(desc)}"
                   for key, desc in SHORTCUTS_HELP.items()]
        lineas += [
            "",
            f"[dim]{self._t('help_more')}[/]",
            f"[dim]{self._t('config_path', path=cfg_mod.CONFIG_PATH)}[/]",
        ]
        return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(prog="term", description="Term -- TUI con IA")
    parser.add_argument("--workdir", "-w", default="", help="Directorio de trabajo")
    parser.add_argument(
        "--theme", "-t", default="", choices=theme_names(), help="Tema de color"
    )
    parser.add_argument(
        "--lang", "-l", default="", choices=list(LANGUAGES), help="Idioma"
    )
    parser.add_argument(
        "--version", "-v", action="version", version=f"Term {VERSION}"
    )
    args = parser.parse_args()

    workdir = os.path.expanduser(args.workdir) if args.workdir else ""
    if workdir and not os.path.isdir(workdir):
        print(f"term: el directorio no existe: {workdir}", file=sys.stderr)
        raise SystemExit(2)

    TermApp(workdir=workdir, theme=args.theme, lang=args.lang).run()


if __name__ == "__main__":
    main()
