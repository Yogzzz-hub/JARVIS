"""Run local, contact-scoped verified holdout replay for reviewed contacts."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time

from jarvis.integrations.whatsapp.personal_reply.agent import PersonalReplyAgent
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore
from jarvis.integrations.whatsapp.personal_reply.models import Authorship, Direction
from jarvis.integrations.whatsapp.personal_reply.understand import memory_need


async def main() -> None:
    store = PersonalReplyStore()
    agent = PersonalReplyAgent(store=store, transport=None, use_jde=False)
    wanted = {'e35117b2', '003c7eaf', 'adbd8753'}
    results = []
    elapsed_ms = []
    top_similarities = []
    retrieval_total = 0
    retrieval_empty = 0
    cross_contact = 0
    future_examples = 0
    for contact in store.contacts():
        cid = contact['contact_id']
        key = hashlib.sha256(cid.encode()).hexdigest()[:8]
        if key not in wanted:
            continue
        started = time.perf_counter()
        report = await agent.evaluate_contact(cid)
        elapsed_ms.append(round((time.perf_counter() - started) * 1000, 1))
        verified = report['VERIFIED_HOLDOUT']
        retrieval_total += verified.get('retrieval_invoked', 0)
        retrieval_empty += verified.get('retrieval_empty', 0)
        holdout, _ = store.examples(cid, splits=('HOLDOUT',))
        for example in holdout:
            if example.provenance not in (Authorship.USER_TYPED, Authorship.VERIFIED_MANUAL_OWNER_SEND,
                                          Authorship.USER_EDITED_AI_DRAFT, Authorship.VERIFIED_LEGACY_OWNER):
                continue
            prior = [line for line in store.sources(cid) if line.timestamp < example.timestamp][-8:]
            state = agent.answerability_classifier(example.context,
                                                   [(line.direction == Direction.USER, line.text) for line in prior])
            if state.gate != 'ANSWERABLE' or memory_need(example.context, state.category) == 'MEMORY_NOT_NEEDED':
                continue
            hits = agent.index.retrieve(cid, example.context, k=6, now=example.timestamp)
            if hits:
                top_similarities.append(round(hits[0].similarity, 3))
            cross_contact += sum(hit.example.contact_id != cid for hit in hits)
            future_examples += sum(hit.example.timestamp > example.timestamp for hit in hits)
        results.append({'contact_hash': key, 'samples': verified['samples'],
                        'generated': verified.get('generated', 0),
                        'language_match': verified.get('language_match_rate'),
                        'length_match': verified.get('length_match_rate'),
                        'emoji_match': verified.get('emoji_match_rate'),
                        'modality_match': verified.get('modality_match_rate'),
                        'semantic_pass': verified.get('semantic_pass_rate'),
                        'needs_owner_context': verified.get('needs_owner_context', 0),
                        'tool_required': verified.get('tool_required', 0),
                        'no_reply_needed': verified.get('no_reply_needed', 0),
                        'retrieval_invoked': verified.get('retrieval_invoked', 0),
                        'retrieval_empty': verified.get('retrieval_empty', 0),
                        'style_score': verified.get('style_score'),
                        'review_cases': len(verified.get('review_case_ids', [])),
                        'auto_reply_eligible': False})
    print(json.dumps({'contacts': results, 'retrieval_invoked': retrieval_total,
                      'retrieval_empty': retrieval_empty,
                      'top1_similarity': top_similarities,
                      'cross_contact_hits': cross_contact,
                      'future_example_hits': future_examples,
                      'contact_replay_latency_ms': elapsed_ms}, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
