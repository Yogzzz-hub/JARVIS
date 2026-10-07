"""Local fixture talkback through real synthesis and speaker playback; no command execution."""
import asyncio
import json
from pathlib import Path
from jarvis.core.response.engine import ResponseEngine
from jarvis.core.audio.output.player import AudioOutputManager
from jarvis.core.tts.speech_service import JarvisSpeechResponseService
from jarvis.core.response.coordinator import RESPONSE_LANGUAGE
from jarvis.core.response.whatsapp import render


async def main():
    tts = JarvisSpeechResponseService(keep_warm=False)
    output = AudioOutputManager()
    output.start()
    engine = ResponseEngine(tts_manager=tts, audio_output=output)
    data = dict(unread_count=49, unread_direct_chats=34, groups_unread_count=20,
        sync_state='PARTIAL_SYNC', urgent_messages=[], normal_messages=[])
    summary = render('summarize_whatsapp_messages', data)['spoken']
    latest = render('read_whatsapp_messages', dict(count=1,
        messages=[dict(sender='264398572675321@lid', text='Sollunga anna', timestamp=1728102840)]))['spoken']
    for request_id, text in [('fixture_summary', summary), ('fixture_latest', latest),
                             ('fixture_tamil', 'சரிபார்ப்பு முடிந்தது.')]:
        token = RESPONSE_LANGUAGE.set('TAMIL' if request_id.endswith('tamil') else 'ENGLISH')
        engine.schedule_final(request_id, text)
        RESPONSE_LANGUAGE.reset(token)
        await asyncio.gather(*engine._speech_tasks)
    engine.schedule_final('fixture_summary', summary)
    original_english = tts.piper.synthesize
    def unavailable(text): raise RuntimeError('Controlled fixture Piper failure')
    tts.piper.synthesize = unavailable
    engine.schedule_final('fixture_fallback', 'The local speech fallback is working.')
    await asyncio.gather(*engine._speech_tasks)
    tts.piper.synthesize = original_english
    original_tamil = tts.tamil.synthesize
    tts.tamil.synthesize = unavailable
    token = RESPONSE_LANGUAGE.set('TAMIL')
    engine.schedule_final('fixture_tamil_unavailable', 'சரிபார்ப்பு முடிந்தது.')
    RESPONSE_LANGUAGE.reset(token)
    await asyncio.gather(*engine._speech_tasks)
    tts.tamil.synthesize = original_tamil
    engine.schedule_final('fixture_suppression', 'Do not read an OTP aloud.')
    root = Path('reports/talkback_reliability_evidence'); root.mkdir(exist_ok=True)
    (root/'physical_delivery.json').write_text(json.dumps(dict(source='SYNTHETIC_FIXTURES_REAL_LOCAL_PLAYBACK',
        owner_listening_review=False, counters=engine.delivery.counters(),
        jobs=list(engine.delivery.jobs.values()), hardware_errors=output.total_device_errors),
        indent=2), encoding='utf-8')
    output.stop(); tts.unload()
    print(json.dumps(engine.delivery.counters()))


if __name__ == '__main__': asyncio.run(main())
