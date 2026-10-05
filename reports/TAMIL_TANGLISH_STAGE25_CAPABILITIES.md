# Stage 2.5 capability retrieval status

**Freeze stage status:** Retrieval stays separate from the classifier and from the short-reply state policy. The independent 2,000-case benchmark remains unbuilt pending the human audit and admitted training split. Recall@1/3/5/10 and MRR are N/A; no registry-description paraphrases were counted as evaluation cases. No capability was invoked.

Capability retrieval remains separate from the Stage 2.5 language classifier. The requested 2,000-query independent Tamil/Tanglish benchmark and Recall@1/3/5/10 and MRR are **not yet built or measured**. They belong after the independent data audit and semantic training gate in the continuation workflow. Existing small registry-example probes do not qualify as independent cases.

The [ontology audit](STAGE25_ACTION_ONTOLOGY_COVERAGE.md) identifies 56 supported language-level concepts, four distinctions represented by existing typed frames, and two external-transaction registry gaps (PAY and SUBMIT). A language label still does not prove that a live capability exists or that execution is permitted.

A SemanticFrame candidate cannot invoke a tool by itself. Transfer cases still require a resolved channel, actual resource, recipient, compatible live capability, and policy decision. No external message, destructive action, or live JARVIS capability was executed in this data build.
