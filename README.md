# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.17 scope

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
- stochastic gradual-drift evaluation across many random seeds
- probability of exact change-epoch detection, eventual detection, delay dispersion and false-alarm rate

v0.12 established online learning. v0.13 stress-tested longer streams and moved contextual document-frequency maintenance to observation time. v0.14 introduced temporal epochs. v0.15 separated contextual similarity from direct episodic relations and added historical timeline reconstruction. v0.16 added deterministic gradual drift.

v0.17 adds **stochastic gradual drift**. The nominal sequence uses new-relation probabilities `0%, 10%, 30%, 50%, 70%, 90%, 100%`, but each epoch is sampled independently rather than receiving exact counts. The reference protocol runs 1,000 deterministic random seeds with 100 observations per epoch and recency decay `0.9`.

For that reference protocol, the detector switches on the expected first-majority epoch in `994/1000` runs (`0.994` probability). The remaining 6 runs switch one epoch later. Eventual detection is `1.000`, mean detection delay is approximately `0.006` epoch, delay standard deviation is approximately `0.077`, and the observed false-alarm rate before the defined ground-truth transition is `0.000` in this simulation. These numbers are properties of this synthetic protocol only; they are not universal accuracy claims.

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

This is an experimental research project. The current evidence supports exact reconstruction, multiscale structural memory, sparse contextual association, controlled online incorporation, temporal epoch preservation, episodic relation tracking and robust change detection on the current synthetic stochastic protocol. It does **not** yet establish unrestricted semantic understanding, general intelligence, absence of forgetting at scale, constant-time retrieval, factual truth assessment, or superiority over modern NLP/embedding models.

The next decisive stage is to vary sample size, decay, drift speed and noise strength systematically, then repeat the same temporal protocol on independent natural-language streams and compare against standard online change-detection baselines.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
