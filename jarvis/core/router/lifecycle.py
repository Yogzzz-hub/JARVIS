import asyncio
from enum import StrEnum
import logging
import time
import httpx

class ModelLifecycleState(StrEnum):
    UNLOADED = "UNLOADED"
    LOADING = "LOADING"
    WARM = "WARM"
    IDLE = "IDLE"

class ModelLifecycleManager:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3:0.6b",
        initial_keep_alive: str = "2m",
        idle_unload_seconds: float = 180.0,
    ):
        self.base_url = base_url
        self.model = model
        self.initial_keep_alive = initial_keep_alive
        self.idle_unload_seconds = idle_unload_seconds
        self.state = ModelLifecycleState.UNLOADED
        self.last_used: float = 0.0
        self.consecutive_uses: int = 0
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=5.0)
        return self._client

    async def touch(self):
        """Called upon successful Lane 1 inference."""
        async with self._lock:
            self.last_used = time.time()
            self.consecutive_uses += 1
            self.state = ModelLifecycleState.WARM

    async def prewarm(self):
        """Asynchronously prewarms the model without blocking startup."""
        async with self._lock:
            if self.state == ModelLifecycleState.WARM:
                return
            self.state = ModelLifecycleState.LOADING
            try:
                client = await self._get_client()
                # A 0-token predict loads model weights into memory
                resp = await client.post(
                    "/api/generate",
                    json={"model": self.model, "prompt": "", "keep_alive": self.initial_keep_alive},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    self.state = ModelLifecycleState.WARM
                    self.last_used = time.time()
                    logging.getLogger("jarvis.router.model").info("Model %s prewarmed successfully", self.model)
                else:
                    self.state = ModelLifecycleState.UNLOADED
            except Exception as exc:
                self.state = ModelLifecycleState.UNLOADED
                logging.getLogger("jarvis.router.model").debug("Prewarm skipped or unavailable: %s", exc)

    async def unload(self):
        """Forces immediate model eviction from VRAM."""
        async with self._lock:
            try:
                client = await self._get_client()
                await client.post(
                    "/api/generate",
                    json={"model": self.model, "keep_alive": 0},
                    timeout=5.0,
                )
                self.state = ModelLifecycleState.UNLOADED
                self.consecutive_uses = 0
                logging.getLogger("jarvis.router.model").info("Model %s unloaded", self.model)
            except Exception:
                self.state = ModelLifecycleState.UNLOADED

    async def check_idle(self):
        """Unloads if idle longer than configured threshold."""
        if self.state == ModelLifecycleState.WARM and (time.time() - self.last_used) > self.idle_unload_seconds:
            await self.unload()

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
