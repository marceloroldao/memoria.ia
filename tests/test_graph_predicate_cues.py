from __future__ import annotations

from types import SimpleNamespace

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.graph_predicate_cues import (
    resolve_graph_predicate_cues,
    resolve_graph_semantic_cues,
)


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


def _core_with_generic_semantics(namespace: str) -> EvidenceCore:
    core = EvidenceCore()
    for predicate, evidence_id in (
        ("tipo_de", "role-type"),
        ("tecnologia_de", "role-tech"),
        ("modelo_de", "role-model"),
        ("estágio_de", "role-stage"),
    ):
        core.observe_relation(
            predicate,
            "semantic_role",
            "concept",
            evidence_id=evidence_id,
            source_text=f"{predicate} expande conceitos.",
            namespace=namespace,
        )
    core.observe_relation(
        "ONU",
        "tipo_de",
        "equipamento",
        evidence_id="sem-onu",
        source_text="ONU é um tipo de equipamento.",
        namespace=namespace,
    )
    core.observe_relation(
        "EPON",
        "tecnologia_de",
        "rede",
        evidence_id="sem-epon",
        source_text="EPON é tecnologia de rede.",
        namespace=namespace,
    )
    core.observe_relation(
        "RB5009",
        "modelo_de",
        "roteador",
        evidence_id="sem-rb",
        source_text="RB5009 é modelo de roteador.",
        namespace=namespace,
    )
    core.observe_relation(
        "filhote",
        "estágio_de",
        "gato",
        evidence_id="sem-kitten",
        source_text="Filhote é estágio de gato.",
        namespace=namespace,
    )
    return core


def test_graph_declared_semantic_roles_expand_concepts_without_domain_table():
    namespace = "profile:app:u"
    resolver = EvidenceResolver(_core_with_generic_semantics(namespace))

    onu = resolve_graph_semantic_cues(
        resolver,
        message="A ONU caiu",
        session_id=namespace,
        ignored_terms=frozenset({"a", "caiu"}),
    )
    epon = resolve_graph_semantic_cues(
        resolver,
        message="EPON está instável",
        session_id=namespace,
        ignored_terms=frozenset({"esta", "está", "instável"}),
    )
    router = resolve_graph_semantic_cues(
        resolver,
        message="RB5009 reiniciou",
        session_id=namespace,
        ignored_terms=frozenset({"reiniciou"}),
    )
    kitten = resolve_graph_semantic_cues(
        resolver,
        message="O filhote dormiu",
        session_id=namespace,
        ignored_terms=frozenset({"o", "dormiu"}),
    )

    assert onu.concept_terms == ("equipamento",)
    assert epon.concept_terms == ("rede",)
    assert router.concept_terms == ("roteador",)
    assert kitten.concept_terms == ("gato",)
    assert onu.predicate_terms == ()


def test_semantic_role_itself_is_persisted_and_contributes_provenance():
    namespace = "profile:app:u"
    resolver = EvidenceResolver(_core_with_generic_semantics(namespace))

    result = resolve_graph_semantic_cues(
        resolver,
        message="ONU com problema",
        session_id=namespace,
        ignored_terms=frozenset({"com", "problema"}),
    )

    assert result.concept_terms == ("equipamento",)
    assert "sem-onu" in result.memory_ids
    assert "role-type" in result.memory_ids


def test_relation_without_declared_semantic_role_does_not_expand_concept():
    namespace = "profile:app:u"
    core = EvidenceCore()
    core.observe_relation(
        "ONU",
        "related_to",
        "equipamento",
        evidence_id="ordinary-link",
        source_text="ONU relacionada a equipamento.",
        namespace=namespace,
    )
    resolver = EvidenceResolver(core)

    result = resolve_graph_semantic_cues(
        resolver,
        message="ONU falhou",
        session_id=namespace,
        ignored_terms=frozenset({"falhou"}),
    )

    assert result.concept_terms == ()
    assert result.predicate_terms == ()


def test_declared_predicate_role_generalizes_beyond_unit_of():
    namespace = "profile:app:u"
    core = EvidenceCore()
    core.observe_relation(
        "mede",
        "semantic_role",
        "predicate",
        evidence_id="role-measure",
        source_text="mede orienta predicados.",
        namespace=namespace,
    )
    core.observe_relation(
        "rpm",
        "mede",
        "rotação",
        evidence_id="sem-rpm",
        source_text="RPM mede rotação.",
        namespace=namespace,
    )
    resolver = EvidenceResolver(core)

    result = resolve_graph_semantic_cues(
        resolver,
        message="Quantos rpm tem meu motor?",
        session_id=namespace,
        target="motor",
        ignored_terms=frozenset({"quantos", "tem", "meu"}),
    )

    assert result.predicate_terms == ("rotação",)
    assert result.concept_terms == ()
    assert "role-measure" in result.memory_ids
    assert "sem-rpm" in result.memory_ids
