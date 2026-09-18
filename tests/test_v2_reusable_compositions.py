from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.v2_ontogenesis import V2OntogenesisIngestor


def test_recurrent_prefix_promotes_one_reusable_composition_and_keeps_branches():
    core = EvidenceCore()
    ingest = V2OntogenesisIngestor(core, min_composition_support=2)

    first = ingest.observe("Hoje me acordei feliz.", namespace="wake")
    second = ingest.observe("Hoje me acordei triste.", namespace="wake")
    third = ingest.observe("Hoje me acordei feliz.", namespace="wake")

    assert first.compositions == ()
    assert len(second.compositions) == 1
    assert len(third.compositions) >= 1

    shared = ingest._composition_id(("hoje", "me", "acordei"))
    assert shared in second.compositions
    assert shared in third.compositions

    history = core.evidence_history(namespace="wake")
    members = [e.object for e in history if e.subject == shared and e.predicate == ingest.COMPOSITION_MEMBER_PREDICATE]
    assert set(members) == {"0:hoje", "1:me", "2:acordei"}

    next_edges = [e for e in history if e.predicate == ingest.NEXT_PREDICATE]
    assert sum(e.subject == "acordei" and e.object == "feliz" for e in next_edges) == 2
    assert sum(e.subject == "acordei" and e.object == "triste" for e in next_edges) == 1


def test_composition_address_is_content_based_not_occurrence_based():
    a = V2OntogenesisIngestor(EvidenceCore())
    b = V2OntogenesisIngestor(EvidenceCore())
    assert a._composition_id(("hoje", "me", "acordei")) == b._composition_id(("hoje", "me", "acordei"))
    assert a._composition_id(("hoje", "me", "acordei")) != a._composition_id(("hoje", "me", "dormi"))
