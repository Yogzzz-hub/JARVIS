"""Base Protocol for Visual Candidate Parsers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol
from PIL import Image
from jarvis.core.vision.models import VisualCandidate


class VisualParser(Protocol):
    """Protocol for detecting interactive visual UI candidates from images."""

    def detect_candidates(
        self,
        image: Image.Image,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[VisualCandidate]:
        """Analyze image and return list of interactive candidate elements."""
        ...
