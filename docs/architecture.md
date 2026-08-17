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

## Contextual association — v0.4

v0.4 tests whether association can emerge from repeated trajectory context without predeclared synonym tables, dense embeddings or neural networks.

For each observed node `n`, the model accumulates a sparse contextual profile:

`C(n)[(delta, neighbor)] += 1`

where `delta` is the signed relative position of a neighboring node inside a configurable trajectory radius.

Two nodes are compared by weighted cosine similarity between these sparse contextual profiles. Context features shared by many nodes are down-weighted with inverse-frequency weighting, while rarer contextual features contribute more strongly.

In a controlled experiment, two distinct symbolic nodes repeatedly exposed to the same trajectory neighborhoods converge to a high contextual similarity, while a node exposed to unrelated neighborhoods receives a substantially lower score.

This behavior is best described as **distributional structural association**. It demonstrates learned contextual convergence, but it is not by itself proof that the system understands lexical semantics or abstract meaning.

## Current limits

The system currently measures structural, sequential, temporal and contextual similarity. Contextual convergence must still be stress-tested on larger corpora, adversarial cases, paraphrases and multimodal data before stronger cognitive claims are justified.
