-- Migration 007: everyday assistant data and decision-engine (JDE) shadow log

CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL, done_at REAL
);
CREATE TABLE IF NOT EXISTS memory_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, fact TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS shortcuts (
    phrase TEXT PRIMARY KEY, steps TEXT NOT NULL, created_at REAL NOT NULL
);
-- One row per request: the router's decision next to JDE's (shadow mode). Never used for automatic training.
CREATE TABLE IF NOT EXISTS jde_decisions (
    id INTEGER PRIMARY KEY, request_id TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jde_decisions_request ON jde_decisions(request_id);
