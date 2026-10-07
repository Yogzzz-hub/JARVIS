from types import SimpleNamespace
from unittest.mock import Mock,AsyncMock
import pytest
from jarvis.core.response.whatsapp import render
from jarvis.core.commands.service import CommandService
from jarvis.tools.base import ToolResult
from jarvis.integrations.whatsapp.ai import WhatsAppAI,ContextualReplyUnavailable

@pytest.mark.parametrize('language',['ENGLISH','TANGLISH','TAMIL'])
def test_unread_names_only_latest_unique_all_unread_not_just_urgent(language):
    result=render('summarize_whatsapp_messages',dict(unread_count=9,sync_state='READY',unread_chats=[
        dict(chat_id='1@s.whatsapp.net',name='Arun',timestamp=10),
        dict(chat_id='2@s.whatsapp.net',name='Naveen',timestamp=20)],
        urgent_messages=[dict(sender='Arun',text='secret original message',timestamp=10)]),language)
    assert 'Naveen' in result['spoken'] and 'Arun' in result['spoken']
    assert result['spoken'].index('Naveen')<result['spoken'].index('Arun')
    assert 'secret original' not in result['spoken']

def test_names_select_read_then_reply_exact_selected_chat_and_no_fuzzy_guess():
    service=CommandService.__new__(CommandService)
    task=SimpleNamespace(source='test',chat_id=None)
    service._remember_whatsapp_conversation(task,ToolResult(success=True,tool_name='summarize_whatsapp_messages',data=dict(unread_chats=[
        dict(chat_id='arun@s.whatsapp.net',name='Arun',is_group=False)])))
    assert service._whatsapp_contact_followup('Arnu','local') is None
    assert service._whatsapp_contact_followup('reply','local').lane=='CLARIFY'
    selected=service._whatsapp_contact_followup('Arun','local')
    assert selected.intent=='read_whatsapp_messages' and selected.slots==dict(sender='arun@s.whatsapp.net',filter='all',limit=1)
    service._remember_whatsapp_conversation(task,ToolResult(success=True,tool_name='read_whatsapp_messages',data=dict(
        filter='all',messages=[dict(chat_id='arun@s.whatsapp.net',sender='Arun',text='Which module needs debugging?')],count=1)))
    reply=service._whatsapp_contact_followup('reply','local')
    assert reply.intent=='reply_whatsapp_message' and reply.slots['recipient']=='arun@s.whatsapp.net'
    assert service._whatsapp_contact_followup('Arun','other') is None

def test_named_read_reads_body_while_unread_discovery_reads_name_only():
    data=dict(count=1,filter='unread',messages=[dict(chat_id='arun@s.whatsapp.net',sender='Arun',text='Which module needs debugging?')])
    assert 'Which module' not in render('read_whatsapp_messages',data)['spoken']
    data.update(filter='all',selected_sender='arun@s.whatsapp.net')
    assert 'Which module needs debugging' in render('read_whatsapp_messages',data)['spoken']

def test_selected_contact_is_isolated_by_actual_request_channel_and_saved_name():
    service=CommandService.__new__(CommandService)
    service._request_channels={'request-one':'whatsapp:owner-one'}
    resolver=SimpleNamespace(resolve=Mock(return_value=(SimpleNamespace(display_name='Saved Arun'),False,None)))
    task=SimpleNamespace(source='whatsapp',request_id='request-one')
    service._remember_whatsapp_conversation(task,ToolResult(success=True,tool_name='summarize_whatsapp_messages',data=dict(
        unread_chats=[dict(chat_id='arun@s.whatsapp.net',name='Push name')])),resolver)
    assert service._whatsapp_contact_followup('Saved Arun','whatsapp:owner-one').slots['sender']=='arun@s.whatsapp.net'
    assert service._whatsapp_contact_followup('Saved Arun','local') is None
    assert service._whatsapp_contact_followup('Saved Arun','whatsapp:owner-two') is None

@pytest.mark.asyncio
@pytest.mark.parametrize('answer',['Got your message.','',"I'll finish it tomorrow."])
async def test_no_canned_or_unsupported_draft_no_static_fallback(monkeypatch,answer):
    msg=SimpleNamespace(chat_id='arun@s.whatsapp.net',sender_display_name='Arun',sender_id='arun@s.whatsapp.net',message_id='m1',text='When can you finish?')
    client=SimpleNamespace(chat_json=AsyncMock(return_value={'message':answer}))
    ai=WhatsAppAI(client=client,inbox=SimpleNamespace(find_latest_incoming=Mock(return_value=msg)))
    monkeypatch.setattr(ai,'_history_lines',lambda *a:['Arun: When can you finish?'])
    monkeypatch.setattr(ai,'style_hint',lambda *a:'')
    validator=SimpleNamespace(validate=Mock(return_value=SimpleNamespace(passed=False)))
    monkeypatch.setattr('jarvis.integrations.whatsapp.intelligence.engine.get_intelligence',lambda *a:SimpleNamespace(context=lambda *a:object(),validator=validator))
    with pytest.raises(ContextualReplyUnavailable): await ai.draft_reply('Arun')
    assert client.chat_json.call_count==1

@pytest.mark.asyncio
async def test_context_reply_draft_uses_actual_history_and_owner_evidence(monkeypatch):
    msg=SimpleNamespace(chat_id='arun@s.whatsapp.net',sender_display_name='Arun',sender_id='arun@s.whatsapp.net',message_id='m1',text='Which module needs debugging?')
    client=SimpleNamespace(chat_json=AsyncMock(return_value={'message':'Which error are you seeing in the backend module?'}))
    ai=WhatsAppAI(client=client,inbox=SimpleNamespace(find_latest_incoming=Mock(return_value=msg)))
    monkeypatch.setattr(ai,'_history_lines',lambda *a:['Owner: The backend has an error.','Arun: Which module needs debugging?'])
    monkeypatch.setattr(ai,'style_hint',lambda *a:'')
    validator=SimpleNamespace(validate=Mock(return_value=SimpleNamespace(passed=True)))
    monkeypatch.setattr('jarvis.integrations.whatsapp.intelligence.engine.get_intelligence',lambda *a:SimpleNamespace(context=lambda *a:object(),validator=validator))
    result=await ai.draft_reply('Arun')
    assert 'backend module' in result.text and result.recipient_jid=='arun@s.whatsapp.net'
    assert 'Owner: The backend has an error.' in client.chat_json.call_args.args[0][0]['content']
    assert validator.validate.call_args.args[2]==''
