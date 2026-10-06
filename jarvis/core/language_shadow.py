"""Bounded, asynchronous shadow collection; production decisions are untouched."""
from __future__ import annotations
import atexit
import hashlib
import json
import logging
import queue
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'jarvis/config/nlp_candidate.json'
DB = ROOT / 'data/nlp_shadow/shadow.sqlite3'
DECISIONS = {'PRODUCTION_CORRECT', 'CANDIDATE_CORRECT', 'BOTH_CORRECT', 'BOTH_WRONG', 'UNSURE'}


def generated_auto_reply_blocked():
    try:
        config = json.loads(CONFIG.read_text(encoding='utf-8'))
        return config.get('MULTILINGUAL_NLP_SHADOW') is True and config.get('WHATSAPP_GENERATED_REPLY_SHADOW') is True
    except (OSError, ValueError):
        return True  # Configuration uncertainty must not authorize a reply.


def safe_text(text):
    import re
    # Identifiers remain in raw inference memory, but secret-bearing commands
    # are omitted entirely from durable records and external worker IPC.
    if re.search(r'\b(?:password|passwd|secret|otp|api[_ -]?key|access[_ -]?token|bearer|private[_ -]?key)\b|sk-[A-Za-z0-9]|://[^/\s]+:[^/\s]+@|[?&](?:token|key|secret)=', text, re.I):
        return False
    return True


class ShadowStore:
    def __init__(self, path=DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, created REAL, source TEXT, mode TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, case_id TEXT, decision TEXT, reviewer TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY, value INTEGER);''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=2)

    def increment(self, name):
        with self.connect() as c:
            c.execute('INSERT INTO counters VALUES(?,1) ON CONFLICT(name) DO UPDATE SET value=value+1', (name,))

    def record(self, item):
        if item['mode'] == 'conversation':
            item = {k: v for k, v in item.items() if k not in {'raw_text', 'production', 'context'}}
        with self.connect() as c:
            c.execute('INSERT OR IGNORE INTO cases VALUES(?,?,?,?,?)', (item['id'], time.time(), item['source'], item['mode'], json.dumps(item, ensure_ascii=False)))

    def review(self, case_id, decision, reviewer):
        if decision not in DECISIONS or not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 100:
            raise ValueError('Explicit owner decision and reviewer identity required')
        with self.connect() as c:
            row = c.execute('SELECT payload FROM cases WHERE id=?', (case_id,)).fetchone()
            if not row or json.loads(row[0]).get('mode') != 'command':
                raise ValueError('Unknown command comparison')
            c.execute('INSERT INTO reviews(case_id,decision,reviewer,created) VALUES(?,?,?,?)', (case_id, decision, reviewer.strip(), time.time()))

    def state(self, limit=50, offset=0):
        with self.connect() as c:
            counts = dict(c.execute('SELECT mode,count(*) FROM cases GROUP BY mode'))
            reviewed = dict(c.execute('SELECT case_id,decision FROM reviews WHERE id IN (SELECT max(id) FROM reviews GROUP BY case_id)'))
            counters = dict(c.execute('SELECT name,value FROM counters'))
            command_rows = [json.loads(r[0]) for r in c.execute("SELECT payload FROM cases WHERE mode='command' ORDER BY created DESC")]
        comparable = [r for r in command_rows if r.get('agreements')]
        agreement = {key: sum(r['agreements'].get(key) is True for r in comparable) / sum(r['agreements'].get(key) is not None for r in comparable)
                     if any(r['agreements'].get(key) is not None for r in comparable) else None
                     for key in ('domain', 'action', 'slots', 'recipient', 'reference', 'negation', 'correction')}
        disagreements = [r for r in command_rows if any(v is False for v in r.get('agreements', {}).values())]
        times = sorted(r['latency_ms'] for r in command_rows if isinstance(r.get('latency_ms'), (int, float)))
        percentile = lambda q: times[min(len(times)-1, round((len(times)-1)*q))] if times else None
        offset = max(0, int(offset));limit = min(100, max(1, int(limit)))
        return {'counts': counts, 'agreement': agreement, 'owner_reviewed': len(reviewed),
                'review_counts': {d: list(reviewed.values()).count(d) for d in sorted(DECISIONS)},
                'disagreements': [{**r, 'owner_decision': reviewed.get(r['id'])} for r in disagreements[offset:offset+limit]],
                'disagreement_total': len(disagreements), 'offset':offset,
                'latency': {'cases':len(times),'p50_ms':percentile(.5),'p95_ms':percentile(.95)},
                'sources': {s:sum(r['source']==s for r in command_rows) for s in sorted({r['source'] for r in command_rows})},
                'counters': counters, 'accuracy': None, 'execute_precision': None, 'execute_coverage': 0,
                'note': 'Agreement is not accuracy. Owner choices are not complete slot gold annotations.'}


