import asyncio
import os
from pathlib import Path
import sqlite3
import time
from typing import Any
from jarvis.config import ROOT, SearchConfig
from jarvis.memory.search.extractor import compute_file_hash, extract_file_content
from jarvis.memory.search.tokenizer import path_tokens_string, tokenize_filename
from jarvis.memory.search.vector.base import VectorStore
from jarvis.memory.search.vector.embeddings import EmbeddingProvider

class FileIndexer:
    """Manages two-stage file indexing: Stage A (metadata) and Stage B (background enrichment)."""
    def __init__(
        self,
        db_path: Path | str,
        config: SearchConfig | None = None,
        vector_store: VectorStore | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        self.db_path = str(db_path)
        self.config = config or SearchConfig()
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.is_enriching = False
        self.total_indexed = 0
        self.total_enriched = 0

    def _get_connection(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def _resolve_roots(self) -> list[Path]:
        resolved = []
        for r in self.config.roots:
            expanded = os.path.expandvars(r)
            p = Path(expanded)
            if p.exists() and p.is_dir():
                resolved.append(p)
        return resolved

    def _is_excluded(self, path: Path) -> bool:
        path_str = str(path).lower()
        parts = {part.lower() for part in path.parts}
        for pattern in self.config.exclude_patterns:
            pattern_low = pattern.lower()
            if pattern_low in parts or pattern_low in path_str:
                return True
        return False

    def index_metadata_stage_a(self, custom_roots: list[Path] | None = None) -> int:
        """STAGE A: Ultra-fast metadata ingestion using os.scandir with batched SQLite commits."""
        roots = custom_roots or self._resolve_roots()
        now_ns = time.time_ns()
        batch = []
        indexed_count = 0
        batch_size = self.config.enrichment_batch_size

        with self._get_connection() as con:
            for root in roots:
                stack = [root]
                while stack:
                    curr = stack.pop()
                    try:
                        with os.scandir(curr) as it:
                            for entry in it:
                                try:
                                    entry_path = Path(entry.path)
                                    if self._is_excluded(entry_path):
                                        continue

                                    is_dir = entry.is_dir(follow_symlinks=False)
                                    if is_dir:
                                        stack.append(entry_path)

                                    stat = entry.stat(follow_symlinks=False)
                                    name = entry.name
                                    name_norm = name.lower()
                                    stem = entry_path.stem.lower()
                                    ext = entry_path.suffix.lower() if not is_dir else "[directory]"
                                    path_str = str(entry_path)
                                    path_norm = path_str.lower()
                                    parent_str = str(entry_path.parent)

                                    batch.append((
                                        path_str,
                                        path_norm,
                                        parent_str,
                                        name,
                                        name_norm,
                                        stem,
                                        ext,
                                        stat.st_size if not is_dir else 0,
                                        int(stat.st_ctime * 1e9),
                                        int(stat.st_mtime * 1e9),
                                        now_ns,
                                        now_ns,
                                        1 if is_dir else 0,
                                        1 if entry.name.startswith(".") else 0,
                                        1,
                                        "PENDING" if not is_dir else "SKIPPED",
                                    ))

                                    if len(batch) >= batch_size:
                                        self._commit_metadata_batch(con, batch)
                                        indexed_count += len(batch)
                                        batch.clear()

                                except (PermissionError, OSError):
                                    continue
                    except (PermissionError, OSError):
                        continue

            if batch:
                self._commit_metadata_batch(con, batch)
                indexed_count += len(batch)
                batch.clear()

        self.total_indexed = indexed_count
        return indexed_count

    def _commit_metadata_batch(self, con: sqlite3.Connection, batch: list[tuple]):
        # Insert or replace into files
        cur = con.cursor()
        cur.executemany(
            """
            INSERT INTO files (
                path, path_norm, parent_path, name, name_norm, stem, extension,
                size_bytes, created_ns, modified_ns, indexed_ns, last_seen_ns,
                is_directory, is_hidden, is_available, content_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                name = excluded.name,
                name_norm = excluded.name_norm,
                stem = excluded.stem,
                extension = excluded.extension,
                size_bytes = excluded.size_bytes,
                modified_ns = excluded.modified_ns,
                last_seen_ns = excluded.last_seen_ns,
                is_available = 1
            """,
            batch,
        )

        # Ingest FTS5 entries for new/updated files
        paths = [b[0] for b in batch]
        placeholders = ",".join("?" * len(paths))
        cur.execute(f"SELECT id, path, name, stem FROM files WHERE path IN ({placeholders})", paths)
        fts_rows = []
        for row in cur.fetchall():
            fid, fpath, fname, fstem = row
            ptokens = path_tokens_string(fpath)
            fts_rows.append((fid, fname, fstem, ptokens, ""))

        # Delete existing FTS entries for these file_ids
        cur.executemany("DELETE FROM files_fts WHERE file_id = ?", [(r[0],) for r in fts_rows])
        # Insert new FTS entries
        cur.executemany(
            "INSERT INTO files_fts(file_id, name, stem, path_tokens, content) VALUES (?, ?, ?, ?, ?)",
            fts_rows,
        )
        con.commit()

    async def run_enrichment_stage_b(self, limit: int = 100):
        """STAGE B: Asynchronous background content extraction and embedding."""
        if self.is_enriching:
            return
        self.is_enriching = True
        try:
            with self._get_connection() as con:
                con.row_factory = sqlite3.Row
                cur = con.execute(
                    "SELECT id, path, name, extension FROM files WHERE content_status = 'PENDING' AND is_available = 1 ORDER BY modified_ns DESC LIMIT ?",
                    (limit,),
                )
                pending = [dict(row) for row in cur.fetchall()]

            for item in pending:
                fid = item["id"]
                path_str = item["path"]
                ext = item["extension"]

                # Extract content in worker thread
                text, excerpt, status, error = await asyncio.to_thread(
                    extract_file_content,
                    path_str,
                    self.config.max_file_size_mb,
                    self.config.max_text_chars,
                    self.config.max_pdf_pages,
                )

                now_ns = time.time_ns()
                with self._get_connection() as con:
                    # Update file_content
                    con.execute(
                        """
                        INSERT INTO file_content (file_id, content_excerpt, content_text, extract_status, extract_error, extracted_ns)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(file_id) DO UPDATE SET
                            content_excerpt = excluded.content_excerpt,
                            content_text = excluded.content_text,
                            extract_status = excluded.extract_status,
                            extract_error = excluded.extract_error,
                            extracted_ns = excluded.extracted_ns
                        """,
                        (fid, excerpt, text, status, error, now_ns),
                    )

                    # Update files table
                    con.execute("UPDATE files SET content_status = ? WHERE id = ?", (status, fid))

                    # Update FTS5 content column
                    if text:
                        ptokens = path_tokens_string(path_str)
                        con.execute("DELETE FROM files_fts WHERE file_id = ?", (fid,))
                        con.execute(
                            "INSERT INTO files_fts(file_id, name, stem, path_tokens, content) VALUES (?, ?, ?, ?, ?)",
                            (fid, item["name"], Path(path_str).stem, ptokens, text[:10000]),
                        )
                    con.commit()

                # Generate Document Embedding if enabled
                if self.vector_store and self.embedding_provider and text:
                    doc_rep = f"{item['name']} {excerpt}"[:1000]
                    try:
                        emb = await self.embedding_provider.embed(doc_rep)
                        self.vector_store.upsert(fid, emb)
                    except Exception:
                        pass

                self.total_enriched += 1
                # Cooperative yield between files
                await asyncio.sleep(0.005)

        finally:
            self.is_enriching = False
