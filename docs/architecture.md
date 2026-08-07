# Resolutive Memory Architecture v0.1

## Layer rule

The experimental hierarchy is defined by:

\[R_L = 8 \cdot 2^L\]

so L0=8 bits, L1=16 bits, L2=32 bits, L3=64 bits.

## Identity vs occurrence

A node represents unique content at a given resolution. An occurrence records where that node appeared in a memory trajectory.

- Node identity: `(layer, payload) -> content digest`
- Occurrence: `(memory_id, layer, local_time, node_id)`

This separation enables deduplication without losing temporal order.

## Retrieval

Queries are decomposed across layers. Candidate nodes are ranked by document frequency, favoring rarer nodes as initial attractors. The current implementation is structural, not semantic: paraphrases that share little byte structure may fail.

## Scientific status

This repository is experimental. v0.1 demonstrates exact reconstruction, multiscale node reuse, and structural retrieval. It does not yet demonstrate semantic understanding or replacement of neural networks.
