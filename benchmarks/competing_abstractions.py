from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.factual_consolidation import FactualConsolidationService
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex


@dataclass(frozen=True, slots=True)
class CompetingAbstractionsResult:
    before_active: tuple[str, ...]
    after_active: tuple[str, ...]
    invalidated: tuple[str, ...]
    preserved: tuple[str, ...]
    unrelated_preserved: bool
    selective_invalidation_ok: bool


def _fact(core: EvidenceCore, prov: MemoryProvenanceIndex, mid: str, subject: str, predicate: str, obj: str) -> None:
    core.observe_relation(
        subject,
        predicate,
        obj,
        evidence_id=mid,
        source_text=f"{subject} {predicate} {obj}",
        provenance="competing-abstractions-benchmark",
        origin="user",
        namespace="compete",
    )
    prov.register(mid, source_type="user_assertion", namespace="compete")


def run_competing_abstractions() -> CompetingAbstractionsResult:
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    svc = FactualConsolidationService(core)

    # Shared support participates in two different abstractions.
    _fact(core, prov, "f_alt_cat", "Alt", "is_a", "cat")
    _fact(core, prov, "f_alt_pet", "Alt", "role", "pet")
    _fact(core, prov, "f_alt2_cat", "Alt2", "is_a", "cat")
    _fact(core, prov, "f_alt2_pet", "Alt2", "role", "pet")

    # Independent pattern must survive changes to Alt.
    _fact(core, prov, "f_mia_cat", "Mia", "is_a", "cat")
    _fact(core, prov, "f_nina_cat", "Nina", "is_a", "cat")

    svc.consolidate(
        memory_id="abs_pair_cats",
        subject="group:alt-alt2",
        predicate="kind",
        object="cat-pair",
        support_memory_ids=("f_alt_cat", "f_alt2_cat"),
        namespace="compete",
    )
    svc.consolidate(
        memory_id="abs_pair_pets",
        subject="group:alt-alt2",
        predicate="kind",
        object="pet-pair",
        support_memory_ids=("f_alt_pet", "f_alt2_pet"),
        namespace="compete",
    )
    svc.consolidate(
        memory_id="abs_other_cats",
        subject="group:mia-nina",
        predicate="kind",
        object="cat-pair",
        support_memory_ids=("f_mia_cat", "f_nina_cat"),
        namespace="compete",
    )

    ids = ("abs_pair_cats", "abs_pair_pets", "abs_other_cats")
    before = tuple(mid for mid in ids if svc.is_factually_active(mid, namespace="compete"))

    # Correct only Alt's species. This should invalidate the cat abstraction that
    # depends on f_alt_cat, but not the pet abstraction or the unrelated cat pair.
    _fact(core, prov, "f_alt_dog", "Alt", "is_a", "dog")
    prov.supersede("f_alt_cat", by_memory_id="f_alt_dog", namespace="compete")

    after = tuple(mid for mid in ids if svc.is_factually_active(mid, namespace="compete"))
    invalidated = tuple(mid for mid in before if mid not in after)
    preserved = tuple(mid for mid in after if mid in before)

    expected_after = {"abs_pair_pets", "abs_other_cats"}
    return CompetingAbstractionsResult(
        before_active=before,
        after_active=after,
        invalidated=invalidated,
        preserved=preserved,
        unrelated_preserved="abs_other_cats" in after,
        selective_invalidation_ok=(set(after) == expected_after and invalidated == ("abs_pair_cats",)),
    )


def main() -> None:
    print(json.dumps(asdict(run_competing_abstractions()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
