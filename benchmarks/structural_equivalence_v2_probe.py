from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from hashlib import sha256


@dataclass(frozen=True)
class Observation:
    signature: tuple[str, ...]
    terminal: str
    lineage: str


def sid(signature: tuple[str, ...]) -> str:
    payload = "\x1f".join(signature).encode("utf-8")
    return sha256(payload).hexdigest()[:16]


def support(observations: list[Observation], a: tuple[str, ...], b: tuple[str, ...]):
    a_id, b_id = sid(a), sid(b)
    by_sig: dict[str, dict[str, set[str]]] = {}
    for obs in observations:
        by_sig.setdefault(sid(obs.signature), {}).setdefault(obs.terminal, set()).add(obs.lineage)
    shared = set(by_sig.get(a_id, {})) & set(by_sig.get(b_id, {}))
    independent = 0
    evidence = []
    for terminal in sorted(shared):
        left = by_sig[a_id][terminal]
        right = by_sig[b_id][terminal]
        # Pair only genuinely independent lineages.
        pairs = {(x, y) for x in left for y in right if x != y}
        if pairs:
            independent += min(len(left), len(right))
            evidence.append({"terminal": terminal, "left": sorted(left), "right": sorted(right)})
    return {
        "a": a_id,
        "b": b_id,
        "shared_terminals": sorted(shared),
        "independent_convergence": independent,
        "supported": independent >= 2,
        "evidence": evidence,
    }


def main() -> None:
    a = ("sig:a",)
    b = ("sig:b",)
    c = ("sig:c",)

    positive = [
        Observation(a, "region:lotus", "L1"),
        Observation(b, "region:lotus", "L2"),
        Observation(a, "region:lotus", "L3"),
        Observation(b, "region:lotus", "L4"),
    ]
    copied = [Observation(a, "region:x", "same") for _ in range(100)] + [Observation(b, "region:x", "same") for _ in range(100)]
    accidental = [Observation(a, "region:y", "A1"), Observation(c, "region:y", "C1")]

    result = {
        "schema": "memoria.structural-equivalence.v2.probe.1",
        "constraints": {
            "semantic_regex": False,
            "domain_vocabulary": False,
            "embeddings": False,
            "neural_networks": False,
            "learned_weights": False,
        },
        "positive": support(positive, a, b),
        "same_lineage_repetition": support(copied, a, b),
        "single_accidental_convergence": support(accidental, a, c),
    }
    result["checks"] = {
        "positive_supported": result["positive"]["supported"],
        "same_lineage_not_supported": not result["same_lineage_repetition"]["supported"],
        "single_accidental_not_supported": not result["single_accidental_convergence"]["supported"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(result["checks"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
