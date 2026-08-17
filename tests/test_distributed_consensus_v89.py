from memoria_resolutiva.distributed_consensus import KnowledgeDescriptor, compare_knowledge


def kd(kid, sem, mod, fp, polarity=1, confidence=1.0):
    return KnowledgeDescriptor(kid, frozenset(sem), frozenset(mod), fp, polarity, confidence)


def test_same_requires_identity_proof():
    a = kd("a", {"door", "stuck"}, {"vision"}, "fp-1")
    b = kd("b", {"door", "jammed"}, {"language"}, "fp-1")
    assert compare_knowledge(a, b).relation == "same"


def test_related_does_not_auto_merge():
    a = kd("a", {"cup", "handle", "ceramic", "drink"}, {"vision"}, "fp-a")
    b = kd("b", {"cup", "handle", "ceramic", "fragile"}, {"touch"}, "fp-b")
    assert compare_knowledge(a, b).relation == "related"


def test_conflict_is_explicit():
    sem = {"door", "open", "hall", "robot"}
    a = kd("a", sem, {"vision"}, "fp-a", polarity=1)
    b = kd("b", sem, {"language"}, "fp-b", polarity=-1)
    assert compare_knowledge(a, b).relation == "conflict"


def test_low_confidence_does_not_force_conflict():
    sem = {"door", "open", "hall", "robot"}
    a = kd("a", sem, {"vision"}, "fp-a", polarity=1, confidence=0.2)
    b = kd("b", sem, {"language"}, "fp-b", polarity=-1, confidence=0.2)
    assert compare_knowledge(a, b).relation != "conflict"


def test_unrelated_knowledge_stays_distinct():
    a = kd("a", {"bank", "credit", "loan"}, {"text"}, "fa")
    b = kd("b", {"database", "index", "table"}, {"text"}, "fb")
    assert compare_knowledge(a, b).relation == "distinct"
