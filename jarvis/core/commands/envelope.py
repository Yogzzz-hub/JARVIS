"""Transport-neutral input captured before any production text rewriting."""
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class JarvisInputEnvelope(BaseModel):
    input_id: str
    source: str
    raw_text: str
    audio_metadata: dict = Field(default_factory=dict)
    authenticated_actor: str
    timestamp: str
    conversation_id: str
    language_hint: str | None = None
    device: str = 'pc'
    context_refs: list = Field(default_factory=list)
    reply_channel: str = 'local'

    @classmethod
    def from_request(cls, request):
        metadata = request.metadata or {}
        source = metadata.get('input_source', request.source)
        source = source if source in {'http', 'cli', 'websocket', 'voice', 'whatsapp',
            'dashboard', 'desktop_overlay', 'phone', 'automation_builder', 'test', 'benchmark'} else request.source
        remote = source in {'whatsapp', 'phone'}
        return cls(input_id=request.request_id, source=source, raw_text=request.text,
            audio_metadata=dict(metadata.get('audio_metadata') or {}),
            authenticated_actor='owner' if request.is_owner else 'untrusted_contact',
            timestamp=datetime.now(timezone.utc).isoformat(),
            conversation_id=request.chat_id or str(metadata.get('conversation_id') or ('phone' if source == 'phone' else 'local')),
            language_hint=metadata.get('language_hint'), device='phone' if source == 'phone' else 'pc',
            context_refs=list(metadata.get('context_refs') or []),
            reply_channel=source if remote else 'text_only' if metadata.get('response_channel') == 'text_only' else 'local')
