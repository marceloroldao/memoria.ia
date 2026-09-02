<p align="center">
  <img src="assets/brand/logo-official.svg" alt="Memoria.ia — Memória Resolutiva" width="760" />
</p>

<p align="center"><strong>Resolutive Memory for persistent state, relations, trajectories and AI context.</strong></p>

# memoria.ia

Experimental implementation of **Resolutive Memory**, a local-first memory architecture built around persistent state, reusable knowledge nodes, multiple trajectories, provenance, online lifecycle dynamics and conservative resolution.

## v1.0 Release Candidate 2

Current freeze candidate: **v1.0.0-rc2** (`1.0.0rc2` package version).

RC2 starts from the published `v1.0.0-rc1` baseline and incorporates the post-v1 capabilities that were intentionally excluded from RC1. The feature set is now frozen; this branch accepts only bug fixes, regression tests, documentation, metadata, packaging and release-gate work.

The runtime architecture remains:

```text
application / OFF.IA / agent
          ↓
      Memoria.ia
          ↓
   Resolutive-DB / BDR
```

Memoria.ia owns memory semantics, state, relations, provenance, trajectories, retrieval and bounded inference. BDR owns durable persistence. LLMs remain optional consumers and do not become the authoritative memory store.

The v1.0.0-rc2 line includes:

- organization and namespace isolation;
- FastAPI `/api/v1` PC/server product interface;
- administrator and scoped application credentials;
- persistent restart/recovery;
- Docker/Compose deployment;
- provider-neutral LLM adapters;
- memory/context/token/latency metrics;
- integrity-checked backup/restore;
- native production runtime path;
- Android arm64-v8a mobile ABI;
- BDR-backed durable native memory state;
- semantic, episodic, temporal and relation kernels;
- provenance and lineage safeguards;
- Retrieval v2 with deterministic normalization, ambiguity checks and conceptual-coverage gates;
- separated evidence dimensions: source authority, retrieval relevance, semantic confidence and freshness;
- automatic episodic capture for identified sessions;
- relation semantic validation before graph promotion;
- `assistant_generated` content blocked from automatic factual relation promotion by default;
- explicit resolution modes: `DIRECT`, `INFERRED`, `UNRESOLVED`, `CONFLICT`;
- bounded deterministic 2-hop Resolutive Inference with proof memory IDs and path confidence;
- strict typed transitive relations: `esta_em`, `parte_de`, `subclasse_de`;
- generic `is` / `é` remains non-transitive;
- inferred conclusions are calculated but are not persisted as new facts.

## Validation status

The final functional slice before RC2 stabilization was PR #153, merged as:

`d893abe1001c74c19a36003f1ee631e266e58cff`

Before merge, the corrected head passed the required gates including Retrieval v2 adapter/matrix, relation validation, typed relation extraction, external relevance, evidence metrics/runtime, automatic episodes, durable restart behavior and Android ARM64 ABI.

The RC2 stabilization branch must remain fully green before tagging.

## Conservative resolution behavior

Memoria.ia intentionally treats uncertainty as a valid outcome.

```text
DIRECT
INFERRED
UNRESOLVED
CONFLICT
```

Direct persisted evidence has precedence. Inference is attempted only after a direct miss and only with explicit structured subject/predicate input. Unsupported relations, insufficient conceptual coverage or equally strong contradictory inference paths fail closed instead of fabricating certainty.

Retrieval and inference remain separate layers: similarity retrieves existing evidence; only explicitly typed and allowlisted transitive relations may produce a new inferred conclusion.

## Security status

**v1.0.0-rc2 is not represented as production-security certified.**

The repository includes authentication boundaries, application isolation, integrity-checked backup/restore and negative security tests, but no independent production security audit is claimed.

## Previous releases

- **v1.0.0-rc1** — first v1 publication candidate; archival DOI **10.5281/zenodo.22170165**.
- **v0.99.0-alpha.1** — first PC/server product alpha.
- **v0.95.1** — archived stable research metadata patch.
- **v0.95.0** — stable research release.

The RC1 DOI must not be reused for RC2. RC2 receives its own archival DOI only after the exact freeze commit is tagged/published.

## Research lineage

The v0.95 research line established controlled experimental stages covering hierarchical and temporal memory, online lifecycle dynamics, consolidation/deconsolidation, polysemy, trajectories, conservative distributed consensus, atomic persistence and scaling/stress benchmarks.

The validated temporal research rule remains:

`r_L = 2^-L`

with the v0.95 research default configuration:

- levels = 5
- max_strength = 1.25

## MA2A boundary

The local v1.0.0-rc2 runtime does not require production MA2A federation or PKI. Personal/private memory must remain local by default, and future federation must preserve explicit scope and provenance boundaries.

## Install and test

Development/test install:

```bash
python -m pip install -e '.[product,test]'
python -m pytest -q
```

Research baseline gate:

```bash
python -m pip install -e '.[test]'
python scripts/release_gate_v95.py
```

Container deployment is defined by `Dockerfile`, `compose.yaml` and `.env.example`.

## Public interfaces

The original research facade exposes:

- `remember(...)`
- `reinforce(...)`
- `challenge(...)`
- `recall(...)`
- `route_status(...)`
- `compare(...)`
- `save(...)`
- `load(...)`

The product layer wraps stable memory behavior behind a versioned HTTP/service boundary. The native/mobile path adds a C ABI with conservative resolution, learning, restart persistence, provenance-aware state and bounded inference behavior.

## Research and claims status

Memoria.ia remains an experimental architecture. v1.0.0-rc2 is a reproducible software release candidate, not a claim of artificial general intelligence, biological equivalence or replacement of general-purpose LLMs.

Important limitations include:

- deterministic Retrieval v2 does not claim universal language understanding;
- Resolutive Inference is bounded to explicit typed 2-hop transitive relations in this RC;
- no claim is made that Memoria.ia eliminates the need for a language model in general conversational tasks;
- performance measurements are workload- and environment-specific;
- distributed/federated operation remains outside the stable local runtime boundary;
- security controls have not undergone independent production certification.

See `KNOWN_LIMITATIONS.md` for the full release boundary.

## License

Source is publicly visible under the **Resolutive Research and Non-Commercial License (RRNCL) v1.0**. Academic, educational and permitted non-commercial research use is allowed under its terms. Commercial use requires separate authorization. Because commercial use is restricted, this project should not be represented as OSI-approved Open Source.

## Resolutive Science compatibility

Compatibility metadata must be re-audited before stable `v1.0.0`. RC2 remains a release candidate until the project-wide RSMS/Resolutive Science compatibility declaration and final publication metadata are confirmed.

## Release notes

See `RELEASE_NOTES_v1.0.0-rc2.md` for the RC2 scope, validation evidence and freeze discipline.
