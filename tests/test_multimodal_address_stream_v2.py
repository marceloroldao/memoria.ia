from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.topological_density_v2 import TopologicalDensityEngine


def test_text_ingestion_rejects_immediate_same_address_loops() -> None:
    memory = AddressTrajectoryMemory()
    trajectory = memory.ingest("de de de de de de")
    assert len(trajectory.addresses) == 1
    assert trajectory.surfaces == ("de",)
    assert trajectory.raw_text == "de de de de de de"


def test_non_immediate_recurrence_is_preserved() -> None:
    memory = AddressTrajectoryMemory()
    trajectory = memory.ingest("de gato de")
    assert trajectory.surfaces == ("de", "gato", "de")


def test_external_address_stream_uses_same_loop_rule_without_words() -> None:
    memory = AddressTrajectoryMemory()
    trajectory = memory.ingest_address_stream(
        ("audio:A", "audio:A", "audio:B", "audio:B", "audio:A"),
        surfaces=("frame-A", "frame-A", "frame-B", "frame-B", "frame-A"),
        provenance="audio:test-001",
    )
    assert trajectory.addresses == ("audio:A", "audio:B", "audio:A")
    assert trajectory.surfaces == ("frame-A", "frame-B", "frame-A")
    assert trajectory.raw_text == "audio:test-001"


def test_density_engine_is_modality_agnostic() -> None:
    memory = AddressTrajectoryMemory()
    for index in range(12):
        memory.ingest_address_stream(
            (f"video:left:{index}", "video:hub", f"video:right:{index}"),
            provenance=f"video:{index}",
        )
    profiles = TopologicalDensityEngine(memory).profiles()
    assert profiles
    assert profiles[0].address == "video:hub"
    assert profiles[0].trajectory_count == 12
    assert profiles[0].predecessor_count == 12
    assert profiles[0].successor_count == 12
