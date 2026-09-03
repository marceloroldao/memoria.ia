from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.factual_recompute import FactualIncrementalRecompute


def test_correction_recomputes_only_affected_derivations_and_versions_provenance():
    core = EvidenceCore()
    system = FactualIncrementalRecompute(core)
    system.add_root("price", 10.0, memory_id="price-v1", namespace="s")
    system.add_root("tax", 0.2, memory_id="tax-v1", namespace="s")
    system.add_derived(
        "gross",
        ["price", "tax"],
        memory_id="gross-v1",
        combine=lambda xs: xs[0] * (1.0 + xs[1]),
        namespace="s",
    )
    system.add_derived(
        "label",
        ["tax"],
        memory_id="label-v1",
        namespace="s",
    )

    revisions = system.correct_root(
        "price",
        20.0,
        new_memory_id="price-v2",
        namespace="s",
    )

    assert system.graph.nodes["gross"].value == 24.0
    assert system.graph.nodes["label"].value == 0.2
    assert [r.node_id for r in revisions] == ["gross"]

    gross_v2 = system.memory_ids["gross"]
    assert gross_v2.startswith("gross-v1:recompute:")
    assert system.provenance.inspect("price-v1", namespace="s").superseded_by == "price-v2"
    assert system.provenance.inspect("gross-v1", namespace="s").superseded_by == gross_v2
    assert system.provenance.inspect(gross_v2, namespace="s").parent_memory_ids == ("price-v2", "tax-v1")
    assert system.provenance.factual_ultimate_source(gross_v2, namespace="s") is not None
    assert system.provenance.factual_ultimate_source("gross-v1", namespace="s") is None


def test_downstream_recompute_uses_newly_versioned_parent_memory():
    core = EvidenceCore()
    system = FactualIncrementalRecompute(core)
    system.add_root("a", 2.0, memory_id="a-v1", namespace="s")
    system.add_derived("b", ["a"], memory_id="b-v1", combine=lambda xs: xs[0] * 2, namespace="s")
    system.add_derived("c", ["b"], memory_id="c-v1", combine=lambda xs: xs[0] + 1, namespace="s")

    revisions = system.correct_root("a", 5.0, new_memory_id="a-v2", namespace="s")

    assert [r.node_id for r in revisions] == ["b", "c"]
    assert system.graph.nodes["b"].value == 10.0
    assert system.graph.nodes["c"].value == 11.0
    b_v2 = system.memory_ids["b"]
    c_v2 = system.memory_ids["c"]
    assert system.provenance.inspect(b_v2, namespace="s").parent_memory_ids == ("a-v2",)
    assert system.provenance.inspect(c_v2, namespace="s").parent_memory_ids == (b_v2,)
