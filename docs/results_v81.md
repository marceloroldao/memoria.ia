# v0.81 — Saturating lifecycle results

## Motivation

The v0.80 A→B→A continual-learning probe exposed a stability/plasticity failure: layer strength grew without bound under repeated support. After 32 supports, the packed lifecycle required nearly the full 32-step contradictory regime to deactivate, behaving similarly to a simple accumulator.

## Change

v0.81 introduces `SaturatingPackedMemoryLifecycle`, which preserves the layer clock

`r_L = 2^-L`

but caps layer strength at a configurable saturation value. This prevents indefinitely reinforced memories from becoming arbitrarily expensive to revise.

## Controlled A→B→A probe

For 32 active observations, 32 inactive/contradictory observations and 32 active observations again:

| saturation | online accuracy | post-shift accuracy | deactivation steps | reactivation steps | historical depth |
|---:|---:|---:|---:|---:|---:|
| 1.5 | 0.8021 | 0.7188 | 17 | 1 | 4 |
| 2.0 | 0.8021 | 0.7188 | 17 | 1 | 4 |
| 3.0 | 0.7500 | 0.6406 | 22 | 1 | 4 |
| 4.0 | 0.7083 | 0.5781 | 26 | 1 | 4 |
| 8.0 | 0.6667 | 0.5156 | 30 | 1 | 4 |

The unsaturated packed lifecycle required approximately the entire contradictory segment to deactivate in the same probe.

## Interpretation

Saturation improves plasticity while preserving historical depth and fast reactivation. Lower saturation values adapt faster, but the parameter must not be selected from a single benchmark. The next step is a multi-regime and multi-seed sweep including short noise bursts, persistent regime changes and return-to-old-regime tests to identify a stability/plasticity frontier.

This is an experimental result, not evidence of general continual-learning superiority.
