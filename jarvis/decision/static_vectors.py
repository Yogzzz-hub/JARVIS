"""Pretrained static word vectors as an offline semantic backbone (no torch, no ONNX, no HuggingFace).

``build_static_vectors()`` extracts the 300-d word vectors that ship inside the spaCy
``en_core_web_md`` model wheel (downloaded from GitHub releases) WITHOUT installing spaCy: the wheel's
``strings.json`` is hashed with spaCy's MurmurHash64A (seed 1) and joined with the msgpack ``key2row``
map. The result is a compact ``static-vectors.npz`` (float16) in ``models/jde/encoders``.

``StaticVectorEncoder`` embeds a sentence as the weighted mean of its word vectors (stop words
down-weighted), L2-normalised - sub-millisecond on CPU, a few tens of MB of RAM.
"""
from __future__ import annotations

import io
import json
import logging
import re
import struct
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from jarvis.decision.encoder import ENCODER_CACHE_DIR, normalize_text

logger = logging.getLogger("jarvis.decision.static_vectors")

WHEEL_URL = "https://github.com/explosion/spacy-models/releases/download/en_core_web_md-3.8.0/en_core_web_md-3.8.0-py3-none-any.whl"
GLOVE_URL = "https://github.com/RaRe-Technologies/gensim-data/releases/download/glove-wiki-gigaword-100/glove-wiki-gigaword-100.gz"
VECTORS_FILE = ENCODER_CACHE_DIR / "static-vectors.npz"
_MASK = (1 << 64) - 1

STOP = set("""a an the of to in on at for from by with and or but if then so is are was were be been being am do does did
i me my mine you your yours he him his she her they them their it its we us our this that these those there here
please pls can could would will shall should just really very some any all""".split())


def murmurhash64a(data: bytes, seed: int = 1) -> int:
    m, r = 0xC6A4A7935BD1E995, 47
    h = (seed ^ ((len(data) * m) & _MASK)) & _MASK
    nblocks = len(data) // 8
    for i in range(nblocks):
        k = int.from_bytes(data[8 * i: 8 * i + 8], "little")
        k = (k * m) & _MASK
        k ^= k >> r
        k = (k * m) & _MASK
        h ^= k
        h = (h * m) & _MASK
    tail = data[nblocks * 8:]
    if tail:
        for idx in range(len(tail) - 1, -1, -1):
            h ^= tail[idx] << (8 * idx)
        h = (h * m) & _MASK
    h ^= h >> r
    h = (h * m) & _MASK
    h ^= h >> r
    return h


def _read_key2row(buf: bytes) -> dict[int, int]:
    """Minimal msgpack reader for spaCy's {uint64: int} key2row map."""
    pos = 0

    def read_uint() -> int:
        nonlocal pos
        b = buf[pos]
        pos += 1
        if b <= 0x7F:
            return b
        fmt = {0xCC: ">B", 0xCD: ">H", 0xCE: ">I", 0xCF: ">Q", 0xD0: ">b", 0xD1: ">h", 0xD2: ">i", 0xD3: ">q"}[b]
        size = struct.calcsize(fmt)
        v = struct.unpack(fmt, buf[pos: pos + size])[0]
        pos += size
        return v

    head = buf[pos]
    pos += 1
    if head == 0xDF:
        n = struct.unpack(">I", buf[pos: pos + 4])[0]
        pos += 4
    elif head == 0xDE:
        n = struct.unpack(">H", buf[pos: pos + 2])[0]
        pos += 2
    else:
        n = head & 0x0F
    out = {}
    for _ in range(n):
        k = read_uint()
        out[k] = read_uint()
    return out


