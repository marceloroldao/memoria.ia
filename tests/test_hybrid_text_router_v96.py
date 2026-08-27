import pytest

from memoria_resolutiva.hybrid_text_router_v96 import HybridTextRouterV96
from memoria_resolutiva.textual import native_context_available


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_structural_resolves_when_semantic_tie_abstains():
    router = HybridTextRouterV96(
        semantic_threshold=0.0,
        semantic_min_margin=0.05,
        structural_threshold=0.45,
        structural_min_margin=0.08,
        use_native=True,
    )
    router.observe([
        "cliente paga banco",
        "banco paga cliente",
        "cliente transfere banco",
        "banco transfere cliente",
    ] * 24)
    # Same anchors deliberately create a semantic tie. Structure must carry role.
    router.register_semantic_concept("cliente_paga_banco", {"cliente", "banco"})
    router.register_semantic_concept("banco_paga_cliente", {"cliente", "banco"})
    router.register_structural_many("cliente_paga_banco", ["cliente paga banco", "cliente transfere banco"])
    router.register_structural_many("banco_paga_cliente", ["banco paga cliente", "banco transfere cliente"])

    forward = router.resolve_text("cliente paga banco")
    reverse = router.resolve_text("banco paga cliente")
    assert forward.semantic.concept_id is None
    assert reverse.semantic.concept_id is None
    assert forward.concept_id == "cliente_paga_banco"
    assert reverse.concept_id == "banco_paga_cliente"
    assert forward.source == "structural"
    assert reverse.source == "structural"


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_semantic_result_is_preserved_when_structure_has_no_pattern():
    router = HybridTextRouterV96(
        semantic_threshold=0.0,
        semantic_min_margin=0.01,
        use_native=True,
    )
    router.observe([
        "o automovel entrou na oficina para revisar o motor",
        "o carro ficou na oficina com problema no motor",
        "o veiculo voltou da oficina depois da manutencao",
    ] * 24)
    router.register_semantic_concept("veiculo", {"carro", "veiculo"})
    result = router.resolve_text("automovel oficina motor")
    assert result.concept_id == "veiculo"
    assert result.source == "semantic"
    assert result.structural.concept_id is None


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_matching_semantic_and_structural_results_form_consensus():
    router = HybridTextRouterV96(
        semantic_threshold=0.0,
        semantic_min_margin=0.0,
        structural_threshold=0.40,
        structural_min_margin=0.0,
        use_native=True,
    )
    router.observe(["sensor detecta falha equipamento"] * 32)
    router.register_semantic_concept("diagnostico", {"sensor", "falha"})
    router.register_structural_pattern("diagnostico", "sensor detecta falha")
    result = router.resolve_text("sensor detecta falha")
    assert result.concept_id == "diagnostico"
    assert result.source == "consensus"


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_semantic_structural_disagreement_abstains():
    router = HybridTextRouterV96(
        semantic_threshold=0.0,
        semantic_min_margin=0.0,
        structural_threshold=0.40,
        structural_min_margin=0.0,
        use_native=True,
    )
    router.observe(["sensor detecta falha equipamento"] * 32)
    router.register_semantic_concept("diagnostico", {"sensor", "falha"})
    router.register_structural_pattern("acao", "sensor detecta falha")
    result = router.resolve_text("sensor detecta falha")
    assert result.concept_id is None
    assert result.source == "conflict"
    assert result.semantic.concept_id == "diagnostico"
    assert result.structural.concept_id == "acao"


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_open_set_remains_unresolved_and_stats_are_auditable():
    router = HybridTextRouterV96(use_native=True)
    router.observe(["rede fibra sinal roteador"] * 16)
    router.register_semantic_concept("conectividade", {"rede", "fibra"})
    router.register_structural_pattern("conectividade", "rede perde sinal")
    result = router.resolve_text("galaxia ilumina planeta")
    assert result.concept_id is None
    assert result.source == "unresolved"
    stats = router.stats()
    assert stats.total == 1
    assert stats.unresolved == 1
    router.reset_stats()
    assert router.stats().total == 0
