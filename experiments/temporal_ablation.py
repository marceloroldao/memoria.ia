"""Compare uniform and multiscale consolidation clocks.

Run from repository root:
    python experiments/temporal_ablation.py
"""
from src.memoria_ia import ResolutiveMemory


def run(multiscale: bool):
    m = ResolutiveMemory(temporal_scaling=multiscale)

    # Establish stable knowledge.
    for _ in range(64):
        m.observe("A", "stable")

    stable_before = m.recall("A")

    # Inject short contradictory burst.
    for _ in range(3):
        m.observe("A", "noise")

    stable_after_noise = m.recall("A")

    # Restore coherent evidence.
    for _ in range(64):
        m.observe("A", "stable")

    final = m.recall("A")
    return {
        "clock": "multiscale" if multiscale else "uniform",
        "before": stable_before,
        "after_noise": stable_after_noise,
        "final": final,
        "footprint": m.footprint(),
        "periods": [x.update_period for x in m.layers],
    }


if __name__ == "__main__":
    for mode in (False, True):
        print(run(mode))
