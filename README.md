# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## v0.1 scope

The first reproducible prototype implements:

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits
- unique content nodes separated from occurrences
- exact byte reconstruction
- multiscale deduplication
- structural retrieval using rare-node attractors
- tests and a retrieval benchmark

The layer rule is:

`R(L) = 8 * 2^L`

## Install and test

```bash
python -m pip install -e .
python -m pytest -q
python benchmarks/benchmark_retrieval.py
```

## Research status

This is an experimental research project. The current implementation tests memory structure and retrieval. It does **not** yet claim semantic understanding, general intelligence, or replacement of neural networks.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
