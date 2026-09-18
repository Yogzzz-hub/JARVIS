"""Deterministic Region and Contour Candidate Detector."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

from jarvis.core.vision.models import VisualCandidate

logger = logging.getLogger("jarvis.core.vision.parsers.simple_regions")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def compute_iou(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
    """Compute Intersection over Union between two integer pixel boxes [x1, y1, x2, y2]."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = max(0, (box1[2] - box1[0]) * (box1[3] - box1[1]))
    area2 = max(0, (box2[2] - box2[0]) * (box2[3] - box2[1]))
    union_area = area1 + area2 - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / float(union_area)


def non_max_suppression(boxes: List[Tuple[int, int, int, int]], iou_threshold: float = 0.5) -> List[Tuple[int, int, int, int]]:
    """Prune overlapping boxes."""
    if not boxes:
        return []
    # Sort primarily by area descending
    sorted_boxes = sorted(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    kept: List[Tuple[int, int, int, int]] = []
    for b in sorted_boxes:
        if not any(compute_iou(b, k) > iou_threshold for k in kept):
            kept.append(b)
    return kept


class SimpleRegionsParser:
    """Fast, deterministic edge and contour-based UI candidate detector."""

    def __init__(
        self,
        min_w: int = 12,
        min_h: int = 12,
        max_ratio: float = 0.95,
        max_candidates: int = 64,
    ) -> None:
        self.min_w = min_w
        self.min_h = min_h
        self.max_ratio = max_ratio
        self.max_candidates = max_candidates

    def detect_candidates(
        self,
        image: Image.Image,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[VisualCandidate]:
        """Detect visual candidates in the given image."""
        w, h = image.size

        # 1. Check if synthetic / manual test candidates were provided in context
        if context and "synthetic_candidates" in context:
            candidates: List[VisualCandidate] = []
            for idx, item in enumerate(context["synthetic_candidates"], start=1):
                cid = item.get("candidate_id", f"C{idx}")
                if "bbox_pixels" in item:
                    px1, py1, px2, py2 = item["bbox_pixels"]
                    b_norm = [
                        max(0.0, min(1.0, px1 / float(w))),
                        max(0.0, min(1.0, py1 / float(h))),
                        max(0.0, min(1.0, px2 / float(w))),
                        max(0.0, min(1.0, py2 / float(h))),
                    ]
                else:
                    b_norm = item.get("bbox_normalized", [0.1, 0.1, 0.2, 0.2])
                    px1 = int(round(b_norm[0] * w))
                    py1 = int(round(b_norm[1] * h))
                    px2 = int(round(b_norm[2] * w))
                    py2 = int(round(b_norm[3] * h))

                candidates.append(
                    VisualCandidate(
                        candidate_id=cid,
                        bbox_normalized=b_norm,
                        bbox_pixels=[px1, py1, px2, py2],
                        candidate_type=item.get("candidate_type", "button"),
                        detector_confidence=item.get("detector_confidence", 0.95),
                        visible_text=item.get("visible_text"),
                        icon_description=item.get("icon_description"),
                        interactive_probability=item.get("interactive_probability", 0.95),
                        source="synthetic",
                        metadata=item.get("metadata", {}),
                    )
                )
            return candidates

        raw_boxes: List[Tuple[int, int, int, int]] = []

        if HAS_CV2:
            try:
                np_img = np.array(image.convert("RGB"))
                gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
                # Blur and edge detection
                blurred = cv2.GaussianBlur(gray, (3, 3), 0)
                edges = cv2.Canny(blurred, 50, 150)
                # Find contours
                contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                for cnt in contours:
                    bx, by, bw, bh = cv2.boundingRect(cnt)
                    if bw >= self.min_w and bh >= self.min_h:
                        if bw <= w * self.max_ratio and bh <= h * self.max_ratio:
                            raw_boxes.append((bx, by, bx + bw, by + bh))
            except Exception as e:
                logger.warning(f"OpenCV region detection encountered error: {e}")

        # Fallback grid tiling if no contours detected or cv2 unavailable
        if not raw_boxes:
            # Generate coarse grid regions
            cols, rows = 4, 4
            cell_w, cell_h = w // cols, h // rows
            for r in range(rows):
                for c in range(cols):
                    raw_boxes.append((c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h))

        # Filter duplicates
        filtered = non_max_suppression(raw_boxes, iou_threshold=0.4)

        # Sort in natural reading order: top-to-bottom, left-to-right
        sorted_boxes = sorted(filtered, key=lambda b: (b[1] // 30, b[0]))[: self.max_candidates]

        candidates: List[VisualCandidate] = []
        for idx, (bx1, by1, bx2, by2) in enumerate(sorted_boxes, start=1):
            cid = f"C{idx}"
            norm_box = [
                max(0.0, min(1.0, bx1 / float(w))),
                max(0.0, min(1.0, by1 / float(h))),
                max(0.0, min(1.0, bx2 / float(w))),
                max(0.0, min(1.0, by2 / float(h))),
            ]
            candidates.append(
                VisualCandidate(
                    candidate_id=cid,
                    bbox_normalized=norm_box,
                    bbox_pixels=[bx1, by1, bx2, by2],
                    candidate_type="button",
                    detector_confidence=0.88,
                    interactive_probability=0.90,
                    source="simple_regions",
                )
            )

        return candidates
