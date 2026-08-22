from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Iterable

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_split = _load("natural_language_split_v96_protocol", _HERE / "natural_language_split_v96.py")
_adv = _load("adversarial_generalization_v96_protocol", _HERE / "adversarial_generalization_v96.py")

TRAIN = _split.TRAIN
CALIBRATION = _split.CALIBRATION
CONTRASTIVE_CALIBRATION = _split.CONTRASTIVE_CALIBRATION
ADVERSARIAL = _adv.ADVERSARIAL
COUNTEREXAMPLES = _adv.COUNTEREXAMPLES

PROTOCOL_ID = "v0.96-event-action-protocol-1"


def _normalized(sentence: str) -> str:
    return " ".join(sentence.split()).strip().lower()


def iter_concept_counterexamples() -> Iterable[tuple[str, str]]:
    """Yield deterministic, deduplicated concept-specific negative trajectories.

    Sources are limited to the pre-existing calibration/counterexample corpora. The
    frozen ADVERSARIAL set is evaluation-only and is never yielded here.
    """
    seen: set[tuple[str, str]] = set()
    for source in (COUNTEREXAMPLES, CONTRASTIVE_CALIBRATION):
        for concept_id in sorted(source):
            for sentence in source[concept_id]:
                key = (concept_id, _normalized(sentence))
                if key in seen:
                    continue
                seen.add(key)
                yield concept_id, sentence


def iter_global_actions() -> Iterable[str]:
    """Yield one deterministic, globally deduplicated action/normal corpus.

    Every concept-specific counterexample also contributes once to the global
    action/normal channel. Calibration entries labelled None are then added once.
    """
    seen: set[str] = set()
    for _, sentence in iter_concept_counterexamples():
        key = _normalized(sentence)
        if key in seen:
            continue
        seen.add(key)
        yield sentence
    for expected, sentence in CALIBRATION:
        if expected is not None:
            continue
        key = _normalized(sentence)
        if key in seen:
            continue
        seen.add(key)
        yield sentence


def protocol_summary() -> dict[str, int | str]:
    concept_negatives = list(iter_concept_counterexamples())
    actions = list(iter_global_actions())
    return {
        "protocol_id": PROTOCOL_ID,
        "concepts": len(TRAIN),
        "positive_sentences": sum(len(v) for v in TRAIN.values()),
        "concept_counterexamples": len(concept_negatives),
        "global_actions": len(actions),
        "adversarial_evaluation_sentences": len(ADVERSARIAL),
    }
