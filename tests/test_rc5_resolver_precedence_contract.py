from pathlib import Path


def test_rc5_resolver_precedence_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    bridge = (root / "native" / "mobile" / "concept_relation_resolve_bridge.c").read_text(encoding="utf-8")

    base_guard = bridge.index("if (base_status != MEMORIA_MOBILE_UNRESOLVED) return base_status;")
    relation_anchor = bridge.index("memoria_relation_anchor_extract(query")
    collection = bridge.index("memoria_collection_query_extract(query")
    neighborhood = bridge.index("memoria_relation_neighborhood_query_extract(query")

    assert base_guard < relation_anchor < collection < neighborhood
    assert "return base_status;" in bridge[base_guard:relation_anchor]
