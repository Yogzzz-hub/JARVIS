import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from jarvis.core.diagnostics import CandidateOverlay, OperationalDiagnostics, OperationalTrace, TraceStore
from jarvis.core.extensions import ExtensionRegistry, ExtensionSpec, HardwareProfile, ModelSpec, SkillSpec


def trace(**kwargs):
    return OperationalTrace(source="test", outcome="SUCCESS", **kwargs)


def test_metadata_schema_rejects_private_content():
    with pytest.raises(ValidationError):
        trace(message="private", raw_text="secret")
    with pytest.raises(ValidationError):
        trace(tool="123@lid")
    with pytest.raises(ValidationError):
        trace(provenance="VERIFIED_REAL")
    with pytest.raises(ValidationError):
        trace(duration_ms=float('nan'))
    with pytest.raises(ValidationError):
        trace(label='private-contact-name')


def test_store_retention_and_provenance_are_separate(tmp_path):
    store = TraceStore(tmp_path / 'traces.db', max_rows=3)
    for _ in range(5):
        store.append(trace())
    assert len(store.recent()) == 3
    result = store.aggregate()
    assert result['real_shadow'] == result['verified_real'] == result['owner_reviewed'] == 0


@pytest.mark.asyncio
async def test_advisor_abstains_and_subscriber_does_not_persist_payload(tmp_path):
    store = TraceStore(tmp_path / 'traces.db')
    diag = OperationalDiagnostics(store, advisor_enabled=True)
    await diag.consume(SimpleNamespace(name='response.ready', data={'message':'private'}))
    await diag.consume(SimpleNamespace(name='trace.completed', data=trace().model_dump()))
    assert len(store.recent()) == 1
    assert store.recent()[0].recommendation is None
    assert 'private' not in json.dumps([r.model_dump() for r in store.recent()])


def test_candidate_gates_and_rollback():
    candidate = CandidateOverlay(candidate_id='dev', target='routing_threshold', source_hash='a'*64, candidate_hash='b'*64)
    candidate = candidate.transition('SHADOW')
    with pytest.raises(ValueError):
        candidate.transition('ACCEPTANCE_READY')
    candidate = candidate.model_copy(update={'gates': dict.fromkeys(('quality','latency','resource','safety','regression','real_evidence'),True), 'rollback_pointer':'baseline'})
    candidate = candidate.transition('ACCEPTANCE_READY')
    with pytest.raises(ValueError):
        candidate.transition('PROMOTED')
    assert candidate.transition('PROMOTED', owner_approved=True).transition('ROLLED_BACK').state == 'ROLLED_BACK'


def test_extensions_cannot_escalate_scope_or_assume_resources():
    registry = ExtensionRegistry('engine')
    registry.register(ExtensionSpec(id='ollama', kind='engine'))
    with pytest.raises(ValueError):
        registry.register(ExtensionSpec(id='ollama', kind='engine'))
    with pytest.raises(ValueError):
        registry.register(ExtensionSpec(id='other', kind='channel'))
    skill = SkillSpec(id='unreviewed', description='test', source='local', sha256='a'*64, required_capabilities=('delete_file',))
    with pytest.raises(ValueError):
        skill.validate_enable({'delete_file'})
    with pytest.raises(ValueError):
        skill.model_copy(update={'trust':'CORE'}).validate_enable({'read_file'})
    assert not HardwareProfile('cpu', 16*1024**3, 2*1024**3).eligible(ModelSpec(model_id='unknown', available=True))


def test_legacy_raw_powershell_is_denied_before_execution(monkeypatch):
    from jarvis.security.policy.evaluator import PolicyEvaluator
    from jarvis.tools.system.computer_tools import PowerShellCommandTool
    tool = PowerShellCommandTool()
    policy = PolicyEvaluator()
    assert policy.evaluate_node(tool.definition, {'command':'Get-Date', 'as_admin':False}).is_denied
    monkeypatch.setattr('subprocess.run', lambda *a, **k: pytest.fail('raw shell executed'))
    assert tool.run({'command':'Get-Date'})['status'] == 'policy_denied'


def test_scope_lookup_error_fails_closed(monkeypatch):
    from jarvis.security.policy.evaluator import PolicyEvaluator
    from jarvis.tools.system.computer_tools import BrowserNavigateTool
    def broken():
        raise RuntimeError('Scope service unavailable')
    monkeypatch.setattr('jarvis.security.policy.scope.get_task_scope_manager', broken)
    assert PolicyEvaluator().evaluate_node(BrowserNavigateTool.definition, {'url':'https://example.com'}, task_id='task').is_denied


def test_incomplete_snapshot_does_not_clear_other_chats_or_claim_ready(tmp_path):
    from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
    inbox = WhatsAppInbox(tmp_path / 'inbox.db')
    inbox.set_connector_state('CONNECTED')
    inbox.update_chats([{'chat_id':'111@lid','unread':3}], full=False)
    inbox.update_chats([{'chat_id':'222@lid','unread':1}], full=True, synced=False,
                       generation='current', synced_generation='old')
    assert not inbox.chats_synced()
    with inbox._get_conn() as con:
        assert con.execute("SELECT unread FROM whatsapp_chats WHERE chat_id='111@lid'").fetchone()[0] == 3


def test_snapshot_import_missing_source_cannot_mutate_database(tmp_path):
    from scripts.sync_real_whatsapp_db import import_snapshot
    db = tmp_path / 'inbox.db'
    with pytest.raises(FileNotFoundError):
        import_snapshot(db, tmp_path / 'missing.json', apply=True)
    assert not db.exists()


def test_runtime_registry_metadata_cannot_contaminate_default_or_another_runtime():
    from jarvis.core.capabilities.registry import get_default_capability_registry
    from jarvis.tools.registry import ToolRegistry
    from jarvis.tools.system.whatsapp_intelligence import create_intelligence_tools
    tools = ToolRegistry()
    for tool in create_intelligence_tools():
        tools.register(tool)
    isolated = get_default_capability_registry(tools)
    assert isolated.get_by_tool('whatsapp_draft_cancel') is not None
    assert get_default_capability_registry().get_by_tool('whatsapp_draft_cancel') is None
    assert get_default_capability_registry(ToolRegistry()).get_by_tool('whatsapp_draft_cancel') is None
    from jarvis.core.router.router import SmartRouter
    from jarvis.core.router.ollama import DisabledProvider
    router = SmartRouter(tool_registry=tools, llm_provider=DisabledProvider())
    assert not router._retrieval_ok('whatsapp_draft_cancel', 'Cancel the queued indexing jobs')
    assert not router._retrieval_ok('whatsapp_message_read', 'Retry the document search')
    assert router._retrieval_ok('whatsapp_message_read', 'Read WhatsApp messages')


@pytest.mark.asyncio
async def test_postcondition_cannot_promote_reported_failure_or_uncertainty():
    from jarvis.security.postconditions import verify_postconditions
    for data in ({'success':False}, {'status':'NEEDS_GUIDANCE'}, {'status':'ERROR'}):
        assert not (await verify_postconditions('dev_fixture', {}, data)).verified
    result = await verify_postconditions('dev_fixture', {}, {'status':'UNCERTAIN'})
    assert result.status == 'UNCERTAIN' and not result.retry_safe
    result = await verify_postconditions('browser_click', {}, {'success':True, 'verification_status':'UNCERTAIN'})
    assert not result.verified and not result.retry_safe
    assert not (await verify_postconditions('browser_workflow', {}, {'status':'PAUSED'})).verified
