# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.25 scope

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

v0.19 established that the exponential temporal detector alone is closely related to a matched EWMA. v0.20 moved the comparison to the complete online-memory workflow. v0.21 added append-only factual timelines. v0.22 added contradiction/provenance handling with explicit abstention. v0.23 introduced source reliability learned online from later confirmed or contradicted historical claims. v0.24 added independence-aware evidence resolution when origin families are known.

v0.25 adds **automatic dependency inference**. Source documents are compared only against earlier documents. A probable dependency score combines lexical Jaccard overlap, exponential temporal proximity and explicit citation signals. Links above threshold form a directed dependency graph, and dependency chains are collapsed to their earliest reachable origin. This lets the evidence resolver estimate origin families when provenance labels are not directly supplied.

The controlled attack contains one false origin followed by 10 near-identical or explicitly citing copies, versus three independently worded documents supporting the rival value. The inferred graph collapses the false echo into one probable origin while preserving the three independent documents as separate roots. Thus an upstream raw 11-to-3 source count can be transformed into an estimated 1-to-3 origin count before evidence resolution.

This is a mechanism test only. Jaccard overlap, publication timing and citations are insufficient to establish true causal dependence in unrestricted data. Paraphrases can evade lexical detection, unrelated sources can independently use similar wording, timestamps can be missing or manipulated, and citation graphs can be incomplete. The dependency score must therefore be treated as probabilistic provenance evidence, not ground truth.

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

The next decisive stage is adversarial dependency inference: paraphrased copies, delayed reposts, missing citations and coordinated source networks, compared against raw-majority and provenance-aware resolution. Precision/recall of dependency-edge inference should be measured separately from final claim-resolution accuracy.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
