# LocalSend — Fast PC ↔ Android Local File & Text Transfer

## Overview
JARVIS EDGE integrates **LocalSend** as the preferred local-network file and text transfer connector.
Transfers happen completely over the local Wi-Fi / Ethernet LAN without uploading files to external clouds or third-party servers.

## Workflow & Natural Commands
1. "Send this file to my phone."
2. "Send the latest PDF to my phone."
3. "Send this text to my phone."
4. "Send these screenshots to my phone."

## Invariants & Ambiguity Resolution
- **ResourceRef Integration**: Files are resolved from `WorkingMemory.active_resource` or recent search results.
- **Ambiguity Guard**: If multiple files match a generic phrase (e.g. "Send the PDF"), JARVIS prompts the user to disambiguate or utilizes Phase 12 ordinal resolution ("Send the second one").
- **Offline Graceful Degradation**: If LocalSend is not active on the PC or phone, JARVIS does not crash or silently upload to the cloud. It returns:
  `"LocalSend isn't available right now. Please launch the LocalSend app."`

## Transfer Progress Events
The connector emits real-time events over the internal EventBus for Desktop UI visibility:
- `TRANSFER_PREPARING`
- `TRANSFER_STARTED`
- `TRANSFER_PROGRESS`
- `TRANSFER_COMPLETED`
- `TRANSFER_FAILED`
