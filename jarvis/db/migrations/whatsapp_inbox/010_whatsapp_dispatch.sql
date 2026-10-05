CREATE TABLE IF NOT EXISTS wa_dispatch_jobs(message_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL,
    payload TEXT NOT NULL, created_at REAL NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', error TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS wa_dispatch_pending ON wa_dispatch_jobs(status,created_at);
