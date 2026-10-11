# Open-source research and adoption

Reviewed primary upstream sources for concepts; no upstream implementation was copied or vendored and no new third-party runtime was installed.

| Source | Applied concept | Boundary |
|---|---|---|
| [OpenJarvis design](https://open-jarvis.github.io/OpenJarvis/architecture/design-principles/) | Typed engine/registry interfaces, local operational evidence | Existing Ollama client/runtime retained; full engine family not implemented |
| [Leon context architecture](https://github.com/leon-ai/leon/blob/develop/core/context/ARCHITECTURE.md) | Explicit context ownership and lifecycle documentation | Existing typed WorkingMemory retained |
| [Home Assistant voice pipelines](https://developers.home-assistant.io/docs/voice/pipelines/) and [Wyoming](https://www.home-assistant.io/integrations/wyoming) | Component boundaries and honest availability | No protocol/server dependency added |
| [LiveKit turns](https://docs.livekit.io/agents/logic/turns/) and [Pipecat](https://github.com/pipecat-ai/pipecat) | Interruption-aware streaming and bounded voice lifecycle | Existing PULSE repaired; smart-turn remains OFF |
| [OpenVoiceOS message bus](https://github.com/OpenVoiceOS/architecture/blob/dev/msg-1.md) | Event-driven diagnostics | Existing bounded EventBus reused; events confer no authority |
| [Willow](https://github.com/HeyWillow/willow) | Edge hardware and latency constraints | No device firmware imported |
| [Genie](https://github.com/stanford-oval/genie-toolkit) and [ThingTalk](https://github.com/stanford-oval/thingtalk) | Declarative typed actions | Browser programs are data; arbitrary scripts are forbidden |
| [Rhasspy](https://github.com/rhasspy/rhasspy) and [Mycroft](https://github.com/MycroftAI/mycroft-core) | Local intent/voice separation, historical design references | No foreign assistant runtime imported |

These are conceptual adaptations, not claims of upstream feature parity. License obligations would need a fresh review before copying upstream code or redistributing models; this change introduces neither.
