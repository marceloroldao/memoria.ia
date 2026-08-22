from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BENCH_PATH = _HERE / "event_pair_adversarial_v96.py"
_spec = importlib.util.spec_from_file_location("event_pair_adversarial_v96_sweep", _BENCH_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load benchmark: {_BENCH_PATH}")
_bench = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _bench
_spec.loader.exec_module(_bench)


def main() -> None:
    for min_state_score in (0.04, 0.06, 0.08, 0.10, 0.12):
        for strong_state_score in (0.25, 0.30, 0.35):
            router = _bench.build(
                min_state_score=min_state_score,
                min_event_pairs=1,
                strong_state_score=strong_state_score,
            )
            metrics = _bench.evaluate(router, verbose=False)
            print({
                "min_state_score": min_state_score,
                "strong_state_score": strong_state_score,
                **metrics,
            })


if __name__ == "__main__":
    main()
