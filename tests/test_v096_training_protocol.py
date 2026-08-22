from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "experiments" / "v096_training_protocol.py"


def _load_protocol():
    spec = importlib.util.spec_from_file_location("v096_training_protocol_test", PROTOCOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_clean_training_path_is_exactly_disjoint_from_test():
    protocol = _load_protocol()
    audit = protocol.protocol_audit()
    assert audit["clean_training_path_exactly_disjoint_from_test"] is True
    assert audit["clean_train_calibration_vs_test_exact_overlap"] == []


def test_adversarial_development_counterexamples_are_not_clean_calibration():
    protocol = _load_protocol()
    clean = {
        protocol.normalize_sentence(sentence)
        for _, sentence in protocol.iter_clean_concept_counterexamples()
    }
    development = {
        protocol.normalize_sentence(sentence)
        for rows in protocol.DEVELOPMENT_COUNTEREXAMPLES.values()
        for sentence in rows
    }
    assert clean.isdisjoint(development)


def test_development_counterexamples_expose_known_test_overlap():
    protocol = _load_protocol()
    audit = protocol.protocol_audit()
    overlap = set(audit["development_counterexample_vs_test_exact_overlap"])
    assert overlap == {
        "foi emitido um comprovante de pagamento ja realizado",
        "o tecnico substituiu a fonte de alimentacao da onu",
        "o usuario quer atualizar telefone e email do cadastro",
    }
