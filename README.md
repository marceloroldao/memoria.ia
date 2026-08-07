# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.2 scope

The current prototype implements:

- unique content nodes separated from temporal occurrences
- exact byte reconstruction
- multiscale deduplication
- structural retrieval using rare-node attractors
- persistent storage using SQLite
- indexed node occurrences by memory, layer and local time
- structural trajectory-association experiments
- unit tests and retrieval benchmarks

SQLite persistence deliberately stores both the original payload and the resolutive node graph at this research stage. This makes round-trip validation explicit while the project measures when hierarchical storage becomes advantageous.

The v0.2 association experiment is **structural, not semantic**. It tests whether memories sharing multiscale node trajectories rank closer than unrelated memories without embeddings or neural networks.

## Install and test

```bash
python -m pip install -e .
python -m pytest -q
python benchmarks/benchmark_retrieval.py
```

## Research status

This is an experimental research project. The current implementation tests memory structure, persistence, retrieval and trajectory association. It does **not** yet claim semantic understanding, general intelligence, or replacement of neural networks.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
