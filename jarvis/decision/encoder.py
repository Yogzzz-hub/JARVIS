"""Text encoders for JDE. The architecture depends only on ``DecisionEncoder``; backends are swappable.

* ``HashingEncoder``   - dependency-free, offline, deterministic: word 1-2 grams + character 3-5 grams hashed
                         into a fixed vector (sublinear TF, L2-normalised). Always available.
* ``FastEmbedEncoder`` - ONNX sentence embeddings on CPU via FastEmbed (all-MiniLM-L6-v2, BGE-small-en-v1.5, ...).
                         Models are downloaded once into ``models/jde/encoders`` (or loaded from there offline).
* ``ConcatEncoder``    - dense semantic + hashed lexical, so rare tokens (app names, file types) still count.
"""
from __future__ import annotations

import logging
import re
import threading
import zlib
from pathlib import Path
from typing import Iterable, Protocol, Sequence

import numpy as np

logger = logging.getLogger("jarvis.decision.encoder")

ENCODER_CACHE_DIR = Path(__file__).resolve().parents[2] / "models" / "jde" / "encoders"

FASTEMBED_MODELS = {
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",
    "bge-small": "BAAI/bge-small-en-v1.5",
}


class DecisionEncoder(Protocol):
    name: str
    dim: int

    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def normalize_text(text: str) -> str:
    t = (text or "").lower().replace("’", "'")
    t = re.sub(r"https?://\S+", " urltoken ", t)
    t = re.sub(r"\b\S+\.(?:pdf|docx?|xlsx?|pptx?|txt|csv|png|jpe?g|mp[34]|zip|exe|py|js)\b", lambda m: " filetoken " + m.group(0).rsplit(".", 1)[1], t)
    t = re.sub(r"\+?\d[\d\s-]{7,}\d", " phonenumbertoken ", t)
    t = re.sub(r"\d+", " 0 ", t)
    return re.sub(r"\s+", " ", t).strip()


class HashingEncoder:
    """Deterministic feature hashing (crc32), so vectors are identical across processes and machines."""

    def __init__(self, dim: int = 4096, char_ngrams: tuple[int, int] = (3, 5)):
        self.dim = dim
        self.char_ngrams = char_ngrams
        self.name = f"hash-{dim}"

    def _features(self, text: str) -> dict[int, float]:
        t = normalize_text(text)
        words = _TOKEN.findall(t)
        feats: dict[int, float] = {}

        def add(key: str, weight: float) -> None:
            h = zlib.crc32(key.encode("utf-8"))
            idx = h % self.dim
            sign = 1.0 if (h >> 31) & 1 == 0 else -1.0
            feats[idx] = feats.get(idx, 0.0) + sign * weight

        for w in words:
            add("w:" + w, 1.0)
        for a, b in zip(words, words[1:]):
            add("b:" + a + "_" + b, 0.8)
        if words:
            add("first:" + words[0], 1.2)
            if len(words) > 1:
                add("first2:" + words[0] + "_" + words[1], 0.9)
        lo, hi = self.char_ngrams
        for w in words:
            padded = f" {w} "
            for n in range(lo, hi + 1):
                for i in range(0, max(0, len(padded) - n + 1)):
                    add("c:" + padded[i:i + n], 0.35)
        return feats

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for idx, val in self._features(text).items():
                out[row, idx] = val
        # sublinear scaling keeps long inputs from dominating; then unit length
        out = np.sign(out) * np.log1p(np.abs(out))
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


class FastEmbedEncoder:
    """ONNX CPU sentence embeddings (no torch). Thread-safe lazy load, loaded once per process."""

    def __init__(self, model: str = "minilm", cache_dir: Path | None = None, threads: int | None = None):
        self.model_name = FASTEMBED_MODELS.get(model, model)
        self.name = model
        self.cache_dir = cache_dir or ENCODER_CACHE_DIR
        self.threads = threads
        self._model = None
        self._lock = threading.Lock()
        self.dim = 384

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from fastembed import TextEmbedding

                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    self._model = TextEmbedding(self.model_name, cache_dir=str(self.cache_dir), threads=self.threads)
                    probe = np.asarray(list(self._model.embed(["probe"]))[0], dtype=np.float32)
                    self.dim = int(probe.shape[0])
        return self._model

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        model = self._load()
        prepared = list(texts)
        if "bge" in self.model_name.lower():
            prepared = [t for t in prepared]  # BGE query instruction is optional for short classification inputs
        vecs = np.asarray(list(model.embed(prepared, batch_size=64)), dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms


class ConcatEncoder:
    """[dense semantic ; hashed lexical * weight] - semantics generalise, lexical keeps names/rare tokens."""

    def __init__(self, dense: DecisionEncoder, lexical: DecisionEncoder, lexical_weight: float = 0.6):
        self.dense, self.lexical, self.lexical_weight = dense, lexical, lexical_weight
        self.name = f"{dense.name}+{lexical.name}"

    @property
    def dim(self) -> int:
        return self.dense.dim + self.lexical.dim

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        return np.hstack([self.dense.encode(texts), self.lexical.encode(texts) * self.lexical_weight]).astype(np.float32)


def make_encoder(spec: str) -> DecisionEncoder:
    """'hash' | 'minilm' | 'bge-small' | 'minilm+hash' | 'bge-small+hash' | any FastEmbed model id."""
    spec = (spec or "hash").strip().lower()
    if spec in ("hash", "hashing"):
        return HashingEncoder()
    if spec in ("glove", "static", "spacy"):
        from jarvis.decision.static_vectors import StaticVectorEncoder
        return StaticVectorEncoder()
    if "+" in spec:
        dense, lexical = spec.split("+", 1)
        return ConcatEncoder(make_encoder(dense), make_encoder(lexical))
    return FastEmbedEncoder(spec)


def available_encoders(candidates: Iterable[str] = ("hash", "glove+hash", "minilm+hash", "bge-small+hash")) -> list[str]:
    """Encoders that can actually load here (FastEmbed models need the package + a cached/downloadable model)."""
    ok = []
    for spec in candidates:
        try:
            make_encoder(spec).encode(["open chrome"])
            ok.append(spec)
        except Exception as exc:
            logger.info("Encoder %s unavailable: %s", spec, str(exc)[:160])
    return ok
