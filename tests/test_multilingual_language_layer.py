import json
import time
import pytest
from jarvis.core.language_layer import repair, conversation_features, clauses, automation_semantics
from jarvis.core.language_shadow import JarvisLanguageUnderstandingService, ShadowStore, safe_text


def frame(text, **extra):
    return dict(raw_text=text, action='SEND', domain='WHATSAPP', object_type='MessageRef',
                speech_act='COMMAND', slots=[], values={}, confidence=.99, **extra)


@pytest.mark.parametrize('text,negated', [('delete pannadha', True), ('delete pannalama?', False),
    ('avan delete pannala nu sonnan', False), ('not Gmail, WhatsApp check pannu', False),
    ('write "do not delete"', False), ('அந்த file delete பண்ணாத', True)])
def test_negation_scopes(text, negated):
    f = repair(frame(text))
    assert f['negation'] is negated
    assert not f['should_execute'] and not f['jarvis_semantic_frame']['actionability']


def test_role_correction_and_identifier():
    f = repair(frame('Priya anupuna brief.pdf Deepa ku send pannu actually Arun ku'))
    assert f['sender'] == 'Priya' and f['recipient'] == 'Arun'
    assert {'slot': 'recipient', 'superseded': 'Deepa', 'active': 'Arun'} in f['corrections']
    assert f['values']['file'] == 'brief.pdf'
    assert f['resource']['identifiers']['file'] == 'brief.pdf'


def test_reference_and_raw():
    raw = '  avan anupuna second pdf open pannu  '
    f = repair(frame(raw))
    assert f['raw_text'] == raw
    assert {r['type'] for r in f['references']} == {'SelectedFileRef', 'OrdinalRef'}
    assert all(r['value'] is None for r in f['references'])
    assert f['values']['ordinal'] == 2


def test_status_and_conversation_never_execute():
    f = repair(frame('backend running ah?'))
    assert f['speech_act'] == 'STATUS_QUERY' and f['action'] == 'CHECK'
    assert f['intent'] == 'CHECK' and f['jarvis_semantic_frame']['intent'] == 'CHECK'
    f = conversation_features('dei free ah?', repair(frame('dei free ah?')))
    assert f['personal_state_required'] and not f['auto_reply'] and not f['should_execute']


def test_shadow_boundaries_and_immutable_review_history(tmp_path):
    cfg = tmp_path / 'jarvis/config'
    cfg.mkdir(parents=True)
    (cfg / 'nlp_candidate.json').write_text(json.dumps({'MULTILINGUAL_NLP_SHADOW': True}))
    store = ShadowStore(tmp_path / 'shadow.db')
    service = JarvisLanguageUnderstandingService(tmp_path, store, worker=lambda i: {'candidate': {}, 'agreements': {'action': False}, 'language': 'ENGLISH'})
    assert not service.submit('open Chrome', 'whatsapp', owner=False)
    assert not service.submit('open Chrome', 'test', owner=True)
    assert not service.submit('password is secret', 'http', owner=True)
    assert service.submit('open Chrome', 'http', owner=True)
    service.pending.join()
    case = store.state()['disagreements'][0]
    store.review(case['id'], 'CANDIDATE_CORRECT', 'owner')
    store.review(case['id'], 'UNSURE', 'owner')
    assert store.state()['owner_reviewed'] == 1
    assert store.state()['review_counts']['UNSURE'] == 1
    with store.connect() as c:
        assert c.execute('SELECT count(*) FROM reviews').fetchone()[0] == 2
    service.close()


def test_conversation_logs_features_only(tmp_path):
    store = ShadowStore(tmp_path / 'shadow.db')
    store.record({'id': 'contact', 'mode': 'conversation', 'source': 'whatsapp', 'raw_text': 'private text', 'candidate': {'speech_act': 'QUESTION'}})
    with store.connect() as c:
        assert 'private text' not in c.execute('SELECT payload FROM cases').fetchone()[0]
    with pytest.raises(ValueError):
        store.review('contact', 'CANDIDATE_CORRECT', 'owner')


@pytest.mark.parametrize('text', ['api_key=hello', 'Bearer abc', 'https://x.test/?token=abc', 'https://user:pass@host'])
def test_secret_omission(text):
    assert not safe_text(text)


def test_composition_and_automation_do_not_install():
    assert clauses('open Firefox then search GitLab') == ['open Firefox', 'search GitLab']
    assert clauses('write "open then delete"') == ['write "open then delete"']
    a = automation_semantics('when backend is unavailable, notify me')
    assert a['condition'] == 'backend is unavailable'
    assert not a['should_execute'] and a['requires_planner']


def test_actual_command_observer_preserves_result(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from jarvis.core.commands.service import CommandService
    from jarvis.core.commands.contracts import CommandRequest
    import jarvis.core.language_shadow as shadow
    observed = []
    monkeypatch.setattr(shadow, 'get_language_service', lambda: SimpleNamespace(submit=lambda *a, **k: observed.append((a, k))))
    service = object.__new__(CommandService)
    service._last_decisions = {}
    answer = object()
    async def production(request, clock):
        service._last_decisions[request.request_id] = SimpleNamespace(intent='open_app', slots={'app': 'Firefox'}, lane='LANE_0', context_trace=None)
        request = request.model_copy(update={'text': 'normalized production text'})
        return answer
    service._handle = production
    request = CommandRequest(text='Firefox open pannunga', source='voice')
    assert asyncio.run(service.handle(request)) is answer
    assert observed[0][0][0] == 'Firefox open pannunga'
    assert observed[0][0][1] == 'voice'
    assert observed[0][0][2]['intent'] == 'open_app'


def test_shadow_blocks_auto_reply_without_revoking_owner_grants(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from jarvis.integrations.whatsapp.personal_reply.agent import PersonalReplyAgent
    from jarvis.integrations.whatsapp.personal_reply.models import ReplyMode
    import jarvis.core.language_shadow as shadow
    monkeypatch.setattr(shadow, 'generated_auto_reply_blocked', lambda: True)
    agent = object.__new__(PersonalReplyAgent)
    agent.clock = lambda: 100
    agent.store = SimpleNamespace(load_profile=lambda cid: object())
    agent.policy = SimpleNamespace(stop_generation=0, decide=lambda *a, **k: SimpleNamespace(mode=ReplyMode.AUTO_REPLY_UNTIL, auto=True))
    result = asyncio.run(agent.process_batch(SimpleNamespace(contact_id='contact', display_name='Friend', chat_id='contact@s.whatsapp.net')))
    assert result['auto_reply'] is False
