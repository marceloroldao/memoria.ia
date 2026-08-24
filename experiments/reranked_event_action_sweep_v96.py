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


_bench = _load("reranked_event_action_adversarial_v96_sweep", _HERE / "reranked_event_action_adversarial_v96.py")


def main() -> None:
    # Coarse architecture sweep. The frozen adversarial corpus is evaluation-only.
    for rerank_lambda in (0.0, 0.25, 0.5, 0.75, 1.0):
        for event_score in (-0.30, -0.20, -0.15, -0.10, -0.05, 0.0):
            metrics = _bench.evaluate(
                _bench.build(
                    rerank_lambda=rerank_lambda,
                    min_event_action_score=event_score,
                ),
                verbose=False,
            )
            print({
                "rerank_lambda": rerank_lambda,
                "min_event_action_score": event_score,
                **metrics,
            })


if __name__ == "__main__":
    main()
