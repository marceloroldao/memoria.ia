# Memoria.ia v1.0.0-rc3 — Corrected Release Candidate

Release date: 2026-09-02

## Summary

`v1.0.0-rc3` is a corrective release candidate that supersedes `v1.0.0-rc2` because RC2 was published with a release-tag alignment error.

RC3 does not introduce a new functional capability over the validated RC2 freeze lineage. Its purpose is to ensure that the release tag, package version, citation metadata and archival publication all refer to the intended frozen codebase.

## Frozen capabilities

- Retrieval v2 with deterministic lexical/morphological normalization;
- conservative ambiguity and conceptual-coverage gates;
- provenance-aware relational memory;
- separated evidence dimensions for authority, relevance, semantic confidence and freshness;
- automatic episodic capture with durable restart recovery;
- explicit lineage safeguards;
- semantic relation validation;
- protection against automatic factual promotion of `assistant_generated` content;
- explicit resolution modes: `DIRECT`, `INFERRED`, `UNRESOLVED`, `CONFLICT`;
- deterministic bounded 2-hop Resolutive Inference;
- auditable proof memory IDs and path confidence;
- explicit transitive predicate policy;
- typed transitive relations: `esta_em`, `parte_de`, `subclasse_de`;
- generic `is` / `é` remains non-transitive;
- inferred conclusions are not automatically persisted as facts;
- durable Resolutive-DB persistence and restart recovery;
- Android ARM64 native ABI validation on the frozen functional lineage.

## Corrective publication note

The previously published RC2 DOI is:

`10.5281/zenodo.22244038`

That DOI remains associated with RC2 and must not be reused for RC3.

RC3 must receive a new DOI after the `v1.0.0-rc3` tag is created on the exact corrective freeze commit.

## Functional provenance

RC3 starts from the fully validated RC2 freeze lineage and changes only release/version/publication metadata. No semantic runtime behavior is intentionally changed by this corrective candidate.

## Claims boundary

This release does not claim artificial general intelligence, unrestricted general reasoning, biological equivalence, replacement of general-purpose LLMs, production security certification or production-ready MA2A federation.

## Release discipline

1. No new functional capability is allowed in RC3.
2. Any semantic/runtime change requires re-running the full candidate validation cycle.
3. The `v1.0.0-rc3` tag must point to the exact final corrective freeze commit.
4. RC3 must receive a new archival DOI.
