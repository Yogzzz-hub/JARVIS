import json
import hashlib
import sqlite3
import asyncio

from jarvis.integrations.whatsapp.personal_reply.legacy_provenance import LegacyProvenanceResolver, evidence_weight
from jarvis.integrations.whatsapp.personal_reply.models import Authorship, ChatLine, Direction
from jarvis.integrations.whatsapp.personal_reply.importer import build_examples
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore


def test_legacy_classifier_keeps_authorship_uncertain_and_excludes_known_sends(tmp_path):
    inbox = tmp_path / 'inbox.db'
    store = tmp_path / 'store.db'
    with sqlite3.connect(inbox) as db:
        db.execute('CREATE TABLE wa_generated_messages(message_id TEXT,thread_id TEXT,content_hash TEXT,created_at REAL)')
        db.execute('INSERT INTO wa_generated_messages VALUES(?,?,?,?)',
                   ('pending:draft', 'contact@lid', hashlib.sha256(b'generic reply').hexdigest(), 500))
    with sqlite3.connect(store) as db:
        db.execute('CREATE TABLE action_ledger(tool TEXT,created_at TEXT,status TEXT,provider_ack_json TEXT,verification_json TEXT)')
        db.execute('CREATE TABLE wa_pr_replies(sent_message_id TEXT)')
        db.execute('INSERT INTO action_ledger VALUES (?,?,?,?,?)',
                   ('send_whatsapp_message','2026-10-01T00:00:00','VERIFIED',json.dumps({'message_id':'known'}),'{}'))
    r = LegacyProvenanceResolver(inbox, store)
    base = dict(chat_id='contact@lid', message_type='text', text='hi da', from_me=True, payload=None)
    assert r.classify(message_id='known', timestamp=1, **base).provenance == Authorship.AUTO_GENERATED
    old = r.classify(message_id='old', timestamp=1, **base)
    assert old.provenance == Authorship.LEGACY_OWNER_LIKELY
    assert evidence_weight(old.provenance, old.confidence) < evidence_weight(Authorship.USER_TYPED)
    forwarded = r.classify(message_id='forward', timestamp=1,
                           **{**base, 'payload': json.dumps({'metadata': {'forwardingScore': 1}})})
    assert forwarded.provenance == Authorship.UNKNOWN
    assert r.classify(message_id='group', timestamp=1, **{**base, 'chat_id':'group@g.us'}).provenance == Authorship.UNKNOWN
    assert r.classify(message_id='test', timestamp=1, **{**base, 'text':'JARVIS LIVE FIX 1004'}).provenance == Authorship.AUTO_GENERATED
    assert r.classify(message_id='hash', timestamp=550, **{**base, 'text':'generic reply'}).provenance == Authorship.AUTO_GENERATED
    assert r.classify(message_id='old-hash', timestamp=1, **{**base, 'text':'generic reply'}).provenance == Authorship.LEGACY_OWNER_LIKELY


def test_legacy_pairs_are_separate_from_verified_holdout():
    lines = []
    for i in range(12):
        lines.extend([
            ChatLine(timestamp=i*100, sender='friend', direction=Direction.CONTACT, text='question', message_id=f'c{i}'),
            ChatLine(timestamp=i*100+1, sender='owner', direction=Direction.USER, text='answer', message_id=f'u{i}',
                     provenance=Authorship.LEGACY_OWNER_LIKELY, provenance_confidence=.55),
        ])
    examples = build_examples('friend@lid', lines)
    assert len(examples) == 12
    assert [e.split for e in examples].count('HOLDOUT') > 0
    assert all(e.provenance == Authorship.LEGACY_OWNER_LIKELY and e.evidence_weight < .5 for e in examples)


def test_reviewed_legacy_pairs_get_chronological_verified_holdout():
    lines = []
    for i in range(20):
        lines.extend([
            ChatLine(timestamp=i*100, sender='friend', direction=Direction.CONTACT,
                     text=f'question {i}', message_id=f'c{i}'),
            ChatLine(timestamp=i*100+1, sender='owner', direction=Direction.USER,
                     text=f'answer {i}', message_id=f'u{i}',
                     provenance=Authorship.VERIFIED_LEGACY_OWNER, provenance_confidence=1),
        ])
    examples = build_examples('friend@lid', lines)
    train = [e for e in examples if e.split == 'TRAIN']
    holdout = [e for e in examples if e.split == 'HOLDOUT']
    assert len(train) == 15 and len(holdout) == 5
    assert max(e.timestamp for e in train) < min(e.timestamp for e in holdout)


