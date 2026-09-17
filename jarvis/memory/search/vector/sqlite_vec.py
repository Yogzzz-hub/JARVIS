import math
import sqlite3
from typing import Any
from jarvis.memory.search.vector.base import VectorStore

class SQLiteVecStore(VectorStore):
    """VectorStore implementation using sqlite-vec if loadable, with in-memory cosine fallback."""
    def __init__(self, db_path: str = ":memory:", dimension: int = 384):
        self.db_path = db_path
        self.dimension = dimension
        self.is_sqlite_vec_active = False
        self._fallback_vectors: dict[int, list[float]] = {}
        self._init_backend()

    def _init_backend(self):
        try:
            import sqlite_vec
            con = sqlite3.connect(self.db_path)
            con.enable_load_extension(True)
            sqlite_vec.load(con)
            con.enable_load_extension(False)
            con.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_files USING vec0(file_id integer primary key, embedding float[{self.dimension}])")
            self.is_sqlite_vec_active = True
            con.close()
        except Exception:
            # Fallback to in-memory cosine vectors
            self.is_sqlite_vec_active = False

    def upsert(self, file_id: int, embedding: list[float], metadata: dict[str, Any] | None = None) -> None:
        if self.is_sqlite_vec_active:
            try:
                con = sqlite3.connect(self.db_path)
                con.enable_load_extension(True)
                import sqlite_vec
                sqlite_vec.load(con)
                con.enable_load_extension(False)
                con.execute("INSERT OR REPLACE INTO vec_files(file_id, embedding) VALUES (?, ?)", (file_id, embedding))
                con.commit()
                con.close()
                return
            except Exception:
                pass
        self._fallback_vectors[file_id] = embedding

    def delete(self, file_id: int) -> None:
        if self.is_sqlite_vec_active:
            try:
                con = sqlite3.connect(self.db_path)
                con.enable_load_extension(True)
                import sqlite_vec
                sqlite_vec.load(con)
                con.enable_load_extension(False)
                con.execute("DELETE FROM vec_files WHERE file_id = ?", (file_id,))
                con.commit()
                con.close()
            except Exception:
                pass
        self._fallback_vectors.pop(file_id, None)

    def search(self, query_vector: list[float], limit: int = 10) -> list[tuple[int, float]]:
        if self.is_sqlite_vec_active:
            try:
                con = sqlite3.connect(self.db_path)
                con.enable_load_extension(True)
                import sqlite_vec
                sqlite_vec.load(con)
                con.enable_load_extension(False)
                cur = con.execute(
                    "SELECT file_id, distance FROM vec_files WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
                    (query_vector, limit)
                )
                rows = cur.fetchall()
                con.close()
                # distance to similarity conversion
                return [(row[0], max(0.0, 1.0 - (row[1] / 2.0))) for row in rows]
            except Exception:
                pass

        # Fallback: In-memory exact cosine similarity
        results = []
        q_norm = math.sqrt(sum(x * x for x in query_vector)) or 1e-9
        for fid, emb in self._fallback_vectors.items():
            dot = sum(a * b for a, b in zip(query_vector, emb))
            e_norm = math.sqrt(sum(y * y for y in emb)) or 1e-9
            sim = dot / (q_norm * e_norm)
            results.append((fid, float(sim)))

        results.sort(key=lambda item: item[1], reverse=True)
        return results[:limit]

    def query(self, query_vector: list[float], top_k: int = 10, limit: int | None = None) -> list[tuple[int, float]]:
        k = limit if limit is not None else top_k
        return self.search(query_vector, limit=k)

    def health(self) -> dict[str, Any]:
        count = len(self._fallback_vectors)
        return {
            "status": "READY",
            "backend": "sqlite-vec" if self.is_sqlite_vec_active else "in-memory-cosine",
            "count": count,
            "dimension": self.dimension,
        }

    def version(self) -> str:
        return "sqlite-vec-0.1.6" if self.is_sqlite_vec_active else "in-memory-fallback-v1"
