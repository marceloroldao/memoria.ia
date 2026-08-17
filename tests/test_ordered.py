from memoria_resolutiva.ordered import compare_ordered
from memoria_resolutiva.trajectory import Occurrence


def occs(ids):
    return [Occurrence("m", 0, i, node_id) for i, node_id in enumerate(ids)]


def test_ordered_similarity_prefers_same_sequence():
    a = occs(["A", "B", "C", "D"])
    same = occs(["A", "B", "C", "D"])
    reversed_seq = occs(["D", "C", "B", "A"])
    s_same = compare_ordered(a, same)
    s_rev = compare_ordered(a, reversed_seq)
    assert s_same.combined_score > s_rev.combined_score
    assert s_same.order_score == 1.0


def test_ordered_similarity_penalizes_changed_temporal_spacing():
    a = [Occurrence("a", 0, t, n) for t, n in zip([0, 1, 2, 3], ["A", "B", "C", "D"])]
    b = [Occurrence("b", 0, t, n) for t, n in zip([0, 1, 2, 3], ["A", "B", "C", "D"])]
    stretched = [Occurrence("c", 0, t, n) for t, n in zip([0, 2, 5, 9], ["A", "B", "C", "D"])]
    assert compare_ordered(a, b).combined_score > compare_ordered(a, stretched).combined_score
