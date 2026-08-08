from memoria_resolutiva.hypothesis_learning import HypothesisLearner


def test_hypothesis_is_not_fact_on_creation():
    l = HypothesisLearner()
    h = l.propose("A", "B", "r", "x", 0.75)
    assert h.status == "pending"
    assert ("B", "r", "x") not in l.facts


def test_independent_confirmations_raise_confidence():
    l = HypothesisLearner(support_threshold=0.80)
    h = l.propose("A", "B", "r", "x", 0.70)
    before = h.posterior_confidence
    l.observe("B", "r", "x")
    l.observe("B", "r", "x")
    assert h.posterior_confidence > before
    assert h.status == "supported"


def test_contradictory_observations_lower_confidence_and_can_reject():
    l = HypothesisLearner(reject_threshold=0.20)
    h = l.propose("A", "B", "r", "x", 0.70)
    before = h.posterior_confidence
    for _ in range(12):
        l.observe("B", "r", "y")
    assert h.posterior_confidence < before
    assert h.status == "rejected"


def test_only_observation_changes_hypothesis_confidence():
    l = HypothesisLearner()
    h = l.propose("A", "B", "r", "x", 0.70)
    p = h.posterior_confidence
    for _ in range(20):
        l.get(h.hypothesis_id)
    assert h.posterior_confidence == p
    assert h.history == []


def test_history_records_epistemic_change():
    l = HypothesisLearner()
    h = l.propose("A", "B", "r", "x", 0.70)
    l.observe("B", "r", "x")
    l.observe("B", "r", "y")
    assert [event for _, event, _ in h.history] == ["confirm", "reject"]
    assert h.history[0][0] < h.history[1][0]
