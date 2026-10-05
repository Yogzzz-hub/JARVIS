import json

from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
from jarvis.integrations.whatsapp.incoming_trace import trace_generation, trace_incoming
from jarvis.integrations.whatsapp.models import NormalizedWhatsAppMessage


def test_metadata_trace_and_sqlite_dedupe_exclude_private_body(tmp_path, monkeypatch):
    log = tmp_path / 'incoming.jsonl'
    monkeypatch.setenv('JARVIS_WHATSAPP_TRACE_PYTHON', str(log))
    inbox = WhatsAppInbox(tmp_path / 'inbox.db')
    message = NormalizedWhatsAppMessage(message_id='probe-1', chat_id='123@lid', sender_id='123@lid',
        timestamp='2026-10-03T15:00:00Z', text='private body must stay out of trace')
    token = trace_generation.set('generation-1')
    try:
        trace_incoming(stage='python_websocket_receive', event_type='incoming_message',
                       message_id=message.message_id, chat_jid=message.chat_id,
                       text=message.text, python_receive_result='RECEIVED')
        inbox.add_message(message)
        inbox.add_message(message)
    finally:
        trace_generation.reset(token)
    rows = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
    assert [r['sqlite_result'] for r in rows if r['stage'] == 'sqlite'] == ['INSERTED', 'DEDUPE_EXISTING']
    assert all(r['generation'] == 'generation-1' for r in rows)
    assert 'private body' not in log.read_text(encoding='utf-8')
    with inbox._get_conn() as conn:
        assert conn.execute('select count(*) from whatsapp_messages where message_id=?', ('probe-1',)).fetchone()[0] == 1
        assert conn.execute('pragma integrity_check').fetchone()[0] == 'ok'
