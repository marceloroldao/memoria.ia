# memoria.ia v1.0.0-rc1

## Release candidate scope

`v1.0.0-rc1` is the feature-freeze candidate for the first v1 line of memoria.ia. It consolidates the validated research core, durable PC/server/mobile state, Retrieval v2, provenance-aware relational memory, episodic continuity, and bounded deterministic Resolutive Inference.

No new feature work is required for this RC. Promotion to stable `v1.0.0` is gated by stabilization, metadata review, immutable release preparation, and archival publication preparation.

## What is frozen

- durable Resolutive-DB-backed mobile/native memory state with close/reopen recovery;
- namespace isolation and application/org boundaries already covered by the product layer;
- Retrieval v2 with deterministic normalization, ambiguity checks and conceptual-coverage gates;
- separate evidence dimensions: source authority, retrieval relevance, semantic confidence and freshness;
- semantic relation validation and provenance-aware automatic promotion;
- `assistant_generated` content blocked from automatic factual relation promotion by default;
- automatic episodic capture for identified sessions with durable restart recovery;
- explicit resolution modes: `DIRECT`, `INFERRED`, `UNRESOLVED`, `CONFLICT`;
- bounded 2-hop Resolutive Inference with proof memory IDs and path confidence;
- explicit transitive predicate policy;
- strict typed relation extraction for `esta_em`, `parte_de`, and `subclasse_de`;
- generic `is`/`é` remains non-transitive;
- inferred conclusions are calculated, not persisted as new facts;
- Android ARM64 native ABI build gate.

## Safety / conservative behavior

The RC intentionally fails closed when knowledge is ambiguous or insufficient. Authority cannot compensate for low retrieval relevance, low conceptual coverage cannot be rescued by ranking, conflicting equal-strength inference paths return `CONFLICT`, and unsupported predicate composition returns `UNRESOLVED`.

Retrieval and inference remain separate layers: similarity retrieves existing evidence; only explicitly typed and allowed transitive relations may produce a new inferred conclusion.

## Validation checkpoint

The final functional PR before stabilization was PR #153, merged as `d893abe1001c74c19a36003f1ee631e266e58cff` after all required gates passed on the corrected head, including:

- Retrieval v2 adapter and semantic matrix;
- relation semantic validator;
- typed relation extractor;
- external relevance kernel;
- evidence metrics and durable evidence runtime;
- automatic episode capture;
- durable host/restart path;
- Android ARM64 ABI.

## Known limits

See `KNOWN_LIMITATIONS.md`. In particular, this RC does not claim unrestricted general reasoning, production security, MA2A federation readiness, cryptographic source attestation, multi-hop (>2) inference, or universal language understanding.

## Release discipline

From this RC stabilization branch onward:

1. no new functional capabilities;
2. only bug fixes, regression tests, documentation, metadata, packaging and release-gate work;
3. any semantic behavior change must reopen the release-candidate validation cycle;
4. stable `v1.0.0` must be cut only from a fully green, reviewed freeze commit.
