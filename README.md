# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.15 scope

The current prototype implements:

- unique content nodes separated from temporal occurrences
- exact byte reconstruction
- multiscale deduplication
- structural retrieval using rare-node attractors
- SQLite persistence
- ordered trajectory similarity and temporal-delta consistency
- sparse contextual association from repeated trajectory neighborhoods
- natural-language tokenization and ambiguity probing
- unordered cooccurrence and TF-IDF-like context baselines
- optional Word2Vec baseline through `gensim`
- multi-seed Word2Vec stability evaluation
- external corpus and human-rated similarity benchmark loaders
- explicit vocabulary coverage separated from zero semantic similarity
- Spearman rank correlation on covered benchmark pairs
- online/incremental observation without replaying prior batches
- immediate post-update retrieval and retention measurement
- streaming-scale evaluator with heterogeneous noise and adversarial rivals
- per-batch update latency and sparse-memory growth metrics
- incrementally maintained contextual feature document frequencies
- explicit temporal epochs for concept drift and contradictory evidence
- recency-weighted current-state queries without deleting historical state
- historical epoch queries and change-score measurement
- episodic timeline reconstruction
- automatic dominant-association change detection

v0.12 established the explicit online-learning protocol. v0.13 extended it to a longer stream and moved contextual document-frequency maintenance to observation time. v0.14 introduced temporal epochs so current evidence can change without deleting historical associations.

v0.15 adds **episodic temporal memory**. For a query token, the system can now reconstruct the dominant association independently at every stored epoch, report the current recency-weighted dominant association, and detect epochs where the historical dominant partner changed.

The controlled episodic experiment uses the sequence `ponte → tunel → ponte → balsa → balsa → tunel`. The expected change epochs are `[0, 1, 2, 3, 5]`: epoch 4 is correctly not flagged because the dominant association remains `balsa`. This tests return to a previously seen state, persistence without change, and a later transition. Historical epoch queries remain independent from the recency-weighted current query.

This remains a synthetic mechanism test. It demonstrates temporal bookkeeping and change detection, not unrestricted temporal reasoning or factual truth assessment.

## Install and test

```bash
python -m pip install -e .
python -m pytest -q
```

Online-learning experiment:

```bash
python experiments/online_learning_v12.py
```

Streaming-scale experiment:

```bash
python experiments/streaming_v13.py
```

Temporal concept-drift experiment:

```bash
python experiments/temporal_drift_v14.py
```

Episodic temporal experiment:

```bash
python experiments/episodic_timeline_v15.py
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

This is an experimental research project. The current evidence supports exact reconstruction, multiscale structural memory, sparse contextual association, controlled online incorporation, temporal epoch preservation and episodic change tracking. It does **not** yet establish unrestricted semantic understanding, general intelligence, absence of forgetting at scale, constant-time retrieval, factual truth assessment, or superiority over modern NLP/embedding models.

The next decisive stage is temporal learning on independent natural-language streams with noisy gradual changes, measuring detection delay, false change alarms, historical fidelity, current-state accuracy, latency and memory growth.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
