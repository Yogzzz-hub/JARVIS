"""Playwright Semantic Locators with Strict Ambiguity Handling."""
from __future__ import annotations

import logging
from typing import Optional, Tuple
from playwright.async_api import Locator, Page
from jarvis.core.computer.models import TargetConfidence

logger = logging.getLogger("jarvis.computer.browser.locator")


class BrowserLocatorResolver:
    """Resolves Playwright semantic locators strictly according to Section 31-33."""

    @classmethod
    async def resolve_strict(
        cls,
        page: Page,
        role: Optional[str] = None,
        name: Optional[str] = None,
        text: Optional[str] = None,
        label: Optional[str] = None,
        placeholder: Optional[str] = None,
        test_id: Optional[str] = None,
    ) -> Tuple[Optional[Locator], TargetConfidence]:
        """Resolve a locator with strict ambiguity detection.
        
        Priority:
        1. get_by_role + name
        2. get_by_label
        3. get_by_placeholder
        4. get_by_text
        5. get_by_test_id
        """
        locator: Optional[Locator] = None

        # 1. Role + Name
        if role and name:
            try:
                loc = page.get_by_role(role, name=name, exact=False)
                cnt = await loc.count()
                if cnt == 1:
                    return loc, TargetConfidence.HIGH
                elif cnt > 1:
                    # Check exact match
                    loc_exact = page.get_by_role(role, name=name, exact=True)
                    if await loc_exact.count() == 1:
                        return loc_exact, TargetConfidence.HIGH
                    return None, TargetConfidence.AMBIGUOUS
            except Exception:
                pass

        # 2. Label
        if label:
            try:
                loc = page.get_by_label(label, exact=False)
                cnt = await loc.count()
                if cnt == 1:
                    return loc, TargetConfidence.HIGH
                elif cnt > 1:
                    return None, TargetConfidence.AMBIGUOUS
            except Exception:
                pass

        # 3. Placeholder
        if placeholder:
            try:
                loc = page.get_by_placeholder(placeholder, exact=False)
                cnt = await loc.count()
                if cnt == 1:
                    return loc, TargetConfidence.HIGH
                elif cnt > 1:
                    return None, TargetConfidence.AMBIGUOUS
            except Exception:
                pass

        # 4. Text
        if text:
            try:
                loc = page.get_by_text(text, exact=True)
                cnt = await loc.count()
                if cnt == 1:
                    return loc, TargetConfidence.HIGH
                elif cnt > 1:
                    return None, TargetConfidence.AMBIGUOUS

                # Substring fallback
                loc_sub = page.get_by_text(text, exact=False)
                cnt_sub = await loc_sub.count()
                if cnt_sub == 1:
                    return loc_sub, TargetConfidence.MEDIUM
                elif cnt_sub > 1:
                    return None, TargetConfidence.AMBIGUOUS
            except Exception:
                pass

        # 5. Test ID
        if test_id:
            try:
                loc = page.get_by_test_id(test_id)
                cnt = await loc.count()
                if cnt == 1:
                    return loc, TargetConfidence.HIGH
                elif cnt > 1:
                    return None, TargetConfidence.AMBIGUOUS
            except Exception:
                pass

        return None, TargetConfidence.LOW
