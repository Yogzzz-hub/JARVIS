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
    router_ai: Literal[False] = False
    planner: Literal[False] = False
    voice: Literal[False] = False
    tts: Literal[False] = False
    phone: Literal[False] = False
    google: Literal[False] = False
    browser: Literal[False] = False
    vision: Literal[False] = False

class Models(Frozen):
    fast: Literal[""] = ""
    planner: Literal[""] = ""
    vision: Literal[""] = ""

class SearchConfig(Frozen):
    roots: tuple[str, ...] = (
        "%USERPROFILE%\\Desktop",
        "%USERPROFILE%\\Documents",
        "%USERPROFILE%\\Downloads",
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

class Config(Frozen):
    server: Server = Server()
    performance: Performance = Performance()
    database: Database = Database()
    paths: Paths = Paths()
    features: Features = Features()
    models: Models = Models()
    search: SearchConfig = SearchConfig()
    aliases: tuple[tuple[str, str], ...] = ()

def load(path: Path | None = None) -> Config:
    with (path or ROOT / "config/jarvis.toml").open("rb") as file:
        data = tomllib.load(file)
    data["aliases"] = tuple(data.get("aliases", {}).items())
    return Config.model_validate(data)
