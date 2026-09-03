from __future__ import annotations

import json
from pathlib import Path


def test_post_v1_relation_quality_fixture_is_balanced_and_explicit():
    fixture = Path(__file__).parent / "fixtures" / "relation_quality_post_v1.json"
    payload = json.loads(fixture.read_text("utf-8"))

    accepted = payload["accepted"]
    rejected = payload["rejected"]

    assert len(accepted) >= 3
    assert len(rejected) >= 6
    assert all(item["predicate"] == "is" for item in accepted)
    assert "isso é verdade" in rejected
    assert "ele é azul" in rejected
    assert "quem é atlas" in rejected
