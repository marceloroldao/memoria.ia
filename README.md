# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.26 scope

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
- inferred source-dependency links using content overlap, temporal proximity and explicit citations
- adversarial dependency evaluation with precision, recall, false-positive and false-negative edge metrics

v0.19 established that the exponential temporal detector alone is closely related to a matched EWMA. v0.20 moved the comparison to the complete online-memory workflow. v0.21 added append-only factual timelines. v0.22 added contradiction/provenance handling with explicit abstention. v0.23 introduced source reliability learned online from later confirmed or contradicted historical claims. v0.24 added independence-aware evidence resolution when origin families are known. v0.25 added basic automatic dependency inference.

v0.26 adds **adversarial dependency evaluation**. The dependency detector is now tested on strong paraphrases, delayed reposts, missing citations and independently worded rival evidence. Evaluation separates provenance reconstruction from final fact resolution by reporting dependency-edge precision, recall, false positives and false negatives.

The controlled adversarial corpus contains a false origin, an easy lexical copy, stronger paraphrases with increasing publication delay, and multiple independently worded documents supporting the rival claim. Threshold sweeps expose the expected precision/recall trade-off: relaxed thresholds recover more copied/paraphrased items but risk linking independent documents, while strict thresholds reduce false links but miss heavily rewritten copies. This is intentionally treated as a failure-surface measurement rather than a claim of solved source attribution.

A central conclusion of v0.26 is that lexical overlap plus time and citations is not enough for robust open-world provenance. Strong paraphrase can reduce recall substantially. Future provenance inference should add semantic similarity, named-entity/event fingerprints, URL/domain relationships and graph-level consistency, and should be evaluated on external datasets with known source relationships.

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
python experiments/dependency_inference_v25.py
python experiments/adversarial_dependency_v26.py
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

This is an experimental research project. The current evidence supports exact reconstruction, multiscale structural memory, sparse contextual association, controlled online incorporation, temporal epoch preservation, episodic relation tracking, factual timelines, provenance-aware conflict representation, learned source reliability, resistance to duplicate-origin evidence, and basic automatic dependency inference on controlled tests. It does **not** yet establish unrestricted semantic understanding, general intelligence, factual truth assessment, reliable open-world source-independence discovery, absence of forgetting at scale, constant-time retrieval, or superiority over modern NLP/embedding models.

v0.26 makes the current provenance limitation measurable. The next decisive stage is to improve paraphrase robustness and then compare raw-majority, reliability-weighted and independence-aware claim resolution on large randomized source graphs, ideally followed by external provenance datasets.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
