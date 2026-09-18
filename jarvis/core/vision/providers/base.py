"""Base Protocol for Multimodal Vision Providers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple
from PIL import Image

from jarvis.core.vision.models import VisualCandidate, VisualGroundingDecision


class VisionProvider(Protocol):
    """Protocol for local VLM inference engines (Qwen3-VL, Fake, etc.)."""

    @property
    def is_loaded(self) -> bool:
        """Return True if model weights are loaded in memory."""
        ...

    def load(self) -> bool:
        """Load model weights into memory/VRAM on-demand."""
        ...

    def unload(self) -> None:
        """Evict model weights to release GPU VRAM/RAM."""
        ...

    def analyze(self, image: Image.Image, prompt: str) -> str:
        """Run read-only visual inspection and return text summary."""
        ...

    def ground(
        self,
        goal: str,
        candidates: List[VisualCandidate],
        image: Image.Image,
        context: Optional[Dict[str, Any]] = None,
    ) -> VisualGroundingDecision:
        """Select appropriate candidate ID from visual candidates for the given goal."""
        ...

    def verify_visual_state(
        self,
        before_image: Image.Image,
        after_image: Image.Image,
        expected_condition: str,
    ) -> Tuple[bool, str]:
        """Verify whether the expected visual state change occurred between observations."""
        ...

    def cancel(self) -> None:
        """Cancel ongoing inference."""
        ...
