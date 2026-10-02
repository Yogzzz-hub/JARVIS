# Generalisation, noise suppression, wake word, live transcription and the voice overlay

This round followed Phase-500 ([PHASE500_REPORT.md](PHASE500_REPORT.md)). The goals were better accuracy on commands
JARVIS has never seen, background-noise removal, a sturdier wake word, live transcription that doesn't flicker, and
an overlay that shows what's happening.

## 1. Can it be 100% on unseen commands?

No honest test can promise that. The deterministic router is a set of rules, and new phrasings keep arriving. What
the router does about a command it doesn't understand matters as much as its accuracy:

- It goes to the local model and planner (with Ollama running), or JARVIS asks.
- It never goes to a wrong action. The target that *can* be met is **zero criticals**: no unseen command routed to a
  consequential tool (send, delete, close, install, power, …) that the owner didn't ask for.

To measure this honestly, two new unseen sets were written and frozen (`FROZEN.sha256`) before the fixes they would
measure:

| Set | Commands | Written before | Before | First run after the fixes (blind) | After using its own failures (not blind) |
|---|---:|---|---:|---:|---:|
| Blind-7 (`tests/blind7`) | 3,483 | any fix in this round | 75.3%, 24 criticals | **80.0%**, 13 criticals | 94.0%, 0 criticals |
| Blind-8 (`tests/blind8`) | 2,200 | the fixes driven by Blind-7's failures | 85.6%, 0 criticals | **85.6%**, 0 criticals | - |

**Reading it honestly**

- On commands nobody tuned for, the router is at **80% to 86%**.
- The fixes driven by Blind-7's failures raised Blind-7 to 94% but moved Blind-8 by **0.0 points**. Fixing from one
  set's failures does not generalise to new wording.
- All 13 criticals on Blind-7's first run came from two rules added in this round:
  - "phone wifi off" read as a phone call
  - "won't respond" read as the messaging verb "respond"

  Both were fixed, and the rest of this round produced no criticals.
- Both sets were written by the same author as the fixes, so even the blind numbers may be optimistic.
- Every command in `python -m tests.blind7.runner` / `python -m tests.blind8.runner` is scored with no AI model.

The Phase-500 suite after this round:

| | All 16,502 | Dev | Holdout (spent last round) | Criticals |
|---|---:|---:|---:|---:|
| End of Phase-500 | 94.7% | 99.4% | 81.5% | 0 |
| Now | 99.3% | 99.4% | 99.1% | 0 |

### What changed in understanding (generic, no sentence-specific rules)

**A construction canonicaliser** (`jarvis/core/router/canonical.py`) runs before matching. It rewrites shapes, never
particular sentences, and never touches message, typed or note content:

| Shape | Examples | Becomes |
|---|---|---|
| synonym verbs | gimme X, fire up X, load X, get X running, can I have X | open X |
| | kill / terminate / exit / force close X | close X |
| subject first | "X is stuck, kill it", "I'm done with X, close it", "X won't respond, force close it" | close / restart X |
| modal or question | "can the volume be 40", "could you bump the volume to 30" | set volume to N |
| elided second verb | "set volume to 40 and brightness to 60" | … and set brightness to 60 |
| trailing filler | "… again like last time", "… as usual", "… now" | dropped |
| spoken output | "say the time out loud", "read today's calendar out loud" | tell me the time / calendar |
| sites, folders, files | "open zomato.com", "take me to documents", "dig out my itinerary", "can you open my insurance policy", "I don't need X.py anymore, delete it" | go to … / open folder / find my … / delete X.py |
| install / update / windows | "grab X from the internet and install it", "get the latest version of X", "shrink X", "jump to X", "get rid of X window" | install / update / minimise / switch / close window |
| status questions | "am I plugged in", "how much storage do I have left", "how much charge does my phone have" | battery / disk / phone battery |
| watches | "announce it when Nisha messages me", "when my battery hits 85 percent tell me" | tell me when … |
| phone shorthand | "phone wifi off", "dim my phone to 58%" | toggle / phone brightness |
| British spelling | summarise, organise, minimise | -ize forms |

**Typo repair** now also repairs endings of known words ("laoding" → "loading"). It never repairs file names, paths,
URLs, quoted text, or the words of a message or reply. "bored" is no longer turned into "broed", and "readme" no
longer into "rename".

**New capabilities found missing:**

- *"tell me when Nisha messages me"* / *"…when anyone texts me"*: a WhatsApp-message watch. It only observes the
  inbox and only counts one-to-one chats. It says who wrote, never what they wrote.
- Reading the clipboard ("what's on my clipboard").
- Summarising or asking a named file ("summarise report.pdf", "what does report.pdf say about …").
- Duplicating a named file.
- "show your recent actions" now goes to the action record. It used to open Gmail.

