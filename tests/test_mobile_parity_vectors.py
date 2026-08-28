from tools.generate_mobile_parity_vectors import build_vectors


def test_mobile_reference_vectors_cover_first_native_slice():
    vectors = {row["name"]: row for row in build_vectors()}

    hit = vectors["user-source-hit"]["expected"]
    assert hit["status"] == "HIT"
    assert "24 V" in hit["selected_context"]
    assert hit["provenance"][0]["source_type"] == "user_assertion"

    conflict = vectors["independent-conflict-unresolved"]["expected"]
    assert conflict["status"] == "UNRESOLVED"
    assert conflict["memory_ids"] == []

    echo = vectors["assistant-echo-does-not-replace-root"]["expected"]
    assert echo["status"] == "HIT"
    assert echo["provenance"][0]["source_type"] == "user_assertion"
    assert echo["provenance"][0]["ultimate_source_memory_id"] == echo["memory_ids"][0]
