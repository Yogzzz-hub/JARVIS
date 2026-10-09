# Auto-reply policy

Auto-reply is off by default. The existing personal reply agent requires an explicit bounded grant, a direct chat, a valid contact/style policy, reply necessity, a nonsensitive candidate, quality and grounding checks, and a final grant recheck before sending. Group conversations are structurally excluded. Expired and paused grants cannot be reused to extend authorization.

The old gateway fallback that generated generic “Got your message” drafts after the grant-aware agent declined a message has been removed. A declined message is now announced and returned as `NO_REPLY_AUTHORIZATION`; it does not enter a second AI reply lane. Explicit user draft requests still use the registered draft capability.

The active diagnostic listener forces `JARVIS_WHATSAPP_READ_ONLY=1`, so the personal reply agent is not started and no auto-reply can be sent. Local expiry, group and policy tests pass; a real explicitly granted direct-chat auto-reply has not been performed in this request.
