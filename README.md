# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.12 scope

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
- immediate post-update retrieval measurement
- retention measurement for previously learned relations
- per-batch update-time measurement

v0.11 established the external evaluation protocol and corrected coverage semantics.

v0.12 adds an explicit **online learning protocol**. New observations are appended directly to the existing sparse contextual memory. Prior batches are not replayed or globally retrained. After each incoming batch the evaluator measures (1) whether the newly introduced relation is immediately available at top-1, (2) whether previously learned relations remain top-1, and (3) the incremental update cost.

In the current controlled four-stage experiment, each new relation becomes immediately retrievable after its batch is observed, while previously learned pairs remain top-1 throughout. The prototype therefore demonstrates the intended incremental behavior in a small controlled setting. This is not yet evidence that retention will remain perfect at large scale; v0.12 exists to make that claim measurable rather than assumed.

## Install and test

```bash
python -m pip install -e .
python -m pytest -q
```

Online-learning experiment:

```bash
python experiments/online_learning_v12.py
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

This is an experimental research project. The current evidence supports exact reconstruction, multiscale structural memory, sparse contextual association, controlled online incorporation and promising controlled comparisons. It does **not** yet establish unrestricted semantic understanding, general intelligence, absence of forgetting at scale, or superiority over modern NLP/embedding models.

The next decisive stage is a large sequential stream with thousands of batches, measuring retention curves, immediate-learning accuracy, update latency, memory growth and comparison with incremental/retrained baselines.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
