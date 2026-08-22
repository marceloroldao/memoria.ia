from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_bench = _load("trajectory_event_action_adversarial_v96_sweep", _HERE / "trajectory_event_action_adversarial_v96.py")


def main() -> None:
    for score_i in range(-40, 11, 5):
        min_score = score_i / 100
        metrics = _bench.evaluate(_bench.build(min_event_action_score=min_score), verbose=False)
        print({"min_event_action_score": min_score, **metrics})


if __name__ == "__main__":
    main()
