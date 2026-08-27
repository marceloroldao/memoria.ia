# Memoria.ia v1.0 Candidate Architecture

Status: integration planning baseline

This document defines the promotion boundary for the first Memoria.ia v1.0 candidate. It intentionally separates validated product functionality, memory-core functionality, persistence, and MA2A responsibilities.

## Product baseline

The v1.0 candidate starts from the current `main` / v0.99.0-alpha.1 product line.

Retain:

- PC/server installability;
- FastAPI `/api/v1` service;
- Web UI;
- Docker / Docker Compose;
- organization-scoped memory isolation;
- administrator and application credential boundaries;
- provider-neutral LLM adapter;
- OpenAI / Gemini / mock provider paths;
- metrics;
- backup / restore and integrity validation;
- restart/recovery behavior;
- product acceptance and negative-security gates.

## Persistence decision

Target v1.0 storage policy:

- Linux: Resolutive-DB (BDR) v1.1.0 direct `AtomicDatabase` binding is the preferred native backend once extracted cleanly from `experiment/bdr-primary-linux` and revalidated on this integration lineage.
- Other platforms: SQLite remains the portability/default fallback until Resolutive-DB native portability is validated there.
- SQLite remains the behavioral control/reference backend even on Linux.

Do not merge `experiment/bdr-primary-linux` wholesale. It is heavily diverged from `main` and contains unrelated semantic-routing and trajectory experiments. Only the persistence contract, direct BDR binding, focused tests, build support and BDR documentation should be promoted.

Required BDR acceptance gates:

1. exact Resolutive-DB v1.1.0 build;
2. direct `AtomicDatabase` binding;
3. SQLite/BDR logical equivalence;
4. one logical Memoria.ia memory per atomic BDR sequence;
5. torn-final-write recovery is all-or-none per logical memory;
6. reopen preserves data, metadata and durable sequence;
7. configurable durability cadence does not merge logical atomic transactions;
8. complete Memoria.ia product regression remains green;
9. Linux BDR preferred-backend selection and explicit SQLite fallback behavior are covered by tests.

Known v1.0 limitations to document rather than hide:

- BDR native path remains Linux-first;
- cross-process multi-writer is not enabled;
- the BDR v1.1 `AtomicDatabase` API does not currently expose an independent checkpoint primitive, so the adapter maps the checkpoint boundary to durable sync.

## Core promotion boundary

### Belongs in Memoria.ia

The following concepts are memory/cognition semantics and may be promoted after independent regression review:

- event / episode / pattern / abstraction layers;
- abstraction relations backed by stored evidence;
- candidate ontology and ontology-guided retrieval when conservative and source-traceable;
- structural inference using only explicit stored evidence;
- namespace isolation;
- temporal state and historical queries;
- conflict-aware abstention;
- provenance and explicit confidence;
- independent evidence-origin corroboration;
- source reliability learned only through explicit external adjudication;
- cycle protection for reliability adjudication.

These features must not become required for the deterministic exact-key Product Alpha contract. They should be additive capabilities behind stable interfaces.

### Does not belong in the Memoria.ia runtime core

Identity/governance/network trust experiments are retained as executable research evidence but their production responsibility belongs to MA2A:

- distributed authority identity;
- trusted-root attestations;
- attestation expiry/revocation;
- authority key rotation;
- compromised-key recovery;
- guardian recovery policies;
- independent-controller quorum;
- controller transfer;
- controller-transfer approval quorum;
- transfer-approval revocation;
- protocol-level replay protection tied to distributed identity/governance.

Canonical migration details are tracked in `marceloroldao/ma2a` and referenced by `docs/MA2A_MIGRATION_BOUNDARY.md`.

## MA2A integration rule

Memoria.ia v1.0 must remain usable without MA2A.

The integration boundary should be an optional adapter/interface. The memory engine may receive already-validated identity/governance metadata from MA2A, but it must not become responsible for network PKI, distributed handshakes, licensing certificates, quorum transport or federation policy.

## v1.0 candidate sequence

1. Create clean integration lineage from `main`.
2. Extract and revalidate BDR v1.1 persistence only.
3. Re-run complete Product Alpha acceptance with SQLite and Linux BDR modes.
4. Audit v1.04-v1.16 memory-core experiments and promote only evidence-preserving features that pass the stable-core contract.
5. Keep v1.17+ identity/governance implementation out of the production memory core; preserve tests/source as migration references for MA2A.
6. Add an explicit optional MA2A adapter contract without implementing the distributed protocol in this milestone.
7. Execute end-to-end application -> Memoria.ia -> LLM evaluation with persistent restart, context reuse, hit/miss, token, latency and external-call metrics.
8. Only after those gates are green should a v1.0 release candidate be considered.

## Non-goals for this candidate

- MA2A federation implementation;
- production PKI/security certification;
- ESP32 optimization;
- general-language-understanding claims;
- replacing LLMs;
- merging all experimental branches into the product line.
