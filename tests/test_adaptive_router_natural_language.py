from __future__ import annotations

import pytest

from memoria_resolutiva.semantic_router_v96 import AdaptiveSemanticRouterV96, SemanticRouterV96
from memoria_resolutiva.textual import native_context_available


NATURAL_CORPUS = [
    # veiculos / sinonimia
    "o carro ficou parado na estrada depois de uma falha no motor",
    "o automovel precisou de oficina depois que o motor aqueceu",
    "o veiculo entrou na garagem para manutencao e troca de oleo",
    "a oficina revisou o carro e o automovel antes da viagem",
    # animais / sinonimia
    "o cachorro correu pelo quintal e latiu perto da casa",
    "o cao dormiu ao lado da porta depois de brincar no quintal",
    "o animal domestico recebeu comida e agua perto da casa",
    "o veterinario examinou o cachorro e o cao durante a consulta",
    # conectividade / termos correlatos
    "a internet caiu quando a fibra perdeu sinal no roteador",
    "o link de fibra voltou depois que o tecnico reiniciou o roteador",
    "a conexao de rede ficou instavel durante a falha do provedor",
    "o tecnico mediu o sinal da internet e da fibra no equipamento",
    # financeiro / termos correlatos
    "o pagamento do boleto foi confirmado pelo banco durante a tarde",
    "a fatura foi quitada depois que o cliente pagou o boleto",
    "o banco registrou o pagamento e atualizou o saldo da conta",
    "o cliente abriu a conta para receber dinheiro e pagar a fatura",
    # banco como assento: polissemia intencional
    "o banco de madeira ficou na praca ao lado da arvore",
    "as pessoas sentaram no banco da praca durante a caminhada",
    "o banco foi pintado junto com os outros assentos do parque",
    "o marceneiro consertou o banco de madeira usado como assento",
] * 12

CONCEPTS = {
    "veiculo": {"carro", "veiculo"},
    "animal": {"cachorro", "animal"},
    "conectividade": {"internet", "rede"},
    "financeiro": {"pagamento", "fatura"},
    "mobiliario": {"assento", "madeira"},
}

IDENTIFIABLE = {
    "automovel": "veiculo",
    "cao": "animal",
    "fibra": "conectividade",
    "boleto": "financeiro",
}

PHRASES = {
    "automovel na oficina": "veiculo",
    "cao no quintal": "animal",
    "fibra sem sinal": "conectividade",
    "boleto para pagamento": "financeiro",
    "banco de madeira": "mobiliario",
    "pagamento no banco": "financeiro",
}

AMBIGUOUS_OR_OPEN = ("banco", "casa", "tecnico", "galaxia", "fotossintese")


def _build_pair(*, threshold: float = 0.0, min_margin: float = 0.0):
    full = SemanticRouterV96(threshold=threshold, min_margin=min_margin, use_native=True)
    adaptive = AdaptiveSemanticRouterV96(
        threshold=threshold,
        min_margin=min_margin,
        use_native=True,
        adaptive_threshold=4,
        candidate_limit=4,
    )
    for router in (full, adaptive):
        router.observe(NATURAL_CORPUS)
        for concept_id, anchors in CONCEPTS.items():
            router.register_concept(concept_id, anchors)
    return full, adaptive


def _assert_same(full, adaptive, query: str) -> None:
    expected = full.resolve_token(query)
    actual = adaptive.resolve_token(query)
    assert actual.concept_id == expected.concept_id
    assert actual.source == expected.source
    assert actual.score == pytest.approx(expected.score, abs=1e-12)
    assert actual.margin == pytest.approx(expected.margin, abs=1e-12)


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_adaptive_matches_full_scan_on_natural_portuguese_synonyms():
    full, adaptive = _build_pair()
    for query, expected_concept in IDENTIFIABLE.items():
        _assert_same(full, adaptive, query)
        assert full.resolve_token(query).concept_id == expected_concept


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_adaptive_preserves_full_scan_on_polysemy_noise_and_open_set():
    full, adaptive = _build_pair(threshold=0.55, min_margin=0.08)
    for query in AMBIGUOUS_OR_OPEN:
        _assert_same(full, adaptive, query)

    # "banco" occurs in two intentionally different senses. The adaptive
    # router may prune only when its top-two separation is safe; otherwise
    # it must verify against the authoritative full scan.
    adaptive.resolve_token("banco")
    assert adaptive.last_route_mode in {"full_verify", "discriminative"}


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_phrase_resolution_uses_resolved_tokens_as_conservative_evidence():
    full, adaptive = _build_pair(threshold=0.55, min_margin=0.08)
    for text, expected_concept in PHRASES.items():
        expected = full.resolve_text(text)
        actual = adaptive.resolve_text(text)
        assert expected.concept_id == expected_concept
        assert actual.concept_id == expected.concept_id
        assert actual.score == pytest.approx(expected.score, abs=1e-12)
        assert actual.margin == pytest.approx(expected.margin, abs=1e-12)
        assert actual.evidence

    assert full.resolve_text("galaxia distante").concept_id is None
    assert adaptive.resolve_text("galaxia distante").concept_id is None


@pytest.mark.skipif(not native_context_available(), reason="native core unavailable")
def test_natural_language_gate_exercises_adaptive_telemetry():
    _full, adaptive = _build_pair()
    for query in list(IDENTIFIABLE) + list(AMBIGUOUS_OR_OPEN):
        adaptive.resolve_token(query)
    stats = adaptive.routing_stats()
    assert stats.total == len(IDENTIFIABLE) + len(AMBIGUOUS_OR_OPEN)
    assert stats.discriminative + stats.full_verify + stats.full == stats.total
