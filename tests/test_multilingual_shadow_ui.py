"""All browser writes intercepted: never produce real owner decisions."""
import json
from pathlib import Path
import pytest


def test_shadow_review_browser():
    playwright = pytest.importorskip('playwright.sync_api')
    html = '<input id="reviewer" value="TEST_OWNER">' + Path('scripts/multilingual_shadow_panel.html').read_text(encoding='utf-8').replace('__TOKEN__', 'TEST_TOKEN')
    sent = []
    case = {'id':'fake-case','source':'voice','language':'TANGLISH','raw_text':'<img src=x onerror=alert(1)>',
            'production':{'action':'READ'},'candidate':{'action':'OPEN','should_execute':False},'agreements':{'action':False}}
    state = {'enabled':True,'production_authoritative':True,'counts':{'command':1},'agreement':{'action':0},
             'owner_reviewed':0,'review_counts':{},'disagreements':[case],'disagreement_total':1,'offset':0,
             'execute_precision':None,'execute_coverage':0,'note':'Agreement is not accuracy','counters':{},'sources':{'voice':1},'latency':{}}
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        def intercept(route):
            if '/api/shadow/review' in route.request.url:
                sent.append(route.request.post_data_json)
                route.fulfill(content_type='application/json',body='{"saved":true}')
            elif '/api/shadow' in route.request.url:
                route.fulfill(content_type='application/json',body=json.dumps(state))
            else:
                route.fulfill(content_type='text/html',body=html)
        page.route('**/*',intercept)
        page.goto('http://shadow.test')
        page.wait_for_selector('#shadowCases details')
        assert page.locator('#shadowCases img').count() == 0
        assert page.locator('#shadowNext').is_disabled()
        page.locator('#shadowCases summary').click()
        page.get_by_role('button',name='CANDIDATE_CORRECT',exact=True).click()
        page.wait_for_timeout(100)
        assert sent == [{'case_id':'fake-case','decision':'CANDIDATE_CORRECT','reviewer':'TEST_OWNER'}]
        assert not errors
        browser.close()
