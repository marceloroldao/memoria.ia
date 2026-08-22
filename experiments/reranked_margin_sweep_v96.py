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


_bench = _load("reranked_event_action_adversarial_v96_margin", _HERE / "reranked_event_action_adversarial_v96.py")


def main() -> None:
    # lambda=0 isolates confidence/ambiguity from the failed negative reranking hypothesis.
    for retrieval_threshold in (0.04, 0.05, 0.06, 0.07):
        for margin_i in range(0, 51, 5):
            min_margin = margin_i / 1000
            for event_score in (-0.20, -0.15, -0.10):
                metrics = _bench.evaluate(
                    _bench.build(
                        retrieval_threshold=retrieval_threshold,
                        rerank_lambda=0.0,
                        min_reranked_score=0.0,
                        min_reranked_margin=min_margin,
                        min_event_action_score=event_score,
                    ),
                    verbose=False,
                )
                print({
                    "retrieval_threshold": retrieval_threshold,
                    "min_reranked_margin": min_margin,
                    "min_event_action_score": event_score,
                    **metrics,
                })


if __name__ == "__main__":
    main()
