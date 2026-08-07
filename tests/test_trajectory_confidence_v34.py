from collections import Counter

from memoria_resolutiva.polysemy import Sense
from memoria_resolutiva.trajectory_confidence import AutoConceptConfidence, derive_trajectory_evidence


def sense(sense_id, words, occurrences=5):
    s = Sense(sense_id)
    s.contexts = Counter(words)
    s.occurrences = occurrences
    return s


def test_similar_trajectories_favor_merge():
    a = sense(0, {"credito": 3, "cliente": 3, "conta": 2, "juros": 2})
    b = sense(1, {"credito": 2, "cliente": 3, "conta": 3, "emprestimo": 2})
    ev = derive_trajectory_evidence(a, b)
    assert ev.merge_signal > ev.split_signal


def test_divergent_trajectories_favor_split():
    a = sense(0, {"credito": 3, "cliente": 3, "conta": 2})
    b = sense(1, {"dados": 3, "servidor": 3, "tabelas": 2})
    ev = derive_trajectory_evidence(a, b)
    assert ev.split_signal > ev.merge_signal


def test_confidence_updates_without_manual_labels():
    similar_a = sense(0, {"credito": 3, "cliente": 3, "conta": 2})
    similar_b = sense(1, {"credito": 2, "cliente": 3, "emprestimo": 2})
    divergent = sense(2, {"dados": 3, "servidor": 3, "registros": 2})

    c = AutoConceptConfidence()
    p0 = c.merge_probability
    p1 = c.update(derive_trajectory_evidence(similar_a, similar_b))
    p2 = c.update(derive_trajectory_evidence(similar_a, divergent), weight=3.0)
    assert p1 > p0
    assert p2 < p1


def test_state_has_uncertainty_band():
    c = AutoConceptConfidence()
    assert c.state == "uncertain"
