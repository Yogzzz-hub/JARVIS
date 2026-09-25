import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from jarvis.config import load
from jarvis.core.commands.contracts import CommandRequest
from jarvis.core.commands.service import CommandService
from jarvis.core.gateway.app import create_app
from jarvis.core.metrics.clock import Clock
from jarvis.core.router.models import RouteLane
from jarvis.core.router.ollama import DisabledProvider
from jarvis.core.router.router import SmartRouter
from jarvis.core.router.slots import parse_percentage
from jarvis.core.tasks.manager import TaskManager
from jarvis.tools.base import ToolResult, VerificationResult
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.system.native import AppInput, AppOutput, SystemTool


@pytest.mark.parametrize('prefix', ['', 'Please ', 'Hey Jarvis, ', 'Can you ', 'Could you please '])
@pytest.mark.parametrize('verb', ['open', 'launch', 'start', 'bring up'])
@pytest.mark.parametrize('app', ['notepad', 'calculator', 'chrome', 'edge', 'vscode'])
def test_natural_app_variants(prefix, verb, app):
    decision = asyncio.run(SmartRouter(llm_provider=DisabledProvider()).route(f'{prefix}{verb} {app}.'))
    assert decision.lane == RouteLane.LANE_0
    assert decision.intent == 'open_app'
    assert decision.slots == {'name': app}


@pytest.mark.parametrize('text,intent,slots', [
    ('What time is it?', 'get_time', {}),
    ('What is the time?', 'get_time', {}),
    ('Turn volume to twenty five percent.', 'volume_set', {'percent': 25}),
    ('set volume to ninety-nine percent', 'volume_set', {'percent': 99}),
])
def test_readonly_questions_and_numbers(text, intent, slots):
    decision = asyncio.run(SmartRouter(llm_provider=DisabledProvider()).route(text))
    assert decision.lane == RouteLane.LANE_0
    assert (decision.intent, decision.slots) == (intent, slots)


@pytest.mark.parametrize('text', ['-5', '1.5', '20 5', 'abc50', '101', 'True'])
def test_invalid_percent_is_not_silently_changed(text):
    assert parse_percentage(text) is None


@pytest.mark.parametrize('text', ["Don't open Chrome.", 'Don’t open Chrome.', 'Hey Jarvis, do not launch Notepad.'])
def test_negation(text):
    assert asyncio.run(SmartRouter(llm_provider=DisabledProvider()).route(text)).lane == RouteLane.REJECT


def make_service():
    bus, writer, metrics = Mock(), Mock(), Mock()
    registry = ToolRegistry()
    registry.register(SystemTool('open_app', AppInput, AppOutput, lambda _: None, False))
    registry.finalize()
    executor = Mock(execute=AsyncMock())
    verifier = Mock(verify=AsyncMock(return_value=VerificationResult(verified=True, confidence=1., evidence={'observed': True})))
    return CommandService(registry, executor, verifier, Mock(), TaskManager(bus, writer), bus, writer, metrics,
                          router=SmartRouter(llm_provider=DisabledProvider()), planner_enabled=False)


def test_cancel_works_even_at_execution_capacity():
    async def scenario():
        service = make_service()
        previous = [service.tasks.create(CommandRequest(text='open notepad'), Clock()) for _ in range(2)]
        service.active.update([object(), object()])
        result = await service.handle(CommandRequest(text='Hey Jarvis, cancel.'))
        assert result.state == 'SUCCESS'
        assert all(task.cancellation.is_set() for task in previous)
        assert result.tool_result.data['cancelled_tasks'] == 2
        service.executor.execute.assert_not_called()
    asyncio.run(scenario())


@pytest.mark.parametrize('fail_execution,fail_verification', [(True, False), (False, True), (False, False)])
def test_compound_checks_results_and_state_transitions(fail_execution, fail_verification):
    async def scenario():
        service = make_service()
        service.executor.execute.return_value = ToolResult(
            success=not fail_execution, tool_name='open_app',
            error='launch failed' if fail_execution else None, data={'name': 'notepad'})
        if fail_verification:
            service.verifier.verify.return_value = VerificationResult(verified=False, confidence=0., error='No process')
        result = await service.handle(CommandRequest(text='open notepad and calculator'))
        failed = fail_execution or fail_verification
        assert result.state == ('FAILED' if failed else 'SUCCESS')
        assert service.executor.execute.await_count == (1 if failed else 2)
    asyncio.run(scenario())


def test_missing_capability_returns_failure():
    result = asyncio.run(make_service().handle(CommandRequest(text='close notepad')))
    assert result.state == 'FAILED'
    assert 'not available' in result.message


def test_disabled_planner_does_not_execute():
    service = make_service()
    result = asyncio.run(service.handle(CommandRequest(text='How do I open Chrome?')))
    assert result.state == 'FAILED'
    service.executor.execute.assert_not_called()


def test_browser_origin_cannot_submit_commands():
    client = TestClient(create_app(Mock()))
    assert client.post('/command', headers={'Origin': 'https://untrusted.example'}, json={'text': 'open notepad'}).status_code == 403


def test_toml_search_arrays(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('[search]\nroots = ["C:/Test"]\nexclude_patterns = [".git"]\n')
    assert load(config).search.roots == ('C:/Test',)
