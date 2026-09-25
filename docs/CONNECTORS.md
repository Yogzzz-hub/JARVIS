# JARVIS EDGE v1.x — Local Connector Framework

## Overview
The JARVIS EDGE Local Connector Framework integrates local tools, devices, and self-hosted services into the JARVIS runtime without compromising JARVIS's role as the sole brain, policy authority, router, planner, and verifier.

```
                         JARVIS EDGE
                              │
                 ┌────────────┴────────────┐
                 │                         │
              ROUTER                   PLANNER
                 │                         │
                 └────────────┬────────────┘
                              │
                       TOOL REGISTRY
                              │
     ┌────────────┬───────────┼───────────┬────────────┐
     │            │           │           │            │
   PHONE        FILES      BROWSER       NEWS        NOTES
     │            │           │           │            │
   scrcpy     LocalSend    Playwright   FreshRSS      Memos
     │            │           │           │            │
     └────────────┴───────────┼───────────┴────────────┘
                              │
                         ntfy/Gotify (Mobile Alerts)
                              │
                           Node-RED (Event Bridge)
```

## Supported Connectors

| Connector | Role | Transport | Network Requirement | Policy Risk |
| :--- | :--- | :--- | :--- | :--- |
| **scrcpy** | Android screen mirror & typed actions | ADB / USB or Wi-Fi | Localhost / USB | REVERSIBLE |
| **LocalSend** | High-speed PC ↔ Phone file & text transfer | LocalSend v2 HTTP API | LAN (127.0.0.1:53317) | REVERSIBLE |
| **Playwright** | Semantic DOM browser interaction | CDP / Playwright Driver | Localhost / Internet | REVERSIBLE |
| **FreshRSS** | Local news & feed aggregator | Local REST API / RSS | LAN / Internet | READ_ONLY |
| **ntfy / Gotify** | Mobile push notifications & alerts | HTTP POST | LAN / Internet | REVERSIBLE |
| **Memos** | Human-readable notes & reminders | Local DB / REST API | Localhost / LAN | REVERSIBLE |
| **Node-RED** | External workflow and event bridge | HTTP Webhooks | Localhost / LAN | REVERSIBLE |

## Connector States & Graceful Degradation
All connectors implement `BaseConnector` and report one of the following authoritative states:
- `DISABLED`: Connector is disabled in `config/connectors.toml`.
- `UNAVAILABLE`: Service is enabled, but local daemon or hardware is unreachable.
- `CONNECTING`: Establishing initial handshake.
- `READY`: Service is verified and fully operational.
- `DEGRADED`: Partial functionality (e.g. ADB present but no phone connected).
- `ERROR`: Unexpected failure during initialization.

**Crucial Invariant**: No connector is a hard startup dependency. If a connector is `UNAVAILABLE` or `DISABLED`, JARVIS continues operating natively.

## Configuration
Connectors are configured in `config/connectors.toml`. Credentials and tokens are stored in the OS Keyring / SecureStore and never in plain text.
