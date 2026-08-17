from random import Random

from memoria_resolutiva.memory_decomposition_v65 import run_workload


def stable_events(n: int, items: int, seed: int):
    rng = Random(seed)
    return [(f"item_{rng.randrange(items)}", True, 1.0) for _ in range(n)]


def contradictory_events(n: int, items: int, seed: int):
    rng = Random(seed)
    out = []
    for i in range(n):
        key = f"item_{rng.randrange(items)}"
        positive = (i // 8) % 2 == 0
        out.append((key, positive, 1.0))
    return out


def main():
    for n, items in [(10_000, 1_000), (100_000, 5_000)]:
        for seed in (11, 37, 83):
            print("stable", n, seed, run_workload(stable_events(n, items, seed), items))
            print("contradictory", n, seed, run_workload(contradictory_events(n, items, seed), items))


if __name__ == "__main__":
    main()
