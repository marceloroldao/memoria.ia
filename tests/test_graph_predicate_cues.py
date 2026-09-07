from __future__ import annotations

from types import SimpleNamespace

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.graph_predicate_cues import resolve_graph_predicate_cues


class EvidenceResolver:
    def __init__(self, core: EvidenceCore):
        self.evidence = SimpleNamespace(core=core)


def _core_with_units(namespace: str) -> EvidenceCore:
    core = EvidenceCore()
    core.observe_relation(
        "volt",
        "unidade_de",
        "tensão",
        evidence_id="unit-volt",
        source_text="Volt é unidade de tensão.",
        namespace=namespace,
    )
    core.observe_relation(
        "ampere",
        "unidade_de",
        "corrente",
        evidence_id="unit-ampere",
        source_text="Ampere é unidade de corrente.",
        namespace=namespace,
    )
    core.observe_relation(
        "Celsius",
        "unidade_de",
        "temperatura",
        evidence_id="unit-celsius",
        source_text="Celsius é unidade de temperatura.",
        namespace=namespace,
    )
    return core


def test_graph_cue_resolves_plural_unit_without_builtin_unit_table():
    namespace = "profile:app:u"
    resolver = EvidenceResolver(_core_with_units(namespace))

    result = resolve_graph_predicate_cues(
        resolver,
        message="Com quantos volts está minha bateria?",
        session_id=namespace,
        target="bateria",
        ignored_terms=frozenset({"com", "quantos", "esta", "está", "minha"}),
    )

    assert result.terms == ("tensão",)
    assert result.memory_ids == ("unit-volt",)


def test_graph_cues_generalize_to_other_measurements():
    namespace = "profile:app:u"
    resolver = EvidenceResolver(_core_with_units(namespace))

    current = resolve_graph_predicate_cues(
        resolver,
        message="Quantos amperes tem meu motor?",
        session_id=namespace,
        target="motor",
        ignored_terms=frozenset({"quantos", "tem", "meu"}),
    )
    temperature = resolve_graph_predicate_cues(
        resolver,
        message="Em Celsius, como está meu sensor?",
        session_id=namespace,
        target="sensor",
        ignored_terms=frozenset({"em", "como", "esta", "está", "meu"}),
    )

    assert current.terms == ("corrente",)
    assert temperature.terms == ("temperatura",)


def test_unrelated_relation_is_not_treated_as_predicate_cue():
    namespace = "profile:app:u"
    core = EvidenceCore()
    core.observe_relation(
        "volts",
        "related_to",
        "tensão",
        evidence_id="not-a-cue",
        source_text="Volts relacionado a tensão.",
        namespace=namespace,
    )
    resolver = EvidenceResolver(core)

    result = resolve_graph_predicate_cues(
        resolver,
        message="Quantos volts tem minha bateria?",
        session_id=namespace,
        target="bateria",
        ignored_terms=frozenset({"quantos", "tem", "minha"}),
    )

    assert result.terms == ()
    assert result.memory_ids == ()


def test_cue_respects_namespace_isolation():
    core = _core_with_units("profile:app:user-a")
    resolver = EvidenceResolver(core)

    result = resolve_graph_predicate_cues(
        resolver,
        message="Quantos volts tem minha bateria?",
        session_id="profile:app:user-b",
        target="bateria",
        ignored_terms=frozenset({"quantos", "tem", "minha"}),
    )

    assert result.terms == ()


class NativeCueResolver:
    def activate_relations(self, **kwargs):
        concept = kwargs["concept"]
        if concept.casefold() not in {"volts", "volt"}:
            return {"status": "UNRESOLVED", "confidence": 0.0, "selected_context": "", "relations": []}
        return {
            "status": "HIT",
            "confidence": 1.0,
            "selected_context": "volt | unidade_de | tensão",
            "relations": [
                {
                    "subject_key": "volt",
                    "object_key": "tensão",
                    "evidence_id": "native-unit-volt",
                }
            ],
        }


def test_graph_cue_uses_native_activation_contract_when_available():
    result = resolve_graph_predicate_cues(
        NativeCueResolver(),
        message="Quantos volts tem minha bateria?",
        session_id="profile:app:u",
        target="bateria",
        ignored_terms=frozenset({"quantos", "tem", "minha"}),
    )

    assert result.terms == ("tensão",)
    assert result.memory_ids == ("native-unit-volt",)
