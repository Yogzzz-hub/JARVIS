-- 004_planner_dag.sql
-- Phase 4: Adaptive Complex Planner + Verified DAG Scheduler

CREATE TABLE IF NOT EXISTS task_graphs (
    graph_id TEXT PRIMARY KEY,
    request_id TEXT,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,
    planner_model TEXT,
    schema_version TEXT NOT NULL,
    registry_version TEXT NOT NULL,
    node_count INTEGER NOT NULL,
    depth INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    planning_ms REAL,
    execution_ms REAL
);

CREATE TABLE IF NOT EXISTS graph_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    graph_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    state TEXT NOT NULL,
    duration_ms REAL,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    FOREIGN KEY (graph_id) REFERENCES task_graphs(graph_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS graph_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    graph_id TEXT NOT NULL,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    edge_type TEXT DEFAULT 'dependency',
    FOREIGN KEY (graph_id) REFERENCES task_graphs(graph_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS planner_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model TEXT NOT NULL,
    cold BOOLEAN DEFAULT 0,
    prompt_tokens INTEGER,
    output_tokens INTEGER,
    load_ms REAL,
    prompt_eval_ms REAL,
    generation_ms REAL,
    total_ms REAL,
    valid_first_try BOOLEAN DEFAULT 1,
    repair_used BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plan_cache (
    template_id TEXT PRIMARY KEY,
    task_signature TEXT NOT NULL UNIQUE,
    tool_registry_fingerprint TEXT NOT NULL,
    graph_template_json TEXT NOT NULL,
    hit_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS capability_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capability TEXT NOT NULL,
    reason TEXT NOT NULL,
    related_tools TEXT,
    user_request TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_task_graphs_status ON task_graphs(status);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_graph_id ON graph_nodes(graph_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_graph_id ON graph_edges(graph_id);
CREATE INDEX IF NOT EXISTS idx_plan_cache_signature ON plan_cache(task_signature);
