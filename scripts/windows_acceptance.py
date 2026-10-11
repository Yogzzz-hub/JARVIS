"""Bounded read-only Windows acceptance. Raw responses stay local and uncommitted.

Run with the existing .venv after start.ps1/start.bat. This script does not
refresh OAuth, send messages, open apps, synthesize owner speech or promote.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

import httpx
import psutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/acceptance'


def hardware():
    mem = psutil.virtual_memory()
    gpu = []
    try:
        proc = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu', '--format=csv,noheader,nounits'],
                              capture_output=True, text=True, timeout=5,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                parts = [v.strip() for v in line.split(',')]
                if len(parts) == 5:
                    gpu.append(dict(zip(('name', 'driver', 'vram_total_mib', 'vram_used_mib', 'utilization_percent'), parts)))
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {'os': platform.platform(), 'cpu': platform.processor(), 'ram_total_bytes': mem.total,
            'ram_available_bytes': mem.available, 'system_memory_percent': mem.percent,
            'gpu': gpu, 'cuda_runtime': 'NOT_PROBED; GPU presence alone does not prove CUDA availability',
            'python': sys.version.split()[0]}


def backend_pid():
    # Listening socket identifies the actual gateway; never guess from names.
    for c in psutil.net_connections(kind='tcp'):
        if c.status == psutil.CONN_LISTEN and c.laddr.port == 8765:
            return c.pid
    return None


def resources(pid, samples=6):
    if not pid:
        return {'status': 'BACKEND_UNAVAILABLE'}
    root = psutil.Process(pid)
    records = []
    for _ in range(samples):
        children = root.children(recursive=True)
        records.append({'root_rss': root.memory_info().rss,
                        'children_rss': sum(c.memory_info().rss for c in children if c.is_running()),
                        'child_count': len(children), 'cpu_percent': root.cpu_percent(interval=.15)})
    return {'pid': pid, 'samples': len(records), 'root_peak_rss': max(r['root_rss'] for r in records),
            'children_peak_rss': max(r['children_rss'] for r in records),
            'max_child_count': max(r['child_count'] for r in records),
            'cpu_percent_mean': statistics.mean(r['cpu_percent'] for r in records),
            'memory_leak': 'NOT_INFERRED_FROM_SINGLE_WINDOW'}


def command(client, text):
    start = time.perf_counter()
    response = client.post('/command', json={'text': text, 'source': 'benchmark',
        'metadata': {'response_channel': 'text_only', 'acceptance_provenance': 'SYNTHETIC'}})
    response.raise_for_status()
    body = response.json()
    # Keep actual text only in ignored, private evidence.
    return body, (time.perf_counter()-start)*1000


def run(include_web=False):
    if sys.platform != 'win32':
        raise SystemExit('WINDOWS_ACCEPTANCE_REQUIRES_LOCAL_WINDOWS_CODEX')
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {'date_utc': datetime.now(timezone.utc).isoformat(), 'hardware': hardware(),
               'provenance': 'SYNTHETIC commands through real Windows runtime; hardware directly measured',
               'natural_owner_commands': 0, 'owner_voice': 'OWNER_ACTION_REQUIRED',
               'promoted': 0, 'production_authoritative': True}
    with httpx.Client(base_url='http://127.0.0.1:8765', timeout=90) as client:
        try:
            health = client.get('/health')
            health.raise_for_status()
            summary['core'] = health.json()
        except (httpx.HTTPError, ValueError) as exc:
            summary['core'] = {'status':'UNAVAILABLE', 'error': type(exc).__name__}
            (OUT / 'windows-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
            return summary
        pid = backend_pid()
        summary['idle_resources'] = resources(pid)
        raw = []
        times = []
        for _ in range(8):
            try:
                body, elapsed = command(client, 'what time is it')
            except httpx.HTTPError as exc:
                raw.append({'kind':'DETERMINISTIC', 'result':{'state':'FAILED'}, 'error':type(exc).__name__})
                continue
            raw.append({'kind':'DETERMINISTIC', 'result':body, 'elapsed_ms':elapsed})
            times.append(elapsed)
        summary['deterministic'] = {'count':len(times), 'cold_ms':times[0] if times else None,
            'warm_p50_ms':statistics.median(times[1:]) if len(times)>1 else None, 'warm_p95_ms':sorted(times[1:])[-1] if len(times)>1 else None,
            'success_count':sum(r['result'].get('state') == 'SUCCESS' for r in raw)}
        summary['deterministic_resources'] = resources(pid)
        questions = ['What is hallucination?']
        if include_web:
            questions += ['search web and summarize', 'why does it happen?', 'now explain overfitting', 'compare both', 'what is halusination']
        knowledge = []
        for question in questions:
            try:
                body, elapsed = command(client, question)
                raw.append({'kind':'KNOWLEDGE_CONTEXT', 'query':question, 'result':body, 'elapsed_ms':elapsed})
                knowledge.append({'state':body['state'], 'elapsed_ms':elapsed,
                                  'tool':(body.get('tool_result') or {}).get('tool_name'),
                                  'verified':(body.get('verification') or {}).get('verified')})
            except httpx.HTTPError as exc:
                knowledge.append({'state':'FAILED','error':type(exc).__name__})
        summary['knowledge_context'] = knowledge
        try:
            response = client.get('/voice/status'); response.raise_for_status()
            data = response.json()
            summary['voice'] = {k:data.get(k) for k in ('enabled','running','tts_enabled','tts_played','hotkey_registered')}
            summary['voice']['error_present'] = bool(data.get('error') or data.get('tts_error'))
        except httpx.HTTPError as exc:
            summary['voice'] = {'status':'UNAVAILABLE','error':type(exc).__name__}
        try:
            response = client.get('/dashboard/whatsapp/diagnostics'); response.raise_for_status()
            data = response.json()
            # Do not export contacts, message IDs, raw diagnostics or auth paths.
            summary['whatsapp'] = {k:data.get(k) for k in ('overall_state','history_sync_state','history_complete',
                'transport_connected','event_stream_verified','authenticated','chat_snapshot_current')}
            identity = data.get('bridge_identity') or {}
            summary['whatsapp']['read_only'] = identity.get('read_only', 'NOT_REPORTED')
        except httpx.HTTPError as exc:
            summary['whatsapp'] = {'status':'UNAVAILABLE','error':type(exc).__name__}
        # Fresh credentials only: token refresh is explicitly forbidden here.
        from jarvis.integrations.google.auth.manager import GoogleAuthManager
        auth = GoogleAuthManager()
        accounts = auth.list_accounts()
        summary['google'] = {'accounts':len(accounts),
            'status':'AUTH_MISSING' if not accounts else 'NOT_TESTED',
            'reason':'No fresh in-process access credentials available to collector; no OAuth refresh attempted'}
        summary['phone'] = 'PHONE_NOT_READY; authenticated pairing not verified'
        summary['mcp'] = 'MCP_NOT_TESTED; disabled'
        summary['code_agent'] = 'NOT_IMPLEMENTED; existing registered project tools retained'
        summary['research_agent'] = 'Existing bounded web path; no new autonomous agent'
        try:
            with httpx.Client(base_url='http://127.0.0.1:11434', timeout=5) as ollama:
                tags = ollama.get('/api/tags'); tags.raise_for_status()
                running = ollama.get('/api/ps'); running.raise_for_status()
                summary['models'] = {'installed':[{k:m.get(k) for k in ('name','size','digest','details')} for m in tags.json().get('models',[])],
                    'resident':[{k:m.get(k) for k in ('name','size','size_vram','context_length')} for m in running.json().get('models',[])],
                    'provider':'Ollama local API; no downloads or model loads requested by inventory'}
        except httpx.HTTPError as exc:
            summary['models'] = {'status':'UNAVAILABLE','error':type(exc).__name__}
        (OUT / 'windows-private-results.json').write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding='utf-8')
    summary['hardware_after'] = hardware()
    summary['final_status'] = 'MORE_DEVELOPMENT_REQUIRED'
    (OUT / 'windows-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--web', action='store_true', help='Attempt bounded conversational web acceptance')
    args = parser.parse_args()
    print(json.dumps(run(args.web), indent=2))
