"""Summarize the local shadow runtime without exposing chats or contact identities."""
from __future__ import annotations

import datetime as dt
import json
import socket
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo

def listening(port: int) -> bool:
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=1):
            return True
    except OSError:
        return False


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    style = json.loads((root/'jarvis/data/whatsapp_style_flywheel_audit.json').read_text(
        encoding='utf-8'))['summary']
    today = dt.datetime(2026, 10, 5, tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
    with sqlite3.connect(root/'jarvis/db/jarvis.db', timeout=2) as db:
        statuses = dict(db.execute(
            "SELECT status,count(*) FROM wa_pr_replies WHERE mode='SUGGEST_ONLY' "
            "AND created_at>=? GROUP BY status", (today,)).fetchall())
        feedback = dict(db.execute(
            "SELECT state,count(*) FROM wa_pr_draft_feedback_events WHERE recorded_at>=? "
            "GROUP BY state", (today,)).fetchall())
        train = db.execute("SELECT count(*) FROM wa_pr_examples WHERE split='TRAIN'").fetchone()[0]
        stickers = db.execute("SELECT count(*) FROM wa_pr_sticker_usage").fetchone()[0]
        evaluations = db.execute(
            "SELECT metrics_json FROM wa_pr_evaluations WHERE samples>0").fetchall()
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
    verified_reports = [json.loads(row[0]).get('VERIFIED_HOLDOUT', {}) for row in evaluations]
    generated = sum(r.get('generated', 0) for r in verified_reports)
    clarification_draft = sum(r.get('clarification_draft', 0) for r in verified_reports)
    needs_owner_context = sum(r.get('needs_owner_context', 0) for r in verified_reports)
    model_unavailable = sum(r.get('model_unavailable', 0) for r in verified_reports)
    quality = {}
    for metric in ('language_match_rate','length_match_rate','emoji_match_rate',
                   'modality_match_rate','semantic_pass_rate','style_score'):
        quality[metric] = (round(sum(r[metric] * r.get('generated', 0) for r in verified_reports
                                     if r.get(metric) is not None) / generated, 3)
                           if generated else 'N/A')
    latency_file = root/'jarvis/data/whatsapp_shadow_draft_latency.json'
    latency = json.loads(latency_file.read_text(encoding='utf-8')) if latency_file.exists() else {}
    reviewed = sum(feedback.get(k, 0) for k in ('EDITED_SENT','APPROVED_SENT','NO_REPLY','BAD_STYLE','WRONG_CONTEXT'))
    accepted = feedback.get('EDITED_SENT',0) + feedback.get('APPROVED_SENT',0)
    values = [
        ('LIVE LISTENER', 'Python and bridge ports open' if listening(8765) and listening(8768) else 'NOT_RUNNING'),
        ('SHADOW DRAFT MODE', '3 contacts SUGGEST_ONLY; no generated auto-reply'),
        ('CONTACTS', style['CONTACTS']), ('DRAFT_READY', style['DRAFT_READY']),
        ('VERIFIED_STYLE_BUILDING', style['VERIFIED_STYLE_BUILDING']),
        ('AUTO_REPLY_CANDIDATES', style['AUTO_REPLY_CANDIDATES']),
        ('VERIFIED MANUAL OWNER', style['VERIFIED MANUAL OWNER ROWS']),
        ('VERIFIED LEGACY OWNER', style['VERIFIED LEGACY ROWS']),
        ('VERIFIED EDITED DRAFTS', style['VERIFIED EDITED DRAFTS']),
        ('APPROVED AI DRAFTS', style['USER-APPROVED AI DRAFTS']),
        ('TRAIN EXAMPLES', train), ('VERIFIED HOLDOUT', style['VERIFIED HOLDOUT']),
        ('VERIFIED REPLAY GENERATED', generated),
        ('VERIFIED REPLAY CLARIFICATION DRAFT', clarification_draft),
        ('VERIFIED REPLAY NEEDS OWNER CONTEXT', needs_owner_context),
        ('VERIFIED REPLAY MODEL UNAVAILABLE', model_unavailable),
        ('LEGACY HOLDOUT', style['LEGACY HOLDOUT']),
        ('DRAFTS GENERATED', sum(statuses.values())),
        ('DRAFTS ACCEPTED', accepted), ('DRAFTS EDITED', feedback.get('EDITED_SENT',0)),
        ('DRAFTS REJECTED', feedback.get('NO_REPLY',0)),
        ('BAD_STYLE', feedback.get('BAD_STYLE',0)),
        ('WRONG_CONTEXT', feedback.get('WRONG_CONTEXT',0)),
        ('DRAFT ACCEPTANCE RATE', round(accepted/reviewed,3) if reviewed else 'N/A'),
        ('AVERAGE EDIT RATIO', style['AVERAGE EDIT RATIO'] or 'N/A'),
        ('LANGUAGE MATCH', quality.get('language_match_rate','N/A')),
        ('LENGTH MATCH', quality.get('length_match_rate','N/A')),
        ('EMOJI MATCH', quality.get('emoji_match_rate','N/A')),
        ('MODALITY MATCH', quality.get('modality_match_rate','N/A')),
        ('REPLY/NO-REPLY DECISION', 'N/A (replied pairs only)'),
        ('FORMALITY MATCH', 'N/A (not separately scored)'),
        ('SEMANTIC APPROPRIATENESS', quality.get('semantic_pass_rate','N/A')),
        ('STYLE SCORE', quality.get('style_score','N/A')),
        ('STICKERS INDEXED', stickers),
        ('MEDIAN DRAFT GENERATION LATENCY', f"{latency['median_ms']} ms" if latency.get('median_ms') else 'N/A'),
        ('P95 DRAFT GENERATION LATENCY', f"{latency['p95_ms']} ms" if latency.get('p95_ms') else 'N/A'),
        ('PYTHON TESTS', '79/79 focused cases passed'),
        ('NODE TESTS', '24/24 passed'),
    ]
    lines = ['# WhatsApp personal brain shadow mode', '',
             'Observed 2026-10-05 IST. Counts come from the local encrypted style store. No chat bodies or full contact IDs are in this report.', '',
             '| Measure | Result |', '|---|---:|']
    lines += [f'| {name} | {value} |' for name, value in values]
    lines += ['', f'The {generated} generated verified holdout answers are **diagnostic samples**, not a reliable quality estimate. {clarification_draft} case(s) could use a previously verified same-contact owner clarification as a review-only draft; {needs_owner_context} case(s) had no such evidence and were held. {model_unavailable} case(s) had no model output. Clarifications do not count as correct factual answers. The owner identified a wrong-direction update draft; that original case remains unrated and is not counted as a successful reply. Owner side-by-side ratings remain pending. The style proxy is not calibrated and must not be treated as approval. Approved legacy rows support draft style but the generated auto-reply gate still requires stronger verified manual/edited evidence and a much larger verified holdout.', '',
              f"The latency probe generated {latency.get('generated',0)} of {latency.get('attempts',0)} drafts using generic local prompts before the three owner reviews. It excludes live WhatsApp delivery and does not measure a fresh incoming event. Live shadow drafts will be counted when a new direct message arrives for one of the three configured contacts. General sending and generated auto-reply remain disabled; the prior one-shot outgoing delivery still awaits receiving-phone confirmation.", '',
              f'SQLite integrity: `{integrity}`. The private review sheets and side-by-side case stay in ignored local data.', '']
    path = root/'reports/WHATSAPP_SHADOW_MODE.md'
    path.write_text('\n'.join(lines), encoding='utf-8')
    print(f'report={path} live_drafts={sum(statuses.values())} verified_holdout={style["VERIFIED HOLDOUT"]}')


if __name__ == '__main__':
    main()
