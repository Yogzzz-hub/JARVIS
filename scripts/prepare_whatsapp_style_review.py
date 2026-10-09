"""Create local, untracked review sheets for the three draft-ready contacts."""
from __future__ import annotations

import hashlib
from pathlib import Path

from jarvis.integrations.whatsapp.personal_reply.agent import PersonalReplyAgent
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    store = PersonalReplyStore(root / 'jarvis/db/jarvis.db')
    agent = PersonalReplyAgent(store=store, transport=None, use_jde=False)
    out_dir = root / 'jarvis/data/whatsapp_style_reviews'
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for contact in store.contacts():
        cid = contact['contact_id']
        state = agent.maturity(cid)
        if state not in ('DRAFT_READY', 'VERIFIED_STYLE_BUILDING'):
            continue
        key = hashlib.sha256(cid.encode()).hexdigest()[:8]
        batch = agent.legacy_review_batch(cid, limit=35)['examples']
        if state == 'VERIFIED_STYLE_BUILDING':
            with store._conn() as conn:
                pair_times = {r[0] for r in conn.execute(
                    "SELECT ts FROM wa_pr_examples WHERE contact_id=? AND provenance='LEGACY_OWNER_LIKELY'",
                    (cid,))}
            batch = [row for row in batch if row['timestamp'] in pair_times]
            if not batch:
                continue
        lines = [f'# Owner style review: {store.display_name(cid) or key}', '',
                 'Private local review sheet. Confirm authorship only; this does not enable auto-reply.',
                 'Mark each sampled row APPROVE or REJECT. Leave uncertain rows unapproved.', '',
                 f'Contact hash: `{key}`. Sampled rows: {len(batch)}.', '']
        for item in batch:
            body = ' '.join(item['text'].split())
            lines.append(f"- [ ] APPROVE / REJECT `{item['message_id']}` · {body}")
        lines += ['', 'To cancel, leave the sheet unchanged. Only an explicit owner review changes provenance.', '']
        path = out_dir / (f'{key}.pairs.md' if state == 'VERIFIED_STYLE_BUILDING' else f'{key}.md')
        path.write_text('\n'.join(lines), encoding='utf-8')
        written += 1
        print(f'{key}: {len(batch)} samples -> {path}')
    print(f'prepared_contacts={written}')


if __name__ == '__main__':
    main()
