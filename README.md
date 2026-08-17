# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## Current research scope — v0.60

The prototype has evolved from structural hierarchical memory into a broader experimental memory system covering exact reconstruction, deduplication, ordered trajectories, sparse contextual association, online incorporation, temporal/episodic tracking, provenance-aware conflict representation, source reliability, emergent ontology, polysemy, sense consolidation, regime adaptation, layered consolidation/deconsolidation, layer-local clocks, memory lifecycle, stress/scaling analysis and conventional baselines.

v0.58 introduced a capability-per-cost score, but its demonstration experiment still contained placeholder capability/cost values. v0.59 removes that methodological weakness by measuring retention, short-noise resistance, persistent-regime adaptation and reactivation directly from each memory model and pairing those observations with measured latency and peak memory.

v0.60 adds multi-seed statistical evaluation. The same workload family is generated across multiple deterministic seeds and evaluated at multiple event scales. For each system the evaluator reports means and sample standard deviations for quality, latency, peak memory and utility-per-cost, plus a 95% normal-approximation confidence interval for the utility score.

This version intentionally does **not** claim superiority. The next requirement is to execute the v0.60 experiment in clean reproducible environments, record raw results, inspect variance and determine whether any apparent advantage persists across seeds, scales and hardware.

## Install and test

```bash
python -m pip install -e .
python -m pytest -q
```

Key recent experiments:

```bash
python experiments/stress_v55.py
python experiments/baseline_comparison_v57.py
python experiments/capability_cost_v58.py
python experiments/measured_capability_cost_v59.py
python experiments/statistical_robustness_v60.py
```

Third-party datasets remain outside this repository. Earlier experiments remain available under `experiments/`.

## Research status

This is an experimental research project. Results must be treated as controlled prototype evidence until reproduced under larger workloads, external datasets and independent environments. Negative results and failure surfaces are retained rather than hidden by parameter tuning.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
