"""Functional synthetic checks, explicitly separate from owner acceptance."""
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
from time import perf_counter
import wave
import psutil
from jarvis.core.tts.speech_service import JarvisSpeechResponseService
from jarvis.core.stt.faster_whisper_engine import FasterWhisperEngine
from jarvis.core.stt.vocabulary import JarvisSpeechVocabulary


async def main():
    out = Path('reports/voice_daily_evidence'); out.mkdir(parents=True, exist_ok=True)
    tts = JarvisSpeechResponseService(keep_warm=True)
    samples = [('ENGLISH', 'Checking FastAPI. Backend is running.'),
        ('TANGLISH', 'Backend running bro. API connection iruku.'),
        ('TAMIL', 'சரிபார்க்கிறேன். சரிபார்ப்பு முடிந்தது.'),
        ('MIXED', 'FastAPI backend இயங்குகிறது. Postgres connection okay.')]
    cold = []
    for language in ['ENGLISH', 'TAMIL']:
        row = next(r for r in samples if r[0] == language)
        start = perf_counter(); pcm, backend = tts.synthesize(row[1], language)
        cold.append({'language': language, 'first_complete_pcm_ms': (perf_counter()-start)*1000,
            'bytes': len(pcm), 'backend': backend,
            'model_load_ms': tts.piper.last_load_ms if language == 'ENGLISH' else tts.tamil.last_load_ms})
    start = perf_counter(); tts.warm_up()
    warmup = {'elapsed_ms': (perf_counter()-start)*1000, **tts.warmup_metrics}
    rows = []
    from jarvis.core.response.coordinator import RESPONSE_LANGUAGE
    for language, text in samples:
        token = RESPONSE_LANGUAGE.set(language)
        try:
            start = perf_counter(); first_ms = None; chunks = []
            async for chunk, backend in tts.stream(text):
                if first_ms is None: first_ms = (perf_counter()-start)*1000
                chunks.append(chunk.pcm)
            rows.append({'language': language, 'first_sentence_pcm_ms': first_ms,
                'total_ms': (perf_counter()-start)*1000, 'chunks': len(chunks),
                'bytes': sum(len(c) for c in chunks), 'owner_rating': 'PENDING'})
            with wave.open(str(out/(language.lower()+'.wav')), 'wb') as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(22050); wav.writeframes(b''.join(chunks))
        finally:
            RESPONSE_LANGUAGE.reset(token)
    # Real Windows fallback call, without sending a tool command.
    original = tts.piper.synthesize
    tts.piper.synthesize = lambda text: (_ for _ in ()).throw(RuntimeError('Controlled fallback test'))
    pcm, backend = tts.synthesize('Fallback voice check.', 'ENGLISH')
    tts.piper.synthesize = original
    fallback = {'bytes': len(pcm), 'backend': backend, 'functional': bool(pcm)}
    tts_ram = psutil.Process().memory_info().rss/1048576
    tts.unload()
    stt = FasterWhisperEngine(model='models/whisper/small', device='cuda',
        compute_type='int8_float16', language=None,
        initial_prompt=JarvisSpeechVocabulary.from_metadata(apps=['Chrome'], contacts=[]).generate_prompt())
    await stt.load()
    transcripts = []
    # Existing generated samples, never presented as microphone recordings.
    for language, filename in [('ENGLISH', 'english'), ('TANGLISH', 'tanglish'),
            ('TAMIL', 'tamil'), ('MIXED', 'mixed_tamil_english')]:
        from scipy.signal import resample_poly
        import numpy as np
        import math
        with wave.open(str(Path('reports/integration_evidence')/(filename+'.wav')), 'rb') as wav:
            rate = wav.getframerate(); pcm = wav.readframes(wav.getnframes())
        x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        gcd = math.gcd(rate,16000)
        x = resample_poly(x,16000//gcd,rate//gcd).clip(-32768,32767).astype(np.int16)
        await stt.start_session(language); await stt.feed_audio(x.tobytes())
        transcripts.append({'expected_language': language, 'source': 'SYNTHETIC_TTS',
            'transcript': asdict(await stt.finalize()), 'semantic_accuracy': 'NOT_SCORED'})
    result = {'source': 'FUNCTIONAL_SYNTHETIC_ONLY', 'cold': cold, 'warmup': warmup,
        'talkback': rows, 'fallback': fallback, 'tts_loaded_ram_mib': tts_ram,
        'stt': transcripts, 'stt_process_ram_mib': psutil.Process().memory_info().rss/1048576,
        'owner_microphone': 'OWNER_MIC_BENCHMARK_PENDING', 'owner_listening': 'PENDING'}
    (out/'functional.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    await stt.unload()
    print('Functional evidence saved; owner acceptance remains pending.')


if __name__ == '__main__': asyncio.run(main())
