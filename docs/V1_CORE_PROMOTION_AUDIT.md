# Memoria.ia v1.0 Core Promotion Audit

This document records the selective promotion decision for the experimental Core lineage and prevents historical experiment branches from being merged wholesale into the v1.0 candidate.

## Promotion rule

Promote capabilities, invariants and tests. Do not promote versioned experiment lineage as architecture.

The v1.11-v1.16 modules are technically useful, but v1.11 depends on v1.10 and v1.10 depends on the v1.09 -> v1.01 semantic/abstraction chain. Copying those modules literally would import the historical research stack into the product candidate. The v1.0 implementation therefore targets a compact evidence-core API with the same externally validated behavior.

## Capability classification

| Experiment | Capability | v1.0 disposition |
|---|---|---|
| v1.11 | structural evidence paths | Promote to Memoria.ia Core |
| v1.12 | temporal state, latest-visible epoch, conflict abstention | Promote to Memoria.ia Core |
| v1.13 | explicit provenance and confidence gating | Promote to Memoria.ia Core |
| v1.14 | independent-origin corroboration | Promote to Memoria.ia Core |
| v1.15 | externally adjudicated source reliability | Promote to Memoria.ia Core, with external adjudication boundary |
| v1.16 | acyclic adjudication dependency guard | Promote to Memoria.ia Core as local evidence-safety invariant |
| v1.17 | authority independence | MA2A boundary / executable specification |
| v1.18 | authority attestations | MA2A boundary / executable specification |
| v1.19 | attestation lifecycle | MA2A boundary / executable specification |
| v1.20 | authority key rotation | MA2A boundary / executable specification |
| v1.21 | compromise recovery | MA2A boundary / executable specification |
| v1.22 | recovery quorum | MA2A boundary / executable specification |
| v1.23 | guardian independence | MA2A boundary / executable specification |
| v1.24 | controller transfer | MA2A boundary / executable specification |
| v1.25 | controller-transfer quorum | MA2A boundary / executable specification |
| v1.26 | approval revocation | MA2A boundary / executable specification |

## Required v1.0 evidence-core invariants

1. Every traversed structural edge must reference explicit source evidence.
2. Multi-hop traversal must never synthesize a new predicate or factual claim.
3. Namespace boundaries are strict; the default namespace is not a wildcard.
4. Temporal observations are append-only and queryable by epoch.
5. For single-valued predicates, conflicting values in the latest visible epoch cause abstention.
6. Confidence is explicit input in [0,1]; path confidence cannot hide a weaker edge.
7. Repetition from one evidence origin does not increase independent-origin count.
8. Source reliability is not learned from the memory's own inference output; it changes only through explicit external adjudication.
9. A reliability adjudication cannot be self-referential and cannot create direct or indirect trust cycles.
10. None of the above depends on certificates, distributed identity, guardians, controller transfer, network quorum or MA2A transport.

## Compatibility requirement

The evidence core must be additive to Product Alpha. Existing `/api/v1` memory, chat, backup/restore and persistence behavior must remain valid. BDR/SQLite remain persistence concerns and must not be coupled to inference semantics.

## Implementation strategy

Create a compact unversioned evidence-core module on `integration/v1.0-core-promotion`. Re-express the v1.11-v1.16 regression cases against that module. Keep the historical versioned experiment modules and branches unchanged as research provenance.

Do not merge v1.01-v1.10 merely to satisfy imports. If a small semantic relation representation is needed, define the minimal stable data contract in the promoted module and bridge experimental parsers separately later.

## Acceptance before merge into integration/v1.0-candidate

- Structural path and namespace tests pass.
- Temporal/conflict tests pass.
- Provenance/confidence tests pass.
- Independent-origin corroboration tests pass.
- Reliability and anti-cycle tests pass.
- Full Ubuntu + Windows regression passes.
- Native Linux BDR regression passes.
- Product HTTP store/restart/chat tests remain unchanged and green.
- No import from v1.17-v1.26 modules exists in promoted runtime code.
