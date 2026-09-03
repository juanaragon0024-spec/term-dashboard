"""Temas de color y renderizado del logo."""

from __future__ import annotations

__all__ = ["DEFAULT_THEME", "THEMES", "build_logo", "theme_names"]

DEFAULT_THEME = "neon"

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


def theme_names() -> list[str]:
    """Claves de tema en orden de declaracion."""
    return list(THEMES)


def build_logo(theme_key: str = DEFAULT_THEME) -> str:
    """Render del logo ASCII con un degradado horizontal del tema."""
    grad = THEMES.get(theme_key, THEMES[DEFAULT_THEME])["grad"]
    width = max(len(line) for line in _LOGO)
    lines: list[str] = []
    for line in _LOGO:
        buf = ""
        for i, char in enumerate(line):
            if char == " ":
                buf += " "
            else:
                idx = int(i / max(width, 1) * (len(grad) - 1))
                buf += f"[bold {grad[idx]}]{char}[/]"
        lines.append(buf)
    return "\n".join(lines)
