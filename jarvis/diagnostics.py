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
    for module in ('sounddevice', 'faster_whisper', 'openwakeword', 'silero_vad_lite', 'piper', 'keyboard', 'scipy',
                   'playwright', 'uiautomation', 'win32gui', 'PIL'):
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
    _voice_model_checks(config, add)
    _ollama_checks(config, add)
    add('Google', 'WARN', 'DISCONNECTED; optional')
    return checks


def _voice_model_checks(config, add):
    project = ROOT.parent
    fix = 'run: python scripts/setup_models.py'
    stt = project / config.voice.stt_model
    if stt.is_dir():
        ok = (stt / 'model.bin').exists()
        add('Speech model (Whisper)', 'PASS' if ok else 'WARN',
            str(stt) if ok else f'{stt} has no model.bin (downloads on first use; {fix})')
    else:
        add('Speech model (Whisper)', 'PASS', f'{config.voice.stt_model} (downloaded by faster-whisper on first use)')
    wake = project / config.voice.model_path
    add('Wake word model', 'PASS' if wake.exists() else 'WARN', str(wake) if wake.exists() else f'missing: {wake} (built-in "hey_jarvis" is used)')
    try:
        import tomllib
        with (project / 'config/response.toml').open('rb') as f:
            tts_path = project / tomllib.load(f)['tts']['model_path']
        add('Voice model (Piper)', 'PASS' if tts_path.exists() else 'WARN',
            str(tts_path) if tts_path.exists() else f'missing {tts_path.name} (Windows SAPI voice is used instead; {fix})')
    except Exception as exc:
        add('Voice model (Piper)', 'WARN', f'Could not read config/response.toml: {exc}')


def _ollama_checks(config, add):
    from jarvis.core.llm.client import LLMSettings, choose_fallback, match_installed
    settings = LLMSettings.from_config(config)
    try:
        with urlopen(f'{settings.base_url}/api/tags', timeout=3) as response:
            models = [m['name'] for m in json.load(response).get('models', [])]
    except Exception as exc:
        add('Ollama', 'WARN', f'Not reachable at {settings.base_url} ({type(exc).__name__}). JARVIS starts it automatically '
                              'when installed; deterministic commands work without it.')
        return
    add('Ollama', 'PASS', f'{settings.base_url}: {", ".join(models) or "no models installed"}')
    for role in ('fast', 'planner', 'chat', 'embed'):
        wanted = settings.model_for(role)
        exact = match_installed(wanted, models)
        if exact:
            add(f'AI role: {role}', 'PASS', exact)
            continue
        fallback = choose_fallback(role, models)
        hint = f'ollama pull {wanted}' if wanted else 'set it in [models]'
        if fallback:
            add(f'AI role: {role}', 'WARN', f'{wanted or "(unset)"} not installed; using {fallback}. For best results: {hint}')
        else:
            add(f'AI role: {role}', 'WARN', f'no suitable model installed; run: {hint}')


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
