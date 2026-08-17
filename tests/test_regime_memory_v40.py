from random import Random

from memoria_resolutiva.regime_memory import RegimeMemory


def test_known_regimes_are_distinguishable():
    m = RegimeMemory(threshold=0.95)
    m.store("A", (1.0, 0.0, 0.0), 20)
    m.store("B", (0.0, 1.0, 0.0), 20)
    m.store("C", (0.0, 0.0, 1.0), 20)
    assert m.match((0.98, 0.02, 0.0))[0] == "A"
    assert m.match((0.01, 0.99, 0.0))[0] == "B"
    assert m.match((0.0, 0.03, 0.97))[0] == "C"


def test_unknown_regime_can_abstain():
    m = RegimeMemory(threshold=0.99)
    m.store("A", (1.0, 0.0), 10)
    name, score = m.match((0.7, 0.7))
    assert name is None
    assert score < 0.99


def test_returning_regime_can_be_reactivated_from_short_prefix():
    rng = Random(7)
    A = (0.9, 0.1, 0.8)
    samples = [tuple(max(0.0, x + rng.gauss(0, 0.02)) for x in A) for _ in range(30)]
    learned = tuple(sum(s[i] for s in samples) / len(samples) for i in range(len(A)))
    m = RegimeMemory(threshold=0.99)
    m.store("A", learned, 30)

    prefix = []
    detected = None
    for step in range(1, 10):
        prefix.append(tuple(max(0.0, x + rng.gauss(0, 0.02)) for x in A))
        current = tuple(sum(s[i] for s in prefix) / len(prefix) for i in range(len(A)))
        if m.match(current)[0] == "A":
            detected = step
            break
    assert detected is not None
    assert detected < 30


def test_profiles_are_not_erased_by_matching():
    m = RegimeMemory()
    m.store("A", (1.0, 0.0), 5)
    before = m.profiles()
    m.match((0.99, 0.01))
    assert m.profiles() == before
