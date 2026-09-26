from pathlib import Path
from typing import Literal
import tomllib
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]

class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

class Server(Frozen):
    host: Literal["127.0.0.1"] = "127.0.0.1"
    port: int = Field(default=8765, ge=1024, le=65535)
    workers: Literal[1] = 1
    http_backend: Literal["httptools", "h11"] = "httptools"
    ws_backend: Literal["websockets-sansio", "wsproto"] = "websockets-sansio"
    ws_compression: Literal[False] = False
    access_log: bool = False

class Performance(Frozen):
    event_queue_size: int = Field(default=1024, ge=1, le=65536)
    persistence_queue_size: int = Field(default=4096, ge=1, le=65536)
    metric_queue_size: int = Field(default=4096, ge=1, le=65536)
    verify_poll_ms: int = Field(default=50, ge=1)
    verify_timeout_ms: int = Field(default=3000, ge=1)

class Database(Frozen):
    journal_mode: Literal["WAL"] = "WAL"
    synchronous: Literal["NORMAL"] = "NORMAL"
    busy_timeout_ms: int = Field(default=3000, ge=1)

class Paths(Frozen):
    db: str = "db/jarvis.db"
    logs: str = "logs/jarvis.jsonl"
    models: str = "models"

class Features(Frozen):
    router_ai: bool = True
    planner: bool = True
    voice: bool = False
    tts: bool = False
    phone: bool = False
    google: bool = False
    browser: bool = False
    vision: bool = False

class Models(Frozen):
    """Ollama model roles. Any role whose model is not pulled falls back to the best installed model."""
    fast: str = ""
    planner: str = ""
    chat: str = ""
    vision: str = ""
    embed: str = "nomic-embed-text"
    base_url: str = "http://127.0.0.1:11434"
    keep_alive: str = "30m"
    timeout_s: float = Field(default=60.0, gt=0, le=600)
    num_ctx: int = Field(default=4096, ge=1024, le=131072)
    auto_start: bool = True
    warm_on_start: bool = True

class SearchConfig(Frozen):
    roots: tuple[str, ...] = (
        "%USERPROFILE%\\Desktop",
        "%USERPROFILE%\\Documents",
        "%USERPROFILE%\\Downloads",
        "%USERPROFILE%\\OneDrive\\Desktop",
        "%USERPROFILE%\\OneDrive\\Documents",
    )
    exclude_patterns: tuple[str, ...] = (
        ".git", "node_modules", "venv", ".venv", "__pycache__", "AppData",
        "Windows", "Program Files", "Program Files (x86)", "$Recycle.Bin",
        "System Volume Information", "browser caches"
    )
    max_file_size_mb: float = 25.0
    max_text_chars: int = 100_000
    max_pdf_pages: int = 50
    max_extraction_seconds: float = 3.0
    fts_prefix: str = "2 3 4"
    cache_capacity: int = 2048
    enrichment_batch_size: int = 250
    enable_usn: bool = False
    enable_semantic: bool = True

class VoiceConfig(Frozen):
    device: str | int | None = None
    wake_enabled: bool = True
    ptt_enabled: bool = True
    model_path: str = "models/wake/hey_jarvis_v0.1.onnx"
    threshold: float = Field(default=0.5, ge=0, le=1)
    stt_model: str = "auto"
    stt_device: Literal["auto", "cpu", "cuda"] = "auto"
    compute_type: str = "int8"
    stt_beam_size: int = Field(default=5, ge=1, le=10)
    preroll_ms: int = Field(default=500, ge=0, le=2000)
    # How long a pause ends your turn (ms). Longer for unfinished sentences, shorter for finished commands.
    endpoint_silence_ms: int = Field(default=800, ge=200, le=4000)
    max_utterance_s: float = Field(default=45.0, ge=5, le=180)
    # What JARVIS does when it hears "Hey Jarvis": a short chime, a spoken acknowledgement, or nothing.
    wake_ack: Literal["chime", "voice", "none"] = "chime"

class DecisionConfig(Frozen):
    # JARVIS Decision Engine rollout stage: "off", "shadow" (log only) or "read_only" (stage B).
    stage: Literal["off", "shadow", "read_only"] = "shadow"

class Config(Frozen):
    server: Server = Server()
    performance: Performance = Performance()
    database: Database = Database()
    paths: Paths = Paths()
    features: Features = Features()
    models: Models = Models()
    search: SearchConfig = SearchConfig()
    voice: VoiceConfig = VoiceConfig()
    decision: DecisionConfig = DecisionConfig()
    aliases: tuple[tuple[str, str], ...] = ()

def load(path: Path | None = None) -> Config:
    with (path or ROOT / "config/jarvis.toml").open("rb") as file:
        data = tomllib.load(file)
    data["aliases"] = tuple(data.get("aliases", {}).items())
    # TOML arrays decode as lists; preserve strict tuple schemas internally.
    for key in ("roots", "exclude_patterns"):
        if key in data.get("search", {}):
            data["search"][key] = tuple(data["search"][key])
    return Config.model_validate(data)
