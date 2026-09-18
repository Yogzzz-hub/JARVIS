"""Typed Playwright Browser Action Handlers."""
from __future__ import annotations

import logging
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
            await loc.click(timeout=10000)
            return InteractionOutcome(
                success=True,
                action="browser_click",
                verification_status="VERIFIED",
                evidence={"role": role, "name": name or text},
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
