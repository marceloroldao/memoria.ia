from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .external_benchmark import SimilarityRow


def load_text_lines(path: str | Path, *, min_chars: int = 3) -> list[str]:
    """Load a UTF-8 corpus with one text unit per line.

    Empty/very short lines are skipped. External corpora are intentionally kept
    outside the repository; this loader makes the benchmark reproducible without
    redistributing third-party data.
    """
    p = Path(path)
    lines: list[str] = []
    with p.open("r", encoding="utf-8") as fh:
        for raw in fh:
            text = raw.strip()
            if len(text) >= min_chars:
                lines.append(text)
    return lines


def load_similarity_tsv(
    path: str | Path,
    *,
    delimiter: str = "\t",
    word1_col: int = 0,
    word2_col: int = 1,
    score_col: int = 2,
    skip_header: bool = False,
) -> list[SimilarityRow]:
    """Load a generic human-scored word-similarity file.

    The loader is deliberately format-light: PT-65, WordSim-style and SimLex-
    style files can be normalized by selecting columns rather than embedding a
    benchmark-specific parser in the core package.
    """
    p = Path(path)
    rows: list[SimilarityRow] = []
    with p.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh):
            if skip_header and line_no == 0:
                continue
            text = raw.strip()
            if not text or text.startswith("#"):
                continue
            parts = text.split(delimiter)
            need = max(word1_col, word2_col, score_col)
            if len(parts) <= need:
                continue
            try:
                score = float(parts[score_col].replace(",", "."))
            except ValueError:
                continue
            rows.append(
                SimilarityRow(
                    parts[word1_col].strip().lower(),
                    parts[word2_col].strip().lower(),
                    score,
                )
            )
    return rows


def train_models(sentences: Iterable[str], *, word2vec_seed: int = 1):
    """Train all currently supported v0.11 text models on identical input."""
    from .textual import TextContextMemory
    from .tfidf_context import TfidfContextBaseline

    sentences = list(sentences)
    resolutive = TextContextMemory(radius=3)
    tfidf = TfidfContextBaseline(radius=3)
    resolutive.observe_many(sentences)
    tfidf.observe_many(sentences)

    word2vec = None
    try:
        from .word2vec_baseline import Word2VecBaseline

        candidate = Word2VecBaseline(seed=word2vec_seed, epochs=20)
        candidate.fit(sentences)
        word2vec = candidate
    except RuntimeError:
        pass

    return resolutive, tfidf, word2vec
