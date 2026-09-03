"""Registro en disco de las conversaciones, para poder retomarlas mas tarde.

Term guarda aqui solo los metadatos que necesita para reabrir una sesion; el
historial real vive en la CLI de Claude Code y se recupera con `--resume`.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import CONFIG_DIR, SESSIONS_PATH

__all__ = ["SessionRecord", "SessionStore"]

# Cuantas sesiones conservamos. Sin tope, sessions.json crece sin fin y
# /sessions acaba siendo una lista inmanejable.
_MAX_RECORDS = 50


@dataclass
class SessionRecord:
    session_id: str
    title: str = ""
    workdir: str = ""
    model: str = "default"
    messages: int = 0
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    @property
    def age_label(self) -> str:
        delta = time.time() - self.updated
        if delta < 60:
            return "ahora"
        if delta < 3600:
            return f"hace {int(delta // 60)} min"
        if delta < 86400:
            return f"hace {int(delta // 3600)} h"
        return f"hace {int(delta // 86400)} d"


class SessionStore:
    """Lista de sesiones ordenada de la mas reciente a la mas antigua."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or SESSIONS_PATH
        self.records: list[SessionRecord] = []
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.records = []
            return
        if not isinstance(raw, list):
            self.records = []
            return
        records = []
        for item in raw:
            if not isinstance(item, dict) or not item.get("session_id"):
                continue
            allowed = {k: v for k, v in item.items()
                       if k in SessionRecord.__dataclass_fields__}
            try:
                records.append(SessionRecord(**allowed))
            except TypeError:
                continue
        self.records = sorted(records, key=lambda r: r.updated, reverse=True)

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=CONFIG_DIR, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump([asdict(r) for r in self.records[:_MAX_RECORDS]],
                          fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            return False
        return True

    def touch(
        self,
        session_id: str,
        *,
        title: str = "",
        workdir: str = "",
        model: str = "",
        messages: int = 0,
    ) -> SessionRecord:
        """Crear o actualizar el registro de una sesion y subirlo al principio."""
        for record in self.records:
            if record.session_id == session_id:
                if title:
                    record.title = title
                if workdir:
                    record.workdir = workdir
                if model:
                    record.model = model
                if messages:
                    record.messages = messages
                record.updated = time.time()
                self.records.remove(record)
                self.records.insert(0, record)
                self.save()
                return record

        record = SessionRecord(
            session_id=session_id, title=title, workdir=workdir,
            model=model or "default", messages=messages,
        )
        self.records.insert(0, record)
        del self.records[_MAX_RECORDS:]
        self.save()
        return record

    def get(self, index: int) -> SessionRecord | None:
        """Registro por su posicion en la lista que ve el usuario (1-based)."""
        if 1 <= index <= len(self.records):
            return self.records[index - 1]
        return None

    def remove(self, session_id: str) -> bool:
        before = len(self.records)
        self.records = [r for r in self.records if r.session_id != session_id]
        if len(self.records) != before:
            self.save()
            return True
        return False
