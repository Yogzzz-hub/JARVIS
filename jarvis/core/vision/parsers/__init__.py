"""Visual Candidate Detectors and Parsers."""
from __future__ import annotations

from jarvis.core.vision.parsers.base import VisualParser
from jarvis.core.vision.parsers.simple_regions import SimpleRegionsParser
from jarvis.core.vision.parsers.omniparser import OmniParserAdapter

__all__ = ["VisualParser", "SimpleRegionsParser", "OmniParserAdapter"]
