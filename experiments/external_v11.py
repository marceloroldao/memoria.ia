from __future__ import annotations

import argparse

from memoria_resolutiva.corpus_io import load_similarity_tsv, load_text_lines, train_models
from memoria_resolutiva.external_benchmark import evaluate_similarity_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="v0.11 external-corpus similarity benchmark")
    parser.add_argument("--corpus", required=True, help="UTF-8 text file, one sentence/text unit per line")
    parser.add_argument("--benchmark", required=True, help="TSV/CSV-like human-rated word-pair file")
    parser.add_argument("--delimiter", default="\t")
    parser.add_argument("--word1-col", type=int, default=0)
    parser.add_argument("--word2-col", type=int, default=1)
    parser.add_argument("--score-col", type=int, default=2)
    parser.add_argument("--skip-header", action="store_true")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-lines", type=int, default=0, help="0 uses the full corpus")
    args = parser.parse_args()

    sentences = load_text_lines(args.corpus)
    if args.max_lines > 0:
        sentences = sentences[: args.max_lines]
    rows = load_similarity_tsv(
        args.benchmark,
        delimiter=args.delimiter,
        word1_col=args.word1_col,
        word2_col=args.word2_col,
        score_col=args.score_col,
        skip_header=args.skip_header,
    )

    resolutive, tfidf, word2vec = train_models(sentences, word2vec_seed=args.seed)
    models = [
        (
            "resolutive",
            resolutive.associator.similarity,
            lambda word: word.lower() in resolutive.associator.profiles,
        ),
        (
            "tfidf",
            tfidf.similarity,
            lambda word: word.lower() in tfidf.profiles,
        ),
    ]
    if word2vec is not None:
        models.append(
            (
                "word2vec",
                word2vec.similarity,
                lambda word: word2vec.model is not None and word.lower() in word2vec.model.wv,
            )
        )

    print(f"corpus_lines={len(sentences)} benchmark_pairs={len(rows)}")
    for name, similarity, contains in models:
        result = evaluate_similarity_rows(rows, similarity, contains=contains)
        print(
            f"{name:10s} coverage={result['coverage']:.3f} "
            f"covered={int(result['covered_pairs'])}/{int(result['pairs'])} "
            f"spearman={result['spearman']:.3f}"
        )


if __name__ == "__main__":
    main()
