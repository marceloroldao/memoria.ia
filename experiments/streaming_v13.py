from __future__ import annotations

import random
from statistics import mean

from memoria_resolutiva.streaming import StreamingLearningEvaluator

SEED = 123
PAIR_COUNT = 30
BATCHES = 60
SIGNAL_PER_BATCH = 20
NOISE_PER_BATCH = 15
CONTEXT = [
    "sistema", "processo", "rede", "memoria", "campo", "controle",
    "dados", "sinal", "estado", "fluxo", "modelo", "estrutura",
]


def make_batch(rng: random.Random, pair: tuple[str, str], step: int) -> list[str]:
    a, b = pair
    c1, c2, c3 = rng.sample(CONTEXT, 3)
    sentences: list[str] = []
    for _ in range(SIGNAL_PER_BATCH // 2):
        sentences.append(f"{a} {c1} {c2} {c3} operativo")
        sentences.append(f"{b} {c1} {c2} {c3} operativo")
    for _ in range(NOISE_PER_BATCH):
        noise = " ".join(rng.sample(CONTEXT, 4))
        sentences.append(f"{noise} ruido{rng.randrange(200)}")

    # After two thirds of the stream, periodically inject a plausible rival in
    # the same context. This stresses retention without overwriting old memory.
    if step >= 40 and step % 6 == 0:
        rival = f"rival_{a}"
        for _ in range(8):
            sentences.append(f"{rival} {c1} {c2} {c3} operativo")

    rng.shuffle(sentences)
    return sentences


def main() -> None:
    rng = random.Random(SEED)
    pairs = [(f"conceito{i}a", f"conceito{i}b") for i in range(PAIR_COUNT)]
    evaluator = StreamingLearningEvaluator(radius=3)
    checkpoints = []

    for step in range(BATCHES):
        pair = pairs[step % len(pairs)]
        batch = make_batch(rng, pair, step)
        checkpoint = evaluator.observe_batch(
            batch,
            expected_pair=pair,
            measure_retention=((step + 1) % 5 == 0),
        )
        checkpoints.append(checkpoint)
        if (step + 1) % 5 == 0:
            print(
                f"batch={checkpoint.batch:3d} sentences={checkpoint.sentences_seen:5d} "
                f"update_ms={checkpoint.update_seconds * 1000:8.3f} "
                f"immediate={checkpoint.immediate_top1:.3f} "
                f"retention={checkpoint.retention_top1:.3f} "
                f"nodes={checkpoint.nodes:4d} features={checkpoint.features:6d}"
            )

    first = checkpoints[:10]
    last = checkpoints[-10:]
    print("\nsummary")
    print(f"sentences_total={checkpoints[-1].sentences_seen}")
    print(f"mean_update_ms_first10={mean(c.update_seconds for c in first) * 1000:.3f}")
    print(f"mean_update_ms_last10={mean(c.update_seconds for c in last) * 1000:.3f}")
    print(f"final_nodes={checkpoints[-1].nodes}")
    print(f"final_features={checkpoints[-1].features}")


if __name__ == "__main__":
    main()
