"""Knowledge base (RAG): natural-language lexical search, hybrid dense retrieval, scopes, ingestion, QA tools."""
from __future__ import annotations

import pytest

from jarvis.core.knowledge.engine import KnowledgeEngine, build_fts_query
from jarvis.core.knowledge.models import KnowledgeScopeFilter
from jarvis.core.knowledge.service import KnowledgeService
from jarvis.tests.fake_ollama import FakeOllama

DOC = (
    "# Travel policy\n\n"
    "Employees may claim up to 2500 rupees per day for meals while travelling.\n\n"
    "# Refunds\n\n"
    "Customers receive a full refund within 14 days of purchase if the product is unused.\n\n"
    "# Security\n\n"
    "Badges must be worn at all times inside the Chennai office."
)


def test_fts_query_drops_stopwords_and_ors_terms():
    q = build_fts_query("What is the refund policy for customers?")
    assert '"what"' not in q and '"the"' not in q
    assert '"refund"*' in q and '"policy"*' in q and " OR " in q
    assert build_fts_query("what is it?") == ""


def test_natural_language_question_finds_the_right_chunk(tmp_path):
    ke = KnowledgeEngine(tmp_path / "k.db")
    col = ke.create_collection("Policies", [str(tmp_path)])
    ke.index_document_text(col.collection_id, str(tmp_path / "policy.md"), DOC)
    hits = ke.search("How many days do customers have to get a refund?")
    assert hits, "a full English question must match (it used to require every word)"
    assert "14 days" in hits[0].snippet
    assert hits[0].title.startswith("policy.md (Refunds")


def test_reindexing_replaces_chunks_without_stale_fts_rows(tmp_path):
    ke = KnowledgeEngine(tmp_path / "k.db")
    col = ke.create_collection("Docs", [])
    path = str(tmp_path / "a.md")
    ke.index_document_text(col.collection_id, path, "alpha bravo charlie")
    ke.index_document_text(col.collection_id, path, "delta echo foxtrot")
    assert not ke.search("alpha bravo")
    assert ke.search("foxtrot")
    with ke._get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM rag_chunks_fts").fetchone()[0] == 1
    # Same content in two files must not collide on chunk id.
    ke.index_document_text(col.collection_id, str(tmp_path / "b.md"), "delta echo foxtrot")
    assert len(ke.search("foxtrot", limit=5)) == 2


@pytest.mark.asyncio
async def test_hybrid_search_uses_embeddings_and_keeps_scope_isolation(tmp_path):
    fake = FakeOllama()
    client = fake.client(embed_model="nomic-embed-text")
    ke = KnowledgeEngine(tmp_path / "k.db")
    ks = KnowledgeService(ke, embedder=client)
    ke.index_document_text("c1", "public.md", "Quarterly revenue grew twelve percent.")
    ke.index_document_text("c2", "chat_a.txt", "Secret launch code is NEBULA.", conversation_scope="scope:whatsapp:chat:a",
                           privacy_scope="scope:whatsapp")
    assert await ke.embed_pending(client) == 2
    assert ke.vector_count() == 2

    outsider = KnowledgeScopeFilter(allowed_scopes={"scope:user", "scope:whatsapp:chat:b"})
    items = await ks.search_unified("secret launch code", scope_filter=outsider)
    assert all("NEBULA" not in i.snippet for i in items), "dense retrieval must respect privacy scopes too"

    owner = KnowledgeScopeFilter(allowed_scopes={"scope:user", "scope:documents", "scope:whatsapp:chat:a"})
    items = await ks.search_unified("secret launch code", scope_filter=owner)
    assert items and "NEBULA" in items[0].snippet
    assert any(p == "/api/embed" for p, _ in fake.requests)


def test_ingest_folder_indexes_supported_files(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.md").write_text("# Meeting\n\nThe demo is on Friday at 3 pm.", encoding="utf-8")
    (tmp_path / "notes" / "b.txt").write_text("Grocery list: milk, eggs, bread.", encoding="utf-8")
    (tmp_path / "notes" / "image.png").write_bytes(b"\x89PNG....")
    (tmp_path / "notes" / "node_modules").mkdir()
    (tmp_path / "notes" / "node_modules" / "x.md").write_text("ignored dependency docs", encoding="utf-8")
    ke = KnowledgeEngine(tmp_path / "k.db")
    stats = ke.ingest_path(tmp_path / "notes", "Personal")
    assert stats["files_indexed"] == 2
    assert ke.search("when is the demo")[0].snippet.startswith("# Meeting")
    assert not ke.search("ignored dependency")
    listing = ke.list_collections()
    assert listing[0]["name"] == "Personal" and listing[0]["files"] == 2


@pytest.mark.asyncio
async def test_document_qa_answers_from_passages_with_citations(tmp_path):
    from jarvis.core.llm.assistant import Assistant
    from jarvis.tools.productivity.doc_qa import DocumentQAInput, DocumentQATool

    def responder(payload):
        context = payload["messages"][-1]["content"]
        assert "14 days" in context
        return "Customers can get a full refund within 14 days if unused. [2]"

    fake = FakeOllama(responder=responder)
    doc = tmp_path / "policy.md"
    doc.write_text(DOC, encoding="utf-8")
    tool = DocumentQATool(assistant=Assistant(client=fake.client(chat_model="llama3.2")))
    out = await tool.arun(DocumentQAInput(question="How long do customers have for refunds?", document_path=str(doc)))
    assert out["abstained"] is False
    assert "14 days" in out["answer"] and "[2]" not in out["answer"]
    assert out["citations"] and out["citations"][0].source_path == str(doc)

    fake.responder = lambda p: "INSUFFICIENT_EVIDENCE"
    out = await tool.arun(DocumentQAInput(question="What is the CEO's salary?", document_path=str(doc)))
    assert out["abstained"] is True


@pytest.mark.asyncio
async def test_document_qa_offline_falls_back_to_keyword_evidence(tmp_path):
    from jarvis.core.llm.assistant import Assistant
    from jarvis.tools.productivity.doc_qa import DocumentQAInput, DocumentQATool

    doc = tmp_path / "policy.md"
    doc.write_text(DOC, encoding="utf-8")
    tool = DocumentQATool(assistant=Assistant(client=FakeOllama(reachable=False).client()))
    out = await tool.arun(DocumentQAInput(question="refund within days of purchase", document_path=str(doc)))
    assert out["abstained"] is False and "refund" in out["answer"].lower()


@pytest.mark.asyncio
async def test_knowledge_tools_ingest_then_answer(tmp_path):
    from jarvis.core.llm.assistant import Assistant
    from jarvis.tools.productivity.doc_qa import KnowledgeIngestTool, KnowledgeSearchTool

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "wifi.md").write_text("The guest wifi password is Falcon-42.", encoding="utf-8")
    fake = FakeOllama(responder=lambda p: "The guest wifi password is Falcon-42. [1]")
    client = fake.client(chat_model="llama3.2", embed_model="nomic-embed-text")
    ks = KnowledgeService(KnowledgeEngine(tmp_path / "k.db"), embedder=client)
    ingest = KnowledgeIngestTool(knowledge_service=ks)
    out = await ingest.run({"path": str(tmp_path / "docs"), "collection": "Home"})
    assert out["files_indexed"] == 1 and "learned 1 file" in out["message"]

    search = KnowledgeSearchTool(knowledge_service=ks, assistant=Assistant(client=client))
    ans = await search.arun({"question": "what is the guest wifi password"})
    assert "Falcon-42" in ans["answer"] and not ans["abstained"]
    assert "Falcon-42" in search.run({"question": "guest wifi password"})["answer"]
