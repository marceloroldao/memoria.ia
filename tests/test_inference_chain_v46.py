from memoria_resolutiva.inference_chain import InferenceChain


def test_two_hop_inference_preserves_path_and_provenance():
    g = InferenceChain(hop_penalty=0.95)
    g.add("A", "r1", "B", 0.9, "ab")
    g.add("B", "r2", "C", 0.8, "bc")
    paths = g.infer("A", "C")
    assert paths
    p = paths[0]
    assert p.nodes == ("A", "B", "C")
    assert [e.provenance for e in p.edges] == ["ab", "bc"]


def test_longer_chain_has_lower_confidence_when_edges_are_equal():
    g = InferenceChain(hop_penalty=0.95)
    g.add("A", "r", "B", 0.9)
    g.add("B", "r", "C", 0.9)
    g.add("C", "r", "D", 0.9)
    c = g.infer("A", "C")[0].confidence
    d = g.infer("A", "D")[0].confidence
    assert d < c


def test_cycle_is_not_followed_indefinitely():
    g = InferenceChain(max_depth=5)
    g.add("A", "r", "B", 0.9)
    g.add("B", "r", "A", 0.9)
    g.add("B", "r", "C", 0.9)
    paths = g.infer("A", "C")
    assert len(paths) == 1
    assert paths[0].nodes == ("A", "B", "C")


def test_best_path_ranked_first():
    g = InferenceChain(hop_penalty=1.0)
    g.add("A", "r", "B", 0.9)
    g.add("B", "r", "D", 0.9)
    g.add("A", "r", "C", 0.6)
    g.add("C", "r", "D", 0.6)
    paths = g.infer("A", "D")
    assert paths[0].confidence > paths[1].confidence
    assert paths[0].nodes == ("A", "B", "D")
