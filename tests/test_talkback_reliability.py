import asyncio
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from jarvis.core.response.whatsapp import render, IDENTIFIER, display_name
from jarvis.core.response.delivery import SpeechDelivery
from jarvis.ui.connection_health import ConnectionHealth


def test_whatsapp_summary_has_safe_names_short_speech_and_structured_visual():
    data = dict(unread_count=49, unread_direct_chats=34, groups_unread_count=20,
        sync_state='PARTIAL_SYNC', urgent_messages=[dict(sender='264398572675321',
        text='Sollunga anna', timestamp=1), dict(sender='Sanjana Makesh', text='Hm dha', timestamp=2)], normal_messages=[])
    result = render('summarize_whatsapp_messages', data)
    assert not IDENTIFIER.search(result['visual']+result['spoken'])
    assert 'one contact' in result['visual'] and 'Sanjana Makesh' in result['visual']
    assert len(result['spoken'].split()) <= 55 and '\nImportant:' in result['visual']
    assert result['spoken'].count('Sync') == 1
    for language in ('TANGLISH', 'TAMIL', 'MIXED'):
        localized = render('summarize_whatsapp_messages', data, language)
        assert '49' in localized['spoken'] and not IDENTIFIER.search(localized['spoken'])


def test_latest_message_uses_local_time_unknown_name_and_safe_preview():
    data = dict(count=1, messages=[dict(sender='264398572675321@lid', timestamp=1728102840, text='Sollunga anna')])
    result = render('read_whatsapp_messages', data)
    assert result['spoken'].startswith('Your latest WhatsApp message is from one contact at ')
    assert 'Standard Time' not in result['spoken'] and not IDENTIFIER.search(result['spoken'])
    data['messages'][0]['text'] = 'Your OTP is 123456'
    assert '123456' not in render('read_whatsapp_messages', data)['spoken']


def test_saved_contact_takes_priority_without_fuzzy_target_guessing():
    resolver = SimpleNamespace(resolve=Mock(return_value=(SimpleNamespace(display_name='Arun'), [], None)))
    assert display_name(dict(sender='Push name', sender_id='1234567890@lid'), resolver) == 'Arun'
    resolver.resolve.assert_called_once_with('1234567890@lid')


def test_brief_disconnect_and_optional_failure_do_not_mean_offline():
    now = [0.0]
    health = ConnectionHealth(clock=lambda: now[0])
    assert health.connected() == 'ONLINE'
    assert health.disconnected('socket dropped', True) == 'RECONNECTING'
    now[0] = 1
    assert health.connected() == 'ONLINE'
    assert health.disconnected('backend unreachable', False) == 'RECONNECTING'
    now[0] = 12
    assert health.disconnected('backend unreachable', False) == 'OFFLINE'


@pytest.mark.asyncio
async def test_delivery_tracks_actual_mock_playback_and_suppresses_only_delivered_duplicate():
    from jarvis.core.response.engine import ResponseEngine
    from jarvis.core.audio.output.player import AudioOutputManager
    from jarvis.core.tts.base import TTSChunk
    class TTS:
        sample_rate = 22050
        complete_sentence_chunks = True
        async def stream(self, text):
            for index in range(2):
                yield TTSChunk(pcm=b'\x01\x00'*100, sample_rate=22050, is_final=index==1), 'fixture'
    output = AudioOutputManager(mock_output=True); output.start()
    engine = ResponseEngine(tts_manager=TTS(), audio_output=output)
    engine.schedule_final('safe_fixture', 'First sentence. Second sentence.')
    await asyncio.gather(*engine._speech_tasks)
    job = engine.delivery.snapshot()
    assert job['state'] == 'DELIVERED' and job['playback_completed']
    assert output.total_played == 2
    engine.schedule_final('safe_fixture', 'Repeated sentence.')
    assert engine.delivery.snapshot()['duplicate_suppressions'] == 1
    output.stop()


@pytest.mark.asyncio
async def test_failed_undelivered_job_can_retry_but_partial_delivery_cannot():
    delivery = SpeechDelivery()
    job = delivery.begin('fixture', 'TAMIL')
    delivery.update(job, 'FAILED', failure_reason='TTS_UNAVAILABLE_FOR_LANGUAGE')
    retry = delivery.begin('fixture', 'TAMIL')
    assert retry is not None
    delivery.update(retry, 'FAILED', playback_started=True, failure_reason='partial')
    assert delivery.begin('fixture', 'TAMIL') is None


@pytest.mark.asyncio
async def test_playback_initialization_watchdog_cancels_only_stuck_job():
    from jarvis.core.response.models import SpokenResponse, ResponseType
    delivery = SpeechDelivery(); job = delivery.begin('stuck', 'ENGLISH')
    response = SpokenResponse(text='Fixture', type=ResponseType.FINAL, request_id='stuck', audio_bytes=b'\0\0')
    output = SimpleNamespace(cancel_request=Mock())
    await delivery.monitor(job, [response], output, timeout=.02)
    assert job['state'] == 'FAILED' and job['failure_reason'] == 'PLAYBACK_OR_QUEUE_TIMEOUT'
    output.cancel_request.assert_called_once_with('stuck')


