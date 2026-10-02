# Blind-11 oracle errata

The locked set (`tests/blind11/cases.jsonl`, sha256 `eacfa96ceb02e26a2a44602f737608e02ea18faa972ba709f17fab2f42216643`) is never
edited. Mistakes in its expected answers are recorded here and in `tests/blind11/errata.json`.

- **Strict** scores use the set exactly as locked.
- **Audited** scores leave out only the cases listed in `errata.json`.

## Found by the structural oracle check, before the first run

`python -m tests.blind11.oracle_check` (output in `tests/blind11/ORACLE_CHECK.txt`) checks every expected capability and
slot name against the live tool registry and against the router-level capabilities. It found 14 structural errors, all
the same name: `lock_pc`.

JARVIS has no capability called `lock_pc`. "Lock the PC" is `system_power_control` with `action=lock`. The name came
from the capability catalogue given to the generator (`tests/blind11/generation/capabilities.json`, `runtime_and_control`),
which listed it by mistake. That is a fault of the benchmark author, not of the generator or of JARVIS.

| Cases | Effect | Treatment |
|---|---|---|
| B11-01_router-10, B11-01_router-26, B11-03_safety-48, B11-16_tanglish-18 | `lock_pc` is listed **next to** `system_power_control` as an accepted capability. | None needed: the real capability is accepted. |
| B11-02_core_os-13, B11-02_core_os-43, B11-02_core_os-45, B11-02_core_os-46, B11-05_multistep-35, B11-15_chat-49 | `lock_pc` is listed **next to** `system_power_control` as a forbidden capability. | None needed: the real capability is forbidden. |
| B11-05_multistep-02, B11-05_multistep-23, B11-05_multistep-32 | The expected plan has the step `lock_pc`, which can never be produced. | **Erratum.** Left out of audited scores; counted as written in strict scores. |
| B11-21_automation-50 | Forbids `lock_pc` but not `system_power_control`. A wrong PC lock in this case would not be caught by the forbidden list. | Kept in both scores. The report checks it by hand and says so if JARVIS locked the PC. |

## Found after the first run

None yet. Anything found while reading the results is added below with the evidence. It never changes the locked file
or JARVIS.
