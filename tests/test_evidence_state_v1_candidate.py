from __future__ import annotations

import pytest

from memoria_resolutiva.bdr_store import native_bdr_available
from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.evidence_state import EvidenceCorePersistence, EvidenceCoreStateCodec


def _build_core() -> EvidenceCore:
    core = EvidenceCore()
    core.observe_relation(
        "Delta",
        "powers",
        "controlador",
        evidence_id="e1",
        source_text="A fonte Delta alimenta o controlador.",
        provenance="sensor-a",
        origin="origin-a",
        confidence=0.9,
        namespace="lab",
        epoch=0,
    )
    core.observe_relation(
        "controlador",
        "belongs_to",
        "Orion",
        evidence_id="e2",
        source_text="O controlador pertence ao Orion.",
        provenance="registry-b",
        origin="origin-b",
        confidence=0.8,
        namespace="lab",
        epoch=1,
    )
    core.adjudicate_origin(
        "origin-a",
        resolution_id="r1",
        confirmed=True,
        adjudicator_origins=("reviewer-x",),
        weight=2.0,
    )
    return core


def _assert_behavior(core: EvidenceCore) -> None:
    result = core.infer_path("Delta", "Orion", namespace="lab", max_hops=2)
    assert result.inferred
    path = result.paths[0]
    assert path.nodes == ("Delta", "controlador", "Orion")
    assert path.predicates == ("powers", "belongs_to")
    assert path.evidence_ids == ("e1", "e2")
    assert path.synthesized_claims == 0
    assert core.origin_reliability("origin-a") > 0.5


def test_evidence_state_codec_is_canonical_and_replay_equivalent():
    original = _build_core()
    first = EvidenceCoreStateCodec.dump(original)
    restored = EvidenceCoreStateCodec.load(first)
    second = EvidenceCoreStateCodec.dump(restored)

    assert first == second
    _assert_behavior(restored)


def test_evidence_state_sqlite_roundtrip_is_deterministic(tmp_path):
    persistence = EvidenceCorePersistence(
        tmp_path / "sqlite-state",
        backend="sqlite",
        allow_fallback=False,
    )
    original = _build_core()
    receipt = persistence.store(original)
    assert receipt.backend == "sqlite"

    restored = EvidenceCorePersistence(
        tmp_path / "sqlite-state",
        backend="sqlite",
        allow_fallback=False,
    ).load(receipt)
    _assert_behavior(restored)
    assert EvidenceCoreStateCodec.dump(restored) == EvidenceCoreStateCodec.dump(original)


@pytest.mark.skipif(not native_bdr_available(), reason="native BDR extension not built")
def test_evidence_state_native_bdr_roundtrip_is_deterministic(tmp_path):
    persistence = EvidenceCorePersistence(
        tmp_path / "bdr-state",
        backend="bdr",
        allow_fallback=False,
    )
    original = _build_core()
    receipt = persistence.store(original)
    assert receipt.backend == "bdr"

    restored = EvidenceCorePersistence(
        tmp_path / "bdr-state",
        backend="bdr",
        allow_fallback=False,
    ).load(receipt)
    _assert_behavior(restored)
    assert EvidenceCoreStateCodec.dump(restored) == EvidenceCoreStateCodec.dump(original)
