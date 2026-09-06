# Memoria.ia v1.0.0-rc5 — Native Relational Memory Candidate

Release date: 2026-09-06

## Summary

`v1.0.0-rc5` freezes the post-RC4 native relational-memory work for OFF.IA, server and mobile validation.

Functional freeze commit:

`06c747478e05ee11ab2c5c3c24cf75365262b872`

No new runtime features are to be added to the RC5 line after this freeze. Changes after the freeze are restricted to release metadata, documentation, packaging and regression fixes required to publish the candidate coherently.

## Main additions since RC4

- deterministic native concept identity and canonicalization;
- persisted relation-to-concept graph adaptation;
- bounded multi-hop concept relation traversal;
- relational inference activated only after direct resolution fails;
- deterministic natural-language extraction for explicit X↔Y relation questions;
- bounded one-hop relation neighborhood queries;
- deterministic confidence ordering with preserved evidence IDs;
- directional type collection for questions such as `Quais gatos você conhece?`;
- explicit separation between membership edges and taxonomy/attribute edges;
- namespace isolation and fail-closed ambiguity handling across relational modes;
- no LLM, embedding model, neural network or fuzzy matching required for these paths.

## Resolver precedence

The frozen native resolver precedence is:

1. direct/base HIT;
2. explicit or inferred X↔Y relation inference;
3. directional type collection;
4. bounded one-hop neighborhood;
5. UNRESOLVED.

## Concrete regression boundary

The release regression includes a collection case in which:

- `Alt é um gato`;
- `Luna é um gato`;
- `gato é um animal`.

The query `Quais gatos você conhece?` returns Alt and Luna while excluding `animal`, preserving evidence IDs and namespace isolation.

## Validation status

The functional freeze passed the five recurring release-blocking gates:

- v0.96 semantic validation;
- product-alpha validation;
- product application credentials;
- Android mobile ABI;
- layered performance baseline.

## Architectural boundary

Memoria.ia remains local-first and deterministic at the memory/inference layer. LLMs remain optional consumers and are not the authoritative memory store.

```text
application / OFF.IA / agent
          ↓
      Memoria.ia
          ↓
 Resolutive-DB / BDR
```

## Known RC5 boundaries

- external/public learning on the mobile ABI remains outside this candidate;
- collection-query language remains deliberately narrow and fail-closed;
- neighborhood exploration is bounded to one hop in this candidate;
- relational inference is bounded and conservative rather than general-purpose reasoning;
- no independent production-security certification is claimed;
- MA2A federation remains outside the stable local runtime boundary.

## Publication lineage

Previous public release:

- `v1.0.0-rc4` — layered adaptive memory candidate.

Archived prior candidate DOI retained for lineage:

- `v1.0.0-rc2` — DOI: `10.5281/zenodo.22244038`.

A new RC5 DOI must be inserted only after the archival record exists; no DOI is pre-assigned in this preparation commit.

## Claims boundary

Memoria.ia remains an experimental Resolutive Memory architecture. This release does not claim AGI, unrestricted general reasoning, biological equivalence, production-security certification or replacement of general-purpose LLMs. Claims remain limited to the implementation, tests and reproducible evidence contained in the repository.
