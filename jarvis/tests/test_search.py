import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import pytest

from jarvis.config import SearchConfig
from jarvis.memory.search.cache import SearchHotCache
from jarvis.memory.search.engine import SearchEngine
from jarvis.memory.search.extractor import extract_file_content, compute_file_hash
from jarvis.memory.search.models import MatchReason, SearchQuery, SearchResult
from jarvis.memory.search.query_parser import parse_search_query
from jarvis.memory.search.ranking import calculate_rrf_score, rerank_search_results
from jarvis.memory.search.tokenizer import tokenize_filename, tokenize_path, path_tokens_string
from jarvis.memory.search.vector.embeddings import MockEmbeddingProvider, QueryEmbeddingCache
from jarvis.memory.search.vector.sqlite_vec import SQLiteVecStore
from jarvis.memory.working_memory import WorkingMemory
from jarvis.tools.system.file_tools import (
    CopyFileInput,
    CopyFileTool,
    CreateFolderInput,
    CreateFolderTool,
    DeleteFileInput,
    DeleteFileTool,
    FindFileInput,
    FindFileTool,
    MoveFileInput,
    MoveFileTool,
    OpenFileInput,
    OpenFileTool,
    ReadMetadataInput,
    ReadFileMetadataTool,
    RenameFileInput,
    RenameFileTool,
)

# ----------------- 1. Tokenizer Tests -----------------

def test_tokenize_filename():
    assert tokenize_filename("UNIT_4_DL_FINAL_2.pdf") == ["unit", "4", "dl", "final", "2", "pdf"]
    assert tokenize_filename("DeepLearningNotes.pdf") == ["deep", "learning", "notes", "pdf"]
    assert tokenize_filename("nlp-unit5_final-v2.pdf") == ["nlp", "unit", "5", "final", "v", "2", "pdf"]
    assert tokenize_filename("report_2026_Q3.docx") == ["report", "2026", "q", "3", "docx"]
    assert tokenize_filename("MyAwesomeApp.tar.gz") == ["my", "awesome", "app", "tar", "gz"]

def test_tokenize_path():
    tokens = tokenize_path(r"C:\Users\ashok\Documents\Notes\DeepLearning.pdf")
    assert "users" in tokens
    assert "documents" in tokens
    assert "notes" in tokens
    assert "deep" in tokens
    assert "learning" in tokens
    assert "pdf" in tokens

def test_path_tokens_string():
    res = path_tokens_string(r"C:\Projects\nlp\classifier.py")
    assert "projects" in res
    assert "nlp" in res
    assert "classifier" in res
    assert "py" in res

# ----------------- 2. Query Parser Tests -----------------

def test_query_parser_type_hints():
    q = parse_search_query("find NLP pdf")
    assert q.type_hint == ".pdf"
    assert "nlp" in q.tokens

    q2 = parse_search_query("where is my budget spreadsheet")
    assert q2.type_hint == ".xlsx"
    assert "budget" in q2.tokens

    q3 = parse_search_query("search for python script benchmark")
    assert q3.type_hint == ".py"
    assert "benchmark" in q3.tokens

    q4 = parse_search_query("find presentation on quarterly review")
    assert q4.type_hint == ".pptx"

def test_query_parser_temporal_hints():
    q = parse_search_query("find the report I opened yesterday")
    assert q.temporal_hint == "opened yesterday"

    q2 = parse_search_query("show my latest notes")
    assert q2.latest is True

def test_query_parser_context_references():
    assert parse_search_query("open that file").context_reference is True
    assert parse_search_query("the second one").context_reference is True
    assert parse_search_query("open that folder").context_reference is True
    assert parse_search_query("open that").context_reference is True
    assert parse_search_query("find deep learning pdf").context_reference is False

def test_query_parser_semantic_triggers():
    q1 = parse_search_query("find the notes explaining attention mechanism")
    assert q1.semantic is True

    q2 = parse_search_query("search for document discussing transformer models")
    assert q2.semantic is True

    q3 = parse_search_query("unit 4 dl notes.pdf")
    assert q3.semantic is False

# ----------------- 3. Hot Cache Tests -----------------

def test_search_hot_cache_hit_and_eviction():
    cache = SearchHotCache(max_entries=3)
    q1 = parse_search_query("test query 1")
    q2 = parse_search_query("test query 2")
    q3 = parse_search_query("test query 3")
    q4 = parse_search_query("test query 4")

    res = [SearchResult(file_id=1, path="a.txt", name="a.txt", extension=".txt", score=1.0, confidence=1.0)]

    assert cache.get(q1) is None
    cache.put(q1, res)
    assert cache.get(q1) == res
    assert cache.hits == 1

    cache.put(q2, res)
    cache.put(q3, res)
    cache.put(q4, res)  # Should evict oldest (q1)

    assert cache.get(q1) is None
    assert cache.misses >= 1

