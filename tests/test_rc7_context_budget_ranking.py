from types import SimpleNamespace

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.relational_activation import activate


class Resolver:
    def __init__(self, core: EvidenceCore):
        self.evidence = SimpleNamespace(core=core)


def _observe(core, subject, predicate, object_, evidence_id, confidence=1.0, namespace="rc7:d"):
    core.observe_relation(
        subject,
        predicate,
        object_,
        evidence_id=evidence_id,
        source_text=f"{subject} {predicate} {object_}",
        confidence=confidence,
        namespace=namespace,
    )


def test_rc7_exact_min_confidence_boundary_is_inclusive():
    core = EvidenceCore()
    _observe(core, "root", "rel", "edge", "e1", confidence=0.45)

    result = activate(Resolver(core), concept="root", session_id="rc7:d", depth=1, min_confidence=0.45)

    assert result.status == "HIT"
    assert "root | rel | edge" in result.selected_context


def test_rc7_second_hop_decay_boundary_is_enforced_exactly():
    core = EvidenceCore()
    _observe(core, "root", "rel", "mid", "e1", confidence=1.0)
    _observe(core, "mid", "rel_kept", "kept", "e2", confidence=0.625)
    _observe(core, "mid", "rel_dropped", "dropped", "e3", confidence=0.624)

    result = activate(
        Resolver(core),
        concept="root",
        session_id="rc7:d",
        depth=2,
        hop_decay=0.72,
        min_confidence=0.45,
    )

    assert "mid | rel_kept | kept" in result.selected_context
    assert "mid | rel_dropped | dropped" not in result.selected_context


def test_rc7_oversized_relation_does_not_block_smaller_relation():
    core = EvidenceCore()
    _observe(core, "root", "rel_large", "x" * 120, "large", confidence=1.0)
    _observe(core, "root", "rel_small", "ok", "small", confidence=0.9)

    result = activate(Resolver(core), concept="root", session_id="rc7:d", depth=1, budget=32)

    assert result.status == "HIT"
    assert result.selected_context == "root | rel_small | ok"
    assert result.memory_ids == ("small",)


def test_rc7_budget_never_partially_renders_relation_line():
    core = EvidenceCore()
    _observe(core, "root", "predicate", "object", "e1", confidence=1.0)
    full_line = "root | predicate | object"

    too_small = activate(Resolver(core), concept="root", session_id="rc7:d", depth=1, budget=len(full_line) - 1)
    exact = activate(Resolver(core), concept="root", session_id="rc7:d", depth=1, budget=len(full_line))

    assert too_small.status == "UNRESOLVED"
    assert too_small.selected_context == ""
    assert exact.status == "HIT"
    assert exact.selected_context == full_line


def test_rc7_ranking_is_deterministic_under_insertion_order_variation():
    rows = [
        ("root", "zeta", "b", "e2", 0.8),
        ("root", "alpha", "a", "e1", 0.8),
        ("root", "beta", "c", "e3", 0.9),
    ]

    outputs = []
    for sequence in (rows, list(reversed(rows))):
        core = EvidenceCore()
        for subject, predicate, object_, evidence_id, confidence in sequence:
            _observe(core, subject, predicate, object_, evidence_id, confidence)
        result = activate(Resolver(core), concept="root", session_id="rc7:d", depth=1, budget=1200)
        outputs.append((result.selected_context, result.memory_ids, result.confidence))

    assert outputs[0] == outputs[1]
    assert outputs[0][0].splitlines()[0] == "root | beta | c"


def test_rc7_empty_concept_fails_closed_without_context_amplification():
    core = EvidenceCore()
    _observe(core, "root", "rel", "value", "e1", confidence=1.0)

    result = activate(Resolver(core), concept="   ", session_id="rc7:d", depth=2, budget=1200)

    assert result.status == "UNRESOLVED"
    assert result.selected_context == ""
    assert result.concepts == ()
