# WhatsApp personal reply agent

JARVIS can answer your WhatsApp messages in **your** way of talking to each person: casual Tanglish with one friend,
professional English with a colleague, and "ok" / "seri" with the friend who only gets one-word replies. It works
only for a time window you grant ("reply to Yoga for the next hour"). It is never on in group chats.

This is an extension of the existing WhatsApp integration, not a second chatbot. It reuses these existing pieces:

- the Baileys bridge and `WhatsAppChannelGateway`;
- the inbox;
- `ActionLedger` and `PolicyEvaluator`;
- the JDE, the router and the tool registry;
- the local LLM client;
- the database and the Qt dashboard.

> **No accuracy promise.** Replies come from a local language model guided by your own past messages. They can be
> wrong. The agent holds anything it is unsure about for your review instead of guessing. Start with *Suggest only* or
> *Ask before send*, and move a contact to automatic replies only after its previews look right to you.

---

## 1. Quick start

1. **Name yourself in exports.** In `config/whatsapp.toml`, under `[whatsapp.personal_reply]`, set
   `export_names = ["<your name as it appears in exported chats>"]`.
2. **Restart the bridge** (`integrations/whatsapp/bridge`, `npm start`) so it uses the new message handling:
   - your own messages in personal chats are forwarded, for learning;
   - "Waiting for this message" placeholders are forwarded, and are never answered;
   - the new `get_message` action is available.
3. **Import a chat.** Open **Dashboard → WhatsApp → Contacts**. Add a contact (number or saved name) and click
   **Import chat**. Pick the `.txt` from WhatsApp's *Export chat → Without media*, or use **From WhatsApp history** to
   learn from messages JARVIS has already seen.
4. **Preview.** Click **Preview style**. Check the draft replies, and use the chips (**Too formal**, **Too casual**,
   **More English**, **More Tanglish**, **Shorter**, **Longer**, **Looks right**) until they sound like you.
5. **Test.** Use **Test reply** with a message of your own. Nothing is sent.
6. **Grant a window.** Say "reply to Yoga automatically for the next hour", or enter minutes next to **Auto for
   (min)** on the contact.

## 2. Reply modes

| Mode | What happens to a new message from that contact |
|---|---|
| `OFF` (default) | Nothing. The existing announcement and draft behaviour is unchanged. |
| `SUGGEST_ONLY` | A draft appears on the Contacts page. It is never sent. |
| `ASK_BEFORE_SEND` | A draft appears with **Send / Good example + send / Discard**, and you get a toast on the PC. |
| `AUTO_REPLY_UNTIL` | Sent automatically until the grant expires, but only if every check below passes. |
| `ALL_DIRECT_CONTACTS_AUTO_UNTIL` | The same for every **personal** chat, for a limited time. |

In `ALL_DIRECT_CONTACTS_AUTO_UNTIL` mode:

- People without a style profile only get suggestions (`auto_reply_untrained_contacts = false`). They get the
  `DefaultUserStyleProfile`, built from all your imported messages.
- You can exclude individual people.

**Grants.**
- Every automatic mode is a stored, time-boxed `AutoReplyGrant`. There is no permanent auto mode.
- The longest window is `max_auto_reply_hours` (12 by default, hard cap 24).
- When a grant expires, it ends at once: the background tick marks it EXPIRED, you get the announcement "Auto
  replies to Yoga have ended", and later messages from that contact are only announced.
- A reply that was being drafted when the window closed is not sent.

## 3. Voice and text commands

| You say | Result |
|---|---|
| "Reply to Yoga automatically for the next hour" | Yoga, 60 minutes |
| "Handle Arun's messages until 6 PM" | Until 18:00; if two contacts match "Arun", asks which one and never guesses |
| "Reply to her for 30 minutes" | "her" is the last contact you talked about; asks if there is none |
| "For the next two hours, respond to everyone" | All personal chats; "everyone" must be said explicitly |
| "Stop replying to her" / "Stop auto reply for Yoga" | That contact back to OFF |
| "Stop WhatsApp auto reply" | **Emergency stop**: ends every grant, and cancels drafts being written |
| "Who is JARVIS replying to?" | Active grants with their end times |
| "Auto reply in the family group for an hour" | Refused: group chats are never auto-replied |