def test_search_hot_cache_generational_invalidation():
    cache = SearchHotCache()
    q = parse_search_query("nlp notes")
    res = [SearchResult(file_id=1, path="a.txt", name="a.txt", extension=".txt", score=1.0, confidence=1.0)]

    cache.put(q, res)
    assert cache.get(q) == res

    cache.bump_generation()
    assert cache.get(q) is None

# ----------------- 4. Working Memory & Pronoun Resolution -----------------

def test_working_memory_pronoun_resolution():
    wm = WorkingMemory()
    r1 = SearchResult(file_id=1, path="C:/docs/report.pdf", name="report.pdf", extension=".pdf", score=0.9, confidence=0.9)
    r2 = SearchResult(file_id=2, path="C:/docs/notes.txt", name="notes.txt", extension=".txt", score=0.8, confidence=0.8)
    r3 = SearchResult(file_id=3, path="C:/docs/slides.pptx", name="slides.pptx", extension=".pptx", score=0.7, confidence=0.7)

    q = parse_search_query("find notes")
    wm.record_search(q, [r1, r2, r3])

    # Positional ordinals
    assert wm.resolve_reference("the first one") == r1
    assert wm.resolve_reference("the second one") == r2
    assert wm.resolve_reference("the last one") == r3

    # Type-filtered reference
    assert wm.resolve_reference("open the pdf") == r1

    # Direct pronoun fallback
    assert wm.resolve_reference("open that file") == r1

    # Record opened file
    wm.record_opened("C:/docs/notes.txt")
    assert wm.resolve_reference("open that file") == "C:/docs/notes.txt"
    assert Path(wm.resolve_reference("open that folder")) == Path("C:/docs")

# ----------------- 5. Ranking & Ambiguity Tests -----------------

def test_ranking_and_bonuses():
    q = parse_search_query("find nlp pdf")
    candidates = [
        {
            "id": 1,
            "path": "C:/docs/nlp.pdf",
            "name": "nlp.pdf",
            "name_norm": "nlp.pdf",
            "stem": "nlp",
            "extension": ".pdf",
            "modified_ns": time.time_ns(),
            "open_count": 5,
        },
        {
            "id": 2,
            "path": "C:/docs/nlp_lecture.txt",
            "name": "nlp_lecture.txt",
            "name_norm": "nlp_lecture.txt",
            "stem": "nlp_lecture",
            "extension": ".txt",
            "modified_ns": time.time_ns() - (10 * 86400 * 1_000_000_000),
            "open_count": 0,
        },
    ]

    results, is_ambig, clarify = rerank_search_results(candidates, q)
    assert len(results) == 2
    top = results[0]
    assert top.file_id == 1
    assert MatchReason.EXACT_NAME.value in top.match_reasons
    assert MatchReason.TYPE_MATCH.value in top.match_reasons
    assert MatchReason.RECENT.value in top.match_reasons
    assert MatchReason.USAGE_BOOST.value in top.match_reasons
    assert is_ambig is False

def test_ambiguity_detection():
    q = parse_search_query("project plan")
    candidates = [
        {
            "id": 10,
            "path": "C:/a/project_plan.docx",
            "name": "project_plan.docx",
            "name_norm": "project_plan.docx",
            "stem": "project_plan",
            "extension": ".docx",
            "modified_ns": 1000,
            "open_count": 0,
        },
        {
            "id": 11,
            "path": "C:/b/project_plan.docx",
            "name": "project_plan.docx",
            "name_norm": "project_plan.docx",
            "stem": "project_plan",
            "extension": ".docx",
            "modified_ns": 1000,
            "open_count": 0,
        },
    ]
    results, is_ambig, clarify = rerank_search_results(candidates, q, ambiguity_threshold=0.05)
    assert is_ambig is True
    assert clarify is not None
    assert "multiple" in clarify.lower() or "which one" in clarify.lower()

# ----------------- 6. Content Extractor Tests -----------------