def build_static_vectors(wheel: Optional[Path] = None, out: Path = VECTORS_FILE, max_words: int = 400_000) -> Path:
    if wheel is None or not Path(wheel).exists():
        logger.info("Downloading %s", WHEEL_URL)
        data = urllib.request.urlopen(WHEEL_URL, timeout=120).read()
        zf = zipfile.ZipFile(io.BytesIO(data))
    else:
        zf = zipfile.ZipFile(wheel)
    base = next(n for n in zf.namelist() if n.endswith("vocab/vectors")).rsplit("/", 1)[0]
    vectors = np.load(io.BytesIO(zf.read(base + "/vectors")))
    key2row = _read_key2row(zf.read(base + "/key2row"))
    strings = json.loads(zf.read(base + "/strings.json"))
    words, rows = [], []
    word_re = re.compile(r"^[a-z][a-z'\-]{0,24}$")
    for s in strings:
        if not word_re.match(s):
            continue
        row = key2row.get(murmurhash64a(s.encode("utf-8")))
        if row is None:
            continue
        words.append(s)
        rows.append(row)
        if len(words) >= max_words:
            break
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, words=np.asarray(words), rows=np.asarray(rows, dtype=np.int32),
                        vectors=vectors.astype(np.float16))
    logger.info("Saved %d words -> %s", len(words), out)
    return out


def build_glove(source: Optional[Path] = None, out: Path = VECTORS_FILE, max_words: int = 150_000) -> Path:
    """GloVe 6B 100-d (Wikipedia + Gigaword), frequency-ordered: keep the most frequent ``max_words``."""
    import gzip

    if source is None or not Path(source).exists():
        logger.info("Downloading %s", GLOVE_URL)
        tmp = ENCODER_CACHE_DIR / "glove.gz.part"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(GLOVE_URL, timeout=600) as resp, open(tmp, "wb") as f:
            while chunk := resp.read(1 << 20):
                f.write(chunk)
        source = tmp
    words, vecs = [], []
    with gzip.open(source, "rt", encoding="utf-8", errors="ignore") as f:
        first = f.readline().split()
        if len(first) != 2:  # no word2vec header line
            words.append(first[0])
            vecs.append(np.asarray(first[1:], dtype=np.float32))
        for line in f:
            parts = line.rstrip().split(" ")
            if len(parts) < 50:
                continue
            words.append(parts[0])
            vecs.append(np.asarray(parts[1:], dtype=np.float32))
            if len(words) >= max_words:
                break
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, words=np.asarray(words), rows=np.arange(len(words), dtype=np.int32),
                        vectors=np.vstack(vecs).astype(np.float16), ranked=np.asarray([1]))
    if source.name.endswith(".part"):
        source.unlink(missing_ok=True)
    logger.info("Saved %d GloVe words -> %s", len(words), out)
    return out


class StaticVectorEncoder:
    def __init__(self, path: Path = VECTORS_FILE):
        if not Path(path).exists():
            raise FileNotFoundError(f"{path} missing. Build it: python -m jarvis.decision.static_vectors")
        data = np.load(path)
        self._index = {w: int(r) for w, r in zip(data["words"].tolist(), data["rows"].tolist())}
        V = data["vectors"].astype(np.float32)
        norms = np.linalg.norm(V, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._V = V / norms
        self.dim = int(V.shape[1])
        # frequency-ranked vocabularies (GloVe): SIF-style weight a / (a + p(w)), p ~ Zipf(rank)
        self._ranked = "ranked" in data.files
        self.name = f"static-glove{self.dim}" if self._ranked else f"static-spacy{self.dim}"

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            words = re.findall(r"[a-z][a-z']*", normalize_text(t))
            acc, wsum = np.zeros(self.dim, dtype=np.float32), 0.0
            for w in words:
                row = self._index.get(w) or self._index.get(w.rstrip("s"))
                if row is None:
                    continue
                if self._ranked:
                    p = 1.0 / ((row + 10) * 12.0)
                    weight = 1e-3 / (1e-3 + p)
                else:
                    weight = 0.25 if w in STOP else 1.0
                acc += weight * self._V[row]
                wsum += weight
            if wsum:
                v = acc / wsum
                out[i] = v / (np.linalg.norm(v) or 1.0)
        return out


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    print(build_static_vectors(arg) if arg and arg.suffix == ".whl" else build_glove(arg))
