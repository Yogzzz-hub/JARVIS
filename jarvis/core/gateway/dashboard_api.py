"""Read / manage endpoints the desktop dashboard uses: remembered facts, to-dos, shortcuts and live diagnostics.

Local only (the gateway binds 127.0.0.1 and refuses browser-origin writes). Nothing here runs a PC action.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class FactBody(BaseModel):
    fact: str = Field(min_length=1, max_length=500)


def _store():
    from jarvis.tools.system.everyday_tools import PersonalStore
    return PersonalStore()


def memory_snapshot(store: Any = None) -> dict[str, Any]:
    store = store or _store()
    with store.connect() as con:
        facts = [{"id": r[0], "fact": r[1], "created_at": r[2]}
                 for r in con.execute("SELECT id, fact, created_at FROM memory_facts ORDER BY id DESC LIMIT 200")]
        todos = [{"id": r[0], "text": r[1], "done": bool(r[2])}
                 for r in con.execute("SELECT id, text, done FROM todos ORDER BY done, id DESC LIMIT 200")]
    shortcuts = [{"phrase": p, "steps": s} for p, s in store.shortcuts().items()]
    return {"facts": facts, "todos": todos, "shortcuts": shortcuts}


def register(app: FastAPI, runtime: Any = None) -> None:
    @app.get("/dashboard/memory")
    async def memory() -> dict[str, Any]:
        return await asyncio.to_thread(memory_snapshot)

    @app.post("/dashboard/memory/facts")
    async def add_fact(body: FactBody) -> dict[str, Any]:
        store = _store()
        fid = await asyncio.to_thread(store.add_fact, body.fact.strip())
        return {"id": fid, "message": "Remembered."}

    @app.delete("/dashboard/memory/facts/{fact_id}")
    async def delete_fact(fact_id: int) -> dict[str, Any]:
        store = _store()

        def run() -> int:
            with store._lock, store.connect() as con:
                return con.execute("DELETE FROM memory_facts WHERE id = ?", (fact_id,)).rowcount
        if not await asyncio.to_thread(run):
            raise HTTPException(404, "That memory is already gone.")
        return {"message": "Forgotten."}

    @app.delete("/dashboard/memory/shortcuts/{phrase}")
    async def delete_shortcut(phrase: str) -> dict[str, Any]:
        if not await asyncio.to_thread(_store().delete_shortcut, phrase):
            raise HTTPException(404, "No shortcut with that phrase.")
        return {"message": "Shortcut deleted."}

    @app.get("/dashboard/diagnostics")
    async def diagnostics() -> dict[str, Any]:
        from jarvis.diagnostics import collect
        started = time.perf_counter()
        checks = await asyncio.to_thread(collect)
        for c in checks:  # the audio device table is long: one line is enough on a card
            c["detail"] = str(c.get("detail", "")).splitlines()[0][:300] if c.get("detail") else ""
        return {"checks": checks, "ms": round((time.perf_counter() - started) * 1000)}
