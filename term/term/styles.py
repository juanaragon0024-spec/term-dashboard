"""Hoja de estilos de la TUI.

Las variables $bg1, $accent1... las resuelve TermApp.get_css_variables() a
partir del tema activo, por eso cambiar de tema no requiere recargar nada.
"""

from __future__ import annotations

__all__ = ["APP_CSS"]

APP_CSS = """
Screen {
    background: $bg1;
}

/* -- Top bar -- */
#top-bar {
    dock: top;
    height: 1;
    background: $bg2;
    padding: 0 1;
}
#top-bar-title {
    color: $accent1;
    text-style: bold;
    width: 1fr;
    padding: 0 1;
}
#theme-cycle-btn {
    background: $bg3;
    color: $accent1;
    border: none;
    dock: right;
    padding: 0 2;
    min-width: 16;
}
#theme-cycle-btn:hover {
    background: $accent1;
    color: $bg1;
}

/* -- Main area -- */
#main {
    background: $bg1;
    height: 1fr;
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
    min-width: 10;
    text-style: bold;
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
    padding: 0 1;
    scrollbar-color: $border;
    scrollbar-color-hover: $accent1;
}
.user-msg {
    color: $text;
    background: $bg2;
    height: auto;
    width: auto;
    max-width: 80%;
    margin: 0 0 1 6;
    padding: 0 1;
    border: round $accent2;
    text-align: left;
}
.assistant-msg {
    background: transparent;
    color: $text;
    height: auto;
    margin: 0 6 1 0;
    padding: 0 1;
    border: round $border;
}
.assistant-msg Markdown {
    margin: 0;
    padding: 0;
}
.assistant-msg MarkdownFence {
    background: #0d1117;
    border: round $border;
    margin: 0;
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

/* -- Barra de entrada (TextArea: admite varias lineas) -- */
.input-bar {
    dock: bottom;
    height: auto;
    max-height: 12;
    background: $bg1;
    padding: 0 1;
}
.chat-input {
    background: $bg2;
    color: $text;
    border: round $border;
    height: auto;
    max-height: 10;
    padding: 0 1;
}
.chat-input:focus {
    border: round $accent1;
}
.input-hint {
    dock: bottom;
    height: 1;
    color: $muted;
    background: $bg1;
    padding: 0 2;
}

/* -- Command suggestions -- */
.cmd-suggestions {
    dock: bottom;
    height: auto;
    max-height: 12;
    background: $bg2;
    color: $text;
    padding: 0 12;
    display: none;
    border-top: solid $border;
}
.cmd-suggestions.visible {
    display: block;
}

/* -- Status bar -- */
#status-bar {
    height: 1;
    background: $bg2;
    color: $muted;
    padding: 0 2;
    text-style: bold;
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
    margin: 0;
    padding: 1;
}
/* Los dialogos y los listados de rutas son listas: centrarlos los hace
   ilegibles, y una ruta partida a la mitad no se puede copiar. */
#dialog,
.listing {
    text-align: left;
    padding: 1 2;
}
.listing {
    color: $text;
}

/* -- Panels -- */
/* El contenido de un panel es mas largo que la pantalla, asi que va dentro de
   un contenedor con scroll. Sin esto el TabPane crecia hasta el alto del texto
   y no habia nada que desplazar. */
.panel-scroll {
    height: 1fr;
    overflow-y: auto;
    background: $bg1;
    scrollbar-color: $border;
    scrollbar-color-hover: $accent1;
}
.panel-scroll:focus {
    scrollbar-color: $accent1;
}
.panel {
    height: auto;
    padding: 1 3;
    background: $bg1;
}
.panel Label {
    color: $text;
}

/* -- Footer -- */
Footer {
    background: $bg2;
    color: $muted;
    height: 1;
    text-style: bold;
}

/* -- File panel -- */
#file-panel {
    width: 28;
    background: $bg2;
    border-left: solid $border;
    padding: 1;
    display: none;
}
#file-panel.visible {
    display: block;
}
#file-panel-title {
    color: $accent1;
    text-style: bold;
    padding: 0 0 1 0;
}
#file-panel ListView {
    background: $bg2;
    scrollbar-color: $border;
    scrollbar-color-hover: $accent1;
}
#file-panel ListItem {
    background: $bg2;
    color: $text;
    padding: 0 1;
}
#file-panel ListItem:hover {
    background: $bg3;
}
#chat-col {
    width: 1fr;
}

/* -- Eventos de herramienta dentro de una respuesta -- */
.tool-event {
    color: $accent3;
    background: $bg2;
    height: 1;
    margin: 0 6 0 0;
    padding: 0 1;
    border-left: outer $accent3;
}
.tool-event-detail {
    color: $muted;
}

/* -- Coincidencias de /search -- */
.search-hit {
    background: $bg3;
    color: $accent4;
    margin: 0 2;
    padding: 0 2;
    border-left: outer $accent4;
}

/* -- Aviso al pie de los paneles -- */
.panel-hint {
    color: $muted;
    text-style: italic;
    padding: 1 4;
}

/* -- Bloque de error -- */
.error-block {
    color: $accent2;
    background: $bg2;
    border: round $accent2;
    margin: 1 8 1 2;
    padding: 1 2;
}

/* -- Coste y sesion en la barra de estado -- */
#status-cost {
    color: $accent3;
}
#status-git {
    color: $accent4;
}
"""

