# Known Limitations — memoria.ia v1.0.0-rc2

This document records the scientific and engineering limits of the v1.0 release-candidate line. The RC is a freeze candidate, not a claim of production-secure general intelligence.

## Scope

- memoria.ia is a structured, persistent memory and bounded inference system; it is not a general intelligence system.
- No claim is made that it replaces neural networks, LLMs, perception models, or unrestricted general-purpose reasoning.
- Retrieval v2 is deterministic and conservative; it can return `UNRESOLVED` when coverage or ambiguity gates are not satisfied.
- Resolutive Inference is intentionally bounded to explicit typed 2-hop paths and an allowlist of transitive predicates.

## Inference boundaries

- Only explicitly typed transitive predicates are eligible for automatic 2-hop composition in this RC: `esta_em`, `parte_de`, and `subclasse_de`.
- Generic copular `is` / `é`, `irmao_de`, `cor`, `porta`, and every unlisted predicate are non-transitive by policy.
- Inferred conclusions are not persisted as new facts; the engine returns the proof path and source memory IDs instead.
- Equal-strength contradictory conclusions fail closed as `CONFLICT`.
- Multi-hop (>2) inference, predicate-equivalence inference, unrestricted rule chaining, and probabilistic theorem proving are outside this RC.

## Persistence and provenance

- Durable mobile state depends on the pinned Resolutive-DB atomic C ABI used by the release candidate.
- Persisted payloads and trajectory nodes in the research facade must remain JSON-serializable where that facade is used.
- `assistant_generated` content may be stored as conversation/episode state but is not eligible for automatic relation promotion by default.
- Provenance and authority are explicit metadata, but this RC does not claim cryptographic source attestation.

## Retrieval and language

- Retrieval v2 uses deterministic normalization and conservative semantic gates; it does not use embeddings or an LLM in the native path.
- The normalization vocabulary is intentionally limited. Unsupported morphology, paraphrases, or languages may remain unresolved.
- Retrieval is separate from inference: lexical or semantic similarity alone does not authorize a new logical relation.

## Distributed memory and MA2A

- `related` does not establish identity and never authorizes destructive automatic merge.
- MA2A federation, PKI, Byzantine-fault tolerance, network partition reconciliation, and production distributed consensus remain outside the local v1.0.0-rc2 freeze boundary.

## Security and deployment

- The Enterprise/HTTP layer has not completed a formal production security review.
- The RC must not be described as production-secure until the documented security gate is completed.
- Android ARM64 ABI compilation is continuously validated, but OFF.IA application-level UX/device testing is a separate downstream validation step.

## Performance

- Performance depends on hardware, allocator, persistence workload, namespace size, and memory graph structure.
- Hash-map or conventional database baselines remain preferable for simple key/value workloads where memory lifecycle, provenance, retrieval and inference are unnecessary.
- Repository benchmark results are workload-specific and must not be treated as universal performance or compression guarantees.

## Compatibility

- Resolutive Science baseline remains v0.1.1 / RSPS 1.0-draft with RSMS 1.0-rc.1 candidate compatibility until the repository-wide compatibility metadata is re-audited.
- RSMS compatibility must be re-audited before promoting this release candidate to stable v1.0.0 if the normative RSMS baseline changes.

## Release status

v1.0.0-rc2 freezes the post-RC1 feature set around durable memory, Retrieval v2, provenance-aware relations, episodic continuity, explicit resolution modes, and bounded typed Resolutive Inference. Stable v1.0.0 requires stabilization evidence, final metadata review, immutable tag/release preparation, compatibility re-audit, and archival publication preparation; no additional feature work is required for this freeze candidate.
