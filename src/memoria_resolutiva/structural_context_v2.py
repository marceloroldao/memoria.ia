from __future__ import annotations

from typing import Iterable

from .evolving_address_state_v2 import AddressStateRevision, EvolvingAddressStateJournalV2


class StructuralContextAddressV2:
    """Use one stable opaque address as an evolving structural context.

    This is deliberately a thin role over the generic evolving-address journal.
    It introduces no text, grammar, modality or semantic rules: the payload is only
    an ordered tuple of opaque structural addresses, and every admitted change is
    an immutable append-only revision.
    """

    def __init__(self, journal: EvolvingAddressStateJournalV2 | None = None) -> None:
        self.journal = journal if journal is not None else EvolvingAddressStateJournalV2()

    def revise(
        self,
        context_address: int,
        *,
        hierarchy_id: str,
        sequence: int,
        payload_addresses: Iterable[int] = (),
        trajectory_ids: Iterable[str] = (),
        provenance_ids: Iterable[str] = (),
    ) -> AddressStateRevision:
        return self.journal.append(
            context_address,
            hierarchy_id=hierarchy_id,
            sequence=sequence,
            payload_addresses=payload_addresses,
            trajectory_ids=trajectory_ids,
            provenance_ids=provenance_ids,
        )

    def current(
        self,
        context_address: int,
        *,
        hierarchy_id: str,
    ) -> AddressStateRevision | None:
        return self.journal.current_revision(context_address, hierarchy_id=hierarchy_id)

    def history(
        self,
        context_address: int,
        *,
        hierarchy_id: str,
    ) -> tuple[AddressStateRevision, ...]:
        return self.journal.history(context_address, hierarchy_id=hierarchy_id)
