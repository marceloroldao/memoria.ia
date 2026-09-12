from __future__ import annotations

from dataclasses import dataclass

from .address_trajectory_v2 import AddressTrajectoryMemory
from .end_to_end_resolver_v2 import EndToEndAddressResolver, EndToEndResolution
from .structural_equivalence_v2 import StructuralEquivalenceState
from .structural_equivalence_resolver_v2 import resolve_via_structural_equivalence
from .structural_witness_discovery_v2 import (
    TrajectoryOccurrence,
    discover_witnesses,
    events_from_discovered_witnesses,
    structural_signature,
)


@dataclass(frozen=True, slots=True)
class StructuralFallbackDiagnostics:
    witnesses: int
    equivalence_events: int
    known_signatures: int


@dataclass(frozen=True, slots=True)
class EndToEndStructuralResolution:
    resolution: EndToEndResolution
    diagnostics: StructuralFallbackDiagnostics


class EndToEndStructuralResolver:
    """Experimental V2 resolver: direct occurrence frontier, then structural fallback.

    The caller provides only a memory and the current address configuration. Direct
    contiguous evidence always wins. Only when direct resolution is unresolved do
    we derive structural witnesses from the immutable snapshot, reconstruct a
    revocable equivalence state, and ask whether the current configuration is
    structurally equivalent to another observed origin with a unique supported
    terminal.

    No semantic vocabulary, intent labels, embeddings, neural weights or persistent
    shortcut edges are introduced. The fallback is query-read-only.
    """

    def __init__(
        self,
        memory: AddressTrajectoryMemory,
        *,
        min_supporting_witnesses: int = 2,
        min_bridge_addresses: int = 2,
        max_bucket_signatures: int = 32,
        max_witnesses_per_pair: int = 8,
    ) -> None:
        self.memory = memory
        self.direct = EndToEndAddressResolver(memory)
        self.min_supporting_witnesses = min_supporting_witnesses
        self.min_bridge_addresses = min_bridge_addresses
        self.max_bucket_signatures = max_bucket_signatures
        self.max_witnesses_per_pair = max_witnesses_per_pair

    def _derived_equivalence_state(self):
        snapshot = self.memory.snapshot()
        occurrences = tuple(
            TrajectoryOccurrence(
                trajectory=trajectory,
                lineage_id=trajectory.trajectory_id,
                occurrence_id=trajectory.trajectory_id,
            )
            for trajectory in snapshot
        )
        witnesses = discover_witnesses(
            occurrences,
            min_bridge_addresses=self.min_bridge_addresses,
            max_bucket_signatures=self.max_bucket_signatures,
            max_witnesses_per_pair=self.max_witnesses_per_pair,
        )
        events = events_from_discovered_witnesses(witnesses)
        state = StructuralEquivalenceState(
            list(events),
            min_supporting_witnesses=self.min_supporting_witnesses,
        )

        signature_terminals: dict[str, set[str]] = {}
        known_signatures: set[str] = set()
        for event in events:
            known_signatures.add(event.signature_id)
            signature_terminals.setdefault(event.signature_id, set()).add(event.terminal_region_id)

        return state, signature_terminals, tuple(sorted(known_signatures)), len(witnesses), len(events)

    def resolve_addresses(self, query_addresses: tuple[str, ...]) -> EndToEndStructuralResolution:
        direct = self.direct.resolve_addresses(query_addresses)
        if direct.resolved or direct.ambiguous or not query_addresses:
            return EndToEndStructuralResolution(
                direct,
                StructuralFallbackDiagnostics(0, 0, 0),
            )

        state, terminals, known, witness_count, event_count = self._derived_equivalence_state()
        query_signature = structural_signature(query_addresses)
        equivalence = resolve_via_structural_equivalence(
            query_signature_id=query_signature,
            equivalence_state=state,
            signature_terminals=terminals,
            known_signature_ids=known,
        )

        diagnostics = StructuralFallbackDiagnostics(witness_count, event_count, len(known))
        if equivalence.ambiguous:
            return EndToEndStructuralResolution(
                EndToEndResolution(
                    False,
                    True,
                    None,
                    None,
                    "structural-equivalence-conflict",
                    equivalence.competing_terminal_region_ids,
                    (),
                ),
                diagnostics,
            )
        if not equivalence.resolved or equivalence.terminal_region_id is None:
            return EndToEndStructuralResolution(
                EndToEndResolution(False, False, None, None, "unresolved-after-structural-fallback"),
                diagnostics,
            )

        terminal = equivalence.terminal_region_id
        surface = None
        supporting: set[str] = set()
        for trajectory in self.memory.snapshot():
            for index, address in enumerate(trajectory.addresses):
                if address == terminal:
                    supporting.add(trajectory.trajectory_id)
                    if surface is None and index < len(trajectory.surfaces):
                        surface = trajectory.surfaces[index]

        return EndToEndStructuralResolution(
            EndToEndResolution(
                True,
                False,
                terminal,
                surface,
                "structural-equivalence-fallback",
                (terminal,),
                tuple(sorted(supporting)),
            ),
            diagnostics,
        )

    def resolve_text(self, text: str) -> EndToEndStructuralResolution:
        tokens = self.memory._collapse_immediate_tokens(self.memory.decompose(text))
        return self.resolve_addresses(tuple(token.address for token in tokens))