def test_extract_plain_text(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("Hello JARVIS! Ultra-fast file intelligence.", encoding="utf-8")

    text, excerpt, status, err = extract_file_content(f)
    sha = compute_file_hash(f)
    assert status == "SUCCESS"
    assert "Ultra-fast" in text
    assert len(excerpt) <= 300
    assert len(sha) == 64

def test_extract_large_text_truncation(tmp_path):
    f = tmp_path / "big.txt"
    large_content = "Word " * 50_000
    f.write_text(large_content, encoding="utf-8")

    cfg = SearchConfig(max_text_chars=5000)
    text, excerpt, status, _ = extract_file_content(f, max_text_chars=cfg.max_text_chars)
    assert status == "SUCCESS"
    assert len(text) <= 5000

# ----------------- 7. Database & Search Engine Fixture -----------------

@pytest.fixture
def test_db_path(tmp_path):
    db_file = tmp_path / "test_search.db"
    # Apply migrations 001, 002, 003
    migration_dir = Path(__file__).resolve().parent.parent / "db/migrations"
    migrations = sorted(migration_dir.glob("*.sql"))

    with sqlite3.connect(db_file) as con:
        con.execute("PRAGMA journal_mode=WAL")
        for m in migrations:
            con.executescript(m.read_text(encoding="utf-8"))

    return db_file

@pytest.fixture
def populated_engine(test_db_path):
    now_ns = time.time_ns()
    # Populate test files
    with sqlite3.connect(test_db_path) as con:
        con.execute(
            """
            INSERT INTO files (id, path, path_norm, parent_path, name, name_norm, stem, extension, size_bytes, modified_ns, is_available, open_count)
            VALUES 
            (1, 'C:/Users/test/Documents/DeepLearning_Unit4.pdf', 'c:/users/test/documents/deeplearning_unit4.pdf', 'c:/users/test/documents', 'DeepLearning_Unit4.pdf', 'deeplearning_unit4.pdf', 'deeplearning_unit4', '.pdf', 10240, ?, 1, 3),
            (2, 'C:/Users/test/Documents/nlp_lecture_notes.docx', 'c:/users/test/documents/nlp_lecture_notes.docx', 'c:/users/test/documents', 'nlp_lecture_notes.docx', 'nlp_lecture_notes.docx', 'nlp_lecture_notes', '.docx', 20480, ?, 1, 1),
            (3, 'C:/Users/test/Desktop/classifier.py', 'c:/users/test/desktop/classifier.py', 'c:/users/test/desktop', 'classifier.py', 'classifier.py', 'classifier', '.py', 4096, ?, 1, 0),
            (4, 'C:/Users/test/Downloads/attention_paper.pdf', 'c:/users/test/downloads/attention_paper.pdf', 'c:/users/test/downloads', 'attention_paper.pdf', 'attention_paper.pdf', 'attention_paper', '.pdf', 51200, ?, 1, 0)
            """,
            (now_ns, now_ns - 86400 * 1_000_000_000, now_ns - 2 * 86400 * 1_000_000_000, now_ns)
        )
        # Populate FTS5 index
        con.execute(
            """
            INSERT INTO files_fts (file_id, name, stem, path_tokens, content)
            VALUES
            (1, 'DeepLearning_Unit4.pdf', 'deeplearning_unit4', 'users test documents deep learning unit 4 pdf', 'convolutional neural networks backpropagation gradient descent'),
            (2, 'nlp_lecture_notes.docx', 'nlp_lecture_notes', 'users test documents nlp lecture notes docx', 'natural language processing tokenization transformers word2vec'),
            (3, 'classifier.py', 'classifier', 'users test desktop classifier py', 'import torch import numpy as np train evaluate'),
            (4, 'attention_paper.pdf', 'attention_paper', 'users test downloads attention paper pdf', 'attention is all you need multihead self attention mechanism transformer')
            """
        )
        con.commit()

    hot_cache = SearchHotCache()
    wm = WorkingMemory()
    vec_store = SQLiteVecStore(test_db_path)
    embedder = MockEmbeddingProvider(dim=128)
    engine = SearchEngine(
        db_path=test_db_path,
        hot_cache=hot_cache,
        working_memory=wm,
        vector_store=vec_store,
        embedding_provider=embedder,
    )
    return engine

# ----------------- 8. Search Engine Cascade Tests -----------------

@pytest.mark.asyncio
async def test_search_engine_exact_metadata(populated_engine):
    resp = await populated_engine.search("classifier.py")
    assert resp.search_mode == "EXACT_METADATA"
    assert len(resp.results) > 0
    assert resp.results[0].name == "classifier.py"
    assert resp.latency_ms < 50.0  # Well within hard ceiling

@pytest.mark.asyncio
async def test_search_engine_fts_filename(populated_engine):
    resp = await populated_engine.search("find deep learning unit 4")
    assert len(resp.results) > 0
    top = resp.results[0]
    assert "DeepLearning_Unit4.pdf" in top.name
    assert resp.results[0].confidence > 0.1
    assert resp.latency_ms < 50.0

@pytest.mark.asyncio
async def test_search_engine_fts_content_fallback(populated_engine):
    # Query words only present in content: "backpropagation gradient descent"
    resp = await populated_engine.search("backpropagation")
    assert len(resp.results) > 0
    assert resp.results[0].file_id == 1
    assert resp.search_mode in ("CONTENT_FTS", "FTS_CONTENT", "HYBRID")

@pytest.mark.asyncio
async def test_search_engine_hot_cache_hit(populated_engine):
    q = "find nlp lecture"
    resp1 = await populated_engine.search(q)
    assert resp1.search_mode != "HOT_CACHE"

    resp2 = await populated_engine.search(q)
    assert resp2.search_mode == "HOT_CACHE"
    assert resp2.latency_ms < 5.0

@pytest.mark.asyncio
async def test_search_engine_context_resolution(populated_engine):
    # First search
    await populated_engine.search("find nlp lecture")
    # Second search with pronoun
    resp = await populated_engine.search("open that file")
    assert resp.search_mode == "CONTEXT"
    assert len(resp.results) > 0
    assert "nlp_lecture_notes.docx" in resp.results[0].name

# ----------------- 9. Vector Store & Fallback Tests -----------------

@pytest.mark.asyncio
async def test_mock_embeddings_and_vector_store(test_db_path):
    store = SQLiteVecStore(test_db_path)
    mock = MockEmbeddingProvider(dimension=64)

    v1 = await mock.embed("deep learning neural networks")
    v2 = await mock.embed("deep learning artificial intelligence")
    v3 = await mock.embed("cooking recipe pasta dinner")

    assert len(v1) == 64
    assert len(v2) == 64

    store.upsert(1, v1)
    store.upsert(2, v2)
    store.upsert(3, v3)

    results = store.query(v1, top_k=2)
    assert len(results) == 2
    # Top match should be 1 with high cosine similarity
    assert results[0][0] == 1
    assert results[0][1] > 0.9

# ----------------- 10. File Tools System Tests -----------------

def test_file_tools_suite(tmp_path, populated_engine):
    test_dir = tmp_path / "sandbox"
    test_dir.mkdir()

    # 1. Create Folder
    cf_tool = CreateFolderTool()
    sub_dir = test_dir / "subfolder"
    cf_res = cf_tool.run(CreateFolderInput(path=str(sub_dir)))
    assert cf_res.created is True
    assert sub_dir.exists()

    # 2. File for metadata and copy
    test_file = test_dir / "sample.txt"
    test_file.write_text("JARVIS test content", encoding="utf-8")

    # Read Metadata
    rm_tool = ReadFileMetadataTool()
    rm_res = rm_tool.run(ReadMetadataInput(path=str(test_file)))
    assert rm_res.name == "sample.txt"
    assert rm_res.size_bytes > 0
    assert rm_res.is_directory is False

    # Copy File
    copied_file = sub_dir / "copied.txt"
    cp_tool = CopyFileTool()
    cp_res = cp_tool.run(CopyFileInput(source=str(test_file), destination=str(copied_file)))
    assert cp_res.copied is True
    assert copied_file.exists()

    # Move File
    moved_file = sub_dir / "moved.txt"
    mv_tool = MoveFileTool()
    mv_res = mv_tool.run(MoveFileInput(source=str(copied_file), destination=str(moved_file)))
    assert mv_res.moved is True
    assert not copied_file.exists()
    assert moved_file.exists()

    # Rename File
    ren_tool = RenameFileTool()
    ren_res = ren_tool.run(RenameFileInput(source=str(moved_file), new_name="renamed.txt"))
    assert ren_res.renamed is True
    assert (sub_dir / "renamed.txt").exists()

    # Open File (using mock launcher to avoid GUI window popup)
    opened_paths = []
    of_tool = OpenFileTool(
        db_path=populated_engine.db_path,
        working_memory=populated_engine.memory,
        launcher=lambda p: opened_paths.append(p),
    )
    of_res = of_tool.run(OpenFileInput(path=str(test_file)))
    assert of_res.opened is True
    assert len(opened_paths) == 1
    assert opened_paths[0] == str(test_file)
    assert populated_engine.memory.last_opened_file == str(test_file)

    # Delete File (Send2Trash fallback / safe delete)
    del_tool = DeleteFileTool()
    target_to_delete = sub_dir / "renamed.txt"
    del_res = del_tool.run(DeleteFileInput(path=str(target_to_delete)))
    assert del_res.deleted is True
    assert not target_to_delete.exists()

# ----------------- 11. Golden Dataset Sample Validation -----------------

def test_golden_dataset_parser_coverage():
    golden_path = Path(__file__).resolve().parent.parent.parent / "tests/data/search_golden.jsonl"
    if not golden_path.exists():
        golden_path = Path(__file__).resolve().parent.parent / "tests/data/search_golden.jsonl"

    assert golden_path.exists(), f"Golden dataset not found at {golden_path}"

    with open(golden_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) >= 200, f"Expected at least 200 golden queries, found {len(lines)}"

    # Validate parsing for all lines without exceptions
    for line in lines:
        entry = json.loads(line)
        query_text = entry["query"]
        sq = parse_search_query(query_text)
        assert sq.raw_query == query_text
        assert isinstance(sq.tokens, list)
        if "type_hint" in entry and entry["type_hint"]:
            assert sq.type_hint == entry["type_hint"]
