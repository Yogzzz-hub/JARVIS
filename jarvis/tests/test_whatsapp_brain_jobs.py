"""The shared intelligence build never exposes half-published derived state."""
from __future__ import annotations

import time
import threading
from types import SimpleNamespace

import pytest

from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
from jarvis.integrations.whatsapp.personal_reply.agent import PersonalReplyAgent
from jarvis.integrations.whatsapp.personal_reply.models import Authorship, ChatLine, Direction
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore


def _agent(tmp_path):
    inbox = WhatsAppInbox(tmp_path / 'inbox.db')
    with inbox._get_conn() as con:
        con.execute('CREATE TABLE IF NOT EXISTS wa_events(message_id TEXT PRIMARY KEY,payload TEXT)')
    store = PersonalReplyStore(tmp_path / 'style.db')
    cid = '1234567890@s.whatsapp.net'
    store.upsert_contact(cid, 'Test')
    store.add_sources(cid, [
        ChatLine(timestamp=100, sender='contact', direction=Direction.CONTACT,
                 text='hello', message_id='in-1'),
        ChatLine(timestamp=110, sender='owner', direction=Direction.USER,
                 text='hey da', message_id='out-1', provenance=Authorship.VERIFIED_LEGACY_OWNER,
                 provenance_confidence=1.0),
    ], import_id='reviewed_test')
    return PersonalReplyAgent(store=store, inbox=inbox, use_jde=False), cid


def _wait(jobs, job_id):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        job = jobs.get(job_id)
        if job['status'] in ('COMPLETE', 'FAILED', 'CANCELLED'):
            return job
        time.sleep(.05)
    pytest.fail('Background intelligence job did not finish')


def test_contact_build_publishes_once_and_failure_keeps_old_index(tmp_path, monkeypatch):
    agent, cid = _agent(tmp_path)
    jobs = agent.brain_jobs
    first = _wait(jobs, jobs.start('CONTACT', cid)['job_id'])
    assert first['status'] == 'COMPLETE', first
    assert first['new_index_version'] == 1
    assert agent.store.example_count(cid) == 1
    assert agent.store.brain_state(cid)['contact']['derived']['reply_pairs'] == 1
    baseline = agent.store.brain_state()['active_version']
    monkeypatch.setattr(agent.store, 'publish_brain_snapshots',
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError('validation failed')))
    failed = _wait(jobs, jobs.start('CONTACT', cid)['job_id'])
    assert failed['status'] == 'FAILED'
    assert agent.store.brain_state()['active_version'] == baseline
    assert agent.store.example_count(cid) == 1
    assert agent.store.sources(cid)[1].provenance == Authorship.VERIFIED_LEGACY_OWNER


def test_all_build_skips_unchanged_sources(tmp_path):
    agent, cid = _agent(tmp_path)
    jobs = agent.brain_jobs
    assert _wait(jobs, jobs.start('ALL')['job_id'])['status'] == 'COMPLETE'
    first = agent.store.brain_state()['active_version']
    assert _wait(jobs, jobs.start('ALL')['job_id'])['status'] == 'COMPLETE'
    assert agent.store.brain_state()['active_version'] == first
    assert agent.store.brain_state(cid)['contact']['index_version'] == first


def test_cancel_before_publish_keeps_active_index(tmp_path, monkeypatch):
    agent, cid = _agent(tmp_path)
    jobs = agent.brain_jobs
    entered, release = threading.Event(), threading.Event()
    original = jobs._snapshot
    def slow_snapshot(contact_id):
        entered.set()
        assert release.wait(5)
        return original(contact_id)
    monkeypatch.setattr(jobs, '_snapshot', slow_snapshot)
    job_id = jobs.start('CONTACT', cid)['job_id']
    assert entered.wait(5)
    assert jobs.cancel(job_id)['status'] == 'CANCELLED'
    release.set()
    assert _wait(jobs, job_id)['status'] == 'CANCELLED'
    if jobs._worker:
        jobs._worker.join(5)
    assert agent.store.brain_state()['active_version'] == 0
    assert agent.store.example_count(cid) == 0


def test_dashboard_brain_api_uses_existing_store(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from jarvis.integrations.whatsapp.personal_reply.api import register

    agent, cid = _agent(tmp_path)
    app = FastAPI()
    register(app, SimpleNamespace(whatsapp_service=SimpleNamespace(
        personal_reply=agent, transport=SimpleNamespace(is_connected=False))))
    client = TestClient(app)
    overview = client.get('/whatsapp/personal/intelligence/overview')
    assert overview.status_code == 200
    assert overview.json()['history']['remote_history_complete'] == 'UNKNOWN'
    started = client.post('/whatsapp/personal/intelligence/jobs',
                          json={'scope': 'CONTACT', 'contact_id': cid})
    assert started.status_code == 200
    finished = _wait(agent.brain_jobs, started.json()['job_id'])
    assert finished['status'] == 'COMPLETE'
    detail = client.get(f'/whatsapp/personal/intelligence/contacts/{cid}')
    assert detail.status_code == 200
    assert detail.json()['contact']['derived']['reply_pairs'] == 1
    assert client.post('/whatsapp/personal/intelligence/jobs',
                       json={'scope': 'CONTACT', 'contact_id': 'bad@g.us'}).status_code == 400
