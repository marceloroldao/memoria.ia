import pytest

from memoria_resolutiva.temporal_query_resolver import TemporalQueryResolver
from memoria_resolutiva.topological_memory import AddressSpace, TemporalEventStore, TemporalOperator


def _shirt_store():
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    store.observe_state("minha camisa", "cor", "azul", sequence=12)
    store.observe_state("minha camisa", "cor", "preta", sequence=24)
    store.observe_state("minha camisa", "cor", "branca", sequence=31)
    return store, TemporalQueryResolver(store)


def _value(store, resolution):
    return store.value_text(resolution.result.value_address)


def test_acceptance_current_previous_history_before_and_diff_without_llm():
    store, resolver = _shirt_store()

    current = resolver.resolve("Qual é a cor da minha camisa?")
    assert current.plan.operator is TemporalOperator.CURRENT
    assert current.plan.subject == "minha camisa"
    assert current.plan.attribute == "cor"
    assert _value(store, current) == "branca"
    assert current.result.sequence == 31

    previous = resolver.resolve("Qual era a cor da minha camisa?")
    assert previous.plan.operator is TemporalOperator.PREVIOUS_STATE
    assert _value(store, previous) == "preta"
    assert previous.result.sequence == 24

    existed = resolver.resolve("Minha camisa já foi azul?")
    assert existed.plan.operator is TemporalOperator.EXISTED_IN_HISTORY
    assert existed.plan.value == "azul"
    assert existed.result.exists is True
    assert existed.result.sequence == 12

    before = resolver.resolve("Qual era a cor antes de ficar preta?")
    assert before.plan.operator is TemporalOperator.STATE_BEFORE_VALUE
    assert before.plan.subject == "minha camisa"  # inferred from unique cor+preta slot
    assert before.plan.value == "preta"
    assert _value(store, before) == "azul"
    assert before.result.sequence == 12

    changed = resolver.resolve("O que mudou na minha camisa?")
    assert changed.plan.operator is TemporalOperator.STATE_DIFF
    assert changed.plan.attribute == "cor"  # inferred from the entity's unique state slot
    assert [store.value_text(value) for _, value in changed.result.history] == ["azul", "preta", "branca"]


def test_first_history_and_after_operators_are_generic():
    store, resolver = _shirt_store()

    first = resolver.resolve("Qual foi a primeira cor conhecida da minha camisa?")
    assert first.plan.operator is TemporalOperator.FIRST_STATE
    assert _value(store, first) == "azul"

    history = resolver.resolve("Qual o histórico da cor da minha camisa?")
    assert history.plan.operator is TemporalOperator.HISTORY
    assert [store.value_text(value) for _, value in history.result.history] == ["azul", "preta", "branca"]

    after = resolver.resolve("Qual a cor depois de ficar preta?")
    assert after.plan.operator is TemporalOperator.STATE_AFTER_VALUE
    assert _value(store, after) == "branca"


def test_same_language_planner_generalizes_from_memory_vocabulary_not_domain_tables():
    cases = [
        ("meu carro", "cor", "preto", "azul", "Qual era a cor do meu carro?", "preto"),
        ("sensor sala", "temperatura", "21", "23", "Qual era a temperatura do sensor sala?", "21"),
        ("servidor principal", "ip", "10.0.0.1", "10.0.0.2", "Qual era o ip do servidor principal?", "10.0.0.1"),
        ("robo 1", "position", "A", "B", "Qual era a position do robo 1?", "a"),
        ("meu gato", "nome", "Alt", "Altair", "Qual era o nome do meu gato?", "alt"),
    ]
    for subject, attribute, old, new, question, expected in cases:
        store = TemporalEventStore(AddressSpace())
        store.observe_state(subject, attribute, old)
        store.observe_state(subject, attribute, new)
        resolution = TemporalQueryResolver(store).resolve(question)
        assert resolution.plan.subject == subject.casefold()
        assert resolution.plan.attribute == attribute.casefold()
        assert _value(store, resolution) == expected


def test_query_ambiguity_fails_closed_instead_of_guessing():
    store = TemporalEventStore(AddressSpace())
    store.observe_state("meu carro", "cor", "azul")
    store.observe_state("minha camisa", "cor", "azul")
    resolver = TemporalQueryResolver(store)

    with pytest.raises(LookupError, match="ambiguous"):
        resolver.resolve("Qual era a cor?")


def test_resolution_trace_exposes_addresses_and_sequence_candidates():
    _, resolver = _shirt_store()
    resolution = resolver.resolve("Qual era a cor da minha camisa?")

    assert len(resolution.plan.activated_addresses) == 2
    assert resolution.plan.candidate_sequences == (12, 24, 31)
