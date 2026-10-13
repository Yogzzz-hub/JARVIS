# Voice pipeline

Existing microphone/VAD/STT, PULSE, TTS and audio-output components remain the voice path. Streamed sentences now own final playback without an additional repeated final answer. Barge-in prevents fallback playback of the cancelled answer. Audio queue rejection is explicit (`False`), while legacy sinks returning `None` remain compatible.

No new smart-turn model or always-on heavy encoder was enabled. `consolidation.smart_turn` currently accepts only `off`.

Owner listening judgments for English, Tanglish, Tamil and mixed speech are deferred by the owner's explicit instruction. Automated tests and TTS capability status cannot establish pronunciation quality, intelligibility, microphone accuracy or real barge-in behavior.
