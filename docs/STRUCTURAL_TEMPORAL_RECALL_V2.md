# Structural Temporal Recall V2

## Purpose

This experimental V2 component recalls supported passive temporal structure and can
intersect that structure with concrete continuation candidates supplied by an external
world.

It does not generate world futures.

The design separates:

\`\`\`text
recall of remembered structure
        !=
creation of a possible future
\`\`\`

## Module

\`src/memoria_resolutiva/structural_temporal_recall_v2.py\`

Validated code lineage:

\`experiment/address-trajectory-v2\`

Gate commit:

\`438c273d98479a550e2162964deecf737e0a5891\`

## Recall

\`recall_structural_temporal_neighbors()\` takes one opaque pattern address and returns
supported temporal neighbors.

Relations are expressed only relative to the query:

- \`after_query\`
- \`before_query\`
- \`simultaneous\`

Example:

\`\`\`text
memory:
A before B

query A -> B is after_query
query B -> A is before_query
\`\`\`

Only hypotheses with the required independent RealitySlice support are returned.

Recall is read-only.

## World candidate intersection

\`resolve_temporal_world_candidates()\` receives:

1. the current opaque pattern;
2. a tuple of concrete candidates supplied by the World Runtime.

Each candidate contains:

\`\`\`text
candidate_id
pattern_address
\`\`\`

Memoria.ia is not allowed to append candidates to that set.

A remembered pattern absent from the supplied world candidate set cannot become a
resolved continuation.

## Supported continuation

A concrete future candidate is supported only when memory contains a supported
\`after_query\` relation from the current pattern to that candidate pattern.

A remembered:

- \`before_query\` relation does not support a future;
- \`simultaneous\` relation does not support a future.

## Multiple futures

If two concrete world candidates are independently supported as future continuations,
the resolver returns ambiguity.

It does not compare rho, evidence_score or another metric to choose a winner.

## Contested relation

If the same pair contains both:

\`\`\`text
A before B
B before A
\`\`\`

with independent support, and the world offers B as a future of A, B remains
contested.

The resolver returns:

\`\`\`text
resolved = false
ambiguous = true
reason = contested-supported-world-continuation
\`\`\`

No temporal orientation is deleted.

## Boundary

The component never:

- creates a World Runtime candidate;
- mutates structural temporal observation memory;
- writes causal intervention memory;
- promotes temporal support to semantic meaning;
- promotes association to causality.

It only performs recall plus set intersection.

## Acceptance

The gate validates:

- direction relative to query;
- exclusion of insufficient support;
- single supported world continuation;
- no invention when remembered continuation is absent from world candidates;
- ambiguity for multiple supported concrete futures;
- reverse-only relation not treated as future;
- contested orientation ambiguity;
- simultaneous recall not treated as future;
- read-only resolution;
- duplicate world candidate rejection.
