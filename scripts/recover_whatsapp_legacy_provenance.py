"""Rebuild derived personal style metadata from the local WhatsApp inbox only.

The source inbox is opened read-only. No transport or send API is used.
"""
from __future__ import annotations

import collections
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from jarvis.integrations.whatsapp.inbox import WhatsAppInbox
from jarvis.integrations.whatsapp.personal_reply.agent import PersonalReplyAgent
from jarvis.integrations.whatsapp.personal_reply.legacy_provenance import LegacyProvenanceResolver
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore


def recover(inbox_path: Path, store_path: Path) -> dict:
    inbox = WhatsAppInbox(inbox_path)
    store = PersonalReplyStore(store_path)
    resolver = LegacyProvenanceResolver(inbox_path, store_path)
    agent = PersonalReplyAgent(inbox=inbox, store=store, transport=None, use_jde=False)
    audit = []
    by_contact = collections.defaultdict(collections.Counter)
    with sqlite3.connect(f'file:{inbox_path.resolve()}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT m.message_id,m.chat_id,m.timestamp,m.type,m.text,m.is_from_me,e.payload "
                          "FROM whatsapp_messages m LEFT JOIN wa_events e USING(message_id) "
                          "WHERE m.is_from_me=1 ORDER BY m.timestamp,m.message_id").fetchall()
    for row in rows:
        decision = resolver.classify(message_id=row['message_id'], chat_id=row['chat_id'],
                                     timestamp=row['timestamp'], message_type=row['type'], text=row['text'],
                                     from_me=True, payload=row['payload'])
        audit.append((row['message_id'], row['chat_id'], decision.provenance.value,
                      decision.confidence, list(decision.reasons)))
        by_contact[row['chat_id']][decision.provenance.value] += 1
        if 'forwarding_metadata' in decision.reasons:
            by_contact[row['chat_id']]['FORWARDED_EXCLUDED'] += 1
        if 'jarvis_message_id_match' in decision.reasons:
            by_contact[row['chat_id']]['MATCHED_JARVIS_ID'] += 1
    store.record_legacy_audit(audit)
    direct = sorted({row['chat_id'] for row in rows if inbox.is_direct_chat(row['chat_id'])
                     and row['type'] == 'text' and row['text']})
    results = []
    for chat_id in direct:
        # import_chat reclassifies all source text for this direct contact, and
        # rebuilds only its derived examples/profile. Raw WhatsApp history is kept.
        result = agent.import_chat(chat_id, from_inbox=True)
        with store._conn() as db:
            splits = [dict(r) for r in db.execute(
                "SELECT provenance,split,count(*) count FROM wa_pr_examples WHERE contact_id=? "
                "GROUP BY provenance,split", (chat_id,))]
        verified = sum(x['count'] for x in splits if x['provenance'] in ('USER_TYPED','USER_EDITED_AI_DRAFT') and x['split']=='HOLDOUT')
        legacy = sum(x['count'] for x in splits if x['provenance']=='LEGACY_OWNER_LIKELY' and x['split']=='HOLDOUT')
        status = ('DRAFT_READY' if result['messages_analyzed'] >= 10 and result['examples'] >= 3
                  and result['summary']['confidence'] >= 0.16 else 'INSUFFICIENT_HISTORY')
        results.append({'contact_id': chat_id, 'classification': dict(by_contact[chat_id]),
                        'source_lines_added': result['lines_added'], 'reply_pairs': result['examples'],
                        'verified_holdout': verified, 'legacy_holdout': legacy,
                        'messages_analyzed': result['messages_analyzed'], 'confidence': result['summary']['confidence'],
                        'status': status, 'splits': splits})
    total = collections.Counter()
    bins = collections.Counter()
    for _, _, provenance, confidence, reasons in audit:
        total[provenance] += 1
        bins[f'{confidence:.2f}'] += 1
        if 'forwarding_metadata' in reasons: total['FORWARDED_EXCLUDED'] += 1
        if 'jarvis_message_id_match' in reasons: total['MATCHED_JARVIS_ID'] += 1
    with store._conn() as db:
        total['VERIFIED_OWNER_SOURCE_ROWS'] = db.execute(
            "SELECT count(*) FROM wa_pr_sources WHERE direction='USER' AND provenance IN ('USER_TYPED','USER_EDITED_AI_DRAFT')").fetchone()[0]
        total['INDEXED_STICKERS'] = db.execute('SELECT count(*) FROM wa_pr_sticker_usage').fetchone()[0]
    return {'run_at': datetime.now(timezone.utc).isoformat(),
            'first_recorded_jarvis_send': datetime.fromtimestamp(resolver.first_send_at, timezone.utc).isoformat()
            if resolver.first_send_at else None,
            'total_from_me_rows': len(rows), 'counts': dict(total), 'confidence_distribution': dict(bins),
            'contacts': results}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    result = recover(root/'jarvis/data/whatsapp_inbox.db', root/'jarvis/db/jarvis.db')
    dest = root/'jarvis/data/whatsapp_legacy_provenance_audit.json'
    dest.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'total_from_me_rows': result['total_from_me_rows'], 'counts': result['counts'],
                      'confidence_distribution': result['confidence_distribution'],
                      'contacts': len(result['contacts']), 'reply_pairs': sum(c['reply_pairs'] for c in result['contacts'])},
                     indent=2))
