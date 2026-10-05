# WhatsApp security boundaries

- Incoming text, quoted messages, attachments, voice transcripts and retrieved pages are untrusted data. They cannot authorize PC tools or policy changes.
- Only stable configured owner identities can enter CommandService. Display names and quoted or forwarded owner text confer no authority.
- Direct-chat auto-reply requires a current explicit grant; groups are excluded. Sensitive content routes to review.
- Consequential sends use existing policy, ledger and verification paths. A timeout or lost receipt is `UNCERTAIN`, never a reason to resend automatically.
- Read-only mode now blocks every send in Python and Node. The former exact-message test exception was removed after the one authorized test was used.
- Auth/history are preserved. The Node bridge no longer supplies a baked-in pairing phone number if auth becomes unregistered.

The code and synthetic adversarial tests support these boundaries. Real external owner-command and auto-reply acceptance remains open.
