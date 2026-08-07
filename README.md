# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.6 scope

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
- noise-injection experiments
- adversarial distractors with partially overlapping context
- association-margin evaluation
- held-apart evaluation logic for expected partner vs distractor
- unit tests and retrieval benchmarks

SQLite persistence deliberately stores both the original payload and the resolutive node graph at this research stage. This makes round-trip validation explicit while the project measures when hierarchical storage becomes advantageous.

The v0.2 association experiment is structural, not semantic. The v0.3 extension adds order and temporal-spacing sensitivity so that two memories containing the same nodes in different sequences are no longer treated as equivalent.

The v0.4 extension adds **contextual association**. Nodes are not declared synonymous or equivalent. Instead, each node accumulates a sparse profile of neighboring nodes and their signed relative positions. Similarity is computed from these observed trajectory contexts with inverse-frequency weighting so ubiquitous context contributes less.

The v0.5 extension evaluates that mechanism across several domains at once. Controlled hidden pairs such as `carro/automovel`, `guardar/armazenar`, `fibra/enlace` and `estrela/astro` are exposed through repeated contexts while unrelated noise trajectories are injected.

The v0.6 extension adds **adversarial generalization tests**. Distractors such as `veiculo`, `salvar`, `cabo` and `planeta` intentionally share part of the expected context. Evaluation now measures not only top-1 accuracy but also the score margin between the expected hidden partner and the strongest declared distractor.

In the current controlled adversarial corpus, the expected hidden partner remains top-1 for all 8 directional queries with 1000 injected noise trajectories. The experiment is intentionally synthetic and should be interpreted as mechanism validation, not unrestricted semantic understanding.

## Install and test

```bash
python -m pip install -e .
python -m pytest -q
python benchmarks/benchmark_retrieval.py
python experiments/ordered_trajectory_v03.py
python experiments/emergent_context_v04.py
python experiments/multidomain_v05.py
python experiments/generalization_v06.py
```

## Research status

This is an experimental research project. The current implementation tests memory structure, persistence, retrieval, ordered trajectories, contextual association and adversarial generalization. It does **not** yet claim semantic understanding, general intelligence, or replacement of neural networks.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
