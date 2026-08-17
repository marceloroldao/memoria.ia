from memoria_resolutiva.analogical_transfer import AnalogicalTransfer


def test_supported_similar_relation_becomes_candidate_not_fact():
    t = AnalogicalTransfer()
    t.observe("A1", "requires", "validation")
    result = t.propose("A1", "B1", "requires", 0.92, independent_support=2)
    assert result and result[0].status == "candidate"
    assert t.values("B1", "requires") == set()


def test_weak_support_forces_abstention():
    t = AnalogicalTransfer()
    t.observe("A1", "requires", "validation")
    result = t.propose("A1", "B1", "requires", 0.92, independent_support=1)
    assert result and result[0].status == "abstain"


def test_low_similarity_blocks_transfer():
    t = AnalogicalTransfer()
    t.observe("A1", "requires", "validation")
    assert t.propose("A1", "B1", "requires", 0.50, independent_support=5) == []


def test_target_conflict_forces_abstention():
    t = AnalogicalTransfer()
    t.observe("A1", "requires", "validation")
    t.observe("B1", "requires", "isolation")
    result = t.propose("A1", "B1", "requires", 0.95, independent_support=3)
    assert result and all(r.status == "abstain" for r in result)


def test_no_source_relation_means_no_candidate():
    t = AnalogicalTransfer()
    assert t.propose("A1", "B1", "unknown", 0.99, independent_support=5) == []
