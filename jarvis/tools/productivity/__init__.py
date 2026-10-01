from __future__ import annotations

from jarvis.tools.base import Tool
from jarvis.tools.productivity.dictation import (
    DictationTool,
    VoiceEditTool,
    DictationModeControlTool,
)
from jarvis.tools.productivity.workspace import SaveWorkspaceTool, LaunchWorkspaceTool
from jarvis.tools.productivity.downloads_organizer import OrganizeDownloadsTool
from jarvis.tools.productivity.batch_ops import BatchRenameTool
from jarvis.tools.productivity.duplicate_finder import DuplicateFinderTool
from jarvis.tools.productivity.doc_qa import DocumentQATool, KnowledgeIngestTool, KnowledgeSearchTool
from jarvis.tools.productivity.quick_notes import QuickNoteTool, SearchNotesTool
from jarvis.tools.productivity.meeting_notes import MeetingNotesTool
from jarvis.tools.productivity.media_tools import ExtractAudioTool, TrimClipTool
from jarvis.tools.productivity.briefing import PersonalBriefingTool, StudyFocusTool
from jarvis.tools.productivity.developer_tools import GitStatusTool, RunProjectTestsTool, DiagnoseErrorTool
from jarvis.tools.productivity.project_tools import create_project_tools
from jarvis.tools.productivity.code_tools import create_code_tools
from jarvis.tools.productivity.database_tools import create_database_tools


def create_productivity_tools() -> list[Tool]:
    base_prod = [
        DictationTool(),
        VoiceEditTool(),
        DictationModeControlTool(),
        SaveWorkspaceTool(),
        LaunchWorkspaceTool(),
        OrganizeDownloadsTool(),
        BatchRenameTool(),
        DuplicateFinderTool(),
        DocumentQATool(),
        KnowledgeIngestTool(),
        KnowledgeSearchTool(),
        QuickNoteTool(),
        SearchNotesTool(),
        MeetingNotesTool(),
        ExtractAudioTool(),
        TrimClipTool(),
        PersonalBriefingTool(),
        StudyFocusTool(),
        GitStatusTool(),
        RunProjectTestsTool(),
        DiagnoseErrorTool(),
    ]
    return base_prod + create_project_tools() + create_code_tools() + create_database_tools()


__all__ = [
    "DictationTool",
    "VoiceEditTool",
    "DictationModeControlTool",
    "SaveWorkspaceTool",
    "LaunchWorkspaceTool",
    "OrganizeDownloadsTool",
    "BatchRenameTool",
    "DuplicateFinderTool",
    "DocumentQATool",
    "KnowledgeIngestTool",
    "KnowledgeSearchTool",
    "QuickNoteTool",
    "SearchNotesTool",
    "MeetingNotesTool",
    "ExtractAudioTool",
    "TrimClipTool",
    "PersonalBriefingTool",
    "StudyFocusTool",
    "GitStatusTool",
    "RunProjectTestsTool",
    "DiagnoseErrorTool",
    "create_productivity_tools",
]
