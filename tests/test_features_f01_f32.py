import os
import tempfile
from pathlib import Path
import pytest

from jarvis.tools.productivity.dictation import DictationTool, DictateInput, format_dictation
from jarvis.tools.productivity.workspace import SaveWorkspaceTool, LaunchWorkspaceTool, WorkspaceSaveInput, WorkspaceLaunchInput
from jarvis.tools.productivity.downloads_organizer import OrganizeDownloadsTool, OrganizeDownloadsInput, classify_file
from jarvis.tools.productivity.batch_ops import BatchRenameTool, BatchRenameInput
from jarvis.tools.productivity.duplicate_finder import DuplicateFinderTool, FindDuplicatesInput
from jarvis.tools.productivity.doc_qa import DocumentQATool, DocumentQAInput
from jarvis.tools.productivity.quick_notes import QuickNoteTool, SearchNotesTool, CaptureNoteInput, SearchNotesInput
from jarvis.tools.productivity.meeting_notes import MeetingNotesTool, MeetingNotesInput
from jarvis.tools.productivity.media_tools import ExtractAudioTool, ExtractAudioInput
from jarvis.tools.productivity.briefing import PersonalBriefingTool, StudyFocusTool, BriefingInput, StudyFocusInput
from jarvis.tools.productivity.developer_tools import DiagnoseErrorTool, DiagnoseErrorInput, redact_secrets


# =====================================================================
# F03: Dictation (Quoted command is never executed as an action)
# =====================================================================

def test_dictation_formatting_and_command_isolation():
    tool = DictationTool()
    raw = 'please type "delete the file" period and new line then "format c drive"'
    out = tool.run(DictateInput(text=raw, target_app="Notepad"))

    assert out["target_app"] == "Notepad"
    # Punctuation converted
    assert "." in out["formatted_text"]
    assert "\n" in out["formatted_text"]
    # The destructive command remains literal text, NOT an execution ticket
    assert '"delete the file"' in out["formatted_text"]
    assert out["status"] in ("ready_to_insert", "inserted")


# =====================================================================
# F04: Workspace Save and Launch
# =====================================================================

def test_workspace_manifest_save_and_launch():
    save_tool = SaveWorkspaceTool()
    launch_tool = LaunchWorkspaceTool()

    save_out = save_tool.run(
        WorkspaceSaveInput(
            name="ML Study Session",
            folders=("c:/ml/notes", "c:/ml/papers"),
            urls=("https://arxiv.org",),
            notes_path="c:/ml/scratch.md",
            timer_minutes=45,
        )
    )
    assert save_out["status"] == "saved"
    assert Path(save_out["manifest_path"]).exists()

    launch_out = launch_tool.run(WorkspaceLaunchInput(name="ML Study Session"))
    assert launch_out["name"] == "ML Study Session"
    assert "c:/ml/notes" in launch_out["opened_folders"]
    assert "https://arxiv.org" in launch_out["opened_urls"]


# =====================================================================
# F06: Downloads Organizer
# =====================================================================

def test_downloads_organizer_classification_and_preview():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "paper.pdf").write_text("dummy pdf", encoding="utf-8")
        (p / "photo.jpg").write_text("dummy image", encoding="utf-8")
        (p / "script.py").write_text("print('hello')", encoding="utf-8")

        tool = OrganizeDownloadsTool()
        # 1. Preview mode (dry_run=True)
        preview = tool.run(OrganizeDownloadsInput(downloads_path=str(p), dry_run=True))
        assert preview["dry_run"] is True
        assert preview["total_moved"] == 3
        # Files should NOT have moved yet
        assert (p / "paper.pdf").exists()

        # 2. Execution mode (dry_run=False)
        executed = tool.run(OrganizeDownloadsInput(downloads_path=str(p), dry_run=False))
        assert executed["dry_run"] is False
        assert (p / "Documents" / "paper.pdf").exists()
        assert (p / "Images" / "photo.jpg").exists()
        assert (p / "Code" / "script.py").exists()


# =====================================================================
# F07: Batch Operations
# =====================================================================

def test_batch_rename_with_collision_avoidance():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "report_old_v1.txt").write_text("1", encoding="utf-8")
        (p / "report_old_v2.txt").write_text("2", encoding="utf-8")

        tool = BatchRenameTool()
        out = tool.run(BatchRenameInput(directory=str(p), pattern="old", replacement="new", dry_run=False))
        assert out["total_processed"] == 2
        assert (p / "report_new_v1.txt").exists()
        assert (p / "report_new_v2.txt").exists()


