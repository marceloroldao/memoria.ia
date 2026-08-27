from memoria_resolutiva.structural_router_v96 import StructuralSemanticRouterV96


def _router():
    router = StructuralSemanticRouterV96(
        relation_window=5,
        threshold=0.20,
        min_margin=0.03,
    )
    router.register_many(
        "customer_pays_bank",
        [
            "cliente paga banco",
            "cliente transfere dinheiro banco",
            "cliente envia pagamento banco",
        ],
    )
    router.register_many(
        "bank_pays_customer",
        [
            "banco paga cliente",
            "banco transfere dinheiro cliente",
            "banco envia pagamento cliente",
        ],
    )
    return router


def test_structural_paraphrase_preserves_direction_with_inserted_words():
    router = _router()
    forward = router.resolve_text("cliente transfere dinheiro para banco")
    reverse = router.resolve_text("banco transfere dinheiro para cliente")
    assert forward.concept_id == "customer_pays_bank"
    assert reverse.concept_id == "bank_pays_customer"


def test_structural_paraphrase_keeps_direction_when_verb_changes():
    router = _router()
    forward = router.resolve_text("cliente envia pagamento ao banco")
    reverse = router.resolve_text("banco envia pagamento ao cliente")
    assert forward.concept_id == "customer_pays_bank"
    assert reverse.concept_id == "bank_pays_customer"


def test_structural_paraphrase_abstains_on_unseen_relation():
    router = _router()
    result = router.resolve_text("cliente visita banco")
    assert result.concept_id is None
