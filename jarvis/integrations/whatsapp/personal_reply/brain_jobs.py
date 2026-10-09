"""Resumable background builds for the existing shared WhatsApp style store.

Raw inbox and owner review records stay in their existing tables. Derived examples,
profiles and aggregate behavior data are staged in memory and published together.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from collections import Counter
from typing import Any

import numpy as np

from . import importer as imp, language, style_analyzer
from .dedupe import is_group_chat
from .example_index import embed
from .models import Authorship, Direction, ExampleSource
from .store import VECTOR_DIM


_ELIGIBLE = {Authorship.USER_TYPED, Authorship.VERIFIED_MANUAL_OWNER_SEND,
             Authorship.USER_EDITED_AI_DRAFT, Authorship.USER_APPROVED_AI_DRAFT,
             Authorship.VERIFIED_LEGACY_OWNER, Authorship.LEGACY_OWNER_LIKELY}
_TECH = re.compile(r'\b(?:backend|api|server|deploy|git|code|project|bug|database)\b', re.I)


def _derived(lines, examples) -> dict[str, Any]:
    """Communication statistics only; no private text crosses into dashboard lists."""
    incoming = [line for line in lines if line.direction == Direction.CONTACT]
    outgoing = [line for line in lines if line.direction == Direction.USER and line.provenance in _ELIGIBLE]
    train = [ex for ex in examples if ex.split == 'TRAIN']
    lang_counts = Counter(language.detect(line.text).label for line in incoming)
    modes = Counter('QUESTION' if '?' in line.text else 'TECHNICAL' if _TECH.search(line.text)
                    else 'CASUAL' for line in incoming)
    dyadic: dict[str, dict[str, Any]] = {}
    for mode in ('QUESTION', 'TECHNICAL', 'CASUAL'):
        pairs = [ex for ex in train if ('QUESTION' if '?' in ex.context else
                 'TECHNICAL' if _TECH.search(ex.context) else 'CASUAL') == mode]
        if pairs:
            dyadic[mode] = {'pairs': len(pairs),
                            'median_reply_words': sorted(len(ex.reply.split()) for ex in pairs)[len(pairs)//2],
                            'reply_languages': dict(Counter(language.detect(ex.reply).label for ex in pairs))}
    verified = sum(line.provenance in {Authorship.USER_TYPED, Authorship.VERIFIED_MANUAL_OWNER_SEND,
                                      Authorship.USER_EDITED_AI_DRAFT, Authorship.VERIFIED_LEGACY_OWNER}
                   for line in outgoing)
    return {'messages': len(lines), 'contact_messages': len(incoming), 'owner_style_messages': len(outgoing),
            'reply_pairs': len(examples), 'verified_owner_messages': verified,
            'contact_behavior': {'languages': dict(lang_counts), 'modes': dict(modes),
                                 'question_rate': round(sum('?' in x.text for x in incoming)/max(1, len(incoming)), 3),
                                 'emoji_rate': round(sum(bool(language.emojis(x.text)) for x in incoming)/max(1, len(incoming)), 3),
                                 'median_words': (sorted(len(x.text.split()) for x in incoming)[len(incoming)//2]
                                                  if incoming else 0)},
            'dyadic': dyadic, 'dyadic_confidence': round(min(1.0, len(train)/30), 3),
            'memory_coverage': 'RECENT_AND_EXAMPLE_ONLY', 'history_completeness': 'UNKNOWN'}


class BrainJobs:
    def __init__(self, agent):
        self.agent = agent
        self.store = agent.store
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        with self.store._lock, self.store._conn() as con:
            con.execute("UPDATE wa_brain_jobs SET status='QUEUED',stage='RESUME_AFTER_RESTART',updated_at=? "
                        "WHERE status IN ('RUNNING','VALIDATING','PUBLISHING','RELOADING')", (time.time(),))
        self._start_next()

    def _emit(self, job_id: str) -> None:
        try:
            self.agent._emit('ingestion', **self.get(job_id))
        except Exception:
            pass

    def get(self, job_id: str) -> dict[str, Any]:
        with self.store._conn() as con:
            row = con.execute('SELECT * FROM wa_brain_jobs WHERE job_id=?', (job_id,)).fetchone()
        if not row:
            raise KeyError(job_id)
        result = dict(row)
        result['warnings'] = json.loads(result.pop('warnings_json'))
        result['metrics'] = json.loads(result.pop('metrics_json'))
        result['percentage'] = round(100 * result['processed']/max(1, result['total']))
        return result

    def latest(self) -> dict[str, Any] | None:
        with self.store._conn() as con:
            row = con.execute('SELECT job_id FROM wa_brain_jobs ORDER BY updated_at DESC LIMIT 1').fetchone()
        return self.get(row[0]) if row else None

    def start(self, scope: str, contact_id: str = '') -> dict[str, Any]:
        if scope not in ('ALL', 'CONTACT') or (scope == 'CONTACT' and
           (not contact_id or not self.agent.inbox.is_direct_chat(contact_id))):
            raise ValueError('Choose all direct chats or one direct contact')
        with self._lock, self.store._lock, self.store._conn() as con:
            existing = con.execute("SELECT job_id FROM wa_brain_jobs WHERE scope=? AND contact_id=? "
                                   "AND status IN ('QUEUED','RUNNING','VALIDATING','PUBLISHING','RELOADING') "
                                   "ORDER BY started_at LIMIT 1", (scope, contact_id)).fetchone()
            if existing:
                return self.get(existing[0])
            job_id = uuid.uuid4().hex
            now = time.time()
            con.execute('INSERT INTO wa_brain_jobs(job_id,scope,contact_id,status,stage,started_at,updated_at) '
                        "VALUES(?,?,?,'QUEUED','DISCOVER',?,?)", (job_id, scope, contact_id, now, now))
        self._start_next()
        return self.get(job_id)

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self.store._lock, self.store._conn() as con:
            con.execute("UPDATE wa_brain_jobs SET status='CANCELLED',stage='CANCELLED',updated_at=? "
                        "WHERE job_id=? AND status IN ('QUEUED','RUNNING','VALIDATING')", (time.time(), job_id))
        self._emit(job_id)
        return self.get(job_id)

    def _start_next(self) -> None:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            with self.store._conn() as con:
                row = con.execute("SELECT job_id FROM wa_brain_jobs WHERE status='QUEUED' "
                                  "ORDER BY started_at LIMIT 1").fetchone()
            if row:
                self._worker = threading.Thread(target=self._run, args=(row[0],), daemon=True,
                                                name='whatsapp-brain-build')
                self._worker.start()

    def _update(self, job_id: str, status: str, stage: str, processed: int | None = None,
                total: int | None = None, error: str = '', version: int = 0,
                metrics: dict[str, int] | None = None) -> None:
        with self.store._lock, self.store._conn() as con:
            con.execute("UPDATE wa_brain_jobs SET status=?,stage=?,processed=coalesce(?,processed),"
                        "total=coalesce(?,total),error=?,metrics_json=coalesce(?,metrics_json),"
                        "new_index_version=CASE WHEN ?>0 THEN ? "
                        "ELSE new_index_version END,updated_at=? WHERE job_id=? AND status!='CANCELLED'",
                        (status, stage, processed, total, error[:250],
                         json.dumps(metrics) if metrics is not None else None,
                         version, version, time.time(), job_id))
        self._emit(job_id)

    def _cancelled(self, job_id: str) -> bool:
        return self.get(job_id)['status'] == 'CANCELLED'

    def _contacts(self, scope: str, contact_id: str) -> list[str]:
        if scope == 'CONTACT':
            return [contact_id]
        known = {row['contact_id'] for row in self.store.contacts() if row['contact_id'] != '__default__'}
        try:
            with self.agent.inbox._get_conn() as con:
                known |= {row[0] for row in con.execute('SELECT DISTINCT chat_id FROM whatsapp_messages')}
        except Exception:
            pass
        return sorted(cid for cid in known if cid and not is_group_chat(cid)
                      and (cid.endswith('@s.whatsapp.net') or cid.endswith('@lid') or cid.endswith('@c.us')))

    def _snapshot(self, cid: str) -> dict[str, Any]:
        lines = self.store.sources(cid)
        examples = imp.build_examples(cid, lines)
        vecs = embed([e.context for e in examples]) if examples else np.zeros((0, VECTOR_DIM), np.float32)
        train_cutoff = max((e.timestamp for e in examples if e.split == 'TRAIN'), default=float('inf'))
        eval_replies = {(e.timestamp, e.reply) for e in examples if e.split != 'TRAIN'}
        held_parts = {(ts, part) for ts, rep in eval_replies for part in rep.split('\n')}
        owner_lines = [ln for ln in lines if ln.direction == Direction.USER and ln.provenance in _ELIGIBLE
                       and ln.timestamp <= train_cutoff and (ln.timestamp, ln.text) not in held_parts
                       and not any(abs(ln.timestamp - ts) < 601 and ln.text in rep.split('\n')
                                   for ts, rep in eval_replies)]
        old = self.store.load_profile(cid)
        profile = style_analyzer.analyze(cid, self.store.display_name(cid), owner_lines,
                                         preferences=old.preferences if old else None)
        from .legacy_provenance import evidence_weight
        with self.store._conn() as con:
            stickers = con.execute('SELECT provenance,provenance_confidence FROM wa_pr_sticker_usage '
                                   'WHERE contact_id=?', (cid,)).fetchall()
        sticker_weight = sum(evidence_weight(Authorship(row[0]), row[1]) for row in stickers)
        if sticker_weight:
            profile.modality_counts['STICKER_ONLY'] = round(sticker_weight, 3)
            profile.sticker_frequency = round(sticker_weight / max(1, profile.effective_evidence + sticker_weight), 3)
        return {'contact_id': cid, 'source_hash': self.store.source_fingerprint(cid),
                'examples': examples, 'vectors': vecs, 'profile': profile,
                'derived': _derived(lines, examples)}

    def _run(self, job_id: str) -> None:
        try:
            if self._cancelled(job_id):
                return
            job = self.get(job_id)
            self._update(job_id, 'RUNNING', 'DISCOVER')
            contacts = self._contacts(job['scope'], job['contact_id'])
            self._update(job_id, 'RUNNING', 'NORMALIZE_AND_CLASSIFY', 0, len(contacts))
            snapshots = []
            metrics = {'messages': 0, 'reply_pairs': 0, 'embeddings': 0, 'profiles': 0,
                       'skipped_unchanged_contacts': 0}
            for number, cid in enumerate(contacts, 1):
                if self._cancelled(job_id):
                    return
                # Import only already-local inbox history. Existing source classifications
                # and owner attestations remain untouched on repeat builds.
                try:
                    from .legacy_provenance import LegacyProvenanceResolver
                    resolver = LegacyProvenanceResolver(self.agent.inbox.db_path, self.store.path)
                    lines = imp.lines_from_inbox(self.agent.inbox, cid, limit=100000, resolver=resolver)
                    if lines:
                        self.store.upsert_contact(cid)
                        self.store.add_sources(cid, lines, import_id='legacy_inbox', preserve_existing=True)
                except Exception as exc:
                    raise RuntimeError(f'History import failed for a direct contact: {type(exc).__name__}') from exc
                digest = self.store.source_fingerprint(cid)
                state = self.store.brain_state(cid)['contact']
                if job['scope'] == 'CONTACT' or not state or state['source_hash'] != digest:
                    snap = self._snapshot(cid)
                    snapshots.append(snap)
                    metrics['messages'] += snap['derived']['messages']
                    metrics['reply_pairs'] += len(snap['examples'])
                    metrics['embeddings'] += len(snap['vectors'])
                    metrics['profiles'] += int(bool(snap['profile'].messages_analyzed))
                else:
                    metrics['skipped_unchanged_contacts'] += 1
                self._update(job_id, 'RUNNING', 'BUILD_PROFILES_AND_EMBEDDINGS', number, len(contacts),
                             metrics=metrics)
            if self._cancelled(job_id):
                return
            self._update(job_id, 'VALIDATING', 'VALIDATION', len(contacts), len(contacts), metrics=metrics)
            if any(s['derived']['messages'] < s['derived']['owner_style_messages'] for s in snapshots):
                raise ValueError('Derived source count validation failed')
            if self._cancelled(job_id):
                return
            self._update(job_id, 'PUBLISHING', 'ATOMIC_PUBLISH', len(contacts), len(contacts), metrics=metrics)
            if self._cancelled(job_id):
                return
            version = self.store.publish_brain_snapshots(snapshots, job_id)
            for snap in snapshots:
                self.agent.index.invalidate(snap['contact_id'])
            self.agent._refresh_default_profile()
            self._update(job_id, 'COMPLETE', 'READY', len(contacts), len(contacts), version=version,
                         metrics=metrics)
        except Exception as exc:
            self._update(job_id, 'FAILED', 'FAILED', error=f'{type(exc).__name__}: {exc}')
        finally:
            with self._lock:
                self._worker = None
            self._start_next()
