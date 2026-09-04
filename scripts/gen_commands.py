#!/usr/bin/env python3
"""Genera el catálogo de comandos de la web a partir del de la terminal.

El panel de ayuda de la web tenía los comandos escritos a mano, y se quedó con
catorce mientras la terminal llegaba a ochenta y tres. Generándolo no se pueden
volver a desincronizar.

    python3 scripts/gen_commands.py

Marca además qué comandos funcionan en el navegador: la mayoría necesita acceso
al sistema y solo existe en la terminal, y decirlo es más honesto que ofrecer
un comando que no va a hacer nada.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "term"))

from term.commands import COMMAND_GROUPS, SHORTCUTS_HELP  # noqa: E402
from term.i18n import TRANSLATIONS  # noqa: E402

DESTINO = RAIZ / "frontend" / "src" / "commands.generated.ts"

# Comandos que la web sabe ejecutar. El resto se muestra, pero marcado como
# exclusivo de la terminal.
EN_LA_WEB = {
    "/new", "/close", "/clear", "/name", "/search", "/export", "/copy",
    "/model", "/effort", "/theme", "/workdir", "/save",
    "/help", "/apps", "/tools", "/settings", "/about", "/version", "/tab",
    "/files", "/map",
}

# Atajos que el navegador puede interceptar sin pelearse con los del sistema.
ATAJOS_WEB = {
    "ctrl+t": "Nueva pestaña",
    "ctrl+w": "Cerrar pestaña",
    "ctrl+l": "Limpiar el chat",
    "ctrl+e": "Cambiar el nivel de esfuerzo",
    "ctrl+k": "Ir a un panel",
    "enter": "Enviar el mensaje",
    "shift+enter": "Salto de línea",
    "escape": "Cancelar la generación",
}


def main() -> int:
    grupos = []
    for clave, comandos in COMMAND_GROUPS.items():
        titulo = TRANSLATIONS["es"].get(clave, clave)
        entradas = [
            {
                "cmd": cmd,
                "desc": desc,
                "web": cmd.split()[0] in EN_LA_WEB,
            }
            for cmd, desc in comandos.items()
        ]
        grupos.append({"key": clave, "title": titulo, "commands": entradas})

    cabecera = (
        "// Generado por scripts/gen_commands.py — no editar a mano.\n"
        "// Se genera desde term/commands.py para que la ayuda de la web y la\n"
        "// de la terminal no puedan desincronizarse.\n\n"
        "export interface CommandEntry {\n"
        "  cmd: string\n"
        "  desc: string\n"
        "  /** Si el navegador sabe ejecutarlo; si no, es solo de terminal. */\n"
        "  web: boolean\n"
        "}\n\n"
        "export interface CommandGroup {\n"
        "  key: string\n"
        "  title: string\n"
        "  commands: CommandEntry[]\n"
        "}\n\n"
    )
    cuerpo = (
        f"export const COMMAND_GROUPS: CommandGroup[] = {json.dumps(grupos, ensure_ascii=False, indent=2)}\n\n"
        f"export const SHORTCUTS: Record<string, string> = {json.dumps(ATAJOS_WEB, ensure_ascii=False, indent=2)}\n\n"
        f"export const TERMINAL_SHORTCUTS: Record<string, string> = {json.dumps(dict(SHORTCUTS_HELP), ensure_ascii=False, indent=2)}\n\n"
        "export const WEB_COMMANDS: string[] = COMMAND_GROUPS.flatMap((g) =>\n"
        "  g.commands.filter((c) => c.web).map((c) => c.cmd.split(' ')[0]),\n"
        ")\n"
    )
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(cabecera + cuerpo, encoding="utf-8")

    total = sum(len(g["commands"]) for g in grupos)
    en_web = sum(1 for g in grupos for c in g["commands"] if c["web"])
    print(f"{DESTINO.relative_to(RAIZ)}: {total} comandos en {len(grupos)} grupos, "
          f"{en_web} disponibles en la web")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
