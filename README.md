# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.13 scope

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

v0.12 established the explicit online-learning protocol: new observations are appended to the existing memory, previous batches are not replayed, and immediate acquisition plus retention are measured after each update.

v0.13 extends that protocol to a longer heterogeneous stream and fixes a scalability bottleneck discovered during stress testing. Earlier versions rebuilt contextual feature document frequencies during every similarity calculation. v0.13 maintains those frequencies incrementally at observation time, so retrieval no longer rescans the complete contextual feature space merely to rebuild global weights.

The controlled v0.13 experiment uses 60 sequential batches (about 2,100 sentences with the default configuration), 30 hidden relation pairs, unrelated noise, repeated revisits and plausible rival tokens injected late in the stream. In the prototype simulation, immediate acquisition and checkpoint retention remained 1.00 through the final checkpoint. Mean batch-update latency did not grow across the run. These values are evidence only for this synthetic controlled stream; they do not establish absence of forgetting or constant-time behavior at unrestricted scale.

The new `footprint()` metric reports sparse node count, contextual feature count, document-frequency index size and total observations so model growth can be compared with accuracy and latency.

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

This is an experimental research project. The current evidence supports exact reconstruction, multiscale structural memory, sparse contextual association, controlled online incorporation and promising controlled comparisons. It does **not** yet establish unrestricted semantic understanding, general intelligence, absence of forgetting at scale, constant-time retrieval, or superiority over modern NLP/embedding models.

The next decisive stage is a substantially larger stream with independent natural-language data, explicit concept drift and contradictory evidence, while comparing retention, immediate-learning accuracy, update latency, query latency, memory growth and baseline retraining/incremental costs.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
