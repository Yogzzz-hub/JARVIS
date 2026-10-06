"""Read / manage endpoints the desktop dashboard uses: remembered facts, to-dos, shortcuts and live diagnostics.

Local only (the gateway binds 127.0.0.1 and refuses browser-origin writes). Nothing here runs a PC action.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field


class FactBody(BaseModel):
    fact: str = Field(min_length=1, max_length=500)


class LanguagePreviewBody(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
    mode: str = Field(default='automation_builder', pattern='^(automation_builder|conversation)$')


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
    import secrets
    from jarvis.core.audio.owner_benchmark import OwnerVoiceBenchmark
    benchmark = OwnerVoiceBenchmark(runtime)
    app.state.voice_benchmark = benchmark
    app.state.voice_benchmark_token = secrets.token_urlsafe(32)

    @app.get('/dashboard/voice-benchmark')
    async def benchmark_state():
        return await asyncio.to_thread(benchmark.state)

    @app.get('/dashboard/voice-benchmark/page')
    async def benchmark_page(request: Request):
        from pathlib import Path
        from fastapi.responses import HTMLResponse
        if request.headers.get('host', '') not in {'127.0.0.1:8765', 'localhost:8765', 'testserver'}:
            raise HTTPException(403, 'Local owner page only')
        html = Path(__file__).with_name('voice_benchmark.html').read_text(encoding='utf-8')
        return HTMLResponse(html.replace('__TOKEN__', app.state.voice_benchmark_token))

    def require_owner(request):
        if request.headers.get('host', '') not in {'127.0.0.1:8765', 'localhost:8765', 'testserver'} or not secrets.compare_digest(
                request.headers.get('x-jarvis-benchmark', ''), app.state.voice_benchmark_token):
            raise HTTPException(403, 'Local benchmark token required')

    @app.post('/dashboard/voice-benchmark/record')
    async def benchmark_record(request: Request, body: dict):
        require_owner(request)
        try:
            return await benchmark.record(body.get('sample_id'))
        except (ValueError, asyncio.TimeoutError) as exc:
            raise HTTPException(409, str(exc) or 'Microphone capture timed out')

    @app.post('/dashboard/voice-benchmark/rating')
    async def benchmark_rating(request: Request, body: dict):
        require_owner(request)
        try:
            await asyncio.to_thread(benchmark.rate, body.get('language'), body.get('rating'))
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return {'saved': True}

    @app.get('/dashboard/voice-benchmark/audio/{language}')
    async def benchmark_audio(language: str):
        from fastapi.responses import FileResponse
        from pathlib import Path
        names = {'english': 'english', 'tanglish': 'tanglish', 'tamil': 'tamil', 'mixed': 'mixed_tamil_english'}
        if language not in names:
            raise HTTPException(404, 'Unknown language')
        tts = getattr(getattr(getattr(runtime, 'service', None), 'response', None), 'tts', None)
        gender = getattr(tts, 'voice_gender', 'male')
        if gender not in {'male', 'female'}:
            raise HTTPException(503, 'Voice preference unavailable')
        path = Path('reports/voice_gender_evidence') / (gender + '_' + language + '.wav')
        if not path.exists():
            raise HTTPException(404, 'Listening sample unavailable')
        return FileResponse(path, media_type='audio/wav', headers={'Cache-Control': 'no-store'})

    @app.get('/dashboard/voice-language')
    async def voice_language_status():
        from jarvis.core.response.status import integration_status
        return await asyncio.to_thread(integration_status, runtime)

    @app.get('/dashboard/voice-language/page')
    async def voice_language_page():
        from fastapi.responses import HTMLResponse
        from pathlib import Path
        return HTMLResponse(Path(__file__).with_name('voice_language.html').read_text(encoding='utf-8'))

    @app.post("/dashboard/nlp/understand")
    async def language_preview(body: LanguagePreviewBody):
        from jarvis.core.language_shadow import get_language_service
        accepted = get_language_service().submit(body.text, 'dashboard', mode=body.mode)
        return {"queued": accepted, "controls_tools": False, "production_authoritative": True}

    @app.post('/dashboard/nlp/resolve-references')
    async def reference_preview(frame: dict):
        from jarvis.core.context.semantic_adapter import resolve_semantic_references
        memory = getattr(getattr(runtime, 'service', None), 'working_memory', None)
        if memory is None:
            return {'recommendation': 'CLARIFY', 'controls_tools': False, 'reason': 'WorkingContext unavailable'}
        if len(str(frame)) > 16384:
            raise HTTPException(413, 'Frame too large')
        return await asyncio.to_thread(resolve_semantic_references, frame, memory)

    @app.get("/dashboard/nlp/shadow")
    async def language_shadow():
        from jarvis.core.language_shadow import ShadowStore
        return await asyncio.to_thread(ShadowStore().state)

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

    @app.get("/dashboard/whatsapp/diagnostics")
    async def whatsapp_diagnostics() -> dict[str, Any]:
        from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
        service = getattr(runtime, "whatsapp_service", None)
        if service and service.transport.is_connected:
            response = await service.transport._call("get_status", timeout=3)
            if response.get("success"):
                service._on_bridge_status(response["result"])
        result = await asyncio.to_thread(WhatsAppInbox.get_default().diagnostics)
        intelligence = getattr(service, "intelligence", None)
        if intelligence is not None:
            result["intelligence"] = await asyncio.to_thread(intelligence.diagnostics)
        return result
