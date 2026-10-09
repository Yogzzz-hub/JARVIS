"""Local synthetic load probe: no microphone, execution, training, or evaluation-set reads."""
import asyncio
import json
from pathlib import Path
from time import perf_counter
import urllib.request
import numpy as np
import websockets


def request(path, body=None):
    raw = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request('http://127.0.0.1:8765'+path, data=raw,
                                 headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=15))


async def main():
    from jarvis.core.stt.faster_whisper_engine import FasterWhisperEngine
    engine = FasterWhisperEngine(model='models/whisper/small', device='cpu', compute_type='int8')
    async def stt():
        started = perf_counter()
        await engine.load()
        # Deliberately synthetic audio: tests compute isolation, not recognition quality.
        audio = (.04*np.sin(2*np.pi*440*np.arange(16000*8)/16000)).astype(np.float32)
        def infer():
            counts = []
            for _ in range(3):
                segments, _ = engine._model.transcribe(audio, language='en', beam_size=5,
                    vad_filter=False, condition_on_previous_text=False)
                counts.append(sum(1 for _ in segments))
            return counts
        counts = await asyncio.to_thread(infer)
        await engine.unload()
        return dict(calls=3, elapsed_ms=(perf_counter()-started)*1000, segment_counts=counts,
                    model='local small', device='cpu', interpretation='synthetic load only')
    before = await asyncio.to_thread(request, '/dashboard/nlp/shadow')
    stt_task = asyncio.create_task(stt())
    accepted = []
    latency = []
    async with websockets.connect('ws://127.0.0.1:8765/ws', ping_interval=None) as socket:
        for index in range(80):
            if index < 8:
                result = await asyncio.to_thread(request, '/dashboard/nlp/understand',
                    dict(text=f'Synthetic load fixture {index}: inspect Docker and FastAPI project status.',
                         mode='automation_builder'))
                accepted.append(result['queued'])
            started = perf_counter()
            rid = 'inference_load_ping_'+str(index)
            await socket.send(json.dumps(dict(version=1, type='ping', request_id=rid)))
            while True:
                event = json.loads(await asyncio.wait_for(socket.recv(), 5))
                if event.get('type')=='pong' and event.get('request_id')==rid: break
            latency.append((perf_counter()-started)*1000)
            await asyncio.sleep(.25)
    stt_result = await asyncio.wait_for(stt_task, 60)
    after = await asyncio.to_thread(request, '/dashboard/nlp/shadow')
    evidence = dict(stt=stt_result, nlp_queued=sum(accepted),
        nlp_counters_before=before['counters'], nlp_counters_after=after['counters'],
        heartbeat_samples=len(latency), heartbeat_p50_ms=float(np.percentile(latency, 50)),
        heartbeat_p95_ms=float(np.percentile(latency, 95)), heartbeat_max_ms=max(latency),
        backend_health=(await asyncio.to_thread(request, '/health'))['status'],
        controls_tools=False, owner_recordings=False)
    Path('reports/talkback_reliability_evidence/inference_stress.json').write_text(
        json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence))


if __name__ == '__main__': asyncio.run(main())
