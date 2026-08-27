from __future__ import annotations

import itertools
import json

from memoria_resolutiva.trajectory_policy_gate_experimental import BOS, EOS, ExperimentalTrajectoryPolicyGate


def build_gate(base_repeat: int, conflict_repeat: int):
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    base = [
        "fonte transmite sinal destino",
        "origem envia pacote servidor",
        "emissor remete dado receptor",
    ]
    conflict = [
        "destino transmite sinal fonte",
        "servidor envia pacote origem",
        "receptor remete dado emissor",
    ]
    gate.observe(base * base_repeat + conflict * conflict_repeat)
    gate.register_role("source", ["fonte", "origem", "emissor"])
    gate.register_role("action", ["transmite", "envia", "remete"])
    gate.register_role("payload", ["sinal", "pacote", "dado"])
    gate.register_role("destination", ["destino", "servidor", "receptor"])
    gate.register_pattern(("source", "action", "payload", "destination"))
    return gate


def relation_purity(gate, left: str, offset: int, right: str) -> float:
    profile = gate.router.roles.memory.associator.profiles.get(left)
    if not profile:
        return 0.0
    wanted = profile.get((offset, right), 0)
    total = sum(count for (other_offset, token), count in profile.items() if token == right and other_offset != 0)
    return wanted / total if total else 0.0


def purity_score(gate, tokens: tuple[str, ...]) -> float:
    assoc = gate.router.roles.memory.associator
    seq = (BOS,) + tokens + (EOS,)
    values = []
    radius = assoc.radius
    for i, token in enumerate(seq):
        lo = max(0, i - radius)
        hi = min(len(seq), i + radius + 1)
        for j in range(lo, hi):
            if i == j:
                continue
            values.append(relation_purity(gate, token, j - i, seq[j]))
    return sum(values) / max(1, len(values))


def calibrate_purity(gate):
    concepts = gate.router.roles._concepts
    pattern = gate._patterns[0]
    role_by_anchor = {anchor: role for role in pattern for anchor in concepts[role]}
    rows = []
    max_anchors = max(len(concepts[role]) for role in pattern)
    for shift in range(max_anchors):
        seq = tuple(sorted(concepts[role])[shift % len(concepts[role])] for role in pattern)
        for perm in itertools.permutations(seq):
            roles = tuple(role_by_anchor[token] for token in perm)
            rows.append((roles == pattern, purity_score(gate, perm)))
    valid = [score for is_valid, score in rows if is_valid]
    invalid = [score for is_valid, score in rows if not is_valid]
    vmin, imax = min(valid), max(invalid)
    margin = vmin - imax
    return {
        "separable": margin > 0.0,
        "vmin": vmin,
        "imax": imax,
        "margin": margin,
        "threshold": (vmin + imax) / 2.0 if margin > 0 else None,
    }


def main():
    rows = []
    for conflict_repeat in (0, 1, 2, 4, 8, 16, 32):
        gate = build_gate(8, conflict_repeat)
        calibration = calibrate_purity(gate)
        forward = purity_score(gate, ("fonte", "transmite", "sinal", "destino"))
        reverse = purity_score(gate, ("destino", "transmite", "sinal", "fonte"))
        threshold = calibration["threshold"]
        rows.append({
            "base_repeat": 8,
            "conflict_repeat": conflict_repeat,
            "calibration": calibration,
            "forward_score": forward,
            "reverse_score": reverse,
            "forward_above_boundary": bool(threshold is not None and forward > threshold),
            "reverse_above_boundary": bool(threshold is not None and reverse > threshold),
        })
    print(json.dumps({
        "experiment": "calibrated directional purity under incremental conflict",
        "principle": "edge evidence is normalized over all observed offsets for the same token pair",
        "rows": rows,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
