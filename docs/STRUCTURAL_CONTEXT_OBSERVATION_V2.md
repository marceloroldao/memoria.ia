# Structural Context Observation V2

## Purpose

This experimental V2 component stores and recalls sparse higher-order structural
observations admitted upstream by bit.analyze.

The stored form is:

\`\`\`text
{opaque pattern A, opaque pattern C} -> opaque consequence P
\`\`\`

The antecedent context remains a tuple of two opaque pattern addresses.

No synthetic combined pattern address is created.

## Boundary

Memoria.ia does not:

- generate antecedent combinations;
- search the Cartesian product of remembered patterns;
- decide when higher-order structure is necessary;
- assign semantic meaning to a context;
- assign a causal predicate;
- rank multiple supported consequences by upstream metric score.

Those responsibilities remain outside this component.

## Observation contract

Each admitted observation preserves:

- two canonical antecedent pattern addresses;
- one consequence pattern address;
- upstream candidate ID;
- rho;
- context coverage;
- temporal stability;
- context reliability;
- both lower-order reliabilities;
- repetition count;
- mean consequence delay;
- delay variance;
- independent RealitySlice IDs;
- source frame IDs;
- provenance.

Support inside Memoria.ia is derived from independent RealitySlice provenance rather
than from rho or evidence score.

## Additive evidence

Replaying the identical observation is idempotent.

If the same context/consequence is observed again with new independent slices, support
increases.

If metrics change while slice provenance stays the same, the observations are retained
for audit but independent support is not inflated.

## Recall

\`recall_structural_context()\` requires exactly two antecedent patterns.

A one-pattern query is rejected instead of guessing the missing context.

Supported consequences are returned for the exact canonical context pair.

If multiple consequences independently have sufficient support, all remain visible.
No metric ranking silently chooses a winner.

## Separation from temporal pair memory

This component does not replace:

- \`StructuralTemporalObservationMemory\`;
- \`structural_temporal_recall_v2\`.

Pairwise temporal structure and sparse higher-order context remain separate evidence
types.

## Intended integration

The expected upstream path is:

\`\`\`text
RealitySlice
  -> TemporalAssociator
  -> SparseContextAssociator
  -> higher-order evidence gate
  -> StructuralContextObservationMemory
\`\`\`

The higher-order gate must establish that:

1. the observed context recurs independently;
2. the joint context reliably precedes the consequence;
3. both lower-order antecedent-to-consequence relations remain insufficient.

Memoria.ia receives only the admitted opaque structural candidate.
