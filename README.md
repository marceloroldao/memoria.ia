# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.18 scope

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

v0.17 established stochastic drift evaluation across many random seeds. The reference 1,000-seed protocol with 100 observations per epoch and decay `0.9` produced exact first-majority detection in `994/1000` runs, eventual detection `1.000`, mean delay about `0.006` epoch and no pre-transition false alarms in that specific synthetic protocol.

v0.18 adds a **stability map** instead of assuming one universal temporal parameter. The default grid spans three drift profiles (slow/medium/fast), sample sizes `10/30/100`, decay values `0.3/0.9/1.5`, and ambiguity/noise values `0/0.1/0.25`. For each operating point the experiment records eventual detection, exact-epoch detection, mean and standard deviation of delay, and false-alarm rate.

The sweep exposes a real trade-off: low decay preserves a longer temporal history and is conservative but can lag a changing stream; high decay reacts faster but becomes more sensitive to stochastic fluctuations, especially with small samples and added ambiguity. Therefore decay should be treated as an operating-regime parameter rather than a fixed universal constant.

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

The next decisive stage is to repeat the stability analysis on independent natural-language streams and compare temporal adaptation against standard online change-detection or incremental-learning baselines.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
