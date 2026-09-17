CREATE TABLE IF NOT EXISTS route_cache (
    normalized_pattern TEXT PRIMARY KEY,
    intent TEXT NOT NULL,
    slot_template_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    success_count INTEGER NOT NULL DEFAULT 1,
    failure_count INTEGER NOT NULL DEFAULT 0,
    last_used REAL NOT NULL,
    registry_version TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS route_decisions (
    request_id TEXT PRIMARY KEY,
    normalized_text_hash TEXT NOT NULL,
    lane TEXT NOT NULL,
    intent TEXT,
    confidence REAL NOT NULL,
    source TEXT NOT NULL,
    complexity TEXT NOT NULL,
    routing_ms REAL NOT NULL,
    model_ms REAL NOT NULL DEFAULT 0.0,
    cache_hit INTEGER NOT NULL DEFAULT 0,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_route_decisions_created ON route_decisions(created_at);
CREATE INDEX IF NOT EXISTS idx_route_cache_success ON route_cache(success_count);
