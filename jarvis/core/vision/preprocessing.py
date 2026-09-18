"""Image Preprocessing, Adaptive Resizing, and Candidate ID Annotation."""
from __future__ import annotations

import base64
import io
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFont
from jarvis.core.vision.models import VisualCandidate


def resize_to_target_long_edge(image: Image.Image, max_long_edge: int = 1024) -> Tuple[Image.Image, float]:
    """Resize image so its longest dimension does not exceed max_long_edge.
    
    Returns:
        (resized_image, scale_factor)
    """
    w, h = image.size
    long_edge = max(w, h)
    if long_edge <= max_long_edge:
        return image.copy(), 1.0

    scale = max_long_edge / float(long_edge)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return resized, scale


def annotate_candidates_on_image(
    image: Image.Image,
    candidates: List[VisualCandidate],
    box_color: str = "#FF0055",
    text_color: str = "#FFFFFF",
    badge_bg: str = "#000000",
) -> Image.Image:
    """Draw high-contrast bounding boxes and candidate ID badges (C1, C2...) on the image."""
    annotated = image.copy().convert("RGB")
    draw = ImageDraw.Draw(annotated)
    w, h = annotated.size

    for c in candidates:
        bx1, by1, bx2, by2 = c.bbox_pixels
        # Clamp to bounds
        bx1 = max(0, min(w - 1, bx1))
        by1 = max(0, min(h - 1, by1))
        bx2 = max(bx1 + 1, min(w, bx2))
        by2 = max(by1 + 1, min(h, by2))

        # Draw outer rectangle
        draw.rectangle([bx1, by1, bx2, by2], outline=box_color, width=2)

        # Draw badge label
        label = c.candidate_id
        badge_w = len(label) * 8 + 6
        badge_h = 16
        badge_x1 = bx1
        badge_y1 = max(0, by1 - badge_h)
        badge_x2 = min(w, badge_x1 + badge_w)
        badge_y2 = badge_y1 + badge_h

        draw.rectangle([badge_x1, badge_y1, badge_x2, badge_y2], fill=badge_bg)
        draw.text((badge_x1 + 3, badge_y1 + 1), label, fill=text_color)

    return annotated


def encode_image_to_base64(image: Image.Image, format: str = "JPEG", quality: int = 85) -> str:
    """Encode PIL image to base64 string for VLM payload."""
    buffered = io.BytesIO()
    rgb_img = image.convert("RGB") if format.upper() == "JPEG" else image
    rgb_img.save(buffered, format=format, quality=quality)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def encode_image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """Encode PIL image to bytes."""
    buffered = io.BytesIO()
    image.save(buffered, format=format)
    return buffered.getvalue()
