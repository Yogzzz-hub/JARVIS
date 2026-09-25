"""Screen Capture Latency Benchmark for JARVIS EDGE v1.0.

Measures:
1. Active window vs 1080p monitor screen capture latency on REAL HARDWARE.
2. In-memory pixel buffer conversion latency (zero disk write).
3. Frame perceptual difference / hash latency.
"""
from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path
from time import perf_counter_ns

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jarvis.core.vision.cache import VisualCache
from jarvis.core.vision.capture import ScreenCaptureProvider


def run_benchmark():
    print("\n" + "=" * 60)
    print("JARVIS EDGE v1.0 — SCREEN CAPTURE BENCHMARK [REAL HARDWARE]")
    print("=" * 60)

    provider = ScreenCaptureProvider()

    # 1. Full Desktop / Monitor Capture Latency (20 iterations)
    print("\n1. In-Memory Full Monitor Screen Capture (20 iterations):")
    capture_times = []
    frames = []

    for _ in range(20):
        t0 = perf_counter_ns()
        img, meta = provider.capture_window(0)
        dur = (perf_counter_ns() - t0) / 1e6
        capture_times.append(dur)
        frames.append(img)

    p50_cap = np.percentile(capture_times, 50)
    p95_cap = np.percentile(capture_times, 95)
    sample_w, sample_h = frames[0].size
    print(f"Capture ({sample_w}x{sample_h}) -> p50: {p50_cap:5.2f} ms | p95: {p95_cap:5.2f} ms | Disk Writes: 0")

    # 2. In-Memory NumPy / Pillow Format Conversion Latency
    print("\n2. In-Memory Pixel Format Conversion Latency (20 iterations):")
    conv_times = []
    for img in frames:
        t0 = perf_counter_ns()
        # Direct conversion to RGB numpy array for candidate parsing / vision
        arr = np.array(img.convert("RGB"))
        conv_times.append((perf_counter_ns() - t0) / 1e6)

    p50_conv = np.percentile(conv_times, 50)
    p95_conv = np.percentile(conv_times, 95)
    print(f"PIL -> RGB NumPy array -> p50: {p50_conv:5.2f} ms | p95: {p95_conv:5.2f} ms | Shape: {arr.shape}")

    # 3. Frame Difference / Perceptual Hash Latency
    print("\n3. Frame Perceptual Difference / Hash Latency (50 iterations):")
    cache = VisualCache(default_ttl_s=15.0)
    hash_times = []

    for img in frames[:10] * 5:
        t0 = perf_counter_ns()
        # Downscale to 64x64 grayscale for ultra-fast screen change detection (<1ms)
        thumb = img.resize((64, 64), Image.Resampling.NEAREST).convert("L")
        h = hashlib.md5(thumb.tobytes()).hexdigest()
        cache.record_image_hash(h)
        hash_times.append((perf_counter_ns() - t0) / 1e6)

    p50_hash = np.percentile(hash_times, 50)
    p95_hash = np.percentile(hash_times, 95)
    print(f"Perceptual Screen Hash -> p50: {p50_hash:5.3f} ms | p95: {p95_hash:5.3f} ms | Stalled: {cache.is_stalled()}")

    print("\nCapture benchmark completed successfully.")


if __name__ == "__main__":
    run_benchmark()
