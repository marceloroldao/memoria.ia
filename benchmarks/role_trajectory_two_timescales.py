from __future__ import annotations

from collections import deque
import json
import traceback

from memoria_resolutiva.trajectory_policy_gate_experimental import ExperimentalTrajectoryPolicyGate
from role_trajectory_slot_support import slot_support
from role_trajectory_partial_drift import temporal_state


BASE = 8
PHASE = 16
CYCLES = 8
FAST_WINDOW = 16

OLD = ("fonte", "transmite", "sinal", "seguro", "destino")
ALT = ("fonte", "transmite", "pacote", "seguro", "destino")


def build_gate() -> ExperimentalTrajectoryPolicyGate:
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    families = [
        ("fonte", "transmite", "sinal", "seguro", "destino"),
        ("origem", "envia", "pacote", "cifrado", "servidor"),
        ("emissor", "remete", "dado", "protegido", "receptor"),
    ]
    gate.observe([" ".join(family) for family in families] * BASE)
    gate.register_role("source", ["fonte", "origem", "emissor"])
    gate.register_role("action", ["transmite", "envia", "remete"])
    gate.register_role("payload", ["sinal", "pacote", "dado"])
    gate.register_role("quality", ["seguro", "cifrado", "protegido"])
    gate.register_role("destination", ["destino", "servidor", "receptor"])
    gate.register_pattern(("source", "action", "payload", "quality", "destination"))
    if not gate.calibrate():
        raise RuntimeError("trajectory gate calibration failed")
    return gate


def fast_delta(window: deque[tuple[str, ...]]) -> float:
    old = 0
    new = 0
    for tokens in window:
        if len(tokens) >= 3 and tokens[1] == "transmite":
            if tokens[2] == "sinal":
                old += 1
            elif tokens[2] == "pacote":
                new += 1
    total = old + new
    return (old - new) / total if total else 0.0


def slow_delta(gate: ExperimentalTrajectoryPolicyGate) -> float:
    return slot_support(gate, "transmite", 1, "sinal") - slot_support(gate, "transmite", 1, "pacote")


def snapshot(gate, recent, label: str, deadband: float) -> dict:
    slow = slow_delta(gate)
    fast = fast_delta(recent)
    return {
        "label": label,
        "slow_delta": slow,
        "fast_delta": fast,
        "slow_state": temporal_state(slow, deadband),
        "fast_state": temporal_state(fast, deadband),
        "deadband": deadband,
        "historical_old_support": slot_support(gate, "transmite", 1, "sinal"),
        "historical_new_support": slot_support(gate, "transmite", 1, "pacote"),
        "unchanged_support": slot_support(gate, "fonte", 1, "transmite"),
    }


def observe_phase(gate, recent, tokens: tuple[str, ...], repeats: int) -> None:
    sentence = " ".join(tokens)
    gate.observe([sentence] * repeats)
    for _ in range(repeats):
        recent.append(tokens)


def run() -> bool:
    gate = build_gate()
    # Calibration describes the slow structural geometry. New temporal observations
    # invalidate the gate's live calibration on purpose, so the temporal experiment
    # keeps this initial structural reference frozen instead of recalibrating it.
    structural_margin = gate._margin
    if structural_margin is None:
        raise RuntimeError("calibrated gate did not expose a structural margin")
    deadband = structural_margin / 2.0

    recent: deque[tuple[str, ...]] = deque(maxlen=FAST_WINDOW)
    for _ in range(BASE):
        recent.append(OLD)

    rows = [snapshot(gate, recent, "baseline", deadband)]
    for cycle in range(1, CYCLES + 1):
        observe_phase(gate, recent, ALT, PHASE)
        rows.append(snapshot(gate, recent, f"cycle_{cycle}_B", deadband))
        observe_phase(gate, recent, OLD, PHASE)
        rows.append(snapshot(gate, recent, f"cycle_{cycle}_A", deadband))

    b_rows = [row for row in rows if row["label"].endswith("_B")]
    a_rows = [row for row in rows if row["label"].endswith("_A")]
    fast_tracks_present = all(row["fast_state"] == "regime_shift" and row["fast_delta"] < 0 for row in b_rows) and all(
        row["fast_state"] == "stable" and row["fast_delta"] > 0 for row in a_rows
    )
    historical_inertia_visible = abs(b_rows[-1]["slow_delta"]) < abs(b_rows[0]["slow_delta"]) and abs(a_rows[-1]["slow_delta"]) < abs(a_rows[0]["slow_delta"])
    history_preserved = all(row["historical_old_support"] > 0 and row["historical_new_support"] > 0 for row in rows[1:])
    unrelated_relation_stable = all(row["unchanged_support"] >= 0.999999 for row in rows)
    all_passed = fast_tracks_present and historical_inertia_visible and history_preserved and unrelated_relation_stable

    result = {
        "experiment": "dual temporal scales under recurrent cycles",
        "principle": "slow cumulative history preserves long-term evidence while a bounded recent window tracks current state",
        "cycles": CYCLES,
        "phase_repeats": PHASE,
        "fast_window": FAST_WINDOW,
        "frozen_structural_margin": structural_margin,
        "deadband": deadband,
        "rows": rows,
        "summary": {
            "fast_tracks_present": fast_tracks_present,
            "historical_inertia_visible": historical_inertia_visible,
            "history_preserved": history_preserved,
            "unrelated_relation_stable": unrelated_relation_stable,
            "all_passed": all_passed,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return all_passed


def main() -> None:
    try:
        passed = run()
    except Exception as exc:
        print(json.dumps({
            "experiment": "dual temporal scales under recurrent cycles",
            "error": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False, indent=2))
        raise
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
