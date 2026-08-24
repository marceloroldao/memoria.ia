from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from memoria_resolutiva.reranked_event_action_v96 import RerankedEventActionRouterV96

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_protocol = _load("v096_training_protocol_clean_ablation", _HERE / "v096_training_protocol.py")
_selector = _load("clean_calibrated_event_action_v96_ablation", _HERE / "clean_calibrated_event_action_v96.py")


def build(*, retrieval_threshold: float, min_margin: float, event_score: float):
    router = RerankedEventActionRouterV96(
        retrieval_threshold=retrieval_threshold,
        rerank_lambda=0.0,
        min_reranked_score=0.0,
        min_reranked_margin=min_margin,
        min_event_action_score=event_score,
    )
    for concept_id, examples in _protocol.TRAIN.items():
        router.observe_concept(concept_id, examples)
    for sentence in _protocol.iter_clean_global_actions():
        router.observe_action(sentence)
    return router


def report(name: str, retrieval: float, margin: float, event_score: float):
    router = build(
        retrieval_threshold=retrieval,
        min_margin=margin,
        event_score=event_score,
    )
    return {
        "variant": name,
        "retrieval_threshold": retrieval,
        "min_margin": margin,
        "min_event_action_score": event_score,
        "calibration": _selector.evaluate(router, _protocol.clean_calibration_rows()),
        "test": _selector.evaluate(router, _protocol.TEST),
    }


def main() -> None:
    # Fixed from calibration-only selector. No parameter below is chosen from TEST.
    retrieval = 0.04
    selected_margin = 0.01
    selected_event = -0.50
    event_disabled = -1_000_000.0

    variants = [
        report("retrieval_only", retrieval, 0.0, event_disabled),
        report("retrieval_plus_margin", retrieval, selected_margin, event_disabled),
        report("retrieval_plus_event", retrieval, 0.0, selected_event),
        report("selected_full", retrieval, selected_margin, selected_event),
    ]

    print("clean_ablation_v96")
    print({"protocol": _protocol.CLEAN_PROTOCOL_ID, "variants": variants})


if __name__ == "__main__":
    main()
