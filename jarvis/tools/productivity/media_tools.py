from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from pydantic import Field
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition


class ExtractAudioInput(Contract):
    video_path: str = Field(min_length=1, max_length=4096)
    output_audio_path: str | None = None


class ExtractAudioOutput(Contract):
    output_path: str
    format: str
    status: str


class TrimClipInput(Contract):
    media_path: str = Field(min_length=1, max_length=4096)
    start_time: str = Field(min_length=1, max_length=16)  # e.g., "00:01:30"
    duration: str = Field(min_length=1, max_length=16)    # e.g., "00:00:45"
    output_path: str | None = None


class TrimClipOutput(Contract):
    output_path: str
    duration: str
    status: str


class ExtractAudioTool(Tool):
    definition = ToolDefinition(
        name="extract_audio",
        description="Extracts audio track from a video file into an MP3/WAV file using FFmpeg.",
        input_model=ExtractAudioInput,
        output_model=ExtractAudioOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=60.0,
        tags=("media", "ffmpeg", "f13"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: ExtractAudioInput) -> dict[str, Any]:
        p = Path(arguments.video_path)
        if not p.exists():
            raise FileNotFoundError(f"Video file '{arguments.video_path}' not found.")

        ffmpeg = shutil.which("ffmpeg")
        out_path = Path(arguments.output_audio_path or p.with_suffix(".mp3"))

        if ffmpeg:
            cmd = [ffmpeg, "-y", "-i", str(p), "-vn", "-acodec", "libmp3lame", "-q:a", "2", "--", str(out_path)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg error: {proc.stderr[:200]}")
            status = "completed"
        else:
            status = "ffmpeg_missing_simulated"

        return {
            "output_path": str(out_path),
            "format": out_path.suffix.lstrip("."),
            "status": status,
        }


class TrimClipTool(Tool):
    definition = ToolDefinition(
        name="trim_media_clip",
        description="Trims a section of video or audio given start timestamp and duration using FFmpeg templates.",
        input_model=TrimClipInput,
        output_model=TrimClipOutput,
        read_only=False,
        risk=RiskLevel.REVERSIBLE,
        timeout_s=60.0,
        tags=("media", "ffmpeg", "f13"),
        execution_method=ExecutionMethod.CLI,
    )

    def run(self, arguments: TrimClipInput) -> dict[str, Any]:
        p = Path(arguments.media_path)
        if not p.exists():
            raise FileNotFoundError(f"Media file '{arguments.media_path}' not found.")

        ffmpeg = shutil.which("ffmpeg")
        out_path = Path(arguments.output_path or (p.parent / f"{p.stem}_trimmed{p.suffix}"))

        if ffmpeg:
            cmd = [
                ffmpeg, "-y", "-ss", arguments.start_time, "-i", str(p),
                "-t", arguments.duration, "-c", "copy", "--", str(out_path)
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg error: {proc.stderr[:200]}")
            status = "completed"
        else:
            status = "ffmpeg_missing_simulated"

        return {
            "output_path": str(out_path),
            "duration": arguments.duration,
            "status": status,
        }
