"""Vision Manager: Orchestrates On-Demand Screen Grounding, Policy, and Verification."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

from jarvis.core.computer.models import TargetConfidence, UIElement, VisionRequiredResult
from jarvis.core.vision.cache import VisualCache
from jarvis.core.vision.capture import ScreenCaptureProvider
from jarvis.core.vision.crop import ImageCropManager
from jarvis.core.vision.grounding import VisionGrounder
from jarvis.core.vision.input_controller import VisualInputController
from jarvis.core.vision.models import (
    GroundingConfidence,
    VisionStatus,
    VisualActionOutcome,
    VisualCandidate,
    VisualGroundingDecision,
    VisualObservation,
)
from jarvis.core.vision.parsers.base import VisualParser
from jarvis.core.vision.parsers.simple_regions import SimpleRegionsParser
from jarvis.core.vision.preprocessing import encode_image_to_bytes, resize_to_target_long_edge
from jarvis.core.vision.privacy import evaluate_visual_observation_privacy
from jarvis.core.vision.providers.base import VisionProvider
from jarvis.core.vision.providers.fake import FakeVisionProvider
from jarvis.core.vision.resolver import VisualTargetResolver
from jarvis.core.vision.verifier import VisualVerifier

logger = logging.getLogger("jarvis.core.vision.manager")


class VisionManager:
    """Orchestrates on-demand screen capture, candidate-first visual grounding, and verified interaction."""

    def __init__(
        self,
        provider: Optional[VisionProvider] = None,
        parser: Optional[VisualParser] = None,
        capture_provider: Optional[ScreenCaptureProvider] = None,
        max_steps: int = 8,
    ) -> None:
        self.provider = provider or FakeVisionProvider()
        self.parser = parser or SimpleRegionsParser()
        self.capture_provider = capture_provider or ScreenCaptureProvider()
        self.grounder = VisionGrounder(self.provider, max_passes=2)
        self.input_controller = VisualInputController(simulate_only=False)
        self.verifier = VisualVerifier(self.provider)
        self.cache = VisualCache(default_ttl_s=15.0)
        self.max_steps = min(max_steps, 8)  # Strictly bounded to max 8 vision steps
        self.step_count = 0
        self.generation = 1

    def observe(
        self,
        window_id: int | str,
        application: str = "",
        window_title: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[VisualObservation, Image.Image, Dict[str, Any]]:
        """Capture on-demand window-scoped screenshot and extract candidate visual elements."""
        t0 = time.perf_counter_ns()
        img, cap_meta = self.capture_provider.capture_window(window_id)

        # Invalidate cache if window bounds shifted
        win_bounds = (
            cap_meta.get("left", 0),
            cap_meta.get("top", 0),
            cap_meta.get("width", 0),
            cap_meta.get("height", 0),
        )
        self.cache.notify_window_bounds(win_bounds)

        # Detect visual candidates
        t_p0 = time.perf_counter_ns()
        candidates = self.parser.detect_candidates(img, context=context)
        parser_ms = (time.perf_counter_ns() - t_p0) / 1_000_000.0

        w, h = img.size
        obs = VisualObservation(
            observation_id=f"vis_obs_{int(time.time()*1000)}",
            window_id=str(window_id),
            application=application,
            window_title=window_title,
            capture_region=cap_meta,
            image_width=w,
            image_height=h,
            dpi_scale=cap_meta.get("dpi_scale", 1.0),
            generation=self.generation,
            candidates=candidates,
        )
        obs_bytes = encode_image_to_bytes(img)
        obs.compute_image_hash(obs_bytes)
        self.cache.record_image_hash(obs.image_hash)

        # Run automatic visual privacy and prompt injection quarantine scan
        text_corpus = f"{window_title} " + " ".join(c.visible_text or "" for c in candidates)
        evaluate_visual_observation_privacy(observation=obs, visible_text_corpus=text_corpus)

        perf_meta = {
            "capture_ms": cap_meta.get("capture_ms", 0.0),
            "parser_ms": parser_ms,
            "total_observe_ms": (time.perf_counter_ns() - t0) / 1_000_000.0,
        }
        return obs, img, perf_meta

    def ground_and_execute(
        self,
        goal: str,
        window_id: int | str,
        application: str = "",
        window_title: str = "",
        structured_anchors: Optional[List[UIElement]] = None,
        context: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> VisualActionOutcome:
        """Complete visual grounding pipeline: observe -> privacy gate -> ground -> validate -> act -> verify."""
        t_start = time.perf_counter_ns()
        self.step_count += 1
        if self.step_count > self.max_steps:
            return VisualActionOutcome(
                success=False,
                verification_status="FAILED",
                failure_reason="STEP_LIMIT_EXCEEDED",
                message=f"Maximum vision interaction steps ({self.max_steps}) exceeded.",
            )

        # 1. Capture on-demand observation
        obs, img, perf_meta = self.observe(
            window_id=window_id,
            application=application,
            window_title=window_title,
            context=context,
        )

        # 2. Check privacy and prompt-injection gate
        allowed, sec_code, notes = evaluate_visual_observation_privacy(
            observation=obs,
            visible_text_corpus=f"{window_title} " + " ".join(c.visible_text or "" for c in obs.candidates),
        )
        if not allowed:
            return VisualActionOutcome(
                success=False,
                verification_status=sec_code,
                failure_reason=sec_code,
                message=notes[0] if notes else "Action blocked by visual privacy/security policy.",
                evidence={"quarantine_notes": notes},
            )

        # 3. Check for stalled loop
        if self.cache.is_stalled(threshold=3):
            return VisualActionOutcome(
                success=False,
                verification_status="FAILED",
                failure_reason="INTERACTION_STALLED",
                message="Visual state unchanged after 3 consecutive actions.",
            )

        # 4. Read-only query fast-paths (e.g. "What is on my screen?")
        goal_lower = goal.lower()
        if "what is on my screen" in goal_lower or "describe screen" in goal_lower:
            analysis = self.provider.analyze(img, prompt="Summarize what is visible on this screen.")
            return VisualActionOutcome(
                success=True,
                verification_status="VERIFIED",
                evidence={"analysis": analysis, "candidates_count": len(obs.candidates)},
                message=analysis,
            )

        # 5. Visual Grounding Pass
        t_g0 = time.perf_counter_ns()
        decision, passes = self.grounder.ground_target(
            goal=goal,
            image=img,
            candidates=obs.candidates,
            context=context,
        )
        ground_ms = (time.perf_counter_ns() - t_g0) / 1_000_000.0

        # Handle Read-only "where is..." mode
        if "where is" in goal_lower:
            if decision.match and decision.candidate_id:
                cand = next((c for c in obs.candidates if c.candidate_id == decision.candidate_id), None)
                loc_desc = f"Located at normalized bounds {cand.bbox_normalized}" if cand else "Found"
                return VisualActionOutcome(
                    success=True,
                    candidate_id=decision.candidate_id,
                    verification_status="VERIFIED",
                    evidence={"candidate": cand.model_dump() if cand else {}, "read_only": True},
                    message=f"Target '{goal}' identified at {decision.candidate_id} ({loc_desc}). Zero clicks executed.",
                )
            return VisualActionOutcome(
                success=False,
                verification_status="FAILED",
                failure_reason="TARGET_NOT_FOUND",
                message=f"Could not visually locate target for '{goal}'.",
            )

        if not decision.match or not decision.candidate_id:
            status = "AMBIGUOUS" if decision.confidence == GroundingConfidence.AMBIGUOUS else "FAILED"
            return VisualActionOutcome(
                success=False,
                verification_status=status,
                failure_reason=decision.reason_code or "NO_MATCH",
                message=decision.clarification_prompt or f"Target could not be matched reliably ({decision.reason_code}).",
            )

        target_candidate = next((c for c in obs.candidates if c.candidate_id == decision.candidate_id), None)
        if not target_candidate:
            return VisualActionOutcome(
                success=False,
                verification_status="FAILED",
                failure_reason="UNKNOWN_CANDIDATE",
                message=f"Model returned non-existent candidate ID '{decision.candidate_id}'.",
            )

        # 6. Cross-check with Phase-10 Structured Anchors
        if structured_anchors:
            structured_match = VisualTargetResolver.cross_check_with_structured_ui(
                candidate=target_candidate,
                structured_elements=structured_anchors,
            )
            if structured_match:
                logger.info(f"Target resolved to structured UIA control '{structured_match.name}'. Preferring structured target.")

        # 7. Ambiguity check
        final_conf = VisualTargetResolver.fuse_confidence(
            decision=decision,
            candidate=target_candidate,
            has_anchor_support=structured_anchors is not None and len(structured_anchors) > 0,
        )
        if final_conf == GroundingConfidence.AMBIGUOUS:
            return VisualActionOutcome(
                success=False,
                candidate_id=target_candidate.candidate_id,
                verification_status="AMBIGUOUS",
                failure_reason="AMBIGUOUS_VISUAL_TARGET",
                message=f"Multiple ambiguous visual candidates matching '{goal}'. Refusing blind click.",
            )

        # 8. Dry-run Mode
        if dry_run:
            pt = VisualInputController.compute_physical_click_point(
                target_candidate,
                obs.capture_region,
                obs.dpi_scale,
            )
            return VisualActionOutcome(
                success=True,
                candidate_id=target_candidate.candidate_id,
                verification_status="DRY_RUN",
                physical_click_point=pt,
                evidence={"candidate": target_candidate.model_dump(), "decision": decision.model_dump()},
                message=f"[DRY RUN] Would click {target_candidate.candidate_id} at {pt}. Zero actions executed.",
            )

        # 9. Controlled Physical Input Dispatch
        action_outcome = self.input_controller.click_candidate(
            candidate=target_candidate,
            observation=obs,
        )
        if not action_outcome.success:
            return action_outcome

        # 10. Postcondition Observation & Verification
        self.generation += 1
        time.sleep(0.05)  # Bounded settling delay for UI render
        post_obs, post_img, _ = self.observe(
            window_id=window_id,
            application=application,
            window_title=window_title,
            context=context,
        )

        ok, verif_status, verif_evidence = self.verifier.verify_transition(
            before_image=img,
            after_image=post_img,
            before_obs=obs,
            after_obs=post_obs,
            expected_condition=context.get("expected_condition", "state_change") if context else "state_change",
        )

        action_outcome.success = ok
        action_outcome.verification_status = verif_status
        action_outcome.evidence.update(verif_evidence)
        if not ok:
            action_outcome.failure_reason = "POSTCONDITION_VERIFICATION_FAILED"
            action_outcome.message = f"Visual click executed, but postcondition verification failed: {verif_status}"

        return action_outcome
