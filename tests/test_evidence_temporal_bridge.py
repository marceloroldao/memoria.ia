from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.evidence_temporal_bridge import (
    EpistemicPromotionPolicy,
    EpistemicSource,
    EvidenceTemporalBridge,
)
from memoria_resolutiva.topological_memory import AddressSpace, TemporalEventStore, TemporalOperator


def _runtime():
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    bridge = EvidenceTemporalBridge(addresses, store)
    return addresses, store, bridge


def test_user_confirmed_evidence_promotes_to_temporal_state():
    evidence = EvidenceCore()
    edge = evidence.observe_relation(
        "minha camisa",
        "cor",
        "azul",
        evidence_id="u1",
        source_text="Minha camisa é azul.",
        provenance="USER_CONFIRMED",
        origin="user",
        confidence=1.0,
    )
    addresses, store, bridge = _runtime()

    projection = bridge.project_edge(edge)

    assert projection.promoted is True
    assert projection.epistemic_source is EpistemicSource.USER_CONFIRMED
    result = store.resolve("minha camisa", "cor", TemporalOperator.CURRENT)
    assert store.value_text(result.value_address) == "azul"
    assert projection.temporal_event is not None
    assert projection.temporal_event.source == "USER_CONFIRMED"
    assert addresses.reconstruct_raw(projection.temporal_event.raw_memory_address) == "Minha camisa é azul."


def test_llm_generated_conflict_never_changes_current_or_history():
    evidence = EvidenceCore()
    evidence.observe_relation(
        "minha camisa",
        "cor",
        "azul",
        evidence_id="u1",
        source_text="Minha camisa é azul.",
        provenance="USER_CONFIRMED",
        origin="user",
    )
    evidence.observe_relation(
        "minha camisa",
        "cor",
        "vermelha",
        evidence_id="llm1",
        source_text="Sua camisa provavelmente é vermelha.",
        provenance="LLM_GENERATED",
        origin="assistant",
        confidence=0.99,
    )
    _addresses, store, bridge = _runtime()

    batch = bridge.project_history(evidence)

    assert len(batch.promoted) == 1
    assert len(batch.quarantined) == 1
    assert batch.quarantined[0].epistemic_source is EpistemicSource.LLM_GENERATED
    current = store.resolve("minha camisa", "cor", TemporalOperator.CURRENT)
    history = store.resolve("minha camisa", "cor", TemporalOperator.HISTORY)
    assert store.value_text(current.value_address) == "azul"
    assert [store.value_text(address) for _, address in history.history] == ["azul"]


def test_llm_source_cannot_be_enabled_even_if_custom_policy_lists_it():
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    policy = EpistemicPromotionPolicy(promotable_sources=(EpistemicSource.LLM_GENERATED,))
    bridge = EvidenceTemporalBridge(addresses, store, policy=policy)
    evidence = EvidenceCore()
    edge = evidence.observe_relation(
        "servidor",
        "ip",
        "10.0.0.2",
        evidence_id="llm2",
        source_text="O servidor deve estar em 10.0.0.2.",
        provenance="LLM_GENERATED",
        origin="local_llm",
    )

    projection = bridge.project_edge(edge)

    assert projection.promoted is False
    assert tuple(store.iter_events()) == ()


def test_external_public_and_derived_are_quarantined_by_default():
    evidence = EvidenceCore()
    public = evidence.observe_relation(
        "produto x",
        "preço",
        "100",
        evidence_id="web1",
        source_text="Página pública informa preço 100.",
        provenance="EXTERNAL_PUBLIC",
        origin="web",
    )
    derived = evidence.observe_relation(
        "produto x",
        "preço_com_imposto",
        "120",
        evidence_id="d1",
        source_text="Preço derivado por cálculo.",
        provenance="DERIVED",
        origin="computed",
    )
    _addresses, store, bridge = _runtime()

    p1 = bridge.project_edge(public)
    p2 = bridge.project_edge(derived)

    assert p1.promoted is False
    assert p2.promoted is False
    assert tuple(store.iter_events()) == ()


def test_sensor_observation_can_advance_temporal_state():
    evidence = EvidenceCore()
    evidence.observe_relation(
        "sensor sala",
        "temperatura",
        "25",
        evidence_id="s1",
        source_text="sensor sala temperatura 25",
        provenance="SENSOR_OBSERVED",
        origin="telemetry",
    )
    evidence.observe_relation(
        "sensor sala",
        "temperatura",
        "26",
        evidence_id="s2",
        source_text="sensor sala temperatura 26",
        provenance="SENSOR_OBSERVED",
        origin="device",
    )
    _addresses, store, bridge = _runtime()

    batch = bridge.project_history(evidence)

    assert len(batch.promoted) == 2
    current = store.resolve("sensor sala", "temperatura", TemporalOperator.CURRENT)
    previous = store.resolve("sensor sala", "temperatura", TemporalOperator.PREVIOUS_STATE)
    assert store.value_text(current.value_address) == "26"
    assert store.value_text(previous.value_address) == "25"


def test_unknown_provenance_fails_closed_as_system_inferred():
    evidence = EvidenceCore()
    edge = evidence.observe_relation(
        "robô",
        "posição",
        "A3",
        evidence_id="x1",
        source_text="posição estimada A3",
        provenance="mystery-source",
        origin="unknown-engine",
    )
    _addresses, store, bridge = _runtime()

    projection = bridge.project_edge(edge)

    assert projection.epistemic_source is EpistemicSource.SYSTEM_INFERRED
    assert projection.promoted is False
    assert tuple(store.iter_events()) == ()


def test_confidence_threshold_applies_to_promotable_sources():
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    bridge = EvidenceTemporalBridge(
        addresses,
        store,
        policy=EpistemicPromotionPolicy(min_confidence=0.9),
    )
    evidence = EvidenceCore()
    edge = evidence.observe_relation(
        "meu carro",
        "cor",
        "preto",
        evidence_id="u-low",
        source_text="Meu carro é preto.",
        provenance="USER_CONFIRMED",
        origin="user",
        confidence=0.5,
    )

    projection = bridge.project_edge(edge)

    assert projection.promoted is False
    assert tuple(store.iter_events()) == ()


def test_duplicate_evidence_id_is_idempotent_for_temporal_projection():
    evidence = EvidenceCore()
    edge = evidence.observe_relation(
        "meu gato",
        "nome",
        "Alt",
        evidence_id="cat1",
        source_text="Meu gato se chama Alt.",
        provenance="USER_CONFIRMED",
        origin="user",
    )
    _addresses, store, bridge = _runtime()

    first = bridge.project_edge(edge)
    second = bridge.project_edge(edge)

    assert first.promoted is True
    assert second.promoted is False
    assert len(store.iter_events()) == 1
