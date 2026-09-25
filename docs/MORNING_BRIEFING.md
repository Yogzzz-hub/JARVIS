# "Good Morning Jarvis" Workflow

## Overview
Triggered by:
- "Good morning Jarvis."
- "Morning briefing."
- "What's happening today?"

## Architecture & Parallel Fanout
Data collection runs concurrently using `asyncio.gather` with per-provider timeouts (1.0s to 2.5s) so slow or offline services never freeze the briefing:

```
                     GOOD MORNING
                          │
          ┌───────────────┼────────────────┐
          │               │                │
       Calendar         FreshRSS        Projects
          │               │                │
          ├───────────────┼────────────────┤
          │               │                │
       Tasks/Notes      PC Status       Downloads
          │               │                │
          └───────────────┼────────────────┘
                          ↓
                     AGGREGATOR
                          ↓
                     SUMMARIZER
                          ↓
                    RESPONSE ENGINE
                          ↓
                    PIPER STREAMING TTS
```

## Performance & Invariants
- **Instant Acknowledgment**: Audio response ("Good morning. Getting your briefing.") plays immediately while parallel gathering proceeds.
- **Disconnected Calendar**: Google Calendar is cleanly skipped without error if disconnected (never fakes events).
- **Context Retention**: Collected news items are recorded in `WorkingMemory.last_feed_items` so follow-ups ("Open the second one", "Send that to my phone") resolve without re-fetching.
- **Measured Latency**: Parallel gathering completes in **5.54 ms (p50)** locally.
