# Memory and context

Existing WorkingMemory, typed resource references, retrieval and conversation history remain in use. Browser checkpoints persist task ID, state, completed step count, allowed origin and last verified state hash; they omit page titles, private URLs and contents. Resume requires the currently open page to match the checkpoint exactly.

Operational traces intentionally omit raw requests, message contents, contacts, URLs, tokens and model reasoning. They are evidence metadata, not a new semantic memory. No autonomous training or owner-style learning is enabled by these changes.

Consolidating every existing memory provider into one new public interface remains incomplete; do not infer completion from the extension metadata contracts.
