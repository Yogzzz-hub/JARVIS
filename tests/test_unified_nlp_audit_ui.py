"""Browser interactions use intercepted requests, never real human decisions."""
import json
from pathlib import Path

import pytest

from scripts.unified_nlp_audit import AuditStore, ACTION_FAMILY, COARSE, SLOTS


def test_human_review_browser():
    playwright = pytest.importorskip("playwright.sync_api")
    store = AuditStore()
    state = {"status": store.status(), "queue": store.queue, "reviews": {},
             "precheck": store.precheck(),
             "schema": {"actions": ACTION_FAMILY, "speech": COARSE, "slots": sorted(SLOTS)}}
    html = Path("scripts/unified_nlp_audit.html").read_text(encoding="utf-8").replace("__TOKEN__", "TEST_ONLY")
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-proxy-server"])
        page = browser.new_page()
        page.set_default_timeout(10000)
        errors, sent = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def intercept(route):
            url = route.request.url
            if url.endswith("/api/state"):
                route.fulfill(content_type="application/json", body=json.dumps(state))
            elif url.endswith("/api/review"):
                sent.append(route.request.post_data_json)
                route.fulfill(content_type="application/json", body=json.dumps(state["status"]))
            else:
                route.fulfill(content_type="text/html", body=html)

        page.route("**/*", intercept)
        page.goto("http://audit.test")
        page.wait_for_function("document.getElementById('id').textContent.includes('/12')")
        assert not page.locator("#frame").is_visible()
        assert "Manual review: 10" in page.locator("#aiCounts").inner_text()
        page.click("#likely")
        assert "/738" in page.locator("#id").inner_text()
        page.click("#high")
        assert "HIGH-RISK" in page.locator("#mode").inner_text()
        page.click("#flagged")
        old = page.locator("#id").inner_text()
        page.locator("body").click(position={"x": 5, "y": 5})
        page.keyboard.press("n")
        assert page.locator("#id").inner_text() != old
        page.keyboard.press("p")
        assert page.locator("#id").inner_text() == old
        page.keyboard.press("f")
        assert page.locator("#fix").is_visible()
        assert page.get_by_label("Domain", exact=True).is_visible()
        assert page.get_by_label("Should Execute", exact=True).is_visible()
        page.click("#cancelFix")
        page.fill("#reviewer", "UI_TEST_ONLY")
        page.click("#approve")
        page.wait_for_function("document.getElementById('id').textContent.startsWith('2/')")
        assert len(sent) == 1 and sent[0]["decision"] == "APPROVE"
        page.click("#wrong")
        page.get_by_label("Domain", exact=True).select_option("FILES")
        page.click("#saveFix")
        page.wait_for_function("document.getElementById('id').textContent.startsWith('3/')")
        assert len(sent) == 2 and sent[1]["decision"] == "FIX_LABEL"
        assert sent[1]["corrected_labels"]["domain"] == "FILES"
        assert "text" not in sent[1]
        assert not errors
        browser.close()
