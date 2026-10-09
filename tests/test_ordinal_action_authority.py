"""An ordinal in a question must not authorize opening an unrelated resource."""
import pytest
from jarvis.core.router.guards import allows_ordinal_open


@pytest.mark.parametrize('text', [
    'what isn the last msg in appa',
    'what is the last message in WhatsApp',
    'who sent the first email',
    'explain the second result',
    'send the last file to Arun',
    'delete the first document',
])
def test_ordinal_does_not_supply_an_open_action(text):
    assert not allows_ordinal_open(text)


@pytest.mark.parametrize('text', ['second one', 'the last file', 'open the second one', 'show the first result'])
def test_explicit_open_and_terse_selections_remain_supported(text):
    assert allows_ordinal_open(text)


def test_inbox_scope_is_not_previous_assistant_action_history():
    from jarvis.core.action_log import is_followup
    assert not is_followup('what is the last message in WhatsApp')
    assert not is_followup('what was the last email I received in Gmail')
    assert is_followup('what was the last message you sent on WhatsApp')


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['what isn the last msg in appa', 'what is the last message in WhatsApp', 'who sent the first email'])
async def test_question_with_active_file_does_not_route_to_open(tmp_path, text):
    from jarvis.core.router.router import SmartRouter
    from jarvis.core.router.ollama import DisabledProvider
    from jarvis.memory.working_memory import WorkingMemory
    memory = WorkingMemory()
    file = tmp_path/'whatsapp_notes.md'; file.write_text('fixture', encoding='utf-8')
    memory.record_opened(str(file))
    router = SmartRouter(llm_provider=DisabledProvider(), working_memory=memory)
    decision = await router.preview(text)
    assert decision.intent not in {'open_file', 'open_app', 'file_op'}
    if decision.intent is None:
        assert decision.reason_code == 'QUESTION_NOT_COMMAND'
    else:
        assert decision.intent in {'whatsapp_message_read', 'read_whatsapp_messages',
                                   'whatsapp_summary', 'summarize_whatsapp_messages'}
