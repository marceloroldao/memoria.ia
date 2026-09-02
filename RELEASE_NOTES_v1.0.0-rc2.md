# Memoria.ia v1.0.0-rc2 — Release Candidate 2

Release date: 2026-09-02

## Summary

`v1.0.0-rc2` is the second publication candidate for the Memoria.ia v1 line. It starts from the published `v1.0.0-rc1` baseline and incorporates the post-v1 memory intelligence work that remained intentionally excluded from RC1.

RC2 freezes the feature set around durable memory, deterministic Retrieval v2, provenance-aware relations, episodic continuity, explicit resolution modes, and bounded typed Resolutive Inference.

## Added since RC1

- Retrieval v2 activated in the post-v1 native/mobile runtime;
- deterministic lexical/morphological normalization with conservative ambiguity and conceptual-coverage gates;
- realistic distractor and authority-conflict regression matrices;
- separated evidence dimensions: `source_authority`, `retrieval_relevance`, `semantic_confidence`, and `freshness`;
- automatic episodic capture for identified sessions with durable restart recovery;
- explicit lineage continuity with safeguards preventing conversational order from becoming factual authority;
- relation semantic validation before graph promotion;
- `assistant_generated` content blocked from automatic factual relation promotion by default;
- explicit resolution modes: `DIRECT`, `INFERRED`, `UNRESOLVED`, `CONFLICT`;
- deterministic 2-hop Resolutive Inference returning proof memory IDs and path confidence;
- explicit transitive-predicate policy;
- strict typed relation extraction for `esta_em`, `parte_de`, and `subclasse_de`;
- generic `is` / `é` remains non-transitive;
- typed relations persist through the normal BDR graph and remain inferable after close/reopen;
- inferred conclusions are not persisted as new facts.

## Conservative behavior

RC2 intentionally fails closed when evidence is ambiguous or insufficient. Authority cannot compensate for low relevance, low conceptual coverage cannot be rescued by ranking, unsupported transitive composition returns `UNRESOLVED`, and equal-strength contradictory inference paths return `CONFLICT`.

Retrieval and inference are separate layers: Retrieval v2 retrieves stored evidence; only explicitly typed and allowlisted transitive relations may create an inferred conclusion.

## Frozen functional checkpoint

The final functional slice before stabilization was PR #153, merged as:

`d893abe1001c74c19a36003f1ee631e266e58cff`

The corrected PR head passed all required gates before merge, including:

- Retrieval v2 semantic adapter;
- Retrieval v2 semantic matrix;
- relation semantic validator;
- typed relation extractor;
- external relevance kernel;
- evidence metrics;
- durable evidence metrics runtime;
- automatic episode capture;
- durable host/restart path;
- Android ARM64 ABI.

## Freeze discipline

From `release/post-v1-freeze-stabilization` onward:

1. no new functional capabilities;
2. only bug fixes, regression tests, documentation, metadata, packaging and release-gate work;
3. any semantic behavior change reopens the full release-candidate validation cycle;
4. the RC2 tag must point to a fully green, reviewed freeze commit;
5. stable `v1.0.0` still requires the compatibility/security/publication gates documented by the project.

## Known limits

See `KNOWN_LIMITATIONS.md`. RC2 does not claim unrestricted general reasoning, general language understanding, production security certification, MA2A federation readiness, cryptographic source attestation, or inference beyond the bounded typed 2-hop policy.

## Version metadata

- Release tag candidate: `v1.0.0-rc2`
- Python package: `1.0.0rc2`
- License: Resolutive Research and Non-Commercial License (RRNCL) v1.0
- Author: Marcelo Roldão Matos
- ORCID: `0009-0003-6075-4680`
- RC1 archival DOI remains: `10.5281/zenodo.22170165`
- RC2 DOI: assign only after the RC2 release is frozen and archived; do not reuse the RC1 DOI.
