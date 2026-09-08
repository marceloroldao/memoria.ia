# Memoria.ia v1.0.0-rc7 — Stabilization and Consistency Candidate

Release date: 2026-09-08

## Summary

RC7 is a stabilization-only release candidate. It intentionally adds no new runtime capability over RC6. Its purpose is to correct, harden and freeze the behavior already present in the semantic-relational runtime before further functional evolution.

RC7 cumulative functional freeze commit:

`ca4089cad0369da3a13c484c93cc4c97ee54cfaf`

Last runtime-changing stabilization commit:

`3f72f7e46c976245818e8878e36f6d906d6ba0ba`

Changes after the cumulative freeze are restricted to publication metadata, packaging and narrowly scoped release corrections.

## What RC7 stabilizes

- direct resolution precedence before structural fallback;
- bounded semantic activation and maximum concept/depth budgets;
- provenance authority ordering and factual/generative contamination barriers;
- rejection of `assistant_generated` evidence as authoritative factual roots;
- same-user/session/profile isolation and fail-closed cross-scope behavior;
- server/chat resolver wiring without changing `/conversation/*` public behavior;
- deterministic context ranking and insertion-order stability;
- atomic context-budget rendering without partial relation lines;
- exact confidence and second-hop decay boundaries;
- floating-point stability at the confidence threshold;
- SQLite restart equivalence and portable snapshot recovery;
- repeated semantic activation as a read-only, non-amplifying operation;
- recurring semantic, product, credentials, metadata and performance gates.

## RC7 correction found during stabilization

The RC7 boundary tests exposed one runtime defect: an exact second-hop confidence threshold could be rejected because binary floating-point multiplication produced a value infinitesimally below the mathematical cutoff. The comparison was corrected with a narrowly bounded numeric tolerance. The regression test remains in the suite.

No new semantic behavior was introduced by this correction.

## Validation status

RC7 phases A–F validated:

- semantic-path regression behavior;
- provenance and contamination barriers;
- Python/native/server runtime contracts;
- context budget and ranking boundaries;
- persistence/restart and semantic non-amplification;
- cumulative release metadata and performance gates.

The recurring release-blocking workflows passed on the frozen lineage:

- v0.96 semantic validation;
- product-alpha validation;
- product application credentials;
- layered performance baseline;
- release metadata validation.

Android/mobile ABI compatibility remains part of the inherited validated native boundary. RC7 did not introduce a new mobile ABI or public conversation API.

## Architectural boundary

Memoria.ia remains local-first and deterministic at the memory/inference layer. LLM output does not become authoritative memory by default. The semantic layer remains bounded and retrieves/projects persisted evidence rather than synthesizing factual edges merely to answer a query.

```text
application / OFF.IA / agent
          ↓
      Memoria.ia
          ↓
 Resolutive-DB / BDR
```

## Known boundaries

- automatic learning/promotion of new `semantic_role` declarations remains post-RC7 work;
- new external/public learning capabilities are outside RC7;
- unrestricted graph reasoning is not introduced;
- no independent production-security certification is claimed;
- MA2A federation remains outside the stable local runtime boundary;
- final v1.0 promotion remains dependent on a re-audit against the stable RSMS specification.

## Publication lineage

Previous public release:

- `v1.0.0-rc6` — Semantic Relational Context Candidate.
- DOI: `10.5281/zenodo.22648409`.

A new RC7 DOI must be inserted only after the archival record exists; no DOI is pre-assigned in this publication commit.

## Claims boundary

Memoria.ia remains an experimental Resolutive Memory architecture. This release does not claim AGI, unrestricted general reasoning, biological equivalence, production-security certification or replacement of general-purpose LLMs. Claims remain limited to the implementation, tests and reproducible evidence contained in the repository.
