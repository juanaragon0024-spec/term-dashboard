#!/usr/bin/env python3
"""Ejecutor del banco de pruebas de Term.

Corre cada tarea contra el motor de verdad —el mismo `ChatSession` que usa la
TUI— en una carpeta desechable, y comprueba el resultado mirando el disco.

    python3 bench/run.py                      todas, con el modelo por defecto
    python3 bench/run.py --tag facil          solo las fáciles
    python3 bench/run.py --model opencode/…   con otro proveedor
    python3 bench/run.py --task arreglar-bug  una sola
    python3 bench/run.py --dry-run            sin llamar a ninguna IA

OJO: salvo con --dry-run, esto llama a la IA de verdad y gasta lo que gaste tu
proveedor. Empieza por --tag facil para hacerte una idea del coste.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ.parent))

from tasks import TASKS, Task, by_name, by_tag  # noqa: E402

from term.commands import build_system_context  # noqa: E402
from term.models import normalise_ref  # noqa: E402
from term.session import ChatSession  # noqa: E402
from term.syscontrol import IS_MACOS  # noqa: E402


@dataclass
class Resultado:
    task: str
    ok: bool
    detalle: str
    segundos: float = 0.0
    coste: float = 0.0
    turnos: int = 0
    herramientas: list[str] = field(default_factory=list)
    error: str = ""


def preparar(task: Task) -> Path:
    """Carpeta desechable con el estado inicial de la tarea."""
    base = Path(tempfile.mkdtemp(prefix=f"bench-{task.name}-"))
    for ruta, contenido in task.setup.items():
        destino = base / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")
    return base


async def ejecutar(task: Task, model_ref: str, verbose: bool) -> Resultado:
    carpeta = preparar(task)
    sesion = ChatSession()
    sesion.set_model_ref(model_ref)

    herramientas: list[str] = []
    coste = 0.0
    turnos = 0
    error = ""
    empezado = time.monotonic()

    prompt = (
        f"{task.prompt}\n\n"
        "Trabaja en el directorio actual. Cuando termines, di solo LISTO."
    )
    try:
        async for evento in sesion.run(
            prompt,
            effort="medium",
            workdir=str(carpeta),
            system_prompt=build_system_context("es", macos=IS_MACOS),
            max_turns=task.max_turns,
        ):
            if evento.kind == "tool":
                herramientas.append(evento.tool)
                if verbose:
                    print(f"      · {evento.tool} {evento.detail}"[:100])
            elif evento.kind == "result" and evento.usage:
                coste = evento.usage.total_cost_usd
                turnos = evento.usage.num_turns
            elif evento.kind == "error":
                error = evento.text
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    segundos = time.monotonic() - empezado
    try:
        ok, detalle = task.check(carpeta)
    except Exception as exc:
        ok, detalle = False, f"la comprobación falló: {exc}"

    shutil.rmtree(carpeta, ignore_errors=True)
    return Resultado(task.name, ok, detalle, segundos, coste, turnos,
                     herramientas, error)


def imprimir(resultado: Resultado) -> None:
    marca = "\033[32mBIEN\033[0m" if resultado.ok else "\033[31mMAL \033[0m"
    print(f"  {marca}  {resultado.task:24s} {resultado.segundos:5.1f}s"
          f"  ${resultado.coste:.4f}  {resultado.turnos:2d} turnos")
    print(f"        {resultado.detalle}")
    if resultado.herramientas:
        cuenta: dict[str, int] = {}
        for h in resultado.herramientas:
            cuenta[h] = cuenta.get(h, 0) + 1
        print("        usó: " + ", ".join(f"{k}×{v}" for k, v in cuenta.items()))
    if resultado.error:
        print(f"        \033[33merror:\033[0m {resultado.error[:150]}")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Banco de pruebas de Term")
    parser.add_argument("--model", default="claude/default",
                        help="proveedor/modelo, como en /model")
    parser.add_argument("--tag", help="solo las tareas con esta etiqueta")
    parser.add_argument("--task", help="una tarea concreta, por su nombre")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="enseñar las herramientas según se usan")
    parser.add_argument("--dry-run", action="store_true",
                        help="preparar y comprobar sin llamar a ninguna IA")
    parser.add_argument("--json", dest="como_json", metavar="RUTA",
                        help="guardar los resultados en un archivo JSON")
    args = parser.parse_args()

    if args.task:
        tarea = by_name(args.task)
        if tarea is None:
            print(f"No existe la tarea «{args.task}»", file=sys.stderr)
            return 2
        tareas = [tarea]
    elif args.tag:
        tareas = by_tag(args.tag)
        if not tareas:
            print(f"Ninguna tarea con la etiqueta «{args.tag}»", file=sys.stderr)
            return 2
    else:
        tareas = TASKS

    model_ref = normalise_ref(args.model)
    print(f"\nBanco de pruebas de Term — {len(tareas)} tareas · {model_ref}")
    if args.dry_run:
        print("Sin llamar a ninguna IA: solo se comprueba el montaje.\n")
    else:
        print("\033[33mEsto llama a la IA de verdad y gasta créditos.\033[0m\n")

    resultados: list[Resultado] = []
    for tarea in tareas:
        if args.dry_run:
            carpeta = preparar(tarea)
            ok, detalle = tarea.check(carpeta)
            shutil.rmtree(carpeta, ignore_errors=True)
            # En seco, lo esperable es que falle: nadie ha hecho el trabajo.
            resultados.append(Resultado(tarea.name, not ok,
                                        f"parte de un estado {'ya resuelto (mal)' if ok else 'sin resolver (bien)'}: {detalle}"))
        else:
            print(f"  ▶ {tarea.name}…")
            resultados.append(await ejecutar(tarea, model_ref, args.verbose))
        imprimir(resultados[-1])
        print()

    aciertos = sum(1 for r in resultados if r.ok)
    coste = sum(r.coste for r in resultados)
    segundos = sum(r.segundos for r in resultados)
    print("─" * 62)
    print(f"  {aciertos}/{len(resultados)} tareas completadas"
          f"   ·  ${coste:.4f}  ·  {segundos:.0f}s")

    if args.como_json:
        Path(args.como_json).write_text(json.dumps(
            [r.__dict__ for r in resultados], indent=2, ensure_ascii=False))
        print(f"  resultados en {args.como_json}")

    return 0 if aciertos == len(resultados) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
