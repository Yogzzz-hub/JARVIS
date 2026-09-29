"""Vision setup: the vision role only uses a model that can really see images, WhatsApp photos from the owner are read
with that role, and other people's photos are never sent to the vision model."""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from jarvis.core.llm.client import LLMSettings, LLMUnavailable, OllamaClient


def _client(caps: dict[str, list[str] | None], installed=("qwen3.5:4b", "qwen2.5vl:3b")) -> OllamaClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": m} for m in installed]})
        if request.url.path == "/api/show":
            import json
            model = json.loads(request.content)["model"]
            if caps.get(model) is None:
                return httpx.Response(404, json={"error": "unknown"})
            return httpx.Response(200, json={"capabilities": caps[model]})
        return httpx.Response(404)
    settings = LLMSettings(vision_model="qwen3.5:4b, qwen2.5vl:3b")
    return OllamaClient(settings, transport=httpx.MockTransport(handler))


def test_a_text_only_build_is_skipped_for_vision():
    client = _client({"qwen3.5:4b": ["completion", "tools"], "qwen2.5vl:3b": ["completion", "vision"]})
    assert client.resolve_sync("vision") == "qwen2.5vl:3b"
    assert asyncio.run(_client({"qwen3.5:4b": ["completion"], "qwen2.5vl:3b": ["completion", "vision"]}).resolve("vision")) == "qwen2.5vl:3b"


def test_the_preferred_model_is_kept_when_it_can_see():
    client = _client({"qwen3.5:4b": ["completion", "vision", "tools"], "qwen2.5vl:3b": ["completion", "vision"]})
    assert client.resolve_sync("vision") == "qwen3.5:4b"  # already loaded for chat: no second model to load


def test_unknown_capabilities_trust_the_configuration():
    assert _client({}).resolve_sync("vision") == "qwen3.5:4b"  # older Ollama without "capabilities"


def test_no_model_that_can_see_says_what_to_install():
    client = _client({"qwen3.5:4b": ["completion"]}, installed=("qwen3.5:4b",))
    with pytest.raises(LLMUnavailable, match="qwen2.5vl:3b"):
        client.resolve_sync("vision")


def test_whatsapp_image_provider_uses_the_vision_role(monkeypatch):
    from jarvis.core.llm import client as client_mod
    from jarvis.core.vision.providers.qwen3vl import Qwen3VLProvider

    class Fake:
        def resolve_sync(self, role):
            assert role == "vision"
            return "qwen2.5vl:3b"
    monkeypatch.setattr(client_mod, "get_llm", lambda: Fake())
    provider = Qwen3VLProvider()
    assert provider._model() == "qwen2.5vl:3b" and "vision role" in provider.model_name
    assert Qwen3VLProvider(model_name="llava:7b")._model() == "llava:7b"


@pytest.mark.asyncio
async def test_other_peoples_photos_are_not_sent_to_the_vision_model(tmp_path):
    from PIL import Image

    from jarvis.integrations.whatsapp.gateway import WhatsAppChannelGateway
    from jarvis.integrations.whatsapp.media_pipeline import WhatsAppMediaPipeline
    from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage

    seen = []

    class Vision:
        def analyze(self, image, prompt):
            seen.append(prompt)
            return "a receipt for 250 rupees"

    img = Path(tmp_path) / "p.jpg"
    Image.new("RGB", (8, 8)).save(img)

    class Transport:
        async def send_text(self, *a, **k):
            return {"status": "SENT"}

    gw = WhatsAppChannelGateway(command_service=None, transport=Transport(),
                                media_pipeline=WhatsAppMediaPipeline(vision_provider=Vision()),
                                owner_identities={"911111111111@s.whatsapp.net"})
    msg = NormalizedWhatsAppMessage(message_id="m1", chat_id="922222222222@s.whatsapp.net", sender_id="922222222222@s.whatsapp.net",
                                    sender_display_name="Someone", timestamp="1", type="image", text="",
                                    media_ref={"file_path": str(img)})
    try:
        await gw.handle_incoming(msg)
    except Exception:
        pass  # the rest of the flow needs a full stack; only the vision call matters here
    assert seen == []
    Image.new("RGB", (8, 8)).save(img)
    own = msg.model_copy(update={"message_id": "m2", "sender_id": "911111111111@s.whatsapp.net",
                                 "chat_id": "911111111111@s.whatsapp.net", "text": "what is this bill for"})
    try:
        await gw.handle_incoming(own)
    except Exception:
        pass
    assert seen == ["what is this bill for"]  # the owner's own photo is read