@pytest.mark.asyncio
async def test_queue_watchdog_allows_known_prior_audio_then_observes_delivery():
    from jarvis.core.audio.output.player import AudioOutputManager
    from jarvis.core.response.models import SpokenResponse, ResponseType
    output = AudioOutputManager(mock_output=True)
    first = SpokenResponse(text='Prior audio', type=ResponseType.FINAL, request_id='first',
        audio_bytes=b'\0\0'*2205, sample_rate=22050)
    second = SpokenResponse(text='Next audio', type=ResponseType.FINAL, request_id='second',
        audio_bytes=b'\0\0'*220, sample_rate=22050)
    output.play(first); output.play(second)
    assert output.queue_wait_seconds(second) >= .1
    delivery = SpeechDelivery(); job = delivery.begin('second', 'ENGLISH')
    output.start()
    try:
        await delivery.monitor(job, [second], output, timeout=.04)
        assert job['state']=='DELIVERED' and job['playback_completed']
    finally:
        output.stop()


def test_gateway_pongs_and_health_survive_unavailable_optional_services():
    from fastapi.testclient import TestClient
    from jarvis.core.gateway.app import create_app
    from jarvis.core.events.bus import EventBus
    runtime = SimpleNamespace(ready=True, registry=SimpleNamespace(list=lambda: []),
        writer=SimpleNamespace(error=None, dropped=0), bus=EventBus(),
        metrics=SimpleNamespace(dropped=0), logs=SimpleNamespace(handler=SimpleNamespace(dropped=0)),
        config=SimpleNamespace(features=SimpleNamespace(voice=False)), voice=None,
        whatsapp_service=None, llm=None, service=SimpleNamespace(response=SimpleNamespace()))
    app = create_app(runtime)
    client = TestClient(app)
    assert client.get('/health').json()['status'] == 'ready'
    for _ in range(2):
        with client.websocket_connect('/ws') as socket:
            socket.send_json(dict(version=1, type='ping', request_id='fixture_ping'))
            assert socket.receive_json()['type'] == 'pong'


@pytest.mark.asyncio
async def test_synthesis_worker_does_not_block_async_heartbeat():
    import time
    ticks = []
    async def heartbeat():
        for _ in range(8):
            ticks.append(time.monotonic()); await asyncio.sleep(.01)
    await asyncio.gather(asyncio.to_thread(time.sleep, .12), heartbeat())
    assert len(ticks) == 8 and max(b-a for a,b in zip(ticks,ticks[1:])) < .1


def test_current_chat_snapshot_uses_timestamp_not_reply_priority(tmp_path):
    import sqlite3
    from jarvis.core.llm.assistant import Assistant
    path = tmp_path/'fixture.db'
    def connection():
        conn = sqlite3.connect(path); conn.row_factory = sqlite3.Row; return conn
    with connection() as conn:
        conn.execute('CREATE TABLE whatsapp_messages (chat_id TEXT, is_from_me INT, timestamp REAL, sender TEXT, text TEXT, needs_reply INT)')
        conn.executemany('INSERT INTO whatsapp_messages VALUES (?,0,?,?,?,?)', [
            ('1@lid', 100, 'Earlier', 'Old message', 1), ('2@lid', 200, 'Arun', 'New message', 0)])
    inbox = SimpleNamespace(_get_conn=connection, _row_to_msg=lambda row: SimpleNamespace(to_dict=lambda: dict(row)), sync_state=lambda:'READY')
    registry = SimpleNamespace(contains=lambda name:name=='read_whatsapp_messages', get=lambda name:SimpleNamespace(inbox=inbox))
    facts = Assistant(registry=registry)._whatsapp_snapshot('What is my latest WhatsApp message?')
    assert len(facts)==1 and 'New message' in facts[0]['snippet'] and 'Old message' not in facts[0]['snippet']


@pytest.mark.asyncio
async def test_partial_stream_failure_is_recorded_and_never_replayed():
    from unittest.mock import AsyncMock
    from jarvis.core.pulse.engine import SpeechStream
    delivery = SpeechDelivery()
    service = SimpleNamespace(delivery=delivery)
    class Owner:
        def schedule_final(self, *args): pass
    owner = Owner(); owner.delivery = delivery
    response = SimpleNamespace(source='fixture')
    engine = SimpleNamespace(final_delivery=owner.schedule_final, _speech_tasks=set(),
        audio_output=SimpleNamespace(_cancel_ns=0),
        scheduler=SimpleNamespace(cancel_race_timer=Mock()),
        _speak_chunk=AsyncMock(side_effect=[response, RuntimeError('second chunk failed')]),
        end_of_answer=Mock())
    async def played(job, responses, output):
        delivery.update(job, 'DELIVERED', playback_started=True, playback_completed=True)
    delivery.monitor = played
    stream = SpeechStream(engine, 'partial_fixture')
    stream.push('First sentence.'); stream.push('Second sentence.'); stream.close()
    await stream.task
    assert stream.spoke and stream.job['state']=='FAILED'
    assert stream.job['failure_reason']=='second chunk failed'
    assert not stream.job['playback_completed']
    assert delivery.begin('partial_fixture', 'ENGLISH') is None
