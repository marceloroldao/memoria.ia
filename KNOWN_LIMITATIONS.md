# Known Limitations — memoria.ia v0.95.0rc1

This document records known scientific and engineering limitations for the v0.95 release-candidate line.

## Scope

- The project implements experimental structured memory, not a general intelligence system.
- No claim is made that the architecture replaces neural networks, LLMs, perception models, or general-purpose reasoning systems.
- Semantic consolidation and polysemy handling remain experimental.

## Persistence

- Persisted payloads and trajectory nodes must currently be JSON-serializable.
- The compact MI93 snapshot optimizes storage/transmission and may require more CPU during encoding.
- Compression ratios depend strongly on data redundancy. Results observed in repository benchmarks must not be treated as universal compression guarantees.

## Distributed memory

- `related` does not establish identity and never authorizes destructive automatic merge.
- Distributed consensus is currently conservative and local; Byzantine-fault tolerance, cryptographic trust, network partition reconciliation, and production distributed consensus are outside this release-candidate scope.
- Provenance is recorded as metadata but is not yet backed by cryptographic signatures.

## Online lifecycle

- The candidate default `max_strength = 1.25` was selected from controlled stability/plasticity experiments, not from a universal theoretical optimum.
- The temporal rule `r_L = 2^-L` is an architectural hypothesis validated only against the included controlled workloads.
- Different domains may require recalibration.

## Performance

- Benchmarks are Python-prototype measurements and are sensitive to interpreter version, allocator, hardware, workload distribution, and payload structure.
- Hash-map baselines remain superior for simple key/value aggregation where resolutive lifecycle capabilities are unnecessary.
- Earlier negative results are intentionally preserved in `docs/results_*.md`.

## Compatibility

- Governance alignment is currently with `resolutive-science` v0.1.1 and RSPS 1.0-draft.
- No formal numbered RSMS compatibility is claimed until such a normative RSMS version is published and audited.

## Release status

v0.95.0rc1 is a release candidate gate. A stable v1.0 requires final complete-suite validation, release metadata review, immutable release/tag preparation, and archival publication preparation.