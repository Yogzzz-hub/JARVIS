"""Owner-only local acceptance recordings. Never calls CommandService.handle.

Recordings remain evaluation evidence; there is no training/export admission
path. The existing microphone and STT are shared, not opened a second time.
"""
import asyncio
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter_ns
from uuid import uuid4
import wave
from datetime import datetime, timezone
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / 'data/voice_owner_acceptance'


def prompts():
    wake = [('Jarvis', 'normal'), ('Jarvis', 'quiet'), ('Jarvis', 'loud'),
        ('Jarvis open Chrome', 'fast'), ('Jarvis backend status', 'slow'),
        ('Jarvis Gmail open pannu', 'near mic'), ('Jarvis enna time', 'normal distance'),
        ('ஜார்விஸ்', 'natural Tamil pronunciation'), ('Hey Jarvis', 'normal'),
        ('Hey Jarvis open Chrome', 'normal distance')]
    rows = [{'id': f'w{i+1:02}', 'text': text, 'condition': condition, 'kind': 'wake',
        'expected_wake': True, 'wake_family': 'hey' if text.startswith('Hey') else 'bare',
        'language': 'TAMIL' if text == 'ஜார்விஸ்' else 'MIXED' if 'pannu' in text else 'ENGLISH',
        'expected_intent': 'activation' if text in {'Jarvis', 'Hey Jarvis', 'ஜார்விஸ்'} else 'command'}
        for i, (text, condition) in enumerate(wake)]
    rows += [{'id': f'n{i+1:02}', 'text': text, 'condition': 'normal background',
        'kind': 'background', 'expected_wake': False, 'wake_family': 'negative',
        'language': 'BACKGROUND', 'expected_intent': 'none'} for i, text in enumerate([
        'Remain silent', 'Let a fan or normal room noise run',
        'Speak naturally without the wake word', 'Play TV/music without the wake word'])]
    commands = [
        ('ENGLISH', 'Open Chrome', 'OPEN', ['Chrome']),
        ('ENGLISH', 'Is the backend running?', 'CHECK', ['backend']),
        ('ENGLISH', 'Do not delete that file', 'DELETE_NEGATED', ['file']),
        ('TANGLISH', 'Deepa ku file anupu', 'SEND', ['Deepa', 'file']),
        ('TANGLISH', 'Gmail la latest mail check pannu', 'CHECK', ['Gmail']),
        ('TANGLISH', 'athu illa second one', 'CORRECTION_REFERENCE', ['second']),
        ('TAMIL', 'நேரம் என்ன?', 'CHECK', []),
        ('TAMIL', 'அந்த கோப்பை அழிக்க வேண்டாம்', 'DELETE_NEGATED', []),
        ('TAMIL', 'அதை திறக்காதே சுருக்கம் மட்டும் சொல்லு', 'SUMMARIZE_CORRECTION', []),
        ('MIXED', 'FastAPI backend status என்ன', 'CHECK', ['FastAPI', 'backend']),
        ('MIXED', 'Postgres connection check பண்ணு', 'CHECK', ['Postgres']),
        ('MIXED', 'GitHub la Jarvis repo open pannitu 4 mani ku remind pannu',
         'OPEN_CREATE_MULTISTEP', ['GitHub', 'Jarvis', '4'])]
    rows += [{'id': f's{i+1:02}', 'text': text, 'condition': 'normal voice', 'kind': 'stt',
        'expected_wake': False, 'wake_family': 'not_scored', 'language': language,
        'expected_intent': intent, 'critical_entities': entities}
        for i, (language, text, intent, entities) in enumerate(commands)]
    return rows


def wake_metrics(rows, family):
    eligible = [r for r in rows if r['prompt']['kind'] in {'wake', 'background'}
        and (r['prompt']['wake_family'] == family or r['prompt']['kind'] == 'background')]
    if not eligible:
        return {'state': 'OWNER_MIC_BENCHMARK_PENDING', 'TP': None, 'FP': None, 'FN': None, 'TN': None}
    tp = sum(r['prompt']['expected_wake'] and r['wake']['detected'] for r in eligible)
    fn = sum(r['prompt']['expected_wake'] and not r['wake']['detected'] for r in eligible)
    fp = sum(not r['prompt']['expected_wake'] and r['wake']['detected'] for r in eligible)
    tn = sum(not r['prompt']['expected_wake'] and not r['wake']['detected'] for r in eligible)
    latency = [r['wake']['latency_from_energy_onset_ms'] for r in eligible
        if r['prompt']['expected_wake'] and r['wake']['detected']
        and r['wake']['latency_from_energy_onset_ms'] is not None]
    seconds = sum(r['duration_s'] for r in eligible if not r['prompt']['expected_wake'])
    return {'state': 'PARTIAL_OWNER_EVIDENCE', 'TP': int(tp), 'FP': int(fp), 'FN': int(fn), 'TN': int(tn),
        'TPR': tp/(tp+fn) if tp+fn else None, 'FNR': fn/(tp+fn) if tp+fn else None,
        'FPR': fp/(fp+tn) if fp+tn else None,
        'false_activations_per_hour': fp/seconds*3600 if seconds else None,
        'negative_seconds': seconds, 'p50_ms': float(np.percentile(latency, 50)) if latency else None,
        'p95_ms': float(np.percentile(latency, 95)) if latency else None,
        'latency_reference': 'energy onset proxy; not manually labelled wake-phrase end'}


