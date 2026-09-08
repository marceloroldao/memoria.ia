from memoria_resolutiva.context_compiler import ContextCompiler
from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.evidence_temporal_bridge import EvidenceTemporalBridge
from memoria_resolutiva.topological_memory import AddressSpace, TemporalEventStore


def _shirt_runtime():
    evidence = EvidenceCore()
    evidence.observe_relation(
        "minha camisa",
        "cor",
        "azul",
        evidence_id="u1",
        source_text="Minha camisa é azul e esta frase bruta não deve ir para a LLM.",
        provenance="USER_CONFIRMED",
        origin="user",
        confidence=1.0,
    )
    evidence.observe_relation(
        "minha camisa",
        "cor",
        "vermelha",
        evidence_id="llm1",
        source_text="Texto bruto da LLM que também não deve ir para o pacote.",
        provenance="LLM_GENERATED",
        origin="assistant",
        confidence=0.99,
    )
    evidence.observe_relation(
        "minha camisa",
        "cor",
        "preta",
        evidence_id="u2",
        source_text="Agora minha camisa é preta.",
        provenance="USER_CONFIRMED",
        origin="user",
        confidence=1.0,
    )
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    bridge = EvidenceTemporalBridge(addresses, store)
    bridge.project_history(evidence)
    return addresses, store, bridge


def test_current_packet_contains_only_authoritative_compiled_fact():
    _addresses, store, bridge = _shirt_runtime()
    compiler = ContextCompiler(store, projections=bridge.iter_projections())

    packet = compiler.compile("Qual é a cor da minha camisa?")

    assert packet.operator == "CURRENT"
    assert packet.subject == "minha camisa"
    assert packet.attribute == "cor"
    assert len(packet.facts) == 1
    fact = packet.facts[0]
    assert fact.value == "preta"
    assert fact.source == "USER_CONFIRMED"
    assert fact.evidence_id == "u2"
    assert fact.confidence == 1.0
    assert all(item.evidence_id != "llm1" for item in packet.facts)


def test_packet_never_contains_raw_memory_or_quarantined_llm_text():
    _addresses, store, bridge = _shirt_runtime()
    compiler = ContextCompiler(store, projections=bridge.iter_projections())

    encoded = compiler.compile("Qual é a cor da minha camisa?").to_json()

    assert "frase bruta" not in encoded
    assert "Texto bruto da LLM" not in encoded
    assert "vermelha" not in encoded
    assert "llm1" not in encoded
    assert "preta" in encoded


def test_history_packet_is_bounded_and_reports_omissions():
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    for index in range(1, 11):
        store.observe_state("sensor sala", "temperatura", str(20 + index), sequence=index)
    compiler = ContextCompiler(store, max_history=3)

    packet = compiler.compile("Qual o histórico da temperatura do sensor sala?")

    assert [fact.sequence for fact in packet.facts] == [8, 9, 10]
    assert [fact.value for fact in packet.facts] == ["28", "29", "30"]
    assert packet.omitted_history_count == 7
    assert packet.candidate_sequences == (8, 9, 10)
    assert packet.omitted_candidate_count == 7


def test_state_diff_packet_is_bounded_and_structural():
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    for sequence, color in ((1, "azul"), (2, "preta"), (3, "branca"), (4, "verde")):
        store.observe_state("meu carro", "cor", color, sequence=sequence)
    compiler = ContextCompiler(store, max_history=2)

    packet = compiler.compile("O que mudou na cor do meu carro?")

    assert packet.operator == "STATE_DIFF"
    assert [(item.from_value, item.to_value) for item in packet.transitions] == [
        ("preta", "branca"),
        ("branca", "verde"),
    ]
    assert packet.omitted_history_count == 1
    assert {fact.sequence for fact in packet.facts} == {2, 3, 4}


def test_existed_query_compiles_boolean_and_matching_fact():
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    store.observe_state("minha camisa", "cor", "azul", sequence=12)
    store.observe_state("minha camisa", "cor", "preta", sequence=24)
    compiler = ContextCompiler(store)

    packet = compiler.compile("Minha camisa já foi azul?")

    assert packet.operator == "EXISTED_IN_HISTORY"
    assert packet.exists is True
    assert packet.requested_value == "azul"
    assert len(packet.facts) == 1
    assert packet.facts[0].sequence == 12
    assert packet.facts[0].value == "azul"


def test_compiler_is_read_only():
    _addresses, store, bridge = _shirt_runtime()
    compiler = ContextCompiler(store, projections=bridge.iter_projections())
    before_events = store.iter_events()
    before_transitions = store.iter_transitions()

    compiler.compile("Qual era a cor da minha camisa?")

    assert store.iter_events() == before_events
    assert store.iter_transitions() == before_transitions


def test_compiler_rejects_unbounded_or_empty_inputs():
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)

    try:
        ContextCompiler(store, max_history=0)
        assert False, "expected ValueError"
    except ValueError:
        pass

    compiler = ContextCompiler(store)
    try:
        compiler.compile("   ")
        assert False, "expected ValueError"
    except ValueError:
        pass
