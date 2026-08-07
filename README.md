# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.9 scope

The current prototype implements:

- unique content nodes separated from temporal occurrences
- exact byte reconstruction
- multiscale deduplication
- structural retrieval using rare-node attractors
- persistent storage using SQLite
- indexed node occurrences by memory, layer and local time
- structural trajectory-association experiments
- ordered trajectory similarity using sequence alignment
- temporal-delta consistency between occurrences
- sparse contextual association learned from repeated trajectory neighborhoods
- nearest-context lookup without embeddings or neural networks
- multidomain controlled corpora with hidden associations
- automatic top-1 and top-k association metrics
- noise-injection and adversarial-distractor experiments
- association-margin evaluation
- deterministic natural-language tokenization
- sentence-level contextual observation
- ambiguity probing using ranked alternatives, entropy and top-margin
- unordered window-cooccurrence baseline
- TF-IDF-like unordered context-vector baseline
- comparative benchmark for signed positional context vs stronger non-neural context statistics
- unit tests and retrieval benchmarks

SQLite persistence deliberately stores both the original payload and the resolutive node graph at this research stage. This makes round-trip validation explicit while the project measures when hierarchical storage becomes advantageous.

The v0.2 association experiment is structural, not semantic. The v0.3 extension adds order and temporal-spacing sensitivity so that two memories containing the same nodes in different sequences are no longer treated as equivalent.

The v0.4 extension adds **contextual association**. Nodes are not declared synonymous or equivalent. Instead, each node accumulates a sparse profile of neighboring nodes and their signed relative positions. Similarity is computed from these observed trajectory contexts with inverse-frequency weighting so ubiquitous context contributes less.

The v0.5 extension evaluates that mechanism across several domains at once, v0.6 adds adversarial distractors, v0.7 introduces direct natural-language observation and ambiguity measurement, and v0.8 adds the first direct comparison against unordered cooccurrence.

The v0.9 extension adds a **TF-IDF-like contextual baseline** that keeps weighted neighboring-token profiles but deliberately discards signed relative position. In the current controlled Portuguese benchmark, both the resolutive model and the TF-IDF contextual baseline recover 8/8 hidden-pair directional queries at top-1. The distinction appears in robustness against distractors: the mean expected-partner margin is approximately 0.61 for the resolutive model versus 0.33 for the TF-IDF contextual baseline, with minimum margins of approximately 0.39 and 0.21 respectively. This is stronger controlled evidence that positional trajectory information contributes useful signal, but it is not an external benchmark and does not establish superiority over modern NLP models.

## Install and test

```bash
python -m pip install -e .
python -m pytest -q
python benchmarks/benchmark_retrieval.py
python experiments/ordered_trajectory_v03.py
python experiments/emergent_context_v04.py
python experiments/multidomain_v05.py
python experiments/generalization_v06.py
python experiments/natural_language_v07.py
python experiments/comparative_v08.py
python experiments/comparative_v09.py
```

## Research status

This is an experimental research project. The current implementation tests memory structure, persistence, retrieval, ordered trajectories, contextual association, adversarial generalization, small-corpus natural-language behavior and comparative non-neural baselines. It does **not** yet claim unrestricted semantic understanding, general intelligence, or replacement of neural networks.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
