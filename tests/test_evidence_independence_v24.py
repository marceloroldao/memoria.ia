from memoria_resolutiva.evidence_independence import EvidenceItem, IndependentEvidenceResolver


def test_ten_copies_of_one_origin_do_not_outvote_two_independent_origins():
    r = IndependentEvidenceResolver(min_margin=0.15)
    for i in range(10):
        r.observe(EvidenceItem("c", "x", f"copy{i}", "same_origin", 1.0))
    r.observe(EvidenceItem("c", "y", "y1", "independent_1", 1.0))
    r.observe(EvidenceItem("c", "y", "y2", "independent_2", 1.0))
    decision = r.resolve("c")
    assert decision.winner == "y"
    assert decision.independent_origins["x"] == 1
    assert decision.independent_origins["y"] == 2


def test_true_independent_majority_wins():
    r = IndependentEvidenceResolver(min_margin=0.15)
    for origin in ("a", "b", "c"):
        r.observe(EvidenceItem("c", "x", origin, origin, 1.0))
    r.observe(EvidenceItem("c", "y", "d", "d", 1.0))
    assert r.resolve("c").winner == "x"


def test_close_independent_split_abstains():
    r = IndependentEvidenceResolver(min_margin=0.20)
    r.observe(EvidenceItem("c", "x", "a", "a", 1.0))
    r.observe(EvidenceItem("c", "x", "b", "b", 1.0))
    r.observe(EvidenceItem("c", "y", "c", "c", 1.0))
    r.observe(EvidenceItem("c", "y", "d", "d", 1.0))
    decision = r.resolve("c")
    assert decision.conflict
    assert decision.winner is None


def test_duplicate_source_inside_same_origin_does_not_stack_weight():
    r = IndependentEvidenceResolver()
    r.observe(EvidenceItem("c", "x", "a", "origin", 1.0))
    r.observe(EvidenceItem("c", "x", "b", "origin", 1.0))
    r.observe(EvidenceItem("c", "x", "c", "origin", 3.0))
    decision = r.resolve("c")
    assert decision.support["x"] == 3.0
    assert decision.independent_origins["x"] == 1
