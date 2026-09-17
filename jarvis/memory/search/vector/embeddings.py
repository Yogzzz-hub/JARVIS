from collections import OrderedDict
import hashlib
import math
from typing import Protocol, runtime_checkable
import httpx

@runtime_checkable
class EmbeddingProvider(Protocol):
    dimension: int

    async def embed(self, text: str) -> list[float]:
        ...

class MockEmbeddingProvider:
    """Deterministic, zero-download embedding provider for testing and offline execution."""
    def __init__(self, dimension: int = 384, dim: int | None = None):
        self.dimension = dim if dim is not None else dimension

    async def embed(self, text: str) -> list[float]:
        # Generate pseudo-vector from text hash
        vec = []
        clean = text.strip().casefold()
        for i in range(self.dimension):
            h = hashlib.md5(f"{clean}:{i}".encode("utf-8")).hexdigest()
            val = (int(h[:4], 16) / 32768.0) - 1.0
            vec.append(val)
        # Normalize to unit length
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

class OllamaEmbeddingProvider:
    """Ollama local embedding provider using all-minilm or bge-small."""
    def __init__(self, model: str = "all-minilm", base_url: str = "http://127.0.0.1:11434", dimension: int = 384):
        self.model = model
        self.base_url = base_url
        self.dimension = dimension
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=5.0)
        return self._client

    async def embed(self, text: str) -> list[float]:
        client = await self._get_client()
        resp = await client.post("/api/embeddings", json={"model": self.model, "prompt": text})
        if resp.status_code == 200:
            data = resp.json()
            return data.get("embedding", [0.0] * self.dimension)
        raise RuntimeError(f"Ollama embedding failed with HTTP {resp.status_code}")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

class QueryEmbeddingCache:
    """Bounded LRU cache for query vectors."""
    def __init__(self, capacity: int = 1024):
        self.capacity = capacity
        self._cache: OrderedDict[str, list[float]] = OrderedDict()

    def get(self, text: str) -> list[float] | None:
        key = text.strip().casefold()
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, text: str, vector: list[float]):
        key = text.strip().casefold()
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = vector
            return
        if len(self._cache) >= self.capacity:
            self._cache.popitem(last=False)
        self._cache[key] = vector
