# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.11 scope

The current prototype implements:

- unique content nodes separated from temporal occurrences
- exact byte reconstruction
- multiscale deduplication
- structural retrieval using rare-node attractors
- SQLite persistence
- ordered trajectory similarity and temporal-delta consistency
- sparse contextual association from repeated trajectory neighborhoods
- natural-language tokenization and ambiguity probing
- unordered cooccurrence and TF-IDF-like context baselines
- optional Word2Vec baseline through `gensim`
- multi-seed Word2Vec stability evaluation
- external corpus loader with third-party data kept outside the repository
- generic human-rated word-similarity loader
- explicit vocabulary coverage separated from zero semantic similarity
- Spearman rank correlation on covered benchmark pairs
- reproducible external benchmark CLI for Resolutive / TF-IDF / Word2Vec
- regression tests for ranking and coverage semantics

The v0.9 controlled benchmark showed equal 8/8 top-1 accuracy for the resolutive and TF-IDF-like context models, with larger partner-vs-distractor margins for the signed positional model.

v0.10 added Word2Vec and showed that the deliberately tiny controlled corpus is too small for a stable embedding comparison: five deterministic Word2Vec seeds ranged from 3/8 to 7/8 top-1 and all produced at least one negative partner-vs-distractor margin. This is treated as a benchmark-design warning, not as evidence of superiority.

v0.11 moves the project to a reproducible **external evaluation protocol**. Third-party corpora and benchmarks are not copied into this repository. A UTF-8 corpus can be supplied at runtime, all models are trained on the same input, and a human-rated Portuguese word-similarity file is evaluated by vocabulary coverage and Spearman correlation. Coverage is now explicit: an in-vocabulary pair with model similarity `0.0` is no longer incorrectly counted as out-of-vocabulary.

Portuguese benchmark candidates include LX-SimLex-999 and LX-WordSim-353 from LX-DSemVectors. An independently sourced training corpus candidate is TTS-Portuguese Corpus (CC BY 4.0), which reports 71,358 words and 13,311 distinct words. The training corpus and human-rated evaluation pairs must remain logically separated.

## Install and test

```bash
python -m pip install -e .
python -m pytest -q
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

Column indices depend on the source benchmark format; inspect the upstream file before running. Earlier experiments remain available under `experiments/`.

## Research status

This is an experimental research project. The current evidence supports exact reconstruction, multiscale structural memory, sparse contextual association and promising controlled comparisons. It does **not** yet establish unrestricted semantic understanding, general intelligence, or superiority over modern NLP/embedding models. The decisive next stage is an actual large-corpus run with standard Portuguese human-rated benchmarks, reported with coverage, Spearman correlation, runtime and memory usage.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
