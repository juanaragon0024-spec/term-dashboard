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
    ListItem,
    ListView,
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

VERSION = "2.2.0"

# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------

LANGUAGES = {
    "es": "Espanol",
    "en": "English",
    "pt": "Portugues",
    "fr": "Francais",
    "de": "Deutsch",
    "it": "Italiano",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
}

# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------

TRANSLATIONS: dict[str, dict[str, str]] = {
    "es": {
        "effort_label": "Esfuerzo",
        "context_label": "Contexto",
        "model_label": "Modelo",
        "dir_label": "Dir",
        "processing": " Procesando...",
        "placeholder": "Mensaje o /comando...",
        "write_or_help": "Escribe un mensaje o /help para comandos",
        "commands_available": "Comandos disponibles",
        "theme_set": "Tema",
        "themes_list": "Temas",
        "effort_set": "Esfuerzo",
        "levels": "Niveles",
        "model_set": "Modelo",
        "models_list": "Modelos",
        "dir_set": "Dir",
        "not_found": "No encontrado",
        "save_done": "Configuracion guardada",
        "about": "Term v{version}",
        "models_available": "Modelos disponibles",
        "themes_available": "Temas disponibles",
        "active_marker": "<< activo",
        "connected": "conectado",
        "disconnected": "desconectado",
        "context_reset": "Contexto reiniciado a 0",
        "open_usage": "Uso: /open <nombre de app>",
        "opening": "Abriendo {name}...",
        "run_usage": "Uso: /run <comando>",
        "no_output": "(sin salida)",
        "cmd_timeout": "Comando agotado (10s)",
        "volume_usage": "Uso: /volume <0-100>",
        "volume_set": "Volumen: {val}%",
        "play_pause": "Play/Pausa",
        "next_track": "Siguiente cancion",
        "prev_track": "Cancion anterior",
        "copied": "Copiado al portapapeles",
        "copy_error": "Error al copiar: {err}",
        "no_response_copy": "No hay respuesta para copiar",
        "messages_count": "Mensajes en esta tab: {count}",
        "exported": "Exportado a {path}",
        "export_error": "Error al exportar: {err}",
        "no_active_chat": "No hay chat activo",
        "compact_tip": "Consejo: conversaciones largas usan mas contexto. Usa /clear para empezar de nuevo, o /reset para reiniciar el contador.",
        "cannot_close_last": "No se puede cerrar la ultima tab",
        "unknown_cmd": "Comando desconocido: {cmd}. Prueba /help",
        "select_model": "Selecciona modelo para la nueva tab",
        "type_number": "Escribe el numero (1-{n}) o el nombre del modelo",
        "invalid_model": "Modelo invalido: {text}",
        "perms_title": "Term necesita permisos para funcionar correctamente.",
        "perms_accept": "Al aceptar, Term podra:",
        "perms_apps": "Aplicaciones     Abrir y controlar apps (Safari, Spotify, etc.)",
        "perms_files": "Archivos         Leer y escribir archivos en tu directorio de trabajo",
        "perms_system": "Sistema          Ajustar volumen, ejecutar comandos shell",
        "perms_config": "Configuracion    Guardar preferencias en ~/.config/term/",
        "perms_net": "Red              Conectar con la IA via OAuth",
        "perms_local": "Todos los comandos se ejecutan localmente en tu maquina.",
        "perms_oauth": "Term usa tu autenticacion OAuth existente.",
        "perms_question": "Aceptar permisos? (s/n)",
        "perms_granted": "Permisos concedidos",
        "perms_denied": "Permisos denegados -- funciones de sistema desactivadas",
        "select_browser": "Selecciona navegador",
        "type_browser_number": "Escribe el numero (1-{n}) o el nombre",
        "set_default_browser": "Usa /browser <nombre> para establecer uno por defecto",
        "browser_not_found": "Navegador no encontrado: {text}",
        "no_browsers": "No se encontraron navegadores instalados",
        "default_browser_set": "Navegador por defecto: {name}",
        "not_installed": "{name} no esta instalado",
        "valid_names": "Nombres validos: {names}",
        "current_browser": "Navegador actual: {name}",
        "no_default_browser": "Sin navegador por defecto. Usa /browser <nombre>",
        "lang_current": "Idioma actual: {lang}",
        "lang_available": "Idiomas disponibles",
        "lang_set": "Idioma cambiado a: {lang}",
        "lang_invalid": "Idioma no valido: {code}. Usa /lang para ver opciones",
        "lang_usage": "Usa /lang <codigo> para cambiar (ej. /lang en)",
        # Settings panel
        "settings_title": "Ajustes",
        "available": "Disponibles",
        "change_cmd": "Cambiar",
        "save_cmd": "/save para guardar ajustes en disco",
        # Apps panel
        "cli_apps_title": "Aplicaciones CLI instaladas",
        "apps_hint": "Tambien puedes pedir en el chat: 'abrir Safari', 'pon musica en Spotify', etc.",
        # Tools panel
        "tools_title": "Herramientas conectadas",
        # Help panel
        "term_subtitle": "TUI con IA",
        "what_is": "Que es Term?",
        "what_is_desc": "Una TUI que conecta con modelos de IA via OAuth CLI.\n  Chatea, controla tu Mac, abre apps, cambia musica,\n  y mas -- todo desde tu terminal.",
        "commands_title": "Comandos",
        "shortcuts_title": "Atajos de teclado",
        "system_examples": "Ejemplos de control del sistema",
        "config_path": "Config: {path}",
        # Bindings
        "quit": "Salir",
        "clear": "Limpiar",
        "new_tab": "Nueva tab",
        "close_tab": "Cerrar tab",
        "effort_binding": "Esfuerzo",
        "cancel": "Cancelar",
        # User/Assistant labels for export
        "user_label": "Usuario",
        "assistant_label": "Asistente",
    },
    "en": {
        "effort_label": "Effort",
        "context_label": "Context",
        "model_label": "Model",
        "dir_label": "Dir",
        "processing": " Processing...",
        "placeholder": "Message or /command...",
        "write_or_help": "Type a message or /help for commands",
        "commands_available": "Available commands",
        "theme_set": "Theme",
        "themes_list": "Themes",
        "effort_set": "Effort",
        "levels": "Levels",
        "model_set": "Model",
        "models_list": "Models",
        "dir_set": "Dir",
        "not_found": "Not found",
        "save_done": "Configuration saved",
        "about": "Term v{version}",
        "models_available": "Available models",
        "themes_available": "Available themes",
        "active_marker": "<< active",
        "connected": "connected",
        "disconnected": "disconnected",
        "context_reset": "Context reset to 0",
        "open_usage": "Usage: /open <app name>",
        "opening": "Opening {name}...",
        "run_usage": "Usage: /run <command>",
        "no_output": "(no output)",
        "cmd_timeout": "Command timed out (10s)",
        "volume_usage": "Usage: /volume <0-100>",
        "volume_set": "Volume: {val}%",
        "play_pause": "Play/Pause",
        "next_track": "Next track",
        "prev_track": "Previous track",
        "copied": "Copied to clipboard",
        "copy_error": "Copy error: {err}",
        "no_response_copy": "No response to copy",
        "messages_count": "Messages in this tab: {count}",
        "exported": "Exported to {path}",
        "export_error": "Export error: {err}",
        "no_active_chat": "No active chat",
        "compact_tip": "Tip: long conversations use more context. Use /clear to start fresh, or /reset to reset the counter.",
        "cannot_close_last": "Cannot close the last tab",
        "unknown_cmd": "Unknown command: {cmd}. Try /help",
        "select_model": "Select model for new tab",
        "type_number": "Type the number (1-{n}) or model name",
        "invalid_model": "Invalid model: {text}",
        "perms_title": "Term needs permissions to work correctly.",
        "perms_accept": "By accepting, Term will be able to:",
        "perms_apps": "Applications     Open and control apps (Safari, Spotify, etc.)",
        "perms_files": "Files            Read and write files in your working directory",
        "perms_system": "System           Adjust volume, run shell commands",
        "perms_config": "Configuration    Save preferences in ~/.config/term/",
        "perms_net": "Network          Connect to AI via OAuth",
        "perms_local": "All commands run locally on your machine.",
        "perms_oauth": "Term uses your existing OAuth authentication.",
        "perms_question": "Accept permissions? (y/n)",
        "perms_granted": "Permissions granted",
        "perms_denied": "Permissions denied -- system functions disabled",
        "select_browser": "Select browser",
        "type_browser_number": "Type the number (1-{n}) or the name",
        "set_default_browser": "Use /browser <name> to set a default",
        "browser_not_found": "Browser not found: {text}",
        "no_browsers": "No installed browsers found",
        "default_browser_set": "Default browser: {name}",
        "not_installed": "{name} is not installed",
        "valid_names": "Valid names: {names}",
        "current_browser": "Current browser: {name}",
        "no_default_browser": "No default browser. Use /browser <name>",
        "lang_current": "Current language: {lang}",
        "lang_available": "Available languages",
        "lang_set": "Language changed to: {lang}",
        "lang_invalid": "Invalid language: {code}. Use /lang to see options",
        "lang_usage": "Use /lang <code> to change (e.g. /lang es)",
        "settings_title": "Settings",
        "available": "Available",
        "change_cmd": "Change",
        "save_cmd": "/save to save settings to disk",
        "cli_apps_title": "Installed CLI applications",
        "apps_hint": "You can also ask in chat: 'open Safari', 'play music on Spotify', etc.",
        "tools_title": "Connected tools",
        "term_subtitle": "AI-powered TUI",
        "what_is": "What is Term?",
        "what_is_desc": "A TUI that connects to AI models via OAuth CLI.\n  Chat, control your Mac, open apps, change music,\n  and more -- all from your terminal.",
        "commands_title": "Commands",
        "shortcuts_title": "Keyboard shortcuts",
        "system_examples": "System control examples",
        "config_path": "Config: {path}",
        "quit": "Quit",
        "clear": "Clear",
        "new_tab": "New tab",
        "close_tab": "Close tab",
        "effort_binding": "Effort",
        "cancel": "Cancel",
        "user_label": "User",
        "assistant_label": "Assistant",
    },
    "pt": {
        "effort_label": "Esforco",
        "context_label": "Contexto",
        "model_label": "Modelo",
        "dir_label": "Dir",
        "processing": " Processando...",
        "placeholder": "Mensagem ou /comando...",
        "write_or_help": "Digite uma mensagem ou /help para comandos",
        "commands_available": "Comandos disponiveis",
        "theme_set": "Tema",
        "themes_list": "Temas",
        "effort_set": "Esforco",
        "levels": "Niveis",
        "model_set": "Modelo",
        "models_list": "Modelos",
        "dir_set": "Dir",
        "not_found": "Nao encontrado",
        "save_done": "Configuracao salva",
        "about": "Term v{version}",
        "models_available": "Modelos disponiveis",
        "themes_available": "Temas disponiveis",
        "active_marker": "<< ativo",
        "connected": "conectado",
        "disconnected": "desconectado",
        "context_reset": "Contexto reiniciado para 0",
        "open_usage": "Uso: /open <nome do app>",
        "opening": "Abrindo {name}...",
        "run_usage": "Uso: /run <comando>",
        "no_output": "(sem saida)",
        "cmd_timeout": "Comando expirou (10s)",
        "volume_usage": "Uso: /volume <0-100>",
        "volume_set": "Volume: {val}%",
        "play_pause": "Play/Pausa",
        "next_track": "Proxima musica",
        "prev_track": "Musica anterior",
        "copied": "Copiado para a area de transferencia",
        "copy_error": "Erro ao copiar: {err}",
        "no_response_copy": "Sem resposta para copiar",
        "messages_count": "Mensagens nesta aba: {count}",
        "exported": "Exportado para {path}",
        "export_error": "Erro ao exportar: {err}",
        "no_active_chat": "Sem chat ativo",
        "compact_tip": "Dica: conversas longas usam mais contexto. Use /clear para comecar de novo, ou /reset para reiniciar o contador.",
        "cannot_close_last": "Nao e possivel fechar a ultima aba",
        "unknown_cmd": "Comando desconhecido: {cmd}. Tente /help",
        "select_model": "Selecione modelo para nova aba",
        "type_number": "Digite o numero (1-{n}) ou nome do modelo",
        "invalid_model": "Modelo invalido: {text}",
        "perms_title": "Term precisa de permissoes para funcionar corretamente.",
        "perms_accept": "Ao aceitar, Term podera:",
        "perms_apps": "Aplicativos      Abrir e controlar apps (Safari, Spotify, etc.)",
        "perms_files": "Arquivos         Ler e escrever arquivos no seu diretorio de trabalho",
        "perms_system": "Sistema          Ajustar volume, executar comandos shell",
        "perms_config": "Configuracao     Salvar preferencias em ~/.config/term/",
        "perms_net": "Rede             Conectar com a IA via OAuth",
        "perms_local": "Todos os comandos sao executados localmente na sua maquina.",
        "perms_oauth": "Term usa sua autenticacao OAuth existente.",
        "perms_question": "Aceitar permissoes? (s/n)",
        "perms_granted": "Permissoes concedidas",
        "perms_denied": "Permissoes negadas -- funcoes de sistema desativadas",
        "select_browser": "Selecione navegador",
        "type_browser_number": "Digite o numero (1-{n}) ou o nome",
        "set_default_browser": "Use /browser <nome> para definir um padrao",
        "browser_not_found": "Navegador nao encontrado: {text}",
        "no_browsers": "Nenhum navegador instalado encontrado",
        "default_browser_set": "Navegador padrao: {name}",
        "not_installed": "{name} nao esta instalado",
        "valid_names": "Nomes validos: {names}",
        "current_browser": "Navegador atual: {name}",
        "no_default_browser": "Sem navegador padrao. Use /browser <nome>",
        "lang_current": "Idioma atual: {lang}",
        "lang_available": "Idiomas disponiveis",
        "lang_set": "Idioma alterado para: {lang}",
        "lang_invalid": "Idioma invalido: {code}. Use /lang para ver opcoes",
        "lang_usage": "Use /lang <codigo> para mudar (ex. /lang en)",
        "settings_title": "Configuracoes",
        "available": "Disponiveis",
        "change_cmd": "Alterar",
        "save_cmd": "/save para salvar configuracoes no disco",
        "cli_apps_title": "Aplicativos CLI instalados",
        "apps_hint": "Voce tambem pode pedir no chat: 'abrir Safari', 'tocar musica no Spotify', etc.",
        "tools_title": "Ferramentas conectadas",
        "term_subtitle": "TUI com IA",
        "what_is": "O que e Term?",
        "what_is_desc": "Uma TUI que conecta com modelos de IA via OAuth CLI.\n  Converse, controle seu Mac, abra apps, mude musica,\n  e mais -- tudo do seu terminal.",
        "commands_title": "Comandos",
        "shortcuts_title": "Atalhos de teclado",
        "system_examples": "Exemplos de controle do sistema",
        "config_path": "Config: {path}",
        "quit": "Sair",
        "clear": "Limpar",
        "new_tab": "Nova aba",
        "close_tab": "Fechar aba",
        "effort_binding": "Esforco",
        "cancel": "Cancelar",
        "user_label": "Usuario",
        "assistant_label": "Assistente",
    },
    "fr": {
        "effort_label": "Effort",
        "context_label": "Contexte",
        "model_label": "Modele",
        "dir_label": "Rep",
        "processing": " Traitement...",
        "placeholder": "Message ou /commande...",
        "write_or_help": "Tapez un message ou /help pour les commandes",
        "commands_available": "Commandes disponibles",
        "theme_set": "Theme",
        "themes_list": "Themes",
        "effort_set": "Effort",
        "levels": "Niveaux",
        "model_set": "Modele",
        "models_list": "Modeles",
        "dir_set": "Rep",
        "not_found": "Non trouve",
        "save_done": "Configuration sauvegardee",
        "about": "Term v{version}",
        "models_available": "Modeles disponibles",
        "themes_available": "Themes disponibles",
        "active_marker": "<< actif",
        "connected": "connecte",
        "disconnected": "deconnecte",
        "context_reset": "Contexte reinitialise a 0",
        "open_usage": "Utilisation: /open <nom app>",
        "opening": "Ouverture de {name}...",
        "run_usage": "Utilisation: /run <commande>",
        "no_output": "(pas de sortie)",
        "cmd_timeout": "Commande expiree (10s)",
        "volume_usage": "Utilisation: /volume <0-100>",
        "volume_set": "Volume: {val}%",
        "play_pause": "Play/Pause",
        "next_track": "Piste suivante",
        "prev_track": "Piste precedente",
        "copied": "Copie dans le presse-papiers",
        "copy_error": "Erreur de copie: {err}",
        "no_response_copy": "Pas de reponse a copier",
        "messages_count": "Messages dans cet onglet: {count}",
        "exported": "Exporte vers {path}",
        "export_error": "Erreur d'export: {err}",
        "no_active_chat": "Pas de chat actif",
        "compact_tip": "Conseil: les longues conversations utilisent plus de contexte. Utilisez /clear pour recommencer, ou /reset pour reinitialiser le compteur.",
        "cannot_close_last": "Impossible de fermer le dernier onglet",
        "unknown_cmd": "Commande inconnue: {cmd}. Essayez /help",
        "select_model": "Selectionnez le modele pour le nouvel onglet",
        "type_number": "Tapez le numero (1-{n}) ou le nom du modele",
        "invalid_model": "Modele invalide: {text}",
        "perms_title": "Term a besoin de permissions pour fonctionner correctement.",
        "perms_accept": "En acceptant, Term pourra:",
        "perms_apps": "Applications     Ouvrir et controler des apps (Safari, Spotify, etc.)",
        "perms_files": "Fichiers         Lire et ecrire des fichiers dans votre repertoire de travail",
        "perms_system": "Systeme          Ajuster le volume, executer des commandes shell",
        "perms_config": "Configuration    Sauvegarder les preferences dans ~/.config/term/",
        "perms_net": "Reseau           Se connecter a l'IA via OAuth",
        "perms_local": "Toutes les commandes s'executent localement sur votre machine.",
        "perms_oauth": "Term utilise votre authentification OAuth existante.",
        "perms_question": "Accepter les permissions? (o/n)",
        "perms_granted": "Permissions accordees",
        "perms_denied": "Permissions refusees -- fonctions systeme desactivees",
        "select_browser": "Selectionnez le navigateur",
        "type_browser_number": "Tapez le numero (1-{n}) ou le nom",
        "set_default_browser": "Utilisez /browser <nom> pour definir un defaut",
        "browser_not_found": "Navigateur non trouve: {text}",
        "no_browsers": "Aucun navigateur installe trouve",
        "default_browser_set": "Navigateur par defaut: {name}",
        "not_installed": "{name} n'est pas installe",
        "valid_names": "Noms valides: {names}",
        "current_browser": "Navigateur actuel: {name}",
        "no_default_browser": "Pas de navigateur par defaut. Utilisez /browser <nom>",
        "lang_current": "Langue actuelle: {lang}",
        "lang_available": "Langues disponibles",
        "lang_set": "Langue changee en: {lang}",
        "lang_invalid": "Langue invalide: {code}. Utilisez /lang pour voir les options",
        "lang_usage": "Utilisez /lang <code> pour changer (ex. /lang en)",
        "settings_title": "Parametres",
        "available": "Disponibles",
        "change_cmd": "Changer",
        "save_cmd": "/save pour sauvegarder les parametres sur le disque",
        "cli_apps_title": "Applications CLI installees",
        "apps_hint": "Vous pouvez aussi demander dans le chat: 'ouvrir Safari', 'mettre de la musique sur Spotify', etc.",
        "tools_title": "Outils connectes",
        "term_subtitle": "TUI avec IA",
        "what_is": "Qu'est-ce que Term?",
        "what_is_desc": "Un TUI qui se connecte aux modeles d'IA via OAuth CLI.\n  Discutez, controlez votre Mac, ouvrez des apps, changez la musique,\n  et plus -- tout depuis votre terminal.",
        "commands_title": "Commandes",
        "shortcuts_title": "Raccourcis clavier",
        "system_examples": "Exemples de controle du systeme",
        "config_path": "Config: {path}",
        "quit": "Quitter",
        "clear": "Effacer",
        "new_tab": "Nouvel onglet",
        "close_tab": "Fermer l'onglet",
        "effort_binding": "Effort",
        "cancel": "Annuler",
        "user_label": "Utilisateur",
        "assistant_label": "Assistant",
    },
}

