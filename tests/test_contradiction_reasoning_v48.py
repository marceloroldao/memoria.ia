from memoria_resolutiva.contradiction_reasoning import Argument, decide_conflict


def test_balanced_independent_conflict_abstains():
    args = [
        Argument("D", True, 0.78, frozenset({"s1"})),
        Argument("D", False, 0.75, frozenset({"s2"})),
    ]
    d = decide_conflict(args, "D", decision_margin=0.10)
    assert d.status == "abstain"


def test_multiple_independent_support_paths_can_win():
    args = [
        Argument("D", True, 0.70, frozenset({"s1"})),
        Argument("D", True, 0.65, frozenset({"s2"})),
        Argument("D", False, 0.60, frozenset({"s3"})),
    ]
    d = decide_conflict(args, "D", decision_margin=0.15)
    assert d.status == "support"
    assert d.support_confidence > d.reject_confidence


def test_dependent_duplicates_do_not_overpower_opposition():
    args = [
        Argument("D", True, 0.70, frozenset({"root"})),
        Argument("D", True, 0.69, frozenset({"root", "x"})),
        Argument("D", True, 0.68, frozenset({"x"})),
        Argument("D", False, 0.72, frozenset({"other"})),
    ]
    d = decide_conflict(args, "D", decision_margin=0.10)
    assert d.status == "abstain"
    assert d.support_confidence == 0.70


def test_clear_negative_evidence_rejects():
    args = [
        Argument("D", True, 0.55, frozenset({"s1"})),
        Argument("D", False, 0.80, frozenset({"s2"})),
        Argument("D", False, 0.70, frozenset({"s3"})),
    ]
    d = decide_conflict(args, "D", decision_margin=0.15)
    assert d.status == "reject"


def test_no_relevant_evidence_is_explicit():
    d = decide_conflict([], "D")
    assert d.status == "no_evidence"
