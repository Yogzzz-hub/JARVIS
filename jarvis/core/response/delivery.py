"""Bounded final-speech delivery evidence; audio playback remains the sole owner."""
import asyncio
from collections import OrderedDict
from time import monotonic
from uuid import uuid4


class SpeechDelivery:
    def __init__(self, capacity=512):
        self.jobs = OrderedDict()
        self.capacity = capacity

    def begin(self, request_id, language):
        old = self.jobs.get(request_id)
        if old and old['state'] not in {'FAILED'}:
            old['duplicate_suppressions'] += 1
            return None
        if old and old['playback_started']:
            old['duplicate_suppressions'] += 1
            return None
        job = dict(request_id=request_id, response_id=str(uuid4()), text_generated=True,
            tts_requested=True, tts_language=language, tts_engine=None, queue_entered=False,
            synthesis_started=False, synthesis_completed=False, playback_started=False,
            playback_completed=False, cancel_reason=None, suppression_reason=None,
            failure_reason=None, state='PENDING', duplicate_suppressions=0, started=monotonic())
        self.jobs[request_id] = job
        while len(self.jobs) > self.capacity: self.jobs.popitem(last=False)
        return job

    def update(self, job, state=None, **values):
        job.update(values)
        if state: job['state'] = state
        job['latency_ms'] = (monotonic()-job['started'])*1000

    async def monitor(self, job, responses, output, timeout=10):
        for response in responses:
            start = monotonic()
            duration = len(response.audio_bytes or b'')/(2*(response.sample_rate or 22050))
            estimate = getattr(output, 'queue_wait_seconds', None)
            ahead = float(estimate(response)) if callable(estimate) else 0.0
            queue_limit = min(120, timeout + max(0, ahead))
            self.update(job, queue_wait_budget_ms=queue_limit * 1000)
            while True:
                if job['state'] == 'CANCELLED': return
                status = str(getattr(response.delivery_status, 'value', response.delivery_status))
                if response.playback_started_ns:
                    self.update(job, 'PLAYING', playback_started=True)
                if status == 'completed': break
                if status in {'interrupted', 'dropped_stale'}:
                    self.update(job, 'CANCELLED', cancel_reason='USER_OR_BARGE_IN')
                    return
                if status == 'failed_fallback':
                    self.update(job, 'FAILED', failure_reason=getattr(output, 'last_error', '') or 'PLAYBACK_FAILED')
                    return
                limit = duration+30 if response.playback_started_ns else queue_limit
                if monotonic()-start > limit:
                    output.cancel_request(job['request_id'])
                    self.update(job, 'FAILED', failure_reason='PLAYBACK_OR_QUEUE_TIMEOUT')
                    return
                await asyncio.sleep(.02)
        if responses and job['playback_started']:
            self.update(job, 'DELIVERED', playback_completed=True)
        else:
            self.update(job, 'FAILED', failure_reason='TTS_NOT_DELIVERED')

    def snapshot(self):
        return dict(next(reversed(self.jobs.values()))) if self.jobs else None

    def counters(self):
        return dict(text_responses_generated=len(self.jobs),
            tts_requested=sum(j['tts_requested'] for j in self.jobs.values()),
            tts_delivered=sum(j['state']=='DELIVERED' for j in self.jobs.values()),
            tts_failures=sum(j['state']=='FAILED' for j in self.jobs.values()),
            tts_suppressions=sum(bool(j['suppression_reason']) for j in self.jobs.values()),
            duplicate_suppressions=sum(j['duplicate_suppressions'] for j in self.jobs.values()))
