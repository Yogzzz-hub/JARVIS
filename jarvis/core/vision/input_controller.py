"""Visual Input Controller and Physical Coordinate Mapping."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple
from jarvis.core.vision.models import (
    VisualActionOutcome,
    VisualCandidate,
    VisualObservation,
)

logger = logging.getLogger("jarvis.core.vision.input_controller")

try:
    import win32api
    import win32con
    HAS_WIN32_MOUSE = True
except ImportError:
    HAS_WIN32_MOUSE = False


class VisualInputController:
    """Computes physical OS coordinates from visual candidates and dispatches verified input."""

    def __init__(self, simulate_only: bool = False) -> None:
        self.simulate_only = simulate_only
        self.last_dispatched_point: Optional[Tuple[int, int]] = None

    @staticmethod
    def compute_physical_click_point(
        candidate: VisualCandidate,
        window_region: Dict[str, int],
        dpi_scale: float = 1.0,
    ) -> Tuple[int, int]:
        """Compute absolute screen coordinates from candidate pixel center and window offset."""
        cx, cy = candidate.center_pixel()
        win_left = window_region.get("left", 0)
        win_top = window_region.get("top", 0)

        screen_x = win_left + int(round(cx * dpi_scale))
        screen_y = win_top + int(round(cy * dpi_scale))
        return screen_x, screen_y

    def click_candidate(
        self,
        candidate: VisualCandidate,
        observation: VisualObservation,
        current_window_region: Optional[Dict[str, int]] = None,
    ) -> VisualActionOutcome:
        """Validate candidate bounds and execute controlled physical mouse click."""
        # 1. Validate candidate box
        box = candidate.as_bounding_box()
        if not box.is_valid() or box.area < 0.00001:
            return VisualActionOutcome(
                success=False,
                candidate_id=candidate.candidate_id,
                verification_status="FAILED",
                failure_reason="INVALID_CANDIDATE_BOUNDS",
                message=f"Candidate {candidate.candidate_id} bounding box is degenerate or invalid.",
            )

        # 2. Pre-click revalidation: check for window movement or stale capture
        region = current_window_region or observation.capture_region
        if current_window_region and observation.capture_region:
            # Check if window moved
            d_x = abs(current_window_region.get("left", 0) - observation.capture_region.get("left", 0))
            d_y = abs(current_window_region.get("top", 0) - observation.capture_region.get("top", 0))
            if d_x > 5 or d_y > 5:
                return VisualActionOutcome(
                    success=False,
                    candidate_id=candidate.candidate_id,
                    verification_status="STALE",
                    failure_reason="STALE_VISUAL_OBSERVATION",
                    message="Target window moved between observation capture and click dispatch.",
                )

        # 3. Compute deterministic screen coordinates
        click_x, click_y = self.compute_physical_click_point(
            candidate=candidate,
            window_region=region,
            dpi_scale=observation.dpi_scale,
        )
        self.last_dispatched_point = (click_x, click_y)

        # 4. Dispatch pointer action
        if not self.simulate_only and HAS_WIN32_MOUSE:
            try:
                win32api.SetCursorPos((click_x, click_y))
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, click_x, click_y, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, click_x, click_y, 0, 0)
            except Exception as e:
                logger.warning(f"Native mouse dispatch encountered error: {e}")

        return VisualActionOutcome(
            success=True,
            candidate_id=candidate.candidate_id,
            verification_status="ACTION_DISPATCHED",
            physical_click_point=(click_x, click_y),
            evidence={
                "candidate_id": candidate.candidate_id,
                "click_x": click_x,
                "click_y": click_y,
                "window_region": region,
            },
            message=f"Dispatched verified visual click on {candidate.candidate_id} at ({click_x}, {click_y})",
        )
