from memoria_resolutiva import ResolutiveMemory


def test_structural_retrieval():
    mem = ResolutiveMemory()
    mem.add("astro", b"curva de rotacao da galaxia permaneceu plana")
    mem.add("rede", b"olt registrou perda optica elevada na fibra")
    mem.add("quantum", b"tres cavidades acopladas com controle de fase")
    hits = mem.search(b"perda optica elevada na fibra")
    assert hits
    assert hits[0].memory_id == "rede"