# Fallback: for languages without full translation, use Spanish
for _code in LANGUAGES:
    if _code not in TRANSLATIONS:
        TRANSLATIONS[_code] = TRANSLATIONS["es"]

# ---------------------------------------------------------------------------
# System prompt for macOS control
# ---------------------------------------------------------------------------

SYSTEM_CONTEXT_BASE = (
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


def _build_system_context(lang: str) -> str:
    lang_name = LANGUAGES.get(lang, "Espanol")
    lang_instruction = f"\n\nIMPORTANT: Always respond in {lang_name} ({lang})."
    return SYSTEM_CONTEXT_BASE + lang_instruction

# ---------------------------------------------------------------------------
# Command reference
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
    "/browse [url]":          "Abrir URL en navegador (selector de navegadores)",
    "/browser <nombre>":      "Establecer navegador por defecto (brave, chrome, safari)",
    "/lang [codigo]":         "Cambiar idioma (es, en, pt, fr, de, it, zh, ja, ko, ar)",
    "/files":                 "Refrescar panel de archivos",
    "/attach <ruta>":         "Adjuntar archivo al siguiente mensaje",
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
        "lang": "es",
    }


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

# ---------------------------------------------------------------------------
# Detect installed CLI apps
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Detect installed browsers
# ---------------------------------------------------------------------------