def test_batch_review_preserves_original_and_excludes_rejections(tmp_path):
    store = PersonalReplyStore(tmp_path/'brain.db')
    lines = [ChatLine(1, 'owner', Direction.USER, 'hi da', message_id='one',
                      provenance=Authorship.LEGACY_OWNER_LIKELY, provenance_confidence=.55),
             ChatLine(2, 'owner', Direction.USER, 'forwarded style', message_id='two',
                      provenance=Authorship.LEGACY_OWNER_LIKELY, provenance_confidence=.55)]
    assert store.add_sources('friend@lid', lines, import_id='legacy_inbox') == 2
    assert len(store.legacy_review_candidates('friend@lid')) == 2
    assert store.review_legacy_rows('friend@lid', {'one': True, 'two': False}) == {'APPROVED': 1, 'REJECTED': 1}
    assert [line.provenance for line in store.sources('friend@lid')] == [
        Authorship.VERIFIED_LEGACY_OWNER, Authorship.REJECTED_LEGACY]
    with store._conn() as db:
        assert [r[0] for r in db.execute('SELECT original_provenance FROM wa_pr_owner_reviews')] == [
            'LEGACY_OWNER_LIKELY', 'LEGACY_OWNER_LIKELY']
    store.add_sources('friend@lid', lines, import_id='legacy_inbox')
    assert store.sources('friend@lid')[1].provenance == Authorship.REJECTED_LEGACY


def test_live_manual_needs_exact_owner_proof_and_no_unresolved_send(tmp_path):
    inbox, store = tmp_path/'inbox.db', tmp_path/'store.db'
    with sqlite3.connect(inbox) as db:
        db.execute('CREATE TABLE wa_generated_messages(message_id TEXT,thread_id TEXT,content_hash TEXT,created_at REAL)')
    with sqlite3.connect(store) as db:
        db.execute('CREATE TABLE action_ledger(tool TEXT,created_at TEXT,status TEXT,provider_ack_json TEXT,verification_json TEXT)')
        db.execute('CREATE TABLE wa_pr_replies(sent_message_id TEXT)')
        db.execute('INSERT INTO action_ledger VALUES(?,?,?,?,?)',
                   ('send_whatsapp_message','2026-10-01T00:00:00','STARTED',None,None))
    resolver = LegacyProvenanceResolver(inbox, store)
    params = dict(message_id='human',chat_id='friend@lid',message_type='text',text='hi',timestamp=1790812800.)
    assert resolver.classify_live(**params).provenance == Authorship.UNKNOWN
    assert resolver.classify_live(**params, source_device_proof='OWNER_ATTESTED_MESSAGE_ID').provenance == Authorship.UNKNOWN
    params['timestamp'] += 2000
    assert resolver.classify_live(**params, source_device_proof='OWNER_ATTESTED_MESSAGE_ID').provenance == Authorship.VERIFIED_MANUAL_OWNER_SEND
    assert resolver.classify_live(**{**params,'message_id':'missing'}, source_device_proof='').provenance == Authorship.UNKNOWN


def test_draft_only_policy_never_auto_sends_with_grant(tmp_path):
    from jarvis.integrations.whatsapp.personal_reply.auto_reply_policy import AutoReplyPolicy
    from jarvis.integrations.whatsapp.personal_reply.models import GrantScope, ReplyMode
    store = PersonalReplyStore(tmp_path/'brain.db')
    policy = AutoReplyPolicy(store, generated_auto_reply_enabled=False)
    policy.grant(GrantScope.CONTACT, ['friend@lid'], expires_at=1000, now=1)
    assert policy.decide('friend@lid','friend@lid',has_profile=True,now=2).mode == ReplyMode.SUGGEST_ONLY


def test_generated_draft_can_be_reviewed_without_sending(tmp_path):
    from tests.whatsapp_personal.harness import make_agent
    from tests.whatsapp_personal.synthetic import export_text
    agent = make_agent(tmp_path)
    contact = '91900000001@s.whatsapp.net'
    agent.import_chat(contact, 'Test', export_text=export_text('yoga', n=40), verified_fixture=True)
    assert agent.maturity(contact) in ('VERIFIED_STYLE_BUILDING','AUTO_REPLY_CANDIDATE')
    result = asyncio.run(agent.test_reply(contact, 'hello'))
    assert result['sent'] is False
    assert agent.transport.sent_messages == []


def test_latest_inbox_message_gets_reviewable_draft_without_send(tmp_path):
    from tests.whatsapp_personal.harness import make_agent, msg
    from tests.whatsapp_personal.synthetic import export_text
    agent = make_agent(tmp_path)
    contact = '91900000001@s.whatsapp.net'
    agent.import_chat(contact, 'Test', export_text=export_text('yoga', n=40), verified_fixture=True)
    agent.inbox.add_message(msg(contact, 'are you free?', 'Test', message_id='fresh-incoming'), is_from_me=False)
    result = asyncio.run(agent.draft_latest(contact))
    assert result['status'] == 'SUGGESTED' and result['sent'] is False
    assert agent.store.reply_for_message('fresh-incoming')['status'] == 'SUGGESTED'
    assert agent.transport.sent_messages == []


