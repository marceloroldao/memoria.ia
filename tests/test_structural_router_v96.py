import pytest

from memoria_resolutiva.structural_router_v96 import StructuralSemanticRouterV96, native_structural_available

PATTERNS = {
    "cliente_paga_banco": ["cliente paga banco", "cliente transfere banco", "cliente envia pagamento banco"],
    "banco_paga_cliente": ["banco paga cliente", "banco transfere cliente", "banco envia pagamento cliente"],
    "sensor_detecta_falha": ["sensor detecta falha", "sensor identifica falha", "sensor registra falha"],
    "falha_aciona_sensor": ["falha aciona sensor", "falha ativa sensor", "falha dispara sensor"],
}


def _router(*, use_native=None):
    router = StructuralSemanticRouterV96(relation_window=3, threshold=0.45, min_margin=0.08, use_native=use_native)
    for concept_id, patterns in PATTERNS.items():
        router.register_many(concept_id, patterns)
    return router


def test_same_bag_different_order_resolves_different_intent():
    router = _router(use_native=False)
    forward = router.resolve_text("cliente paga banco")
    reverse = router.resolve_text("banco paga cliente")
    assert forward.concept_id == "cliente_paga_banco"
    assert reverse.concept_id == "banco_paga_cliente"
    assert forward.margin > 0.08
    assert reverse.margin > 0.08


def test_structural_router_generalizes_over_relation_synonyms():
    router = _router(use_native=False)
    assert router.resolve_text("cliente transfere banco").concept_id == "cliente_paga_banco"
    assert router.resolve_text("banco transfere cliente").concept_id == "banco_paga_cliente"
    assert router.resolve_text("sensor identifica falha").concept_id == "sensor_detecta_falha"
    assert router.resolve_text("falha ativa sensor").concept_id == "falha_aciona_sensor"


def test_unseen_or_conflicting_structure_abstains():
    router = _router(use_native=False)
    assert router.resolve_text("galaxia ilumina planeta").concept_id is None
    assert router.resolve_text("cliente sensor banco").concept_id is None


def test_word_order_changes_sparse_signature_even_with_same_tokens():
    router = _router(use_native=False)
    a = router._features("cliente paga banco")
    b = router._features("banco paga cliente")
    assert set(token for feature in a for token in (feature[0], feature[2])) == set(token for feature in b for token in (feature[0], feature[2]))
    assert a != b


@pytest.mark.skipif(not native_structural_available(), reason="native structural core unavailable")
def test_native_structural_matches_python_reference():
    python_router = _router(use_native=False)
    native_router = _router(use_native=True)
    queries = [
        "cliente paga banco", "banco paga cliente", "cliente transfere banco",
        "banco transfere cliente", "sensor identifica falha", "falha ativa sensor",
        "galaxia ilumina planeta", "cliente sensor banco",
    ]
    for query in queries:
        expected = python_router.resolve_text(query)
        actual = native_router.resolve_text(query)
        assert actual.concept_id == expected.concept_id
        assert actual.score == pytest.approx(expected.score, abs=1e-12)
        assert actual.margin == pytest.approx(expected.margin, abs=1e-12)
        assert len(actual.evidence) == len(expected.evidence)
        for got, want in zip(actual.evidence, expected.evidence):
            assert got.concept_id == want.concept_id
            assert got.score == pytest.approx(want.score, abs=1e-12)