**Time windows.** Accepted forms:
- "for 45 minutes", "for an hour", "for half an hour", "for two hours";
- "until 6 PM", "until 10" (the next 10 o'clock), "till 18:30";
- "for the rest of the day".

**Confirmation.** The spoken result states the end time: "Auto replies to Yoga enabled for 1 hour (until 3:20 PM).
Group chats remain disabled."

**Routing.** The commands go through the existing router (`match_auto_reply` → the `whatsapp_auto_reply` tool). The
tool is REVERSIBLE and is in `AI_CONFIRM_TOOLS` and `AGENT_EXCLUDED_TOOLS`, so the open-ended AI agent can never turn
auto-reply on by itself.

## 4. How a reply is produced

```
Baileys bridge ── message (is_group, state) ──► WhatsAppChannelGateway
   │  placeholder ("Waiting for this message", no text, CIPHERTEXT)  → PENDING_DECRYPTION, never answered, retried later
   │  from you (fromMe, personal chat)                                → learned as a live example of your style
   │  group / broadcast / newsletter                                  → IGNORED_GROUP (before any model call)
   ▼
PersonalReplyAgent.handle_incoming
   1. persistent dedupe: wa_pr_processed.claim(message_id)      → a replayed event is DUPLICATE
   2. AutoReplyPolicy.decide(contact)                           → mode + grant (group block first)
   3. burst coalescing (1.2 s)                                  → "dei" + "tomorrow" + "varuviya?" answered once
   4. understand(): intent, unclear?, asks for a PC action?     → JDE advisory only (channel whatsapp_external)
   5. ContextBuilder: CONTACT, STYLE_PROFILE, RECENT_THREAD, RELEVANT_USER_EXAMPLES (3-8), CURRENT_MESSAGE, REPLY_POLICY
   6. ReplyGenerator: local model, JSON {reply, understood, confidence, intent}; AI phrases stripped
   7. QualityGate: relevance, style, language, consistency, hallucination, sensitive topics
   8. mode: SUGGEST → store; ASK → approval card; AUTO → still inside the grant? owner has not replied meanwhile?
   9. send: PolicyEvaluator (Phase 5 stays authoritative) → ActionLedger PREPARED → STARTED → send → VERIFIED / FAILED / UNCERTAIN
```

**What happens when you reply yourself.**
- If you reply from your phone while JARVIS is drafting, JARVIS drops its draft (OWNER_REPLIED).
- Your reply is learned as an example.
- JARVIS's own sent messages come back from the bridge as `fromMe` echoes. They are recognised by message id or text
  hash and are **not** learned.

### 4.1 Held for your review (`NEEDS_USER_REVIEW`)

Even inside an active grant, a draft is held (not sent) and you get a notification when:

- **The message is unclear.** Examples:
  - emoji or punctuation only;
  - "hmm?", "k?";
  - a lone letter;
  - keyboard mash;
  - the model says it did not understand.
- **The topic is sensitive:**
  - money (UPI, GPay, loans, invoices);
  - OTPs, passwords, ID numbers;
  - sending or forwarding files, photos, documents;
  - addresses and private information;
  - commitments (sign, book, confirm, promise);
  - conflict;
  - legal or official matters;
  - emergencies;
  - instructions aimed at the assistant ("ignore your rules", "jarvis open…").
- **It asks for something on your PC.** "Send me the PDF" can only ever get a conversation reply, and only after you
  approve.
- **The reply does not fit you.**
  - It is much longer than you write to this person.
  - It has too many emojis for someone you never send emojis to.
  - It contains AI phrases ("Certainly!", "I'd be happy to help").
  - It uses the wrong language: Tanglish to someone you only write English to.
- **It adds facts.** Times, amounts or links that are not in the chat or in your own past replies.
- **It copies an unrelated past reply.** The model repeated one of your old replies, word for word, that was written
  for a different situation.
- **The profile is too thin.** Its confidence is below 0.35: only a handful of your messages have been seen.
- **The model is offline.** The reply is held. It is never a canned text.

### 4.2 Sending, duplicates and restarts

- **Dedupe.** Every incoming message id is claimed once in `wa_pr_processed`. `wa_pr_replies.incoming_message_id` is
  UNIQUE, and the `ActionLedger` has a duplicate check. A replayed or re-delivered event, including one replayed
  after a restart, is `DUPLICATE`.
- **UNCERTAIN.** A timeout or unknown bridge error means WhatsApp may or may not have sent it. The reply becomes
  `UNCERTAIN` and is **never resent automatically**; it shows on the Contacts page for you to check.
  - If JARVIS restarts during a send, `recover()` marks the send UNCERTAIN in both the reply table and the ledger.
- **FAILED.** A refused send (bridge disconnected) is `FAILED`. It is not retried silently.
- **Recipient identity.** The recipient is the JID of the chat the message came from, and is re-checked just before
  sending. Commands that name an ambiguous contact ask which one.

## 5. How your style is learned

**Import.**
- The importer reads Android and iOS "Export chat" files, including multi-line messages. It skips system lines,
  "<Media omitted>", "This message was deleted", "Waiting for this message" and "<This message was edited>".
- Group exports (more than two senders) are refused.
- If your name is not in `export_names`, it asks which sender is you.
- **From WhatsApp history** uses the messages JARVIS has already recorded in the inbox.

**Examples.** Each example is *what they said → how you answered*.
- Examples are split by hash into 80% TRAIN, 10% DEV and 10% HOLDOUT.
- HOLDOUT examples are never indexed or used in the profile; they are kept for evaluation.
- Sources are IMPORT, LIVE_USER (you typed it), USER_EDITED (you edited a draft) and APPROVED (you pressed *Good
  example + send*).
- There is **no** source for autonomous AI output, so JARVIS never trains on its own replies unless you approve them.

**`ContactStyleProfile`** (versioned; every rebuild keeps the previous version). It is computed from **your**
messages only:
- English / Tanglish ratio and preferred language;
- formality and directness;
- typical length (average and median words, and the band you stay in);
- emoji frequency and favourites;
- punctuation and capitalisation;
- greetings, closings and acknowledgements;
- humour;
- how often you ask questions;
- common words, and your own Tanglish words with that person;
- your feedback adjustments;
- confidence.

**Per-contact RAG.** Each contact has its own example index.
- Vectors are hashed character and word n-grams (1024 dimensions), so no download is needed.
- Retrieval picks 3–8 examples by similarity. It boosts recent ones and ones you verified or edited, prefers
  examples with the same question/statement intent, and keeps them diverse (MMR).
- Examples from another contact can never enter a prompt: the context builder raises `CrossContactLeak`.
- The two different "Arun"s are separate because identity is the WhatsApp JID, never the display name.

**No fine-tuning.** Nothing is fine-tuned per contact. The profile plus retrieved examples plus the current thread
is enough, and it stays editable and deletable.

### 5.1 English and Tanglish

**Detection.** Detection uses three sources:
- an English wordlist (top 10,000 GloVe words, with Tamil particles removed);
- a small lexicon of romanised Tamil words;
- common Tanglish word endings and the question tag in "free **ah**?".

It labels text `ENGLISH`, `TANGLISH`, `MIXED` or `UNKNOWN`. It is used only to *measure* language. The reply
vocabulary comes only from your own messages to that person, so JARVIS never invents Tanglish you do not use.

**Language for a reply.** It is chosen with these weights:

| Evidence | Weight |
|---|---|
| The current message | 0.5 |
| The recent thread | 0.3 |
| The relationship profile | 0.2 |

So a colleague who suddenly writes Tanglish gets `MIXED`: English is still allowed, and a little Tanglish is allowed
only if you use it with them.

**The language check** allows Tanglish in an English turn only where you really code-switch with that person, such as
Karthik, who gets "haa varan" for "coming?". It never allows it for someone you only write English to.

## 6. Privacy and security

- **Local only.** All data stays on the PC, in the main JARVIS database (`paths.db`, migration
  `008_whatsapp_personal_reply.sql`). Tables:
  - contacts, raw sources, examples with vectors;
  - profiles and profile versions;
  - grants;
  - processed ids, replies, activity.
- **Encryption.** Message text in those tables is encrypted with Fernet. The key is in the OS keyring
  (`jarvis_edge_whatsapp_personal`). The dashboard shows the encryption state.
  - If `cryptography` or a keyring is not available, the page shows "encryption unavailable" and the data is stored
    as plaintext in the local database.
- **Delete profile** removes the profile, its versions, its examples and the raw imported text for that contact.
- **Incoming text is `EXTERNAL_MESSAGE_CONTENT`.**
  - The JDE may classify it with channel `whatsapp_external`, but its output is advisory only.
  - The agent holds no `ToolRegistry`, and an incoming message can never authorize or run a JARVIS tool.
  - Prompt-injection text only ever reaches the reply model as quoted chat content, and such messages are held for
    review.
- **Commands.** Only you can change modes, by voice, the PC chat or the dashboard. Your own `fromMe` messages are
  learned and never treated as commands. Owner-number remote control keeps its existing rules.

## 7. Dashboard: WhatsApp → Contacts

**Header.** It shows:
- a **GROUPS: BLOCKED** badge;
- an **ENCRYPTED / NOT ENCRYPTED** badge;
- **Add contact**;
- **Everyone (min)**;
- **STOP ALL AUTO-REPLY**.

**Contact list.** Each contact shows:
- its name;
- its mode, or "AUTO until 3:20 PM" while a grant is active;
- its profile status, sample count and language style;
- the last message.

**Detail pane.**
- The WhatsApp ID, profile confidence, messages analysed, and the auto-reply state.
- Mode buttons: **Off, Suggest, Ask, Auto for (min)** with a minutes field, and **Stop**.
- **Import chat**, **From WhatsApp history**, **Refresh profile**, **Delete profile**.
- **Preview style** with the feedback chips.
- **Test** (reply not sent), which shows the draft, the language chosen and the quality scores.
- **View history** of drafts and sends with their outcome. Pending drafts have **Send / Good example + send /
  Discard**.

**Live activity.** A feed of events such as "Yoga: Analyzing → Style Tanglish/Very casual → Draft generated → SENT ✓"
or "NOT SENT – needs review: sensitive topic (money)".

**REST API.** Under `http://127.0.0.1:8765/whatsapp/personal`:
- `GET` and `POST /contacts`;
- `GET /contacts/{id}`;
- `POST /contacts/{id}/import`, `rebuild`, `test`, `mode`, `stop`, `feedback`;
- `GET /contacts/{id}/preview` and `/contacts/{id}/history`;
- `DELETE /contacts/{id}/profile`;
- `POST /everyone`, `/stop_all`, `/replies/{id}/approve`, `/replies/{id}/reject`.

**Live events.** They reach the UI as `whatsapp.personal.{activity, suggestion, approval_needed, review_needed,
reply, grant, profile}`.

## 8. Configuration (`config/whatsapp.toml`)

```toml
[whatsapp.personal_reply]
enabled = true
coalesce_seconds = 1.2                  # messages within this window are answered together
max_auto_reply_hours = 12               # longest window one command can grant
auto_reply_untrained_contacts = false   # "everyone" mode: people without a profile only get suggestions
export_names = []                       # your name in exported chats, e.g. ["Yogesh"]
```

## 9. Code map

| File | Role |
|---|---|
| `jarvis/integrations/whatsapp/personal_reply/agent.py` | `PersonalReplyAgent`: pipeline, send, learning, recovery, dashboard operations |
| `…/importer.py` | Android and iOS export parser, owner detection, example pairing and split |
| `…/style_analyzer.py` | `ContactStyleProfile` from your messages; `DefaultUserStyleProfile` |
| `…/language.py` | English / Tanglish / mixed detection (detection only) |
| `…/example_index.py` | Per-contact retrieval (hashing vectors, recency/source boosts, MMR) |
| `…/context_builder.py` | Prompt sections, language choice, cross-contact guard |
| `…/reply_generator.py` | Local model call (JSON), AI-phrase clean-up |
| `…/quality_gate.py` | Relevance, style, language, consistency, hallucination, sensitive topics |
| `…/understand.py` | Intent, unclear-message detection, PC-action request detection, JDE (advisory) |
| `…/auto_reply_policy.py` | Grants, expiry, emergency stop, group block |
| `…/dedupe.py` | Placeholder and group detection |
| `…/store.py`, `…/crypto.py` | SQLite tables, encryption |
| `…/commands.py` | Command parser and `whatsapp_auto_reply` tool |
| `…/api.py` | REST routes for the dashboard |
| `jarvis/ui/whatsapp_contacts.py`, `jarvis/ui/qml/pages/WhatsAppContactsPage.qml` | Contacts page |
| `integrations/whatsapp/bridge/src/*.js` | `is_group`, `state`, fromMe forwarding, placeholder updates, `get_message` |

## 10. Audit of the integration before this change

| Found | Decision |
|---|---|
| **Gateway.** Owner isolation, untrusted-content handling, an AI draft per message, `ALLOWLIST_AUTO_REPLY` with no expiry and no per-contact style | Kept. The personal agent runs first for personal chats. The allow-list path is unchanged when the agent is not enabled for a contact. |
| **Bridge.** Dropped `fromMe` messages and messages without text, and had no group or decryption state | It now forwards `is_group` and `state`, your own personal-chat messages (for learning), placeholders (never answered), and `messages.update` when the real text arrives. |
| **Inbox.** Had `is_direct_chat` and chat history | Reused for the recent thread and for **From WhatsApp history**. |
| **`WhatsAppAI`.** One generic style for everyone | Left alone. The personal agent has its own contact-specific pipeline, which reuses the same LLM client. |
| **`ActionLedger` / `PolicyEvaluator`** | Reused for every automatic send. Phase 5 policy stays authoritative. |
| **Router / tools / capabilities** | One new intent (`whatsapp_auto_reply`) and one capability (`whatsapp.auto_reply`). There is no new router, planner or memory system. |

## 11. Tests and benchmark

**Tests.**
- The unit and integration tests are in `jarvis/tests/test_whatsapp_personal_reply.py` (54 tests). They cover:
  - import, the profile, Tanglish, context and retrieval;
  - timers and expiry, the emergency stop, the group block;
  - duplicates, restarts, pending decryption;
  - style isolation, the two Aruns, sensitive gating, PC-action refusal;
  - UNCERTAIN sends, coalescing, owner-typed replies, encryption;
  - commands, router and gateway integration.
- The existing WhatsApp tests still pass.

**Benchmark.** `python -m tests.whatsapp_personal.benchmark` runs 500 cases on a fake WhatsApp provider with synthetic
contacts; nothing is sent. It writes:
- `reports/WHATSAPP_PERSONAL_REPLY_BENCHMARK.{md,json}`;
- `reports/whatsapp_personal_review_sample.md`, with 20 drafts per contact for you to mark GOOD / TOO FORMAL / TOO
  CASUAL / WRONG LANGUAGE / WRONG MEANING.

Add `--live` to generate the style cases with your real local model.

**Generator.** The default generator is a deterministic stand-in: it re-uses the most relevant retrieved example of
yours. So these numbers measure the pipeline (profile, language choice, retrieval, isolation, gating, sending safety),
**not** the quality of the language model.

Latest run (stand-in generator):

| | Result |
|---|---|
| Cases | 500 / 500 passed, 24 categories |
| WRONG_CONTACT_SEND, GROUP_AUTO_REPLY, EXPIRED_AUTO_REPLY, DUPLICATE_SEND, PLACEHOLDER_REPLY, CROSS_CONTACT_DATA_LEAK, BLIND_UNCERTAIN_RESEND | 0 each |
| Language-mode / length / emoji fit of generated replies | 100% / 100% / 100% (122 replies) |
| Holdout: situations never imported | Language mode, length and emoji 100% for all four contacts. Semantic similarity to your real reply is low (0.12–0.50), and 0–100% per contact are held for review (Karthik 0%, Arun 100%). The stand-in can only copy an old reply, and the copy guard catches the copies that don't fit. |
| HOLDOUT-split examples retrieved into any prompt | 0 |

The 24 categories are: English, Tanglish, mixed, contact-specific, unseen messages, follow-ups, context changes,
short replies, long questions, bursts, ambiguity, missing profile, low-confidence profile, timer expiry, manual stop,
everyone mode, groups, duplicates, pending decryption, reconnect, UNCERTAIN sends, sensitive topics, cross-contact
isolation, prompt injection.

## 12. Manual acceptance before you rely on it

1. **Import.** Import 3 real chats with different styles (one Tanglish, one professional, one very short). Check each
   profile summary.
2. **Preview.** Run **Preview style** for each: at least 20 drafts per contact. Mark every one, and use the feedback
   chips until the large majority are *Looks right*.
3. **Ask first.** Put one contact on **Ask** (ask before send) for a day. Send, edit or discard every draft; your edits are
   learned.
4. **Short grant.** Grant that one contact **Auto for (min)** with 15 minutes. Watch the activity feed while they message you. Then check
   each of these:
   - the grant ends on time;
   - "Stop WhatsApp auto reply" stops everything at once;
   - a message in a shared group gets no reply;
   - a "Waiting for this message" gets no reply;
   - a money or file question is held;
   - replying from your phone cancels JARVIS's draft.
5. **Widen gradually.** Only then use longer windows or "everyone". Keep `auto_reply_untrained_contacts = false`.

## 13. Known limits

- **Model quality.** Reply quality depends on the local model. Small models can misunderstand long or indirect
  messages; the gate catches many such cases, not all.
- **Tanglish coverage.** Detection is heuristic. Rare romanised spellings may count as "unknown", which is safe: it
  never *adds* Tanglish you did not use.
- **Media.** Voice notes are answered only from their transcript, when the WhatsApp media pipeline produced one.
  Images, stickers, documents and other media are not auto-answered.
- **Retrying undecrypted messages.** The bridge can re-fetch an undecrypted message only while it still holds it in
  memory. After a bridge restart, such a message stays pending until WhatsApp re-delivers it.
