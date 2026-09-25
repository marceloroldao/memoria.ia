<p align="center">
  <img src="assets/brand/logo-official.svg" alt="Memoria.ia — Memória Resolutiva" width="760" />
</p>

<p align="center"><strong>Resolutive Memory for persistent state, relations, trajectories and AI context.</strong></p>

<p align="center"><a href="assets/brand/BRAND_GUIDE.md">Visual identity</a> · <a href="assets/brand/README.md">Brand assets</a></p>

# memoria.ia

Experimental implementation of **Resolutive Memory**, a local-first memory architecture for persistent state, reusable structural nodes, provenance, recurrence, temporal dynamics and conservative resolution.

## v2.0 release candidates

Published structural baseline: **v2.0.0-rc1** (archived package version `2.0.0rc1`). The cognitive-core candidate **[v2.0.0-rc2](https://github.com/marceloroldao/memoria.ia/releases/tag/v2.0.0-rc2)** is published as a GitHub pre-release with package version `2.0.0rc2` on commit `e38f27b639bec1cfcb83694c1418a4d01f250ffd`; its software DOI is **[10.5281/zenodo.22949633](https://doi.org/10.5281/zenodo.22949633)**. Its functional freeze is `e240bf2197000f955d65edec5dba47045d9f237e`. See `docs/V2_RC2_FREEZE_RECORD.md` and `RELEASE_NOTES_v2.0.0-rc2.md`.

V2 RC1 functional freeze commit: **`bd33b9cfcfa78f0e3850fb5e298cbf4cbdc360b9`**.

Published companion Resolutive-DB/BDR candidate for the current native/mobile structural runtime: **`v1.2.0-rc4`** at **`317882a00f041fc1568ff986af8016b09453f21a`**, DOI **[10.5281/zenodo.22948288](https://doi.org/10.5281/zenodo.22948288)**. Memoria.ia cross-repository validation against this pin passed on PR #361; see `docs/V2_RC2_FREEZE_RECORD.md` for the exact runs.

The V2 RC1 historical validation used BDR commit `d09914b85646353d8fd004ccf99e96a94fab9eef`; its archived release notes and DOI remain unchanged.

V2 RC1 archived release DOI: **[10.5281/zenodo.22908785](https://doi.org/10.5281/zenodo.22908785)**.

Previous archived release RC7 DOI: **[10.5281/zenodo.22654141](https://doi.org/10.5281/zenodo.22654141)**.

The architecture remains:

```text
application / OFF.IA / agent
          ↓
      Memoria.ia
          ↓
   Resolutive-DB / BDR
```

Memoria.ia owns memory structure, state, relations, provenance, temporal/recurrence dynamics and context selection. BDR owns durable persistence. LLMs are optional consumers and are not the authoritative memory store.

## What V2 RC1 freezes

V2 RC1 freezes the structural-memory baseline before the next inference-oriented development line. The frozen runtime includes:

- structural text observation;
- read-only structural resolution;
- deterministic structural token identity and native/Python integration;
- recurrence-sensitive association/ranking behavior;
- coexistence of competing observations instead of forced destructive correction;
- physical/continuous decay and bounded selectivity mechanisms developed in the V2 structural line;
- persistence and cold reopen through the shared BDR runtime;
- source/provenance preservation;
- native/mobile structural ABI for OFF.IA;
- structural server endpoints already present in the V2 line;
- negative behavior in which unrelated queries remain unresolved instead of leaking unrelated remembered context.

This candidate does **not** claim that general inference over trajectories is complete. Explicit addressed evolving state, trajectory traversal, attractor dynamics, a no-LLM Resolutive Inference Engine and the future Context Compiler belong to the post-RC1 V2 roadmap.

## Validation boundary

The structural V2 lineage used as the functional freeze has been exercised through repository/native integration gates covering:

- structural observation and resolution;
- recurrence-sensitive competing observations;
- coexistence of old and newer evidence;
- unrelated-query selectivity;
- persistence/cold reopen;
- native/mobile ABI exposure;
- OFF.IA-facing structural integration.

Queries must remain read-only: asking a question must not reinforce its own candidate answer.

No benchmark result should be represented as resolutive inference if the result is actually produced by an LLM or by a domain-specific hard-coded semantic rule.

Release-candidate metadata is checked by:

```bash
python scripts/validate_release_metadata.py
```

## Security status

**v2.0.0-rc1 is not represented as production-security certified.**

The repository contains security and isolation mechanisms, but no independent production security audit is claimed.

## Previous releases

- **v2.0.0-rc1** — structural V2 baseline; DOI `10.5281/zenodo.22908785`.
- **v1.0.0-rc7** — stabilization and consistency candidate; DOI `10.5281/zenodo.22654141`.
- **v1.0.0-rc6** — semantic relational context candidate; DOI `10.5281/zenodo.22648409`.
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

The research line established controlled experimental stages covering hierarchical and temporal memory layers, continual support/contradiction updates, consolidation/deconsolidation/reactivation, polysemy, multinodal and multimodal trajectories, distributed consensus, persistent snapshots and scaling experiments.

The validated historical temporal research rule remains:

`r_L = 2^-L`

with the v0.95 research default configuration:

- levels = 5
- max_strength = 1.25

## Post-RC1 direction

The next V2 development line is intentionally separated from this freeze. Its planned sequence is:

1. preserve the RC1 empirical baseline;
2. introduce stable addresses with evolving state/payload;
3. represent explicit forward/reverse trajectories;
4. evolve attractor dynamics from recurrence, time, density and provenance;
5. implement resolutive inference over persisted memory state before any LLM;
6. benchmark with LLM calls disabled;
7. compare against a conventional RAG control;
8. introduce a compact cognitive package/Context Compiler;
9. connect modality-neutral StructuralEvent/RealitySlice input;
10. evolve local/server distributed memory with explicit provenance.

The roadmap is developed separately so that this RC1 remains a reproducible historical baseline.

## MA2A boundary

Network federation remains a separate architectural boundary/project. The local V2 RC1 runtime does not require production MA2A federation or PKI. Personal/private memory must remain local by default unless an explicit synchronization policy authorizes otherwise.

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

The project contains research, product/server and native/mobile boundaries. The V2 RC1 structural path adds observation and read-only resolution of structural text through the server/native layers while retaining provenance and BDR persistence.

## Research and claims status

Memoria.ia remains an experimental architecture. v2.0.0-rc1 is a reproducible structural-memory release candidate, not a claim of AGI, unrestricted general reasoning, biological equivalence or replacement of general-purpose LLMs.

The central post-RC1 research question is whether useful inference can increasingly occur over Memoria.ia's own persistent state and trajectories before language generation.

## License

Source is publicly visible under the **Resolutive Research and Non-Commercial License (RRNCL) v1.0**. Academic, educational and permitted non-commercial research use is allowed under its terms. Commercial use requires separate authorization. Because commercial use is restricted, this project should not be represented as OSI-approved Open Source.

## Resolutive Science compatibility

- Resolutive Science published baseline: **v0.2.0**
- Project governance baseline: **RSPS 1.0-draft**
- RSMS compatibility declaration remains experimental and must be re-audited before any stable V2 promotion.

## Release notes

See `RELEASE_NOTES_v2.0.0-rc1.md` for the publication scope, validation evidence and known boundaries of this candidate.
