from __future__ import annotations

from collections import deque
import json

from memoria_resolutiva.trajectory_policy_gate_experimental import ExperimentalTrajectoryPolicyGate
from role_trajectory_partial_drift import temporal_state


BASE = 8
WINDOWS = (4, 8, 16, 32, 64)
PHASES = (4, 8, 16, 32, 64)
OLD = ("fonte", "transmite", "sinal", "seguro", "destino")
ALT = ("fonte", "transmite", "pacote", "seguro", "destino")


def build_deadband() -> float:
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    families = [
        ("fonte", "transmite", "sinal", "seguro", "destino"),
        ("origem", "envia", "pacote", "cifrado", "servidor"),
        ("emissor", "remete", "dado", "protegido", "receptor"),
    ]
    gate.observe([" ".join(f) for f in families] * BASE)
    gate.register_role("source", ["fonte", "origem", "emissor"])
    gate.register_role("action", ["transmite", "envia", "remete"])
    gate.register_role("payload", ["sinal", "pacote", "dado"])
    gate.register_role("quality", ["seguro", "cifrado", "protegido"])
    gate.register_role("destination", ["destino", "servidor", "receptor"])
    gate.register_pattern(("source", "action", "payload", "quality", "destination"))
    if not gate.calibrate() or gate._margin is None:
        raise RuntimeError("calibration failed")
    return gate._margin / 2.0


def delta(window) -> float:
    old = sum(1 for x in window if x == OLD)
    alt = sum(1 for x in window if x == ALT)
    total = old + alt
    return (old - alt) / total if total else 0.0


def run_case(window_size: int, phase: int, deadband: float) -> dict:
    recent = deque([OLD] * window_size, maxlen=window_size)
    crossing = None
    min_delta = 1.0
    for step in range(1, phase + 1):
        recent.append(ALT)
        d = delta(recent)
        min_delta = min(min_delta, d)
        if crossing is None and temporal_state(d, deadband) == "regime_shift":
            crossing = step

    # Let the OLD regime return for the same duration and measure reversibility.
    recovery = None
    max_delta = min_delta
    for step in range(1, phase + 1):
        recent.append(OLD)
        d = delta(recent)
        max_delta = max(max_delta, d)
        if recovery is None and temporal_state(d, deadband) == "stable":
            recovery = step

    detects_within_phase = crossing is not None
    recovers_within_phase = recovery is not None
    return {
        "window": window_size,
        "phase": phase,
        "window_phase_ratio": window_size / phase,
        "crossing_step": crossing,
        "recovery_step": recovery,
        "crossing_phase_fraction": (crossing / phase) if crossing else None,
        "recovery_phase_fraction": (recovery / phase) if recovery else None,
        "detects_within_phase": detects_within_phase,
        "recovers_within_phase": recovers_within_phase,
        "min_delta_after_alt_phase": min_delta,
        "max_delta_after_recovery_phase": max_delta,
    }


def main() -> None:
    deadband = build_deadband()
    rows = [run_case(w, p, deadband) for p in PHASES for w in WINDOWS]

    # For each phase duration, shorter/equal windows should be no worse at detecting
    # the new regime than larger windows. This is a diagnostic invariant, not a
    # requirement that every window must detect every short phase.
    monotonic_by_phase = True
    for phase in PHASES:
        group = [r for r in rows if r["phase"] == phase]
        seen_failure = False
        for row in group:
            if not row["detects_within_phase"]:
                seen_failure = True
            elif seen_failure:
                monotonic_by_phase = False

    symmetric_when_detected = all(
        (not r["detects_within_phase"] and not r["recovers_within_phase"])
        or (r["detects_within_phase"] and r["recovers_within_phase"])
        for r in rows
    )

    # Estimate the largest window/phase ratio that still detects before the regime ends.
    detectable = [r for r in rows if r["detects_within_phase"]]
    undetectable = [r for r in rows if not r["detects_within_phase"]]
    max_detectable_ratio = max((r["window_phase_ratio"] for r in detectable), default=None)
    min_undetectable_ratio = min((r["window_phase_ratio"] for r in undetectable), default=None)

    all_passed = monotonic_by_phase and symmetric_when_detected and bool(detectable) and bool(undetectable)
    result = {
        "experiment": "regime phase duration x fast-window horizon",
        "deadband": deadband,
        "windows": list(WINDOWS),
        "phases": list(PHASES),
        "rows": rows,
        "summary": {
            "monotonic_by_phase": monotonic_by_phase,
            "symmetric_when_detected": symmetric_when_detected,
            "max_detectable_window_phase_ratio": max_detectable_ratio,
            "min_undetectable_window_phase_ratio": min_undetectable_ratio,
            "all_passed": all_passed,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
