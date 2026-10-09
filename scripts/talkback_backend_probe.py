"""Read-only owner acceptance probes; persist only counts/states, not private message bodies."""
import asyncio
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4
import urllib.request
import websockets
import numpy as np
from jarvis.core.response.whatsapp import IDENTIFIER


def request(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request('http://127.0.0.1:8765'+path, data=data,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=50) as response:
        return json.loads(response.read())


async def main():
    observations = []
    results = []
    playback_events = []
    def record(event):
        if event.get('event') in {'tts.started', 'tts.stopped'}:
            payload = event.get('payload') or {}
            playback_events.append(dict(request_id=event.get('request_id'), event=event['event'],
                response_id=payload.get('response_id'), status=payload.get('status')))
    async def command(text, label):
        request_id = 'talkback_probe_'+uuid4().hex
        try:
            result = await asyncio.to_thread(request, '/command', dict(text=text, source='voice', request_id=request_id,
                metadata={'response_language': 'ENGLISH'}))
            visual = result.get('message', '')
            spoken = result.get('spoken_message') or visual
            results.append(dict(label=label, request_id=request_id, state=result.get('state'),
                tool=result.get('tool_result', {}).get('tool_name') if result.get('tool_result') else None,
                verified=(result.get('verification') or {}).get('verified'),
                raw_identifier_leak=bool(IDENTIFIER.search(visual+' '+spoken)),
                spoken_words=len(spoken.split()), visual_lines=len(visual.splitlines())))
        except Exception as exc:
            results.append(dict(label=label, request_id=request_id, error_category=type(exc).__name__))
    async with websockets.connect('ws://127.0.0.1:8765/ws', ping_interval=None) as socket:
        jobs = [asyncio.create_task(command('summarize my whatsapp', 'SUMMARY')),
                asyncio.create_task(command('what is the latest msg i got in whatsapp', 'LATEST'))]
        for index in range(50):
            started = perf_counter()
            request_id = 'probe_ping_'+str(index)
            await socket.send(json.dumps(dict(version=1, type='ping', request_id=request_id)))
            while True:
                event = json.loads(await asyncio.wait_for(socket.recv(), 5))
                record(event)
                if event.get('type') == 'pong' and event.get('request_id') == request_id: break
            observations.append((perf_counter()-started)*1000)
            await asyncio.sleep(.1)
        await asyncio.gather(*jobs)
        # HTTP completion does not prove speech delivery. Retain the transport
        # until the separately monitored final playback completes.
        playback_deadline = perf_counter() + 45
        while perf_counter() < playback_deadline:
            status = await asyncio.to_thread(request, '/dashboard/voice-language')
            job = status['tts'].get('latest_speech_job') or {}
            if job.get('state') in {'DELIVERED', 'FAILED', 'CANCELLED'}: break
            try:
                event = json.loads(await asyncio.wait_for(socket.recv(), 1))
                record(event)
            except asyncio.TimeoutError:
                pass
        # Drain completion events already in flight without replaying commands.
        while True:
            try: record(json.loads(await asyncio.wait_for(socket.recv(), .2)))
            except asyncio.TimeoutError: break
    # Reopen the transport; never replay a command to recover a response.
    async with websockets.connect('ws://127.0.0.1:8765/ws', ping_interval=None) as socket:
        await socket.send(json.dumps(dict(version=1, type='ping', request_id='probe_reconnect')))
        while True:
            event = json.loads(await asyncio.wait_for(socket.recv(), 5))
            if event.get('type') == 'pong': break
    health = await asyncio.to_thread(request, '/health')
    evidence = dict(source='LIVE_LOCAL_BACKEND_READ_ONLY_OWNER_PROBES', commands=results,
        heartbeat_samples=len(observations), heartbeat_p50_ms=float(np.percentile(observations, 50)),
        heartbeat_p95_ms=float(np.percentile(observations, 95)), heartbeat_max_ms=max(observations),
        reconnect_pong=True, backend_health=health['status'], private_bodies_recorded=False)
    evidence['speech_counters'] = status['tts']['speech_counters']
    evidence['latest_speech_job'] = job
    evidence['playback_events'] = playback_events
    path = Path('reports/talkback_reliability_evidence/live_backend.json')
    path.parent.mkdir(exist_ok=True); path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence))


if __name__ == '__main__': asyncio.run(main())