**Safety fixes:**

| Was | Now |
|---|---|
| "unlock my phone without the pin" woke the phone | refused |
| "wipe my whole hard drive" was not refused | refused |
| "buy this phone on amazon" started the web agent | asks: JARVIS doesn't buy or pay, but can search the shop for you |
| "exit full screen" closed an app called "full screen" | presses Escape |
| "find my flight ticket" / "go to zomato.com" were refused as bookings | find the file / open the site |

Real-world actions (book, order, pay, deliver) and impossible ones are still refused. The guard now lets through only
clearly PC objects (files, documents, websites), so "find a walk-in clinic" or "check my credit score" still ask.

## 2. Noise suppression (`jarvis/core/audio/denoise.py`)

The filter is a streaming spectral Wiener filter, built only on numpy:

- **Processing:** 20 ms sqrt-Hann frames with a 10 ms hop and an 80 Hz high-pass.
- **Noise tracking:** follows the quietest recent level of each band, so it learns fans, AC hum and traffic but never
  speech.
- **Gain:** decision-directed, smoothed across frequency, with a gain floor (−9 / −15 / −22 dB for low / medium /
  high). Removing everything would create "musical noise" that makes Whisper invent words.
- **Automatic gain:** lifts a quiet or distant voice up to 4×, and never amplifies silence.

It runs in the audio hub, once per frame:

- **Cleaned audio** goes to VAD, speech recognition, live transcription and the pre-roll buffer.
- **The wake word** keeps the raw microphone audio, because it was trained on unprocessed speech.
- **If the filter fails**, the hub falls back to raw audio and keeps working.

Measured on speech-like test audio (`jarvis/tests/test_voice_quality_and_generalisation.py`):

| Noise | SNR before → after |
|---|---|
| white noise | 7.6 → 14.9 dB |
| fan (low-frequency) | 10.7 → 14.1 dB |
| 50 Hz hum + hiss | 6.0 → 17.1 dB |
| clean speech, no noise | 28 dB transparency (almost unchanged) |
| cost | about 0.14 ms per 20 ms frame, 10 ms added latency |

Settings (`[voice]` in the config):

- `noise_suppression = "medium"`: one of off / low / medium / high.
- `auto_gain = true`.

These numbers come from synthetic test signals, not recordings of real rooms.

## 3. Wake word

- **Two-chunk confirmation.** A quiet or distant "hey Jarvis" often scores just under the threshold on two
  consecutive 80 ms chunks. Two near-threshold chunks in a row now count (both ≥ 70% of the threshold, average ≥ 85%),
  while a single one (a cough, a word on TV) never does. A clear wake word still fires at once.
- **OpenWakeWord's own Speex noise suppression** is used when `speexdsp_ns` is installed.
- The wake score is sent to the UI.

## 4. Live transcription

The stabiliser shown while you speak (`jarvis/core/stt/prefix_consensus.py`) now:

- compares words ignoring case and punctuation, so "Chrome," and "chrome" agree;
- on a real revision ("tape" → "type"), drops only the contradicted words and keeps the part that still agrees. The
  line never flickers back to empty.
- only grows the stable text, so live dictation never retypes a word it already typed.

## 5. Voice overlay

- **Live transcript:** stable words are solid, and the tail that may still change is dimmed.
- **Mic-quality line:**
  - a plain sentence describing the room, for example "Background noise – filtering it out" or "Very noisy room –
    speak closer to the mic";
  - the noise floor, the SNR, and how many dB are being filtered.
- Driven by the existing `audio.level` event (now carrying `noise_db`, `snr_db`, `reduction_db`, `wake_score`) and
  `voice.stable_prefix`.

## 6. Checks

| Check | Previous round | Now |
|---|---|---|
| `pytest jarvis/tests tests` | 2,554 passed, 21 failed | **2,629 passed**, the same 21 failed (they fail on earlier code too), 0 new |
| Phase command suite: dev / blind 1–6 / torture failures | 44 / 16·4·3·3·0·0 / 42 | **40** / 16·4·3·3·0·0 / **41**, 0 new |
| Universal Operator suite | 99.88%, 2 wrong capability | **99.95%**, **1** wrong capability, 0 negated executed |
| AGI-520 suite | dev 93.58%, holdout 69.86% | dev **93.66%**, holdout 69.86%, 0 critical |
| New tests (`test_voice_quality_and_generalisation.py`) | - | 75 passed |

One existing reference test changed on purpose. `tests/test_reference_algorithms.py` expected the stable transcript
to empty itself on a revision. It now expects the agreed words to stay.
