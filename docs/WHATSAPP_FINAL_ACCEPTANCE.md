    # WhatsApp final acceptance tracker

    Updated 2026-10-04. `PASS` requires the stated evidence, and a local test does not stand in for a live WhatsApp action. The fresh bridge and Python listener remain read only apart from the single exact-match outgoing test recorded below. General sending and auto-reply remain disabled.

    The verified-style learning pass added draft-only personalization, safe manual-send attribution and optional legacy review. Three contacts are configured `SUGGEST_ONLY`; generated auto-reply is explicitly off. At the latest process check, the bridge/listener were no longer running, so live incoming draft generation requires a read-only restart. No new WhatsApp message was sent for this pass. [Style evidence and limits](../reports/WHATSAPP_VERIFIED_STYLE_FLYWHEEL.md) are recorded separately.

    On 2026-10-05 the normal fresh bridge and Python backend were restarted in read-only mode; the bridge returned `READY` and the local personal contacts endpoint reported three `SUGGEST_ONLY` contacts and zero auto-reply contacts. The prior one-shot outgoing delivery remains pending phone confirmation. One owner-reviewed historical batch and one supplemental row are now verified legacy style evidence, with one diagnostic verified holdout case. See [shadow-mode status](../reports/WHATSAPP_SHADOW_MODE.md). No fresh direct incoming message has yet exercised live shadow draft creation in this generation.

    The owner subsequently approved the other two prepared contact batches. The style store now has 106 verified legacy rows and 10 verified holdout pairs across three contacts; all remain `SUGGEST_ONLY` and `VERIFIED_STYLE_BUILDING`. Offline replay is diagnostic only, with owner ratings pending. Live shadow draft receipt, any new outgoing send, and generated auto-reply remain unaccepted.

    | Area | Status | Evidence or remaining proof |
    |---|---|---|
    | Fresh auth promoted | PASS | TOML, Node default and launcher select the fresh companion; startup guard rejects old auth on the port. |
    | Normal startup | PARTIAL | Static config and verifier tests pass; normal launcher and reboot have not been exercised end to end. |
    | Auth / transport | PASS | Current registered fresh companion connects on 8768 and completes pending notifications. |
    | Live incoming / raw→upsert latency | PASS | Three earlier phone-confirmed exact IDs: 10, 3 and 4 ms; restart marker: 16 ms, all downstream boundaries observed. |
    | Python ingest / SQLite exact-once | PASS | Three exact IDs reached schema/dispatch and have one row each; integrity check passed. |
    | History state | PARTIAL | Current chat/badge snapshot is available; full historical message coverage is unproven. Local history remains readable. |
    | Direct / group / union reads | PARTIAL | Typed scopes and SQL filters have local tests; owner command and live group-read acceptance remain. |
    | Search / summarization | PARTIAL | Real local history and scoped FTS have been exercised; full-history recall and live command acceptance remain. |
    | Contact resolution / context | PARTIAL | A unique test contact resolves and local typed context tests exist; live ambiguous-contact and cross-turn acceptance remain. |
    | Attachments / forwarding | PARTIAL | Bounded, thread-scoped download and local media paths exist; live receive/send/forward proof remains. |
    | Voice | PARTIAL | Faster-Whisper and PyAV import locally; a real voice note, decode and transcription acceptance remain. |
    | Outgoing text / reply | PARTIAL | One exact outgoing test was accepted by Baileys and persisted locally once; receiving-phone confirmation and a reply-to-message test remain pending. |
