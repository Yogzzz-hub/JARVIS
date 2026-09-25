"""Read-only deployment checks. Run with python -m jarvis.diagnostics."""
import argparse
import importlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import sqlite3
from urllib.request import urlopen

from jarvis.config import ROOT, load


def collect():
    checks = []

    def add(name, status, detail):
        checks.append(dict(name=name, status=status, detail=detail))

    add('Python', 'PASS' if platform.python_version_tuple()[:2] == ('3', '12') else 'FAIL', platform.python_version())
    try:
        config = load()
        add('Configuration', 'PASS', 'Validated')
    except Exception as exc:
        add('Configuration', 'FAIL', str(exc))
        return checks
    for module in ('fastapi', 'uvicorn', 'httpx', 'pydantic', 'psutil', 'yaml', 'rapidfuzz', 'numpy', 'watchdog'):
        try:
            importlib.import_module(module)
            add(module, 'PASS', 'Import succeeded')
        except Exception as exc:
            add(module, 'FAIL', f'{type(exc).__name__}: {exc}')
    for module in ('sounddevice', 'faster_whisper', 'openwakeword', 'piper', 'playwright', 'uiautomation', 'win32gui', 'PIL'):
        try:
            importlib.import_module(module)
            add(module, 'PASS', 'Installed; feature integration must be checked separately')
        except Exception as exc:
            add(module, 'WARN', f'Optional dependency unavailable: {type(exc).__name__}')
    for name, enabled in config.features.model_dump().items():
        add(f'Feature: {name}', 'PASS' if enabled else 'WARN', 'Enabled' if enabled else 'Disabled in current deployment')
    for executable in ('git', 'winget', 'ffmpeg', 'ollama', 'nvidia-smi'):
        found = shutil.which(executable)
        add(executable, 'PASS' if found else 'WARN', found or 'Not on PATH')
    db = ROOT / config.paths.db
    if db.exists():
        try:
            with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=3) as connection:
                result = connection.execute('PRAGMA quick_check').fetchone()[0]
            add('Database', 'PASS' if result == 'ok' else 'FAIL', result)
        except sqlite3.Error as exc:
            add('Database', 'FAIL', str(exc))
    else:
        add('Database', 'WARN', 'Will be created on first startup')
    try:
        with urlopen(f'http://127.0.0.1:{config.server.port}/health', timeout=2) as response:
            health = json.load(response)
        ready = health.get('status') == 'ready' and health.get('database_status') == 'ready'
        add('Gateway', 'PASS' if ready else 'WARN', json.dumps(health))
    except Exception as exc:
        add('Gateway', 'WARN', f'Not reachable: {type(exc).__name__}; run start.bat')
    try:
        import sounddevice as sd
        add('Audio devices', 'PASS', str(sd.query_devices()))
    except Exception as exc:
        add('Audio devices', 'WARN', str(exc))
    try:
        with urlopen('http://127.0.0.1:11434/api/tags', timeout=2) as response:
            models = [m['name'] for m in json.load(response).get('models', [])]
        add('Ollama models', 'PASS', ', '.join(models) or 'No models installed')
    except Exception as exc:
        add('Ollama models', 'WARN', f'Unavailable: {type(exc).__name__}; deterministic commands remain available')
    add('Google', 'WARN', 'DISCONNECTED; optional')
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    checks = collect()
    if args.json:
        print(json.dumps(checks, indent=2))
    else:
        for check in checks:
            print(f"{check['status']:4} {check['name']}: {check['detail']}")
    return int(any(c['status'] == 'FAIL' for c in checks))


if __name__ == '__main__':
    raise SystemExit(main())
