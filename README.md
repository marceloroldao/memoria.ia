<p align="center">
  <img src="assets/brand/logo-official.svg" alt="Memoria.ia — Memória Resolutiva" width="760" />
</p>

<p align="center"><strong>Resolutive Memory for persistent state, relations, trajectories and AI context.</strong></p>

<p align="center"><a href="assets/brand/BRAND_GUIDE.md">Visual identity</a> · <a href="assets/brand/README.md">Brand assets</a></p>

# memoria.ia

Experimental implementation of **Resolutive Memory**, a local-first memory architecture built around persistent state, reusable knowledge nodes, multiple trajectories, provenance, online lifecycle dynamics and conservative resolution.

## v1.0 release candidate

Current publication candidate: **v1.0.0-rc6** (`1.0.0rc6` package version).

RC6 functional freeze: **`bcef1111f17be06d8f4c26e78bce4a55cf8e1fbd`**.

RC6 archived release DOI: **[10.5281/zenodo.22648409](https://doi.org/10.5281/zenodo.22648409)**.

Previous archived release RC5: **[10.5281/zenodo.22439650](https://doi.org/10.5281/zenodo.22439650)**.

This release candidate consolidates the validated research core and deployable PC/server/mobile runtime boundary while preserving the architecture:

```text
application / OFF.IA / agent
          ↓
      Memoria.ia
          ↓
   Resolutive-DB / BDR
```

Memoria.ia owns memory semantics, state, relations, provenance, trajectories, abstraction, recomputation policy and context selection. BDR owns durable persistence. LLMs remain optional consumers and do not become the authoritative memory store.

The v1.0.0-rc6 line includes the RC5 native relational baseline plus:

- bounded structural relational activation before the LLM, including validated two-hop traversal;
- independent navigation and prompt-context budgets;
- query-aware relational ranking that preserves alternative evidence;
- bounded composed entity→attribute chains without synthesizing new facts;
- open-vocabulary predicate ranking;
- graph-backed implicit predicate cues such as `volt -> unidade_de -> tensão`;
- profile fallback for semantic cues with strict same-user/application isolation;
- generic graph-declared semantic roles such as `semantic_role -> predicate|concept`;
- bounded semantic concept planning with a default maximum of two activated concepts;
- semantic activation wired into server chat without changing the public conversation API;
- factual projection reuse across different query orientations;
- explicit contamination barriers that prevent unpromoted `assistant_generated` content from becoming authoritative factual evidence;
- Android/native ABI, product, credentials, semantic and performance regression parity across the frozen line.

The RC6 candidate is intentionally frozen from further feature expansion. After the functional freeze, changes on this release line are restricted to stabilization, regression fixes, documentation, packaging and publication validation.

## Validation status

The RC6 functional lineage passed the recurring release-blocking gates before the publication branch was prepared:

- v0.96 semantic validation;
- product-alpha validation;
- product application credentials;
- Android mobile ABI;
- layered performance baseline;
- Automatic Context on runtime-changing PRs where applicable.
