# Registries

The production tool registry is `jarvis/tools/registry.py`; production capability descriptions live in `jarvis/core/capabilities/registry.py`. Runtime-specific tool metadata now gets its own capability registry rather than contaminating a process-wide default. Master definitions are copied before registration. Read-only classification caches belong to each router instance.

`ExtensionRegistry` accepts explicit typed metadata for engine, model, agent, capability, skill, memory, channel, benchmark, voice and transport kinds. Duplicate and wrong-kind registration fail. It does not discover/import external packages or execute entries. Separate populated registries for every subsystem remain future work.

`ModelSpec` retains unknown resource/support metadata as unknown. Hardware eligibility refuses unmeasured RAM demand and reserves 1 GiB for the system; it does not automatically download or select models.
