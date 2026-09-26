"""Download / verify every local model JARVIS needs (idempotent, safe to re-run).

    python scripts/setup_models.py            # speech (Whisper), voice (Piper), wake word, Ollama models
    python scripts/setup_models.py --no-ollama
    python scripts/setup_models.py --check    # report only, download nothing
    python scripts/setup_models.py --jde      # also fetch GloVe vectors for the decision engine's glove+hash model

Large model binaries are git-ignored, so a fresh checkout has the folders but not the
weights; without them the voice pipeline cannot start and the wake word never fires.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  downloading {url}")
    with urllib.request.urlopen(url, timeout=60) as resp, tmp.open("wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done / total:6.1%} of {total / 2**20:.0f} MB", end="", flush=True)
    print()
    tmp.replace(dest)


def setup_whisper(config, check: bool) -> bool:
    if config.voice.stt_model in ("auto", "best"):
        try:
            import ctranslate2
            gpu = ctranslate2.get_cuda_device_count() > 0
        except Exception:
            gpu = False
        size = "large-v3-turbo" if gpu else "small.en"
        print(f"[whisper] auto -> '{size}' ({'NVIDIA GPU' if gpu else 'CPU'})")
        if check:
            return True
        try:
            from faster_whisper import download_model
            download_model(size)  # into the faster-whisper cache, used on first start
            print("[whisper] OK")
            return True
        except Exception as exc:
            print(f"[whisper] download failed ({exc}); it will be downloaded on first use")
            return False
    target = PROJECT / config.voice.stt_model
    if not target.is_dir() and "/" not in config.voice.stt_model and "\\" not in config.voice.stt_model:
        print(f"[whisper] using model name '{config.voice.stt_model}' (faster-whisper cache)")
        return True
    if (target / "model.bin").exists():
        print(f"[whisper] OK   {target}")
        return True
    if check:
        print(f"[whisper] MISSING model.bin in {target}")
        return False
    try:
        from faster_whisper import download_model
    except ImportError:
        print("[whisper] faster-whisper is not installed: pip install -e .[voice]")
        return False
    size = target.name if target.name else "base"
    print(f"[whisper] downloading '{size}' into {target}")
    download_model(size, output_dir=str(target))
    ok = (target / "model.bin").exists()
    print(f"[whisper] {'OK' if ok else 'FAILED'}")
    return ok


def setup_piper(check: bool) -> bool:
    with (PROJECT / "config/response.toml").open("rb") as f:
        model_path = PROJECT / tomllib.load(f)["tts"]["model_path"]
    ok = True
    relative = model_path.relative_to(PROJECT / "models/piper").as_posix()
    for suffix in ("", ".json"):
        dest = Path(str(model_path) + suffix)
        if dest.exists():
            continue
        if check:
            print(f"[piper]   MISSING {dest.name}")
            ok = False
            continue
        try:
            _download(PIPER_BASE + relative + suffix, dest)
        except Exception as exc:
            print(f"[piper]   could not download {dest.name}: {exc}")
            ok = False
    if ok:
        print(f"[piper]   OK   {model_path.name}")
    return ok


def setup_wake(config, check: bool) -> bool:
    wake = PROJECT / config.voice.model_path
    if wake.exists():
        print(f"[wake]    OK   {wake.name}")
        return True
    if check:
        print(f"[wake]    MISSING {wake} (built-in hey_jarvis will be downloaded at runtime)")
        return False
    try:
        from openwakeword.utils import download_models
        download_models(model_names=["hey_jarvis"])
        print("[wake]    OK   built-in hey_jarvis model downloaded")
        return True
    except Exception as exc:
        print(f"[wake]    could not download built-in model: {exc}")
        return False


def setup_ollama(config, check: bool) -> bool:
    from jarvis.core.llm.client import find_ollama_executable

    exe = find_ollama_executable()
    if not exe:
        print("[ollama]  not installed - get it from https://ollama.com/download (AI answers, planning and the agent need it)")
        return False
    wanted = [m for m in dict.fromkeys((config.models.fast, config.models.planner, config.models.chat, config.models.embed)) if m]
    try:
        listing = subprocess.run([exe, "list"], capture_output=True, text=True, timeout=20).stdout
    except Exception as exc:
        print(f"[ollama]  could not list models ({exc}); is the server running? (ollama serve)")
        return False
    from jarvis.core.llm.client import match_installed
    installed = [line.split()[0] for line in listing.splitlines()[1:] if line.strip()]
    ok = True
    for model in wanted:
        if match_installed(model, installed):
            print(f"[ollama]  OK   {model}")
            continue
        if check:
            print(f"[ollama]  MISSING {model}  (ollama pull {model})")
            ok = False
            continue
        print(f"[ollama]  pulling {model} ...")
        result = subprocess.run([exe, "pull", model])
        ok = ok and result.returncode == 0
    return ok


def setup_jde(check: bool, want_glove: bool) -> bool:
    """The decision engine ships its trained heads in models/jde; only the optional GloVe backbone is downloaded."""
    from jarvis.decision.engine import latest_model_dir
    from jarvis.decision.static_vectors import VECTORS_FILE, build_glove

    if want_glove and not VECTORS_FILE.exists():
        if check:
            print(f"[jde]     MISSING {VECTORS_FILE.name} (python scripts/setup_models.py --jde)")
        else:
            print("[jde]     downloading GloVe 100-d word vectors (~130 MB, once) ...")
            try:
                build_glove()
            except Exception as exc:
                print(f"[jde]     GloVe download failed ({exc}); the hash encoder model still works")
    model = latest_model_dir()
    if model is None:
        print("[jde]     no trained model in models/jde (python -m jarvis.decision.train --promote); routing is unaffected")
        return True
    try:
        from jarvis.decision.engine import LocalJDE
        LocalJDE.load(model)
        print(f"[jde]     OK   {model.name}")
    except Exception as exc:
        print(f"[jde]     {model.name} cannot load here ({exc}); JDE stays off, routing is unaffected")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="only report what is missing")
    parser.add_argument("--no-ollama", action="store_true", help="skip pulling Ollama models")
    parser.add_argument("--jde", action="store_true", help="download GloVe vectors for the decision engine")
    args = parser.parse_args()

    from jarvis.config import load
    config = load()
    results = [
        setup_whisper(config, args.check),
        setup_piper(args.check),
        setup_wake(config, args.check),
        setup_jde(args.check, args.jde),
    ]
    if not args.no_ollama:
        results.append(setup_ollama(config, args.check))
    print("\nAll models ready." if all(results) else "\nSome items need attention (see above). Voice still starts with fallbacks where possible.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
