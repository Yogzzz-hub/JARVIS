# Node-RED — Event Bridge (Not a Second Brain)

## Overview
**Node-RED** functions strictly as an optional **event bridge** between external systems and JARVIS EDGE.
Node-RED is **NEVER** allowed to act as an independent reasoning engine, planner, or arbitrary command execution surface.

## Relationship & Hierarchy
- **Node-RED**: Notifies JARVIS that an external event occurred (e.g. `download_completed`, `rss_updated`, `scheduled_morning_event`).
- **JARVIS**: Determines the meaning, evaluates security policies, and executes verified actions.

## Strict Security Boundaries
1. **Schema Validation**: Every incoming event must conform to `ExternalEvent`.
2. **Event Type Allowlist**: Events outside `APPROVED_EVENT_TYPES` are rejected immediately.
3. **Replay Protection**: Event IDs are cached and deduplicated.
4. **Rate Limiting**: Enforces a strict ceiling of 10 events per minute.
5. **No Shell / Arbitrary Execution**: External payloads cannot execute arbitrary PowerShell, ADB, or Python code.
