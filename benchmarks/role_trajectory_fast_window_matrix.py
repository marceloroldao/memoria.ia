from __future__ import annotations

from collections import deque
import json

from memoria_resolutiva.trajectory_policy_gate_experimental import ExperimentalTrajectoryPolicyGate
from role_trajectory_partial_drift import temporal_state


BASE = 8
PHASE = 16
WINDOWS = (4, 8, 16, 32, 64)
NOISE_BURSTS = (0, 1, 2, 4)
OLD = ("fonte", "transmite", "sinal", "seguro", "destino")
ALT = ("fonte", "transmite", "pacote", "seguro", "destino")


def build_gate() -> tuple[ExperimentalTrajectoryPolicyGate, float]:
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
    return gate, gate._margin / 2.0


def delta(window) -> float:
    old = sum(1 for x in window if x == OLD)
    alt = sum(1 for x in window if x == ALT)
    total = old + alt
    return (old - alt) / total if total else 0.0


def append(window, token, n=1):
    for _ in range(n):
        window.append(token)


def first_crossing(window_size: int, deadband: float) -> dict:
    recent = deque([OLD] * window_size, maxlen=window_size)
    to_alt = None
    trace_alt = []
    for step in range(1, max(PHASE, window_size * 2) + 1):
        recent.append(ALT)
        d = delta(recent)
        state = temporal_state(d, deadband)
        trace_alt.append((step, d, state))
        if state == "regime_shift" and to_alt is None:
            to_alt = step
            break

    recent = deque([ALT] * window_size, maxlen=window_size)
    to_old = None
    trace_old = []
    for step in range(1, max(PHASE, window_size * 2) + 1):
        recent.append(OLD)
        d = delta(recent)
        state = temporal_state(d, deadband)
        trace_old.append((step, d, state))
        if state == "stable" and to_old is None:
            to_old = step
            break

    return {
        "window": window_size,
        "steps_to_alt": to_alt,
        "steps_to_old": to_old,
        "alt_crossing_fraction": (to_alt / window_size) if to_alt else None,
        "old_crossing_fraction": (to_old / window_size) if to_old else None,
    }


def noise_case(window_size: int, noise: int, deadband: float) -> dict:
    # Start with a fully stable recent state and inject a short contrary burst.
    recent = deque([OLD] * window_size, maxlen=window_size)
    append(recent, ALT, noise)
    d_old = delta(recent)
    old_state = temporal_state(d_old, deadband)

    # Symmetric check while ALT is dominant.
    recent = deque([ALT] * window_size, maxlen=window_size)
    append(recent, OLD, noise)
    d_alt = delta(recent)
    alt_state = temporal_state(d_alt, deadband)
    return {
        "window": window_size,
        "noise": noise,
        "old_delta_after_noise": d_old,
        "old_state_after_noise": old_state,
        "alt_delta_after_noise": d_alt,
        "alt_state_after_noise": alt_state,
        "old_not_flipped": old_state != "regime_shift",
        "alt_not_flipped": alt_state != "stable",
    }


def main() -> None:
    _, deadband = build_gate()
    response = [first_crossing(w, deadband) for w in WINDOWS]
    noise = [noise_case(w, n, deadband) for w in WINDOWS for n in NOISE_BURSTS if n < w]

    crossings_exist = all(r["steps_to_alt"] is not None and r["steps_to_old"] is not None for r in response)
    symmetry = all(r["steps_to_alt"] == r["steps_to_old"] for r in response)
    noise_monotonic = all(r["old_not_flipped"] and r["alt_not_flipped"] for r in noise)
    # Larger windows must not react in fewer absolute observations than smaller ones.
    reaction_monotonic = all(response[i]["steps_to_alt"] <= response[i + 1]["steps_to_alt"] for i in range(len(response) - 1))
    all_passed = crossings_exist and symmetry and noise_monotonic and reaction_monotonic

    result = {
        "experiment": "fast temporal window response/noise matrix",
        "deadband": deadband,
        "windows": list(WINDOWS),
        "noise_bursts": list(NOISE_BURSTS),
        "response": response,
        "noise": noise,
        "summary": {
            "crossings_exist": crossings_exist,
            "symmetric_response": symmetry,
            "noise_bursts_do_not_force_opposite_regime": noise_monotonic,
            "reaction_latency_monotonic_with_window": reaction_monotonic,
            "all_passed": all_passed,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
