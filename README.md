# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.29 scope

The current prototype includes the previous online, temporal, provenance and emergent-ontology experiments and now adds **context-conditioned concept splitting for polysemous words**.

v0.29 introduces `PolysemyMemory`. A surface token is no longer forced to own one global semantic state. Each occurrence produces a local context trajectory. The occurrence is attached to the closest existing sense when contextual overlap is sufficient; otherwise a new sense node is created online. No neural model and no global replay/retraining step are required.

The controlled experiment uses the Portuguese word `banco` in two regimes: finance (`credito`, `emprestimo`, `cliente`, `conta`, `juros`) and data/storage (`dados`, `registros`, `servidor`, `tabelas`, `consulta`). The expected behavior is that repeated observations create at least two context-conditioned sense nodes and that finance/data queries resolve to different sense IDs.

A second regression test starts with only the financial meaning and later streams database-related sentences. The new sense must appear after the new evidence without replaying the earlier financial sentences. This preserves the project's central online-learning constraint: concept structure may expand as memory is formed.

This remains a controlled mechanism test. The current splitter uses sparse local context and Jaccard overlap with a threshold. It can over-split rare words, under-split closely related senses, and is sensitive to window size and threshold. It does not establish general word-sense disambiguation. The next rigorous stage should measure sense purity, over-splitting/under-splitting and stability across shuffled streams, then compare against simple clustering and embedding baselines.

## Install and test

```bash
python -m pip install -e .
python -m pytest -q
```

Key recent experiments:

```bash
python experiments/adversarial_dependency_v26.py
python experiments/semantic_fingerprint_v27.py
python experiments/emergent_ontology_v28.py
python experiments/polysemy_v29.py
```

Optional Word2Vec baseline:

```bash
python -m pip install -e '.[word2vec]'
```

Third-party datasets remain outside this repository. Earlier experiments remain available under `experiments/`.

## Research status

This is an experimental research project. Current controlled evidence supports exact reconstruction, multiscale structural memory, sparse contextual association, online incorporation, temporal/episodic tracking, provenance-aware conflict representation, learned source reliability, duplicate-origin resistance, basic dependency inference, emergent contextual clustering, and now context-conditioned splitting of one surface word into multiple sense nodes. It does **not** establish unrestricted semantic understanding, general intelligence, general word-sense disambiguation, factual truth assessment, absence of forgetting at scale, constant-time retrieval, or superiority over modern NLP/embedding models.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
