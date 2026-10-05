"""Apply an owner's explicit decision to one prepared private review sheet."""
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
from pathlib import Path

from jarvis.integrations.whatsapp.personal_reply.agent import PersonalReplyAgent
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-hash', required=True, choices=('e35117b2', '003c7eaf', 'adbd8753'))
    parser.add_argument('--action', required=True, choices=('APPROVE_ALL', 'REJECT_ALL'))
    parser.add_argument('--rebuild-only', action='store_true')
    parser.add_argument('--supplement', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    store = PersonalReplyStore(root/'jarvis/db/jarvis.db')
    matches = [c['contact_id'] for c in store.contacts()
               if hashlib.sha256(c['contact_id'].encode()).hexdigest()[:8] == args.batch_hash]
    if len(matches) != 1:
        raise SystemExit('Contact hash is not unique; no rows updated')
    contact = matches[0]
    if args.rebuild_only:
        result = PersonalReplyAgent(store=store, transport=None, use_jde=False).rebuild_profile(contact)
        print(f"batch={args.batch_hash} examples={result['examples']} holdout={result['holdout_examples']}")
        return
    sheet_name = f'{args.batch_hash}.pairs.md' if args.supplement else f'{args.batch_hash}.md'
    sheet = root/'jarvis/data/whatsapp_style_reviews'/sheet_name
    content = sheet.read_text(encoding='utf-8')
    ids = re.findall(r'^- \[ \] APPROVE / REJECT `([^`]+)`', content, re.M)
    if not ids or len(set(ids)) != len(ids) or (not args.supplement and len(ids) != 35):
        raise SystemExit('Review sheet changed or incomplete; no rows updated')
    current = store.legacy_review_candidates(contact, limit=35)
    if args.supplement:
        with store._conn() as conn:
            pair_times = {r[0] for r in conn.execute(
                "SELECT ts FROM wa_pr_examples WHERE contact_id=? AND provenance='LEGACY_OWNER_LIKELY'",
                (contact,))}
        current = [row for row in current if row['timestamp'] in pair_times]
    eligible = {r['message_id'] for r in current}
    if set(ids) != eligible:
        raise SystemExit('Current batch differs from owner-reviewed sheet; no rows updated')
    backup = root/'jarvis/db'/f'jarvis.before_style_review_{args.batch_hash}.db'
    if not backup.exists():
        with sqlite3.connect(store.path) as src, sqlite3.connect(backup) as dst:
            src.backup(dst)
    agent = PersonalReplyAgent(store=store, transport=None, use_jde=False)
    result = agent.review_legacy(contact, {mid: args.action == 'APPROVE_ALL' for mid in ids})
    print(f"batch={args.batch_hash} approved={result['APPROVED']} rejected={result['REJECTED']} "
          f"maturity={agent.maturity(contact)} backup={backup.name}")


if __name__ == '__main__':
    main()