# =====================================================================
# F08: Duplicate Finder (Size + Hash)
# =====================================================================

def test_duplicate_finder_exact_hash_match():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        content = "Exact duplicate content across multiple files"
        (p / "fileA.txt").write_text(content, encoding="utf-8")
        (p / "fileB.txt").write_text(content, encoding="utf-8")
        (p / "unique.txt").write_text("Different content", encoding="utf-8")

        tool = DuplicateFinderTool()
        res = tool.run(FindDuplicatesInput(directory=str(p)))
        assert len(res["duplicate_groups"]) == 1
        group = res["duplicate_groups"][0]
        assert len(group.file_paths) == 2
        assert res["total_duplicates"] == 1


# =====================================================================
# F09: Private Document Q&A with Citations and Abstention
# =====================================================================

def test_doc_qa_grounded_answer_and_abstention():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "article.txt"
        p.write_text(
            "Introduction to Quantum Algorithms.\n"
            "Shor's algorithm provides polynomial-time integer factorization.\n"
            "Grover's algorithm provides a quadratic speedup for unstructured search.\n",
            encoding="utf-8",
        )

        tool = DocumentQATool()
        # Supported query
        res = tool.run(DocumentQAInput(document_path=str(p), question="What does Shor's algorithm do?"))
        assert res["abstained"] is False
        assert len(res["citations"]) > 0
        assert "Shor's algorithm" in res["answer"]
        assert res["citations"][0].line_number == 2

        # Unsupported query -> Must abstain!
        res_unsupported = tool.run(DocumentQAInput(document_path=str(p), question="What is the weather in Tokyo today?"))
        assert res_unsupported["abstained"] is True
        assert "cannot answer" in res_unsupported["answer"]


# =====================================================================
# F10: Quick Capture and Notes
# =====================================================================

def test_quick_notes_capture_and_search():
    cap_tool = QuickNoteTool()
    search_tool = SearchNotesTool()

    note_out = cap_tool.run(CaptureNoteInput(content="Review research on PrefixConsensus and ASR streaming", tag="research"))
    assert note_out["status"] == "saved"
    assert Path(note_out["file_path"]).exists()

    search_out = search_tool.run(SearchNotesInput(query="PrefixConsensus"))
    assert search_out["total_found"] >= 1
    assert any("PrefixConsensus" in m.snippet for m in search_out["matches"])


# =====================================================================
# F12: Meeting & Lecture Notes
# =====================================================================

def test_meeting_notes_extraction():
    tool = MeetingNotesTool()
    transcript = (
        "Alice: We need to finalize the quarterly roadmap.\n"
        "Bob: Action item: Ashok will implement the connector protocol by Friday.\n"
        "Charlie: We will follow up next Monday.\n"
    )
    res = tool.run(MeetingNotesInput(title="Quarterly Review", transcript=transcript))
    assert res["status"] == "created"
    assert len(res["action_items"]) >= 1
    assert any("Ashok will implement" in a for a in res["action_items"])


# =====================================================================
# F16 & F17: Briefing and Study Focus
# =====================================================================

def test_briefing_and_focus_mode():
    briefing_tool = PersonalBriefingTool()
    briefing = briefing_tool.run(BriefingInput(include_calendar=True, project_path="c:/dev/jarvis"))
    assert "personal briefing" in briefing["briefing_text"].lower()

    focus_tool = StudyFocusTool()
    focus = focus_tool.run(StudyFocusInput(subject="Quantum Computing", duration_minutes=30))
    assert focus["status"] == "active"
    assert focus["timer_minutes"] == 30


# =====================================================================
# F19: Error Diagnosis & Secret Redaction
# =====================================================================

def test_secret_redaction_and_diagnosis():
    log_sample = (
        "Traceback (most recent call last):\n"
        "  File 'api.py', line 12, in send_payload\n"
        "    token = 'AIzaSyDx1234567890abcdefghijklmnopqrst'\n"
        "ModuleNotFoundError: No module named 'requests'\n"
    )
    redacted = redact_secrets(log_sample)
    assert "AIzaSy" not in redacted
    assert "[REDACTED_SECRET]" in redacted

    diag_tool = DiagnoseErrorTool()
    res = diag_tool.run(DiagnoseErrorInput(error_log=log_sample))
    assert "Missing Python module" in res["diagnosis"]
    assert "requests" not in res["redacted_log"] or "[REDACTED_SECRET]" in res["redacted_log"]
