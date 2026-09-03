<p align="center">
  <img src="assets/brand/logo-official.svg" alt="Memoria.ia — Memória Resolutiva" width="760" />
</p>

<p align="center"><strong>Resolutive Memory for persistent state, relations, trajectories and AI context.</strong></p>

<p align="center"><a href="assets/brand/BRAND_GUIDE.md">Visual identity</a> · <a href="assets/brand/README.md">Brand assets</a></p>

# memoria.ia

Experimental implementation of **Resolutive Memory**, a local-first memory architecture built around persistent state, reusable knowledge nodes, multiple trajectories, provenance, online lifecycle dynamics and conservative resolution.

## v1.0 release candidate

Current publication candidate: **v1.0.0-rc4** (`1.0.0rc4` package version).

RC4 functional freeze: **`b4a891eb76e7fc51a272120b55dff07abe58e451`**.

The most recent archived DOI in this release lineage remains the RC2 record: **[10.5281/zenodo.22244038](https://doi.org/10.5281/zenodo.22244038)**. A dedicated RC4 DOI is added only after the archival record exists.

This release candidate consolidates the validated research core and deployable PC/server/mobile runtime boundary while preserving the architecture:

```text
application / OFF.IA / agent
          ↓
      Memoria.ia
          ↓
   Resolutive-DB / BDR
```

Memoria.ia owns memory semantics, state, relations, provenance, trajectories, abstraction, recomputation policy and context selection. BDR owns durable persistence. LLMs remain optional consumers and do not become the authoritative memory store.

The v1.0.0-rc4 line includes:

- organization-scoped memory isolation;
- FastAPI `/api/v1` PC/server product interface;
- administrator and scoped application credentials;
- persistent restart/recovery;
- Docker/Compose deployment;
- provider-neutral LLM adapter with mock, Gemini and OpenAI implementations;
- memory/context/token/latency metrics;
- backup/restore with SHA-256 integrity validation;
- native production runtime path;
- Android arm64-v8a mobile ABI;
- BDR-backed durable native memory state;
- semantic, episodic, temporal and relation kernels;
- namespace isolation and provenance lineage;
- conservative `HIT` / `MISS` / `UNRESOLVED` behavior;
- indexed native resolve path for large-memory workloads;
- explicit layered factual abstraction with provenance;
- vertical dependency edges between abstraction levels;
- selective invalidation of dependent facts and abstractions;
- incremental recomputation of affected branches;
- multi-root batch recomputation with shared-ancestor deduplication;
- adaptive incremental/full recomputation by affected graph density;
- optional hysteresis for oscillating workloads;
- deterministic workload profiling and audited strategy execution;
- reproducible layered scale and performance baselines;
- official Memoria.ia visual identity assets.

The RC4 candidate is intentionally frozen from further feature expansion. After the functional freeze, changes on this release line are restricted to stabilization, regression fixes, documentation, packaging and publication validation.

## Validation status

The RC4 functional lineage passed the semantic, product, credentials and layered-performance gates before the release branch was prepared.

Representative deterministic layered baseline:

- 127 nodes: 7 incremental nodes touched versus 127 full;
- 1,023 nodes: 10 incremental nodes touched versus 1,023 full;
- 16,383 nodes: 14 incremental nodes touched versus 16,383 full.

The recorded 16,383-node CI baseline measured roughly **0.125 ms** for the local incremental update versus **75.716 ms** for full recomputation on that specific runner. These are environment-specific measurements; exact snapshot equivalence and touched-node locality are the deterministic correctness criteria.

Release-candidate metadata is checked by:

```bash
python scripts/validate_release_metadata.py
```

The final v1.0 release will only be promoted after the release-candidate gates remain reproducible and the Resolutive Science compatibility boundary is re-audited against a stable RSMS specification.

## Security status

**v1.0.0-rc4 is not represented as production-security certified.**

The repository includes authentication boundaries, application isolation, integrity-checked backup/restore and negative security tests, but no independent production security audit is claimed.

## Previous releases

- **v1.0.0-rc3** — corrective release candidate that fixed RC2 tag/provenance alignment.
- **v1.0.0-rc2** — archived candidate; DOI `10.5281/zenodo.22244038`.
- **v1.0.0-rc1** — first v1.0 release candidate; DOI `10.5281/zenodo.22170165`.
- **v0.99.0-alpha.1** — first PC/server product alpha.
- **v0.95.1** — archived stable research metadata patch.
- **v0.95.0** — stable research release.

Archived v0.95 DOI: **10.5281/zenodo.21973472**.

## Research lineage

The v0.95 research line established controlled experimental stages covering:

- hierarchical and temporal memory layers;
- online support/contradiction updates without neural retraining;
- consolidation, deconsolidation and reactivation;
- saturation-based stability/plasticity control;
- polysemy and sense-consolidation experiments;
- multinodal and multimodal trajectories;
- individual and collective memory routes;
- shared payloads with independent route confidence;
- conservative distributed consensus (`same`, `related`, `conflict`, `distinct`);
- atomic persistent snapshots with integrity validation;
- compact snapshot transport format;
- scaling, memory-cost, stress and continual-learning benchmarks.

The validated temporal research rule remains:

`r_L = 2^-L`

with the v0.95 research default configuration:

- levels = 5
- max_strength = 1.25

## MA2A boundary

The repository retains historical experimental MA2A material, but the network protocol is now treated as a separate architectural boundary/project.

The local v1.0.0-rc4 runtime does not require production MA2A federation or PKI. Personal/private memory must remain local by default, and future federation must preserve explicit scope and provenance boundaries.

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

Representative research experiments remain under `experiments/`.

## Public interfaces

The original stable research facade exposes:

- `remember(...)`
- `reinforce(...)`
- `challenge(...)`
- `recall(...)`
- `route_status(...)`
- `compare(...)`
- `save(...)`
- `load(...)`

The product layer wraps stable memory behavior behind a versioned HTTP/service boundary. The native/mobile path adds a C ABI with conservative resolution, learning, restart persistence and provenance-aware state behavior.

See the documentation under `docs/` for API, Android runtime, BDR integration, reproducibility and production-path boundaries.

## Research and claims status

Memoria.ia remains an experimental architecture. v1.0.0-rc4 is a reproducible software release candidate, not a claim of artificial general intelligence, biological equivalence or replacement of general-purpose LLMs.

Important limitations include:

- semantic consolidation remains experimental and does not claim general language understanding;
- no claim is made that Memoria.ia eliminates the need for a language model in general conversational tasks;
- performance measurements are workload- and environment-specific;
- distributed/federated operation remains outside the stable local runtime boundary;
- security controls have not undergone an independent production certification;
- post-v1 external/public learning and autonomous curiosity remain separate development tracks.

Negative results, failed hypotheses and known limitations are intentionally retained where applicable.

## License

Source is publicly visible under the **Resolutive Research and Non-Commercial License (RRNCL) v1.0**. Academic, educational and permitted non-commercial research use is allowed under its terms. Commercial use requires separate authorization. Because commercial use is restricted, this project should not be represented as OSI-approved Open Source.

## Resolutive Science compatibility

- Resolutive Science published baseline: **v0.2.0**
- Project governance baseline: **RSPS 1.0-draft**
- RSMS compatibility for this candidate: **RSMS 1.0-rc.1**

v1.0.0-rc4 intentionally remains a release candidate while RSMS itself is still at release-candidate compatibility. Before promoting Memoria.ia to final v1.0, this compatibility declaration must be re-audited against the stable RSMS specification.

## Release notes

See `RELEASE_NOTES_v1.0.0-rc4.md` for the publication scope, validation evidence and known boundaries of this candidate.
