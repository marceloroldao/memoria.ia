from __future__ import annotations

import argparse
import json
import random
import time

from memoria_resolutiva.textual import TextContextMemory, native_context_available


def make_corpus(sentences: int, vocab: int, width: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    words = [f"t{i}" for i in range(vocab)]
    out: list[str] = []
    for i in range(sentences):
        # A stable local motif plus controlled noise creates realistic overlap
        # without turning every profile into the same dense neighborhood.
        base = (i * 7) % vocab
        row = [words[(base + j) % vocab] for j in range(width // 2)]
        row.extend(words[rng.randrange(vocab)] for _ in range(width - len(row)))
        out.append(" ".join(row))
    return out


def build(corpus: list[str], use_native: bool) -> tuple[TextContextMemory, float]:
    t0 = time.perf_counter()
    memory = TextContextMemory(radius=3, use_native=use_native)
    memory.observe_many(corpus)
    return memory, time.perf_counter() - t0


def score(memory: TextContextMemory, pairs: list[tuple[str, str]]) -> tuple[float, float]:
    checksum = 0.0
    t0 = time.perf_counter()
    for a, b in pairs:
        checksum += max(memory.similarity(a, b), memory.unordered_similarity(a, b))
    return time.perf_counter() - t0, checksum


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sentences", type=int, default=6000)
    parser.add_argument("--vocab", type=int, default=2500)
    parser.add_argument("--width", type=int, default=14)
    parser.add_argument("--queries", type=int, default=30000)
    parser.add_argument("--seed", type=int, default=126)
    args = parser.parse_args()

    if not native_context_available():
        raise SystemExit("native context extension not built")

    corpus = make_corpus(args.sentences, args.vocab, args.width, args.seed)
    pure, pure_build = build(corpus, False)
    native, native_build = build(corpus, True)

    tokens = sorted(pure.associator.profiles)
    rng = random.Random(args.seed + 1)
    pairs = [(tokens[rng.randrange(len(tokens))], tokens[rng.randrange(len(tokens))]) for _ in range(args.queries)]

    pure_s, pure_sum = score(pure, pairs)
    native_s, native_sum = score(native, pairs)
    if abs(pure_sum - native_sum) > 1e-8 * max(1.0, abs(pure_sum)):
        raise AssertionError((pure_sum, native_sum))

    result = {
        "sentences": args.sentences,
        "vocab": args.vocab,
        "width": args.width,
        "queries": args.queries,
        "python": {"build_s": pure_build, "score_s": pure_s},
        "native": {"build_s": native_build, "score_s": native_s},
        "speedup": {
            "score": pure_s / native_s if native_s else None,
            "build": pure_build / native_build if native_build else None,
        },
        "checksum": native_sum,
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
