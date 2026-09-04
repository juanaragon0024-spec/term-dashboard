"""Procesos que siguen corriendo mientras tu sigues trabajando.

`/run` sirve para un comando que termina: espera, devuelve la salida y ya. Un
servidor de desarrollo, unos tests en modo vigilancia o una compilacion no
terminan, o tardan minutos, y esperarlos bloqueando la interfaz es justo lo que
obliga a abrir otra terminal.

Aqui el proceso se lanza y se olvida: su salida se va guardando en un buffer y
se puede mirar cuando interese. Como el buffer esta en memoria, tambien puede
leerlo la IA, que es lo que permite preguntar «por que falla el build» sin
copiar y pegar nada.
"""

from __future__ import annotations

import asyncio
import contextlib
import shlex
import signal
import time
from collections import deque
from dataclasses import dataclass, field

__all__ = ["Job", "JobManager"]

# Lineas que se guardan por proceso. Un servidor lleva horas escribiendo: sin
# tope se comeria la memoria, y lo unico que interesa es el final.
_MAX_LINES = 2_000

# Lo que se le enseña a la IA de una vez. Mas que esto no cabe en el contexto
# y ademas casi nunca hace falta.
_AI_TAIL = 120


@dataclass
class Job:
    """Un proceso en marcha, o uno que ya terminó."""

    id: int
    command: str
    cwd: str
    proc: asyncio.subprocess.Process | None = None
    started: float = field(default_factory=time.time)
    finished_at: float = 0.0
    exit_code: int | None = None
    # Lo paramos nosotros, no se murio solo: la diferencia importa al leer
    # la lista, porque un proceso parado a mano no es un fallo.
    stopped: bool = False
    lines: deque[str] = field(default_factory=lambda: deque(maxlen=_MAX_LINES))
    _reader: asyncio.Task | None = field(default=None, repr=False)

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    @property
    def elapsed(self) -> float:
        return (self.finished_at or time.time()) - self.started

    @property
    def status(self) -> str:
        if self.running:
            return "corriendo"
        if self.stopped:
            return "parado"
        if self.exit_code == 0:
            return "terminado"
        if self.exit_code is None:
            return "parado"
        return f"falló ({self.exit_code})"

    @property
    def elapsed_label(self) -> str:
        segundos = int(self.elapsed)
        if segundos < 60:
            return f"{segundos}s"
        if segundos < 3600:
            return f"{segundos // 60}m {segundos % 60}s"
        return f"{segundos // 3600}h {(segundos % 3600) // 60}m"

    def tail(self, count: int = 40) -> str:
        """Las ultimas lineas de salida."""
        if not self.lines:
            return "(sin salida todavía)"
        return "\n".join(list(self.lines)[-count:])

    def search(self, texto: str, count: int = 40) -> str:
        """Las lineas que contienen un texto, para buscar un error concreto."""
        aguja = texto.lower()
        encontradas = [ln for ln in self.lines if aguja in ln.lower()]
        return "\n".join(encontradas[-count:]) if encontradas else ""


