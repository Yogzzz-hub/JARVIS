# JARVIS EDGE v1.0 — Final Architecture & Connector Specification

## Architectural Invariants
1. **JARVIS Remains THE Brain**: Connectors are peripheral tools. They never function as independent authorities, planners, or memory stores.
2. **Phase 1-12 Foundation Preserved**: No Phase 13 was created. This enhancement strictly expands v1.x local connectors and multi-step orchestration.
3. **Strict Policy Path**:
   `User Intent -> Fast Router -> ToolRegistry -> Phase 5 Policy + ActionLedger -> Connector Execution -> Verifier -> ResponseEngine -> Piper Streaming TTS`
4. **Data Isolation**: External content (web pages, RSS items, Memos, Node-RED payloads) is strictly tagged as `UNTRUSTED_DATA` and cannot trigger arbitrary code or commands.
5. **Resilient Local Operation**: If any local service or hardware is disconnected or unconfigured, JARVIS operates normally without errors or delays.

## Status CLI
Run:
```bash
python -m jarvis.connectors.status
python -m jarvis.report final
```
