"""Measure local shadow-draft latency without sending or printing chat content."""
from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path

from jarvis.integrations.whatsapp.personal_reply.agent import PersonalReplyAgent
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * p + .5))], 1)


async def run() -> dict:
    root = Path(__file__).resolve().parents[1]
    store = PersonalReplyStore(root / 'jarvis/db/jarvis.db')
    agent = PersonalReplyAgent(store=store, transport=None, use_jde=False)
    ready = [c['contact_id'] for c in store.contacts()
             if c['mode'] == 'SUGGEST_ONLY' and store.load_profile(c['contact_id']) is not None]
    # Generic test inputs avoid copying private chat text to benchmark logs.
    prompts = ('Hello bro', 'Super da', 'Haha nice one')
    rows = []
    phase_rows = []
    for contact in ready:
        for prompt in prompts:
            start = time.perf_counter()
            try:
                result = await agent.test_reply(contact, prompt)
                status = 'GENERATED' if result.get('reply') else 'NO_DRAFT'
                if status == 'GENERATED' and result.get('timing_ms'):
                    phase_rows.append(result['timing_ms'])
            except Exception as exc:
                status = type(exc).__name__
            rows.append({'status': status, 'latency_ms': round((time.perf_counter() - start) * 1000, 1)})
    completed = [r['latency_ms'] for r in rows if r['status'] == 'GENERATED']
    result = {'contacts': len(ready), 'attempts': len(rows), 'generated': len(completed),
              'median_ms': round(statistics.median(completed), 1) if completed else None,
              'p95_ms': percentile(completed, .95), 'statuses': [r['status'] for r in rows],
              'phases': {key: {'p50_ms': percentile([r[key] for r in phase_rows], .5),
                               'p95_ms': percentile([r[key] for r in phase_rows], .95)}
                         for key in (phase_rows[0] if phase_rows else [])},
              'sent': False, 'scope': 'offline generic prompts; excludes WhatsApp transport'}
    (root/'jarvis/data/whatsapp_shadow_draft_latency.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    print(json.dumps(asyncio.run(run()), indent=2))
