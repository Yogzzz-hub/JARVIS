# Security invariants

Owner authentication, task scope, existing policy, confirmation and ActionLedger remain the execution boundary. Scope service lookup errors fail closed. Web pages, messages, files, observations, model text and imported skills are data and cannot authorize actions.

The legacy `powershell_command` binding remains discoverable for compatibility but is tagged arbitrary_ps, classified PRIVILEGED and denied before execution, including `as_admin=False`. Its direct implementation also denies. Use existing narrowly typed capabilities instead.

WhatsApp partial/history imports cannot clear unrelated unread chats or assert current-generation READY. Historical snapshot import defaults to dry-run and validates all records before applying. No acceptance command sends a message, refreshes OAuth or promotes a model. Generated auto-replies remain disabled during language shadow.

Browser workflows require an existing task grant, enforce owner-defined HTTP(S) origins and stop at authentication, CAPTCHA, graded assessment or ambiguous/mutating controls. Local fixtures are SYNTHETIC evidence even when driven by a real browser. The experimental workflow is not certified for arbitrary sites or financial/form submissions.
