# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.24 scope

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
- append-only factual timelines with historical and current queries
- provenance-aware conflicting evidence with explicit abstention
- online source-reliability learning from confirmed/contradicted historical claims
- evidence-family clustering that prevents copied sources from multiplying support

v0.19 established that the exponential temporal detector alone is closely related to a matched EWMA. v0.20 moved the comparison to the complete online-memory workflow. v0.21 added append-only factual timelines. v0.22 added contradiction/provenance handling with explicit abstention. v0.23 introduced source reliability learned online from later confirmed or contradicted historical claims using a Beta prior and conservative Wilson diagnostics.

v0.24 adds **independence-aware evidence resolution**. Raw source count is no longer treated as independent support. Every evidence item carries a source and an `origin` family. Multiple sites, agents or messages that derive from the same origin are collapsed into one evidence family for a claim; within one origin/value pair, only the strongest supplied weight contributes. This blocks a simple echo-chamber failure mode where many copies of one report manufacture a majority.

In the controlled echo test, 10 sources repeat value `X` but all share one origin, while two genuinely independent origins support value `Y`. The resolver therefore counts one independent origin for `X` and two for `Y`, so `Y` wins despite the 10-to-2 raw source count. A 2-vs-2 independent split triggers abstention when the normalized margin is below threshold. These are controlled mechanism tests, not a general solution for discovering causal/source independence in open-world data.

The difficult unresolved problem is **origin inference** itself. v0.24 assumes origin labels are known or supplied by upstream provenance analysis. Future work must infer likely copying/dependence from URLs, timestamps, citations, content similarity and source graphs rather than trusting declared origin metadata.

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
python experiments/factual_timeline_v21.py
python experiments/conflict_provenance_v22.py
python experiments/source_reliability_v23.py
python experiments/evidence_independence_v24.py
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

This is an experimental research project. The current evidence supports exact reconstruction, multiscale structural memory, sparse contextual association, controlled online incorporation, temporal epoch preservation, episodic relation tracking, factual timelines, provenance-aware conflict representation, learned source reliability and resistance to duplicate-origin evidence on controlled tests. It does **not** yet establish unrestricted semantic understanding, general intelligence, factual truth assessment, automatic discovery of independent sources, absence of forgetting at scale, constant-time retrieval, or superiority over modern NLP/embedding models.

The next decisive stage is to infer evidence dependence automatically and test coordinated misinformation / copying graphs where sources hide their common origin. That should be benchmarked against raw-majority, reliability-weighted and independence-aware resolution on the same synthetic and external provenance datasets.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
