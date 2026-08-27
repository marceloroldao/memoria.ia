from __future__ import annotations

import json

from memoria_resolutiva.trajectory_policy_gate_experimental import ExperimentalTrajectoryPolicyGate
from role_trajectory_slot_support import slot_support
from role_trajectory_partial_drift import temporal_state


BASE = 8
LEVELS = (4, 8, 16)  # 0.5x, 1x, 2x
EPS = 1e-12


def build_gate(payload_n: int, destination_n: int):
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    family_a = ("fonte", "transmite", "sinal", "seguro", "destino")
    family_b = ("origem", "envia", "pacote", "cifrado", "servidor")
    family_c = ("emissor", "remete", "dado", "protegido", "receptor")
    payload_alt = ("fonte", "transmite", "pacote", "seguro", "destino")
    destination_alt = ("fonte", "transmite", "sinal", "seguro", "servidor")

    obs = [" ".join(family_a), " ".join(family_b), " ".join(family_c)] * BASE
    obs += [" ".join(payload_alt)] * payload_n
    obs += [" ".join(destination_alt)] * destination_n
    gate.observe(obs)

    gate.register_role("source", ["fonte", "origem", "emissor"])
    gate.register_role("action", ["transmite", "envia", "remete"])
    gate.register_role("payload", ["sinal", "pacote", "dado"])
    gate.register_role("quality", ["seguro", "cifrado", "protegido"])
    gate.register_role("destination", ["destino", "servidor", "receptor"])
    gate.register_pattern(("source", "action", "payload", "quality", "destination"))
    return gate


def delta(gate, left: str, old: str, new: str) -> float:
    return slot_support(gate, left, 1, old) - slot_support(gate, left, 1, new)


def nonincreasing(values: list[float]) -> bool:
    return all(b <= a + EPS for a, b in zip(values, values[1:]))


def main():
    clean = build_gate(0, 0)
    assert clean.calibrate()
    deadband = clean._margin / 2.0

    cells = {}
    rows = []
    for payload_n in LEVELS:
        for destination_n in LEVELS:
            gate = build_gate(payload_n, destination_n)
            p_delta = delta(gate, "transmite", "sinal", "pacote")
            d_delta = delta(gate, "seguro", "destino", "servidor")
            p_state = temporal_state(p_delta, deadband)
            d_state = temporal_state(d_delta, deadband)
            anchor = slot_support(gate, "fonte", 1, "transmite")
            cell = {
                "payload_n": payload_n,
                "payload_ratio": payload_n / BASE,
                "payload_delta": p_delta,
                "payload_state": p_state,
                "destination_n": destination_n,
                "destination_ratio": destination_n / BASE,
                "destination_delta": d_delta,
                "destination_state": d_state,
                "unchanged_anchor_support": anchor,
                "state_vector": [p_state, d_state],
            }
            cells[(payload_n, destination_n)] = cell
            rows.append(cell)

    # The two slots share trajectory context, so their absolute thresholds are coupled.
    # What must remain local is the direction of evidence: increasing evidence for one
    # alternative must monotonically weaken that slot's old relation for every fixed
    # level of the other slot. Stable unrelated anchors must remain unchanged.
    payload_slices = []
    for destination_n in LEVELS:
        values = [cells[(p, destination_n)]["payload_delta"] for p in LEVELS]
        payload_slices.append({
            "destination_n": destination_n,
            "values": values,
            "monotonic": nonincreasing(values),
        })

    destination_slices = []
    for payload_n in LEVELS:
        values = [cells[(payload_n, d)]["destination_delta"] for d in LEVELS]
        destination_slices.append({
            "payload_n": payload_n,
            "values": values,
            "monotonic": nonincreasing(values),
        })

    anchors_stable = all(r["unchanged_anchor_support"] >= 0.999999 for r in rows)
    own_axis_monotonic = all(x["monotonic"] for x in payload_slices + destination_slices)
    all_passed = anchors_stable and own_axis_monotonic

    result = {
        "experiment": "asynchronous slot drift matrix",
        "principle": "temporal evidence is locally directional but context-coupled: shared trajectory context may shift absolute thresholds while each slot must remain monotonic on its own evidence axis",
        "deadband": deadband,
        "rows": rows,
        "payload_axis_checks": payload_slices,
        "destination_axis_checks": destination_slices,
        "summary": {
            "cells": len(rows),
            "anchors_stable": anchors_stable,
            "own_axis_monotonic": own_axis_monotonic,
            "all_passed": all_passed,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
