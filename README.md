# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.20 scope

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
- deterministic and stochastic gradual concept-drift evaluation
- stability-map sweep over sample size, temporal decay, drift speed and noise
- matched EWMA and CUSUM online change-detection baselines
- end-to-end online comparison against incremental cooccurrence and rebuilt TF-IDF-like context retrieval

v0.19 established that the exponential temporal detector alone is closely related to a matched EWMA. The contribution therefore cannot be claimed to lie in the exponential change filter itself.

v0.20 moves the comparison to the **complete online-memory workflow**. Resolutive Memory and a simple cooccurrence baseline receive only each incoming batch and update their existing sparse state. A TF-IDF-like contextual baseline is rebuilt from the full accumulated history after every batch, representing a retraining/reindexing workflow. After every update the benchmark measures immediate retrieval of the newly introduced relation, retention of older relations, update/rebuild latency and sparse structural growth.

In the current small controlled corpus, all three approaches preserve the tested relations, so this experiment does not establish a quality advantage for Resolutive Memory. The architectural distinction is update semantics: Resolutive Memory and incremental cooccurrence incorporate only new observations, while the rebuilt TF-IDF-like baseline reprocesses the accumulated history. Timing ratios are environment-specific and are intentionally not treated as universal performance claims.

The important unresolved comparison is therefore whether richer ordered/episodic structure provides a useful quality, provenance or historical-query advantage over simpler incremental indexes at comparable update and memory cost.

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
python experiments/stochastic_drift_v17.py
python experiments/stability_map_v18.py
python experiments/drift_baselines_v19.py
python experiments/end_to_end_v20.py
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

This is an experimental research project. The current evidence supports exact reconstruction, multiscale structural memory, sparse contextual association, controlled online incorporation, temporal epoch preservation, episodic relation tracking and statistically characterized synthetic change detection. It does **not** yet establish unrestricted semantic understanding, general intelligence, absence of forgetting at scale, constant-time retrieval, factual truth assessment, or superiority over modern NLP/embedding models.

v0.20 establishes an end-to-end protocol for comparing immediate online incorporation, retention and structural growth. The next decisive stage should use a much longer independent natural-language stream with conflicting updates and historical questions, then compare (1) accuracy after each update, (2) provenance/historical fidelity, (3) update and query latency, and (4) measured serialized memory size rather than only sparse structural counts.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
