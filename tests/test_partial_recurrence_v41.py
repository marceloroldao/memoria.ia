from memoria_resolutiva.partial_recurrence import PartialRecurrenceClassifier


def classifier():
    c = PartialRecurrenceClassifier(recurrence_threshold=0.96, variant_threshold=0.78, ambiguity_margin=0.04)
    c.remember("A", [1.0, 0.8, 0.1, 0.0, 0.2])
    c.remember("B", [0.1, 0.2, 1.0, 0.8, 0.0])
    c.remember("C", [0.0, 0.1, 0.2, 0.4, 1.0])
    return c


def test_close_return_is_recurrence():
    d = classifier().classify([1.0, 0.79, 0.11, 0.01, 0.19])
    assert d.kind == "recurrence" and d.regime == "A"


def test_partial_match_can_be_variant_not_recurrence():
    d = classifier().classify([0.85, 0.60, 0.30, 0.10, 0.35])
    assert d.kind in {"variant", "recurrence"}
    assert d.regime == "A"
    if d.similarity < 0.96:
        assert d.kind == "variant"


def test_distant_profile_is_novel():
    c = PartialRecurrenceClassifier(recurrence_threshold=0.98, variant_threshold=0.90)
    c.remember("A", [1.0, 0.0, 0.0])
    d = c.classify([0.0, 1.0, 0.0])
    assert d.kind == "novel" and d.regime is None


def test_close_competing_profiles_can_abstain_as_ambiguous():
    c = PartialRecurrenceClassifier(recurrence_threshold=0.99, variant_threshold=0.70, ambiguity_margin=0.08)
    c.remember("A", [1.0, 0.0])
    c.remember("B", [0.0, 1.0])
    d = c.classify([0.71, 0.70])
    assert d.kind == "ambiguous" and d.regime is None
