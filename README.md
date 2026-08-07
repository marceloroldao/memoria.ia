# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.30 scope

The current prototype includes the previous online, temporal, provenance, emergent-ontology and polysemy experiments and now adds **order-stability evaluation for context-conditioned sense splitting**.

v0.29 introduced `PolysemyMemory`, allowing one surface token to own multiple context-conditioned sense nodes without neural training or global replay. v0.30 tests whether those sense distinctions survive different observation orders.

The controlled `banco` corpus is presented in four regimes: finance-first, data-first, alternating, and many shuffled streams. The evaluator records (1) whether finance and database queries resolve to different senses and (2) how many sense nodes are created.

Internal simulation of the reference corpus found a useful mixed result: finance-vs-data separation remained stable across the tested shuffled orders, but the current local-Jaccard splitter typically created about 6-7 sense nodes rather than the intended two broad senses. Therefore the main v0.30 finding is **successful domain separation with substantial over-splitting**. This is intentionally recorded as a failure surface rather than hidden behind a tuned test.

The next algorithmic problem is sense consolidation: merge nearby micro-senses after enough evidence accumulates while preserving truly distinct meanings. A future version should reduce the number of `banco` senses toward two without losing order robustness or requiring replay of the full history.

## Install and test

```bash
python -m pip install -e .
python -m pytest -q
```

Key recent experiments:

```bash
python experiments/semantic_fingerprint_v27.py
python experiments/emergent_ontology_v28.py
python experiments/polysemy_v29.py
python experiments/polysemy_stability_v30.py
```

Third-party datasets remain outside this repository. Earlier experiments remain available under `experiments/`.

## Research status

This is an experimental research project. Current controlled evidence supports exact reconstruction, multiscale structural memory, sparse contextual association, online incorporation, temporal/episodic tracking, provenance-aware conflict representation, learned source reliability, emergent contextual clustering, and context-conditioned sense splitting. v0.30 specifically shows that the current splitter can preserve broad polysemous separation under order changes while still over-fragmenting each broad sense. It does **not** establish general word-sense disambiguation or semantic understanding.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
