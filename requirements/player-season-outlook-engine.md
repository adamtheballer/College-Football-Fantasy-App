# Player Season Outlook Engine

The player card may show a short, deterministic 2026 outlook when a reviewed
record is available. It must be generated from local canonical imports only:
historical final season stats, current role/depth context, verified team
environment data, and imported preseason projections.

Generation is an explicit batch job. Card reads only return the persisted
record; they never call a provider, generate copy, or use an LLM. The batch
script is dry-run by default and emits a reviewable JSON artifact. Only
validated records are eligible for display.

Each record stores a versioned evidence payload, generator version, generation
time, source identifiers, review state, and a stable player/season identity.
The public response exposes only the approved display fields. The UI hides the
section when there is no ready record and supports expanding longer copy.
