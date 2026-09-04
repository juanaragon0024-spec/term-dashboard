#!/usr/bin/env python3
"""Servidor MCP mínimo, solo para los tests.

Habla lo justo del protocolo —initialize, tools/list y tools/call— para poder
probar el cliente sin depender de npm ni de la red.
"""

from __future__ import annotations

import json
import sys

TOOLS = [
    {
        "name": "saludar",
        "description": "Devuelve un saludo",
        "inputSchema": {
            "type": "object",
            "properties": {"nombre": {"type": "string"}},
            "required": ["nombre"],
        },
    },
    {
        "name": "sumar",
        "description": "Suma dos números",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    },
]


def responder(mensaje: dict) -> dict | None:
    metodo = mensaje.get("method")
    ident = mensaje.get("id")

    if metodo == "initialize":
        return {"jsonrpc": "2.0", "id": ident, "result": {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "falso", "version": "1"},
        }}

    if metodo == "notifications/initialized":
        return None  # las notificaciones no llevan respuesta

    if metodo == "tools/list":
        return {"jsonrpc": "2.0", "id": ident, "result": {"tools": TOOLS}}

    if metodo == "tools/call":
        params = mensaje.get("params") or {}
        nombre = params.get("name")
        args = params.get("arguments") or {}
        if nombre == "saludar":
            texto = f"Hola, {args.get('nombre', 'nadie')}"
        elif nombre == "sumar":
            texto = str((args.get("a") or 0) + (args.get("b") or 0))
        else:
            return {"jsonrpc": "2.0", "id": ident,
                    "error": {"code": -32602, "message": f"no existe: {nombre}"}}
        return {"jsonrpc": "2.0", "id": ident,
                "result": {"content": [{"type": "text", "text": texto}]}}

    return {"jsonrpc": "2.0", "id": ident,
            "error": {"code": -32601, "message": f"método desconocido: {metodo}"}}


def main() -> None:
    # Una línea suelta que no es JSON: el cliente debe saltársela.
    print("servidor falso listo", file=sys.stdout, flush=True)
    for linea in sys.stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            mensaje = json.loads(linea)
        except ValueError:
            continue
        salida = responder(mensaje)
        if salida is not None:
            print(json.dumps(salida), flush=True)


if __name__ == "__main__":
    main()
