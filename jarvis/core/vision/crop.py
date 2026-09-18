"""Image Cropping and Adaptive Zoom Crop Pass."""
from __future__ import annotations

from typing import Tuple
from PIL import Image
from jarvis.core.vision.models import BoundingBox


class ImageCropManager:
    """Manages window cropping and adaptive zoom-crop passes with coordinate re-projection."""

    @staticmethod
    def crop_normalized(image: Image.Image, bbox: BoundingBox) -> Tuple[Image.Image, Tuple[int, int]]:
        """Crop an image using normalized bounding box coordinates.
        
        Returns:
            (cropped_image, (offset_x_pixels, offset_y_pixels))
        """
        w, h = image.size
        x1, y1, x2, y2 = bbox.to_pixels(w, h)
        x1 = max(0, min(w - 1, x1))
        y1 = max(0, min(h - 1, y1))
        x2 = max(x1 + 1, min(w, x2))
        y2 = max(y1 + 1, min(h, y2))
        cropped = image.crop((x1, y1, x2, y2))
        return cropped, (x1, y1)

    @staticmethod
    def adaptive_zoom_crop(
        image: Image.Image,
        suspected_box: BoundingBox,
        padding_ratio: float = 0.25,
    ) -> Tuple[Image.Image, BoundingBox, Tuple[int, int]]:
        """Extract an expanded high-resolution sub-region around a candidate box.
        
        Returns:
            (cropped_image, crop_bounds_normalized, (offset_x_pixels, offset_y_pixels))
        """
        bw = suspected_box.width
        bh = suspected_box.height
        pad_x = max(0.05, bw * padding_ratio)
        pad_y = max(0.05, bh * padding_ratio)

        cx1 = max(0.0, suspected_box.x1 - pad_x)
        cy1 = max(0.0, suspected_box.y1 - pad_y)
        cx2 = min(1.0, suspected_box.x2 + pad_x)
        cy2 = min(1.0, suspected_box.y2 + pad_y)

        crop_box = BoundingBox(x1=cx1, y1=cy1, x2=cx2, y2=cy2)
        cropped, offset = ImageCropManager.crop_normalized(image, crop_box)
        return cropped, crop_box, offset

    @staticmethod
    def map_cropped_to_parent(local_box: BoundingBox, crop_box_norm: BoundingBox) -> BoundingBox:
        """Project a bounding box discovered inside a cropped image back to parent normalized coordinates."""
        cw = crop_box_norm.width
        ch = crop_box_norm.height

        px1 = crop_box_norm.x1 + (local_box.x1 * cw)
        py1 = crop_box_norm.y1 + (local_box.y1 * ch)
        px2 = crop_box_norm.x1 + (local_box.x2 * cw)
        py2 = crop_box_norm.y1 + (local_box.y2 * ch)

        return BoundingBox(
            x1=max(0.0, min(1.0, px1)),
            y1=max(0.0, min(1.0, py1)),
            x2=max(0.0, min(1.0, px2)),
            y2=max(0.0, min(1.0, py2)),
        )
