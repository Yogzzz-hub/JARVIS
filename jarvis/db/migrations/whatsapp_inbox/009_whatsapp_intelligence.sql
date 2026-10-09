-- Applied to the existing WhatsAppInbox database by IntelligenceStore; raw inbox rows are preserved.
CREATE TABLE IF NOT EXISTS wa_intelligence_versions(version INTEGER PRIMARY KEY, applied_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS wa_events(message_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, timestamp REAL NOT NULL,
    payload TEXT NOT NULL, authorship TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1);
CREATE INDEX IF NOT EXISTS wa_events_thread ON wa_events(thread_id, timestamp);
CREATE VIRTUAL TABLE IF NOT EXISTS wa_events_fts USING fts5(message_id UNINDEXED, thread_id UNINDEXED, text);
CREATE TABLE IF NOT EXISTS wa_thread_state(thread_id TEXT PRIMARY KEY, version INTEGER NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS wa_resources(id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, kind TEXT NOT NULL,
    message_id TEXT NOT NULL DEFAULT '', payload TEXT NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS wa_resources_thread ON wa_resources(thread_id, kind);
CREATE TABLE IF NOT EXISTS wa_generated_messages(message_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL,
    content_hash TEXT NOT NULL, request_id TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS wa_intelligence_jobs(message_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS wa_vectors(message_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, model TEXT NOT NULL,
    vector TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wa_lexicon(surface TEXT PRIMARY KEY, meaning TEXT NOT NULL,
    observations INTEGER NOT NULL DEFAULT 0, confirmed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS wa_watcher_matches(watcher_id TEXT PRIMARY KEY, message_id TEXT NOT NULL,
    notified INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS wa_intelligence_metrics(name TEXT PRIMARY KEY, value REAL NOT NULL DEFAULT 0);
