# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.14 scope

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

v0.12 established the explicit online-learning protocol: new observations are appended to the existing memory, previous batches are not replayed, and immediate acquisition plus retention are measured after each update.

v0.13 extends that protocol to a longer heterogeneous stream and fixes a scalability bottleneck discovered during stress testing. Contextual feature document frequencies are maintained incrementally at observation time, so retrieval no longer rescans the complete contextual feature space merely to rebuild global weights.

v0.14 introduces **temporal concept drift**. Instead of collapsing all evidence into a single timeless contextual profile, observations can be grouped into explicit epochs. Historical epochs remain queryable, while current-state similarity combines epoch-local evidence using exponential recency weighting. This allows the system to represent both "what was associated before" and "what is favored now" without deleting the old trajectory.

In the controlled temporal-drift experiment, `rota` is first associated with `ponte`, then later with `tunel`. The old epoch retains `rota↔ponte` similarity near 1.00. After the transition epoch, the recency-weighted current scores are approximately 0.29 for `ponte` and 0.71 for `tunel`; after the latest epoch they are approximately 0.11 and 0.89 respectively. The historical old-epoch score remains near 1.00. This demonstrates the intended mechanism on a synthetic corpus only; it does not establish temporal reasoning in unrestricted language.

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

This is an experimental research project. The current evidence supports exact reconstruction, multiscale structural memory, sparse contextual association, controlled online incorporation, temporal epoch preservation and promising controlled comparisons. It does **not** yet establish unrestricted semantic understanding, general intelligence, absence of forgetting at scale, constant-time retrieval, or superiority over modern NLP/embedding models.

The next decisive stage is temporal learning on independent natural-language streams with multiple repeated concept changes, measuring detection delay, false change alarms, historical fidelity, current-state accuracy, latency and memory growth.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
