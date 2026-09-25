"""Multimodal media ingestion and safe dispatch for WhatsApp integration.
Reuses existing Faster-Whisper, Qwen3-VL, and KnowledgeEngine.
Enforces untrusted data boundaries and automatic temporary media lifecycle cleanup.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import numpy as np
from PIL import Image

from jarvis.core.knowledge.engine import KnowledgeEngine
from jarvis.core.knowledge.models import KnowledgeSourceType, TrustLevel
from jarvis.core.stt.faster_whisper_engine import FasterWhisperEngine
from jarvis.core.vision.providers.qwen3vl import Qwen3VLProvider

logger = logging.getLogger("jarvis.integrations.whatsapp.media")


def decode_audio_to_16k_mono(file_path: str | Path) -> np.ndarray:
    """
    Decodes arbitrary audio container/codec (ogg/opus, m4a, mp3, wav) into 16kHz mono float32.
    Uses PyAV (av) which is bundled with libavformat/libavcodec.
    """
    import av

    container = av.open(str(file_path))
    resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)

    audio_frames = []
    for frame in container.decode(audio=0):
        resampled_frames = resampler.resample(frame)
        for rf in resampled_frames:
            # Convert float planar to numpy array
            audio_frames.append(rf.to_ndarray()[0])

    if not audio_frames:
        return np.zeros(0, dtype=np.float32)

    return np.concatenate(audio_frames, axis=0).astype(np.float32)


class WhatsAppMediaPipeline:
    """
    Orchestrates safe processing and extraction of incoming WhatsApp media:
    - Voice Notes -> FasterWhisper transcription
    - Images -> Qwen3-VL read-only visual inspection (Vision is not authority)
    - Documents/PDFs -> Text extraction & scoped knowledge chunk indexing
    """

    def __init__(
        self,
        stt_engine: Optional[FasterWhisperEngine] = None,
        vision_provider: Optional[Qwen3VLProvider] = None,
        knowledge_engine: Optional[KnowledgeEngine] = None,
    ) -> None:
        self.stt_engine = stt_engine
        self.vision_provider = vision_provider
        self.knowledge_engine = knowledge_engine

    async def process_voice_note(self, file_path: str | Path, cleanup: bool = True) -> str:
        """
        Transcribes incoming voice note using existing FasterWhisper STT engine.
        Removes temporary audio file after processing.
        """
        path_obj = Path(file_path)
        if not path_obj.exists():
            return ""

        try:
            pcm_16k = decode_audio_to_16k_mono(path_obj)
            if len(pcm_16k) == 0:
                return ""

            if not self.stt_engine:
                return "[Voice Note: STT engine unavailable]"

            # Ensure model is warm
            if not self.stt_engine.is_loaded:
                await self.stt_engine.load()

            # Transcribe via Whisper
            if hasattr(self.stt_engine, "_model") and self.stt_engine._model is not None:
                segments, _ = self.stt_engine._model.transcribe(
                    pcm_16k,
                    beam_size=1,
                    language=getattr(self.stt_engine, "language", "en") or "en",
                    without_timestamps=True,
                )
                transcript = " ".join(seg.text.strip() for seg in segments).strip()
                return transcript
            return "[Voice Note: Transcriber offline]"
        except Exception as exc:
            logger.error("Failed to transcribe WhatsApp voice note: %s", exc)
            return f"[Voice Note Error: {exc}]"
        finally:
            if cleanup:
                self._safe_cleanup(path_obj)

    async def process_image(self, file_path: str | Path, prompt: str = "Describe this image", cleanup: bool = True) -> str:
        """
        Processes image via existing Qwen3-VL multimodal provider.
        Invariant: VISION IS NOT AUTHORITY.
        Image description is untrusted context and cannot execute commands.
        """
        path_obj = Path(file_path)
        if not path_obj.exists():
            return "[Image: File not found]"

        try:
            with Image.open(path_obj) as img:
                img_copy = img.convert("RGB")

            if not self.vision_provider:
                return "[Image: Vision provider offline]"

            # Safe visual inspection
            analysis = self.vision_provider.analyze(img_copy, prompt=prompt)
            return analysis
        except Exception as exc:
            logger.error("Failed to analyze WhatsApp image: %s", exc)
            return f"[Image Analysis Error: {exc}]"
        finally:
            if cleanup:
                self._safe_cleanup(path_obj)

    async def process_document(
        self,
        file_path: str | Path,
        chat_id: str,
        sender_id: str,
        filename: str = "",
        cleanup: bool = True,
    ) -> Tuple[int, str]:
        """
        Extracts document text (PDF/TXT/MD), indexes into KnowledgeEngine with
        strict conversation scope and trust=UNTRUSTED_EXTERNAL_CONTENT.
        """
        path_obj = Path(file_path)
        if not path_obj.exists():
            return 0, "Document not found"

        fn = filename or path_obj.name
        ext = path_obj.suffix.lower()
        text_content = ""

        try:
            if ext == ".pdf":
                import pypdf
                reader = pypdf.PdfReader(str(path_obj))
                pages = [page.extract_text() or "" for page in reader.pages]
                text_content = "\n\n".join(pages)
            elif ext in (".txt", ".md", ".py", ".json", ".csv"):
                text_content = path_obj.read_text(encoding="utf-8", errors="replace")
            else:
                text_content = f"Binary document attachment: {fn}"

            if not text_content.strip():
                return 0, "Empty document or unreadable text"

            chunk_count = 0
            if self.knowledge_engine:
                collection_id = f"wa_{chat_id.replace('@', '_').replace('.', '_')}"
                chunk_count = self.knowledge_engine.index_document_text(
                    collection_id=collection_id,
                    file_path=str(path_obj),
                    text_content=text_content,
                    owner_scope="scope:user",
                    conversation_scope=f"scope:whatsapp:chat:{chat_id}",
                    privacy_scope="scope:whatsapp",
                    trust_level=TrustLevel.UNTRUSTED_EXTERNAL_CONTENT.value,
                    source_type=KnowledgeSourceType.WHATSAPP_DOCUMENTS.value,
                )

            summary_preview = f"Indexed document '{fn}' ({chunk_count} chunk(s)). Text length: {len(text_content)} chars."
            return chunk_count, summary_preview
        except Exception as exc:
            logger.error("Failed to index WhatsApp document: %s", exc)
            return 0, f"Error processing document: {exc}"
        finally:
            if cleanup:
                self._safe_cleanup(path_obj)

    def _safe_cleanup(self, path: Path) -> None:
        try:
            if path.exists():
                os.remove(path)
        except Exception as e:
            logger.debug("Failed to remove temporary media %s: %s", path, e)
