"""Write private side-by-side owner review sheets for verified holdout cases."""
from __future__ import annotations

import hashlib
from pathlib import Path

from jarvis.integrations.whatsapp.personal_reply.store import PersonalReplyStore


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    store = PersonalReplyStore(root/'jarvis/db/jarvis.db')
    out_dir = root/'jarvis/data/whatsapp_style_reviews'
    out_dir.mkdir(parents=True, exist_ok=True)
    for contact in store.contacts():
        cid = contact['contact_id']
        cases = store.holdout_review_cases(cid, limit=5)
        if not cases:
            continue
        key = hashlib.sha256(cid.encode()).hexdigest()[:8]
        lines = [f'# Verified holdout review: {store.display_name(cid) or key}', '',
                 'Private local evaluation. The historical owner reply was withheld from generation.',
                 'Rate each case EXACT_STYLE, GOOD, OKAY, BAD_STYLE, or WRONG_MEANING.',
                 'Also mark semantic, dyadic, language, emoji and length separately when you have reviewed them.', '']
        for case in cases:
            lines += [f"## Case `{case['case_id']}`", '',
                      '**Incoming:**', '', case['incoming'], '',
                      '**JARVIS draft:**', '', case['jarvis'], '',
                      '**Owner actual:**', '', case['owner_actual'], '',
                      f"**Your rating:** {case['rating'] or 'PENDING'}", '',
                      f"**Semantic correct:** {case['dimensions'].get('semantic_correct', 'PENDING')}",
                      f"**Dyadic correct:** {case['dimensions'].get('dyadic_correct', 'PENDING')}",
                      f"**Language match:** {case['dimensions'].get('language_match', 'PENDING')}",
                      f"**Emoji appropriate:** {case['dimensions'].get('emoji_appropriate', 'PENDING')}",
                      f"**Length appropriate:** {case['dimensions'].get('length_appropriate', 'PENDING')}", '']
        path = out_dir/f'{key}.holdout.md'
        path.write_text('\n'.join(lines), encoding='utf-8')
        print(f'{key}: cases={len(cases)} -> {path}')


if __name__ == '__main__':
    main()
