from __future__ import annotations

import json

from role_trajectory_directional_purity import build_gate, calibrate_purity, purity_score


def state(delta: float, structural_margin: float) -> str:
    if delta > structural_margin:
        return "stable"
    if delta < -structural_margin:
        return "regime_shift"
    return "uncertain"


def main():
    baseline = build_gate(8, 0)
    base_cal = calibrate_purity(baseline)
    assert base_cal["separable"]
    structural_margin = base_cal["margin"]

    forward_tokens = ("fonte", "transmite", "sinal", "destino")
    reverse_tokens = ("destino", "transmite", "sinal", "fonte")
    rows = []
    for conflict_repeat in (0, 1, 2, 4, 8, 16, 32):
        gate = build_gate(8, conflict_repeat)
        forward = purity_score(gate, forward_tokens)
        reverse = purity_score(gate, reverse_tokens)
        delta = forward - reverse
        rows.append({
            "base_repeat": 8,
            "conflict_repeat": conflict_repeat,
            "forward_score": forward,
            "reverse_score": reverse,
            "delta": delta,
            "structural_margin": structural_margin,
            "temporal_state": state(delta, structural_margin),
        })

    expected = {
        0: "stable",
        1: "stable",
        2: "stable",
        4: "uncertain",
        8: "uncertain",
        16: "uncertain",
        32: "regime_shift",
    }
    matches = all(row["temporal_state"] == expected[row["conflict_repeat"]] for row in rows)
    print(json.dumps({
        "experiment": "structural-margin temporal hysteresis",
        "principle": "freeze structural calibration; use its learned separation margin as a dead-band for directional temporal conflict",
        "baseline_structural_margin": structural_margin,
        "rows": rows,
        "expected_curve_matches": matches,
    }, ensure_ascii=False, indent=2))
    if not matches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
