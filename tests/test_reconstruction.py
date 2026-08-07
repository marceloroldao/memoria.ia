from memoria_resolutiva import ResolutiveMemory


def test_exact_reconstruction():
    mem = ResolutiveMemory()
    data = b"Fisica Resolutiva e memoria hierarquica"
    mem.add("doc", data)
    assert mem.reconstruct("doc") == data