class JobManager:
    """Los procesos en segundo plano de esta sesion."""

    def __init__(self) -> None:
        self.jobs: dict[int, Job] = {}
        self._next_id = 0

    # ------------------------------------------------------------ arrancar

    async def start(self, command: str, cwd: str) -> Job:
        """Lanzar un comando y devolver enseguida, sin esperarlo."""
        self._next_id += 1
        job = Job(id=self._next_id, command=command, cwd=cwd)
        self.jobs[job.id] = job

        try:
            # Se usa una shell para que funcionen las tuberias y los comodines,
            # que es como la gente escribe estos comandos.
            job.proc = await asyncio.create_subprocess_shell(
                command,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,   # todo junto, como en la terminal
                cwd=cwd or None,
                # Grupo propio para poder parar al proceso y a sus hijos: un
                # `npm run dev` deja un servidor detras si solo matas al padre.
                start_new_session=True,
            )
        except OSError as exc:
            job.lines.append(f"no se pudo arrancar: {exc}")
            job.exit_code = -1
            job.finished_at = time.time()
            return job

        job._reader = asyncio.create_task(self._read(job))
        return job

    async def _read(self, job: Job) -> None:
        """Ir guardando la salida segun llega."""
        proc = job.proc
        if proc is None or proc.stdout is None:
            return
        try:
            while True:
                linea = await proc.stdout.readline()
                if not linea:
                    break
                job.lines.append(
                    linea.decode("utf-8", errors="replace").rstrip("\n"))
        except (asyncio.CancelledError, ValueError):
            raise
        finally:
            with contextlib.suppress(Exception):
                await proc.wait()
            job.exit_code = proc.returncode
            job.finished_at = time.time()

    # ------------------------------------------------------------ consultar

    def get(self, job_id: int) -> Job | None:
        return self.jobs.get(job_id)

    def latest(self) -> Job | None:
        """El ultimo lanzado, que es el que se suele querer mirar."""
        return self.jobs[max(self.jobs)] if self.jobs else None

    def running(self) -> list[Job]:
        return [j for j in self.jobs.values() if j.running]

    def listing(self) -> list[Job]:
        return sorted(self.jobs.values(), key=lambda j: j.id)

    # ------------------------------------------------------------ parar

    async def stop(self, job_id: int) -> bool:
        """Parar un proceso y a los hijos que haya dejado."""
        job = self.jobs.get(job_id)
        if job is None or job.proc is None or not job.running:
            return False

        import os

        job.stopped = True
        try:
            # Al grupo entero: matar solo al padre deja el servidor vivo.
            os.killpg(os.getpgid(job.proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            with contextlib.suppress(ProcessLookupError, OSError):
                job.proc.terminate()

        with contextlib.suppress(TimeoutError, Exception):
            await asyncio.wait_for(job.proc.wait(), 5)
        if job.running:
            with contextlib.suppress(ProcessLookupError, OSError):
                os.killpg(os.getpgid(job.proc.pid), signal.SIGKILL)

        if job._reader is not None:
            job._reader.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await job._reader
        job.finished_at = job.finished_at or time.time()
        return True

    async def stop_all(self) -> int:
        """Parar todo. Se llama al cerrar Term para no dejar nada suelto."""
        parados = 0
        for job_id in list(self.jobs):
            if await self.stop(job_id):
                parados += 1
        return parados

    def clear_finished(self) -> int:
        terminados = [i for i, j in self.jobs.items() if not j.running]
        for job_id in terminados:
            del self.jobs[job_id]
        return len(terminados)

    # ------------------------------------------------------------ para la IA

    def summary_for_ai(self) -> str:
        """Estado de los procesos, en el formato que se le pasa al modelo."""
        if not self.jobs:
            return "No hay ningún proceso en segundo plano."
        lineas = []
        for job in self.listing():
            lineas.append(
                f"[{job.id}] {job.command}  ({job.status}, {job.elapsed_label})")
        return "\n".join(lineas)

    def logs_for_ai(self, job_id: int | None = None, grep: str = "") -> str:
        """Los logs de un proceso, listos para que el modelo los lea."""
        job = self.get(job_id) if job_id else self.latest()
        if job is None:
            return "No hay ningún proceso con ese número."
        cabecera = f"[{job.id}] {job.command} — {job.status}\n\n"
        cuerpo = job.search(grep, _AI_TAIL) if grep else job.tail(_AI_TAIL)
        if not cuerpo:
            cuerpo = f"(ninguna línea contiene «{grep}»)"
        return cabecera + cuerpo


def looks_long_running(command: str) -> bool:
    """Si un comando pinta de los que no terminan solos.

    Sirve para sugerir /bg cuando alguien lanza un servidor con /run y se le
    queda la interfaz esperando.
    """
    try:
        piezas = shlex.split(command)
    except ValueError:
        piezas = command.split()
    texto = " ".join(piezas).lower()
    señales = (
        "runserver", "npm run dev", "yarn dev", "pnpm dev", "vite",
        "next dev", "serve", "watch", "--watch", "-w ", "nodemon",
        "uvicorn", "gunicorn", "flask run", "rails s", "docker compose up",
        "tail -f", "ping ",
    )
    return any(s in texto for s in señales)