class JarvisLanguageUnderstandingService:
    """One process-isolated encoder for all sources, using a bounded CPU worker.

    submit never waits for inference. It does not call router, planner, tools,
    contacts, or a reply sender. Normal contact messages are data-only.
    """
    def __init__(self, root=ROOT, store=None, worker=None):
        self.root = Path(root)
        self.store = store
        self.worker = worker
        self.pending = queue.Queue(maxsize=32)
        self.thread = None
        self.process = None
        self.lock = threading.Lock()
        self.closed = False

    def enabled(self):
        try:
            return json.loads((self.root / 'jarvis/config/nlp_candidate.json').read_text(encoding='utf-8')).get('MULTILINGUAL_NLP_SHADOW') is True
        except (OSError, ValueError):
            return False

    def submit(self, raw_text, source, production=None, *, owner=False, mode='command', context=None, event_id=None, reference_resolver=None):
        import os
        # Injected temporary stores remain testable; real usage evidence must
        # never be populated by a pytest Personal Reply intake fixture.
        if self.root.resolve() == ROOT.resolve() and os.environ.get('PYTEST_CURRENT_TEST'):
            return False
        if self.closed or not self.enabled() or not isinstance(raw_text, str) or not 0 < len(raw_text) <= 4096:
            return False
        if mode not in {'command', 'conversation', 'automation_builder'}:
            return False
        if mode == 'command' and (not owner or source not in {'http', 'cli', 'websocket', 'voice', 'whatsapp', 'dashboard', 'phone'}):
            return False
        if not safe_text(raw_text):
            return False
        # Never forward arbitrary metadata/context containing credentials or
        # resolved private resource IDs to the worker or durable log.
        context = {k: v for k, v in (context or {}).items() if k in {'afternoon_low_hours'} and isinstance(v, bool)}
        item = {'id': hashlib.sha256((mode + ':' + event_id).encode()).hexdigest() if event_id else uuid.uuid4().hex, 'raw_text': raw_text, 'source': source, 'mode': mode,
                'production': production, 'context': context}
        if reference_resolver is not None and mode == 'command' and owner:
            item['_reference_resolver'] = reference_resolver
        try:
            self.pending.put_nowait(item)
        except queue.Full:
            return False
        with self.lock:
            if self.thread is None:
                self.thread = threading.Thread(target=self._run, name='jarvis-language-shadow', daemon=True)
                self.thread.start()
        return True

    def _infer(self, item):
        if self.worker:
            return self.worker(item)
        if self.process is None:
            python = self.root / '.venv-stage24/Scripts/python.exe'
            self.process = subprocess.Popen([str(python), '-u', '-m', 'scripts.multilingual_shadow_worker'],
                cwd=self.root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0))
        self.process.stdin.write(json.dumps(item, ensure_ascii=False) + '\n')
        self.process.stdin.flush()
        result = json.loads(self.process.stdout.readline())
        if 'error' in result:
            raise RuntimeError(result['error'])
        return result

    async def benchmark_preview(self, text):
        """Same advisory worker, serialized with normal shadow jobs; no usage log."""
        import asyncio
        from concurrent.futures import Future
        if not self.enabled() or not safe_text(text):
            return {'state': 'UNAVAILABLE', 'controls_tools': False}
        future = Future()
        item = {'id': uuid.uuid4().hex, 'raw_text': text, 'source': 'dashboard',
            'mode': 'command', 'production': None, 'context': {}, '_benchmark_future': future}
        self.pending.put_nowait(item)
        with self.lock:
            if self.thread is None:
                self.thread = threading.Thread(target=self._run, name='jarvis-language-shadow', daemon=True)
                self.thread.start()
        return await asyncio.wait_for(asyncio.wrap_future(future), 45)

    def _run(self):
        self.store = self.store or ShadowStore()
        while not self.closed:
            try:
                item = self.pending.get(timeout=1)
            except queue.Empty:
                continue
            try:
                benchmark_future = item.pop('_benchmark_future', None)
                reference_resolver = item.pop('_reference_resolver', None)
                result = self._infer(item)
                if benchmark_future is not None:
                    if not benchmark_future.done():
                        benchmark_future.set_result(result)
                    continue
                if reference_resolver and result.get('candidate', {}).get('references'):
                    resolution = reference_resolver(result['candidate'])
                    # Context identifiers remain in local memory; durable shadow
                    # evidence stores outcome/type only, never private resource IDs.
                    result['working_context_advisory'] = {'recommendation': resolution['recommendation'],
                        'controls_tools': False, 'references': [{k: row[k] for k in ('type', 'status')} for row in resolution['references']]}
                self.store.record({**item, **result})
                self.store.increment('completed')
            except Exception:
                if benchmark_future is not None and not benchmark_future.done():
                    benchmark_future.set_result({'state': 'UNAVAILABLE', 'controls_tools': False})
                logging.getLogger(__name__).warning('Advisory NLP worker failed; production unaffected')
                self.store.increment('worker_errors')
                if self.process is not None:
                    self.process.kill()
                    self.process = None
            finally:
                self.pending.task_done()

    def close(self):
        self.closed = True
        if self.process is not None:
            self.process.kill()
            self.process.wait(timeout=3)


_service = None
_service_lock = threading.Lock()


def get_language_service():
    global _service
    with _service_lock:
        if _service is None:
            _service = JarvisLanguageUnderstandingService()
            atexit.register(_service.close)
    return _service


def production_snapshot(decision):
    """Semantic projection of actual output, never infer gold from input text."""
    # The legacy baseline adapter is deliberately not used: it consults gold.
    intent = getattr(decision, 'intent', None)
    slots = {k: v for k, v in dict(getattr(decision, 'slots', {}) or {}).items()
             if k in {'action', 'app', 'application', 'recipient', 'contact', 'sender', 'source', 'destination', 'path', 'file', 'folder', 'url', 'query', 'time', 'date', 'ordinal', 'project'}}
    return {'intent': intent, 'slots': slots, 'lane': str(getattr(decision, 'lane', '')),
            'semantic_frame': (getattr(decision, 'context_trace', None) or {}).get('semantic_frame')}
