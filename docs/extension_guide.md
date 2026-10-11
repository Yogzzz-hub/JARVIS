# Extending JARVIS

1. Add a typed tool to the existing ToolRegistry with accurate risk, scope, availability and verification metadata.
2. Reuse existing policy, confirmation, ledger and execution paths; never call raw shell or a parallel transport from a new agent.
3. Register explicit metadata. Imported skill content starts UNREVIEWED; enabling metadata grants no execution authority.
4. Measure model support/residency and leave unknown fields unknown. Reuse the existing Ollama client through `OllamaEngine` when appropriate.
5. Add meaningful isolated regressions, run the affected existing suites and record environment/acceptance limitations honestly.
6. Keep raw owner data, auth, audio, databases and local acceptance results out of Git. Share aggregate reports only.

Current registries/adapters do not constitute a completed plugin loader or a second autonomous runtime.
