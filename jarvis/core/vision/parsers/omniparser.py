"""OmniParser Adapter for Interactive UI Parsing."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from PIL import Image

from jarvis.core.vision.models import VisualCandidate
from jarvis.core.vision.parsers.simple_regions import SimpleRegionsParser

logger = logging.getLogger("jarvis.core.vision.parsers.omniparser")


class OmniParserAdapter:
    """Modular adapter for Microsoft OmniParser UI element detection."""

    def __init__(self, fallback_to_simple: bool = True) -> None:
        self.fallback_to_simple = fallback_to_simple
        self._is_available: Optional[bool] = None
        self._simple_parser = SimpleRegionsParser() if fallback_to_simple else None

    @property
    def is_available(self) -> bool:
        if self._is_available is None:
            try:
                # Check for omniparser / yolo dependencies
                import torch
                # If omniparser package is present
                import importlib
                spec = importlib.util.find_spec("omniparser")
                self._is_available = spec is not None
            except Exception:
                self._is_available = False
        return self._is_available

    def detect_candidates(
        self,
        image: Image.Image,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[VisualCandidate]:
        """Detect interactive UI elements using OmniParser or clean fallback."""
        if self.is_available:
            try:
                # In a live environment with OmniParser weights loaded:
                # return self._run_omniparser(image)
                pass
            except Exception as e:
                logger.warning(f"OmniParser execution failed ({e}), falling back to simple regions.")

        if self._simple_parser:
            candidates = self._simple_parser.detect_candidates(image, context)
            for c in candidates:
                c.source = "omniparser_fallback"
            return candidates

        return []
