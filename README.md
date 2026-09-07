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

Release-candidate metadata is checked by:

```bash
python scripts/validate_release_metadata.py
```

The final v1.0 release will only be promoted after the release-candidate gates remain reproducible and the Resolutive Science compatibility boundary is re-audited against a stable RSMS specification.

## Security status

**v1.0.0-rc6 is not represented as production-security certified.**

The repository includes authentication boundaries, application isolation, integrity-checked backup/restore and negative security tests, but no independent production security audit is claimed.

## Previous releases

- **v1.0.0-rc5** — native relational memory candidate; DOI `10.5281/zenodo.22439650`.
- **v1.0.0-rc4** — layered adaptive memory candidate.
- **v1.0.0-rc3** — corrective release candidate that fixed RC2 tag/provenance alignment.
- **v1.0.0-rc2** — archived candidate; DOI `10.5281/zenodo.22244038`.
- **v1.0.0-rc1** — first v1.0 release candidate; DOI `10.5281/zenodo.22170165`.
- **v0.99.0-alpha.1** — first PC/server product alpha.
- **v0.95.1** — archived stable research metadata patch.
- **v0.95.0** — stable research release.

Archived v0.95 DOI: **10.5281/zenodo.21973472**.

## Research lineage

The v0.95 research line established controlled experimental stages covering hierarchical and temporal memory layers, continual online support/contradiction updates, consolidation/deconsolidation/reactivation, polysemy, multinodal and multimodal trajectories, distributed consensus, atomic persistent snapshots and scaling experiments.

The validated temporal research rule remains:

`r_L = 2^-L`

with the v0.95 research default configuration:

- levels = 5
- max_strength = 1.25

## MA2A boundary

The repository retains historical experimental MA2A material, but the network protocol is now treated as a separate architectural boundary/project.

The local v1.0.0-rc6 runtime does not require production MA2A federation or PKI. Personal/private memory must remain local by default, and future federation must preserve explicit scope and provenance boundaries.

See:

- `docs/MA2A_MIGRATION_BOUNDARY.md`
- `docs/ROADMAP_POST_V1.md`

## Install and test

Development/test install:

```bash
python -m pip install -e '.[product,test]'
python -m pytest -q
python scripts/validate_release_metadata.py
```

Research baseline gate:

```bash
python -m pip install -e '.[test]'
python scripts/release_gate_v95.py
```

Container deployment is defined by `Dockerfile`, `compose.yaml` and `.env.example`.

## Public interfaces

The original stable research facade exposes `remember`, `reinforce`, `challenge`, `recall`, `route_status`, `compare`, `save` and `load`. The product layer wraps stable memory behavior behind a versioned HTTP/service boundary. The native/mobile path adds a C ABI with conservative resolution, learning, restart persistence and provenance-aware state behavior.

## Research and claims status

Memoria.ia remains an experimental architecture. v1.0.0-rc6 is a reproducible software release candidate, not a claim of artificial general intelligence, biological equivalence or replacement of general-purpose LLMs.

Important limitations include semantic consolidation remaining experimental, no claim of general language understanding, environment-specific performance measurements, federation outside the stable local runtime boundary, no independent production security certification, and external/public learning remaining a separate development track.

## License

Source is publicly visible under the **Resolutive Research and Non-Commercial License (RRNCL) v1.0**. Academic, educational and permitted non-commercial research use is allowed under its terms. Commercial use requires separate authorization. Because commercial use is restricted, this project should not be represented as OSI-approved Open Source.

## Resolutive Science compatibility

- Resolutive Science published baseline: **v0.2.0**
- Project governance baseline: **RSPS 1.0-draft**
- RSMS compatibility for this candidate: **RSMS 1.0-rc.1**

v1.0.0-rc6 intentionally remains a release candidate while RSMS itself is still at release-candidate compatibility. Before promoting Memoria.ia to final v1.0, this compatibility declaration must be re-audited against the stable RSMS specification.

## Release notes

See `RELEASE_NOTES_v1.0.0-rc6.md` for the publication scope, validation evidence and known boundaries of this candidate.