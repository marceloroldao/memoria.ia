from pathlib import Path


def test_relation_resolve_activation_is_miss_only_and_bounded() -> None:
    root = Path(__file__).resolve().parents[1]
    bridge = (root / "native" / "mobile" / "concept_relation_resolve_bridge.c").read_text(encoding="utf-8")
    doc = (root / "docs" / "POST_V1_NATIVE_RELATION_RESOLVE_ACTIVATION.md").read_text(encoding="utf-8")

    assert "base_status != MEMORIA_MOBILE_UNRESOLVED" in bridge
    assert 'bridge_json_string(json, "relation_source")' in bridge
    assert 'bridge_json_string(json, "relation_target")' in bridge
    assert "path_count == 1u" in bridge
    assert "BRIDGE_MAX_HOPS 4u" in bridge
    assert "BRIDGE_MAX_PATHS 2u" in bridge
    assert "BRIDGE_MIN_CONFIDENCE 0.80" in bridge
    assert "Existing direct HIT response shape and priority are unchanged." in doc
