from memoria_resolutiva.address_portal_resolution_v2 import (
    DensityAwareConvergenceResolver,
)
from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory


def test_less_dense_terminal_wins_only_when_structural_support_ties() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato de")
    memory.ingest("meu gato Lotus")

    # Make `de` structurally hyper-connected without teaching semantics.
    for index in range(20):
        memory.ingest(f"origem{index} de destino{index}")

    matches = DensityAwareConvergenceResolver(memory).resolve("meu gato", limit=2)
    assert len(matches) == 2
    assert matches[0].terminal_surface == "lotus"
    assert matches[0].structural_key == matches[1].structural_key
    assert matches[0].terminal_density_key < matches[1].terminal_density_key


def test_dense_terminal_can_still_win_with_stronger_convergence() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("irmao meu gato de")
    memory.ingest("meu gato Lotus")

    for index in range(20):
        memory.ingest(f"origem{index} de destino{index}")

    matches = DensityAwareConvergenceResolver(memory).resolve(
        "irmao meu gato", limit=2
    )
    assert len(matches) == 2
    assert matches[0].terminal_surface == "de"
    assert matches[0].matched_addresses > matches[1].matched_addresses


def test_portal_resolution_is_read_only_and_restart_deterministic() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato de")
    memory.ingest("meu gato Lotus")
    for index in range(8):
        memory.ingest(f"origem{index} de destino{index}")

    before = memory.snapshot()
    first = DensityAwareConvergenceResolver(memory).resolve("meu gato", limit=3)
    after = memory.snapshot()
    assert before == after

    restored = AddressTrajectoryMemory.restore(before)
    second = DensityAwareConvergenceResolver(restored).resolve("meu gato", limit=3)
    assert first == second
