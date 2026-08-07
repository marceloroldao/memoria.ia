# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.28 scope

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
- rule-based semantic/event fingerprints using canonical concepts, action concepts and numeric anchors
- emergent contextual ontology clustering without a manual synonym map

v0.19 established that the exponential temporal detector alone is closely related to a matched EWMA. v0.20 moved the comparison to the complete online-memory workflow. v0.21 added append-only factual timelines. v0.22 added contradiction/provenance handling with explicit abstention. v0.23 introduced source reliability learned online from later confirmed or contradicted historical claims. v0.24 added independence-aware evidence resolution when origin families are known. v0.25 added basic automatic dependency inference. v0.26 exposed the failure surface under adversarial paraphrase and missing provenance cues. v0.27 added a hand-authored semantic-structural fingerprint baseline.

v0.28 adds an **emergent ontology mechanism test**. Terms are grouped only from contextual similarity learned by `TextContextMemory`; no synonym dictionary is supplied to the clustering step. In the controlled corpus, `tarifa`, `cobranca` and `encargo` repeatedly occur in equivalent structural contexts and form one latent cluster, while `estrela` and `astro` form another. Cluster purity is measured against labels used only for evaluation, not for training.

The online test also introduces a previously unseen term, `taxa`. Before contextual observations it remains isolated. After receiving new sentences that place `taxa` in the same contexts as the existing fee terms, the term joins the `tarifa/cobranca/encargo` cluster without editing a dictionary or retraining from scratch. This demonstrates the intended mechanism that ontology membership can emerge and update incrementally from memory formation.

This remains a controlled distributional test. Contextual similarity can merge antonyms, topical neighbors or polysemous terms that share contexts, and the current threshold-based connected-component clustering can suffer chaining effects. Therefore v0.28 does not establish autonomous semantic understanding or a general ontology learner.

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
python experiments/semantic_fingerprint_v27.py
python experiments/emergent_ontology_v28.py
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

This is an experimental research project. The current evidence supports exact reconstruction, multiscale structural memory, sparse contextual association, controlled online incorporation, temporal epoch preservation, episodic relation tracking, factual timelines, provenance-aware conflict representation, learned source reliability, resistance to duplicate-origin evidence, basic automatic dependency inference, and controlled emergent contextual clustering. It does **not** yet establish unrestricted semantic understanding, general intelligence, factual truth assessment, reliable open-world source-independence discovery, absence of forgetting at scale, constant-time retrieval, or superiority over modern NLP/embedding models.

v0.28 shows that small latent term groups can emerge and accept new members online from repeated contexts without a manual synonym map. The next decisive test should evaluate concept splitting and polysemy: one word used in two meanings must be able to belong to distinct context-conditioned concepts instead of forcing one global cluster.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
