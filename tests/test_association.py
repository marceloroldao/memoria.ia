from memoria_resolutiva.association import association_score, nearest_associations
from memoria_resolutiva.store import ResolutiveMemory


def test_related_trajectories_rank_together():
    memory = ResolutiveMemory()
    memory.add("optica_a", b"fibra optica perda sinal olt")
    memory.add("optica_b", b"fibra optica perda potencia olt")
    memory.add("galaxia", b"galaxia curva rotacao materia")

    assert association_score(memory, "optica_a", "optica_b") > association_score(memory, "optica_a", "galaxia")
    assert nearest_associations(memory, "optica_a", top_k=1)[0][0] == "optica_b"
