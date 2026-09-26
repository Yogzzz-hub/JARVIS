-- Migration 008: WhatsApp personal reply agent (contact style profiles, examples, auto-reply grants,
-- processed ids for duplicate / placeholder protection, reply log, activity feed).
CREATE TABLE IF NOT EXISTS wa_pr_contacts (
    contact_id TEXT PRIMARY KEY, display_name TEXT NOT NULL DEFAULT '', mode TEXT NOT NULL DEFAULT 'OFF',
    updated_at REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS wa_pr_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id TEXT NOT NULL, import_id TEXT NOT NULL, ts REAL NOT NULL,
    direction TEXT NOT NULL, text_enc TEXT NOT NULL, message_id TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wa_pr_sources_contact ON wa_pr_sources(contact_id, ts);
CREATE TABLE IF NOT EXISTS wa_pr_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id TEXT NOT NULL, context_enc TEXT NOT NULL, reply_enc TEXT NOT NULL,
    ts REAL NOT NULL, source TEXT NOT NULL, split TEXT NOT NULL DEFAULT 'TRAIN', vector BLOB, created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wa_pr_examples_contact ON wa_pr_examples(contact_id, split);
CREATE TABLE IF NOT EXISTS wa_pr_profiles (
    contact_id TEXT PRIMARY KEY, display_name TEXT NOT NULL DEFAULT '', profile_enc TEXT NOT NULL,
    profile_version INTEGER NOT NULL, updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS wa_pr_profile_versions (
    contact_id TEXT NOT NULL, profile_version INTEGER NOT NULL, profile_enc TEXT NOT NULL, created_at REAL NOT NULL,
    PRIMARY KEY (contact_id, profile_version)
);
CREATE TABLE IF NOT EXISTS wa_pr_grants (
    grant_id TEXT PRIMARY KEY, scope TEXT NOT NULL, contact_ids TEXT NOT NULL, mode TEXT NOT NULL,
    enabled_at REAL NOT NULL, expires_at REAL NOT NULL, granted_by_user INTEGER NOT NULL DEFAULT 1,
    revoked_at REAL, include_untrained INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS wa_pr_processed (
    message_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS wa_pr_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT, incoming_message_id TEXT NOT NULL UNIQUE, message_ids TEXT NOT NULL,
    contact_id TEXT NOT NULL, chat_id TEXT NOT NULL, grant_id TEXT, mode TEXT NOT NULL, status TEXT NOT NULL,
    draft_hash TEXT, final_hash TEXT, text_enc TEXT, incoming_enc TEXT, reason TEXT, quality_json TEXT,
    ledger_action_id TEXT, sent_message_id TEXT, send_started REAL, send_verified REAL,
    created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wa_pr_replies_contact ON wa_pr_replies(contact_id, created_at);
CREATE INDEX IF NOT EXISTS idx_wa_pr_replies_status ON wa_pr_replies(status);
CREATE TABLE IF NOT EXISTS wa_pr_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, contact_id TEXT NOT NULL, display_name TEXT NOT NULL,
    stage TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''
);
