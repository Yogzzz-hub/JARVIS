"""Typed Playwright Browser Action Handlers."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional
from playwright.async_api import Page
from jarvis.core.computer.models import BrowserFailureReason, InteractionOutcome, TargetConfidence
from jarvis.core.computer.browser.locator import BrowserLocatorResolver

logger = logging.getLogger("jarvis.computer.browser.actions")


class BrowserActionRunner:
    """Executes structured Playwright interactions with auto-wait and ambiguity checks."""

    @classmethod
    async def click(
        cls,
        page: Page,
        role: Optional[str] = None,
        name: Optional[str] = None,
        text: Optional[str] = None,
        label: Optional[str] = None,
        test_id: Optional[str] = None,
    ) -> InteractionOutcome:
        """Click a semantic element with strict resolution."""
        loc, conf = await BrowserLocatorResolver.resolve_strict(
            page=page, role=role, name=name, text=text, label=label, test_id=test_id
        )

        if conf == TargetConfidence.AMBIGUOUS:
            return InteractionOutcome(
                success=False,
                action="browser_click",
                verification_status="AMBIGUOUS",
                failure_reason=BrowserFailureReason.LOCATOR_AMBIGUOUS.value,
                message="Multiple elements match the requested locator. Refusing to click.",
            )
        if not loc or conf == TargetConfidence.LOW:
            return InteractionOutcome(
                success=False,
                action="browser_click",
                verification_status="FAILED",
                failure_reason=BrowserFailureReason.LOCATOR_NOT_FOUND.value,
                message="Element not found on active page.",
            )

        try:
            target_name = (await loc.inner_text(timeout=2000)).strip()
            if re.search(r"\b(?:captcha|buy|purchase|pay|checkout|transfer|donate|delete all|submit order|confirm payment)\b", target_name, re.I):
                return InteractionOutcome(success=False, action="browser_click", verification_status="PAUSE_FOR_USER",
                    message="This control requires the owner's direct interaction.")
            from jarvis.core.computer.browser.snapshot import BrowserSnapshotBuilder
            before = await BrowserSnapshotBuilder.capture(page)
            await loc.click(timeout=10000)
            after = await BrowserSnapshotBuilder.capture(page)
            changed = before.state_hash != after.state_hash
            return InteractionOutcome(
                success=changed,
                action="browser_click",
                verification_status="VERIFIED" if changed else "UNCERTAIN",
                evidence={"state_changed": changed, "business_effect_verified": False},
                message="Observed page state changed." if changed else "Click dispatched; no resulting state change verified. Do not retry automatically.",
            )
        except Exception as e:
            logger.warning(f"browser_click failed: {e}")
            return InteractionOutcome(
                success=False,
                action="browser_click",
                verification_status="FAILED",
                failure_reason=BrowserFailureReason.ACTIONABILITY_TIMEOUT.value,
                message=str(e),
            )

    @classmethod
    async def fill(
        cls,
        page: Page,
        value: str,
        role: Optional[str] = None,
        name: Optional[str] = None,
        label: Optional[str] = None,
        placeholder: Optional[str] = None,
    ) -> InteractionOutcome:
        """Fill an input field with strict resolution and password check."""
        # Detect password
        combined = f"{name or ''} {label or ''} {placeholder or ''}".lower()
        if any(p in combined for p in ["pass", "pwd", "secret", "pin", "otp"]):
            return InteractionOutcome(
                success=False,
                action="browser_fill",
                verification_status="PAUSE_FOR_USER",
                message="Sensitive password/credential field detected. Pausing for user.",
            )

        loc, conf = await BrowserLocatorResolver.resolve_strict(
            page=page, role=role, name=name, label=label, placeholder=placeholder
        )

        if conf == TargetConfidence.AMBIGUOUS:
            return InteractionOutcome(
                success=False,
                action="browser_fill",
                verification_status="AMBIGUOUS",
                failure_reason=BrowserFailureReason.LOCATOR_AMBIGUOUS.value,
                message="Multiple inputs match. Refusing to fill ambiguous field.",
            )
        if not loc or conf == TargetConfidence.LOW:
            return InteractionOutcome(
                success=False,
                action="browser_fill",
                verification_status="FAILED",
                failure_reason=BrowserFailureReason.LOCATOR_NOT_FOUND.value,
                message="Input element not found.",
            )

        try:
            # Labels alone cannot identify credential fields: inspect the
            # resolved DOM input before any fill (including innocuous labels).
            attrs = [await loc.get_attribute(k) or "" for k in ("type", "autocomplete", "name", "id")]
            if any(p in " ".join(attrs).lower() for p in ("password", "passwd", "one-time-code", "otp", "cvv", "cc-number", "cc-csc")):
                return InteractionOutcome(success=False, action="browser_fill", verification_status="PAUSE_FOR_USER",
                    message="Authentication or payment input requires owner interaction.")
            await loc.fill(value, timeout=10000)
            actual_val = await loc.input_value()
            matched = (actual_val == value)
            return InteractionOutcome(
                success=matched,
                action="browser_fill",
                verification_status="VERIFIED" if matched else "FAILED",
                evidence={"value_verified": matched},
            )
        except Exception as e:
            return InteractionOutcome(
                success=False,
                action="browser_fill",
                verification_status="FAILED",
                failure_reason=BrowserFailureReason.ACTIONABILITY_TIMEOUT.value,
                message=str(e),
            )

    @classmethod
    async def check(
        cls,
        page: Page,
        name: Optional[str] = None,
        label: Optional[str] = None,
        expected: bool = True,
    ) -> InteractionOutcome:
        """Check or uncheck a checkbox with state verification."""
        loc, conf = await BrowserLocatorResolver.resolve_strict(
            page=page, role="checkbox", name=name, label=label
        )
        if not loc:
            return InteractionOutcome(
                success=False,
                action="browser_check",
                verification_status="FAILED",
                failure_reason=BrowserFailureReason.LOCATOR_NOT_FOUND.value,
                message="Checkbox element not found.",
            )

        try:
            if expected:
                await loc.check()
            else:
                await loc.uncheck()

            actual_checked = await loc.is_checked()
            verified = (actual_checked == expected)
            return InteractionOutcome(
                success=verified,
                action="browser_check",
                verification_status="VERIFIED" if verified else "FAILED",
                evidence={"checked": actual_checked, "verified": verified},
            )
        except Exception as e:
            return InteractionOutcome(
                success=False,
                action="browser_check",
                verification_status="FAILED",
                message=str(e),
            )
