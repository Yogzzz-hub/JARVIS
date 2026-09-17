-- Migration 005: Security, Action Ledger, Method Statistics, and Audit Log

CREATE TABLE IF NOT EXISTS action_ledger (
    action_id TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    request_id TEXT NOT NULL,
    graph_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    risk TEXT NOT NULL,
    idempotency TEXT NOT NULL,
    status TEXT NOT NULL,
    args_hash TEXT NOT NULL,
    confirmation_ticket TEXT,
    method TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    verified_at TIMESTAMP,
    finished_at TIMESTAMP,
    error_class TEXT,
    verification_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_action_ledger_fingerprint ON action_ledger(fingerprint);
CREATE INDEX IF NOT EXISTS idx_action_ledger_status ON action_ledger(status);
CREATE INDEX IF NOT EXISTS idx_action_ledger_graph ON action_ledger(graph_id);

CREATE TABLE IF NOT EXISTS method_stats (
    capability TEXT NOT NULL,
    method TEXT NOT NULL,
    context_key TEXT NOT NULL DEFAULT 'default',
    attempts INTEGER DEFAULT 0,
    successes INTEGER DEFAULT 0,
    verified_successes INTEGER DEFAULT 0,
    failures INTEGER DEFAULT 0,
    uncertain INTEGER DEFAULT 0,
    mean_latency_ms REAL DEFAULT 0.0,
    ewma_latency_ms REAL DEFAULT 0.0,
    last_success TIMESTAMP,
    last_failure TIMESTAMP,
    PRIMARY KEY (capability, method, context_key)
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    graph_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tool TEXT NOT NULL,
    method TEXT NOT NULL,
    risk TEXT NOT NULL,
    decision TEXT NOT NULL,
    confirmation_ticket_id TEXT,
    action_fingerprint TEXT NOT NULL,
    result_status TEXT NOT NULL,
    verification_summary TEXT,
    duration_ms REAL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_tool ON audit_log(tool);
