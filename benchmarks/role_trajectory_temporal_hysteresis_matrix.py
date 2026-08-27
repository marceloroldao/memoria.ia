from __future__ import annotations

import json

from memoria_resolutiva.trajectory_policy_gate_experimental import BOS, EOS, ExperimentalTrajectoryPolicyGate


def relation_purity(gate, left: str, offset: int, right: str) -> float:
    profile = gate.router.roles.memory.associator.profiles.get(left)
    if not profile:
        return 0.0
    wanted = profile.get((offset, right), 0)
    total = sum(count for (other_offset, token), count in profile.items() if token == right and other_offset != 0)
    return wanted / total if total else 0.0


def purity_score(gate, tokens: tuple[str, ...]) -> float:
    seq = (BOS,) + tokens + (EOS,)
    radius = gate.router.roles.memory.associator.radius
    values = []
    for i, token in enumerate(seq):
        lo = max(0, i - radius)
        hi = min(len(seq), i + radius + 1)
        for j in range(lo, hi):
            if i != j:
                values.append(relation_purity(gate, token, j - i, seq[j]))
    return sum(values) / max(1, len(values))


def domain(length: int):
    roles = [f"r{i}" for i in range(length)]
    a = [f"a{i}" for i in range(length)]
    b = [f"b{i}" for i in range(length)]
    c = [f"c{i}" for i in range(length)]
    forward = [" ".join(a), " ".join(b), " ".join(c)]
    reverse = [" ".join(reversed(a)), " ".join(reversed(b)), " ".join(reversed(c))]
    anchors = {role: [a[i], b[i], c[i]] for i, role in enumerate(roles)}
    return roles, a, forward, reverse, anchors


def build(length: int, base_repeat: int, conflict_repeat: int):
    roles, probe, forward, reverse, anchors = domain(length)
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    gate.observe(forward * base_repeat + reverse * conflict_repeat)
    for role in roles:
        gate.register_role(role, anchors[role])
    gate.register_pattern(tuple(roles))
    return gate, tuple(probe), tuple(reversed(probe))


def temporal_state(delta: float, deadband: float) -> str:
    if delta > deadband:
        return "stable"
    if delta < -deadband:
        return "regime_shift"
    return "uncertain"


def run_case(length: int, base_repeat: int):
    baseline, _forward_tokens, _reverse_tokens = build(length, base_repeat, 0)
    if not baseline.calibrate():
        return {"length": length, "base_repeat": base_repeat, "calibrated": False}

    # `gate._margin` is the full gap between the closest valid and invalid
    # calibration examples. Because the calibrated threshold is the midpoint
    # of that gap, the confidence distance to either class frontier is half it.
    separation_gap = baseline._margin
    deadband = separation_gap / 2.0

    raw_conflicts = (
        0,
        max(1, base_repeat // 4),
        max(1, base_repeat // 2),
        base_repeat,
        base_repeat * 2,
        base_repeat * 4,
    )
    conflict_points = sorted(set(raw_conflicts))
    points = []
    for conflict_repeat in conflict_points:
        gate, forward_tokens, reverse_tokens = build(length, base_repeat, conflict_repeat)
        forward = purity_score(gate, forward_tokens)
        reverse = purity_score(gate, reverse_tokens)
        delta = forward - reverse
        points.append({
            "conflict_repeat": conflict_repeat,
            "ratio": conflict_repeat / base_repeat,
            "forward": forward,
            "reverse": reverse,
            "delta": delta,
            "state": temporal_state(delta, deadband),
        })

    rank = {"stable": 0, "uncertain": 1, "regime_shift": 2}
    monotonic = all(rank[points[i]["state"]] <= rank[points[i + 1]["state"]] for i in range(len(points) - 1))
    equal_point = next(point for point in points if point["ratio"] == 1.0)
    strongest = points[-1]
    return {
        "length": length,
        "base_repeat": base_repeat,
        "calibrated": True,
        "separation_gap": separation_gap,
        "temporal_deadband": deadband,
        "points": points,
        "state_progression_monotonic": monotonic,
        "starts_stable": points[0]["state"] == "stable",
        "equal_support_uncertain": equal_point["state"] == "uncertain",
        "strong_reverse_regime_shift": strongest["state"] == "regime_shift",
    }


def case_passes(row: dict) -> bool:
    return bool(
        row.get("calibrated")
        and row.get("state_progression_monotonic")
        and row.get("starts_stable")
        and row.get("equal_support_uncertain")
        and row.get("strong_reverse_regime_shift")
    )


def main():
    rows = [run_case(length, base) for length in (4, 5, 6) for base in (2, 4, 8, 16)]
    passed = all(case_passes(row) for row in rows)
    print(json.dumps({
        "experiment": "temporal hysteresis scale matrix",
        "principle": "use half of the calibrated structural separation gap as the temporal confidence dead-band",
        "rows": rows,
        "summary": {
            "cases": len(rows),
            "passed": sum(1 for row in rows if case_passes(row)),
            "all_passed": passed,
        },
    }, ensure_ascii=False, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
