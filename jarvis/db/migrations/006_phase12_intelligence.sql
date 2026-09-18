-- Migration 006: Phase 12 Layered Memory, Episodes, Workflows, RAG Collections & Optimization

CREATE TABLE IF NOT EXISTS memory_items (
    memory_id TEXT PRIMARY KEY,
    layer TEXT NOT NULL,
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_reference TEXT,
    confidence TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    last_verified TIMESTAMP,
    use_count INTEGER DEFAULT 0,
    successful_use_count INTEGER DEFAULT 0,
    correction_count INTEGER DEFAULT 0,
    expires_at TIMESTAMP,
    supersedes_id TEXT,
    status TEXT DEFAULT 'ACTIVE'
);

CREATE INDEX IF NOT EXISTS idx_memory_items_layer ON memory_items(layer);
CREATE INDEX IF NOT EXISTS idx_memory_items_kind ON memory_items(kind);
CREATE INDEX IF NOT EXISTS idx_memory_items_key ON memory_items(key);
CREATE INDEX IF NOT EXISTS idx_memory_items_status ON memory_items(status);
CREATE INDEX IF NOT EXISTS idx_memory_items_expires ON memory_items(expires_at);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_items_fts USING fts5(
    memory_id UNINDEXED,
    key,
    value_text,
    kind,
    source_type
);

CREATE TABLE IF NOT EXISTS episodes (
    episode_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    request_id TEXT NOT NULL,
    normalized_goal TEXT NOT NULL,
    tools_used_json TEXT NOT NULL,
    resources_json TEXT NOT NULL,
    outcome TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 1,
    duration_ms REAL DEFAULT 0.0,
    user_correction TEXT,
    tags_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_episodes_timestamp ON episodes(timestamp);
CREATE INDEX IF NOT EXISTS idx_episodes_outcome ON episodes(outcome);
CREATE INDEX IF NOT EXISTS idx_episodes_request ON episodes(request_id);

CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
    episode_id UNINDEXED,
    normalized_goal,
    user_correction,
    tags
);

CREATE TABLE IF NOT EXISTS workflow_templates (
    workflow_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    input_schema_json TEXT NOT NULL,
    graph_template_json TEXT NOT NULL,
    required_tools_json TEXT NOT NULL,
    required_capabilities_json TEXT NOT NULL,
    risk_profile TEXT NOT NULL,
    registry_fingerprint TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    version INTEGER DEFAULT 1,
    status TEXT DEFAULT 'APPROVED',
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    avg_latency_ms REAL DEFAULT 0.0,
    last_success TIMESTAMP,
    last_failure TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workflow_name ON workflow_templates(name);
CREATE INDEX IF NOT EXISTS idx_workflow_status ON workflow_templates(status);

CREATE TABLE IF NOT EXISTS workflow_candidates (
    candidate_id TEXT PRIMARY KEY,
    name_suggestion TEXT NOT NULL,
    normalized_goal TEXT NOT NULL,
    graph_shape_hash TEXT NOT NULL,
    variable_slots_json TEXT NOT NULL,
    preconditions_json TEXT NOT NULL,
    risk_summary TEXT NOT NULL,
    occurrence_count INTEGER DEFAULT 1,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    evidence_episodes_json TEXT NOT NULL,
    status TEXT DEFAULT 'PROPOSED'
);

CREATE INDEX IF NOT EXISTS idx_workflow_candidates_hash ON workflow_candidates(graph_shape_hash);
CREATE INDEX IF NOT EXISTS idx_workflow_candidates_status ON workflow_candidates(status);

CREATE TABLE IF NOT EXISTS rag_collections (
    collection_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    source_roots_json TEXT NOT NULL,
    file_filters_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_policy TEXT DEFAULT 'PUBLIC'
);

CREATE TABLE IF NOT EXISTS rag_chunks (
    chunk_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    section_title TEXT,
    line_start INTEGER,
    line_end INTEGER,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_collection ON rag_chunks(collection_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_path ON rag_chunks(file_path);

CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
    chunk_id UNINDEXED,
    collection_id UNINDEXED,
    section_title,
    content
);

CREATE TABLE IF NOT EXISTS optimization_proposals (
    proposal_id TEXT PRIMARY KEY,
    parameter TEXT NOT NULL,
    current_value TEXT NOT NULL,
    proposed_value TEXT NOT NULL,
    evidence TEXT NOT NULL,
    benchmark_delta_json TEXT,
    status TEXT DEFAULT 'PROPOSED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_opt_proposals_status ON optimization_proposals(status);
