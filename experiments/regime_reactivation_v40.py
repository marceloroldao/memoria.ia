from random import Random

from memoria_resolutiva.regime_memory import RegimeMemory


def noisy(base, rng, sigma=0.03):
    return tuple(max(0.0, x + rng.gauss(0.0, sigma)) for x in base)


def avg_signature(samples):
    d = len(samples[0])
    return tuple(sum(s[i] for s in samples) / len(samples) for i in range(d))


def detect_steps(memory, base, rng, max_steps=40):
    samples = []
    for step in range(1, max_steps + 1):
        samples.append(noisy(base, rng))
        name, score = memory.match(avg_signature(samples))
        if name is not None:
            return step, name, score
    return None, None, 0.0


def main():
    rng = Random(12345)
    A = (0.90, 0.15, 0.10, 0.80)
    B = (0.15, 0.90, 0.20, 0.20)
    C = (0.20, 0.25, 0.90, 0.15)

    memory = RegimeMemory(threshold=0.985)
    # First exposures require full local learning before profiles exist.
    memory.store("A", avg_signature([noisy(A, rng) for _ in range(30)]), 30)
    memory.store("B", avg_signature([noisy(B, rng) for _ in range(30)]), 30)
    memory.store("C", avg_signature([noisy(C, rng) for _ in range(30)]), 30)

    steps, name, score = detect_steps(memory, A, rng)
    print("return_to_A_detected_after", steps, "steps", "matched", name, "score", round(score, 6))
    print("cold_start_reference_steps", 30)
    if steps is not None:
        print("reactivation_speedup", round(30 / steps, 3))


if __name__ == "__main__":
    main()
