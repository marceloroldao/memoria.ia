# Memoria.ia v1.0.0-rc4 — Layered Adaptive Memory Candidate

Release date: 2026-09-03

## Summary

`v1.0.0-rc4` freezes the post-RC3 layered-memory and adaptive-recomputation work as a new release candidate for server and OFF.IA validation.

The functional freeze for this candidate is:

`b4a891eb76e7fc51a272120b55dff07abe58e451`

No new runtime features are to be added to the RC4 line after this freeze. Changes after the freeze are restricted to release metadata, documentation, packaging and regression fixes required to publish the candidate coherently.

## Main additions since RC3

- explicit layered factual abstractions with provenance;
- vertical dependency edges between abstraction levels;
- selective invalidation of dependent facts and abstractions;
- incremental recomputation of only affected branches;
- multi-root batch recomputation with shared ancestors visited once per batch;
- adaptive incremental/full recomputation based on affected graph density;
- optional hysteresis policy for oscillating workloads;
- deterministic workload profiles (`sparse`, `burst`, `oscillating`, `near_global`, `mixed`);
- audited strategy recommendation and execution path;
- deterministic workload matrix and scale benchmarks;
- reproducible layered performance baseline.

## Scale evidence recorded during development

The deterministic balanced-graph benchmark preserved exact snapshot equivalence between incremental and full recomputation at all tested scales.

Representative recorded baseline:

- 127 nodes: 7 incremental nodes touched versus 127 full;
- 1,023 nodes: 10 incremental nodes touched versus 1,023 full;
- 16,383 nodes: 14 incremental nodes touched versus 16,383 full.

On the recorded CI runner, the 16,383-node scenario measured roughly 0.125 ms for the local incremental update versus 75.716 ms for a complete recomputation. These wall-clock values are environment-specific and are retained only as a versioned performance baseline; exact snapshot equivalence and touched-node locality are the deterministic correctness criteria.

## Architectural boundary

Memoria.ia remains local-first and deterministic at the memory/inference layer. No LLM, embedding model or neural network is required for the layered invalidation, recomputation, workload classification or strategy-selection mechanisms added in this candidate.

The architecture remains:

```text
application / OFF.IA / agent
          ↓
      Memoria.ia
          ↓
 Resolutive-DB / BDR
```

Memoria.ia owns memory semantics, lineage, abstraction and recomputation policy. Resolutive-DB / BDR owns durable persistence.

## Release status

This is a release candidate and must be published as a pre-release.

The RC4 feature set is frozen at the functional commit above. Before publication, the candidate must pass the full semantic, product, credentials and layered-performance gates with aligned package/version/citation metadata.

## Publication lineage

Previous public release:

- `v1.0.0-rc3` — corrective release candidate that fixed RC2 tag/provenance alignment.

Archived prior candidate:

- `v1.0.0-rc2` — DOI: `10.5281/zenodo.22244038`.

A new RC4 DOI must be inserted only after the archival record exists; no DOI is pre-assigned in this preparation commit.

## Claims boundary

Memoria.ia remains an experimental Resolutive Memory architecture. This release does not claim AGI, unrestricted general reasoning, biological equivalence, production-security certification or replacement of general-purpose LLMs. Claims remain limited to the implementation, tests and reproducible evidence contained in the repository.
