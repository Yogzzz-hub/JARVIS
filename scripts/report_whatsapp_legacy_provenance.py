"""Render a privacy-preserving local audit of the derived legacy style evidence."""
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore


def render(root: Path) -> Path:
    audit = json.loads((root/'jarvis/data/whatsapp_legacy_provenance_audit.json').read_text(encoding='utf-8'))
    replay_path = root/'jarvis/data/whatsapp_legacy_replay.json'
    replay = json.loads(replay_path.read_text(encoding='utf-8')) if replay_path.exists() else []
    store = PersonalReplyStore(root/'jarvis/db/jarvis.db')
    profiles = collections.Counter()
    table = []
    for contact in sorted(audit['contacts'], key=lambda x: (-x['reply_pairs'], x['contact_id'])):
        profile = store.load_profile(contact['contact_id'])
        confidence = profile.confidence if profile else 0.0
        profiles['high' if confidence >= .7 else 'medium' if confidence >= .4 else 'low' if profile else 'none'] += 1
        emoji = round(profile.modality_counts.get('EMOJI_ONLY', 0) + profile.modality_counts.get('TEXT_EMOJI', 0), 2) if profile else 0
        counts = contact['classification']
        alias = hashlib.sha256(contact['contact_id'].encode()).hexdigest()[:8]
        table.append(f"| `{alias}` | {sum(counts.get(k,0) for k in ('LEGACY_OWNER_LIKELY','UNKNOWN','AUTO_GENERATED'))} | "
                     f"{counts.get('LEGACY_OWNER_LIKELY',0)} | {counts.get('UNKNOWN',0)} | "
                     f"{counts.get('AUTO_GENERATED',0)} | {contact['reply_pairs']} | {emoji} | 0 | "
                     f"{confidence:.2f} | {contact['status']} |")
    counts = audit['counts']
    bins = ', '.join(f'{n} at {score}' for score, n in sorted(audit['confidence_distribution'].items()))
    ready = sum(c['status'] == 'DRAFT_READY' for c in audit['contacts'])
    legacy_generated = sum(r['legacy']['generated'] for r in replay)
    legacy_samples = sum(r['legacy']['samples'] for r in replay)
    per_replay = '; '.join(
        f"`{hashlib.sha256(r['contact_id'].encode()).hexdigest()[:8]}` language match "
        f"{r['legacy']['language_match_rate']}, length match {r['legacy']['length_match_rate']}, "
        f"semantic proxy {r['legacy']['semantic_pass_rate']}" for r in replay)
    content = f"""# WhatsApp legacy owner provenance audit

Run: {audit['run_at']}. First recorded JARVIS WhatsApp send: {audit['first_recorded_jarvis_send']}. This date comes from ActionLedger.

## Classification

The inbox contained **{audit['total_from_me_rows']}** `fromMe` rows: **{counts.get('LEGACY_OWNER_LIKELY',0)}** lower-confidence `LEGACY_OWNER_LIKELY`, **{counts.get('UNKNOWN',0)}** `UNKNOWN`, and **{counts.get('AUTO_GENERATED',0)}** `AUTO_GENERATED`. **{counts.get('MATCHED_JARVIS_ID',0)}** rows matched recorded JARVIS message IDs. **0** forwarded rows had positive forwarding metadata; the stored event schema usually omits forwarding flags, so zero is a detection limit. Confidence bins: {bins}. The 17 rows in a synthetic test contact are `UNKNOWN`. Most remaining legacy rows postdate the first recorded JARVIS send and receive confidence 0.55 and style weight 0.2475.

Known JARVIS IDs come from ActionLedger acknowledgements, personal reply sends, and generated-message records. Only two exact IDs matched; most old ledger records have no provider message ID, so additional automated rows may remain among legacy candidates. The classifier excludes non-direct chats, non-style types, placeholders, positive forwarding metadata, synthetic contacts and known test/generated templates. It never promotes legacy rows to `USER_TYPED`. Raw inbox data is preserved; decisions and reasons are derived metadata.

## Rebuilt evidence

**{sum(c['reply_pairs'] for c in audit['contacts'])}** reply pairs across **{len(audit['contacts'])}** direct contacts: 66 legacy train, 5 legacy development, 5 legacy holdout; 0 verified holdout. There are **{profiles['high']} high**, **{profiles['medium']} medium**, **{profiles['low']} low** confidence profiles and **{profiles['none']}** contacts without a profile. **{ready}** contacts are `DRAFT_READY`; **{len(audit['contacts'])-ready}** are `INSUFFICIENT_HISTORY`; **0** are `AUTO_REPLY_CANDIDATE`. Profile confidence is provisional and is not an authorship probability. No owner sticker with usable local media was indexed. Stable contact hashes protect identities in this report; private local JSON retains the mapping.

| Contact hash | fromMe | Legacy likely | Unknown | Auto | Pairs | Weighted emoji messages | Stickers | Profile confidence | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
{chr(10).join(table)}

## Offline replay

The local generator produced **{legacy_generated}** drafts for **{legacy_samples}** legacy holdout pairs in {len(replay)} contacts. Verified holdout samples: **0**. Per-contact legacy results: {per_replay}. These tiny proxy results do not establish real reply quality. No owner reviewed the drafts and no message was sent.

## Safeguards and limits

Retrieval is scoped to each contact and chronological training examples. Verified examples rank above legacy examples. Legacy data can shape drafts; production auto-reply requires at least 20 verified owner source rows, 20 generated verified holdout evaluations with zero flagged critical cases, evaluation approval, and an explicit timed direct-contact grant. This run meets none of those. Weight 0.45 and draft readiness cutoffs (10 lines, 3 pairs, profile confidence 0.16) are provisional and have not been tuned on an independent gold set.

The derived store was backed up locally at `jarvis/db/jarvis.before_legacy_provenance_20261004.db` before migration. Re-run `python scripts/recover_whatsapp_legacy_provenance.py` with `PYTHONPATH=.` to rebuild classifications. It does not clear or edit the WhatsApp inbox. No private chat bodies were printed or uploaded. The read-only bridge and outgoing acceptance state were not changed.
"""
    path = root/'reports/WHATSAPP_LEGACY_PROVENANCE_AUDIT.md'
    path.write_text(content, encoding='utf-8')
    return path


if __name__ == '__main__':
    print(render(Path(__file__).resolve().parents[1]))
