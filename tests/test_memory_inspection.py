from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.memory_inspection import MemoryInspectionService
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex


def test_inspection_exposes_generative_space_without_factual_authority():
    core = EvidenceCore()
    provenance = MemoryProvenanceIndex(core)
    provenance.register("g1", source_type="assistant_generated", created_order=1, namespace="s")

    payload = MemoryInspectionService(provenance).inspect("g1", namespace="s")

    assert payload["memory_space"] == "generative"
    assert payload["factual_active"] is False
    assert payload["active_ultimate_source_memory_id"] is None


def test_inspection_preserves_direct_space_and_reports_factual_lineage_for_echo():
    core = EvidenceCore()
    provenance = MemoryProvenanceIndex(core)
    provenance.register("u1", source_type="user_assertion", created_order=1, namespace="s")
    provenance.register(
        "g1",
        source_type="assistant_generated",
        parent_memory_ids=("u1",),
        created_order=2,
        namespace="s",
    )

    payload = MemoryInspectionService(provenance).inspect("g1", namespace="s")

    assert payload["memory_space"] == "generative"
    assert payload["factual_active"] is True
    assert payload["active_ultimate_source_memory_id"] == "u1"
    assert payload["active_ultimate_source_type"] == "user_assertion"
