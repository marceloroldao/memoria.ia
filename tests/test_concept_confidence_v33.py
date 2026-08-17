from memoria_resolutiva.concept_confidence import ConceptConfidence


def test_starts_neutral_and_uncertain():
    c = ConceptConfidence()
    assert c.confidence_merge() == 0.5
    assert c.state() == "uncertain"


def test_merge_evidence_raises_confidence_gradually():
    c = ConceptConfidence()
    first = c.observe(1, merge_evidence=1.0)
    second = c.observe(2, merge_evidence=2.0)
    assert 0.5 < first.confidence_merge < second.confidence_merge < 1.0


def test_single_contradiction_does_not_force_immediate_flip():
    c = ConceptConfidence()
    c.observe(1, merge_evidence=3.0)
    assert c.state() == "merge"
    c.observe(2, split_evidence=1.0)
    assert c.state() in {"merge", "uncertain"}


def test_sufficient_split_evidence_can_reverse_state():
    c = ConceptConfidence()
    c.observe(1, merge_evidence=3.0)
    c.observe(2, split_evidence=1.0)
    c.observe(3, split_evidence=3.0)
    c.observe(4, split_evidence=4.0)
    assert c.confidence_merge() < 0.33
    assert c.state() == "split"


def test_historical_confidence_is_preserved():
    c = ConceptConfidence()
    c.observe(1, merge_evidence=2.0)
    early = c.at(1)
    c.observe(2, split_evidence=5.0)
    assert c.at(1) == early
    assert c.at(2) != early
