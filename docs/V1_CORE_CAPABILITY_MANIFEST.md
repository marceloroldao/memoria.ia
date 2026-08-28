# Memoria.ia v1.0 Core Capability Manifest

Status: candidate, pending final CI on the Product Evidence boundary.

## Stable Core responsibilities

### Memory product runtime
- organization-scoped persistent memories;
- versioned update/revoke/recall;
- crash-safe portable snapshot contract;
- selectable SQLite or native Resolutive-DB v1.1 persistence;
- backup/restore and restart compatibility;
- LLM adapter boundary and measurable context/token metrics.

### Evidence Core
- explicit source-backed relations;
- conservative multi-hop structural navigation;
- no synthesized predicates or unsupported claims;
- strict namespace isolation;
- append-only temporal epochs;
- latest-state semantics for single-valued predicates;
- abstention on same-epoch conflicts;
- explicit provenance, origin and confidence;
- independent-origin corroboration;
- externally adjudicated source reliability;
- replay protection for reliability resolutions;
- self-adjudication rejection;
- direct and indirect reliability-cycle rejection;
- canonical replay-based persistence;
- deterministic restart on SQLite and native BDR;
- structured Product adapter routes for relation ingest and inference.

## Adapter responsibilities

Natural-language parsing, entity extraction, semantic routing and transformation of text into explicit structural relations remain outside the stable Evidence Core. Adapters may evolve independently as long as the relations delivered to the Evidence Core are explicit and source-backed.

## Persistence boundary

The Product memory snapshot and Evidence Core state are independent durable contracts. Both use the selectable v1 storage layer. Evidence Core state is content-addressed and stores only explicit evidence plus explicit reliability adjudications; derived indexes are rebuilt by deterministic replay.

## Explicitly outside Memoria.ia v1.0 Core

The following responsibilities belong to the MA2A integration boundary and are not required for standalone Memoria.ia operation:

- distributed node/organization authority;
- network trust attestations;
- certificate and key lifecycle;
- authority key rotation;
- compromise recovery;
- guardians and recovery quorum;
- controller transfer and approval lifecycle;
- approval revocation;
- distributed replay protection tied to authority/governance;
- MA2A transport, federation and synchronization protocol.

## Architectural result

Application / LLM
    -> adapter or parser
    -> explicit source-backed relations
    -> Evidence Core
    -> Product runtime
    -> SQLite or Resolutive-DB

MA2A is an optional higher-level distributed protocol boundary, not a dependency of the standalone memory engine.

## Promotion rule

No experimental feature is promoted to this manifest merely because it exists in a later experiment branch. Promotion requires a clean dependency boundary, deterministic regression tests, Product compatibility, and no hidden MA2A dependency.
