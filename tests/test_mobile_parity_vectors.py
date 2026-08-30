from experiments.generate_mobile_parity_vectors import build_vectors


def _by_id(payload):
    return {row["id"]: row for row in payload["vectors"]}


def test_mobile_parity_vectors_are_deterministic_and_cover_required_classes():
    first = build_vectors()
    second = build_vectors()
    assert first == second
    assert first["schema"] == "memoria-mobile-parity-v1"
    rows = _by_id(first)
    required = {
        "semantic.basic.hit",
        "semantic.open_set.unresolved",
        "semantic.independent_conflict.unresolved",
        "provenance.echoes.canonical_source",
        "episodic.latest.hit",
        "episodic.same_order.unresolved",
        "restart.semantic.same_result",
        "restart.episodic.same_result",
    }
    assert required.issubset(rows)


def test_mobile_parity_vectors_preserve_conservative_statuses_and_restart_equivalence():
    rows = _by_id(build_vectors())
    assert rows["semantic.basic.hit"]["expected"]["status"] == "HIT"
    assert rows["semantic.open_set.unresolved"]["expected"]["status"] == "UNRESOLVED"
    assert rows["semantic.independent_conflict.unresolved"]["expected"]["status"] == "UNRESOLVED"
    assert rows["episodic.latest.hit"]["expected"]["status"] == "HIT"
    assert rows["episodic.same_order.unresolved"]["expected"]["status"] == "UNRESOLVED"
    assert rows["restart.semantic.same_result"]["expected"] == rows["semantic.basic.hit"]["expected"]
    assert rows["restart.episodic.same_result"]["expected"] == rows["episodic.latest.hit"]["expected"]


def test_echo_vector_resolves_to_original_factual_source():
    row = _by_id(build_vectors())["provenance.echoes.canonical_source"]
    assert row["expected"]["status"] == "HIT"
    provenance = row["expected"]["provenance"]
    assert provenance
    assert provenance[0]["ultimate_source_memory_id"] == row["expected_ultimate_source_memory_id"]
    assert provenance[0]["source_type"] == "user_assertion"
