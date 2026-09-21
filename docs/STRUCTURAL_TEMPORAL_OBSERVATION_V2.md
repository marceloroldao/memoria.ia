# Structural Temporal Observation V2

## Purpose

This experimental V2 component stores **passive temporal structure** separately from
intervention/consequence memory.

It is designed for evidence produced upstream by systems such as bit.analyze after an
explicit admission gate.

The memory does not assert that an observed temporal association is:

- causal;
- factual;
- semantically understood;
- a law;
- a truth claim.

It only preserves structural temporal observations and their provenance.

## Contract

Module:

`src/memoria_resolutiva/structural_temporal_observation_v2.py`

Primary types:

- `StructuralTemporalObservation`
- `StructuralTemporalHypothesis`
- `StructuralTemporalResolution`
- `StructuralTemporalObservationMemory`

An observation contains two opaque pattern addresses, one orientation, upstream
evidence metrics, and supporting provenance.

Supported orientations:

- `a_before_b`
- `simultaneous`
- `b_before_a`

## Separation from causal memory

This component is deliberately independent from `InterventionConsequenceMemory`.

Passive temporal association does not contain a real intervention boundary. Creating a
synthetic intervention merely to reuse causal memory would incorrectly turn passive
observation into intervention-shaped evidence.

## Reinforcement

Support is based on the union of unique `supporting_slice_ids`.

If the same candidate is observed first with slices:

```text
1, 2, 3
```

and later with:

```text
1, 2, 3, 4
```

the independent support is 4, not 7.

Exact replay of the same evidence bundle is idempotent.

## Conflict

Different orientations are preserved independently.

If `a_before_b` has sufficient support and a one-slice `b_before_a` observation
arrives, the supported orientation remains visible while the competitor is preserved
as unsupported evidence.

If both orientations independently reach the configured support threshold, resolution
becomes:

```text
resolved = false
ambiguous = true
reason = competing-supported-orientations
```

No history is deleted and no orientation is marked false.

## Metrics

The observation preserves upstream metrics such as:

- rho;
- selectivity;
- temporal stability;
- evidence score;
- orientation confidence;
- mean dt;
- dt variance.

These values are audit evidence. They are **not** used internally as a hidden truth
weight.

Current structural reinforcement is derived from independent provenance support.

## Persistence surface

`snapshot()` returns immutable observation history.

`restore()` rebuilds the same observation memory deterministically.

This gate does not yet define durable BDR persistence.

## Acceptance

The V2 gate validates:

- one supported orientation;
- idempotent replay;
- overlapping provenance union;
- preserved conflicting orientation;
- ambiguity when competing orientations are both supported;
- pair canonicalization;
- audit-metric preservation without support inflation;
- snapshot/restore determinism;
- invalid same-pattern relation rejection.
