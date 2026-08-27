from __future__ import annotations

import json

from role_trajectory_partial_drift import build_gate


def slot_support(gate, left: str, offset: int, right: str) -> float:
    profile = gate.router.roles.memory.associator.profiles.get(left)
    if not profile:
        return 0.0
    wanted = profile.get((offset, right), 0)
    total = sum(count for (other_offset, _token), count in profile.items() if other_offset == offset)
    return wanted / total if total else 0.0


def edge_delta(gate, kind: str) -> tuple[float, dict]:
    if kind == "boundary":
        # quality -> destination competes directly at +1
        left, offset, old, new = "seguro", 1, "destino", "servidor"
    else:
        # action -> payload competes directly at +1
        left, offset, old, new = "transmite", 1, "sinal", "pacote"
    old_s = slot_support(gate, left, offset, old)
    new_s = slot_support(gate, left, offset, new)
    return old_s - new_s, {
        "left": left, "offset": offset, "old": old, "new": new,
        "old_support": old_s, "new_support": new_s,
    }


def main():
    cases = []
    for kind in ("boundary", "internal"):
        clean, _, _ = build_gate(kind, 0)
        assert clean.calibrate()
        deadband = clean._margin / 2.0
        rows = []
        for n in (0, 1, 2, 4, 8, 16, 32):
            gate, _, _ = build_gate(kind, n)
            delta, edge = edge_delta(gate, kind)
            state = "stable" if delta > deadband else "regime_shift" if delta < -deadband else "uncertain"
            rows.append({"drift_repeat": n, "ratio": n/8.0, "delta": delta, "state": state, **edge})
        cases.append({"kind": kind, "deadband": deadband, "rows": rows})
    print(json.dumps({"experiment":"slot-conditioned temporal support","cases":cases}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
