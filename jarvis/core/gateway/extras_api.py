"""Read-only extras: a reader-mode view of a public web page and the reasoning-brain status / diagnostics."""
from __future__ import annotations

import asyncio

from fastapi import HTTPException
from fastapi.responses import HTMLResponse


def register(app, runtime) -> None:
    @app.get("/api/reader", response_class=HTMLResponse)
    async def reader(url: str):
        """Fetch a public page server-side (SSRF-gated) and return a clean, script-free reading view."""
        from jarvis.tools.system.reader import read_article, reader_html
        try:
            article = await asyncio.wait_for(asyncio.to_thread(read_article, url), 20)
        except (ValueError, OSError) as exc:
            raise HTTPException(400, str(exc) or "Page could not be read") from exc
        except asyncio.TimeoutError as exc:
            raise HTTPException(504, "Page took too long to load") from exc
        return HTMLResponse(reader_html(article), headers={
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'self'",
            "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"})

    @app.get("/api/brain/status")
    async def brain_status():
        """Which brain answers (local Ollama / Claude Code), and whether Claude Code is installed and signed in."""
        out = {"local": {}}
        try:
            from jarvis.core.brain.claude_code import status
            out["claude"] = status()
        except Exception as exc:     # SDK missing or misconfigured: report it, never fail the dashboard
            out["claude"] = {"available": False, "last_error": str(exc)}
        try:
            from jarvis.core.llm.client import get_llm
            llm = get_llm()
            out["local"] = {"base_url": llm.base_url, "circuit_open": bool(llm._breaker_open()),
                            "last_error": llm.last_error}
        except Exception as exc:
            out["local"] = {"error": str(exc)}
        return out

    @app.get("/api/diagnostics")
    async def diagnostics():
        """One-glance health: brain, voice (wake / clap / talk-over), speech output and pending background records."""
        voice = runtime.voice_status() if hasattr(runtime, "voice_status") else {}
        executor = getattr(getattr(runtime, "service", None), "executor", None)
        return {"brain": await brain_status(), "voice": voice,
                "pending_records": len(getattr(executor, "_pending_records", ()) or ())}
