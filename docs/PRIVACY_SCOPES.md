# Privacy Scopes & Multi-Contact Data Isolation

## 1. Scope Taxonomies
Every item indexed or stored in the unified knowledge base possesses explicit scope metadata:
- `owner_scope`: The owning user/device (e.g. `scope:user`, `scope:device`).
- `conversation_scope`: The conversation boundary (e.g. `scope:whatsapp:chat:<chat_id>`, `scope:desktop`, `scope:android`).
- `privacy_scope`: The resource category (e.g. `scope:documents`, `scope:projects`, `scope:whatsapp`).
- `trust_level`: `DATA_ONLY` or `UNTRUSTED_EXTERNAL_CONTENT`.

---

## 2. Pre-Ranking Scope Filtering Invariant
To prevent any data leakage across contacts:
```python
scope_filter.is_accessible(item_scopes)
```
- Filtering is applied **BEFORE** candidate ranking.
- Contact A's private notes and messages in `scope:whatsapp:chat:contactA@s.whatsapp.net` will **never** be retrieved, scored, or leaked into responses for Contact B.

---

## 3. Secret & Credential Redaction
- Session credentials and linked-device auth keys are stored outside git in `data/whatsapp_auth/` (enforced by `.gitignore`).
- Passwords, OTPs, API keys, and session tokens are permanently excluded from durable conversational memory.
- Diagnostic output and Desktop UI strictly redact tokens and numbers.
