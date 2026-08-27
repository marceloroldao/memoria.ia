# MA2A Migration Boundary

This document records the architectural decision that distributed identity, trust, credential lifecycle, recovery governance and controller-transfer governance are not permanent responsibilities of the Memoria.ia memory core.

The canonical integration specification is maintained in:

`marceloroldao/ma2a` → `docs/MEMORIA_IA_INTEGRATION_BOUNDARY.md`

## Remain in Memoria.ia

- deterministic memory storage/retrieval;
- hierarchical temporal memory;
- consolidation/deconsolidation/reactivation;
- contradiction/reinforcement handling;
- namespace isolation;
- source-backed structural evidence and bounded structural inference;
- temporal state/history;
- provenance and confidence metadata;
- independent evidence-origin corroboration;
- source reliability and adjudication-cycle protection;
- abstraction/ontology-oriented memory structures;
- persistence abstraction (BDR/SQLite);
- standalone product isolation and auditability.

## Migrate to MA2A

The v1.17-v1.26 experimental governance lineage is retained as behavioral reference, but the permanent implementations belong to MA2A:

- distributed authority/root-of-control identity;
- trusted authority attestations;
- attestation expiry/revocation lifecycle;
- authority key rotation and continuity;
- compromised-key recovery;
- N-of-M recovery quorum;
- guardian/controller-domain independence;
- controller transfer;
- controller-transfer quorum;
- transfer-approval revocation;
- associated replay protection and network trust-policy epochs;
- cryptographic verification and network credential handling.

## Rule

Memoria.ia must remain fully usable without MA2A.

When MA2A is enabled, Memoria.ia should consume validated identity/trust/provenance metadata through a narrow MA2A adapter instead of performing distributed trust decisions itself.

Do not delete the existing experimental modules/tests during migration. They are executable specifications that should be ported into MA2A conformance/security tests before runtime responsibility is removed from Memoria.ia.
