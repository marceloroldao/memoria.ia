# Resolutive Memory Architecture

## Layer rule

The memory hierarchy uses:

`R(L) = 8 * 2^L`

so the first layers are L0=8, L1=16, L2=32 and L3=64 bits.

## Node identity vs occurrence

A node represents reusable content identity. An occurrence represents where that node appeared:

`Occurrence = (memory_id, layer, local_time, node_id)`

This separation allows one node to be referenced by many memories without duplicating its identity.

## Retrieval

Structural retrieval decomposes a query through the configured layers, selects rare nodes as attractors and scores memories containing those attractors. This is an indexed structural retrieval mechanism, not semantic embedding search.

## Persistence

The SQLite backend stores memories, unique nodes and occurrences separately. Indexes are maintained for node lookup and ordered reconstruction by `(memory_id, layer, local_time)`.

At the current research stage the original memory payload is retained to make exact round-trip validation explicit.

## Ordered trajectory similarity — v0.3

v0.3 adds trajectory order and temporal spacing to association.

For two occurrence trajectories A and B, the prototype computes:

`S = (1 - w_t) * S_order + w_t * S_time`

where:

- `S_order` is the normalized longest-common-subsequence score over node identities;
- `S_time` compares local-time deltas between successive occurrences;
- `w_t` controls the contribution of temporal consistency.

This means that identical node sets no longer imply identical memories. A reversed or temporally distorted trajectory receives a lower score than the same ordered trajectory.

## Current limits

The system currently measures structural and sequential similarity. It does not yet infer lexical semantics, synonymy or abstract meaning. Those are future experimental targets and must be evaluated separately.