class OwnerVoiceBenchmark:
    def __init__(self, runtime, root=EVIDENCE):
        self.runtime = runtime
        self.root = Path(root)
        self.lock = asyncio.Lock()
        self.active = False

    def rows(self):
        result = []
        for file in sorted(self.root.glob('*/record.json')):
            result.append(json.loads(file.read_text(encoding='utf-8')))
        return result

    def state(self):
        rows = self.rows()
        claims = [json.loads(p.read_text(encoding='utf-8')) for p in self.root.glob('*/claim.json')]
        configurations = sorted({r['configuration_sha256'] for r in rows})
        ratings = {}
        path = self.root / 'listening.jsonl'
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                item = json.loads(line); ratings[item['language']] = item['rating']
        return {'acceptance': 'VOICE_OWNER_TEST_REQUIRED', 'recording': self.active,
            'real_recordings': len(rows), 'prompts': prompts(),
            'completed_ids': [r['prompt']['id'] for r in rows],
            'claimed_ids': [r['prompt']['id'] for r in claims],
            'configuration_versions': configurations,
            'bare': wake_metrics(rows, 'bare'), 'hey': wake_metrics(rows, 'hey'),
            'stt_semantic_pass_rate': None, 'semantic_review': 'INDEPENDENT_REVIEW_REQUIRED',
            'listening_ratings': ratings, 'training_admission': False, 'tools_executed': False}

    async def record(self, sample_id):
        prompt = next((p for p in prompts() if p['id'] == sample_id), None)
        if prompt is None:
            raise ValueError('Unknown prompt')
        if self.lock.locked():
            raise ValueError('A recording is already active')
        voice = getattr(self.runtime, 'voice', None)
        if not voice or not voice.is_running or not voice.stt.is_loaded:
            raise ValueError('Microphone/STT is unavailable')
        if voice.stt_session_lock.locked() or voice._session or voice._command_tasks:
            raise ValueError('Voice is busy; wait until the current interaction ends')
        async with self.lock:
            if sample_id in self.state()['claimed_ids']:
                raise ValueError('This acceptance prompt is already recorded; no overwrite or tuning rerun')
            directory = self.root / uuid4().hex
            directory.mkdir(parents=True)
            # Claim before microphone capture; interrupted takes remain explicit evidence.
            files = ['jarvis/config/jarvis.toml', 'jarvis/core/audio/pipeline.py',
                'jarvis/core/audio/wake/__init__.py', 'jarvis/core/stt/faster_whisper_engine.py',
                'jarvis/core/stt/uncertainty.py', 'jarvis/core/stt/vocabulary.py',
                'jarvis/core/audio/source.py', 'jarvis/core/tts/speech_service.py',
                'jarvis/core/tts/piper_engine.py', 'jarvis/core/stt/quality.py',
                'data/nlp_shadow/shadow_configuration.json',
                'models/wake/hey_jarvis_v0.1.onnx', 'models/whisper/small/download_manifest.json']
            hashes = {p: sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
            config_digest = sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
            (directory/'claim.json').write_text(json.dumps({'prompt': prompt,
                'configuration_sha256': config_digest, 'source_hashes': hashes,
                'created_utc': datetime.now(timezone.utc).isoformat(),
                'training_allowed': False}), encoding='utf-8')
            voice.benchmark_active = True
            voice.input_epoch += 1
            self.active = True
            consumer = voice.hub.register('owner_acceptance', queue_size=400, clean=False)
            acquired_stt = False
            try:
                await voice.stt_session_lock.acquire()
                acquired_stt = True
                self.runtime.service.response.stop_speaking()
                self.runtime.service.response.close_followup_window()
                frames = []
                end = asyncio.get_running_loop().time() + 7
                while asyncio.get_running_loop().time() < end:
                    frame = await asyncio.wait_for(consumer.queue.get(), 2)
                    frames.append(frame)
                audio = b''.join(f.pcm for f in frames)
                with wave.open(str(directory/'microphone.wav'), 'wb') as out:
                    out.setnchannels(1); out.setsampwidth(2); out.setframerate(16000); out.writeframes(audio)
                wake = await asyncio.to_thread(self._wake, frames)
                transcript = None
                production = None
                candidate = None
                if prompt['kind'] != 'background':
                    await voice.stt.start_session(directory.name)
                    await voice.stt.feed_audio(audio)
                    transcript = await voice.stt.finalize()
                    from jarvis.core.audio.pipeline import VoicePipeline
                    clean = VoicePipeline._strip_wake_phrase(transcript.text)
                    if clean:
                        from jarvis.core.language_shadow import production_snapshot, get_language_service
                        production = production_snapshot(await self.runtime.service.router.preview(clean))
                        try:
                            candidate = await get_language_service().benchmark_preview(clean)
                        except Exception as exc:
                            candidate = {'state': 'UNAVAILABLE', 'controls_tools': False,
                                'error_category': type(exc).__name__}
                result = {'prompt': prompt, 'source': 'REAL_OWNER_MICROPHONE',
                    'duration_s': len(audio)/32000, 'audio_sha256': sha256(audio).hexdigest(),
                    'timestamp_ns': perf_counter_ns(), 'configuration_sha256': config_digest,
                    'created_utc': datetime.now(timezone.utc).isoformat(),
                    'wake': wake, 'stt': asdict(transcript) if transcript else None,
                    'production_preview': production, 'candidate': candidate,
                    'clarification': transcript.clarification_required if transcript else None,
                    'semantic_pass': None, 'critical_entities_correct': None,
                    'tools_executed': False, 'training_allowed': False,
                    'dropped_frames': consumer.dropped,
                    'microphone': getattr(voice.hub.source, 'selected_device', None)}
                (directory/'record.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                return result
            finally:
                voice.input_epoch += 1
                voice.hub.discard_before_ns = perf_counter_ns()
                if hasattr(voice.hub, 'ring'):
                    voice.hub.ring.clear()
                voice.ptt_engine._triggered = False
                if acquired_stt:
                    voice.stt_session_lock.release()
                voice.hub.unregister(consumer)
                voice._drain(voice._wake_consumer); voice._drain(voice._vad_consumer)
                voice.wake_engine.reset(); voice.vad.reset()
                voice.benchmark_active = False
                self.active = False

    def _wake(self, frames):
        from jarvis.core.audio.wake import OpenWakeWordEngine
        voice = self.runtime.voice
        # Same already-loaded model, CPU, inference serialized while live voice paused.
        engine = voice.wake_engine
        engine.reset()
        first = frames[0].timestamp_ns
        onset = None
        detection_ms = None
        peak = 0.0
        compute = []
        for frame in frames:
            rms = float(np.sqrt(np.mean((np.frombuffer(frame.pcm, dtype=np.int16).astype(np.float32)/32768)**2)))
            if onset is None and rms > .015:
                onset = (frame.timestamp_ns-first)/1e6
            detected = engine.feed(frame)
            peak = max(peak, engine.last_score)
            if engine.last_inference_ms is not None:
                compute.append(engine.last_inference_ms)
            if detected and detected.detected and detection_ms is None:
                detection_ms = (frame.timestamp_ns-first)/1e6
        captured_start = max(0, detection_ms-voice.preroll_ms) if detection_ms is not None else None
        return {'detected': detection_ms is not None, 'peak_score': peak,
            'threshold': engine.threshold, 'adaptive_threshold': engine.adaptive_threshold,
            'detection_ms': detection_ms, 'speech_energy_start_ms': onset,
            'latency_from_energy_onset_ms': max(0, detection_ms-onset) if detection_ms is not None and onset is not None else None,
            'captured_start_ms': captured_start, 'first_word_clipping': 'INDEPENDENT_AUDIO_REVIEW_REQUIRED',
            'energy_onset_outside_preroll': captured_start > onset if captured_start is not None and onset is not None else None,
            'cpu_inference_p95_ms': float(np.percentile(compute, 95)) if compute else None}

    def rate(self, language, rating):
        if language not in {'ENGLISH', 'TANGLISH', 'TAMIL', 'MIXED'} or rating not in {'CLEAR', 'OK', 'BAD'}:
            raise ValueError('Invalid listening rating')
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root/'listening.jsonl').open('a', encoding='utf-8') as out:
            out.write(json.dumps({'language': language, 'rating': rating,
                'timestamp_ns': perf_counter_ns(), 'created_utc': datetime.now(timezone.utc).isoformat(),
                'reviewer': 'LOCAL_OWNER'})+'\n')

