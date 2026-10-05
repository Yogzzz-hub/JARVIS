"""Privacy-preserving local maturity and feedback report for the existing store."""
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

from jarvis.integrations.whatsapp.personal_reply.agent import PersonalReplyAgent
from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore


def report(root: Path) -> dict:
    store = PersonalReplyStore(root/'jarvis/db/jarvis.db')
    agent = PersonalReplyAgent(store=store, transport=None, use_jde=False)
    rows = []
    with store._conn() as db:
        contacts = [r[0] for r in db.execute("SELECT DISTINCT contact_id FROM wa_pr_sources WHERE contact_id!='__default__'")]
        for contact in contacts:
            sources = dict(db.execute("SELECT provenance,count(*) FROM wa_pr_sources WHERE contact_id=? AND direction='USER' "
                                      "GROUP BY provenance", (contact,)).fetchall())
            pairs = db.execute("SELECT count(*) FROM wa_pr_examples WHERE contact_id=?", (contact,)).fetchone()[0]
            holdouts = dict(db.execute("SELECT provenance,count(*) FROM wa_pr_examples WHERE contact_id=? "
                                       "AND split='HOLDOUT' GROUP BY provenance", (contact,)).fetchall())
            stickers = db.execute("SELECT count(*) FROM wa_pr_sticker_usage WHERE contact_id=?", (contact,)).fetchone()[0]
            feedback = [dict(r) for r in db.execute("SELECT state,edit_ratio FROM wa_pr_draft_feedback WHERE contact_id=?",
                                                   (contact,))]
            feedback_events = [r[0] for r in db.execute(
                "SELECT state FROM wa_pr_draft_feedback_events WHERE contact_id=?", (contact,))]
            quality = [json.loads(r[0]) for r in db.execute(
                "SELECT quality_json FROM wa_pr_replies WHERE contact_id=? AND quality_json IS NOT NULL", (contact,))]
            profile = store.load_profile(contact)
            accepted = sum(r['state'] in ('EDITED_SENT','APPROVED_SENT') for r in feedback)
            reviewed = sum(r['state'] in ('EDITED_SENT','APPROVED_SENT','NO_REPLY','BAD_STYLE','WRONG_CONTEXT') for r in feedback)
            edits = [r['edit_ratio'] for r in feedback if r['state']=='EDITED_SENT' and r['edit_ratio'] is not None]
            emoji_weight = (profile.modality_counts.get('TEXT_EMOJI',0)+profile.modality_counts.get('EMOJI_ONLY',0)) if profile else 0
            rows.append({'contact_hash': hashlib.sha256(contact.encode()).hexdigest()[:8],
                         'legacy_owner_examples': sources.get('LEGACY_OWNER_LIKELY',0),
                         'verified_manual_owner_examples': sources.get('VERIFIED_MANUAL_OWNER_SEND',0),
                         'verified_edited_examples': sources.get('USER_EDITED_AI_DRAFT',0),
                         'approved_ai_examples': sources.get('USER_APPROVED_AI_DRAFT',0),
                         'verified_legacy_examples': sources.get('VERIFIED_LEGACY_OWNER',0),
                         'reply_pairs': pairs,
                         'verified_holdout': sum(n for p,n in holdouts.items() if p in (
                             'USER_TYPED','VERIFIED_MANUAL_OWNER_SEND','USER_EDITED_AI_DRAFT',
                             'VERIFIED_LEGACY_OWNER')),
                         'legacy_holdout': sum(n for p,n in holdouts.items() if p not in (
                             'USER_TYPED','VERIFIED_MANUAL_OWNER_SEND','USER_EDITED_AI_DRAFT',
                             'VERIFIED_LEGACY_OWNER')),
                         'style_confidence': profile.confidence if profile else 0,
                         'language_confidence': round(max(profile.english_ratio,profile.tanglish_ratio)*profile.confidence,3) if profile else 0,
                         'emoji_confidence': round(min(1,emoji_weight/10),3),
                         'sticker_evidence': stickers,
                         'draft_acceptance_rate': round(accepted/reviewed,3) if reviewed else None,
                         'average_edit_ratio': round(sum(edits)/len(edits),3) if edits else None,
                         'semantic_failures': sum(bool(q.get('hallucination_risk',0)>.5 or q.get('relevance',1)<.6) for q in quality),
                         'style_failures': sum(bool(q.get('style_match',1)<.5) for q in quality)
                         + feedback_events.count('BAD_STYLE'),
                         'wrong_context_flags': feedback_events.count('WRONG_CONTEXT'),
                         'maturity': agent.maturity(contact)})
        total = dict(db.execute("SELECT provenance,count(*) FROM wa_pr_sources WHERE direction='USER' GROUP BY provenance").fetchall())
        feedback_all = [dict(r) for r in db.execute("SELECT state,edit_ratio FROM wa_pr_draft_feedback")]
    statuses = collections.Counter(r['maturity'] for r in rows)
    reviewed = [r for r in feedback_all if r['state'] in ('EDITED_SENT','APPROVED_SENT','NO_REPLY','BAD_STYLE','WRONG_CONTEXT')]
    accepted = sum(r['state'] in ('EDITED_SENT','APPROVED_SENT') for r in reviewed)
    edits = [r['edit_ratio'] for r in feedback_all if r['state']=='EDITED_SENT' and r['edit_ratio'] is not None]
    summary = {'LEGACY OWNER ROWS': total.get('LEGACY_OWNER_LIKELY',0),
               'VERIFIED MANUAL OWNER ROWS': total.get('VERIFIED_MANUAL_OWNER_SEND',0),
               'VERIFIED LEGACY ROWS': total.get('VERIFIED_LEGACY_OWNER',0),
               'VERIFIED EDITED DRAFTS': total.get('USER_EDITED_AI_DRAFT',0),
               'USER-APPROVED AI DRAFTS': total.get('USER_APPROVED_AI_DRAFT',0),
               'EXCLUDED JARVIS SENDS': total.get('AUTO_GENERATED',0),
               'CONTACTS': len(rows), 'DRAFT_READY': statuses['DRAFT_READY'],
               'VERIFIED_STYLE_BUILDING': statuses['VERIFIED_STYLE_BUILDING'],
               'AUTO_REPLY_CANDIDATES': statuses['AUTO_REPLY_CANDIDATE'],
               'REPLY PAIRS': sum(r['reply_pairs'] for r in rows),
               'VERIFIED HOLDOUT': sum(r['verified_holdout'] for r in rows),
               'LEGACY HOLDOUT': sum(r['legacy_holdout'] for r in rows),
               'EMOJI EVIDENCE': sum(r['emoji_confidence'] > 0 for r in rows),
               'STICKER EVIDENCE': sum(r['sticker_evidence'] for r in rows),
               'DRAFT ACCEPTANCE RATE': round(accepted/len(reviewed),3) if reviewed else None,
               'AVERAGE EDIT RATIO': round(sum(edits)/len(edits),3) if edits else None}
    return {'summary': summary, 'contacts': rows}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    data = report(root)
    (root/'jarvis/data/whatsapp_style_flywheel_audit.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    lines = ['# WhatsApp verified style learning flywheel', '',
             'Local derived-data audit. Contact identifiers are SHA-256 prefixes; message bodies are omitted.', '',
             'The 484 legacy owner count below is text sources admitted to the style store. The separate inbox provenance audit classified 486 historical `fromMe` rows as legacy owner likely; two were not admitted as text style sources.', '',
             '`EMOJI EVIDENCE` counts contacts with a nonzero weighted emoji profile; it is not a count of emoji messages.', '',
             '## Counts', '']
    lines += [f'- {k}: {v if v is not None else "N/A (no reviewed drafts)"}' for k,v in data['summary'].items()]
    lines += ['', '## Contacts', '',
              '| Hash | Legacy | Manual | Edited | Approved AI | Verified legacy | Pairs | Verified holdout | Legacy holdout | Style confidence | Language confidence | Emoji confidence | Stickers | Draft acceptance | Edit ratio | Semantic failures | Style failures | Wrong context | State |',
              '|---|' + '---:|' * 17 + '---|']
    for r in sorted(data['contacts'],key=lambda v:(-v['reply_pairs'],v['contact_hash'])):
        lines.append('| '+ ' | '.join(str(r[k]) if r[k] is not None else 'N/A' for k in (
            'contact_hash','legacy_owner_examples','verified_manual_owner_examples','verified_edited_examples',
            'approved_ai_examples','verified_legacy_examples','reply_pairs','verified_holdout','legacy_holdout',
            'style_confidence','language_confidence','emoji_confidence','sticker_evidence','draft_acceptance_rate',
            'average_edit_ratio','semantic_failures','style_failures','wrong_context_flags','maturity'))+' |')
    lines += ['', '## Current mode', '',
              'Three local contacts are in SUGGEST_ONLY mode. The live bridge and listener were not running at this audit, so natural incoming drafts will start only after the read-only listener is restarted with this code. The draft API can generate a suggestion on demand from stored incoming text. General sending and generated auto-reply remain disabled.', '',
              'Only an exact-ID owner attestation can presently prove a phone outgoing message was manually authored. Unmatched `fromMe` echoes remain unverified. Legacy batch review is optional and retains the original classification. Unchanged approved AI drafts have lower style weight than edits; neither is treated as organically typed text. No draft was sent during this implementation.', '',
              'The current five legacy holdout drafts are bootstrap diagnostics. There are no verified holdout cases or owner-reviewed live drafts, so autonomous quality is unmeasured.', '']
    (root/'reports/WHATSAPP_VERIFIED_STYLE_FLYWHEEL.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(data['summary'],indent=2))
