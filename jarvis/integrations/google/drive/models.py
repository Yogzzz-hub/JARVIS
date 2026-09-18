"""Data models and resource identifiers for Google Drive integration."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    """Explicit boundary distinguishing local filesystem paths from cloud resources."""
    LOCAL_FILE = "LOCAL_FILE"
    GOOGLE_DRIVE_FILE = "GOOGLE_DRIVE_FILE"


class ResourceRef(BaseModel):
    """
    Unified resource reference.
    Guarantees that a Google Drive file ID is NEVER conflated with a local Windows path.
    """
    resource_type: ResourceType
    provider: str = "google_drive"
    resource_id: str
    display_name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDE_MIME = "application/vnd.google-apps.presentation"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"

# Deterministic default export mappings
EXPORT_MAPPINGS = {
    GOOGLE_DOC_MIME: {
        "default_mime": "application/pdf",
        "default_ext": ".pdf",
        "docx_mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx_ext": ".docx",
    },
    GOOGLE_SHEET_MIME: {
        "default_mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "default_ext": ".xlsx",
        "pdf_mime": "application/pdf",
        "pdf_ext": ".pdf",
    },
    GOOGLE_SLIDE_MIME: {
        "default_mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "default_ext": ".pptx",
        "pdf_mime": "application/pdf",
        "pdf_ext": ".pdf",
    },
}


class DriveFileMetadata(BaseModel):
    """Normalized Google Drive file metadata."""
    file_id: str
    name: str
    mime_type: str
    modified_time: Optional[str] = None
    size_bytes: Optional[int] = None
    parents: Tuple[str, ...] = Field(default_factory=tuple)
    web_view_link: Optional[str] = None
    is_folder: bool = False
    is_google_doc: bool = False

    def to_resource_ref(self) -> ResourceRef:
        return ResourceRef(
            resource_type=ResourceType.GOOGLE_DRIVE_FILE,
            provider="google_drive",
            resource_id=self.file_id,
            display_name=self.name,
            metadata={
                "mime_type": self.mime_type,
                "size_bytes": self.size_bytes,
                "is_folder": self.is_folder,
                "is_google_doc": self.is_google_doc,
                "web_view_link": self.web_view_link,
            },
        )
