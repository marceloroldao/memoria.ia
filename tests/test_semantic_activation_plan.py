import pytest

from memoria_resolutiva.semantic_activation_plan import plan_activation_concepts


def test_base_concept_keeps_precedence_and_semantic_concept_fills_remaining_slot():
    assert plan_activation_concepts(("ONU",), ("equipamento",), max_concepts=2) == (
        "ONU",
        "equipamento",
    )


def test_semantic_concepts_do_not_expand_existing_two_concept_budget():
    assert plan_activation_concepts(("EPON", "OLT"), ("rede", "equipamento"), max_concepts=2) == (
        "EPON",
        "OLT",
    )


def test_duplicate_semantic_concept_does_not_consume_budget_twice():
    assert plan_activation_concepts(("roteador",), ("Roteador", "rede"), max_concepts=2) == (
        "roteador",
        "rede",
    )


def test_matching_is_accent_insensitive():
    assert plan_activation_concepts(("estágio",), ("estagio", "gato"), max_concepts=2) == (
        "estágio",
        "gato",
    )


def test_domain_is_not_encoded_in_planner():
    assert plan_activation_concepts(("qualquer-coisa",), ("conceito-novo",), max_concepts=2) == (
        "qualquer-coisa",
        "conceito-novo",
    )


def test_invalid_budget_is_rejected():
    with pytest.raises(ValueError):
        plan_activation_concepts(("ONU",), ("equipamento",), max_concepts=0)
