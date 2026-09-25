# JARVIS ULTRA — THIRD-PARTY LICENSES & COMPLIANCE MATRIX

## 1. Governance Principle: Code Licence vs. Model Weight Licence
Under the JARVIS ULTRA architecture, code licences and model weight licences are strictly tracked separately. Permissive code licences (e.g., Apache-2.0, MIT) often bundle or link model weights with differing obligations (e.g., CC BY-NC-SA 4.0, GPL-3.0, or restrictive non-commercial terms).

---

## 2. Component Licensing Matrix

| Subsystem / Layer | Component / Library | Upstream Source | Code Licence | Model / Weight Licence | Distribution & Commercial Implication |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Wake Engine** | openWakeWord | [dscripka/openWakeWord](https://github.com/dscripka/openWakeWord) | Apache-2.0 | Bundled Pretrained Models: **CC BY-NC-SA 4.0** | Commercial redistribution of bundled weights requires explicit model licensing or custom models trained from scratch under permissive terms. |
| **Acoustic VAD** | Silero VAD Lite | [snakers4/silero-vad](https://github.com/snakers4/silero-vad) | MIT | **MIT** | Fully permissive. Suitable for unrestricted local use and distribution. |
| **Thought Endpointing** | Pipecat Smart Turn | [pipecat-ai/smart-turn](https://github.com/pipecat-ai/smart-turn) | BSD-2-Clause | **BSD-2-Clause / Open Model** | Permissive 8M parameter int8 ONNX model (~8 MB). Fully self-contained. |
| **Streaming STT** | Faster-Whisper | [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | OpenAI Whisper Weights: **MIT** | Fully permissive. CTranslate2 runtime is MIT. |
| **Alternative STT** | sherpa-onnx | [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | Apache-2.0 | Nemotron: **NVIDIA Open Model License**; Parakeet: **CC-BY-4.0** | Permissive with standard attribution and NVIDIA model terms. |
| **Alternative STT** | Moonshine | [moonshine-ai/moonshine](https://github.com/moonshine-ai/moonshine) | MIT | **MIT** | Permissive weights and runtime designed for low-latency local execution. |
| **Lightweight STT** | Vosk | [alphacep/vosk-api](https://github.com/alphacep/vosk-api) | Apache-2.0 | **Apache-2.0 / Kaldi Public** | Fully permissive emergency fallback. |
| **TTS Engine** | Piper (Current) | [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl) | GPL-3.0 | Voice Weights: **MIT / Open Public Domain** | Maintained by Open Home Foundation (moved from archived Rhasspy). Code is GPL-3.0; Python wrapper invoked as isolated process/library. |
| **TTS Alternative** | Kokoro | [hexgrad/kokoro](https://github.com/hexgrad/kokoro) | Apache-2.0 | **Apache-2.0** | 82M parameter permissive TTS model. Highly attractive quality alternative. |
| **TTS Non-Default** | Coqui / XTTS | [idiap/coqui-ai-TTS](https://github.com/idiap/coqui-ai-TTS) | MPL-2.0 | XTTS v2 Weights: **Coqui Public Model License (CPML)** | **REJECTED AS DEFAULT**: Non-commercial restriction in CPML weights prevents unrestricted deployment. |
| **Generative Models** | Qwen3.5 Series (0.8B, 4B) | [QwenLM/Qwen3.5](https://github.com/QwenLM) | Apache-2.0 | **Apache-2.0** | Permissive weights and architecture supported natively by llama.cpp. |
| **Vision Model** | Qwen3-VL-2B-Instruct | [QwenLM/Qwen3-VL](https://github.com/QwenLM/Qwen3-VL) | Apache-2.0 | **Apache-2.0** | Permissive multimodal weights. |
| **Visual Parser** | OmniParser v2 | [microsoft/OmniParser](https://github.com/microsoft/OmniParser) | MIT (repo) | `icon_detect_v3`: **MIT (YOLOv9)**; Caption: **MIT** | Current v3 detector is MIT-clean; older Ultralytics-derived weights carry AGPL obligations and are explicitly avoided. |
| **Browser Engine** | Playwright | [microsoft/playwright](https://github.com/microsoft/playwright) | Apache-2.0 | N/A (Chromium binaries: BSD-style) | Fully permissive. |
| **Screen Capture** | python-mss | [BoboTiG/python-mss](https://github.com/BoboTiG/python-mss) | MIT | N/A | Permissive direct GDI/DIBSection memory capture on Windows. |
| **Native API & UIA** | pywin32, uiautomation | PSF / Apache-2.0 | Permissive | N/A | Standard Windows platform wrappers. |
| **Desktop UI** | PySide6 (Qt Quick) | The Qt Company | LGPL-3.0 | N/A | Dynamically linked Qt 6 bindings; source modification not required; compliant under LGPL-3.0. |

---

## 3. Compliance Action Items
1. **Never conflate code licence with model weight licence**.
2. **Exclude restrictive non-commercial weights** (e.g. Coqui CPML) from standard automated deployment pipelines.
3. **Verify OmniParser detector version**: If OmniParser is downloaded, strictly verify that `icon_detect_v3` (MIT) is used rather than legacy AGPL weights.
