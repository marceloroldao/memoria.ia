# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.16 scope

The current prototype implements:

- unique content nodes separated from temporal occurrences
- exact byte reconstruction and multiscale deduplication
- structural retrieval using rare-node attractors
- SQLite persistence
- ordered trajectory and sparse contextual association
- natural-language tokenization and ambiguity probing
- TF-IDF-like and optional Word2Vec baselines
- external similarity evaluation with coverage and Spearman correlation
- online/incremental learning without replaying prior batches
- retention, update latency and sparse-memory growth measurements
- incrementally maintained contextual feature statistics
- explicit temporal epochs and recency-weighted current-state queries
- direct episodic relation memory separated from contextual similarity
- episodic timeline reconstruction and dominant-association change detection
- gradual concept-drift evaluation with detection delay and false alarms

v0.12 established online learning. v0.13 stress-tested longer streams and moved contextual document-frequency maintenance to observation time. v0.14 introduced temporal epochs. v0.15 separated contextual similarity from direct episodic relations and added historical timeline reconstruction.

v0.16 adds **gradual concept drift**. A controlled sequence changes evidence from an old relation to a new one using fractions `0%, 10%, 30%, 50%, 70%, 90%, 100%` for the new relation. Ground-truth change is defined as the first epoch where the new relation is a strict local majority. Detection is the first epoch where the recency-weighted current relation score of the new partner exceeds the old one.

For the default deterministic test with decay `0.9`, the expected transition occurs at epoch 4 (30/70 old/new) and the detector also switches at epoch 4, yielding detection delay `0` and `0` false alarms. A control stream that never crosses 50% produces no detected change. These are synthetic mechanism tests, not evidence of unrestricted temporal reasoning or factual truth assessment.

## Install and test

```bash
python -m pip install -e .
python -m pytest -q
```

Key experiments:

```bash
python experiments/online_learning_v12.py
python experiments/streaming_v13.py
python experiments/temporal_drift_v14.py
python experiments/episodic_timeline_v15.py
python experiments/gradual_drift_v16.py
```

Optional Word2Vec baseline:

```bash
python -m pip install -e '.[word2vec]'
```

External benchmark example:

```bash
python experiments/external_v11.py \
  --corpus /path/to/portuguese_corpus.txt \
  --benchmark /path/to/LX-SimLex-999.txt \
  --word1-col 0 --word2-col 1 --score-col 3 --skip-header
```

Third-party datasets remain outside this repository. Earlier experiments remain available under `experiments/`.

## Research status

This is an experimental research project. The current evidence supports exact reconstruction, multiscale structural memory, sparse contextual association, controlled online incorporation, temporal epoch preservation, episodic relation tracking and gradual-change detection on synthetic streams. It does **not** yet establish unrestricted semantic understanding, general intelligence, absence of forgetting at scale, constant-time retrieval, factual truth assessment, or superiority over modern NLP/embedding models.

The next decisive stage is noisy stochastic gradual drift across many random seeds and independent natural-language streams, measuring mean detection delay, false-alarm rate, historical fidelity, current-state accuracy, latency and memory growth.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
