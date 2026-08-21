# memoria.ia

Experimental implementation of **Resolutive Memory**, a memory architecture built around reusable knowledge nodes, multiple trajectories, online lifecycle dynamics, distributed consensus, and persistence.

## Archived release

Latest archived release: **v0.95.1**  
Zenodo DOI: **10.5281/zenodo.21973472**

## Current maturity — v0.95 series

The v0.95 stable research line consolidates controlled experimental stages covering:

- hierarchical and temporal memory layers;
- online support/contradiction updates without neural retraining;
- consolidation, deconsolidation and reactivation;
- saturation-based stability/plasticity control;
- polysemy and sense-consolidation experiments;
- multinodal and multimodal trajectories;
- individual and collective memory routes;
- shared payloads with independent route confidence;
- conservative distributed consensus (`same`, `related`, `conflict`, `distinct`);
- atomic persistent snapshots with CRC validation;
- compact snapshot transport format;
- scaling, memory-cost, stress and continual-learning benchmarks.

The validated temporal rule remains:

`r_L = 2^-L`

with the v0.95 default configuration:

- levels = 5
- max_strength = 1.25

## MA2A — Agent-to-Agent Protocol

The project includes the experimental **Memoria.ia Agent-to-Agent Protocol (MA2A) v0.1** specification:

- `docs/RFC_MA2A_v0.1.md`

MA2A defines deterministic agent discovery, authenticated session negotiation, canonical trajectory addressing, `RESOLVE_REQ` / `RESOLVE_RESP`, delta synchronization, reinforcement signaling, deterministic conflict resolution, replay protection, and hard namespace isolation.

Its core interoperability principle is:

> **Agents exchange state, not conversation.**

The base privacy invariant is structural: trajectories under `("user", "private", ...)` MUST be rejected before transport serialization and MUST NOT be persisted or processed by L2/L3 synchronization infrastructure.

### MA2A reference implementation

The experimental reference core lives in:

- `src/memoria_resolutiva/a2a.py`
- `tests/test_a2a_protocol.py`
- `scripts/ma2a_reference_demo.py`

It currently implements canonical trajectory encoding/hashing, fail-closed transport namespace enforcement, canonical JSON framing, Ed25519 node identities/signatures, replay protection, deterministic state hashing, idempotent delta application, direct trajectory resolution, and deterministic tie-breaking for already-detected concurrent scalar writes.

Install the MA2A crypto dependency and run the executable two-agent demonstration with:

```bash
python -m pip install -e '.[a2a]'
python scripts/ma2a_reference_demo.py
```

Run the MA2A conformance tests with:

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_a2a_protocol.py
```

The reference core intentionally does not yet freeze a production network transport. WebSocket, QUIC, IPv6 overlay, VPN, LAN, Wi-Fi Direct, and Bluetooth transports can be layered around the same signed MA2A frames without changing protocol semantics.

The MA2A RFC is currently an experimental protocol specification. Performance claims for local Resolutive Memory remain separate from end-to-end network behavior and require reproducible benchmark validation.

## Validation

The v0.95 implementation was promoted from `v0.95.0rc1` after a clean Google Colab checkout on Python 3.12 completed the full release gate:

- 267 tests passed;
- 0 failures;
- `python scripts/release_gate_v95.py`;
- final output: `v0.95 release gate: PASS`.

The `v0.95.1` release is a metadata-only citation interoperability fix over the validated v0.95.0 implementation.

## Install and test

```bash
python -m pip install -e '.[test]'
python scripts/release_gate_v95.py
```

Representative recent experiments:

```bash
python experiments/compact_stress_v63.py
python experiments/scaling_v64.py
python experiments/stability_plasticity_v82.py
python experiments/stochastic_stability_v83.py
python experiments/multitrajectory_v87.py
python experiments/compact_snapshot_v93.py
python experiments/incompressible_snapshot_v94.py
```

## Public API

The v0.95 facade exposes:

- `remember(...)`
- `reinforce(...)`
- `challenge(...)`
- `recall(...)`
- `route_status(...)`
- `compare(...)`
- `save(...)`
- `load(...)`

See `docs/API_V090.md` and subsequent persistence/result notes.

## Research status

This remains a research implementation, not a claim of general intelligence or a final v1.0 architecture. Claims are limited to controlled tests in this repository. Negative results, failed hypotheses and known limits are retained.

Important known limitations include:

- payload and trajectory persistence currently requires JSON-serializable values;
- compact snapshot compression depends on data redundancy and may trade CPU time for storage savings;
- semantic consolidation remains experimental and does not claim general language understanding;
- no claim is made that this replaces a general neural model or LLM;
- distributed consensus is conservative and deliberately avoids automatic destructive merge for merely related knowledge.

## License

Source is publicly visible under the **Resolutive Research and Non-Commercial License (RRNCL) v1.0**. Academic, educational and non-commercial research use is permitted under its terms. Commercial use requires separate authorization. Because commercial use is restricted, this project should not be represented as OSI-approved Open Source.

## Resolutive Science compatibility

- Resolutive Science repository baseline: **v0.1.1**
- Project governance baseline: **RSPS 1.0-draft**
- RSMS compatibility: **1.0-rc.1 — candidate compatibility**

The current declaration is pinned to the published RSMS release-candidate specification in `resolutive-science`. It must be re-audited when RSMS 1.0 becomes stable and before a stable `memoria.ia` v1.0 release. Project-specific computational semantics remain subordinate to explicit RSMS definitions where shared terminology is used.
