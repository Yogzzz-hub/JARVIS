# PULSE — Parallel User Latency & Status Engine

## Executive Architecture
PULSE completely decouples JARVIS's Perception & Execution into two concurrent, asynchronous lanes:
1. **Action Lane**: Intent routing, parameter validation, tool execution (native/CLI/DOM/UIA), postcondition verification, and Action Ledger commitment.
2. **Feedback Lane (PULSE)**: An asynchronous observer of the Action Lane, driving earcons, cached micro-ACKs, progressive natural status updates, UI state transitions, and verified final speech.

```
                    ┌──► ACTION LANE ─► Execute ─► Verify ─► Done
Your speech ─► Route┤
                    └──► FEEDBACK LANE (PULSE)
                         │
                         ├─ In-Memory Earcon / ACK
                         ├─ UI state transition
                         ├─ Event-to-Speech progress
                         └─ Final verified speech
```

**Key Law of PULSE**: Speech **never** sits in front of execution. Execution starts immediately upon routing. Speech failure or TTS latency has zero effect on action outcome.

---

## 1. Adaptive Feedback Budgeting & Race-to-Completion

Rather than applying uniform chatter to every request, PULSE predicts execution latency using Exponential Weighted Moving Average (EWMA) over historical PC telemetry:

$$\text{EWMA}_t = \alpha \cdot \text{duration}_{\text{observed}} + (1 - \alpha) \cdot \text{EWMA}_{t-1} \quad (\alpha = 0.25)$$

| Predicted Latency | Feedback Policy | User Experience |
| :--- | :--- | :--- |
| **< 250 ms** | **Silent / Earcon only** | Fast native command executes immediately; subtle `SUCCESS` chord on finish. Zero verbal chatter. |
| **250 ms – 1.2 s** | **Race-to-Completion Micro-ACK** | Action starts immediately; 250ms race timer starts. If action completes $<250$ms, verbal ACK is **cancelled**. Otherwise, speaks short cached ACK ("Opening it.", "Looking.") |
| **1.2 s – 4.0 s** | **Contextual Micro-ACK** | Speaks contextual ACK immediately in parallel with execution, followed by final verified speech. |
| **4.0+ s** | **Progressive Milestones** | Contextual ACK + verified internal event milestones + final verified speech. |

### Race-to-Completion State Machine

```
   RECEIVED
      ↓
  DISPATCHED
      ↓
 ACK_PENDING ──────────────┐
      │                    │
      │ action finishes    │ race timer expires (250ms)
      ▼                    ▼
  CANCEL_ACK           SPEAK_ACK
      │                    │
      └──────────┬─────────┘
                 ▼
             EXECUTING
                 │
         ┌───────┴────────┐
         ▼                ▼
     PROGRESS          VERIFIED
         │                │
         └────────────────┤
                          ▼
                     FINAL_RESPONSE
```

---

## 2. In-Memory Audio Earcons

PULSE synthesizes 6 distinct, mathematically generated 16-bit PCM waveforms at 22,050 Hz directly into RAM at startup (zero disk I/O, sub-millisecond retrieval):

| Earcon Type | Waveform / Acoustics | Duration | Perceptual Meaning |
| :--- | :--- | :--- | :--- |
| `COMMAND_ACCEPTED` | 1200 Hz pure tone, exponential decay | 20 ms | Command received & understood |
| `LISTENING` | 440 Hz $\to$ 880 Hz rising chirp | 60 ms | Microphone open / listening |
| `PROCESSING` | 300 Hz soft sine pulse | 40 ms | Background thinking / tool running |
| `SUCCESS` | C5 (523 Hz) + E5 (659 Hz) dyad chord | 70 ms | Action verified and complete |
| `CONFIRMATION_NEEDED`| 440 Hz $\to$ 660 Hz rising inflection | 80 ms | User approval or UAC required |
| `FAILED_UNCERTAIN` | 280 Hz $\to$ 200 Hz downward alert | 90 ms | Execution error or uncertain state |

---

## 3. Event-to-Speech Engine (Zero LLM)

Translates verified execution states into concise, truthful spoken feedback without generative hallucinations:

```python
EVENT_SPEECH_TEMPLATES = {
    "APP_LAUNCH_STARTED": "Opening {name}.",
    "FILE_SEARCH_STARTED": "I'm looking for it.",
    "DOWNLOAD_STARTED": "Downloading it.",
    "INSTALL_WAITING_FOR_USER": "Windows needs your approval to continue.",
    "BROWSER_NAVIGATION_STARTED": "Checking that now.",
    "TASK_RETRYING_SAFE_METHOD": "That didn't respond. I'm trying another method.",
    "TASK_VERIFIED": "Done.",
    "TASK_UNCERTAIN": "I couldn't verify that it completed.",
}
```

---

## 4. UI State Synchronization

PULSE continuously broadcasts structured UI events to the PySide6/QML desktop overlay:

$$\text{LISTENING} \longrightarrow \text{HEARD} \longrightarrow \text{UNDERSTOOD} \longrightarrow \text{EXECUTING} \longrightarrow \text{VERIFYING} \longrightarrow \text{DONE}$$
