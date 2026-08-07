# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.22 scope

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

v0.19 established that the exponential temporal detector alone is closely related to a matched EWMA. v0.20 moved the comparison to the complete online-memory workflow. v0.21 added append-only factual timelines: later facts can supersede the current state without deleting earlier states, enabling direct queries such as “what is true now?”, “what was recorded at epoch t?” and “when was value X superseded?”.

v0.22 adds **contradiction and provenance handling**. Multiple sources may assert different values for the same subject/relation at the same epoch. Evidence is preserved per source instead of being collapsed or overwritten. Resolution is weighted and includes an explicit abstention rule: if the leading value is not separated from the strongest rival by the configured decision margin, the memory returns `conflict=True` and `winner=None` rather than manufacturing certainty.

In the controlled mechanism test, equal-weight evidence (`Carlos` from source A versus `Ana` from source B, 1.0 vs 1.0) produces a conflict with no winner and confidence 0.50. A 3.0 vs 1.0 evidence split resolves to the stronger value with confidence 0.75 while preserving the weaker source in provenance. A later unambiguous epoch can become the current state while the earlier conflicting epoch remains independently queryable.

Source weights are currently experimental inputs, not objective truth scores. Future work must derive or calibrate source reliability from reproducible evidence rather than manually assigning trust.

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

This is an experimental research project. The current evidence supports exact reconstruction, multiscale structural memory, sparse contextual association, controlled online incorporation, temporal epoch preservation, episodic relation tracking, factual timelines and provenance-aware conflict representation on controlled tests. It does **not** yet establish unrestricted semantic understanding, general intelligence, factual truth assessment, absence of forgetting at scale, constant-time retrieval, or superiority over modern NLP/embedding models.

The next decisive stage is to replace manually supplied evidence weights with a learned/calibrated reliability mechanism based on source history: sources gain or lose reliability only when later independently verified outcomes confirm or contradict their past assertions. That would let the system distinguish “source disagreement” from “evidence-weighted confidence” without hard-coding authority.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
