from __future__ import annotations

from .textual import tokenize


class Word2VecBaseline:
    """Optional shallow embedding baseline backed by gensim Word2Vec.

    The dependency is intentionally optional so the core project remains
    lightweight. Training is deterministic when workers=1 and seed is fixed.
    """

    def __init__(self, vector_size: int = 64, window: int = 3, seed: int = 1, epochs: int = 100):
        self.vector_size = vector_size
        self.window = window
        self.seed = seed
        self.epochs = epochs
        self.model = None

    def fit(self, sentences) -> None:
        try:
            from gensim.models import Word2Vec
        except ImportError as exc:
            raise RuntimeError("Install memoria-resolutiva[word2vec] to use this baseline") from exc
        corpus = [tokenize(s) for s in sentences]
        corpus = [s for s in corpus if s]
        self.model = Word2Vec(
            sentences=corpus,
            vector_size=self.vector_size,
            window=self.window,
            min_count=1,
            sg=1,
            negative=5,
            epochs=self.epochs,
            workers=1,
            seed=self.seed,
        )

    def similarity(self, a: str, b: str) -> float:
        if self.model is None:
            raise RuntimeError("fit() must be called before similarity()")
        a, b = a.lower(), b.lower()
        if a not in self.model.wv or b not in self.model.wv:
            return 0.0
        return float(self.model.wv.similarity(a, b))
