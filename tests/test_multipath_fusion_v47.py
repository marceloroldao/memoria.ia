from memoria_resolutiva.multipath_fusion import EvidencePath, fuse_paths


def test_independent_paths_raise_confidence():
    paths = [
        EvidencePath("x", 0.70, frozenset({"a"}), "p1"),
        EvidencePath("x", 0.60, frozenset({"b"}), "p2"),
    ]
    r = fuse_paths(paths)
    assert r is not None
    assert r.independent_groups == 2
    assert r.fused_confidence > 0.70


def test_shared_origin_is_not_double_counted():
    paths = [
        EvidencePath("x", 0.70, frozenset({"root"}), "p1"),
        EvidencePath("x", 0.80, frozenset({"root", "other"}), "p2"),
    ]
    r = fuse_paths(paths)
    assert r is not None
    assert r.independent_groups == 1
    assert abs(r.fused_confidence - 0.80) < 1e-12
    assert r.contributing_paths == ("p2",)


def test_transitive_dependency_collapses_family():
    paths = [
        EvidencePath("x", 0.60, frozenset({"a"}), "p1"),
        EvidencePath("x", 0.70, frozenset({"a", "b"}), "p2"),
        EvidencePath("x", 0.80, frozenset({"b"}), "p3"),
    ]
    r = fuse_paths(paths)
    assert r is not None
    assert r.independent_groups == 1
    assert abs(r.fused_confidence - 0.80) < 1e-12


def test_empty_input_returns_none():
    assert fuse_paths([]) is None


def test_mixed_conclusions_are_rejected():
    paths = [
        EvidencePath("x", 0.6, frozenset({"a"}), "p1"),
        EvidencePath("y", 0.7, frozenset({"b"}), "p2"),
    ]
    try:
        fuse_paths(paths)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
