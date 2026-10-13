# Consolidated runtime

The existing `jarvis.core.runtime.Runtime` owns lifecycle. Commands enter the existing gateway, then `CommandService`, `SmartRouter`, registered tools, policy, confirmation, executor, verifier and response delivery. The twelve existing phases remain in place.

`core/extensions.py` provides metadata contracts, an Ollama adapter over the existing client and a narrow `JarvisKernel` facade. These are extension interfaces, not replacements for the production runtime. Alternative inference engines and autonomous coding agents are not implemented.

Optional operational diagnostics subscribe to the bounded EventBus. Failure of this subscriber does not change routing or authorize actions. Browser workflows reuse the existing Playwright manager and policy; their current scope is bounded navigation on explicitly allowed origins.

See `reports/JARVIS_BEST_OF_OPEN_SOURCE_FINAL.md` for measured results and outstanding acceptance requirements.
