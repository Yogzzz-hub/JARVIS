"""JARVIS EDGE WhatsApp Omnichannel Integration.
Provides transport boundary adapter, owner authorization, privacy scoping, and media ingestion.
"""

from jarvis.integrations.whatsapp.contact_resolver import ContactResolver
from jarvis.integrations.whatsapp.fake_transport import FakeWhatsAppTransport
from jarvis.integrations.whatsapp.gateway import WhatsAppChannelGateway
from jarvis.integrations.whatsapp.media_pipeline import WhatsAppMediaPipeline
from jarvis.integrations.whatsapp.models import (
    NormalizedWhatsAppMessage,
    OutboundMessageDraft,
    WhatsAppBridgeStatus,
)
from jarvis.integrations.whatsapp.service import (
    BaileysWebSocketTransport,
    WhatsAppIntegrationService,
)

__all__ = [
    "WhatsAppChannelGateway",
    "NormalizedWhatsAppMessage",
    "WhatsAppBridgeStatus",
    "OutboundMessageDraft",
    "ContactResolver",
    "WhatsAppMediaPipeline",
    "FakeWhatsAppTransport",
    "BaileysWebSocketTransport",
    "WhatsAppIntegrationService",
]
