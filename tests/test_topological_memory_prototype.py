from memoria_resolutiva.topological_memory import (
    AddressSpace,
    TemporalEventStore,
    TemporalOperator,
)


def _value(store: TemporalEventStore, result) -> str | None:
    return store.value_text(result.value_address)


def test_phase_a_reuses_word_address_and_preserves_raw_provenance():
    addresses = AddressSpace()

    first = addresses.ingest_text("Hoje acordei às 18h30.")
    acordar_first = addresses.resolve("word", "acordei")
    assert acordar_first is not None
    first_address = acordar_first.address

    second = addresses.ingest_text("Acordei de bom humor.")
    acordar_second = addresses.resolve("word", "ACORDEI")
    assert acordar_second is not None

    assert acordar_second.address == first_address
    assert acordar_second.occurrences == 2
    assert first.raw_memory_address != second.raw_memory_address
    assert addresses.reconstruct_raw(first.raw_memory_address) == "Hoje acordei às 18h30."
    assert addresses.reconstruct_raw(second.raw_memory_address) == "Acordei de bom humor."
    assert second.reused_nodes > 0
    assert addresses.metrics()["duplicate_address_count"] == 0


def test_phase_a_word_composition_is_reconstructable_from_symbol_addresses():
    addresses = AddressSpace()
    addresses.ingest_text("Hoje")

    hoje = addresses.resolve("word", "hoje")
    assert hoje is not None
    symbols = [addresses.node(address).canonical_value for address in hoje.components]
    assert symbols == ["h", "o", "j", "e"]

    ho = addresses.resolve("fragment", "ho")
    hoj = addresses.resolve("fragment", "hoj")
    assert ho is not None
    assert hoj is not None
    assert hoje.address in addresses.node(hoje.components[0]).edges_in


def test_phase_b_sequence_is_occurrence_metadata_not_node_identity():
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)

    e12 = store.observe_state("minha camisa", "cor", "azul", sequence=12)
    e24 = store.observe_state("minha camisa", "cor", "preta", sequence=24)
    e31 = store.observe_state("minha camisa", "cor", "branca", sequence=31)

    assert [e.sequence for e in (e12, e24, e31)] == [12, 24, 31]
    azul = addresses.resolve("value", "azul")
    assert azul is not None
    assert azul.address == e12.value_address
    assert azul.occurrences == 1
    assert store.metrics()["events_created"] == 3


def test_phase_c_creates_transitions_without_destroying_history():
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    store.observe_state("minha camisa", "cor", "azul", sequence=12)
    store.observe_state("minha camisa", "cor", "preta", sequence=24)
    store.observe_state("minha camisa", "cor", "branca", sequence=31)

    result = store.resolve("minha camisa", "cor", TemporalOperator.STATE_DIFF)
    assert [store.value_text(value) for _, value in result.history] == ["azul", "preta", "branca"]
    assert [(t.from_sequence, t.to_sequence) for t in result.transitions] == [(12, 24), (24, 31)]
    assert [
        (store.value_text(t.from_value_address), store.value_text(t.to_value_address))
        for t in result.transitions
    ] == [("azul", "preta"), ("preta", "branca")]


def test_phase_d_temporal_operators_resolve_deterministically():
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    store.observe_state("minha camisa", "cor", "azul", sequence=12)
    store.observe_state("minha camisa", "cor", "preta", sequence=24)
    store.observe_state("minha camisa", "cor", "branca", sequence=31)

    assert _value(store, store.resolve("minha camisa", "cor", TemporalOperator.CURRENT)) == "branca"
    assert _value(store, store.resolve("minha camisa", "cor", TemporalOperator.PREVIOUS_STATE)) == "preta"
    assert _value(store, store.resolve("minha camisa", "cor", TemporalOperator.FIRST_STATE)) == "azul"

    existed = store.resolve("minha camisa", "cor", TemporalOperator.EXISTED_IN_HISTORY, value="azul")
    assert existed.exists is True
    assert existed.sequence == 12

    before = store.resolve("minha camisa", "cor", TemporalOperator.STATE_BEFORE_VALUE, value="preta")
    assert _value(store, before) == "azul"
    assert before.sequence == 12

    after = store.resolve("minha camisa", "cor", TemporalOperator.STATE_AFTER_VALUE, value="preta")
    assert _value(store, after) == "branca"
    assert after.sequence == 31


def test_phase_e_same_engine_generalizes_across_domains():
    cases = [
        ("meu carro", "cor", ("preto", "azul")),
        ("sensor sala", "temperatura", ("21", "23")),
        ("servidor principal", "ip", ("10.0.0.1", "10.0.0.2")),
        ("robo 1", "position", ("A", "B")),
        ("meu gato", "nome", ("Alt", "Altair")),
    ]
    for subject, attribute, values in cases:
        addresses = AddressSpace()
        store = TemporalEventStore(addresses)
        store.observe_state(subject, attribute, values[0])
        store.observe_state(subject, attribute, values[1])
        current = store.resolve(subject, attribute, TemporalOperator.CURRENT)
        previous = store.resolve(subject, attribute, TemporalOperator.PREVIOUS_STATE)
        assert _value(store, current) == values[1].casefold()
        assert _value(store, previous) == values[0].casefold()


def test_sequence_rejects_backward_occurrence_order():
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    store.observe_state("sensor", "temperatura", "20", sequence=10)

    try:
        store.observe_state("sensor", "temperatura", "19", sequence=9)
    except ValueError as exc:
        assert "monotonic" in str(exc)
    else:
        raise AssertionError("backward sequence must be rejected")