def test_unchanged_approval_and_edited_draft_get_distinct_provenance(tmp_path):
    from tests.whatsapp_personal.harness import make_agent, msg, deliver
    from tests.whatsapp_personal.synthetic import export_text
    agent = make_agent(tmp_path)
    contact = '91900000001@s.whatsapp.net'
    agent.import_chat(contact, 'Test', export_text=export_text('yoga', n=40), verified_fixture=True)
    agent.set_mode(contact, 'ASK_BEFORE_SEND')
    async def run():
        first = await deliver(agent, msg(contact, 'hi da', 'Test'))
        assert first['status'] == 'AWAITING_APPROVAL'
        sent = await agent.approve_reply(first['reply_id'])
        second = await deliver(agent, msg(contact, 'tomorrow?', 'Test'))
        assert second['status'] == 'AWAITING_APPROVAL'
        edited = await agent.approve_reply(second['reply_id'], edited_text='seri da')
        return sent, edited
    sent, edited = asyncio.run(run())
    assert sent['status'] == edited['status'] == 'VERIFIED'
    with agent.store._conn() as db:
        provenance = [r[0] for r in db.execute("SELECT provenance FROM wa_pr_sources WHERE import_id='reviewed_draft' ORDER BY ts")]
        states = [r[0] for r in db.execute('SELECT state FROM wa_pr_draft_feedback ORDER BY reply_id')]
    assert provenance == ['USER_APPROVED_AI_DRAFT','USER_EDITED_AI_DRAFT']
    assert states == ['APPROVED_SENT','EDITED_SENT']


def test_exact_id_owner_attestation_rejects_jarvis_send(tmp_path):
    from tests.whatsapp_personal.harness import make_agent, msg
    agent = make_agent(tmp_path)
    contact = '91900000001@s.whatsapp.net'
    own = msg(contact, 'natural human reply', 'Me', message_id='manual-1', from_me=True)
    agent.inbox.add_message(own, is_from_me=True)
    assert agent.verify_manual_owner_send(contact, 'manual-1')['status'] == 'VERIFIED_MANUAL_OWNER_SEND'
    assert any(ln.message_id == 'manual-1' and ln.provenance == Authorship.VERIFIED_MANUAL_OWNER_SEND
               for ln in agent.store.sources(contact))
    reply_id = agent.store.start_reply('incoming-1', ['incoming-1'], contact, contact, 'ASK_BEFORE_SEND', None, 'hi')
    agent.store.update_reply(reply_id, sent_message_id='jarvis-1')
    echo = msg(contact, 'generated reply', 'Me', message_id='jarvis-1', from_me=True)
    agent.inbox.add_message(echo, is_from_me=True)
    assert agent.verify_manual_owner_send(contact, 'jarvis-1')['status'] == 'NOT_ELIGIBLE'


def test_draft_feedback_keeps_earlier_quality_flags(tmp_path):
    store = PersonalReplyStore(tmp_path/'brain.db')
    store.record_draft_feedback(1, 'friend@lid', 'BAD_STYLE', 'too formal')
    store.record_draft_feedback(1, 'friend@lid', 'EDITED_SENT', 'too formal', 'okay da', .7, 'sent-1')
    with store._conn() as db:
        events = [r[0] for r in db.execute(
            'SELECT state FROM wa_pr_draft_feedback_events WHERE reply_id=1 ORDER BY id')]
        latest = db.execute('SELECT state FROM wa_pr_draft_feedback WHERE reply_id=1').fetchone()[0]
    assert events == ['BAD_STYLE', 'EDITED_SENT']
    assert latest == 'EDITED_SENT'


def test_natural_manual_attestation_requires_one_recent_candidate(tmp_path):
    from tests.whatsapp_personal.harness import make_agent, msg
    agent = make_agent(tmp_path)
    agent.clock = lambda: 1790000050.0
    contact = '91900000001@s.whatsapp.net'
    agent.inbox.add_message(msg(contact, 'my own wording', 'Me', message_id='manual-a', from_me=True),
                            is_from_me=True)
    assert agent.verify_last_manual_owner_send('that last message was mine')['status'] == 'VERIFIED_MANUAL_OWNER_SEND'
    agent.inbox.add_message(msg(contact, 'another reply', 'Me', message_id='manual-b', from_me=True),
                            is_from_me=True)
    assert agent.verify_last_manual_owner_send('yes I wrote that')['status'] == 'NEEDS_CLARIFICATION'
    assert agent.verify_last_manual_owner_send('maybe it was mine')['status'] == 'NEEDS_OWNER_CONFIRMATION'


def test_holdout_review_is_contact_scoped_and_preserves_rating(tmp_path):
    store = PersonalReplyStore(tmp_path/'brain.db')
    case_id = store.save_holdout_review_case('friend@lid', 'free?', 'yeah', 'seri', 123)
    assert store.holdout_review_cases('other@lid') == []
    assert store.rate_holdout_review_case('other@lid', case_id, 'GOOD') is False
    assert store.rate_holdout_review_case('friend@lid', case_id, 'GOOD') is True
    assert store.holdout_review_cases('friend@lid')[0]['rating'] == 'GOOD'