BROWSER_MAP = {
    "Safari": "Safari",
    "Google Chrome": "Google Chrome",
    "Brave Browser": "Brave Browser",
    "Firefox": "Firefox",
    "Microsoft Edge": "Microsoft Edge",
    "Opera": "Opera",
    "Arc": "Arc",
    "Vivaldi": "Vivaldi",
    "Zen Browser": "Zen Browser",
}

BROWSER_ALIASES = {
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


def _detect_browsers() -> list[dict]:
    found = []
    apps_dir = Path("/Applications")
    for name, app_name in BROWSER_MAP.items():
        if (apps_dir / f"{app_name}.app").exists():
            found.append({"name": name, "app": app_name})
    return found

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

/* -- Top bar -- */
#top-bar {
    dock: top;
    height: 2;
    background: $bg2;
    border-bottom: solid $border;
    padding: 0 2;
}
#top-bar-title {
    color: $accent1;
    text-style: bold;
    width: 1fr;
    padding: 0 1;
}
#theme-label {
    color: $muted;
    dock: right;
    padding: 0 2;
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
    padding: 0 3;
    min-width: 12;
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
    height: 3;
    background: $bg1;
    padding: 0 20 0 20;
}
.input-bar Input {
    background: $bg1;
    color: $text;
    border: none;
}
.input-bar Input:focus {
    border: none;
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
    dock: bottom;
    height: 2;
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
    height: 2;
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
            yield Static("", classes="cmd-suggestions", id=f"cmdsug-{self.tab_id}")
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
        cfg = _load_config()
        self._context_tokens = 0
        self._max_context = 200_000
        self._tabs: dict[str, ChatTab] = {}
        self._apps = _detect_apps()
        self._browsers = _detect_browsers()
        self._default_browser: str = cfg.get("default_browser", "")
        self._active_panel = "chat"
        self._awaiting_model_selection: str | None = None
        self._pending_new_tab_name: str | None = None
        self._awaiting_browser_selection: str | None = None
        self._pending_browse_url: str = ""
        self._awaiting_permissions = False
        self._permissions_granted: bool = cfg.get("permissions_granted", False)
        self._lang: str = cfg.get("lang", "es")
        self._attached_content: str = ""
        super().__init__()
        self.workdir: str = workdir or cfg.get("workdir", str(Path.home()))
        self.theme_key = theme or cfg.get("theme", "neon")
        self.effort = cfg.get("effort", "high")
        self.current_model = cfg.get("model", "claude")

    # ------------------------------------------------------------------ i18n helper

    def _t(self, key: str, **kwargs: object) -> str:
        """Get translated string for current language."""
        strings = TRANSLATIONS.get(self._lang, TRANSLATIONS["es"])
        text = strings.get(key, TRANSLATIONS["es"].get(key, key))
        if kwargs:
            text = text.format(**kwargs)
        return text

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
        theme_name = THEMES.get(self.theme_key, THEMES["neon"])["name"]
        yield Horizontal(
            Label("[bold]TERM[/]", id="top-bar-title"),
            Label(f"Tema: {theme_name}", id="theme-label"),
            id="top-bar",
        )
        with Horizontal(id="main"):
            with Vertical(id="chat-col"):
                with TabbedContent(id="main-tabs"):
                    tab_id = self._next_tab_id()
                    chat = ChatTab(
                        self.current_model, tab_id, self.theme_key, self.workdir,
                    )
                    self._tabs[tab_id] = chat
                    with TabPane("Chat", id=f"pane-{tab_id}"):
                        yield chat
            with Vertical(id="file-panel"):
                yield Label(self.workdir, id="file-panel-title")
                yield ListView(id="file-list")
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

    def _update_tab_labels(self) -> None:
        """Update tab labels: active tab shows ' x' when 2+ tabs exist."""
        try:
            tc = self.query_one("#main-tabs", TabbedContent)
            active = tc.active
            for tid, chat in self._tabs.items():
                pane_id = f"pane-{tid}"
                try:
                    tab = tc.get_tab(pane_id)
                    label_text = str(tab.label)
                    # Strip existing ' x' suffix
                    if label_text.endswith(" x"):
                        label_text = label_text[:-2]
                    if pane_id == active and len(self._tabs) > 1:
                        tab.label = label_text + " x"
                    else:
                        tab.label = label_text
                except Exception:
                    pass
        except NoMatches:
            pass

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """When a tab is activated, update labels to show/hide close indicator."""
        self._update_tab_labels()

    async def on_mount(self) -> None:
        self._refresh_status()
        self._refresh_file_panel()
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
                f"[bold]{self._t('perms_title')}[/]\n\n"
                f"{self._t('perms_accept')}\n\n"
                f"  [bold]{self._t('perms_apps')}[/]\n"
                f"  [bold]{self._t('perms_files')}[/]\n"
                f"  [bold]{self._t('perms_system')}[/]\n"
                f"  [bold]{self._t('perms_config')}[/]\n"
                f"  [bold]{self._t('perms_net')}[/]\n\n"
                f"{self._t('perms_local')}\n"
                f"{self._t('perms_oauth')}\n\n"
                f"[bold]{self._t('perms_question')}[/]"
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
        # Update theme button label
        try:
            theme_name = THEMES.get(value, THEMES["neon"])["name"]
            self.query_one("#theme-label", Label).update(f"Tema: {theme_name}")
        except NoMatches:
            pass
        # Force full CSS refresh
        new_vars = self.get_css_variables()
        self.stylesheet.set_variables(new_vars)
        self.stylesheet.reparse()
        self.screen.update_node_styles()
        self.screen.refresh(layout=True)

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
                f"[bold]{self._t('effort_label')}:[/] {self.effort}"
            )
            self.query_one("#status-context", Label).update(
                f"[bold]{self._t('context_label')}:[/] [{bar}] {pct}% ({self._context_tokens:,}/{self._max_context:,})"
            )
            model_name = AI_MODELS.get(self.current_model, AI_MODELS["claude"])["name"]
            self.query_one("#status-model", Label).update(
                f"[bold]{self._t('model_label')}:[/] {model_name}"
            )
            wd = self.workdir
            if len(wd) > 30:
                wd = "..." + wd[-27:]
            self.query_one("#status-workdir", Label).update(f"[bold]{self._t('dir_label')}:[/] {wd}")
        except NoMatches:
            pass

    def _persist_config(self) -> None:
        _save_config({
            "theme": self.theme_key,
            "workdir": self.workdir,
            "effort": self.effort,
            "model": self.current_model,
            "permissions_granted": self._permissions_granted,
            "lang": self._lang,
        })

    def _refresh_file_panel(self) -> None:
        """Refresh file panel with contents of current workdir."""
        try:
            lv = self.query_one("#file-list", ListView)
            lv.clear()
            title = self.query_one("#file-panel-title", Label)
            wd = self.workdir
            if len(wd) > 24:
                wd = "..." + wd[-21:]
            title.update(wd)
            workpath = Path(self.workdir)
            if not workpath.is_dir():
                return
            # Parent directory entry
            lv.append(ListItem(Label("[dir] ..")))
            entries = sorted(workpath.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    lv.append(ListItem(Label(f"[dir] {entry.name}")))
                else:
                    lv.append(ListItem(Label(entry.name)))
        except (NoMatches, OSError):
            pass

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """When a file is selected in the file panel, handle navigation or attach."""
        try:
            label_widget = event.item.query_one(Label)
            text = str(label_widget.renderable)
        except Exception:
            return
        if text == "[dir] ..":
            parent = str(Path(self.workdir).parent)
            self.workdir = parent
            for chat in self._tabs.values():
                chat.workdir = parent
            self._refresh_status()
            self._refresh_file_panel()
            return
        if text.startswith("[dir] "):
            dirname = text.replace("[dir] ", "")
            new_path = str(Path(self.workdir) / dirname)
            if os.path.isdir(new_path):
                self.workdir = new_path
                for chat in self._tabs.values():
                    chat.workdir = new_path
                self._refresh_status()
                self._refresh_file_panel()
            return
        # Regular file -- append path to active input
        file_path = str(Path(self.workdir) / text)
        tab_id = self._active_tab_id()
        if tab_id:
            try:
                inp = self.query_one(f"#input-{tab_id}", Input)
                current = inp.value
                if current:
                    inp.value = current + " " + file_path
                else:
                    inp.value = file_path
                inp.focus()
            except NoMatches:
                pass

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
        self._active_panel = panel
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
                f"[bold]{self._t('settings_title')}[/]\n\n"
                f"{self._t('theme_set')}: [bold]{theme_name}[/]\n"
                f"  {self._t('available')}: {', '.join(THEMES.keys())}\n"
                f"  {self._t('change_cmd')}: [bold]/theme <nombre>[/]\n\n"
                f"{self._t('model_label')}: [bold]{model_name}[/]\n"
                f"  {self._t('available')}: {', '.join(AI_MODELS.keys())}\n"
                f"  {self._t('change_cmd')}: [bold]/model <nombre>[/]\n\n"
                f"{self._t('effort_label')}: [bold]{self.effort}[/]\n"
                f"  {self._t('levels')}: {', '.join(EFFORT_LEVELS)}\n"
                f"  {self._t('change_cmd')}: [bold]/effort <nivel>[/]\n\n"
                f"{self._t('dir_label')}: [bold]{self.workdir}[/]\n"
                f"  {self._t('change_cmd')}: [bold]/workdir <ruta>[/]\n\n"
                f"[bold]{self._t('save_cmd')}[/]"
            )
            await pane.mount(Static(content, classes="panel"))

        elif panel == "apps":
            cats: dict[str, list[dict]] = {}
            for app in self._apps:
                cats.setdefault(app["category"], []).append(app)
            lines = [f"[bold]{self._t('cli_apps_title')}[/]\n"]
            for cat, items in cats.items():
                lines.append(f"\n[bold]{cat}[/]")
                for it in items:
                    lines.append(f"  {it['name']} [dim]({it['cmd']})[/]")
            lines.append(
                f"\n[dim]{self._t('apps_hint')}[/]"
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
            lines = [f"[bold]{self._t('tools_title')}[/]\n"]
            for name, cmd, desc in checks:
                found = shutil.which(cmd) is not None
                marker = "[green bold]OK[/]" if found else "[red]NO[/]"
                lines.append(f"  {marker} [bold]{name}[/] - {desc}")
            await pane.mount(Static("\n".join(lines), classes="panel"))

        elif panel == "help":
            models_info = []
            for k, m in AI_MODELS.items():
                connected = shutil.which(m["cmd"][0]) is not None
                status = f"[green]{self._t('connected')}[/]" if connected else f"[red]{self._t('disconnected')}[/]"
                models_info.append(f"  [bold]{m['name']}[/] ({k}) {status}")

            lines = [
                _build_logo(self.theme_key),
                "",
                f"[bold]Term[/] -- {self._t('term_subtitle')}",
                "",
                f"[bold]{self._t('what_is')}[/]",
                f"  {self._t('what_is_desc')}",
                "",
                f"[bold]{self._t('models_available')}:[/]",
                *models_info,
                "",
                f"[bold]{self._t('commands_title')}:[/]",
            ]
            for cmd, desc in COMMANDS_HELP.items():
                lines.append(f"  [bold]{cmd:28s}[/] {desc}")
            lines.append("")
            lines.append(f"[bold]{self._t('shortcuts_title')}:[/]")
            for key, desc in SHORTCUTS_HELP.items():
                lines.append(f"  [bold]{key:28s}[/] {desc}")
            lines.extend([
                "",
                f"[bold]{self._t('system_examples')}:[/]",
                "  'abrir Safari'",
                "  'siguiente cancion en Spotify'",
                "  'pon el volumen a 50'",
                "  'abre la terminal'",
                "",
                f"[dim]{self._t('config_path', path=CONFIG_PATH)}[/]",
            ])
            await pane.mount(Static("\n".join(lines), classes="panel"))

    def _show_panel_sync(self, panel: str) -> None:
        self.run_worker(self._show_panel(panel), exclusive=True)

    # ------------------------------------------------------------ input handler

    def on_input_changed(self, event: Input.Changed) -> None:
        """Show command suggestions when typing /."""
        iid = event.input.id or ""
        if not iid.startswith("input-chat"):
            return
        tab_id = iid.replace("input-", "")
        text = event.value
        try:
            sug = self.query_one(f"#cmdsug-{tab_id}", Static)
        except NoMatches:
            return

        if text.startswith("/") and not text.startswith("/ "):
            query = text.lower()
            slash_cmds = {k: v for k, v in COMMANDS_HELP.items() if k.startswith("/")}
            matches = []
            for c, d in slash_cmds.items():
                if query == "/" or c.lower().startswith(query.split()[0]):
                    matches.append(f"  [bold]{c}[/]  [dim]{d}[/]")
            if matches:
                sug.update("\n".join(matches[:10]))
                sug.add_class("visible")
            else:
                sug.update("")
                sug.remove_class("visible")
        else:
            sug.update("")
            sug.remove_class("visible")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        iid = event.input.id or ""
        if not iid.startswith("input-chat"):
            return

        raw = event.value
        text = raw.strip()
        if not text:
            return

        tab_id = iid.replace("input-", "")

        # Hide command suggestions
        try:
            self.query_one(f"#cmdsug-{tab_id}", Static).remove_class("visible")
        except NoMatches:
            pass

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
                self.notify(self._t("perms_granted"), timeout=2)
                first_tab = next(iter(self._tabs.values()), None)
                if first_tab:
                    try:
                        msgs = self.query_one(f"#msgs-{first_tab.tab_id}", VerticalScroll)
                        logo = _build_logo(self.theme_key)
                        model = AI_MODELS.get(first_tab.model_key, AI_MODELS["claude"])
                        await msgs.mount(Static(
                            logo + "\n\n"
                            f"[dim]{model['name']} | {self._t('write_or_help')}[/]",
                            classes="info-block",
                        ))
                    except NoMatches:
                        pass
            else:
                self.notify(self._t("perms_denied"), timeout=3)
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
                self.notify(self._t("invalid_model", text=text), timeout=2)
                return
            await self._create_tab(self._pending_new_tab_name, selected)
            self._pending_new_tab_name = None
            return

        # Browser selection flow for /browse
        if self._awaiting_browser_selection == tab_id:
            event.input.value = ""
            self._awaiting_browser_selection = None
            try:
                self.query_one("#browser-selector").remove()
            except NoMatches:
                pass
            selected_browser = None
            if text.isdigit() and 1 <= int(text) <= len(self._browsers):
                selected_browser = self._browsers[int(text) - 1]["app"]
            else:
                for b in self._browsers:
                    if text.lower() in b["name"].lower() or text.lower() in b["app"].lower():
                        selected_browser = b["app"]
                        break
            if selected_browser:
                url = self._pending_browse_url or "https://www.google.com"
                subprocess.Popen(["open", "-a", selected_browser, url])
                self.notify(self._t("opening", name=selected_browser), timeout=1)
            else:
                self.notify(self._t("browser_not_found", text=text), timeout=2)
            self._pending_browse_url = ""
            return

        chat = self._tabs.get(tab_id)
        if chat is None or chat.is_loading:
            return

        event.input.value = ""

        # Bare "/" shows command list
        if text == "/":
            lines = [f"[bold]{self._t('commands_available')}:[/]\n"]
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

        # Prepend attached file content if any
        prompt = text
        if self._attached_content:
            prompt = self._attached_content + text
            self._attached_content = ""

        self._run_ai(chat, prompt)

    # ------------------------------------------------------------ slash commands

    async def _handle_command(self, text: str, tab_id: str) -> None:
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/theme":
            if arg in THEMES:
                self.theme_key = arg
                self.notify(f"{self._t('theme_set')}: {THEMES[arg]['name']}", timeout=1)
            else:
                self.notify(f"{self._t('themes_list')}: {', '.join(THEMES.keys())}", timeout=3)

        elif cmd == "/effort":
            if arg in EFFORT_LEVELS:
                self.effort = arg
                self._refresh_status()
                self.notify(f"{self._t('effort_set')}: {arg}", timeout=1)
            else:
                self.notify(f"{self._t('levels')}: {', '.join(EFFORT_LEVELS)}", timeout=2)

        elif cmd == "/model":
            if arg in AI_MODELS:
                self.current_model = arg
                chat = self._tabs.get(tab_id)
                if chat:
                    chat.model_key = arg
                self._refresh_status()
                self.notify(f"{self._t('model_set')}: {AI_MODELS[arg]['name']}", timeout=1)
            else:
                self.notify(f"{self._t('models_list')}: {', '.join(AI_MODELS.keys())}", timeout=2)

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
                    self._refresh_file_panel()
                    self.notify(f"{self._t('dir_set')}: {expanded}", timeout=1)
                else:
                    self.notify(f"{self._t('not_found')}: {arg}", timeout=2)

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
                    status = f"[green]{self._t('connected')}[/]" if connected else f"[red]{self._t('disconnected')}[/]"
                    items.append(
                        f"  [bold]{i}[/]) [bold]{m['name']}[/] ({k}) {status}"
                    )
                try:
                    msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                    await msgs.mount(Static(
                        f"[bold]{self._t('select_model')}:[/]\n\n"
                        + "\n".join(items)
                        + f"\n\n[dim]{self._t('type_number', n=len(AI_MODELS))}[/]",
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
            self.notify(self._t("save_done"), timeout=2)

        elif cmd == "/help":
            self._show_panel_sync("help")

        elif cmd == "/apps":
            self._show_panel_sync("apps")

        elif cmd == "/tools":
            self._show_panel_sync("tools")

        elif cmd == "/settings":
            self._show_panel_sync("settings")

        elif cmd == "/about":
            self.notify(self._t("about", version=VERSION), timeout=3)

        elif cmd == "/models":
            lines = [f"[bold]{self._t('models_available')}:[/]\n"]
            for i, (k, m) in enumerate(AI_MODELS.items(), 1):
                connected = shutil.which(m["cmd"][0]) is not None
                status = f"[green]{self._t('connected')}[/]" if connected else f"[red]{self._t('disconnected')}[/]"
                current = f" [bold cyan]{self._t('active_marker')}[/]" if k == self.current_model else ""
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
            lines = [f"[bold]{self._t('themes_available')}:[/]\n"]
            for k, t in THEMES.items():
                current = f" [bold cyan]{self._t('active_marker')}[/]" if k == self.theme_key else ""
                lines.append(f"  [bold]{t['name']}[/] ({k}){current}")
            try:
                msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                await msgs.mount(Static("\n".join(lines), classes="info-block"))
                msgs.scroll_end(animate=False)
            except NoMatches:
                pass

        elif cmd == "/status":
            self.notify(
                f"{self._t('theme_set')}: {THEMES[self.theme_key]['name']} | "
                f"{self._t('model_label')}: {AI_MODELS[self.current_model]['name']} | "
                f"{self._t('effort_label')}: {self.effort} | "
                f"{self._t('dir_label')}: {self.workdir}",
                timeout=5,
            )

        elif cmd == "/reset":
            self._context_tokens = 0
            self._refresh_status()
            self.notify(self._t("context_reset"), timeout=1)

        elif cmd == "/version":
            self.notify(self._t("about", version=VERSION), timeout=2)

        elif cmd == "/open":
            if arg:
                try:
                    subprocess.Popen(["open", "-a", arg])
                    self.notify(self._t("opening", name=arg), timeout=1)
                except Exception as e:
                    self.notify(f"Error: {e}", timeout=2)
            else:
                self.notify(self._t("open_usage"), timeout=2)

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
                    output = result.stdout or result.stderr or self._t("no_output")
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
                    self.notify(self._t("cmd_timeout"), timeout=2)
                except Exception as e:
                    self.notify(f"Error: {e}", timeout=2)
            else:
                self.notify(self._t("run_usage"), timeout=2)

        elif cmd == "/volume":
            if arg and arg.isdigit() and 0 <= int(arg) <= 100:
                subprocess.run(
                    ["osascript", "-e", f"set volume output volume {arg}"],
                    capture_output=True,
                )
                self.notify(self._t("volume_set", val=arg), timeout=1)
            else:
                self.notify(self._t("volume_usage"), timeout=2)

        elif cmd == "/play":
            subprocess.run(
                ["osascript", "-e", 'tell application "Spotify" to playpause'],
                capture_output=True,
            )
            self.notify(self._t("play_pause"), timeout=1)

        elif cmd == "/next":
            subprocess.run(
                ["osascript", "-e", 'tell application "Spotify" to next track'],
                capture_output=True,
            )
            self.notify(self._t("next_track"), timeout=1)

        elif cmd == "/prev":
            subprocess.run(
                ["osascript", "-e", 'tell application "Spotify" to previous track'],
                capture_output=True,
            )
            self.notify(self._t("prev_track"), timeout=1)

        elif cmd == "/copy":
            chat = self._tabs.get(tab_id)
            if chat and chat.last_response:
                try:
                    subprocess.run(
                        ["pbcopy"],
                        input=chat.last_response.encode(),
                        check=True,
                    )
                    self.notify(self._t("copied"), timeout=1)
                except Exception as e:
                    self.notify(self._t("copy_error", err=e), timeout=2)
            else:
                self.notify(self._t("no_response_copy"), timeout=2)

        elif cmd == "/history":
            chat = self._tabs.get(tab_id)
            count = chat.message_count if chat else 0
            self.notify(self._t("messages_count", count=count), timeout=2)

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
                            texts.append(f"[{self._t('user_label')}] {child.renderable}")
                        elif isinstance(child, AssistantMessage):
                            texts.append(f"[{self._t('assistant_label')}] {child._text}")
                        elif isinstance(child, Static):
                            texts.append(str(child.renderable))
                    path.write_text("\n\n".join(texts))
                    self.notify(self._t("exported", path=path), timeout=3)
                except Exception as e:
                    self.notify(self._t("export_error", err=e), timeout=2)
            else:
                self.notify(self._t("no_active_chat"), timeout=2)

        elif cmd == "/compact":
            self.notify(self._t("compact_tip"), timeout=5)

        elif cmd == "/restart":
            self.exit()
            os.execv(sys.executable, [sys.executable, "-m", "term.app"])

        elif cmd == "/browse":
            url = arg.strip() if arg else ""
            if self._default_browser:
                # Use default browser directly
                browser_app = self._default_browser
                open_url = url or "https://www.google.com"
                subprocess.Popen(["open", "-a", browser_app, open_url])
                self.notify(self._t("opening", name=browser_app), timeout=1)
            elif len(self._browsers) == 1:
                # Only one browser, use it
                open_url = url or "https://www.google.com"
                subprocess.Popen(["open", "-a", self._browsers[0]["app"], open_url])
                self.notify(self._t("opening", name=self._browsers[0]["name"]), timeout=1)
            elif len(self._browsers) > 1:
                # Show selector
                self._pending_browse_url = url
                items = []
                for i, b in enumerate(self._browsers, 1):
                    items.append(f"  [bold]{i}[/]) {b['name']}")
                try:
                    msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                    await msgs.mount(Static(
                        f"[bold]{self._t('select_browser')}:[/]\n\n"
                        + "\n".join(items)
                        + f"\n\n[dim]{self._t('type_browser_number', n=len(self._browsers))}[/]"
                        + f"\n[dim]{self._t('set_default_browser')}[/]",
                        classes="info-block",
                        id="browser-selector",
                    ))
                    msgs.scroll_end(animate=False)
                except NoMatches:
                    pass
                self._awaiting_browser_selection = tab_id
            else:
                self.notify(self._t("no_browsers"), timeout=2)

        elif cmd == "/browser":
            if arg:
                alias = arg.lower().strip()
                if alias in BROWSER_ALIASES:
                    app_name = BROWSER_ALIASES[alias]
                    # Verify installed
                    if Path(f"/Applications/{app_name}.app").exists():
                        self._default_browser = app_name
                        cfg = _load_config()
                        cfg["default_browser"] = app_name
                        _save_config(cfg)
                        self.notify(self._t("default_browser_set", name=app_name), timeout=2)
                    else:
                        self.notify(self._t("not_installed", name=app_name), timeout=2)
                else:
                    aliases = ", ".join(BROWSER_ALIASES.keys())
                    self.notify(self._t("valid_names", names=aliases), timeout=3)
            else:
                if self._default_browser:
                    self.notify(self._t("current_browser", name=self._default_browser), timeout=2)
                else:
                    self.notify(self._t("no_default_browser"), timeout=2)

        elif cmd == "/lang":
            if arg:
                code = arg.lower().strip()
                if code in LANGUAGES:
                    self._lang = code
                    self._persist_config()
                    self._refresh_status()
                    self.notify(self._t("lang_set", lang=LANGUAGES[code]), timeout=2)
                else:
                    self.notify(self._t("lang_invalid", code=arg), timeout=3)
            else:
                lines = [f"[bold]{self._t('lang_available')}:[/]\n"]
                for code, name in LANGUAGES.items():
                    current = f" [bold cyan]{self._t('active_marker')}[/]" if code == self._lang else ""
                    lines.append(f"  [bold]{code}[/] - {name}{current}")
                lines.append(f"\n[dim]{self._t('lang_usage')}[/]")
                try:
                    msgs = self.query_one(f"#msgs-{tab_id}", VerticalScroll)
                    await msgs.mount(Static("\n".join(lines), classes="info-block"))
                    msgs.scroll_end(animate=False)
                except NoMatches:
                    pass

        elif cmd == "/files":
            try:
                fp = self.query_one("#file-panel")
                fp.toggle_class("visible")
                if fp.has_class("visible"):
                    self._refresh_file_panel()
            except NoMatches:
                pass

        elif cmd == "/attach":
            if arg:
                file_path = os.path.expanduser(arg.strip())
                if not os.path.isabs(file_path):
                    file_path = os.path.join(self.workdir, file_path)
                if os.path.isfile(file_path):
                    try:
                        content = Path(file_path).read_text(errors="replace")
                        if len(content) > 10000:
                            content = content[:10000] + "\n... (truncated)"
                        self._attached_content = f"[File: {file_path}]\n```\n{content}\n```\n\n"
                        self.notify(f"Attached: {os.path.basename(file_path)}", timeout=2)
                    except Exception as e:
                        self.notify(f"Error reading file: {e}", timeout=2)
                else:
                    self.notify(f"File not found: {file_path}", timeout=2)
            else:
                self.notify("Usage: /attach <path>", timeout=2)

        else:
            self.notify(self._t("unknown_cmd", cmd=cmd), timeout=2)

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
        self._update_tab_labels()

        await asyncio.sleep(0.1)
        try:
            self.query_one(f"#input-{tab_id}", Input).focus()
        except NoMatches:
            pass

    async def action_new_tab(self) -> None:
        await self._create_tab()

    async def action_close_tab(self) -> None:
        if len(self._tabs) <= 1:
            self.notify(self._t("cannot_close_last"), timeout=1)
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
            self._update_tab_labels()

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
        self.notify(f"{self._t('effort_set')}: {self.effort}", timeout=1)

    # ------------------------------------------------------------ AI execution

    @work(exclusive=False, thread=False)
    async def _run_ai(self, chat: ChatTab, prompt: str) -> None:
        model = AI_MODELS.get(chat.model_key, AI_MODELS["claude"])
        full_output = ""
        system_context = _build_system_context(self._lang)

        try:
            cmd_line = (
                model["cmd"]
                + [prompt]
                + model["args"]
                + ["--effort", self.effort]
                + ["--append-system-prompt", system_context]
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
