"""Read-Only Visual Debug Inspector for Screen Grounding."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import time
from typing import Optional

from jarvis.core.vision.capture import ScreenCaptureProvider
from jarvis.core.vision.manager import VisionManager
from jarvis.core.vision.parsers.simple_regions import SimpleRegionsParser
from jarvis.core.vision.preprocessing import annotate_candidates_on_image
from jarvis.core.vision.providers.fake import FakeVisionProvider

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def run_vision_debug(
    window_id: Optional[str] = None,
    capture: bool = True,
    detect: bool = True,
    ground_goal: Optional[str] = None,
    save_debug: Optional[str] = None,
) -> None:
    print("=" * 64)
    print("         JARVIS EDGE -- Vision Debug Inspector")
    print("=" * 64)

    cap_provider = ScreenCaptureProvider()
    mgr = VisionManager(capture_provider=cap_provider)

    target_win = window_id or "0"
    print(f"Target Window:        {target_win}")

    # 1. Capture on demand
    t0 = time.perf_counter_ns()
    obs, img, perf_meta = mgr.observe(
        window_id=target_win,
        window_title="Debug Window",
    )
    obs_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

    print(f"Capture Dimensions:   {obs.image_width}x{obs.image_height}")
    print(f"DPI Scaling Factor:   {obs.dpi_scale}x")
    print(f"Capture Latency:      {perf_meta.get('capture_ms', 0.0):.2f} ms")
    print(f"Parser Latency:       {perf_meta.get('parser_ms', 0.0):.2f} ms")
    print(f"Total Observe Time:   {obs_ms:.2f} ms")
    print(f"Candidates Detected:  {len(obs.candidates)}")

    if detect and obs.candidates:
        print("\nInteractive Candidate Elements:")
        for c in obs.candidates[:15]:
            desc = f" '{c.visible_text}'" if c.visible_text else ""
            print(f"  - [{c.candidate_id}] {c.candidate_type}{desc} @ {c.bbox_pixels} (conf: {c.detector_confidence:.2f})")
        if len(obs.candidates) > 15:
            print(f"  ... and {len(obs.candidates) - 15} more candidates.")

    # 2. Grounding if requested
    if ground_goal:
        print(f"\nGrounding Goal:       '{ground_goal}'")
        decision, passes = mgr.grounder.ground_target(
            goal=ground_goal,
            image=img,
            candidates=obs.candidates,
        )
        print(f"Grounding Match:      {decision.match}")
        print(f"Candidate Selected:   {decision.candidate_id}")
        print(f"Confidence Level:     {decision.confidence.value}")
        print(f"Reason Code:          {decision.reason_code}")
        print(f"Grounding Passes:     {passes}")

        if decision.candidate_id:
            cand = next((c for c in obs.candidates if c.candidate_id == decision.candidate_id), None)
            if cand:
                pt = mgr.input_controller.compute_physical_click_point(
                    candidate=cand,
                    window_region=obs.capture_region,
                    dpi_scale=obs.dpi_scale,
                )
                print(f"Derived OS Point:     {pt} (computed by code, zero model coordinates)")

    # 3. Explicit debug save only if requested
    if save_debug:
        out_dir = Path(save_debug)
        out_dir.mkdir(parents=True, exist_ok=True)
        annotated = annotate_candidates_on_image(img, obs.candidates)
        out_file = out_dir / f"vision_debug_{int(time.time())}.jpg"
        annotated.save(out_file, "JPEG", quality=85)
        print(f"\n[DEBUG SAVED] Annotated screenshot saved to: {out_file}")
    else:
        print("\nScreenshot Ephemeral: RAM only (0 files written to disk)")

    print("=" * 64)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-Only Vision Debug Tool")
    parser.add_argument("--window", "-w", type=str, default=None, help="Window ID to inspect")
    parser.add_argument("--capture", "-c", action="store_true", default=True, help="Capture screenshot")
    parser.add_argument("--detect", "-d", action="store_true", default=True, help="Detect candidates")
    parser.add_argument("--ground", "-g", type=str, default=None, help="Goal to ground against candidates")
    parser.add_argument("--save-debug", "-s", type=str, default=None, help="Directory to save debug screenshot")
    args = parser.parse_args()

    run_vision_debug(
        window_id=args.window,
        capture=args.capture,
        detect=args.detect,
        ground_goal=args.ground,
        save_debug=args.save_debug,
    )


if __name__ == "__main__":
    main()
