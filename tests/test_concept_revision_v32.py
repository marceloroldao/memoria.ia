from memoria_resolutiva.polysemy import PolysemyMemory
from memoria_resolutiva.concept_revision import ConceptRevisionHistory, snapshot_from_memory


def test_revision_history_preserves_old_snapshot():
    m = PolysemyMemory(window=2, split_threshold=0.18)
    h = ConceptRevisionHistory()
    for sentence in ["banco recebeu cliente dados", "banco registrou conta sistema"]:
        m.observe(sentence)
    old = snapshot_from_memory(h, m, "banco", 1, threshold=0.15)
    for sentence in ["banco aprovou credito", "banco armazenou dados", "consulta acessou banco"]:
        m.observe(sentence)
    new = snapshot_from_memory(h, m, "banco", 2, threshold=0.30)
    assert h.at("banco", 1) == old
    assert h.current("banco") == new


def test_revision_is_reported_when_grouping_changes():
    m = PolysemyMemory(window=2, split_threshold=0.18)
    h = ConceptRevisionHistory()
    for sentence in ["banco recebeu cliente dados", "banco registrou conta sistema"]:
        m.observe(sentence)
    snapshot_from_memory(h, m, "banco", 1, threshold=0.10)
    for sentence in ["banco aprovou credito cliente", "banco armazena dados sistema", "servidor consulta banco"]:
        m.observe(sentence)
    snapshot_from_memory(h, m, "banco", 2, threshold=0.35)
    revisions = h.revisions("banco")
    assert len(revisions) >= 1
    assert revisions[-1][0].epoch == 1
    assert revisions[-1][1].epoch == 2


def test_unknown_token_has_no_snapshot():
    h = ConceptRevisionHistory()
    assert h.current("inexistente") is None
    assert h.at("inexistente", 10) is None
