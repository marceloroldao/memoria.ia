# v0.83 — Stochastic stability under noisy regime changes

## Goal

Test whether the v0.82 candidate saturation limit remains robust when observations are noisy and regime changes are not perfectly clean.

The evaluator uses eight deterministic seeds and three observation-noise levels: 5%, 10% and 15%.

Each run contains:

1. initial consolidation of an active concept;
2. a long stable period with stochastic contradictory observations;
3. a persistent inactive regime with stochastic support noise;
4. return to the active regime with stochastic contradiction noise.

The system is evaluated on:

- survival of the stable regime under noise;
- accuracy during the inactive/active regime switches;
- historical-memory retention;
- final reactivation.

## Results

All tested candidates preserved historical memory and returned to the active state in every tested seed. Stable-regime survival was 1.0 in this controlled experiment for all reported candidates.

### 5% observation noise

| max_strength | switch accuracy mean |
|---:|---:|
| 1.25 | **0.8813** |
| 1.50 | 0.8613 |
| 2.00 | 0.8175 |
| 3.00 | 0.7306 |

### 10% observation noise

| max_strength | switch accuracy mean |
|---:|---:|
| 1.25 | **0.8525** |
| 1.50 | 0.8313 |
| 2.00 | 0.7844 |
| 3.00 | 0.6956 |

### 15% observation noise

| max_strength | switch accuracy mean |
|---:|---:|
| 1.25 | **0.8113** |
| 1.50 | 0.7856 |
| 2.00 | 0.7388 |
| 3.00 | 0.6450 |

The standard deviation of switch accuracy remained small across the eight tested seeds (roughly 0.015–0.022 depending on configuration).

## Interpretation

Within this controlled benchmark family, `max_strength=1.25` remains the best stability/plasticity compromise among the tested values. Increasing the saturation ceiling consistently slows adaptation to persistent regime changes without providing an observable robustness advantage in the tested stochastic-noise range.

Therefore `1.25` is promoted from a single-test optimum to a **candidate default** for the saturating lifecycle.

This is not yet a universal constant of the architecture. The value must still survive the semantic/polysemy and broader workload tests planned for v0.85 before it can be considered the default for a release candidate.

## Scientific status

This result supports a bounded-strength mechanism for online adaptation. It does not establish optimality outside the tested workloads, noise model or activation/deactivation thresholds.
