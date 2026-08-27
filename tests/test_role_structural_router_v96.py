from memoria_resolutiva.role_structural_router_v96 import RoleStructuralRouterV96


def _router():
    router = RoleStructuralRouterV96(
        role_threshold=0.30,
        role_min_margin=0.02,
        structural_threshold=0.45,
        structural_min_margin=0.08,
        relation_window=5,
    )
    router.observe(
        [
            "cliente envia pagamento banco",
            "comprador transfere dinheiro banco",
            "usuario remete valor instituicao",
            "banco envia pagamento cliente",
            "instituicao transfere dinheiro comprador",
            "banco remete valor usuario",
        ]
    )
    router.register_role("customer", ["cliente", "comprador", "usuario"])
    router.register_role("transfer", ["paga", "envia", "transfere", "remete"])
    router.register_role("money", ["dinheiro", "pagamento", "valor"])
    router.register_role("bank", ["banco", "instituicao"])
    router.register_intent_pattern("customer_to_bank", ["customer", "transfer", "money", "bank"])
    router.register_intent_pattern("bank_to_customer", ["bank", "transfer", "money", "customer"])
    return router


def test_role_canonicalization_ignores_surface_connectors_and_preserves_direction():
    router = _router()
    forward = router.resolve_text("cliente transfere dinheiro para o banco")
    reverse = router.resolve_text("o banco transfere dinheiro para o cliente")
    assert forward.canonical_roles == ("customer", "transfer", "money", "bank")
    assert reverse.canonical_roles == ("bank", "transfer", "money", "customer")
    assert forward.concept_id == "customer_to_bank"
    assert reverse.concept_id == "bank_to_customer"


def test_role_canonicalization_generalizes_across_registered_synonyms():
    router = _router()
    cases = [
        ("comprador envia pagamento para instituicao", "customer_to_bank"),
        ("usuario remete valor ao banco", "customer_to_bank"),
        ("instituicao envia pagamento ao comprador", "bank_to_customer"),
        ("banco remete valor para usuario", "bank_to_customer"),
    ]
    for text, expected in cases:
        result = router.resolve_text(text)
        assert result.concept_id == expected


def test_role_canonicalization_abstains_when_action_role_is_missing():
    router = _router()
    result = router.resolve_text("cliente visita banco")
    assert result.concept_id is None
