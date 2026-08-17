from random import Random

from memoria_resolutiva.scaling_v64 import empirical_exponent, evaluate_scale


def make_events(n: int, items: int, seed: int):
    rng = Random(seed)
    out = []
    for i in range(n):
        key = f"item_{rng.randrange(items)}"
        phase = (i // max(1, n // 10)) % 4
        positive = phase != 2 if rng.random() < 0.85 else phase == 2
        out.append((key, positive, 1.0))
    return out


def main():
    seeds = [11, 37, 83]
    scales = [(10_000, 1_000), (100_000, 5_000), (1_000_000, 20_000)]
    rows = []
    for events, items in scales:
        sets = [make_events(events, items, seed) for seed in seeds]
        row = evaluate_scale(sets, items=items, levels=5)
        rows.append(row)
        print(row)

    print("peak-memory exponent vs items:", empirical_exponent(
        [r.items for r in rows], [r.peak_bytes_mean for r in rows]))
    print("latency exponent vs events:", empirical_exponent(
        [r.events for r in rows], [r.latency_us_mean for r in rows]))


if __name__ == "__main__":
    main()
