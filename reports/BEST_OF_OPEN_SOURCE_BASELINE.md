# Consolidation baseline

Baseline commit: `7d305bd281fa0f47d4f191751eda37ba968368e1`. Existing 12 phases are preserved.

|Component|Path|State|Decision|
|---|---|---|---|
|Composition and lifecycle|jarvis/core/runtime.py|Existing production runtime|Keep; add optional observability|
|Tool registry and progressive schemas|jarvis/tools/registry.py; jarvis/core/llm/tool_catalog.py|Existing|Extend metadata; preserve bindings|
|Capability retrieval|jarvis/core/capabilities/|Existing|Keep|
|Model backend|jarvis/core/llm/client.py|Ollama existing|Adapter, no model downloads|
|Context and memory|jarvis/core/context/; jarvis/core/memory/; jarvis/memory/|Existing|Keep typed references|
|Policy, scopes, confirmation, ledger|jarvis/security/; jarvis/core/tasks/scope.py|Existing|Repair measured defects only|
|Browser|jarvis/core/computer/browser/; jarvis/core/operator/browser.py|Existing semantic actions|Extend bounded verified workflows|
|Voice|jarvis/core/audio/; jarvis/core/stt/; jarvis/core/tts/|Existing|Keep; owner acceptance pending|
|Channels|jarvis/integrations/|Existing WhatsApp and Google|Read-only acceptance|
|Events|jarvis/core/events/bus.py|Bounded independent subscribers|Reuse|
|Consolidation traces/advisor|No existing consolidated implementation found|Missing|Add opt-in metadata-only diagnostics|

Tests: full Python baseline running; Node/Baileys 24/24 passed on owner Windows. Dependencies remain those in pyproject.toml and bridge/package.json. No foreign runtime is imported.

## Protected source hashes

```json
{
  "jarvis/security/policy/evaluator.py": "5f103fc5d16f852aa908ccf0424b7a36f856f4e3be4e3b5a76a4833fb80ab108",
  "jarvis/security/policy/scope.py": "d3c568d95d5e09b7ddb40bb2b34a7211d9eb2e8e354ab598f8cf29faccb2ed22",
  "jarvis/core/tasks/scope.py": "131383ceab813329a9d0b42d1bc7a838d06b9862e1a32678cb3766e0e2d48b6d",
  "jarvis/security/confirmation/manager.py": "ef5c028152f4b21fabb76acde0652aaa97fdd37772bf80c9866d51b7cc191e88",
  "jarvis/security/ledger/ledger.py": "95266d85b8a84c20a87d97e018c9343939b959d8260549fc0eeed2608f0e8580",
  "jarvis/core/router/router.py": "237a67dc298ef1e32eae5ebca63b19dba5cba72bcc3a93314605b78bef2e6997",
  "jarvis/core/commands/provenance.py": "223be88367c672ffff93cfa3a4d504566fbd7b954525a601f35e348628243d04",
  "jarvis/integrations/whatsapp/service.py": "dbe0ca25a3133d3263f4dfe9e67c9a647b95edb18521da93beccc31244b492ed",
  "jarvis/integrations/whatsapp/gateway.py": "6a69bf2f98905e04cc1d1f46f37d6b02be65681d64390cc5d6f1c3ef59e3cf7e"
}
```
