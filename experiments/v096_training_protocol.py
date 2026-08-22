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
TEST = _split.TEST

# Development diagnostics only. These corpora have already been inspected during
# architecture development and therefore are not publication-grade blind holdouts.
ADVERSARIAL_DEV = _adv.ADVERSARIAL
DEVELOPMENT_COUNTEREXAMPLES = _adv.COUNTEREXAMPLES

CLEAN_PROTOCOL_ID = "v0.96-clean-calibration-protocol-2"
DEVELOPMENT_PROTOCOL_ID = "v0.96-adversarial-development-only"


def normalize_sentence(sentence: str) -> str:
    return " ".join(sentence.split()).strip().lower()


def iter_clean_concept_counterexamples() -> Iterable[tuple[str, str]]:
    """Yield only pre-test calibration counterexamples."""
    seen: set[tuple[str, str]] = set()
    for concept_id in sorted(CONTRASTIVE_CALIBRATION):
        for sentence in CONTRASTIVE_CALIBRATION[concept_id]:
            key = (concept_id, normalize_sentence(sentence))
            if key in seen:
                continue
            seen.add(key)
            yield concept_id, sentence


def iter_clean_global_actions() -> Iterable[str]:
    """Yield globally deduplicated action/normal calibration evidence."""
    seen: set[str] = set()
    for _, sentence in iter_clean_concept_counterexamples():
        key = normalize_sentence(sentence)
        if key in seen:
            continue
        seen.add(key)
        yield sentence
    for expected, sentence in CALIBRATION:
        if expected is not None:
            continue
        key = normalize_sentence(sentence)
        if key in seen:
            continue
        seen.add(key)
        yield sentence


def clean_calibration_rows() -> list[tuple[str | None, str]]:
    """Rows allowed for parameter selection before evaluation."""
    rows = list(CALIBRATION)
    rows.extend((None, sentence) for sentence in iter_clean_global_actions())
    out: list[tuple[str | None, str]] = []
    seen: set[tuple[str | None, str]] = set()
    for expected, sentence in rows:
        key = (expected, normalize_sentence(sentence))
        if key in seen:
            continue
        seen.add(key)
        out.append((expected, sentence))
    return out


def iter_development_concept_counterexamples() -> Iterable[tuple[str, str]]:
    """Development-only negatives; forbidden for clean holdout claims."""
    seen: set[tuple[str, str]] = set()
    for source in (DEVELOPMENT_COUNTEREXAMPLES, CONTRASTIVE_CALIBRATION):
        for concept_id in sorted(source):
            for sentence in source[concept_id]:
                key = (concept_id, normalize_sentence(sentence))
                if key in seen:
                    continue
                seen.add(key)
                yield concept_id, sentence


def iter_development_global_actions() -> Iterable[str]:
    seen: set[str] = set()
    for _, sentence in iter_development_concept_counterexamples():
        key = normalize_sentence(sentence)
        if key not in seen:
            seen.add(key)
            yield sentence
    for expected, sentence in CALIBRATION:
        if expected is None:
            key = normalize_sentence(sentence)
            if key not in seen:
                seen.add(key)
                yield sentence


def _normalized_rows(rows: Iterable[tuple[str | None, str]]) -> set[str]:
    return {normalize_sentence(sentence) for _, sentence in rows}


def protocol_audit() -> dict[str, object]:
    train_sentences = {normalize_sentence(s) for examples in TRAIN.values() for s in examples}
    calibration_sentences = _normalized_rows(clean_calibration_rows())
    test_sentences = _normalized_rows(TEST)
    adversarial_sentences = _normalized_rows(ADVERSARIAL_DEV)
    dev_counterexamples = {
        normalize_sentence(s)
        for examples in DEVELOPMENT_COUNTEREXAMPLES.values()
        for s in examples
    }
    clean_memory = train_sentences | calibration_sentences
    clean_test_overlap = sorted(clean_memory & test_sentences)
    clean_adversarial_overlap = sorted(clean_memory & adversarial_sentences)
    dev_counterexample_test_overlap = sorted(dev_counterexamples & test_sentences)
    return {
        "clean_protocol_id": CLEAN_PROTOCOL_ID,
        "development_protocol_id": DEVELOPMENT_PROTOCOL_ID,
        "concepts": len(TRAIN),
        "positive_train_sentences": len(train_sentences),
        "clean_calibration_rows": len(clean_calibration_rows()),
        "clean_global_actions": len(list(iter_clean_global_actions())),
        "test_rows": len(TEST),
        "adversarial_dev_rows": len(ADVERSARIAL_DEV),
        "clean_train_calibration_vs_test_exact_overlap": clean_test_overlap,
        "clean_train_calibration_vs_adversarial_exact_overlap": clean_adversarial_overlap,
        "development_counterexample_vs_test_exact_overlap": dev_counterexample_test_overlap,
        "clean_training_path_exactly_disjoint_from_test": not clean_test_overlap,
    }


def protocol_summary() -> dict[str, object]:
    return protocol_audit()


# Backward-compatible names are intentionally development-only. Existing historical
# adversarial scripts keep running, but their output must not be presented as a
# blind publication estimate.
PROTOCOL_ID = DEVELOPMENT_PROTOCOL_ID
ADVERSARIAL = ADVERSARIAL_DEV
COUNTEREXAMPLES = DEVELOPMENT_COUNTEREXAMPLES
iter_concept_counterexamples = iter_development_concept_counterexamples
iter_global_actions = iter_development_global_actions
