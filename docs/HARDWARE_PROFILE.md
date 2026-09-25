# JARVIS ULTRA — PHYSICAL HARDWARE PROFILE

## 1. System Hardware Specifications

This profile was collected directly from the active host machine using Windows Management Instrumentation (WMI) and PowerShell hardware inspection commands on 18 September 2026.

```
Host Architecture:         x86_64 (64-bit)
Operating System:          Microsoft Windows 11 Home (64-bit)
OS Build / Version:        10.0.26200
```

### Central Processing Unit (CPU)
- **Model**: 12th Gen Intel(R) Core(TM) i5-12450HX
- **Physical Cores**: 8
- **Logical Processors / Threads**: 12
- **Base Clock**: 2.40 GHz (Turbo up to 4.40 GHz)
- **Architecture**: Alder Lake Hybrid (4 Performance cores + 4 Efficient cores)
- **L3 Cache**: 12 MB Intel Smart Cache

### System Memory (RAM)
- **Total Physical RAM**: 16.00 GB (15.73 GB usable)
- **Type**: DDR4 / DDR5 High-Speed SO-DIMM
- **Pagefile / Virtual Memory**: Managed by Windows

### Graphics Processing Unit (GPU)
- **Dedicated GPU**: NVIDIA GeForce RTX 3050 6GB Laptop GPU
  - **Dedicated VRAM**: 6,144 MiB GDDR6 (6 GB)
  - **NVIDIA Driver Version**: 32.0.15.7705 (Release 577.05)
  - **CUDA Version Support**: CUDA 12.x capable
  - **Memory Bus Width**: 96-bit
- **Integrated GPU**: Intel(R) UHD Graphics (Alder Lake-P 16EU)
  - **Adapter RAM**: 2,048 MB shared

### Audio Subsystem
- **Physical Capture Device (Default Input)**: Microphone Array (Realtek(R) Audio)
  - Supported Native Rates: 44,100 Hz / 48,000 Hz, 16/24-bit PCM
- **Physical Playback Device (Default Output)**: Speakers (Realtek(R) Audio)
  - Supported Native Rates: 48,000 Hz stereo 24-bit PCM
- **Virtual Audio Endpoints**:
  - Nahimic VAD & Nahimic Mirroring Device
  - NVIDIA High Definition Audio (HDMI / DisplayPort output)
  - NVIDIA Virtual Audio Device (Wave Extensible) (WDM)

### Persistent Storage
- **Primary Drive (C:)**: NVMe PCIe M.2 Solid State Drive
  - **Total Capacity**: ~476 GB
  - **Used Space**: ~328 GB
  - **Free Space**: ~146.8 GB (Ample space for models, virtual environments, and caches)

---

## 2. Hardware Implications for JARVIS ULTRA Architecture

1. **GPU Residency Constraint (6 GB VRAM)**:
   - With 6 GB VRAM, the system comfortably runs **one** major generative model or VLM resident at a time.
   - **Primary Planner**: Qwen3.5-4B Q4 (~2.8 GB VRAM) or Qwen3.5-0.8B Q4 (~0.6 GB VRAM).
   - **Vision Fallback**: Qwen3-VL-2B-Instruct Q4 (~1.8 GB VRAM).
   - `ResourceGovernor` must enforce mutually exclusive eviction between heavy planner reasoning and visual grounding to avoid Out-Of-Memory (OOM) allocations.
2. **CPU Offload Strategy (12 Threads)**:
   - The 12-thread Intel i5-12450HX provides strong parallel throughput.
   - Acoustic wake detection (`openWakeWord`), speech segmentation (`Silero VADLite`), and streaming transcription (`Faster-Whisper int8` / `sherpa-onnx`) run on CPU without competing for GPU VRAM.
   - Audio ring buffers and IPC queues execute lock-free in high-speed RAM.
3. **Audio Synchronization**:
   - Single-owner `AudioHub` captures at the hardware native rate (48 kHz) and executes a single canonical resampling step to 16,000 Hz mono PCM16 to feed wake, VAD, and ASR concurrently without duplicate device contention.
