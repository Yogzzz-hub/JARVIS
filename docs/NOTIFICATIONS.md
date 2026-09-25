# Push Notifications — ntfy & Gotify Provider

## Overview
JARVIS EDGE provides an abstract push notification interface supporting self-hosted or cloud **ntfy** or **Gotify** instances for alerting users on their mobile devices.

## Supported Commands
- "Notify my phone when this finishes."
- "Notify my phone when this download finishes."
- "Send notification to phone: Meeting in 15 minutes."

## Features & Boundaries
- **Verification First**: Notifications for tasks or downloads are never sent before verification succeeds.
- **Secret Redaction**: API keys, tokens, Bearer strings, and passwords are automatically scrubbed via regex before dispatch.
- **Deduplication**: Identical notifications within a sliding 60-second window are deduplicated to avoid alert spamming during retries.
- **Zero Cloud Leak**: Can be configured with a local self-hosted `http://localhost:8080` or LAN ntfy container.
