"""Client for Google Drive API operations."""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jarvis.integrations.google.common.cache import get_connector_cache
from jarvis.integrations.google.common.errors import (
    GoogleErrorCode,
    GoogleProviderError,
    normalize_google_error,
)
from jarvis.integrations.google.common.retry import execute_with_retry
from jarvis.integrations.google.drive.models import (
    EXPORT_MAPPINGS,
    GOOGLE_DOC_MIME,
    GOOGLE_FOLDER_MIME,
    GOOGLE_SHEET_MIME,
    GOOGLE_SLIDE_MIME,
    DriveFileMetadata,
)

logger = logging.getLogger("jarvis.integrations.google.drive.client")

DRIVE_STANDARD_FIELDS = "id, name, mimeType, modifiedTime, size, parents, webViewLink"


class DriveClient:
    """Wrapper around Google Drive API v3."""

    def __init__(self, service: Any, account_id: str = "default") -> None:
        self.service = service
        self.account_id = account_id
        self._cache = get_connector_cache()

    def _normalize_metadata(self, raw: Dict[str, Any]) -> DriveFileMetadata:
        """Parse raw Drive API JSON file into typed DriveFileMetadata."""
        mime = raw.get("mimeType", "application/octet-stream")
        is_folder = mime == GOOGLE_FOLDER_MIME
        is_google_doc = mime in (GOOGLE_DOC_MIME, GOOGLE_SHEET_MIME, GOOGLE_SLIDE_MIME)
        raw_size = raw.get("size")
        size_bytes = int(raw_size) if raw_size is not None else None

        parents_val = raw.get("parents", [])
        parents = tuple(parents_val) if isinstance(parents_val, list) else ()

        return DriveFileMetadata(
            file_id=raw.get("id", ""),
            name=raw.get("name", "Untitled"),
            mime_type=mime,
            modified_time=raw.get("modifiedTime"),
            size_bytes=size_bytes,
            parents=parents,
            web_view_link=raw.get("webViewLink"),
            is_folder=is_folder,
            is_google_doc=is_google_doc,
        )

    def list_files(
        self,
        folder_id: str = "root",
        page_size: int = 20,
        page_token: Optional[str] = None,
    ) -> Tuple[List[DriveFileMetadata], Optional[str]]:
        """List files located in a specific Drive folder."""
        cache_key = f"drive:list:{self.account_id}:{folder_id}:{page_size}:{page_token}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        q = f"'{folder_id}' in parents and trashed = false"

        def _call() -> Dict[str, Any]:
            req = self.service.files().list(
                q=q,
                pageSize=min(page_size, 50),
                pageToken=page_token,
                fields=f"nextPageToken, files({DRIVE_STANDARD_FIELDS})",
                spaces="drive",
            )
            return req.execute()

        try:
            res = execute_with_retry(_call, operation_name="drive_list_files", is_write=False)
        except Exception as e:
            raise normalize_google_error(e, "drive_list_files") from e

        files = [self._normalize_metadata(f) for f in res.get("files", [])]
        next_token = res.get("nextPageToken")
        result = (files, next_token)
        self._cache.set(cache_key, result, ttl_seconds=60)
        return result

    def search(
        self,
        query: str,
        page_size: int = 20,
        page_token: Optional[str] = None,
    ) -> Tuple[List[DriveFileMetadata], Optional[str]]:
        """Search files across Drive by keyword or query filter."""
        # Sanitize query to prevent syntax errors
        clean_query = query.replace("'", "\\'")
        q_str = f"name contains '{clean_query}' and trashed = false"

        def _call() -> Dict[str, Any]:
            req = self.service.files().list(
                q=q_str,
                pageSize=min(page_size, 50),
                pageToken=page_token,
                fields=f"nextPageToken, files({DRIVE_STANDARD_FIELDS})",
                spaces="drive",
            )
            return req.execute()

        try:
            res = execute_with_retry(_call, operation_name="drive_search", is_write=False)
        except Exception as e:
            raise normalize_google_error(e, "drive_search") from e

        files = [self._normalize_metadata(f) for f in res.get("files", [])]
        next_token = res.get("nextPageToken")
        return files, next_token

    def get_metadata(self, file_id: str) -> Optional[DriveFileMetadata]:
        """Fetch metadata for a specific Drive file."""
        cache_key = f"drive:meta:{self.account_id}:{file_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        def _call() -> Dict[str, Any]:
            req = self.service.files().get(fileId=file_id, fields=DRIVE_STANDARD_FIELDS)
            return req.execute()

        try:
            res = execute_with_retry(_call, operation_name="drive_get_metadata", is_write=False)
        except GoogleProviderError as gpe:
            if gpe.code == GoogleErrorCode.NOT_FOUND:
                return None
            raise
        except Exception as e:
            err = normalize_google_error(e, "drive_get_metadata")
            if err.code == GoogleErrorCode.NOT_FOUND:
                return None
            raise err from e

        meta = self._normalize_metadata(res)
        self._cache.set(cache_key, meta, ttl_seconds=120)
        return meta

    def download_file(
        self,
        file_id: str,
        destination_path: str,
        export_mime_type: Optional[str] = None,
        overwrite: bool = False,
        max_size_mb: int = 50,
    ) -> str:
        """
        Download a file or export a Google Doc/Sheet/Slide to the local filesystem.
        Stream content in bounded chunks to protect RAM.
        """
        dest = Path(destination_path).resolve()
        if dest.exists() and not overwrite:
            raise FileExistsError(f"Destination file already exists: {dest}")

        dest.parent.mkdir(parents=True, exist_ok=True)

        meta = self.get_metadata(file_id)
        if not meta:
            raise GoogleProviderError(GoogleErrorCode.NOT_FOUND, f"File {file_id} not found on Drive.")

        if meta.is_folder:
            raise ValueError(f"Cannot download folder {file_id} directly as a file.")

        if meta.size_bytes and meta.size_bytes > max_size_mb * 1024 * 1024:
            raise ValueError(f"File size {meta.size_bytes / (1024*1024):.1f}MB exceeds limit {max_size_mb}MB.")

        # Streaming download handler
        def _download_stream() -> None:
            from googleapiclient.http import MediaIoBaseDownload

            if meta.is_google_doc:
                # Must use export_media
                target_export = export_mime_type
                if not target_export:
                    mapping = EXPORT_MAPPINGS.get(meta.mime_type, {})
                    target_export = mapping.get("default_mime", "application/pdf")
                request = self.service.files().export_media(fileId=file_id, mimeType=target_export)
            else:
                request = self.service.files().get_media(fileId=file_id)

            with open(dest, "wb") as fh:
                if hasattr(request, "uri"):
                    downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 512)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                else:
                    data = request.execute() if hasattr(request, "execute") else b""
                    if isinstance(data, (bytes, bytearray)):
                        fh.write(data)
                    else:
                        fh.write(str(data).encode("utf-8"))


        try:
            execute_with_retry(_download_stream, operation_name="drive_download_file", is_write=False)
        except Exception as e:
            if dest.exists() and dest.stat().st_size == 0:
                try:
                    dest.unlink()
                except Exception:
                    pass
            raise normalize_google_error(e, "drive_download_file") from e

        return str(dest)

    def upload_file(
        self,
        local_path: str,
        filename: Optional[str] = None,
        folder_id: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> DriveFileMetadata:
        """
        Upload local file to Google Drive.
        Uses resumable chunked upload for files > 5MB to stream without memory spikes.
        """
        src = Path(local_path).resolve()
        if not src.exists() or not src.is_file():
            raise FileNotFoundError(f"Local file does not exist: {src}")

        target_name = filename or src.name
        file_size = src.stat().st_size
        use_resumable = file_size > 5 * 1024 * 1024

        file_metadata: Dict[str, Any] = {"name": target_name}
        if folder_id:
            file_metadata["parents"] = [folder_id]

        def _call_upload() -> Dict[str, Any]:
            from googleapiclient.http import MediaFileUpload

            media = MediaFileUpload(
                str(src),
                mimetype=mime_type or "application/octet-stream",
                resumable=use_resumable,
                chunksize=1024 * 512 if use_resumable else -1,
            )
            req = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields=DRIVE_STANDARD_FIELDS,
            )
            if use_resumable:
                response = None
                while response is None:
                    status, response = req.next_chunk()
                return response
            else:
                return req.execute()

        try:
            res = execute_with_retry(_call_upload, operation_name="drive_upload_file", is_write=True)
        except Exception as e:
            raise normalize_google_error(e, "drive_upload_file") from e

        # Invalidate folder listing caches
        if folder_id:
            self._cache.invalidate_prefix(f"drive:list:{self.account_id}:{folder_id}")
        self._cache.invalidate_prefix(f"drive:list:{self.account_id}:root")

        return self._normalize_metadata(res)

    def create_folder(
        self,
        folder_name: str,
        parent_id: Optional[str] = None,
    ) -> DriveFileMetadata:
        """Create a new folder on Google Drive."""
        metadata: Dict[str, Any] = {
            "name": folder_name,
            "mimeType": GOOGLE_FOLDER_MIME,
        }
        if parent_id:
            metadata["parents"] = [parent_id]

        def _call() -> Dict[str, Any]:
            req = self.service.files().create(
                body=metadata,
                fields=DRIVE_STANDARD_FIELDS,
            )
            return req.execute()

        try:
            res = execute_with_retry(_call, operation_name="drive_create_folder", is_write=True)
        except Exception as e:
            raise normalize_google_error(e, "drive_create_folder") from e

        if parent_id:
            self._cache.invalidate_prefix(f"drive:list:{self.account_id}:{parent_id}")
        self._cache.invalidate_prefix(f"drive:list:{self.account_id}:root")

        return self._normalize_metadata(res)
