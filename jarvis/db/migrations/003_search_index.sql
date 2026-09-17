-- Phase 3: Ultra-Fast File + Knowledge Intelligence

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    path_norm TEXT NOT NULL,
    parent_path TEXT,
    name TEXT NOT NULL,
    name_norm TEXT NOT NULL,
    stem TEXT,
    extension TEXT,
    size_bytes INTEGER,
    created_ns INTEGER,
    modified_ns INTEGER,
    indexed_ns INTEGER,
    last_seen_ns INTEGER,
    is_directory INTEGER DEFAULT 0,
    is_hidden INTEGER DEFAULT 0,
    is_available INTEGER DEFAULT 1,
    content_status TEXT DEFAULT 'PENDING',
    content_hash TEXT NULL,
    open_count INTEGER DEFAULT 0,
    last_opened_ns INTEGER NULL,
    last_accessed_by_jarvis_ns INTEGER NULL,
    source_root_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_files_path_norm ON files(path_norm);
CREATE INDEX IF NOT EXISTS idx_files_name_norm ON files(name_norm);
CREATE INDEX IF NOT EXISTS idx_files_stem ON files(stem);
CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension);
CREATE INDEX IF NOT EXISTS idx_files_modified ON files(modified_ns);
CREATE INDEX IF NOT EXISTS idx_files_last_opened ON files(last_opened_ns);
CREATE INDEX IF NOT EXISTS idx_files_source_root ON files(source_root_id);
CREATE INDEX IF NOT EXISTS idx_files_available ON files(is_available);

CREATE TABLE IF NOT EXISTS file_content (
    file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    content_excerpt TEXT,
    content_text TEXT,
    content_version INTEGER DEFAULT 1,
    extractor TEXT,
    extract_status TEXT DEFAULT 'PENDING',
    extract_error TEXT,
    extracted_ns INTEGER
);

CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
    file_id UNINDEXED,
    name,
    stem,
    path_tokens,
    content,
    tokenize="unicode61 separators '_-. '",
    prefix='2 3 4'
);
