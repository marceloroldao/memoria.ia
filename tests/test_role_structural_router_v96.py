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
            "depositante envia quantia agencia",
            "cliente transfere quantia agencia",
            "depositante remete pagamento banco",
            "banco envia pagamento cliente",
            "instituicao transfere dinheiro comprador",
            "agencia envia quantia depositante",
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


def test_role_canonicalization_inherits_unregistered_roles_from_context():
    router = _router()
    assert "depositante" not in router._exact_roles
    assert "quantia" not in router._exact_roles
    assert "agencia" not in router._exact_roles

    forward = router.resolve_text("depositante remete quantia para agencia")
    reverse = router.resolve_text("agencia remete quantia para depositante")

    assert forward.canonical_roles == ("customer", "transfer", "money", "bank")
    assert reverse.canonical_roles == ("bank", "transfer", "money", "customer")
    assert forward.concept_id == "customer_to_bank"
    assert reverse.concept_id == "bank_to_customer"
    assert any(item.source == "context_joint" for item in forward.role_evidence)


def test_context_aliases_can_be_locally_ambiguous_and_require_joint_structure():
    router = _router()
    rankings = {
        token: [item.role_id for item in router._rank_role_candidates(token)]
        for token in ("depositante", "quantia", "agencia")
    }
    assert rankings["depositante"][0] == "customer", rankings
    assert "money" in rankings["quantia"], rankings
    assert rankings["quantia"][0] != "money", rankings
    assert "bank" in rankings["agencia"], rankings
    assert rankings["agencia"][0] != "bank", rankings


def test_role_canonicalization_abstains_when_action_role_is_missing():
    router = _router()
    result = router.resolve_text("cliente visita banco")
    assert result.concept_id is None


def test_role_structural_router_tolerates_neutral_surface_noise_without_changing_direction():
    router = _router()
    forward = router.resolve_text("hoje cliente realmente transfere dinheiro com cuidado para o banco")
    reverse = router.resolve_text("ontem o banco calmamente transfere dinheiro de volta para o cliente")
    assert forward.concept_id == "customer_to_bank"
    assert reverse.concept_id == "bank_to_customer"
    assert forward.canonical_roles == ("customer", "transfer", "money", "bank")
    assert reverse.canonical_roles == ("bank", "transfer", "money", "customer")


def test_role_structural_router_rejects_reordered_or_duplicated_role_sequences():
    router = _router()
    adversarial = [
        "cliente dinheiro transfere banco",
        "cliente transfere banco dinheiro",
        "cliente cliente transfere dinheiro banco",
        "cliente transfere dinheiro banco cliente",
        "banco dinheiro transfere cliente",
    ]
    for text in adversarial:
        result = router.resolve_text(text)
        assert result.concept_id is None, (text, result.canonical_roles, result.concept_id, result.score)


def test_role_structural_router_rejects_context_alias_reordering_without_relabeling_to_fit():
    router = _router()
    adversarial = [
        "depositante quantia remete agencia",
        "agencia quantia remete depositante",
        "quantia remete depositante agencia",
    ]
    for text in adversarial:
        result = router.resolve_text(text)
        assert result.concept_id is None, (
            text,
            result.canonical_roles,
            result.concept_id,
            result.score,
            result.role_evidence,
        )


def test_role_structural_router_rejects_known_entities_with_wrong_relation():
    router = _router()
    adversarial = [
        "cliente consulta saldo banco",
        "cliente visita banco com dinheiro",
        "banco informa valor cliente",
        "cliente guarda dinheiro perto banco",
    ]
    for text in adversarial:
        result = router.resolve_text(text)
        assert result.concept_id is None, (text, result.canonical_roles, result.concept_id, result.score)


def test_role_structural_router_does_not_force_fit_unseen_noise_into_known_pattern():
    router = _router()
    adversarial = [
        "astronauta observa planeta distante",
        "sensor mede temperatura ambiente",
        "motor gira eixo lentamente",
        "professor explica conceito aluno",
    ]
    for text in adversarial:
        result = router.resolve_text(text)
        assert result.concept_id is None, (text, result.canonical_roles, result.concept_id, result.score)


def test_role_structural_router_does_not_borrow_length_from_another_intent():
    router = _router()
    router.register_intent_pattern(
        "bank_to_customer_with_receipt",
        ["bank", "transfer", "money", "customer", "money"],
    )

    result = router.resolve_text("cliente cliente transfere dinheiro banco")

    assert result.concept_id is None, (
        result.canonical_roles,
        result.concept_id,
        result.score,
    )
