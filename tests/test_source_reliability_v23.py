from memoria_resolutiva.source_reliability import SourceReliabilityMemory


def test_new_source_starts_neutral():
    m = SourceReliabilityMemory()
    assert m.reliability("new") == 0.5
    assert m.evidence_count("new") == 0.0


def test_reliability_is_learned_from_history():
    m = SourceReliabilityMemory()
    for _ in range(92):
        m.confirm("a")
    for _ in range(8):
        m.contradict("a")
    for _ in range(55):
        m.confirm("b")
    for _ in range(45):
        m.contradict("b")
    assert m.reliability("a") > m.reliability("b")
    assert m.reliability("a") > 0.9
    assert 0.5 < m.reliability("b") < 0.6


def test_prior_prevents_single_observation_from_becoming_certainty():
    m = SourceReliabilityMemory()
    m.confirm("a")
    assert 0.5 < m.reliability("a") < 1.0


def test_contradictions_reduce_reliability_online():
    m = SourceReliabilityMemory()
    for _ in range(10):
        m.confirm("a")
    before = m.reliability("a")
    for _ in range(10):
        m.contradict("a")
    assert m.reliability("a") < before


def test_wilson_lower_rewards_evidence_volume():
    m = SourceReliabilityMemory()
    m.confirm("small")
    for _ in range(90):
        m.confirm("large")
    for _ in range(10):
        m.contradict("large")
    assert m.wilson_lower("large") > m.wilson_lower("small")
