# JARVIS ULTRA — MODEL MANIFEST & RESOURCE DIRECTORY

## 1. Executive Model Residency Policy
On the target hardware (NVIDIA GeForce RTX 3050 6GB Laptop GPU with 6,144 MiB VRAM), GPU allocation must be strictly governed by `ResourceGovernor`.
- **CPU Tenant**: Acoustic wake models, acoustic VAD, and streaming speech-to-text models run preferentially on CPU (using int8 CTranslate2 / ONNX Runtime) to preserve dedicated VRAM for generative reasoning.
- **GPU Primary Tenant**: Only **one** major generative or multimodal model is resident in VRAM at any given time.
- **Mutual Exclusion**: If visual grounding (`Qwen3-VL-2B`) is invoked, the planner model (`Qwen3.5-4B`) is evicted if necessary to prevent out-of-memory crashes.

---

## 2. Active Model Inventory

| Role | Model Name | Format / Framework | Local Disk Path | Download Size | Runtime Memory (RAM / VRAM) | Device Target | Residency Policy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Acoustic Wake Word** | `hey_jarvis_v0.1` | ONNX Runtime | `models/wake/hey_jarvis_v0.1.onnx` | ~4.2 MB | ~15 MB RAM | CPU | **ALWAYS HOT** |
| **Audio Feature Extractor**| `melspectrogram` | ONNX Runtime | `models/wake/melspectrogram.onnx` | ~1.1 MB | ~8 MB RAM | CPU | **ALWAYS HOT** |
| **Audio Embedding** | `embedding_model` | ONNX Runtime | `models/wake/embedding_model.onnx` | ~8.5 MB | ~25 MB RAM | CPU | **ALWAYS HOT** |
| **Voice Activity Gate** | Silero VAD Lite v5 | ONNX Runtime | Embedded in `silero-vad-lite` | ~1.8 MB | ~12 MB RAM | CPU | **ALWAYS HOT** |
| **Turn Completion** | Pipecat Smart Turn | ONNX Runtime int8 | `models/smart_turn/smart_turn.onnx` (optional) | ~8.0 MB | ~20 MB RAM | CPU | **HOT UPON SPEECH** |
| **Streaming STT (Primary)**| Whisper Base (int8) | CTranslate2 | `models/whisper/base/` | ~145 MB | ~150 MB RAM / 0 VRAM | CPU | **HOT WHILE SPEAKING** |
| **Fast Spoken Synthesis** | Piper `en_US-ryan-medium`| ONNX Runtime | `models/piper/en/en_US/ryan/medium/` | ~64 MB | ~85 MB RAM | CPU | **ALWAYS HOT** |
| **Spoken Synthesis (Alt)** | Piper `en_US-lessac-medium`| ONNX Runtime | `models/piper/en/en_US/lessac/medium/` | ~62 MB | ~85 MB RAM | CPU | WARM CACHED |
| **Tiny Router (Lane 2)** | Qwen3.5-0.8B Q4_K_M | llama.cpp GGUF / Ollama | `models/gguf/qwen3.5-0.8b-q4.gguf` (candidate) | ~520 MB | ~650 MB RAM | CPU / GPU | **ON DEMAND (TTL: 60s)**|
| **Task Planner (Lane 3)**| Qwen3.5-4B Q4_K_M | llama.cpp GGUF / Ollama | `models/gguf/qwen3.5-4b-q4.gguf` (candidate) | ~2.6 GB | ~2.8 GB VRAM | GPU | **ON DEMAND (MUTEX 1)** |
| **Visual Grounding VLM** | Qwen3-VL-2B-Instruct Q4 | llama.cpp GGUF / Ollama | `models/gguf/qwen3-vl-2b-q4.gguf` (candidate) | ~1.6 GB | ~1.9 GB VRAM | GPU | **ON DEMAND (MUTEX 2)** |

---

## 3. Storage Layout
```
models/
├── piper/
│   └── en/en_US/
│       ├── ryan/medium/en_US-ryan-medium.onnx
│       └── lessac/medium/en_US-lessac-medium.onnx
├── wake/
│   ├── hey_jarvis_v0.1.onnx
│   ├── embedding_model.onnx
│   └── melspectrogram.onnx
└── whisper/
    └── base/
        ├── model.bin (145.2 MB)
        ├── config.json
        ├── tokenizer.json
        └── vocabulary.txt
```