| Style profile / draft | PARTIAL | Conservative legacy recovery yielded 76 lower-confidence reply pairs and 3 draft-ready contacts, with zero verified owner examples. Five legacy holdout drafts were replayed; real reviewed draft quality remains unmeasured. See [brain audit](../reports/WHATSAPP_PERSONAL_BRAIN.md) and [provenance audit](../reports/WHATSAPP_LEGACY_PROVENANCE_AUDIT.md). |
| Auto-reply / expiry | PARTIAL | Direct-only grant and expiry have local tests; production generated auto-replies now require a reviewed offline evaluation. No real grant/send acceptance. Default remains off. |
    | Group auto-reply block | PASS | Structural direct-JID gate and local tests; channels are excluded too. |
    | Sensitive message gate | PARTIAL | Local policy exists; live review/deny acceptance remains. |
    | Owner remote control / prompt-injection isolation | PARTIAL | Stable-identity and data-boundary code/tests exist; live owner and non-owner probes remain. |
    | ActionLedger / uncertain-send recovery | PARTIAL | Local tests exercise records and no blind resend; real timeout reconciliation remains. |
    | Idempotency | PARTIAL | Incoming exact-once passed live; outgoing exactly-once remains unverified. |
    | Restart persistence | PARTIAL | Read-only Node/Python restart retained the fresh auth and SQLite; the fresh marker passed in the restarted generation. Reboot remains untested. |
    | Node tests | PASS | 24/24 after the exact one-use outgoing guard was added. |
    | Python tests | PASS | 420 passed, 3 skipped in the WhatsApp/router/policy selection; 48/48 focused scope/unread/acceptance checks. The rest of the repository suite was not part of this run. |
    | Full live acceptance | PARTIAL | Incoming text passes. Outgoing, media, voice, policy and restart steps remain. |

    ## External actions needed

    1. Confirm whether the dedicated test phone received the one outgoing marker below. Do not resend an uncertain message.
    2. For subsequent stages, arrange consenting test messages and media from another account, and approve any actual reply or temporary auto-reply grant before it is enabled.
    3. Confirm owner remote-command and reboot behavior with a controlled phone/account test after local checks pass.

    The old auth is preserved as degraded evidence and is not selected by normal startup. Do not merge its Signal files into the fresh auth directory or unlink the old phone companion as part of this acceptance tracker.

    At 06:02 UTC on 2026-10-04, the current read-only bridge PID 27344 was registered and `READY` against the fresh auth. The Python listener remained connected. On offline completion, the bridge republished full runtime status and chat state; Python now records `received_pending_notifications=true` for the current generation. It reports `PARTIAL_SYNC` because a new complete chat snapshot was not received, while `local_history_available=true`. `event_stream_verified=false` for this new generation until the requested fresh phone-confirmed message is traced; the earlier three-message verification remains valid evidence for the prior generation. No chat was sent by JARVIS during restart.

    At 06:05 UTC the Python read-only listener was also restarted from the existing script with the workspace on `PYTHONPATH` (PID 20792). It printed `TRACED_READ_ONLY_LISTENER_RUNNING`, connected to the fresh bridge, and stored history remained available. The first attempt lacked `PYTHONPATH` and exited before opening the listener; it caused no WhatsApp action. `JARVIS RESTART CHECK 1004` had zero SQLite matches at this check and had not yet been confirmed on the phone. Reboot and new-generation live delivery are still pending.

    At 07:26 UTC the current read-only Node/Python pair was restarted with metadata-only exact-ID traces enabled (Node PID 23172, Python PID 28560). The fresh auth passed the registered/connected/pending-notification startup guard in generation `db63be34-600b-444b-9fae-8ff2788bd5e5`. `JARVIS RESTART CHECK 1004` still had zero SQLite rows, and no owner phone confirmation had arrived. The trace files are ignored local data and contain IDs, JIDs, timestamps and boundary results, without message bodies. Later reconnects receive new generation IDs; earlier generation-specific stream verification is not reused.

    At 07:40 UTC, after an internal reconnect to generation `8370865b-6b4a-4ae0-af83-ce31229b839e`, the restart marker reached the dad-chat thread as exact ID `AC7ECAAD4C884744B70C0CF61070F712`. Raw → upsert was 16 ms; every subsequent boundary passed and SQLite has one row for that ID. The owner reported the phone-displayed time as 1:10, aligning with 1:10 PM IST from the trace; exact-ID live acceptance was recorded in the active generation. Outgoing remains disabled pending an exact one-message authorization.

    At 07:53 UTC the read-only bridge was restarted with a one-use exception for the exact dad-chat recipient, text `JARVIS outgoing acceptance 1004`, and request ID `373c72e1-af54-4fab-b217-5170c07b7127`. The Python listener remained read only. Generation `6a3c9cdf-0d10-41d1-b0cf-761d393c4356` connected and completed pending notifications. The single send returned Baileys status `SENT` with ID `3EB00DE5A23955CBB82465`; the bridge's last outgoing command matches the request and ID. ActionLedger records the external acknowledgement and local persistence evidence, with status `EXTERNALLY_ACKNOWLEDGED` pending the receiving phone. SQLite contains exactly one outgoing row for that ID, the exact text and same dad-chat thread, with `PRAGMA integrity_check=ok`. The receiving phone has not yet confirmed delivery, so **outgoing delivery remains pending**. The one-use gate was consumed before the send and must not be retried automatically.
