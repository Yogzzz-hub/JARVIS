# Trace evidence and advisory learning

`OperationalTrace` is strict, frozen metadata. Provenance is REAL_SHADOW, SYNTHETIC or MOCK; the operational collector cannot mint VERIFIED_REAL. SQLite retention is bounded (default 10,000 rows, maximum 100,000), with writes off the command event loop. Aggregates separate provenance and keep owner-reviewed/verified-real counts at zero until a separate reviewed-evidence workflow exists.

The optional shadow advisor counts successful operational lanes by language/source, abstains below 20 observations or 80% agreement, and never executes or changes production decisions. Lane agreement is not accuracy. The current advisor is deliberately coarse; query-conditioned learned routing and robust offline evaluation remain incomplete.

CandidateOverlay describes DEVELOPMENT, SHADOW, ACCEPTANCE_READY, PROMOTED and ROLLED_BACK transitions. Quality, latency, resource, safety, regression and real-evidence gates plus explicit owner approval and rollback pointer are required for promotion. It is metadata only: no production source/config mutation is implemented. No candidate was promoted.
