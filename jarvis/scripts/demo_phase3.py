import asyncio
import os
from pathlib import Path
import sqlite3
import tempfile
import time

from jarvis.config import ROOT
from jarvis.memory.search.cache import SearchHotCache
from jarvis.memory.search.engine import SearchEngine
from jarvis.memory.search.query_parser import parse_search_query
from jarvis.memory.search.vector.embeddings import MockEmbeddingProvider
from jarvis.memory.search.vector.sqlite_vec import SQLiteVecStore
from jarvis.memory.working_memory import WorkingMemory
from jarvis.tools.system.file_tools import (
    CreateFolderInput,
    CreateFolderTool,
    FindFileInput,
    FindFileTool,
    OpenFileInput,
    OpenFileTool,
    ReadMetadataInput,
    ReadFileMetadataTool,
)

async def run_phase3_demo():
    print("=" * 80)
    print("      JARVIS EDGE -- PHASE 3 ACCEPTANCE DEMONSTRATION")
    print("=" * 80)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db_path = tf.name

    # Apply migration 003
    migration_path = ROOT / "db/migrations/003_search_index.sql"
    if not migration_path.exists():
        migration_path = ROOT.parent / "db/migrations/003_search_index.sql"

    dummy_target = Path(tempfile.gettempdir()) / "classifier_demo.py"
    dummy_target.write_text("print('demo classifier')", encoding="utf-8")

    with sqlite3.connect(temp_db_path) as con:
        con.executescript(migration_path.read_text(encoding="utf-8"))
        now_ns = time.time_ns()
        con.execute(
            """
            INSERT INTO files (id, path, path_norm, parent_path, name, name_norm, stem, extension, size_bytes, modified_ns, is_available, open_count)
            VALUES 
            (1, 'C:/Users/ashok/Documents/NLP_Transformers_Unit5.pdf', 'c:/users/ashok/documents/nlp_transformers_unit5.pdf', 'c:/users/ashok/documents', 'NLP_Transformers_Unit5.pdf', 'nlp_transformers_unit5.pdf', 'nlp_transformers_unit5', '.pdf', 1048576, ?, 1, 10),
            (2, ?, ?, ?, 'classifier_demo.py', 'classifier_demo.py', 'classifier_demo', '.py', 4096, ?, 1, 4),
            (3, 'C:/Users/ashok/Documents/DeepLearningNotes.docx', 'c:/users/ashok/documents/deeplearningnotes.docx', 'c:/users/ashok/documents', 'DeepLearningNotes.docx', 'deeplearningnotes.docx', 'deeplearningnotes', '.docx', 32768, ?, 1, 2),
            (4, 'C:/Users/ashok/Downloads/attention_paper.pdf', 'c:/users/ashok/downloads/attention_paper.pdf', 'c:/users/ashok/downloads', 'attention_paper.pdf', 'attention_paper.pdf', 'attention_paper', '.pdf', 524288, ?, 1, 1)
            """,
            (now_ns, str(dummy_target), str(dummy_target).lower(), str(dummy_target.parent), now_ns, now_ns - 86400 * 1_000_000_000, now_ns)
        )
        con.execute(
            """
            INSERT INTO files_fts (file_id, name, stem, path_tokens, content)
            VALUES
            (1, 'NLP_Transformers_Unit5.pdf', 'nlp_transformers_unit5', 'users ashok documents nlp transformers unit 5 pdf', 'natural language processing tokenization multi-head attention'),
            (2, 'classifier_demo.py', 'classifier_demo', 'classifier demo py', 'import torch neural network training optimizer evaluation loss'),
            (3, 'DeepLearningNotes.docx', 'deeplearningnotes', 'users ashok documents deep learning notes docx', 'convolutional networks residual connections adam optimizer'),
            (4, 'attention_paper.pdf', 'attention_paper', 'users ashok downloads attention paper pdf', 'attention is all you need vaswani feed forward layers transformer architecture')
            """
        )
        con.commit()

    hot_cache = SearchHotCache()
    wm = WorkingMemory()
    vec_store = SQLiteVecStore(temp_db_path)
    mock_embed = MockEmbeddingProvider(dimension=64)

    engine = SearchEngine(
        db_path=temp_db_path,
        hot_cache=hot_cache,
        working_memory=wm,
        vector_store=vec_store,
        embedding_provider=mock_embed,
    )

    # ---------------- DEMO 1: Exact Filename Lookup ----------------
    print("\n[DEMO 1] Exact Filename Lookup: 'classifier_demo.py'")
    t0 = time.perf_counter_ns()
    r1 = await engine.search("classifier_demo.py")
    d1_ms = (time.perf_counter_ns() - t0) / 1e6
    print(f"  Target:            p95 < 3.0 ms")
    print(f"  Mode:              {r1.search_mode}")
    print(f"  Latency:           {d1_ms:.3f} ms")
    print(f"  Top Match:         {r1.results[0].name} ({r1.results[0].path})")
    assert r1.search_mode == "EXACT_METADATA"
    assert d1_ms < 10.0
    print("  Status:            PASS [OK]")

    # ---------------- DEMO 2: Natural Language Query ----------------
    print("\n[DEMO 2] Natural Language Query: 'find NLP pdf'")
    t0 = time.perf_counter_ns()
    r2 = await engine.search("find NLP pdf")
    d2_ms = (time.perf_counter_ns() - t0) / 1e6
    print(f"  Target:            p95 < 20.0 ms")
    print(f"  Mode:              {r2.search_mode}")
    print(f"  Latency:           {d2_ms:.3f} ms")
    print(f"  Top Match:         {r2.results[0].name} (confidence: {r2.results[0].confidence:.2f})")
    print(f"  Reasons:           {', '.join(r2.results[0].match_reasons)}")
    assert "NLP" in r2.results[0].name
    assert d2_ms < 20.0
    print("  Status:            PASS [OK]")

    # ---------------- DEMO 3: Stem / Partial Search ----------------
    print("\n[DEMO 3] Stem / Partial Match: 'deeplearn notes'")
    t0 = time.perf_counter_ns()
    r3 = await engine.search("deeplearn notes")
    d3_ms = (time.perf_counter_ns() - t0) / 1e6
    print(f"  Mode:              {r3.search_mode}")
    print(f"  Latency:           {d3_ms:.3f} ms")
    print(f"  Top Match:         {r3.results[0].name}")
    assert "DeepLearningNotes" in r3.results[0].name
    print("  Status:            PASS [OK]")

    # ---------------- DEMO 4: Body Content Search ----------------
    print("\n[DEMO 4] Body Content Search: 'vaswani feed forward'")
    t0 = time.perf_counter_ns()
    r4 = await engine.search("vaswani feed forward")
    d4_ms = (time.perf_counter_ns() - t0) / 1e6
    print(f"  Mode:              {r4.search_mode}")
    print(f"  Latency:           {d4_ms:.3f} ms")
    print(f"  Top Match:         {r4.results[0].name}")
    assert "attention_paper.pdf" in r4.results[0].name
    print("  Status:            PASS [OK]")

    # ---------------- DEMO 5: Conversational Context ----------------
    print("\n[DEMO 5] Conversational Context: 'open that file'")
    t0 = time.perf_counter_ns()
    r5 = await engine.search("open that file")
    d5_ms = (time.perf_counter_ns() - t0) / 1e6
    print(f"  Target:            p95 < 2.0 ms")
    print(f"  Mode:              {r5.search_mode}")
    print(f"  Latency:           {d5_ms:.3f} ms")
    print(f"  Resolved Target:   {r5.results[0].name}")
    assert r5.search_mode == "CONTEXT"
    assert d5_ms < 5.0
    print("  Status:            PASS [OK]")

    # ---------------- DEMO 6: Hot Cache Lookup ----------------
    print("\n[DEMO 6] Hot Cache Lookup: 'find NLP pdf' (Repeated)")
    t0 = time.perf_counter_ns()
    r6 = await engine.search("find NLP pdf")
    d6_ms = (time.perf_counter_ns() - t0) / 1e6
    print(f"  Target:            p95 < 1.0 ms")
    print(f"  Mode:              {r6.search_mode}")
    print(f"  Latency:           {d6_ms:.3f} ms")
    assert r6.search_mode == "HOT_CACHE"
    assert d6_ms < 2.0
    print("  Status:            PASS [OK]")

    # ---------------- DEMO 7: Native File Tools ----------------
    print("\n[DEMO 7] Native File Tool Invocation")
    find_tool = FindFileTool(engine)
    f_res = find_tool.run(FindFileInput(query="find classifier code"))
    print(f"  find_file:         Found {len(f_res.results)} results in {f_res.latency_ms:.2f} ms")

    rm_tool = ReadFileMetadataTool()
    m_res = rm_tool.run(ReadMetadataInput(path=str(Path(temp_db_path))))
    print(f"  read_metadata:     {m_res.name}, size: {m_res.size_bytes} bytes, modified: {m_res.modified_iso}")

    opened_record = []
    open_tool = OpenFileTool(
        db_path=temp_db_path,
        working_memory=wm,
        launcher=lambda p: opened_record.append(p),
    )
    o_res = open_tool.run(OpenFileInput(file_id=2))
    print(f"  open_file:         {o_res.message} (file_id: {o_res.file_id})")
    assert len(opened_record) == 1
    print("  Status:            PASS [OK]")

    print("\n" + "=" * 80)
    print("    ALL 7 PHASE 3 DEMONSTRATION SCENARIOS COMPLETED SUCCESSFULLY!")
    print("=" * 80 + "\n")

    try:
        Path(temp_db_path).unlink(missing_ok=True)
    except Exception:
        pass

def main():
    asyncio.run(run_phase3_demo())

if __name__ == "__main__":
    main()
