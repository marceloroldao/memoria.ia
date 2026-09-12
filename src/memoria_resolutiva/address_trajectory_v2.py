from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
import unicodedata


def _canonical(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold().strip()
    return " ".join(text.split())


def _units(text: str) -> tuple[str, ...]:
    """Mechanical segmentation only: no semantic regex or domain rules.

    A unit is any maximal run of non-whitespace characters after canonicalization.
    Punctuation remains part of the surface unit intentionally in this first lab;
    future decomposition can move below word boundaries without changing resolver
    semantics.
    """
    canonical = _canonical(text)
    return tuple(part for part in canonical.split(" ") if part)


def _address(kind: str, value: str) -> str:
    payload = f"memoria.address-trajectory.v2\x00{kind}\x00{value}".encode("utf-8")
    return "at2:" + blake2b(payload, digest_size=16).hexdigest()


@dataclass(frozen=True, slots=True)
class AddressToken:
    surface: str
    address: str


@dataclass(frozen=True, slots=True)
class AddressTrajectory:
    trajectory_id: str
    raw_text: str
    addresses: tuple[str, ...]
    surfaces: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TrajectoryMatch:
    trajectory_id: str
    raw_text: str
    overlap: int
    ordered_overlap: int
    adjacency_overlap: int
    query_coverage_num: int
    query_coverage_den: int
    terminal_surface: str | None

    @property
    def structural_key(self) -> tuple[int, int, int, int, int, str]:
        # Lexicographic structural ranking: address geometry only.
        # No learned scalar weights and no dependency on raw textual provenance.
        coverage_num = self.query_coverage_num
        coverage_den = max(self.query_coverage_den, 1)
        return (
            coverage_num,
            -coverage_den,
            self.ordered_overlap,
            self.adjacency_overlap,
            self.overlap,
            self.trajectory_id,
        )


class AddressTrajectoryMemory:
    """Experimental V2 memory based on reusable addresses and trajectory fit.

    Text is only one adapter. External modalities may ingest already-addressed
    streams (audio, video, sensors, etc.) through ``ingest_address_stream``.
    Immediate self-loops are collapsed by address equality, independently of
    modality or vocabulary.
    """

    def __init__(self) -> None:
        self._trajectories: list[AddressTrajectory] = []
        self._next_id = 1

    @staticmethod
    def decompose(text: str) -> tuple[AddressToken, ...]:
        return tuple(AddressToken(unit, _address("unit", unit)) for unit in _units(text))

    @staticmethod
    def _collapse_immediate_tokens(tokens: tuple[AddressToken, ...]) -> tuple[AddressToken, ...]:
        accepted: list[AddressToken] = []
        current: str | None = None
        for token in tokens:
            if token.address == current:
                continue
            accepted.append(token)
            current = token.address
        return tuple(accepted)

    def _append_trajectory(
        self,
        *,
        raw_text: str,
        addresses: tuple[str, ...],
        surfaces: tuple[str, ...],
    ) -> AddressTrajectory:
        if not addresses:
            raise ValueError("trajectory must contain at least one address")
        if len(addresses) != len(surfaces):
            raise ValueError("addresses and surfaces must have equal length")
        trajectory = AddressTrajectory(
            trajectory_id=f"AT{self._next_id}",
            raw_text=raw_text,
            addresses=addresses,
            surfaces=surfaces,
        )
        self._next_id += 1
        self._trajectories.append(trajectory)
        return trajectory

    def ingest(self, text: str) -> AddressTrajectory:
        tokens = self._collapse_immediate_tokens(self.decompose(text))
        if not tokens:
            raise ValueError("text must be non-empty")
        return self._append_trajectory(
            raw_text=text,
            addresses=tuple(token.address for token in tokens),
            surfaces=tuple(token.surface for token in tokens),
        )

    def ingest_address_stream(
        self,
        addresses: tuple[str, ...],
        *,
        surfaces: tuple[str, ...] | None = None,
        provenance: str = "",
    ) -> AddressTrajectory:
        """Ingest a modality-agnostic stream of precomputed addresses.

        Consecutive duplicate addresses are rejected before trajectory creation.
        The caller may provide human-readable surfaces for diagnostics; otherwise
        addresses themselves are used as surfaces. No semantic interpretation is
        performed here.
        """
        if not addresses:
            raise ValueError("address stream must be non-empty")
        if surfaces is None:
            surfaces = addresses
        if len(addresses) != len(surfaces):
            raise ValueError("addresses and surfaces must have equal length")

        kept_addresses: list[str] = []
        kept_surfaces: list[str] = []
        current: str | None = None
        for address, surface in zip(addresses, surfaces):
            if address == current:
                continue
            kept_addresses.append(address)
            kept_surfaces.append(surface)
            current = address

        return self._append_trajectory(
            raw_text=provenance,
            addresses=tuple(kept_addresses),
            surfaces=tuple(kept_surfaces),
        )

    def snapshot(self) -> tuple[AddressTrajectory, ...]:
        return tuple(self._trajectories)

    @classmethod
    def restore(cls, trajectories: tuple[AddressTrajectory, ...]) -> "AddressTrajectoryMemory":
        memory = cls()
        memory._trajectories = list(trajectories)
        max_id = 0
        for trajectory in trajectories:
            if trajectory.trajectory_id.startswith("AT"):
                try:
                    max_id = max(max_id, int(trajectory.trajectory_id[2:]))
                except ValueError:
                    pass
        memory._next_id = max_id + 1
        return memory

    @staticmethod
    def _ordered_overlap(query: tuple[str, ...], candidate: tuple[str, ...]) -> int:
        if not query or not candidate:
            return 0
        prev = [0] * (len(candidate) + 1)
        for q in query:
            curr = [0]
            for index, c in enumerate(candidate, start=1):
                if q == c:
                    curr.append(prev[index - 1] + 1)
                else:
                    curr.append(max(curr[-1], prev[index]))
            prev = curr
        return prev[-1]

    @staticmethod
    def _adjacency_overlap(query: tuple[str, ...], candidate: tuple[str, ...]) -> int:
        query_pairs = set(zip(query, query[1:]))
        candidate_pairs = set(zip(candidate, candidate[1:]))
        return len(query_pairs & candidate_pairs)

    def resolve(self, text: str, *, limit: int = 5) -> tuple[TrajectoryMatch, ...]:
        query_tokens = self._collapse_immediate_tokens(self.decompose(text))
        query = tuple(token.address for token in query_tokens)
        if not query:
            return ()
        query_set = set(query)
        matches: list[TrajectoryMatch] = []
        for trajectory in self._trajectories:
            candidate_set = set(trajectory.addresses)
            overlap = len(query_set & candidate_set)
            if overlap == 0:
                continue
            ordered_overlap = self._ordered_overlap(query, trajectory.addresses)
            adjacency_overlap = self._adjacency_overlap(query, trajectory.addresses)
            matches.append(
                TrajectoryMatch(
                    trajectory_id=trajectory.trajectory_id,
                    raw_text=trajectory.raw_text,
                    overlap=overlap,
                    ordered_overlap=ordered_overlap,
                    adjacency_overlap=adjacency_overlap,
                    query_coverage_num=overlap,
                    query_coverage_den=len(query_set),
                    terminal_surface=trajectory.surfaces[-1] if trajectory.surfaces else None,
                )
            )
        matches.sort(key=lambda item: item.structural_key, reverse=True)
        return tuple(matches[: max(0, limit)])
