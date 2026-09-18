"""Compact Semantic Browser Snapshot Builder."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from playwright.async_api import Page
from jarvis.core.computer.models import UIBackend, UIElement, UIObservation
from jarvis.core.computer.browser.security import detect_web_prompt_injection

logger = logging.getLogger("jarvis.computer.browser.snapshot")


class BrowserSnapshotBuilder:
    """Extracts compact semantic snapshots of web pages."""

    EXTRACT_SCRIPT = """() => {
        const results = [];
        const interactive = document.querySelectorAll(
            'button, a[href], input, select, textarea, [role="button"], [role="link"], [role="checkbox"], [role="tab"], h1, h2, h3, [role="dialog"], .g-recaptcha, .h-captcha, [id*="captcha"], [class*="captcha"]'
        );

        let idCounter = 1;
        for (const el of interactive) {
            // Check visibility
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                continue;
            }
            if (el.offsetWidth === 0 && el.offsetHeight === 0) {
                continue;
            }

            const tag = el.tagName.toLowerCase();
            let role = el.getAttribute('role') || tag;
            let name = (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.title || el.value || '').trim();
            // Truncate overly long names
            if (name.length > 100) name = name.substring(0, 97) + '...';

            let type = el.getAttribute('type') || '';
            let autoId = el.id || el.getAttribute('data-testid') || '';
            let value = (tag === 'input' || tag === 'textarea' || tag === 'select') ? el.value : '';

            let checked = null;
            if (type === 'checkbox' || type === 'radio' || role === 'checkbox') {
                checked = el.checked || (el.getAttribute('aria-checked') === 'true');
            }

            const isPassword = (type === 'password' || autoId.toLowerCase().includes('pass'));
            const isCaptcha = (autoId.toLowerCase().includes('captcha') || name.toLowerCase().includes('captcha') || document.querySelector('.g-recaptcha, .h-captcha') !== null);

            results.push({
                element_id: 'dom_' + (idCounter++),
                tag: tag,
                role: role,
                name: name,
                control_type: tag,
                automation_id: autoId,
                value_summary: value,
                enabled: !el.disabled,
                visible: true,
                checked: checked,
                editable: (tag === 'input' && type !== 'submit' && type !== 'button') || tag === 'textarea',
                is_password: isPassword,
                is_captcha: isCaptcha,
                ancestor_path: el.parentElement ? (el.parentElement.tagName.toLowerCase()) : ''
            });

            if (results.length >= 300) break; // Hard limit per snapshot
        }
        return results;
    }"""

    @classmethod
    async def capture(cls, page: Page) -> UIObservation:
        """Capture and normalize a compact semantic snapshot."""
        url = page.url
        title = await page.title()

        try:
            raw_elements = await page.evaluate(cls.EXTRACT_SCRIPT)
        except Exception as e:
            logger.warning(f"Failed to execute DOM snapshot extraction: {e}")
            raw_elements = []

        ui_elements: List[UIElement] = []
        quarantine_notes = []

        for item in raw_elements:
            elem = UIElement(
                element_id=item["element_id"],
                role=item["role"],
                name=item["name"],
                control_type=item["control_type"],
                automation_id=item["automation_id"],
                value_summary=item["value_summary"],
                enabled=item["enabled"],
                visible=item["visible"],
                checked=item["checked"],
                editable=item["editable"],
                ancestor_path=item["ancestor_path"],
            )
            # Check prompt injection
            if elem.name:
                injection_detected, pattern = detect_web_prompt_injection(elem.name)
                if injection_detected:
                    quarantine_notes.append(f"Suspicious prompt-injection string in control '{elem.name}': {pattern}")

            ui_elements.append(elem)

        # Check overall page text for prompt injection
        try:
            body_text = await page.inner_text("body")
            inj_detected, pattern = detect_web_prompt_injection(body_text)
            if inj_detected:
                quarantine_notes.append(f"Suspicious prompt-injection pattern detected in page text: {pattern}")
        except Exception:
            pass

        obs = UIObservation(
            observation_id=f"web_snap_{int(time.time()*1000)}",
            backend=UIBackend.BROWSER,
            application="Browser",
            window_title=title,
            url=url,
            elements=ui_elements,
            is_untrusted=True,
            quarantine_notes=quarantine_notes,
        )
        obs.compute_state_hash()
        return obs
