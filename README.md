# memoria.ia

Experimental implementation of **Resolutive Memory**, a hierarchical memory architecture based on reusable nodes, trajectories and increasing bit resolution.

## Layer model

- L0 = 8 bits
- L1 = 16 bits
- L2 = 32 bits
- L3 = 64 bits

The layer rule is:

`R(L) = 8 * 2^L`

## v0.10 scope

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
- external word-similarity benchmark support
- Spearman rank correlation and vocabulary coverage metrics
- reproducible experiments and unit tests

The v0.9 controlled benchmark showed equal 8/8 top-1 accuracy for the resolutive and TF-IDF-like context models, with larger partner-vs-distractor margins for the signed positional model.

v0.10 adds a shallow neural/distributional baseline. On the deliberately tiny v0.9 corpus, Word2Vec is highly seed-sensitive: in a five-seed probe it ranged from 3/8 to 7/8 top-1 and produced negative minimum margins in every run. This is recorded as evidence that a tiny constructed corpus is inadequate for a definitive Word2Vec comparison, not as evidence that the resolutive model is superior to Word2Vec.

The project now includes generic external benchmark evaluation using human-scored word pairs. This enables PT-65, Portuguese WordSim-353, Portuguese SimLex-999 or compatible datasets to be evaluated using vocabulary coverage and Spearman correlation between model similarity and human judgments.

An external corpus candidate is the TTS-Portuguese Corpus, which is openly licensed under CC BY 4.0 and reports 71,358 words with 13,311 distinct words. External corpora and human-rated similarity benchmarks should remain independent from the controlled development corpus.

## Install and test

```bash
python -m pip install -e .
python -m pytest -q
```

Optional Word2Vec baseline:

```bash
python -m pip install -e '.[word2vec]'
python experiments/comparative_v10.py
```

Earlier experiments remain available under `experiments/`.

## Research status

This is an experimental research project. The current evidence supports exact reconstruction, multiscale structural memory, sparse contextual association and promising controlled comparisons. It does **not** yet establish unrestricted semantic understanding, general intelligence, or superiority over modern NLP/embedding models. The next decisive stage is evaluation on an independently sourced corpus with standard Portuguese similarity benchmarks and strict train/test separation.

See [`docs/architecture.md`](docs/architecture.md) for the current model.
