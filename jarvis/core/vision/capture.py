"""Screen Capture Provider with Window-Scoped Capture and DPI Awareness."""
from __future__ import annotations

import io
import logging
import time
from typing import Any, Dict, Optional, Tuple
from PIL import Image, ImageGrab

logger = logging.getLogger("jarvis.core.vision.capture")

try:
    import win32gui
    import win32ui
    import win32con
    import win32api
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class ScreenCaptureProvider:
    """Captures on-demand window-scoped or monitor-scoped screenshots with DPI awareness."""

    def __init__(self, mock_image: Optional[Image.Image] = None) -> None:
        self.mock_image = mock_image

    def get_dpi_scale(self, hwnd: Optional[int] = None) -> float:
        """Estimate system or per-window DPI scaling factor."""
        if not HAS_WIN32:
            return 1.0
        try:
            # Per-monitor DPI if available on Windows 10/11
            import ctypes
            shcore = ctypes.windll.shcore
            if hwnd and hasattr(shcore, "GetDpiForWindow"):
                dpi = shcore.GetDpiForWindow(hwnd)
                return float(dpi) / 96.0
            hdc = win32gui.GetDC(0)
            logpixelsx = win32ui.GetDeviceCaps(hdc, win32con.LOGPIXELSX)
            win32gui.ReleaseDC(0, hdc)
            return float(logpixelsx) / 96.0
        except Exception:
            return 1.0

    def capture_window(self, hwnd: int | str) -> Tuple[Image.Image, Dict[str, Any]]:
        """Capture the target window bounding box.
        
        Prefers capturing solely the target window to reduce latency, memory,
        and privacy exposure.
        """
        t0 = time.perf_counter_ns()
        if self.mock_image is not None:
            w, h = self.mock_image.size
            metadata = {
                "window_id": str(hwnd),
                "left": 0,
                "top": 0,
                "width": w,
                "height": h,
                "dpi_scale": 1.0,
                "capture_ms": (time.perf_counter_ns() - t0) / 1_000_000.0,
            }
            return self.mock_image.copy(), metadata

        int_hwnd = int(hwnd) if isinstance(hwnd, int) or (isinstance(hwnd, str) and hwnd.isdigit()) else 0

        if HAS_WIN32 and int_hwnd and win32gui.IsWindow(int_hwnd):
            try:
                rect = win32gui.GetWindowRect(int_hwnd)
                left, top, right, bottom = rect
                width = max(1, right - left)
                height = max(1, bottom - top)
                dpi = self.get_dpi_scale(int_hwnd)

                # Capture via PIL ImageGrab with window bbox
                img = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
                metadata = {
                    "window_id": str(hwnd),
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height,
                    "dpi_scale": dpi,
                    "capture_ms": (time.perf_counter_ns() - t0) / 1_000_000.0,
                }
                return img, metadata
            except Exception as e:
                logger.warning(f"Window capture via win32 failed ({e}), falling back to desktop grab.")

        # Fallback to full screen or primary display
        try:
            img = ImageGrab.grab(all_screens=False)
        except Exception:
            try:
                import mss
                with mss.mss() as sct:
                    f = sct.grab(sct.monitors[0])
                    img = Image.frombytes("RGB", f.size, f.bgra, "raw", "BGRX")
            except Exception:
                img = Image.new("RGB", (1920, 1080), color=(24, 24, 27))

        w, h = img.size
        metadata = {
            "window_id": str(hwnd),
            "left": 0,
            "top": 0,
            "width": w,
            "height": h,
            "dpi_scale": 1.0,
            "capture_ms": (time.perf_counter_ns() - t0) / 1_000_000.0,
        }
        return img, metadata

    def capture_screen(self, monitor_id: Optional[int] = None) -> Tuple[Image.Image, Dict[str, Any]]:
        """Capture entire desktop across multi-monitor setup."""
        t0 = time.perf_counter_ns()
        if self.mock_image is not None:
            w, h = self.mock_image.size
            return self.mock_image.copy(), {
                "left": 0,
                "top": 0,
                "width": w,
                "height": h,
                "dpi_scale": 1.0,
                "capture_ms": (time.perf_counter_ns() - t0) / 1_000_000.0,
            }

        img = ImageGrab.grab(all_screens=True)
        w, h = img.size
        metadata = {
            "left": 0,
            "top": 0,
            "width": w,
            "height": h,
            "dpi_scale": self.get_dpi_scale(),
            "capture_ms": (time.perf_counter_ns() - t0) / 1_000_000.0,
        }
        return img, metadata
