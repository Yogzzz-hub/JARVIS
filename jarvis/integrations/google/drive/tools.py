"""Native typed tools for Google Drive integration."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import Field

from jarvis.integrations.google.auth.scopes import GoogleCapability, ScopeGuard
from jarvis.integrations.google.drive.client import DriveClient
from jarvis.integrations.google.drive.models import (
    DriveFileMetadata,
    ResourceRef,
    ResourceType,
)
from jarvis.integrations.google.drive.verifier import DriveVerifier
from jarvis.tools.base import (
    Contract,
    ExecutionMethod,
    IdempotencyClass,
    RiskLevel,
    Tool,
    ToolDefinition,
    ToolResult,
    VerificationResult,
)

logger = logging.getLogger("jarvis.integrations.google.drive.tools")


# ----------------- CONTRACTS -----------------

class DriveListFilesInput(Contract):
    folder_id: str = Field(default="root", description="Folder ID to list ('root' for top-level)")
    account_id: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=50)
    page_token: Optional[str] = None


class DriveListFilesOutput(Contract):
    files: Tuple[DriveFileMetadata, ...]
    next_page_token: Optional[str] = None
    count: int


class DriveSearchInput(Contract):
    query: str = Field(min_length=1, max_length=256, description="Search term for file title/content")
    account_id: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=50)
    page_token: Optional[str] = None


class DriveSearchOutput(Contract):
    files: Tuple[DriveFileMetadata, ...]
    query: str
    next_page_token: Optional[str] = None
    count: int


class DriveGetMetadataInput(Contract):
    file_id: str = Field(min_length=1, max_length=128)
    account_id: Optional[str] = None


class DriveGetMetadataOutput(Contract):
    metadata: Optional[DriveFileMetadata] = None
    found: bool
    resource_ref: Optional[ResourceRef] = None


class DriveDownloadFileInput(Contract):
    file_id: str = Field(min_length=1, max_length=128)
    destination_path: str = Field(min_length=1, description="Absolute local target destination path")
    export_mime_type: Optional[str] = Field(default=None, description="MIME type for exporting Google Docs (e.g. application/pdf)")
    overwrite: bool = False
    account_id: Optional[str] = None


class DriveDownloadFileOutput(Contract):
    local_path: str
    file_id: str
    downloaded: bool
    size_bytes: int


class DriveUploadFileInput(Contract):
    local_path: str = Field(min_length=1, description="Local path to file to upload")
    destination_folder_id: Optional[str] = Field(default=None, description="Drive destination folder ID")
    target_filename: Optional[str] = Field(default=None, description="Optional remote filename")
    account_id: Optional[str] = None


class DriveUploadFileOutput(Contract):
    uploaded: bool
    file: Optional[DriveFileMetadata] = None
    resource_ref: Optional[ResourceRef] = None


class DriveCreateFolderInput(Contract):
    folder_name: str = Field(min_length=1, max_length=256)
    parent_folder_id: Optional[str] = None
    account_id: Optional[str] = None


class DriveCreateFolderOutput(Contract):
    created: bool
    folder: Optional[DriveFileMetadata] = None


# ----------------- TOOLS -----------------

class DriveListFilesTool(Tool):
    definition = ToolDefinition(
        name="drive_list_files",
        description="List files in a specific Google Drive folder (default: root).",
        input_model=DriveListFilesInput,
        output_model=DriveListFilesOutput,
        read_only=True,
        requires_confirmation=False,
        risk=RiskLevel.READ_ONLY,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.IDEMPOTENT,
        tags=("drive", "google", "files", "list"),
    )

    def __init__(self, client: Optional[DriveClient] = None) -> None:
        self._client = client

    def run(self, input_data: Any) -> ToolResult:
        if isinstance(input_data, dict):
            input_data = DriveListFilesInput.model_validate(input_data)
        return self.execute(input_data)

    def execute(self, validated_input: DriveListFilesInput) -> ToolResult:
        ScopeGuard.assert_capability(self._client.account_id if self._client else "default", GoogleCapability.DRIVE_APP_FILE_READ)
        if not self._client:
            return ToolResult(success=False, error="DriveClient is not configured.", tool_name=self.definition.name)

        files, next_token = self._client.list_files(
            folder_id=validated_input.folder_id,
            page_size=validated_input.limit,
            page_token=validated_input.page_token,
        )

        out = DriveListFilesOutput(
            files=tuple(files),
            next_page_token=next_token,
            count=len(files),
        )
        return ToolResult(success=True, data=out.model_dump(mode="json"), tool_name=self.definition.name)


class DriveSearchTool(Tool):
    definition = ToolDefinition(
        name="drive_search",
        description="Search Google Drive by keyword. Returns file metadata without downloading content.",
        input_model=DriveSearchInput,
        output_model=DriveSearchOutput,
        read_only=True,
        requires_confirmation=False,
        risk=RiskLevel.READ_ONLY,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.IDEMPOTENT,
        tags=("drive", "google", "search"),
    )

    def __init__(self, client: Optional[DriveClient] = None) -> None:
        self._client = client

    def run(self, input_data: Any) -> ToolResult:
        if isinstance(input_data, dict):
            input_data = DriveSearchInput.model_validate(input_data)
        return self.execute(input_data)

    def execute(self, validated_input: DriveSearchInput) -> ToolResult:
        ScopeGuard.assert_capability(self._client.account_id if self._client else "default", GoogleCapability.DRIVE_BROAD_READ)
        if not self._client:
            return ToolResult(success=False, error="DriveClient is not configured.", tool_name=self.definition.name)

        files, next_token = self._client.search(
            query=validated_input.query,
            page_size=validated_input.limit,
            page_token=validated_input.page_token,
        )

        out = DriveSearchOutput(
            files=tuple(files),
            query=validated_input.query,
            next_page_token=next_token,
            count=len(files),
        )
        return ToolResult(success=True, data=out.model_dump(mode="json"), tool_name=self.definition.name)


class DriveGetMetadataTool(Tool):
    definition = ToolDefinition(
        name="drive_get_metadata",
        description="Retrieve Google Drive file metadata by file ID.",
        input_model=DriveGetMetadataInput,
        output_model=DriveGetMetadataOutput,
        read_only=True,
        requires_confirmation=False,
        risk=RiskLevel.READ_ONLY,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.IDEMPOTENT,
        tags=("drive", "google", "metadata"),
    )

    def __init__(self, client: Optional[DriveClient] = None) -> None:
        self._client = client

    def run(self, input_data: Any) -> ToolResult:
        if isinstance(input_data, dict):
            input_data = DriveGetMetadataInput.model_validate(input_data)
        return self.execute(input_data)

    def execute(self, validated_input: DriveGetMetadataInput) -> ToolResult:
        ScopeGuard.assert_capability(self._client.account_id if self._client else "default", GoogleCapability.DRIVE_APP_FILE_READ)
        if not self._client:
            return ToolResult(success=False, error="DriveClient is not configured.", tool_name=self.definition.name)

        meta = self._client.get_metadata(validated_input.file_id)
        resource_ref = meta.to_resource_ref() if meta else None

        out = DriveGetMetadataOutput(
            metadata=meta,
            found=meta is not None,
            resource_ref=resource_ref,
        )
        return ToolResult(success=True, data=out.model_dump(mode="json"), tool_name=self.definition.name)


class DriveDownloadFileTool(Tool):
    definition = ToolDefinition(
        name="drive_download_file",
        description="Download a file or export a Google Doc from Drive to local filesystem.",
        input_model=DriveDownloadFileInput,
        output_model=DriveDownloadFileOutput,
        read_only=True,
        requires_confirmation=False,
        risk=RiskLevel.READ_ONLY,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.IDEMPOTENT,
        tags=("drive", "google", "download"),
    )

    def __init__(self, client: Optional[DriveClient] = None) -> None:
        self._client = client

    def run(self, input_data: Any) -> ToolResult:
        if isinstance(input_data, dict):
            input_data = DriveDownloadFileInput.model_validate(input_data)
        return self.execute(input_data)

    def execute(self, validated_input: DriveDownloadFileInput) -> ToolResult:
        ScopeGuard.assert_capability(self._client.account_id if self._client else "default", GoogleCapability.DRIVE_APP_FILE_READ)
        if not self._client:
            return ToolResult(success=False, error="DriveClient is not configured.", tool_name=self.definition.name)

        dest_path = self._client.download_file(
            file_id=validated_input.file_id,
            destination_path=validated_input.destination_path,
            export_mime_type=validated_input.export_mime_type,
            overwrite=validated_input.overwrite,
        )

        ver = DriveVerifier.verify_download(
            local_path=dest_path,
            expected_file_id=validated_input.file_id,
        )

        size_bytes = ver.evidence.get("size_bytes", 0) if ver.evidence else 0

        out = DriveDownloadFileOutput(
            local_path=dest_path,
            file_id=validated_input.file_id,
            downloaded=ver.verified,
            size_bytes=size_bytes,
        )
        return ToolResult(
            success=ver.verified,
            data=out.model_dump(mode="json"),
            error=ver.error if not ver.verified else None,
            evidence=ver.evidence if ver.evidence else {},
            tool_name=self.definition.name,
        )


class DriveUploadFileTool(Tool):
    definition = ToolDefinition(
        name="drive_upload_file",
        description="Upload a local file to Google Drive. Requires Phase 5 policy confirmation.",
        input_model=DriveUploadFileInput,
        output_model=DriveUploadFileOutput,
        read_only=False,
        requires_confirmation=True,
        risk=RiskLevel.EXTERNAL_EFFECT,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.VERIFY_BEFORE_RETRY,
        tags=("drive", "google", "upload"),
    )

    def __init__(self, client: Optional[DriveClient] = None) -> None:
        self._client = client

    def human_confirmation_prompt(self, validated_input: DriveUploadFileInput) -> str:
        src = Path(validated_input.local_path).name
        target = validated_input.target_filename or src
        folder_msg = f" to folder '{validated_input.destination_folder_id}'" if validated_input.destination_folder_id else ""
        return f"Upload '{src}' as '{target}'{folder_msg} on Google Drive?"

    def run(self, input_data: Any) -> ToolResult:
        if isinstance(input_data, dict):
            input_data = DriveUploadFileInput.model_validate(input_data)
        return self.execute(input_data)

    def execute(self, validated_input: DriveUploadFileInput) -> ToolResult:
        ScopeGuard.assert_capability(self._client.account_id if self._client else "default", GoogleCapability.DRIVE_APP_FILE_WRITE)
        if not self._client:
            return ToolResult(success=False, error="DriveClient is not configured.", tool_name=self.definition.name)

        src = Path(validated_input.local_path)
        if not src.exists():
            return ToolResult(success=False, error=f"Local file does not exist: {src}", tool_name=self.definition.name)

        target_name = validated_input.target_filename or src.name
        file_meta = self._client.upload_file(
            local_path=str(src),
            filename=target_name,
            folder_id=validated_input.destination_folder_id,
        )

        ver = DriveVerifier.verify_upload(
            client=self._client,
            file_id=file_meta.file_id,
            expected_name=target_name,
            expected_folder=validated_input.destination_folder_id,
        )

        out = DriveUploadFileOutput(
            uploaded=ver.verified,
            file=file_meta,
            resource_ref=file_meta.to_resource_ref(),
        )
        return ToolResult(
            success=ver.verified,
            data=out.model_dump(mode="json"),
            error=ver.error if not ver.verified else None,
            evidence=ver.evidence if ver.evidence else {},
            tool_name=self.definition.name,
        )


class DriveCreateFolderTool(Tool):
    definition = ToolDefinition(
        name="drive_create_folder",
        description="Create a new folder in Google Drive. Requires Phase 5 policy confirmation.",
        input_model=DriveCreateFolderInput,
        output_model=DriveCreateFolderOutput,
        read_only=False,
        requires_confirmation=True,
        risk=RiskLevel.EXTERNAL_EFFECT,
        execution_method=ExecutionMethod.API,
        idempotency=IdempotencyClass.VERIFY_BEFORE_RETRY,
        tags=("drive", "google", "folder", "create"),
    )

    def __init__(self, client: Optional[DriveClient] = None) -> None:
        self._client = client

    def human_confirmation_prompt(self, validated_input: DriveCreateFolderInput) -> str:
        parent_msg = f" inside folder '{validated_input.parent_folder_id}'" if validated_input.parent_folder_id else ""
        return f"Create folder '{validated_input.folder_name}'{parent_msg} on Google Drive?"

    def run(self, input_data: Any) -> ToolResult:
        if isinstance(input_data, dict):
            input_data = DriveCreateFolderInput.model_validate(input_data)
        return self.execute(input_data)

    def execute(self, validated_input: DriveCreateFolderInput) -> ToolResult:
        ScopeGuard.assert_capability(self._client.account_id if self._client else "default", GoogleCapability.DRIVE_APP_FILE_WRITE)
        if not self._client:
            return ToolResult(success=False, error="DriveClient is not configured.", tool_name=self.definition.name)

        folder_meta = self._client.create_folder(
            folder_name=validated_input.folder_name,
            parent_id=validated_input.parent_folder_id,
        )

        ver = DriveVerifier.verify_folder_create(
            client=self._client,
            folder_id=folder_meta.file_id,
            expected_name=validated_input.folder_name,
        )

        out = DriveCreateFolderOutput(
            created=ver.verified,
            folder=folder_meta,
        )
        return ToolResult(
            success=ver.verified,
            data=out.model_dump(mode="json"),
            error=ver.error if not ver.verified else None,
            evidence=ver.evidence if ver.evidence else {},
            tool_name=self.definition.name,
        )
