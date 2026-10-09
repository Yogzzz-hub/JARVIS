"""Real local audio synthesis + synthetic wake/STT evidence, never owner recordings."""
import asyncio
import hashlib
import json
from pathlib import Path
from time import perf_counter
import wave
import numpy as np
from jarvis.core.tts.speech_service import JarvisSpeechResponseService
from jarvis.core.audio.wake import OpenWakeWordEngine
from jarvis.core.audio.frame import AudioFrame
from jarvis.core.stt.faster_whisper_engine import FasterWhisperEngine

OUT = Path('reports/integration_evidence')


def wav_save(path, pcm, rate):
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(rate); f.writeframes(pcm)


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tts = JarvisSpeechResponseService(keep_warm=False)
    samples = [('ENGLISH', 'Backend is running. API health is okay.'),
        ('TANGLISH', 'Backend running bro. API connection iruku.'),
        ('TAMIL', 'வணக்கம். சரிபார்ப்பு முடிந்தது.'),
        ('MIXED_TAMIL_ENGLISH', 'FastAPI backend இயங்குகிறது. Postgres connection okay.')]
    records = []
    for selected, text in samples:
        start = perf_counter()
        pcm, backend = tts.synthesize(text, selected)
        path = OUT / (selected.lower() + '.wav')
        wav_save(path, pcm, tts.sample_rate)
        played = False
        if pcm:
            import winsound
            await asyncio.to_thread(winsound.PlaySound, str(path.resolve()), winsound.SND_FILENAME)
            played = True
        records.append({'language': selected, 'text': text, 'unicode_preserved': True,
            'audio_bytes': len(pcm), 'backend': backend, 'sample_rate': tts.sample_rate,
            'first_pcm_ms': tts.last_synthesis_ms, 'playback_api_completed': played,
            'wav_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'naturalness': 'OWNER_LISTENING_REVIEW_REQUIRED', 'clipping': 'NOT_LISTENING_VALIDATED'})
    (OUT/'talkback.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    print('Talkback WAV files synthesized and playback calls completed.', flush=True)

    # Resampled synthetic speech is explicitly separate from microphone acceptance.
    stimuli = [('Jarvis', True), ('Hey Jarvis', True), ('Jarvis open Chrome', True),
        ('Open Chrome please', False), ('Backend is running', False), ('Good morning everyone', False)]
    audio = []
    for text, positive in stimuli:
        pcm, _ = tts.synthesize(text, 'ENGLISH')
        samples = np.frombuffer(pcm,dtype=np.int16).astype(float)
        positions = np.linspace(0,len(samples)-1,round(len(samples)*16000/tts.sample_rate))
        audio.append((text,positive,np.interp(positions,np.arange(len(samples)),samples)))
    wake = OpenWakeWordEngine(model_path='models/wake/hey_jarvis_v0.1.onnx',threshold=.5)
    started = perf_counter(); wake._ensure_loaded(); load_ms=(perf_counter()-started)*1000
    rng = np.random.default_rng(20261005)
    conditions = ['quiet','fan_synthetic','music_synthetic','far_synthetic','fast_synthetic','slow_synthetic']
    rows=[]
    for condition in conditions:
        for text,positive,speech in audio:
            x=speech.copy()
            if condition == 'fan_synthetic': x += rng.normal(0,350,len(x))
            if condition == 'music_synthetic':
                t=np.arange(len(x))/16000; x += 400*np.sin(2*np.pi*220*t)+300*np.sin(2*np.pi*330*t)
            if condition == 'far_synthetic': x *= .25
            if condition in {'fast_synthetic','slow_synthetic'}:
                factor=.8 if condition=='fast_synthetic' else 1.2
                x=np.interp(np.linspace(0,len(x)-1,round(len(x)*factor)),np.arange(len(x)),x)
            x=np.concatenate([np.zeros(16000),x,np.zeros(16000)])
            x=np.clip(x,-32768,32767).astype(np.int16)
            wake.reset(); wake.noise_floor=0; wake.recent_false_triggers=0; wake.adaptive_threshold=wake.base_threshold
            detection_ms=None; start=perf_counter()
            for offset in range(0,len(x),1280):
                chunk=x[offset:offset+1280]
                frame=AudioFrame.from_float32((chunk.astype(float)/32768).tolist(),sequence_id=offset//1280)
                detection=wake.feed(frame)
                if detection and detection.detected and detection_ms is None:
                    detection_ms=(offset+len(chunk))/16-1000
            rows.append({'condition':condition,'text':text,'positive':positive,'detected':detection_ms is not None,
                'synthetic_onset_detection_ms':detection_ms,'processing_ms':(perf_counter()-start)*1000})
    summaries={}
    for condition in conditions:
        selected=[r for r in rows if r['condition']==condition]
        tp=sum(r['positive'] and r['detected'] for r in selected); fn=sum(r['positive'] and not r['detected'] for r in selected)
        fp=sum(not r['positive'] and r['detected'] for r in selected); tn=sum(not r['positive'] and not r['detected'] for r in selected)
        lat=[r['synthetic_onset_detection_ms'] for r in selected if r['positive'] and r['detected']]
        summaries[condition]={'tp':tp,'fn':fn,'fp':fp,'tn':tn,'tpr':tp/(tp+fn),'fpr':fp/(fp+tn),
            'fnr':fn/(tp+fn),'median_onset_ms':float(np.median(lat)) if lat else None,
            'p95_onset_ms':float(np.percentile(lat,95)) if lat else None}
    (OUT/'wake_synthetic.json').write_text(json.dumps({'evidence':'TTS_SYNTHETIC_NOT_MICROPHONE',
        'model_loaded':wake._loaded,'startup_ms':load_ms,'threshold':wake.threshold,
        'conditions':summaries,'cases':rows},indent=2)+'\n')
    wake.close(); tts.unload()
    print('Synthetic wake benchmark completed; not real microphone acceptance.',flush=True)

    stt=FasterWhisperEngine(model='auto',device='auto',language=None,thanglish=True)
    start=perf_counter(); await stt.load(); load_ms=(perf_counter()-start)*1000
    rows=[]
    for record in records:
        with wave.open(str(OUT/(record['language'].lower()+'.wav')),'rb') as f:
            rate=f.getframerate(); pcm=f.readframes(f.getnframes())
        x=np.frombuffer(pcm,dtype=np.int16)
        converted=np.interp(np.linspace(0,len(x)-1,round(len(x)*16000/rate)),np.arange(len(x)),x).astype(np.int16).tobytes()
        await stt.start_session('synthetic_'+record['language'])
        await stt.feed_audio(converted)
        start=perf_counter(); final=await stt.finalize(); elapsed=(perf_counter()-start)*1000
        rows.append({'input_language':record['language'],'transcript':final.text,'detected_language':final.language,
            'stt_final_ms':elapsed,'partial_latency_ms':None,'evidence':'LOCAL_TTS_SYNTHETIC_NOT_OWNER_SPEECH'})
    (OUT/'stt_synthetic.json').write_text(json.dumps({'startup_ms':load_ms,'model':stt.model_name_str,
        'device':stt._device_actual,'cases':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    await stt.unload()
    print('Synthetic STT round trip completed.',flush=True)


if __name__ == '__main__':
    asyncio.run(main())
