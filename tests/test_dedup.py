from memoria_resolutiva import ResolutiveMemory


def test_identical_memories_reuse_nodes():
    mem = ResolutiveMemory()
    payload = b"abcabcabcabcabcabc"
    mem.add("a", payload)
    nodes_after_a = len(mem.nodes)
    mem.add("b", payload)
    assert len(mem.nodes) == nodes_after_a
    assert mem.stats()["occurrences"] > nodes_after_a
