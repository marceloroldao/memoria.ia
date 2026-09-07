# Memoria.ia v1.0.0-rc6 — Semantic Relational Context Candidate

Release date: 2026-09-07

## Summary

`v1.0.0-rc6` freezes the post-RC5 work that turns native relational memory into a bounded semantic pre-context layer for OFF.IA and server chat while preserving the local-first and deterministic memory boundary.

Functional freeze commit:

`bcef1111f17be06d8f4c26e78bce4a55cf8e1fbd`

No new runtime features are to be added to the RC6 line after this freeze. Changes after the freeze are restricted to release metadata, documentation, packaging and regression fixes required to publish the candidate coherently.

## Main additions since RC5

- bounded structural relation activation before the LLM;
- validated two-hop traversal with confidence decay and context budgets;
- separation between internal navigation budget and prompt-text budget;
- query-aware relational ranking that preserves alternative evidence;
- bounded composed entity→attribute chains using persisted facts only;
- open-vocabulary predicate ranking;
- graph-backed implicit predicate cues (`volt -> unidade_de -> tensão`, etc.);
- same-user profile fallback for semantic cues with strict namespace isolation;
- generic graph-declared semantic roles (`semantic_role -> predicate|concept`);
- bounded semantic concept planning with a default maximum of two concepts;
- reusable semantic activation resolver;
- server chat wiring without changes to `/conversation/*` public behavior;
- health visibility for semantic chat activation and configured concept limit;
- native/Python parity for relational activation and context budgeting;
- regression proving different query projections over one stable factual state;
- hard contamination barrier excluding unpromoted `assistant_generated` evidence from authoritative factual projection.

## Reference behavior

Examples covered in the frozen lineage include:

- `meu gato -> Alt`, `Alt -> cor -> preto` with `Qual é a cor do meu gato?`;
- `meu roteador -> RB5009`, `RB5009 -> ip -> 192.168.88.1`;
- `bateria -> tensão -> 48 V` with a graph cue `volt -> unidade_de -> tensão`;
- `ONU -> tipo_de -> equipamento` where `tipo_de -> semantic_role -> concept` authorizes bounded concept expansion;
- one factual state supporting both `gato -> {Vivi, Lay}` and `Vivi -> {gato, preto}` without rewriting facts.

The memory layer does not synthesize new factual edges merely to answer the current query. It selects, ranks and projects persisted evidence for the downstream LLM.

## Validation status

The RC6 functional lineage passed the recurring release-blocking gates:

- v0.96 semantic validation;
- product-alpha validation;
- product application credentials;
- Android mobile ABI;
- layered performance baseline;
- Automatic Context on runtime-changing pull requests where applicable.

The final cumulative freeze PR re-ran semantic, product, credentials and performance validation over the exact post-RC5 baseline selected for publication. Android ABI and Automatic Context had already passed immediately before the documentation-only freeze step.

## Architectural boundary

Memoria.ia remains local-first and deterministic at the memory/inference layer. LLMs remain optional consumers and are not the authoritative memory store.

```text
application / OFF.IA / agent
          ↓
      Memoria.ia
          ↓
 Resolutive-DB / BDR
```

The new semantic layer remains bounded. The default activation plan permits at most two concepts and the structural traversal remains bounded rather than becoming unrestricted graph reasoning.

## Known RC6 boundaries

- automatic learning/promotion of new `semantic_role` declarations remains post-RC6 work;
- semantic graph declarations are authoritative only when stored in the allowed factual namespace/provenance path;
- external/public learning on the mobile ABI remains outside this candidate;
- semantic activation is bounded and conservative, not unrestricted general-purpose reasoning;
- no independent production-security certification is claimed;
- MA2A federation remains outside the stable local runtime boundary;
- the final v1.0 promotion remains dependent on a re-audit against the stable RSMS specification.

## Publication lineage

Previous public release:

- `v1.0.0-rc5` — Native Relational Memory Candidate.
- DOI: `10.5281/zenodo.22439650`.

A new RC6 DOI must be inserted only after the archival record exists; no DOI is pre-assigned in this preparation commit.

## Claims boundary

Memoria.ia remains an experimental Resolutive Memory architecture. This release does not claim AGI, unrestricted general reasoning, biological equivalence, production-security certification or replacement of general-purpose LLMs. Claims remain limited to the implementation, tests and reproducible evidence contained in the repository.
