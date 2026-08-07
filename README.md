# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.19 scope

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

v0.17 established stochastic drift evaluation across many random seeds. The reference 1,000-seed protocol with 100 observations per epoch and decay `0.9` produced exact first-majority detection in `994/1000` runs, eventual detection `1.000`, mean delay about `0.006` epoch and no pre-transition false alarms in that specific synthetic protocol.

v0.18 added a stability map over drift profile, sample size, temporal decay and ambiguity/noise. It exposed the expected adaptation-versus-stability trade-off: longer temporal memory is conservative but can lag; shorter temporal memory responds faster but becomes more sensitive to stochastic fluctuations.

v0.19 adds **classical online change-detection baselines**. The recency-weighted Resolutive detector is compared on exactly the same sampled streams against a matched EWMA and a one-sided CUSUM. When EWMA uses `alpha = 1 - exp(-decay)`, its behavior is expected to be very close to the normalized exponential temporal detector. This is an important negative/clarifying result: the exponential change detector by itself should not be presented as a novel contribution. The research question therefore shifts to whether the surrounding architecture — persistent episodic history, direct relation memory, sparse contextual association, multiscale reconstruction and immediate online incorporation — provides measurable advantages beyond the classical filter.

In the reference stochastic protocol with 100 observations per epoch, the matched EWMA and Resolutive exponential detector are nearly coincident in exact detection and delay. The configured CUSUM is substantially more conservative: it can reduce early alarms but typically detects later. These comparisons are protocol- and parameter-specific rather than universal rankings.

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

v0.19 specifically establishes that the current exponential temporal detector is closely related to standard EWMA behavior. The next decisive comparison should therefore evaluate the complete Resolutive Memory system — not only its temporal filter — against standard continual-learning / retrieval systems on independent natural-language streams, including memory growth, update cost, historical query fidelity and immediate-use latency.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
