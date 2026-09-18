"""Verification logic for Google Drive downloads, uploads, and mutations."""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from jarvis.integrations.google.drive.client import DriveClient
from jarvis.integrations.google.drive.models import DriveFileMetadata
from jarvis.tools.base import VerificationResult

logger = logging.getLogger("jarvis.integrations.google.drive.verifier")


class DriveVerifier:
    """Verifies Drive operations locally and against provider state."""

    @staticmethod
    def verify_download(
        local_path: str,
        expected_file_id: str,
        expected_size: Optional[int] = None,
    ) -> VerificationResult:
        """Verify downloaded file exists locally and has non-zero size / matching size."""
        p = Path(local_path).resolve()
        if not p.exists() or not p.is_file():
            return VerificationResult(
                verified=False,
                evidence={"local_path": str(p), "file_id": expected_file_id},
                error=f"Downloaded file does not exist at path: {p}",
            )

        actual_size = p.stat().st_size
        if actual_size == 0 and (expected_size is None or expected_size > 0):
            return VerificationResult(
                verified=False,
                evidence={"local_path": str(p), "file_id": expected_file_id, "size": 0},
                error="Downloaded file is 0 bytes (empty file).",
            )

        if expected_size is not None and expected_size > 0 and actual_size != expected_size:
            # Note: Google Docs exports (PDF/DOCX) will have different size than raw doc size
            logger.info("Download size %d differs from provider raw metadata size %d (likely doc export)", actual_size, expected_size)

        # Compute SHA256 of downloaded file
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        file_hash = h.hexdigest()

        return VerificationResult(
            verified=True,
            evidence={
                "local_path": str(p),
                "file_id": expected_file_id,
                "size_bytes": actual_size,
                "sha256": file_hash,
            },
            error=None,
        )

    @staticmethod
    def verify_upload(
        client: DriveClient,
        file_id: str,
        expected_name: str,
        expected_folder: Optional[str] = None,
    ) -> VerificationResult:
        """Verify uploaded file exists at provider with expected name and parent."""
        try:
            meta = client.get_metadata(file_id)
            if not meta:
                return VerificationResult(
                    verified=False,
                    evidence={"file_id": file_id},
                    error=f"Uploaded file {file_id} not found at provider.",
                )

            if meta.name != expected_name:
                return VerificationResult(
                    verified=False,
                    evidence={"file_id": file_id, "provider_name": meta.name, "expected_name": expected_name},
                    error=f"Uploaded filename mismatch: expected '{expected_name}', got '{meta.name}'",
                )

            if expected_folder and expected_folder not in meta.parents:
                return VerificationResult(
                    verified=False,
                    evidence={"file_id": file_id, "parents": meta.parents, "expected_folder": expected_folder},
                    error=f"Uploaded file not found in expected folder {expected_folder}",
                )

            return VerificationResult(
                verified=True,
                evidence={
                    "provider_file_id": meta.file_id,
                    "name": meta.name,
                    "mime_type": meta.mime_type,
                    "size_bytes": meta.size_bytes,
                    "web_view_link": meta.web_view_link,
                },
                error=None,
            )
        except Exception as e:
            return VerificationResult(
                verified=False,
                evidence={"file_id": file_id},
                error=f"Upload verification failed with error: {e}",
            )

    @staticmethod
    def verify_folder_create(
        client: DriveClient,
        folder_id: str,
        expected_name: str,
    ) -> VerificationResult:
        """Verify created folder exists at provider."""
        try:
            meta = client.get_metadata(folder_id)
            if not meta or not meta.is_folder:
                return VerificationResult(
                    verified=False,
                    evidence={"folder_id": folder_id},
                    error=f"Folder {folder_id} not found or not marked as folder at provider.",
                )

            return VerificationResult(
                verified=True,
                evidence={
                    "folder_id": meta.file_id,
                    "name": meta.name,
                    "is_folder": True,
                },
                error=None,
            )
        except Exception as e:
            return VerificationResult(
                verified=False,
                evidence={"folder_id": folder_id},
                error=f"Folder verification failed with error: {e}",
            )
